from __future__ import annotations

import datetime
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import db
import momentum_screen
import yfinance as yf
from sources import nse as nse_source
from sources import prices as prices_source


def _clean_numeric(value: object) -> "float | None":
    """None unless value is a finite (non-NaN) int/float — guards against
    yfinance returning NaN for a field, which isinstance() alone wouldn't
    catch (NaN is a float) and which must not silently reach a quality
    gate as a real value or a stored column as an invalid NaN token that
    breaks JSON parsing on the frontend."""
    if isinstance(value, (int, float)) and value == value:
        return float(value)
    return None


def _fetch_fundamentals(yf_symbol: str) -> dict:
    """Best-effort — yfinance .info coverage for NSE tickers is
    inconsistent; any missing/NaN field is None, never assumed to fail a
    gate (see momentum_screen.evaluate_quality_gates)."""
    try:
        info = yf.Ticker(yf_symbol).info
        if not isinstance(info, dict):
            raise ValueError("`.info` did not return a dict")
    except Exception:
        return {
            "market_cap_cr": None, "promoter_holding_pct": None,
            "debt_to_equity": None, "earnings_growth_pct": None,
            "sector": None, "pe_ratio": None,
        }

    market_cap = _clean_numeric(info.get("marketCap"))
    market_cap_cr = (market_cap / 1e7) if market_cap is not None else None

    promoter_holding = _clean_numeric(info.get("heldPercentInsiders"))
    promoter_holding_pct = (promoter_holding * 100) if promoter_holding is not None else None

    debt_to_equity_raw = _clean_numeric(info.get("debtToEquity"))
    # ASSUMPTION, not independently verified from this environment:
    # yfinance commonly reports debtToEquity as a percentage (e.g. 45.2
    # meaning a ratio of 0.452), not a raw ratio — normalized here to
    # match this project's <1.0 threshold convention. If live data proves
    # this wrong for NSE tickers specifically, the gate's threshold will
    # silently almost-always-pass or almost-always-fail — see the setup
    # checklist, which flags this as a first-deploy verification item
    # alongside the ASM/GSM URLs.
    debt_to_equity = (debt_to_equity_raw / 100) if debt_to_equity_raw is not None else None

    earnings_growth = _clean_numeric(info.get("earningsGrowth"))
    earnings_growth_pct = (earnings_growth * 100) if earnings_growth is not None else None

    sector = info.get("sector")
    sector = sector if isinstance(sector, str) and sector else None

    return {
        "market_cap_cr": market_cap_cr,
        "promoter_holding_pct": promoter_holding_pct,
        "debt_to_equity": debt_to_equity,
        "earnings_growth_pct": earnings_growth_pct,
        "sector": sector,
        "pe_ratio": _clean_numeric(info.get("trailingPE")),
    }


def _fetch_one(bare_symbol: str, nse_flags: dict, bhavcopy: dict, trading_day: datetime.date) -> tuple:
    yf_symbol = f"{bare_symbol}.NS"
    ohlcv = prices_source.fetch_ohlcv_history(yf_symbol)
    fundamentals = _fetch_fundamentals(yf_symbol)

    bhav_row = bhavcopy.get(bare_symbol)
    volumes = ohlcv["volume"]
    deliveries = None
    latest_date = ohlcv["dates"][-1] if ohlcv.get("dates") else None
    if bhav_row and latest_date == trading_day.isoformat():
        # Only attach bhavcopy-sourced volume/delivery when yfinance's own
        # latest row is actually the same trading day as the bhavcopy —
        # otherwise (e.g. the bhavcopy hasn't published yet and
        # latest_trading_day() fell back a day) they'd be silently
        # misaligned, corrupting volume_increase and delivery_pct.
        deliveries = [bhav_row["delivery_pct"]]
        if bhav_row.get("volume"):
            volumes = volumes[:-1] + [bhav_row["volume"]]

    avg_price = sum(ohlcv["close"][-10:]) / len(ohlcv["close"][-10:])
    avg_volume = sum(volumes[-10:]) / len(volumes[-10:])
    avg_daily_traded_value_cr = (avg_price * avg_volume) / 1e7
    if avg_daily_traded_value_cr != avg_daily_traded_value_cr:  # NaN check
        avg_daily_traded_value_cr = None

    metrics = momentum_screen.build_symbol_metrics(
        closes=ohlcv["close"],
        volumes=volumes,
        deliveries=deliveries,
        fundamentals=fundamentals,
        nse_flags=nse_flags,
        avg_daily_traded_value=avg_daily_traded_value_cr,
    )
    metrics["sector"] = fundamentals["sector"]
    metrics["pe_ratio"] = fundamentals["pe_ratio"]
    return bare_symbol, metrics


