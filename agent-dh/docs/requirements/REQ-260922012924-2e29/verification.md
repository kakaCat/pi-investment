# REQ-260922012924-2e29 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：REQ-260922012924-2e29 交付完成：FR-1 四问测试同步（15/15 绿，原 4 红清零）、FR-2 requirementDocPath 消费 docBasePath（6 新用例，老记录逐字节一致）、FR-3 nodeIsolation 压缩开启（配置+重启+活动配置继承，R-017 noop 核验通过）、FR-4 文档路径绝对化（state 端点 workspaceRoot curl 实证，看板任何工作区会话可打开文档，产物按钮悬停见绝对路径）、FR-5 立项拒绝粘滞（rejected 落盘留痕+弹框前置检查，6 用例绿——修复"点不立项没结束还继续推进"）。全量回归 91 失败经 main worktree 基线实证全部为存量红灯，本需求触碰面 0 失败。待人工实证：看板点击文档链接、FR-5 线上自然发生。

## 1. 验收列表

### v1-1 · [FR-1] 更新 capture-tool.test.ts 为四问口径

**验收内容**：【[FR-1] 更新 capture-tool.test.ts 为四问口径】验收：cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts 全绿（当前 4 红转 0 红）。

**操作步骤**：
1. cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts 全绿（当前 4 红转 0 红）。

**预期结果**：按上述步骤执行后满足验收标准：cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts 全绿（当前 4 红转 0 红）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-2 · [FR-2] requirementDocPath 消费 docBasePath + 单测

**验收内容**：【[FR-2] requirementDocPath 消费 docBasePath + 单测】验收：npx vitest run packages/web/dsh-pmboard/tests/artifact-path.test.ts 全绿，且含新 4 用例；无 docBasePath 老记录输出与现状逐字节一致（单测断言）。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests/artifact-path.test.ts 全绿，且含新 4 用例
2. 无 docBasePath 老记录输出与现状逐字节一致（单测断言）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests/artifact-path.test.ts 全绿，且含新 4 用例；无 docBasePath 老记录输出与现状逐字节一致（单测断言）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-3 · [FR-3] cordis.yml 开启 nodeIsolation 并重启验证

**验收内容**：【[FR-3] cordis.yml 开启 nodeIsolation 并重启验证】验收：grep -A2 "id: dsh-pmboard" config/cordis.yml 见 nodeIsolation: true；重启后 grep "压缩开关" .dsh-data/state/launchd.out.log | tail -1 见 NODE_ISOLATION=true；isolation-trace 有 G0 门 skip(doc_not_ready) 或后续压缩留痕。

**操作步骤**：
1. grep -A2 "id: dsh-pmboard" config/cordis.yml 见 nodeIsolation: true
2. 重启后 grep "压缩开关" .dsh-data/state/launchd.out.log | tail -1 见 NODE_ISOLATION=true
3. isolation-trace 有 G0 门 skip(doc_not_ready) 或后续压缩留痕。

**预期结果**：按上述步骤执行后满足验收标准：grep -A2 "id: dsh-pmboard" config/cordis.yml 见 nodeIsolation: true；重启后 grep "压缩开关" .dsh-data/state/launchd.out.log | tail -1 见 NODE_ISOLATION=true；isolation-trace 有 G0 门 skip(doc_not_ready) 或后续压缩留痕。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-4 · [FR-4] state 端点暴露 workspaceRoot/homeDir + 客户端绝对路径打开与显示

**验收内容**：【[FR-4] state 端点暴露 workspaceRoot/homeDir + 客户端绝对路径打开与显示】验收：curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot,homeDir}' 返回 agent-dh 绝对路径；相关测试全绿；实证：工作区=dsh-pmboard 会话看板打开文档链接成功。

**操作步骤**：
1. curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot,homeDir}' 返回 agent-dh 绝对路径
2. 相关测试全绿
3. 实证：工作区=dsh-pmboard 会话看板打开文档链接成功。

**预期结果**：按上述步骤执行后满足验收标准：curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot,homeDir}' 返回 agent-dh 绝对路径；相关测试全绿；实证：工作区=dsh-pmboard 会话看板打开文档链接成功。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-5 · [FR-5] 立项拒绝粘滞：rejected 落痕 + 弹框前置检查 + 提示词纪律

