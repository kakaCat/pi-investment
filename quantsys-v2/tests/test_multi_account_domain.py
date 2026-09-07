"""多账户域模型测试"""
import pytest
from datetime import date, datetime
from types import SimpleNamespace


@pytest.fixture(autouse=True)
def _fixed_trading_clock(monkeypatch):
    """固定交易时段时钟：49d0b2b 引入交易时段护栏后，非交易时段跑本文件
    一律 422。交易判定是生产行为、非本文件测试目标，统一注入
    固定交易时间 + 常真日历，使测试与时间无关。"""
    from application.services import account_trading_service as ats
    real_init = ats.AccountTradingService.__init__

    def patched_init(self, repo=None, calendar=None, now_fn=None):
        real_init(self, repo=repo, calendar=calendar, now_fn=now_fn)
        if now_fn is None:
            self.now_fn = lambda: datetime(2026, 8, 3, 10, 0)  # 周一 10:00，交易时段内
        if calendar is None:
            self.calendar = SimpleNamespace(is_trading_day=lambda d: True)

    monkeypatch.setattr(ats.AccountTradingService, '__init__', patched_init)


class TestORMModels:
    """Task 1: 模型结构"""

    def test_account_has_new_columns(self):
        from infrastructure.persistence.orm.models.simulation import SimulationAccount
        cols = {c.name for c in SimulationAccount.__table__.columns}
        assert 'cash_available' in cols
        assert 'cash_frozen' in cols
        assert 'position_value' in cols
        assert 'initial_capital' in cols
        assert 'display_name' in cols
        assert 'strategy_name' in cols
        assert 'status' in cols
        assert 'cash' not in cols  # 旧列已改名

    def test_position_has_t1_columns(self):
        from infrastructure.persistence.orm.models.simulation import SimulationPosition
        cols = {c.name for c in SimulationPosition.__table__.columns}
        assert 'shares_total' in cols
        assert 'shares_available' in cols
        assert 'avg_cost' in cols
        assert 'profit_total' in cols
        assert 'profit_total_rate' in cols
        assert 'profit_today' in cols
        assert 'shares' not in cols

    def test_trade_has_realized_pnl_columns(self):
        from infrastructure.persistence.orm.models.simulation import SimulationTrade
        cols = {c.name for c in SimulationTrade.__table__.columns}
        for col in ('order_id', 'transfer_fee', 'realized_pnl', 'realized_pnl_rate', 'reason'):
            assert col in cols, f"missing {col}"

    def test_new_models_exist(self):
        from infrastructure.persistence.orm.models.simulation import (
            SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
        )
        order_cols = {c.name for c in SimulationOrder.__table__.columns}
        assert {'account_name', 'action', 'order_type', 'symbol', 'shares',
                'status', 'filled_shares', 'avg_filled_price', 'reason'} <= order_cols
        flow_cols = {c.name for c in SimulationCashFlow.__table__.columns}
        assert {'account_name', 'flow_type', 'amount', 'balance_after'} <= flow_cols
        snap = SimulationEquitySnapshot.__table__
        snap_cols = {c.name for c in snap.columns}
        assert {'account_name', 'snapshot_date', 'cash', 'position_value',
                'total_value', 'daily_return', 'cumulative_return', 'drawdown'} <= snap_cols


class TestMigration:
    """Task 2: 迁移脚本幂等 + 结果正确"""

    def test_migration_idempotent(self):
        from scripts.migrate_20260720_multi_account import run_migration
        run_migration()   # 第一次
        run_migration()   # 第二次不报错即幂等

        from sqlalchemy import inspect
        from infrastructure.persistence.database.engine import get_engine
        insp = inspect(get_engine())
        acc_cols = {c['name'] for c in insp.get_columns('simulation_account', schema='quant')}
        assert 'cash_available' in acc_cols and 'cash' not in acc_cols
        pos_cols = {c['name'] for c in insp.get_columns('simulation_positions', schema='quant')}
        assert 'shares_total' in pos_cols and 'shares' not in pos_cols
        for table in ('simulation_order', 'simulation_cash_flow', 'simulation_equity_snapshot'):
            assert insp.has_table(table, schema='quant'), f"missing table {table}"


TEST_ACCOUNTS = ('test_acc_a', 'test_acc_b')


