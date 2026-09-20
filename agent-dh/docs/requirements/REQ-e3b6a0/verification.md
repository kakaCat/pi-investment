# REQ-e3b6a0 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：REQ-e3b6a0 交付：闸门确认后置链（切面 + 责任链 H1–H5）+ 立项 pm 专有弹框 reqboard_capture + 立项提示硬化。
实施层与门禁层已全部收口：pmboard 全量 1383 通过 / 本次新增失败 0（13 条失败逐条为既有他人债）、tsc 仅基线 1 条、客户端构建与哨兵校验通过。
本轮额外修复（E2E 走查实测所得）：定位了"立项有提示词却不弹框"的真因——链路全通（登记/命中/注入均正常），但窗口 35 次 PTC 子调用零次 reqboard_capture，断点在模型执行而非机制；已把立项提示从"请你判断可能值得立项"硬化成"必须显式裁定 + 值得立项时本回合第一个工具调用即 reqboard_capture + 不立项必须写明理由"，并用单测锁定防再软化。
需求级线上走查（AC-7.1 立项三问 / AC-11.2 G1 与两处留痕各 +1）按 2026-09-20 用户裁定正位到本验收阶段采集，验收义务不变。

## 1. 验收列表

### v1-1 · 实测 V1 契约：surface replace 是否唤醒 driver

**验收内容**：【实测 V1 契约：surface replace 是否唤醒 driver】验收：在一次性 agent（不得用本会话）上执行一次 replace，记录结果并写入 design/interfaces.md §8；结论必须是"H4 用 followup"或"H4 只发摘要"二者之一

**操作步骤**：
1. 在一次性 agent（不得用本会话）上执行一次 replace，记录结果并写入 design/interfaces.md §8
2. 结论必须是"H4 用 followup"或"H4 只发摘要"二者之一

**预期结果**：按上述步骤执行后满足验收标准：在一次性 agent（不得用本会话）上执行一次 replace，记录结果并写入 design/interfaces.md §8；结论必须是"H4 用 followup"或"H4 只发摘要"二者之一

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 建闸门领域：GateSpec + GateCatalog，收敛四处重复定义

**验收内容**：【建闸门领域：GateSpec + GateCatalog，收敛四处重复定义】验收：① grep -rn "const ADVANCE_MAP|const questionByTransition" packages/pages/dsh-pmboard/src 返回 0 命中；② npx vitest run tests/gate-catalog.test.ts 全绿（6/6，含 advanceTargetFor 与 questionCardFor 对旧实现逐条对拍、humanOnly 与 HUMAN_ONLY_REQ_TRANSITIONS 互锁）；③ 全量 npx vitest run 与 pristine HEAD 基线逐条 diff 后新增失败为 0；④ grep -rn "brainstorming>design" src 只剩 RequirementStatus 的人工专属集合（由 ② 锁死一致）与注释

**操作步骤**：
1. ① grep -rn "const ADVANCE_MAP|const questionByTransition" packages/pages/dsh-pmboard/src 返回 0 命中
2. ② npx vitest run tests/gate-catalog.test.ts 全绿（6/6，含 advanceTargetFor 与 questionCardFor 对旧实现逐条对拍、humanOnly 与 HUMAN_ONLY_REQ_TRANSITIONS 互锁）
3. ③ 全量 npx vitest run 与 pristine HEAD 基线逐条 diff 后新增失败为 0
4. ④ grep -rn "brainstorming>design" src 只剩 RequirementStatus 的人工专属集合（由 ② 锁死一致）与注释

**预期结果**：按上述步骤执行后满足验收标准：① grep -rn "const ADVANCE_MAP|const questionByTransition" packages/pages/dsh-pmboard/src 返回 0 命中；② npx vitest run tests/gate-catalog.test.ts 全绿（6/6，含 advanceTargetFor 与 questionCardFor 对旧实现逐条对拍、humanOnly 与 HUMAN_ONLY_REQ_TRANSITIONS 互锁）；③ 全量 npx vitest run 与 pristine HEAD 基线逐条 diff 后新增失败为 0；④ grep -rn "brainstorming>design" src 只剩 RequirementStatus 的人工专属集合（由 ② 锁死一致）与注释

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 后置链框架：H1..H5 + 两相执行 + 幂等/降级

**验收内容**：【后置链框架：H1..H5 + 两相执行 + 幂等/降级】验收：npx vitest run tests/gate-post-chain.test.ts（新增）断言链序为 H1→H2(skip)→H3→H4→H5、H2 skip 不阻断 H3、H2/H4 抛错后 H1 落库结果不变；开关关时 Phase B 执行计数为 0

