# Scheduler JobRegistry 架构文档 - 2026-09-01

## 文档概述

本文档描述 scheduler.py 到 JobRegistry 重构后的最终架构、数据流和执行流程。

**重构日期：** 2026-09-01  
**重构目标：** 统一任务注册，消除双轨系统，简化维护  
**重构成果：** 代码减少600行，13个阻塞任务立即可用

---

## 1. 架构全景图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application Startup                       │
│  (adapters/inbound/fastapi_app/main.py::lifespan)                      │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         │ 1. register_all_jobs()
                         ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         JobRegistry (全局单例)                           │
│  application/jobs/job_registry.py                                       │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Jobs: Dict[str, Job]                                           │   │
│  │  ├─ fund_flow_update          → FundFlowUpdateJob              │   │
│  │  ├─ pool_refresh_daily        → PoolRefreshDailyJob            │   │
│  │  ├─ chan_scan                 → ChanScanJob                    │   │
│  │  ├─ signal_generate           → SignalGenerateJob              │   │
│  │  ├─ data_quality_check        → DataQualityCheckJob            │   │
│  │  ├─ kline_update              → KlineUpdateJob                 │   │
│  │  ├─ v13_daily_check           → V13DailyCheckJob               │   │
│  │  ├─ ... (共28个job)                                            │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Methods:                                                                │
│  • get(name: str) → Optional[Job]                                       │
│  • execute(name: str, params: Dict) → JobResult                         │
└─────────────────────────────────────────────────────────────────────────┘
                         ↑
                         │ 2. 查找并执行job
                         │
┌─────────────────────────────────────────────────────────────────────────┐
│                    SchedulerService (调度核心)                           │
│  infrastructure/scheduler/scheduler.py                                  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  _execute_command(command: str, params: Dict) → Dict            │ │
│  │                                                                   │ │
│  │  ┌─ 优先路径: JobRegistry ─────────────────────────┐            │ │
│  │  │                                                   │            │ │
│  │  │  job = job_registry.get(command)                 │            │ │
│  │  │  if job is not None:                             │            │ │
│  │  │      result = asyncio.run(                       │            │ │
│  │  │          job_registry.execute(command, params)   │            │ │
│  │  │      )                                            │            │ │
│  │  │      return convert_to_dict(result)  # 向后兼容  │            │ │
│  │  └───────────────────────────────────────────────────┘            │ │
│  │                                                                   │ │
│  │  ┌─ Fallback路径: Legacy Handlers ─────────────────┐            │ │
│  │  │                                                   │            │ │
│  │  │  legacy_handlers = {                             │            │ │
│  │  │      "data_update": _handle_data_update,         │            │ │
│  │  │      "risk_check": _handle_risk_check,           │            │ │
│  │  │      "backtest_run": _handle_backtest_run,       │            │ │
│  │  │      "model_train": _handle_model_train,         │            │ │
│  │  │      "benchmark_run": _handle_benchmark_run,     │            │ │
│  │  │      "index_constituents_update": ...            │            │ │
│  │  │  }                                                │            │ │
│  │  │  return legacy_handlers[command](params)         │            │ │
│  │  └───────────────────────────────────────────────────┘            │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  • run_loop() - 30秒轮询，检查到期任务                                   │
│  • run_task(task_id) - 执行单个任务                                     │
│  • create_run() / complete_run() - 记录执行历史                         │
└─────────────────────────────────────────────────────────────────────────┘
                         ↑
                         │ 3. 定时触发
                         │
┌─────────────────────────────────────────────────────────────────────────┐
│                      调度触发机制（三选一）                              │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ A. Agent OS Scheduler (优先)                                     │  │
│  │    - Agent OS 统一调度                                           │  │
│  │    - Webhook 回调 quantsys-v2                                    │  │
│  │    - URL: POST /internal/scheduler/webhook                       │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ B. Local SchedulerService (Fallback)                            │  │
│  │    - 后台线程每30秒轮询                                          │  │
│  │    - 查询 scheduler_tasks 表                                     │  │
│  │    - 自动执行到期任务                                            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ C. HTTP API 手动触发                                             │  │
│  │    - POST /api/scheduler/tasks/{task_id}/run                     │  │
│  │    - 立即执行指定任务                                            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                         ↑
                         │
