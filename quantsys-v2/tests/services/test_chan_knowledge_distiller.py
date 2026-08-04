"""ChanKnowledgeDistiller 测试——缠论信号胜率蒸馏入 agent_knowledge"""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import polars as pl
import pytest

from application.services.chan_knowledge_distiller import ChanKnowledgeDistiller


def _signals():
    """3 个 chan_1买 信号：2 胜 1 负（20 日窗）"""
    base = date(2026, 6, 1)
    return [
        {'symbol': '600519.SH', 'signal_date': base, 'strategy_id': 'chan_1买', 'action': 'buy'},
        {'symbol': '000858.SZ', 'signal_date': base, 'strategy_id': 'chan_1买', 'action': 'buy'},
        {'symbol': '601318.SH', 'signal_date': base, 'strategy_id': 'chan_1买', 'action': 'buy'},
    ]


def _klines(start_price: float, end_price: float, days: int = 30) -> pl.DataFrame:
    """线性价格序列 polars df"""
    base = date(2026, 6, 1)
    step = (end_price - start_price) / (days - 1)
    return pl.DataFrame({
        'date': [base + timedelta(days=i) for i in range(days)],
        'open': [start_price] * days,
        'high': [start_price] * days,
        'low': [start_price] * days,
        'close': [start_price + step * i for i in range(days)],
        'volume': [1000] * days,
    })


class TestDistiller:
    @patch('application.services.chan_knowledge_distiller.AgentKnowledgeORMRepository')
    @patch('application.services.chan_knowledge_distiller.KlineORMRepository')
    @patch('application.services.chan_knowledge_distiller.SignalORMRepository')
    def test_distill_aggregates_win_rate(self, mock_sig, mock_kline, mock_know):
        mock_sig.return_value.get_signals_by_date_range.return_value = _signals()
        # 600519 涨（胜）、000858 跌（负）、601318 涨（胜）
        mock_kline.return_value.get_daily_klines.side_effect = [
            _klines(100.0, 110.0), _klines(100.0, 95.0), _klines(100.0, 105.0),
        ]
        upserts = []
        mock_know.return_value.upsert_knowledge.side_effect = lambda **kw: upserts.append(kw)

        result = ChanKnowledgeDistiller(window_days=20, lookback_days=90).distill()

        assert result['strategies_distilled'] == 1
        assert len(upserts) == 1
        u = upserts[0]
        assert u['knowledge_id'] == 'chan_chan_1买_20d'
        assert u['domain'] == 'chan_theory'
        assert u['knowledge_type'] == 'signal_effectiveness'
        assert u['validation_count'] == 3
        assert u['success_count'] == 2
        assert abs(u['content']['win_rate'] - 2 / 3) < 1e-3  # content 按 4 位小数舍入
        assert u['content']['samples'] == 3
        # 3 样本 < 10 → confidence 封顶 0.3
        assert u['confidence'] == 0.3

    @patch('application.services.chan_knowledge_distiller.AgentKnowledgeORMRepository')
    @patch('application.services.chan_knowledge_distiller.KlineORMRepository')
    @patch('application.services.chan_knowledge_distiller.SignalORMRepository')
    def test_missing_klines_excluded(self, mock_sig, mock_kline, mock_know):
        """验证窗内K线缺失的信号不计入统计"""
        mock_sig.return_value.get_signals_by_date_range.return_value = _signals()[:2]
        mock_kline.return_value.get_daily_klines.side_effect = [
            _klines(100.0, 110.0), pl.DataFrame(),
        ]
        upserts = []
        mock_know.return_value.upsert_knowledge.side_effect = lambda **kw: upserts.append(kw)

        result = ChanKnowledgeDistiller(window_days=20, lookback_days=90).distill()
        assert upserts[0]['validation_count'] == 1
        assert result['signals_excluded'] == 1
