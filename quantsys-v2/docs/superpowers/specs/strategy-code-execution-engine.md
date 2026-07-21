# 策略代码执行引擎设计文档

## 文档信息

- **标题**: 策略代码执行引擎 (Strategy Code Execution Engine)
- **版本**: 1.0
- **创建日期**: 2026-05-22
- **状态**: 设计完成，待实施

## 1. 概述

### 1.1 背景

QuantDinger 项目提供了强大的用户自定义策略功能，允许用户通过编写 Python 代码来实现自己的交易策略。这个功能极大地提升了系统的灵活性和可扩展性。

quantsys-v2 作为 AI Agent 的量化工具，需要移植这个核心能力，使 AI Agent 能够：
1. 生成策略代码
2. 提交策略到系统
3. 验证策略安全性
4. 回测策略
5. 运行策略生成交易信号

### 1.2 目标

**核心目标**：
- 支持两种策略模式：IndicatorStrategy（信号驱动）和 ScriptStrategy（事件驱动）
- 提供安全的代码沙箱执行环境
- 通过 CLI 接口供 AI Agent 调用
- 完整的策略生命周期管理（创建、验证、回测、运行、更新、删除）

**非目标**：
- 不提供 Web UI（Web 平台由独立项目负责）
- 不集成 LLM（AI Agent 本身就是 LLM）
- 不支持实盘交易（当前阶段只做回测和信号生成）

### 1.3 设计原则

1. **安全第一**：代码执行必须在沙箱环境中，禁止危险操作
2. **简单易用**：AI Agent 通过简单的 CLI 命令即可操作
3. **灵活扩展**：支持两种策略模式，满足不同场景需求
4. **性能优先**：代码执行和回测要高效
5. **可观测性**：完整的日志和错误信息

---

## 2. 整体架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│ AI Agent (Claude/GPT)                                       │
│ - 生成策略代码                                               │
│ - 调用 CLI 命令                                              │
└──────────────────┬──────────────────────────────────────────┘
                   ↓ CLI 命令
┌─────────────────────────────────────────────────────────────┐
│ CLI Layer (cli/commands/strategy_commands.py)              │
│ - strategy.create                                           │
│ - strategy.backtest                                         │
│ - strategy.run                                              │
│ - strategy.list / get / update / delete                    │
└──────────────────┬──────────────────────────────────────────┘
                   ↓ 直接调用
┌─────────────────────────────────────────────────────────────┐
│ Service Layer (services/strategy_code_service.py)          │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ StrategyCodeService                                     │ │
│ │ - create_strategy()      # 创建策略                     │ │
│ │ - validate_code()        # 验证代码                     │ │
│ │ - backtest_strategy()    # 回测策略                     │ │
│ │ - run_strategy()         # 运行策略                     │ │
│ │ - list_strategies()      # 列出策略                     │ │
│ │ - get_strategy()         # 获取详情                     │ │
│ │ - update_strategy()      # 更新策略                     │ │
│ │ - delete_strategy()      # 删除策略                     │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   ↓ 调用引擎
┌─────────────────────────────────────────────────────────────┐
│ Strategy Engine Layer                                       │
│ ┌──────────────────────┐  ┌──────────────────────────────┐ │
│ │ IndicatorStrategy    │  │ ScriptStrategy               │ │
│ │ Executor             │  │ Executor                     │ │
│ │ - 信号驱动            │  │ - 事件驱动                    │ │
│ │ - df['buy']/['sell'] │  │ - on_init() / on_bar()       │ │
│ │ - 图表输出            │  │ - ctx.buy() / ctx.sell()     │ │
│ └──────────────────────┘  └──────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ParamParser (参数解析器)                                 │ │
│ │ - parse_params()      # 解析 @param                    │ │
│ │ - parse_strategy_config() # 解析 @strategy             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ CodeValidator (代码安全验证)                             │ │
│ │ - validate()              # 验证代码安全性              │ │
│ │ - check_syntax()          # 语法检查                   │ │
│ │ - check_forbidden_imports() # 禁止危险导入             │ │
│ │ - check_forbidden_operations() # 禁止危险操作          │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   ↓ 数据存储
┌─────────────────────────────────────────────────────────────┐
│ Repository Layer (repositories/strategy_repository.py)     │
│ - create_user_strategy()                                    │
│ - get_user_strategies()                                     │
│ - update_validation_status()                                │
│ - update_last_executed()                                    │
│ - update() / delete()                                       │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ Database (PostgreSQL)                                       │
│ - quant.strategy_configs (扩展)                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 两种策略模式对比

| 维度 | IndicatorStrategy | ScriptStrategy |
|------|-------------------|----------------|
| **编程模式** | 信号驱动 | 事件驱动 |
| **代码风格** | DataFrame 操作 | 逐 bar 处理 |
| **信号生成** | `df['buy']` / `df['sell']` | `ctx.buy()` / `ctx.sell()` |
| **状态管理** | 无状态 | 有状态 (`ctx.state`) |
| **适用场景** | 技术指标策略 | 复杂交易逻辑（网格、套利等） |
| **图表输出** | 支持 `output` | 不支持 |
| **AI 使用难度** | 更简单 | 更灵活 |
| **执行方式** | 一次性处理全部数据 | 逐 bar 回调 |

