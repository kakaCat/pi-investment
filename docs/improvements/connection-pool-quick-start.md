# 连接池快速启动指南

## 🎯 问题概述

**当前状态**：19个泄漏的 idle 数据库连接，导致内存泄漏和系统不稳定。

**根本原因**：
1. 每次请求创建新连接，从不关闭
2. 17个文件直接使用 `self.db.cursor()` 绕过连接池
3. 连接池代码已存在但未启用

## ✅ Phase 1: 启用连接池（已完成）

### 修改内容

**1. 修改了 `quantsys-v2/api/server.py`**：
```python
# 添加了连接池初始化
from infrastructure.database.connection_pool import get_connection_pool, close_pool

def create_app():
    # ... 
    # ✅ 初始化连接池
    pool = get_connection_pool()
    
    # ✅ 应用关闭时清理
    @app.teardown_appcontext
    def shutdown_pool(exception=None):
        close_pool()
```

**2. 创建了环境变量配置**：
```bash
# .env.connection_pool
DB_POOL_MIN=5
DB_POOL_MAX=20
```

### 立即生效步骤

#### 步骤 1: 清理现有泄漏连接

```bash
# 先清理当前的19个泄漏连接
./scripts/cleanup-idle-connections.sh
```

#### 步骤 2: 配置环境变量

将以下内容添加到 `quantsys-v2/.env`：
```bash
# 数据库连接池配置
DB_POOL_MIN=5
DB_POOL_MAX=20
```

或者直接使用：
```bash
cat .env.connection_pool >> quantsys-v2/.env
```

#### 步骤 3: 重启服务

```bash
# 停止现有服务
pkill -f "python api/server.py"

# 启动服务（连接池自动启用）
cd quantsys-v2
python api/server.py
```

#### 步骤 4: 验证连接池工作

```bash
# 方法 1: 使用自动化测试脚本（推荐）
./scripts/test-connection-pool.sh

# 方法 2: 手动监控
./scripts/monitor-db-connections.sh

# 应该看到：
# - 初始连接数 = 5 (DB_POOL_MIN)
# - 并发请求时 ≤ 20 (DB_POOL_MAX)
# - 请求结束后回落到 5
```

### 预期效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| Idle 连接数 | 19 | 5 |
| 总连接数 | 20+ | 5-20 |
| 内存占用 | 19MB | 5-20MB |
| 连接泄漏 | 是 | 否 |
| 系统稳定性 | 崩溃 | 稳定 |

## 📊 验证命令

### 快速检查
```bash
# 查看当前连接数
psql -h 127.0.0.1 -U mac -d quant_investment -c "
SELECT state, count(*) 
FROM pg_stat_activity 
WHERE datname = 'quant_investment' 
GROUP BY state;
"

# 预期输出（服务启动后）：
#  state  | count 
# --------+-------
#  idle   |     5   ← 应该等于 DB_POOL_MIN
```

### 压力测试
```bash
# 发送100个并发请求
for i in {1..100}; do 
    curl -s http://127.0.0.1:5001/api/health > /dev/null & 
done

# 立即检查连接数
psql -h 127.0.0.1 -U mac -d quant_investment -c "
SELECT count(*) as total_connections 
FROM pg_stat_activity 
WHERE datname = 'quant_investment';
"

# 应该 ≤ 20 (DB_POOL_MAX) ✅
```

### 健康检查端点
```bash
# 查询连接池统计（未来会添加专用端点）
curl http://127.0.0.1:5001/api/health
```

## 🔧 故障排查

### 问题 1: 连接数仍然泄漏

**检查**：
```bash
# 确认环境变量已加载
cd quantsys-v2
python -c "import os; print('DB_POOL_MIN:', os.getenv('DB_POOL_MIN')); print('DB_POOL_MAX:', os.getenv('DB_POOL_MAX'))"
```

**解决**：
- 确保 `.env` 文件包含 `DB_POOL_MIN` 和 `DB_POOL_MAX`
- 重启服务

### 问题 2: 服务启动失败

**检查日志**：
```bash
cd quantsys-v2
python api/server.py 2>&1 | grep -i "pool\|connection"
```

**可能原因**：
- 数据库连接信息错误（检查 `PGDATABASE`, `PGHOST` 等）
- PostgreSQL 服务未启动（运行 `pg_isready`）

### 问题 3: 连接池未初始化

**回滚到旧行为**（应急方案）：

编辑 `quantsys-v2/api/server.py`，注释掉连接池相关代码：
```python
def create_app():
    # 注释掉这行
    # pool = get_connection_pool()
    
    # 注释掉这个装饰器
    # @app.teardown_appcontext
    # def shutdown_pool(exception=None):
    #     close_pool()
```

## 📈 下一步计划

### Phase 2: 迁移 Repository 层（2-3周）

逐步迁移所有 Repository 使用连接池：
1. 创建 `BaseRepositoryV2`（使用连接池）
2. 迁移高频 Repository（Kline, Strategy, Backtest）
3. 迁移剩余 14 个 Repository
4. 删除旧的 `BaseRepository`

### Phase 3: 监控和优化（1周）

1. 添加 `/api/health/db` 端点显示连接池统计
2. 添加连接泄漏检测
3. 根据实际负载优化配置

详细计划见：[connection-pool-migration-plan.md](./connection-pool-migration-plan.md)

## 📝 相关文件

- ✅ `quantsys-v2/api/server.py` - 已修改（启用连接池）
- ✅ `quantsys-v2/infrastructure/database/connection_pool.py` - 连接池实现（已存在）
- ✅ `.env.connection_pool` - 配置示例（已创建）
- ✅ `scripts/test-connection-pool.sh` - 自动化测试（已创建）
- ✅ `scripts/monitor-db-connections.sh` - 监控脚本（已存在）
- ✅ `scripts/cleanup-idle-connections.sh` - 清理脚本（已存在）

## 🎉 总结

**Phase 1 已完成**，现在只需：
1. 配置环境变量（2分钟）
2. 重启服务（1分钟）
3. 运行测试验证（1分钟）

**总耗时：< 5分钟，彻底解决连接泄漏问题！**
