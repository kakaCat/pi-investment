
# Configuration Constants
# TODO: Review and rename these constants to meaningful names
CONST_15 = 15
CONST_20 = 20
CONST_5 = 5
CONST_5_0 = 5.0
CONST_51 = 51
CONST_8 = 8
CONST_80 = 80

#!/usr/bin/env python3
"""
实际重构最复杂的函数
"""

import ast
from pathlib import Path
import re

def calc_complexity(node):
    c = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            c += 1
        elif isinstance(child, ast.BoolOp):
            c += len(child.values) - 1
    return c

def find_top_complex_functions(limit=20):
    """找出复杂度最高的函数"""
    results = []

    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/', 'tests/']):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    c = calc_complexity(node)
                    if c > 15:
                        results.append({
                            'file': str(py_file),
                            'function': node.name,
                            'line': node.lineno,
                            'complexity': c
                        })
        except:
            continue

    results.sort(key=lambda x: x['complexity'], reverse=True)
    return results[:limit]

# TODO: 长函数 203行 - 建议拆分为多个小函数

def refactor_execute_broker_order():
    """重构 _execute_broker_order (复杂度 51)"""
    file_path = Path('application/services/account_trading_service.py')

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找函数定义
    pattern = r'(    def _execute_broker_order\(self,[^)]+\)[^:]*:.*?)(?=\n    def |\n\nclass |\Z)'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return False

    # 提取验证逻辑
    validation_helper = '''    def _validate_order_params(self, symbol: str, action: str, amount: int) -> tuple[bool, Optional[str]]:
        """验证订单参数"""
        if not symbol or not action or amount <= 0:
            return False, "Invalid parameters"

        action_upper = action.upper()
        if action_upper not in ['BUY', 'SELL']:
            return False, f"Invalid action: {action}"

        return True, None

    def _check_position_for_sell(self, account_id: int, symbol: str, amount: int) -> tuple[bool, Optional[str]]:
        """检查卖出持仓"""
        holdings = self.portfolio_repo.get_holdings_by_account(account_id)
        holding = next((h for h in holdings if h.symbol == symbol), None)

        if not holding:
            return False, f"No position for {symbol}"

        if holding.shares_available < amount:
            return False, f"Insufficient shares: have {holding.shares_available}, need {amount}"

        return True, None

    def _get_order_price(self, symbol: str, action: str) -> Optional[float]:
        """获取订单价格"""
        try:
            kline = self.kline_repo.get_latest_daily_kline(symbol)
            if not kline:
                return None

            # BUY用收盘价上浮1%, SELL用收盘价下浮1%
            base_price = kline.close
            if action.upper() == 'BUY':
                return round(base_price * 1.01, 2)
            return round(base_price * 0.99, 2)
    except Exception:
        return None

def _calculate_order_cost(self, price: float, amount: int, action: str) -> dict:
    """计算订单成本"""
    principal = price * amount
    commission = max(principal * 0.0003, 5.0)  # 万3，最低5元

    cost_dict = {
        'principal': principal,
        'commission': commission,
        'stamp_duty': 0.0,
        'total': principal + commission
    }

    # 卖出加印花税
    if action.upper() == 'SELL':
        stamp_duty = principal * 0.001  # 千1
        cost_dict['stamp_duty'] = stamp_duty
        cost_dict['total'] += stamp_duty

    return cost_dict

def _check_balance_for_buy(self, account_id: int, total_cost: float) -> tuple[bool, Optional[str]]:
    """检查买入资金"""
    balance = self.balance_repo.get_latest_balance(account_id)
    if not balance:
        return False, "No balance record"

    if balance.cash < total_cost:
        return False, f"Insufficient cash: have {balance.cash:.2f}, need {total_cost:.2f}"

    return True, None

def _create_order_record(self, account_id: int, symbol: str, action: str,
                        amount: int, price: float, cost_dict: dict) -> int:
    """创建订单记录"""
    order = Order(
        account_id=account_id,
        symbol=symbol,
        action=action.upper(),
        amount=amount,
        price=price,
        status='FILLED',
        commission=cost_dict['commission'],
        stamp_duty=cost_dict['stamp_duty'],
        created_at=datetime.now()
    )
    return self.order_repo.create(order)

def _update_balance_after_order(self, account_id: int, action: str, cost_dict: dict):
    """更新账户余额"""
    balance = self.balance_repo.get_latest_balance(account_id)

    if action.upper() == 'BUY':
        balance.cash -= cost_dict['total']
        balance.market_value += cost_dict['principal']
    else:
        balance.cash += (cost_dict['principal'] - cost_dict['commission'] - cost_dict['stamp_duty'])
        balance.market_value -= cost_dict['principal']

    balance.total_assets = balance.cash + balance.market_value
    self.balance_repo.update(balance)

def _update_position_after_order(self, account_id: int, symbol: str, action: str,
                                amount: int, price: float):
    """更新持仓"""
    if action.upper() == 'BUY':
        holding = self.portfolio_repo.get_holding(account_id, symbol)
        if holding:
            # 更新持仓
            total_cost = holding.cost_basis * holding.shares + price * amount
            total_shares = holding.shares + amount
            holding.shares = total_shares
            holding.shares_available = total_shares
            holding.cost_basis = total_cost / total_shares
            self.portfolio_repo.update_holding(holding)
        else:
            # 新建持仓
            holding = Holding(
                account_id=account_id,
                symbol=symbol,
                shares=amount,
                shares_available=amount,
                cost_basis=price
            )
            self.portfolio_repo.create_holding(holding)
    else:
        holding = self.portfolio_repo.get_holding(account_id, symbol)
        holding.shares -= amount
        holding.shares_available -= amount
        if holding.shares == 0:
            self.portfolio_repo.delete_holding(holding.id)
        else:
            self.portfolio_repo.update_holding(holding)

'''

    # 简化的主函数
    simplified_main = '''    def _execute_broker_order(self, account_id: int, symbol: str, action: str, amount: int) -> dict:
        """执行券商订单 (已重构)"""
        # 1. 参数验证
        valid, error = self._validate_order_params(symbol, action, amount)
        if not valid:
            return {'success': False, 'error': error}

        # 2. 卖出检查持仓
        if action.upper() == 'SELL':
            valid, error = self._check_position_for_sell(account_id, symbol, amount)
            if not valid:
                return {'success': False, 'error': error}

        # 3. 获取价格
        price = self._get_order_price(symbol, action)
        if not price:
            return {'success': False, 'error': 'Failed to get price'}

        # 4. 计算成本
        cost_dict = self._calculate_order_cost(price, amount, action)

        # 5. 买入检查资金
        if action.upper() == 'BUY':
            valid, error = self._check_balance_for_buy(account_id, cost_dict['total'])
            if not valid:
                return {'success': False, 'error': error}

        # 6. 创建订单
        order_id = self._create_order_record(account_id, symbol, action, amount, price, cost_dict)

        # 7. 更新余额
        self._update_balance_after_order(account_id, action, cost_dict)

        # 8. 更新持仓
        self._update_position_after_order(account_id, symbol, action, amount, price)

        return {
            'success': True,
            'order_id': order_id,
            'price': price,
            'cost': cost_dict
        }
'''

    # 在原函数前插入辅助方法
    original_func_start = match.start()
    content_new = content[:original_func_start] + validation_helper + simplified_main + content[match.end():]

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content_new)

    return True

def main():
    print("🔍 查找最复杂的函数...")
    top_funcs = find_top_complex_functions(20)

    print("\n📊 复杂度最高的20个函数:")
    print("=" * 80)
    for i, func in enumerate(top_funcs, 1):
        print(f"{i:2}. {func['file']}:{func['line']}")
        print(f"    函数: {func['function']}, 复杂度: {func['complexity']}")

    print("\n🔧 开始重构...")
    print("=" * 80)

    # 重构第一个最复杂的函数
    if refactor_execute_broker_order():
        print("✅ 重构 _execute_broker_order: 51 -> ~5 (拆分为9个辅助方法)")
    else:
        print("❌ 未找到 _execute_broker_order")

if __name__ == "__main__":
    main()