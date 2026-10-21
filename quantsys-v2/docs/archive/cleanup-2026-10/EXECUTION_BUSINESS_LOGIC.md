# 执行记录业务逻辑设计

## 数据表关系

### 1. signals（信号表）
- 策略生成的买入/卖出信号
- 关键字段：id, symbol, name, action (buy/sell), price, signal_date, status

### 2. signal_executions（执行记录表）
- 记录信号的执行情况
- 关键字段：id, signal_id, execution_date, execution_price, quantity, status, pnl, close_date, close_price

### 3. positions（持仓表）
- 记录当前持有的股票
- 关键字段：id, symbol, quantity, cost_basis, entry_date, status (open/closed)

## 业务流程

### 买入流程（Buy）

```
信号生成 → 创建执行记录 → 创建/更新持仓
```

**步骤：**
1. 策略生成买入信号（signals 表，action='buy'）
2. 创建执行记录（signal_executions 表，status='pending'）
3. 执行买入操作：
   - 更新执行记录状态：status='executed'
   - 检查是否已有该股票的持仓（status='open'）
     - 如果有：更新持仓数量和成本基础（加权平均）
     - 如果没有：创建新持仓记录
4. 记录执行日期和价格

**关键业务规则：**
- 买入可以多次执行（建仓、加仓）
- 每次买入都要更新持仓的成本基础（加权平均价格）
- cost_basis = (原持仓量 × 原成本 + 新买入量 × 新价格) / 总持仓量

### 卖出流程（Sell）

```
信号生成 → 检查持仓 → 创建执行记录 → 更新持仓 → 计算盈亏
```

**步骤：**
1. 策略生成卖出信号（signals 表，action='sell'）
2. **检查持仓（关键步骤）**：
   - 查询是否有该股票的持仓（status='open'）
   - 检查持仓数量是否足够
   - 如果没有持仓或数量不足，拒绝创建执行记录
3. 创建执行记录（signal_executions 表，status='pending'）
4. 执行卖出操作：
   - 更新执行记录状态：status='executed'
   - 记录平仓日期和价格：close_date, close_price
   - 计算盈亏：pnl = (close_price - cost_basis) × quantity - commission
   - 更新持仓：
     - 减少持仓数量
     - 如果全部卖出：更新持仓状态为 'closed'
     - 如果部分卖出：保持 'open' 状态
5. 更新相关统计数据

**关键业务规则：**
- **卖出前必须检查持仓**（防止无持仓卖出）
- 卖出数量不能超过持仓数量
- 必须计算并记录盈亏
- 全部卖出后，持仓状态改为 'closed'

## 状态流转

### signal_executions.status
- `pending`: 待执行（刚创建）
- `executed`: 已执行（买入/卖出完成）
- `cancelled`: 已取消（手动取消或条件不满足）
- `expired`: 已过期（超过有效期）

### positions.status
- `open`: 持仓中（有股票）
- `closed`: 已平仓（全部卖出）

## 盈亏计算

### 单次卖出盈亏
```
pnl = (close_price - cost_basis) × quantity - commission
```

### 持仓未实现盈亏
```
unrealized_pnl = (current_price - cost_basis) × quantity
unrealized_pnl_pct = (current_price - cost_basis) / cost_basis × 100%
```

## API 端点业务逻辑

### POST /api/executions（创建执行记录）
```python
def create_execution(signal_id, quantity):
    # 1. 查询信号
    signal = get_signal(signal_id)
    
    # 2. 如果是卖出，检查持仓
    if signal.action == 'sell':
        position = get_open_position(signal.symbol)
        if not position:
            raise BusinessError("没有持仓，无法卖出")
        if position.quantity < quantity:
            raise BusinessError(f"持仓不足，当前持仓：{position.quantity}")
    
    # 3. 创建执行记录
    execution = create_execution_record(
        signal_id=signal_id,
        execution_date=today,
        execution_price=signal.price,
        quantity=quantity,
        status='pending'
    )
    
    return execution
```

### PUT /api/executions/:id/execute（执行买入/卖出）
```python
def execute_trade(execution_id):
    # 1. 查询执行记录和信号
    execution = get_execution(execution_id)
    signal = get_signal(execution.signal_id)
    
    # 2. 根据 action 执行不同逻辑
    if signal.action == 'buy':
        # 买入逻辑
        position = get_open_position(signal.symbol)
        if position:
            # 加仓：更新持仓
            new_quantity = position.quantity + execution.quantity
            new_cost_basis = (
                position.quantity * position.cost_basis +
                execution.quantity * execution.execution_price
            ) / new_quantity
            update_position(position.id, {
                'quantity': new_quantity,
                'cost_basis': new_cost_basis
            })
        else:
            # 建仓：创建持仓
            create_position({
                'symbol': signal.symbol,
                'name': signal.name,
                'quantity': execution.quantity,
                'cost_basis': execution.execution_price,
                'entry_date': execution.execution_date,
                'status': 'open'
            })
        
        # 更新执行记录状态
        update_execution(execution_id, {'status': 'executed'})
    
    elif signal.action == 'sell':
        # 卖出逻辑
        position = get_open_position(signal.symbol)
        if not position:
            raise BusinessError("没有持仓，无法卖出")
        
        # 计算盈亏
        pnl = (execution.execution_price - position.cost_basis) * execution.quantity - execution.commission
        
        # 更新执行记录
        update_execution(execution_id, {
            'status': 'executed',
            'close_date': today,
            'close_price': execution.execution_price,
            'pnl': pnl
        })
        
        # 更新持仓
        new_quantity = position.quantity - execution.quantity
        if new_quantity == 0:
            # 全部卖出
            update_position(position.id, {'status': 'closed'})
        else:
            # 部分卖出
            update_position(position.id, {'quantity': new_quantity})
    
    return execution
```

## 数据一致性保证

1. **事务处理**：买入/卖出操作必须在事务中执行，确保执行记录和持仓数据的一致性
2. **并发控制**：使用数据库锁防止并发卖出导致的超卖问题
3. **状态校验**：每次操作前检查记录状态，防止重复执行
4. **回滚机制**：操作失败时回滚所有变更

## 待实现功能

1. ✅ 删除错误的执行记录数据
2. ⏳ 实现持仓检查逻辑（卖出前检查）
3. ⏳ 实现买入后创建/更新持仓
4. ⏳ 实现卖出后更新持仓和计算盈亏
5. ⏳ 添加事务处理和错误处理
6. ⏳ 测试完整的买卖流程
