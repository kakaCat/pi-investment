# 挂单、持仓管理与交易流程优化建议

## 🔍 当前流程分析

### 现有问题

#### 1. **数据一致性风险** ⚠️
**问题**：
- `portfolio.json` 和 `trades.json` 是两个独立的数据源
- 手动买入只更新 `portfolio.json`，不记录到 `trades.json`
- 可能导致数据不一致：trades 无法重建完整的 portfolio

**场景**：
```
用户手动录入: manage_portfolio(add, 600519, 100股, 1800)
→ portfolio.json 有记录
→ trades.json 无记录 ❌

如果 portfolio.json 损坏，无法从 trades.json 重建
```

#### 2. **挂单成交后缺少通知** 📢
**问题**：
- 挂单自动成交后，用户不知道
- 需要主动查看才能发现

**场景**：
```
用户创建挂单 → 定时检查触发 → 自动成交
→ 用户不知道已经成交 ❌
→ 可能错过后续操作时机
```

#### 3. **止损和目标价未自动创建挂单** 🎯
**问题**：
- `portfolio.json` 中有 `stop_loss` 和 `target_price` 字段
- 但这些只是记录，不会自动创建挂单
- 需要用户手动创建止损单

**场景**：
```
用户买入时设置: stop_loss = 1620
→ 只是记录在 portfolio.json ❌
→ 不会自动创建止损挂单
→ 不会自动触发卖出
```

#### 4. **缺少持仓成本调整机制** 💰
**问题**：
- 分红、送股、配股后，持仓成本需要调整
- 当前只能用 `update` 手动修改
- 容易出错，缺少审计记录

#### 5. **交易手续费未计入成本** 💸
**问题**：
- `TradeService` 有 `commission` 字段
- 但 `PortfolioService.add()` 不考虑手续费
- 实际成本 = 买入价 + 手续费

**场景**：
```
买入 100股 @ 50元，手续费 5元
实际成本 = (100 * 50 + 5) / 100 = 50.05元
但 portfolio.json 记录的是 50元 ❌
```

#### 6. **挂单过期清理不自动** ⏰
**问题**：
- 挂单有 `expires_at` 字段
- 但需要手动调用 `expireOverdue()` 才会清理
- 过期挂单可能一直显示为 pending

#### 7. **缺少批量操作** 📦
**问题**：
- 创建多个挂单需要多次调用
- 查看多只股票的挂单需要多次调用
- 效率低

#### 8. **缺少挂单优先级** 🔢
**问题**：
- 同一只股票有多个挂单时，无法设置优先级
- 例如：先成交止损单，再成交止盈单

---

## 💡 优化建议

### 优化 1: 统一数据源 - 所有操作都记录交易 ⭐⭐⭐

**方案**：
```typescript
// 手动买入也记录到 trades.json
manage_portfolio({ action: "add", ... })
  ↓
PortfolioService.add()
  ↓
TradeService.add()  // ✅ 新增：记录交易
  ↓
portfolio.json + trades.json 都更新
```

**好处**：
- ✅ 数据一致性：trades.json 可以重建 portfolio.json
- ✅ 完整审计：所有买卖都有记录
- ✅ 便于分析：可以统计总买入、总卖出、总盈亏

**实现**：
```typescript
// portfolio-tools.ts - add 操作
if (action === "add") {
  // ... 参数校验 ...
  
  const res = _portfolioSvc.add(symbol, quantity, avg_cost, name ?? "", market ?? "A", notes ?? "");
  
  // ✅ 新增：记录交易
  try {
    const ts = new TradeService(PI_DIR);
    ts.add(chinaDate(), symbol, name || symbol, "buy", quantity, avg_cost, 0, market ?? "A", notes || "手动录入");
  } catch (e) {
    console.warn("交易记录失败:", e);
  }
  
  return { content: [{ type: "text" as const, text: JSON.stringify(res) }], details: undefined };
}
```

---

### 优化 2: 挂单成交通知 ⭐⭐⭐

**方案 1: 返回成交摘要**
```typescript
check_pending_orders() 返回:
{
  fills: [
    { symbol: "688981", side: "buy", quantity: 300, price: 45.0 }
  ],
  summary: "✅ 本次成交 1 笔：688981 买入 300股@45.0"
}
```

**方案 2: 集成飞书/企业微信通知**
```typescript
// check-pending-orders.ts
if (fills.length > 0) {
  await sendNotification({
    title: "挂单成交通知",
    content: `${symbol} ${side} ${quantity}股@${price}`
  });
}
```

**方案 3: 写入通知队列**
```typescript
// .pi-invest/notifications.json
{
  notifications: [
    {
      type: "order_filled",
      timestamp: "2026-05-15 14:30:00",
      data: { symbol: "688981", ... },
      read: false
    }
  ]
}
```

---

### 优化 3: 自动创建止损/止盈挂单 ⭐⭐⭐

