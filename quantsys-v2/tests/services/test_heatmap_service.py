"""HeatmapService 聚合逻辑测试（真实 quant_test DB，日期取 2009 年避免冲突）"""
from datetime import date, datetime

import pytest

from application.services.heatmap_service import HeatmapService
from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
from adapters.outbound.repositories.pool_change_log_repository import PoolChangeLog
from adapters.outbound.repositories.stock_pool_repository import StockPool
from infrastructure.persistence.orm.models.portfolio import PortfolioHolding
from infrastructure.persistence.orm.models.signal import Signal
from infrastructure.persistence.orm.models.stock import DailyKline, Stock

D0, D1 = date(2009, 2, 2), date(2009, 2, 3)   # 周一/周二，window=1


@pytest.fixture
def seeded():
    repo = HeatmapRepository()
    s = repo.session
    stocks = [
        Stock(symbol='TST100', name='买信号股', industry='测试半导体', market='A', market_cap=100.0),
        Stock(symbol='TST101', name='池外参照股', industry='测试半导体', market='A', market_cap=50.0),
        Stock(symbol='TST102', name='停牌股', industry='测试半导体', market='A', market_cap=10.0),
        Stock(symbol='TST103', name='持仓股', industry='测试白酒', market='A', market_cap=200.0),
    ]
    s.add_all(stocks)
    klines = []
    for sym, c0, c1 in [('TST100', 10.0, 11.0), ('TST101', 20.0, 19.0), ('TST103', 5.0, 5.5)]:
        klines += [
            DailyKline(symbol=sym, trade_date=D0, open=c0, high=c0, low=c0, close=c0, volume=1, amount=1),
            DailyKline(symbol=sym, trade_date=D1, open=c1, high=c1, low=c1, close=c1, volume=1, amount=1),
        ]
    # TST102 只有 d0 没有 dn → 应被剔除
    klines.append(DailyKline(symbol='TST102', trade_date=D0, open=1, high=1, low=1, close=8.0, volume=1, amount=1))
    s.add_all(klines)
    s.add(Signal(symbol='TST100', name='买信号股', signal_date=date(2009, 1, 30),
                 action='buy', strategy_id='v13', price=1.0, confidence=0.8))
    pool = StockPool(name='回放池', pool_type='dynamic', symbols='{}', members=['TST100'])
    s.add(pool)
    s.flush()
    # D0 之前的日志：保证 has_pool_log_before 为 True（否则 scope 退化）
    s.add(PoolChangeLog(pool_id=pool.id, changed_at=datetime(2009, 1, 28, 10, 0),
                        action='add', symbol='TST100', reason='D前调入'))
    # D 之后调入 TST100 → 回放后 D 时点不在池内（但信号仍使其 in_scope）
    s.add(PoolChangeLog(pool_id=pool.id, changed_at=datetime(2009, 2, 10, 10, 0),
                        action='add', symbol='TST100', reason='D后调入'))
    s.add(PortfolioHolding(symbol='TST103', name='持仓股', quantity=100, avg_cost=5.0,
                           total_invested=500.0, added_date=date(2009, 1, 10), market='A'))
    s.commit()
    svc = HeatmapService()
    yield svc
    syms = ['TST100', 'TST101', 'TST102', 'TST103']
    s.query(DailyKline).filter(DailyKline.symbol.in_(syms)).delete()
    s.query(Signal).filter(Signal.symbol.in_(syms)).delete()
    s.query(PoolChangeLog).filter(PoolChangeLog.pool_id == pool.id).delete()
    s.query(StockPool).filter(StockPool.id == pool.id).delete()
    s.query(PortfolioHolding).filter(PortfolioHolding.symbol.in_(syms)).delete()
    s.query(Stock).filter(Stock.symbol.in_(syms)).delete()
    s.commit()


def _industry(data, name):
    return next((i for i in data['industries'] if i['name'] == name), None)


