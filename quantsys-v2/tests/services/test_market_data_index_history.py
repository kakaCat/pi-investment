"""MarketDataService.get_index_history 回归测试

akshare stock_zh_index_daily 的 date 列是 datetime.date 对象，
与 str 型 start_date/end_date 直接比较会 TypeError（2026-08-05 行为进化回填时发现，
基准对比链路因此整体静默降级）。
"""
from datetime import date
from unittest.mock import patch, MagicMock
import sys

import pandas as pd

from application.services.market_data_service import MarketDataService


def _fake_df():
    return pd.DataFrame({
        'date': [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)],
        'open': [3900, 3910, 3920],
        'close': [3910, 3920, 3905],
        'high': [3920, 3930, 3925],
        'low': [3890, 3900, 3900],
        'volume': [1e8, 1.1e8, 0.9e8],
    })


class TestGetIndexHistory:
    def test_date_column_normalized_for_str_filter(self):
        fake_ak = MagicMock()
        fake_ak.stock_zh_index_daily.return_value = _fake_df()
        with patch.dict(sys.modules, {'akshare': fake_ak}):
            result = MarketDataService().get_index_history(
                'sh000300', '2026-07-02', '2026-07-03')
        assert result['success'] is True
        klines = result['data']['klines']
        assert len(klines) == 2
        # 返回给调用方的 date 应为字符串（benchmark_comparison._benchmark_daily_returns 按 str 处理）
        assert all(isinstance(k['date'], str) for k in klines)
        assert klines[0]['date'] == '2026-07-02'

    def test_empty_filter_returns_all(self):
        fake_ak = MagicMock()
        fake_ak.stock_zh_index_daily.return_value = _fake_df()
        with patch.dict(sys.modules, {'akshare': fake_ak}):
            result = MarketDataService().get_index_history('sh000300')
        assert result['success'] is True
        assert result['data']['total'] == 3
