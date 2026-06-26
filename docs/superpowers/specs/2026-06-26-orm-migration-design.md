# 项目全量ORM迁移计划

## Context

当前项目使用 SQLAlchemy Engine 管理连接池，但所有数据库操作都是原生 psycopg2 + SQL。这导致：
1. 代码冗长，大量重复的 cursor 操作
2. 容易出现连接泄漏（如V13任务）
3. 缺少对象关系映射，业务逻辑和数据访问混杂
4. 难以维护，修改表结构需要同步更新多处SQL

用户决策：
- **全量迁移**：所有29个Repository（11,515行代码，40+张表）改造为ORM
- **重构接口**：设计符合ORM风格的新接口
- **全局scoped_session**：自动管理线程级Session
- **单元测试覆盖**：确保迁移正确性

## 项目现状

### 统计数据
- Repository文件：29个
- 代码行数：11,515行
- 数据库表：40+张（包括 daily_klines, simulation_account, signals 等）
- 调用方：DataService, 各种Job, SimulationTrader 等

### 架构模式
```
调用方 → Repository (原生SQL + psycopg2) → PostgreSQL
              ↓
         BaseRepository (管理连接)
              ↓
      SQLAlchemy Engine (连接池)
```

### 典型代码模式
```python
class StockRepository(BaseRepository):
    def get_stock(self, symbol: str) -> Optional[Dict]:
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM quant.stocks WHERE symbol = %s", (symbol,))
        result = cursor.fetchone()
        cursor.close()
        return dict(result) if result else None
```

**问题**：
- 手工管理 cursor
- 返回 dict 而不是对象
- SQL 字符串分散在代码中
- 没有类型提示

## 目标架构

### ORM模式
```
调用方 → Repository (ORM Query) → SQLAlchemy ORM → PostgreSQL
              ↓
         Session (scoped_session)
              ↓
      SQLAlchemy Engine (连接池)
```

### ORM代码模式
```python
# 1. Model定义
class Stock(Base):
    __tablename__ = 'stocks'
    __table_args__ = {'schema': 'quant'}
    
    symbol = Column(String(10), primary_key=True)
    name = Column(String(50))
    exchange = Column(String(10))
    
    # 关系映射
    klines = relationship('DailyKline', back_populates='stock')

# 2. Repository
class StockRepository:
    def get_stock(self, symbol: str) -> Optional[Stock]:
        return session.query(Stock).filter_by(symbol=symbol).first()
    
    def list_stocks(self, exchange: str = None) -> List[Stock]:
        query = session.query(Stock)
        if exchange:
            query = query.filter_by(exchange=exchange)
        return query.all()
```

**优势**：
- ✅ 自动管理会话，无需手动 close
- ✅ 返回类型化对象，IDE支持补全
- ✅ SQL生成自动化，减少错误
- ✅ 支持关系映射（一对多、多对多）

## 实施计划

### 阶段1: 基础设施搭建（第1周）

#### 1.1 创建ORM配置模块
**文件**: `infrastructure/persistence/orm/config.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from infrastructure.persistence.database.engine import _resolve_db_dsn

Base = declarative_base()
engine = None
Session = None

def init_orm(echo=False):
    """初始化ORM（应用启动时调用一次）"""
    global engine, Session
    dsn = _resolve_db_dsn()
    engine = create_engine(
        dsn,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=echo
    )
    Session = scoped_session(sessionmaker(bind=engine))
    return engine, Session

def get_session():
    """获取当前线程的Session"""
    if Session is None:
        init_orm()
    return Session()

def close_session():
    """关闭当前线程的Session"""
    if Session:
        Session.remove()
```

#### 1.2 定义所有Model
**目录结构**:
```
infrastructure/persistence/orm/
├── __init__.py
├── config.py           # ORM配置
├── base.py            # Base和通用Mixin
└── models/
    ├── __init__.py
    ├── stock.py       # Stock, DailyKline, MinuteKline
    ├── signal.py      # Signal, SignalExecution, SignalExecutionLog
    ├── portfolio.py   # Position, PortfolioHolding
    ├── simulation.py  # SimulationAccount, SimulationPosition, SimulationTrade
    ├── backtest.py    # BacktestResult
    ├── factor.py      # FactorValue, FactorCalculation
    ├── risk.py        # RiskMetric, RiskConfig
    └── ...
```

**Model设计原则**:
1. 使用 `__table_args__ = {'schema': 'quant'}` 指定schema
2. 主键、索引、约束与数据库一致
3. 添加 `relationship()` 建立关系映射
4. 时间字段使用 `DateTime(timezone=True)`
5. 添加 `__repr__()` 方便调试