### 2.3 调用流程

```python
# AI Agent 通过 CLI 调用
$ qsv2 strategy.create --name "双均线" --type indicator --code "..."

# CLI 直接调用 Service
from services.strategy_code_service import StrategyCodeService

service = StrategyCodeService()
result = service.create_strategy(
    name="双均线",
    code="df['buy'] = ...",
    code_type='indicator'
)

# Service 调用 Engine
executor = IndicatorStrategyExecutor()
result = executor.execute(code, klines, params)

# Engine 调用 Repository
repo = StrategyRepository()
strategy = repo.create_user_strategy(data)
```

---

## 3. IndicatorStrategy 详细设计

### 3.1 概念

**IndicatorStrategy** 是信号驱动的策略模式，用户通过 DataFrame 操作生成买卖信号。

**核心特点**：
- 基于 pandas DataFrame 操作
- 通过 `df['buy']` 和 `df['sell']` 列生成信号
- 支持图表输出（`output` 变量）
- 无状态，适合技术指标策略

### 3.2 代码示例

```python
# ============================================================
# 双均线交叉策略
# ============================================================

# 策略元数据
my_indicator_name = "双均线交叉策略"
my_indicator_description = "使用短期/长期均线金叉与死叉生成买卖信号"

# 参数声明（供 AI 和系统解析）
# @param ma_short int 5 短期均线周期
# @param ma_long int 20 长期均线周期

# 策略风控配置
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05
# @strategy entryPct 0.25

# 获取参数
ma_short = params.get('ma_short', 5)
ma_long = params.get('ma_long', 20)

# 计算指标
df = df.copy()
df['ma_short'] = df['close'].rolling(ma_short).mean()
df['ma_long'] = df['close'].rolling(ma_long).mean()

# 生成信号（金叉买入，死叉卖出）
df['buy'] = (df['ma_short'] > df['ma_long']) & (df['ma_short'].shift(1) <= df['ma_long'].shift(1))
df['sell'] = (df['ma_short'] < df['ma_long']) & (df['ma_short'].shift(1) >= df['ma_long'].shift(1))

# 图表输出（可选）
output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": f"MA{ma_short}",
            "data": df['ma_short'].fillna(0).tolist(),
            "color": "#FF9800",
            "overlay": True
        },
        {
            "name": f"MA{ma_long}",
            "data": df['ma_long'].fillna(0).tolist(),
            "color": "#3F51B5",
            "overlay": True
        }
    ]
}
```

### 3.3 执行流程

```
1. 验证代码安全性
   ↓
2. 解析 @param 和 @strategy 注释
   ↓
3. 合并参数（用户传入覆盖默认值）
   ↓
4. 创建沙箱环境（受限的 namespace）
   ↓
5. 执行代码（exec(code, namespace)）
   ↓
6. 验证信号列（df['buy'] 和 df['sell']）
   ↓
7. 提取 output（可选）
   ↓
8. 返回结果
```

### 3.4 核心组件

**文件**: `quant/engine/indicator_strategy_executor.py`

**主要类**:
- `IndicatorStrategyExecutor`: 执行引擎
- `ParamParser`: 参数解析器
- `CodeValidator`: 代码验证器
- `IndicatorStrategyResult`: 执行结果

**关键方法**:
```python
def execute(code: str, klines: List[Dict], params: Dict) -> IndicatorStrategyResult:
    """执行 IndicatorStrategy 代码"""
    pass

def _create_sandbox_namespace(df: pd.DataFrame, params: Dict) -> Dict:
    """创建沙箱执行环境"""
    pass

def _validate_signals(df: pd.DataFrame):
    """验证信号列存在且有效"""
    pass
```

---

## 4. ScriptStrategy 详细设计

### 4.1 概念

**ScriptStrategy** 是事件驱动的策略模式，用户通过 `on_init` 和 `on_bar` 回调函数实现策略逻辑。

**核心特点**：
- 事件驱动，逐 bar 处理
- 通过 `ctx.buy()` 和 `ctx.sell()` 下单
- 有状态管理（`ctx.state`）
- 适合复杂交易逻辑（网格、套利、高频等）

### 4.2 代码示例

