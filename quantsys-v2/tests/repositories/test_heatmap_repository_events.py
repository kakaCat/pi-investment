"""HeatmapRepository 信号/池事件/持仓查询测试（真实 quant_test DB）"""
from datetime import date, datetime

import pytest

from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
from adapters.outbound.repositories.pool_change_log_repository import PoolChangeLog
from adapters.outbound.repositories.stock_pool_repository import StockPool
from infrastructure.persistence.orm.models.portfolio import PortfolioHolding
from infrastructure.persistence.orm.models.signal import Signal
from infrastructure.persistence.orm.models.stock import Stock

D = date(2009, 1, 20)


@pytest.fixture
def seeded():
    repo = HeatmapRepository()
    s = repo.session
    s.add(Stock(symbol='TST010', name='信号股', industry='测试医药', market='A', market_cap=10.0))
    s.add(Stock(symbol='TST011', name='持仓股', industry='测试医药', market='A', market_cap=20.0))
    s.add_all([
        Signal(symbol='TST010', name='信号股', signal_date=date(2009, 1, 15),
               action='buy', strategy_id='v13', price=1.0, confidence=0.8),
        Signal(symbol='TST010', name='信号股', signal_date=date(2009, 1, 18),
               action='sell', strategy_id='v13', price=1.0, confidence=0.7),
        # 窗口外信号（2009-01-05 前）不应返回
        Signal(symbol='TST010', name='信号股', signal_date=date(2008, 12, 1),
               action='buy', strategy_id='v13', price=1.0, confidence=0.6),
    ])
    pool = StockPool(name='测试池', pool_type='dynamic', symbols='{}', members=['TST011'])
    s.add(pool)
    s.flush()
    s.add_all([
        PoolChangeLog(pool_id=pool.id, changed_at=datetime(2009, 1, 19, 10, 0),
                      action='add', symbol='TST010', reason='测试调入'),
        PoolChangeLog(pool_id=pool.id, changed_at=datetime(2009, 1, 21, 10, 0),
                      action='remove', symbol='TST011', reason='D 之后的事件（回放用）'),
    ])
    s.add(PortfolioHolding(symbol='TST011', name='持仓股', quantity=100, avg_cost=5.0,
                           total_invested=500.0, added_date=date(2009, 1, 10), market='A'))
    s.commit()
    yield {'repo': repo, 'pool_id': pool.id}
    s.query(Signal).filter(Signal.symbol.in_(['TST010', 'TST011'])).delete()
    s.query(PoolChangeLog).filter(PoolChangeLog.pool_id == pool.id).delete()
    s.query(StockPool).filter(StockPool.id == pool.id).delete()
    s.query(PortfolioHolding).filter(PortfolioHolding.symbol == 'TST011').delete()
    s.query(Stock).filter(Stock.symbol.in_(['TST010', 'TST011'])).delete()
    s.commit()


class TestSignals:
    def test_signals_in_window(self, seeded):
        sigs = seeded['repo'].get_signals_between(date(2009, 1, 1), D)
        ours = [x for x in sigs if x['symbol'] == 'TST010']
        assert len(ours) == 2
        assert {x['action'] for x in ours} == {'buy', 'sell'}
        assert ours[0]['strategy_id'] == 'v13'


class TestPoolEvents:
    def test_pool_events_between(self, seeded):
        evts = seeded['repo'].get_pool_events_between(datetime(2009, 1, 1), datetime(2009, 1, 20, 23, 59))
        ours = [e for e in evts if e['symbol'] == 'TST010']
        assert len(ours) == 1
        assert ours[0]['action'] == 'add'

    def test_pool_events_after_for_replay(self, seeded):
        evts = seeded['repo'].get_pool_events_after(datetime(2009, 1, 20, 23, 59))
        ours = [e for e in evts if e['pool_id'] == seeded['pool_id']]
        assert len(ours) == 1 and ours[0]['action'] == 'remove'

    def test_pool_names(self, seeded):
        names = seeded['repo'].get_pool_names()
        assert names[seeded['pool_id']] == '测试池'

    def test_pool_members_now(self, seeded):
        members = seeded['repo'].get_pool_members_now()
        assert 'TST011' in members

    def test_has_pool_log_before(self, seeded):
        repo = seeded['repo']
        # 池内有 2009-01-19 的日志 → 2009-01-20 之前有记录
        assert repo.has_pool_log_before(datetime(2009, 1, 20, 23, 59)) is True
        # 2009-01-01 之前没有任何日志
        assert repo.has_pool_log_before(datetime(2009, 1, 1)) is False


class TestHoldings:
    def test_current_holding_symbols(self, seeded):
        assert 'TST011' in seeded['repo'].get_current_holding_symbols()
