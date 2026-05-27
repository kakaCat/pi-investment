# 指标工具系统设计文档

**日期：** 2026-05-27  
**作者：** Claude  
**状态：** 设计阶段

## 1. 背景与目标

### 1.1 问题描述

当前 quantsys-v2 系统存在以下痛点（按影响排序）：

1. **quant_cli 缺指标 CRUD 命令**（最大痛点）
   - 当前只能用 curl + 手动 JSON 转义操作指标
   - 后端路由已完整（`/api/indicators/*`），但 CLI 缺少对应命令
   - 需要补充：`indicators.create`, `indicators.update`, `indicators.run`, `indicators.backtest`

2. **缺少沙箱列可用性探查端点**
   - 回测前不知道 `roe_q`/`debt_ratio_q`/`atr` 等列对某只标的是否有数据
   - 需要端点：`GET /api/indicators/sandbox-columns?symbol=600010`
   - 返回：列名 → 有值比例 + 最新值

3. **缺少双策略对比回测端点**
   - 验证 v5 vs v6 的差异，现在要手动跑两次 + diff
   - 需要端点：`POST /api/indicators/compare`
   - 返回：两个策略的对比结果，包括 B 过滤掉的交易

4. **回测结果缺少关键指标摘要**
   - 当前 `indicators/backtest` 返回 `equity_curve` + `trades` 原始数组
   - 需要在返回体添加 `summary` 字段：总收益、年化收益、最大回撤、夏普比率、胜率等

### 1.2 目标

实现完整的指标工具系统，包括：
- 5 个 CLI 命令（list/create/update/run/backtest）
- 3 个新后端端点（sandbox-columns/compare）+ 1 个增强端点（backtest summary）
- 提升指标开发和回测的效率

### 1.3 非目标

- 不修改现有 `strategy.*` 命令（保持向后兼容）
- 不改变指标的存储结构（仍使用 `strategies` 表，`code_type='indicator'`）
- 不引入新的服务层抽象（复用现有 `StrategyService`）

## 2. 整体架构

### 2.1 改动范围

```
quantsys-v2/
├── cli/
│   ├── commands/
│   │   ├── indicator_commands.py          [新增] 5个指标CLI命令
│   │   └── __init__.py                     [修改] 导出indicator_commands
│   ├── command_registry.py                 [修改] 注册indicator命令
│   └── main.py                             [修改] 添加indicators.*子命令解析
├── api/
│   └── routes/
│       └── indicators.py                   [修改] 添加3个新端点
└── services/
    └── strategy_code_service.py            [可选] 添加辅助方法
```

### 2.2 技术方案选择

**选择方案 A：最小改动方案**

**CLI 层：**
- 新建 `indicator_commands.py`，实现 5 个命令类
- 继承 `HTTPCommand`，直接调用现有 API 端点
- 在 `main.py` 添加 `indicators.*` 子命令解析器

**后端层：**
- 在 `indicators.py` 添加 3 个新端点
- 修改 `backtest_indicator()` 返回体，添加 `summary` 字段
- 复用现有 `StrategyService` 和 `StrategyRepository`

**优点：**
- 改动最小，风险低
- 不破坏现有 `strategy.*` 命令
- 清晰的 API 边界

## 3. CLI 命令设计

### 3.1 命令接口定义

```bash
# 1. 列出指标
qsv2 indicators list [--page 1] [--page-size 20] [--type my|system] [--author xxx]

# 2. 创建指标
qsv2 indicators create --name "RSI策略" --code "代码内容或文件路径" \
  [--description "描述"] [--params '{"period":14}']

# 3. 更新指标
qsv2 indicators update --id 123 [--name "新名称"] [--code "新代码"] \
  [--params '{}'] [--active true]

# 4. 运行指标
qsv2 indicators run --id 123 --symbol 600519.SH [--limit 100]

# 5. 回测指标
qsv2 indicators backtest --id 123 --symbol 600519.SH \
  --start 2024-01-01 --end 2024-12-31 [--initial-cash 1000000]
```

### 3.2 命令实现结构

每个命令继承 `HTTPCommand`，实现三个方法：
- `name` - 命令名称（如 "indicators.create"）
- `validate_params(**kwargs)` - 参数验证
- `execute(**kwargs)` - 调用 HTTP API，返回 `CommandResult`

### 3.3 与现有 strategy 命令的区别

