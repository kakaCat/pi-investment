# ORM + 连接池框架迁移设计

## 🎯 方案选择

### 为什么选择 SQLAlchemy 2.0？

**优势**：
1. ✅ **已在依赖中**（`sqlalchemy>=2.0.0`），零额外安装
2. ✅ **工业级连接池**（QueuePool）：成熟稳定，自动管理生命周期
3. ✅ **性能优异**：连接复用、预编译语句、批量操作优化
4. ✅ **类型安全**：与 Pydantic 完美集成
5. ✅ **灵活性**：支持 ORM + Core（SQL Expression）双模式
6. ✅ **异步支持**：AsyncEngine + AsyncSession（未来可用）
7. ✅ **生态完善**：Alembic 迁移工具、pytest-sqlalchemy 测试支持

### 其他方案对比

| 框架 | 连接池 | 学习曲线 | 性能 | 社区 | 推荐度 |
|------|--------|---------|------|------|--------|
| **SQLAlchemy 2.0** | ✅ QueuePool | 中 | ⭐⭐⭐⭐⭐ | 最大 | ⭐⭐⭐⭐⭐ |
| Peewee | ⚠️ 简单池 | 低 | ⭐⭐⭐ | 小 | ⭐⭐⭐ |
| Tortoise ORM | ✅ 异步池 | 中 | ⭐⭐⭐⭐ | 中等 | ⭐⭐⭐⭐ |
| Django ORM | ✅ 内置池 | 高 | ⭐⭐⭐⭐ | 大 | ⭐⭐ (重量级) |
| 手写 psycopg2 | ❌ 需自己实现 | 低 | ⭐⭐⭐⭐ | N/A | ⭐ (当前方案) |

**结论**：SQLAlchemy 2.0 是最佳选择。

## 📐 架构设计

### 现有架构问题

```python
# ❌ 当前方式：每个 Repository 持有独立连接
class KlineRepository(BaseRepository):
    def __init__(self):
        self.db = psycopg2.connect(dsn)  # 泄漏根源
    
    def get_latest(self, symbol):
        cursor = self.db.cursor()  # 从不关闭
        cursor.execute("SELECT ...")
        return cursor.fetchone()
```

**问题**：
- 26 个 Repository × N 次实例化 = 数百个连接
- 无连接复用
- 手动管理游标生命周期

### 新架构设计

```python
# ✅ SQLAlchemy 方式：全局 Engine + Session 池
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# 1. 全局 Engine（单例，内置连接池）
engine = create_engine(
    "postgresql://user:pass@host:port/db",
    pool_size=10,           # 常驻连接数
    max_overflow=20,        # 额外连接数
    pool_timeout=30,        # 获取连接超时
    pool_recycle=3600,      # 连接回收时间（防止数据库端超时）
    pool_pre_ping=True,     # 连接健康检查
    echo=False              # 生产环境禁用 SQL 日志
)

# 2. Session 工厂
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# 3. Repository 使用 Session（不持有连接）
class KlineRepository:
    def get_latest(self, session: Session, symbol: str):
        return session.query(Kline)\
            .filter(Kline.symbol == symbol)\
            .order_by(Kline.trade_date.desc())\
            .first()

# 4. 依赖注入模式（推荐）
@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# 使用方式
with get_db_session() as session:
    repo = KlineRepository()
    latest = repo.get_latest(session, "600000.SH")
```

**优势**：
- ✅ 连接自动复用（池管理）
- ✅ 事务自动管理（commit/rollback）
- ✅ 连接自动关闭（context manager）
- ✅ 类型安全（ORM 模型）

## 🗂️ ORM 模型设计

### 方案 1: 纯 ORM（推荐用于新表）

```python
# quantsys-v2/infrastructure/database/models.py

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Date, Integer, Text
from datetime import date

class Base(DeclarativeBase):
    pass

class Kline(Base):
    __tablename__ = "klines"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    
    def __repr__(self):
        return f"<Kline(symbol={self.symbol}, date={self.trade_date})>"

class Strategy(Base):
    __tablename__ = "user_indicators"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(Text)
    code_type: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[date]
```

**优势**：
- 类型安全（IDE 自动补全）
- 自动验证（Pydantic 集成）
- 关系映射（外键、一对多）

### 方案 2: SQLAlchemy Core（推荐用于现有表）

```python
# 适用于已有表结构，不想重写 ORM 模型
from sqlalchemy import text

class KlineRepository:
    def get_latest(self, session: Session, symbol: str):
        # 使用 Core API（纯 SQL + 参数绑定）
        result = session.execute(
            text("SELECT * FROM klines WHERE symbol = :symbol ORDER BY trade_date DESC LIMIT 1"),
            {"symbol": symbol}
        )
        return result.mappings().first()
```

