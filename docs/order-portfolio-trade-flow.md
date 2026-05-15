# 挂单、持仓管理与交易流程完整业务梳理

## 📊 核心数据结构

### 1. 持仓数据 (portfolio.json)
```typescript
interface Holding {
  symbol: string;           // 股票代码
  name: string;             // 股票名称
  quantity: number;         // 持股数量
  avg_cost: number;         // 持仓均价
  market: "A" | "HK";       // 市场类型
  notes: string;            // 备注
  added_date: string;       // 首次录入日期
  stop_loss?: number;       // 止损价（可选）
  target_price?: number;    // 目标价（可选）
  sector?: string;          // 行业（可选）
  buy_reason?: string;      // 买入理由（可选）
}
```

### 2. 交易记录 (trades.json)
```typescript
interface Trade {
  id: string;
  date: string;             // YYYY-MM-DD
  symbol: string;
  name: string;
  action: "buy" | "sell";
  quantity: number;         // 股数
  price: number;            // 成交均价
  commission: number;       // 手续费
  amount: number;           // 成交金额
  market: "A" | "HK";
  notes: string;
}
```

### 3. 挂单数据 (orders.json)
```typescript
interface PendingOrder {
  id: string;
  symbol: string;
  name: string;
  side: "buy" | "sell";
  type: "limit" | "stop_loss" | "batch_plan";
  price: number;            // 挂单价
  quantity: number;         // 挂单数量
  filled_quantity: number;  // 已成交数量
  fill_price: number | null;// 实际成交价
  status: "pending" | "filled" | "partial" | "cancelled" | "expired";
  market: "A" | "HK";
  created_at: string;
  updated_at: string;
  expires_at: string | null;// null=永不过期
  history: OrderHistoryEntry[];
  notes: string;
}
```

---

## 🔄 完整业务流程

### 流程 1: 手动买入（立即成交）

```
用户说："买入 600519 贵州茅台 100股，成本价 1800"
    ↓
manage_portfolio({ 
  action: "add",
  symbol: "600519",
  name: "贵州茅台",
  quantity: 100,
  avg_cost: 1800
})
    ↓
PortfolioService.add()
    ├─ 检查是否已有持仓
    ├─ 如果有：计算加权平均成本
    │   new_avg = (old_qty * old_cost + new_qty * new_cost) / (old_qty + new_qty)
    └─ 如果无：创建新持仓
    ↓
写入 portfolio.json
    ↓
✅ 完成：持仓已更新
```

**数据变化**：
- `portfolio.json`: 新增或更新持仓记录
- `trades.json`: 无变化（手动录入不记录交易）

---

### 流程 2: 手动卖出（立即成交）

```
用户说："卖出 600519 50股，价格 2000"
    ↓
manage_portfolio({ 
  action: "sell",
  symbol: "600519",
  quantity: 50,
  price: 2000
})
    ↓
PortfolioService 校验
    ├─ 检查持仓是否存在
    ├─ 检查持仓数量是否足够 ✅ (已修复)
    │   if (holding.quantity < quantity) → 报错
    └─ 计算盈亏
        pnl_per_share = price - avg_cost
        pnl_amount = pnl_per_share * quantity
        pnl_pct = (pnl_per_share / avg_cost) * 100
    ↓
更新持仓
    ├─ remaining = holding.quantity - quantity
    ├─ if (remaining <= 0) → 清仓，删除持仓
    └─ else → 减仓，更新数量
    ↓
TradeService.add()
    └─ 记录卖出交易到 trades.json
    ↓
✅ 完成：持仓已更新，交易已记录
```

**数据变化**：
- `portfolio.json`: 减少或删除持仓
- `trades.json`: 新增卖出记录

---

### 流程 3: 创建挂单（延迟成交）

```
用户说："在 45 元挂单买入中芯国际 300股"
    ↓
manage_orders({ 
  action: "place",
  symbol: "688981",
  name: "中芯国际",
  side: "buy",
  type: "limit",
  price: 45.0,
  quantity: 300
})
    ↓
OrderService.create()
    ├─ 生成唯一 ID
    ├─ 设置状态为 "pending"
    ├─ 计算过期时间（如果指定）
    └─ 记录创建历史
    ↓
写入 orders.json
    ↓
✅ 完成：挂单已创建，等待触发
```

