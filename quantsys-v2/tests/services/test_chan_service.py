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

    @patch('application.services.chan_service.KlineORMRepository')
    def test_analyze_with_string_dates(self, mock_repo_cls):
        """生产 K 线 date 列可能是字符串（polars→pandas 未转 datetime），
        analyze 不应报 'str' object has no attribute 'strftime'（线上事故回归）"""
        df = _make_klines().with_columns(
            pl.col('date').dt.strftime('%Y-%m-%d').alias('date')
        )
        mock_repo_cls.return_value.get_daily_klines.return_value = df
        result = ChanService().analyze('600519.SH')
        assert result['symbol'] == '600519.SH'
        assert isinstance(result['klines'], list) and len(result['klines']) > 0
        # klines 日期输出仍为 YYYY-MM-DD 字符串
        assert isinstance(result['klines'][0]['date'], str)


def _mock_analyzer_with_buypoints():
    """让 service.analyzer 返回确定性的 1买/2买 买卖点（合成K线不保证产生买卖点）"""
    from unittest.mock import MagicMock
    from datetime import datetime as _dt

    bp1 = MagicMock()
    bp1.type, bp1.price, bp1.index = '1买', 1620.5, 100
    bp1.date, bp1.confidence, bp1.position_ratio, bp1.reason = _dt(2026, 8, 3), 0.9, 1.0, '下跌背驰'
    bp2 = MagicMock()
    bp2.type, bp2.price, bp2.index = '2买', 1610.0, 95
    bp2.date, bp2.confidence, bp2.position_ratio, bp2.reason = _dt(2026, 8, 1), 0.7, 0.6, '回调不破中枢'

    result = MagicMock()
    result.trend_type, result.bis, result.segments, result.zhongshus = '上涨', [], [], []
    result.buypoints, result.klines = [bp1, bp2], []
    analyzer = MagicMock()
    analyzer.analyze.return_value = result
    return analyzer


class TestChanServiceKnowledge:
    @patch('application.services.chan_service.AgentKnowledgeORMRepository')
    @patch('application.services.chan_service.KlineORMRepository')
    def test_buypoints_carry_knowledge(self, mock_repo_cls, mock_know_cls):
        """买卖点附加该类型历史胜率；无知识时 knowledge=None"""
        mock_repo_cls.return_value.get_daily_klines.return_value = _make_klines()
        mock_know_cls.return_value.get_by_domain.return_value = [{
            'knowledge_id': 'chan_chan_1买_20d',
            'content': {'strategy': 'chan_1买', 'win_rate': 0.62, 'samples': 37,
                        'avg_return': 0.041},
            'confidence': 0.7, 'validation_count': 37, 'success_count': 23,
        }]

        service = ChanService()
        service.analyzer = _mock_analyzer_with_buypoints()
        result = service.analyze('600519.SH')

        for bp in result['buypoints']:
            if bp['type'] == '1买':
                assert bp['knowledge'] is not None
                assert bp['knowledge']['win_rate'] == 0.62
                assert bp['knowledge']['samples'] == 37
                assert bp['knowledge']['suggested_confidence'] == '中高'
            else:
                assert bp['knowledge'] is None

    @patch('application.services.chan_service.AgentKnowledgeORMRepository')
    @patch('application.services.chan_service.KlineORMRepository')
    def test_knowledge_repo_failure_not_fatal(self, mock_repo_cls, mock_know_cls):
        """知识库查询异常不阻塞分析，knowledge 全为 None"""
        mock_repo_cls.return_value.get_daily_klines.return_value = _make_klines()
        mock_know_cls.return_value.get_by_domain.side_effect = RuntimeError('db down')

        service = ChanService()
        service.analyzer = _mock_analyzer_with_buypoints()
        result = service.analyze('600519.SH')

        assert result['symbol'] == '600519.SH'
        assert len(result['buypoints']) == 2
        for bp in result['buypoints']:
            assert bp['knowledge'] is None

    @patch('application.services.chan_service.AgentKnowledgeORMRepository')
    @patch('application.services.chan_service.KlineORMRepository')
    def test_default_buypoint_types_not_none(self, mock_repo_cls, mock_know_cls):
        """buypoint_types 缺省（None）时必须回落默认列表——
        直接传 None 会让 analyzer 的 `bp.type in None` 炸 TypeError
        （生产扫描 14/54 errors 根因：有买卖点的股票全灭）"""
        mock_repo_cls.return_value.get_daily_klines.return_value = _make_klines()
        mock_know_cls.return_value.get_by_domain.return_value = []

        service = ChanService()
        service.analyzer = _mock_analyzer_with_buypoints()
        result = service.analyze('600519.SH')  # 不传 buypoint_types

        assert len(result['buypoints']) == 2  # 不炸且未误过滤
        # 关键契约：传给 analyzer 的 enable_buypoints 不得为 None
        call_args = service.analyzer.analyze.call_args
        enable = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get('enable_buypoints')
        assert enable is not None and '1买' in enable

    @patch('application.services.chan_service.AgentKnowledgeORMRepository')
    @patch('application.services.chan_service.KlineORMRepository')
    def test_format_bi_zhongshu(self, mock_repo_cls, mock_know_cls):
        """BiZhongShu 格式化：high=ZG, low=ZD, type='笔中枢', bi_count；segments 契约置空"""
        from unittest.mock import MagicMock
        from domain.chan.types import BiZhongShu, Bi, FenXing
        from datetime import datetime as _dt

        mock_repo_cls.return_value.get_daily_klines.return_value = _make_klines()
        mock_know_cls.return_value.get_by_domain.return_value = []

        fx = lambda i, p, t: FenXing(type=t, index=i, price=p, date=_dt(2026, 1, 1), klines=[])
        bi = Bi(direction='up', start_fenxing=fx(0, 9.0, 'bottom'),
                end_fenxing=fx(5, 10.0, 'top'), high=10.0, low=9.0, length=6, price_change=0.1)
        zs = BiZhongShu(zg=10.5, zd=9.5, gg=11.0, dd=9.0,
                        start_bi_idx=0, end_bi_idx=2, bis=[bi, bi, bi])

        result_mock = MagicMock()
        result_mock.trend_type, result_mock.bis, result_mock.segments = '盘整', [], []
        result_mock.zhongshus, result_mock.buypoints, result_mock.klines = [zs], [], []

        service = ChanService()
        service.analyzer = MagicMock()
        service.analyzer.analyze.return_value = result_mock

        out = service.analyze('600519.SH')
        assert out['segments'] == []
        z = out['zhongshus'][0]
        assert z['high'] == 10.5 and z['low'] == 9.5
        assert z['type'] == '笔中枢'
        assert z['bi_count'] == 3
