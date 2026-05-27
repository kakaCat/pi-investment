# 指标工具系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的指标工具系统，包括 5 个 CLI 命令和 3 个新 API 端点，解决用户四大痛点

**Architecture:** CLI 层新建 indicator_commands.py（5个命令类继承 HTTPCommand），后端在 indicators.py 添加 3 个新端点，复用现有 StrategyService

**Tech Stack:** Python 3.13, Flask, Click/argparse, pytest, pandas

---

## 文件结构

### 新增文件
- `quantsys-v2/cli/commands/indicator_commands.py` - 5个指标CLI命令类
- `quantsys-v2/tests/cli/test_indicator_commands.py` - CLI命令单元测试
- `quantsys-v2/tests/api/test_indicators_routes.py` - API路由单元测试

### 修改文件
- `quantsys-v2/cli/commands/__init__.py` - 导出 indicator_commands
- `quantsys-v2/cli/command_registry.py` - 注册 indicator 命令
- `quantsys-v2/cli/main.py` - 添加 indicators.* 子命令解析
- `quantsys-v2/api/routes/indicators.py` - 添加 3 个新端点，增强 backtest

---

## Task 1: CLI 命令基础结构

**Files:**
- Create: `quantsys-v2/cli/commands/indicator_commands.py`
- Create: `quantsys-v2/tests/cli/test_indicator_commands.py`

- [ ] **Step 1: 创建测试文件和基础测试**

创建 `quantsys-v2/tests/cli/test_indicator_commands.py`:

```python
"""测试指标命令"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import os


def test_indicator_list_command_exists():
    """测试 IndicatorListCommand 类存在"""
    from cli.commands.indicator_commands import IndicatorListCommand
    
    mock_client = Mock()
    cmd = IndicatorListCommand(mock_client)
    
    assert cmd.name == "indicators.list"
    assert cmd.description == "列出所有指标"


def test_indicator_create_command_validation():
    """测试创建指标参数验证"""
    from cli.commands.indicator_commands import IndicatorCreateCommand
    
    mock_client = Mock()
    cmd = IndicatorCreateCommand(mock_client)
    
    # 缺少name
    error = cmd.validate_params(code="test")
    assert error == "指标名称不能为空"
    
    # 缺少code
    error = cmd.validate_params(name="测试")
    assert error == "指标代码不能为空"
    
    # 参数完整
    error = cmd.validate_params(name="测试", code="test")
    assert error is None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/cli/test_indicator_commands.py::test_indicator_list_command_exists -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'cli.commands.indicator_commands'"

- [ ] **Step 3: 创建 indicator_commands.py 骨架**

创建 `quantsys-v2/cli/commands/indicator_commands.py`:

```python
"""
Indicator Commands

指标管理相关命令，提供完整的指标 CRUD 操作。
"""

import json
import os
from typing import Any, Dict

from ..command_base import HTTPCommand, CommandResult


class IndicatorListCommand(HTTPCommand):
    """列出指标命令"""
    
    @property
    def name(self) -> str:
        return "indicators.list"
    
    @property
    def description(self) -> str:
        return "列出所有指标"
    
    def execute(self, **kwargs) -> CommandResult:
        """执行列出指标命令"""
        params = {
            'page': kwargs.get('page', 1),
            'pageSize': kwargs.get('page_size', 20)
        }
        
        if kwargs.get('type'):
            params['type'] = kwargs['type']
        if kwargs.get('author'):
            params['author'] = kwargs['author']
        
        response = self.http_client.get('/api/indicators/list', params=params)
        return self._handle_response(response)


class IndicatorCreateCommand(HTTPCommand):
    """创建指标命令"""
    
    @property
    def name(self) -> str:
        return "indicators.create"
    
    @property
    def description(self) -> str:
        return "创建新指标"
    
    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('name'):
            return "指标名称不能为空"
        if not kwargs.get('code'):
            return "指标代码不能为空"
        return None
    
    def execute(self, **kwargs) -> CommandResult:
        """执行创建指标命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)
        
        try:
            # 读取代码（支持文件路径或直接代码）
            code_input = kwargs.get('code')
            if code_input.endswith('.py'):
                if not os.path.exists(code_input):
                    return CommandResult(
                        success=False,
                        error=f"代码文件不存在: {code_input}"
                    )
                with open(code_input, 'r', encoding='utf-8') as f:
                    code = f.read()
            else:
                code = code_input
            
            # 解析参数（如果提供）
            params = None
            if kwargs.get('params'):
                try:
                    params = json.loads(kwargs['params'])
                except json.JSONDecodeError as e:
                    return CommandResult(
                        success=False,
                        error=f"参数JSON格式错误: {str(e)}"
                    )
            
            # 构建请求体
            payload = {
                'name': kwargs['name'],
                'code': code,
                'description': kwargs.get('description', ''),
            }
            if params:
                payload['params'] = params
            
            response = self.http_client.post('/api/indicators/create', json=payload)
            return self._handle_response(response)
            
        except Exception as e:
            return CommandResult(success=False, error=str(e))


class IndicatorUpdateCommand(HTTPCommand):
    """更新指标命令"""
    
    @property
    def name(self) -> str:
        return "indicators.update"
    
    @property
    def description(self) -> str:
        return "更新指标"
    
    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('id'):
            return "指标ID不能为空"
        return None
    
    def execute(self, **kwargs) -> CommandResult:
        """执行更新指标命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)
        
        try:
            indicator_id = kwargs['id']
            payload = {}
            
            # 处理代码
            if kwargs.get('code'):
                code_input = kwargs['code']
                if code_input.endswith('.py'):
                    if not os.path.exists(code_input):
                        return CommandResult(
                            success=False,
                            error=f"代码文件不存在: {code_input}"
                        )
                    with open(code_input, 'r', encoding='utf-8') as f:
                        payload['code'] = f.read()
                else:
                    payload['code'] = code_input
            
            # 处理其他参数
            if kwargs.get('name'):
                payload['name'] = kwargs['name']
            if kwargs.get('description'):
                payload['description'] = kwargs['description']
            if kwargs.get('params'):
                try:
                    payload['params'] = json.loads(kwargs['params'])
                except json.JSONDecodeError as e:
                    return CommandResult(
                        success=False,
                        error=f"参数JSON格式错误: {str(e)}"
                    )
            if kwargs.get('active') is not None:
                payload['isActive'] = kwargs['active'].lower() == 'true'
            
            response = self.http_client.post(
                f'/api/indicators/update/{indicator_id}',
                json=payload
            )
            return self._handle_response(response)
            
        except Exception as e:
            return CommandResult(success=False, error=str(e))


