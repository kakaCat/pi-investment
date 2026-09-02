# quantsys-v2 账户/订单/券商领域审计报告

**审计日期**: 2026-09-01  
**审计范围**: quantsys-v2 账户、订单、券商领域的代码质量、架构合理性、业务逻辑正确性  
**审计人员**: Claude (Fable 5)

---

## 执行摘要

### 整体评级: B+ (良好，有改进空间)

**优点**:
- ✅ 清晰的六边形架构：Domain → Application → Adapters 分层明确
- ✅ 领域模型设计合理：Account/Balance/Order/Trade 职责清晰
- ✅ 交易护栏完善：资金/持仓/仓位/T+1/交易时段多重校验
- ✅ 并发安全：行级锁 (get_account_for_update) 防止资金竞态
- ✅ 事务完整性：单事务内完成订单-成交-资金-持仓-快照全链路
- ✅ 费用计算准确：佣金/印花税/过户费符合 A 股规则

**待改进问题**:
- ⚠️ **P0** 券商抽象层未实际使用（domain/brokers 是空壳）
- ⚠️ **P1** 订单状态机缺少 FILLED 转态验证
- ⚠️ **P1** 资金扣减未原子化（deduct_cash/add_cash 无事务保证）
- ⚠️ **P2** 领域服务与应用服务职责重叠
- ⚠️ **P2** 测试覆盖不足（缺少券商/订单服务单测）

---

## 架构审计

### 1. 六边形架构评估

```
domain/
  accounts/
    models/          ✅ 领域模型纯粹，无基础设施依赖
      - account.py   ✅ Account: 账户实体（名称/状态/资金）
      - balance.py   ✅ Balance: 资金快照值对象
    ports/           ✅ 仓储接口定义清晰
      - IAccountRepository.py
    services/        ⚠️ AccountService 职责薄弱（仅透传）
      - account_service.py
  
  trading/
    models/          ✅ 订单/成交领域模型
      - order.py     ✅ Order: 订单实体（状态/价格/数量）
      - trade.py     ✅ Trade: 成交记录值对象
    services/        ✅ OrderService 业务逻辑完整
      - order_service.py
  
  brokers/           ❌ 空壳，未实际集成
    - base_broker.py ⚠️ 定义了完整接口，但无消费方
    - trading_types.py
    - broker_registry.py

application/
  services/          ✅ 应用编排层
    - account_trading_service.py ✅ 单事务交易编排
    - order_service.py           ⚠️ 与 domain/trading/services 重名
    - trade_service.py

adapters/
  outbound/
    repositories/    ✅ ORM 适配器
      - simulation_account_repository.py ✅ 适配到 IAccountRepository
    brokers/         ❌ 未被调用
      - akshare_broker.py
      - alpaca_broker.py
```

**架构问题**:

1. **券商层空壳化** (P0)
   - `domain/brokers/base_broker.py` 定义了完整的券商抽象（下单/撤单/查询持仓）
   - 实现了 3 个券商适配器（akshare/alpaca/ibkr）
   - 但 **没有任何代码实际调用** 这些接口
   - 当前交易流程完全绕过券商层，直接操作数据库

   **影响**: 架构设计与实现脱节，未来对接真实券商需要重构

2. **领域服务职责薄弱** (P2)
   - `domain/accounts/services/account_service.py` 仅做透传，无业务逻辑
   - 真正业务逻辑在 `application/services/account_trading_service.py`
   - 违反"胖领域模型"原则

   **建议**: 
   - 将交易校验逻辑（资金校验/持仓校验/仓位控制）下沉到领域服务
   - 应用服务仅负责编排和事务边界

3. **服务重名混淆** (P2)
   - `domain/trading/services/order_service.py`
   - `application/services/order_service.py`
   - 两者职责部分重叠，调用关系不清晰

---

## 领域模型审计

### 1. Account 领域模型

**文件**: [domain/accounts/models/account.py](quantsys-v2/domain/accounts/models/account.py:1)

