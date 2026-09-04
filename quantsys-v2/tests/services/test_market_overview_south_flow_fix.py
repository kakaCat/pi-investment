"""2026-09-05 两处上游 bug 修复的回归测试

1. MarketDataService.get_market_overview()：report_daily 曾调用不存在的
   get_market_summary()（自始 AttributeError 被吞 → "市场概况"节永远缺失）。
   修复：新增 get_market_overview()，走 provider_manager.get_market_overview()。
2. AkshareHKProvider.get_south_flow()：上游 stock_hk_fund_flow_em 在现装
   akshare(1.18.81) 已不存在 → 永远返回 None。修复：改用东财沪深港通历史
   官方南向序列 stock_hsgt_hist_em(symbol='南向资金')。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from application.services.market_data_service import MarketDataService
from adapters.outbound.datasources.providers.hk.akshare import AkshareHKProvider


class TestGetMarketOverview:
    """修复1：report_daily 市场概况节的数据源"""

    def test_success_unwraps_overview_dict(self):
        svc = MarketDataService()
        svc.provider_manager = MagicMock()
        svc.provider_manager.get_market_overview.return_value = {
            'success': True,
            'data': SimpleNamespace(data={
                'rise': 2800, 'fall': 2400, 'unchanged': 120, 'total': 5320,
            }),
            'source': 'akshare-market',
        }
        result = svc.get_market_overview()
        assert result['success'] is True
        assert result['data']['rise'] == 2800
        assert result['data']['fall'] == 2400
        assert result['data']['total'] == 5320

    def test_provider_failure_returns_friendly_error(self):
        svc = MarketDataService()
        svc.provider_manager = MagicMock()
        svc.provider_manager.get_market_overview.return_value = {
            'success': False,
            'error': 'provider down',
            'data': None,
        }
        result = svc.get_market_overview()
        assert result['success'] is False
        assert result['data'] is None
        assert '市场概况' in result['error']

    def test_empty_payload_returns_error(self):
        svc = MarketDataService()
        svc.provider_manager = MagicMock()
        svc.provider_manager.get_market_overview.return_value = {
            'success': True,
            'data': SimpleNamespace(data={}),
            'source': 'akshare-market',
        }
        result = svc.get_market_overview()
        assert result['success'] is False
        assert result['data'] is None


class TestGetSouthFlow:
    """修复2：南向资金上游接口替换（stock_hk_fund_flow_em → stock_hsgt_hist_em）"""

    def test_success_returns_records_from_hsgt_hist_em(self):
        provider = AkshareHKProvider()
        fake_ak = MagicMock()
        # stock_hsgt_hist_em(symbol='南向资金') 返回日序列
        import pandas as pd
        fake_ak.stock_hsgt_hist_em.return_value = pd.DataFrame({
            '日期': ['2026-09-02', '2026-09-03', '2026-09-04'],
            '当日成交净买额': [40.93, 33.95, -100.21],
            '买入成交额': [433.93, 418.49, 483.34],
        })
        with patch.dict('sys.modules', {'akshare': fake_ak}):
            result = provider.get_south_flow()
        assert result is not None
        assert result.data_type == 'south_flow'
        assert result.total == 3
        assert result.data[0]['日期'] == '2026-09-02'
        assert result.data[0]['当日成交净买额'] == 40.93

    def test_empty_df_returns_none(self):
        provider = AkshareHKProvider()
        fake_ak = MagicMock()
        import pandas as pd
        fake_ak.stock_hsgt_hist_em.return_value = pd.DataFrame()
        with patch.dict('sys.modules', {'akshare': fake_ak}):
            result = provider.get_south_flow()
        assert result is None

    def test_upstream_failure_returns_none_not_raise(self):
        provider = AkshareHKProvider()
        fake_ak = MagicMock()
        fake_ak.stock_hsgt_hist_em.side_effect = RuntimeError('boom')
        with patch.dict('sys.modules', {'akshare': fake_ak}):
            result = provider.get_south_flow()
        assert result is None

    def test_records_clean_nan_and_date(self):
        """_records 须 JSON 兼容：date→iso str、nan/inf→None

        2026-09-05 回归：原实现缺 astype(object) → float 列 NaN 在 to_dict 复活，
        route 层 raw json.dumps 报 'Out of range float values ... nan'；date 列
        datetime.date 对象无法 json 序列化。
        """
        import math
        from datetime import date, datetime

        import pandas as pd

        provider = AkshareHKProvider()
        df = pd.DataFrame({
            '日期': [date(2026, 9, 4), datetime(2026, 9, 3, 10, 30)],
            '净买额': [float('nan'), 40.93],
            '余额': [float('inf'), 87.32],
        })
        records = provider._records(df)
        assert records[0]['日期'] == '2026-09-04'
        assert records[1]['日期'] == '2026-09-03T10:30:00'
        assert records[0]['净买额'] is None
        assert records[0]['余额'] is None
        assert all(math.isfinite(v) or v is None
                   for r in records for v in r.values() if isinstance(v, float))