class IndicatorRunCommand(HTTPCommand):
    """运行指标命令"""
    
    @property
    def name(self) -> str:
        return "indicators.run"
    
    @property
    def description(self) -> str:
        return "运行指标生成信号"
    
    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('id'):
            return "指标ID不能为空"
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        return None
    
    def execute(self, **kwargs) -> CommandResult:
        """执行运行指标命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)
        
        try:
            indicator_id = kwargs['id']
            payload = {
                'symbol': kwargs['symbol'],
                'limit': kwargs.get('limit', 100)
            }
            
            response = self.http_client.post(
                f'/api/indicators/run/{indicator_id}',
                json=payload
            )
            return self._handle_response(response)
            
        except Exception as e:
            return CommandResult(success=False, error=str(e))


class IndicatorBacktestCommand(HTTPCommand):
    """回测指标命令"""
    
    @property
    def name(self) -> str:
        return "indicators.backtest"
    
    @property
    def description(self) -> str:
        return "回测指标"
    
    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('id'):
            return "指标ID不能为空"
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        if not kwargs.get('start'):
            return "开始日期不能为空"
        if not kwargs.get('end'):
            return "结束日期不能为空"
        return None
    
    def execute(self, **kwargs) -> CommandResult:
        """执行回测指标命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)
        
        try:
            payload = {
                'indicatorId': int(kwargs['id']),
                'symbol': kwargs['symbol'],
                'startDate': kwargs['start'],
                'endDate': kwargs['end'],
                'initialCash': kwargs.get('initial_cash', 1000000)
            }
            
            response = self.http_client.post('/api/indicators/backtest', json=payload)
            return self._handle_response(response)
            
        except Exception as e:
            return CommandResult(success=False, error=str(e))


def get_all_commands():
    """获取所有指标命令类"""
    return [
        IndicatorListCommand,
        IndicatorCreateCommand,
        IndicatorUpdateCommand,
        IndicatorRunCommand,
        IndicatorBacktestCommand,
    ]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/cli/test_indicator_commands.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add cli/commands/indicator_commands.py tests/cli/test_indicator_commands.py
git commit -m "feat(cli): add indicator commands structure with 5 command classes"
```


---

## Task 2: CLI 命令注册和参数解析

**Files:**
- Modify: `quantsys-v2/cli/commands/__init__.py`
- Modify: `quantsys-v2/cli/command_registry.py:98-137`
- Modify: `quantsys-v2/cli/main.py:73-238`

- [ ] **Step 1: 编写注册测试**

在 `quantsys-v2/tests/cli/test_indicator_commands.py` 添加:

```python
def test_indicator_commands_registered():
    """测试指标命令已注册"""
    from cli.command_registry import auto_discover_commands
    from unittest.mock import Mock
    
    mock_client = Mock()
    registry = auto_discover_commands(mock_client)
    
    assert registry.exists("indicators.list")
    assert registry.exists("indicators.create")
    assert registry.exists("indicators.update")
    assert registry.exists("indicators.run")
    assert registry.exists("indicators.backtest")
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/cli/test_indicator_commands.py::test_indicator_commands_registered -v
```

Expected: FAIL with "AssertionError: assert False"

- [ ] **Step 3: 修改 __init__.py 导出命令**

修改 `quantsys-v2/cli/commands/__init__.py`:

```python
"""
CLI Commands Package
"""

from . import stock_commands
from . import market_commands
from . import kline_commands
from . import factor_commands
from . import signal_commands
from . import strategy_commands
from . import indicator_commands  # 新增