**操作步骤**：
1. npx vitest run tests/gate-post-chain.test.ts（新增）断言链序为 H1→H2(skip)→H3→H4→H5、H2 skip 不阻断 H3、H2/H4 抛错后 H1 落库结果不变
2. 开关关时 Phase B 执行计数为 0

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/gate-post-chain.test.ts（新增）断言链序为 H1→H2(skip)→H3→H4→H5、H2 skip 不阻断 H3、H2/H4 抛错后 H1 落库结果不变；开关关时 Phase B 执行计数为 0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 修投递死链路：AgentDeliverer 统一投递形状

**验收内容**：【修投递死链路：AgentDeliverer 统一投递形状】验收：① grep -rnE "^[[:space:]]*agents\??\.?[[:space:]]*\.?followup\(" packages/pages/dsh-pmboard/src 返回 0 命中（语句位置的死调用；注释里的历史写法不计）；② npx vitest run tests/agent-deliverer.test.ts 全绿（7/7：在线 → delivered=true 且消息形状为 {id,role:user,content,source}；离线 / 无 followup / followup 抛错 / agents.get 抛错 / 服务缺失 → delivered=false 且不抛）；③ 既有催办路径断言仍全绿：npx vitest run tests/capture-hook.test.ts 通过（含 4 条里程碑超时提醒断言）；④ 全量 npx vitest run 与 pristine HEAD 基线 diff 后新增失败为 0

**操作步骤**：
1. ① grep -rnE "^[[:space:]]*agents\??\.?[[:space:]]*\.?followup\(" packages/pages/dsh-pmboard/src 返回 0 命中（语句位置的死调用
2. 注释里的历史写法不计）
3. ② npx vitest run tests/agent-deliverer.test.ts 全绿（7/7：在线 → delivered=true 且消息形状为 {id,role:user,content,source}
4. 离线 / 无 followup / followup 抛错 / agents.get 抛错 / 服务缺失 → delivered=false 且不抛）
5. ③ 既有催办路径断言仍全绿：npx vitest run tests/capture-hook.test.ts 通过（含 4 条里程碑超时提醒断言）
6. ④ 全量 npx vitest run 与 pristine HEAD 基线 diff 后新增失败为 0

**预期结果**：按上述步骤执行后满足验收标准：① grep -rnE "^[[:space:]]*agents\??\.?[[:space:]]*\.?followup\(" packages/pages/dsh-pmboard/src 返回 0 命中（语句位置的死调用；注释里的历史写法不计）；② npx vitest run tests/agent-deliverer.test.ts 全绿（7/7：在线 → delivered=true 且消息形状为 {id,role:user,content,source}；离线 / 无 followup / followup 抛错 / agents.get 抛错 / 服务缺失 → delivered=false 且不抛）；③ 既有催办路径断言仍全绿：npx vitest run tests/capture-hook.test.ts 通过（含 4 条里程碑超时提醒断言）；④ 全量 npx vitest run 与 pristine HEAD 基线 diff 后新增失败为 0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · H2 压缩接线：接入 isolateNodeContext（含自足判定与开关）

**验收内容**：【H2 压缩接线：接入 isolateNodeContext（含自足判定与开关）】验收：npx vitest run tests/h2-compact.test.ts（新增）断言 status=replaced 且 range 自首个非 system 节点起、artifactSeq < replacementSeq；文档不存在→skip、idle=false→skip、触达不到→fallback

**操作步骤**：
1. npx vitest run tests/h2-compact.test.ts（新增）断言 status=replaced 且 range 自首个非 system 节点起、artifactSeq < replacementSeq
2. 文档不存在→skip、idle=false→skip、触达不到→fallback

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/h2-compact.test.ts（新增）断言 status=replaced 且 range 自首个非 system 节点起、artifactSeq < replacementSeq；文档不存在→skip、idle=false→skip、触达不到→fallback

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · H3 注入器 + 难度取词映射（promptDifficulty→light/heavy）

**验收内容**：【H3 注入器 + 难度取词映射（promptDifficulty→light/heavy）】验收：① npx vitest run tests/difficulty-mapping.test.ts 全绿（11/11：四档枚举全覆盖→light/light/heavy/heavy、取重不取轻、未声明保持向后兼容、显式 difficulty 优先）；② npx vitest run tests/h3-inject.test.ts 全绿（10/10：G1 确认后注入 design 档且 fragmentIds 不含 brainstorming 档、取词阶段由 ctx.to 决定、INV-6 留痕十字段与取词结果一致、四条 skip/degraded、难度透传 expert→heavy 与 simple→light 与未声明不传）；③ npx vitest run tests/stage-prompts.test.ts 仍全绿（回归）；④ 全量 npx vitest run 与 pristine HEAD 基线 diff 后新增失败为 0

