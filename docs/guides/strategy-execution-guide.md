# 策略执行使用指南

## 概述

策略执行系统提供三种模式，覆盖从单股分析到完整自动化的所有场景。统一通过 `quant_cli` 工具的 `strategy.execute` 命令调用。

### 三种执行模式

| 模式 | 用途 | 输入 | 输出 | 适用场景 |
|------|------|------|------|----------|
| **single** | 单股快速分析 | 单个股票代码 | 详细信号 + 风控参数 | 人工决策、深度分析 |
| **batch** | 批量信号生成 | 股票代码数组 | 信号列表 + 统计摘要 | 选股筛选、机会扫描 |
| **pipeline** | 完整自动化流程 | 股票代码数组 | 执行统计 + 订单列表 | 日终批处理、自动交易 |

### 核心特性

- **默认持久化**: 所有信号自动记录到 `signal_test_log` 表，支持完整追踪链路
- **错误隔离**: 单个股票失败不影响其他股票执行
- **流式响应**: batch/pipeline 模式使用 NDJSON 流式返回，实时反馈进度
- **风控集成**: pipeline 模式内置风控检查，自动过滤高风险信号

---

## 使用场景

### 场景 1: 快速分析单只股票

**需求**: 分析某只股票是否有交易机会，获取详细的风控参数。

**方案**: 使用 `action='single'`

```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600519.SH",
    strategy: "Turtle",
    persist: true,
    return_details: true
  }
})
```

**输出**:
```json
{
  "symbol": "600519.SH",
  "strategy": "Turtle",
  "signal_type": "BUY",
  "confidence": 0.85,
  "entry_price": 1850.0,
  "stop_loss": 1800.0,
  "target_price": 1950.0,
  "position_size": 0.15,
  "indicators": {
    "atr": 25.5,
    "ma20": 1820.0,
    "ma50": 1780.0,
    "upper_band": 1900.0,
    "lower_band": 1750.0
  },
  "timestamp": "2026-05-30T10:30:00"
}
```

**关键字段说明**:
- `signal_type`: 交易信号（BUY/SELL/HOLD）
- `confidence`: 置信度（0-1），建议 ≥ 0.7 才执行
- `entry_price`: 建议入场价格
- `stop_loss`: 止损价格
- `target_price`: 目标价格
- `position_size`: 建议仓位（占总资金比例）
- `indicators`: 技术指标详情（用于人工复核）

**适用场景**:
- 用户询问"茅台现在能买吗？"
- 需要详细的技术指标和风控参数
- 人工决策前的量化参考

---

### 场景 2: 批量筛选交易机会

**需求**: 从股票池中筛选出高置信度的交易信号。

**方案**: 使用 `action='batch'`

```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "batch",
    symbols: ["600519.SH", "000001.SZ", "000002.SZ", "600000.SH"],
    strategy: "Turtle",
    min_confidence: 0.7,
    persist: true
  }
})
```

**输出** (NDJSON 流式):
```json
{"type": "signal", "data": {"symbol": "600519.SH", "signal_type": "BUY", "confidence": 0.85}}
{"type": "signal", "data": {"symbol": "000001.SZ", "signal_type": "HOLD", "confidence": 0.72}}
{"type": "error", "data": {"symbol": "000002.SZ", "error": "Insufficient data"}}
{"type": "summary", "data": {"total": 4, "success": 3, "failed": 1, "buy": 1, "sell": 0, "hold": 2, "duration_ms": 1250}}
```

**关键参数**:
- `min_confidence`: 最低置信度过滤（推荐 0.6-0.8）
  - 0.6: 宽松筛选，更多候选
  - 0.7: 平衡筛选（推荐）
  - 0.8: 严格筛选，高质量信号

**适用场景**:
- 每日盘前/盘后扫描全市场
- 从自选股池筛选交易机会
- 多策略信号对比

**性能**:
- 并发度: 10 workers
- 建议批次大小: 50-100 只股票
- 100 只股票约 2-5 秒

---

### 场景 3: 完全自动化交易

**需求**: 每日自动执行策略、风控检查、创建订单。

**方案**: 使用 `action='pipeline'`

```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "pipeline",
    symbols: stockPool, // 从数据库加载
    strategy: "Turtle",
    create_orders: true,
    risk_check: true
  }
})
```

**输出**:
```json
{
  "signals_generated": 50,
  "signals_passed": 12,
  "signals_rejected": 38,
  "orders_created": 12,
  "rejection_reasons": {
    "position_limit": 15,
    "concentration_risk": 10,
    "volatility_too_high": 8,
    "insufficient_liquidity": 5
  },
  "duration_ms": 8500
}
```

**执行流程**:
```
1. 批量生成信号 (50 只股票)
   ↓
2. 风控检查 (RiskManager)
   - 仓位限制
   - 行业集中度
   - 波动率检查
   - 流动性检查
   ↓
3. 创建订单 (12 只通过)
   - 自动计算数量
   - 关联 signal_id
   - 记录到 orders 表
   ↓
4. 返回统计摘要
```

