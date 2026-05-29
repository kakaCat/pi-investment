# 策略系统统一设计文档

**日期**: 2026-05-29  
**状态**: Draft  
**作者**: AI Agent  

## 1. 背景和动机

### 1.1 当前问题

项目中存在两套功能重复的策略执行系统：

1. **`strategy_execute` 工具** - 独立工具，单股策略执行
   - 位置: `src/infrastructure/tools/strategy/execute-tool.ts`
   - 功能: 执行单个策略，返回详细风控参数
   - 特点: 不持久化到数据库

2. **`signal.generate` 命令** - quant_cli 的一个命令
   - 位置: `src/infrastructure/tools/core/quant-cli-tool.ts`
   - 功能: 批量生成交易信号
   - 特点: 持久化到数据库，支持后续仲裁流程

### 1.2 存在的问题

- **功能重复**: 两者都执行策略生成信号，造成维护负担
- **接口不一致**: 参数格式、返回结果、错误处理各不相同
- **用户困惑**: 不清楚何时使用哪个工具
- **架构不统一**: 违反 CLAUDE.md 中"量化能力统一使用 quant_cli"的原则

### 1.3 设计目标

1. **统一接口**: 合并为一个工具，提供一致的使用体验
2. **功能完整**: 支持单股分析、批量生成、完整流程三种场景
3. **向后兼容**: 平滑迁移，不破坏现有调用
4. **性能优化**: 批量执行支持并发和流式响应
5. **可追踪性**: 默认持久化，支持策略循环闭合

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────┐
│  quant_cli 工具 (TypeScript)                     │
│  - strategy.execute 命令（统一入口）              │
│  - 参数验证、格式化、错误处理                      │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  QuantV2Client (HTTP 客户端)                     │
│  - executeStrategy() - 单股执行                   │
│  - batchExecuteStrategy() - 批量执行              │
│  - pipelineExecuteStrategy() - 流程执行           │
│  - NDJSON 流式响应处理                            │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  quantsys-v2 Flask API (Python)                 │
│  - POST /api/strategies/execute                  │
│  - POST /api/strategies/batch-execute            │
│  - POST /api/strategies/pipeline-execute         │
│  - 策略执行、信号生成、数据库持久化                │
└─────────────────────────────────────────────────┘
```

### 2.2 工具分工

- **`quant_cli` 的 `strategy.execute`** - 手动/交互式策略执行
- **`signal_execution` 工具** - 自动化定时任务触发（保持不变）

### 2.3 设计原则

1. **Action 驱动**: 通过 action 参数明确操作意图
2. **默认持久化**: 所有信号默认写入数据库（可选关闭）
3. **流式响应**: 批量模式使用 NDJSON 流式返回
4. **错误隔离**: 批量执行时单个失败不影响其他股票
5. **类型安全**: 完整的 TypeScript 类型定义

## 3. 接口设计

### 3.1 命令接口

**命令名称**: `strategy.execute`（重命名自 `signal.generate`）

**通用参数**:
- `action` (required): "single" | "batch" | "pipeline"
- `strategy` (required): 策略名称（字符串）
- `date` (optional): 执行日期 (YYYY-MM-DD)，默认最新
- `persist` (optional): 是否持久化，默认 true

### 3.2 模式 1: 单股快速分析

**用途**: 获取单只股票的策略判断和完整风控参数

**参数**:
```typescript
{
  action: "single",
  symbol: "600519.SH",           // 股票代码
  strategy: "Turtle",             // 策略名称
  date: "2026-05-29",            // 可选
  persist: true,                  // 默认 true
  return_details: true            // 返回完整技术指标
}
```

**返回内容**:
- 交易信号（BUY/SELL/HOLD）
- 置信度
- 止损价格、目标价格
- 仓位建议
- 技术指标详情
- 信号 ID（如果 persist=true）

**使用场景**:
- 快速分析单只股票
- 获取详细的风控建议
- 策略参数调优

### 3.3 模式 2: 批量信号生成

**用途**: 对股票列表批量执行策略，生成交易信号

**参数**:
```typescript
{
  action: "batch",
  symbols: ["600519.SH", "000001.SZ", ...],  // 股票列表
  strategy: "Turtle",                         // 策略名称
  date: "2026-05-29",                        // 可选
  persist: true,                              // 默认 true
  min_confidence: 0.6                         // 可选：过滤低置信度
}
```

**返回内容**:
- 每只股票的信号摘要（symbol, signal, confidence）
- 统计信息（总数、BUY/SELL/HOLD 分布）
- 信号 ID 列表
- 失败记录（如果有）

**使用场景**:
- 每日信号扫描
- 策略回测
- 批量筛选

### 3.4 模式 3: 完整自动化流程

**用途**: 策略执行 → 信号生成 → 风控检查 → 订单创建

**参数**:
```typescript
{
  action: "pipeline",
  symbols: ["600519.SH", "000001.SZ", ...],  // 股票列表
  strategy: "Turtle",                         // 策略名称
  create_orders: true,                        // 自动创建订单
  risk_check: true                            // 风控检查（默认 true）
}
```

**返回内容**:
- 信号统计（生成/通过/拒绝）
- 风控拒绝原因分布
- 创建的订单列表
- 执行耗时

**使用场景**:
- 自动化交易
- 定时任务触发
- 策略实盘运行

## 4. 数据流设计

### 4.1 数据库表结构

使用现有表结构：

```sql
-- 信号记录表
signal_test_log (
  id SERIAL PRIMARY KEY,
  symbol VARCHAR(20),
  strategy_id INTEGER,
  signal_type VARCHAR(10),      -- BUY/SELL/HOLD
  confidence DECIMAL(5,4),
  entry_price DECIMAL(10,2),
  stop_loss DECIMAL(10,2),
  target_price DECIMAL(10,2),
  status VARCHAR(20),            -- pending/executed/cancelled
  created_at TIMESTAMP,
  signal_id VARCHAR(100) UNIQUE  -- 全局唯一标识符
)

