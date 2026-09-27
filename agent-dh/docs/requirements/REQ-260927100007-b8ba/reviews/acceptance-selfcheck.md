# REQ-260927100007-b8ba 验收自检（逐条 FR × 证据锚点）

> 本文件是**自检**：逐条 FR 给出「怎么算过 / 我跑的命令 / 看到的结果 / 结论」。
> 最终裁决仍是人工（看板「通过 / 退回返工」）——本文件不代替人点头。
>
> 口径：只认**可复核**的锚点（命令 + 输出摘要 / 文件路径 / 台账读数）。没有锚点的一律标"未验证"。

## 0. 交付边界（先说清楚，不藏在细节里）

| # | 边界 | 影响 | 处置 |
|---|---|---|---|
| B1 | FR-14 的 `GatePromptPort` 已实现并单测覆盖，但**未在生产组合根装配** | 现实运行时 Dive 仍不会主动弹框（行为与 FR-14 前逐字一致） | 任务卡明确允许该状态（"未装配端口→行为与改动前逐字一致"）；激活需在 src/index.ts 注入 `createGatePromptPort` 且给端口补 agent 解析（当前 `questions.ask` 不带 agent，idle 期路由语义未验证）。**未经人裁决不擅自打开**（否则会向人弹未经确认的框） |
| B2 | `tests/acceptance-criteria.test.ts` 的 schemaVersion 断言（7 vs 8）红 | 与本需求无关的既有红 | HEAD 的 `REQBOARD_SCHEMA_VERSION` 已是 8（本需求未动 schemaVersion），属另一工作线 |
| B3 | `acceptance-criteria.test.ts` 在默认 threads 池全红 | 环境性（该文件 beforeEach 调 `process.chdir()`，vitest 1.x worker 不支持） | `--pool=forks` 下仅剩 B2 一条 |
| B4 | `wiki_probe.py` 报现行页死链 30 条 | 全部为既有（README 指向不存在的 `packages/*/README.md` 等） | 本需求新增/修改页**零新增**死链/孤儿（见 tests/ 证据） |

## 1. 逐条自检