**关键参数**:
- `create_orders`: 是否创建订单
  - `false`: 仅生成信号（测试模式）
  - `true`: 创建订单（生产模式）
- `risk_check`: 是否风控检查（默认 true）
  - 建议始终开启

**适用场景**:
- 日终批处理（盘后执行）
- 定时任务（cron job）
- 完全自动化交易系统

**安全建议**:
1. 先在测试环境运行（`create_orders: false`）
2. 验证信号质量和风控逻辑
3. 小规模上线（10-20 只股票）
4. 逐步扩大规模

---

## 最佳实践

### 1. 默认持久化

所有模式默认 `persist=true`，确保信号追踪链路完整：

```
signal_test_log → orders → strategy_performance
```

**好处**:
- 完整的信号历史记录
- 支持策略回测和优化
- 自动生成经验数据

**何时关闭持久化**:
- 临时测试（不想污染数据库）
- 高频探索（避免大量无效记录）

```typescript
// 临时测试，不持久化
params: {
  action: "single",
  symbol: "600519.SH",
  strategy: "Turtle",
  persist: false
}
```

### 2. 批量模式使用置信度过滤

```typescript
// 只关注高置信度信号
params: {
  action: "batch",
  symbols: stockPool,
  strategy: "Turtle",
  min_confidence: 0.7  // 过滤低置信度
}
```

**置信度阈值建议**:
- **0.6**: 宽松筛选，适合探索阶段
- **0.7**: 平衡筛选，日常使用（推荐）
- **0.8**: 严格筛选，保守策略

### 3. Pipeline 模式先测试后上线

```typescript
// 阶段 1: 测试模式（不创建订单）
params: {
  action: "pipeline",
  symbols: testPool,
  strategy: "Turtle",
  create_orders: false,  // 仅生成信号
  risk_check: true
}

// 阶段 2: 小规模上线（10-20 只股票）
params: {
  action: "pipeline",
  symbols: smallPool,
  strategy: "Turtle",
  create_orders: true,
  risk_check: true
}

// 阶段 3: 全量上线（100+ 只股票）
params: {
  action: "pipeline",
  symbols: fullPool,
  strategy: "Turtle",
  create_orders: true,
  risk_check: true
}
```

### 4. 错误处理

所有模式都有错误隔离：

**single 模式**:
```typescript
try {
  const result = await quant_cli({
    command: "strategy.execute",
    params: { action: "single", symbol: "600519.SH", strategy: "Turtle" }
  });
} catch (error) {
  // 处理错误（数据不足、策略失败等）
  console.error(`执行失败: ${error.message}`);
}
```

**batch 模式**:
```json
// 错误记录在 errors 数组，不影响其他股票
{
  "type": "error",
  "data": {
    "symbol": "000002.SZ",
    "error": "Insufficient data"
  }
}
```

**pipeline 模式**:
```json
// 错误记录在统计中，继续执行
{
  "signals_generated": 50,
  "signals_passed": 12,
  "signals_rejected": 38,
  "errors": [
    {"symbol": "000002.SZ", "error": "Insufficient data"}
  ]
}
```

### 5. 策略选择

**可用策略**:
- `Turtle`: 海龟交易法则（趋势跟踪）
- `MeanReversion`: 均值回归
- `Momentum`: 动量策略
- `BreakoutStrategy`: 突破策略
- 更多策略见 `quantsys-v2/strategies/`

**策略参数**:
```typescript
// 使用策略 ID
params: {
  strategy: "53"  // 策略 ID
}

// 使用策略名称
params: {
  strategy: "Turtle"  // 策略名称
}
```

---

## 性能优化

### 批量执行

**并发配置**:
- 默认并发度: 10 workers
- 可通过环境变量调整: `STRATEGY_WORKERS=20`

**批次大小建议**:
- **50-100 只**: 最佳性能（2-5 秒）
- **100-200 只**: 可接受（5-10 秒）
- **200+ 只**: 建议分批执行

**分批执行示例**:
```typescript
const allSymbols = [...]; // 500 只股票
const batchSize = 100;

for (let i = 0; i < allSymbols.length; i += batchSize) {
  const batch = allSymbols.slice(i, i + batchSize);
  
  await quant_cli({
    command: "strategy.execute",
    params: {
      action: "batch",
      symbols: batch,
      strategy: "Turtle"
    }
  });
}
```

### Pipeline 执行

**执行时机**:
- **推荐**: 盘后执行（15:30 - 17:00）
- **避免**: 交易时段（9:30 - 15:00）

**性能监控**:
```typescript
const startTime = Date.now();

const result = await quant_cli({
  command: "strategy.execute",
  params: {
    action: "pipeline",
    symbols: stockPool,
    strategy: "Turtle"
  }
});

const duration = Date.now() - startTime;

if (duration > 300000) {  // 超过 5 分钟
  console.warn(`执行时间过长: ${duration}ms，需要优化`);
}
```

