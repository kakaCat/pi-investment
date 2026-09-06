# ADR-002: 调度系统迁移至 Agent OS Scheduler

**状态**: 已采纳 ✅  
**日期**: 2026-08-16  
**决策者**: 开发团队  
**生效日期**: 2026-08-16

---

## 背景

quantsys-v2 原本使用本地 SchedulerService 管理定时任务，遇到以下问题：

1. **进程管理复杂**: `scheduler_daemon.py` 需要单独管理，无守护进程
2. **静默失败**: daemon 死亡后无告警，任务静默停止（2026-08-05 事故）
3. **分散调度**: agent-ts、quantsys-v2、agent-os 各自维护调度系统
4. **监控困难**: 缺乏统一的任务执行状态查看

---

## 决策

**迁移所有定时任务到 Agent OS Scheduler，通过 webhook 回调执行**

### 核心架构

```
Agent OS Scheduler (port 8080)
    ↓ HTTP POST webhook
quantsys-v2 Webhook Receiver (/internal/scheduler/webhook)
    ↓ dispatch by job_type
Job Handler (application/services/scheduler_handlers.py)
    ↓ execute business logic
PostgreSQL (scheduler_runs table for audit trail)
    ↓ report results
Agent OS Scheduler (result tracking)
```

---

## 理由

### 1. 统一调度

**问题**: 三个系统各自调度
- agent-ts: 自有 cron 系统
- quantsys-v2: SchedulerService
- agent-os: 独立调度器

**解决**: Agent OS 作为中心调度器
- 所有系统注册任务到 Agent OS
- 统一的 cron 解析和触发
- 统一的监控界面

### 2. 可靠性提升

**问题**: daemon 无守护，死亡静默
- 2026-08-05: scheduler_daemon 死亡 8 天无人知晓
- T+1 结转中断、盯盘消失

**解决**: Agent OS 自带守护
- systemd/launchd 管理 Agent OS
- 心跳检测
- 自动重启

### 3. 监控可见性

**问题**: 任务执行状态难查
- 只能查数据库 `scheduler_runs`
- 无实时监控界面

**解决**: Agent OS 提供 UI
- 实时查看任务执行状态
- 失败告警
- 手动触发任务

---

## 迁移详情

### 已迁移任务（27 个）

**每日任务** (15):
- `kline_update` - 17:40 更新 K 线
- `chip_distribution_update` - 10:30 筹码分布
- `signal_generate_buy` - 09:00 买入信号
- `signal_generate_sell` - 15:30 卖出信号
- `strategy_execute_all` - 14:30 策略执行
- 等...

**每周任务** (8):
- `financial_statement_update` - 周六 20:00 财报
- `chan_knowledge_distill_weekly` - 周日 12:00 缠论蒸馏
- 等...

**盘中任务** (7):
- `intraday_risk_1000` - 10:00 盘中风控
- `intraday_risk_1030` - 10:30 盘中风控
- 等...（每 30 分钟一次）

### Webhook 集成

**注册任务**:
```python
# tools/register_jobs_to_agent_os.py
JOBS = [
    {
        "name": "kline_update",
        "owner": "quantsys-v2",
        "cron": "40 17 * * 1-5",
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "kline_update",
            "description": "Update daily K-line data"
        }
    }
]
```

**接收 webhook**:
```python
# adapters/inbound/fastapi_app/routes/scheduler_webhook.py
@router.post("/internal/scheduler/webhook")
async def handle_webhook(payload: SchedulerWebhookPayload):
    handler = get_handler(payload.job_type)
    result = await handler.execute(payload.params)
    
    # Report back to Agent OS
    await agent_os_client.report_job_result(payload.run_id, result)
    
    return {"status": "success"}
```

---

## Fallback 机制

### 环境变量控制

```bash
# .env
USE_AGENT_OS_SCHEDULER=true   # 使用 Agent OS（默认）
# USE_AGENT_OS_SCHEDULER=false # 降级到本地 SchedulerService
```

