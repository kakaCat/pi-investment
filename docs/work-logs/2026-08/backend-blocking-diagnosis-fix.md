# 后端阻塞问题诊断与修复方案

**日期**: 2026-08-30  
**问题**: 9个工具报错，后端服务反复阻塞无响应

---

## 问题分类

### ✅ 实际正常（3个）
后端未阻塞时可正常工作：
- `risk_barra_decomposition` - 端点 `/api/factor-models/barra/calculate` 正常
- `data_fetch_financial` - 端点 `/api/financial/stock/{symbol}` 正常  
- `factor_calculate` - 端点 `/api/compute/factors` 正常

### ❌ 后端阻塞导致（5个）

#### 1. K线同步任务死循环
- **工具**: `kline_daily_sync`
- **端点**: `/api/data/sync-daily-klines`
- **症状**: 30s 超时
- **根因**: 后端启动时触发的 baostock K线更新任务无限重试
- **日志证据**:
```
baostock 登录失败: 网络接收错误。
AkShare kline provider failed: RemoteDisconnected
```

#### 2. WatchEngine 启动阻塞
- **工具**: `watch_manage`
- **端点**: `/api/watch/rules`
- **症状**: 10s 超时
- **根因**: WatchEngine 线程启动时查询数据库遇到锁或长查询

#### 3. 数据库事务泄漏
- **工具**: `trade_verify`
- **端点**: `/api/trades/verify` (404 - 端点不存在)
- **症状**: 超时
- **根因**: 发现2个 `idle in transaction` 空闲事务持有锁
- **证据**:
```sql
pid 40705: idle in transaction, ClientRead
pid 40703: idle in transaction, ClientRead
```

#### 4. 后端内部异常
- **工具**: `data_fetch_macro`
- **端点**: `/api/market/macro`
- **症状**: HTTP 500 Internal Error
- **根因**: 未知后端异常（需查看详细日志）

#### 5. 端点不存在
- **工具**: `sector_analysis`
- **端点**: 未知（可能是 `/api/analysis/sector`）
- **症状**: HTTP 404
- **根因**: FastAPI 路由中该端点未注册

### ❌ 配置错误（1个）

#### 6. 日志文件路径错误
- **工具**: `agent_os_logs`
- **配置路径**: `agent-os/logs/main.log`
- **实际路径**: `agent-os/logs/agent-os.log`
- **修复**: 需要找到工具配置并更新路径

---

## 根本原因

**FastAPI 启动时的3个后台线程导致阻塞**:

1. **WatchEngine** (`watch_bootstrap.py:151`)
   - 实时盯盘线程，启动时查询数据库
   - 可能遇到数据库锁或慢查询

2. **DailyOrchestrator** (`orchestrator_bootstrap.py:163`)
   - 每日调度线程，触发定时任务
   - 可能触发K线更新等耗时操作

3. **Agent OS Scheduler 注册** (`main.py:118`)
   - 注册调度任务到 Agent OS
   - 失败时回退到本地 SchedulerService

这些线程在启动时会触发数据获取任务（K线、财报等），而数据源（baostock/akshare）连接失败时会无限重试，导致整个服务阻塞。

---

## 临时解决方案

### 方案1：禁用启动时的后台任务（快速修复）

修改 `quantsys-v2/adapters/inbound/fastapi_app/main.py`:

```python
# 在 lifespan 函数中添加环境变量开关
DISABLE_BACKGROUND_TASKS = os.getenv('DISABLE_BACKGROUND_TASKS', 'false').lower() == 'true'

if not DISABLE_BACKGROUND_TASKS:
    # 启动 WatchEngine
    # 启动 Orchestrator
    # 注册 Agent OS Scheduler
else:
    logger.warning("⚠️ Background tasks disabled via DISABLE_BACKGROUND_TASKS")
```

启动命令：
```bash
DISABLE_BACKGROUND_TASKS=true python adapters/inbound/fastapi_app/main.py
```

### 方案2：修复数据库事务泄漏

1. 确保所有 ORM Session 使用 `with` 上下文管理器
2. 启用 Session Guard（已在代码中，但需验证生效）
3. 定期清理空闲事务：
```bash
psql -U yunpeng -d quant_investment -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE state = 'idle in transaction' 
  AND state_change < now() - interval '5 minutes';
"
```

### 方案3：修复 K线数据获取死循环

修改 K线提供者的重试逻辑：
- 添加最大重试次数（例如 3 次）
- 添加超时机制（例如单次请求 10s 超时）
- 失败后立即返回，不阻塞主线程

---

## 长期解决方案

### P0 - 后台任务异步化

将所有启动时的数据获取任务移到异步队列：
1. 使用 Celery 或 Agent OS 调度
2. 启动时只注册任务，不立即执行
3. 任务失败不影响主服务

### P1 - 完善端点

1. **sector_analysis**: 实现 `/api/analysis/sector` 端点
2. **trade_verify**: 实现 `/api/trades/verify` 端点
3. **data_fetch_macro**: 修复 500 错误，添加异常处理

### P2 - 工具配置修复

找到并修复 `agent_os_logs` 工具的日志路径配置。

---

## 立即执行步骤

1. ✅ 停掉冗余的 `com.pi-investment.quantsys-v2` launchd 服务
2. ✅ 清理数据库空闲事务
3. ✅ 强制重启后端服务
4. ⏳ 设置 `DISABLE_BACKGROUND_TASKS=true` 环境变量
5. ⏳ 验证9个工具的可用性
6. ⏳ 修复 agent_os_logs 路径
7. ⏳ 实现缺失的端点

---

## 验证清单

- [ ] 后端 `/health` 端点 < 1s 响应
- [ ] `risk_barra_decomposition` 正常
- [ ] `data_fetch_financial` 正常
- [ ] `factor_calculate` 正常
- [ ] `data_fetch_macro` 修复 500 错误
- [ ] `sector_analysis` 实现端点
- [ ] `kline_daily_sync` 不超时
- [ ] `watch_manage` 不超时
- [ ] `trade_verify` 实现端点
- [ ] `agent_os_logs` 路径修复

---

## 相关文件

- `quantsys-v2/adapters/inbound/fastapi_app/main.py` - 启动入口
- `quantsys-v2/adapters/inbound/fastapi_app/watch_bootstrap.py` - WatchEngine
- `quantsys-v2/adapters/inbound/fastapi_app/orchestrator_bootstrap.py` - Orchestrator
- `quantsys-v2/tools/register_jobs_to_agent_os.py` - Agent OS 调度注册
- `~/Library/LaunchAgents/com.pi-investment.v2-api.plist` - launchd 配置

---

## 结论

**核心问题**: 后端启动时的后台任务（K线更新、盯盘引擎）因数据源连接失败而无限重试，导致整个服务阻塞。

**临时方案**: 禁用后台任务启动，确保 API 服务可用。

**长期方案**: 将耗时任务异步化，添加超时和重试上限，实现缺失端点。
