# 拆分计划（REQ-260927121324-abde）

> 目标：把 dsh-pmboard 的**三条 token 写路径**（需求状态迁移 / 任务执行开工-完工 / 任务完成后的派生推进）
> 全部收口到各自唯一收敛点并按写时快照落账，缺失（undefined）与取不到（unavailable）在读路径一律
> 计入 degraded=true；既有 token 单测由 3 failed 转 0 failed，并加两道源码扫描守卫防回归。
> 做法：先立执行快照助手契约（t1）与读路径判定（t6），再收口三条写路径（t2~t5），
> 最后补结构守卫与行为回归（t7/t8）、兼容验证（t9）、文档（t10）。共 10 张卡，无 schema 迁移、无历史回填。

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点表 | 需求条款（FR-1…FR-9） |
| R1/R2/R3 | requirement.md 根因 | 三类缺陷（执行漏快照 / 迁移漏传+绕过 / 读路径漏报） |
| t-x | 本文档任务表 | 计划任务键（批准后落库为台账任务卡） |
| T-x | design/test-cases.md | 测试用例（T-1…T-20） |

## 改动盘点（对照设计逐份）

**新增测试文件**

| 文件 | 作用 | 关联 |
|---|---|---|
| tests/execution-token-guard.test.ts | 源码扫描：tokenUsage 写点 / executions.push 只准在助手内 | FR-8 |
| tests/requirement-transition-guard.test.ts | 源码扫描：src 内无 req.status 直接赋值 | FR-8 |
| tests/task-move-snapshot.test.ts / rollup-snapshot.test.ts / accept-verdicts-snapshot.test.ts | 看板 / 自动链 / 裁决三条新路径的行为用例 | FR-3/5/6 |

**修改源文件（12 个，全部 host 侧，客户端不动）**

| 文件 | 动作 | 关联 |
|---|---|---|
| src/application/internal/token-usage.ts | 新增 6 个导出（执行助手 + 窗口码/提供者解析）；执行快照唯一写入口 | FR-4/5/6/8 |
| src/application/internal/confirm-settle.ts | :278/:304 两分支补 snap | FR-2 |
| src/application/use-cases/HandleFailure.ts | :87/:109 直接赋值改经收敛点 | FR-1 |
| src/http/routers/requirements.ts | :111 改经收敛点；:270 补 snap+sessionId | FR-1/2 |
| src/http/routers/verdicts.ts | :106 改经收敛点；:170 补第 8 实参 snap | FR-1/3 |
| src/application/use-cases/MoveTask.ts | 执行记录改经助手；:127 rollup 带快照 | FR-4/5/6 |
| src/http/routers/tasks.ts | 执行记录改经助手；create/update 读可选 sessionId；rollup 带快照 | FR-4/5/6 |
| src/application/use-cases/AdvanceChain.ts | 父卡开工/收尾改经助手；:205 rollup 带快照 | FR-4/5/6 |
| src/application/use-cases/ExecuteTask.ts | 子卡执行开工/收尾改经助手 | FR-4/5 |
| src/application/use-cases/ReportTask.ts | :136 改 refreshRunningExecution | FR-5 |
| src/wiring/pm-capture-root.ts | :133 接手推进传快照提供者 | FR-6 |
| src/application/query/QueryRequirementToken.ts | hasUnavailableSnapshot → hasSnapshotGap | FR-7 |

**同步文档**：docs/architecture/project-manual.md、需求 RTM、docs/work-logs/。
**删除**：无。**schema**：REQBOARD_SCHEMA_VERSION 保持 8，无迁移脚本、无回填。

## 任务表

