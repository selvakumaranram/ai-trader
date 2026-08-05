from __future__ import annotations

import csv
import datetime
import io
import re
from typing import Dict, List, Set, Tuple

import requests

_BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/csv,application/csv,*/*",
    "Referer": "https://www.nseindia.com/",
}

_HOMEPAGE_URL = "https://www.nseindia.com/"
_NIFTY200_URL = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
_FO_BAN_URL = "https://nsearchives.nseindia.com/content/fo/fo_secban.csv"
# NOTE: these two ASM/GSM URLs follow NSE's established archives.nseindia.com /
# nsearchives.nseindia.com path convention but are NOT independently confirmed against
# the live site from this environment. Verify these against NSE's current Surveillance
# pages at first deployment and update here if they've moved — same category of
# "confirm at setup time, don't trust a guess" caveat as this project's Postgres env
# var name.
_ASM_URL = "https://nsearchives.nseindia.com/content/equities/asmStage1List.csv"
_GSM_URL = "https://nsearchives.nseindia.com/content/equities/gsmStage1List.csv"
_BHAVCOPY_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{ddmmyyyy}.csv"
)

_SYMBOL_SHAPE_RE = re.compile(r"^[A-Z0-9&.\-]{1,20}$")


def new_session() -> requests.Session:
    """One session should be created per cron run and threaded through
    every fetch_* call below — NSE's data endpoints need cookies from a
    homepage visit first, and reusing one session avoids repeating that
    handshake (and the extra traffic it generates) once per call."""
    session = requests.Session()
    session.headers.update(_BASE_HEADERS)
    try:
        session.get(_HOMEPAGE_URL, timeout=10)
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to establish an NSE session: {exc}") from exc
    return session


def _fetch_csv_rows(session: requests.Session, url: str) -> List[Dict[str, str]]:
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch {url!r}: {exc}") from exc

    content_type = response.headers.get("Content-Type", "")
    if "html" in content_type.lower():
        raise RuntimeError(
            f"Expected CSV from {url!r} but got Content-Type {content_type!r} — "
            "likely an anti-bot challenge page, not real data"
        )

    try:
        reader = csv.DictReader(io.StringIO(response.text))
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    except Exception as exc:
        raise RuntimeError(f"Failed to parse CSV response from {url!r}: {exc}") from exc


def fetch_nifty200_symbols(session: requests.Session) -> List[str]:
    rows = _fetch_csv_rows(session, _NIFTY200_URL)
    symbols = [row["Symbol"] for row in rows if row.get("Symbol")]
    if not symbols:
        raise RuntimeError("Nifty 200 constituent list was empty or malformed")
    return symbols


def _first_column_symbols(rows: List[Dict[str, str]]) -> Set[str]:
    # Ban/surveillance list exports have varied their header text across
    # NSE's own revisions over time; the symbol is reliably the first
    # column regardless of what that column is named that day. Values
    # that don't look like a plausible NSE symbol (e.g. an HTML fragment
    # from a mis-parsed anti-bot response that slipped past the
    # Content-Type check) are silently dropped rather than corrupting the
    # set — an empty result here is a legitimate state (no bans today).
    symbols: Set[str] = set()
    for row in rows:
        values = list(row.values())
        if values and values[0]:
            candidate = values[0].strip().upper()
            if _SYMBOL_SHAPE_RE.match(candidate):
                symbols.add(candidate)
    return symbols


def fetch_fo_ban_symbols(session: requests.Session) -> Set[str]:
    rows = _fetch_csv_rows(session, _FO_BAN_URL)
    return _first_column_symbols(rows)


def fetch_asm_symbols(session: requests.Session) -> Set[str]:
    rows = _fetch_csv_rows(session, _ASM_URL)
    return _first_column_symbols(rows)


def fetch_gsm_symbols(session: requests.Session) -> Set[str]:
    rows = _fetch_csv_rows(session, _GSM_URL)
    return _first_column_symbols(rows)


def fetch_bhavcopy(trading_date: datetime.date, session: requests.Session) -> Dict[str, Dict[str, float]]:
    url = _BHAVCOPY_URL_TEMPLATE.format(ddmmyyyy=trading_date.strftime("%d%m%Y"))
    rows = _fetch_csv_rows(session, url)
    if not rows:
        raise RuntimeError(f"Bhavcopy for {trading_date.isoformat()} was empty")

    result: Dict[str, Dict[str, float]] = {}
    for row in rows:
        symbol = row.get("SYMBOL", "").strip().upper()
        if not symbol:
            continue
        try:
            volume = float(row.get("TTL_TRD_QNTY", "0").replace(",", "") or 0)
            delivery_pct = float(row.get("DELIV_PER", "0").replace(",", "") or 0)
        except ValueError:
            continue
        result[symbol] = {"volume": volume, "delivery_pct": delivery_pct}
    if not result:
        raise RuntimeError(f"Bhavcopy for {trading_date.isoformat()} had no usable SYMBOL rows")
    return result


def latest_trading_day(
    session: requests.Session, today: datetime.date | None = None
) -> Tuple[datetime.date, Dict[str, Dict[str, float]]]:
    """Walk backward from today until a bhavcopy fetch succeeds (skips
    weekends/holidays, which have no bhavcopy file). Returns the
    successful bhavcopy alongside its date so the caller doesn't have to
    re-fetch the same (heaviest) file a second time, and so it can assert
    date alignment against other data sources instead of assuming it."""
    candidate = today or datetime.date.today()
    for _ in range(10):  # NSE holidays never run more than a few days consecutively
        try:
            bhavcopy = fetch_bhavcopy(candidate, session)
            return candidate, bhavcopy
        except RuntimeError:
            candidate -= datetime.timedelta(days=1)
    raise RuntimeError("Could not find a valid NSE trading day with a bhavcopy in the last 10 days")
