# ORM使用指南

## 概述

quantsys-v2已完成ORM基础设施搭建，提供SQLAlchemy ORM支持。

**当前状态**: 阶段1完成 ✅
- ✅ ORM配置模块（scoped_session）
- ✅ Base类和Mixin
- ✅ BaseORMRepository
- ✅ 核心Model（Stock, DailyKline, MinuteKline, Signal, SimulationAccount等）
- ✅ StockORMRepository示例
- ✅ 功能测试通过

**下一步**: 阶段2 - 逐步迁移29个Repository

## 目录结构

```
infrastructure/persistence/orm/
├── __init__.py              # 模块入口
├── config.py                # ORM配置（init_orm, get_session等）
├── base.py                  # Base类和Mixin
├── base_repository.py       # 基础Repository
└── models/
    ├── __init__.py          # Model统一导出
    ├── stock.py             # Stock, DailyKline
    ├── kline.py             # MinuteKline
    ├── signal.py            # Signal, SignalExecution
    └── simulation.py        # SimulationAccount, Position, Trade

adapters/outbound/repositories/orm/
└── stock_repository.py      # StockORMRepository（示例）
```

## 快速开始

### 1. 应用启动时初始化ORM

```python
from infrastructure.persistence.orm import init_orm

# 在应用启动时调用一次
init_orm(echo=False)  # echo=True时会打印SQL日志
```

### 2. 使用Model进行查询

```python
from infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models import Stock, DailyKline

# 获取Session（线程安全）
session = get_session()

# 查询单个股票
stock = session.query(Stock).filter_by(symbol='000001').first()
print(f"{stock.name}: ROE={stock.roe}%")

# 查询列表
stocks = session.query(Stock).filter_by(market='A').limit(10).all()

# 关系映射（自动JOIN）
stock = session.query(Stock).filter_by(symbol='000001').first()
klines = stock.daily_klines.order_by(DailyKline.trade_date.desc()).limit(10).all()

# 请求/Job结束时清理Session
from infrastructure.persistence.orm import close_session
close_session()
```

### 3. 使用Repository

```python
from adapters.outbound.repositories.orm.stock_repository import StockORMRepository

repo = StockORMRepository()

# 查询单只股票
stock = repo.get_by_symbol('000001')
print(f"{stock.symbol} {stock.name}")

# 按市场查询
a_stocks = repo.list_by_market(market='A', limit=10)

# 搜索
results = repo.search_by_name('平安', limit=5)

# 统计
count = repo.count_by_market('A')

# 获取行业列表
industries = repo.get_industries()
```

## 核心API

### ORM配置（config.py）

```python
from infrastructure.persistence.orm import (
    init_orm,        # 初始化ORM（应用启动时调用）
    get_session,     # 获取当前线程的Session
    close_session,   # 关闭当前线程的Session
    get_engine,      # 获取Engine实例
    is_initialized   # 检查是否已初始化
)
```

### Base和Mixin（base.py）

```python
from infrastructure.persistence.orm import Base, TimestampMixin, to_dict

# 定义Model
class MyModel(Base, TimestampMixin):  # TimestampMixin自动管理created_at/updated_at
    __tablename__ = 'my_table'
    __table_args__ = {'schema': 'quant'}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50))

# 转换为字典
obj = session.query(MyModel).first()
data = to_dict(obj, exclude={'created_at'})
```

### BaseORMRepository

```python
from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import Stock

class MyRepository(BaseORMRepository[Stock]):
    model = Stock
    
    # 继承的方法：
    # - get_by_id(id) -> Optional[T]
    # - list_all(limit, offset) -> List[T]
    # - count() -> int
    # - create(obj, commit=True) -> Optional[T]
    # - create_batch(objs, commit=True) -> bool
    # - update(obj, commit=True) -> Optional[T]
    # - delete(obj, commit=True) -> bool
    # - delete_by_id(id, commit=True) -> bool
    # - commit(), rollback(), flush()
```

## 已有Model

### Stock - 股票基础信息

```python
from infrastructure.persistence.orm.models import Stock

stock = session.query(Stock).filter_by(symbol='000001').first()
print(f"{stock.symbol} {stock.name}")
print(f"市场: {stock.market}, 行业: {stock.industry}")
print(f"ROE: {stock.roe}%, PE: {stock.pe}, PB: {stock.pb}")
print(f"ST: {stock.is_st}, 停牌: {stock.is_suspended}")
```

### DailyKline - 日K线

```python
from infrastructure.persistence.orm.models import DailyKline

# 查询K线
klines = session.query(DailyKline).filter(
    DailyKline.symbol == '000001',
    DailyKline.trade_date >= '2026-01-01'
).order_by(DailyKline.trade_date.desc()).all()

for kline in klines:
    print(f"{kline.trade_date}: O={kline.open}, H={kline.high}, L={kline.low}, C={kline.close}")
```

### Signal - 交易信号