class TestGetHeatmap:
    def test_window_validation(self, seeded):
        r = seeded.get_heatmap(date='2009-02-02', window=7)
        assert r['success'] is False

    def test_basic_aggregation(self, seeded):
        r = seeded.get_heatmap(date='2009-02-02', window=1)
        assert r['success'] is True
        d = r['data']
        assert d['date'] == '2009-02-02'
        assert d['actual_end_date'] == '2009-02-03'
        semi = _industry(d, '测试半导体')
        assert semi is not None
        by_symbol = {s['symbol']: s for s in semi['stocks']}
        # 涨跌幅
        assert by_symbol['TST100']['change_pct'] == pytest.approx(10.0)
        assert by_symbol['TST101']['change_pct'] == pytest.approx(-5.0)
        # in_scope 口径：信号股 in_scope，池外参照股不 in_scope
        assert by_symbol['TST100']['in_scope'] is True
        assert by_symbol['TST101']['in_scope'] is False
        # 停牌剔除
        assert 'TST102' not in by_symbol
        assert d['excluded_count'] >= 1
        # 信号透传
        assert by_symbol['TST100']['signals'][0]['type'] == 'buy'
        assert by_symbol['TST100']['signals'][0]['strategy'] == 'v13'
        # D 前有池日志 → 未退化
        assert d['scope_degraded'] is False

    def test_holding_makes_in_scope_and_industry_present(self, seeded):
        r = seeded.get_heatmap(date='2009-02-02', window=1)
        liquor = _industry(r['data'], '测试白酒')
        assert liquor is not None
        assert liquor['stocks'][0]['symbol'] == 'TST103'
        assert liquor['stocks'][0]['in_scope'] is True

    def test_stance_derivation(self, seeded):
        r = seeded.get_heatmap(date='2009-02-02', window=1)
        semi = _industry(r['data'], '测试半导体')
        # 1 个 buy 信号、无 sell/remove → bullish
        assert semi['agent_stance'] == 'bullish'
        liquor = _industry(r['data'], '测试白酒')
        assert liquor['agent_stance'] == 'neutral'

    def test_partial_window(self, seeded):
        # window=20 但 2009-02-03 之后（对测试符号）无数据；
        # 若全表更晚日期存在则 dn 会更晚——断言结构而非具体日期
        r = seeded.get_heatmap(date='2009-02-02', window=20)
        assert r['success'] is True
        assert r['data']['window'] == 20
        assert 'partial' in r['data'] and 'actual_end_date' in r['data']

    def test_date_alignment_non_trade_day(self, seeded):
        # 2009-02-01 是周日 → 对齐到之前最近交易日（未必是 D0，取决于全表数据，只断言成功且结构齐）
        r = seeded.get_heatmap(date='2009-02-01', window=1)
        assert r['success'] is True
        assert r['data']['date'] <= '2009-02-01'

    def test_empty_when_no_klines(self, seeded):
        r = seeded.get_heatmap(date='1990-01-01', window=1)
        assert r['success'] is True
        assert r['data']['industries'] == []


@pytest.fixture
def seeded_no_pool_log():
    """只有池成员、无任何池变更日志 → 无法回放 → scope_degraded + 空结果"""
    repo = HeatmapRepository()
    s = repo.session
    s.add(Stock(symbol='TST200', name='无日志股', industry='测试无日志', market='A', market_cap=10.0))
    s.add_all([
        DailyKline(symbol='TST200', trade_date=D0, open=1, high=1, low=1, close=10.0, volume=1, amount=1),
        DailyKline(symbol='TST200', trade_date=D1, open=1, high=1, low=1, close=11.0, volume=1, amount=1),
    ])
    pool = StockPool(name='无日志池', pool_type='dynamic', symbols='{}', members=['TST200'])
    s.add(pool)
    s.commit()
    yield HeatmapService()
    s.query(DailyKline).filter(DailyKline.symbol == 'TST200').delete()
    s.query(StockPool).filter(StockPool.id == pool.id).delete()
    s.query(Stock).filter(Stock.symbol == 'TST200').delete()
    s.commit()


class TestScopeDegraded:
    def test_no_pool_log_degrades_scope(self, seeded_no_pool_log):
        r = seeded_no_pool_log.get_heatmap(date='2009-02-02', window=1)
        assert r['success'] is True
        d = r['data']
        # 退化后 in_scope 为空（无信号/持仓）→ 行业为空，且标记 degraded
        assert d['scope_degraded'] is True
        assert d['industries'] == []
