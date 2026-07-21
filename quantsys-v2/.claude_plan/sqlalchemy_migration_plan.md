# 统一迁移到 SQLAlchemy 2.0 框架 - 实施计划

## 现状盘点

### 当前数据库访问的 4 套并行体系

1. **BaseRepository**(同步,主力)
   - 位置:`infrastructure/persistence/database/base_repository.py`
   - 继承者:24 个 Repository 类(StockRepository, KlineRepository, FactorRepository, SignalRepository, PortfolioRepository, BacktestRepository, RiskRepository, SignalExecutionRepository 等)
   - 连接方式:手搓 `psycopg2.connect` + `ThreadedConnectionPool(min=5, max=20)`
   - 生命周期:靠 `__del__` 归还连接(今天刚修复成 `_from_pool` 标志 + `_release_connection()`)
   - 使用方:`DataService` 聚合 8 个 Repository,被 API routes/services/scripts 广泛使用

2. **AsyncBaseRepository**(异步)
   - 位置:`infrastructure/persistence/database/async_base_repository.py`
   - 继承者:AsyncFactorRepository, AsyncKlineRepository
   - 连接方式:独立的 `AsyncConnectionPool(min=10, max=50)` — 和同步池**互不相干**
   - 问题:与同步池分离,总连接数难控

3. **scheduler 自己直连**
   - 位置:`infrastructure/scheduler/scheduler.py:265 _get_conn()`
   - 连接方式:缓存单个 `psycopg2.connect(dsn)`,完全绕过 BaseRepository
   - 问题:74 处 SQL 操作都用 `self._conn`,多线程(`ThreadPoolExecutor`)下线程安全隐患

4. **脚本裸连**
   - 34 个训练/回填/初始化脚本调用 `BaseRepository.init_connection_pool()`,自成一体
   - 1 个 migration 脚本用裸 `psycopg2.connect`

5. **SQLAlchemy 现状**
   - 依赖:`requirements.txt` 声明 `sqlalchemy>=2.0.0`,已安装 2.0.51
   - 使用:**仅 1 个文件** `application/services/qlib/qlib_data_adapter.py`,且只用了 `create_engine` + `pd.read_sql`,没用 ORM 映射,且漏了 `engine.dispose()`

### 问题根源

- **连接池碎片化**:同步池 max=20、异步池 max=50、scheduler 单连接、脚本各自建池。N 个进程 × 各自 max 轻松超过 PG 默认 `max_connections=100`。
- **生命周期不统一**:依赖 `__del__`/`atexit`,进程被 terminate 时连接泄漏。
- **fork 不安全**:multiprocessing 子进程继承父进程的池 socket fd,导致连接错乱和泄漏(今天刚加 `os.register_at_fork` 缓解)。
- **有框架不用**:SQLAlchemy 2.0 的成熟连接池(`pool_size`/`max_overflow`/`pool_pre_ping`/`pool_recycle`/`QueuePool`)、生命周期管理、fork 安全处理都现成,却躺在依赖里不用。

---

## 目标架构

### 统一到 SQLAlchemy Engine + Connection Pool

**核心原则:**
- **连接层统一用 SQLAlchemy Engine**,彻底移除手搓 `psycopg2.connect` 和 `ThreadedConnectionPool`。
- **保留现有 SQL 写法**:不强推 ORM 映射(继续用 `text()` + cursor.execute 的 Core 层),降低迁移风险。
- **全局连接预算可控**:一处配置 `pool_size`/`max_overflow`,所有进程共享配置,确保 `总连接数 ≤ PG max_connections`。
- **生命周期清晰**:Engine 在进程启动时创建一次,进程退出时 `engine.dispose()`,不再依赖 GC。

### 分阶段迁移(控制风险)

**Phase 1: 统一同步层(BaseRepository + scheduler)**
- 创建全局 Engine 单例(`infrastructure/persistence/database/engine.py`)
- 改造 `BaseRepository`:底层从 `psycopg2.connect` 换成 `engine.connect()`,保留现有 `_get_cursor()` / `execute` 接口,子类 Repository **零改动**
- 改造 `scheduler._get_conn()`:改用全局 Engine
- 所有脚本统一调用 `init_engine()` 替代 `init_connection_pool()`
- **影响面**:BaseRepository 基类、scheduler、脚本入口,子类 Repository 不动
- **验证**:跑现有测试套件 + 手工验证 API/scheduler/一个训练脚本