__all__ = [
    'stock_commands',
    'market_commands',
    'kline_commands',
    'factor_commands',
    'signal_commands',
    'strategy_commands',
    'indicator_commands',  # 新增
]
```

- [ ] **Step 4: 修改 command_registry.py 注册命令**

在 `quantsys-v2/cli/command_registry.py` 的 `auto_discover_commands()` 函数中添加:

```python
def auto_discover_commands(http_client) -> CommandRegistry:
    """自动发现并注册所有命令"""
    from .commands import stock_commands, market_commands, kline_commands
    from .commands import factor_commands, signal_commands, strategy_commands
    from .commands import indicator_commands  # 新增

    registry = CommandRegistry()

    # 注册Stock命令
    for cmd_class in stock_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Market命令
    for cmd_class in market_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Kline命令
    for cmd_class in kline_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Factor命令
    for cmd_class in factor_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Signal命令
    for cmd_class in signal_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Strategy命令（不需要http_client）
    for cmd_class in strategy_commands.get_all_commands():
        registry.register(cmd_class())

    # 注册Indicator命令（新增）
    for cmd_class in indicator_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    return registry
```

- [ ] **Step 5: 修改 main.py 添加参数解析**

在 `quantsys-v2/cli/main.py` 的 `create_parser()` 函数中，在 strategy 解析器之后添加:

```python
    # ==================== indicators.* ====================
    indicators_parser = subparsers.add_parser('indicators', help='指标管理')
    indicators_subs = indicators_parser.add_subparsers(dest='action', help='指标操作')

    # indicators list
    indicators_list = indicators_subs.add_parser('list', help='列出指标')
    indicators_list.add_argument('--page', type=int, default=1, help='页码')
    indicators_list.add_argument('--page-size', type=int, default=20, help='每页数量')
    indicators_list.add_argument('--type', choices=['my', 'system'], help='指标类型')
    indicators_list.add_argument('--author', help='作者筛选')

    # indicators create
    indicators_create = indicators_subs.add_parser('create', help='创建指标')
    indicators_create.add_argument('--name', required=True, help='指标名称')
    indicators_create.add_argument('--code', required=True, help='指标代码或代码文件路径')
    indicators_create.add_argument('--description', default='', help='指标描述')
    indicators_create.add_argument('--params', help='指标参数JSON')

    # indicators update
    indicators_update = indicators_subs.add_parser('update', help='更新指标')
    indicators_update.add_argument('--id', required=True, help='指标ID')
    indicators_update.add_argument('--name', help='指标名称')
    indicators_update.add_argument('--code', help='指标代码或代码文件路径')
    indicators_update.add_argument('--description', help='指标描述')
    indicators_update.add_argument('--params', help='指标参数JSON')
    indicators_update.add_argument('--active', help='是否启用 true/false')

    # indicators run
    indicators_run = indicators_subs.add_parser('run', help='运行指标')
    indicators_run.add_argument('--id', required=True, help='指标ID')
    indicators_run.add_argument('--symbol', required=True, help='股票代码')
    indicators_run.add_argument('--limit', type=int, default=100, help='K线数量')

    # indicators backtest
    indicators_backtest = indicators_subs.add_parser('backtest', help='回测指标')
    indicators_backtest.add_argument('--id', required=True, help='指标ID')
    indicators_backtest.add_argument('--symbol', required=True, help='股票代码')
    indicators_backtest.add_argument('--start', required=True, help='开始日期 YYYY-MM-DD')
    indicators_backtest.add_argument('--end', required=True, help='结束日期 YYYY-MM-DD')
    indicators_backtest.add_argument('--initial-cash', type=float, default=1000000, help='初始资金')

    return parser
```

- [ ] **Step 6: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/cli/test_indicator_commands.py::test_indicator_commands_registered -v
```

Expected: PASS

- [ ] **Step 7: 手动测试 CLI 帮助**

```bash
cd quantsys-v2
python cli/main.py indicators --help
```

Expected: 显示 indicators 子命令帮助信息

- [ ] **Step 8: 提交**

```bash
cd quantsys-v2
git add cli/commands/__init__.py cli/command_registry.py cli/main.py tests/cli/test_indicator_commands.py
git commit -m "feat(cli): register indicator commands and add argument parsing"
```

---

## Task 3: 回测摘要计算函数

**Files:**
- Modify: `quantsys-v2/api/routes/indicators.py:222-256`
- Create: `quantsys-v2/tests/api/test_indicators_routes.py`

- [ ] **Step 1: 编写回测摘要测试**

创建 `quantsys-v2/tests/api/test_indicators_routes.py`:

```python
"""测试指标路由"""
import pytest
from datetime import datetime


def test_calculate_backtest_summary():
    """测试回测摘要计算"""
    from api.routes.indicators import calculate_backtest_summary
    
    # 模拟 equity curve
    equity_curve = [
        {'date': '2024-01-01', 'equity': 1000000},
        {'date': '2024-01-02', 'equity': 1020000},
        {'date': '2024-01-03', 'equity': 1015000},
        {'date': '2024-01-04', 'equity': 1030000},
        {'date': '2024-01-05', 'equity': 1025000},
    ]
    
    # 模拟交易
    trades = [
        {'date': '2024-01-02', 'action': 'buy', 'price': 10.0, 'pnl': 2000},
        {'date': '2024-01-03', 'action': 'sell', 'price': 10.2, 'pnl': -500},
        {'date': '2024-01-04', 'action': 'buy', 'price': 10.1, 'pnl': 1500},
    ]
    
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 5)
    
    summary = calculate_backtest_summary(equity_curve, trades, start_date, end_date)
    
    assert 'total_return' in summary
    assert 'annual_return' in summary
    assert 'max_drawdown' in summary
    assert 'sharpe_ratio' in summary
    assert 'win_rate' in summary
    assert 'total_trades' in summary
    assert summary['total_trades'] == 3
    assert summary['winning_trades'] == 2
    assert summary['losing_trades'] == 1
    assert summary['total_return'] == pytest.approx(0.025, rel=0.01)


def test_calculate_backtest_summary_empty():
    """测试空数据的回测摘要"""
    from api.routes.indicators import calculate_backtest_summary
    
    summary = calculate_backtest_summary([], [], datetime(2024, 1, 1), datetime(2024, 1, 5))
    
    assert summary == {}
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/api/test_indicators_routes.py::test_calculate_backtest_summary -v
```

