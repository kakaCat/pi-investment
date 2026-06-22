# PostgreSQL 僵尸连接问题解决方案

## 问题诊断

### 根本原因
1. **无连接池管理**：`BaseRepository` 每次实例化都创建新连接（psycopg2.connect），没有复用
2. **无超时机制**：PostgreSQL `idle_in_transaction_session_timeout = 0`（禁用）
3. **无自动清理**：进程异常退出时连接未正确关闭
4. **连接数限制**：PostgreSQL `max_connections = 100`，容易耗尽

### 当前状态
- PostgreSQL 最大连接数：100
- 空闲超时：禁用（0ms）
- 连接方式：每个 Repository 实例一个新连接
- 影响：服务异常退出后遗留大量僵尸连接

## 解决方案

### 1. 短期方案：定期清理脚本

创建自动清理脚本，定期终止超时的空闲连接。

**实现**：`scripts/cleanup-idle-connections.sh`

**使用**：
```bash
# 手动清理
./scripts/cleanup-idle-connections.sh

# 定时清理（每小时）
crontab -e
# 添加：0 * * * * /path/to/scripts/cleanup-idle-connections.sh
```

### 2. 中期方案：PostgreSQL 配置优化

修改 PostgreSQL 配置，自动终止超时连接。

**配置文件**：`/opt/homebrew/var/postgresql@14/postgresql.conf`

```ini
# 空闲事务超时（5分钟）
idle_in_transaction_session_timeout = 300000  # 5 min

# 语句超时（30秒）
statement_timeout = 30000  # 30 sec

# 增加最大连接数
max_connections = 200
```

**重启 PostgreSQL**：
```bash
brew services restart postgresql@14
```

### 3. 长期方案：代码层面改进

#### 3.1 使用连接池

**方案 A：psycopg2 连接池**
```python
from psycopg2 import pool

class ConnectionPool:
    _pool = None
    
    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            cls._pool = pool.ThreadedConnectionPool(
                minconn=5,
                maxconn=20,
                dsn=_resolve_db_dsn(),
                connect_timeout=5
            )
        return cls._pool
    
    @classmethod
    def get_connection(cls):
        return cls.get_pool().getconn()
    
    @classmethod
    def return_connection(cls, conn):
        cls.get_pool().putconn(conn)
```

**方案 B：SQLAlchemy 引擎**
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    dsn,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,  # 1小时回收
    pool_pre_ping=True,  # 连接前检查
    pool_timeout=30
)
```

#### 3.2 Context Manager 模式

确保连接正确关闭：

```python
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    conn = ConnectionPool.get_connection()
    try:
        yield conn
    finally:
        ConnectionPool.return_connection(conn)

# 使用
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
```

#### 3.3 重构 BaseRepository

```python
class BaseRepository(ABC):
    def __init__(self):
        # 不再持有连接，改为使用连接池
        self._pool = ConnectionPool.get_pool()
    
    @contextmanager
    def _get_cursor(self):
        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)
    
    def execute_query(self, query, params=None):
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
```

### 4. 监控和告警

#### 4.1 连接数监控脚本

**实现**：`scripts/monitor-db-connections.sh`

```bash
#!/bin/bash
THRESHOLD=80
CURRENT=$(psql -h 127.0.0.1 -U mac -d postgres -t -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='quant_investment';")

if [ $CURRENT -gt $THRESHOLD ]; then
  echo "WARNING: Database connections: $CURRENT (threshold: $THRESHOLD)"
  # 发送告警通知
fi
```

#### 4.2 健康检查端点

在 `quantsys-v2/api/server.py` 添加连接数检查：

```python
@app.route('/api/health/db-connections')
def db_connections_health():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT count(*) as total,
                   sum(case when state = 'idle' then 1 else 0 end) as idle,
                   sum(case when state = 'active' then 1 else 0 end) as active
            FROM pg_stat_activity 
            WHERE datname = 'quant_investment'
        """)
        stats = cursor.fetchone()
        
        return {
            'total': stats['total'],
            'idle': stats['idle'],
            'active': stats['active'],
            'max_connections': 200,
            'usage_percent': (stats['total'] / 200) * 100
        }
```

## 实施优先级

### P0 - 立即执行（已完成）
- [x] 手动清理 82 个僵尸连接
- [x] 重启 quantsys-v2 服务

### P1 - 本周内（推荐）
- [ ] 配置 PostgreSQL 超时参数
- [ ] 创建定期清理脚本
- [ ] 增加 max_connections 到 200

### P2 - 两周内（根本解决）
- [ ] 实现连接池（psycopg2.pool 或 SQLAlchemy）
- [ ] 重构 BaseRepository 使用 context manager
- [ ] 添加连接数监控端点

### P3 - 持续改进
- [ ] 设置监控告警
- [ ] 定期审查连接使用情况
- [ ] 优化服务重启流程

## 验证方法

### 1. 检查当前连接数
```bash
psql -h 127.0.0.1 -U mac -d postgres -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='quant_investment';"
```

### 2. 查看空闲连接详情
```bash
psql -h 127.0.0.1 -U mac -d postgres -c \
  "SELECT pid, state, state_change, query 
   FROM pg_stat_activity 
   WHERE datname='quant_investment' AND state='idle' 
   ORDER BY state_change 
   LIMIT 10;"
```

### 3. 测试连接池效果
```python
# 压力测试
import concurrent.futures
from infrastructure.database.base_repository import BaseRepository

def test_connection():
    repo = BaseRepository()
    # 执行查询
    return True

with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    futures = [executor.submit(test_connection) for _ in range(100)]
    results = [f.result() for f in futures]
```

## 参考资料

- [PostgreSQL Connection Pooling](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [psycopg2 Connection Pool](https://www.psycopg.org/docs/pool.html)
- [SQLAlchemy Engine Configuration](https://docs.sqlalchemy.org/en/14/core/engines.html)
