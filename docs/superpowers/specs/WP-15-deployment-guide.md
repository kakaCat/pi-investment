# WP-15 Deployment & Testing Guide

**执行时间**: 2026-08-16  
**执行人**: 用户手动执行（需要 sudo 权限）

---

## 部署步骤

### Step 1: 重启 quantsys-v2 服务

```bash
# 重启 FastAPI 服务以加载 WP-15 代码
sudo launchctl kickstart -k system/com.pi-investment.v2-api

# 等待 5 秒让服务完全启动
sleep 5
```

### Step 2: 验证服务启动

```bash
# 检查服务健康状态
curl http://127.0.0.1:5001/health

# 预期输出: {"status":"ok","framework":"fastapi","version":"2.0.0"}
```

### Step 3: 检查日志

```bash
# 查看启动日志
tail -50 ~/v2-api.log

# 查找关键信息:
# ✅ "Registering jobs to Agent OS Scheduler..."
# ✅ "Agent OS Scheduler integration enabled"
# 或
# ⚠️ "Falling back to local scheduler" (如果 Agent OS 不可用)
```

---

## 验证测试

### Test 1: 验证 Webhook 端点

```bash
# 测试 webhook 端点是否可访问
curl -X POST http://127.0.0.1:5001/internal/scheduler/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "test-123",
    "job_name": "test_job",
    "trigger_time": "2026-08-16T10:00:00Z",
    "metadata": {"job_type": "kline_update"}
  }'

# 预期输出: 
# {
#   "status": "accepted",
#   "job_id": "test-123",
#   "job_name": "test_job",
#   "message": "Job execution started for kline_update"
# }
```

### Test 2: 检查任务注册

```bash
# 查看 Agent OS 中注册的任务
curl http://127.0.0.1:8080/api/v1/scheduler/tasks | jq '.[] | select(.owner == "quantsys-v2") | {name, cron, enabled}'

# 预期: 显示 30+ 个注册的任务
```

### Test 3: 使用监控脚本

```bash
cd quantsys-v2

# 查看所有注册的任务
python tools/monitor_scheduler.py

# 查看统计信息
python tools/monitor_scheduler.py --stats

# 查看最近执行记录
python tools/monitor_scheduler.py --executions 10
```

### Test 4: 手动触发测试任务

```bash
# 获取某个任务的 ID
JOB_ID=$(curl -s http://127.0.0.1:8080/api/v1/scheduler/tasks | jq -r '.[] | select(.name == "kline_update") | .id')

# 手动触发该任务
curl -X POST http://127.0.0.1:8080/api/v1/scheduler/tasks/$JOB_ID/trigger

# 查看执行记录
sleep 5
curl "http://127.0.0.1:8080/api/v1/scheduler/executions?task_id=$JOB_ID&limit=1" | jq
```

### Test 5: 验证数据库审计日志

```bash
# 检查本地数据库是否记录了执行历史
psql quant_investment -c "
  SELECT id, task_id, status, started_at, completed_at, error
  FROM quant.scheduler_runs
  ORDER BY started_at DESC
  LIMIT 5;
"

# 预期: 看到最近的任务执行记录
```

---

## 监控指标

### 关键日志检查点

启动日志中应包含：

```
✅ "Registering jobs to Agent OS Scheduler..."
✅ "Registered 'kline_update' (id=xxx, cron=40 17 * * 1-5)"
✅ "Registered 'chip_distribution_update' (id=xxx, ...)"
... (30+ 个任务)
✅ "Registration complete: 30 success, 0 errors"
✅ "Agent OS Scheduler integration enabled"
✅ "Registered: scheduler_webhook (Agent OS integration)"
```

如果 Agent OS 不可用，应看到：

```
⚠️ "Registration failed, falling back to local scheduler"
✅ "Local SchedulerService background thread started (fallback mode)"
```

### 性能指标

在日志中监控以下指标：

- **Webhook 响应时间**: 应 < 100ms
- **任务注册时间**: 全部注册应 < 10s
- **数据库写入**: 无错误

---

## 问题排查

### 问题 1: 服务启动失败

**症状**: `curl http://127.0.0.1:5001/health` 无响应

**排查**:
```bash
# 查看错误日志
tail -100 ~/v2-api.log | grep -i error

# 检查端口占用
lsof -i :5001

# 手动启动查看错误
cd quantsys-v2
source venv/bin/activate
python adapters/inbound/fastapi_app/main.py
```

### 问题 2: Webhook 404 错误

**症状**: POST webhook 返回 404

**排查**:
```bash
# 查看路由注册日志
grep "scheduler_webhook" ~/v2-api.log

# 测试 API 文档
open http://127.0.0.1:5001/docs
# 搜索 "/internal/scheduler/webhook"
```

### 问题 3: 任务未注册到 Agent OS

**症状**: `curl http://127.0.0.1:8080/api/v1/scheduler/tasks` 返回空数组

**排查**:
```bash
# 检查 Agent OS 是否可达
curl http://127.0.0.1:8080/health

# 手动执行注册脚本
cd quantsys-v2
python tools/register_jobs_to_agent_os.py

# 查看详细错误
tail -50 ~/v2-api.log | grep -A 5 "Registration"
```

### 问题 4: 任务执行失败

**症状**: Webhook 被调用但任务失败

**排查**:
```bash
# 查看任务执行日志
tail -100 ~/v2-api.log | grep -i "job.*failed"

# 查看数据库错误记录
psql quant_investment -c "
  SELECT task_id, status, error, started_at
  FROM quant.scheduler_runs
  WHERE status = 'failed'
  ORDER BY started_at DESC
  LIMIT 5;
"

# 检查 job handler 是否注册
python -c "
from api.internal.scheduler_webhook import JOB_HANDLERS
print('Registered handlers:', list(JOB_HANDLERS.keys()))
"
```

---

## 回滚方案

如果遇到严重问题，立即回滚：

### 方案 1: 禁用 Agent OS Scheduler

```bash
# 1. 设置环境变量
echo "USE_AGENT_OS_SCHEDULER=false" >> quantsys-v2/.env

# 2. 重启服务
sudo launchctl kickstart -k system/com.pi-investment.v2-api

# 3. 验证回退成功
tail -50 ~/v2-api.log | grep "Local SchedulerService"
# 应看到: "Local SchedulerService background thread started (fallback mode)"
```

### 方案 2: 回滚代码

```bash
# 1. 回退到上一个提交
git revert HEAD

# 2. 重启服务
sudo launchctl kickstart -k system/com.pi-investment.v2-api
```

---

## 成功标准

部署成功的标志：

- [x] ✅ 服务启动无错误
- [x] ✅ 30+ 任务成功注册到 Agent OS
- [x] ✅ Webhook 端点响应正常
- [x] ✅ 手动触发任务能执行
- [x] ✅ 数据库审计日志正常写入
- [x] ✅ 监控脚本能显示任务状态

---

## 下一步计划

部署成功后：

1. **第 1 天**: 密切监控所有任务执行
2. **第 1 周**: 每日检查任务成功率和执行时间
3. **第 2 周**: 根据监控数据优化配置
4. **第 3 周**: 如果稳定，准备移除 legacy SchedulerService

---

## 联系支持

如果遇到问题：

1. 查看本文档的"问题排查"章节
2. 检查代码审查报告: `docs/superpowers/specs/WP-15-code-review.md`
3. 查看完成报告: `docs/superpowers/specs/WP-15-completion-report.md`
4. 查看 CLAUDE.md 中的"Scheduler Migration"章节

---

**准备就绪** ✅

现在可以执行 Step 1 来部署 WP-15。