-- 策略性能表
strategy_performance (
  id SERIAL PRIMARY KEY,
  strategy_id INTEGER,
  symbol VARCHAR(20),
  signal_id VARCHAR(100),        -- 关联 signal_test_log
  entry_price DECIMAL(10,2),
  exit_price DECIMAL(10,2),
  pnl_pct DECIMAL(10,4),
  holding_days INTEGER,
  source VARCHAR(20)             -- 'paper'/'live'
)
```

### 4.2 持久化策略

**默认持久化** (persist=true):
- 所有信号写入 `signal_test_log` 表
- status='pending'
- 生成唯一 signal_id（格式: `sig_{date}_{symbol}_{strategy}_{uuid}`）

**可选不持久化** (persist=false):
- 仅返回结果，不写数据库
- 适用场景：快速试验、参数调优

### 4.3 信号追踪链路

```
策略执行 → signal_test_log (pending)
    ↓
创建订单 (关联 signal_id)
    ↓
订单成交 → 更新 entry_price/exit_price
    ↓
计算盈亏 → strategy_performance 表
    ↓
经验积累 → ExperienceAccumulator
```

### 4.4 数据一致性

- 使用数据库事务确保信号和订单原子性创建
- signal_id 作为全局唯一标识符
- 失败时自动回滚
- 乐观锁避免并发冲突

## 5. 后端 API 设计

### 5.1 单股策略执行

**端点**: `POST /api/strategies/execute`

**请求体**:
```json
{
  "symbol": "600519.SH",
  "strategy_name": "Turtle",
  "date": "2026-05-29",
  "persist": true,
  "return_details": true
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "signal_id": "sig_20260529_600519_turtle_abc123",
    "symbol": "600519.SH",
    "signal_type": "BUY",
    "confidence": 0.85,
    "entry_price": 1850.0,
    "stop_loss": 1750.0,
    "target_price": 2050.0,
    "position_size": 0.08,
    "indicators": {
      "atr": 45.2,
      "rsi": 62.3,
      "macd": {"value": 12.5, "signal": 10.2}
    }
  }
}
```

### 5.2 批量策略执行

**端点**: `POST /api/strategies/batch-execute`

**请求体**:
```json
{
  "symbols": ["600519.SH", "000001.SZ"],
  "strategy_name": "Turtle",
  "date": "2026-05-29",
  "persist": true,
  "min_confidence": 0.6
}
```

**响应** (NDJSON 流式):
```
{"type": "signal", "data": {"symbol": "600519.SH", "signal_type": "BUY", "confidence": 0.85, ...}}
{"type": "signal", "data": {"symbol": "000001.SZ", "signal_type": "HOLD", "confidence": 0.55, ...}}
{"type": "error", "data": {"symbol": "600000.SH", "error": "数据不足"}}
{"type": "summary", "data": {"total": 3, "success": 2, "failed": 1, "buy": 1, "sell": 0, "hold": 1}}
```

### 5.3 完整流程执行

**端点**: `POST /api/strategies/pipeline-execute`

**请求体**:
```json
{
  "symbols": ["600519.SH", "000001.SZ"],
  "strategy_name": "Turtle",
  "create_orders": true,
  "risk_check": true
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "execution_date": "2026-05-29",
    "duration_ms": 5800,
    "signals_generated": 48,
    "signals_approved": 35,
    "signals_rejected": 13,
    "orders_created": 35,
    "rejection_reasons": {
      "position_limit": 8,
      "daily_trade_limit": 3,
      "stop_loss_insufficient": 2
    },
    "orders": [
      {"order_id": "ORD001", "symbol": "600519.SH", "side": "BUY", "quantity": 100, "price": 1850.0}
    ]
  }
}
```

### 5.4 API 实现位置

- **路由定义**: `quantsys-v2/api/routes/strategies.py`
- **业务逻辑**: `quantsys-v2/services/strategy_execution_service.py`
- **复用组件**:
  - `StrategyEngine` - 策略执行引擎
  - `RiskManager` - 风控检查
  - `OrderService` - 订单创建
  - `SignalTestLogRepository` - 信号持久化

## 6. 前端实现

### 6.1 QuantV2Client 增强

**新增方法**:

```typescript
// src/infrastructure/quant/quant-v2-client.ts

