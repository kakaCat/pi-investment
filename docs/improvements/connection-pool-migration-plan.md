# 数据库连接池迁移方案

## 问题诊断

### 当前状态（2026-06-15）
```bash
# 19个泄漏的 idle 连接
psql> SELECT state, count(*) FROM pg_stat_activity WHERE datname = 'quant_investment' GROUP BY state;
 state  | count 
--------+-------
 active |     1
 idle   |    19
```

### 根本原因
1. **每次请求创建新连接**：`BaseRepository.__init__()` 每次都 `psycopg2.connect()`
2. **连接从不关闭**：17个文件使用 `self.db.cursor()` 后从不调用 `cursor.close()`
3. **连接池代码已存在但未启用**：`connection_pool.py` (229行) 有完整实现但无人使用

### 影响
- 内存泄漏：每个连接 ~1MB，19个连接 = 19MB
- 性能下降：PostgreSQL `max_connections=100`，泄漏到80后新请求失败
- 不稳定：长时间运行后崩溃

## 解决方案

### Phase 1: 启用连接池（立即生效，零代码改动）

**原理**：利用已有的 `connection_pool.py`，在 Flask 启动时初始化。

```python
# quantsys-v2/api/server.py

from infrastructure.database.connection_pool import get_connection_pool, close_pool

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # ✅ 在应用启动时初始化连接池
    get_connection_pool()
    
    # 注册 blueprints...
    
    # ✅ 在应用关闭时清理连接池
    @app.teardown_appcontext
    def shutdown_pool(exception=None):
        close_pool()
    
    return app
```

**配置环境变量**：
```bash
# .env
DB_POOL_MIN=5          # 最小连接数
DB_POOL_MAX=20         # 最大连接数
```

**效果**：
- ✅ 连接复用：最多20个连接处理所有请求
- ✅ 自动清理：应用关闭时释放所有连接
- ✅ 零改动：现有代码继续工作

### Phase 2: 迁移 Repository 层（安全重构）

**目标**：让所有 Repository 使用连接池而非直接连接。

**2.1 创建 BaseRepositoryV2（已存在）**

```python
# quantsys-v2/infrastructure/database/base_repository_v2.py

from infrastructure.database.connection_pool import get_cursor

class BaseRepositoryV2:
    """使用连接池的新 Repository 基类"""
    
    def __init__(self):
        # 不再持有连接，按需从池中获取
        pass
    
    def execute_query(self, sql, params=None):
        """执行查询（自动管理连接生命周期）"""
        with get_cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
    
    def execute_update(self, sql, params=None):
        """执行更新（自动提交/回滚）"""
        with get_cursor(commit=True) as cursor:
            cursor.execute(sql, params or ())
            return cursor.rowcount
```

**2.2 渐进式迁移策略**

逐个迁移 Repository：

```python
# 示例：迁移 KlineRepository
# 旧代码（base_repository.py）
class KlineRepository(BaseRepository):
    def get_latest(self, symbol):
        cursor = self.db.cursor()  # ❌ 泄漏
        cursor.execute("SELECT * FROM klines WHERE symbol=%s", (symbol,))
        return cursor.fetchone()

# 新代码（base_repository_v2.py）
class KlineRepositoryV2(BaseRepositoryV2):
    def get_latest(self, symbol):
        return self.execute_query(
            "SELECT * FROM klines WHERE symbol=%s LIMIT 1",
            (symbol,)
        )
```

**迁移优先级**（按调用频率排序）：
1. `KlineRepository` - 高频查询
2. `StrategyRepository` - 策略执行
3. `BacktestRepository` - 回测历史
4. `FactorRepository` - 因子计算
5. 其他 14 个 Repository

### Phase 3: 监控和优化

**3.1 添加健康检查端点**

```python
# quantsys-v2/api/routes/health.py

from infrastructure.database.connection_pool import get_connection_pool

@health_bp.route('/health/db', methods=['GET'])
def db_health():
    pool = get_connection_pool()
    stats = pool.get_stats()
    
    return jsonify({
        'status': 'ok' if stats['idle_connections'] < stats['pool_max'] * 0.8 else 'warning',
        'connections': stats
    })
```

**3.2 优化连接池配置**

