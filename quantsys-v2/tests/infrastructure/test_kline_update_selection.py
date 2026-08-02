"""kline_update_job 选股 SQL 的 is_delisted 过滤测试（真实 quant_test DB）

背景（2026-08-02）：192 只疑似退市股（名称不带"退"、6 月来无 K 线）每次运行都排在
队列最前（陈旧度排序），浪费 ~192×3 次 provider 请求。新增 is_delisted 字段后，
选股 SQL 必须直接过滤。
"""
import pytest

from infrastructure.jobs.kline_update_job import build_stock_query
from infrastructure.persistence.database.engine import get_engine
from infrastructure.persistence.orm.models.stock import Stock
from adapters.outbound.repositories.heatmap_repository import HeatmapRepository


@pytest.fixture
def seeded_stocks():
    repo = HeatmapRepository()  # 借用其 session（model=DailyKline，但 session 通用）
    s = repo.session
    s.add_all([
        Stock(symbol='TST600', name='正常股', market='A', is_delisted=False),
        Stock(symbol='TST601', name='退市股', market='A', is_delisted=True),
        # 名称带"退"但未标记的也应被旧名称规则拦住
        Stock(symbol='TST602', name='XX退', market='A', is_delisted=False),
    ])
    s.commit()
    yield
    s.query(Stock).filter(Stock.symbol.in_(['TST600', 'TST601', 'TST602'])).delete()
    s.commit()


def _run_query(sql, params):
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


class TestBuildStockQuery:
    def test_all_scope_excludes_delisted(self, seeded_stocks):
        sql, params = build_stock_query('all', None)
        symbols = _run_query(sql, params)
        assert 'TST600' in symbols
        assert 'TST601' not in symbols   # is_delisted 过滤
        assert 'TST602' not in symbols   # 名称"退"过滤保留

    def test_gem_scope_excludes_delisted(self, seeded_stocks):
        s = HeatmapRepository().session
        s.add_all([
            Stock(symbol='TST300', name='创业正常', market='A', is_delisted=False),
            Stock(symbol='TST301', name='创业退市', market='A', is_delisted=True),
        ])
        # gem 分支按 symbol LIKE '300%' 过滤，测试符号需匹配
        from infrastructure.persistence.orm.models.stock import Stock as S
        s.query(S).filter(S.symbol.in_(['TST300', 'TST301'])).delete()
        s.add_all([
            S(symbol='300TST', name='创业正常', market='A', is_delisted=False),
            S(symbol='301TST', name='创业退市', market='A', is_delisted=True),
        ])
        s.commit()
        try:
            sql, params = build_stock_query('gem', None)
            symbols = _run_query(sql, params)
            assert '300TST' in symbols
            assert '301TST' not in symbols
        finally:
            s.query(S).filter(S.symbol.in_(['300TST', '301TST'])).delete()
            s.commit()

    def test_specific_symbols_unfiltered(self, seeded_stocks):
        """显式指定的 symbols 不过滤（调用方明确要查就尊重）"""
        sql, params = build_stock_query('all', ['TST600', 'TST601'])
        symbols = _run_query(sql, params)
        assert set(symbols) == {'TST600', 'TST601'}
