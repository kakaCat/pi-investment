# 拆分计划（REQ-260927100007-b8ba）

> 目标：修掉拆分→实施链路上的 13 个缺陷（D1–D13），让「批准即落库、推进有守卫、状态有收敛点、Dive 与设计一致」。
> 做法：16 张卡，先立契约与收敛点（t1/t2），再补行为（t3–t13），最后做 Dive 弹框与文档（t14–t16）。

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点表 | 需求条款（FR-1…FR-14） |
| I-x | design/interfaces.md | 接口（I-1…I-10） |
| TC-x | design/test-cases.md | 测试用例（TC-1…TC-15） |
| D-x | 流程图文档缺陷索引 | 实测缺陷（D1…D13） |
| t-x | 本文档任务表 | 任务 |

## 任务表

| 计划 key | 任务 id | 标题 | 覆盖条款 | 落点（编号+文件） | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| t1 | （落库后回填） | 抽任务级收敛点并统一四处写入点 | FR-8 | `—` | implement | backend | — | M | npx vitest run tests/task-transition-guard.test.ts 通过 |
| t2 | （落库后回填） | 补 agent 侧需求/任务流转工具 | FR-7 | `—` | implement | backend | t1 | M | tests/apply-wiring.test.ts 里工具期望集合 = 实际 17 个（含 move/task_move/clear_pause/run_status）且通过 |
| t3 | （落库后回填） | 补齐 MoveTask 契约（现有测试即契约） | FR-7 | `—` | implement | backend | t2 | M | cd packages/web/dsh-pmboard && npx vitest run tests/execute-task.test.ts tests/lazy-expand.test.ts tests/concurrency-limits.test.ts tests/application/use-cases.test.ts 全绿（当前 40 passed / 28 failed）。 |
| t4 | （落库后回填） | 批准计划即同步落库并响亮化失败 | FR-1、FR-2 | `—` | implement | backend | t1 | L | npx vitest run tests/confirm-settle-plan-persist.test.ts 通过：同一调用返回时台账任务数=计划卡数 |
| t5 | （落库后回填） | 阶段推进加任务完整性守卫 | FR-3 | `—` | implement | backend | t2 | S | npx vitest run tests/advance-task-completeness-guard.test.ts 通过：计划 14 张/台账 0 张 → 拒绝且错误含修复指引 |
| t6 | （落库后回填） | 修正条款门禁失败提示与计划提交提示 | FR-4 | `—` | implement | backend | — | S | npx vitest run tests/clause-coverage-gate.test.ts 通过，且断言 how 含上述两条路径关键词。 |
| t7 | （落库后回填） | 修 reqboard_decompose 返回体契约 | FR-5 | `—` | implement | backend | — | S | npx vitest run tests/tools-schema.test.ts tests/decompose-tools.test.ts 通过 |
| t8 | （落库后回填） | RTM 刷新集合补 rtm-decomposing | FR-6 | `—` | implement | backend | — | S | npx vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts 通过 |
| t9 | （落库后回填） | 确认门挂起期间的停手守卫 | FR-9 | `—` | implement | backend | t2 | M | npx vitest run tests/confirm-pending-guard.test.ts 通过：pending 存在时 reqboard_submit 被拒且不写盘 |
| t10 | （落库后回填） | 修 reqboard_status 返回体 lossless | FR-10 | `—` | implement | backend | — | S | npx vitest run tests/status-lossless.test.ts 通过 |
| t11 | （落库后回填） | Dive 采集半停止直投 + 投递白名单 | FR-11 | `—` | implement | backend | — | M | npx vitest run tests/dive-manager-alignment.test.ts tests/dive-round-driver.test.ts 通过：同阶段连续两条人类消息 → onStagePrompt 0 次、不产生额外轮次 |
| t12 | （落库后回填） | RTM 窗口绑定投影可更新且有消费者 | FR-12 | `—` | implement | backend | t8 | M | npx vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts 通过：先建后绑 → source_session 随之更新 |
| t13 | （落库后回填） | 证据路径确认后同调用内推进（已实现，补回归） | FR-13 | `—` | test | backend | — | S | npx vitest run tests/confirm-evidence.test.ts 8/8 通过（含 advanced=true 与 kind 不匹配不推进两条）。 |
| t14 | （落库后回填） | Dive 在人工门主动弹框（有边界重弹） | FR-14 | `—` | implement | backend | t11 | L | npx vitest run tests/dive-gate-prompt.test.ts 通过：门已满足未推进时弹出推进确认框 |
| t15 | （落库后回填） | 修 apply-wiring 装配 stub 与期望集合 | FR-7 | `—` | test | backend | t2 | S | npx vitest run tests/apply-wiring.test.ts 4/4 通过（当前因 Service 装配抛错 4/4 红）。 |
| t16 | （落库后回填） | 同步文档：流程图 / 白名单 / 手册 | FR-11、FR-12 | `—` | doc | doc | t11, t12 | S | python3 agent-dh/scripts/wiki_probe.py 无新增死链/孤儿 |

