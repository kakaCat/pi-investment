"""kline_update_job 选股 SQL 的过滤测试（真实 quant DB）

背景（2026-08-02）：192 只疑似退市股每次运行都排在队列最前（陈旧度排序），
浪费 provider 请求 → 新增 is_delisted 过滤，选股 SQL 必须直接过滤。

背景（2026-09-11 w-23c70356）：quant.stocks 曾被测试数据污染（600000.SH…600009.SH，
name='Test'），同步任务把它们当宇宙成员逐日写出 1,213 行伪 K 线——其中
600001/600002/600003/600005（邯郸钢铁/齐鲁石化/ST东北高/武钢股份）早已退市却出现
2026 年"行情"，且与真实裸码同日收盘价 0 天相同（改名合并会污染真数据）。清理
1,507 行后选股 SQL 增加"6 位 A 股裸码"形状过滤（防护第一层）；第二层是写入循环
兜底，见 tests/test_kline_update_throttle.py::test_nonstandard_symbol_skipped。
"""
import pytest

from infrastructure.jobs.kline_update_job import build_stock_query
from infrastructure.persistence.database.engine import get_engine
from infrastructure.persistence.orm.models.stock import Stock
from adapters.outbound.repositories.heatmap_repository import HeatmapRepository

# 6 位合成测试码（避开真实 A 股代码空间，避免与线上数据撞 PK）
NORMAL = '999901'
DELISTED = '999902'
NAME_TUI = '999903'
GEM_NORMAL = '301901'
GEM_DELISTED = '301902'
_ALL_TEST_SYMBOLS = [NORMAL, DELISTED, NAME_TUI, GEM_NORMAL, GEM_DELISTED]


@pytest.fixture
def seeded_stocks():
    s = HeatmapRepository().session  # 借用其 session（session 通用）
    s.query(Stock).filter(Stock.symbol.in_(_ALL_TEST_SYMBOLS)).delete()
    s.add_all([
        Stock(symbol=NORMAL, name='正常股', market='A', is_delisted=False),
        Stock(symbol=DELISTED, name='退市股', market='A', is_delisted=True),
        # 名称带"退"但未标记的也应被旧名称规则拦住
        Stock(symbol=NAME_TUI, name='XX退', market='A', is_delisted=False),
        # 创业板形状（gem 分支按 300/301 前缀选）
        Stock(symbol=GEM_NORMAL, name='创业正常', market='A', is_delisted=False),
        Stock(symbol=GEM_DELISTED, name='创业退市', market='A', is_delisted=True),
        # 注意：不往 stocks 塞含点伪代码——测试库 quant_test 里已存在 600000.SH
        # 及其持仓子行（FK portfolio_holdings_symbol_fkey），塞/删都会触发 FK 冲突。
    ])
    s.commit()
    yield
    s.query(Stock).filter(Stock.symbol.in_(_ALL_TEST_SYMBOLS)).delete()
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
        assert NORMAL in symbols
        assert DELISTED not in symbols   # is_delisted 过滤
        assert NAME_TUI not in symbols   # 名称"退"过滤保留

    def test_gem_scope_excludes_delisted(self, seeded_stocks):
        sql, params = build_stock_query('gem', None)
        symbols = _run_query(sql, params)
        assert GEM_NORMAL in symbols
        assert GEM_DELISTED not in symbols

    def test_specific_symbols_unfiltered(self, seeded_stocks):
        """显式指定的 symbols 不做退市过滤（调用方明确要查就尊重）"""
        sql, params = build_stock_query('all', [NORMAL, DELISTED])
        symbols = _run_query(sql, params)
        assert set(symbols) == {NORMAL, DELISTED}


class TestPseudoSymbolFilter:
    """伪代码（含点后缀/非 6 位）不得进入同步宇宙——历史上写出过 1,213 行伪 K 线

    这里不去刻意往 stocks 表塞污染行：库是共享的（多会话并行 + FK 约束
    portfolio_holdings_symbol_fkey），塞行会在清理时触发 FK 冲突。改为直接断言
    "四个 scope 的实际查询结果里不存在非 6 位符号"——这正是不变量本身，
    且任何窗口往 stocks 里写脏行都会被本测试立刻抓住。
    """

    def test_no_nonstandard_symbol_in_any_scope(self):
        import re
        for scope in ('all', 'gem', 'batch', 'priority'):
            sql, params = build_stock_query(scope, None)
            bad = [s for s in _run_query(sql, params) if not re.fullmatch(r'\d{6}', str(s))]
            assert bad == [], f'{scope} 选出了非标准代码: {bad[:5]}'

    def test_shape_filter_survives_fstring_interpolation(self):
        """batch 分支是 f-string：{6} 必须原样存活（不会被当占位符求值成 6）

        2026-09-11 修复时实际踩到：把 '^[0-9]{6}$' 直接写进 batch 的 f-string，
        Python 会渲染成 '^[0-9]6$'（匹配"一个数字后跟字面量 6"），过滤静默失效。
        故既断言正确形态存在，也断言错误形态不存在。
        """
        sql, _ = build_stock_query('batch', None)
        assert sql.count("[0-9]{6}") == 3      # P0 池内 + P1 热点 + 陈旧补充
        assert "[0-9]6" not in sql
        for scope in ('all', 'gem', 'priority'):
            s, _p = build_stock_query(scope, None)
            assert "[0-9]{6}" in s, f'{scope} 缺形状过滤'
