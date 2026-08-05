from __future__ import annotations

import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import db
import momentum_screen
import yfinance as yf
from sources import nse as nse_source
from sources import prices as prices_source


def _fetch_fundamentals(yf_symbol: str) -> dict:
    """Best-effort — yfinance .info coverage for NSE tickers is
    inconsistent; any missing field is None, never assumed to fail a
    gate (see momentum_screen.evaluate_quality_gates)."""
    try:
        info = yf.Ticker(yf_symbol).info
    except Exception:
        return {
            "market_cap_cr": None, "promoter_holding_pct": None,
            "debt_to_equity": None, "earnings_growth_pct": None,
            "sector": None, "pe_ratio": None,
        }

    market_cap = info.get("marketCap")
    market_cap_cr = (market_cap / 1e7) if isinstance(market_cap, (int, float)) else None
    promoter_holding = info.get("heldPercentInsiders")
    promoter_holding_pct = (promoter_holding * 100) if isinstance(promoter_holding, (int, float)) else None
    debt_to_equity_raw = info.get("debtToEquity")
    # ASSUMPTION, not independently verified from this environment:
    # yfinance commonly reports debtToEquity as a percentage (e.g. 45.2
    # meaning a ratio of 0.452), not a raw ratio — normalized here to
    # match this project's <1.0 threshold convention. If live data proves
    # this wrong for NSE tickers specifically, the gate's threshold will
    # silently almost-always-pass or almost-always-fail — see Task 9's
    # setup checklist, which flags this as a first-deploy verification
    # item alongside the ASM/GSM URLs.
    debt_to_equity = (debt_to_equity_raw / 100) if isinstance(debt_to_equity_raw, (int, float)) else None
    earnings_growth = info.get("earningsGrowth")
    earnings_growth_pct = (earnings_growth * 100) if isinstance(earnings_growth, (int, float)) else None

    return {
        "market_cap_cr": market_cap_cr,
        "promoter_holding_pct": promoter_holding_pct,
        "debt_to_equity": debt_to_equity,
        "earnings_growth_pct": earnings_growth_pct,
        "sector": info.get("sector"),
        "pe_ratio": info.get("trailingPE"),
    }


def _fetch_one(bare_symbol: str, nse_flags: dict, bhavcopy: dict) -> tuple:
    yf_symbol = f"{bare_symbol}.NS"
    ohlcv = prices_source.fetch_ohlcv_history(yf_symbol)
    fundamentals = _fetch_fundamentals(yf_symbol)

    bhav_row = bhavcopy.get(bare_symbol)
    deliveries = [bhav_row["delivery_pct"]] if bhav_row else None
    volumes = ohlcv["volume"]
    if bhav_row and bhav_row.get("volume"):
        # Prefer bhavcopy's official traded quantity for today's volume
        # figure over yfinance's, which can lag/differ for NSE tickers.
        volumes = volumes[:-1] + [bhav_row["volume"]]

    avg_price = sum(ohlcv["close"][-10:]) / len(ohlcv["close"][-10:])
    avg_volume = sum(volumes[-10:]) / len(volumes[-10:])
    avg_daily_traded_value_cr = (avg_price * avg_volume) / 1e7

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
    symbols = nse_source.fetch_nifty200_symbols()

    fo_ban = nse_source.fetch_fo_ban_symbols()
    asm = nse_source.fetch_asm_symbols()
    gsm = nse_source.fetch_gsm_symbols()
    trading_day = nse_source.latest_trading_day()
    bhavcopy = nse_source.fetch_bhavcopy(trading_day)

    pool: dict = {}
    failed: list = []
    with ThreadPoolExecutor(max_workers=10) as pool_executor:
        nse_flags_by_symbol = {
            symbol: {"asm": symbol in asm, "gsm": symbol in gsm, "fo_ban": symbol in fo_ban}
            for symbol in symbols
        }
        futures = {
            pool_executor.submit(_fetch_one, symbol, nse_flags_by_symbol[symbol], bhavcopy): symbol
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

    return {"run_date": trading_day.isoformat(), "symbols_scored": len(rows), "symbols_failed": len(failed), "failed": failed}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = run_screen()
            status = 200
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
