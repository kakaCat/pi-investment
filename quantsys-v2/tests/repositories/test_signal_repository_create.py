"""SignalORMRepository.create_signal 契约修复测试（2026-08-04）

根因：create_signal 按旧模型传 volume=/metadata=（两个字段在现行 Signal 模型
都不存在）→ 每条信号创建都 TypeError 被吞返回 0。这是 ORM 重构契约回归族
（[[orm-refactor-contract-regressions]]）的又一例，strategy_executor 等
多个调用方同时受害。
"""
from datetime import date

import pytest

from adapters.outbound.repositories.signal_repository import SignalORMRepository
from infrastructure.persistence.orm.models import Signal


@pytest.fixture
def repo():
    r = SignalORMRepository()
    yield r
    r.session.query(Signal).filter(Signal.symbol == 'TST900').delete()
    r.session.commit()


class TestCreateSignal:
    def test_create_with_canonical_fields(self, repo):
        signal_id = repo.create_signal({
            'signal_date': date(2026, 8, 4),
            'symbol': 'TST900',
            'name': '测试股票',
            'action': 'buy',
            'action_type': 1,
            'strategy_id': '162',
            'price': 10.5,
            'confidence': 0.8,
            'reason': 'RSI超卖反弹',
            'indicators': {'rsi': 28.5},
        })
        assert signal_id > 0
        row = repo.session.query(Signal).filter(Signal.symbol == 'TST900').one()
        assert row.name == '测试股票'
        assert row.action == 'buy'
        assert row.action_type == 1
        assert row.strategy_id == '162'
        assert row.indicators == {'rsi': 28.5}
        assert row.status == 'pending'

    def test_action_type_derived_from_action(self, repo):
        """调用方不传 action_type 时按 action 推导（buy→1, sell→2）"""
        buy_id = repo.create_signal({
            'signal_date': date(2026, 8, 4), 'symbol': 'TST900', 'name': '测试',
            'action': 'buy', 'strategy_id': 's1', 'price': 1.0,
        })
        sell_id = repo.create_signal({
            'signal_date': date(2026, 8, 4), 'symbol': 'TST900', 'name': '测试',
            'action': 'sell', 'strategy_id': 's2', 'price': 1.0,
        })
        assert buy_id > 0 and sell_id > 0
        rows = {r.strategy_id: r.action_type for r in
                repo.session.query(Signal).filter(Signal.symbol == 'TST900')}
        assert rows == {'s1': 1, 's2': 2}

    def test_duplicate_returns_zero_not_error(self, repo):
        """唯一键 (symbol, signal_date, strategy_id) 冲突 → 返回 0 且不产生重复行"""
        payload = {
            'signal_date': date(2026, 8, 4), 'symbol': 'TST900', 'name': '测试',
            'action': 'buy', 'action_type': 1, 'strategy_id': '162', 'price': 1.0,
        }
        first = repo.create_signal(payload)
        second = repo.create_signal(dict(payload))
        assert first > 0
        assert second == 0
        count = repo.session.query(Signal).filter(
            Signal.symbol == 'TST900', Signal.strategy_id == '162').count()
        assert count == 1