**Phase 2: 统一异步层(AsyncBaseRepository)**
- 创建全局 AsyncEngine(`create_async_engine`)
- 改造 `AsyncBaseRepository`:底层从 `AsyncConnectionPool` 换成 AsyncEngine
- **影响面**:AsyncBaseRepository 基类,AsyncFactorRepository/AsyncKlineRepository 不动
- **验证**:跑 async 测试

**Phase 3: 清理遗留(qlib_data_adapter + migration 脚本)**
- `qlib_data_adapter.py` 改用全局 Engine,补上 dispose
- migration 脚本改用 Engine
- **影响面**:2 个文件

**Phase 4(可选,后续): 引入 ORM 映射**
- 基于统一的 Engine,逐步为高频改动的表(如 backtest_results、strategies)引入 ORM Model
- 不强求全面 ORM,与 Core 层共存

---

## Phase 1 详细设计(本次执行)

### 1.1 创建全局 Engine 单例

**新建文件:** `infrastructure/persistence/database/engine.py`

```python
"""
SQLAlchemy Engine 全局单例 - 统一数据库连接管理

所有同步数据库访问(BaseRepository、scheduler、脚本)统一通过此 Engine。
异步路径见 async_engine.py。
"""
import os
import logging
from typing import Optional
from sqlalchemy import create_engine, Engine, event
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_engine_initialized = False

def get_engine() -> Engine:
    """获取全局 Engine 单例,未初始化时自动 init。"""
    if _engine is None:
        init_engine()
    return _engine

def init_engine(
    dsn: Optional[str] = None,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_pre_ping: bool = True,
    pool_recycle: int = 3600,
    echo: bool = False
) -> Engine:
    """初始化全局 Engine(进程启动时调用一次)。

    Args:
        dsn: 数据库连接字符串,None 则从环境变量读取
        pool_size: 连接池保持的常驻连接数(默认 10)
        max_overflow: 超过 pool_size 时允许的临时连接数(默认 20)
                      总连接上限 = pool_size + max_overflow = 30
        pool_pre_ping: 连接取出前先 ping,坏连接自动移除(默认 True)
        pool_recycle: 连接回收时间(秒),防止 DB 端超时断开(默认 3600)
        echo: 是否打印 SQL 日志(调试用,默认 False)

    Returns:
        Engine 实例

    配置指南:
        - 单进程服务(API/scheduler):pool_size=10, max_overflow=20 足够
        - 多进程训练脚本:每进程 pool_size 降到 5,确保 N_workers × 30 < PG max_connections
        - PostgreSQL 默认 max_connections=100,生产环境建议调到 200+
    """
    global _engine, _engine_initialized

    if _engine_initialized:
        logger.info("Engine already initialized, skipping")
        return _engine

    if dsn is None:
        from infrastructure.persistence.database.base_repository import _resolve_db_dsn
        dsn = _resolve_db_dsn()

    if not dsn:
        raise RuntimeError(
            "No database DSN configured. "
            "Set QUANT_DATABASE_URL, DATABASE_URL, or POSTGRES_DSN."
        )

    _engine = create_engine(
        dsn,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        pool_recycle=pool_recycle,
        echo=echo,
    )

    _engine_initialized = True
    logger.info(
        f"SQLAlchemy Engine initialized: pool_size={pool_size}, "
        f"max_overflow={max_overflow}, total_capacity={pool_size + max_overflow}"
    )

    # 注册 atexit,进程退出时关闭 Engine
    import atexit
    atexit.register(dispose_engine)

    # fork 安全:子进程清空继承的 Engine,强制重新 init
    _register_fork_handler()

    return _engine

def dispose_engine():
    """关闭 Engine(进程退出时调用)。"""
    global _engine, _engine_initialized
    if _engine is not None:
        try:
            _engine.dispose()
            logger.info("Engine disposed")
        except Exception as e:
            logger.error(f"Error disposing engine: {e}")
        finally:
            _engine = None
            _engine_initialized = False

_fork_handler_registered = False

def _register_fork_handler():
    """fork 后在子进程重置 Engine,避免继承父进程的连接池 socket。"""
    global _fork_handler_registered
    if _fork_handler_registered:
        return
    register = getattr(os, "register_at_fork", None)
    if register is None:
        _fork_handler_registered = True
        return

    def _reset_engine_in_child():
        global _engine, _engine_initialized
        # 不 dispose:会关父进程的 socket。只丢引用,子进程需要时重新 init。
        _engine = None
        _engine_initialized = False

    register(after_in_child=_reset_engine_in_child)
    _fork_handler_registered = True
```