**操作步骤**：
1. ① npx vitest run tests/difficulty-mapping.test.ts 全绿（11/11：四档枚举全覆盖→light/light/heavy/heavy、取重不取轻、未声明保持向后兼容、显式 difficulty 优先）
2. ② npx vitest run tests/h3-inject.test.ts 全绿（10/10：G1 确认后注入 design 档且 fragmentIds 不含 brainstorming 档、取词阶段由 ctx.to 决定、INV-6 留痕十字段与取词结果一致、四条 skip/degraded、难度透传 expert→heavy 与 simple→light 与未声明不传）
3. ③ npx vitest run tests/stage-prompts.test.ts 仍全绿（回归）
4. ④ 全量 npx vitest run 与 pristine HEAD 基线 diff 后新增失败为 0

**预期结果**：按上述步骤执行后满足验收标准：① npx vitest run tests/difficulty-mapping.test.ts 全绿（11/11：四档枚举全覆盖→light/light/heavy/heavy、取重不取轻、未声明保持向后兼容、显式 difficulty 优先）；② npx vitest run tests/h3-inject.test.ts 全绿（10/10：G1 确认后注入 design 档且 fragmentIds 不含 brainstorming 档、取词阶段由 ctx.to 决定、INV-6 留痕十字段与取词结果一致、四条 skip/degraded、难度透传 expert→heavy 与 simple→light 与未声明不传）；③ npx vitest run tests/stage-prompts.test.ts 仍全绿（回归）；④ 全量 npx vitest run 与 pristine HEAD 基线 diff 后新增失败为 0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · GateAwareQuestions 装饰器 + 三条 pm 弹框带 gate 声明

**验收内容**：【GateAwareQuestions 装饰器 + 三条 pm 弹框带 gate 声明】验收：npx vitest run tests/gate-aware-questions.test.ts（新增）断言：新增一个带 opts.gate 的假弹框用例后链被登记，且 GateAwareQuestions.ts 与 GatePostChain.ts 未被修改；AskConfirm.ts / AcceptSheet.ts 三条路径作答后各触发一次链

**操作步骤**：
1. npx vitest run tests/gate-aware-questions.test.ts（新增）断言：新增一个带 opts.gate 的假弹框用例后链被登记，且 GateAwareQuestions.ts 与 GatePostChain.ts 未被修改
2. AskConfirm.ts / AcceptSheet.ts 三条路径作答后各触发一次链

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/gate-aware-questions.test.ts（新增）断言：新增一个带 opts.gate 的假弹框用例后链被登记，且 GateAwareQuestions.ts 与 GatePostChain.ts 未被修改；AskConfirm.ts / AcceptSheet.ts 三条路径作答后各触发一次链

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 立项 pm 专有弹框工具 reqboard_capture + 文案改造

**验收内容**：【立项 pm 专有弹框工具 reqboard_capture + 文案改造】验收：grep -n "ask_user_question" packages/pages/dsh-pmboard/src/application/internal/capture-section.ts → 0 命中（本卡汇报 1 已实测）；
三处「两问/三问」口径统一为三问（capture-section.ts / QueryState.ts / CreateTool/prompt.ts），全仓 src「两问」残留 0；
npx vitest run tests/capture-tool.test.ts 通过（含三问同批弹出、自定义优先、创建+绑定+推进、缺项 defaults_used、通道不可用 fallback=board 不创建、用户取消中性、名称为空响亮失败、已绑定则弹框根本没发生）。
说明（正位，2026-09-20 用户裁定）：需求级线上走查（AC-7.1「立项后不再输入任何消息即产出 requirement.md」）不在本卡承载——改由 accepting 阶段的 verification 证据采集，验收义务不变。

**操作步骤**：
1. grep -n "ask_user_question" packages/pages/dsh-pmboard/src/application/internal/capture-section.ts → 0 命中（本卡汇报 1 已实测）
2. 三处「两问/三问」口径统一为三问（capture-section.ts / QueryState.ts / CreateTool/prompt.ts），全仓 src「两问」残留 0
3. npx vitest run tests/capture-tool.test.ts 通过（含三问同批弹出、自定义优先、创建+绑定+推进、缺项 defaults_used、通道不可用 fallback=board 不创建、用户取消中性、名称为空响亮失败、已绑定则弹框根本没发生）。
4. 说明（正位，2026-09-20 用户裁定）：需求级线上走查（AC-7.1「立项后不再输入任何消息即产出 requirement.md」）不在本卡承载——改由 accepting 阶段的 verification 证据采集，验收义务不变。

