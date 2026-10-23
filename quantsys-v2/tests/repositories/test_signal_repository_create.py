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
from infrastructure.persistence.orm.models.stock import Stock


@pytest.fixture
def repo():
    r = SignalORMRepository()
    # 2026-10-21 僵尸批次3：signals 有 FK(signals_symbol_fkey)——不预置 stocks 行
    # 会让 create_signal 吞 IntegrityError 返回 0（裸复现已证实）。自愈式清理
    # + 预置，防跨跑残留 UniqueViolation。
    r.session.query(Signal).filter(Signal.symbol == '999900').delete()
    r.session.query(Stock).filter(Stock.symbol == '999900').delete()
    r.session.commit()
    r.session.add(Stock(symbol='999900', name='测试股票', industry='测试',
                        market='A', market_cap=1.0, is_delisted=False))
    r.session.commit()
    yield r
    r.session.query(Signal).filter(Signal.symbol == '999900').delete()
    r.session.query(Stock).filter(Stock.symbol == '999900').delete()
    r.session.commit()


class TestCreateSignal:
    def test_create_with_canonical_fields(self, repo):
        signal_id = repo.create_signal({
            'signal_date': date(2026, 8, 4),
            'symbol': '999900',
            'name': '测试股票',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': '162',
            'price': 10.5,
            'confidence': 0.8,
            'reason': 'RSI超卖反弹',
            'indicators': {'rsi': 28.5},
        })
        assert signal_id > 0
        row = repo.session.query(Signal).filter(Signal.symbol == '999900').one()
        assert row.name == '测试股票'
        # 2026-10-21 僵尸批次3：08-13 大写冻结（DB canonical = 'BUY'/'SELL'，
        # repo 查询过滤 in_(['BUY','SELL'])）——种子值原样入库，更正过时小写断言。
        assert row.action == 'BUY'
        assert row.action_type == 1
        assert row.strategy_id == '162'
        assert row.indicators == {'rsi': 28.5}
        assert row.status == 'pending'

    def test_action_type_derived_from_action(self, repo):
        """调用方不传 action_type 时按 action 推导（buy→1, sell→2）"""
        buy_id = repo.create_signal({
            'signal_date': date(2026, 8, 4), 'symbol': '999900', 'name': '测试',
            'action': 'BUY', 'strategy_id': 's1', 'price': 1.0,
        })
        sell_id = repo.create_signal({
            'signal_date': date(2026, 8, 4), 'symbol': '999900', 'name': '测试',
            'action': 'SELL', 'strategy_id': 's2', 'price': 1.0,
        })
        assert buy_id > 0 and sell_id > 0
        rows = {r.strategy_id: r.action_type for r in
                repo.session.query(Signal).filter(Signal.symbol == '999900')}
        assert rows == {'s1': 1, 's2': 2}

    def test_duplicate_returns_zero_not_error(self, repo):
        """唯一键 (symbol, signal_date, strategy_id) 冲突 → 返回 0 且不产生重复行"""
        payload = {
            'signal_date': date(2026, 8, 4), 'symbol': '999900', 'name': '测试',
            'action': 'BUY', 'action_type': 1, 'strategy_id': '162', 'price': 1.0,
        }
        first = repo.create_signal(payload)
        second = repo.create_signal(dict(payload))
        assert first > 0
        assert second == 0
        count = repo.session.query(Signal).filter(
            Signal.symbol == '999900', Signal.strategy_id == '162').count()
        assert count == 1