**方案**：
```typescript
// 买入时自动创建止损单
manage_portfolio({ 
  action: "add",
  symbol: "600519",
  quantity: 100,
  avg_cost: 1800,
  stop_loss: 1620,      // -10%
  target_price: 2160    // +20%
})
  ↓
PortfolioService.add()
  ↓
自动创建挂单:
  1. 止损单: 1620元卖出 100股
  2. 止盈单: 2160元卖出 100股
```

**实现**：
```typescript
// portfolio-tools.ts - add 操作
if (action === "add") {
  // ... 添加持仓 ...
  
  // ✅ 新增：自动创建止损/止盈挂单
  const orderService = new OrderService(PI_DIR);
  
  if (params.stop_loss && params.stop_loss > 0) {
    orderService.create({
      symbol,
      name: name || symbol,
      side: "sell",
      type: "stop_loss",
      price: params.stop_loss,
      quantity,
      market: market ?? "A",
      notes: `自动止损单（成本价 ${avg_cost}）`
    });
  }
  
  if (params.target_price && params.target_price > avg_cost) {
    orderService.create({
      symbol,
      name: name || symbol,
      side: "sell",
      type: "limit",
      price: params.target_price,
      quantity,
      market: market ?? "A",
      notes: `自动止盈单（成本价 ${avg_cost}）`
    });
  }
}
```

---

### 优化 4: 持仓成本调整机制 ⭐⭐

**方案**：新增 `adjust` 操作
```typescript
manage_portfolio({ 
  action: "adjust",
  symbol: "600519",
  reason: "dividend",  // 分红/送股/配股
  quantity_change: 10, // 送股 10股
  cost_adjustment: -50 // 分红 50元
})
  ↓
记录到 trades.json:
{
  action: "adjust",
  reason: "dividend",
  quantity_change: 10,
  cost_adjustment: -50
}
  ↓
更新 portfolio.json:
  new_quantity = old_quantity + 10
  new_avg_cost = (old_cost * old_quantity - 50) / new_quantity
```

---

### 优化 5: 手续费计入成本 ⭐⭐

**方案**：
```typescript
// 买入时计入手续费
manage_portfolio({ 
  action: "add",
  symbol: "600519",
  quantity: 100,
  price: 1800,
  commission: 5  // ✅ 新增参数
})
  ↓
实际成本 = (price * quantity + commission) / quantity
         = (1800 * 100 + 5) / 100
         = 1800.05
```

**实现**：
```typescript
// portfolio-service.ts
add(symbol: string, quantity: number, price: number, commission = 0, ...) {
  const actualCost = (price * quantity + commission) / quantity;
  // ... 使用 actualCost 而不是 price ...
}
```

---

### 优化 6: 自动清理过期挂单 ⭐

**方案 1: 在 check_pending_orders 中自动清理**
```typescript
// check-pending-orders.ts
export async function execute() {
  // ✅ 每次检查时自动清理过期挂单
  const expiredCount = orderService.expireOverdue();
  
  // ... 继续检查 pending 挂单 ...
}
```

**方案 2: 定时任务**
```typescript
// 每小时清理一次过期挂单
cron.schedule("0 * * * *", () => {
  const orderService = new OrderService(PI_DIR);
  orderService.expireOverdue();
});
```

---

### 优化 7: 批量操作 ⭐⭐

**方案**：
```typescript
// 批量创建挂单
manage_orders({ 
  action: "place_batch",
  orders: [
    { symbol: "688981", side: "buy", price: 45, quantity: 300 },
    { symbol: "688981", side: "buy", price: 43, quantity: 300 },
    { symbol: "688981", side: "buy", price: 41, quantity: 400 }
  ]
})

// 批量查询挂单
manage_orders({ 
  action: "list",
  symbols: ["688981", "600519", "000001"]
})
```

---

### 优化 8: 挂单优先级 ⭐

**方案**：
```typescript
interface PendingOrder {
  // ... 现有字段 ...
  priority: number;  // ✅ 新增：优先级（1-10，数字越大优先级越高）
}

// 检查触发时按优先级排序
const pendingOrders = orderService.listPending()
  .sort((a, b) => b.priority - a.priority);  // 高优先级先检查
```

**使用场景**：
```typescript
// 止损单优先级最高
manage_orders({ 
  action: "place",
  type: "stop_loss",
  priority: 10  // 最高优先级
})

// 止盈单优先级中等
manage_orders({ 
  action: "place",
  type: "limit",
  priority: 5
})
```

---

### 优化 9: 持仓分组管理 ⭐

**方案**：
```typescript
interface Holding {
  // ... 现有字段 ...
  group?: string;  // ✅ 新增：分组（如 "核心持仓"、"短线"、"打新"）
  strategy?: string; // ✅ 新增：策略（如 "价值投资"、"趋势跟踪"）
}

// 按分组查看持仓
manage_portfolio({ 
  action: "get_with_pnl",
  group: "核心持仓"
})
```

---

### 优化 10: 挂单条件增强 ⭐⭐