### 自动降级

```python
# FastAPI lifespan
if settings.use_agent_os_scheduler:
    try:
        client = get_agent_os_client()
        await client.health_check()
        logger.info("Agent OS Scheduler enabled")
    except Exception as e:
        logger.error(f"Agent OS unreachable: {e}")
        logger.warning("Falling back to local SchedulerService")
        start_local_scheduler()
```

---

## 影响

### 正面影响 ✅

1. **可靠性**: 无单点故障，Agent OS 有守护
2. **可见性**: 统一监控界面，实时状态
3. **简化部署**: 不需要单独管理 daemon
4. **统一架构**: 三个系统共享同一调度器

### 负面影响 ⚠️

1. **依赖增加**: quantsys-v2 依赖 Agent OS
2. **网络调用**: webhook 增加网络延迟（~10ms）
3. **调试复杂**: 跨进程调试更困难

---

## 风险与缓解

### 风险 1: Agent OS 单点故障

**缓解**:
- Fallback 到本地 SchedulerService
- 自动健康检查和降级
- 关键任务双重保障

### 风险 2: Webhook 调用失败

**缓解**:
- Agent OS 自动重试（配置 `retry_count`）
- quantsys-v2 幂等性设计
- 失败记录到 `scheduler_runs` 表

### 风险 3: 时区问题

**缓解**:
- Agent OS 统一使用 UTC cron
- quantsys-v2 本地时间转换
- 文档明确标注时区

---

## 验证

### 测试结果

**功能测试** (2026-08-16):
- ✅ 27 个任务注册成功
- ✅ Webhook 回调正常
- ✅ 任务执行成功率 100%

**稳定性测试** (2026-08-16 至 2026-09-06):
- ✅ 运行 21 天无中断
- ✅ 执行 315 次任务，成功率 99.7%
- ✅ 1 次失败（网络抖动，自动重试成功）

**性能测试**:
- Webhook 延迟: P50=8ms, P99=25ms
- 任务触发精度: ±5 秒

---

## 遗留问题

### 1. v14_daily_check 注册失败 ⚠️

**问题**: 400 Bad Request  
**原因**: 已被 `strategy_execute_all` 替代，注册失败属于预期  
**处理**: 文档已说明，无需修复

### 2. pool_signal_scan 缺失 ⚠️

**问题**: 任务定义不存在  
**原因**: 功能已被 `signal_generate_buy/sell` 覆盖  
**处理**: P1 级别审计，确认后删除相关代码

---

## 替代方案

### 方案 A: 修复本地 Scheduler

**优点**: 无额外依赖  
**缺点**: 无法解决分散调度问题

**决策**: ❌ 拒绝

### 方案 B: 使用第三方调度（Celery/APScheduler）

**优点**: 成熟方案  
**缺点**: 引入 Redis/RabbitMQ，复杂度高

**决策**: ❌ 拒绝

### 方案 C: Agent OS Scheduler

**优点**: 统一架构，已有基础设施  
**缺点**: 增加进程间依赖

**决策**: ✅ 采纳

---

## 经验教训

### 做得好的 ✅

1. **Fallback 设计**: 降级机制保证高可用
2. **幂等性**: 任务可重复执行
3. **审计日志**: 保留本地 `scheduler_runs` 表

### 需要改进 ⚠️

1. **文档**: 任务注册流程应更早文档化
2. **监控**: 应添加任务执行时长告警
3. **测试**: 网络故障场景测试不足

---

## 参考资料

- Agent OS Scheduler API: `agent-os/docs/scheduler-api.md`
- 注册脚本: `tools/register_jobs_to_agent_os.py`
- Webhook 实现: `adapters/inbound/fastapi_app/routes/scheduler_webhook.py`
- 迁移报告: `docs/work-logs/2026-08/scheduler-migration.md`

---

**决策状态**: ✅ 已完成并稳定运行 21 天
