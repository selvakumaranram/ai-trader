import datetime

import pytest
import requests

from sources import nse


class _Resp:
    def __init__(self, text="", content_type="text/csv", status=200):
        self.text = text
        self.headers = {"Content-Type": content_type}
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise requests.HTTPError(f"{self._status}")


class _Session:
    def __init__(self, responses):
        self._responses = responses  # url-substring -> _Resp | Exception
        self.requested = []

    def get(self, url, timeout=None):
        self.requested.append(url)
        for key, value in self._responses.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        return _Resp(status=404)


def test_fetch_csv_rows_rejects_html_challenge_pages():
    session = _Session({"x.csv": _Resp("<html>blocked</html>", content_type="text/html")})
    with pytest.raises(RuntimeError, match="anti-bot"):
        nse._fetch_csv_rows(session, "https://nse/x.csv")


def test_fetch_csv_rows_wraps_network_errors():
    session = _Session({"x.csv": requests.ConnectionError("down")})
    with pytest.raises(RuntimeError, match="Failed to fetch"):
        nse._fetch_csv_rows(session, "https://nse/x.csv")


def test_first_column_symbols_drops_junk():
    rows = [{"Sr": "INFY"}, {"Sr": "<div>"}, {"Sr": "m&m"}, {"Sr": ""}]
    assert nse._first_column_symbols(rows) == {"INFY", "M&M"}


def test_fetch_bhavcopy_parses_volume_and_delivery():
    csv_text = "SYMBOL,TTL_TRD_QNTY,DELIV_PER\nINFY,\"1,000\",55.5\nBAD,abc,1\n"
    session = _Session({"sec_bhavdata_full_02012026": _Resp(csv_text)})
    result = nse.fetch_bhavcopy(datetime.date(2026, 1, 2), session)
    assert result == {"INFY": {"volume": 1000.0, "delivery_pct": 55.5}}


def test_latest_trading_day_walks_back_to_last_published_file():
    csv_text = "SYMBOL,TTL_TRD_QNTY,DELIV_PER\nINFY,10,50\n"
    session = _Session({"sec_bhavdata_full_02012026": _Resp(csv_text)})
    day, bhavcopy = nse.latest_trading_day(session, today=datetime.date(2026, 1, 4))
    assert day == datetime.date(2026, 1, 2)
    assert "INFY" in bhavcopy
    assert len(session.requested) == 3  # 04, 03, then 02


def test_latest_trading_day_gives_up_after_ten_days():
    with pytest.raises(RuntimeError, match="10 days"):
        nse.latest_trading_day(_Session({}), today=datetime.date(2026, 1, 20))