### 1.2 改造 BaseRepository

**修改:** `infrastructure/persistence/database/base_repository.py`

关键改动:
- 移除类变量 `_connection_pool`、`_pool_initialized`、`init_connection_pool()`、`close_connection_pool()`
- `__init__` 不再 `getconn()`,改为存储 `_engine = None`
- 新增 `_get_connection()`:lazy 从 Engine 获取 connection,存到 `self._conn`
- `_get_cursor()`:调用 `_get_connection()`,返回 `self._conn.connection.cursor()`(通过 `.connection` 拿到底层 psycopg2 conn,保持向后兼容)
- `_release_connection()`:改为 `self._conn.close()`(归还给 Engine 池)
- 废弃 `_ensure_db`,Engine 的 `pool_pre_ping` 已自动处理坏连接
- 向后兼容:保留 `init_connection_pool()` 作为 deprecated wrapper,内部调用 `init_engine()`,避免所有脚本一次性爆炸

伪代码(不完整,实际实现时展开):
```python
from infrastructure.persistence.database.engine import get_engine

class BaseRepository(ABC):
    def __init__(self, db_connection=None):
        if db_connection is not None:
            # 外部连接(测试场景)
            self._conn = db_connection
            self._owns_connection = False
        else:
            self._conn = None
            self._owns_connection = True

    def _get_connection(self):
        """Lazy 获取连接(from Engine 池),缓存到 self._conn。"""
        if self._conn is None:
            engine = get_engine()
            self._conn = engine.connect()
        return self._conn

    def _get_cursor(self):
        """返回 psycopg2 cursor(向后兼容现有 Repository 子类)。"""
        conn = self._get_connection()
        # SQLAlchemy connection.connection 是底层 DBAPI 连接(psycopg2.connection)
        return conn.connection.cursor()

    def _release_connection(self):
        if self._owns_connection and self._conn is not None:
            try:
                self._conn.close()  # 归还给 Engine 池
            except Exception as e:
                logger.error(f"Error releasing connection: {e}")
            finally:
                self._conn = None

    def close(self):
        self._release_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        self._release_connection()

    @classmethod
    def init_connection_pool(cls, dsn=None, minconn=5, maxconn=20):
        """Deprecated: 向后兼容旧脚本,内部调用 init_engine。"""
        from infrastructure.persistence.database.engine import init_engine
        import warnings
        warnings.warn(
            "BaseRepository.init_connection_pool() is deprecated, "
            "use init_engine() instead",
            DeprecationWarning,
            stacklevel=2
        )
        init_engine(dsn=dsn, pool_size=minconn, max_overflow=maxconn - minconn)

    @classmethod
    def close_connection_pool(cls):
        """Deprecated: 向后兼容。"""
        from infrastructure.persistence.database.engine import dispose_engine
        dispose_engine()
```

### 1.3 改造 scheduler

**修改:** `infrastructure/scheduler/scheduler.py:265 _get_conn()`

```python
def _get_conn(self):
    """Return a connection from the global Engine pool."""
    from infrastructure.persistence.database.engine import get_engine
    # 不再缓存单连接,每次从池拿(Engine 内部已缓存池)
    engine = get_engine()
    # 返回 psycopg2 connection(向后兼容现有 SQL 代码)
    return engine.raw_connection()
```

每处 SQL 执行后需显式 `conn.commit()` / `conn.rollback()`,并在 finally 里 `conn.close()`(归还池)。或者统一改造成 context manager。

