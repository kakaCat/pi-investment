# 订单-持仓-交易记录业务流程梳理

## 当前问题诊断

根据截图和数据库查询，发现以下问题：

### 1. 数据不一致问题

**订单表（quant.orders）**：
- 显示 3 笔已成交的买入订单（action=buy, status=filled, price=1400, quantity=100）
- 1 笔已取消的买入订单（action=buy, status=cancelled, price=1500, quantity=100）
- **问题**：`signal_id` 字段全部为空（NULL），无法追溯信号来源

**持仓表（quant.positions）**：
- 只有 601398（工商银行）的持仓记录（500股，成本5.8元）
- **问题**：没有 600000.SH（浦发银行）的持仓记录，但订单表显示有 3 笔买入成交

**前端截图显示**：
- 订单表：600000.SH 有 3 笔卖出成交（¥1400.00）+ 1 笔卖出已取消（¥1500.00）
- 交易记录表：600000.SH 有 3 笔买入记录（¥1450.00，关联订单 1/2/3）
- 持仓表：只显示 601398 持仓

**结论**：
1. 前端显示的数据与数据库不一致（可能是缓存或前端状态问题）
2. 订单成交后没有正确更新持仓表
3. 信号追踪链路断裂（signal_id 为空）

---

## 完整业务流程设计

### 核心数据流

```
策略执行 → 生成信号 → 创建订单 → 订单成交 → 更新持仓 → 记录交易
   ↓          ↓          ↓          ↓          ↓          ↓
signals → signal_id → orders → positions → trades → strategy_performance
```

### 1. 策略生成信号（Strategy → Signal）

**表**：`quant.signals`

**字段**：
- `id` — 信号ID（主键）
- `signal_date` — 信号日期
- `symbol` — 股票代码
- `name` — 股票名称
- `action` — 操作类型（buy/sell）
- `action_type` — 操作类型代码
- `strategy_id` — 策略ID（关键：追溯来源）
- `price` — 建议价格
- `reason` — 信号理由
- `confidence` — 信号置信度
- `indicators` — 技术指标（JSONB）
- `status` — 信号状态（pending/approved/rejected/executed）

**流程**：
1. 策略引擎运行策略代码
2. 生成买入/卖出信号
3. 写入 `quant.signals` 表
4. 返回 `signal_id`

**示例**：
```sql
INSERT INTO quant.signals (
    signal_date, symbol, name, action, action_type, strategy_id,
    price, reason, confidence, status
) VALUES (
    '2026-05-29', '600000.SH', '浦发银行', 'buy', 1, 'v15_macd_cross',
    1450.00, 'MACD金叉 + RSI超卖', 0.85, 'pending'
) RETURNING id;
-- 返回 signal_id = 123
```

---

### 2. 信号转订单（Signal → Order）

**表**：`quant.orders`

**字段**：
- `id` — 订单ID（主键）
- `symbol` — 股票代码
- `name` — 股票名称
- `order_type` — 订单类型（limit/market/stop_loss）
- `action` — 操作类型（buy/sell）
- `price` — 订单价格
- `quantity` — 订单数量
- `status` — 订单状态（pending/filled/cancelled/expired）
- **`signal_id`** — 关联信号ID（外键，关键字段）
- `reason` — 订单理由
- `created_at` — 创建时间
- `expires_at` — 过期时间

**流程**：
1. Agent 审核信号（可选）
2. 根据信号创建订单
3. **必须关联 `signal_id`**
4. 写入 `quant.orders` 表

**示例**：
```sql
INSERT INTO quant.orders (
    symbol, name, order_type, action, price, quantity,
    status, signal_id, reason, created_at
) VALUES (
    '600000.SH', '浦发银行', 'limit', 'buy', 1450.00, 100,
    'pending', 123, 'MACD金叉 + RSI超卖', NOW()
) RETURNING id;
-- 返回 order_id = 456
```

**当前问题**：
- ❌ `signal_id` 字段为空
- ❌ 无法追溯订单来源策略
- ❌ 无法统计策略表现

---

### 3. 订单成交（Order → Position + Trade）

**流程**：
1. 监控订单状态（定时任务或实时监控）
2. 检查市场价格是否触发订单
3. 订单成交时：
   - 更新订单状态：`status = 'filled'`
   - 更新持仓表：`quant.positions`
   - 记录交易：`quant.signal_executions` 或本地 `trades.json`
   - **关联 `signal_id` 和 `order_id`**