@pytest.fixture()
def repo():
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    from scripts.migrate_20260720_multi_account import run_migration
    run_migration()  # 幂等，确保测试库结构就位
    r = SimulationORMRepository()
    yield r
    # 清理测试账户数据
    from infrastructure.persistence.orm.models.simulation import (
        SimulationAccount, SimulationPosition, SimulationTrade,
        SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
    )
    for model in (SimulationCashFlow, SimulationOrder, SimulationTrade,
                  SimulationPosition, SimulationEquitySnapshot, SimulationAccount):
        r.session.query(model).filter(model.account_name.in_(TEST_ACCOUNTS)).delete(
            synchronize_session=False)
    r.session.commit()


class TestRepository:
    """Task 3: Repository 扩展"""

    def test_create_account_writes_deposit_flow(self, repo):
        acc = repo.create_account('test_acc_a', initial_capital=200000,
                                  display_name='测试账户A', strategy_name=None)
        assert acc is not None
        assert float(acc.cash_available) == 200000
        assert float(acc.initial_capital) == 200000
        assert acc.status == 'active'
        flows = repo.get_cash_flows('test_acc_a')
        assert len(flows) == 1
        assert flows[0].flow_type == 'deposit'
        assert float(flows[0].balance_after) == 200000

    def test_list_account_summaries(self, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.create_account('test_acc_b', initial_capital=50000)
        summaries = repo.list_account_summaries()
        names = {s['account_name'] for s in summaries}
        assert {'test_acc_a', 'test_acc_b'} <= names
        a = next(s for s in summaries if s['account_name'] == 'test_acc_a')
        assert a['positions_count'] == 0
        assert a['cash_available'] == 100000.0

    def test_add_trade_auto_writes_cash_flow(self, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.add_trade(account_name='test_acc_a', symbol='600519', action='buy',
                       shares=100, price=10.0, filled_price=10.0,
                       commission=5.0, stamp_duty=0.0)
        result = repo.verify_cash_flow_invariant('test_acc_a')
        # 100000 - (1000 + 5) = 98995
        assert result['flow_balance'] == pytest.approx(98995.0, abs=0.01)
        # 账户 cash 尚未同步（由调用方负责），此处只验流水链
        assert result['flow_count'] == 2

    def test_equity_snapshot_upsert(self, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.upsert_equity_snapshot('test_acc_a', cash=60000, position_value=40000,
                                    total_value=100000, daily_return=0.01,
                                    cumulative_return=0.0, drawdown=0.0)
        repo.upsert_equity_snapshot('test_acc_a', cash=60000, position_value=41000,
                                    total_value=101000, daily_return=0.01,
                                    cumulative_return=0.01, drawdown=0.0)
        snaps = repo.get_equity_snapshots('test_acc_a')
        assert len(snaps) == 1  # 同日 upsert 不产生第二条
        assert float(snaps[0].total_value) == 101000

    def test_settle_t1(self, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.upsert_position('test_acc_a', '600519', shares_total=100, avg_cost=10.0,
                             shares_available=0)
        n = repo.settle_t1('test_acc_a')
        assert n == 1
        pos = repo.get_position('test_acc_a', '600519')
        assert pos.shares_available == 100

    def test_settle_t1_same_day_buy_not_sellable(self, repo):
        """回归（2026-08-13）：settle_t1 读取侧曾写死小写 action='buy'，与写入侧
        normalize_action 大写契约不匹配 → 当日买入量恒计为 0 → 当日买入的股数
        在结转后被错误放行为可卖（T+1 形同虚设）。本测试锁死：当日结算不得放行
        当日买入。"""
        from application.services.account_trading_service import AccountTradingService
        repo.create_account('test_acc_a', initial_capital=100000)
        trading = AccountTradingService(repo=repo)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：当日买入不得被当日结转放行', price=10.0)
        n = repo.settle_t1('test_acc_a')  # 默认 today=真实今天，与成交 trade_date 同日
        assert n == 1
        pos = repo.get_position('test_acc_a', '600519')
        assert pos.shares_available == 0  # 当日买入不得因结转放行


class TestAccountTradingService:
    """Task 4: 手工交易事务"""

    @pytest.fixture()
    def trading(self, repo):
        from application.services.account_trading_service import AccountTradingService
        return AccountTradingService(repo=repo)

    def test_buy_success_full_chain(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        result = trading.execute_trade(
            'test_acc_a', 'buy', '600519', shares=100,
            reason='测试买入：技术面突破+放量', price=10.0)
        assert result['order_status'] == 'filled'
        assert result['shares'] == 100
        acc = repo.get_account('test_acc_a')
        # 费用: 佣金 max(1000*0.00025,5)=5, 印花税0, 过户费 1000*0.00001=0.01
        assert float(acc.cash_available) == pytest.approx(100000 - 1000 - 5 - 0.01, abs=0.01)
        pos = repo.get_position('test_acc_a', '600519')
        assert pos.shares_total == 100
        assert pos.shares_available == 0  # T+1 当日不可卖
        inv = repo.verify_cash_flow_invariant('test_acc_a')
        assert inv['invariant_ok'], inv

    def test_sell_t1_blocked_same_day(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：技术面突破+放量', price=10.0)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'sell', '600519', shares=100,
                                  reason='测试卖出：当日卖出应被T+1拦截', price=11.0)
        assert exc.value.status_code == 422
        assert 'T+1' in str(exc.value) or '可卖' in str(exc.value)

    def test_sell_t1_blocked_carries_details(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：技术面突破+放量', price=10.0)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'sell', '600519', shares=100,
                                  reason='测试卖出：当日卖出应被T+1拦截', price=11.0)
        assert exc.value.status_code == 422
        assert exc.value.details == {'sellable_shares': 0, 'symbol': '600519'}

    def test_sell_t1_partial_available_details(self, repo, trading):
        """部分可卖：昨日买入 100（已结转可卖）+ 今日买入 100（不可卖），卖 200 被卡"""
        repo.create_account('test_acc_a', initial_capital=100000)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：第一笔建仓', price=10.0)
        repo.settle_t1('test_acc_a', today=date(2099, 1, 1))  # 模拟次日结转
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：次日加仓部分不可卖', price=10.0)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'sell', '600519', shares=200,
                                  reason='测试卖出：超出可卖数量应被拦截', price=11.0)
        assert exc.value.details == {'sellable_shares': 100, 'symbol': '600519'}

    def test_non_t1_error_has_no_details(self, repo, trading):
        """向后兼容：非 T+1 的 TradingError details 为 None"""
        repo.create_account('test_acc_a', initial_capital=1000)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=1000,
                                  reason='测试买入：资金不足应被拒绝', price=10.0)
        assert exc.value.status_code == 422
        assert exc.value.details is None

    def test_sell_next_day_with_realized_pnl(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：技术面突破+放量', price=10.0)
        repo.settle_t1('test_acc_a', today=date(2099, 1, 1))  # 模拟次日
        result = trading.execute_trade('test_acc_a', 'sell', '600519', shares=100,
                                       reason='测试卖出：止盈离场验证盈亏', price=11.0)
        assert result['realized_pnl'] is not None
        assert result['realized_pnl'] > 0  # 涨价卖出必盈利
        inv = repo.verify_cash_flow_invariant('test_acc_a')
        assert inv['invariant_ok'], inv

    def test_buy_insufficient_cash(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=1000)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=1000,
                                  reason='测试买入：资金不足应被拒绝', price=10.0)
        assert exc.value.status_code == 422

    def test_archived_account_rejected(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.archive_account('test_acc_a')
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                                  reason='测试买入：归档账户应被拒绝', price=10.0)
        assert exc.value.status_code == 409

    def test_reason_required(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                                  reason='太短', price=10.0)
        assert exc.value.status_code == 400

    def test_single_position_risk_limit(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            # 买入 5 万，超过总资产 30%
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=5000,
                                  reason='测试买入：单票超限应被拒绝', price=10.0)
        assert exc.value.status_code == 422



class TestStrategyAccountValidation:
    """Task 9: 策略账户启动校验"""

    def test_strategy_account_validation(self, repo, caplog):
        import logging
        repo.create_account('test_acc_a', initial_capital=100000)
        from application.services.strategy_service import StrategyService
        service = StrategyService()
        with caplog.at_level(logging.WARNING):
            strategies = service.list_strategies()
        # 迁移已建 v13/v14/v15 账户，策略不应被禁用
        assert 'v13' in strategies


class TestFastAPIParity:
    """Task 10: FastAPI 侧端点存在且行为一致"""

    @pytest.fixture()
    def fastapi_client(self, repo):
        from fastapi.testclient import TestClient
        from adapters.inbound.fastapi_app.routes.simulation_async import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_fastapi_accounts_endpoints(self, fastapi_client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        resp = fastapi_client.get('/api/simulation/accounts')
        assert resp.status_code == 200
        assert resp.json()['success'] is True
        names = {a['account_name'] for a in resp.json()['data']['accounts']}
        assert 'test_acc_a' in names

        resp = fastapi_client.get('/api/simulation/trades')
        assert resp.status_code == 400
        resp = fastapi_client.get('/api/simulation/trades?account_name=no_such')
        assert resp.status_code == 404