| 特性 | strategy.* | indicators.* |
|------|-----------|--------------|
| 命名空间 | strategy | indicators |
| API 端点 | `/api/strategies/*` | `/api/indicators/*` |
| type 参数 | 必须指定 `--type indicator` | 自动设置 `code_type='indicator'` |
| 适用场景 | 通用策略管理 | 专门的指标操作 |

### 3.4 参数处理

**--code 参数：**
- 检查是否以 `.py` 结尾
- 如果是文件路径，读取文件内容
- 否则作为代码字符串直接使用

**--params 参数：**
- JSON 字符串格式
- 解析为 Python 字典
- 验证 JSON 格式有效性

**--active 参数：**
- 字符串 "true"/"false"
- 转换为布尔值

## 4. 后端 API 设计

### 4.1 沙箱列可用性探查端点

**端点：** `GET /api/indicators/sandbox-columns?symbol=600519.SH`

**功能：** 查询指定股票的沙箱列（财务指标 + 技术指标）可用性

**请求参数：**
- `symbol` (必需): 股票代码，如 "600519.SH"

**返回格式：**
```json
{
  "success": true,
  "data": {
    "symbol": "600519.SH",
    "columns": {
      "roe_q": {
        "coverage": 0.95,
        "latest_value": 12.3,
        "latest_date": "2024-12-31"
      },
      "debt_ratio_q": {
        "coverage": 0.95,
        "latest_value": 45.2,
        "latest_date": "2024-12-31"
      },
      "atr": {
        "coverage": 1.0,
        "latest_value": 8.5,
        "latest_date": "2024-12-31"
      },
      "rsi": {
        "coverage": 0.98,
        "latest_value": 65.2,
        "latest_date": "2024-12-31"
      },
      "macd": {
        "coverage": 0.98,
        "latest_value": 2.3,
        "latest_date": "2024-12-31"
      }
    },
    "total_rows": 1000,
    "date_range": {
      "start": "2020-01-01",
      "end": "2024-12-31"
    }
  }
}
```

**实现逻辑：**
1. 调用 `KlineRepository.get_klines(symbol)` 获取 K线数据（带财务和技术指标）
2. 使用 Pandas 统计每列的非空比例：`coverage = df[col].notna().sum() / len(df)`
3. 获取每列最新非空值和对应日期
4. 返回结果

**依赖：**
- `repositories.kline_repository.KlineRepository`
- Pandas 数据处理

**错误处理：**
- 缺少 `symbol` 参数 → 400 错误
- 股票不存在或无数据 → 404 错误

---

### 4.2 双策略对比回测端点

**端点：** `POST /api/indicators/compare`

**功能：** 对比两个指标策略的回测结果，找出差异交易

**请求体：**
```json
{
  "indicatorIdA": 5,
  "indicatorIdB": 6,
  "symbol": "600010.SH",
  "startDate": "2024-01-01",
  "endDate": "2024-12-31",
  "initialCash": 1000000
}
```

**返回格式：**
```json
{
  "success": true,
  "data": {
    "strategy_a": {
      "indicator_id": 5,
      "name": "RSI v5",
      "total_return": -0.017,
      "total_trades": 28,
      "equity_curve": [...],
      "trades": [...]
    },
    "strategy_b": {
      "indicator_id": 6,
      "name": "RSI v6",
      "total_return": -0.015,
      "total_trades": 22,
      "equity_curve": [...],
      "trades": [...]
    },
    "comparison": {
      "return_diff": 0.002,
      "trades_diff": -6,
      "filtered_by_b_only": 6,
      "filtered_trades": [
        {
          "date": "2024-03-15",
          "reason": "debt_ratio filter",
          "would_buy_price": 10.5,
          "signal_a": "buy",
          "signal_b": "hold"
        }
      ]
    }
  }
}
```

**实现逻辑：**
1. 验证两个指标 ID 存在且类型为 'indicator'
2. 分别调用 `StrategyService.backtest_strategy()` 回测两个策略
3. 对比交易列表：
   - 找出 A 有买入信号但 B 没有的日期
   - 这些就是 B 过滤掉的交易
4. 计算差异指标：
   - `return_diff = strategy_b.total_return - strategy_a.total_return`
   - `trades_diff = strategy_b.total_trades - strategy_a.total_trades`
   - `filtered_by_b_only = len(filtered_trades)`

**依赖：**
- `services.strategy_code_service.StrategyCodeService`
- 自定义对比逻辑

**错误处理：**
- 缺少必需参数 → 400 错误
- 指标不存在 → 404 错误
- 指标类型不是 'indicator' → 400 错误

---

### 4.3 回测结果增强（添加 summary）

