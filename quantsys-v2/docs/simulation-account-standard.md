# 模拟账户规范标准

**生成时间**: 2026-06-29  
**适用范围**: quantsys-v2 模拟交易系统

---

## 📊 当前状态诊断

### 现有实现

**文件结构**:
```
live_trading/
├── simulation_broker.py      # 模拟券商（交易执行）
├── simulation_trader.py       # 模拟交易器（策略执行）
├── config_simulation.yaml     # 配置文件
└── create_simulation_tables.sql  # 数据库表结构

adapters/outbound/repositories/
├── simulation_repository.py         # ORM Repository（同步）
└── simulation_async_repository.py   # ORM Repository（异步）

infrastructure/persistence/orm/models/
└── simulation.py              # ORM 模型定义
```

### ✅ 已实现的规范

1. **数据持久化**: 使用 PostgreSQL + ORM
2. **Repository 模式**: 数据访问层抽象
3. **配置管理**: YAML 配置文件
4. **风险控制**: 独立的 RiskController
5. **通知集成**: 飞书通知支持

### ⚠️ 存在的问题

#### 问题 1: 日志使用不规范

**当前代码**:
```python
# simulation_broker.py
logging.info(f"模拟券商初始化: 手续费{commission_rate*10000:.1f}‱")

# simulation_trader.py
logging.basicConfig(
    level=self.config['logging']['level'],
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[...]
)
```

**问题**:
- 使用字符串拼接而非结构化日志
- 重复配置 `logging.basicConfig`
- 未使用项目统一的日志配置

#### 问题 2: 数据模型不一致

**ORM 模型** vs **实际使用**存在不一致：

```python
# simulation_trader.py 中直接操作属性
self.cash = float(account.cash)
self.peak_value = float(account.peak_value)

# 但在 Repository 中返回的可能是 dict
if hasattr(account, 'cash'):
    # ORM对象
else:
    # dict
```

**问题**: 类型不确定，需要兼容处理

#### 问题 3: 配置文件分散

```yaml
# config_simulation.yaml
trading:
  commission_rate: 0.0003
  slippage_rate: 0.001

risk_control:
  max_position_ratio: 0.2
  max_drawdown: 0.15

logging:
  level: INFO
  log_dir: logs/simulation
```

**问题**: 配置与项目主配置（.env）分离

#### 问题 4: 缺少标准化接口

- 没有统一的账户接口定义
- 不同模块对账户的理解不一致
- 难以扩展到真实券商

---

## 🎯 规范标准

### 1. 数据模型规范

#### 1.1 ORM 模型定义

```python
from sqlalchemy import Column, String, Numeric, Date, DateTime, Integer
from infrastructure.persistence.orm import Base

class SimulationAccount(Base):
    """模拟账户"""
    __tablename__ = 'simulation_accounts'
    
    id = Column(Integer, primary_key=True)
    account_name = Column(String(50), unique=True, nullable=False, index=True)
    cash = Column(Numeric(15, 2), nullable=False, default=100000.00)
    total_value = Column(Numeric(15, 2), nullable=False, default=100000.00)
    peak_value = Column(Numeric(15, 2), nullable=False, default=100000.00)
    last_rebalance_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SimulationPosition(Base):
    """模拟持仓"""
    __tablename__ = 'simulation_positions'
    
    id = Column(Integer, primary_key=True)
    account_name = Column(String(50), nullable=False, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    shares = Column(Integer, nullable=False)
    cost_price = Column(Numeric(10, 2), nullable=False)
    current_price = Column(Numeric(10, 2), nullable=True)
    market_value = Column(Numeric(15, 2), nullable=True)
    profit_loss = Column(Numeric(15, 2), nullable=True)
    profit_loss_pct = Column(Numeric(10, 4), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 唯一约束：每个账户每个股票只能有一条持仓记录
    __table_args__ = (
        UniqueConstraint('account_name', 'symbol', name='uix_account_symbol'),
    )


class SimulationTrade(Base):
    """模拟交易记录"""
    __tablename__ = 'simulation_trades'
    
    id = Column(Integer, primary_key=True)
    account_name = Column(String(50), nullable=False, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    action = Column(String(10), nullable=False)  # BUY/SELL
    shares = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)  # 委托价格
    filled_price = Column(Numeric(10, 2), nullable=False)  # 成交价格
    amount = Column(Numeric(15, 2), nullable=False)
    commission = Column(Numeric(10, 2), nullable=False, default=0.00)
    trade_date = Column(Date, nullable=False, index=True)
    trade_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(20), nullable=False, default='filled')  # pending/filled/cancelled
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

#### 1.2 数据一致性约束

- ✅ 账户现金不能为负
- ✅ 持仓数量必须是 100 的整数倍
- ✅ 每个账户-股票组合唯一
- ✅ 交易记录不可修改（只能新增）

---

### 2. Repository 规范

#### 2.1 统一接口定义

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from decimal import Decimal

class ISimulationRepository(ABC):
    """模拟交易 Repository 接口"""
    
    @abstractmethod
    def get_account(self, account_name: str = 'default') -> Optional[SimulationAccount]:
        """获取账户"""
        pass
    
    @abstractmethod
    def update_account_cash(self, account_name: str, cash: Decimal) -> None:
        """更新账户现金"""
        pass
    
    @abstractmethod
    def get_all_positions(self, account_name: str = 'default') -> List[SimulationPosition]:
        """获取所有持仓"""
        pass
    
    @abstractmethod
    def get_position(self, account_name: str, symbol: str) -> Optional[SimulationPosition]:
        """获取单个持仓"""
        pass
    
    @abstractmethod
    def add_trade(
        self, 
        account_name: str,
        symbol: str,
        action: str,
        shares: int,
        price: Decimal,
        filled_price: Decimal
    ) -> int:
        """添加交易记录"""
        pass
```

