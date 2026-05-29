"""Tests for the xmtdx minute kline probe adapter."""

from __future__ import annotations

import pandas as pd

from quantsys.data.xmtdx_minute_probe import XmtDxMinuteProbe


class FakeReader:
    def __init__(self) -> None:
        self.calls = []

    def minute(self, symbol: str, category: str, offset: int, count: int) -> pd.DataFrame:
        self.calls.append(
            {
                "symbol": symbol,
                "category": category,
                "offset": offset,
                "count": count,
            }
        )
        if offset == 0:
            return pd.DataFrame(
                [
                    {
                        "datetime": "2026-05-27 09:31:00",
                        "open": 10.0,
                        "high": 10.2,
                        "low": 9.9,
                        "close": 10.1,
                        "vol": 1000,
                        "amount": 10100.0,
                    }
                ]
            )
        return pd.DataFrame()


class FakeDb:
    def __init__(self) -> None:
        self.saved_rows = []

    def upsert_minute_klines(self, rows):
        self.saved_rows.extend(rows)
        return len(rows)


def test_fetch_range_normalizes_xmtdx_rows() -> None:
    reader = FakeReader()
    probe = XmtDxMinuteProbe(reader=reader)

    rows = probe.fetch_range("600519.SH", "2026-05-27", "2026-05-27", max_pages=2, page_size=800)

    assert rows == [
        {
            "symbol": "600519.SH",
            "trade_datetime": "2026-05-27 09:31:00",
            "open": 10.0,
            "high": 10.2,
            "low": 9.9,
            "close": 10.1,
            "volume": 1000.0,
            "amount": 10100.0,
        }
    ]
    assert reader.calls == [
        {"symbol": "sh600519", "category": "1m", "offset": 0, "count": 800},
        {"symbol": "sh600519", "category": "1m", "offset": 800, "count": 800},
    ]


def test_fetch_range_filters_outside_dates() -> None:
    reader = FakeReader()
    probe = XmtDxMinuteProbe(reader=reader)

    rows = probe.fetch_range("600519.SH", "2026-05-28", "2026-05-28", max_pages=1, page_size=800)

    assert rows == []


def test_backfill_range_writes_rows_to_database() -> None:
    reader = FakeReader()
    db = FakeDb()
    probe = XmtDxMinuteProbe(reader=reader)

    count = probe.backfill_range(
        db,
        "600519.SH",
        "2026-05-27",
        "2026-05-27",
        max_pages=1,
        page_size=800,
    )

    assert count == 1
    assert db.saved_rows == [
        {
            "symbol": "600519.SH",
            "trade_datetime": "2026-05-27 09:31:00",
            "open": 10.0,
            "high": 10.2,
            "low": 9.9,
            "close": 10.1,
            "volume": 1000.0,
            "amount": 10100.0,
        }
    ]