Expected: FAIL with "ImportError: cannot import name 'calculate_backtest_summary'"

- [ ] **Step 3: 实现 calculate_backtest_summary 函数**

在 `quantsys-v2/api/routes/indicators.py` 文件末尾添加:

```python
def calculate_backtest_summary(equity_curve, trades, start_date, end_date):
    """计算回测摘要指标"""
    if not equity_curve or len(equity_curve) < 2:
        return {}
    
    # 1. 总收益率
    initial_equity = equity_curve[0]['equity']
    final_equity = equity_curve[-1]['equity']
    total_return = (final_equity - initial_equity) / initial_equity
    
    # 2. 年化收益率
    days = (end_date - start_date).days
    years = days / 365.0
    annual_return = ((1 + total_return) ** (1 / years) - 1) if years > 0 else 0
    
    # 3. 最大回撤
    peak = initial_equity
    max_drawdown = 0
    for point in equity_curve:
        equity = point['equity']
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # 4. 夏普比率
    returns = []
    for i in range(1, len(equity_curve)):
        ret = (equity_curve[i]['equity'] - equity_curve[i-1]['equity']) / equity_curve[i-1]['equity']
        returns.append(ret)
    
    if len(returns) > 0:
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_return = variance ** 0.5
        sharpe_ratio = (annual_return - 0.03) / (std_return * (252 ** 0.5)) if std_return > 0 else 0
    else:
        sharpe_ratio = 0
    
    # 5. 交易统计
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
    
    total_trades = len(trades)
    win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
    
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
    
    total_win = sum(t['pnl'] for t in winning_trades)
    total_loss = abs(sum(t['pnl'] for t in losing_trades))
    profit_factor = total_win / total_loss if total_loss > 0 else 0
    
    return {
        'total_return': round(total_return, 4),
        'annual_return': round(annual_return, 4),
        'max_drawdown': round(max_drawdown, 4),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'win_rate': round(win_rate, 2),
        'total_trades': total_trades,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'avg_win': round(avg_win, 4),
        'avg_loss': round(avg_loss, 4),
        'profit_factor': round(profit_factor, 2)
    }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/api/test_indicators_routes.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add api/routes/indicators.py tests/api/test_indicators_routes.py
git commit -m "feat(api): add backtest summary calculation function"
```


---

## Task 4: 增强回测端点添加摘要

**Files:**
- Modify: `quantsys-v2/api/routes/indicators.py:222-256`

- [ ] **Step 1: 编写集成测试**

在 `quantsys-v2/tests/api/test_indicators_routes.py` 添加:

```python
def test_backtest_indicator_includes_summary(client, mock_strategy_service):
    """测试回测端点返回包含摘要"""
    # Mock strategy service
    mock_strategy_service.get_strategy.return_value = {
        'id': 1,
        'name': '测试指标',
        'code_type': 'indicator'
    }
    
    mock_strategy_service.backtest_strategy.return_value = {
        'equity_curve': [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-01-02', 'equity': 1020000},
        ],
        'trades': [
            {'date': '2024-01-02', 'action': 'buy', 'pnl': 2000}
        ]
    }
    
    response = client.post('/api/indicators/backtest', json={
        'indicatorId': 1,
        'symbol': '600519.SH',
        'startDate': '2024-01-01',
        'endDate': '2024-01-02'
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success']
    assert 'summary' in data['data']
    assert 'total_return' in data['data']['summary']
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/api/test_indicators_routes.py::test_backtest_indicator_includes_summary -v
```

Expected: FAIL (summary 字段不存在)

- [ ] **Step 3: 修改 backtest_indicator 函数**

在 `quantsys-v2/api/routes/indicators.py` 的 `backtest_indicator()` 函数中，找到返回语句前添加:

```python
@indicators_bp.route('/api/indicators/backtest', methods=['POST'])
@handle_api_error
def backtest_indicator():
    """回测指标"""
    data = request.get_json() or {}
    indicator_data = convert_keys_to_snake(data)

    required_fields = ['indicator_id', 'symbol', 'start_date', 'end_date']
    for field in required_fields:
        if field not in indicator_data:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400

    indicator_id = indicator_data['indicator_id']
    try:
        indicator_id = int(indicator_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': f'indicator_id 必须为整数, 当前值: {indicator_id}'}), 400

    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    result = strategy_service.backtest_strategy(
        strategy_id=indicator_id,
        symbol=indicator_data['symbol'],
        start_date=indicator_data['start_date'],
        end_date=indicator_data['end_date'],
        initial_cash=indicator_data.get('initial_cash', 1000000)
    )

    # 新增：计算摘要指标
    from datetime import datetime
    equity_curve = result.get('equity_curve', [])
    trades = result.get('trades', [])
    start_date = datetime.strptime(indicator_data['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(indicator_data['end_date'], '%Y-%m-%d')
    
    summary = calculate_backtest_summary(equity_curve, trades, start_date, end_date)
    result['summary'] = summary

    return api_response(result, message='指标回测完成')
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/api/test_indicators_routes.py::test_backtest_indicator_includes_summary -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add api/routes/indicators.py tests/api/test_indicators_routes.py
git commit -m "feat(api): enhance backtest endpoint to include summary metrics"
```

---

## Task 5: 沙箱列可用性探查端点

**Files:**
- Modify: `quantsys-v2/api/routes/indicators.py` (添加新端点)

- [ ] **Step 1: 编写端点测试**

在 `quantsys-v2/tests/api/test_indicators_routes.py` 添加:

```python
def test_sandbox_columns_missing_symbol(client):
    """测试沙箱列探查缺少symbol参数"""
    response = client.get('/api/indicators/sandbox-columns')
    assert response.status_code == 400
    data = response.get_json()
    assert not data['success']
    assert 'symbol' in data['error']


def test_sandbox_columns_success(client, mock_kline_repo):
    """测试沙箱列探查成功"""
    # Mock kline repository
    mock_kline_repo.get_klines.return_value = [
        {
            'trade_date': '2024-01-01',
            'close': 10.0,
            'roe_q': 15.0,
            'debt_ratio_q': 50.0,
            'rsi': 65.0,
            'atr': 0.5
        },
        {
            'trade_date': '2024-01-02',
            'close': 10.2,
            'roe_q': 15.5,
            'debt_ratio_q': None,
            'rsi': 68.0,
            'atr': 0.52
        }
    ]
    
    response = client.get('/api/indicators/sandbox-columns?symbol=600519.SH')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success']
    assert 'columns' in data['data']
    assert 'roe_q' in data['data']['columns']
    assert data['data']['columns']['roe_q']['coverage'] == 1.0
    assert data['data']['columns']['debt_ratio_q']['coverage'] == 0.5
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/api/test_indicators_routes.py::test_sandbox_columns_missing_symbol -v
```

Expected: FAIL with 404 (端点不存在)

- [ ] **Step 3: 实现沙箱列探查端点**

在 `quantsys-v2/api/routes/indicators.py` 文件中添加新端点:

```python
@indicators_bp.route('/api/indicators/sandbox-columns', methods=['GET'])
@handle_api_error
def get_sandbox_columns():
    """获取沙箱列可用性"""
    symbol = request.args.get('symbol')
    
    if not symbol:
        return jsonify({'success': False, 'error': '缺少symbol参数'}), 400
    
    # 导入依赖
    from repositories.kline_repository import KlineRepository
    import pandas as pd
    
    kline_repo = KlineRepository()
    
    # 获取K线数据（带财务和技术指标）
    klines = kline_repo.get_klines(symbol, limit=1000)
    
    if not klines:
        return jsonify({'success': False, 'error': f'股票 {symbol} 无数据'}), 404
    
    # 转为DataFrame
    df = pd.DataFrame(klines)
    
    # 定义需要检查的列
    columns_to_check = [
        # 财务指标（季度）
        'roe_q', 'gross_margin_q', 'net_profit_margin_q', 'debt_ratio_q',
        'revenue_growth_q', 'ocf_to_profit_q', 'current_ratio_q', 'roa_q', 'operating_margin_q',
        # 财务指标（年度）
        'roe_y', 'gross_margin_y', 'net_profit_margin_y', 'debt_ratio_y',
        'revenue_growth_y', 'ocf_to_profit_y', 'current_ratio_y', 'roa_y', 'operating_margin_y',
        # 技术指标
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'atr', 'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
        'ma5', 'ma10', 'ma20', 'ma60'
    ]
    
    # 统计每列的可用性
    columns_info = {}
    for col in columns_to_check:
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            coverage = non_null_count / len(df) if len(df) > 0 else 0
            
            # 获取最新非空值
            latest_row = df[df[col].notna()].tail(1)
            if not latest_row.empty:
                latest_value = float(latest_row[col].iloc[0])
                latest_date = latest_row['trade_date'].iloc[0] if 'trade_date' in latest_row.columns else None
            else:
                latest_value = None
                latest_date = None
            
            columns_info[col] = {
                'coverage': round(coverage, 4),
                'latest_value': round(latest_value, 4) if latest_value is not None else None,
                'latest_date': str(latest_date) if latest_date else None
            }
    
    # 日期范围
    date_range = {
        'start': str(df['trade_date'].min()) if 'trade_date' in df.columns else None,
        'end': str(df['trade_date'].max()) if 'trade_date' in df.columns else None
    }
    
    return api_response({
        'symbol': symbol,
        'columns': columns_info,
        'total_rows': len(df),
        'date_range': date_range
    })
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/api/test_indicators_routes.py::test_sandbox_columns_missing_symbol -v
python -m pytest tests/api/test_indicators_routes.py::test_sandbox_columns_success -v
```

