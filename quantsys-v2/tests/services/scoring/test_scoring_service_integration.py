"""OpportunityScoringService 动态评分集成测试"""
import pytest
from datetime import datetime, timedelta
from application.services.opportunity_scoring_service import OpportunityScoringService
from adapters.outbound.repositories import KlineORMRepository, StockORMRepository
from adapters.shared.services import get_factor_adapter


@pytest.fixture
def service(db_connection):
    kline_repo = KlineORMRepository()
    kline_repo.db = db_connection
    stock_repo = StockORMRepository()
    stock_repo.db = db_connection
    return OpportunityScoringService(kline_repo, stock_repo, get_factor_adapter())


def _seed_stock(db, symbol, name, pe, roe, gross_margin, revenue_growth):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO quant.stocks (symbol, name, market, pe, roe, gross_margin,
                                  revenue_growth, debt_ratio, updated_at)
        VALUES (%s, %s, 'SH', %s, %s, %s, %s, 40, NOW())
        ON CONFLICT (symbol) DO UPDATE SET
          pe=EXCLUDED.pe, roe=EXCLUDED.roe,
          gross_margin=EXCLUDED.gross_margin,
          revenue_growth=EXCLUDED.revenue_growth
    """, (symbol, name, pe, roe, gross_margin, revenue_growth))
    db.commit()
    cursor.close()


def _seed_klines(db, symbol, days=250):
    cursor = db.cursor()
    for i in range(days):
        date = (datetime.now() - timedelta(days=days - i - 1)).strftime('%Y-%m-%d')
        price = 100 + (i % 20) - 10  # 波动序列，RSI 有值
        cursor.execute("""
            INSERT INTO quant.daily_klines
            (symbol, trade_date, open, high, low, close, volume, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, trade_date) DO NOTHING
        """, (symbol, date, price, price + 2, price - 2, price,
              1000000 + i * 1000, (1000000 + i * 1000) * price))
    db.commit()
    cursor.close()


def _seed_quarterly(db, symbol, margins):
    cursor = db.cursor()
    base = datetime(2026, 3, 31)
    for i, gm in enumerate(margins):
        d = (base - timedelta(days=90 * i)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO quant.income_statements
            (symbol, report_date, period_type, revenue, gross_margin, net_profit)
            VALUES (%s, %s, 'Q', 1000000, %s, 100000)
        """, (symbol, d, gm))
    db.commit()
    cursor.close()


@pytest.fixture
def seeded(db_connection):
    symbols = ['TESTA', 'TESTB', 'TESTC']
    _seed_stock(db_connection, 'TESTA', '测试成长', 40, 10, 50, 60)
    _seed_stock(db_connection, 'TESTB', '测试价值', 5, 25, 20, 3)
    _seed_stock(db_connection, 'TESTC', '测试周期', 8, 18, 20, 5)
    for s in symbols:
        _seed_klines(db_connection, s)
    _seed_quarterly(db_connection, 'TESTA', [30, 30, 30, 30, 30, 30, 30, 30])
    _seed_quarterly(db_connection, 'TESTB', [20, 20, 20, 20, 20, 20, 20, 20])
    # 周期股：毛利率大幅摆动（pstdev=10 ≥ 8）
    _seed_quarterly(db_connection, 'TESTC', [30, 10, 30, 10, 30, 10, 30, 10])
    yield symbols
    cursor = db_connection.cursor()
    for s in symbols:
        cursor.execute("DELETE FROM quant.daily_klines WHERE symbol=%s", (s,))
        cursor.execute("DELETE FROM quant.income_statements WHERE symbol=%s", (s,))
        cursor.execute("DELETE FROM quant.stocks WHERE symbol=%s", (s,))
    db_connection.commit()
    cursor.close()


def test_scan_returns_evidence_chain(service, seeded):
    """响应含完整证据链：breakdown + reasons + applied_context"""
    results = service.score_stocks(seeded, filters={}, no_cache=True)
    assert len(results) >= 2
    for opp in results:
        assert 'score_breakdown' in opp
        assert 'reasons' in opp and len(opp['reasons']) > 0
        assert 'applied_context' in opp
        ctx = opp['applied_context']
        assert ctx['profile'] in ('growth', 'value', 'cyclical', 'balanced')
        assert 'final_weights' in ctx
        assert abs(sum(ctx['final_weights'].values()) - 1.0) < 0.01
        assert 'market_regime' in ctx
        # 证据链可复算：Σ(total × weight) ≈ score
        recomputed = sum(d['total'] * d['weight']
                         for d in opp['score_breakdown'].values())
        assert abs(recomputed - opp['score']) < 1.0


def test_profile_classification_in_scan(service, seeded):
    """周期股被正确分类且带 cycle 维度"""
    results = {r['symbol']: r for r in
               service.score_stocks(seeded, filters={}, no_cache=True)}
    if 'TESTC' in results:
        ctx = results['TESTC']['applied_context']
        assert ctx['profile'] == 'cyclical'
        assert 'cycle' in ctx['final_weights']
        assert 'cycle' in results['TESTC']['score_breakdown']


def test_fundamental_pe_not_always_zero(service, seeded):
    """key 映射修复回归：低 PE 价值股 PE 维度应得正分（此前恒 0）"""
    results = {r['symbol']: r for r in
               service.score_stocks(seeded, filters={}, no_cache=True)}
    if 'TESTB' in results:
        pe_score = results['TESTB']['score_breakdown'] \
            ['fundamental']['details']['pe']
        assert pe_score > 0


def test_weights_override(service, seeded):
    """显式 weights 覆盖动态机制并注明"""
    results = service.score_stocks(
        seeded, filters={},
        weights={'technical': 0.6, 'fundamental': 0.3, 'capital': 0.1},
        no_cache=True)
    for opp in results:
        ctx = opp['applied_context']
        assert ctx['weights_source'] == 'override'
        assert any('指定权重' in r for r in opp['reasons'])


def test_diagnostics_extended(service, seeded):
    """diagnostics 含 degraded / repair_report / elapsed_ms"""
    service.score_stocks(seeded, filters={}, no_cache=True)
    diag = service.last_diagnostics
    assert 'degraded' in diag
    assert 'repair_report' in diag
    assert 'elapsed_ms' in diag
    assert diag['scored'] >= 1


def test_legacy_fields_kept(service, seeded):
    """旧字段保留（web 前端/老调用方不破）"""
    results = service.score_stocks(seeded, filters={}, no_cache=True)
    for opp in results:
        for f in ('symbol', 'name', 'score', 'technical_score',
                  'fundamental_score', 'capital_score', 'reason',
                  'risk_level', 'signal_type'):
            assert f in opp, f'missing legacy field: {f}'