export async function executeStrategy(
  params: StrategyExecuteParams
): Promise<StrategySignal> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  if (!response.ok) {
    throw new QuantV2Error(`Strategy execution failed: ${response.statusText}`);
  }
  
  const result = await response.json();
  return result.data;
}

export async function batchExecuteStrategy(
  params: StrategyBatchExecuteParams
): Promise<{ signals: StrategySignal[], summary: any, errors: any[] }> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/batch-execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  if (!response.ok) {
    throw new QuantV2Error(`Batch execution failed: ${response.statusText}`);
  }
  
  // 解析 NDJSON 流式响应
  const text = await response.text();
  const lines = text.trim().split('\n').filter(line => line.trim());
  
  const signals: StrategySignal[] = [];
  const errors: any[] = [];
  let summary: any = null;
  
  for (const line of lines) {
    const obj = JSON.parse(line);
    if (obj.type === 'signal') {
      signals.push(obj.data);
    } else if (obj.type === 'error') {
      errors.push(obj.data);
    } else if (obj.type === 'summary') {
      summary = obj.data;
    }
  }
  
  return { signals, summary, errors };
}

export async function pipelineExecuteStrategy(
  params: StrategyPipelineExecuteParams
): Promise<PipelineExecutionResult> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/pipeline-execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  if (!response.ok) {
    throw new QuantV2Error(`Pipeline execution failed: ${response.statusText}`);
  }
  
  const result = await response.json();
  return result.data;
}
```

### 6.2 类型定义

```typescript
// src/infrastructure/quant/types.ts

export interface StrategyExecuteParams {
  symbol: string;
  strategy_name: string;
  date?: string;
  persist?: boolean;
  return_details?: boolean;
}

export interface StrategyBatchExecuteParams {
  symbols: string[];
  strategy_name: string;
  date?: string;
  persist?: boolean;
  min_confidence?: number;
}

export interface StrategyPipelineExecuteParams {
  symbols: string[];
  strategy_name: string;
  create_orders?: boolean;
  risk_check?: boolean;
}

export interface StrategySignal {
  signal_id?: string;
  symbol: string;
  signal_type: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  entry_price: number;
  stop_loss?: number;
  target_price?: number;
  position_size?: number;
  indicators?: Record<string, any>;
}

export interface PipelineExecutionResult {
  execution_date: string;
  duration_ms: number;
  signals_generated: number;
  signals_approved: number;
  signals_rejected: number;
  orders_created: number;
  rejection_reasons: Record<string, number>;
  orders: Array<{
    order_id: string;
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price: number;
  }>;
}
```

### 6.3 quant_cli 工具重构

**命令路由增强**:

```typescript
// src/infrastructure/tools/core/quant-cli-tool.ts