**示例**: `models/stock.py`
```python
from sqlalchemy import Column, String, Float, Date, BigInteger, Index
from sqlalchemy.orm import relationship
from ..base import Base

class Stock(Base):
    __tablename__ = 'stocks'
    __table_args__ = (
        Index('idx_stocks_exchange', 'exchange'),
        {'schema': 'quant'}
    )
    
    symbol = Column(String(10), primary_key=True, comment='股票代码')
    name = Column(String(50), nullable=False, comment='股票名称')
    exchange = Column(String(10), nullable=False, comment='交易所')
    list_date = Column(Date, comment='上市日期')
    
    # 关系
    klines = relationship('DailyKline', back_populates='stock', lazy='dynamic')
    
    def __repr__(self):
        return f"<Stock(symbol='{self.symbol}', name='{self.name}')>"

class DailyKline(Base):
    __tablename__ = 'daily_klines'
    __table_args__ = (
        Index('idx_klines_symbol_date', 'symbol', 'trade_date'),
        {'schema': 'quant'}
    )
    
    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(10), ForeignKey('quant.stocks.symbol'), nullable=False)
    trade_date = Column(Date, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    amount = Column(Float)
    
    # 关系
    stock = relationship('Stock', back_populates='klines')
```

#### 1.3 编写Model生成工具
**文件**: `scripts/generate_models.py`

使用 `sqlacodegen` 或自定义脚本从现有数据库生成Model骨架：
```bash
pip install sqlacodegen
sqlacodegen postgresql://user:pass@host/db --schema quant --outfile models_generated.py
```

然后手工调整：
- 添加关系映射
- 优化类型
- 添加注释

### 阶段2: Repository重构（第2-3周）

#### 2.1 新接口设计规范

**原则**:
1. 方法返回 Model 对象或 List[Model]，而不是 dict
2. 查询方法使用 `get_`, `list_`, `find_` 前缀
3. 写入方法使用 `create_`, `update_`, `delete_` 前缀
4. 支持链式查询（返回Query对象）

**对比**:
```python
# 旧接口
def get_stock(self, symbol: str) -> Optional[Dict]:
    cursor = self.conn.cursor()
    cursor.execute("SELECT * FROM quant.stocks WHERE symbol = %s", (symbol,))
    result = cursor.fetchone()
    cursor.close()
    return dict(result) if result else None

# 新接口
def get_stock(self, symbol: str) -> Optional[Stock]:
    """获取单只股票"""
    return get_session().query(Stock).filter_by(symbol=symbol).first()

def list_stocks(
    self, 
    exchange: Optional[str] = None,
    limit: int = None
) -> List[Stock]:
    """列出股票"""
    query = get_session().query(Stock)
    if exchange:
        query = query.filter_by(exchange=exchange)
    if limit:
        query = query.limit(limit)
    return query.all()
```

#### 2.2 Base Repository重构

**文件**: `infrastructure/persistence/orm/base_repository.py`

```python
from sqlalchemy.orm import Session
from typing import TypeVar, Generic, Type, Optional, List
from .config import get_session

T = TypeVar('T')

class BaseORMRepository(Generic[T]):
    """ORM基础Repository"""
    
    model: Type[T] = None
    
    def __init__(self):
        self.session: Session = get_session()
    
    def get_by_id(self, id: any) -> Optional[T]:
        """根据主键获取"""
        return self.session.query(self.model).get(id)
    
    def list_all(self, limit: int = None) -> List[T]:
        """列出所有"""
        query = self.session.query(self.model)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def create(self, obj: T) -> T:
        """创建"""
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj
    
    def update(self, obj: T) -> T:
        """更新"""
        self.session.merge(obj)
        self.session.commit()
        return obj
    
    def delete(self, obj: T):
        """删除"""
        self.session.delete(obj)
        self.session.commit()
```

#### 2.3 Repository迁移优先级

**批次1（核心，优先）**:
1. `stock_repository.py` - 股票基础数据
2. `kline_repository.py` - K线数据
3. `simulation_repository.py` - 模拟交易
4. `signal_repository.py` - 信号
5. `portfolio_repository.py` - 持仓

**批次2（关键业务）**:
6. `backtest_repository.py`
7. `factor_repository.py`
8. `risk_repository.py`
9. `strategy_repository.py`

**批次3（其他）**:
10-29. 剩余Repository

**每个Repository迁移步骤**:
1. 定义对应的Model（如果还没有）
2. 继承 `BaseORMRepository`
3. 重写查询方法，使用ORM Query API
4. 编写单元测试
5. 更新调用方（如DataService）

### 阶段3: 调用方适配（第3-4周）

#### 3.1 DataService改造

**文件**: `application/services/data_service.py`

```python
# 旧代码
def get_stock_full_data(self, symbol: str, start_date: str, end_date: str) -> Dict:
    stock = self.stock.get_stock(symbol)  # 返回dict
    klines = self.kline.get_klines(symbol, start_date, end_date)  # 返回List[Dict]
    
    return {
        'symbol': stock['symbol'],
        'name': stock['name'],
        'klines': klines
    }

# 新代码
def get_stock_full_data(self, symbol: str, start_date: str, end_date: str) -> StockFullData:
    stock = self.stock.get_stock(symbol)  # 返回Stock对象
    klines = self.kline.list_klines(symbol, start_date, end_date)  # 返回List[DailyKline]
    
    return StockFullData(
        stock=stock,
        klines=klines
    )
```