def run_screen() -> dict:
    session = nse_source.new_session()

    try:
        symbols = [s.strip().upper() for s in nse_source.fetch_nifty200_symbols(session)]
    except RuntimeError as exc:
        # The universe itself is the one NSE source with no fallback —
        # without it there is nothing to screen at all.
        raise RuntimeError(f"Cannot screen without the Nifty 200 universe: {exc}") from exc

    degraded_sources: list = []

    def _safe_fetch(label: str, fn):
        try:
            return fn()
        except RuntimeError as exc:
            degraded_sources.append({"source": label, "error": str(exc)})
            return None

    fo_ban = _safe_fetch("fo_ban", lambda: nse_source.fetch_fo_ban_symbols(session))
    asm = _safe_fetch("asm", lambda: nse_source.fetch_asm_symbols(session))
    gsm = _safe_fetch("gsm", lambda: nse_source.fetch_gsm_symbols(session))

    try:
        trading_day, bhavcopy = nse_source.latest_trading_day(session)
    except RuntimeError as exc:
        degraded_sources.append({"source": "bhavcopy", "error": str(exc)})
        trading_day, bhavcopy = datetime.date.today(), {}

    pool: dict = {}
    failed: list = []
    with ThreadPoolExecutor(max_workers=10) as pool_executor:
        nse_flags_by_symbol = {
            symbol: {
                "asm": (symbol in asm) if asm is not None else None,
                "gsm": (symbol in gsm) if gsm is not None else None,
                "fo_ban": (symbol in fo_ban) if fo_ban is not None else None,
            }
            for symbol in symbols
        }
        futures = {
            pool_executor.submit(_fetch_one, symbol, nse_flags_by_symbol[symbol], bhavcopy, trading_day): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                bare_symbol, metrics = future.result()
                pool[bare_symbol] = metrics
            except Exception as exc:
                failed.append({"symbol": symbol, "error": str(exc)})

    scores = momentum_screen.compute_momentum_scores(pool)

    rows = []
    for symbol, metrics in pool.items():
        rows.append((
            trading_day,
            symbol,
            metrics.get("sector"),
            metrics.get("pe_ratio"),
            metrics["current_price"],
            metrics["returns"]["return_1d"],
            metrics["returns"]["return_3d"],
            metrics["returns"]["return_7d"],
            metrics["returns"]["return_1m"],
            metrics["quality_gates"]["passes"],
            metrics["ema_trend"]["passes"],
            json.dumps(metrics["quality_gates"]["detail"]),
            scores.get(symbol),
            metrics["volume_confirmation"],
            metrics["risk"]["stop_loss"],
            metrics["risk"]["target_low"],
            metrics["risk"]["target_high"],
        ))

    if not rows:
        raise RuntimeError(
            f"No symbols were successfully scored for {trading_day.isoformat()} — "
            "refusing to touch momentum_rankings"
        )

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM momentum_rankings WHERE run_date = %s", (trading_day,))
            cur.executemany(
                "INSERT INTO momentum_rankings "
                "(run_date, symbol, sector, pe_ratio, current_price, return_1d, return_3d, "
                "return_7d, return_1m, passes_quality_gates, passes_trend_gate, "
                "quality_gate_detail, momentum_score, volume_confirmation, stop_loss, "
                "target_low, target_high) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "run_date": trading_day.isoformat(),
        "symbols_scored": len(rows),
        "symbols_failed": len(failed),
        "failed": failed,
        "degraded_sources": degraded_sources,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cron_secret = os.environ.get("CRON_SECRET")
        if cron_secret:
            auth_header = self.headers.get("Authorization", "")
            if auth_header != f"Bearer {cron_secret}":
                self._send_json(401, {"error": "Unauthorized"})
                return

        try:
            payload = run_screen()
            status = 200
        except Exception as exc:
            payload = {"error": str(exc)}
            status = 500
        self._send_json(status, payload)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