┌─────────────────────────────────────────────────────────────────────────┐
│                      PostgreSQL Database (quant)                         │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  scheduler_tasks (任务定义)                                     │   │
│  │  ├─ id, name, cron_expression, command, params                 │   │
│  │  ├─ is_enabled, next_run_at, last_run_at                       │   │
│  │  └─ misfire_grace_time_seconds                                 │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  scheduler_runs (执行历史)                                      │   │
│  │  ├─ id, task_id, status, started_at, completed_at             │   │
│  │  ├─ result (jsonb), error, duration_ms                         │   │
│  │  └─ 索引: task_id, status, started_at                          │   │
│  └────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Job 模块组织结构

```
application/jobs/
├── job_protocol.py              # Job 接口定义
│   ├── class Job (ABC)
│   │   ├── name: str            # job名称
│   │   ├── description: str     # 描述
│   │   ├── timeout_seconds: int # 超时时间
│   │   └── execute(params) → JobResult
│   └── class JobResult
│       ├── success: bool
│       ├── message: str
│       ├── details: Dict
│       └── error: Optional[str]
│
├── job_registry.py              # 注册表单例
│   └── JobRegistry
│       ├── _jobs: Dict[str, Job]
│       ├── register(job)
│       ├── get(name) → Job
│       └── execute(name, params) → JobResult
│
├── registry_setup.py            # 启动注册
│   └── register_all_jobs()
│       └── 注册所有 *_jobs.py 中的 Job 实例
│
├── data_jobs.py                 # 数据类任务 (5个)
│   ├── KlineUpdateJob
│   ├── DataQualityCheckJob
│   ├── DataPipelineDailyJob
│   ├── DataPipelineWeeklyJob
│   └── ChipDistributionUpdateJob
│
├── signal_jobs.py               # 信号类任务 (4个)
│   ├── SignalGenerateJob
│   ├── SignalExecutionDailyJob
│   ├── SignalMonitorRealtimeJob
│   └── MarketScanPreopenJob
│
├── trading_jobs.py              # 交易类任务 (6个)
│   ├── V13DailyCheckJob
│   ├── V13RiskCheckJob
│   ├── V13VerificationJob
│   ├── V13WeeklyReportJob
│   ├── V14DailyCheckJob
│   └── TradeVerifyDailyJob
│
├── analysis_jobs.py             # 分析类任务 (5个)
│   ├── FactorComputeJob
│   ├── ChanScanJob
│   ├── ChanKnowledgeDistillJob
│   ├── MarketStyleUpdateJob
│   └── MarketPerceptionDailySnapshotJob
│
├── report_jobs.py               # 报告类任务 (3个)
│   ├── ReportDailyJob
│   ├── DailyEquitySnapshotJob
│   └── DecisionScoreDailyJob
│
└── monitor_jobs.py              # 监控类任务 (5个)
    ├── PoolRefreshDailyJob
    ├── StrategyValidateDailyJob
    ├── StrategyDiscoverWeeklyJob
    ├── FinancialDataUpdateJob
    └── FinancialStatementUpdateJob

总计: 28个Job (全部注册到JobRegistry)
```

---

## 3. 任务执行流程图

### 3.1 定时任务执行流程（自动触发）

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. 定时器触发 (每30秒 or cron时间到)                                │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────────────────────────────┐
│  2. SchedulerService.run_due_tasks()                                 │
│     - 查询 scheduler_tasks 表                                        │
│     - WHERE is_enabled=true AND next_run_at <= NOW()                │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────────────────────────────┐
│  3. 遍历到期任务                                                     │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓
         ┌─────┴─────┐
         │  任务A    │
         └─────┬─────┘
               │
               ↓