**端点：** `POST /api/indicators/backtest`（现有端点增强）

**功能：** 在现有回测结果中添加摘要指标

**新增返回字段：**
```json
{
  "success": true,
  "data": {
    "equity_curve": [...],
    "trades": [...],
    "summary": {
      "total_return": -0.017,
      "annual_return": -0.034,
      "max_drawdown": -0.12,
      "sharpe_ratio": -0.5,
      "win_rate": 0.42,
      "total_trades": 28,
      "winning_trades": 12,
      "losing_trades": 16,
      "avg_win": 0.025,
      "avg_loss": -0.018,
      "profit_factor": 1.39
    }
  }
}
```

**计算逻辑：**

新增辅助函数 `calculate_backtest_summary(equity_curve, trades, start_date, end_date)`：

```python
def calculate_backtest_summary(equity_curve, trades, start_date, end_date):
    """计算回测摘要指标"""
    
    # 1. 总收益率
    initial_equity = equity_curve[0]['equity']
    final_equity = equity_curve[-1]['equity']
    total_return = (final_equity - initial_equity) / initial_equity
    
    # 2. 年化收益率
    days = (end_date - start_date).days
    years = days / 365.0
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    
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
    
    # 4. 夏普比率（假设无风险利率 3%）
    returns = []
    for i in range(1, len(equity_curve)):
        ret = (equity_curve[i]['equity'] - equity_curve[i-1]['equity']) / equity_curve[i-1]['equity']
        returns.append(ret)
    
    if len(returns) > 0:
        avg_return = sum(returns) / len(returns)
        std_return = (sum((r - avg_return)**2 for r in returns) / len(returns)) ** 0.5
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
    
    profit_factor = abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades else 0
    
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

**修改位置：**
在 `api/routes/indicators.py` 的 `backtest_indicator()` 函数中，调用此方法并添加到返回结果。

## 5. 实现细节

### 5.1 CLI 层实现（indicator_commands.py）

**文件位置：** `quantsys-v2/cli/commands/indicator_commands.py`

**命令类结构：**

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

### 5.2 CLI 注册（command_registry.py）

**修改位置：** `quantsys-v2/cli/command_registry.py`

在 `auto_discover_commands()` 函数中添加：

```python
def auto_discover_commands(http_client) -> CommandRegistry:
    """自动发现并注册所有命令"""
    from .commands import stock_commands, market_commands, kline_commands
    from .commands import factor_commands, signal_commands, strategy_commands
    from .commands import indicator_commands  # 新增

    registry = CommandRegistry()

    # ... 现有注册代码 ...

    # 注册Indicator命令（新增）
    for cmd_class in indicator_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    return registry
```

### 5.3 CLI 参数解析（main.py）

**修改位置：** `quantsys-v2/cli/main.py`

在 `create_parser()` 函数中添加 indicators 子命令：

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
```

### 5.4 后端实现（indicators.py）

**修改位置：** `quantsys-v2/api/routes/indicators.py`

#### 5.4.1 沙箱列探查端点

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

#### 5.4.2 双策略对比端点

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

#### 5.4.3 回测摘要增强

在 `backtest_indicator()` 函数末尾添加：

```python
@indicators_bp.route('/api/indicators/backtest', methods=['POST'])
@handle_api_error
def backtest_indicator():
    """回测指标"""
    # ... 现有代码 ...
    
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


## 6. 测试策略

### 6.1 单元测试

**CLI 命令测试（test_indicator_commands.py）：**

```python
"""测试指标命令"""
import pytest
from unittest.mock import Mock, patch
from cli.commands.indicator_commands import (
    IndicatorListCommand,
    IndicatorCreateCommand,
    IndicatorUpdateCommand,
    IndicatorRunCommand,
    IndicatorBacktestCommand
)


def test_indicator_create_validation():
    """测试创建指标参数验证"""
    cmd = IndicatorCreateCommand(Mock())
    
    # 缺少name
    error = cmd.validate_params(code="test")
    assert error == "指标名称不能为空"
    
    # 缺少code
    error = cmd.validate_params(name="测试")
    assert error == "指标代码不能为空"
    
    # 参数完整
    error = cmd.validate_params(name="测试", code="test")
    assert error is None


def test_indicator_backtest_validation():
    """测试回测指标参数验证"""
    cmd = IndicatorBacktestCommand(Mock())
    
    # 缺少必需参数
    error = cmd.validate_params(id="1", symbol="600519.SH")
    assert "开始日期" in error
    
    # 参数完整
    error = cmd.validate_params(
        id="1",
        symbol="600519.SH",
        start="2024-01-01",
        end="2024-12-31"
    )
    assert error is None
