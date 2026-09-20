---
req_id: REQ-e3b6a0
doc: plan.md
type: decomposition-plan
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
---

# 拆分计划：人工闸门域 + 确认后置链

## 1. 目标（人要能读懂）

**做完之后人看到什么变化**：在任何一道人工闸门（立项三问 / 确认需求文档 / 批准计划 / 确认拆分清单 / 验收通过）的弹框里点一下，
**不用再输入任何消息**，agent 就会带着新阶段的纪律继续干活；上下文同时被压缩成一份"节点输入包"，长对话不再拖着走。

**怎么做到**：把"确认之后要发生什么"从散落各处的用例里收进一个**人工闸门领域**，
并用一个**装饰器**把"切面 + 后置责任链"的能力挂到所有 pm 弹框上——新入口零成本获得能力。

## 2. 做法（技术主线）

1. `domain/gate/` 成为闸门唯一事实源（收敛现存四处重复定义）；
2. `application/gate/` 承载后置链（H1 推进 → H2 压缩 → H3 注入 → H4 唤醒 → H5 留痕），两相执行；
3. `adapters/` 落两个适配器：`GateAwareQuestions`（装饰器）与 `AgentDeliverer`（唯一投递实现，修掉 `agents.followup(id,msg)` 死调用）；
4. 立项三问改走 pm 专有弹框工具 `reqboard_capture`，CaptureHook 文案随之改指；
5. 看板"确认产物"通道也纳入切面（确认即推进 + 投递）。

## 3. 任务表（粒度与依赖在此定死）

