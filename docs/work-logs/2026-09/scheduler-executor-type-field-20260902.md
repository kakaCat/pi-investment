# 定时任务表新增 executor_type（执行主体）字段 — 2026-09-02

**作者**：PI 投资顾问·投资脑 (investor, w-8366e526)
**类型**：DB 结构变更记录（无代码改动，Go/Python 均显式列读写，加列不影响现有代码）

## 背景与需求

排查 v2 与 Agent OS 两套定时任务体系时，需要**区分"纯后端自动执行的任务"与"交给 AI agent 处理的任务"**，故在任务表上增加一个字段记录任务的执行主体。用户确认：

- 字段语义：**枚举 `executor_type`**（`system` / `agent` / `both`），非布尔
- 添加范围：v2 与 OS 两侧的定时任务表都加

## 排查过程中的关键事实（决定了加在哪张表）

1. **v2 侧任务表**：`quant_investment.quant.scheduler_tasks`（21 行，全部 cron、全部启用）——由 v2 后端进程内 JobRegistry / legacy handler 执行，**不经过 agent**。
2. **Agent OS 8080 实际使用的任务表不是 `agent_os` 库！** 排查发现：
   - `agent-os/config.yaml` 明确 `database.dbname: quant_investment`（而 `getDefaultConfig()` 里写的是 `agent_os`，存在配置矛盾，实际生效以 config.yaml 为准）。
   - 8080 进程（PID 3179）的 PostgreSQL 连接确实指向 quant_investment 库。
   - API `GET /api/v1/scheduler/tasks` 返回的 13 个任务（owner=investor/agent-dh、`payload.executor=dsh-native`）与 **`quant_investment.public.tasks` 完全一致**。
   - `agent_os` 库 `public.tasks` 只有 9 行 owner=fin-agent 的旧遗留任务，近 7 天 **0 次运行**（task_runs 为 0），是死表。
3. **结论**：三张任务表均为同库或遗留表，用户确认三张都加：
   - `quant.scheduler_tasks`（v2，21 行）→ 全 `system`
   - `quant_investment.public.tasks`（Agent OS 8080 在用，13 行）→ 全 `agent`（dsh-native = 唤起 agent）
   - `agent_os.public.tasks`（旧遗留 fin-agent，9 行）→ 全 `agent`

## 执行内容

对三张表分别执行（幂等）：

```sql
ALTER TABLE <表> ADD COLUMN IF NOT EXISTS executor_type VARCHAR(20) DEFAULT 'system' NOT NULL;
ALTER TABLE <表> ADD CONSTRAINT <表>_executor_type_check CHECK (executor_type IN ('system','agent','both'));
COMMENT ON COLUMN <表>.executor_type IS '执行主体: system=后端自动执行, agent=交给AI agent处理, both=系统与agent协同';
```

回填逻辑：

| 表 | 回填值 | 依据 |
|---|---|---|
| quant.scheduler_tasks (21) | system | v2 后端进程内执行，不唤起 agent |
| quant_investment.public.tasks (13) | agent | owner=investor/agent-dh，payload.executor=dsh-native |
| agent_os.public.tasks (9) | agent | owner=fin-agent 的 AI 任务 |

注意：`ADD COLUMN ... DEFAULT 'system' NOT NULL` 会立即填默认值，因此**先加列再按 `owner`/语义 UPDATE 回填**（不能用 `WHERE executor_type IS NULL` 判断——该条件永远为假）。

## 验证结果

- 三表均新增 `executor_type VARCHAR(20) NOT NULL DEFAULT 'system'` + CHECK 约束（值域 system/agent/both）
- 回填分布：quant.scheduler_tasks = system×21；quant.public.tasks = agent×13；agent_os.tasks = agent×9
- Agent OS API `GET /api/v1/scheduler/tasks` → HTTP 200（13 个任务正常返回）
- quantsys-v2 5001 健康检查 → HTTP 200
- 代码侧无改动：v2 `SchedulerTaskConfig` ORM（显式列）与 agent-os Go `task_repository.go`（显式列 INSERT/SELECT/UPDATE）均不依赖通配列，加列不影响读写。

## 迁移脚本

幂等 SQL 存档：`quantsys-v2/migrations/add_executor_type_to_task_tables.sql`
（含回滚脚本注释；agent_os 库部分因跨库连接需单独执行，脚本内以注释形式给出。）

## 后续可选

- 若希望把 `executor_type` 暴露到 API/前端（如 v2 `GET /scheduler/tasks` 响应、Agent OS GET tasks），需在 ORM 模型 / Go `types.Task` 结构体补字段——本次未做（用户 scope 仅表层面）。
- `agent_os` 库 `public.tasks` 属死表，若确认无进程使用可后续评估清理或迁移至 quant_investment.public.tasks 统一管理。