```python
# ============================================================
# 网格交易策略 (ScriptStrategy)
# ============================================================

# 策略元数据
strategy_name = "网格交易策略"
strategy_description = "在价格区间内进行网格交易"

# 参数声明
# @param grid_size float 0.02 网格间距（百分比）
# @param grid_levels int 5 网格层数
# @param position_size float 0.1 每格仓位大小

# 策略风控配置
# @strategy stopLossPct 0.10
# @strategy maxPositions 5

def on_init(ctx):
    """策略初始化"""
    ctx.state['grids'] = []
    ctx.state['positions'] = {}
    ctx.state['base_price'] = None
    ctx.state['grid_size'] = ctx.params.get('grid_size', 0.02)
    ctx.state['grid_levels'] = ctx.params.get('grid_levels', 5)
    ctx.state['position_size'] = ctx.params.get('position_size', 0.1)
    
    ctx.log(f"网格策略初始化: 网格间距={ctx.state['grid_size']}")

def on_bar(ctx, bar):
    """每根 K 线回调"""
    price = bar.close
    
    # 首次运行，设置基准价格和网格
    if ctx.state['base_price'] is None:
        ctx.state['base_price'] = price
        ctx.state['grids'] = _calculate_grids(
            base_price=price,
            grid_size=ctx.state['grid_size'],
            levels=ctx.state['grid_levels']
        )
        return
    
    # 检查每个网格
    for level, grid_price in enumerate(ctx.state['grids']):
        # 价格下穿网格线 -> 买入
        if price <= grid_price and level not in ctx.state['positions']:
            buy_size = ctx.cash * ctx.state['position_size'] / price
            if buy_size > 0:
                ctx.buy(size=buy_size, price=price, reason=f"网格买入 Level {level}")
                ctx.state['positions'][level] = buy_size
        
        # 价格上穿网格线 -> 卖出
        elif price >= grid_price * (1 + ctx.state['grid_size']) and level in ctx.state['positions']:
            sell_size = ctx.state['positions'][level]
            if sell_size > 0:
                ctx.sell(size=sell_size, price=price, reason=f"网格卖出 Level {level}")
                del ctx.state['positions'][level]

def _calculate_grids(base_price, grid_size, levels):
    """计算网格价格"""
    return [base_price * (1 - grid_size * (i + 1)) for i in range(levels)]
```

### 4.3 执行流程

```
1. 验证代码安全性
   ↓
2. 解析 @param 和 @strategy 注释
   ↓
3. 创建策略上下文 (StrategyContext)
   ↓
4. 提取 on_init 和 on_bar 函数
   ↓
5. 执行 on_init(ctx)
   ↓
6. 逐 bar 执行 on_bar(ctx, bar)
   ↓
7. 记录交易和权益曲线
   ↓
8. 返回结果
```

### 4.4 核心组件

**文件**: `quant/engine/script_strategy_executor.py`

**主要类**:
- `ScriptStrategyExecutor`: 执行引擎
- `StrategyContext`: 策略上下文对象（ctx）
- `Bar`: K 线数据对象
- `Trade`: 交易记录

**StrategyContext API**:
```python
class StrategyContext:
    # 属性
    params: Dict          # 参数
    state: Dict           # 用户状态
    cash: float           # 当前现金
    position: float       # 当前持仓
    equity: float         # 当前权益
    
    # 方法
    def buy(size, price=None, reason="")
    def sell(size, price=None, reason="")
    def close_position(reason="")
    def log(message)
```


---

## 5. 数据库 Schema

### 5.1 扩展 strategy_configs 表

```sql
-- 添加新字段支持用户自定义策略
ALTER TABLE quant.strategy_configs 
ADD COLUMN IF NOT EXISTS code_content TEXT,              -- 策略代码内容
ADD COLUMN IF NOT EXISTS code_type VARCHAR(50),          -- 'builtin' | 'indicator' | 'script'
ADD COLUMN IF NOT EXISTS parsed_params JSONB,            -- 解析后的参数定义
ADD COLUMN IF NOT EXISTS risk_config JSONB,              -- 风控配置
ADD COLUMN IF NOT EXISTS metadata JSONB,                 -- 策略元数据
ADD COLUMN IF NOT EXISTS validation_status VARCHAR(50),  -- 'pending' | 'valid' | 'invalid'
ADD COLUMN IF NOT EXISTS validation_errors TEXT,         -- 验证错误信息
ADD COLUMN IF NOT EXISTS last_executed_at TIMESTAMP;     -- 最后执行时间

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_strategy_code_type ON quant.strategy_configs(code_type);
CREATE INDEX IF NOT EXISTS idx_strategy_validation_status ON quant.strategy_configs(validation_status);

-- 添加注释
COMMENT ON COLUMN quant.strategy_configs.code_content IS '用户自定义策略代码';
COMMENT ON COLUMN quant.strategy_configs.code_type IS '策略类型: builtin(内置), indicator(信号驱动), script(事件驱动)';
COMMENT ON COLUMN quant.strategy_configs.parsed_params IS '从代码中解析的参数定义 @param';
COMMENT ON COLUMN quant.strategy_configs.risk_config IS '从代码中解析的风控配置 @strategy';
COMMENT ON COLUMN quant.strategy_configs.metadata IS '策略元数据(名称、描述等)';
```

### 5.2 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `code_content` | TEXT | 策略代码字符串 | `"df['buy'] = ..."` |
| `code_type` | VARCHAR(50) | 策略类型 | `'indicator'` / `'script'` / `'builtin'` |
| `parsed_params` | JSONB | 解析的参数定义 | `[{"name": "ma_short", "type": "int", "default": 5}]` |
| `risk_config` | JSONB | 风控配置 | `{"stopLossPct": 0.02, "takeProfitPct": 0.05}` |
| `metadata` | JSONB | 元数据 | `{"name": "双均线", "description": "..."}` |
| `validation_status` | VARCHAR(50) | 验证状态 | `'valid'` / `'invalid'` / `'pending'` |
| `validation_errors` | TEXT | 验证错误 | `"禁止导入模块: os"` |
| `last_executed_at` | TIMESTAMP | 最后执行时间 | `2026-05-22 10:30:00` |