#### 3.1 买入成交 → 更新持仓

**场景 A：首次建仓**
```sql
-- 1. 更新订单状态
UPDATE quant.orders
SET status = 'filled',
    filled_quantity = 100,
    avg_filled_price = 1450.00,
    executed_at = NOW()
WHERE id = 456;

-- 2. 创建持仓记录
INSERT INTO quant.positions (
    account_id, symbol, quantity, cost_basis,
    entry_date, entry_reason, status
) VALUES (
    'default', '600000.SH', 100, 1450.00,
    '2026-05-29', 'Signal 123: MACD金叉 + RSI超卖', 'open'
);

-- 3. 记录交易
INSERT INTO quant.signal_executions (
    signal_id, execution_date, execution_price, quantity,
    commission, status
) VALUES (
    123, '2026-05-29', 1450.00, 100, 43.50, 'executed'
);
```

**场景 B：加仓**
```sql
-- 1. 更新订单状态（同上）

-- 2. 更新持仓（加权平均成本）
UPDATE quant.positions
SET quantity = quantity + 100,
    cost_basis = (quantity * cost_basis + 100 * 1450.00) / (quantity + 100),
    updated_at = NOW()
WHERE symbol = '600000.SH' AND status = 'open';

-- 3. 记录交易（同上）
```

#### 3.2 卖出成交 → 更新持仓 + 计算盈亏

**场景 A：部分卖出**
```sql
-- 1. 更新订单状态
UPDATE quant.orders
SET status = 'filled',
    filled_quantity = 50,
    avg_filled_price = 1500.00,
    executed_at = NOW()
WHERE id = 789;

-- 2. 查询持仓成本
SELECT cost_basis FROM quant.positions
WHERE symbol = '600000.SH' AND status = 'open';
-- 假设 cost_basis = 1450.00

-- 3. 计算盈亏
-- pnl = (卖出价 - 成本价) * 数量 - 手续费
-- pnl = (1500 - 1450) * 50 - 37.50 = 2462.50

-- 4. 更新持仓
UPDATE quant.positions
SET quantity = quantity - 50,
    updated_at = NOW()
WHERE symbol = '600000.SH' AND status = 'open';

-- 5. 记录交易（含盈亏）
INSERT INTO quant.signal_executions (
    signal_id, execution_date, execution_price, quantity,
    commission, status, pnl, close_date, close_price
) VALUES (
    124, '2026-05-29', 1500.00, 50, 37.50, 'executed',
    2462.50, '2026-05-29', 1500.00
);

-- 6. 记录策略表现（P2 完成）
INSERT INTO quant.strategy_performance (
    strategy_id, symbol, entry_date, entry_price,
    exit_date, exit_price, quantity, pnl_pct, holding_days, source
) VALUES (
    'v15_macd_cross', '600000.SH', '2026-05-29', 1450.00,
    '2026-05-29', 1500.00, 50, 3.45, 0, 'live'
);
```

**场景 B：清仓**
```sql
-- 1-5 同上

-- 6. 关闭持仓
UPDATE quant.positions
SET status = 'closed',
    updated_at = NOW()
WHERE symbol = '600000.SH' AND status = 'open';
```

---

### 4. 数据追踪链路

**完整追踪链**：
```
strategy_id → signal_id → order_id → execution_id → position_id
     ↓            ↓           ↓            ↓             ↓
  策略代码      信号表      订单表      交易记录表      持仓表
```

**关键关联**：
1. `quant.orders.signal_id` → `quant.signals.id`
2. `quant.signal_executions.signal_id` → `quant.signals.id`
3. `quant.signals.strategy_id` → 策略代码
4. `quant.strategy_performance.strategy_id` → 策略代码

**查询示例**：
```sql
-- 查询某个订单的完整追踪链
SELECT
    s.strategy_id,
    s.signal_date,
    s.action,
    s.reason AS signal_reason,
    o.id AS order_id,
    o.status AS order_status,
    o.price AS order_price,
    o.quantity AS order_quantity,
    se.execution_price,
    se.pnl,
    p.quantity AS current_position
FROM quant.orders o
LEFT JOIN quant.signals s ON o.signal_id = s.id
LEFT JOIN quant.signal_executions se ON se.signal_id = s.id
LEFT JOIN quant.positions p ON p.symbol = o.symbol AND p.status = 'open'
WHERE o.id = 456;
```

