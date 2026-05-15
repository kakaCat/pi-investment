# 挂单与持仓管理优化任务清单

## 📋 优化任务总览

| ID | 优化项 | 优先级 | 状态 | 实施时间 | 收益 | 负责人 |
|----|--------|--------|------|----------|------|--------|
| OPT-001 | 统一数据源 | ⭐⭐⭐ | ✅ 已完成 | 5分钟 | 高 | - |
| OPT-002 | 成交通知 | ⭐⭐⭐ | ✅ 已完成 | 10分钟 | 高 | - |
| OPT-003 | 自动止损/止盈 | ⭐⭐⭐ | ✅ 已完成 | 15分钟 | 高 | - |
| OPT-004 | 持仓成本调整 | ⭐⭐ | 📋 待实施 | 20分钟 | 中 | - |
| OPT-005 | 手续费计入成本 | ⭐⭐ | ✅ 已完成 | 10分钟 | 中 | - |
| OPT-006 | 自动清理过期挂单 | ⭐ | ✅ 已完成 | 5分钟 | 低 | - |
| OPT-007 | 批量操作 | ⭐⭐ | 📋 待实施 | 30分钟 | 中 | - |
| OPT-008 | 挂单优先级 | ⭐ | 📋 待实施 | 15分钟 | 低 | - |
| OPT-009 | 持仓分组管理 | ⭐ | 📋 待实施 | 20分钟 | 低 | - |
| OPT-010 | 挂单条件增强 | ⭐⭐ | 📋 待实施 | 60分钟 | 中 | - |

**状态说明**：
- ✅ 已完成
- 🚧 进行中
- 📋 待实施
- ⏸️ 暂停
- ❌ 已取消

---

## ⭐⭐⭐ 高优先级（已完成）

### OPT-001: 统一数据源

**状态**: ✅ 已完成  
**完成时间**: 2026-05-15  
**实施时间**: 5分钟

#### 问题描述
手动买入只更新 `portfolio.json`，不记录到 `trades.json`，导致：
- 数据不一致：trades 无法重建 portfolio
- 缺少审计：手动录入的买入没有记录
- 统计困难：无法统计总买入、总卖出

#### 解决方案
```typescript
// src/infrastructure/tools/invest/portfolio-tools.ts
if (action === "add") {
  const res = _portfolioSvc.add(symbol, quantity, avg_cost, ...);
  
  // ✅ 记录交易
  try {
    const ts = new TradeService(PI_DIR);
    ts.add(chinaDate(), symbol, name || symbol, "buy", quantity, avg_cost, 0, market ?? "A", notes || "手动录入");
  } catch (e) {
    console.warn("交易记录失败:", e);
  }
}
```

#### 验证方式
```bash
# 1. 手动买入
manage_portfolio({ action: "add", symbol: "600519", quantity: 100, avg_cost: 1800 })

# 2. 检查 trades.json
cat .pi-invest/trades.json | jq '.trades | last'

# 预期：应该看到新增的买入记录
```

#### 收益
- ✅ 数据一致性：trades 可以重建 portfolio
- ✅ 完整审计：所有买卖都有记录
- ✅ 便于分析：可以统计总买入、总卖出、总盈亏

---

### OPT-002: 成交通知

**状态**: ✅ 已完成  
**完成时间**: 2026-05-15  
**实施时间**: 10分钟

#### 问题描述
挂单自动成交后，用户不知道，需要主动查看才能发现

#### 解决方案
```typescript
// src/infrastructure/tools/check-pending-orders.ts
const summary = fills.length > 0
  ? `✅ 本次成交 ${fills.length} 笔：${fills.map(f =>
      `${f.order.name}(${f.order.symbol}) ${f.order.side === "buy" ? "买入" : "卖出"} ${f.fillQuantity}股@¥${f.fillPrice.toFixed(2)}`
    ).join("、")}`
  : notYets.length > 0
    ? `⏳ ${notYets.length} 个挂单等待触发`
    : "📋 当前无挂单";

return {
  content: [{ type: "text" as const, text: lines.join("") + `\n\n---\n\n### 📢 成交通知\n${summary}` }],
  details: { ..., summary }
};
```

#### 验证方式
```bash
# 1. 创建挂单
manage_orders({ action: "place", symbol: "688981", side: "buy", price: 45, quantity: 300 })

