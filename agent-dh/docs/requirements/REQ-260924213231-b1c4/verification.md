# REQ-260924213231-b1c4 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：REQ-b1c4 全量交付：13 张父卡全部完成、需求自动滚进验收。设计阶段死锁的 8 个功能点已落地——agent 可自己登记设计产物并查逐份登记态、闸门拒绝区分「未登记 / 待确认」并给唯一下一步、弹框超宽限返回 pending+回执而非判失败、零参工具可直接调、提示词写明登记命令、断点可续跑、立项降级路径不丢文档位置、pm 弹框带来源标志。收口核对：验收三件套全绿；tsc 23 = 基线；全量失败集合 6 ⊆ 基线 9，无新增失败（链另修好 3 条既有失败）；9 类文档补齐（65 张任务卡 + reviews/ + tests/），验收项全部可照着验。

## 1. 验收列表

### v1-1 · 定义新契约类型与端口

**验收内容**：【定义新契约类型与端口】验收：npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts 全绿；npx tsc --noEmit -p tsconfig.json 错误数 ≤ 基线 23 且新增文件 0 报错

**操作步骤**：
1. npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts 全绿
2. npx tsc --noEmit -p tsconfig.json 错误数 ≤ 基线 23 且新增文件 0 报错

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts 全绿；npx tsc --noEmit -p tsconfig.json 错误数 ≤ 基线 23 且新增文件 0 报错

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-2 · 下沉产物发现核心并薄壳化 ArtifactSync

**验收内容**：【下沉产物发现核心并薄壳化 ArtifactSync】验收：npx vitest run tests/sync-artifacts.test.ts 全绿且既有断言逐字不变；npx vitest run tests/layer-boundary.test.ts 不新增越界（新增文件位于 application 且不 import node:/adapters）

**操作步骤**：
1. npx vitest run tests/sync-artifacts.test.ts 全绿且既有断言逐字不变
2. npx vitest run tests/layer-boundary.test.ts 不新增越界（新增文件位于 application 且不 import node:/adapters）

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/sync-artifacts.test.ts 全绿且既有断言逐字不变；npx vitest run tests/layer-boundary.test.ts 不新增越界（新增文件位于 application 且不 import node:/adapters）

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-3 · 新增 kind=design 登记用例与工具入口

**验收内容**：【新增 kind=design 登记用例与工具入口】验收：npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts 全绿；首次 registered_count=5、二次=0；空目录返回 0 且不谎报成功

**操作步骤**：
1. npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts 全绿
2. 首次 registered_count=5、二次=0
3. 空目录返回 0 且不谎报成功

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts 全绿；首次 registered_count=5、二次=0；空目录返回 0 且不谎报成功

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-4 · 投影逐份登记态到 reqboard_status

**验收内容**：【投影逐份登记态到 reqboard_status】验收：npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts 全绿；design_docs[] 的 on_disk/registered/confirmed 三态与磁盘+台账逐份一致

**操作步骤**：
1. npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts 全绿
2. design_docs[] 的 on_disk/registered/confirmed 三态与磁盘+台账逐份一致

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts 全绿；design_docs[] 的 on_disk/registered/confirmed 三态与磁盘+台账逐份一致

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-5 · 分化 G2 闸门文案并统一拒绝信封

**验收内容**：【分化 G2 闸门文案并统一拒绝信封】验收：npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts 全绿（含基线 2 个历史红例）；未登记消息含「未登记」+ reqboard_submit(kind=design)，待确认消息含「待确认」+ reqboard_ask_confirm，两串不相同；逐 code 断言含 —— 与 补齐：

**操作步骤**：
1. npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts 全绿（含基线 2 个历史红例）
2. 未登记消息含「未登记」+ reqboard_submit(kind=design)，待确认消息含「待确认」+ reqboard_ask_confirm，两串不相同
3. 逐 code 断言含 —— 与 补齐：

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts 全绿（含基线 2 个历史红例）；未登记消息含「未登记」+ reqboard_submit(kind=design)，待确认消息含「待确认」+ reqboard_ask_confirm，两串不相同；逐 code 断言含 —— 与 补齐：

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-6 · 弹框改非阻塞投递并加回执工具

**验收内容**：【弹框改非阻塞投递并加回执工具】验收：npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts 全绿；questions.ask 永不 resolve + 宽限 20ms → 返回 pending=true 且 ticket 非空、不抛错；作答后 reqboard_confirm_receipt(ticket) 返回 confirmed=true, advanced=true 且台账 confirmedAt 已写

**操作步骤**：
1. npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts 全绿
2. questions.ask 永不 resolve + 宽限 20ms → 返回 pending=true 且 ticket 非空、不抛错
3. 作答后 reqboard_confirm_receipt(ticket) 返回 confirmed=true, advanced=true 且台账 confirmedAt 已写

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts 全绿；questions.ask 永不 resolve + 宽限 20ms → 返回 pending=true 且 ticket 非空、不抛错；作答后 reqboard_confirm_receipt(ticket) 返回 confirmed=true, advanced=true 且台账 confirmedAt 已写

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-7 · 打零参绑定 patch