Expected: 2 tests PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add api/routes/indicators.py tests/api/test_indicators_routes.py
git commit -m "feat(api): add sandbox columns availability probe endpoint"
```


---

## Task 6: 双策略对比回测端点

**Files:**
- Modify: `quantsys-v2/api/routes/indicators.py` (添加新端点)

- [ ] **Step 1: 编写端点测试**

在 `quantsys-v2/tests/api/test_indicators_routes.py` 添加:

```python
def test_compare_indicators_missing_params(client):
    """测试对比指标缺少参数"""
    response = client.post('/api/indicators/compare', json={
        'indicatorIdA': 1
    })
    assert response.status_code == 400
    data = response.get_json()
    assert not data['success']


def test_compare_indicators_success(client, mock_strategy_service):
    """测试对比指标成功"""
    # Mock strategy service
    mock_strategy_service.get_strategy.side_effect = [
        {'id': 1, 'name': 'RSI v5', 'code_type': 'indicator'},
        {'id': 2, 'name': 'RSI v6', 'code_type': 'indicator'}
    ]
    
    mock_strategy_service.backtest_strategy.side_effect = [
        {
            'equity_curve': [
                {'date': '2024-01-01', 'equity': 1000000},
                {'date': '2024-01-02', 'equity': 980000},
            ],
            'trades': [
                {'date': '2024-01-02', 'action': 'buy', 'pnl': -2000},
                {'date': '2024-01-03', 'action': 'buy', 'pnl': 1000},
            ]
        },
        {
            'equity_curve': [
                {'date': '2024-01-01', 'equity': 1000000},
                {'date': '2024-01-02', 'equity': 985000},
            ],
            'trades': [
                {'date': '2024-01-03', 'action': 'buy', 'pnl': 1000},
            ]
        }
    ]
    
    response = client.post('/api/indicators/compare', json={
        'indicatorIdA': 1,
        'indicatorIdB': 2,
        'symbol': '600519.SH',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success']
    assert 'comparison' in data['data']
    assert 'filtered_by_b_only' in data['data']['comparison']
    assert data['data']['comparison']['filtered_by_b_only'] == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/api/test_indicators_routes.py::test_compare_indicators_missing_params -v
```

Expected: FAIL with 404 (端点不存在)

- [ ] **Step 3: 实现双策略对比端点**

在 `quantsys-v2/api/routes/indicators.py` 文件中添加新端点:

```python
@indicators_bp.route('/api/indicators/compare', methods=['POST'])
@handle_api_error
def compare_indicators():
    """对比两个指标策略"""
    data = request.get_json() or {}
    indicator_data = convert_keys_to_snake(data)
    
    # 验证参数
    required_fields = ['indicator_id_a', 'indicator_id_b', 'symbol', 'start_date', 'end_date']
    for field in required_fields:
        if field not in indicator_data:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400
    
    indicator_id_a = int(indicator_data['indicator_id_a'])
    indicator_id_b = int(indicator_data['indicator_id_b'])
    symbol = indicator_data['symbol']
    start_date = indicator_data['start_date']
    end_date = indicator_data['end_date']
    initial_cash = indicator_data.get('initial_cash', 1000000)
    
    # 验证指标存在
    indicator_a = strategy_service.get_strategy(indicator_id_a)
    indicator_b = strategy_service.get_strategy(indicator_id_b)
    
    if not indicator_a:
        return jsonify({'success': False, 'error': f'指标A (ID={indicator_id_a}) 不存在'}), 404
    if not indicator_b:
        return jsonify({'success': False, 'error': f'指标B (ID={indicator_id_b}) 不存在'}), 404
    
    if indicator_a.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '策略A不是指标类型'}), 400
    if indicator_b.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '策略B不是指标类型'}), 400
    
    # 回测两个策略
    result_a = strategy_service.backtest_strategy(
        strategy_id=indicator_id_a,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash
    )
    
    result_b = strategy_service.backtest_strategy(
        strategy_id=indicator_id_b,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash
    )
    
    # 对比交易
    trades_a = result_a.get('trades', [])
    trades_b = result_b.get('trades', [])
    
    # 找出A有买入但B没有的交易（B过滤掉的）
    buy_dates_a = set(t['date'] for t in trades_a if t.get('action') == 'buy')
    buy_dates_b = set(t['date'] for t in trades_b if t.get('action') == 'buy')
    filtered_dates = buy_dates_a - buy_dates_b
    
    filtered_trades = []
    for trade in trades_a:
        if trade['date'] in filtered_dates and trade.get('action') == 'buy':
            filtered_trades.append({
                'date': trade['date'],
                'would_buy_price': trade.get('price'),
                'signal_a': 'buy',
                'signal_b': 'hold',
                'reason': 'filtered by strategy B'
            })
    
    # 计算差异指标
    equity_a = result_a.get('equity_curve', [])
    equity_b = result_b.get('equity_curve', [])
    
    total_return_a = (equity_a[-1]['equity'] - equity_a[0]['equity']) / equity_a[0]['equity'] if equity_a else 0
    total_return_b = (equity_b[-1]['equity'] - equity_b[0]['equity']) / equity_b[0]['equity'] if equity_b else 0
    
    comparison = {
        'return_diff': round(total_return_b - total_return_a, 4),
        'trades_diff': len(trades_b) - len(trades_a),
        'filtered_by_b_only': len(filtered_trades),
        'filtered_trades': filtered_trades
    }
    
    return api_response({
        'strategy_a': {
            'indicator_id': indicator_id_a,
            'name': indicator_a.get('name'),
            'total_return': round(total_return_a, 4),
            'total_trades': len(trades_a),
            'equity_curve': equity_a,
            'trades': trades_a
        },
        'strategy_b': {
            'indicator_id': indicator_id_b,
            'name': indicator_b.get('name'),
            'total_return': round(total_return_b, 4),
            'total_trades': len(trades_b),
            'equity_curve': equity_b,
            'trades': trades_b
        },
        'comparison': comparison
    }, message='策略对比完成')
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/api/test_indicators_routes.py::test_compare_indicators_missing_params -v
python -m pytest tests/api/test_indicators_routes.py::test_compare_indicators_success -v
```

Expected: 2 tests PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add api/routes/indicators.py tests/api/test_indicators_routes.py
git commit -m "feat(api): add dual-strategy comparison backtest endpoint"
```