#### 3.2 SimulationTrader改造

**文件**: `live_trading/simulation_trader.py`

```python
# 旧代码
positions = self.repo.get_all_positions()  # List[Dict]
for pos in positions:
    self.portfolio[pos['symbol']] = {
        'shares': pos['shares'],
        'avg_price': pos['avg_price']
    }

# 新代码
positions = self.repo.list_positions()  # List[SimulationPosition]
for pos in positions:
    self.portfolio[pos.symbol] = pos  # 直接使用对象
```

#### 3.3 Job改造

所有 Job（如 `v13_trading_job.py`）中：
- 将 dict 访问改为对象属性访问
- 不再需要手动 `close()` 连接（scoped_session自动管理）

### 阶段4: 测试与验证（第4-5周）

#### 4.1 单元测试编写

为每个Repository编写测试：

**文件**: `tests/orm/test_stock_repository.py`
```python
import pytest
from infrastructure.persistence.orm.models.stock import Stock
from adapters.outbound.repositories.stock_repository import StockRepository

@pytest.fixture
def repo():
    return StockRepository()

def test_get_stock(repo):
    stock = repo.get_stock('000001')
    assert stock is not None
    assert isinstance(stock, Stock)
    assert stock.symbol == '000001'

def test_list_stocks(repo):
    stocks = repo.list_stocks(exchange='SZ', limit=10)
    assert len(stocks) <= 10
    assert all(isinstance(s, Stock) for s in stocks)
    assert all(s.exchange == 'SZ' for s in stocks)
```

目标：**80%+ 代码覆盖率**

#### 4.2 集成测试

测试关键业务流程：
1. V13模拟交易完整流程
2. 回测流程
3. 信号生成和执行

#### 4.3 性能测试

对比ORM vs 原生SQL性能：
- 单条查询延迟
- 批量查询吞吐量
- 内存占用

预期ORM会慢10-30%，但可以接受（换取可维护性）

### 阶段5: 灰度发布（第5周）

#### 5.1 Feature Flag

添加配置项控制ORM启用：

**文件**: `.env`
```bash
USE_ORM=false  # 默认false，逐步切换到true
```

**代码**:
```python
if os.getenv('USE_ORM', 'false') == 'true':
    from adapters.outbound.repositories.orm.stock_repository import StockRepository
else:
    from adapters.outbound.repositories.stock_repository import StockRepository
```

#### 5.2 灰度步骤

1. **开发环境**：启用ORM，运行所有测试
2. **测试环境**：启用ORM，运行业务流程
3. **生产环境**：
   - 第1天：仅查询接口用ORM（只读，风险低）
   - 第3天：写入接口也用ORM
   - 第7天：完全切换到ORM，移除旧代码

#### 5.3 监控指标

- 数据库连接池状态（不应再泄漏）
- SQL查询性能（通过 `echo=True` 日志）
- 应用错误率
- 响应时间

## 关键风险与缓解

### 风险1: 数据不一致
**缓解**:
- 严格的单元测试覆盖
- 对比ORM生成的SQL与原SQL
- 灰度发布，小范围验证

### 风险2: 性能下降
**缓解**:
- 使用 `lazy='dynamic'` 避免N+1查询
- 关键查询使用 `joinedload()` 预加载
- 必要时用原生SQL（`session.execute()`）

### 风险3: 学习成本
**缓解**:
- 编写ORM使用文档
- 代码Review确保规范
- Pair Programming传播知识

### 风险4: 回滚困难
**缓解**:
- Feature Flag支持快速回退
- 保留旧Repository代码至少1个月
- 数据库schema不变（ORM只是访问层）

## 工作量估算

| 阶段 | 工作项 | 预计时间 | 人力 |
|------|--------|----------|------|
| 1 | ORM基础设施 | 3天 | 1人 |
| 1 | Model定义（40+张表） | 5天 | 2人 |
| 2 | Repository重构（29个） | 10天 | 2人 |
| 3 | 调用方适配 | 5天 | 2人 |
| 4 | 测试编写 | 5天 | 2人 |
| 5 | 灰度发布 | 2天 | 1人 |
| **总计** | | **30天** | **2人** |

## 交付物

1. **代码**:
   - `infrastructure/persistence/orm/` - ORM配置和Model
   - 29个重构后的Repository
   - 单元测试（80%+覆盖率）

2. **文档**:
   - ORM使用指南
   - Model关系图
   - 迁移日志

3. **工具**:
   - Model生成脚本
   - 测试数据初始化脚本

## 验证标准

✅ 所有现有功能正常（V13模拟交易、回测、信号生成）
✅ 单元测试覆盖率 > 80%
✅ 集成测试通过
✅ 生产环境运行7天无故障
✅ 连接池无泄漏
✅ 性能下降 < 30%