```

**后端 API 测试（test_indicators_routes.py）：**

```python
"""测试指标路由"""
import pytest
from flask import Flask
from api.routes.indicators import indicators_bp


def test_sandbox_columns_missing_symbol(client):
    """测试沙箱列探查缺少symbol参数"""
    response = client.get('/api/indicators/sandbox-columns')
    assert response.status_code == 400


def test_compare_indicators_success(client):
    """测试对比指标成功"""
    response = client.post('/api/indicators/compare', json={
        'indicatorIdA': 1,
        'indicatorIdB': 2,
        'symbol': '600519.SH',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert 'comparison' in data['data']
```

### 6.2 集成测试

**端到端测试流程：**

```bash
# 1. 启动 quantsys-v2 API 服务
cd quantsys-v2
python api/server.py &

# 2. 创建测试指标
python cli/main.py indicators create \
  --name "测试RSI策略" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70"

# 3. 回测指标（验证包含summary）
python cli/main.py indicators backtest \
  --id 1 \
  --symbol 600519.SH \
  --start 2024-01-01 \
  --end 2024-12-31

# 4. 测试沙箱列探查
curl "http://127.0.0.1:5001/api/indicators/sandbox-columns?symbol=600519.SH"

# 5. 测试双策略对比
curl -X POST http://127.0.0.1:5001/api/indicators/compare \
  -H "Content-Type: application/json" \
  -d '{
    "indicatorIdA": 1,
    "indicatorIdB": 2,
    "symbol": "600519.SH",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }'
```

### 6.3 验收标准

**功能完整性：**
- ✅ 5 个 CLI 命令全部可用（list/create/update/run/backtest）
- ✅ 3 个新 API 端点正常工作（sandbox-columns/compare）
- ✅ 回测结果包含 summary 字段（10个指标）
- ✅ CLI 支持文件路径和直接代码两种方式
- ✅ 参数验证完整，错误提示友好

**性能要求：**
- 沙箱列探查：< 2 秒（1000行数据）
- 单策略回测：< 5 秒（250个交易日）
- 双策略对比：< 10 秒（两次回测 + 对比）

**错误处理：**
- 参数缺失有明确提示（中文）
- 指标不存在返回 404 + 友好提示
- 数据不足有说明
- JSON 格式错误有详细提示

## 7. 实施计划

### 7.1 开发顺序

**Phase 1: CLI 基础命令（优先级最高）**
1. 创建 `indicator_commands.py`
2. 实现 5 个命令类
3. 注册到 `command_registry.py`
4. 添加 `main.py` 参数解析
5. 单元测试

**Phase 2: 回测摘要增强**
1. 实现 `calculate_backtest_summary()` 函数
2. 修改 `backtest_indicator()` 端点
3. 单元测试

**Phase 3: 沙箱列探查**
1. 实现 `get_sandbox_columns()` 端点
2. 单元测试

**Phase 4: 双策略对比**
1. 实现 `compare_indicators()` 端点
2. 单元测试

**Phase 5: 文档和验收**
1. 更新 CLAUDE.md
2. 编写使用示例
3. 完整端到端测试

### 7.2 风险与缓解

**风险1：回测性能问题**
- 风险：双策略对比需要两次完整回测，可能超时
- 缓解：限制回测日期范围（最多1年）、添加缓存机制

**风险2：沙箱列数据不一致**
- 风险：不同股票的财务指标覆盖率差异大
- 缓解：返回 coverage 比例，让用户判断

**风险3：CLI 参数复杂度**
- 风险：--code 参数支持文件和字符串，可能混淆
- 缓解：文档明确说明、错误提示友好

## 8. 总结

本设计文档详细描述了指标工具系统的实现方案，包括：

1. **5 个 CLI 命令** - 提供完整的指标 CRUD 操作
2. **3 个新 API 端点** - 沙箱列探查、双策略对比、回测摘要
3. **最小改动原则** - 复用现有服务，不破坏现有功能
4. **完整测试策略** - 单元测试 + 集成测试 + 端到端测试

**核心价值：**
- 解决用户最大痛点（CLI 缺失）
- 提升回测效率（沙箱列探查、策略对比）
- 改善用户体验（摘要指标、友好错误提示）

**实施周期：** 预计 3-5 天完成核心功能，1 周完成全部测试和文档。