┌──────────────────────────────────────────────────────────────────────┐
│  4. 检查是否已运行 (防止重复提交)                                    │
│     SELECT * FROM scheduler_runs                                     │
│     WHERE task_id=A AND status='running'                             │
└──────────────┬───────────────────────────────────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
    已运行         未运行
        │             │
        ↓             ↓
   ┌────────┐   ┌─────────────────────────────────────────────┐
   │ 检查   │   │  5. 检查僵尸任务 (running > 6小时)           │
   │ 僵尸   │   │     - 是 → 判死并放行                       │
   │ 超时   │   │     - 否 → raise ValueError("already running")│
   └────────┘   └─────────┬───────────────────────────────────┘
        │                 │
        ↓                 ↓
   ┌────────┐        ┌────────────────────────────────────────┐
   │ 判死   │        │  6. 创建run记录                         │
   │ 放行   │        │     run_id = create_run(task_id)        │
   └────────┘        │     status='running', started_at=NOW()  │
                     └─────────┬──────────────────────────────┘
                               │
                               ↓
                     ┌─────────────────────────────────────────┐
                     │  7. _execute_command(command, params)   │
                     │                                         │
                     │  ┌─────────────────────────────────┐  │
                     │  │ 7a. 查找 JobRegistry            │  │
                     │  │     job = job_registry.get(cmd) │  │
                     │  └────┬────────────────────────────┘  │
                     │       │                               │
                     │  ┌────┴─────┐                        │
                     │  │          │                        │
                     │ 找到       找不到                    │
                     │  │          │                        │
                     │  ↓          ↓                        │
                     │ JobRegistry  Legacy Handler          │
                     │ 执行         执行                     │
                     └─────────┬───────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                 成功                   失败
                    │                     │
                    ↓                     ↓
        ┌────────────────────┐  ┌────────────────────┐
        │  8a. 成功处理      │  │  8b. 失败处理      │
        │  complete_run(     │  │  complete_run(     │
        │    run_id,         │  │    run_id,         │
        │    success=True,   │  │    success=False,  │
        │    result=dict     │  │    error=str       │
        │  )                 │  │  )                 │
        └────────┬───────────┘  └────────┬───────────┘
                 │                       │
                 ↓                       ↓
        ┌────────────────────────────────────────┐
        │  9. 更新任务表                         │
        │     - next_run_at = 计算下次执行时间   │
        │     - last_run_at = NOW()              │
        └────────────────────────────────────────┘
                 │
                 ↓
        ┌────────────────────────────────────────┐
        │  10. ORM Session 清理                  │
        │      close_session()                   │
        │      (防止连接泄漏)                    │
        └────────────────────────────────────────┘
```

### 3.2 Job执行流程（JobRegistry路径）

```
┌──────────────────────────────────────────────────────────────────────┐
│  _execute_command(command="fund_flow_update", params={...})          │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────────────────────────────┐
│  1. 查找 JobRegistry                                                 │
│     job = job_registry.get("fund_flow_update")                       │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓ job is not None
┌──────────────────────────────────────────────────────────────────────┐
│  2. 异步执行 (同步上下文中运行)                                      │
│     result = asyncio.run(                                            │
│         job_registry.execute("fund_flow_update", params)             │
│     )                                                                │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────────────────────────────┐
│  3. JobRegistry.execute() 内部                                       │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  job = self.get("fund_flow_update")  # FundFlowUpdateJob   │   │
│  │  result = await job.execute(params)  # 调用Job.execute()   │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────────────────────────────┐
│  4. FundFlowUpdateJob.execute(params)                                │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  try:                                                       │   │
│  │      # 委托给实际实现                                       │   │
│  │      from infrastructure.jobs.fund_flow_update_job import  │   │
│  │          execute                                            │   │
│  │      result = execute(**params)                             │   │
│  │                                                             │   │
│  │      # 返回 JobResult                                       │   │
│  │      return JobResult.ok(                                   │   │
│  │          name="fund_flow_update",                           │   │
│  │          message="资金流更新完成",                          │   │
│  │          details=result                                     │   │
│  │      )                                                       │   │
│  │  except Exception as e:                                     │   │
│  │      return JobResult.fail(                                 │   │
│  │          name="fund_flow_update",                           │   │
│  │          error=str(e)                                       │   │
│  │      )                                                       │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────────────────────────────┐
│  5. 返回 JobResult                                                   │
│     JobResult(                                                       │
│         success=True,                                                │
│         message="资金流更新完成",                                    │
│         details={"symbols_updated": 4521, "errors": 0},              │
│         error=None                                                   │
│     )                                                                │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────────────────────────────┐
│  6. 转换为dict格式 (向后兼容)                                        │
│     return {                                                         │
│         "action": "fund_flow_update",                                │
│         "status": "success",                                         │
│         "message": "资金流更新完成",                                 │
│         "details": {"symbols_updated": 4521, "errors": 0},           │
│         "error": None                                                │
│     }                                                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. 数据模型