---

## 当前系统问题总结

### 1. 信号追踪缺失

**问题**：
- `quant.orders.signal_id` 字段为空
- 无法追溯订单来源策略
- 无法统计策略表现

**影响**：
- 无法回答"这个订单是哪个策略生成的？"
- 无法统计"v15_macd_cross 策略的胜率是多少？"
- 无法生成经验条目（ExperienceAccumulator 依赖 strategy_id）

**修复方案**：
1. 创建订单时必须传入 `signal_id`
2. 修改 `OrderService.create()` 方法，添加 `signal_id` 参数
3. 修改 `trade_manage_orders` 工具，从信号创建订单时关联 `signal_id`

### 2. 订单-持仓不同步

**问题**：
- 订单表显示 3 笔买入成交
- 持仓表没有对应持仓记录

**可能原因**：
1. 订单成交后没有调用持仓更新逻辑
2. 持仓更新失败但订单状态已更新
3. 使用了不同的数据源（本地 JSON vs PostgreSQL）

**修复方案**：
1. 使用事务确保订单成交和持仓更新的原子性
2. 统一数据源（全部使用 PostgreSQL）
3. 添加数据一致性检查任务

### 3. 时间戳缺失

**问题**：
- 前端显示订单创建时间和过期时间为 "--"

**可能原因**：
1. 前端格式化问题
2. 数据库字段为 NULL
3. 前端和后端时间格式不匹配

**修复方案**：
1. 检查前端时间格式化逻辑
2. 确保数据库字段有默认值（`created_at DEFAULT NOW()`）
3. 统一使用 ISO 8601 格式

### 4. 交易理由缺失

**问题**：
- 交易记录表的"理由"字段为空

**修复方案**：
1. 从信号表复制 `reason` 字段到订单表
2. 订单成交时将 `reason` 传递到交易记录
3. 格式：`"Signal {signal_id}: {signal_reason}"`

---

## 推荐的数据架构

### 方案 A：全部使用 PostgreSQL（推荐）

**优点**：
- 数据一致性有保障（事务、外键约束）
- 支持复杂查询和统计
- 支持并发访问
- 易于备份和恢复

**缺点**：
- 需要数据库连接
- 本地开发需要启动 PostgreSQL

**实现**：
1. 订单：`quant.orders`
2. 持仓：`quant.positions`
3. 交易记录：`quant.signal_executions`
4. 信号：`quant.signals`
5. 策略表现：`quant.strategy_performance`

### 方案 B：混合模式（当前）

**优点**：
- 本地文件易于调试
- 无需数据库连接

**缺点**：
- 数据一致性难以保证
- 并发访问有风险
- 查询能力有限

**实现**：
1. 订单：`.pi-invest/orders.json`（本地）
2. 持仓：`quant.positions`（PostgreSQL）
3. 交易记录：`.pi-invest/trades.json`（本地）或 `quant.signal_executions`（PostgreSQL）
4. 信号：`quant.signals`（PostgreSQL）

**问题**：
- 本地 JSON 和 PostgreSQL 数据不同步
- 无法使用外键约束
- 事务支持有限

---

## 修复计划

### Phase 1：修复信号追踪（高优先级）

**目标**：确保所有订单都关联 `signal_id`

**步骤**：
1. 修改 `OrderService.create()` 方法，添加 `signal_id` 参数（必填）
2. 修改 `trade_manage_orders` 工具，从信号创建订单时传入 `signal_id`
3. 添加数据库约束：`ALTER TABLE quant.orders ADD CONSTRAINT orders_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES quant.signals(id);`
4. 回填历史数据（如果可能）

### Phase 2：修复订单-持仓同步（高优先级）

**目标**：订单成交后自动更新持仓

**步骤**：
1. 使用 PostgreSQL 事务确保原子性
2. 订单成交时调用 `PositionRepository` 更新持仓
3. 添加数据一致性检查任务（每日运行）
4. 修复当前不一致的数据

### Phase 3：统一数据源（中优先级）

**目标**：全部使用 PostgreSQL

**步骤**：
1. 迁移 `.pi-invest/orders.json` 到 `quant.orders`
2. 迁移 `.pi-invest/trades.json` 到 `quant.signal_executions`
3. 删除本地 JSON 文件
4. 更新所有代码引用

### Phase 4：完善追踪链路（中优先级）

**目标**：实现完整的策略表现统计