## 覆盖对照

| 需求条款 | 接口（interfaces） | 落点（文件/模块） | 测试用例（test-cases） | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-1 | I-1 | application/internal/confirm-settle.ts | TC-1 | t4 | ✅ |
| FR-2 | I-5 | confirm-settle.ts / adapters/FailureAlert.ts | TC-2 | t4 | ✅ |
| FR-3 | I-5 | application/internal/task-completeness.ts | TC-3 | t5 | ✅ |
| FR-4 | — | application/internal/content-gate-wiring.ts | TC-4 | t6 | ✅ |
| FR-5 | I-4 | tools/DecomposeTool/DecomposeTool.ts | TC-5 | t7 | ✅ |
| FR-6 | I-6 | packages/tools/reqboard/src/rtm/generator.ts | TC-7 | t8 | ✅ |
| FR-7 | I-2, I-3 | application/use-cases/MoveTask.ts / MoveRequirement.ts + tools/ | TC-8 | t2, t3, t15 | ✅ |
| FR-8 | I-1 | application/internal/task-transition.ts | TC-9, TC-10 | t1 | ✅ |
| FR-9 | I-8 | 写路径工具入口（support.ts） | TC-11 | t9 | ✅ |
| FR-10 | I-9 | application/internal/rtm-health.ts | TC-6 | t10 | ✅ |
| FR-11 | I-10 | application/dive/session-driver.ts | TC-12 | t11 | ✅ |
| FR-12 | I-6 | rtm/lifecycle-generator.ts + generator.ts | TC-13 | t12 | ✅ |
| FR-13 | I-7 | application/use-cases/ConfirmArtifact.ts | TC-14 | t13 | ✅ |
| FR-14 | I-10 | application/dive/session-driver.ts + ports.ts | TC-15 | t14 | ✅ |
| **合计** | 10 接口 | 12 模块 | 15 用例 | 16 任务 | 14/14 条款有主 |

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|---|---|---|---|---|
| FR-8 | t1 | （落库后回填） | 抽任务级收敛点并统一四处写入点 | todo |
| FR-7 | t2 | （落库后回填） | 补 agent 侧需求/任务流转工具 | todo |
| FR-7 | t3 | （落库后回填） | 补齐 MoveTask 契约（现有测试即契约） | todo |
| FR-1 | t4 | （落库后回填） | 批准计划即同步落库并响亮化失败 | todo |
| FR-2 | t4 | （落库后回填） | 批准计划即同步落库并响亮化失败 | todo |
| FR-3 | t5 | （落库后回填） | 阶段推进加任务完整性守卫 | todo |
| FR-4 | t6 | （落库后回填） | 修正条款门禁失败提示与计划提交提示 | todo |
| FR-5 | t7 | （落库后回填） | 修 reqboard_decompose 返回体契约 | todo |
| FR-6 | t8 | （落库后回填） | RTM 刷新集合补 rtm-decomposing | todo |
| FR-9 | t9 | （落库后回填） | 确认门挂起期间的停手守卫 | todo |
| FR-10 | t10 | （落库后回填） | 修 reqboard_status 返回体 lossless | todo |
| FR-11 | t11 | （落库后回填） | Dive 采集半停止直投 + 投递白名单 | todo |
| FR-12 | t12 | （落库后回填） | RTM 窗口绑定投影可更新且有消费者 | todo |
| FR-13 | t13 | （落库后回填） | 证据路径确认后同调用内推进（已实现，补回归） | todo |
| FR-14 | t14 | （落库后回填） | Dive 在人工门主动弹框（有边界重弹） | todo |
| FR-7 | t15 | （落库后回填） | 修 apply-wiring 装配 stub 与期望集合 | todo |
| FR-11 | t16 | （落库后回填） | 同步文档：流程图 / 白名单 / 手册 | todo |
| FR-12 | t16 | （落库后回填） | 同步文档：流程图 / 白名单 / 手册 | todo |

## 覆盖完整性规则

1. 每行三格不许空；本计划所有 FR 均有接收任务（14/14）。
2. 反向：设计编号 I-1…I-10 / TC-1…TC-15 均在覆盖对照里被认领。
3. 依赖按 t1 → t2 → t3/t15、t8 → t12、t11 → t14 的次序落库。