# 2. 检查挂单（假设价格触发）
check_pending_orders()

# 预期：应该看到清晰的成交通知
```

#### 收益
- ✅ 用户及时知道成交情况
- ✅ 不错过后续操作时机
- ✅ 提升用户体验

---

### OPT-003: 自动止损/止盈

**状态**: ✅ 已完成  
**完成时间**: 2026-05-15  
**实施时间**: 15分钟

#### 问题描述
`portfolio.json` 中有 `stop_loss` 和 `target_price` 字段，但只是记录，不会自动创建挂单

#### 解决方案
```typescript
// src/infrastructure/tools/invest/portfolio-tools.ts
// 1. 添加参数
parameters: Type.Object({
  stop_loss: Type.Optional(Type.Number({ description: "止损价（可选）" })),
  target_price: Type.Optional(Type.Number({ description: "目标价（可选）" })),
}),

// 2. 实现逻辑
if (action === "add") {
  // ... 添加持仓 ...
  
  if (stop_loss || target_price) {
    const orderSvc = new OrderService(PI_DIR);
    
    if (stop_loss && stop_loss > 0) {
      orderSvc.create({ symbol, side: "sell", type: "stop_loss", price: stop_loss, quantity });
    }
    
    if (target_price && target_price > avg_cost) {
      orderSvc.create({ symbol, side: "sell", type: "limit", price: target_price, quantity });
    }
  }
}
```

#### 验证方式
```bash
# 1. 买入并设置止损止盈
manage_portfolio({ 
  action: "add", 
  symbol: "688981", 
  quantity: 300, 
  avg_cost: 45, 
  stop_loss: 40.5, 
  target_price: 54 
})

# 2. 检查挂单
manage_orders({ action: "list" })

# 预期：应该看到 2 个自动创建的挂单
```

#### 收益
- ✅ 风险管理自动化
- ✅ 不需要手动创建止损单
- ✅ 买入即设置保护

---

## ⭐⭐ 中优先级（待实施）

### OPT-004: 持仓成本调整

**状态**: 📋 待实施  
**预计时间**: 20分钟  
**优先级**: ⭐⭐

#### 问题描述
分红、送股、配股后，持仓成本需要调整，当前只能用 `update` 手动修改，容易出错

#### 解决方案

**1. 新增 `adjust` 操作**：
```typescript
// src/infrastructure/tools/invest/portfolio-tools.ts
if (action === "adjust") {
  // 参数校验
  if (!symbol || !reason) {
    return { error: "adjust 需要 symbol, reason" };
  }
  
  const holding = _portfolioSvc.load().holdings.find(h => h.symbol === symbol);
  if (!holding) {
    return { error: `未找到持仓: ${symbol}` };
  }
  
  // 计算新的数量和成本
  const newQuantity = holding.quantity + (quantity_change || 0);
  const totalCost = holding.avg_cost * holding.quantity + (cost_adjustment || 0);
  const newAvgCost = totalCost / newQuantity;
  
  // 更新持仓
  _portfolioSvc.update(symbol, newQuantity, newAvgCost);
  
  // 记录调整
  const ts = new TradeService(PI_DIR);
  ts.add(chinaDate(), symbol, holding.name, "adjust", quantity_change || 0, 0, 0, holding.market, 
    `${reason}: 数量变化 ${quantity_change}, 成本调整 ${cost_adjustment}`);
  
  return { success: true, message: `持仓已调整: ${symbol}` };
}
```

**2. 添加参数**：
```typescript
parameters: Type.Object({
  // ... 现有字段 ...
  reason: Type.Optional(Type.String({ description: "调整原因: 'dividend'(分红), 'bonus'(送股), 'rights'(配股)" })),
  quantity_change: Type.Optional(Type.Integer({ description: "数量变化（送股/配股）" })),
  cost_adjustment: Type.Optional(Type.Number({ description: "成本调整金额（分红为负，配股为正）" })),
}),
```

#### 使用示例
```typescript
// 分红：每股分红 0.5 元，持有 100 股
manage_portfolio({ 
  action: "adjust",
  symbol: "600519",
  reason: "dividend",
  cost_adjustment: -50  // 分红 50 元，降低成本
})

