# REQ-260927100007-b8ba 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：拆分→实施这一段不再"批了 14 张卡、台账 0 张卡、零告警"：批准计划在同一次调用内同步落库，落库失败不推进并留 pausedReason + 告警；「计划有卡、台账 0 卡」推进到实施被代码级拒绝并给可执行修复指引；decompose 返回体契约修正（task_coverage 数组）；任务状态变化同步刷新实施覆盖度；agent 侧补齐 reqboard_move / reqboard_task_move 与任务级收敛点（非法流转被拒且零副作用）；reqboard_status 返回体 lossless；确认门挂起期间同窗口写路径代码级拒绝；Dive 采集半不再直投会话（投递白名单），人工门兜底改为「Dive 主动弹框」的有界实现；文档（节点流程图/白名单/项目说明书）同步。16 张任务卡全部完工并留汇报，需求已自动滚入验收。

## 1. 验收列表

### v1-1 · 抽任务级收敛点并统一四处写入点

**验收内容**：【抽任务级收敛点并统一四处写入点】验收：npx vitest run tests/task-transition-guard.test.ts 通过；grep -rn "status = " src/application/use-cases src/application/internal 在业务路径零命中（收敛点与迁移除外）。

**操作步骤**：
1. npx vitest run tests/task-transition-guard.test.ts 通过
2. grep -rn "status = " src/application/use-cases src/application/internal 在业务路径零命中（收敛点与迁移除外）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/task-transition-guard.test.ts 通过；grep -rn "status = " src/application/use-cases src/application/internal 在业务路径零命中（收敛点与迁移除外）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 补 agent 侧需求/任务流转工具

**验收内容**：【补 agent 侧需求/任务流转工具】验收：tests/apply-wiring.test.ts 里工具期望集合 = 实际 17 个（含 move/task_move/clear_pause/run_status）且通过；agent 调 reqboard_task_move 能把 todo 卡推到 in_progress。

**操作步骤**：
1. tests/apply-wiring.test.ts 里工具期望集合 = 实际 17 个（含 move/task_move/clear_pause/run_status）且通过
2. agent 调 reqboard_task_move 能把 todo 卡推到 in_progress。

**预期结果**：按上述步骤执行后满足验收标准：tests/apply-wiring.test.ts 里工具期望集合 = 实际 17 个（含 move/task_move/clear_pause/run_status）且通过；agent 调 reqboard_task_move 能把 todo 卡推到 in_progress。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 补齐 MoveTask 契约（现有测试即契约）

**验收内容**：【补齐 MoveTask 契约（现有测试即契约）】验收：cd packages/web/dsh-pmboard && npx vitest run tests/execute-task.test.ts tests/lazy-expand.test.ts tests/concurrency-limits.test.ts tests/application/use-cases.test.ts 全绿（当前 40 passed / 28 failed）。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/execute-task.test.ts tests/lazy-expand.test.ts tests/concurrency-limits.test.ts tests/application/use-cases.test.ts 全绿（当前 40 passed / 28 failed）。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/execute-task.test.ts tests/lazy-expand.test.ts tests/concurrency-limits.test.ts tests/application/use-cases.test.ts 全绿（当前 40 passed / 28 failed）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 批准计划即同步落库并响亮化失败

**验收内容**：【批准计划即同步落库并响亮化失败】验收：npx vitest run tests/confirm-settle-plan-persist.test.ts 通过：同一调用返回时台账任务数=计划卡数；注入落库失败时状态仍 decomposing 且 pausedReason/评论/告警齐备。

**操作步骤**：
1. npx vitest run tests/confirm-settle-plan-persist.test.ts 通过：同一调用返回时台账任务数=计划卡数
2. 注入落库失败时状态仍 decomposing 且 pausedReason/评论/告警齐备。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/confirm-settle-plan-persist.test.ts 通过：同一调用返回时台账任务数=计划卡数；注入落库失败时状态仍 decomposing 且 pausedReason/评论/告警齐备。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 阶段推进加任务完整性守卫

**验收内容**：【阶段推进加任务完整性守卫】验收：npx vitest run tests/advance-task-completeness-guard.test.ts 通过：计划 14 张/台账 0 张 → 拒绝且错误含修复指引；空计划放行。

**操作步骤**：
1. npx vitest run tests/advance-task-completeness-guard.test.ts 通过：计划 14 张/台账 0 张 → 拒绝且错误含修复指引
2. 空计划放行。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/advance-task-completeness-guard.test.ts 通过：计划 14 张/台账 0 张 → 拒绝且错误含修复指引；空计划放行。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 修正条款门禁失败提示与计划提交提示

**验收内容**：【修正条款门禁失败提示与计划提交提示】验收：npx vitest run tests/clause-coverage-gate.test.ts 通过，且断言 how 含上述两条路径关键词。

**操作步骤**：
1. npx vitest run tests/clause-coverage-gate.test.ts 通过，且断言 how 含上述两条路径关键词。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/clause-coverage-gate.test.ts 通过，且断言 how 含上述两条路径关键词。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 修 reqboard_decompose 返回体契约