**优势**：
- 无需定义 ORM 模型
- 灵活的 SQL 控制
- 渐进式迁移（先用 Core，后续再改 ORM）

### 方案 3: 混合模式（最佳实践）

```python
# 核心表使用 ORM（klines, strategies, backtest_results）
# 复杂查询使用 Core（多表 JOIN、聚合统计）

class KlineRepository:
    def get_latest_orm(self, session: Session, symbol: str):
        # ORM 方式
        return session.query(Kline)\
            .filter(Kline.symbol == symbol)\
            .order_by(Kline.trade_date.desc())\
            .first()
    
    def get_ma_cross_signals(self, session: Session, symbol: str):
        # Core 方式（复杂计算）
        sql = text("""
            SELECT
                symbol,
                trade_date,
                close,
                AVG(close) OVER (ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as ma5,
                AVG(close) OVER (ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as ma20
            FROM klines
            WHERE symbol = :symbol
            ORDER BY trade_date DESC
            LIMIT 100
        """)
        return session.execute(sql, {"symbol": symbol}).mappings().all()
```

## 🔧 连接池配置

### 核心参数说明

```python
# quantsys-v2/infrastructure/database/engine.py

import os
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

def create_db_engine():
    dsn = _resolve_db_dsn()  # 复用现有 DSN 解析逻辑
    
    return create_engine(
        dsn,
        poolclass=QueuePool,           # 队列池（默认）
        
        # === 连接池大小 ===
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        # 常驻连接数（始终保持）
        # 开发: 5, 测试: 10, 生产: 20
        
        max_overflow=int(os.getenv("DB_POOL_MAX_OVERFLOW", "20")),
        # 额外连接数（峰值时可创建）
        # 总连接数上限 = pool_size + max_overflow
        
        # === 超时控制 ===
        pool_timeout=30,
        # 获取连接的超时时间（秒）
        # 超过此时间抛出 TimeoutError
        
        pool_recycle=3600,
        # 连接回收时间（秒）
        # 防止数据库端超时断开（MySQL 8小时，PostgreSQL 默认无限）
        
        # === 健康检查 ===
        pool_pre_ping=True,
        # 获取连接前先 ping 一下
        # 确保连接有效（防止数据库重启后连接失效）
        
        # === 日志 ===
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        # 打印 SQL 语句（开发调试用）
        
        # === 事务隔离级别 ===
        isolation_level="READ COMMITTED",
        # PostgreSQL 默认，适合多数场景
    )
```

### 环境变量配置

```bash
# .env

# 数据库连接池配置
DB_POOL_SIZE=10              # 常驻连接数
DB_POOL_MAX_OVERFLOW=20      # 额外连接数（总上限=30）
DB_POOL_TIMEOUT=30           # 获取连接超时（秒）
DB_POOL_RECYCLE=3600         # 连接回收时间（秒）
DB_POOL_PRE_PING=true        # 连接健康检查

# SQL 日志（生产环境禁用）
SQL_ECHO=false

# 推荐配置（按环境调整）
# 开发环境: DB_POOL_SIZE=5, DB_POOL_MAX_OVERFLOW=10
# 测试环境: DB_POOL_SIZE=10, DB_POOL_MAX_OVERFLOW=20
# 生产环境: DB_POOL_SIZE=20, DB_POOL_MAX_OVERFLOW=30
```

## 📋 迁移计划

### Phase 1: 基础设施（Week 1）

**目标**：建立 SQLAlchemy 基础设施，与现有代码共存。

**任务**：
1. ✅ 创建 `infrastructure/database/engine.py`
   - 全局 Engine 单例
   - Session 工厂
   - `get_db_session()` 上下文管理器

2. ✅ 创建 `infrastructure/database/models.py`
   - 定义核心表的 ORM 模型（Kline, Strategy, BacktestResult）
   - 使用 `DeclarativeBase`（SQLAlchemy 2.0 语法）

3. ✅ 修改 `api/server.py`
   - 初始化 Engine（替代手写连接池）
   - 添加 `app.teardown_appcontext` 清理

4. ✅ 编写测试用例
   - `tests/test_sqlalchemy_engine.py`
   - 验证连接池工作正常

**验收标准**：
- Engine 正常初始化
- 连接池统计正常（`engine.pool.status()`）
- 现有代码继续工作（向后兼容）

### Phase 2: 迁移高频 Repository（Week 2-3）

**优先级排序**（按调用频率）：
1. ⭐⭐⭐ `KlineRepository` - 行情数据查询（高频）
2. ⭐⭐⭐ `StrategyRepository` - 策略 CRUD（高频）
3. ⭐⭐ `BacktestRepository` - 回测历史（中频）
4. ⭐⭐ `FactorRepository` - 因子计算（中频）
5. ⭐ 其他 22 个 Repository（低频）

**迁移策略（以 KlineRepository 为例）**：