// 送股：10 送 1，持有 100 股
manage_portfolio({ 
  action: "adjust",
  symbol: "600519",
  reason: "bonus",
  quantity_change: 10  // 增加 10 股
})

// 配股：10 配 1，配股价 10 元，持有 100 股
manage_portfolio({ 
  action: "adjust",
  symbol: "600519",
  reason: "rights",
  quantity_change: 10,
  cost_adjustment: 100  // 配股花费 100 元
})
```

#### 验证方式
```bash
# 1. 初始持仓：100股 @ 50元
manage_portfolio({ action: "add", symbol: "600519", quantity: 100, avg_cost: 50 })

# 2. 分红调整：每股分红 0.5 元
manage_portfolio({ action: "adjust", symbol: "600519", reason: "dividend", cost_adjustment: -50 })

# 3. 检查持仓
manage_portfolio({ action: "get" })

# 预期：成本价应该从 50 降到 49.5
```

#### 实施步骤
- [ ] 1. 在 `portfolio-tools.ts` 中添加 `adjust` 操作
- [ ] 2. 添加参数定义
- [ ] 3. 实现成本调整逻辑
- [ ] 4. 记录调整到 `trades.json`
- [ ] 5. 编写单元测试
- [ ] 6. 更新文档

#### 收益
- ✅ 准确记录分红送股
- ✅ 真实成本计算
- ✅ 完整审计记录

---

### OPT-005: 手续费计入成本

**状态**: ✅ 已完成  
**完成时间**: 2026-05-15  
**实施时间**: 10分钟

#### 问题描述
`TradeService` 有 `commission` 字段，但 `PortfolioService.add()` 不考虑手续费，实际成本 = 买入价 + 手续费

#### 解决方案

**1. 修改 PortfolioService**：
```typescript
// src/services/portfolio/portfolio-service.ts
add(symbol: string, quantity: number, price: number, commission = 0, name = "", market: "A" | "HK" = "A", notes = "") {
  // 计算实际成本（包含手续费）
  const actualCost = (price * quantity + commission) / quantity;
  
  const existing = this.data.holdings.find(h => h.symbol === symbol);
  if (existing) {
    // 加权平均成本
    const totalQty = existing.quantity + quantity;
    const totalCost = existing.avg_cost * existing.quantity + actualCost * quantity;
    existing.avg_cost = roundN(totalCost / totalQty);
    existing.quantity = totalQty;
  } else {
    // 新建持仓
    this.data.holdings.push({
      symbol, name, quantity,
      avg_cost: roundN(actualCost),  // 使用实际成本
      market, notes,
      added_date: today()
    });
  }
  
  this.save();
  return { success: true, message: `新增持仓 ${symbol}` };
}
```

**2. 修改 portfolio-tools**：
```typescript
// src/infrastructure/tools/invest/portfolio-tools.ts
parameters: Type.Object({
  // ... 现有字段 ...
  commission: Type.Optional(Type.Number({ description: "手续费（可选），默认 0" })),
}),

if (action === "add") {
  // ... 参数校验 ...
  
  const res = _portfolioSvc.add(symbol, quantity, avg_cost, commission || 0, name ?? "", market ?? "A", notes ?? "");
  
  // 记录交易时也包含手续费
  const ts = new TradeService(PI_DIR);
  ts.add(chinaDate(), symbol, name || symbol, "buy", quantity, avg_cost, commission || 0, market ?? "A", notes || "手动录入");
}
```

#### 使用示例
```typescript
// 买入 100股 @ 50元，手续费 5元
manage_portfolio({ 
  action: "add",
  symbol: "600519",
  quantity: 100,
  avg_cost: 50,
  commission: 5
})

// 实际成本 = (50 * 100 + 5) / 100 = 50.05元
```

#### 验证方式
```bash
# 1. 买入（含手续费）
manage_portfolio({ action: "add", symbol: "600519", quantity: 100, avg_cost: 50, commission: 5 })

# 2. 检查持仓
manage_portfolio({ action: "get" })