**预期结果**：按上述步骤执行后满足验收标准：grep -n "ask_user_question" packages/pages/dsh-pmboard/src/application/internal/capture-section.ts → 0 命中（本卡汇报 1 已实测）；
三处「两问/三问」口径统一为三问（capture-section.ts / QueryState.ts / CreateTool/prompt.ts），全仓 src「两问」残留 0；
npx vitest run tests/capture-tool.test.ts 通过（含三问同批弹出、自定义优先、创建+绑定+推进、缺项 defaults_used、通道不可用 fallback=board 不创建、用户取消中性、名称为空响亮失败、已绑定则弹框根本没发生）。
说明（正位，2026-09-20 用户裁定）：需求级线上走查（AC-7.1「立项后不再输入任何消息即产出 requirement.md」）不在本卡承载——改由 accepting 阶段的 verification 证据采集，验收义务不变。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-9 · 看板通道 B：确认即推进 + 链侧投递

**验收内容**：【看板通道 B：确认即推进 + 链侧投递】验收：npx vitest run tests/artifact-confirm-board.test.ts（新增）断言 POST /req/artifact/confirm 返回体 advanced=true 且 delivered=true；agents.get 返 undefined 时返回体 advanced=false 且 note 包含"窗口不在线"；B 后再走 A 只推进一次

**操作步骤**：
1. npx vitest run tests/artifact-confirm-board.test.ts（新增）断言 POST /req/artifact/confirm 返回体 advanced=true 且 delivered=true
2. agents.get 返 undefined 时返回体 advanced=false 且 note 包含"窗口不在线"
3. B 后再走 A 只推进一次

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/artifact-confirm-board.test.ts（新增）断言 POST /req/artifact/confirm 返回体 advanced=true 且 delivered=true；agents.get 返 undefined 时返回体 advanced=false 且 note 包含"窗口不在线"；B 后再走 A 只推进一次

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-10 · 测试与门禁收口 + 文档漂移同步

**验收内容**：【测试与门禁收口 + 文档漂移同步】验收：npx vitest run 全绿（新增失败 0；既有他人债逐条列明来源需求）且 npx tsc --noEmit -p tsconfig.json 无新增错误；
grep 判据落成可跑命令：reqboard-workflow.md 的闸门表与 GateCatalog.ts / ArtifactSpec.ts 逐条一致（本卡汇报 1 已落）；
立项硬化语有单测锁定：npx vitest run tests/capture.test.ts 通过，且断言含「第一个工具调用必须是 reqboard_capture」「本条不立项」「不许沉默」。
说明（正位，2026-09-20 用户裁定）：需求级线上走查（AC-7.1 立项、AC-11.2 G1、两处留痕各 +1）不在本卡承载——改由 accepting 阶段的 verification 证据采集，验收义务不变（见 requirement.md §7.3.2 与 AC-11.2）。