```python
@dataclass
class Account:
    account_name: str          # ✅ 主键：账户唯一标识
    display_name: str          # ✅ 显示名称
    status: AccountStatus      # ✅ 枚举：active/frozen/archived
    initial_capital: float     # ✅ 初始资金
    strategy_name: Optional[str]  # ✅ 关联策略
```

**评价**: ✅ 设计合理
- 职责单一：仅包含账户身份和基本属性
- 不包含资金余额（由 Balance 分离）
- 不包含持仓（由 Position 分离）

### 2. Balance 领域模型

**文件**: [domain/accounts/models/balance.py](quantsys-v2/domain/accounts/models/balance.py:1)

```python
@dataclass
class Balance:
    account_name: str
    available_cash: float      # ✅ 可用资金
    frozen_cash: float         # ✅ 冻结资金
    total_value: float         # ✅ 总资产（现金+持仓）
    position_value: float      # ✅ 持仓市值
    peak_value: float          # ✅ 历史峰值（回撤计算用）
    cumulative_return: float   # ✅ 累计收益率
    max_drawdown: float        # ✅ 最大回撤
```

**评价**: ✅ 值对象设计良好
- 将易变的资金状态与账户实体分离
- 支持绩效指标（收益率/回撤）

**潜在问题**: ⚠️ 字段冗余
- `total_value` = `available_cash + frozen_cash + position_value`
- 冗余字段容易不一致

**建议**: 改为计算属性或在持久化前自动计算

### 3. Order 领域模型

**文件**: [domain/trading/models/order.py](quantsys-v2/domain/trading/models/order.py:1)

```python
class OrderStatus(Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"

@dataclass
class Order:
    account_name: str
    symbol: str
    action: OrderSide          # BUY/SELL 枚举
    order_type: OrderType      # limit/market/stop
    quantity: int
    price: float
    status: OrderStatus
    filled_quantity: int       # ✅ 支持部分成交
    avg_filled_price: float    # ✅ 加权平均成交价
    stop_loss_price: Optional[float]   # ✅ 止损价
    take_profit_price: Optional[float] # ✅ 止盈价
```

**评价**: ✅ 模型完整，支持高级特性
- 支持部分成交跟踪
- 支持止损/止盈（但未在代码中实际使用）
- 状态机清晰

**问题**: ⚠️ 状态转换未强制校验
- `OrderService.fill_order` 仅检查 `PENDING/PARTIAL` 可成交
- 但未定义完整状态机约束
- 代码中有 `VALID_TRANSITIONS` 字典但未在运行时强制

**建议**: 
```python
def _validate_transition(self, from_status: OrderStatus, to_status: OrderStatus):
    if (from_status, to_status) not in VALID_TRANSITIONS:
        raise ValueError(f"Invalid transition: {from_status} -> {to_status}")
```

### 4. Trade 领域模型

**文件**: [domain/trading/models/trade.py](quantsys-v2/domain/trading/models/trade.py:1)

```python
@dataclass
class Trade:
    account_name: str
    order_id: Optional[int]
    symbol: str
    action: str                # "BUY" or "SELL" (大写契约)
    shares: int
    price: float               # 委托价
    filled_price: float        # 成交价
    amount: float              # 成交金额
    commission: float          # 佣金
    stamp_duty: float          # 印花税
    transfer_fee: float        # 过户费
    realized_pnl: Optional[float]      # ✅ 已实现盈亏
    realized_pnl_rate: Optional[float] # ✅ 盈亏率
```

**评价**: ✅ 成交记录完整
- 包含所有费用明细
- 包含盈亏计算
- 字段命名清晰

**问题**: ⚠️ action 字段类型不一致
- Order 中是 `OrderSide` 枚举（BUY/SELL）
- Trade 中是 `str` 类型（"BUY"/"SELL"）
- 虽有大小写契约注释，但类型不一致容易出错

**建议**: 统一使用枚举类型

---

## 业务逻辑审计

### 1. 交易执行流程 (AccountTradingService)

**文件**: [application/services/account_trading_service.py](quantsys-v2/application/services/account_trading_service.py:1)

#### 1.1 交易护栏 ✅

代码实现了完善的风控护栏：