**数据变化**：
- `orders.json`: 新增 pending 状态挂单
- `portfolio.json`: 无变化（未成交）
- `trades.json`: 无变化（未成交）

---

### 流程 4: 自动检查挂单触发（核心流程）

```
定时任务或用户主动调用
    ↓
check_pending_orders() 或 manage_orders({ action: "check" })
    ↓
OrderService.listPending()
    └─ 获取所有 status="pending" 的挂单
    ↓
并行获取实时价格
    ├─ A股: get_stock_realtime_price()
    └─ 港股: get_hk_stock_price()
    ↓
逐个检查触发条件
    ├─ 限价买入: currentPrice ≤ order.price → 触发
    ├─ 限价卖出: currentPrice ≥ order.price → 触发
    └─ 止损单:   currentPrice ≤ order.price → 触发
    ↓
如果触发 → 执行成交流程
    ├─ 1. 卖出前校验持仓 ✅ (已修复)
    │      if (side === "sell" && holding.quantity < quantity) → 报错
    │
    ├─ 2. 更新持仓
    │      if (side === "buy")
    │          PortfolioService.add(symbol, quantity, price)
    │      else
    │          PortfolioService.remove/update(symbol, quantity)
    │
    ├─ 3. 记录交易
    │      TradeService.add(date, symbol, side, quantity, price)
    │
    └─ 4. 更新挂单状态
           OrderService.fill(order_id, fill_price, fill_quantity)
           status: "pending" → "filled"
    ↓
✅ 完成：挂单已成交，持仓已更新，交易已记录
```

**数据变化**：
- `orders.json`: 挂单状态 `pending` → `filled`
- `portfolio.json`: 新增/更新/删除持仓
- `trades.json`: 新增交易记录

---

### 流程 5: 手动标记挂单成交

```
用户说："688981 的挂单已经成交了，成交价 46"
    ↓
manage_orders({ 
  action: "fill",
  order_id: "xxx",
  fill_price: 46.0
})
    ↓
OrderService.get(order_id)
    ├─ 检查挂单是否存在
    └─ 检查状态是否为 "pending"
    ↓
卖出前校验持仓 ✅ (已修复)
    if (side === "sell") {
      holding = PortfolioService.load().find(...)
      if (holding.quantity < fill_quantity) → 报错
    }
    ↓
执行成交（同流程 4）
    ├─ 更新持仓
    ├─ 记录交易
    └─ 更新挂单状态
    ↓
✅ 完成：挂单已标记成交
```

**数据变化**：同流程 4

---

### 流程 6: 撤销挂单

```
用户说："撤销 688981 的挂单"
    ↓
manage_orders({ 
  action: "cancel",
  order_id: "xxx",
  reason: "市场环境变化"
})
    ↓
OrderService.cancel(order_id, reason)
    ├─ 检查挂单状态是否为 "pending"
    ├─ 更新状态为 "cancelled"
    └─ 记录取消历史
    ↓
写入 orders.json
    ↓
✅ 完成：挂单已撤销
```

**数据变化**：
- `orders.json`: 挂单状态 `pending` → `cancelled`
- `portfolio.json`: 无变化
- `trades.json`: 无变化

---

### 流程 7: 查看持仓盈亏

```
用户说："看看我的持仓情况"
    ↓
manage_portfolio({ action: "get_with_pnl" })
    ↓
PortfolioService.getWithPnL()
    ├─ 读取 portfolio.json
    ├─ 并行获取所有持仓的实时价格
    └─ 计算每个持仓的盈亏
        current_price = 实时价格
        pnl_pct = (current_price - avg_cost) / avg_cost * 100
        pnl_amount = (current_price - avg_cost) * quantity
        market_value = current_price * quantity
    ↓
汇总统计
    total_cost = Σ(avg_cost * quantity)
    total_value = Σ(current_price * quantity)
    total_pnl = total_value - total_cost
    total_pnl_pct = total_pnl / total_cost * 100
    ↓
返回 PortfolioSnapshot
    ↓
✅ 完成：显示持仓盈亏
```