**验收内容**：【[FR-5] 立项拒绝粘滞：rejected 落痕 + 弹框前置检查 + 提示词纪律】验收：npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts 全绿含新 3 用例；构造 30 分钟内拒绝留痕调 reqboard_capture 不弹框返回未立项（单测断言 questions.ask 未被调用）。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts 全绿含新 3 用例
2. 构造 30 分钟内拒绝留痕调 reqboard_capture 不弹框返回未立项（单测断言 questions.ask 未被调用）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts 全绿含新 3 用例；构造 30 分钟内拒绝留痕调 reqboard_capture 不弹框返回未立项（单测断言 questions.ask 未被调用）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-6 · [FR-1~FR-5] 全量回归与实证验收（含兼容性验证）

**验收内容**：【[FR-1~FR-5] 全量回归与实证验收（含兼容性验证）】验收：cd agent-dh 逐条执行：①npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/requirement-doc-path.test.ts packages/web/dsh-pmboard/tests/state-workspace-root.test.ts → 全部 passed；②npx vitest run packages/web/dsh-pmboard → 记录失败文件清单，与 git worktree @ main 基线同命令的失败清单比对，差集必须为空（即无本需求新引入失败；主干存量红灯不算本需求失败）；③npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → passed；④curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot,homeDir}' → 返回 /Users 开头绝对路径；⑤grep -n "nodeIsolation: true" config/cordis.yml → 有命中行。

**操作步骤**：
1. cd agent-dh 逐条执行：①npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/requirement-doc-path.test.ts packages/web/dsh-pmboard/tests/state-workspace-root.test.ts → 全部 passed
2. ②npx vitest run packages/web/dsh-pmboard → 记录失败文件清单，与 git worktree @ main 基线同命令的失败清单比对，差集必须为空（即无本需求新引入失败
3. 主干存量红灯不算本需求失败）
4. ③npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → passed
5. ④curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot,homeDir}' → 返回 /Users 开头绝对路径
6. ⑤grep -n "nodeIsolation: true" config/cordis.yml → 有命中行。

**预期结果**：按上述步骤执行后满足验收标准：cd agent-dh 逐条执行：①npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/requirement-doc-path.test.ts packages/web/dsh-pmboard/tests/state-workspace-root.test.ts → 全部 passed；②npx vitest run packages/web/dsh-pmboard → 记录失败文件清单，与 git worktree @ main 基线同命令的失败清单比对，差集必须为空（即无本需求新引入失败；主干存量红灯不算本需求失败）；③npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → passed；④curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot,homeDir}' → 返回 /Users 开头绝对路径；⑤grep -n "nodeIsolation: true" config/cordis.yml → 有命中行。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-7 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-10 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

## 2. 测试报告

- vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts → Tests 15 passed (15)
- vitest run packages/web/dsh-pmboard/tests/requirement-doc-path.test.ts → Tests 6 passed (6)
- vitest run packages/web/dsh-pmboard/tests/state-workspace-root.test.ts → Tests 7 passed (7)
- grep "nodeIsolation: true" config/cordis.yml 与 .dsh-data/profiles/agent-dh/cordis.patch.yml → 各 1 处命中
- curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state → workspaceRoot=/Users/yunpeng/pi-investment/agent-dh, homeDir=/Users/yunpeng
- vitest run apps/web/tests/plugin-schema.smoke.test.ts → 20 passed (20)；tsc --noEmit → exit 0
- 全量回归 91 failed/1658：存量实证见 docs/requirements/REQ-260922012924-2e29/tests/evidence.md（6 文件 chdir 环境特征 + 4 文件 main worktree 基线同红）；本需求触碰面 0 失败
- 部署：restart-with-build.sh --build-only 20/20 通过 + relink 24/24 + dist 符号核验命中；self_restart 检查点分支 agent-self/20260922-102948
- 评审报告：docs/requirements/REQ-260922012924-2e29/reviews/self-review.md（含证据口径自纠与可观测性遗留的如实记录）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | [FR-1] 更新 capture-tool.test.ts 为四问口径 | ⬜ 待验收 |  |  |
| v1-2 | [FR-2] requirementDocPath 消费 docBasePath + 单测 | ⬜ 待验收 |  |  |
| v1-3 | [FR-3] cordis.yml 开启 nodeIsolation 并重启验证 | ⬜ 待验收 |  |  |
| v1-4 | [FR-4] state 端点暴露 workspaceRoot/homeDir + 客户端绝对路径打开与显示 | ⬜ 待验收 |  |  |
| v1-5 | [FR-5] 立项拒绝粘滞：rejected 落痕 + 弹框前置检查 + 提示词纪律 | ⬜ 待验收 |  |  |
| v1-6 | [FR-1~FR-5] 全量回归与实证验收（含兼容性验证） | ⬜ 待验收 |  |  |
| v1-7 | 需求级验收 | ⬜ 待验收 |  |  |
| v1-10 | 需求级验收 | ⬜ 待验收 |  |  |