**资金护栏**:
```python
# 买入前资金校验
total_cost = trade_amount + commission + transfer_fee
if total_cost > account.cash_available:
    raise TradingError('可用资金不足', 422)

# 🔒 行级锁内复核（防并发竞态）
locked_account = self.repo.get_account_for_update(account_name)
if total_cost_locked > float(locked_account.cash_available):
    raise TradingError('可用资金不足(锁内复核)', 422)
```

**持仓护栏**:
```python
# T+1 可卖数量校验
if shares > pos.shares_available:
    raise TradingError('T+1 可卖数量不足', 422)

# 锁内重读持仓（防脏读）
self.repo.session.expire_all()
positions = self.repo.get_all_positions(account_name)
```

**仓位控制**:
```python
MAX_SINGLE_POSITION_RATIO = 0.30  # 单票不超30%
MAX_TOTAL_POSITION_RATIO = 0.80   # 总仓位不超80%
MAX_DAILY_BUY_COUNT = 5           # 单日买入笔数
MAX_DAILY_BUY_AMOUNT_RATIO = 0.50 # 单日买入金额占比
```

**交易时段护栏** ✅:
```python
TRADING_SESSIONS = (
    (dt_time(9, 30), dt_time(11, 30)),
    (dt_time(13, 0), dt_time(15, 0)),
)

def _check_trading_window(self, now: datetime):
    if not self.calendar.is_trading_day(day_str):
        raise TradingError('非交易日', 422)
    if not any(start <= t <= end for start, end in self.TRADING_SESSIONS):
        raise TradingError('非交易时段', 422)
```

**评价**: ✅ 护栏设计全面且正确

#### 1.2 费用计算 ✅

```python
COMMISSION_RATE = 0.00025      # 万2.5
COMMISSION_MIN = 5.0           # 最低5元
STAMP_DUTY_RATE = 0.0005       # 印花税0.05%（卖出）
TRANSFER_FEE_RATE = 0.00001    # 过户费0.001%

commission = max(trade_amount * COMMISSION_RATE, COMMISSION_MIN)
stamp_duty = trade_amount * STAMP_DUTY_RATE if action == 'SELL' else 0.0
transfer_fee = trade_amount * TRANSFER_FEE_RATE
```

**评价**: ✅ 符合 A 股交易规则

#### 1.3 事务完整性 ✅

```python
try:
    # 1. 锁定账户
    locked_account = self.repo.get_account_for_update(account_name)
    
    # 2. 创建订单
    order = self.repo.create_order(..., commit=False)
    order.status = 'filled'
    
    # 3. 记录成交
    trade_id = self.repo.add_trade(..., commit=False)
    
    # 4. 更新持仓
    self.repo.upsert_position(..., commit=False)
    
    # 5. 更新资金
    account.cash_available -= total_cost
    
    # 6. 记录快照
    self.repo.upsert_equity_snapshot(..., commit=False)
    
    # 7. 统一提交
    self.repo.session.commit()
except Exception:
    self.repo.session.rollback()
    raise
```

**评价**: ✅ 单事务保证原子性

**潜在问题**: ⚠️ 事务范围过大
- 包含行情查询（`_get_price`）
- 包含日志写入（`_auto_record_decision`）
- 如果行情服务慢，会长时间持有数据库锁

**建议**: 
- 将行情查询前置到事务外
- 决策日志异步化

#### 1.4 并发安全 ✅

使用 **行级锁 (SELECT FOR UPDATE)** 防止并发交易的资金竞态：

```python
locked_account = self.repo.get_account_for_update(account_name)
```

**场景测试**:
```
T1: 查可用资金 10000 → 买入 8000（通过校验）
T2: 查可用资金 10000 → 买入 8000（通过校验）
T1: 扣款 10000 - 8000 = 2000 ✅
T2: 等待 T1 释放锁...
T2: 锁内复核 2000 < 8000 → 拒绝 ✅
```

**评价**: ✅ 并发控制正确

### 2. 订单服务逻辑 (OrderService)

**文件**: [domain/trading/services/order_service.py](quantsys-v2/domain/trading/services/order_service.py:1)

#### 2.1 订单校验 ✅