### 5.3 数据示例

```json
{
  "id": 123,
  "name": "双均线策略",
  "code_type": "indicator",
  "code_content": "df['buy'] = (ma5 > ma20) & ...",
  "parsed_params": [
    {
      "name": "ma_short",
      "type": "int",
      "default": 5,
      "description": "短期均线周期"
    },
    {
      "name": "ma_long",
      "type": "int",
      "default": 20,
      "description": "长期均线周期"
    }
  ],
  "risk_config": {
    "stopLossPct": 0.02,
    "takeProfitPct": 0.05,
    "entryPct": 0.25
  },
  "metadata": {
    "name": "双均线交叉策略",
    "description": "使用短期/长期均线金叉与死叉生成买卖信号"
  },
  "validation_status": "valid",
  "validation_errors": null,
  "is_active": true,
  "last_executed_at": "2026-05-22T10:30:00Z"
}
```

---

## 6. Repository Layer

### 6.1 StrategyRepository 扩展

**文件**: `repositories/strategy_repository.py`

**新增方法**:

```python
class StrategyRepository(BaseRepository):
    """策略配置 Repository（扩展版）"""
    
    # 查询方法
    def get_user_strategies(
        code_type: Optional[str] = None,
        validation_status: Optional[str] = None
    ) -> List[Dict]:
        """获取用户自定义策略"""
        pass
    
    # 写入方法
    def create_user_strategy(data: Dict) -> Dict:
        """创建用户自定义策略"""
        pass
    
    def update_validation_status(
        strategy_id: int,
        status: str,
        errors: Optional[str] = None
    ) -> Optional[Dict]:
        """更新策略验证状态"""
        pass
    
    def update_last_executed(strategy_id: int) -> Optional[Dict]:
        """更新策略最后执行时间"""
        pass
```

### 6.2 关键实现细节

**创建策略**:
```python
def create_user_strategy(self, data: Dict) -> Dict:
    # 验证必需字段
    if 'name' not in data or not data['name']:
        raise ValueError("缺少必需字段: name")
    if 'code_content' not in data:
        raise ValueError("缺少必需字段: code_content")
    if data['code_type'] not in ('indicator', 'script'):
        raise ValueError("code_type 必须是 'indicator' 或 'script'")
    
    # 处理 JSONB 字段
    parsed_params = json.dumps(data.get('parsed_params', []))
    risk_config = json.dumps(data.get('risk_config', {}))
    metadata = json.dumps(data.get('metadata', {}))
    
    # 插入数据库
    query = """
        INSERT INTO quant.strategy_configs (
            name, code_content, code_type, parsed_params,
            risk_config, metadata, validation_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    # ...
```

---

## 7. Service Layer

### 7.1 StrategyCodeService

**文件**: `services/strategy_code_service.py`

**核心职责**:
1. 策略生命周期管理
2. 代码验证
3. 策略执行（回测和实时信号）
4. 与 Repository 和 Engine 的协调

### 7.2 主要方法

```python
class StrategyCodeService:
    """策略代码服务"""
    
    def __init__(self):
        self.strategy_repo = StrategyRepository()
        self.kline_repo = KlineRepository()
        self.indicator_executor = IndicatorStrategyExecutor()
        self.script_executor = ScriptStrategyExecutor()
        self.code_validator = CodeValidator()
    
    # ==================== 策略管理 ====================
    
    def create_strategy(
        name: str,
        code: str,
        code_type: str,
        params: Optional[Dict] = None,
        description: str = ""
    ) -> Dict:
        """
        创建用户自定义策略
        
        流程:
        1. 验证代码类型
        2. 验证代码安全性和语法
        3. 解析参数和风控配置
        4. 保存到数据库
        5. 返回策略ID和验证结果
        """
        pass
    
    def validate_code(code: str, code_type: str) -> Dict:
        """
        验证策略代码
        
        返回:
        {
            'valid': True/False,
            'error': '错误信息',
            'syntax_ok': True,
            'has_buy_signal': True,
            'has_sell_signal': True,
            'params': [...],
            'risk_config': {...}
        }
        """
        pass
    
    def list_strategies(
        code_type: Optional[str] = None,
        active_only: bool = False
    ) -> List[Dict]:
        """列出策略"""
        pass
    
    def get_strategy(strategy_id: int) -> Optional[Dict]:
        """获取策略详情"""
        pass
    
    def update_strategy(
        strategy_id: int,
        code: Optional[str] = None,
        params: Optional[Dict] = None,
        is_active: Optional[bool] = None
    ) -> Dict:
        """更新策略"""
        pass
    
    def delete_strategy(strategy_id: int) -> bool:
        """删除策略"""
        pass
    
    # ==================== 策略执行 ====================
    
    def run_strategy(
        strategy_id: int,
        symbol: str,
        limit: int = 100
    ) -> Dict:
        """
        运行策略生成实时信号
        
        返回:
        {
            'symbol': '600000',
            'latest_signal': 'buy',
            'confidence': 0.8,
            'price': 1680.0,
            'date': '2026-05-22',
            'indicators': {...}
        }
        """
        pass
    
    def backtest_strategy(
        strategy_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_cash: float = 1000000
    ) -> Dict:
        """
        回测策略
        
        返回:
        {
            'total_return': 0.15,
            'sharpe_ratio': 1.8,
            'max_drawdown': -0.12,
            'win_rate': 0.65,
            'total_trades': 45,
            'trades': [...],
            'equity_curve': [...]
        }
        """
        pass
```

