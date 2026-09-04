# 定时任务双体系打标：OS 线别 + v2 领域模型（2026-09-02）

> 决策人：用户（PI 投资顾问窗口 w-8366e526 执行）｜分支：agent-self/20260902-110540
> 需求：定时任务分两类体系——盈利引擎系统设计（profit_engine 线）与自主能力体系（Autonomy 线）留在 OS；业务任务归 v2 并按领域模型打标签；表加字段区别类型；OS 里属 v2 的业务任务迁到 v2 后从 OS 删除。

## 一、架构依据

- **Agent OS（:8080）**：agent 智能任务承载（dsh-native，14→13 个）。按两条 agent 线打标：
  - **盈利引擎系统设计线（profit_engine）**：M 线业务流水线的 agent 例行（盘前/盘中/盘后/M4 熔断/M0 数据质量/事件日历/止盈提醒）
  - **自主能力体系（Autonomy 线）**：L 线自进化闭环（蒸馏→变异→裁决→元学习）+ 学习飞轮周报
- **quantsys-v2（:5001）**：业务 job 承载（APScheduler，30 个 enabled），按领域模型六域打标：`data/signal/trading/analysis/report/monitor`（registry_setup.py 六组 Job 域）。
- 两线唯一接口 = genome；时间隔离：交易时段仅引擎线运转，Autonomy 全在盘后/周末。

## 二、Schema 变更（纯 DB 层，零代码影响）

### 1. `public.tasks`（agent-os）加列 + 回填
```sql
ALTER TABLE public.tasks ADD COLUMN agent_line VARCHAR(32) NOT NULL DEFAULT 'profit_engine';
COMMENT ON COLUMN public.tasks.agent_line IS 'Agent 任务线别: profit_engine=盈利引擎系统设计线 / autonomy=自主能力体系(Autonomy)线';
```
回填 autonomy 5 个：evolution-distill-daily、evolution-weekly-variant、evolution-gate-adjudicate、meta-learning-weekly、weekly-report-m6；其余 8 个默认 profit_engine。

### 2. `quant.scheduler_tasks`（v2）加列 + 回填
```sql
ALTER TABLE quant.scheduler_tasks ADD COLUMN domain VARCHAR(32);
COMMENT ON COLUMN quant.scheduler_tasks.domain IS '领域模型分组: data/signal/trading/analysis/report/monitor';
```
按 command 归属六域模块回填 30 个 enabled 任务，映射无遗漏（0 NULL）。分布：analysis 9 / trading 6 / signal 5 / data 4 / monitor 3 / report 3。

> 安全前提（此前审计确认）：agent-os TaskRepository 与 v2 SQLAlchemy model 均为**显式列读写**，无 `SELECT *` → 加列对运行零影响（实测 agent-os :8080 与 v2 :5001 均 HTTP 200）。

## 三、任务迁移 / 去重裁决（用户授权按规则判定）

| OS 任务 | 判定 | 依据 |
|---|---|---|
| **daily-trade-verify**（16:00 对账） | **删除（已迁 v2）** | v2 已有 307 daily_trade_verify（trade_verify_daily，15:35 交易日自动对账，M5-2 RFC 005 原生承载）；且 post-market-routine-live（15:30）步骤1 已做 trade_verify+飞书告警 → OS 版为三重叠冗余，删后无功能损失 |
| **data-quality-monitor-daily**（16:05） | **保留（profit_engine）** | v2 232 data_quality_check（16:00）只检查回填、**无飞书告警能力**；OS 版 tsx 脚本承载 M0 数据质量主动告警 → 删则丢告警，保留 |

删除方式：agent-os API `DELETE /api/v1/scheduler/tasks/{id}`（非 DB 直删，确保 cronEntries map 同步清理）。删除后 API 列表 13 个，`daily-trade-verify` 不在注册表，DB 与 API 一致。

## 四、执行后状态

### OS 13 个任务
- **autonomy（5）**：evolution-distill-daily、evolution-weekly-variant、evolution-gate-adjudicate、meta-learning-weekly、weekly-report-m6
- **profit_engine（8）**：pre-market-routine、afternoon-open-check-live、post-market-routine-live、data-quality-monitor-daily、m4-circuit-breaker-live、event-calendar-check、geer-take-profit-0901、signal-perf-verify-0903
- 备注：geer-take-profit-0901（歌尔 002241 止盈提醒）与 signal-perf-verify-0903（9/3 一次性）为临时任务，完成后 disable；保留期间 agent_line=profit_engine 不变。

### v2 30 个 enabled 任务（domain 全部回填）
data（4）：232 数据质量检查 / 233 每日数据更新 / 240 每日流水线 / 241 每周全量重建
signal（5）：236 信号生成 / 242 信号执行 / 251 实时信号监控 / 308 资金流更新 / 311 信号表现回填
trading（6）：249/268/269/270 v13-v14 系列 / 258 池刷新 / 307 交易对账
analysis（9）：250/252/253/261/262/263/265/266/312
report（3）：237 周报 / 238 财务数据更新 / 271 v13 周报
monitor（3）：235 风险检查 / 264 权益快照 / 301 市场感知快照

## 五、验证结果

- 双服务健康：agent-os :8080 HTTP 200、v2 :5001 HTTP 200
- OS agent_line 分布：autonomy 5 + profit_engine 9→8（删 1 后）
- v2 domain 分布：6 域齐全、0 NULL、0 未匹配
- 备份：`/tmp/scheduler_line_20260902/pre_alter_backup.sql`（457 行，public.tasks + quant.scheduler_tasks 全量）

## 六、后续可选增强（本次未做）

- 纯 DB 层方案下，agent-os Go 模型 / v2 SchedulerTaskConfig ORM model 尚未包含新列 → **scheduler_manage 工具与管理 API 暂不显示 agent_line/domain**。如需 API 可见：v2 侧在 ORM model + serializer 补 domain（需重启 v2）；agent-os 侧改 Go struct + handler（需重启 OS）。列为后续迭代。