const COMMANDS: Record<string, CommandRule> = {
  // ... 其他命令
  
  "strategy.execute": {
    domain: "strategy",
    action: "execute",
    description: 
      "统一策略执行工具，支持三种模式：\n" +
      "- action='single': 单股快速分析，返回详细风控参数\n" +
      "- action='batch': 批量信号生成，流式返回结果\n" +
      "- action='pipeline': 完整自动化流程（策略→信号→风控→订单）\n" +
      "默认持久化到数据库（persist=true），支持策略循环闭合。",
    params: {
      action: { 
        required: true, 
        type: "string", 
        enum: ["single", "batch", "pipeline"] 
      },
      symbol: { type: "string", symbol: true },
      symbols: { type: "array" },
      strategy: { required: true, type: "string" },
      date: { type: "string" },
      persist: { type: "boolean" },
      return_details: { type: "boolean" },
      min_confidence: { type: "number", min: 0, max: 1 },
      create_orders: { type: "boolean" },
      risk_check: { type: "boolean" }
    },
    example: {
      action: "single",
      symbol: "600519.SH",
      strategy: "Turtle"
    }
  },
  
  // 保留别名（兼容层）
  "signal.generate": {
    domain: "signal",
    action: "generate",
    description: "⚠️ 已重命名为 strategy.execute，请更新调用。",
    params: { /* 映射到 strategy.execute */ },
    example: {}
  }
};
```

**执行逻辑**:

```typescript
// 在 execute 函数中处理 strategy.execute
if (command === "strategy.execute") {
  const { action, symbol, symbols, strategy, ...rest } = params;
  
  // 参数验证
  if (action === "single" && !symbol) {
    return error("action='single' 需要 symbol 参数");
  }
  if ((action === "batch" || action === "pipeline") && !symbols) {
    return error(`action='${action}' 需要 symbols 参数`);
  }
  
  // 调用对应的客户端方法
  if (action === "single") {
    const result = await executeStrategy({
      symbol,
      strategy_name: strategy,
      ...rest
    });
    return formatSingleSignal(result);
  } else if (action === "batch") {
    const result = await batchExecuteStrategy({
      symbols,
      strategy_name: strategy,
      ...rest
    });
    return formatBatchSignals(result);
  } else if (action === "pipeline") {
    const result = await pipelineExecuteStrategy({
      symbols,
      strategy_name: strategy,
      ...rest
    });
    return formatPipelineResult(result);
  }
}

// 兼容层：signal.generate → strategy.execute
if (command === "signal.generate") {
  console.warn("⚠️ signal.generate 已重命名为 strategy.execute，请更新调用");
  
  // 参数转换
  const convertedParams = {
    action: params.symbols ? "batch" : "single",
    symbol: params.symbol,
    symbols: params.symbols,
    strategy: params.strategy_name || await resolveStrategyName(params.strategy_id),
    persist: true,
    ...params
  };
  
  // 递归调用新命令
  return execute(toolCallId, {
    command: "strategy.execute",
    params: convertedParams
  });
}
```

## 7. 输出格式化

### 7.1 单股模式输出

```markdown
## 📊 策略执行结果

**股票**: 贵州茅台 (600519.SH)
**策略**: Turtle (海龟交易)
**日期**: 2026-05-29
**信号ID**: sig_20260529_600519_turtle_abc123

### 交易信号
- **方向**: 🟢 BUY
- **置信度**: 85%
- **当前价格**: ¥1,850.00

### 风险管理
- **止损价格**: ¥1,750.00 (-5.4%)
- **目标价格**: ¥2,050.00 (+10.8%)
- **建议仓位**: 8% (风险调整后)
- **最大亏损**: ¥10,000

### 技术指标
- ATR(14): 45.2
- RSI(14): 62.3
- MACD: 金叉 (3天前)
- 布林带: 中轨附近
```

### 7.2 批量模式输出

```markdown
## 📊 批量策略执行完成

**策略**: Turtle
**执行时间**: 2026-05-29 14:30:25
**耗时**: 2.3秒

### 统计摘要
- 总股票数: 50
- 成功: 48
- 失败: 2
- BUY 信号: 12 (25%)
- SELL 信号: 5 (10%)
- HOLD 信号: 31 (65%)

### BUY 信号列表
| 股票 | 名称 | 置信度 | 当前价 | 止损价 |
|------|------|--------|--------|--------|
| 600519.SH | 贵州茅台 | 85% | 1850.00 | 1750.00 |
| 000001.SZ | 平安银行 | 78% | 12.50 | 11.80 |

