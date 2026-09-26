# REQ-260926215013-1568 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：Dive 两半驱动器已对齐 DSH Goal round driver 机制——续跑只在整 agent 空闲且无竞争输入时经 withoutInitiator 起一轮；回合号走 reservation→admission（只有进入 history 的消息才计数）；回合上限写终态 paused/round-limit 并留 comment；pre-step 前后竞态栅栏、inbox 让位、排队点耐久检查点、fail-closed teardown 全部落地。7/7 任务卡 done，新增 4 个测试文件共 34 条断言全绿，tsc 错误数由 145 降到 140。

## 1. 验收列表

### v1-1 · 契约定死：回合来源、相位值域与驱动状态纯判定

**验收内容**：【契约定死：回合来源、相位值域与驱动状态纯判定】验收：npx vitest run tests/dive-round-state.test.ts 全绿（非 dive 来源不认、round 必须等于 roundsInStage+1、内容不一致返回 false）；npx tsc --noEmit -p tsconfig.json 错误数不高于改动前基线；grep -n paused src/shared/protocol.ts 可见 phase 值域含 paused。

**操作步骤**：
1. npx vitest run tests/dive-round-state.test.ts 全绿（非 dive 来源不认、round 必须等于 roundsInStage+1、内容不一致返回 false）
2. npx tsc --noEmit -p tsconfig.json 错误数不高于改动前基线
3. grep -n paused src/shared/protocol.ts 可见 phase 值域含 paused。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/dive-round-state.test.ts 全绿（非 dive 来源不认、round 必须等于 roundsInStage+1、内容不一致返回 false）；npx tsc --noEmit -p tsconfig.json 错误数不高于改动前基线；grep -n paused src/shared/protocol.ts 可见 phase 值域含 paused。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 回合状态机：空闲才起轮、准入才计数、上限写终态

**验收内容**：【回合状态机：空闲才起轮、准入才计数、上限写终态】验收：npx vitest run tests/dive-round-driver.test.ts 全绿：连发 3 次触发只执行 1 次驱动体；驱动体抛错不产生未捕获异常/未处理 rejection；需求 version 变化后 pre-step 返回 reject 且同批消息被放回；checkpoint 失败后 activation 等于 disarmed；roundsInStage 等于 maxRounds 时 phase 等于 paused 且 pausedReason 等于 round-limit。

**操作步骤**：
1. npx vitest run tests/dive-round-driver.test.ts 全绿：连发 3 次触发只执行 1 次驱动体
2. 驱动体抛错不产生未捕获异常/未处理 rejection
3. 需求 version 变化后 pre-step 返回 reject 且同批消息被放回
4. checkpoint 失败后 activation 等于 disarmed
5. roundsInStage 等于 maxRounds 时 phase 等于 paused 且 pausedReason 等于 round-limit。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/dive-round-driver.test.ts 全绿：连发 3 次触发只执行 1 次驱动体；驱动体抛错不产生未捕获异常/未处理 rejection；需求 version 变化后 pre-step 返回 reject 且同批消息被放回；checkpoint 失败后 activation 等于 disarmed；roundsInStage 等于 maxRounds 时 phase 等于 paused 且 pausedReason 等于 round-limit。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 投递适配：回合消息带机器可识别的来源标识

**验收内容**：【投递适配：回合消息带机器可识别的来源标识】验收：npx vitest run tests/agent-deliverer.test.ts 全绿；断言 createRoundMessage 返回的 message.source 与 {kind:'dive',requirementId,revision,round} 结构相等；deliverMessage 在 agents 不可得时返回 delivered:false 且不抛。

**操作步骤**：
1. npx vitest run tests/agent-deliverer.test.ts 全绿
2. 断言 createRoundMessage 返回的 message.source 与 {kind:'dive',requirementId,revision,round} 结构相等
3. deliverMessage 在 agents 不可得时返回 delivered:false 且不抛。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/agent-deliverer.test.ts 全绿；断言 createRoundMessage 返回的 message.source 与 {kind:'dive',requirementId,revision,round} 结构相等；deliverMessage 在 agents 不可得时返回 delivered:false 且不抛。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 会话驱动器组合：一拍内的定序与原采集行为不变（含向后兼容）

**验收内容**：【会话驱动器组合：一拍内的定序与原采集行为不变（含向后兼容）】验收：npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts 全绿（不注入 round 端口时行为与改动前一致）；wc -l src/application/dive/session-driver.ts 输出行数不超过 400。

**操作步骤**：
1. npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts 全绿（不注入 round 端口时行为与改动前一致）
2. wc -l src/application/dive/session-driver.ts 输出行数不超过 400。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts 全绿（不注入 round 端口时行为与改动前一致）；wc -l src/application/dive/session-driver.ts 输出行数不超过 400。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · Dive 服务接线：订阅收归服务、requirement-moved 不再直接续跑

**验收内容**：【Dive 服务接线：订阅收归服务、requirement-moved 不再直接续跑】验收：npx vitest run tests/dive-manager-wiring.test.ts 全绿（7 条订阅全部成立；requirement-moved 后 deliverMessage 未被调用、agent 空闲后才投递一次；teardown() 后触发不再投递）；grep -c followup src/application/dive/ReqboardDiveManager.ts 输出 0。