**验收内容**：【打零参绑定 patch】验收：npx vitest run tests/zero-arg-binding.test.ts 全绿且断言 patch 后 lib/process.js 绑定工厂为 (args = {})；在本窗口 run_code 内只调 tools.reqboard_status()（零参）→ 正常返回，输出无 binding arguments must be lossless JSON

**操作步骤**：
1. npx vitest run tests/zero-arg-binding.test.ts 全绿且断言 patch 后 lib/process.js 绑定工厂为 (args = {})
2. 在本窗口 run_code 内只调 tools.reqboard_status()（零参）→ 正常返回，输出无 binding arguments must be lossless JSON

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/zero-arg-binding.test.ts 全绿且断言 patch 后 lib/process.js 绑定工厂为 (args = {})；在本窗口 run_code 内只调 tools.reqboard_status()（零参）→ 正常返回，输出无 binding arguments must be lossless JSON

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-8 · 设计提示词写明登记命令

**验收内容**：【设计提示词写明登记命令】验收：node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs 退出 0；npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts 全绿；design/light 与 heavy 文本含 reqboard_submit(kind=design)，且不含「落盘即产物」旧断言

**操作步骤**：
1. node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs 退出 0
2. npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts 全绿
3. design/light 与 heavy 文本含 reqboard_submit(kind=design)，且不含「落盘即产物」旧断言

**预期结果**：按上述步骤执行后满足验收标准：node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs 退出 0；npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts 全绿；design/light 与 heavy 文本含 reqboard_submit(kind=design)，且不含「落盘即产物」旧断言

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-9 · 实现断点常驻与续跑输入包

**验收内容**：【实现断点常驻与续跑输入包】验收：npx vitest run tests/interruption-checkpoint.test.ts 全绿：只交棒 → 台账 interruption.reason==='checkpoint' 且 pendingAction 非空；喂 turn/end 且 reason.kind='error' → reason 变 error:UPSTREAM_STREAM_IDLE:…；重建输入包含 ## 断点 与 pendingAction；老需求无字段 → 输入包逐字节不变

**操作步骤**：
1. npx vitest run tests/interruption-checkpoint.test.ts 全绿：只交棒 → 台账 interruption.reason==='checkpoint' 且 pendingAction 非空
2. 喂 turn/end 且 reason.kind='error' → reason 变 error:UPSTREAM_STREAM_IDLE:…
3. 重建输入包含 ## 断点 与 pendingAction
4. 老需求无字段 → 输入包逐字节不变

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/interruption-checkpoint.test.ts 全绿：只交棒 → 台账 interruption.reason==='checkpoint' 且 pendingAction 非空；喂 turn/end 且 reason.kind='error' → reason 变 error:UPSTREAM_STREAM_IDLE:…；重建输入包含 ## 断点 与 pendingAction；老需求无字段 → 输入包逐字节不变

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-10 · 立项降级路径不丢文档位置

**验收内容**：【立项降级路径不丢文档位置】验收：npx vitest run tests/create-doc-location.test.ts 全绿；不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/' 且 defaults_used 含 doc_location、台账 docBasePath 同值；传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成；返回 status 与台账一致

**操作步骤**：
1. npx vitest run tests/create-doc-location.test.ts 全绿
2. 不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/' 且 defaults_used 含 doc_location、台账 docBasePath 同值
3. 传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成
4. 返回 status 与台账一致

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/create-doc-location.test.ts 全绿；不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/' 且 defaults_used 含 doc_location、台账 docBasePath 同值；传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成；返回 status 与台账一致

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-11 · pm 弹框统一来源标志

**验收内容**：【pm 弹框统一来源标志】验收：npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts 全绿；ask_confirm / accept_sheet / capture 四问 / 失败处置四处 AskQuestion.header 均以 📋 PM · 开头；宿主原生 ask_user_question 不带该前缀

**操作步骤**：
1. npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts 全绿
2. ask_confirm / accept_sheet / capture 四问 / 失败处置四处 AskQuestion.header 均以 📋 PM · 开头
3. 宿主原生 ask_user_question 不带该前缀

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts 全绿；ask_confirm / accept_sheet / capture 四问 / 失败处置四处 AskQuestion.header 均以 📋 PM · 开头；宿主原生 ask_user_question 不带该前缀

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-12 · 组合根瘦身使尺寸门禁转绿

**验收内容**：【组合根瘦身使尺寸门禁转绿】验收：npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts 全绿；wc -l packages/web/dsh-pmboard/src/index.ts ≤ 400；nodeIsolationEnabled 仍可从 src/index.ts import 且行为不变

**操作步骤**：
1. npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts 全绿
2. wc -l packages/web/dsh-pmboard/src/index.ts ≤ 400
3. nodeIsolationEnabled 仍可从 src/index.ts import 且行为不变

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts 全绿；wc -l packages/web/dsh-pmboard/src/index.ts ≤ 400；nodeIsolationEnabled 仍可从 src/index.ts import 且行为不变

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-13 · 迁移兼容卡与 E2E 复跑