**操作步骤**：
1. npx vitest run 全绿（新增失败 0
2. 既有他人债逐条列明来源需求）且 npx tsc --noEmit -p tsconfig.json 无新增错误
3. grep 判据落成可跑命令：reqboard-workflow.md 的闸门表与 GateCatalog.ts / ArtifactSpec.ts 逐条一致（本卡汇报 1 已落）
4. 立项硬化语有单测锁定：npx vitest run tests/capture.test.ts 通过，且断言含「第一个工具调用必须是 reqboard_capture」「本条不立项」「不许沉默」。
5. 说明（正位，2026-09-20 用户裁定）：需求级线上走查（AC-7.1 立项、AC-11.2 G1、两处留痕各 +1）不在本卡承载——改由 accepting 阶段的 verification 证据采集，验收义务不变（见 requirement.md §7.3.2 与 AC-11.2）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run 全绿（新增失败 0；既有他人债逐条列明来源需求）且 npx tsc --noEmit -p tsconfig.json 无新增错误；
grep 判据落成可跑命令：reqboard-workflow.md 的闸门表与 GateCatalog.ts / ArtifactSpec.ts 逐条一致（本卡汇报 1 已落）；
立项硬化语有单测锁定：npx vitest run tests/capture.test.ts 通过，且断言含「第一个工具调用必须是 reqboard_capture」「本条不立项」「不许沉默」。
说明（正位，2026-09-20 用户裁定）：需求级线上走查（AC-7.1 立项、AC-11.2 G1、两处留痕各 +1）不在本卡承载——改由 accepting 阶段的 verification 证据采集，验收义务不变（见 requirement.md §7.3.2 与 AC-11.2）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-14 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 【评审报告】docs/requirements/REQ-e3b6a0/reviews/e2e-rework-review.md（走查事实、根因评审、处置、流程正位、遗留风险）
- 【测试与门禁证据】docs/requirements/REQ-e3b6a0/tests/verification-evidence.md（命令 + 输出摘要 + 既有失败清单归属 + 待验项）
- 【根因实测】读取窗口转录 .dsh-data/sessions/--Users-yunpeng-pi-investment-agent-dh--/session-361c2879-810c-4093-b8e6-3a6fba52cdd2/session.v3.jsonl.zstd（zstd -dc）：turn 2/3/4 的 system/message 均含「检测到用户新输入」针对性立项段；17 次 tool/call 的 PTC 展开 35 次子调用只含 read 与 grep，reqboard_capture 为 0 次
- 【修复·提示词】packages/pages/dsh-pmboard/src/application/internal/capture-section.ts：grep "第一个工具调用必须是 reqboard_capture" 命中 1；同段含「本条不立项」「不许沉默」「判不准按值得立项处理」
- 【修复·留痕】packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts：grep "consumes pending capture" 命中 1
- 【单测】packages/pages/dsh-pmboard/tests/capture.test.ts：23 passed（新增锁定用例：第一个工具调用必须是 reqboard_capture / 本条不立项 / 不许沉默 / 静态引导含弹框问用户）
- 【全量门禁】在 packages/pages/dsh-pmboard 下 npx vitest run：Tests 13 failed | 1383 passed，13 条全部为既有他人债（REQ-a8d582 五条、REQ-327bdf 五条、typecheck 基线、size-budget、client-view），本次新增失败 0
- 【类型门禁】npx tsc --noEmit -p tsconfig.json：仅基线 1 条，位于 packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/update-task-card.ts（TS6133，非本需求）
- 【构建门禁】在 packages/pages/dsh-pmboard 下 pnpm build:client：verify-client OK，bundle=231967 bytes、关键符号齐全、模板字符串哨兵通过
- 【文档同步】docs/requirements/REQ-e3b6a0/requirement.md：FR-7 增第 8 条（触发时机硬化）+ 新增 §7.3.2；过程留痕见 docs/requirements/REQ-e3b6a0/tasks/t-3e11bf.md（汇报 1–3）与 docs/requirements/REQ-e3b6a0/tasks/t-f33035.md（汇报 1）
- 【流程正位·2026-09-20 用户裁定】线上走查由 accepting 阶段承载：t-f33035 与 t-3e11bf 的验收标准已修订，验收义务不变
- 【待验·本验收阶段】AC-7.1：新窗口提工作意图，期望 agent 先调 reqboard_capture 弹立项三问；AC-11.2：G1 后不再输入消息即自动进 design，且 .dsh-data/state/prompt-injection-log.json 最后一条变化、.dsh-data/state/node-isolation-log.json 条目加 1

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 实测 V1 契约：surface replace 是否唤醒 driver | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:34 |
| v1-2 | 建闸门领域：GateSpec + GateCatalog，收敛四处重复定义 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:34 |
| v1-3 | 后置链框架：H1..H5 + 两相执行 + 幂等/降级 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:34 |
| v1-4 | 修投递死链路：AgentDeliverer 统一投递形状 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:34 |
| v1-5 | H2 压缩接线：接入 isolateNodeContext（含自足判定与开关） | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:34 |
| v1-6 | H3 注入器 + 难度取词映射（promptDifficulty→light/heavy） | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:35 |
| v1-7 | GateAwareQuestions 装饰器 + 三条 pm 弹框带 gate 声明 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:35 |
| v1-8 | 立项 pm 专有弹框工具 reqboard_capture + 文案改造 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:35 |
| v1-9 | 看板通道 B：确认即推进 + 链侧投递 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:35 |
| v1-10 | 测试与门禁收口 + 文档漂移同步 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:35 |
| v1-11 | 需求级验收 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:35 |
| v1-14 | 需求级验收 | ✓ 通过 | human/session-878da638-a076-4266-ae40-70a2390060f2 | 2026-09-20 16:35 |