### 4.1 scheduler_tasks 表

```sql
CREATE TABLE quant.scheduler_tasks (
    id                        BIGSERIAL PRIMARY KEY,
    name                      TEXT NOT NULL UNIQUE,
    description               TEXT,
    cron_expression           TEXT NOT NULL,  -- "0 9 * * 1-5" or "managed_by_agent_os"
    command                   TEXT NOT NULL,  -- 对应 JobRegistry 中的 job name
    params                    JSONB,          -- 任务参数
    is_enabled                BOOLEAN DEFAULT true,
    next_run_at               TIMESTAMPTZ,
    last_run_at               TIMESTAMPTZ,
    misfire_grace_time_seconds INTEGER DEFAULT 300,  -- 超过宽限时间跳过本次
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scheduler_tasks_enabled ON quant.scheduler_tasks(is_enabled);
CREATE INDEX idx_scheduler_tasks_next_run ON quant.scheduler_tasks(next_run_at);
```

**关键字段说明：**
- `command`：必须匹配 JobRegistry 中的 job name（如 "fund_flow_update"）
- `cron_expression`：标准5字段cron表达式，或特殊值 "managed_by_agent_os"
- `misfire_grace_time_seconds`：错过执行时间后的宽限期，超过则跳过

### 4.2 scheduler_runs 表

```sql
CREATE TABLE quant.scheduler_runs (
    id           BIGSERIAL PRIMARY KEY,
    task_id      BIGINT REFERENCES quant.scheduler_tasks(id) ON DELETE CASCADE,
    status       TEXT NOT NULL DEFAULT 'running',  -- 'running' | 'success' | 'failed' | 'skipped'
    started_at   TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms  INTEGER,
    result       JSONB,  -- 成功时的返回结果
    error        TEXT    -- 失败时的错误信息
);

CREATE INDEX idx_scheduler_runs_task_id ON quant.scheduler_runs(task_id);
CREATE INDEX idx_scheduler_runs_status ON quant.scheduler_runs(status);
CREATE INDEX idx_scheduler_runs_started_at ON quant.scheduler_runs(started_at DESC);
```

**状态流转：**
1. `running` - 创建run记录时的初始状态
2. `success` - 任务成功完成
3. `failed` - 任务执行失败
4. `skipped` - 因misfire或其他原因跳过

---

## 5. 命令路由规则

### 5.1 优先级顺序

```
请求执行命令 "X"
    ↓
1. 查找 JobRegistry
    job = job_registry.get("X")
    ↓
   找到? ────Yes──→ 执行 JobRegistry 路径
    │
    No
    ↓
2. 查找 Legacy Handlers
    handler = legacy_handlers.get("X")
    ↓
   找到? ────Yes──→ 执行 Legacy Handler
    │
    No
    ↓
3. raise ValueError("Unknown scheduler command: 'X'")
```

### 5.2 当前命令分布

**JobRegistry 路径（28个）：**
```
✅ chan_knowledge_distill        ✅ chan_scan
✅ chip_distribution_update      ✅ daily_equity_snapshot
✅ data_pipeline_daily           ✅ data_pipeline_weekly
✅ data_quality_check            ✅ factor_compute
✅ financial_data_update         ✅ financial_statement_update
✅ fund_flow_update              ✅ kline_update
✅ market_perception_daily_snapshot  ✅ market_scan_preopen
✅ market_style_update           ✅ pool_refresh_daily
✅ report_daily                  ✅ signal_execution_daily
✅ signal_generate               ✅ signal_monitor_realtime
✅ strategy_discover_weekly      ✅ strategy_validate_daily
✅ trade_verify_daily            ✅ v13_daily_check
✅ v13_risk_check                ✅ v13_verification
✅ v13_weekly_report             ✅ v14_daily_check
```