**验收内容**：【迁移兼容卡与 E2E 复跑】验收：npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts 全绿；E2E 一次通过且全程无 REQBOARD_MISSING_ARTIFACT；legacy（artifacts 空）需求仍放行；npx vitest run 失败集合 ⊆ 基线且不新增失败

**操作步骤**：
1. npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts 全绿
2. E2E 一次通过且全程无 REQBOARD_MISSING_ARTIFACT
3. legacy（artifacts 空）需求仍放行
4. npx vitest run 失败集合 ⊆ 基线且不新增失败

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts 全绿；E2E 一次通过且全程无 REQBOARD_MISSING_ARTIFACT；legacy（artifacts 空）需求仍放行；npx vitest run 失败集合 ⊆ 基线且不新增失败

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-14 · 定义新契约类型与端口·研发

**验收内容**：【定义新契约类型与端口·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts 全绿；npx tsc --noEmit -p tsconfig.json 错误数 ≤ 基线 23 且新增文件 0 报错；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-8cd37e.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts 全绿
2. npx tsc --noEmit -p tsconfig.json 错误数 ≤ 基线 23 且新增文件 0 报错
3. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-8cd37e.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts 全绿；npx tsc --noEmit -p tsconfig.json 错误数 ≤ 基线 23 且新增文件 0 报错；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-8cd37e.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-15 · 定义新契约类型与端口·联调

**验收内容**：【定义新契约类型与端口·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-0f05c1-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-0f05c1-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-0f05c1-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-16 · 定义新契约类型与端口·复核

**验收内容**：【定义新契约类型与端口·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-c579d7-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-c579d7-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-c579d7-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-17 · 定义新契约类型与端口·测试

**验收内容**：【定义新契约类型与端口·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4c35b9-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4c35b9-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4c35b9-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-18 · 打零参绑定 patch·研发

**验收内容**：【打零参绑定 patch·研发】验收：改动已落盘：本轮执行内把零参绑定守护测试写入 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts，并跑 `cd packages/web/dsh-pmboard && npx vitest run tests/zero-arg-binding.test.ts` 全绿（贴命令与输出摘要）；已有 patch 与 package.json 登记保持不变

**操作步骤**：
1. 改动已落盘：本轮执行内把零参绑定守护测试写入 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts，并跑 `cd packages/web/dsh-pmboard && npx vitest run tests/zero-arg-binding.test.ts` 全绿（贴命令与输出摘要）
2. 已有 patch 与 package.json 登记保持不变

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘：本轮执行内把零参绑定守护测试写入 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts，并跑 `cd packages/web/dsh-pmboard && npx vitest run tests/zero-arg-binding.test.ts` 全绿（贴命令与输出摘要）；已有 patch 与 package.json 登记保持不变

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-19 · 打零参绑定 patch·联调

**验收内容**：【打零参绑定 patch·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-db23dc-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-db23dc-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-db23dc-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-20 · 打零参绑定 patch·复核

**验收内容**：【打零参绑定 patch·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-9abb40-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-9abb40-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-9abb40-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-21 · 打零参绑定 patch·测试

**验收内容**：【打零参绑定 patch·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-0d19e8-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-0d19e8-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-0d19e8-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-22 · 下沉产物发现核心并薄壳化 ArtifactSync·研发

**验收内容**：【下沉产物发现核心并薄壳化 ArtifactSync·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/sync-artifacts.test.ts 全绿且既有断言逐字不变；npx vitest run tests/layer-boundary.test.ts 不新增越界（新增文件位于 application 且不 import node:/adapters）；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-a394e1.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/sync-artifacts.test.ts 全绿且既有断言逐字不变
2. npx vitest run tests/layer-boundary.test.ts 不新增越界（新增文件位于 application 且不 import node:/adapters）
3. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-a394e1.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/sync-artifacts.test.ts 全绿且既有断言逐字不变；npx vitest run tests/layer-boundary.test.ts 不新增越界（新增文件位于 application 且不 import node:/adapters）；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-a394e1.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-23 · 下沉产物发现核心并薄壳化 ArtifactSync·联调

**验收内容**：【下沉产物发现核心并薄壳化 ArtifactSync·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-34191e-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-34191e-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-34191e-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-24 · 下沉产物发现核心并薄壳化 ArtifactSync·复核

**验收内容**：【下沉产物发现核心并薄壳化 ArtifactSync·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-222d3d-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-222d3d-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-222d3d-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-25 · 下沉产物发现核心并薄壳化 ArtifactSync·测试

**验收内容**：【下沉产物发现核心并薄壳化 ArtifactSync·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e5d2e6-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e5d2e6-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e5d2e6-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-26 · 新增 kind=design 登记用例与工具入口·研发

