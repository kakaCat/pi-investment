"""ChanService 格式化契约测试——防 _format_bi 字段错位复发（线上 500 根因）"""
from datetime import datetime, timedelta
from unittest.mock import patch
import polars as pl
import pytest

from application.services.chan_service import ChanService


def _make_klines(days: int = 120) -> pl.DataFrame:
    """构造单调上行+波动的日K polars DataFrame（KlineORMRepository 返回类型）"""
    base = datetime(2026, 1, 5)
    dates, opens, highs, lows, closes, volumes = [], [], [], [], [], []
    price = 10.0
    for i in range(days):
        price += 0.05 if i % 7 else -0.3  # 制造波动
        dates.append(base + timedelta(days=i))
        opens.append(price)
        highs.append(price + 0.2)
        lows.append(price - 0.2)
        closes.append(price + 0.1)
        volumes.append(1000000)
    return pl.DataFrame({
        'date': dates, 'open': opens, 'high': highs,
        'low': lows, 'close': closes, 'volume': volumes,
    })


class TestChanServiceAnalyze:
    @patch('application.services.chan_service.KlineORMRepository')
    def test_analyze_returns_formatted_bis(self, mock_repo_cls):
        """analyze 应返回格式化结果且不抛 AttributeError（契约：Bi.start_fenxing/price_change）"""
        mock_repo_cls.return_value.get_daily_klines.return_value = _make_klines()
        result = ChanService().analyze('600519.SH')

        assert result['symbol'] == '600519.SH'
        assert isinstance(result['bis'], list)
        assert isinstance(result['klines'], list) and len(result['klines']) > 0
        if result['bis']:  # 有笔时验证格式化字段契约
            bi = result['bis'][0]
            for field in ('direction', 'start_index', 'end_index',
                          'start_price', 'end_price', 'high', 'low',
                          'length', 'price_change'):
                assert field in bi, f"bi 缺字段 {field}"
            assert 'amplitude' not in bi

    @patch('application.services.chan_service.KlineORMRepository')
    def test_analyze_empty_klines_returns_empty(self, mock_repo_cls):
        """无K线数据时返回空结构而非异常"""
        mock_repo_cls.return_value.get_daily_klines.return_value = pl.DataFrame()
        result = ChanService().analyze('600519.SH')
        assert result['trend_type'] == '无数据'
        assert result['bis'] == [] and result['buypoints'] == []