**Legacy Handler 路径（6个）：**
```
⚠️ data_update                    (6个任务使用，待迁移)
⚠️ risk_check                     (风险检查，待迁移)
⚠️ backtest_run                   (回测，待迁移)
⚠️ model_train                    (模型训练，待迁移)
⚠️ benchmark_run                  (基准测试，待迁移)
⚠️ index_constituents_update     (指数成分股，待迁移)
```

---

## 6. 关键代码片段

### 6.1 应用启动时注册Job

```python
# adapters/inbound/fastapi_app/main.py::lifespan()

# 初始化 JobRegistry（2026-09-01: scheduler 重构）
try:
    from application.jobs.registry_setup import register_all_jobs
    register_all_jobs()
    logger.info("✅ JobRegistry initialized (28 jobs registered)")
except Exception as e:
    logger.error(f"❌ JobRegistry initialization failed: {e}")
```

### 6.2 调度器命令执行

```python
# infrastructure/scheduler/scheduler.py::_execute_command()

def _execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch command to JobRegistry (primary) or legacy handler (fallback)."""
    from application.jobs.job_registry import job_registry
    import asyncio
    
    # 1. 优先从 JobRegistry 获取 job
    job = job_registry.get(command)
    if job is not None:
        logger.info(f"Executing job via JobRegistry: {command}")
        try:
            # JobRegistry.execute 是 async 的
            result = asyncio.run(job_registry.execute(command, params or {}))
            
            # 将 JobResult 转换为原来的 dict 格式（向后兼容）
            return {
                "action": command,
                "status": "success" if result.success else "failed",
                "message": result.message,
                "details": result.details or {},
                "error": result.error,
            }
        except Exception as e:
            logger.exception(f"JobRegistry execution failed for {command}")
            return {
                "action": command,
                "status": "failed",
                "error": str(e),
            }
    
    # 2. Fallback: 使用旧的 handler
    logger.debug(f"Job not in JobRegistry, trying legacy handler: {command}")
    legacy_handlers: Dict[str, Any] = {
        "data_update": self._handle_data_update,
        "risk_check": self._handle_risk_check,
        "backtest_run": self._handle_backtest_run,
        "model_train": self._handle_model_train,
        "benchmark_run": self._handle_benchmark_run,
        "index_constituents_update": self._handle_index_constituents_update,
    }
    
    handler = legacy_handlers.get(command)
    if handler is None:
        raise ValueError(f"Unknown scheduler command: {command!r}")
    
    return handler(params)
```

### 6.3 Job 实现示例

```python
# application/jobs/data_jobs.py

class FundFlowUpdateJob(Job):
    """资金流向日更任务"""
    
    @property
    def name(self) -> str:
        return "fund_flow_update"
    
    @property
    def description(self) -> str:
        return "每日更新资金流向数据（主力/大单/中单/小单流向）"
    
    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟
    
    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            # 委托给实际实现
            from infrastructure.jobs.fund_flow_update_job import execute
            result = execute(**params)
            
            return JobResult.ok(
                self.name,
                message=f"资金流更新完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有数据类任务
DATA_JOBS = [
    KlineUpdateJob(),
    DataQualityCheckJob(),
    FundFlowUpdateJob(),  # ← 新增
    DataPipelineDailyJob(),
    DataPipelineWeeklyJob(),
    ChipDistributionUpdateJob(),
]
```

---

## 7. 重构前后对比

### 7.1 架构对比

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| **任务注册方式** | 手动在 `_execute_command()` 中添加映射 | 自动注册到 JobRegistry |
| **新增任务流程** | 1. 实现handler方法<br>2. 在handlers字典添加映射<br>3. 测试 | 1. 创建Job类<br>2. 加入对应*_jobs.py列表 |
| **代码行数** | ~1500行 | ~900行 (-600行) |
| **handler方法数** | 40+ | 6个 (只保留特殊命令) |
| **维护复杂度** | 高（每个任务一个方法） | 低（统一Job接口） |
| **可执行任务** | 20/33 (60.6%) | 33/33 (100%) |