根据实际负载调整：
```bash
# 低负载（开发环境）
DB_POOL_MIN=2
DB_POOL_MAX=10

# 中负载（测试环境）
DB_POOL_MIN=5
DB_POOL_MAX=20

# 高负载（生产环境）
DB_POOL_MIN=10
DB_POOL_MAX=50
```

**3.3 添加连接泄漏检测**

```python
# quantsys-v2/infrastructure/database/leak_detector.py

import atexit
import logging
from infrastructure.database.connection_pool import get_connection_pool

logger = logging.getLogger(__name__)

def check_leaks():
    """应用退出时检查连接泄漏"""
    pool = get_connection_pool()
    stats = pool.get_stats()
    
    if stats['idle_connections'] > stats['pool_max'] * 0.5:
        logger.warning(
            f"检测到潜在连接泄漏: {stats['idle_connections']} idle / {stats['pool_max']} max"
        )

atexit.register(check_leaks)
```

## 实施计划

### Week 1: Phase 1（启用连接池）
- [ ] 修改 `api/server.py` 初始化连接池
- [ ] 添加环境变量配置
- [ ] 测试现有功能是否正常
- [ ] 监控连接数变化

### Week 2: Phase 2（迁移高频 Repository）
- [ ] 迁移 `KlineRepository`
- [ ] 迁移 `StrategyRepository`
- [ ] 迁移 `BacktestRepository`
- [ ] 回归测试

### Week 3: Phase 2（迁移剩余 Repository）
- [ ] 迁移 `FactorRepository`
- [ ] 迁移其他 13 个 Repository
- [ ] 删除 `BaseRepository` 旧代码

### Week 4: Phase 3（监控优化）
- [ ] 添加健康检查端点
- [ ] 添加泄漏检测
- [ ] 性能压测
- [ ] 文档更新

## 验证方法

### 1. 连接数验证
```bash
# 启动服务前
psql> SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment';
 count 
-------
     1

# 启动服务后（Phase 1）
psql> SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment';
 count 
-------
     5  # = DB_POOL_MIN

# 发送100个并发请求
for i in {1..100}; do curl http://127.0.0.1:5001/api/stocks/600000.SH & done

# 峰值连接数应 ≤ DB_POOL_MAX (20)
psql> SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment';
 count 
-------
    18  # < 20 ✅

# 等待请求结束，连接数应回落到 DB_POOL_MIN
psql> SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment';
 count 
-------
     5  # = DB_POOL_MIN ✅
```

### 2. 功能验证
```bash
# 回测测试
curl -X POST http://127.0.0.1:5001/api/backtest/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategyId": 53, "symbol": "600000.SH", ...}'

# 因子计算测试
curl -X POST http://127.0.0.1:5001/api/factors/compute \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["600000.SH"], ...}'

# 所有测试应返回 200 ✅
```

### 3. 压力测试
```bash
# 使用 ab (Apache Bench)
ab -n 1000 -c 50 http://127.0.0.1:5001/api/stocks/600000.SH

# 预期结果：
# - 无连接泄漏
# - 无 "too many clients" 错误
# - 连接数稳定在 DB_POOL_MAX 以内
```

## 回滚方案

如果 Phase 1 出现问题，立即回滚：

```python
# quantsys-v2/api/server.py

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # ❌ 注释掉连接池初始化
    # get_connection_pool()
    
    # 注册 blueprints...
    
    # ❌ 注释掉连接池清理
    # @app.teardown_appcontext
    # def shutdown_pool(exception=None):
    #     close_pool()
    
    return app
```

重启服务即可恢复到旧行为。

## 预期收益

### 立即收益（Phase 1）
- ✅ 连接泄漏归零：19 idle → 5 idle
- ✅ 内存占用减少：19MB → 5MB
- ✅ 系统稳定性提升：不再崩溃

### 长期收益（Phase 2+3）
- ✅ 代码质量提升：统一连接管理
- ✅ 性能提升：连接复用 > 重复创建
- ✅ 可观测性：健康检查 + 泄漏检测

## 相关文件

- `quantsys-v2/infrastructure/database/connection_pool.py` - 连接池实现（已存在）
- `quantsys-v2/infrastructure/database/base_repository.py` - 旧 Repository 基类
- `quantsys-v2/infrastructure/database/base_repository_v2.py` - 新 Repository 基类（待创建）
- `quantsys-v2/api/server.py` - Flask 应用入口