### 7.3 回测流程

```
1. 获取策略配置
   ↓
2. 验证策略状态（必须是 valid）
   ↓
3. 获取 K 线数据
   ↓
4. 根据策略类型执行:
   - IndicatorStrategy: 生成信号 → 运行回测引擎
   - ScriptStrategy: 直接执行 → 得到交易记录
   ↓
5. 计算回测指标:
   - 总收益率
   - 夏普比率
   - 最大回撤
   - 胜率
   ↓
6. 更新最后执行时间
   ↓
7. 返回回测结果
```

---

## 8. CLI 命令

### 8.1 命令列表

| 命令 | 说明 | 参数 |
|------|------|------|
| `strategy.create` | 创建策略 | `--name`, `--code`, `--type`, `--params`, `--description` |
| `strategy.backtest` | 回测策略 | `--strategy-id`, `--symbol`, `--start`, `--end`, `--initial-cash` |
| `strategy.run` | 运行策略 | `--strategy-id`, `--symbol`, `--limit` |
| `strategy.list` | 列出策略 | `--type`, `--active-only` |
| `strategy.get` | 获取详情 | `--id` |
| `strategy.update` | 更新策略 | `--id`, `--code`, `--params`, `--active` |
| `strategy.delete` | 删除策略 | `--id` |

### 8.2 使用示例

**创建 IndicatorStrategy**:
```bash
qsv2 strategy create \
    --name "双均线策略" \
    --type indicator \
    --code "df['buy'] = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1)); df['sell'] = (ma5 < ma20) & (ma5.shift(1) >= ma20.shift(1))" \
    --params '{"ma_short": 5, "ma_long": 20}'
```

**从文件创建 ScriptStrategy**:
```bash
qsv2 strategy create \
    --name "网格策略" \
    --type script \
    --code ./strategies/grid_strategy.py \
    --description "网格交易策略"
```

**回测策略**:
```bash
qsv2 strategy backtest \
    --strategy-id 123 \
    --symbol 600000 \
    --start 2025-01-01 \
    --end 2026-05-22 \
    --initial-cash 1000000
```

**运行策略生成信号**:
```bash
qsv2 strategy run \
    --strategy-id 123 \
    --symbol 600000 \
    --limit 100
```

**列出所有 IndicatorStrategy**:
```bash
qsv2 strategy list --type indicator
```

**获取策略详情**:
```bash
qsv2 strategy get --id 123
```

**更新策略代码**:
```bash
qsv2 strategy update \
    --id 123 \
    --code ./strategies/updated_strategy.py
```

**删除策略**:
```bash
qsv2 strategy delete --id 123
```

### 8.3 CLI 命令实现

**文件**: `cli/commands/strategy_commands.py`

**命令类**:
- `StrategyCreateCommand`
- `StrategyBacktestCommand`
- `StrategyRunCommand`
- `StrategyListCommand`
- `StrategyGetCommand`
- `StrategyUpdateCommand`
- `StrategyDeleteCommand`

**命令基类**:
```python
class StrategyCreateCommand(CommandBase):
    @property
    def name(self) -> str:
        return "strategy.create"
    
    @property
    def description(self) -> str:
        return "创建用户自定义策略"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        # 解析参数
        name = kwargs.get('name')
        code_input = kwargs.get('code')
        code_type = kwargs.get('type', 'indicator')
        
        # 读取代码（支持文件路径或直接代码）
        if code_input.endswith('.py'):
            with open(code_input, 'r') as f:
                code = f.read()
        else:
            code = code_input
        
        # 调用服务
        service = StrategyCodeService()
        result = service.create_strategy(
            name=name,
            code=code,
            code_type=code_type
        )
        
        return result
```


---

## 9. 代码安全

### 9.1 安全威胁

用户自定义代码执行面临的主要安全威胁：
1. **文件系统访问**：读写敏感文件
2. **网络访问**：发送数据到外部服务器
3. **系统命令执行**：执行任意系统命令
4. **资源耗尽**：无限循环、内存泄漏
5. **代码注入**：通过 eval/exec 执行恶意代码

### 9.2 安全措施

**1. 沙箱执行环境**

