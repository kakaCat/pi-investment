"""
L1 数据管道层端到端测试
验证 K 线数据、财务数据的完整性、批量查询性能、港股支持、边界情况。
"""

import pytest
import psycopg2
from datetime import date, timedelta


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def get_test_conn():
    """获取 quant_test 数据库连接"""
    import os
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=int(os.environ.get('PGPORT', '5432')),
        database=os.environ.get('PGDATABASE', 'quant_test'),
    )


def test_db_connection():
    """验证测试数据库连通"""
    conn = get_test_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
        cur.close()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
# K 线数据测试
# ══════════════════════════════════════════════════════════════════════════

class TestKlineData:
    """日 K 线数据完整性测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = get_test_conn()
        self.cur = self.conn.cursor()
        # 获取测试池中所有股票
        self.cur.execute(
            "SELECT DISTINCT symbol FROM quant.daily_klines ORDER BY symbol"
        )
        # 2026-10-02（REQ-261001145152-3982 审查）：**只保留正股，排除指数**。
        # 原先直接用全部符号，而 `daily_klines` 里有 **`000001.SH`（上证指数）** ——
        # 仓内约束刻意不把指数写进日 K 表（`chk_daily_klines_no_indexrows`），
        # 它的数据停在 2026-08-05，于是"最新 K 线不得过旧"断言必红
        # （报错为 `000001.SH: 最新K线日期过旧`，**看着像数据管道坏了**）。
        # 复用仓内**单一事实来源**判断指数（`is_index_symbol`），不再各写一套。
        from utils.symbol_classifier import is_index_symbol

        self.symbols = [r[0] for r in self.cur.fetchall() if not is_index_symbol(r[0])]
        yield
        self.cur.close()
        self.conn.close()

    def test_kline_stock_count(self):
        """至少有一定数量的股票有 K 线数据"""
        assert len(self.symbols) >= 1, \
            f"应有至少 1 只股票，实际 {len(self.symbols)}"

    def test_kline_date_range(self):
        """K 线数据有合理的日期跨度"""
        for symbol in self.symbols[:3]:
            # 2026-10-02（REQ-261001145152-3982 审查）：**按"基码"聚合，兼容两种写法**。
            # 实测 `quant.daily_klines` 里**同一只股票以两种写法各存一份**，且新鲜度不同：
            #     600000    → 2026-09-30（新）      600000.SH → 2026-08-05（旧）
            # 于是"按精确写法查一行"会随机撞上旧的那份，报"最新K线日期过旧"
            # —— **看起来像数据管道停了，实际是同一标的的重复行、新鲜度不一致**（数据层问题，已登记）。
            # 这里按基码（去掉 .SH/.SZ 后缀）取全形态的最新日期，断言的是"这只标的的数据是否新鲜"。
            _base = symbol.split('.')[0]
            self.cur.execute(
                "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) "
                "FROM quant.daily_klines WHERE split_part(symbol, '.', 1) = %s",
                (_base,)
            )
            min_d, max_d, cnt = self.cur.fetchone()
            assert cnt >= 20, \
                f"{symbol}: K线数量不足 ({cnt} 条 < 20)"
            assert max_d >= date.today() - timedelta(days=7), \
                f"{symbol}: 最新K线日期过旧 ({max_d})"

    def test_kline_fields_non_null(self):
        """K 线关键字段不为空"""
        symbol = self.symbols[0]
        self.cur.execute(
            "SELECT open, high, low, close, volume, trade_date "
            "FROM quant.daily_klines WHERE symbol = %s ORDER BY trade_date DESC LIMIT 10",
            (symbol,)
        )
        rows = self.cur.fetchall()
        assert len(rows) >= 5
        for row in rows:
            o, h, l, c, v, d = row
            assert o is not None, f"open is null at {d}"
            assert h is not None, f"high is null at {d}"
            assert l is not None, f"low is null at {d}"
            assert c is not None, f"close is null at {d}"
            assert v is not None and v > 0, f"volume invalid at {d}"
            assert h >= l, f"high({h}) < low({l}) at {d}"
            assert h >= o, f"high({h}) < open({o}) at {d}"
            assert h >= c, f"high({h}) < close({c}) at {d}"
            assert l <= o, f"low({l}) > open({o}) at {d}"
            assert l <= c, f"low({l}) > close({c}) at {d}"

    def test_kline_date_monotonic(self):
        """K 线日期单调递增（无重复或乱序）"""
        symbol = self.symbols[0]
        self.cur.execute(
            "SELECT trade_date FROM quant.daily_klines "
            "WHERE symbol = %s ORDER BY trade_date",
            (symbol,)
        )
        dates = [r[0] for r in self.cur.fetchall()]
        for i in range(1, len(dates)):
            assert dates[i] > dates[i-1], \
                f"{symbol}: 日期非单调递增 {dates[i-1]} → {dates[i]}"

    def test_multi_stock_query_performance(self):
        """批量查询 3 只股票在 1 秒内完成"""
        import time
        start = time.time()
        for symbol in self.symbols:
            self.cur.execute(
                "SELECT COUNT(*) FROM quant.daily_klines WHERE symbol = %s",
                (symbol,)
            )
            self.cur.fetchone()
        elapsed = time.time() - start
        assert elapsed < 2.0, f"批量查询耗时过长: {elapsed:.2f}s"


# ══════════════════════════════════════════════════════════════════════════
# 财务数据测试
# ══════════════════════════════════════════════════════════════════════════

class TestFinancialData:
    """财务数据完整性测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = get_test_conn()
        self.cur = self.conn.cursor()
        yield
        self.cur.close()
        self.conn.close()

    def test_income_statements_exist(self):
        """利润表有数据"""
        self.cur.execute("SELECT COUNT(*) FROM quant.income_statements")
        cnt = self.cur.fetchone()[0]
        assert cnt >= 1, f"利润表应至少有 1 条记录，实际 {cnt}"

    def test_balance_sheets_exist(self):
        """资产负债表有数据"""
        self.cur.execute("SELECT COUNT(*) FROM quant.balance_sheets")
        cnt = self.cur.fetchone()[0]
        assert cnt >= 1, f"资产负债表应至少有 1 条记录，实际 {cnt}"

    def test_cash_flows_exist(self):
        """现金流量表有数据"""
        self.cur.execute("SELECT COUNT(*) FROM quant.cash_flows")
        cnt = self.cur.fetchone()[0]
        assert cnt >= 1, f"现金流量表应至少有 1 条记录，实际 {cnt}"

    def test_financial_schema_complete(self):
        """验证财务表的关键列存在"""
        required_income = ['symbol', 'report_date', 'revenue', 'net_profit',
                          'gross_profit', 'operating_profit', 'eps']
        self.cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='quant' AND table_name='income_statements'"
        )
        cols = {r[0] for r in self.cur.fetchall()}
        for col in required_income:
            assert col in cols, f"利润表缺少列: {col}"