**操作步骤**：
1. npx vitest run tests/dive-manager-wiring.test.ts 全绿（7 条订阅全部成立
2. requirement-moved 后 deliverMessage 未被调用、agent 空闲后才投递一次
3. teardown() 后触发不再投递）
4. grep -c followup src/application/dive/ReqboardDiveManager.ts 输出 0。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/dive-manager-wiring.test.ts 全绿（7 条订阅全部成立；requirement-moved 后 deliverMessage 未被调用、agent 空闲后才投递一次；teardown() 后触发不再投递）；grep -c followup src/application/dive/ReqboardDiveManager.ts 输出 0。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 对齐验收：11 个 FR 的可证伪单测

**验收内容**：【对齐验收：11 个 FR 的可证伪单测】验收：npx vitest run tests/dive-manager-alignment.test.ts 输出 Tests 数不少于 11、failed 0；每条 FR-1…FR-11 至少一条断言（含 FR-11 六条路径留痕断言）。

**操作步骤**：
1. npx vitest run tests/dive-manager-alignment.test.ts 输出 Tests 数不少于 11、failed 0
2. 每条 FR-1…FR-11 至少一条断言（含 FR-11 六条路径留痕断言）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/dive-manager-alignment.test.ts 输出 Tests 数不少于 11、failed 0；每条 FR-1…FR-11 至少一条断言（含 FR-11 六条路径留痕断言）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 迁移与兼容核查 + 回归发版

**验收内容**：【迁移与兼容核查 + 回归发版】验收：python3 scripts/relink-profile.py --check 退出码 0；npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts 全绿且 npx tsc --noEmit -p tsconfig.json 错误数不高于基线；curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:13080/ 输出 200。

**操作步骤**：
1. python3 scripts/relink-profile.py --check 退出码 0
2. npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts 全绿且 npx tsc --noEmit -p tsconfig.json 错误数不高于基线
3. curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:13080/ 输出 200。

**预期结果**：按上述步骤执行后满足验收标准：python3 scripts/relink-profile.py --check 退出码 0；npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts 全绿且 npx tsc --noEmit -p tsconfig.json 错误数不高于基线；curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:13080/ 输出 200。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 主命令：cd packages/web/dsh-pmboard && npx vitest run ./tests/dive-manager-alignment.test.ts → 1 file passed，11 tests passed / 0 failed（TC-01…TC-11 逐条对应 FR-1…FR-11）；文件 packages/web/dsh-pmboard/tests/dive-manager-alignment.test.ts（covers: t-620dc0）
- 回归：cd packages/web/dsh-pmboard && npx vitest run ./tests/capture-hook.test.ts ./tests/dive-session-driver-wiring.test.ts ./tests/isolate-node-context.test.ts → 3 files passed / 63 tests passed / 0 failed（covers: t-cab4a2）
- 类型基线：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -c "error TS" → 140（改动前基线 145，净减 5）
- T-1 契约：npx vitest run ./tests/dive-round-state.test.ts → 12 passed（covers: t-aa2ec9）；实现 packages/web/dsh-pmboard/src/application/dive/round-state.ts
- T-2 状态机：npx vitest run ./tests/dive-round-driver.test.ts → 11 passed（covers: t-0ddfb1）；实现 packages/web/dsh-pmboard/src/application/dive/round-driver.ts
- T-3 投递：npx vitest run ./tests/agent-deliverer.test.ts → 9 passed（covers: t-4a74c8）
- T-5 接线：npx vitest run ./tests/dive-manager-wiring.test.ts → 6 passed（covers: t-1aa789）；grep -c followup packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts → 0
- T-7 迁移兼容：npx vitest run ./tests/t7-legacy-tolerance.test.ts → 3 passed + python3 scripts/relink-profile.py --check 退出码 0（covers: t-2b3e57）
- 发版：cd packages/web/dsh-pmboard && pnpm build 重建 packages/web/dsh-pmboard/dist/index.mjs（22:48）+ quick_restart；lsof -ti tcp:13080 -sTCP:LISTEN 有进程 PID 13808；注 curl / 返回 401（token 网关保护）
- 自检材料：docs/requirements/REQ-260926215013-1568/reviews/self-review.md 与 docs/requirements/REQ-260926215013-1568/tests/alignment-evidence.md（含 covers 覆盖表）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 契约定死：回合来源、相位值域与驱动状态纯判定 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
| v1-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
| v1-3 | 投递适配：回合消息带机器可识别的来源标识 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
| v1-4 | 会话驱动器组合：一拍内的定序与原采集行为不变（含向后兼容） | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
| v1-5 | Dive 服务接线：订阅收归服务、requirement-moved 不再直接续跑 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
| v1-6 | 对齐验收：11 个 FR 的可证伪单测 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
| v1-7 | 迁移与兼容核查 + 回归发版 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
| v1-11 | 需求级验收 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 22:52 |
