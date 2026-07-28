"""并发交易现金一致性回归测试

背景：2026-07-28 agent_virtual 两笔并发买入（10:00:23.436 / 10:00:23.440）
发生 lost update——两事务读到同一现金余额，后者覆盖前者的账户更新，
导致杭州银行 ¥23,346.06 只记流水未扣现金。

修复：execute_trade 事务内先 SELECT ... FOR UPDATE 锁定账户行，
串行化同账户并发交易；verify_cash_flow_invariant 增加流水总额不变式。

本测试需要可用的 PostgreSQL（quant_investment），否则跳过。
"""
import threading

import pytest

from application.services.account_trading_service import AccountTradingService
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from infrastructure.persistence.orm.models.simulation import (
    SimulationAccount, SimulationPosition, SimulationTrade,
    SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
)

ACCT = 'race_test_tmp'
PRICE = 10.0
SHARES = 100
# 每笔成本 = 1000 + max(0.25, 5) 佣金 + 0.01 过户费 = 1005.01
COST_PER_TRADE = round(PRICE * SHARES + 5.0 + round(PRICE * SHARES * 0.00001, 2), 2)


def _cleanup(repo):
    s = repo.session
    for model in (SimulationEquitySnapshot, SimulationCashFlow, SimulationTrade,
                  SimulationOrder, SimulationPosition):
        s.query(model).filter_by(account_name=ACCT).delete()
    s.query(SimulationAccount).filter_by(account_name=ACCT).delete()
    s.commit()


@pytest.fixture()
def account():
    repo = SimulationORMRepository()
    try:
        _cleanup(repo)
        repo.create_account(
            account_name=ACCT, initial_capital=100000,
            display_name='并发竞态回归测试账户')
        yield ACCT
    except Exception as e:
        pytest.skip(f'数据库不可用: {e}')
    finally:
        try:
            _cleanup(repo)
        except Exception:
            pass


def _buy(symbol, results):
    """每个线程独立 service/repo/session，模拟并发请求"""
    try:
        svc = AccountTradingService()
        svc.execute_trade(
            account_name=ACCT, action='buy', symbol=symbol, shares=SHARES,
            price=PRICE, reason='并发竞态回归测试买入委托',
            allow_off_hours=True)
        results.append(('ok', symbol))
    except Exception as e:  # noqa: BLE001
        results.append(('err', f'{symbol}: {e}'))


def test_concurrent_buys_no_lost_update(account):
    """并发买入后：现金必须精确等于 初始 - Σ成本，且流水不变式成立"""
    results = []
    threads = [
        threading.Thread(target=_buy, args=(f'60000{i}', results))
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    errors = [r for r in results if r[0] == 'err']
    assert not errors, f'并发交易出现失败: {errors}'

    repo = SimulationORMRepository()
    acc = repo.get_account(ACCT)
    expected_cash = round(100000 - 4 * COST_PER_TRADE, 2)
    assert abs(float(acc.cash_available) - expected_cash) < 0.01, (
        f'lost update! 现金 {float(acc.cash_available)} != 期望 {expected_cash}')

    inv = repo.verify_cash_flow_invariant(ACCT)
    assert inv['invariant_ok'], f'末条流水余额不一致: {inv}'
    assert inv['sum_invariant_ok'], f'流水总额与现金不一致（链条断裂）: {inv}'

    # 持仓数量也要是 4 只（无丢失的持仓更新）
    positions = repo.get_all_positions(ACCT)
    assert len(positions) == 4


def test_verify_invariant_detects_broken_chain(account):
    """sum_invariant 能检出末条余额恰好一致的链条断裂"""
    repo = SimulationORMRepository()
    # 人为制造 07-28 事故现场：两条流水都基于同一余额计算
    repo.add_cash_flow(ACCT, 'buy_debit', -1000, 99000)      # 正常
    repo.add_cash_flow(ACCT, 'buy_debit', -1000, 99000)      # 并发幻读（应98000）
    acc = repo.get_account(ACCT)
    acc.cash_available = 99000  # 末条余额恰好与现金一致
    repo.session.commit()

    inv = repo.verify_cash_flow_invariant(ACCT)
    assert inv['invariant_ok'] is True          # 旧不变式被骗过
    assert inv['sum_invariant_ok'] is False     # 新不变式检出断裂
