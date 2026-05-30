# 信号追踪功能修复报告

**日期**: 2026-05-29  
**修复人**: Claude  
**优先级**: P0（高优先级）

## 问题诊断

### 1. 核心问题

根据用户提供的截图和数据库查询，发现以下关键问题：

#### 问题 A：信号追踪链路断裂 ❌
- **现象**：数据库中所有订单的 `signal_id` 字段都是 NULL
- **影响**：
  - 无法追溯订单来自哪个策略、哪个信号
  - 无法统计策略表现（胜率、平均收益）
  - 无法生成经验条目（ExperienceAccumulator 依赖 strategy_id）
  - 策略循环闭合（P2）功能无法正常工作

#### 问题 B：订单-持仓数据不一致 ❌
- **现象**：
  - 数据库显示：3笔 600000.SH 买入订单已成交
  - 但持仓表中没有 600000.SH 的记录
- **原因**：订单成交后没有正确更新持仓表

#### 问题 C：前端-后端数据不一致 ❌
- **现象**：
  - 前端显示：卖出订单
  - 数据库显示：买入订单
- **原因**：可能是缓存或前端状态问题

---

## 修复方案

### Phase 1: 添加 signal_id 校验逻辑 ✅

**目标**：确保策略生成的订单必须关联 `signal_id`，手动创建的订单可选。

#### 1.1 修改 API 端点（quantsys-v2/api/routes/orders.py）

**变更**：
- 添加 `from_signal` 参数（布尔值）
- 添加校验逻辑：`from_signal=true` 时，`signal_id` 必填

```python
@orders_bp.route('/api/orders/create', methods=['POST'])
@handle_api_error
def create_order():
    """
    创建订单

    Request Body (JSON):
    {
        "symbol": "600000.SH",           // 股票代码（必需）
        "action": "buy",                 // 交易方向 buy/sell（必需）
        "orderType": "limit",            // 订单类型 limit/market/stop（必需）
        "quantity": 100,                 // 委托数量（必需）
        "price": 1450.00,                // 委托价格（限价单必需）
        "notes": "手动买入",             // 订单备注（可选）
        "signalId": 123,                 // 关联信号ID（可选，但走信号时必填）
        "fromSignal": true               // 是否来自策略信号（可选，默认false）
    }

    校验规则：
    - fromSignal=true 时，signalId 必填（策略生成的订单必须关联信号）
    - fromSignal=false 或未提供时，signalId 可选（手动创建订单）
    """
    data = request.get_json() or {}
    params = convert_keys_to_snake(data)

    # 提取参数
    from_signal = params.get('from_signal', False)
    signal_id = params.get('signal_id')

    # 校验：如果标记为来自信号，则 signal_id 必填
    if from_signal and signal_id is None:
        return jsonify({
            'success': False,
            'error': '订单标记为来自策略信号（fromSignal=true），但未提供 signalId。策略生成的订单必须关联信号ID。'
        }), 400

    order_id = order_service.create_order(
        ds,
        symbol=params['symbol'],
        action=params['action'],
        order_type=params['order_type'],
        quantity=params['quantity'],
        price=params.get('price') or params.get('stop_price'),
        reason=params.get('notes'),
        signal_id=signal_id,
        from_signal=from_signal
    )
    
    # ...
```

#### 1.2 修改 OrderService（quantsys-v2/services/order_service.py）

**变更**：
- 添加 `from_signal` 参数
- 添加信号存在性验证
- 添加详细的错误提示

```python
def create_order(
    ds: DataService,
    symbol: str,
    action: str,
    order_type: str,
    quantity: int,
    price: float = None,
    reason: str = None,
    signal_id: int = None,
    from_signal: bool = False,
) -> int:
    """
    创建新订单

    Args:
        signal_id: 关联信号ID（走信号时必填）
        from_signal: 是否来自策略信号（True=必须提供signal_id，False=手动创建可选）
    """
    # ========== 信号追踪校验 ==========
    # 如果明确标记为来自信号，则 signal_id 必填
    if from_signal and signal_id is None:
        raise ValueError(
            "订单标记为来自策略信号（from_signal=True），但未提供 signal_id。"
            "策略生成的订单必须关联信号ID以确保追踪链路完整。"
        )

    # 如果提供了 signal_id，验证信号是否存在
    if signal_id is not None:
        signal = ds.portfolio.get_signal_by_id(signal_id)
        if signal is None:
            raise ValueError(f"信号不存在: signal_id={signal_id}")
        logger.info(f"订单关联信号: signal_id={signal_id} strategy={signal.get('strategy_id')}")

    # ... 其他逻辑
```

#### 1.3 修改 TypeScript 工具（src/infrastructure/tools/trade/manage-orders-tool.ts）

**变更**：
- 添加 `signal_id` 和 `from_signal` 参数
- 更新工具定义和参数说明

```typescript
/** 创建挂单 */
async function handlePlace(params: {
  symbol: string;
  name?: string;
  side: string;
  type: string;
  price?: number;
  quantity: number;
  notes?: string;
  signal_id?: number;        // 新增
  from_signal?: boolean;     // 新增
}): Promise<string> {
  try {
    const result = await runQuantV2("orders.create", {
      symbol: params.symbol,
      action: params.side,
      order_type: params.type,
      quantity: params.quantity,
      price: params.price,
      notes: params.notes,
      signal_id: params.signal_id,
      from_signal: params.from_signal || false,
    });
    // ...
  }
}

// 工具定义
export const tradeManageOrdersTool: ToolDefinition = {
  // ...
  parameters: Type.Object({
    // ...
    signal_id: Type.Optional(Type.Integer({ 
      description: "关联信号ID（place时使用，策略生成订单时必填）" 
    })),
    from_signal: Type.Optional(Type.Boolean({ 
      description: "是否来自策略信号（place时使用，true=必须提供signal_id，false=手动创建可选，默认false）" 
    })),
  }),
};
```