```python
# 步骤 1: 创建新版本（保留旧版本）
# quantsys-v2/repositories/kline_repository_v2.py

from sqlalchemy.orm import Session
from infrastructure.database.models import Kline
from infrastructure.database.engine import get_db_session

class KlineRepositoryV2:
    """使用 SQLAlchemy 的新版本"""
    
    def get_latest(self, symbol: str) -> dict:
        with get_db_session() as session:
            kline = session.query(Kline)\
                .filter(Kline.symbol == symbol)\
                .order_by(Kline.trade_date.desc())\
                .first()
            
            if not kline:
                return None
            
            return {
                "symbol": kline.symbol,
                "trade_date": kline.trade_date.isoformat(),
                "open": kline.open,
                "high": kline.high,
                "low": kline.low,
                "close": kline.close,
                "volume": kline.volume,
            }
    
    def batch_get(self, symbols: list[str], start_date: str, end_date: str) -> list[dict]:
        with get_db_session() as session:
            klines = session.query(Kline)\
                .filter(
                    Kline.symbol.in_(symbols),
                    Kline.trade_date >= start_date,
                    Kline.trade_date <= end_date
                )\
                .order_by(Kline.symbol, Kline.trade_date)\
                .all()
            
            return [
                {
                    "symbol": k.symbol,
                    "trade_date": k.trade_date.isoformat(),
                    "close": k.close,
                    # ...
                }
                for k in klines
            ]

# 步骤 2: Service 层切换到新版本
# quantsys-v2/services/backtest_service.py

from repositories.kline_repository_v2 import KlineRepositoryV2

class BacktestService:
    def __init__(self):
        # self.kline_repo = KlineRepository()  # 旧版本
        self.kline_repo = KlineRepositoryV2()  # ✅ 新版本
    
    def run_backtest(self, strategy_id, symbol, start_date, end_date):
        # 业务逻辑不变
        klines = self.kline_repo.batch_get([symbol], start_date, end_date)
        # ...

# 步骤 3: 测试验证
# tests/repositories/test_kline_repository_v2.py

def test_get_latest():
    repo = KlineRepositoryV2()
    result = repo.get_latest("600000.SH")
    assert result is not None
    assert result["symbol"] == "600000.SH"

# 步骤 4: 删除旧版本（确认无引用后）
# rm repositories/kline_repository.py
```

**每个 Repository 迁移检查清单**：
- [ ] 创建 V2 版本（使用 SQLAlchemy）
- [ ] 单元测试通过
- [ ] Service 层切换到 V2
- [ ] 集成测试通过
- [ ] 删除旧版本
- [ ] 更新文档

### Phase 3: 异步支持（Week 4，可选）

**目标**：使用 SQLAlchemy AsyncEngine 提升并发性能。

```python
# infrastructure/database/async_engine.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

async_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host:port/db",  # 注意：asyncpg 驱动
    pool_size=20,
    max_overflow=40,
)

AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

async def get_async_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# 使用方式
async def get_klines_async(symbol: str):
    async with get_async_db_session() as session:
        result = await session.execute(
            select(Kline).where(Kline.symbol == symbol)
        )
        return result.scalars().all()
```

**收益**：
- 并发查询性能提升 3-5 倍
- 适用于高并发场景（WebSocket 推送、批量回测）

**成本**：
- 需要迁移到异步语法（`async/await`）
- 依赖 `asyncpg` 驱动（比 `psycopg2` 更快）

### Phase 4: 清理和优化（Week 5）

**任务**：
1. 删除所有旧 Repository 代码
2. 删除 `infrastructure/database/base_repository.py`
3. 删除手写连接池 `connection_pool.py`
4. 统一异常处理
5. 添加性能监控（慢查询日志）
6. 压力测试和调优

## 📊 性能对比

### 连接管理

| 指标 | 手写 psycopg2 | 手写连接池 | SQLAlchemy |
|------|--------------|-----------|------------|
| 连接复用 | ❌ | ✅ | ✅ |
| 连接泄漏风险 | 高 | 低 | 极低 |
| 连接健康检查 | ❌ | 手动实现 | ✅ 内置 |
| 事务管理 | 手动 | 手动 | ✅ 自动 |
| 学习成本 | 低 | 中 | 中高 |
| 代码量 | 多 | 多 | 少 |

### 查询性能

| 场景 | psycopg2 | SQLAlchemy ORM | SQLAlchemy Core |
|------|---------|----------------|-----------------|
| 简单查询 | 100% | 95% | 98% |
| 批量插入 | 100% | 80% | 95% |
| 复杂 JOIN | 100% | 90% | 98% |
| 连接创建 | 慢（每次） | 快（池复用） | 快（池复用） |

**结论**：SQLAlchemy Core 性能接近原生，ORM 略慢但可接受。

## 🎯 推荐方案