| key | 标题 | phase | side | 依赖 | 需求条款 | 验收（可证伪） | 实施方案 |
|---|---|---|---|---|---|---|---|
| t1 | 实测 V1 契约：surface replace 是否唤醒 driver | analysis | backend | — | FR-5 | 在一次性 agent（不得用本会话）上执行一次 replace，记录结果并写入 `design/interfaces.md` §8；结论必须是"H4 用 followup"或"H4 只发摘要"二者之一 | 读 `dsh-agent-loop/lib/index.js` 的 `send/inbox`；在隔离环境建一次性 agent 跑 replace；只写文档不改产品代码 |
| t2 | 建闸门领域：GateSpec + GateCatalog，收敛四处重复定义 | implement | backend | — | FR-10, FR-1 | `grep -rn "ADVANCE_MAP\|ARTIFACT_CONFIRM_GATES" packages/pages/dsh-pmboard/src` 只剩 `domain/gate` 一处；既有 `npx vitest run` 全绿（ArtifactSpec 改再导出） | 新增 `src/domain/gate/{GateSpec,GateCatalog}.ts`；`ArtifactSpec.ts` 改再导出；`AskConfirm.ts` 删私有 ADVANCE_MAP；`support.ts` 问题卡由 GateSpec 派生 |
| t3 | 后置链框架：H1..H5 + 两相执行 + 幂等/降级 | implement | backend | t2 | FR-1, FR-2, FR-6 | `npx vitest run tests/gate-post-chain.test.ts`（新增）断言链序为 H1→H2(skip)→H3→H4→H5、H2 skip 不阻断 H3、H2/H4 抛错后 H1 落库结果不变；开关关时 Phase B 执行计数为 0 | 新增 `application/gate/{GatePostChain,PendingGate}.ts` + `handlers/`；扩展 `node-settlement` 触发源；`ports.ts` 加 `GatePostChainPort` |
| t4 | 修投递死链路：AgentDeliverer 统一投递形状 | implement | backend | t1 | FR-5 | `grep -rn "agents\.followup(" packages/pages/dsh-pmboard/src` 返回 0 命中；`npx vitest run tests/agent-deliverer.test.ts`（新增）断言在线→delivered=true、离线/无 followup/抛错→delivered=false 且不抛 | 新增 `adapters/AgentDeliverer.ts`；`index.ts` 的 `onStagePrompt` 改用它；`CaptureHook` 催办路径补测试 |
| t5 | H2 压缩接线：接入 isolateNodeContext（含自足判定与开关） | implement | backend | t3 | FR-3 | `npx vitest run tests/h2-compact.test.ts`（新增）断言 status=replaced 且 range 自首个非 system 节点起、artifactSeq < replacementSeq；文档不存在→skip、idle=false→skip、触达不到→fallback | 新增 `application/gate/handlers/h2-compact.ts`；调用既有 `isolateNodeContext`；开关沿用 `NODE_ISOLATION` |
| t6 | H3 注入器 + 难度取词映射（promptDifficulty→light/heavy） | implement | backend | t2 | FR-4 | `npx vitest run tests/difficulty-mapping.test.ts`（新增）断言 expert 的 `routeKey` 包含 heavy、simple 包含 light、未声明时与文本推断结果一致；`tests/stage-prompts.test.ts` 断言 G1 确认后注入文本包含 design 档片段 id 且不包含 brainstorming 档 | 新增 `application/gate/handlers/h3-inject.ts`；`domain/prompt` 增加四档→两档映射（冲突取重）+ 单测 |
| t7 | GateAwareQuestions 装饰器 + 三条 pm 弹框带 gate 声明 | implement | backend | t3 | FR-1, FR-10 | `npx vitest run tests/gate-aware-questions.test.ts`（新增）断言：新增一个带 `opts.gate` 的假弹框用例后链被登记，且 `GateAwareQuestions.ts` 与 `GatePostChain.ts` 未被修改；`AskConfirm.ts` / `AcceptSheet.ts` 三条路径作答后各触发一次链 | 新增 `adapters/GateAwareQuestions.ts`；组合根装配；`AskConfirm.ts`/`AcceptSheet.ts` 的 `ask()` 补 `gate`；删除旧 `autoContinue` 桩 |
| t8 | 立项 pm 专有弹框工具 reqboard_capture + 文案改造 | implement | backend | t7 | FR-7 | `grep -n "ask_user_question" packages/pages/dsh-pmboard/src/application/internal/capture-section.ts` 返回 0 命中；真实走一次立项后不再输入任何消息即产出 `requirement.md`；三处口径统一为三问 | 新增 `tools/CaptureTool/*` + 用例 `captureCreate`；`capture-section.ts` 文案改指；`QueryState.ts:63` 与 `CreateTool/prompt.ts` 对齐 |
| t9 | 看板通道 B：确认即推进 + 链侧投递 | implement | backend | t3, t4 | FR-9 | `npx vitest run tests/artifact-confirm-board.test.ts`（新增）断言 `POST /req/artifact/confirm` 返回体 `advanced=true` 且 `delivered=true`；`agents.get` 返 undefined 时返回体 `advanced=false` 且 note 包含"窗口不在线"；B 后再走 A 只推进一次 | 扩展 `http/routers/requirements.ts` 的 confirm handler；`http/routes.ts` deps 加 `delivery`/`chain`；`index.ts` 注入 |
| t10 | 测试与门禁收口 + 文档漂移同步 | test | doc | t4, t5, t6, t8, t9 | FR-8 | `npx vitest run` 全绿且 `npx tsc --noEmit -p tsconfig.json` 无新增错误；:13080 真实 G1 走查通过且 `prompt-injection-log.json` 与 `node-isolation-log.json` 各新增一条；`grep -nE "批准拆分计划\|decomposing → implementing" docs/guides/reqboard-workflow.md` 与 `ArtifactSpec.ts:38` 逐条一致 | 补测试与 E2E 证据；更正 `reqboard-workflow.md:17` 与 `ArtifactSpec.ts:34` 注释 |

## 4. 风险与回滚

| 风险 | 处置 |
|---|---|
| surface 整段替换伤上下文（高风险动作） | H2 单独开关、默认关（D1 分两步上）；先验证"不压缩也能自动续跑" |
| V1 结论与静态实证相反 | t1 先实测再实现；回退方案已写在 `interfaces.md` §8 |
| 与 REQ-99f5fe 撞车（同文件） | D7②：其停手后本需求接管；停手前 t8 不开工 |
| 真出问题 | 全部新增代码集中在 `domain/gate`、`application/gate`、两个 adapters 与一个工具壳；删除即回滚，不涉及台账 schema（无停机迁移） |