#### 2.2 Repository 实现规范

```python
import structlog
from sqlalchemy import select, update
from infrastructure.persistence.orm import BaseORMRepository

logger = structlog.get_logger(__name__)


class SimulationORMRepository(BaseORMRepository[SimulationAccount], ISimulationRepository):
    """模拟交易 Repository
    
    规范：
    1. 所有方法必须记录结构化日志
    2. 返回类型明确（ORM 对象，不要 dict）
    3. 异常必须记录并重新抛出
    4. 数据验证在 Repository 层进行
    """
    
    model = SimulationAccount
    
    def get_account(self, account_name: str = 'default') -> Optional[SimulationAccount]:
        """获取账户"""
        logger.info("get_account_called", account_name=account_name)
        
        try:
            with self.get_session() as session:
                stmt = select(SimulationAccount).where(
                    SimulationAccount.account_name == account_name
                )
                account = session.execute(stmt).scalar_one_or_none()
                
                if account:
                    logger.info(
                        "account_retrieved",
                        account_name=account_name,
                        cash=float(account.cash)
                    )
                else:
                    logger.warning("account_not_found", account_name=account_name)
                
                return account
                
        except Exception as e:
            logger.error(
                "get_account_failed",
                account_name=account_name,
                error=str(e)
            )
            raise
    
    def add_trade(
        self,
        account_name: str,
        symbol: str,
        action: str,
        shares: int,
        price: Decimal,
        filled_price: Decimal
    ) -> int:
        """添加交易记录
        
        数据验证：
        - shares 必须是 100 的整数倍
        - action 必须是 BUY 或 SELL
        - price 和 filled_price 必须 > 0
        """
        logger.info(
            "add_trade_called",
            account_name=account_name,
            symbol=symbol,
            action=action,
            shares=shares
        )
        
        # 数据验证
        if shares % 100 != 0:
            logger.error("invalid_shares", shares=shares, reason="not_multiple_of_100")
            raise ValueError(f"股数必须是100的整数倍: {shares}")
        
        if action not in ['BUY', 'SELL']:
            logger.error("invalid_action", action=action)
            raise ValueError(f"交易动作必须是 BUY 或 SELL: {action}")
        
        if price <= 0 or filled_price <= 0:
            logger.error("invalid_price", price=price, filled_price=filled_price)
            raise ValueError("价格必须大于0")
        
        try:
            with self.get_session() as session:
                trade = SimulationTrade(
                    account_name=account_name,
                    symbol=symbol,
                    action=action,
                    shares=shares,
                    price=price,
                    filled_price=filled_price,
                    amount=shares * filled_price,
                    trade_date=datetime.now().date()
                )
                
                session.add(trade)
                session.commit()
                session.refresh(trade)
                
                logger.info(
                    "trade_added",
                    trade_id=trade.id,
                    account_name=account_name,
                    symbol=symbol,
                    action=action,
                    shares=shares
                )
                
                return trade.id
                
        except Exception as e:
            logger.error(
                "add_trade_failed",
                account_name=account_name,
                symbol=symbol,
                error=str(e)
            )
            raise
```

---

### 3. 模拟券商规范

#### 3.1 SimulationBroker 接口