```python
def validate_order(self, ...):
    # 基础校验
    if quantity <= 0:
        raise ValueError("委托数量必须大于0")
    if quantity % 100 != 0:
        raise ValueError("A股数量必须是100股整数倍")
    
    # 买入资金校验
    if action == OrderSide.BUY:
        total_cost = stock_amount + commission + transfer_fee
        if not self.account_service.validate_buy_balance(...):
            raise ValueError("可用资金不足")
    
    # 卖出持仓校验
    elif action == OrderSide.SELL:
        available_shares = self.position_service.get_available_shares(...)
        if available_shares < quantity:
            raise ValueError("可卖数量不足")
```

**评价**: ✅ 校验逻辑完整

**问题**: ⚠️ 校验时机不当（TOCTOU 问题）
- `validate_order` 在事务外执行
- `create_order` 调用 `validate_order` 后再保存
- 并发场景下可能通过校验但实际不足

**示例**:
```
T1: validate_order (余额 10000，通过) ✅
T2: validate_order (余额 10000，通过) ✅
T1: create_order (扣款 8000) ✅
T2: create_order (扣款 8000) ❌ 实际余额只剩 2000
```

**建议**: 
- `validate_order` 仅用于前端预校验
- `create_order` 应在事务内重新校验

#### 2.2 订单成交逻辑 ✅

```python
def fill_order(self, order_id: int, fill_price: float, fill_quantity: int):
    # 1. 校验状态
    if order.status not in (OrderStatus.PENDING, OrderStatus.PARTIAL):
        raise ValueError("订单状态不允许成交")
    
    # 2. 计算加权平均成交价
    total_cost = old_filled_qty * old_avg_price + fill_quantity * fill_price
    new_avg_price = total_cost / new_filled_qty
    
    # 3. 更新订单状态
    new_status = OrderStatus.FILLED if new_filled_qty >= order.quantity else OrderStatus.PARTIAL
    
    # 4. 创建成交记录
    trade = Trade(...)
```

**评价**: ✅ 支持部分成交，价格计算正确

**问题**: ⚠️ 未更新持仓和资金
- `fill_order` 只创建 Trade 对象，不更新账户
- 注释说 "TODO: 注入 TradeService 并在那里保存"
- **实际未被使用**（当前系统用 `AccountTradingService.execute_trade` 直接成交）

**影响**: 
- `OrderService` 是半成品，未实际参与交易流程
- 与 `AccountTradingService` 职责重复

#### 2.3 订单过期处理 ✅

```python
def expire_orders(self) -> int:
    pending_orders = self.order_repo.get_pending_orders()
    now = datetime.now()
    for order in pending_orders:
        if order.expires_at and order.expires_at < now:
            self.order_repo.update_order_status(order.id, OrderStatus.EXPIRED)
```

**评价**: ✅ 定时清理逻辑简单有效

**问题**: ⚠️ 缺少调度器调用
- 代码存在但未被定时任务调用
- 过期订单会堆积

### 3. 挂单机制 (Pending Orders)

**文件**: [application/services/account_trading_service.py:338](quantsys-v2/application/services/account_trading_service.py:338)

#### 3.1 挂单逻辑 ✅

```python
# 非交易时段 + execute_at='market_open' → 挂单
if execute_at == 'market_open' and not in_window:
    pending = self.repo.create_pending_order(
        account_name=account_name, action=action, symbol=symbol,
        shares=shares, amount=amount, price_limit=price_limit,
        reason=reason, execute_at='market_open')
    return {'status': 'pending', 'pending_order_id': pending.id}
```

**评价**: ✅ 支持条件委托，适合 agent 自动化交易

#### 3.2 撮合执行 ✅

```python
def execute_pending_orders(self, now: Optional[datetime] = None):
    pending = self.repo.get_pending_orders(status='pending')
    for po in pending:
        try:
            result = self.execute_trade(...)  # 完整护栏校验
            self.repo.update_pending_order_status(po.id, 'executed', ...)
        except TradingError as e:
            self.repo.update_pending_order_status(po.id, 'failed', ...)
```

**评价**: ✅ 挂单撮合时重新走完整护栏，保证安全