### 7.2 执行路径对比

**重构前（旧路径）：**
```
scheduler.run_task(task_id)
    ↓
_execute_command(command, params)
    ↓
handlers[command]  ← 查找手动维护的字典
    ↓
_handle_fund_flow_update(params)  ← 找不到 → ValueError
    ↓
infrastructure.jobs.fund_flow_update_job.execute()
```

**重构后（新路径）：**
```
scheduler.run_task(task_id)
    ↓
_execute_command(command, params)
    ↓
job_registry.get(command)  ← 自动注册的JobRegistry
    ↓
FundFlowUpdateJob.execute(params)  ← 找到 ✅
    ↓
infrastructure.jobs.fund_flow_update_job.execute()
```

### 7.3 错误率对比

**重构前（2026-08-31 数据）：**
- Unknown command 错误：13个任务
- fund_flow_update 失败率：75%
- pool_refresh_daily 失败率：83.3%
- 整体任务成功率：~60%

**重构后（预期）：**
- Unknown command 错误：0个
- fund_flow_update 失败率：<5%
- pool_refresh_daily 失败率：<5%
- 整体任务成功率：>95%

---

## 8. 未来演进方向

### 8.1 P1 - 完成Legacy Handler迁移

**目标：** 将剩余6个legacy handler迁移到JobRegistry

**迁移计划：**
1. `data_update` → `DataUpdateJob`
2. `risk_check` → `RiskCheckJob`
3. `backtest_run` → `BacktestRunJob`
4. `model_train` → `ModelTrainJob`
5. `benchmark_run` → `BenchmarkRunJob`
6. `index_constituents_update` → `IndexConstituentsUpdateJob`

**完成后：**
- 删除所有 `_handle_*` 方法
- `_execute_command()` 只保留JobRegistry查找逻辑
- 架构完全统一

### 8.2 P2 - Job超时和重试机制

**当前缺失：**
- Job执行超时控制（定义了 `timeout_seconds` 但未实施）
- 失败任务自动重试
- 任务依赖管理（A任务成功后才执行B任务）

**建议实现：**
```python
class JobRegistry:
    async def execute(self, name: str, params: Dict) -> JobResult:
        job = self.get(name)
        if job is None:
            return JobResult.fail(name, f"Unknown job: {name}")
        
        try:
            # 超时控制
            result = await asyncio.wait_for(
                job.execute(params),
                timeout=job.timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            return JobResult.fail(
                name, 
                f"Job timeout after {job.timeout_seconds}s"
            )
        except Exception as e:
            # 重试逻辑
            if should_retry(job, e):
                return await self._retry_execute(job, params)
            return JobResult.fail(name, str(e))
```

### 8.3 P3 - 任务优先级和资源控制

**当前问题：**
- 所有任务同等优先级
- 无并发控制（可能同时运行多个资源密集型任务）

**建议方案：**
```python
class Job(ABC):
    @property
    def priority(self) -> int:
        """优先级 (1=最高, 10=最低)"""
        return 5
    
    @property
    def resource_group(self) -> str:
        """资源组 (用于并发控制)"""
        return "default"

# 调度器中实现
class SchedulerService:
    def __init__(self):
        self._resource_pools = {
            "cpu_intensive": Semaphore(2),   # 最多2个CPU密集任务
            "io_intensive": Semaphore(5),    # 最多5个IO密集任务
            "default": Semaphore(10),        # 默认10个并发
        }
```

---

## 9. 故障排查指南

### 9.1 任务执行失败

**症状：** 任务状态为 `failed`，scheduler_runs表有错误记录

**排查步骤：**
1. 查看错误信息
   ```sql
   SELECT error FROM quant.scheduler_runs 
   WHERE task_id = X 
   ORDER BY started_at DESC LIMIT 1;
   ```

2. 检查错误类型
   - `Unknown scheduler command` → 命令未在JobRegistry或legacy handlers中
   - `Job not found in registry` → JobRegistry未初始化或Job未注册
   - 其他错误 → Job内部执行异常