```python
import structlog
from decimal import Decimal
from typing import Dict, Literal

logger = structlog.get_logger(__name__)


class SimulationBroker:
    """模拟券商
    
    规范：
    1. 使用结构化日志
    2. 使用 Decimal 处理金额（避免浮点数精度问题）
    3. 所有交易返回标准化结果
    4. 记录详细的成交信息
    """
    
    def __init__(self, commission_rate: float = 0.0003, slippage_rate: float = 0.001):
        """初始化模拟券商
        
        Args:
            commission_rate: 手续费率（默认万3）
            slippage_rate: 滑点率（默认千1）
        """
        self.commission_rate = Decimal(str(commission_rate))
        self.slippage_rate = Decimal(str(slippage_rate))
        
        logger.info(
            "broker_initialized",
            commission_rate=float(self.commission_rate),
            slippage_rate=float(self.slippage_rate)
        )
    
    def buy(
        self,
        symbol: str,
        shares: int,
        price: Decimal,
        order_type: Literal['market', 'limit'] = 'market'
    ) -> Dict:
        """买入股票
        
        Args:
            symbol: 股票代码
            shares: 股数（必须是100的整数倍）
            price: 委托价格
            order_type: 订单类型
            
        Returns:
            Dict: 成交信息
                - symbol: 股票代码
                - action: BUY
                - shares: 成交股数
                - price: 委托价格
                - filled_price: 成交价格
                - amount: 成交金额
                - commission: 手续费
                - total_cost: 总成本
                - order_type: 订单类型
                - timestamp: 成交时间
        """
        logger.info(
            "buy_order_received",
            symbol=symbol,
            shares=shares,
            price=float(price),
            order_type=order_type
        )
        
        # 验证股数
        if shares % 100 != 0:
            logger.error("invalid_shares", shares=shares)
            raise ValueError(f"股数必须是100的整数倍: {shares}")
        
        # 计算成交价（考虑滑点）
        if order_type == 'market':
            filled_price = price * (Decimal('1') + self.slippage_rate)
        else:
            filled_price = price
        
        # 计算成本
        amount = Decimal(shares) * filled_price
        commission = max(amount * self.commission_rate, Decimal('5'))  # 最低5元
        total_cost = amount + commission
        
        result = {
            'symbol': symbol,
            'action': 'BUY',
            'shares': shares,
            'price': price,
            'filled_price': filled_price,
            'amount': amount,
            'commission': commission,
            'total_cost': total_cost,
            'order_type': order_type,
            'timestamp': datetime.now()
        }
        
        logger.info(
            "buy_order_filled",
            symbol=symbol,
            shares=shares,
            filled_price=float(filled_price),
            total_cost=float(total_cost),
            commission=float(commission)
        )
        
        return result
```

---

### 4. 配置规范

#### 4.1 统一配置管理

**使用环境变量 + YAML 配置**:

```python
# .env
SIMULATION_COMMISSION_RATE=0.0003
SIMULATION_SLIPPAGE_RATE=0.001
SIMULATION_INITIAL_CASH=100000.00
SIMULATION_MAX_POSITION_RATIO=0.20
SIMULATION_MAX_DRAWDOWN=0.15
```

```python
# 代码中读取
import os
from decimal import Decimal

class SimulationConfig:
    """模拟交易配置"""
    
    COMMISSION_RATE = Decimal(os.getenv('SIMULATION_COMMISSION_RATE', '0.0003'))
    SLIPPAGE_RATE = Decimal(os.getenv('SIMULATION_SLIPPAGE_RATE', '0.001'))
    INITIAL_CASH = Decimal(os.getenv('SIMULATION_INITIAL_CASH', '100000.00'))
    MAX_POSITION_RATIO = Decimal(os.getenv('SIMULATION_MAX_POSITION_RATIO', '0.20'))
    MAX_DRAWDOWN = Decimal(os.getenv('SIMULATION_MAX_DRAWDOWN', '0.15'))
```

#### 4.2 配置验证

```python
def validate_simulation_config() -> None:
    """验证模拟交易配置"""
    logger.info("validating_simulation_config")
    
    assert 0 < SimulationConfig.COMMISSION_RATE < 0.01, "手续费率超出合理范围"
    assert 0 < SimulationConfig.SLIPPAGE_RATE < 0.01, "滑点率超出合理范围"
    assert SimulationConfig.INITIAL_CASH >= 10000, "初始资金不足"
    assert 0 < SimulationConfig.MAX_POSITION_RATIO <= 1, "单股仓位比例超出范围"
    assert 0 < SimulationConfig.MAX_DRAWDOWN <= 1, "最大回撤比例超出范围"
    
    logger.info(
        "simulation_config_validated",
        commission_rate=float(SimulationConfig.COMMISSION_RATE),
        initial_cash=float(SimulationConfig.INITIAL_CASH)
    )
```