**验收内容**：【新增 kind=design 登记用例与工具入口·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts 全绿；首次 registered_count=5、二次=0；空目录返回 0 且不谎报成功；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-097478.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts 全绿
2. 首次 registered_count=5、二次=0
3. 空目录返回 0 且不谎报成功
4. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-097478.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts 全绿；首次 registered_count=5、二次=0；空目录返回 0 且不谎报成功；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-097478.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-27 · 新增 kind=design 登记用例与工具入口·联调

**验收内容**：【新增 kind=design 登记用例与工具入口·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-52d7fe-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-52d7fe-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-52d7fe-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-28 · 新增 kind=design 登记用例与工具入口·复核

**验收内容**：【新增 kind=design 登记用例与工具入口·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-d76da9-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-d76da9-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-d76da9-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-29 · 新增 kind=design 登记用例与工具入口·测试

**验收内容**：【新增 kind=design 登记用例与工具入口·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4b15cf-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4b15cf-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4b15cf-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-30 · 投影逐份登记态到 reqboard_status·研发

**验收内容**：【投影逐份登记态到 reqboard_status·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts 全绿；design_docs[] 的 on_disk/registered/confirmed 三态与磁盘+台账逐份一致；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-02e4ae.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts 全绿
2. design_docs[] 的 on_disk/registered/confirmed 三态与磁盘+台账逐份一致
3. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-02e4ae.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts 全绿；design_docs[] 的 on_disk/registered/confirmed 三态与磁盘+台账逐份一致；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-02e4ae.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-31 · 投影逐份登记态到 reqboard_status·联调

**验收内容**：【投影逐份登记态到 reqboard_status·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-788302-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-788302-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-788302-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-32 · 投影逐份登记态到 reqboard_status·复核

**验收内容**：【投影逐份登记态到 reqboard_status·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-14057a-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-14057a-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-14057a-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-33 · 投影逐份登记态到 reqboard_status·测试

**验收内容**：【投影逐份登记态到 reqboard_status·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-01bd5b-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-01bd5b-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-01bd5b-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-34 · 分化 G2 闸门文案并统一拒绝信封·研发

**验收内容**：【分化 G2 闸门文案并统一拒绝信封·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts 全绿（含基线 2 个历史红例）；未登记消息含「未登记」+ reqboard_submit(kind=design)，待确认消息含「待确认」+ reqboard_ask_confirm，两串不相同；逐 code 断言含 —— 与 补齐：；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-114ef1.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts 全绿（含基线 2 个历史红例）
2. 未登记消息含「未登记」+ reqboard_submit(kind=design)，待确认消息含「待确认」+ reqboard_ask_confirm，两串不相同
3. 逐 code 断言含 —— 与 补齐：
4. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-114ef1.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts 全绿（含基线 2 个历史红例）；未登记消息含「未登记」+ reqboard_submit(kind=design)，待确认消息含「待确认」+ reqboard_ask_confirm，两串不相同；逐 code 断言含 —— 与 补齐：；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-114ef1.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-35 · 分化 G2 闸门文案并统一拒绝信封·联调

**验收内容**：【分化 G2 闸门文案并统一拒绝信封·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-dde78e-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-dde78e-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-dde78e-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-36 · 分化 G2 闸门文案并统一拒绝信封·复核

**验收内容**：【分化 G2 闸门文案并统一拒绝信封·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-792c94-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-792c94-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-792c94-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-37 · 分化 G2 闸门文案并统一拒绝信封·测试

**验收内容**：【分化 G2 闸门文案并统一拒绝信封·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-44b8c6-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-44b8c6-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-44b8c6-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-38 · 弹框改非阻塞投递并加回执工具·研发

**验收内容**：【弹框改非阻塞投递并加回执工具·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts 全绿；questions.ask 永不 resolve + 宽限 20ms → 返回 pending=true 且 ticket 非空、不抛错；作答后 reqboard_confirm_receipt(ticket) 返回 confirmed=true, advanced=true 且台账 confirmedAt 已写；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-e932fc.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts 全绿
2. questions.ask 永不 resolve + 宽限 20ms → 返回 pending=true 且 ticket 非空、不抛错
3. 作答后 reqboard_confirm_receipt(ticket) 返回 confirmed=true, advanced=true 且台账 confirmedAt 已写
4. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-e932fc.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts 全绿；questions.ask 永不 resolve + 宽限 20ms → 返回 pending=true 且 ticket 非空、不抛错；作答后 reqboard_confirm_receipt(ticket) 返回 confirmed=true, advanced=true 且台账 confirmedAt 已写；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-e932fc.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-39 · 弹框改非阻塞投递并加回执工具·联调

**验收内容**：【弹框改非阻塞投递并加回执工具·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-74ab2d-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-74ab2d-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-74ab2d-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-40 · 弹框改非阻塞投递并加回执工具·复核

**验收内容**：【弹框改非阻塞投递并加回执工具·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-51fc46-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-51fc46-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-51fc46-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-41 · 弹框改非阻塞投递并加回执工具·测试