### 失败记录
- 600000.SH: 数据不足（K线少于20根）
- 000002.SZ: 停牌中
```

### 7.3 流程模式输出

```markdown
## ✅ 自动化流程执行完成

**执行日期**: 2026-05-29
**策略**: Turtle
**耗时**: 5.8秒

### 📊 执行统计
| 阶段 | 数量 |
|------|------|
| 生成信号 | 48 |
| 风控通过 | 35 |
| 风控拒绝 | 13 |
| 创建订单 | 35 |

### 🛡️ 风控拒绝原因
- 仓位超限: 8 只
- 单日交易次数超限: 3 只
- 止损幅度不足: 2 只

### 📝 已创建订单
| 订单ID | 股票 | 方向 | 数量 | 价格 |
|--------|------|------|------|------|
| ORD001 | 600519.SH | BUY | 100 | 1850.00 |
```

## 8. 错误处理

### 8.1 参数验证

**必需参数检查**:
- action: 必须是 "single" | "batch" | "pipeline"
- symbol/symbols: 根据 action 验证
- strategy: 必须是有效的策略名称

**参数冲突检查**:
- action="single" 时不允许 symbols 数组
- action="batch" 时不允许 return_details=true（性能考虑）
- action="pipeline" 时必须 persist=true

**策略名称验证**:
- 调用 `/api/strategies/list` 获取可用策略
- 策略不存在时返回友好错误 + 可用策略列表

### 8.2 错误处理策略

```typescript
// 1. 网络错误
if (fetch 失败) {
  return "❌ 无法连接到 quantsys-v2 服务 (127.0.0.1:5001)\n" +
         "请检查服务是否启动：cd quantsys-v2 && python start_all.py"
}

// 2. 策略执行失败
if (单只股票失败 && action="batch") {
  // 继续执行其他股票，最后汇总错误
  errors.push({ symbol, error })
}

// 3. 数据库写入失败
if (persist=true && 写入失败) {
  return "⚠️ 信号生成成功但持久化失败\n" +
         "原因：{error}\n" +
         "建议：检查数据库连接"
}

// 4. 风控拒绝（action="pipeline"）
if (风控拒绝) {
  return "🛑 风控拒绝：{reason}\n" +
         "信号已记录但未创建订单"
}
```

### 8.3 边界情况

- **空股票列表** → 返回友好提示
- **重复股票代码** → 自动去重
- **无效股票代码** → 跳过并记录警告
- **非交易日执行** → 使用最近交易日数据 + 提示
- **批量执行超时** → 返回已完成部分 + 超时提示

## 9. 性能优化

### 9.1 批量执行优化

**并发控制**:
```python
# quantsys-v2/services/strategy_execution_service.py
from concurrent.futures import ThreadPoolExecutor

def batch_execute_strategies(symbols, strategy_name, **kwargs):
    max_workers = min(10, len(symbols))  # 最多10个并发
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(execute_single, sym, strategy_name): sym 
            for sym in symbols
        }
        
        for future in as_completed(futures):
            yield format_ndjson_signal(future.result())
```

**数据预加载**:
- 批量查询 K线数据（避免 N+1 查询）
- 缓存策略参数（避免重复加载）
- 复用技术指标计算结果

**流式响应**:
- 使用 NDJSON 格式逐条返回信号
- 前端可以实时显示进度
- 避免大批量时的内存峰值

### 9.2 缓存策略

```python
# 策略定义缓存（1小时）
@lru_cache(maxsize=128)
def get_strategy_class(strategy_name: str):
    return StrategyRegistry.get(strategy_name)

# K线数据缓存（5分钟）
@cache_with_ttl(ttl=300)
def get_kline_data(symbol: str, period: str, limit: int):
    return kline_repo.get_latest(symbol, period, limit)
```

### 9.3 性能指标

| 场景 | 目标性能 |
|------|---------|
| 单股执行 | < 500ms |
| 批量10只 | < 2s |
| 批量50只 | < 8s |
| 批量100只 | < 15s |

### 9.4 监控指标

```python
# 添加性能监控
@monitor_execution_time
def execute_strategy(symbol, strategy_name):
    start = time.time()
    result = _do_execute(symbol, strategy_name)
    duration = time.time() - start
    
    metrics.record("strategy_execution_duration", duration, {
        "strategy": strategy_name,
        "action": "single"
    })
    
    return result
