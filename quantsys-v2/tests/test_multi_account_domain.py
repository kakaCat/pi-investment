"""多账户域模型测试"""
import pytest
from datetime import date


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


class TestSimulationAPI:
    """Task 6: 路由层（新端点 + 必填化）"""

    @pytest.fixture()
    def client(self, repo):
        from adapters.inbound.api.routes.simulation import simulation_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
        return app.test_client()

    def test_list_accounts(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        resp = client.get('/api/simulation/accounts')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        names = {a['account_name'] for a in data['data']['accounts']}
        assert 'test_acc_a' in names

    def test_create_account(self, client):
        resp = client.post('/api/simulation/accounts', json={
            'account_name': 'test_acc_a',
            'display_name': 'API开户测试',
            'initial_capital': 50000,
        })
        assert resp.status_code == 201, resp.get_json()

    def test_create_account_conflict(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        resp = client.post('/api/simulation/accounts', json={
            'account_name': 'test_acc_a', 'initial_capital': 50000})
        assert resp.status_code == 409

    def test_trades_missing_account_name_400(self, client):
        resp = client.get('/api/simulation/trades')
        assert resp.status_code == 400
        assert 'available_accounts' in resp.get_json()

    def test_trades_unknown_account_404(self, client):
        resp = client.get('/api/simulation/trades?account_name=no_such_acc')
        assert resp.status_code == 404
        assert 'available_accounts' in resp.get_json()

    def test_trade_endpoint_buy(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        resp = client.post('/api/simulation/accounts/test_acc_a/trade', json={
            'action': 'buy', 'symbol': '600519', 'shares': 100,
            'reason': 'API测试买入：验证交易端点', 'price': 10.0,
        })
        assert resp.status_code == 200, resp.get_json()
        data = resp.get_json()['data']
        assert data['order_status'] == 'filled'

    def test_performance_reads_snapshot(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.upsert_equity_snapshot('test_acc_a', cash=100000, position_value=0,
                                    total_value=100000)
        resp = client.get('/api/simulation/performance?account_name=test_acc_a')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['data']['equity_curve']) >= 1
        assert data['data']['initial_capital'] == 100000.0


class TestPortfolioEndpoints:
    """Task 8: /api/portfolio/* 切源到 simulation 体系"""

    @pytest.fixture()
    def client(self, repo):
        from adapters.inbound.api.routes.orders import orders_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(orders_bp)
        return app.test_client()

    def test_positions_requires_account(self, client):
        resp = client.get('/api/portfolio/positions')
        assert resp.status_code == 400

    def test_positions_from_simulation(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.upsert_position('test_acc_a', '600519', shares_total=100, avg_cost=10.0,
                             current_price=11.0)
        resp = client.get('/api/portfolio/positions?account_name=test_acc_a')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['count'] == 1
        assert data['data']['positions'][0]['symbol'] == '600519'

    def test_summary_from_simulation(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        resp = client.get('/api/portfolio/summary?account_name=test_acc_a')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['data']['totalValue'] == 100000.0


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
