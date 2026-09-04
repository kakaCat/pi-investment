"""MarketDataService.get_index_history 回归测试

akshare stock_zh_index_daily 的 date 列是 datetime.date 对象，
与 str 型 start_date/end_date 直接比较会 TypeError（2026-08-05 行为进化回填时发现，
基准对比链路因此整体静默降级）。

2026-09-05 更新：生产代码从 provider_manager.call_akshare()（方法不存在，AttributeError
被 try/except 吞掉 → 静默降级）迁移到 provider_manager.get_index_daily()，
mock 目标改为 get_index_daily，返回结果 dict（resp['data'].data = {'records': [...], 'total': n}，
date 已由 provider 归一为 str）。
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

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


def _fake_resp():
    """模拟 manager.get_index_daily 的返回（provider 已把 date 归一为 str）"""
    df = _fake_df()
    df['date'] = df['date'].astype(str)  # 复刻 provider：date 列归一为字符串
    records = df.astype(object).where(df.notna(), None).to_dict('records')
    return {
        'success': True,
        'data': SimpleNamespace(data={'records': records, 'total': len(records)}),
        'source': 'akshare-market',
    }


class TestGetIndexHistory:
    def test_date_column_normalized_for_str_filter(self):
        svc = MarketDataService()
        svc.provider_manager = MagicMock()
        svc.provider_manager.get_index_daily.return_value = _fake_resp()
        result = svc.get_index_history('sh000300', '2026-07-02', '2026-07-03')
        assert result['success'] is True
        klines = result['data']['klines']
        assert len(klines) == 2
        # 返回给调用方的 date 应为字符串（benchmark_comparison._benchmark_daily_returns 按 str 处理）
        assert all(isinstance(k['date'], str) for k in klines)
        assert klines[0]['date'] == '2026-07-02'

    def test_empty_filter_returns_all(self):
        svc = MarketDataService()
        svc.provider_manager = MagicMock()
        svc.provider_manager.get_index_daily.return_value = _fake_resp()
        result = svc.get_index_history('sh000300')
        assert result['success'] is True
        assert result['data']['total'] == 3