**验收内容**：【修 reqboard_decompose 返回体契约】验收：npx vitest run tests/tools-schema.test.ts tests/decompose-tools.test.ts 通过；成功返回不再出现 returned invalid output。

**操作步骤**：
1. npx vitest run tests/tools-schema.test.ts tests/decompose-tools.test.ts 通过
2. 成功返回不再出现 returned invalid output。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/tools-schema.test.ts tests/decompose-tools.test.ts 通过；成功返回不再出现 returned invalid output。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · RTM 刷新集合补 rtm-decomposing

**验收内容**：【RTM 刷新集合补 rtm-decomposing】验收：npx vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts 通过；filesForTrigger("task:status") 含 rtm-decomposing.yml 且覆盖度随任务变化。

**操作步骤**：
1. npx vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts 通过
2. filesForTrigger("task:status") 含 rtm-decomposing.yml 且覆盖度随任务变化。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts 通过；filesForTrigger("task:status") 含 rtm-decomposing.yml 且覆盖度随任务变化。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-9 · 确认门挂起期间的停手守卫

**验收内容**：【确认门挂起期间的停手守卫】验收：npx vitest run tests/confirm-pending-guard.test.ts 通过：pending 存在时 reqboard_submit 被拒且不写盘；status/confirm_receipt 仍可用。

**操作步骤**：
1. npx vitest run tests/confirm-pending-guard.test.ts 通过：pending 存在时 reqboard_submit 被拒且不写盘
2. status/confirm_receipt 仍可用。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/confirm-pending-guard.test.ts 通过：pending 存在时 reqboard_submit 被拒且不写盘；status/confirm_receipt 仍可用。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-10 · 修 reqboard_status 返回体 lossless

**验收内容**：【修 reqboard_status 返回体 lossless】验收：npx vitest run tests/status-lossless.test.ts 通过；已绑定窗口调用 reqboard_status 返回 success（修复前必然 not lossless JSON）。

**操作步骤**：
1. npx vitest run tests/status-lossless.test.ts 通过
2. 已绑定窗口调用 reqboard_status 返回 success（修复前必然 not lossless JSON）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/status-lossless.test.ts 通过；已绑定窗口调用 reqboard_status 返回 success（修复前必然 not lossless JSON）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · Dive 采集半停止直投 + 投递白名单

**验收内容**：【Dive 采集半停止直投 + 投递白名单】验收：npx vitest run tests/dive-manager-alignment.test.ts tests/dive-round-driver.test.ts 通过：同阶段连续两条人类消息 → onStagePrompt 0 次、不产生额外轮次；armed+active 时投递且 source.kind==="dive"。

**操作步骤**：
1. npx vitest run tests/dive-manager-alignment.test.ts tests/dive-round-driver.test.ts 通过：同阶段连续两条人类消息 → onStagePrompt 0 次、不产生额外轮次
2. armed+active 时投递且 source.kind==="dive"。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/dive-manager-alignment.test.ts tests/dive-round-driver.test.ts 通过：同阶段连续两条人类消息 → onStagePrompt 0 次、不产生额外轮次；armed+active 时投递且 source.kind==="dive"。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-12 · RTM 窗口绑定投影可更新且有消费者

**验收内容**：【RTM 窗口绑定投影可更新且有消费者】验收：npx vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts 通过：先建后绑 → source_session 随之更新；grep 该字段存在读取方（或类型层如实声明）。

**操作步骤**：
1. npx vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts 通过：先建后绑 → source_session 随之更新
2. grep 该字段存在读取方（或类型层如实声明）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts 通过：先建后绑 → source_session 随之更新；grep 该字段存在读取方（或类型层如实声明）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-13 · 证据路径确认后同调用内推进（已实现，补回归）

**验收内容**：【证据路径确认后同调用内推进（已实现，补回归）】验收：npx vitest run tests/confirm-evidence.test.ts 8/8 通过（含 advanced=true 与 kind 不匹配不推进两条）。

**操作步骤**：
1. npx vitest run tests/confirm-evidence.test.ts 8/8 通过（含 advanced=true 与 kind 不匹配不推进两条）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/confirm-evidence.test.ts 8/8 通过（含 advanced=true 与 kind 不匹配不推进两条）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-14 · Dive 在人工门主动弹框（有边界重弹）

**验收内容**：【Dive 在人工门主动弹框（有边界重弹）】验收：npx vitest run tests/dive-gate-prompt.test.ts 通过：门已满足未推进时弹出推进确认框；同一次等待只弹 1 次；冷却内不弹、上限 2 次后停手并写 comment。

**操作步骤**：
1. npx vitest run tests/dive-gate-prompt.test.ts 通过：门已满足未推进时弹出推进确认框
2. 同一次等待只弹 1 次
3. 冷却内不弹、上限 2 次后停手并写 comment。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/dive-gate-prompt.test.ts 通过：门已满足未推进时弹出推进确认框；同一次等待只弹 1 次；冷却内不弹、上限 2 次后停手并写 comment。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-15 · 修 apply-wiring 装配 stub 与期望集合