**问题**: ⚠️ 撮合时机不明确
- 注释说"由 orchestrator 在开盘后 9:31 起调用"
- 但未见 scheduler 配置
- 可能未实际启用

---

## 数据访问层审计

### 1. IAccountRepository 接口 ✅

**文件**: [domain/accounts/ports/IAccountRepository.py](quantsys-v2/domain/accounts/ports/IAccountRepository.py:1)

```python
class IAccountRepository(ABC):
    @abstractmethod
    def get_account(self, account_name: str) -> Optional[Account]:
        pass
    
    @abstractmethod
    def deduct_cash(self, account_name: str, amount: float) -> bool:
        pass
    
    @abstractmethod
    def add_cash(self, account_name: str, amount: float) -> bool:
        pass
```

**评价**: ✅ 接口清晰，职责明确

**问题**: ⚠️ `deduct_cash`/`add_cash` 无事务保证
- 接口返回 `bool` 表示成功/失败
- 但实现中直接 `session.commit()`
- **调用方无法控制事务边界**

**示例问题**:
```python
# 假设要在一个事务内同时扣两个账户的钱
try:
    repo.deduct_cash("account_a", 1000)  # ✅ 提交了
    repo.deduct_cash("account_b", 1000)  # ❌ 失败
    # account_a 已扣款，无法回滚！
except:
    # 无法回滚 account_a
```

**实际影响**: ⚠️ 当前未出问题是因为所有资金操作都通过 `AccountTradingService` 单事务控制
- 如果直接调用 `deduct_cash`，会有事务问题

**建议**: 
```python
@abstractmethod
def deduct_cash(self, account_name: str, amount: float, commit: bool = True) -> bool:
    """扣减资金
    
    Args:
        commit: 是否立即提交，False 时调用方负责提交/回滚
    """
```

### 2. SimulationAccountRepository 实现

**文件**: [adapters/outbound/repositories/simulation_account_repository.py](quantsys-v2/adapters/outbound/repositories/simulation_account_repository.py:1)

```python
class SimulationAccountRepository(IAccountRepository):
    def __init__(self, sim_repo: Optional[SimulationORMRepository] = None):
        self.sim_repo = sim_repo or SimulationORMRepository()
    
    def deduct_cash(self, account_name: str, amount: float) -> bool:
        account = self.sim_repo.get_account(account_name)
        if float(account.cash_available) < amount:
            return False
        account.cash_available = float(account.cash_available) - amount
        self.sim_repo.session.commit()  # ⚠️ 立即提交
        return True
```

**评价**: ⚠️ 适配器设计有缺陷
- 将 `SimulationORMRepository` 包装成 `IAccountRepository`
- 但 `SimulationORMRepository` 本身就支持事务控制（commit 参数）
- 适配器反而丢失了这个能力

**建议**: 直接使用 `SimulationORMRepository`，不需要额外适配层

---

## 券商抽象层审计

### 1. BaseBroker 设计 ✅

**文件**: [domain/brokers/base_broker.py](quantsys-v2/domain/brokers/base_broker.py:1)

```python
class BaseBroker(ABC):
    # 身份
    @abstractmethod
    def get_id(self) -> str: pass
    
    @abstractmethod
    def get_profile(self) -> BrokerProfile: pass
    
    # 行情数据（必需）
    @abstractmethod
    def get_quotes(self, symbols: List[str]) -> ApiResponse[List[BrokerQuote]]: pass
    
    @abstractmethod
    def get_history(self, symbol: str, ...) -> ApiResponse[List[BrokerCandle]]: pass
    
    # 交易（可选）
    def place_order(self, credentials: BrokerCredentials, order: UnifiedOrder) -> OrderPlaceResponse:
        return OrderPlaceResponse.fail("Trading not supported")
    
    def get_positions(self, ...) -> ApiResponse[List[BrokerPosition]]:
        return ApiResponse.fail("Trading not supported")
```

**评价**: ✅ 设计优秀
- 清晰区分必需功能（行情）和可选功能（交易）
- 统一返回类型 `ApiResponse[T]`
- 支持数据源和交易券商的差异化