**数据变化**：无（只读操作）

---

## 🔐 安全机制（已修复）

### 1. 参数校验
```typescript
✅ quantity > 0
✅ price > 0
✅ avg_cost > 0
✅ fill_price > 0
✅ expires_in_minutes > 0
```

### 2. 持仓数量检查
```typescript
// manage_portfolio - sell 操作
if (holding.quantity < quantity) {
  return { error: "持仓不足: 需卖出 X 股，实际仅持有 Y 股" };
}

// manage_orders - fill 操作（卖出时）
if (order.side === "sell") {
  const heldQty = holding?.quantity ?? 0;
  if (heldQty < fillQty) {
    return "❌ 持仓不足: 需卖出 X 股，实际仅持有 Y 股";
  }
}

// check_pending_orders - 自动成交（卖出时）
if (order.side === "sell") {
  const heldQty = holding?.quantity ?? 0;
  if (heldQty < fillQuantity) {
    return { reason: "持仓不足: 需卖出 X 股，实际仅持有 Y 股" };
  }
}
```

### 3. 状态机保护
```typescript
// 只有 pending 状态的挂单才能成交或撤销
if (order.status !== "pending") {
  return "❌ 挂单当前状态为 ${status}，无法操作";
}
```

---

## 📁 数据文件关系

```
.pi-invest/
├── portfolio.json      # 当前持仓（实时状态）
│   └─ holdings[]       # 每个持仓的数量、成本价
│
├── trades.json         # 交易历史（不可变日志）
│   └─ trades[]         # 每笔买入/卖出记录
│
├── orders.json         # 挂单列表（状态机）
│   └─ orders[]         # pending/filled/cancelled/expired
│
└── reviews/            # 复盘报告
    └─ YYYY-MM-DD.md    # 每日复盘
```

**数据一致性**：
- `portfolio.json` = 当前真实持仓
- `trades.json` = 历史交易记录（可重建持仓）
- `orders.json` = 挂单状态追踪

---

## 🎯 典型使用场景

### 场景 1: 分批建仓
```
1. 创建挂单: 45元买入 300股
2. 创建挂单: 43元买入 300股
3. 创建挂单: 41元买入 400股
4. 定时检查: check_pending_orders()
5. 触发成交: 自动更新持仓
```

### 场景 2: 止损保护
```
1. 持有 600519 100股，成本 1800
2. 创建止损单: 1620元（-10%）卖出 100股
3. 定时检查: check_pending_orders()
4. 价格跌破 1620: 自动卖出，记录交易
```

### 场景 3: 分批止盈
```
1. 持有 688981 300股，成本 45
2. 创建挂单: 54元（+20%）卖出 100股
3. 创建挂单: 58.5元（+30%）卖出 100股
4. 创建挂单: 63元（+40%）卖出 100股
5. 定时检查: 逐步成交
```

---

## 🔄 状态转换图

```
挂单状态机:
pending ──[价格触发]──→ filled
pending ──[用户撤销]──→ cancelled
pending ──[超过期限]──→ expired
pending ──[部分成交]──→ partial ──[继续成交]──→ filled

持仓状态:
无持仓 ──[买入]──→ 有持仓 ──[加仓]──→ 持仓增加
有持仓 ──[减仓]──→ 持仓减少
有持仓 ──[清仓]──→ 无持仓
```

---

## ✅ 总结

### 核心服务
1. **PortfolioService** - 持仓管理（CRUD + 盈亏计算）
2. **TradeService** - 交易记录（不可变日志）
3. **OrderService** - 挂单管理（状态机）

### 核心工具
1. **manage_portfolio** - 手动买卖（立即成交）
2. **manage_orders** - 挂单管理（延迟成交）
3. **check_pending_orders** - 自动检查触发

### 数据流向
```
用户操作 → 工具调用 → 服务层 → JSON 文件
         ↓
      实时价格
         ↓
      触发检查
         ↓
      自动成交
```

### 安全保障
- ✅ 所有数量和金额必须 > 0
- ✅ 卖出前检查持仓数量
- ✅ 状态机保护（只能操作 pending 状态）
- ✅ 错误信息清晰，便于调试