**验收内容**：【修 apply-wiring 装配 stub 与期望集合】验收：npx vitest run tests/apply-wiring.test.ts 4/4 通过（当前因 Service 装配抛错 4/4 红）。

**操作步骤**：
1. npx vitest run tests/apply-wiring.test.ts 4/4 通过（当前因 Service 装配抛错 4/4 红）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/apply-wiring.test.ts 4/4 通过（当前因 Service 装配抛错 4/4 红）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-16 · 同步文档：流程图 / 白名单 / 手册

**验收内容**：【同步文档：流程图 / 白名单 / 手册】验收：python3 agent-dh/scripts/wiki_probe.py 无新增死链/孤儿；流程图文档的缺陷落点索引覆盖 D1–D13。

**操作步骤**：
1. python3 agent-dh/scripts/wiki_probe.py 无新增死链/孤儿
2. 流程图文档的缺陷落点索引覆盖 D1–D13。

**预期结果**：按上述步骤执行后满足验收标准：python3 agent-dh/scripts/wiki_probe.py 无新增死链/孤儿；流程图文档的缺陷落点索引覆盖 D1–D13。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-17 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-20 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 修复前实机复现（本窗口 session-52f725ef）：reqboard_status 返回 "returned invalid output: value is not lossless JSON" —— FR-10 的现场证据（复现与根因见 docs/requirements/REQ-260927100007-b8ba/tests/verification-evidence.md 的 T4 节）
- 命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run <21 个测试文件> -> Test Files 21 passed (21)，Tests 219 passed (219)（完整清单与输出见 docs/requirements/REQ-260927100007-b8ba/tests/verification-evidence.md 的 T1 节）
- FR-12 专项：packages/tools/reqboard/tests/rtm/triggers.test.ts -> 14/14（新增 bind 触发点，刷新集合恰为 rtm-lifecycle.yml）
- FR-11/FR-14 专项：dive-gate-prompt 9/9、dive-session-driver-wiring 8/8、dive-round-driver 14/14、dive-manager-alignment 13/13；capture-hook / isolate-node-context 的旧「阶段纪律投递」契约已改写为「采集半零投递 + 注入留痕照旧」
- 命令：cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard && pnpm build -> 退出码 0；产物内可检索 reqboard_task_move(25) / reqboard_move(22) 与 FR-10 条件展开修法
- 台账复核：REQ-260927100007-b8ba 16/16 任务 done，需求 implementing -> accepting（台账留痕 [自动推进] implementing → accepting）
- docs/requirements/REQ-260927100007-b8ba/tasks/t-4b7697.md（及同目录其余 15 张卡）均已追加「## 汇报」完工记录
- 自检表（逐条 FR × 证据锚点 × 未过项）与任务覆盖标注（covers）：docs/requirements/REQ-260927100007-b8ba/reviews/acceptance-selfcheck.md 与 docs/requirements/REQ-260927100007-b8ba/tests/verification-evidence.md
- 已知既有失败（非本需求引入，已核 HEAD 同样红）：tests/acceptance-criteria.test.ts 的 schemaVersion 断言 7 vs 8（HEAD 已是 8）；该文件默认 threads 池另因 process.chdir() 全红，--pool=forks 下仅上述 1 条失败
- 已知交付边界（响亮报出）：FR-14 的 GatePromptPort 与有界重弹已实现并单测覆盖，但未在生产组合根装配（任务卡明确允许「未装配端口 -> 行为与改动前逐字一致」）；激活需在 src/index.ts 注入 createGatePromptPort 并补 agent 解析，请人裁决是否在本需求内打开
- wiki 自检：python3 agent-dh/scripts/wiki_probe.py -> 现行页死链 30 条全部为既有；本需求新增/修改页零新增死链/孤儿；python3 agent-dh/scripts/docs_index.py --check -> 索引与文档一致

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 抽任务级收敛点并统一四处写入点 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-2 | 补 agent 侧需求/任务流转工具 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-3 | 补齐 MoveTask 契约（现有测试即契约） | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-4 | 批准计划即同步落库并响亮化失败 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-5 | 阶段推进加任务完整性守卫 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-6 | 修正条款门禁失败提示与计划提交提示 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-7 | 修 reqboard_decompose 返回体契约 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-8 | RTM 刷新集合补 rtm-decomposing | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-9 | 确认门挂起期间的停手守卫 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-10 | 修 reqboard_status 返回体 lossless | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:07 |
| v1-11 | Dive 采集半停止直投 + 投递白名单 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:08 |
| v1-12 | RTM 窗口绑定投影可更新且有消费者 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:08 |
| v1-13 | 证据路径确认后同调用内推进（已实现，补回归） | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:08 |
| v1-14 | Dive 在人工门主动弹框（有边界重弹） | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:08 |
| v1-15 | 修 apply-wiring 装配 stub 与期望集合 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:08 |
| v1-16 | 同步文档：流程图 / 白名单 / 手册 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:08 |
| v1-17 | 需求级验收 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:08 |
| v1-20 | 需求级验收 | ✓ 通过 | human/session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8 | 2026-09-27 12:08 |