```

## 10. 测试策略

### 10.1 单元测试

```typescript
// quant-cli-tool.test.ts
describe("strategy.execute command", () => {
  describe("action: single", () => {
    test("执行单股策略并返回详细信号", async () => {
      const result = await quantCliTool.execute("test", {
        command: "strategy.execute",
        params: {
          action: "single",
          symbol: "600519.SH",
          strategy: "Turtle",
          persist: true
        }
      });
      
      expect(result.content[0].text).toContain("交易信号");
      expect(result.content[0].text).toContain("风险管理");
      expect(result.content[0].text).toContain("信号ID");
    });

    test("persist=false 时不写入数据库", async () => {
      // 验证未调用数据库写入
    });

    test("策略不存在时返回可用策略列表", async () => {
      // 验证错误消息包含策略列表
    });
  });

  describe("action: batch", () => {
    test("批量执行并返回统计摘要", async () => {
      // 验证 NDJSON 流式响应解析
    });

    test("部分股票失败时继续执行其他股票", async () => {
      // 验证错误隔离
    });
  });

  describe("action: pipeline", () => {
    test("完整流程：信号→风控→订单", async () => {
      // 验证订单创建
    });

    test("风控拒绝时不创建订单", async () => {
      // 验证风控逻辑
    });
  });

  describe("backward compatibility", () => {
    test("signal.generate 自动映射到 strategy.execute", async () => {
      // 验证兼容层
    });
  });
});
```

### 10.2 集成测试

```python
# quantsys-v2/tests/api/test_strategy_execution.py
def test_single_execute_with_persist():
    """测试单股执行 + 数据库持久化"""
    response = client.post("/api/strategies/execute", json={
        "symbol": "600519.SH",
        "strategy_name": "Turtle",
        "persist": True
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert "signal_id" in data
    
    # 验证数据库记录
    signal = db.query(SignalTestLog).filter_by(
        signal_id=data["signal_id"]
    ).first()
    assert signal is not None
    assert signal.status == "pending"

def test_batch_execute_ndjson_stream():
    """测试批量执行的流式响应"""
    # 验证 NDJSON 格式
    
def test_pipeline_execute_with_risk_check():
    """测试完整流程的风控检查"""
    # 验证风控拒绝逻辑
```

### 10.3 测试覆盖目标

- 单元测试覆盖率 > 85%
- 集成测试覆盖所有 action 模式
- 端到端测试验证完整用户流程

## 11. 迁移计划

### 11.1 废弃的工具/命令

1. **`strategy_execute` 工具** → 废弃
   - 位置: `src/infrastructure/tools/strategy/execute-tool.ts`
   - 替代方案: `quant_cli({ command: "strategy.execute", params: { action: "single", ... } })`
   - 迁移路径: 自动映射（见兼容层）

2. **`signal.generate` 命令** → 重命名为 `strategy.execute`
   - 保留 `signal.generate` 作为别名（3个月过渡期）
   - 显示废弃警告: "⚠️ signal.generate 已重命名为 strategy.execute，请更新调用"

### 11.2 向后兼容策略

```typescript
// quant-cli-tool.ts 中添加兼容层
if (command === "signal.generate") {
  console.warn("⚠️ signal.generate 已重命名为 strategy.execute");
  command = "strategy.execute";
  
  // 自动转换旧参数格式
  if (params.strategy_id && !params.strategy) {
    params.strategy = await resolveStrategyName(params.strategy_id);
  }
  params.action = params.action || "batch";
}
```

### 11.3 迁移检查清单

- [ ] 更新 CLAUDE.md 文档（移除 strategy_execute，更新 quant_cli 说明）
- [ ] 更新工具注册表（从 index.ts 移除 strategyExecuteTool）
- [ ] 搜索代码库中的 `strategy_execute` 调用并替换
- [ ] 添加集成测试覆盖三种 action 模式
- [ ] 更新 Agent 系统提示词（工具列表）

### 11.4 过渡期时间表

| 阶段 | 时间 | 任务 |
|------|------|------|
| Phase 1: 核心功能实现 | Week 1-2 | 后端 API + 前端客户端 + quant_cli 重构 |
| Phase 2: 兼容性和迁移 | Week 3 | 兼容层 + 废弃旧工具 + 迁移指南 |
| Phase 3: 测试和优化 | Week 4 | 集成测试 + 性能优化 + 文档更新 |
| Phase 4: Beta 发布 | Week 5 | 内部测试 + 收集反馈 |
| Phase 5: 正式发布 | Week 6 | 发布公告 + 监控错误率 |
| Phase 6: 过渡期维护 | Week 7-12 | 监控兼容层使用 + 协助迁移 |
| Phase 7: 清理 | Week 13+ | 移除兼容层 + 删除旧代码 |

## 12. 风险评估

### 12.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| NDJSON 流式响应解析失败 | 高 | 中 | 添加完善的错误处理和降级方案（回退到普通 JSON） |
| 批量执行性能不达标 | 中 | 低 | 提前进行性能测试，优化并发策略 |
| 数据库事务死锁 | 高 | 低 | 使用乐观锁，添加重试机制 |
| 旧工具调用未完全迁移 | 中 | 中 | 保留兼容层3个月，添加使用监控 |

### 12.2 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 信号持久化导致数据库膨胀 | 中 | 高 | 添加数据清理策略（保留90天） |
| 自动创建订单的风控漏洞 | 高 | 低 | 多层风控检查，添加人工审核开关 |
| 策略执行结果不一致 | 高 | 低 | 添加结果校验，记录执行日志 |

### 12.3 回滚计划

```bash
# 如果新系统出现严重问题，可以快速回滚

# 1. 恢复旧工具注册
git revert <commit-hash>  # 恢复 tools/index.ts

# 2. 禁用新 API 端点
# 在 quantsys-v2/api/routes/strategies.py 中注释掉新路由

# 3. 切换到兼容模式
# 设置环境变量 USE_LEGACY_STRATEGY_EXECUTE=true

# 4. 通知用户
echo "⚠️ 策略系统已回滚到旧版本，请使用 strategy_execute 工具"
```

### 12.4 监控指标

```python
# 关键指标监控
metrics = {
    "strategy_execute_calls": Counter,           # 调用次数
    "strategy_execute_duration": Histogram,      # 执行耗时
    "strategy_execute_errors": Counter,          # 错误次数
    "signal_persist_success_rate": Gauge,        # 持久化成功率
    "batch_execute_concurrency": Gauge,          # 并发数
    "pipeline_order_creation_rate": Gauge        # 订单创建率
}

# 告警规则
alerts = {
    "error_rate > 5%": "策略执行错误率过高",
    "p99_latency > 10s": "批量执行延迟过高",
    "persist_failure > 1%": "数据库持久化失败",
}
```

## 13. 实现优先级

### 13.1 Phase 1: 核心功能实现（Week 1-2）

**后端 API 实现**:
- [ ] `/api/strategies/execute` - 单股执行
- [ ] `/api/strategies/batch-execute` - 批量执行（NDJSON 流式）
- [ ] `/api/strategies/pipeline-execute` - 完整流程
- [ ] 数据库持久化逻辑
- [ ] 单元测试（覆盖率 > 85%）

**TypeScript 客户端增强**:
- [ ] `QuantV2Client.executeStrategy()` - 单股调用
- [ ] `QuantV2Client.batchExecuteStrategy()` - 批量调用（流式解析）
- [ ] `QuantV2Client.pipelineExecuteStrategy()` - 流程调用
- [ ] 类型定义更新

**quant_cli 工具重构**:
- [ ] 重命名 `signal.generate` → `strategy.execute`
- [ ] 添加 action 参数支持（single/batch/pipeline）
- [ ] 参数验证和错误处理
- [ ] 输出格式化（三种模式）

### 13.2 Phase 2: 兼容性和迁移（Week 3）

**向后兼容层**:
- [ ] `signal.generate` 别名 + 废弃警告
- [ ] 参数自动转换（strategy_id → strategy_name）
- [ ] 兼容性测试

**废弃旧工具**:
- [ ] 从 `tools/index.ts` 移除 `strategyExecuteTool`
- [ ] 添加迁移指南注释
- [ ] 搜索并更新代码库中的调用

### 13.3 Phase 3: 测试和优化（Week 4）

**集成测试**:
- [ ] 端到端测试脚本
- [ ] 性能基准测试
- [ ] 并发压力测试

**性能优化**:
- [ ] 批量执行并发控制
- [ ] 数据预加载和缓存
- [ ] 监控指标埋点

**文档更新**:
- [ ] CLAUDE.md 更新
- [ ] API 文档
- [ ] 迁移指南

### 13.4 关键里程碑

| 里程碑 | 时间 | 交付物 |
|--------|------|--------|
| M1: 核心功能完成 | Week 2 | 三种 action 模式可用 |
| M2: 兼容层就绪 | Week 3 | 旧工具可平滑迁移 |
| M3: Beta 发布 | Week 5 | 内部测试通过 |
| M4: 正式发布 | Week 6 | 生产环境可用 |
| M5: 完全迁移 | Week 13 | 移除所有旧代码 |

## 14. 文档更新

### 14.1 CLAUDE.md 更新

```markdown
## Agent 工具系统

### 六层量化投资架构

#### L3.5 策略执行层

**统一策略执行工具**: `quant_cli` 的 `strategy.execute` 命令

支持三种执行模式：

1. **单股快速分析**（action: "single"）
   - 获取单只股票的策略判断和完整风控参数
   - 返回：信号、置信度、止损价、目标价、仓位建议、技术指标
   - 默认持久化到数据库（可选 persist: false）

2. **批量信号生成**（action: "batch"）
   - 对股票列表批量执行策略
   - 流式返回结果（NDJSON 格式）
   - 适用场景：每日信号扫描、策略回测

3. **完整自动化流程**（action: "pipeline"）
   - 策略执行 → 信号生成 → 风控检查 → 订单创建
   - 自动化交易流程
   - 适用场景：定时任务、自动交易

**使用示例**:

```typescript
// 单股分析
quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600519.SH",
    strategy: "Turtle"
  }
})

// 批量生成
quant_cli({
  command: "strategy.execute",
  params: {
    action: "batch",
    symbols: ["600519.SH", "000001.SZ"],
    strategy: "Turtle",
    min_confidence: 0.6
  }
})

// 完整流程
quant_cli({
  command: "strategy.execute",
  params: {
    action: "pipeline",
    symbols: ["600519.SH"],
    strategy: "Turtle",
    create_orders: true
  }
})
```

**已废弃**:
- ~~`strategy_execute` 工具~~ → 使用 `strategy.execute` (action: "single")
- ~~`signal.generate` 命令~~ → 已重命名为 `strategy.execute`
```

### 14.2 迁移指南

**从 `strategy_execute` 迁移**:

```typescript
// 旧代码
strategy_execute({
  symbol: "600519.SH",
  strategy: "Turtle"
})

// 新代码
quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600519.SH",
    strategy: "Turtle"
  }
})
```

**从 `signal.generate` 迁移**:

```typescript
// 旧代码
quant_cli({
  command: "signal.generate",
  params: {
    strategy_id: 53,
    symbols: ["600519.SH"]
  }
})

