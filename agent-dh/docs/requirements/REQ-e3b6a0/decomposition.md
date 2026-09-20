# REQ-e3b6a0 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| FR-5 | t1 | t-f118db | 实测 V1 契约：surface replace 是否唤醒 driver | todo |
| FR-10 | t2 | t-63a402 | 建闸门领域：GateSpec + GateCatalog，收敛四处重复定义 | todo |
| FR-1 | t2 | t-63a402 | 建闸门领域：GateSpec + GateCatalog，收敛四处重复定义 | todo |
| FR-1 | t3 | t-9f24a5 | 后置链框架：H1..H5 + 两相执行 + 幂等/降级 | todo |
| FR-2 | t3 | t-9f24a5 | 后置链框架：H1..H5 + 两相执行 + 幂等/降级 | todo |
| FR-6 | t3 | t-9f24a5 | 后置链框架：H1..H5 + 两相执行 + 幂等/降级 | todo |
| FR-5 | t4 | t-db8f9c | 修投递死链路：AgentDeliverer 统一投递形状 | todo |
| FR-3 | t5 | t-44ae54 | H2 压缩接线：接入 isolateNodeContext（含自足判定与开关） | todo |
| FR-4 | t6 | t-3f82e9 | H3 注入器 + 难度取词映射（promptDifficulty→light/heavy） | todo |
| FR-1 | t7 | t-3270ae | GateAwareQuestions 装饰器 + 三条 pm 弹框带 gate 声明 | todo |
| FR-10 | t7 | t-3270ae | GateAwareQuestions 装饰器 + 三条 pm 弹框带 gate 声明 | todo |
| FR-7 | t8 | t-f33035 | 立项 pm 专有弹框工具 reqboard_capture + 文案改造 | todo |
| FR-9 | t9 | t-dd6c5c | 看板通道 B：确认即推进 + 链侧投递 | todo |
| FR-8 | t10 | t-3e11bf | 测试与门禁收口 + 文档漂移同步 | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-f118db | 实测 V1 契约：surface replace 是否唤醒 driver | analysis | backend | - | 在一次性 agent（不得用本会话）上执行一次 replace，记录结果并写入 design/interfaces.md §8；结论必须是"H4 用 followup"或"H4 只发摘要"二者之一 |
| t2 | t-63a402 | 建闸门领域：GateSpec + GateCatalog，收敛四处重复定义 | implement | backend | - | grep -rn "ADVANCE_MAP|ARTIFACT_CONFIRM_GATES" packages/pages/dsh-pmboard/src 只剩 domain/gate 一处；既有 npx vitest run 全绿（ArtifactSpec 改再导出） |
| t3 | t-9f24a5 | 后置链框架：H1..H5 + 两相执行 + 幂等/降级 | implement | backend | t-63a402 | npx vitest run tests/gate-post-chain.test.ts（新增）断言链序为 H1→H2(skip)→H3→H4→H5、H2 skip 不阻断 H3、H2/H4 抛错后 H1 落库结果不变；开关关时 Phase B 执行计数为 0 |
| t4 | t-db8f9c | 修投递死链路：AgentDeliverer 统一投递形状 | implement | backend | t-f118db | grep -rn "agents\.followup(" packages/pages/dsh-pmboard/src 返回 0 命中；npx vitest run tests/agent-deliverer.test.ts（新增）断言在线→delivered=true、离线/无 followup/抛错→delivered=false 且不抛 |
| t5 | t-44ae54 | H2 压缩接线：接入 isolateNodeContext（含自足判定与开关） | implement | backend | t-9f24a5 | npx vitest run tests/h2-compact.test.ts（新增）断言 status=replaced 且 range 自首个非 system 节点起、artifactSeq < replacementSeq；文档不存在→skip、idle=false→skip、触达不到→fallback |
| t6 | t-3f82e9 | H3 注入器 + 难度取词映射（promptDifficulty→light/heavy） | implement | backend | t-63a402 | npx vitest run tests/difficulty-mapping.test.ts（新增）断言 expert 的 routeKey 包含 heavy、simple 包含 light、未声明时与文本推断结果一致；tests/stage-prompts.test.ts 断言 G1 确认后注入文本包含 design 档片段 id 且不包含 brainstorming 档 |
| t7 | t-3270ae | GateAwareQuestions 装饰器 + 三条 pm 弹框带 gate 声明 | implement | backend | t-9f24a5 | npx vitest run tests/gate-aware-questions.test.ts（新增）断言：新增一个带 opts.gate 的假弹框用例后链被登记，且 GateAwareQuestions.ts 与 GatePostChain.ts 未被修改；AskConfirm.ts / AcceptSheet.ts 三条路径作答后各触发一次链 |
| t8 | t-f33035 | 立项 pm 专有弹框工具 reqboard_capture + 文案改造 | implement | backend | t-3270ae | grep -n "ask_user_question" packages/pages/dsh-pmboard/src/application/internal/capture-section.ts 返回 0 命中；真实走一次立项后不再输入任何消息即产出 requirement.md；三处口径统一为三问 |
| t9 | t-dd6c5c | 看板通道 B：确认即推进 + 链侧投递 | implement | backend | t-9f24a5, t-db8f9c | npx vitest run tests/artifact-confirm-board.test.ts（新增）断言 POST /req/artifact/confirm 返回体 advanced=true 且 delivered=true；agents.get 返 undefined 时返回体 advanced=false 且 note 包含"窗口不在线"；B 后再走 A 只推进一次 |
| t10 | t-3e11bf | 测试与门禁收口 + 文档漂移同步 | test | doc | t-db8f9c, t-44ae54, t-3f82e9, t-f33035, t-dd6c5c | npx vitest run 全绿且 npx tsc --noEmit -p tsconfig.json 无新增错误；:13080 真实 G1 走查通过且 prompt-injection-log.json 与 node-isolation-log.json 各新增一条；grep -nE "批准拆分计划|decomposing → implementing" docs/guides/reqboard-workflow.md 与 ArtifactSpec.ts:38 逐条一致 |
