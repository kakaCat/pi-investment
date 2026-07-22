#!/usr/bin/env python3
"""多账户域端到端验证（对运行中的 5001 服务）"""
import requests
import sys

BASE = 'http://127.0.0.1:5001'
failures = []


def check(name, cond, detail=''):
    status = '✅' if cond else '❌'
    print(f'{status} {name} {detail}')
    if not cond:
        failures.append(name)


# 1. 账户发现
r = requests.get(f'{BASE}/api/simulation/accounts')
data = r.json()
check('账户发现', r.status_code == 200 and data['success'],
      f"{data['data']['total']}个账户")

# 2. 开户
r = requests.post(f'{BASE}/api/simulation/accounts', json={
    'account_name': 'e2e_verify_acc', 'display_name': 'E2E验证账户',
    'initial_capital': 100000})
check('开户', r.status_code == 201 and r.json()['success'], f"HTTP {r.status_code}")

# 3. 买入（注入价格避免依赖实时行情）
r = requests.post(f'{BASE}/api/simulation/accounts/e2e_verify_acc/trade', json={
    'action': 'buy', 'symbol': '600519', 'shares': 100,
    'reason': 'E2E验证买入：验证多账户交易链路', 'price': 10.0})
data = r.json()
check('买入成交', r.status_code == 200 and data['success'],
      f"order={data.get('data', {}).get('order_id')}")

# 4. T+1 当日卖出被拒
r = requests.post(f'{BASE}/api/simulation/accounts/e2e_verify_acc/trade', json={
    'action': 'sell', 'symbol': '600519', 'shares': 100,
    'reason': 'E2E验证卖出：当日卖出应被T+1拦截', 'price': 11.0})
check('T+1拦截', r.status_code == 422, f"HTTP {r.status_code}")

# 5. 资金流水不变式
sys.path.insert(0, '.')
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
inv = SimulationORMRepository().verify_cash_flow_invariant('e2e_verify_acc')
check('流水不变式', inv['invariant_ok'],
      f"flow={inv['flow_balance']} cash={inv['account_cash']}")

# 6. 绩效（快照）
r = requests.get(f'{BASE}/api/simulation/performance?account_name=e2e_verify_acc')
data = r.json()
check('绩效快照', r.status_code == 200 and data['success']
      and len(data['data']['equity_curve']) >= 1)

# 7. account_name 必填
r = requests.get(f'{BASE}/api/simulation/trades')
check('缺account_name→400', r.status_code == 400
      and 'available_accounts' in r.json())

# 8. 账户不存在
r = requests.get(f'{BASE}/api/simulation/trades?account_name=ghost_acc')
check('不存在账户→404', r.status_code == 404)

# 9. 账户隔离：v13 持仓不混入 e2e 账户
r1 = requests.get(f'{BASE}/api/simulation/accounts/v13_simulation')
r2 = requests.get(f'{BASE}/api/simulation/accounts/e2e_verify_acc')
v13_positions = r1.json()['data']['positions_count']
e2e_positions = [p['symbol'] for p in r2.json()['data']['positions']]
check('账户隔离', v13_positions >= 0 and e2e_positions == ['600519'],
      f"v13={v13_positions}只, e2e={e2e_positions}")

# 清理
from infrastructure.persistence.orm.models.simulation import (
    SimulationAccount, SimulationPosition, SimulationTrade,
    SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
)
repo = SimulationORMRepository()
for model in (SimulationCashFlow, SimulationOrder, SimulationTrade,
              SimulationPosition, SimulationEquitySnapshot, SimulationAccount):
    repo.session.query(model).filter_by(account_name='e2e_verify_acc').delete(
        synchronize_session=False)
repo.session.commit()
print('🧹 e2e_verify_acc 已清理')

if failures:
    print(f'\n❌ 失败 {len(failures)} 项: {failures}')
    sys.exit(1)
print('\n✅ E2E 全部通过')