### 1.4 改造脚本入口

所有调用 `BaseRepository.init_connection_pool()` 的脚本,改为:
```python
from infrastructure.persistence.database.engine import init_engine

if __name__ == '__main__':
    init_engine(pool_size=5, max_overflow=10)  # 训练脚本降低每进程连接数
    # ... 原有逻辑
```

### 1.5 改造 qlib_data_adapter

`application/services/qlib/qlib_data_adapter.py`:
- 移除 `self.engine = create_engine(...)`,改为 `from engine import get_engine; self.engine = get_engine()`
- 删除 `_create_engine` 方法
- 无需 dispose(全局 Engine 由 atexit 统一清理)

---

## 验证计划

### 单元测试
- 跑现有 `tests/test_base_repository.py::TestConnectionLifecycle`(今天新写的 5 个测试需适配新逻辑)
- 增补测试:Engine 单例、fork 后重新 init、连接归还幂等

### 集成测试
- API 接口:`curl http://127.0.0.1:5001/api/scheduler/tasks?page=1&pageSize=12`
- scheduler:观察定时任务执行日志
- 训练脚本:跑一个 `train_ml_*.py`,观察连接数

### 连接数验证
迁移前后对比:
```bash
lsof -nP -iTCP:5432 | grep ESTABLISHED | grep -vi postgres | wc -l
```
预期:API 服务单进程从 20 降到 10-15(pool_size=10)。

### 回归风险
- **高风险点**:BaseRepository 是 24 个子类的基类,底层连接逻辑改动,任何遗漏都可能导致查询报错
- **缓解措施**:
  1. 保留 `_get_cursor()` 接口,子类无感
  2. deprecated wrapper `init_connection_pool()`,旧脚本不爆炸
  3. 分阶段:先同步层,async 层单独验证

---

## 改动清单(Phase 1)

| 文件 | 改动类型 | 风险 |
|---|---|---|
| `infrastructure/persistence/database/engine.py` | 新增 | 低(新文件) |
| `infrastructure/persistence/database/base_repository.py` | 重构核心逻辑 | **高**(24 个子类依赖) |
| `infrastructure/scheduler/scheduler.py` | 修改 `_get_conn()` + 74 处 SQL 的连接管理 | 中 |
| `application/services/qlib/qlib_data_adapter.py` | 改用全局 Engine | 低 |
| `adapters/inbound/api/server.py` | `init_connection_pool` → `init_engine` | 低 |
| `start_all.py` | 无需改(子进程内 server.py 自己 init) | 无 |
| `scripts/*.py`(34 个) | `init_connection_pool` → `init_engine` | 低(逐个验证) |
| `infrastructure/persistence/migrations/create_strategy_circuit_breaker_table.py` | 改用 Engine | 低 |
| `tests/test_base_repository.py` | 适配新逻辑 | 低 |

**总计:** 约 40 个文件,核心风险在 `base_repository.py` 重构。

---

## 执行顺序(本次)

1. 创建 `engine.py`
2. 重构 `base_repository.py`
3. 编译验证 + 跑 `test_base_repository.py`
4. 改造 `server.py`、`qlib_data_adapter.py`、1 个 migration 脚本
5. 改造 `scheduler.py`(最复杂,74 处 SQL,单独一轮)
6. 批量改造 scripts(挑 3 个代表性脚本先验证,再推广)
7. 手工验证:启动 API、触发 scheduler 任务、跑一个训练脚本
8. 监控连接数,确认无泄漏

估计工作量:2-3 小时(含测试)。

---

## 后续(Phase 2-3,本次不做)

- AsyncBaseRepository 迁移到 `create_async_engine`
- 全面清理 psycopg2 裸连
- (可选)逐步引入 ORM Model

---

## 批准确认

请确认:
- [ ] 同意 Phase 1 的迁移范围(BaseRepository + scheduler + scripts + qlib,不动 async)
- [ ] 同意保留向后兼容 wrapper(`init_connection_pool` deprecated)
- [ ] 同意保留现有 SQL 写法(不强推 ORM)
- [ ] 风险可接受(充分测试 + 分阶段验证)

批准后我开始执行。
