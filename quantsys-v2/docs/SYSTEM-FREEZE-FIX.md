# QuantSys-V2 系统假死问题诊断与解决方案

**日期**: 2026-08-28  
**问题**: quantsys-v2 随机假死，API 请求无响应

## 根本原因

通过诊断发现三个关键问题：

### 1. **idle in transaction 事务泄漏** (P0 - 致命)
```sql
-- 发现 11 分钟挂起的事务
pid: 68182 | state: idle in transaction | duration: 00:11:02
query: SELECT quant.stocks.symbol FROM quant.stocks WHERE ...
```

**影响**：
- 未提交的事务持有表锁，阻塞后续所有写操作
- 连接池耗尽（pool_size=10 + max_overflow=20），新请求等待 30s 超时
- 表现为整个系统"假死"

**根因**：
1. ORM Session 未正确关闭（缺少 `close_session()` 调用）
2. PostgreSQL `idle_in_transaction_session_timeout = 0`（永不超时）
3. FastAPI 部分路由未使用依赖注入的 session 管理

### 2. **数据源超时堆积** (P1 - 性能)
```
Provider baostock.get_klines 超时（>60s），降级下一个
AkShare kline provider failed: RemoteDisconnected
Tencent kline provider failed: 'list' object has no attribute 'get'
```

**影响**：
- 单个 K线获取超时 60s，批量操作阻塞主线程
- 多个失败重试叠加，占用连接池和线程资源

### 3. **连接池配置不足** (P1 - 容量)
```python
pool_size=10, max_overflow=20  # 最多 30 个连接
```

**影响**：
- 后台 3 个线程（Scheduler/WatchEngine/Orchestrator）+ API 并发请求
- 高峰期连接不足，触发 pool timeout

## 解决方案

### 方案 A：立即修复（保守，2 小时）

#### A1. 启用数据库超时保护
```bash
psql -d quant_investment <<SQL
ALTER DATABASE quant_investment SET idle_in_transaction_session_timeout = '5min';
SQL
```

#### A2. 增加连接池容量
```python
# quantsys-v2/infrastructure/config/settings.yaml
database:
  pool_size: 20        # 10 -> 20
  max_overflow: 30     # 20 -> 30
```

#### A3. 添加 ORM Session 监控和自动清理
创建中间件自动清理泄漏的 session。

---

### 方案 B：彻底重构（激进，1-2 天）

#### B1. 全面迁移到 FastAPI 依赖注入
- 所有路由强制使用 `Depends(get_orm_session)`
- 后台线程使用 `orm_session_context()` 上下文管理器
- 删除全局 `scoped_session`（容易泄漏）

#### B2. 异步化数据获取
- K线获取改为异步任务队列（Celery/RQ）
- 超时隔离，不阻塞主线程

#### B3. 连接池分层
- API 专用连接池（快速响应）
- 后台任务连接池（长时间查询）
- 数据回填连接池（大批量操作）

---

## 推荐执行计划

### 第一阶段：紧急止血（今天完成）
1. ✅ **立即执行**：杀掉挂起事务 `SELECT pg_terminate_backend(68182)`
2. ⚠️ **启用数据库超时**：`idle_in_transaction_session_timeout = 5min`
3. ⚠️ **扩大连接池**：pool_size=20, max_overflow=30
4. ⚠️ **添加监控脚本**：每分钟检测挂起事务并告警

### 第二阶段：架构修复（本周完成）
5. 📝 审计所有 `get_session()` 调用，确保配对 `close_session()`
6. 📝 后台线程改用 `orm_session_context()` 上下文管理器
7. 📝 K线获取超时降到 10s，失败快速降级

### 第三阶段：系统优化（下周）
8. 🔄 数据回填任务异步化（不占用 API 连接池）
9. 🔄 连接池分层（API/Background/Backfill）
10. 🔄 全面迁移到依赖注入模式

---

## 具体修复代码

见下方文件：
- `scripts/fix_idle_transactions.py` - 监控和自动杀死挂起事务
- `infrastructure/persistence/orm/session_guard.py` - Session 泄漏检测
- `adapters/inbound/fastapi_app/middleware.py` - 自动清理中间件