```python
# 受限的命名空间
namespace = {
    'df': df.copy(),
    'params': params,
    'pd': pd,
    'np': np,
    '__builtins__': {
        # 只允许安全的内置函数
        'len': len,
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'sum': sum,
        'max': max,
        'min': min,
        'abs': abs,
        'round': round,
        'print': print,  # 允许 print 用于调试
    }
}

# 禁止访问危险模块
# - 不允许 import os, sys, subprocess 等
# - 不允许 open(), file() 等文件操作
# - 不允许 eval(), exec(), compile() 等动态执行
```

**2. 代码静态分析**

```python
class CodeValidator:
    FORBIDDEN_IMPORTS = [
        'os', 'sys', 'subprocess', 'socket', 'requests',
        'urllib', 'http', 'ftplib', 'smtplib', 'pickle',
        '__import__', 'eval', 'exec', 'compile'
    ]
    
    FORBIDDEN_BUILTINS = [
        'open', 'file', 'input', 'raw_input',
        'execfile', 'reload', '__import__'
    ]
    
    def validate(self, code: str):
        # 1. 语法检查
        ast.parse(code)
        
        # 2. 检查禁止的导入
        for forbidden in self.FORBIDDEN_IMPORTS:
            if re.search(rf'\bimport\s+{forbidden}\b', code):
                raise ValueError(f"禁止导入模块: {forbidden}")
        
        # 3. 检查禁止的内置函数
        for forbidden in self.FORBIDDEN_BUILTINS:
            if re.search(rf'\b{forbidden}\s*\(', code):
                raise ValueError(f"禁止使用函数: {forbidden}")
```

**3. 执行超时**

```python
# 设置执行超时（防止无限循环）
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("策略执行超时")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)  # 30秒超时

try:
    exec(code, namespace)
finally:
    signal.alarm(0)  # 取消超时
```

**4. 资源限制**

```python
# 限制内存使用
import resource

# 限制最大内存为 1GB
resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))

# 限制 CPU 时间
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
```

### 9.3 安全检查清单

- [ ] 代码语法检查（ast.parse）
- [ ] 禁止危险导入（os, sys, subprocess 等）
- [ ] 禁止危险操作（open, eval, exec 等）
- [ ] 沙箱执行环境（受限 namespace）
- [ ] 执行超时（30秒）
- [ ] 资源限制（内存、CPU）
- [ ] 信号验证（必须生成 buy/sell 信号）
- [ ] 错误捕获和日志记录

---

## 10. 实施计划

### 10.1 阶段划分

**Phase 1: 核心引擎实现（2-3天）**
- [ ] 实现 `CodeValidator`（代码安全验证）
- [ ] 实现 `ParamParser`（参数解析器）
- [ ] 实现 `IndicatorStrategyExecutor`（信号驱动执行引擎）
- [ ] 实现 `ScriptStrategyExecutor`（事件驱动执行引擎）
- [ ] 实现 `StrategyContext`（策略上下文对象）

**Phase 2: 数据层实现（1天）**
- [ ] 数据库 Schema 变更（ALTER TABLE）
- [ ] 扩展 `StrategyRepository`
- [ ] 编写数据库迁移脚本

**Phase 3: 服务层实现（2天）**
- [ ] 实现 `StrategyCodeService`
- [ ] 实现策略创建和验证
- [ ] 实现策略回测逻辑
- [ ] 实现策略运行逻辑

**Phase 4: CLI 命令实现（1天）**
- [ ] 实现 7 个策略管理命令
- [ ] 注册命令到 CLI 主入口
- [ ] 编写命令行参数解析

**Phase 5: 测试和文档（2天）**
- [ ] 单元测试（Engine Layer）
- [ ] 集成测试（Service Layer）
- [ ] CLI 命令测试
- [ ] 编写用户文档和示例

### 10.2 文件清单

**新增文件**:
```
quantsys-v2/
├── quant/engine/
│   ├── indicator_strategy_executor.py      # IndicatorStrategy 执行引擎
│   ├── script_strategy_executor.py         # ScriptStrategy 执行引擎
│   ├── code_validator.py                   # 代码安全验证器
│   └── user_code_strategy.py               # 用户代码策略基类（可选）
├── services/
│   └── strategy_code_service.py            # 策略代码服务
├── cli/commands/
│   └── strategy_commands.py                # 策略管理 CLI 命令
└── tests/
    ├── test_indicator_strategy_executor.py
    ├── test_script_strategy_executor.py
    ├── test_code_validator.py
    └── test_strategy_code_service.py
```

**修改文件**:
```
quantsys-v2/
├── repositories/
│   └── strategy_repository.py              # 扩展策略仓储
├── cli/
│   ├── main.py                             # 扩展 CLI 主入口
│   └── commands/__init__.py                # 注册新命令
└── scripts/migrations/
    └── 001_add_strategy_code_fields.sql    # 数据库迁移脚本
```

### 10.3 依赖关系

```
CodeValidator ←─────────┐
ParamParser ←──────────┐│
                       ││
IndicatorStrategyExecutor ──→ StrategyCodeService ──→ CLI Commands
ScriptStrategyExecutor ─────→                    ──→
                       ││
StrategyRepository ←───┘│
KlineRepository ←───────┘
```

### 10.4 测试策略

