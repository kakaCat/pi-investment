# P2 阶段 2 - Day 2 重构策略

**日期**: 2026-09-01  
**任务**: 重构 AccountTradingService

---

## 重构分析

### 当前 execute_trade 复杂度

**代码行数**: ~240 行  
**职责混杂**:
1. 参数校验和标准化 (应用层 ✅)
2. 交易时段校验 (业务规则 ❌)
3. 每日限额校验 (业务规则 ❌)
4. 价格获取 (基础设施 ✅)
5. 费用计算 (业务规则 ❌)
6. 资金校验 (业务规则 ❌)
7. 仓位校验 (业务规则 ❌)
8. 订单创建 (调用仓储 ❌)
9. 成交记录 (直接操作 ❌)
10. 持仓更新 (直接操作 ❌)
11. 资金更新 (直接操作 ❌)
12. 账户快照 (直接操作 ❌)
13. 决策记录 (应用层 ✅)

**问题**:
- 240 行单一方法
- 业务规则在应用层
- 直接操作仓储
- 难以测试

---

## 重构方案

### 方案选择：渐进式重构

**理由**:
1. execute_trade 被多处调用，破坏性重构风险高
2. 需要保持完全向后兼容
3. 有复杂的事务控制和锁机制

### 重构步骤

#### Step 1: 保留原有方法，标记为 legacy

```python
def execute_trade_legacy(self, ...):
    """原有实现（保持不变）"""
    # 完整的 240 行实现
    pass
```

#### Step 2: 创建新方法使用领域服务

```python
def execute_trade(self, ...):
    """重构版：调用领域服务"""
    
    # 1. 标准化参数
    action = normalize_action(action)
    
    # 2. 挂单处理
    if execute_at == 'market_open' and not in_window:
        return self._create_pending_order(...)
    
    # 3. 获取价格
    price = price or self._get_price(symbol)
    
    # 4. 交易护栏（领域服务）
    fees = self.trade_guard.validate_trade_request(
        account_name, action, symbol, shares, price,
        max_positions, allow_off_hours
    )
    
    # 5. 事务执行
    with self.repo.transaction():
        # 创建订单（领域服务）
        order = self.order_service.create_order(...)
        
        # 成交订单（领域服务）
        trade = self.order_service.fill_order(
            order.id, price, shares
        )
        
        # 保存成交记录
        trade_id = self.repo.add_trade(trade)
        
        # 账户快照
        self._update_account_snapshot(account_name)
    
    # 6. 决策记录
    self._auto_record_decision(...)
    
    return result
```

#### Step 3: 测试验证

1. 单元测试新方法
2. 集成测试端到端流程
3. 对比新旧方法结果一致性

#### Step 4: 切换

1. 默认使用新方法
2. 保留 legacy 方法作为 fallback
3. 监控生产表现

---

## 问题：事务控制

### 当前实现的复杂性

```python
try:
    # 行级锁
    locked_account = repo.get_account_for_update(account_name)
    
    # 锁内重读持仓
    repo.session.expire_all()
    positions = repo.get_all_positions(account_name)
    
    # 复核资金/持仓
    if action == 'BUY':
        if total_cost > locked_account.cash_available:
            raise TradingError(...)
    
    # 创建订单、成交、更新持仓、更新资金、快照
    repo.session.commit()
except:
    repo.session.rollback()
```

**特点**:
- 显式行级锁（防并发）
- 锁内复核（防 TOCTOU）
- 手动事务管理

### 重构后如何处理？

**问题**: OrderService.fill_order() 内部调用 AccountService 和 PositionService，它们也会操作数据库，谁来管理事务？

**选项**:

#### 选项 A: 事务在应用层

```python
# AccountTradingService
with self.repo.transaction():
    locked_account = self.repo.get_account_for_update(account_name)
    
    order = self.order_service.create_order(...)
    trade = self.order_service.fill_order(order.id, price, shares, commit=False)
    trade_id = self.repo.add_trade(trade, commit=False)
    
    self.repo.session.commit()
```

**问题**: OrderService.fill_order() 内部调用的 AccountService.deduct_funds() 会立即 commit，破坏事务边界。

#### 选项 B: 领域服务支持 commit 参数

```python
# OrderService.fill_order()
def fill_order(self, ..., commit=True):
    # 更新订单
    # 更新持仓
    self.position_service.reduce_shares(..., commit=False)
    # 更新资金
    self.account_service.deduct_funds(..., commit=False)
    
    if commit:
        self.repo.session.commit()
```

**缺点**: commit 参数污染领域层接口

#### 选项 C: 使用工作单元模式

```python
class UnitOfWork:
    def __enter__(self):
        self.session.begin()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
```

**优点**: 符合 DDD，但需要大量重构

---

## 决策：采用方案 B（短期）

**理由**:
1. 最小变更
2. 保持向后兼容
3. commit 参数已在现有代码中使用

**实施**:
1. OrderService.fill_order() 添加 commit=True 参数
2. AccountTradingService 传递 commit=False
3. 在应用层手动 commit

**长期目标**: 迁移到工作单元模式（P3）

---

## Task 2.1 实施计划

### 子任务

1. ✅ TradeGuardService 已完成
2. ✅ OrderService.fill_order() 已增强
3. ⏳ 修改 AccountService.deduct_funds/add_funds 添加 commit 参数
4. ⏳ 修改 PositionService.add_shares/reduce_shares 添加 commit 参数
5. ⏳ 重构 AccountTradingService.execute_trade()
6. ⏳ 集成测试

### 风险

- 破坏现有功能
- 事务边界不正确
- 性能下降

### 缓解

- 保留 legacy 方法
- 完整集成测试
- 生产监控

---

**当前状态**: 分析完成，等待继续执行