**步骤**：
1. 确保 `quant.strategy_performance` 表正确记录
2. 实现 `ExperienceAccumulator` 自动生成经验
3. 添加策略表现仪表板
4. 添加信号-订单-持仓-交易的完整追踪查询

---

## 代码示例

### 1. 创建订单时关联信号

```typescript
// src/services/order-service.ts
create(params: {
  symbol: string;
  name: string;
  side: OrderSide;
  type: OrderType;
  price: number;
  quantity: number;
  market: "A" | "HK";
  signal_id?: number;  // 新增：信号ID（必填）
  notes?: string;
  expires_in_minutes?: number;
}): PendingOrder {
  // 验证 signal_id
  if (!params.signal_id) {
    throw new Error("signal_id 是必填字段");
  }

  // ... 其他逻辑
}
```

### 2. 订单成交时更新持仓（事务）

```typescript
// src/services/order-service.ts
async fillOrder(
  orderId: string,
  fillPrice: number,
  fillQuantity?: number,
): Promise<FillOrderResult> {
  // 开始事务
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // 1. 更新订单状态
    await client.query(
      'UPDATE quant.orders SET status = $1, filled_quantity = $2, avg_filled_price = $3, executed_at = NOW() WHERE id = $4',
      ['filled', fillQuantity, fillPrice, orderId]
    );

    // 2. 更新持仓
    if (order.side === 'buy') {
      // 买入逻辑
      await client.query(
        'INSERT INTO quant.positions (symbol, quantity, cost_basis, entry_date, entry_reason, status) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (symbol, status) DO UPDATE SET quantity = positions.quantity + $2, cost_basis = (positions.quantity * positions.cost_basis + $2 * $3) / (positions.quantity + $2)',
        [order.symbol, fillQuantity, fillPrice, new Date(), `Signal ${order.signal_id}`, 'open']
      );
    } else {
      // 卖出逻辑
      await client.query(
        'UPDATE quant.positions SET quantity = quantity - $1 WHERE symbol = $2 AND status = $3',
        [fillQuantity, order.symbol, 'open']
      );
    }

    // 3. 记录交易
    await client.query(
      'INSERT INTO quant.signal_executions (signal_id, execution_date, execution_price, quantity, commission, status) VALUES ($1, $2, $3, $4, $5, $6)',
      [order.signal_id, new Date(), fillPrice, fillQuantity, commission, 'executed']
    );

    await client.query('COMMIT');
    return { success: true, ... };
  } catch (e) {
    await client.query('ROLLBACK');
    return { success: false, error: e.message };
  } finally {
    client.release();
  }
}
```

### 3. 查询完整追踪链

```typescript
// src/services/order-service.ts
async getOrderTrackingChain(orderId: string): Promise<OrderTrackingChain> {
  const query = `
    SELECT
      s.id AS signal_id,
      s.strategy_id,
      s.signal_date,
      s.action AS signal_action,
      s.reason AS signal_reason,
      s.confidence,
      o.id AS order_id,
      o.status AS order_status,
      o.price AS order_price,
      o.quantity AS order_quantity,
      o.created_at AS order_created_at,
      se.id AS execution_id,
      se.execution_price,
      se.pnl,
      se.execution_date,
      p.id AS position_id,
      p.quantity AS current_position,
      p.cost_basis,
      sp.win_rate,
      sp.avg_pnl_pct
    FROM quant.orders o
    LEFT JOIN quant.signals s ON o.signal_id = s.id
    LEFT JOIN quant.signal_executions se ON se.signal_id = s.id
    LEFT JOIN quant.positions p ON p.symbol = o.symbol AND p.status = 'open'
    LEFT JOIN quant.strategy_performance sp ON sp.strategy_id = s.strategy_id
    WHERE o.id = $1
  `;

  const result = await pool.query(query, [orderId]);
  return result.rows[0];
}
```

---

## 总结

当前系统的核心问题是**信号追踪链路断裂**和**订单-持仓数据不同步**。

**关键修复点**：
1. ✅ 确保所有订单都关联 `signal_id`
2. ✅ 使用事务确保订单成交和持仓更新的原子性
3. ✅ 统一数据源（推荐全部使用 PostgreSQL）
4. ✅ 实现完整的追踪查询

**预期效果**：
- 可以追溯每个订单的来源策略
- 可以统计每个策略的表现（胜率、平均收益）
- 可以自动生成经验条目
- 数据一致性有保障