// 新代码
quant_cli({
  command: "strategy.execute",
  params: {
    action: "batch",
    symbols: ["600519.SH"],
    strategy: "Turtle"  // 使用策略名称而非 ID
  }
})
```

## 15. 总结

### 15.1 设计决策

1. **整合到 quant_cli** - 符合"量化能力统一入口"的架构原则
2. **Action 驱动接口** - 清晰的意图表达，易于扩展
3. **默认持久化** - 支持策略循环闭合，可追踪信号表现
4. **流式响应** - 批量执行实时反馈，避免内存峰值
5. **向后兼容** - 3个月过渡期，平滑迁移

### 15.2 核心优势

- **统一体验**: 一个工具支持所有策略执行场景
- **完整闭环**: 信号 → 订单 → 盈亏 → 经验积累
- **高性能**: 并发执行 + 流式响应 + 数据缓存
- **易维护**: 减少工具数量，降低维护成本
- **可扩展**: Action 模式易于添加新场景

### 15.3 关键指标

| 指标 | 目标值 |
|------|--------|
| 单股执行延迟 | < 500ms |
| 批量50只延迟 | < 8s |
| 测试覆盖率 | > 85% |
| 错误率 | < 1% |
| 迁移完成时间 | 13周 |

### 15.4 后续工作

1. **Phase 1-3**: 核心开发和测试（4周）
2. **Phase 4-5**: Beta 和正式发布（2周）
3. **Phase 6**: 过渡期维护（6周）
4. **Phase 7**: 清理旧代码（1周+）

---

**文档版本**: v1.0  
**最后更新**: 2026-05-29  
**审核状态**: 待审核
