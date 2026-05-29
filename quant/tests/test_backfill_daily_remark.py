"""Tests for daily backfill failure remarks."""

from unittest.mock import Mock, patch

from quantsys.data.data_backfiller import DataBackfiller
from quantsys.data.db import Database
from quantsys.data.gap_detector import GapDetector
import pandas as pd


def test_daily_backfill_records_remark_when_download_returns_no_data():
    db = Mock()
    calendar = Mock()
    gap_detector = Mock()
    progress_tracker = Mock()
    backfiller = DataBackfiller(db, calendar, gap_detector, progress_tracker)

    gap_detector.detect_daily_gaps.return_value = ["2026-05-27"]
    progress_tracker.is_completed.return_value = False

    with patch.object(backfiller, "_download_daily_klines_for_dates", return_value={}):
        result = backfiller.backfill_daily("000001", target_days=7, end_date="2026-05-27")

    assert result["failed"] == 1
    db.upsert_daily_kline_remark.assert_called_once()
    args = db.upsert_daily_kline_remark.call_args[0]
    assert args[0] == "000001"
    assert args[1] == "2026-05-27"
    assert "akshare returned no daily data" in args[2]
    progress_tracker.mark_completed.assert_not_called()


def test_daily_gap_detector_can_target_end_date_and_include_new_symbols():
    db = Mock()
    calendar = Mock()
    detector = GapDetector(db, calendar)

    db.get_kline_coverage.return_value = {
        "existing_days": 0,
        "first_date": None,
        "last_date": None,
    }
    calendar.get_trading_days.return_value = []

    detector.detect_daily_gaps(
        "000001",
        target_days=7,
        end_date="2026-05-27",
        include_new_symbols=True,
    )

    start_date, end_date = calendar.get_trading_days.call_args[0]
    assert start_date.isoformat() == "2026-05-20"
    assert end_date.isoformat() == "2026-05-27"


def test_postgres_daily_upsert_normalizes_symbol_before_insert():
    db = Database(connect=False)
    db.provider = "postgres"
    cursor = Mock()
    cursor.fetchone.return_value = ("600519",)
    connection = Mock()
    connection.cursor.return_value = cursor
    db.conn = connection

    db.upsert_daily_klines([
        {
            "symbol": "600519.SH",
            "date": "2026-05-27",
            "open": 1,
            "high": 2,
            "low": 0.5,
            "close": 1.5,
            "volume": 100,
            "amount": 150,
        }
    ])

    rows = cursor.executemany.call_args[0][1]
    assert rows[0][0] == "600519"


def test_postgres_daily_remark_uses_existing_suffixed_symbol_when_normalized_stock_missing():
    db = Database(connect=False)
    db.provider = "postgres"
    cursor = Mock()
    cursor.fetchone.side_effect = [(None,), ("159920.SZ",)]
    connection = Mock()
    connection.cursor.return_value = cursor
    db.conn = connection

    db.upsert_daily_kline_remark("159920.SZ", "2026-05-27", "no provider data")

    insert_args = cursor.execute.call_args_list[-1][0][1]
    assert insert_args[0] == "159920.SZ"


@patch("quantsys.data.data_backfiller.ak.stock_zh_a_hist")
def test_download_daily_klines_for_dates_fetches_range_once(mock_hist):
    backfiller = DataBackfiller(Mock(), Mock(), Mock(), Mock())
    mock_hist.return_value = pd.DataFrame({
        "日期": ["2026-05-26", "2026-05-27"],
        "开盘": [10.0, 11.0],
        "最高": [12.0, 13.0],
        "最低": [9.0, 10.0],
        "收盘": [11.0, 12.0],
        "成交量": [1000, 2000],
        "成交额": [10000.0, 22000.0],
    })

    result = backfiller._download_daily_klines_for_dates(
        "000001",
        ["2026-05-25", "2026-05-26", "2026-05-27"],
    )

    mock_hist.assert_called_once()
    assert sorted(result.keys()) == ["2026-05-26", "2026-05-27"]
    assert result["2026-05-27"]["close"] == 12.0


@patch("quantsys.data.data_backfiller.ak.stock_zh_a_hist")
@patch("quantsys.data.data_backfiller.ak.stock_zh_a_hist_tx")
def test_download_daily_klines_for_dates_falls_back_to_tencent_source(mock_tx, mock_hist):
    backfiller = DataBackfiller(Mock(), Mock(), Mock(), Mock())
    mock_hist.return_value = pd.DataFrame()
    mock_tx.return_value = pd.DataFrame({
        "date": [pd.Timestamp("2026-05-27").date()],
        "open": [31.92],
        "close": [31.65],
        "high": [32.54],
        "low": [31.46],
        "amount": [582351],
    })

    result = backfiller._download_daily_klines_for_dates("002415", ["2026-05-27"])

    mock_tx.assert_called_once()
    assert result["2026-05-27"]["close"] == 31.65
    assert result["2026-05-27"]["volume"] == 582351
    assert result["2026-05-27"]["amount"] is None