**方案**：支持更复杂的触发条件
```typescript
interface PendingOrder {
  // ... 现有字段 ...
  conditions?: {
    price_condition: "gte" | "lte" | "between";  // 价格条件
    volume_min?: number;      // 最小成交量
    time_range?: {            // 时间范围
      start: "09:30",
      end: "14:30"
    };
    market_condition?: {      // 市场条件
      index: "000001",        // 上证指数
      change_pct_min: -2      // 大盘跌幅 > 2% 时才触发
    };
  };
}
```

---

## 📊 优化优先级排序

| 优化项 | 优先级 | 实现难度 | 收益 | 建议 |
|--------|--------|----------|------|------|
| 1. 统一数据源 | ⭐⭐⭐ | 低 | 高 | **立即实施** |
| 2. 成交通知 | ⭐⭐⭐ | 中 | 高 | **立即实施** |
| 3. 自动止损/止盈 | ⭐⭐⭐ | 中 | 高 | **立即实施** |
| 5. 手续费计入 | ⭐⭐ | 低 | 中 | 近期实施 |
| 6. 自动清理过期 | ⭐ | 低 | 低 | 近期实施 |
| 4. 成本调整 | ⭐⭐ | 中 | 中 | 按需实施 |
| 7. 批量操作 | ⭐⭐ | 中 | 中 | 按需实施 |
| 8. 挂单优先级 | ⭐ | 低 | 低 | 按需实施 |
| 9. 持仓分组 | ⭐ | 低 | 低 | 按需实施 |
| 10. 条件增强 | ⭐⭐ | 高 | 中 | 长期规划 |

---

## 🎯 推荐实施方案

### Phase 1: 核心优化（立即实施）

1. **统一数据源** - 手动买入也记录交易
2. **成交通知** - 返回详细的成交摘要
3. **自动止损/止盈** - 买入时自动创建挂单

### Phase 2: 体验优化（近期实施）

4. **手续费计入** - 真实成本计算
5. **自动清理** - 过期挂单自动清理

### Phase 3: 功能增强（按需实施）

6. **成本调整** - 分红送股处理
7. **批量操作** - 提升效率
8. **持仓分组** - 更好的组织

---

## 💻 快速实施代码

### 优化 1: 统一数据源

```typescript
// src/infrastructure/tools/invest/portfolio-tools.ts
if (action === "add") {
  // ... 现有代码 ...
  const res = _portfolioSvc.add(symbol, quantity, avg_cost, name ?? "", market ?? "A", notes ?? "");
  
  // ✅ 新增：记录交易
  try {
    const ts = new TradeService(PI_DIR);
    ts.add(chinaDate(), symbol, name || symbol, "buy", quantity, avg_cost, 0, market ?? "A", notes || "手动录入");
  } catch {}
  
  return { content: [{ type: "text" as const, text: JSON.stringify(res) }], details: undefined };
}
```

### 优化 2: 成交通知

```typescript
// src/infrastructure/tools/check-pending-orders.ts
// 在返回结果中添加摘要
const summary = fills.length > 0 
  ? `✅ 本次成交 ${fills.length} 笔：${fills.map(f => `${f.order.name} ${sideLabel(f.order.side)} ${f.fillQuantity}股@${f.fillPrice}`).join(", ")}`
  : "⏳ 暂无挂单触发";

return {
  content: [{ type: "text" as const, text: lines.join("") + `\n\n${summary}` }],
  details: { fills, notYets, errors, summary }
};
```

### 优化 3: 自动止损/止盈

```typescript
// src/infrastructure/tools/invest/portfolio-tools.ts
// 在 parameters 中添加字段
parameters: Type.Object({
  // ... 现有字段 ...
  stop_loss: Type.Optional(Type.Number({ description: "止损价（可选），自动创建止损挂单" })),
  target_price: Type.Optional(Type.Number({ description: "目标价（可选），自动创建止盈挂单" })),
}),

// 在 execute 中实现
if (action === "add") {
  // ... 添加持仓 ...
  
  // ✅ 自动创建止损/止盈挂单
  if (params.stop_loss || params.target_price) {
    const { OrderService } = await import("../../services/order-service.js");
    const orderSvc = new OrderService(PI_DIR);
    
    if (params.stop_loss && params.stop_loss > 0) {
      orderSvc.create({
        symbol, name: name || symbol, side: "sell", type: "stop_loss",
        price: params.stop_loss, quantity, market: market ?? "A",
        notes: `自动止损（成本 ${avg_cost}）`
      });
    }
    
    if (params.target_price && params.target_price > avg_cost) {
      orderSvc.create({
        symbol, name: name || symbol, side: "sell", type: "limit",
        price: params.target_price, quantity, market: market ?? "A",
        notes: `自动止盈（成本 ${avg_cost}）`
      });
    }
  }
}
```

---

## ✅ 总结

### 最关键的 3 个优化

1. **统一数据源** - 解决数据一致性问题
2. **成交通知** - 提升用户体验
3. **自动止损/止盈** - 风险管理自动化

这三个优化实现简单、收益高，建议优先实施！