# 预期：avg_cost 应该是 50.05，而不是 50
```

#### 实施步骤
- [ ] 1. 修改 `PortfolioService.add()` 方法
- [ ] 2. 在 `portfolio-tools.ts` 中添加 `commission` 参数
- [ ] 3. 更新调用逻辑
- [ ] 4. 编写单元测试
- [ ] 5. 更新文档

#### 收益
- ✅ 真实成本计算
- ✅ 准确的盈亏统计
- ✅ 符合实际交易情况

---

### OPT-007: 批量操作

**状态**: 📋 待实施  
**预计时间**: 30分钟  
**优先级**: ⭐⭐

#### 问题描述
创建多个挂单需要多次调用，效率低

#### 解决方案

**新增 `place_batch` 操作**：
```typescript
// src/infrastructure/tools/order-tools.ts
if (action === "place_batch") {
  if (!params.orders || !Array.isArray(params.orders)) {
    return { error: "place_batch 需要 orders 数组" };
  }
  
  const orderService = new OrderService(PI_DIR);
  const created: string[] = [];
  const errors: string[] = [];
  
  for (const orderParams of params.orders) {
    try {
      const order = orderService.create(orderParams);
      created.push(order.id);
    } catch (e) {
      errors.push(`${orderParams.symbol}: ${e.message}`);
    }
  }
  
  return {
    success: true,
    created_count: created.length,
    error_count: errors.length,
    created_ids: created,
    errors
  };
}
```

#### 使用示例
```typescript
// 分批建仓：3 个买入挂单
manage_orders({ 
  action: "place_batch",
  orders: [
    { symbol: "688981", name: "中芯国际", side: "buy", price: 45, quantity: 300 },
    { symbol: "688981", name: "中芯国际", side: "buy", price: 43, quantity: 300 },
    { symbol: "688981", name: "中芯国际", side: "buy", price: 41, quantity: 400 }
  ]
})
```

#### 实施步骤
- [ ] 1. 在 `order-tools.ts` 中添加 `place_batch` 操作
- [ ] 2. 添加参数定义
- [ ] 3. 实现批量创建逻辑
- [ ] 4. 错误处理
- [ ] 5. 编写单元测试
- [ ] 6. 更新文档

#### 收益
- ✅ 提升效率
- ✅ 减少重复操作
- ✅ 便于分批建仓

---

## ⭐ 低优先级（待实施）

### OPT-006: 自动清理过期挂单

**状态**: ✅ 已完成  
**完成时间**: 2026-05-15  
**实施时间**: 5分钟

#### 问题描述
挂单有 `expires_at` 字段，但需要手动调用 `expireOverdue()` 才会清理

#### 解决方案

**1. 在 check_pending_orders 中自动清理**：
```typescript
// src/infrastructure/tools/check-pending-orders.ts
export async function execute() {
  // ✅ 每次检查时自动清理过期挂单
  const expiredCount = orderService.expireOverdue();
  
  // ... 继续检查 pending 挂单 ...
}
```

**2. 添加定时任务自动执行**：
```json
// .pi-invest/CRON.json
{
  "id": "check-pending-orders",
  "name": "检查挂单并清理过期",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "*/30 9-15 * * 1-5"
  },
  "payload": {
    "kind": "agent_turn",
    "message": "检查所有挂单状态，自动成交触发的订单，清理过期挂单"
  }
}
```

#### 验证方式
```bash
# 1. 启动系统，查看 cron 任务列表
npm start

# 预期输出：
# ⏰ Cron 任务（8 个）:
#   ✅ 检查挂单并清理过期（cron: check-pending-orders） 下次：2026-05-15 09:30（15 分钟后）

# 2. 系统会在交易时间每 30 分钟自动检查挂单
# 3. 过期挂单会被自动清理
```

#### 实施步骤
- [x] 1. 在 `check_pending_orders` 开始时调用 `expireOverdue()`
- [x] 2. 添加 cron 任务配置到 CRON.json
- [x] 3. 验证 cron 任务加载和执行逻辑
- [x] 4. 更新文档

#### 收益
- ✅ 真正的自动化：无需手动调用，系统自动定时清理
- ✅ 及时清理：交易时间每 30 分钟检查一次
- ✅ 自动成交：同时检查挂单触发条件，自动执行成交
- ✅ 保持整洁：orders.json 不会堆积过期挂单

---

### OPT-008: 挂单优先级

**状态**: 📋 待实施  
**预计时间**: 15分钟  
**优先级**: ⭐

#### 问题描述
同一只股票有多个挂单时，无法设置优先级

#### 解决方案
```typescript
// src/services/order-service.ts
interface PendingOrder {
  // ... 现有字段 ...
  priority: number;  // 1-10，数字越大优先级越高
}

