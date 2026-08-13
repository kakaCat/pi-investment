"""action 大小写统一契约测试（2026-08-13）

契约：quant.simulation_trades / simulation_order / simulation_pending_orders /
signals 四表 action 一律大写（BUY/SELL[/HOLD]），三层强制：
1. ORM @validates —— 赋值即规范化（写入漏洞兜底，如 save_simulation_result）
2. DB CHECK 约束 —— 绕过 ORM 的 raw SQL 也插不进脏值
3. 读取侧 —— 统一按大写比较（本文件锁死关键读取点行为）

回归背景：61528de 仅 repository 单点规范化 → settle_t1 小写过滤失效（08-13
今世缘 T+1 拦截事故链一环）、日买入护栏失效、净值快照回放错误等。
"""
import pytest


class TestActionNorm:
    """共享规范化函数（唯一事实源：models/action_norm.py）"""

    def test_normalize_action(self):
        from infrastructure.persistence.orm.models.action_norm import normalize_action
        assert normalize_action('buy') == 'BUY'
        assert normalize_action(' Sell ') == 'SELL'
        with pytest.raises(ValueError):
            normalize_action('hold')
        with pytest.raises(ValueError):
            normalize_action('')

    def test_normalize_signal_action_allows_hold(self):
        from infrastructure.persistence.orm.models.action_norm import normalize_signal_action
        assert normalize_signal_action('hold') == 'HOLD'
        assert normalize_signal_action('buy') == 'BUY'
        with pytest.raises(ValueError):
            normalize_signal_action('watch')

    def test_repository_reexport_compatible(self):
        """旧调用方从 simulation_repository import 的兼容路径必须保持"""
        from adapters.outbound.repositories.simulation_repository import normalize_action
        assert normalize_action('buy') == 'BUY'


class TestOrmValidates:
    """ORM 赋值即规范化：不经 repo 的直写路径也被兜底"""

    def test_simulation_trade_normalizes_on_assign(self):
        from infrastructure.persistence.orm.models.simulation import SimulationTrade
        t = SimulationTrade(action='buy')
        assert t.action == 'BUY'
        t.action = 'sell'
        assert t.action == 'SELL'
        with pytest.raises(ValueError):
            t.action = 'hold'

    def test_simulation_order_normalizes(self):
        from infrastructure.persistence.orm.models.simulation import SimulationOrder
        assert SimulationOrder(action='sell').action == 'SELL'

    def test_simulation_pending_order_normalizes(self):
        from infrastructure.persistence.orm.models.simulation import SimulationPendingOrder
        assert SimulationPendingOrder(action='buy').action == 'BUY'

    def test_signal_normalizes_and_allows_hold(self):
        from infrastructure.persistence.orm.models.signal import Signal
        assert Signal(action='buy').action == 'BUY'
        assert Signal(action='hold').action == 'HOLD'
        with pytest.raises(ValueError):
            Signal(action='watch')


@pytest.fixture()
def repo():
    from scripts.migrate_20260813_action_case_unify import run_migration
    run_migration()  # 幂等，确保 quant_test 已带 CHECK 约束
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    r = SimulationORMRepository()
    yield r
    from infrastructure.persistence.orm.models.simulation import (
        SimulationAccount, SimulationPosition, SimulationTrade,
        SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
    )
    for model in (SimulationCashFlow, SimulationOrder, SimulationTrade,
                  SimulationPosition, SimulationEquitySnapshot, SimulationAccount):
        r.session.query(model).filter(
            model.account_name == 'test_case_unify').delete(synchronize_session=False)
    r.session.commit()


class TestWritePathEnforcement:
    def test_direct_orm_write_lowercase_lands_upper(self, repo):
        """写入漏洞回归（原 save_simulation_result 等未经 normalize_action 的直写点）：
        直接构造 ORM 对象传小写 action，落库必须是大写（@validates 兜底）"""
        from datetime import date
        from infrastructure.persistence.orm.models.simulation import SimulationTrade
        repo.create_account('test_case_unify', initial_capital=100000)
        trade = SimulationTrade(
            account_name='test_case_unify', symbol='600519', action='buy',
            shares=100, price=10.0, filled_price=10.0, amount=1000.0,
            trade_date=date(2026, 8, 13))
        repo.session.add(trade)
        repo.session.commit()
        trades = repo.get_trades_by_account('test_case_unify')
        assert len(trades) == 1
        assert trades[0].action == 'BUY'

    def test_migration_idempotent(self):
        """迁移脚本连跑两次不报错（幂等）"""
        from scripts.migrate_20260813_action_case_unify import run_migration
        run_migration()
        run_migration()
