# REQ-eeb38c 实施计划 · 补齐双线执行看板 v2 任务业务线分类（11 个未归类）

- 需求：REQ-eeb38c（chore）
- 窗口：w-a1402b8c（角色 investor）
- 计划日期：2026-09-13

## 1. 现象

双线执行看板「分类对账」行报：`⚠️ 未归类 11 个：ingest_events_daily、ingest_events_policy、session-probe、equity_snapshot_daily、ingest_events_history、core_plan_generate 等（请补录名单或打标）`。

线上证据（`GET http://127.0.0.1:13080/dashboard/api/board`，2026-09-13 18:56 拉取）：

- `taskCoverage.total = 65`（v2 引擎 40 + Agent OS 25）
- `taskCoverage.unclassified` 恰好 11 个：`ingest_events_daily, ingest_events_policy, session-probe, equity_snapshot_daily, ingest_events_history, core_plan_generate, ingest_disclosure_calendar, minute_kline_sync, industry_chain_refresh, strategy_loop_weekly, data_hygiene_probe`
- `byLine = {engine:28, autonomy:12, account:12, other:13}`；`fieldTagged=25`（全部来自 OS 侧 `agent_line`），`fieldMissing=40`（全部是 v2 侧）

## 2. 根因

分类实现只有一处共享模块：`packages/pages/execution/src/shared/line-classify.ts`，优先级 = ①任务自带字段 → ②任务名名单 → ③other 并标记 unclassified。

- ① 对 v2 任务恒不命中：v2 接口（`GET :5001/api/scheduler/tasks`）不返回任何业务线字段；v2 侧的 `domain` 是六域（data/signal/trading/analysis/report/monitor），与"业务线"（引擎线/Autonomy/账户/其它）**正交**，只能当"是否已打标"的对账信号，不能当 line 用。
- ② 名单是 2026-09-12 按当时任务清单硬编码的过渡兜底 —— 新增或漏收的任务名必然落 other，并被对账显式标为"未归类"。11 个未归类全部属于这一类（其中 `equity_snapshot_daily` 只是因为名单里只有连字符版 `equity-snapshot-daily`）。

## 3. 归类口径（本计划要落地的决策）

原则：**能对齐孪生任务的，以孪生任务自带的 `agent_line` 字段为准**（字段优先于名单，与模块既定口径一致）；无孪生的按任务性质归数据地基/自我改进。

| # | 任务 | 现归类 | 拟归类 | 依据（数据来源见括注） |
|---|---|---|---|---|
| 1 | ingest_events_daily | other/未归类 | engine | 事件入库（持仓∪盯盘公告/财报/解禁/定增），RFC 015 §3.5 数据地基（v2 任务描述，:5001） |
| 2 | ingest_events_policy | other/未归类 | engine | 政策事件采集（每 4h），同上门类 |
| 3 | ingest_events_history | other/未归类 | engine | 研究宇宙事件增量回补（近 35 天公告） |
| 4 | ingest_disclosure_calendar | other/未归类 | engine | 全市场财报披露日历刷新（周度） |
| 5 | minute_kline_sync | other/未归类 | engine | 盘中分钟线增量同步（R-003 拆单/择时的数据源） |
| 6 | industry_chain_refresh | other/未归类 | engine | 产业链成员刷新（chain_scan / 决策原则#4 链式扫描的数据源） |
| 7 | equity_snapshot_daily | other/未归类 | engine | 与 OS 孪生 `equity-snapshot-daily`（agent_line=**profit_engine**，同为 15:35 净值稠密化）对齐 |
| 8 | core_plan_generate | other/未归类 | engine | v2 引擎侧 core 建仓计划生成（只出计划不下单，M2 core 策略生产）；与账户线 `agent-brain-core-plan`（09:10 唤醒 agent 消费计划）是"引擎产出→agent 消费"配对，配对另一半留在 account 正确 |
| 9 | strategy_loop_weekly | other/未归类 | engine | 与 OS 孪生 `strategy-loop-weekly`（agent_line=**profit_engine**）对齐，同一"策略闭环周度复核" |
| 10 | data_hygiene_probe | other/未归类 | autonomy | 与 OS 孪生 `data-hygiene-weekly`（agent_line=**autonomy**）对齐，同一 R-020 数据卫生巡检 |
| 11 | session-probe | other/未归类 | other（**已知其它**，不再告警） | Agent OS 托管的会话探针（已 disabled），属核验类；加入 known-other，与 `board-*`/`geer-*`/`v2_health_check` 同档 |

## 4. 任务拆分

| key | 标题 | phase | side | 依赖 | 验收 |
|---|---|---|---|---|---|
| t1 | 补录 11 个 v2 任务到业务线分类名单（含归类依据注释） | implement | backend | — | `lineOfName` 对 11 个名字分别返回 engine×9 / autonomy×1 / other×1；`classifyTask` 对 `session-probe` 返回 `{line:'other', source:'name', unclassified:false}`；名单新增项带归类依据注释 |
| t2 | 补分类回归测试锁定 11 个名字 | test | backend | t1 | `npx vitest run packages/pages/execution/tests/line-classify.test.ts` 全绿；新增用例覆盖 11 个名字与"未归类清零"断言，且既有 6 个用例不改语义 |
| t3 | 重建 client 产物并核验线上未归类清零 | merge | fullstack | t2 | `pnpm --filter @pi-investment/dashboard-execution build:client` 成功且 `lib/client.cjs` 可 grep 到新增名字；重启后重新拉取 `/dashboard/api/board`，`taskCoverage.unclassified = []`（线上证据）；看板页面刷新后对账行不再显示告警 |

## 5. 验证与留痕

- 单测：`agent-dh/packages/pages/execution/tests/line-classify.test.ts`
- 线上证据：`GET :13080/dashboard/api/board` 的 `taskCoverage.unclassified`（改前 11 个 → 改后 0 个）
- 留痕：decision_audit(record) + memory_write（README/计划文档路径、验收数值）；按 R-013 标注数据来源与时点

## 6. 边界与不做的事

- **不改 quantsys-v2**：本次只在 agent-dh 侧补录名单。源头打标（v2 `scheduler_tasks` 增业务线字段 + 接口暴露，让"字段优先"对 v2 也生效）作为后续独立需求。
- **不清理孪生任务**：顺带发现 v2 与 OS 侧存在同名功能对（equity_snapshot_daily ↔ equity-snapshot-daily、strategy_loop_weekly ↔ strategy-loop-weekly、data_hygiene_probe ↔ data-hygiene-weekly，v2 侧均为 enabled 且时刻相差 15 分钟），疑似重复调度。本次只对齐归类，不在本需求内动调度。
- **不动既有归类**：`daily-strategy-validation`/`v13-verification`（名单=autonomy）与 `strategy-loop-weekly`（孪生字段=profit_engine）之间既有口径不一致，属历史决策，本需求不改，仅在本计划中记录。

## 7. 风险

- 归类是"业务线展示口径"，不改变任何任务的实际执行；改动只影响看板分组与对账告警。
- 名单兜底是过渡方案：新任务仍可能落 other；本次以"未归类显式告警"为安全网（宁显不藏）。