| 计划 key | 标题 | 阶段 | 端侧 | 依赖 |
|---|---|---|---|---|
| t1 | 新增执行快照收敛助手（任务执行唯一写入口） | implement | backend | — |
| t2 | 需求迁移写路径统一经收敛点并带写时快照 | implement | backend | — |
| t3 | agent 任务执行与中途汇报改经执行助手 | implement | backend | t1 |
| t4 | 看板任务流转/建卡改卡带写时快照 | implement | backend | t1 |
| t5 | 自动链任务执行与接手推进改经执行助手并带快照 | implement | backend | t1 |
| t6 | 读路径把快照缺失与不可得同等计入 degraded | implement | backend | — |
| t7 | 新增执行与迁移收敛的结构守卫单测 | test | backend | t1, t2, t3, t4, t5 |
| t8 | 补看板/自动链/读路径行为用例并锁死四条验收命令 | test | backend | t1, t2, t3, t4, t5, t6 |
| t9 | 迁移与兼容验证（无 schema 变更 / 旧台账可载入 / 回滚路径） | test | backend | t1, t2, t3, t4, t5, t6 |
| t10 | 同步说明书与 RTM（写路径收敛与验收命令） | doc | doc | t8 |

> 完整 implementation / acceptance 随 reqboard_submit(kind=plan) 的 tasks 一并提交，落库时逐字写入任务卡。

## 覆盖对照

| 需求条款 | 设计落点（design） | 落点（文件/模块） | 测试用例（test-cases） | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-1 | 架构 §写路径收敛点 / interfaces §需求迁移收敛点 | src/application/internal/token-usage.ts(transitionRequirement) + requirements.ts:111 | TC-9/T-19 | t2 | ✅ |
| FR-2 | backend §逐文件改动（需求迁移） | src/application/internal/confirm-settle.ts:278/:304 + requirements.ts:270 | T-12 | t2 | ✅ |
| FR-3 | backend §逐文件改动（需求迁移） | src/http/routers/verdicts.ts:106/:170 + internal/verdicts.ts | T-10/T-11 | t2 | ✅ |
| FR-4 | 架构 §写路径收敛点 2 / interfaces §执行快照助手 | src/application/internal/token-usage.ts(openExecution) 四处产生点 | T-1/T-5 | t1, t3, t4, t5 | ✅ |
| FR-5 | 架构 §写路径收敛点 2 / data-model §② | token-usage.ts(closeExecutions/refresh) + MoveTask/ReportTask/tasks/AdvanceChain/ExecuteTask | T-2/T-3/T-5 | t1, t3, t4, t5, t8 | ✅ |
| FR-6 | 架构 §写路径收敛点 3 / backend §自动链与无会话路径 | rollup.ts + MoveTask:127/tasks:66,110,157/AdvanceChain:205/pm-capture-root:133 | T-13/T-14 | t1, t3, t4, t5 | ✅ |
| FR-7 | data-model §读路径判定 degraded / backend §读路径降级实现 | src/application/query/QueryRequirementToken.ts:33-46,100 | T-15/T-16/T-17 | t6, t8, t9 | ✅ |
| FR-8 | backend §结构性守卫 | tests/execution-token-guard.test.ts + tests/requirement-transition-guard.test.ts | T-18/T-19 | t1, t7 | ✅ |
| FR-9 | test-cases §验收命令 | 新增行为用例 + 四条验收命令全绿 | T-20/汇总 | t8, t10 | ✅ |

**规则**：每行三格不许空；FR-1…FR-9 全部有接收任务（9/9）；反向 R1→FR-4/5/8、R2→FR-1/2/3、R3→FR-7 亦被认领。

## 依赖次序（DAG）

~~~
t1(执行快照助手契约) ─┬─> t3(agent 执行)
                      ├─> t4(看板执行)
                      └─> t5(自动链/接手推进)
t2(需求迁移收敛)
t6(读路径 degraded)
t1..t5 ──> t7(结构守卫单测)
t1..t6 ──> t8(行为回归 + 四条验收命令) ──> t10(文档)
t1..t6 ──> t9(迁移与兼容)
~~~

次序纪律：depends_on 只引用**前面已定义**的 key（无前向引用）；契约卡 t1 先行，实现卡 depends_on 它。

## 边界与不做（承 requirement.md）

1. 不回填历史数据、不改 schemaVersion（保持 8）；旧需求继续如实显示「无快照」。
2. 不改 token 统计口径（仍为同会话累计值差值近似归因）。
3. 不动 DSH 侧 SessionProbeAdapter.tokenTotals 与端侧 Token tab 视觉。
4. 不修 Dive armed 自动驱动机制本身；只保证写路径不漏账。
5. 无会话上下文的路径（启动对账、纯 system）诚实不传快照，禁止用 0 或单端累计冒充。
