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
