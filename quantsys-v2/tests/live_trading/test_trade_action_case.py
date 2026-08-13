"""simulation_trades action 大小写契约测试（2026-08-12；2026-08-13 升级）

回归背景：simulation_trades.action 曾存在两套写入约定——SimulationTrader/portfolio.py
写大写 'BUY'/'SELL'，AccountTradingService→repo.add_trade 写小写 'buy'/'sell'。
而 SimulationTrader._rebuild_portfolio_from_trades 的 SQL 只匹配大写，
小写行落入 ELSE 0 → 8/5 三笔卖出被无视 → 幽灵持仓注水估值（131069 vs 真实 92614，
+31% 假盈利），且会毒害调仓/止损决策。

2026-08-13 升级：契约上收到 ORM @validates + DB CHECK 双重强制
（migrate_20260813_action_case_unify.py），小写值在 DB 层直接被拒。
本文件的混合大小写用例改为全大写数据（重建逻辑不变式不变），
另增 CHECK 拒绝小写直插的约束生效证据。
"""
import pytest

from adapters.outbound.repositories.simulation_repository import normalize_action
from live_trading.simulation_trader import SimulationTrader


# ── 写入侧：归一化 ───────────────────────────────────────

class TestNormalizeAction:
    def test_lowercase_buy_becomes_upper(self):
        assert normalize_action('buy') == 'BUY'

    def test_lowercase_sell_becomes_upper(self):
        assert normalize_action('sell') == 'SELL'

    def test_upper_passthrough(self):
        assert normalize_action('BUY') == 'BUY'
        assert normalize_action('SELL') == 'SELL'

    def test_invalid_action_rejected(self):
        with pytest.raises(ValueError):
            normalize_action('hold')


# ── 读取侧：净持仓重建（库内全大写契约） ──────────────────

@pytest.fixture
def trades_table():
    from scripts.migrate_20260813_action_case_unify import run_migration
    run_migration()  # 幂等，确保 quant_test 已带 CHECK 约束
    from infrastructure.persistence.database.engine import get_engine
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM quant.simulation_trades WHERE account_name = 'test_acct'")
        conn.commit()
        yield conn
    finally:
        conn.close()


def _insert(conn, rows):
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO quant.simulation_trades "
        "(account_name, symbol, action, shares, price, filled_price, amount, trade_date) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE)",
        [(acct, sym, act, sh, px, px, sh * px) for acct, sym, act, sh, px in rows],
    )
    conn.commit()


def _bare_trader(account='test_acct'):
    t = object.__new__(SimulationTrader)
    t.account_name = account
    return t


class TestRebuildPortfolioMixedCase:
    def test_sell_nets_out_position(self, trades_table):
        """8/5 事故形态：BUY + SELL 等量 → 净持仓必须为 0，不得有幽灵持仓"""
        _insert(trades_table, [
            ('test_acct', '300561', 'BUY', 700, 17.11),
            ('test_acct', '300561', 'SELL', 700, 18.71),
        ])
        pf = _bare_trader()._rebuild_portfolio_from_trades()
        assert '300561' not in pf

    def test_partial_fill(self, trades_table):
        _insert(trades_table, [
            ('test_acct', '300008', 'BUY', 2000, 6.08),
            ('test_acct', '300008', 'SELL', 500, 6.50),
        ])
        pf = _bare_trader()._rebuild_portfolio_from_trades()
        assert pf['300008']['shares'] == 1500

    def test_avg_price_uses_buys(self, trades_table):
        _insert(trades_table, [
            ('test_acct', '300765', 'BUY', 100, 40.0),
            ('test_acct', '300765', 'BUY', 100, 42.0),
        ])
        pf = _bare_trader()._rebuild_portfolio_from_trades()
        assert pf['300765']['shares'] == 200
        assert pf['300765']['avg_price'] == pytest.approx(41.0)


class TestActionCheckConstraint:
    def test_raw_sql_lowercase_insert_rejected(self, trades_table):
        """CHECK 约束生效证据：绕过 ORM 的 raw SQL 小写直插必须被 DB 拒绝"""
        import psycopg2
        cur = trades_table.cursor()
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO quant.simulation_trades "
                "(account_name, symbol, action, shares, price, filled_price, amount, trade_date) "
                "VALUES ('test_acct', '600519', 'buy', 100, 10.0, 10.0, 1000.0, CURRENT_DATE)")
            trades_table.commit()
        trades_table.rollback()