**验收内容**：【弹框改非阻塞投递并加回执工具·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4d6d70-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4d6d70-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4d6d70-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-42 · 设计提示词写明登记命令·研发

**验收内容**：【设计提示词写明登记命令·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs 退出 0；npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts 全绿；design/light 与 heavy 文本含 reqboard_submit(kind=design)，且不含「落盘即产物」旧断言；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-5b02db.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs 退出 0
2. npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts 全绿
3. design/light 与 heavy 文本含 reqboard_submit(kind=design)，且不含「落盘即产物」旧断言
4. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-5b02db.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs 退出 0；npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts 全绿；design/light 与 heavy 文本含 reqboard_submit(kind=design)，且不含「落盘即产物」旧断言；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-5b02db.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-43 · 设计提示词写明登记命令·联调

**验收内容**：【设计提示词写明登记命令·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e80e8b-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e80e8b-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e80e8b-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-44 · 设计提示词写明登记命令·复核

**验收内容**：【设计提示词写明登记命令·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e897e0-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e897e0-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e897e0-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-45 · 设计提示词写明登记命令·测试

**验收内容**：【设计提示词写明登记命令·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-2c7e2e-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-2c7e2e-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-2c7e2e-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-46 · 实现断点常驻与续跑输入包·研发

**验收内容**：【实现断点常驻与续跑输入包·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/interruption-checkpoint.test.ts 全绿：只交棒 → 台账 interruption.reason==='checkpoint' 且 pendingAction 非空；喂 turn/end 且 reason.kind='error' → reason 变 error:UPSTREAM_STREAM_IDLE:…；重建输入包含 ## 断点 与 pendingAction；老需求无字段 → 输入包逐字节不变；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-14191c.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/interruption-checkpoint.test.ts 全绿：只交棒 → 台账 interruption.reason==='checkpoint' 且 pendingAction 非空
2. 喂 turn/end 且 reason.kind='error' → reason 变 error:UPSTREAM_STREAM_IDLE:…
3. 重建输入包含 ## 断点 与 pendingAction
4. 老需求无字段 → 输入包逐字节不变
5. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-14191c.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/interruption-checkpoint.test.ts 全绿：只交棒 → 台账 interruption.reason==='checkpoint' 且 pendingAction 非空；喂 turn/end 且 reason.kind='error' → reason 变 error:UPSTREAM_STREAM_IDLE:…；重建输入包含 ## 断点 与 pendingAction；老需求无字段 → 输入包逐字节不变；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-14191c.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-47 · 实现断点常驻与续跑输入包·联调

**验收内容**：【实现断点常驻与续跑输入包·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-6a3070-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-6a3070-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-6a3070-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-48 · 实现断点常驻与续跑输入包·复核

**验收内容**：【实现断点常驻与续跑输入包·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b89d61-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b89d61-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b89d61-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-49 · 实现断点常驻与续跑输入包·测试

**验收内容**：【实现断点常驻与续跑输入包·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a85c7b-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a85c7b-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a85c7b-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-50 · 立项降级路径不丢文档位置·研发

**验收内容**：【立项降级路径不丢文档位置·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/create-doc-location.test.ts 全绿；不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/' 且 defaults_used 含 doc_location、台账 docBasePath 同值；传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成；返回 status 与台账一致；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-b1f61e.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/create-doc-location.test.ts 全绿
2. 不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/' 且 defaults_used 含 doc_location、台账 docBasePath 同值
3. 传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成
4. 返回 status 与台账一致
5. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-b1f61e.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/create-doc-location.test.ts 全绿；不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/' 且 defaults_used 含 doc_location、台账 docBasePath 同值；传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成；返回 status 与台账一致；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-b1f61e.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-51 · 立项降级路径不丢文档位置·联调

**验收内容**：【立项降级路径不丢文档位置·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-d52c67-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-d52c67-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-d52c67-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-52 · 立项降级路径不丢文档位置·复核

**验收内容**：【立项降级路径不丢文档位置·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-8e8f83-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-8e8f83-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-8e8f83-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-53 · 立项降级路径不丢文档位置·测试

**验收内容**：【立项降级路径不丢文档位置·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b1b27b-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b1b27b-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b1b27b-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-54 · pm 弹框统一来源标志·研发

**验收内容**：【pm 弹框统一来源标志·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts 全绿；ask_confirm / accept_sheet / capture 四问 / 失败处置四处 AskQuestion.header 均以 📋 PM · 开头；宿主原生 ask_user_question 不带该前缀；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-22628e.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts 全绿
2. ask_confirm / accept_sheet / capture 四问 / 失败处置四处 AskQuestion.header 均以 📋 PM · 开头
3. 宿主原生 ask_user_question 不带该前缀
4. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-22628e.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts 全绿；ask_confirm / accept_sheet / capture 四问 / 失败处置四处 AskQuestion.header 均以 📋 PM · 开头；宿主原生 ask_user_question 不带该前缀；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-22628e.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-55 · pm 弹框统一来源标志·联调