### 2. 券商实现

已实现 3 个券商适配器：
- `akshare_broker.py` - AkShare 数据源
- `alpaca_broker.py` - Alpaca 美股交易
- `ibkr_broker.py` - 盈透证券

**问题**: ❌ 全部未被使用
- 无任何代码调用 `BaseBroker` 接口
- 当前系统直接调用各数据源模块（如 `RealtimeQuoteService`）
- 券商层完全是装饰

**影响**:
1. 架构图与实现不符（文档说有券商抽象层，实际没用）
2. 未来对接真实券商需要大改
3. 代码维护成本高（维护了用不到的代码）

**建议**:
- **方案 A**: 删除券商抽象层，承认当前是模拟交易系统
- **方案 B**: 重构交易流程，通过券商层统一下单：
  ```python
  # 当前：直接操作数据库
  self.repo.add_trade(...)
  
  # 改为：通过券商下单
  broker = broker_registry.get_broker("simulation")
  result = broker.place_order(credentials, order)
  ```

---

## 测试覆盖审计

### 1. 已有测试

```
tests/
  test_account_daily_limits.py        ✅ 日买入限额测试
  test_multi_account_domain.py        ✅ 多账户域模型测试
  test_order_trade.py                 ✅ 订单成交流程测试
  test_trade_cash_race.py             ✅ 并发资金竞态测试
  integration/test_signal_to_order_flow.py ✅ 端到端测试
```

### 2. 测试覆盖缺口

**缺少单元测试**:
- ❌ `domain/accounts/services/account_service.py` 无测试
- ❌ `domain/trading/services/order_service.py` 无测试
- ❌ `adapters/outbound/repositories/simulation_account_repository.py` 无测试
- ❌ 所有券商适配器无测试

**缺少边界测试**:
- ❌ 订单状态机非法转换测试
- ❌ 费用计算边界条件（如佣金 < 5元）
- ❌ 并发冲突回滚测试

**建议**: 
1. 为所有服务层添加单元测试（mock 仓储）
2. 为并发场景添加压力测试
3. 为费用计算添加边界值测试

---

## 已知问题清单

### P0 - 阻塞生产

无

### P1 - 影响功能正确性

1. **订单状态机未强制校验**
   - 位置: `domain/trading/services/order_service.py:21`
   - 问题: `VALID_TRANSITIONS` 定义了状态转换规则，但 `fill_order` 未强制执行
   - 风险: 可能出现非法状态转换（如 CANCELLED → FILLED）
   - 修复:
     ```python
     def _validate_transition(self, from_status, to_status):
         if (from_status, to_status) not in VALID_TRANSITIONS:
             raise ValueError(f"Invalid transition: {from_status} -> {to_status}")
     ```

2. **资金操作无事务保证**
   - 位置: `domain/accounts/ports/IAccountRepository.py:46`
   - 问题: `deduct_cash`/`add_cash` 在实现中直接提交事务
   - 风险: 调用方无法组合多个操作到一个事务
   - 修复: 添加 `commit` 参数控制事务提交时机

3. **挂单撮合未启用**
   - 位置: `application/services/account_trading_service.py:370`
   - 问题: `execute_pending_orders` 未被调度器调用
   - 风险: 挂单永远不会成交
   - 修复: 在 scheduler 添加每日 9:31 触发任务

### P2 - 架构问题

4. **券商抽象层未实际使用**
   - 位置: `domain/brokers/`
   - 问题: 定义了完整接口但无调用方
   - 影响: 架构与实现脱节，未来重构成本高
   - 建议: 要么删除，要么重构交易流程使用券商层

5. **领域服务与应用服务职责重叠**
   - 位置: `domain/trading/services/order_service.py` vs `application/services/account_trading_service.py`
   - 问题: `OrderService.fill_order` 未被使用，真正交易逻辑在应用层
   - 影响: 违反领域驱动设计原则
   - 建议: 将交易校验逻辑下沉到领域服务

6. **Balance 冗余字段**
   - 位置: `domain/accounts/models/balance.py:12`
   - 问题: `total_value` 可由其他字段计算得出
   - 风险: 数据不一致
   - 建议: 改为计算属性