---

### 5. 测试规范

#### 5.1 单元测试

```python
import pytest
from decimal import Decimal
from live_trading.simulation_broker import SimulationBroker


class TestSimulationBroker:
    """模拟券商单元测试"""
    
    def test_buy_order_success(self):
        """测试买入订单成功"""
        broker = SimulationBroker()
        
        result = broker.buy(
            symbol='600000',
            shares=100,
            price=Decimal('10.00'),
            order_type='market'
        )
        
        assert result['action'] == 'BUY'
        assert result['shares'] == 100
        assert result['filled_price'] > Decimal('10.00')  # 考虑滑点
        assert result['commission'] >= Decimal('5')  # 最低5元
    
    def test_buy_order_invalid_shares(self):
        """测试买入订单：股数不合法"""
        broker = SimulationBroker()
        
        with pytest.raises(ValueError, match="股数必须是100的整数倍"):
            broker.buy(
                symbol='600000',
                shares=150,  # 不是100的整数倍
                price=Decimal('10.00')
            )
    
    def test_commission_calculation(self):
        """测试手续费计算"""
        broker = SimulationBroker(commission_rate=0.0003)
        
        result = broker.buy(
            symbol='600000',
            shares=100,
            price=Decimal('10.00'),
            order_type='limit'
        )
        
        expected_commission = Decimal('100') * Decimal('10.00') * Decimal('0.0003')
        assert result['commission'] == max(expected_commission, Decimal('5'))
```

#### 5.2 集成测试

```python
import pytest
from live_trading.simulation_trader import SimulationTrader
from adapters.outbound.repositories import SimulationORMRepository


class TestSimulationTrader:
    """模拟交易器集成测试"""
    
    @pytest.fixture
    def trader(self):
        """创建测试用模拟交易器"""
        return SimulationTrader(config_path='tests/fixtures/test_config.yaml')
    
    def test_full_trade_cycle(self, trader):
        """测试完整交易周期：买入 -> 持有 -> 卖出"""
        # 1. 买入
        trader.buy_stock('600000', shares=100, price=10.00)
        
        # 验证持仓
        positions = trader.repo.get_all_positions()
        assert len(positions) == 1
        assert positions[0].symbol == '600000'
        assert positions[0].shares == 100
        
        # 2. 卖出
        trader.sell_stock('600000', shares=100, price=11.00)
        
        # 验证持仓清空
        positions = trader.repo.get_all_positions()
        assert len(positions) == 0
        
        # 验证盈利
        account = trader.repo.get_account()
        assert account.cash > trader.config['trading']['initial_cash']
```

---

## 📋 迁移检查清单

### Phase 1: 日志规范化
- [ ] `simulation_broker.py` 使用结构化日志
- [ ] `simulation_trader.py` 使用结构化日志
- [ ] 删除 `logging.basicConfig` 配置
- [ ] 使用 `structlog.get_logger(__name__)`

### Phase 2: 数据类型规范化
- [ ] 金额字段使用 `Decimal` 类型
- [ ] Repository 返回类型统一为 ORM 对象
- [ ] 删除 dict/ORM 兼容代码

### Phase 3: 配置统一
- [ ] 迁移配置到 .env 文件
- [ ] 添加配置验证函数
- [ ] 删除独立的 YAML 配置文件

### Phase 4: 测试补充
- [ ] 添加 Broker 单元测试
- [ ] 添加 Repository 单元测试
- [ ] 添加 Trader 集成测试
- [ ] 测试覆盖率 >= 80%

---

## ✅ 规范收益

### 代码质量
- ✅ 类型安全（Decimal 避免浮点数精度问题）
- ✅ 日志可追踪（结构化日志 + trace ID）
- ✅ 接口清晰（统一的 Repository 接口）
- ✅ 易于测试（依赖注入，可 mock）

### 可维护性
- ✅ 配置集中管理
- ✅ 数据模型一致
- ✅ 代码职责清晰
- ✅ 易于扩展到真实券商

### 可观测性
- ✅ 所有交易可追踪
- ✅ 异常有详细日志
- ✅ 性能可监控（耗时记录）
- ✅ 数据完整性可验证

---

## 📚 参考文档

- [Python Decimal 文档](https://docs.python.org/3/library/decimal.html)
- [SQLAlchemy ORM 文档](https://docs.sqlalchemy.org/en/20/orm/)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- 本项目实现: `live_trading/simulation_*.py`