3. 验证JobRegistry初始化
   ```python
   from application.jobs.job_registry import job_registry
   print(job_registry.list_jobs().keys())  # 应该看到28个job
   ```

### 9.2 任务未执行

**症状：** 任务到了执行时间但没有运行记录

**排查步骤：**
1. 检查任务是否启用
   ```sql
   SELECT is_enabled, next_run_at 
   FROM quant.scheduler_tasks 
   WHERE id = X;
   ```

2. 检查调度器是否运行
   ```bash
   # 查看5001进程日志
   tail -f ~/v2-api.log | grep -i scheduler
   ```

3. 检查next_run_at是否更新
   - 如果next_run_at一直不变 → 调度器可能卡死
   - 如果next_run_at正常更新 → 任务可能在misfire宽限期内被跳过

### 9.3 僵尸任务

**症状：** scheduler_runs 中有 `status='running'` 的记录超过6小时

**自动处理：**
- SchedulerService 会自动判死超过6小时的running记录
- 判死后下次执行会放行

**手动清理：**
```sql
UPDATE quant.scheduler_runs 
SET status = 'failed', 
    completed_at = NOW(),
    error = '手动清理僵尸任务'
WHERE status = 'running' 
  AND started_at < NOW() - INTERVAL '6 hours';
```

---

## 10. 性能指标

### 10.1 调度器性能

| 指标 | 目标值 | 监控方法 |
|------|--------|---------|
| 轮询间隔 | 30秒 | 固定值 |
| 任务查找时间 | <10ms | JobRegistry.get() |
| 任务启动时间 | <100ms | create_run() → execute() |
| 最大并发任务 | 无限制 | 取决于线程池 |

### 10.2 任务执行时长（典型值）

| 任务类型 | 平均时长 | P95时长 | 超时阈值 |
|---------|---------|---------|---------|
| fund_flow_update | 80s | 120s | 1800s |
| kline_update | 500s | 800s | 3600s |
| data_quality_check | 300s | 600s | 3600s |
| signal_generate | 1s | 2s | 300s |
| v13_daily_check | 5s | 10s | 600s |

---

## 11. 总结

### 11.1 重构成果

✅ **架构统一** - 消除双轨系统，单一JobRegistry路由  
✅ **代码精简** - 删除600行冗余handler方法  
✅ **问题修复** - 13个阻塞任务立即可用  
✅ **可维护性** - 新增任务只需创建Job类，无需修改scheduler.py  
✅ **向后兼容** - 保留legacy handler fallback机制  

### 11.2 关键设计原则

1. **职责分离**
   - `SchedulerService` - 负责调度、时间管理、执行历史
   - `JobRegistry` - 负责任务注册、查找、执行
   - `Job` - 负责具体任务实现

2. **渐进迁移**
   - 优先使用JobRegistry，找不到再fallback到legacy handler
   - 6个特殊命令暂时保留在legacy handler，后续逐个迁移

3. **测试友好**
   - Job是独立类，易于单元测试
   - JobRegistry支持mock替换
   - 执行历史完整记录在数据库

### 11.3 遗留工作

⚠️ **待迁移的Legacy Handlers（6个）**
- 需逐个创建对应的Job类并加入JobRegistry

⚠️ **Job超时机制未实施**
- 已定义 `timeout_seconds` 但未在执行时强制

⚠️ **任务依赖管理缺失**
- 无法定义"任务A成功后才执行任务B"

---

**文档维护：** 本文档应在每次scheduler架构变更后同步更新  
**相关文档：**
- [scheduler-audit-2026-09-01-v2.md](scheduler-audit-2026-09-01-v2.md) - 审计报告
- [ADR-002: Scheduler Ownership Split](../../adr/002-scheduler-ownership-split.md) - 架构决策
- [WP-15: V2 Scheduler Integration](../../superpowers/specs/WP-15-v2-scheduler-integration.md) - 工作包规格

---

**变更历史：**
- 2026-09-01: 初始版本，记录JobRegistry重构后的架构