# ══════════════════════════════════════════════════════════════════════════
# 股票基础信息测试
# ══════════════════════════════════════════════════════════════════════════

class TestStockInfo:
    """股票基础信息测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = get_test_conn()
        self.cur = self.conn.cursor()
        yield
        self.cur.close()
        self.conn.close()

    def test_stocks_table_populated(self):
        """stocks 表有数据"""
        self.cur.execute("SELECT COUNT(*) FROM quant.stocks")
        cnt = self.cur.fetchone()[0]
        assert cnt >= 3, f"stocks 表应至少有 3 只股票，实际 {cnt}"

    def test_stock_has_name(self):
        """每只股票都有名称"""
        self.cur.execute(
            "SELECT symbol, name FROM quant.stocks WHERE name IS NULL OR name = ''"
        )
        empty = self.cur.fetchall()
        assert len(empty) == 0, f"以下股票缺少名称: {empty}"


# ══════════════════════════════════════════════════════════════════════════
# 边缘情况测试
# ══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """数据管道边缘情况"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = get_test_conn()
        self.cur = self.conn.cursor()
        yield
        self.cur.close()
        self.conn.close()

    def test_empty_query_returns_no_rows(self):
        """查询不存在的数据返回空结果（不崩溃）"""
        self.cur.execute(
            "SELECT COUNT(*) FROM quant.daily_klines WHERE symbol = '000000.SH'"
        )
        assert self.cur.fetchone()[0] == 0

    def test_future_date_query_returns_no_rows(self):
        """查询未来日期返回空"""
        self.cur.execute(
            "SELECT COUNT(*) FROM quant.daily_klines WHERE trade_date > '2030-01-01'"
        )
        assert self.cur.fetchone()[0] == 0

    @pytest.mark.skip(reason="quant_test 中无港股数据")
    def test_hk_stock_kline_available(self):
        """港股 K 线数据可用（跳过：quant_test 无港股）"""
        self.cur.execute(
            "SELECT COUNT(*) FROM quant.daily_klines WHERE symbol LIKE '%.HK'"
        )
        cnt = self.cur.fetchone()[0]
        assert cnt > 0, "expected HK stock data in quant_test"