**单元测试**:
- `CodeValidator`: 测试各种危险代码的检测
- `ParamParser`: 测试参数和配置解析
- `IndicatorStrategyExecutor`: 测试信号生成和沙箱执行
- `ScriptStrategyExecutor`: 测试事件驱动执行和上下文管理

**集成测试**:
- `StrategyCodeService`: 测试完整的策略生命周期
- CLI 命令: 测试端到端的命令执行

**测试用例**:
```python
# 测试 IndicatorStrategy
def test_indicator_strategy_execution():
    code = """
df['ma5'] = df['close'].rolling(5).mean()
df['ma20'] = df['close'].rolling(20).mean()
df['buy'] = (df['ma5'] > df['ma20']) & (df['ma5'].shift(1) <= df['ma20'].shift(1))
df['sell'] = (df['ma5'] < df['ma20']) & (df['ma5'].shift(1) >= df['ma20'].shift(1))
    """
    executor = IndicatorStrategyExecutor()
    result = executor.execute(code, klines, {})
    assert 'buy' in result.signals.columns
    assert 'sell' in result.signals.columns

# 测试 ScriptStrategy
def test_script_strategy_execution():
    code = """
def on_init(ctx):
    ctx.state['position'] = 0

def on_bar(ctx, bar):
    if bar.close > 100 and ctx.position == 0:
        ctx.buy(size=100, price=bar.close)
    """
    executor = ScriptStrategyExecutor()
    result = executor.execute(code, klines, {})
    assert len(result['trades']) > 0

# 测试代码安全验证
def test_code_validator_forbidden_import():
    validator = CodeValidator()
    with pytest.raises(ValueError, match="禁止导入模块: os"):
        validator.validate("import os")

# 测试回测
def test_backtest_strategy():
    service = StrategyCodeService()
    result = service.backtest_strategy(
        strategy_id=123,
        symbol='600000',
        start_date='2025-01-01',
        end_date='2026-05-22'
    )
    assert 'total_return' in result
    assert 'sharpe_ratio' in result
```

### 10.5 风险和缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 代码沙箱被绕过 | 高 | 低 | 多层安全检查、定期安全审计 |
| 执行性能问题 | 中 | 中 | 执行超时、资源限制、性能测试 |
| 参数解析错误 | 中 | 低 | 完善的单元测试、错误处理 |
| 回测结果不准确 | 高 | 中 | 与 QuantDinger 对比验证 |
| CLI 命令参数复杂 | 低 | 中 | 详细的文档和示例 |

---

## 11. 示例代码

### 11.1 IndicatorStrategy 完整示例

```python
# ============================================================
# MACD 策略
# ============================================================

my_indicator_name = "MACD 交叉策略"
my_indicator_description = "使用 MACD 指标的金叉死叉生成交易信号"

# @param fast_period int 12 快线周期
# @param slow_period int 26 慢线周期
# @param signal_period int 9 信号线周期

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.08
# @strategy entryPct 0.3

# 获取参数
fast = params.get('fast_period', 12)
slow = params.get('slow_period', 26)
signal = params.get('signal_period', 9)

# 计算 MACD
df = df.copy()
ema_fast = df['close'].ewm(span=fast).mean()
ema_slow = df['close'].ewm(span=slow).mean()
df['macd'] = ema_fast - ema_slow
df['signal'] = df['macd'].ewm(span=signal).mean()
df['histogram'] = df['macd'] - df['signal']

# 生成信号
df['buy'] = (df['macd'] > df['signal']) & (df['macd'].shift(1) <= df['signal'].shift(1))
df['sell'] = (df['macd'] < df['signal']) & (df['macd'].shift(1) >= df['signal'].shift(1))

# 图表输出
output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": "MACD",
            "data": df['macd'].fillna(0).tolist(),
            "color": "#2196F3",
            "overlay": False
        },
        {
            "name": "Signal",
            "data": df['signal'].fillna(0).tolist(),
            "color": "#FF9800",
            "overlay": False
        }
    ]
}
```

### 11.2 ScriptStrategy 完整示例