### 最终推荐：渐进式迁移

**Phase 1（立即）**：启用 SQLAlchemy Engine + QueuePool
- 替换手写连接池
- 现有 Repository 继续使用 `psycopg2` cursor
- 通过 `engine.raw_connection()` 获取原生连接

```python
# 兼容旧代码的过渡方案
from infrastructure.database.engine import engine

class BaseRepositoryCompat:
    def __init__(self):
        # 从 Engine 池中获取连接（不是创建新连接）
        self.db = engine.raw_connection()
    
    def close(self):
        self.db.close()  # 归还到池
```

**Phase 2（2-3周）**：迁移到 SQLAlchemy Core
- 保留现有 SQL 语句
- 使用 Session + `text()` 执行
- 参数绑定防止 SQL 注入

**Phase 3（1个月后）**：选择性使用 ORM
- 核心表定义 ORM 模型
- 复杂查询继续用 Core
- 异步场景使用 AsyncEngine

## 📝 代码示例

### 完整示例：从 psycopg2 到 SQLAlchemy

#### 旧代码（psycopg2）

```python
# repositories/strategy_repository.py (旧)

class StrategyRepository(BaseRepository):
    def get_by_id(self, strategy_id: int):
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM user_indicators WHERE id = %s",
            (strategy_id,)
        )
        return cursor.fetchone()
    
    def create(self, name: str, code: str):
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO user_indicators (name, code) VALUES (%s, %s) RETURNING id",
            (name, code)
        )
        self.db.commit()
        return cursor.fetchone()["id"]
```

#### 新代码（SQLAlchemy Core）

```python
# repositories/strategy_repository_v2.py (新)

from sqlalchemy import text
from infrastructure.database.engine import get_db_session

class StrategyRepositoryV2:
    def get_by_id(self, strategy_id: int):
        with get_db_session() as session:
            result = session.execute(
                text("SELECT * FROM user_indicators WHERE id = :id"),
                {"id": strategy_id}
            )
            return result.mappings().first()
    
    def create(self, name: str, code: str):
        with get_db_session() as session:
            result = session.execute(
                text("INSERT INTO user_indicators (name, code) VALUES (:name, :code) RETURNING id"),
                {"name": name, "code": code}
            )
            return result.scalar()
```

#### 新代码（SQLAlchemy ORM）

```python
# repositories/strategy_repository_v3.py (最佳)

from infrastructure.database.models import Strategy
from infrastructure.database.engine import get_db_session

class StrategyRepositoryV3:
    def get_by_id(self, strategy_id: int):
        with get_db_session() as session:
            return session.query(Strategy)\
                .filter(Strategy.id == strategy_id)\
                .first()
    
    def create(self, name: str, code: str):
        with get_db_session() as session:
            strategy = Strategy(name=name, code=code)
            session.add(strategy)
            session.flush()  # 获取自增 ID
            return strategy.id
```

## 🔒 安全性提升

### SQL 注入防护

```python
# ❌ 危险：字符串拼接
sql = f"SELECT * FROM klines WHERE symbol = '{symbol}'"
cursor.execute(sql)  # SQL 注入风险

# ✅ 安全：参数绑定
sql = "SELECT * FROM klines WHERE symbol = %s"
cursor.execute(sql, (symbol,))

# ✅ SQLAlchemy 自动防护
session.query(Kline).filter(Kline.symbol == symbol)  # 自动转义
```

### 事务管理

```python
# ❌ 手动管理（容易遗漏）
try:
    cursor.execute("INSERT ...")
    cursor.execute("UPDATE ...")
    self.db.commit()
except:
    self.db.rollback()
    raise

# ✅ SQLAlchemy 自动管理
with get_db_session() as session:
    session.execute(...)
    session.execute(...)
    # 自动 commit（正常）或 rollback（异常）
```

## 📚 相关资源

- SQLAlchemy 2.0 文档: https://docs.sqlalchemy.org/en/20/
- 连接池文档: https://docs.sqlalchemy.org/en/20/core/pooling.html
- 迁移指南: https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
- 性能优化: https://docs.sqlalchemy.org/en/20/faq/performance.html

## 🎉 总结

### 为什么选择 SQLAlchemy？

1. ✅ **已在依赖中**，零额外成本
2. ✅ **工业级连接池**，彻底解决泄漏
3. ✅ **渐进式迁移**，风险可控
4. ✅ **长期收益**，提升代码质量

### 立即行动（5分钟）

```bash
# 1. 确认依赖已安装
pip show sqlalchemy

# 2. 创建基础设施文件
touch quantsys-v2/infrastructure/database/engine.py
touch quantsys-v2/infrastructure/database/models.py

# 3. 阅读下一步实现指南
cat docs/improvements/orm-implementation-guide.md
```

下一步：查看 [ORM 实现指南](./orm-implementation-guide.md)