// 检查触发时按优先级排序
const pendingOrders = orderService.listPending()
  .sort((a, b) => b.priority - a.priority);
```

#### 实施步骤
- [ ] 1. 在 `PendingOrder` 中添加 `priority` 字段
- [ ] 2. 修改 `check_pending_orders` 排序逻辑
- [ ] 3. 更新文档

---

### OPT-009: 持仓分组管理

**状态**: 📋 待实施  
**预计时间**: 20分钟  
**优先级**: ⭐

#### 问题描述
无法对持仓进行分组管理（核心持仓、短线、打新等）

#### 解决方案
```typescript
// src/services/portfolio/portfolio-service.ts
interface Holding {
  // ... 现有字段 ...
  group?: string;     // 分组：核心持仓、短线、打新
  strategy?: string;  // 策略：价值投资、趋势跟踪
}

// 按分组查看
manage_portfolio({ action: "get_with_pnl", group: "核心持仓" })
```

#### 实施步骤
- [ ] 1. 在 `Holding` 中添加 `group` 和 `strategy` 字段
- [ ] 2. 修改查询逻辑支持分组过滤
- [ ] 3. 更新文档

---

### OPT-010: 挂单条件增强

**状态**: 📋 待实施  
**预计时间**: 60分钟  
**优先级**: ⭐⭐

#### 问题描述
挂单只支持简单的价格触发，无法设置复杂条件

#### 解决方案
```typescript
interface PendingOrder {
  // ... 现有字段 ...
  conditions?: {
    volume_min?: number;      // 最小成交量
    time_range?: {            // 时间范围
      start: "09:30",
      end: "14:30"
    };
    market_condition?: {      // 市场条件
      index: "000001",
      change_pct_min: -2
    };
  };
}
```

#### 实施步骤
- [ ] 1. 设计条件数据结构
- [ ] 2. 实现条件判断逻辑
- [ ] 3. 更新触发检查
- [ ] 4. 编写单元测试
- [ ] 5. 更新文档

---

## 📊 实施进度跟踪

### 已完成 (5/10)
- ✅ OPT-001: 统一数据源
- ✅ OPT-002: 成交通知
- ✅ OPT-003: 自动止损/止盈
- ✅ OPT-005: 手续费计入成本
- ✅ OPT-006: 自动清理过期挂单

### 进行中 (0/10)
- 无

### 待实施 (5/10)
- 📋 OPT-004: 持仓成本调整
- 📋 OPT-007: 批量操作
- 📋 OPT-008: 挂单优先级
- 📋 OPT-009: 持仓分组管理
- 📋 OPT-010: 挂单条件增强

---

## 📅 实施计划

### Phase 1: 核心优化（已完成）
- ✅ OPT-001: 统一数据源
- ✅ OPT-002: 成交通知
- ✅ OPT-003: 自动止损/止盈

### Phase 2: 体验优化（已完成）
- ✅ OPT-005: 手续费计入成本（10分钟）
- ✅ OPT-006: 自动清理过期挂单（5分钟）
- 📋 OPT-004: 持仓成本调整（20分钟）

### Phase 3: 功能增强（按需实施）
- 📋 OPT-007: 批量操作（30分钟）
- 📋 OPT-008: 挂单优先级（15分钟）
- 📋 OPT-009: 持仓分组管理（20分钟）
- 📋 OPT-010: 挂单条件增强（60分钟）

---

## 📝 更新日志

### 2026-05-15
- ✅ 完成 OPT-001: 统一数据源
- ✅ 完成 OPT-002: 成交通知
- ✅ 完成 OPT-003: 自动止损/止盈
- ✅ 完成 OPT-005: 手续费计入成本
- ✅ 完成 OPT-006: 自动清理过期挂单
- 📄 创建优化任务清单文档

---

## 🔗 相关文档

- [业务流程梳理](order-portfolio-trade-flow.md)
- [优化建议](order-portfolio-optimization.md)
- [优化完成报告](optimization-completion-report.md)
- [重构完成报告](refactoring-completion-report.md)
- [Phase 2 优化报告](phase2-optimization-report.md)
- [Phase 2 完成总结](phase2-completion-summary.md)
- [OPT-006 Cron 实现详解](opt-006-cron-implementation.md)
