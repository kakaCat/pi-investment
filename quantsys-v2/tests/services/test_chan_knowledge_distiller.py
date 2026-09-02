"""ChanKnowledgeDistiller 测试——缠论信号胜率蒸馏入 agent_knowledge"""
from datetime import date, timedelta
from unittest.mock import MagicMock
from types import SimpleNamespace
import polars as pl
import pytest

from application.services.chan_knowledge_distiller import ChanKnowledgeDistiller


def _signals():
    base = date(2026, 6, 1)
    return [
        {'symbol': '600519.SH', 'signal_date': base, 'strategy_id': 'chan_1买', 'action': 'BUY'},
        {'symbol': '000858.SZ', 'signal_date': base, 'strategy_id': 'chan_1买', 'action': 'BUY'},
        {'symbol': '601318.SH', 'signal_date': base, 'strategy_id': 'chan_1买', 'action': 'BUY'},
    ]


def _klines(start_price: float, end_price: float, days: int = 30) -> pl.DataFrame:
    base = date(2026, 6, 1)
    step = (end_price - start_price) / (days - 1)
    return pl.DataFrame({
        'date': [(base + timedelta(days=i)).isoformat() for i in range(days)],
        'open': [start_price] * days,
        'high': [start_price] * days,
        'low': [start_price] * days,
        'close': [start_price + step * i for i in range(days)],
        'volume': [1000] * days,
    })


class TestDistiller:
    def test_distill_aggregates_win_rate(self):
        signal_repo = MagicMock()
        signal_repo.get_signals_by_date_range.return_value = _signals()
        kline_repo = MagicMock()
        kline_repo.get_daily_klines.side_effect = [
            _klines(100.0, 110.0), _klines(100.0, 95.0), _klines(100.0, 105.0),
        ]
        upserts = []
        knowledge_repo = MagicMock()
        knowledge_repo.upsert_knowledge.side_effect = lambda **kw: upserts.append(kw)

        result = ChanKnowledgeDistiller(
            window_days=20, lookback_days=90,
            signal_repo=signal_repo, kline_repo=kline_repo, knowledge_repo=knowledge_repo
        ).distill()

        assert result['strategies_distilled'] == 1
        assert len(upserts) == 1
        u = upserts[0]
        assert u['knowledge_id'] == 'chan_chan_1买_20d'
        assert u['domain'] == 'chan_theory'
        assert u['knowledge_type'] == 'signal_effectiveness'
        assert u['validation_count'] == 3
        assert u['success_count'] == 2
        assert abs(u['content']['win_rate'] - 2 / 3) < 1e-3
        assert u['content']['samples'] == 3
        assert u['confidence'] == 0.3

    def test_missing_klines_excluded(self):
        signal_repo = MagicMock()
        signal_repo.get_signals_by_date_range.return_value = _signals()[:2]
        kline_repo = MagicMock()
        kline_repo.get_daily_klines.side_effect = [
            _klines(100.0, 110.0), pl.DataFrame(),
        ]
        upserts = []
        knowledge_repo = MagicMock()
        knowledge_repo.upsert_knowledge.side_effect = lambda **kw: upserts.append(kw)

        result = ChanKnowledgeDistiller(
            window_days=20, lookback_days=90,
            signal_repo=signal_repo, kline_repo=kline_repo, knowledge_repo=knowledge_repo
        ).distill()
        assert upserts[0]['validation_count'] == 1
        assert result['signals_excluded'] == 1

    def test_orm_signal_objects_supported(self):
        base = date(2026, 6, 1)
        orm_signals = [
            SimpleNamespace(symbol='600519', signal_date=base, strategy_id='chan_1买', action='BUY'),
            SimpleNamespace(symbol='000858', signal_date=base, strategy_id='chan_1买', action='BUY'),
        ]
        signal_repo = MagicMock()
        signal_repo.get_signals_by_date_range.return_value = orm_signals
        kline_repo = MagicMock()
        kline_repo.get_daily_klines.side_effect = [
            _klines(100.0, 110.0), _klines(100.0, 95.0),
        ]
        upserts = []
        knowledge_repo = MagicMock()
        knowledge_repo.upsert_knowledge.side_effect = lambda **kw: upserts.append(kw)

        result = ChanKnowledgeDistiller(
            window_days=20, lookback_days=90,
            signal_repo=signal_repo, kline_repo=kline_repo, knowledge_repo=knowledge_repo
        ).distill()
        assert result['strategies_distilled'] == 1
        assert upserts[0]['validation_count'] == 2
        assert upserts[0]['success_count'] == 1

    def test_sell_signal_wins_when_price_falls(self):
        base = date(2026, 6, 1)
        signal_repo = MagicMock()
        signal_repo.get_signals_by_date_range.return_value = [
            {'symbol': '600519', 'signal_date': base, 'strategy_id': 'chan_1卖', 'action': 'SELL'},
            {'symbol': '000858', 'signal_date': base, 'strategy_id': 'chan_1卖', 'action': 'SELL'},
        ]
        kline_repo = MagicMock()
        kline_repo.get_daily_klines.side_effect = [
            _klines(100.0, 90.0), _klines(100.0, 110.0),
        ]
        upserts = []
        knowledge_repo = MagicMock()
        knowledge_repo.upsert_knowledge.side_effect = lambda **kw: upserts.append(kw)

        result = ChanKnowledgeDistiller(
            window_days=20, lookback_days=90,
            signal_repo=signal_repo, kline_repo=kline_repo, knowledge_repo=knowledge_repo
        ).distill()
        assert result['strategies_distilled'] == 1
        assert upserts[0]['validation_count'] == 2
        assert upserts[0]['success_count'] == 1