```python
from infrastructure.persistence.orm.models import Signal

# 查询最近的买入信号
signals = session.query(Signal).filter(
    Signal.action == 'BUY',
    Signal.status == 'pending'
).order_by(Signal.created_at.desc()).limit(10).all()

for sig in signals:
    print(f"{sig.signal_date} {sig.symbol} {sig.name}")
    print(f"策略: {sig.strategy_id}, 置信度: {sig.confidence}")
    print(f"指标: {sig.indicators}")
```

### SimulationAccount - 模拟账户

```python
from infrastructure.persistence.orm.models import SimulationAccount, SimulationPosition

# 查询账户
account = session.query(SimulationAccount).filter_by(account_name='default').first()
print(f"账户: {account.account_name}")
print(f"现金: {account.cash}, 总资产: {account.total_value}")
print(f"累计收益: {account.cumulative_return}%, 最大回撤: {account.max_drawdown}%")

# 查询持仓（通过关系映射）
positions = account.positions.all()
for pos in positions:
    print(f"{pos.symbol}: {pos.shares}股 @ {pos.avg_price}")
```

## 关系映射示例

ORM的强大之处在于对象关系映射：

```python
# 股票 -> K线数据（一对多）
stock = session.query(Stock).filter_by(symbol='000001').first()
klines = stock.daily_klines.limit(10).all()  # 懒加载

# 信号 -> 股票（多对一）
signal = session.query(Signal).first()
stock = signal.stock  # 自动JOIN

# 账户 -> 持仓（一对多）
account = session.query(SimulationAccount).filter_by(account_name='default').first()
positions = account.positions.filter(SimulationPosition.shares > 0).all()
```

## Session生命周期管理

### Flask/FastAPI应用

```python
from flask import Flask
from infrastructure.persistence.orm import init_orm, close_session

app = Flask(__name__)

# 应用启动时初始化
@app.before_first_request
def initialize():
    init_orm()

# 每个请求结束时清理
@app.teardown_appcontext
def cleanup(exception=None):
    close_session()

@app.route('/stocks/<symbol>')
def get_stock(symbol):
    repo = StockORMRepository()
    stock = repo.get_by_symbol(symbol)
    if stock:
        return stock.to_dict()
    return {'error': 'Not found'}, 404
```

### Job/脚本

```python
from infrastructure.persistence.orm import init_orm, close_session

def my_job():
    # 初始化
    init_orm()
    
    try:
        # 业务逻辑
        repo = StockORMRepository()
        stocks = repo.list_by_market('A')
        # ...
    finally:
        # 清理
        close_session()
```

## 测试

运行ORM功能测试：

```bash
cd quantsys-v2
PGDATABASE=quant_investment python scripts/test_orm.py
```

测试覆盖：
- ✅ ORM初始化
- ✅ Session管理（线程安全）
- ✅ Model直接查询
- ✅ Repository CRUD操作
- ✅ 关系映射
- ✅ 信号查询

## 迁移指南

### 旧代码（原生SQL + psycopg2）

```python
class StockRepository(BaseRepository):
    def get_stock(self, symbol: str) -> Optional[Dict]:
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM quant.stocks WHERE symbol = %s", (symbol,))
        result = cursor.fetchone()
        cursor.close()
        return dict(result) if result else None
```

### 新代码（ORM）

```python
class StockORMRepository(BaseORMRepository[Stock]):
    model = Stock
    
    def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        return self.session.query(Stock).filter_by(symbol=symbol).first()
```

**优势**：
- ✅ 自动Session管理，无需手动close
- ✅ 返回类型化对象，IDE支持补全
- ✅ SQL生成自动化，减少错误
- ✅ 支持关系映射

## 下一步计划

按照[docs/superpowers/specs/2026-06-26-orm-migration-design.md](../superpowers/specs/2026-06-26-orm-migration-design.md)：

### 阶段2: Repository重构（第2-3周）
- 批次1（核心）：kline_repository, simulation_repository, signal_repository, portfolio_repository
- 批次2（关键）：backtest_repository, factor_repository, risk_repository
- 批次3（其他）：剩余Repository

### 阶段3: 调用方适配（第3-4周）
- DataService改造
- SimulationTrader改造
- Job改造

### 阶段4: 测试与验证（第4-5周）
- 单元测试（80%+覆盖率）
- 集成测试
- 性能测试

### 阶段5: 灰度发布（第5周）
- Feature Flag控制
- 灰度发布
- 监控指标

## 常见问题

### Q: Session何时关闭？
A: 使用scoped_session，每个线程自动管理。请求/Job结束时调用`close_session()`。

### Q: 如何避免N+1查询？
A: 使用`lazy='dynamic'`或`joinedload()`预加载关系。

### Q: 如何执行原生SQL？
A: `session.execute(text("SELECT ..."))` 或使用get_engine()。

### Q: 事务如何管理？
A: Repository方法默认自动commit。如需手动控制，使用`commit=False`参数。

### Q: 如何调试SQL？
A: 初始化时设置`init_orm(echo=True)`，会打印所有SQL语句。

## 参考资料

- [SQLAlchemy ORM官方文档](https://docs.sqlalchemy.org/en/20/orm/)
- [ORM迁移设计文档](../superpowers/specs/2026-06-26-orm-migration-design.md)
- [测试脚本](../../scripts/test_orm.py)