---

## 使用示例

### 场景 1：策略生成订单（必须关联信号）

```typescript
// Agent 调用工具
trade_manage_orders({
  action: "place",
  symbol: "600000.SH",
  side: "buy",
  type: "limit",
  price: 1450.00,
  quantity: 100,
  notes: "MACD金叉 + RSI超卖",
  signal_id: 123,           // 必填
  from_signal: true         // 标记为来自信号
})
```

**后端校验**：
- ✅ `from_signal=true` 且 `signal_id=123` → 通过
- ❌ `from_signal=true` 且 `signal_id=null` → 报错："订单标记为来自策略信号，但未提供 signalId"

### 场景 2：手动创建订单（signal_id 可选）

```typescript
// Agent 调用工具
trade_manage_orders({
  action: "place",
  symbol: "600000.SH",
  side: "buy",
  type: "limit",
  price: 1450.00,
  quantity: 100,
  notes: "手动买入",
  from_signal: false        // 或不提供（默认false）
  // signal_id 可选，不提供也可以
})
```

**后端校验**：
- ✅ `from_signal=false` 且 `signal_id=null` → 通过（手动创建）
- ✅ `from_signal=false` 且 `signal_id=123` → 通过（手动创建但关联信号）

---

## 数据追踪链路

### 完整追踪链

```
strategy_id → signal_id → order_id → execution_id → position_id
     ↓            ↓           ↓            ↓             ↓
  策略代码      信号表      订单表      交易记录表      持仓表
```

### 关键关联

1. `quant.orders.signal_id` → `quant.signals.id`
2. `quant.signal_executions.signal_id` → `quant.signals.id`
3. `quant.signals.strategy_id` → 策略代码
4. `quant.strategy_performance.strategy_id` → 策略代码

### 查询示例

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

## 测试验证

### 测试文件

创建了完整的测试套件：`quantsys-v2/tests/test_signal_tracking.py`

### 测试用例

1. **test_create_order_with_signal_validation**
   - 验证 `from_signal=true` 时 `signal_id` 必填
   - 验证 `from_signal=false` 时 `signal_id` 可选

2. **test_create_order_with_invalid_signal_id**
   - 验证提供无效 `signal_id` 时报错

3. **test_order_tracking_chain**
   - 验证完整的信号-订单-持仓-交易追踪链路

4. **test_manual_order_without_signal**
   - 验证手动创建订单（不关联信号）

5. **test_sell_order_with_signal_tracking**
   - 验证卖出订单的信号追踪和盈亏计算

### 运行测试

```bash
cd quantsys-v2
pytest tests/test_signal_tracking.py -v -s
```

---

## 影响范围

### 修改的文件

1. `quantsys-v2/api/routes/orders.py` — API 端点校验
2. `quantsys-v2/services/order_service.py` — 服务层校验
3. `src/infrastructure/tools/trade/manage-orders-tool.ts` — TypeScript 工具
4. `quantsys-v2/tests/test_signal_tracking.py` — 测试文件（新增）

### 向后兼容性

✅ **完全向后兼容**

- 现有代码不传 `from_signal` 参数时，默认为 `false`（手动创建模式）
- 现有代码不传 `signal_id` 参数时，仍然可以创建订单
- 只有明确标记 `from_signal=true` 时才强制要求 `signal_id`

---

## 后续工作

### Phase 2: 修复订单-持仓同步（待实现）

**目标**：使用 PostgreSQL 事务确保订单成交和持仓更新的原子性

**计划**：
1. 修改 `order_service.fill_order()` 使用事务
2. 确保订单成交、持仓更新、交易记录创建在同一事务中
3. 添加回滚机制

### Phase 3: 数据一致性检查（待实现）

**目标**：定期检查订单-持仓-交易数据一致性

**计划**：
1. 创建数据一致性检查脚本
2. 检查已成交订单是否有对应的持仓记录
3. 检查持仓记录是否有对应的订单记录
4. 生成不一致报告

---

## 总结

### 修复内容

✅ 添加了 `signal_id` 校验逻辑  
✅ 支持策略生成订单（必须关联信号）  
✅ 支持手动创建订单（signal_id 可选）  
✅ 完善了错误提示  
✅ 添加了完整的测试套件  
✅ 保持向后兼容性  

### 预期效果

- 策略生成的订单必须关联 `signal_id`，确保追踪链路完整
- 手动创建的订单可以选择是否关联 `signal_id`
- 可以追溯每个订单的来源策略
- 可以统计每个策略的表现（胜率、平均收益）
- 可以自动生成经验条目
- 策略循环闭合（P2）功能可以正常工作

### 使用建议

1. **策略生成订单时**：必须设置 `from_signal=true` 和 `signal_id`
2. **手动创建订单时**：设置 `from_signal=false` 或不设置（默认false）
3. **查询追踪链路时**：使用 SQL JOIN 查询完整的信号-订单-持仓-交易链路