```python
# ============================================================
# 布林带均值回归策略
# ============================================================

strategy_name = "布林带均值回归"
strategy_description = "价格触及布林带上下轨时进行反向交易"

# @param period int 20 布林带周期
# @param std_dev float 2.0 标准差倍数
# @param position_size float 0.2 仓位大小

# @strategy stopLossPct 0.05
# @strategy takeProfitPct 0.10

def on_init(ctx):
    """初始化"""
    ctx.state['period'] = ctx.params.get('period', 20)
    ctx.state['std_dev'] = ctx.params.get('std_dev', 2.0)
    ctx.state['position_size'] = ctx.params.get('position_size', 0.2)
    ctx.state['prices'] = []
    ctx.log(f"布林带策略初始化: 周期={ctx.state['period']}, 标准差={ctx.state['std_dev']}")

def on_bar(ctx, bar):
    """每根 K 线回调"""
    # 记录价格
    ctx.state['prices'].append(bar.close)
    
    # 需要足够的数据才能计算布林带
    if len(ctx.state['prices']) < ctx.state['period']:
        return
    
    # 计算布林带
    prices = ctx.state['prices'][-ctx.state['period']:]
    mean = sum(prices) / len(prices)
    variance = sum((p - mean) ** 2 for p in prices) / len(prices)
    std = variance ** 0.5
    
    upper_band = mean + ctx.state['std_dev'] * std
    lower_band = mean - ctx.state['std_dev'] * std
    
    # 交易逻辑
    if ctx.position == 0:
        # 价格触及下轨 -> 买入（预期反弹）
        if bar.close <= lower_band:
            size = ctx.cash * ctx.state['position_size'] / bar.close
            ctx.buy(size=size, price=bar.close, reason=f"触及下轨 {lower_band:.2f}")
    
    elif ctx.position > 0:
        # 价格回到中轨 -> 卖出
        if bar.close >= mean:
            ctx.sell(size=ctx.position, price=bar.close, reason=f"回归均值 {mean:.2f}")
        # 价格触及上轨 -> 卖出
        elif bar.close >= upper_band:
            ctx.sell(size=ctx.position, price=bar.close, reason=f"触及上轨 {upper_band:.2f}")
```

### 11.3 AI Agent 使用示例

```python
# AI Agent 生成策略代码
strategy_code = """
# 双均线策略
# @param ma_short int 5 短期均线
# @param ma_long int 20 长期均线

ma_short = params.get('ma_short', 5)
ma_long = params.get('ma_long', 20)

df = df.copy()
df['ma_short'] = df['close'].rolling(ma_short).mean()
df['ma_long'] = df['close'].rolling(ma_long).mean()

df['buy'] = (df['ma_short'] > df['ma_long']) & (df['ma_short'].shift(1) <= df['ma_long'].shift(1))
df['sell'] = (df['ma_short'] < df['ma_long']) & (df['ma_short'].shift(1) >= df['ma_long'].shift(1))
"""

# AI Agent 调用 CLI 创建策略
import subprocess
import json

result = subprocess.run([
    'qsv2', 'strategy', 'create',
    '--name', '双均线策略',
    '--type', 'indicator',
    '--code', strategy_code,
    '--params', json.dumps({'ma_short': 5, 'ma_long': 20})
], capture_output=True, text=True)

response = json.loads(result.stdout)
strategy_id = response['strategy_id']

# AI Agent 回测策略
result = subprocess.run([
    'qsv2', 'strategy', 'backtest',
    '--strategy-id', str(strategy_id),
    '--symbol', '600000',
    '--start', '2025-01-01',
    '--end', '2026-05-22'
], capture_output=True, text=True)

backtest_result = json.loads(result.stdout)
print(f"总收益率: {backtest_result['total_return']}")
print(f"夏普比率: {backtest_result['sharpe_ratio']}")
print(f"最大回撤: {backtest_result['max_drawdown']}")
```

---

## 12. 总结

### 12.1 核心价值

1. **灵活性**：支持两种策略模式，满足不同场景需求
2. **安全性**：多层安全检查，沙箱执行环境
3. **易用性**：简单的 CLI 接口，AI Agent 易于使用
4. **完整性**：覆盖策略完整生命周期
5. **可扩展性**：易于添加新的策略类型和功能

### 12.2 技术亮点

- **双模式策略**：IndicatorStrategy（信号驱动）+ ScriptStrategy（事件驱动）
- **代码沙箱**：安全的用户代码执行环境
- **参数解析**：通过注释声明参数和配置
- **CLI 优先**：为 AI Agent 设计的命令行接口
- **完整回测**：支持多种回测指标计算

### 12.3 后续优化方向

1. **性能优化**：
   - 策略代码编译缓存
   - 并行回测多个策略
   - 增量计算优化

2. **功能扩展**：
   - 支持多品种策略
   - 支持期货、期权策略
   - 支持组合策略

3. **安全增强**：
   - 更严格的资源限制
   - 代码审计日志
   - 异常行为检测

4. **用户体验**：
   - 策略模板库
   - 策略调试工具
   - 可视化回测报告

---

## 附录

### A. 参考资料

- QuantDinger 策略开发指南: `/Users/mac/Documents/ai/lianghua/QuantDinger/docs/STRATEGY_DEV_GUIDE.md`
- QuantDinger 回测服务: `/Users/mac/Documents/ai/lianghua/QuantDinger/backend_api_python/app/services/backtest.py`
- quantsys-v2 现有策略: `/Users/mac/Documents/ai/pi-investment/quantsys-v2/quant/engine/`

### B. 术语表

| 术语 | 说明 |
|------|------|
| IndicatorStrategy | 信号驱动策略模式，基于 DataFrame 操作 |
| ScriptStrategy | 事件驱动策略模式，基于回调函数 |
| 沙箱 | 受限的代码执行环境，禁止危险操作 |
| 回测 | 使用历史数据测试策略表现 |
| 夏普比率 | 衡量策略风险调整后收益的指标 |
| 最大回撤 | 策略权益曲线的最大跌幅 |

### C. 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-05-22 | 初始版本，完整设计文档 |