| FR | 怎么算过 | 证据锚点 | 结论 |
|---|---|---|---|
| FR-1 批准计划同步落库 | 批准动作内落库；失败不推进 + pausedReason | `tests/confirm-settle-plan-persist.test.ts` 绿；`src/application/internal/confirm-settle.ts`、`plan-landing.ts` | 过 |
| FR-2 静默停滞响亮化 | 无任务时写 comment + pausedReason + 告警 | 同上文件用例；`src/application/internal/failure-handling.ts` | 过 |
| FR-3 推进任务完整性守卫 | 计划有卡/台账 0 卡 → 拒 + 修复指引 | `tests/advance-task-completeness-guard.test.ts` 绿；`src/application/internal/task-completeness.ts` | 过 |
| FR-4 门禁失败提示可用 | 提示两条真能用的路径 | `tests/clause-coverage-gate.test.ts` 绿；`src/application/internal/content-gate-wiring.ts` | 过 |
| FR-5 decompose 返回体契约 | task_coverage 声明为 array 且取值一致 | `tests/tools-schema.test.ts` + `tests/contract-shapes.test.ts` 绿；`src/tools/DecomposeTool/DecomposeTool.ts` | 过 |
| FR-6 rtm-decomposing 随任务刷新 | task:status/report 刷新集合含它 | `packages/tools/reqboard/tests/rtm/triggers.test.ts` 14/14；`generator.ts filesForTrigger` | 过 |
| FR-7 补齐 agent 侧流转工具 | reqboard_move / reqboard_task_move 已注册 | `tests/apply-wiring.test.ts` 绿；build 产物 `dist/index.mjs` 内两名字可检索（各 25 / 22 处） | 过（**部署后**才在运行实例可见，见 §3） |
| FR-8 任务级收敛点 | 四处写入点全走 transitionTask；非法流转被拒且零副作用 | `tests/task-transition-guard.test.ts` 绿；`src/application/internal/task-transition.ts`；`ExecuteTask/AdvanceChain/failure-handling/http.routers.tasks` 均 import 它 | 过 |
| FR-9 挂起期停手守卫 | pending 时写路径被拒（REQBOARD_CONFIRM_PENDING），status/receipt 仍可用 | `tests/confirm-pending-guard.test.ts` 绿；`src/application/internal/support.ts assertNoPendingConfirm` | 过 |
| FR-10 status 返回体 lossless | 已绑定窗口调 reqboard_status 不再报 invalid output | `tests/status-lossless.test.ts` 绿；`src/application/internal/rtm-health.ts` 无记录时**省略** last_failure；修复前实机复现记录见 tests/ | 过 |
| FR-11 采集半不直投 | 同阶段连续两条人类消息 → 零投递；armed+active 才走 round 半 | `tests/dive-session-driver-wiring.test.ts`、`capture-hook.test.ts`、`isolate-node-context.test.ts` 绿（旧"阶段纪律投递"契约已改写为"零投递 + 留痕照旧"） | 过 |
| FR-12 RTM 窗口绑定投影 | bind 触发点刷新 lifecycle；消费者如实声明 | `triggers.test.ts` 14/14（新增 3 例）；`generator.ts`、`rtm/types.ts`、`rtm-yaml.ts`、`CaptureRequirement.ts` | 过（含**实证纠偏**：全仓无 resultRequirementId 生产写入方，故 bind 接在唯一真实绑定写入 reqboard_capture） |
| FR-13 文字证据确认同调用内推进 | evidence 确认后同一调用 brainstorming→design | `tests/confirm-evidence.test.ts` 绿；`src/application/use-cases/ConfirmArtifact.ts` | 过 |
| FR-14 Dive 人工门主动弹框 | 门已满足未推进 → 弹推进框；一次等待只弹 1 次；冷却 5min、上限 2、到顶留痕 | `tests/dive-gate-prompt.test.ts` 9/9；`src/application/dive/gate-prompt.ts` | 过（**未装配**，见 B1） |

## 2. 代码级复核（人读得到的结论）

- **任务状态只有一个改法**：`src/application/internal/task-transition.ts` 是任务侧唯一收敛点；业务路径上不再有绕过校验直接写 `task.status` 的地方（`ExecuteTask` / `AdvanceChain` / `failure-handling` / `http/routers/tasks` 四处已改由它流转）。
- **落章与推进同一原子**：需求级 `confirm-settle`、任务级 `MoveTask/MoveRequirement` 都在同一次调用内完成"校验 + 状态 + 事件"；失败即回滚（`mutate` 语义），不留半迁移态。
- **进会话只有一个合法通道**：round 半的 `createRoundMessage`（`source.kind='dive'`，走预留→投递→准入计数）。采集半已零投递；白名单只剩"人点头后的收尾/交接/唤醒"（pending-confirm wake / 闸门链 H4 / 失败告警 / FR-14 弹框降级）。
- **响亮化**：本需求涉及的三处"原本静默"的地方（批准不落库、任务侧空、弹框到顶）现在都写台账 comment / 返回结构化拒绝，不再沉默。

## 3. 部署与运行态

- 已执行 `pnpm build`（退出码 0，host + client 双产物），`dist/index.mjs` 内已含 `reqboard_task_move` / `reqboard_move` 与 FR-10 的条件展开修法。
- **注意**：运行中的 :13080 实例需要一次重启才会加载新产物；重启前调用 `reqboard_status` 仍会报 FR-10 的旧错误——这是"改了源码 ≠ 已生效"的本仓既有语义（见 agent-dh/CLAUDE.md），不是修复未生效。

## 4. 未过项 / 待人工裁决项

1. B1（FR-14 未装配）：是否需要在本需求内激活，还是作为后续小单——请裁决。
2. 本需求 16 张任务卡均已 done 并留汇报；需求已自动滚入验收（台账留痕 `[自动推进] implementing → accepting`）。