---

## Task 7: 端到端集成测试

**Files:**
- Create: `quantsys-v2/tests/integration/test_indicator_e2e.sh`

- [ ] **Step 1: 创建集成测试脚本**

创建 `quantsys-v2/tests/integration/test_indicator_e2e.sh`:

```bash
#!/bin/bash
# 端到端集成测试脚本

set -e

echo "=== 指标工具系统端到端测试 ==="

# 1. 启动 API 服务
echo "1. 启动 API 服务..."
cd quantsys-v2
python api/server.py &
API_PID=$!
sleep 3

# 2. 测试健康检查
echo "2. 测试健康检查..."
curl -f http://127.0.0.1:5001/api/health || { echo "API 服务未启动"; kill $API_PID; exit 1; }

# 3. 创建测试指标
echo "3. 创建测试指标..."
INDICATOR_ID=$(python cli/main.py indicators create \
  --name "测试RSI策略" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70" \
  --description "简单RSI策略" \
  --format json | jq -r '.id')

echo "创建的指标ID: $INDICATOR_ID"

# 4. 列出指标
echo "4. 列出指标..."
python cli/main.py indicators list --type my --format json | jq '.items | length'

# 5. 运行指标
echo "5. 运行指标..."
python cli/main.py indicators run --id $INDICATOR_ID --symbol 600519.SH --limit 100 --format json | jq '.signals | length'

# 6. 回测指标（验证包含summary）
echo "6. 回测指标..."
python cli/main.py indicators backtest \
  --id $INDICATOR_ID \
  --symbol 600519.SH \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --format json > /tmp/backtest_result.json

# 验证 summary 字段存在
if jq -e '.summary' /tmp/backtest_result.json > /dev/null; then
  echo "✓ 回测结果包含 summary 字段"
else
  echo "✗ 回测结果缺少 summary 字段"
  kill $API_PID
  exit 1
fi

# 7. 测试沙箱列探查
echo "7. 测试沙箱列探查..."
curl -s "http://127.0.0.1:5001/api/indicators/sandbox-columns?symbol=600519.SH" | jq '.data.columns | keys | length'

# 8. 创建第二个指标用于对比
echo "8. 创建第二个指标..."
INDICATOR_ID_2=$(python cli/main.py indicators create \
  --name "测试RSI策略v2" \
  --code "df['buy'] = (df['rsi'] < 30) & (df['debt_ratio_q'] < 60); df['sell'] = df['rsi'] > 70" \
  --format json | jq -r '.id')

# 9. 测试双策略对比
echo "9. 测试双策略对比..."
curl -s -X POST http://127.0.0.1:5001/api/indicators/compare \
  -H "Content-Type: application/json" \
  -d "{
    \"indicatorIdA\": $INDICATOR_ID,
    \"indicatorIdB\": $INDICATOR_ID_2,
    \"symbol\": \"600519.SH\",
    \"startDate\": \"2024-01-01\",
    \"endDate\": \"2024-12-31\"
  }" | jq '.data.comparison.filtered_by_b_only'

# 10. 清理
echo "10. 清理..."
kill $API_PID

echo "=== 所有测试通过 ==="
```

- [ ] **Step 2: 添加执行权限**

```bash
chmod +x quantsys-v2/tests/integration/test_indicator_e2e.sh
```

- [ ] **Step 3: 运行集成测试**

```bash
cd quantsys-v2
./tests/integration/test_indicator_e2e.sh
```

Expected: 所有步骤通过，输出 "=== 所有测试通过 ==="

- [ ] **Step 4: 提交**

```bash
cd quantsys-v2
git add tests/integration/test_indicator_e2e.sh
git commit -m "test: add end-to-end integration test for indicator tools"
```

---

## Task 8: 文档更新

**Files:**
- Modify: `quantsys-v2/CLAUDE.md`

- [ ] **Step 1: 更新 CLAUDE.md 文档**

在 `quantsys-v2/CLAUDE.md` 的 "Dev Commands" 部分添加:

```markdown
# CLI - Indicator Commands
python cli/main.py indicators list [--type my|system]
python cli/main.py indicators create --name "策略名" --code "代码或文件路径"
python cli/main.py indicators update --id 1 --code "新代码"
python cli/main.py indicators run --id 1 --symbol 600519.SH
python cli/main.py indicators backtest --id 1 --symbol 600519.SH --start 2024-01-01 --end 2024-12-31
```

在 "API Endpoints" 部分添加:

```markdown
## Indicator Endpoints

- `GET /api/indicators/sandbox-columns?symbol=600519.SH` - 沙箱列可用性探查
- `POST /api/indicators/compare` - 双策略对比回测
- `POST /api/indicators/backtest` - 回测指标（包含 summary 摘要）
```

- [ ] **Step 2: 创建使用示例文档**

创建 `quantsys-v2/docs/examples/indicator-tools-usage.md`:

```markdown
# 指标工具使用示例

## CLI 命令示例

### 1. 创建指标

```bash
# 从代码字符串创建
python cli/main.py indicators create \
  --name "RSI超卖策略" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70" \
  --description "简单RSI策略"

# 从文件创建
python cli/main.py indicators create \
  --name "复杂策略" \
  --code strategy.py \
  --params '{"period": 14}'
```

### 2. 列出指标

```bash
# 列出所有指标
python cli/main.py indicators list

# 只列出自定义指标
python cli/main.py indicators list --type my

# 分页
python cli/main.py indicators list --page 2 --page-size 10
```

### 3. 更新指标

```bash
python cli/main.py indicators update \
  --id 1 \
  --code "df['buy'] = (df['rsi'] < 30) & (df['roe_q'] > 15); df['sell'] = df['rsi'] > 70"
```

### 4. 运行指标

```bash
python cli/main.py indicators run \
  --id 1 \
  --symbol 600519.SH \
  --limit 100
```

### 5. 回测指标

```bash
python cli/main.py indicators backtest \
  --id 1 \
  --symbol 600519.SH \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --format json | jq '.summary'
```

## API 使用示例

### 1. 沙箱列探查

```bash
curl "http://127.0.0.1:5001/api/indicators/sandbox-columns?symbol=600519.SH" | jq '.data.columns | keys'
```

### 2. 双策略对比

```bash
curl -X POST http://127.0.0.1:5001/api/indicators/compare \
  -H "Content-Type: application/json" \
  -d '{
    "indicatorIdA": 1,
    "indicatorIdB": 2,
    "symbol": "600519.SH",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }' | jq '.data.comparison'
```

## 常见工作流

### 策略迭代优化

```bash
# 1. 创建基础版本
python cli/main.py indicators create --name "RSI v1" --code "df['buy'] = df['rsi'] < 30"

# 2. 回测
python cli/main.py indicators backtest --id 1 --symbol 600519.SH --start 2024-01-01 --end 2024-12-31

# 3. 创建改进版本
python cli/main.py indicators create --name "RSI v2" --code "df['buy'] = (df['rsi'] < 30) & (df['debt_ratio_q'] < 60)"

# 4. 对比两个版本
curl -X POST http://127.0.0.1:5001/api/indicators/compare \
  -H "Content-Type: application/json" \
  -d '{"indicatorIdA": 1, "indicatorIdB": 2, "symbol": "600519.SH", "startDate": "2024-01-01", "endDate": "2024-12-31"}'
```
```

- [ ] **Step 3: 提交文档**

```bash
cd quantsys-v2
git add CLAUDE.md docs/examples/indicator-tools-usage.md
git commit -m "docs: update documentation for indicator tools system"
```

---

## 自我审查清单

### 1. 规格覆盖检查

- [x] CLI 命令（5个）：list, create, update, run, backtest - Task 1, 2
- [x] 沙箱列探查端点 - Task 5
- [x] 双策略对比端点 - Task 6
- [x] 回测摘要增强 - Task 3, 4
- [x] 参数验证和错误处理 - Task 1
- [x] 测试覆盖 - Task 1-7
- [x] 文档更新 - Task 8

### 2. Placeholder 扫描

- [x] 无 TBD 或 TODO
- [x] 所有代码块完整
- [x] 所有测试命令包含预期输出

### 3. 类型一致性

- [x] CLI 参数命名：snake_case (page_size, initial_cash)
- [x] API 参数命名：camelCase (indicatorId, startDate)
- [x] 函数命名一致：calculate_backtest_summary
- [x] 命令名称一致：indicators.list, indicators.create 等

### 4. 依赖关系

- Task 1 → Task 2 (命令类必须先存在才能注册)
- Task 3 → Task 4 (摘要函数必须先实现才能在端点中使用)
- Task 1-6 → Task 7 (集成测试依赖所有功能)
- Task 1-7 → Task 8 (文档更新在功能完成后)

---

## 执行建议

**预计工期：** 3-5 天

**优先级顺序：**
1. Task 1-2: CLI 基础（最大痛点）
2. Task 3-4: 回测摘要（快速见效）
3. Task 5: 沙箱列探查（独立功能）
4. Task 6: 双策略对比（独立功能）
5. Task 7: 集成测试（验证）
6. Task 8: 文档（收尾）

**风险点：**
- KlineRepository.get_klines() 可能需要调整参数
- 财务指标列名可能与实际数据库不一致
- 回测性能可能需要优化（双策略对比）