**验收内容**：【pm 弹框统一来源标志·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-f4d6b1-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-f4d6b1-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-f4d6b1-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-56 · pm 弹框统一来源标志·复核

**验收内容**：【pm 弹框统一来源标志·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-3d59ae-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-3d59ae-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-3d59ae-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-57 · pm 弹框统一来源标志·测试

**验收内容**：【pm 弹框统一来源标志·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-456a3d-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-456a3d-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-456a3d-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-58 · 组合根瘦身使尺寸门禁转绿·研发

**验收内容**：【组合根瘦身使尺寸门禁转绿·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts 全绿；wc -l packages/web/dsh-pmboard/src/index.ts ≤ 400；nodeIsolationEnabled 仍可从 src/index.ts import 且行为不变；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-c396e9.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts 全绿
2. wc -l packages/web/dsh-pmboard/src/index.ts ≤ 400
3. nodeIsolationEnabled 仍可从 src/index.ts import 且行为不变
4. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-c396e9.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts 全绿；wc -l packages/web/dsh-pmboard/src/index.ts ≤ 400；nodeIsolationEnabled 仍可从 src/index.ts import 且行为不变；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-c396e9.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-59 · 组合根瘦身使尺寸门禁转绿·联调

**验收内容**：【组合根瘦身使尺寸门禁转绿·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a45bcd-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a45bcd-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a45bcd-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-60 · 组合根瘦身使尺寸门禁转绿·复核

**验收内容**：【组合根瘦身使尺寸门禁转绿·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-57bfa5-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-57bfa5-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-57bfa5-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-61 · 组合根瘦身使尺寸门禁转绿·测试

**验收内容**：【组合根瘦身使尺寸门禁转绿·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b36caf-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b36caf-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b36caf-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-62 · 迁移兼容卡与 E2E 复跑·研发

**验收内容**：【迁移兼容卡与 E2E 复跑·研发】验收：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts 全绿；E2E 一次通过且全程无 REQBOARD_MISSING_ARTIFACT；legacy（artifacts 空）需求仍放行；npx vitest run 失败集合 ⊆ 基线且不新增失败；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-3d5f80.md

**操作步骤**：
1. 本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts 全绿
2. E2E 一次通过且全程无 REQBOARD_MISSING_ARTIFACT
3. legacy（artifacts 空）需求仍放行
4. npx vitest run 失败集合 ⊆ 基线且不新增失败
5. 本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-3d5f80.md

**预期结果**：按上述步骤执行后满足验收标准：本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts 全绿；E2E 一次通过且全程无 REQBOARD_MISSING_ARTIFACT；legacy（artifacts 空）需求仍放行；npx vitest run 失败集合 ⊆ 基线且不新增失败；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-3d5f80.md

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-63 · 迁移兼容卡与 E2E 复跑·联调

**验收内容**：【迁移兼容卡与 E2E 复跑·联调】验收：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-87ca1c-integrate.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 接口联调通过：给出请求样例、期望响应与实际返回，三者一致
2. 并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-87ca1c-integrate.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-87ca1c-integrate.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-64 · 迁移兼容卡与 E2E 复跑·复核

**验收内容**：【迁移兼容卡与 E2E 复跑·复核】验收：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-55b8c4-review.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）
2. 并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-55b8c4-review.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-55b8c4-review.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-65 · 迁移兼容卡与 E2E 复跑·测试

**验收内容**：【迁移兼容卡与 E2E 复跑·测试】验收：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-5a41f7-test.md，在 filesChanged 中列出该文件

**操作步骤**：
1. 目标命令输出全绿（贴命令与结果摘要）
2. 并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-5a41f7-test.md，在 filesChanged 中列出该文件

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-5a41f7-test.md，在 filesChanged 中列出该文件

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-66 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-67 · 需求级验收

**验收内容**：孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——packages/web/dsh-pmboard/tests/confirm-evidence.test.ts、packages/web/dsh-pmboard/tests/design-registration.test.ts、packages/web/dsh-pmboard/tests/pm-question-badge.test.ts、packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts。请补 serves: 声明，或说明为何无需映射。

**操作步骤**：
1. 孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——packages/web/dsh-pmboard/tests/confirm-evidence.test.ts、packages/web/dsh-pmboard/tests/design-registration.test.ts、packages/web/dsh-pmboard/tests/pm-question-badge.test.ts、packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts。请补 serves: 声明，或说明为何无需映射。

**预期结果**：按上述步骤执行后满足验收标准：孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——packages/web/dsh-pmboard/tests/confirm-evidence.test.ts、packages/web/dsh-pmboard/tests/design-registration.test.ts、packages/web/dsh-pmboard/tests/pm-question-badge.test.ts、packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts。请补 serves: 声明，或说明为何无需映射。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-69 · 需求级验收

**验收内容**：E2E 覆盖：**有**（存在跨组件跑通完整业务链路的场景用例）