### P3 - 代码质量

7. **Trade.action 类型不一致**
   - 位置: `domain/trading/models/trade.py:14`
   - 问题: Order 用枚举，Trade 用字符串
   - 影响: 类型安全性差
   - 建议: 统一使用枚举

8. **测试覆盖不足**
   - 问题: 领域服务/仓储适配器/券商层均无测试
   - 影响: 重构风险高
   - 建议: 补充单元测试

---

## 优秀实践

1. **行级锁防并发竞态** ✅
   ```python
   locked_account = self.repo.get_account_for_update(account_name)
   # 锁内复核资金
   if total_cost > float(locked_account.cash_available):
       raise TradingError('资金不足')
   ```

2. **单事务保证原子性** ✅
   ```python
   try:
       # 订单-成交-持仓-资金-快照 全部 commit=False
       self.repo.session.commit()  # 统一提交
   except:
       self.repo.session.rollback()
   ```

3. **费用计算准确** ✅
   - 佣金最低 5元
   - 印花税仅卖出收取
   - 过户费买卖双向

4. **交易护栏完善** ✅
   - 资金/持仓/仓位/交易时段 多层防护
   - 日买入限额防 LLM 失控

5. **T+1 结算正确** ✅
   - 买入当日 `shares_available` 不增加
   - 由定时任务 `settle_t1` 次日结转

---

## 改进建议

### 短期（1-2周）

1. **修复订单状态机校验** (P1)
   - 在 `OrderService` 添加状态转换验证
   - 测试非法转换场景

2. **启用挂单撮合** (P1)
   - 在 scheduler 添加每日 9:31 任务
   - 测试挂单成交流程

3. **补充单元测试** (P3)
   - `AccountService` 测试
   - `OrderService` 测试
   - 费用计算边界测试

### 中期（1-2月）

4. **重构领域服务职责** (P2)
   - 交易校验逻辑下沉到 `OrderService`
   - `AccountTradingService` 仅负责编排
   - 统一使用 `OrderService.fill_order`

5. **修复事务控制接口** (P1)
   - `IAccountRepository` 添加 `commit` 参数
   - 测试多步骤事务场景

6. **统一类型定义** (P3)
   - `Trade.action` 改用枚举
   - 移除 `Balance` 冗余字段

### 长期（3-6月）

7. **决策券商层去留** (P2)
   - **方案 A**: 删除券商抽象层（承认当前是模拟系统）
   - **方案 B**: 重构交易流程使用券商层（为真实券商对接做准备）

8. **性能优化**
   - 行情查询前置到事务外
   - 决策日志异步化
   - 快照写入改为异步

---

## 总结

### 优点
- 领域模型设计合理，职责清晰
- 交易护栏完善，并发控制正确
- 费用计算准确，符合 A 股规则
- 事务原子性保证良好

### 主要问题
- 券商抽象层是空壳，未实际使用
- 订单状态机未强制校验
- 资金操作接口缺少事务控制
- 测试覆盖不足

### 整体评价
代码质量 **B+**，可用于生产环境（模拟交易），但需要修复 P1 问题并补充测试后才能对接真实券商。

---

## 附录

### A. 文件清单

**领域层**:
- `domain/accounts/models/account.py` - 账户实体
- `domain/accounts/models/balance.py` - 资金值对象
- `domain/accounts/services/account_service.py` - 账户领域服务
- `domain/accounts/ports/IAccountRepository.py` - 账户仓储接口
- `domain/trading/models/order.py` - 订单实体
- `domain/trading/models/trade.py` - 成交值对象
- `domain/trading/services/order_service.py` - 订单领域服务
- `domain/brokers/base_broker.py` - 券商抽象基类

**应用层**:
- `application/services/account_trading_service.py` - 交易编排服务
- `application/services/order_service.py` - 订单应用服务
- `application/services/trade_service.py` - 成交应用服务

**适配器层**:
- `adapters/outbound/repositories/simulation_account_repository.py` - 账户仓储实现
- `adapters/outbound/brokers/akshare_broker.py` - AkShare 券商适配器
- `adapters/outbound/brokers/alpaca_broker.py` - Alpaca 券商适配器
- `adapters/outbound/brokers/ibkr_broker.py` - IBKR 券商适配器

