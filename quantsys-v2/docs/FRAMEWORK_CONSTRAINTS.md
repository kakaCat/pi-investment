# 框架使用规范与常见陷阱

**版本**: 1.0  
**生效日期**: 2026-08-15  
**适用范围**: quantsys-v2 项目

---

## 目录

1. [ORM 使用规范](#orm-使用规范)
2. [SQLAlchemy Session 管理](#sqlalchemy-session-管理)
3. [Repository 模式约束](#repository-模式约束)
4. [数据库事务处理](#数据库事务处理)
5. [常见 Bug 及预防](#常见-bug-及预防)
6. [FastAPI 特定约束](#fastapi-特定约束)
7. [并发与线程安全](#并发与线程安全)

---

## ORM 使用规范

### 1. Session 生命周期

#### ✅ 正确：使用 context manager

```python
from infrastructure.persistence.database import get_db_session

def my_service_method():
    """服务方法：使用 context manager 管理 session"""
    with get_db_session() as session:
        # 查询操作
        result = session.query(Stock).filter_by(symbol='600000.SH').first()
        
        # 写操作
        session.add(new_record)
        session.commit()
        
        # session 自动关闭
    
    return result  # ✅ 在 with 块外访问已加载的数据
```

#### ❌ 错误：Session 未正确关闭

```python
def bad_service_method():
    """❌ 错误：session 泄漏"""
    session = get_db_session()
    result = session.query(Stock).all()
    # 忘记关闭 session！
    return result
```

**后果**：
- 连接池耗尽（"too many clients"）
- 内存泄漏
- 死锁风险

### 2. 写后读必须在 with 块外

#### ❌ 错误：在 with 块内读取刚写入的数据

```python
def bad_example():
    """❌ Bug: 在 with 块内读取未提交的数据"""
    with get_db_session() as session:
        # 写入数据
        new_record = Stock(symbol='600000.SH', name='浦发银行')
        session.add(new_record)
        session.commit()
        
        # ❌ 错误：在同一个 with 块内读取
        result = session.query(Stock).filter_by(symbol='600000.SH').first()
        # result 可能读不到刚插入的数据！
    
    return result
```

**根因**：
- `with` 块内 `commit()` 后，session 可能还未真正刷新
- ORM 缓存和数据库状态不同步

#### ✅ 正确：写后读分离

```python
def good_example():
    """✅ 正确：写操作独立，读操作在新 session"""
    # 写入数据
    with get_db_session() as session:
        new_record = Stock(symbol='600000.SH', name='浦发银行')
        session.add(new_record)
        session.commit()
    # session 已关闭，数据已持久化
    
    # 读取数据（新 session）
    with get_db_session() as session:
        result = session.query(Stock).filter_by(symbol='600000.SH').first()
    
    return result  # ✅ 读取到最新数据
```

### 3. Lazy Loading 陷阱

#### ❌ 错误：在 session 关闭后访问关联对象

```python
def bad_lazy_loading():
    """❌ 错误：DetachedInstanceError"""
    with get_db_session() as session:
        stock = session.query(Stock).first()
    
    # ❌ session 已关闭，访问关联对象会报错
    print(stock.klines)  # DetachedInstanceError!
```

#### ✅ 正确：使用 eager loading

```python
from sqlalchemy.orm import joinedload

def good_eager_loading():
    """✅ 正确：使用 joinedload 预加载"""
    with get_db_session() as session:
        stock = session.query(Stock)\
            .options(joinedload(Stock.klines))\
            .first()
        
        # 在 session 关闭前访问关联对象
        klines_data = [k.to_dict() for k in stock.klines]
    
    return klines_data  # ✅ 数据已加载到内存
```

---

## SQLAlchemy Session 管理

### 1. Repository 中的 Session

#### ✅ 正确：Repository 接收 session

```python
from infrastructure.persistence.orm import BaseORMRepository

class StockORMRepository(BaseORMRepository):
    """✅ 正确：继承 BaseORMRepository，自动获得 session"""
    
    def get_by_symbol(self, symbol: str):
        """查询方法：使用继承的 self.session"""
        return self.session.query(Stock).filter_by(symbol=symbol).first()
    
    def create(self, stock_data: Dict):
        """写入方法：使用继承的 self.session"""
        stock = Stock(**stock_data)
        self.session.add(stock)
        self.session.commit()
        return stock.id
```

#### ❌ 错误：Repository 内部创建 session

```python
class BadRepository:
    """❌ 错误：自己管理 session"""
    
    def get_by_symbol(self, symbol: str):
        # ❌ 错误：创建新 session
        with get_db_session() as session:
            return session.query(Stock).filter_by(symbol=symbol).first()
```

**为什么错？**
- 破坏了事务边界
- 无法跨 Repository 共享事务
- 增加连接开销

### 2. Service 层事务管理

#### ✅ 正确：Service 控制事务边界

```python
class StockDataService:
    """✅ 正确：Service 层控制事务"""
    
    def __init__(self):
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        self.stock_repo: IStockRepository = StockORMRepository()
    
    def update_stock_with_klines(self, symbol: str, kline_data: List):
        """复杂操作：Service 控制整个事务"""
        with get_db_session() as session:
            # Repository 使用同一个 session
            self.stock_repo.session = session
            
            # 更新 stock
            stock = self.stock_repo.get_by_symbol(symbol)
            stock.last_update = datetime.now()
            
            # 批量插入 klines
            for kline in kline_data:
                session.add(Kline(**kline))
            
            session.commit()  # 一次性提交
```

---

## Repository 模式约束

### 1. 返回类型规范

#### ✅ 正确：返回字典或领域模型

```python
class StockORMRepository(BaseORMRepository):
    def get_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """✅ 返回字典（JSON 可序列化）"""
        row = self.session.query(Stock).filter_by(symbol=symbol).first()
        if row:
            return {
                'symbol': row.symbol,
                'name': row.name,
                'market': row.market,
                # ...
            }
        return None
    
    def get_all(self) -> List[Dict[str, Any]]:
        """✅ 返回字典列表"""
        rows = self.session.query(Stock).all()
        return [self._to_dict(row) for row in rows]
```

#### ❌ 错误：返回 ORM 对象

```python
class BadRepository:
    def get_by_symbol(self, symbol: str) -> Stock:
        """❌ 错误：返回 ORM 对象"""
        return self.session.query(Stock).filter_by(symbol=symbol).first()
        # 问题：ORM 对象绑定 session，session 关闭后无法访问
```

### 2. 批量操作性能

#### ✅ 正确：使用 bulk 操作

```python
def bulk_insert_klines(self, klines: List[Dict]) -> int:
    """✅ 正确：使用 bulk_insert_mappings"""
    from sqlalchemy import insert
    
    # 方法 1: bulk_insert_mappings（推荐）
    self.session.bulk_insert_mappings(Kline, klines)
    self.session.commit()
    
    # 方法 2: 批量 INSERT（更快）
    stmt = insert(Kline).values(klines)
    self.session.execute(stmt)
    self.session.commit()
    
    return len(klines)
```

#### ❌ 错误：循环单条插入

```python
def bad_insert_klines(self, klines: List[Dict]) -> int:
    """❌ 错误：循环插入，性能极差"""
    count = 0
    for kline in klines:
        self.session.add(Kline(**kline))
        self.session.commit()  # ❌ 每次都 commit！
        count += 1
    return count
```

**性能对比**：
- 循环插入 1000 条：~30 秒
- bulk_insert_mappings：~0.5 秒
- bulk INSERT：~0.2 秒

---

## 数据库事务处理

### 1. 异常处理

#### ✅ 正确：捕获异常并回滚

```python
def safe_create_stock(self, stock_data: Dict) -> Optional[int]:
    """✅ 正确：异常处理 + 回滚"""
    try:
        stock = Stock(**stock_data)
        self.session.add(stock)
        self.session.commit()
        return stock.id
    except IntegrityError as e:
        self.session.rollback()  # ✅ 回滚事务
        logger.error(f"Stock creation failed: {e}")
        return None
    except Exception as e:
        self.session.rollback()
        logger.error(f"Unexpected error: {e}")
        raise
```

#### ❌ 错误：不处理异常

```python
def bad_create_stock(self, stock_data: Dict) -> int:
    """❌ 错误：异常不回滚，session 进入脏状态"""
    stock = Stock(**stock_data)
    self.session.add(stock)
    self.session.commit()  # 可能失败但不处理
    return stock.id
```

### 2. 嵌套事务

#### ✅ 正确：使用 SAVEPOINT

```python
def complex_operation(self):
    """✅ 正确：使用 nested() 创建 SAVEPOINT"""
    with get_db_session() as session:
        # 外层事务
        session.add(Stock(symbol='600000.SH'))
        
        # 内层事务（SAVEPOINT）
        with session.begin_nested():
            try:
                # 可能失败的操作
                session.add(Stock(symbol='INVALID'))
                session.flush()
            except:
                # 只回滚内层事务
                pass
        
        # 外层事务继续
        session.commit()
```

---

## 常见 Bug 及预防

### Bug 1: 连接池耗尽

**症状**：
```
psycopg2.OperationalError: FATAL: too many clients already
```

**根因**：
- Session 未关闭
- 连接泄漏累积

**修复**：
```python
# ❌ 错误
def bad_code():
    session = get_db_session()
    result = session.query(Stock).all()
    return result  # session 未关闭！

# ✅ 正确
def good_code():
    with get_db_session() as session:
        result = session.query(Stock).all()
    return result  # session 自动关闭
```

**预防**：
- 始终使用 `with get_db_session()`
- 监控连接池使用率
- 设置合理的 pool_size 和 max_overflow

### Bug 2: FastAPI Session 池耗尽

**症状**：
- FastAPI 接口 500 错误
- 响应时间 30 秒超时

**根因**（2026-08-18 修复）：
- Flask→FastAPI 迁移时遗失 `teardown_appcontext`
- Session 实例缓存在请求期间
- `_IncludedRouter` 重建 `dependant` 导致中间件失效

**修复**：
```python
# middleware.py
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    """✅ 中间件：确保 session 关闭"""
    response = None
    try:
        response = await call_next(request)
    finally:
        # 清理 session（如果有）
        if hasattr(request.state, "db_session"):
            request.state.db_session.close()
    return response

# dependencies.py
def get_db():
    """✅ 依赖注入：创建并清理 session"""
    session = get_db_session()
    try:
        yield session
    finally:
        session.close()
```

**预防**：
- 使用 FastAPI 的依赖注入系统
- 添加 middleware 作为安全网
- 监控连接池指标

### Bug 3: 写后读数据丢失

**症状**：
- 插入数据后立即查询，查不到
- 测试断言失败（明明插入了）

**根因**（2026-08-18 修复）：
- 在同一个 `with` 块内写后读
- `commit()` 后 session 缓存未刷新

**修复**：
```python
# ❌ 错误
def bad_code():
    with get_db_session() as session:
        session.add(Stock(symbol='600000.SH'))
        session.commit()
        
        # ❌ 读不到刚插入的数据
        result = session.query(Stock).filter_by(symbol='600000.SH').first()
    return result

# ✅ 正确
def good_code():
    # 写操作
    with get_db_session() as session:
        session.add(Stock(symbol='600000.SH'))
        session.commit()
    
    # 读操作（新 session）
    with get_db_session() as session:
        result = session.query(Stock).filter_by(symbol='600000.SH').first()
    return result
```

**预防**：
- 写后读必须开新 session
- 单元测试中验证写后读逻辑

### Bug 4: Action 大小写不匹配

**症状**（2026-08-12 修复）：
- 幽灵持仓（已卖出股票仍显示持有）
- 估值异常

**根因**：
- 数据库存储 `action='sell'`（小写）
- 重建 SQL 匹配 `action='SELL'`（大写）
- 导致卖出记录未被识别

**修复**：
```python
def normalize_action(action: str) -> str:
    """✅ 标准化 action 为大写"""
    return action.upper() if action else action

# Repository 层
def create_trade(self, trade_data: Dict) -> int:
    """✅ 写入时强制大写"""
    trade_data['action'] = normalize_action(trade_data.get('action'))
    trade = Trade(**trade_data)
    self.session.add(trade)
    self.session.commit()
    return trade.id

# SQL 查询层
WHERE UPPER(action) = 'SELL'  # ✅ 大小写不敏感查询
```

**预防**：
- 所有枚举值统一大小写
- 数据库层添加 CHECK 约束
- ORM 模型添加 `@validates` 装饰器

### Bug 5: T+1 可卖数量错误

**症状**（2026-08-12 修复）：
- 当日买入股票显示可卖
- 422 错误但无详细信息

**根因**：
- `shares_available` 未区分 T+0 和 T+1
- 错误响应缺少 `details` 字段

**修复**：
```python
class Position:
    @property
    def shares_available(self) -> int:
        """✅ 计算可卖数量（排除当日买入）"""
        if not self.trades:
            return self.shares
        
        # 当日买入的数量
        today = date.today()
        today_buy = sum(
            t.shares for t in self.trades
            if t.action == 'BUY' and t.trade_date == today
        )
        
        # 可卖 = 总持仓 - 当日买入
        return max(0, self.shares - today_buy)

# API 响应
return JSONResponse(
    status_code=422,
    content={
        'error': 'Insufficient shares',
        'details': {  # ✅ 透出详细信息
            'requested': shares,
            'available': position.shares_available,
            'total': position.shares,
            'reason': 'T+1 settlement rule'
        }
    }
)
```

**预防**：
- Position 模型添加 T+1 逻辑
- API 返回详细错误信息
- 前端显示可卖数量

---

## FastAPI 特定约束

### 1. 依赖注入

#### ✅ 正确：使用 Depends

```python
from fastapi import Depends
from infrastructure.persistence.database import get_db

@app.get("/stocks/{symbol}")
def get_stock(symbol: str, db: Session = Depends(get_db)):
    """✅ 正确：依赖注入 session"""
    stock = db.query(Stock).filter_by(symbol=symbol).first()
    return stock.to_dict() if stock else None
```

#### ❌ 错误：手动管理 session

```python
@app.get("/stocks/{symbol}")
def get_stock(symbol: str):
    """❌ 错误：手动创建 session"""
    with get_db_session() as session:
        stock = session.query(Stock).filter_by(symbol=symbol).first()
    return stock
```

### 2. 后台任务

#### ✅ 正确：使用 BackgroundTasks

```python
from fastapi import BackgroundTasks

def process_klines(symbol: str):
    """后台任务函数"""
    with get_db_session() as session:
        # 长时间处理...
        pass

@app.post("/klines/update")
def update_klines(
    symbol: str,
    background_tasks: BackgroundTasks
):
    """✅ 正确：后台任务有独立 session"""
    background_tasks.add_task(process_klines, symbol)
    return {"status": "processing"}
```

#### ❌ 错误：在请求处理中长时间持有 session

```python
@app.post("/klines/update")
def update_klines(symbol: str, db: Session = Depends(get_db)):
    """❌ 错误：占用连接太久"""
    # 长时间处理（几分钟）
    for i in range(10000):
        db.add(Kline(...))
    db.commit()  # 连接占用太久！
```

---

## 并发与线程安全

### 1. Session 线程安全

**❌ 禁止：跨线程共享 Session**

```python
# ❌ 错误：全局 session
global_session = get_db_session()  # 危险！

def thread_worker():
    # ❌ 多线程共享 session
    result = global_session.query(Stock).all()
```

**✅ 正确：每个线程独立 Session**

```python
import threading

def thread_worker():
    """✅ 每个线程独立创建 session"""
    with get_db_session() as session:
        result = session.query(Stock).all()
        # 处理 result...

threads = [threading.Thread(target=thread_worker) for _ in range(10)]
for t in threads:
    t.start()
```

### 2. 连接池配置

```python
# infrastructure/persistence/database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # ✅ 基础连接数
    max_overflow=20,        # ✅ 最大溢出连接
    pool_timeout=30,        # ✅ 获取连接超时
    pool_recycle=3600,      # ✅ 1 小时回收连接
    pool_pre_ping=True,     # ✅ 连接健康检查
)
```

**配置说明**：
- `pool_size=10`: 常驻连接 10 个（覆盖 90% 负载）
- `max_overflow=20`: 峰值最多 30 个连接（10+20）
- `pool_timeout=30`: 30 秒内获取不到连接则报错
- `pool_recycle=3600`: 1 小时回收连接（防止 MySQL gone away）
- `pool_pre_ping=True`: 使用前 ping 一下（防止死连接）

---

## Code Review 检查点

### Session 管理

- [ ] 是否使用 `with get_db_session()`？
- [ ] 是否有 session 泄漏风险？
- [ ] 写后读是否在新 session 中？

### Repository 模式

- [ ] Repository 是否返回字典/模型？
- [ ] 是否有批量操作可以优化？
- [ ] 异常是否正确处理和回滚？

### FastAPI 集成

- [ ] 是否使用 `Depends(get_db)`？
- [ ] 长任务是否用 BackgroundTasks？
- [ ] 是否有中间件确保清理？

### 性能

- [ ] 是否使用 eager loading（避免 N+1）？
- [ ] 批量操作是否用 bulk 方法？
- [ ] 连接池配置是否合理？

---

## 参考资料

### 内部文档

- [Bug 修复: FastAPI Session 池耗尽](docs/superpowers/specs/2026-08-18-fastapi-session-pool-fix.md)
- [Bug 修复: 写后读数据丢失](docs/superpowers/specs/2026-08-18-baserepo-migration-audit.md)
- [Bug 修复: Action 大小写](docs/superpowers/specs/2026-08-12-trade-action-case-fix.md)
- [Bug 修复: T+1 可卖数量](docs/superpowers/specs/2026-08-12-t1-sellable-visibility.md)

### 外部资料

- [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/14/orm/session_basics.html)
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Database Connection Pooling](https://docs.sqlalchemy.org/en/14/core/pooling.html)

---

**维护者**: Architecture Team  
**最后更新**: 2026-08-15  
**版本历史**:
- v1.0 (2026-08-15): 初始版本，整合历史 bug 修复经验