**优化建议**:
- 减少股票池大小
- 增加并发度
- 优化策略计算逻辑
- 使用缓存（K线数据、技术指标）

---

## 常见问题

### Q1: single 模式和 batch 模式有什么区别？

**single 模式**:
- 返回详细的技术指标和风控参数
- 适合人工决策
- 单次调用，同步返回

**batch 模式**:
- 返回简化的信号列表
- 适合批量筛选
- 流式返回，实时反馈

### Q2: 如何选择置信度阈值？

根据策略历史表现调整：

```typescript
// 查询策略历史表现
const performance = await quant_cli({
  command: "performance.analyze",
  params: {
    strategy: "Turtle",
    days: 60
  }
});

// 根据胜率调整阈值
if (performance.win_rate > 0.7) {
  min_confidence = 0.6;  // 策略表现好，可以放宽
} else if (performance.win_rate > 0.5) {
  min_confidence = 0.7;  // 策略表现一般，保持平衡
} else {
  min_confidence = 0.8;  // 策略表现差，严格筛选
}
```

### Q3: Pipeline 模式如何处理风控拒绝？

风控拒绝的信号会记录原因，但不会创建订单：

```json
{
  "signals_rejected": 38,
  "rejection_reasons": {
    "position_limit": 15,        // 仓位超限
    "concentration_risk": 10,    // 行业集中度过高
    "volatility_too_high": 8,    // 波动率过高
    "insufficient_liquidity": 5  // 流动性不足
  }
}
```

**优化建议**:
- 调整风控参数（`RiskManager` 配置）
- 扩大股票池（分散风险）
- 降低单笔仓位

### Q4: 如何追踪信号执行结果？

所有持久化的信号都有 `signal_id`，可以追踪完整生命周期：

```typescript
// 1. 生成信号
const signal = await quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600519.SH",
    strategy: "Turtle",
    persist: true
  }
});

// 2. 查询信号状态
const status = await quant_cli({
  command: "signal.status",
  params: {
    signal_id: signal.signal_id
  }
});

// 3. 查询关联订单
const orders = await quant_cli({
  command: "order.list",
  params: {
    signal_id: signal.signal_id
  }
});

// 4. 查询盈亏
const performance = await quant_cli({
  command: "performance.query",
  params: {
    signal_id: signal.signal_id
  }
});
```

### Q5: 如何处理数据不足的情况？

**batch/pipeline 模式**:
- 自动跳过数据不足的股票
- 错误记录在 `errors` 数组

**single 模式**:
- 抛出异常，需要手动处理

```typescript
try {
  const result = await quant_cli({
    command: "strategy.execute",
    params: {
      action: "single",
      symbol: "新股代码",
      strategy: "Turtle"
    }
  });
} catch (error) {
  if (error.message.includes("Insufficient data")) {
    console.log("数据不足，跳过该股票");
  }
}
```

---

## 迁移指南

### 从旧版 `strategy_execute` 工具迁移

**旧版**:
```typescript
strategy_execute({
  symbol: "600519.SH",
  strategy_name: "Turtle"
})
```

**新版**:
```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600519.SH",
    strategy: "Turtle"
  }
})
```

### 从旧版 `signal.generate` 命令迁移

**旧版**:
```typescript
quant_cli({
  command: "signal.generate",
  params: {
    symbols: ["600519.SH", "000001.SZ"],
    strategy: "Turtle"
  }
})
```

**新版**:
```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "batch",
    symbols: ["600519.SH", "000001.SZ"],
    strategy: "Turtle"
  }
})
```

---

## 相关文档

- **迁移指南**: `docs/migration/strategy-system-unification.md`
- **设计文档**: `docs/superpowers/specs/2026-05-29-strategy-system-unification-design.md`
- **实现计划**: `docs/superpowers/plans/2026-05-29-strategy-system-unification.md`
- **API 文档**: `quantsys-v2/api/routes/strategy_execution.py`

---

## 总结

策略执行系统提供三种模式，覆盖从单股分析到完整自动化的所有场景：

| 场景 | 模式 | 关键参数 | 输出 |
|------|------|----------|------|
| 快速分析单股 | single | `symbol`, `strategy` | 详细信号 + 风控参数 |
| 批量筛选机会 | batch | `symbols`, `min_confidence` | 信号列表 + 统计摘要 |
| 完全自动化 | pipeline | `create_orders`, `risk_check` | 执行统计 + 订单列表 |

**核心原则**:
- 默认持久化，确保追踪链路完整
- 错误隔离，单个失败不影响整体
- 流式响应，实时反馈进度
- 风控集成，自动过滤高风险信号

**最佳实践**:
- 使用置信度过滤（推荐 0.7）
- Pipeline 模式先测试后上线
- 监控执行时间，超过 5 分钟需优化
- 根据策略历史表现调整参数