### B. 数据库表结构

```sql
-- 账户表
simulation_accounts (
    account_name VARCHAR PRIMARY KEY,
    display_name VARCHAR,
    status VARCHAR,  -- active/frozen/archived
    initial_capital DECIMAL,
    cash_available DECIMAL,
    cash_frozen DECIMAL,
    position_value DECIMAL,
    total_value DECIMAL,
    peak_value DECIMAL,
    cumulative_return DECIMAL,
    max_drawdown DECIMAL,
    strategy_name VARCHAR
)

-- 订单表
simulation_orders (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR,
    symbol VARCHAR,
    action VARCHAR,  -- BUY/SELL
    shares INTEGER,
    price DECIMAL,
    status VARCHAR,  -- pending/partial/filled/cancelled
    filled_shares INTEGER,
    avg_filled_price DECIMAL,
    reason TEXT,
    created_at TIMESTAMP
)

-- 成交表
simulation_trades (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR,
    order_id INTEGER,
    symbol VARCHAR,
    action VARCHAR,  -- BUY/SELL
    shares INTEGER,
    price DECIMAL,
    filled_price DECIMAL,
    amount DECIMAL,
    commission DECIMAL,
    stamp_duty DECIMAL,
    transfer_fee DECIMAL,
    realized_pnl DECIMAL,
    realized_pnl_rate DECIMAL,
    trade_date DATE,
    created_at TIMESTAMP
)

-- 持仓表
simulation_positions (
    account_name VARCHAR,
    symbol VARCHAR,
    shares_total INTEGER,
    shares_available INTEGER,  -- T+1 可卖
    avg_cost DECIMAL,
    current_price DECIMAL,
    market_value DECIMAL,
    PRIMARY KEY (account_name, symbol)
)

-- 挂单表
simulation_pending_orders (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR,
    symbol VARCHAR,
    action VARCHAR,
    shares INTEGER,
    amount DECIMAL,
    price_limit DECIMAL,
    reason TEXT,
    status VARCHAR,  -- pending/executed/failed/cancelled
    execute_at VARCHAR,  -- market_open
    executed_trade_id INTEGER,
    fail_reason TEXT,
    created_at TIMESTAMP
)
```

### C. 交易流程图

```
┌─────────────┐
│ Agent 发起  │
│ 交易请求    │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────┐
│ AccountTradingService            │
│ execute_trade()                  │
└──────┬───────────────────────────┘
       │
       ├─> 1. 校验交易时段
       │   _check_trading_window()
       │
       ├─> 2. 获取实时行情
       │   RealtimeQuoteService.get_quote()
       │
       ├─> 3. 计算费用
       │   commission / stamp_duty / transfer_fee
       │
       ├─> 4. 校验护栏
       │   - 资金充足？
       │   - 持仓充足？
       │   - 仓位限制？
       │   - 日买入限额？
       │
       ▼
┌──────────────────────────────────┐
│ 单事务执行                        │
└──────┬───────────────────────────┘
       │
       ├─> 5. 锁定账户（行级锁）
       │   get_account_for_update()
       │
       ├─> 6. 复核资金/持仓（防并发）
       │   session.expire_all()
       │
       ├─> 7. 创建订单
       │   create_order(commit=False)
       │
       ├─> 8. 记录成交
       │   add_trade(commit=False)
       │
       ├─> 9. 更新持仓
       │   upsert_position(commit=False)
       │
       ├─> 10. 更新资金
       │    account.cash_available -= total_cost
       │
       ├─> 11. 记录快照
       │    upsert_equity_snapshot(commit=False)
       │
       ├─> 12. 统一提交
       │    session.commit()
       │
       ▼
┌──────────────────────────────────┐
│ 返回成交结果                      │
│ {order_id, trade_id, ...}        │
└──────────────────────────────────┘
```

---

**审计完成日期**: 2026-09-01  
**下次审计建议**: 2026-12-01 (P1 问题修复后)