**操作步骤**：
1. E2E 覆盖：**有**（存在跨组件跑通完整业务链路的场景用例）

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**有**（存在跨组件跑通完整业务链路的场景用例）

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

## 2. 测试报告

- 验收三件套（可复跑）：cd packages/web/dsh-pmboard && npx vitest run e2e-design-handoff migration consistency zero-arg-binding contract-shapes → 5 files / 37 tests 全绿，exit 0
- 类型门禁：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 23 条，与改动前基线同为 23；新增/改动文件 0 报错
- 全量回归：cd packages/web/dsh-pmboard && npx vitest run → 5 文件 / 6 用例失败（157 文件 1857 用例通过）；改动前基线 7 文件 / 9 用例 → 失败集合 ⊆ 基线、无新增；链另修好 design-completeness-gate ×2 与 size-budget ×1
- 零参实调（FR-4 / A4）：run_code 里对 tools.reqboard_status 不带参数调用 → 正常返回看板状态，未出现 binding arguments must be lossless JSON
- 交付核对全文（命令 + 输出 + 基线对比 + 修正记录）：docs/requirements/REQ-260924213231-b1c4/tests/00-交付核对-命令与输出.md
- 评审索引（含自查发现的 2 处偏离与处置）：docs/requirements/REQ-260924213231-b1c4/reviews/00-评审索引.md
- 逐子卡证据（39 份联调/复核/测试记录）：docs/requirements/REQ-260924213231-b1c4/evidence/；9 类文档：65 张任务卡 + 14 份 reviews + 14 份 tests
- 推进留痕（13 张卡逐事件，末条 ROLLUP ok）：docs/requirements/REQ-260924213231-b1c4/advance-log.md
- 交付检查点提交：ec69a758（基线 9e5ebf60）——git show --stat ec69a758 可复核
- FR-5 提示词写明登记命令与触发者：packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md
- FR-5 守护测试：packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts、packages/web/dsh-pmboard/tests/prompt-baseline.test.ts 全绿
- FR-8 pm 弹框来源标志：packages/web/dsh-pmboard/tests/pm-question-badge.test.ts 全绿
- FR-6 断点常驻与续跑：packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts 全绿
- FR-7 立项降级不丢文档位置：packages/web/dsh-pmboard/tests/create-doc-location.test.ts 全绿
- FR-3 弹框非阻塞 + 回执：packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts 全绿
- FR-1/FR-2 登记与闸门文案：packages/web/dsh-pmboard/tests/design-registration.test.ts、packages/web/dsh-pmboard/tests/design-gate-messages.test.ts、packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts 全绿
- 运行提示（人工核验 A1/A2/A3/A6 前必做）：:13080 当前进程仍是改动前代码（tsx 直载），需重启 profile 才加载本次交付

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 定义新契约类型与端口 | ⬜ 待验收 |  |  |
| v1-2 | 下沉产物发现核心并薄壳化 ArtifactSync | ⬜ 待验收 |  |  |
| v1-3 | 新增 kind=design 登记用例与工具入口 | ⬜ 待验收 |  |  |
| v1-4 | 投影逐份登记态到 reqboard_status | ⬜ 待验收 |  |  |
| v1-5 | 分化 G2 闸门文案并统一拒绝信封 | ⬜ 待验收 |  |  |
| v1-6 | 弹框改非阻塞投递并加回执工具 | ⬜ 待验收 |  |  |
| v1-7 | 打零参绑定 patch | ⬜ 待验收 |  |  |
| v1-8 | 设计提示词写明登记命令 | ⬜ 待验收 |  |  |
| v1-9 | 实现断点常驻与续跑输入包 | ⬜ 待验收 |  |  |
| v1-10 | 立项降级路径不丢文档位置 | ⬜ 待验收 |  |  |
| v1-11 | pm 弹框统一来源标志 | ⬜ 待验收 |  |  |
| v1-12 | 组合根瘦身使尺寸门禁转绿 | ⬜ 待验收 |  |  |
| v1-13 | 迁移兼容卡与 E2E 复跑 | ⬜ 待验收 |  |  |
| v1-14 | 定义新契约类型与端口·研发 | ⬜ 待验收 |  |  |
| v1-15 | 定义新契约类型与端口·联调 | ⬜ 待验收 |  |  |
| v1-16 | 定义新契约类型与端口·复核 | ⬜ 待验收 |  |  |
| v1-17 | 定义新契约类型与端口·测试 | ⬜ 待验收 |  |  |
| v1-18 | 打零参绑定 patch·研发 | ⬜ 待验收 |  |  |
| v1-19 | 打零参绑定 patch·联调 | ⬜ 待验收 |  |  |
| v1-20 | 打零参绑定 patch·复核 | ⬜ 待验收 |  |  |
| v1-21 | 打零参绑定 patch·测试 | ⬜ 待验收 |  |  |
| v1-22 | 下沉产物发现核心并薄壳化 ArtifactSync·研发 | ⬜ 待验收 |  |  |
| v1-23 | 下沉产物发现核心并薄壳化 ArtifactSync·联调 | ⬜ 待验收 |  |  |
| v1-24 | 下沉产物发现核心并薄壳化 ArtifactSync·复核 | ⬜ 待验收 |  |  |
| v1-25 | 下沉产物发现核心并薄壳化 ArtifactSync·测试 | ⬜ 待验收 |  |  |
| v1-26 | 新增 kind=design 登记用例与工具入口·研发 | ⬜ 待验收 |  |  |
| v1-27 | 新增 kind=design 登记用例与工具入口·联调 | ⬜ 待验收 |  |  |
| v1-28 | 新增 kind=design 登记用例与工具入口·复核 | ⬜ 待验收 |  |  |
| v1-29 | 新增 kind=design 登记用例与工具入口·测试 | ⬜ 待验收 |  |  |
| v1-30 | 投影逐份登记态到 reqboard_status·研发 | ⬜ 待验收 |  |  |
| v1-31 | 投影逐份登记态到 reqboard_status·联调 | ⬜ 待验收 |  |  |
| v1-32 | 投影逐份登记态到 reqboard_status·复核 | ⬜ 待验收 |  |  |
| v1-33 | 投影逐份登记态到 reqboard_status·测试 | ⬜ 待验收 |  |  |
| v1-34 | 分化 G2 闸门文案并统一拒绝信封·研发 | ⬜ 待验收 |  |  |
| v1-35 | 分化 G2 闸门文案并统一拒绝信封·联调 | ⬜ 待验收 |  |  |
| v1-36 | 分化 G2 闸门文案并统一拒绝信封·复核 | ⬜ 待验收 |  |  |
| v1-37 | 分化 G2 闸门文案并统一拒绝信封·测试 | ⬜ 待验收 |  |  |
| v1-38 | 弹框改非阻塞投递并加回执工具·研发 | ⬜ 待验收 |  |  |
| v1-39 | 弹框改非阻塞投递并加回执工具·联调 | ⬜ 待验收 |  |  |
| v1-40 | 弹框改非阻塞投递并加回执工具·复核 | ⬜ 待验收 |  |  |
| v1-41 | 弹框改非阻塞投递并加回执工具·测试 | ⬜ 待验收 |  |  |
| v1-42 | 设计提示词写明登记命令·研发 | ⬜ 待验收 |  |  |
| v1-43 | 设计提示词写明登记命令·联调 | ⬜ 待验收 |  |  |
| v1-44 | 设计提示词写明登记命令·复核 | ⬜ 待验收 |  |  |
| v1-45 | 设计提示词写明登记命令·测试 | ⬜ 待验收 |  |  |
| v1-46 | 实现断点常驻与续跑输入包·研发 | ⬜ 待验收 |  |  |
| v1-47 | 实现断点常驻与续跑输入包·联调 | ⬜ 待验收 |  |  |
| v1-48 | 实现断点常驻与续跑输入包·复核 | ⬜ 待验收 |  |  |
| v1-49 | 实现断点常驻与续跑输入包·测试 | ⬜ 待验收 |  |  |
| v1-50 | 立项降级路径不丢文档位置·研发 | ⬜ 待验收 |  |  |
| v1-51 | 立项降级路径不丢文档位置·联调 | ⬜ 待验收 |  |  |
| v1-52 | 立项降级路径不丢文档位置·复核 | ⬜ 待验收 |  |  |
| v1-53 | 立项降级路径不丢文档位置·测试 | ⬜ 待验收 |  |  |
| v1-54 | pm 弹框统一来源标志·研发 | ⬜ 待验收 |  |  |
| v1-55 | pm 弹框统一来源标志·联调 | ⬜ 待验收 |  |  |
| v1-56 | pm 弹框统一来源标志·复核 | ⬜ 待验收 |  |  |
| v1-57 | pm 弹框统一来源标志·测试 | ⬜ 待验收 |  |  |
| v1-58 | 组合根瘦身使尺寸门禁转绿·研发 | ⬜ 待验收 |  |  |
| v1-59 | 组合根瘦身使尺寸门禁转绿·联调 | ⬜ 待验收 |  |  |
| v1-60 | 组合根瘦身使尺寸门禁转绿·复核 | ⬜ 待验收 |  |  |
| v1-61 | 组合根瘦身使尺寸门禁转绿·测试 | ⬜ 待验收 |  |  |
| v1-62 | 迁移兼容卡与 E2E 复跑·研发 | ⬜ 待验收 |  |  |
| v1-63 | 迁移兼容卡与 E2E 复跑·联调 | ⬜ 待验收 |  |  |
| v1-64 | 迁移兼容卡与 E2E 复跑·复核 | ⬜ 待验收 |  |  |
| v1-65 | 迁移兼容卡与 E2E 复跑·测试 | ⬜ 待验收 |  |  |
| v1-66 | 需求级验收 | ⬜ 待验收 |  |  |
| v1-67 | 需求级验收 | ⬜ 待验收 |  |  |
| v1-69 | 需求级验收 | ⬜ 待验收 |  |  |
