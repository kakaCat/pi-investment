# REQ-202609262349-1518 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v2

**交付结论**：RTM 追溯基础设施交付并首次端到端打通：看板「追溯」Tab 现在真的能看到 FR→设计→任务→测试 的完整链条与覆盖度卡片了。

**这一步做完，什么变了**：
1. 追溯数据此前从未出现在接口里（写了一半：数据源模块缺失、工作区根被静默丢弃），现在 API 实测已返回 traceability/coverage——design 阶段 fr_to_design=9、design_to_tasks=40、fr_to_tasks=9、fr_to_tests=9。
2. 「🔗 追溯」Tab 从"无样式白板 + 点击报错"变为可渲染：补上了 17 个此前在本仓根本不存在的样式令牌（--vscode-* → --dsw-*），并消除了会抛 ReferenceError 的未定义变量引用。
3. 服务此前处于"一重启就崩"的状态（引用了不存在的模块），现已可正常重启运行。

**重要说明（交付边界）**：
- 本需求台账任务数为 0——批准的 14 张计划卡从未落库（开工前即如此），故 DAG 层级/泳道/实施覆盖度这些**执行期视图仍为空**，本次未擅自补落库；且计划卡的 depends_on 在提交时已丢失，即便落库也只会是单层。
- 台账 schemaVersion 保持 8（未引入 v9 字段），与常量自洽，无数据不一致隐患。

**已知遗留（非本需求引入，建议另立卡）**：traceability-view.ts 415 行超尺寸门禁；内容门禁的测试覆盖度检查已在拒绝既有验收提交；content-trace.ts 三级覆盖度 Level 3 仍为 TODO；deps.cwd 全局未设置这一结构性问题（本次只堵了追溯路径）。

## 1. 验收列表

### v2-1 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v2-4 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

## 2. 测试报告

- API 实测（重启+完整构建后）：design 阶段 body 含 traceability/coverage，fr_to_design=9、design_to_tasks=40、fr_to_tasks=9、fr_to_tests=9；accepting 阶段含 task_to_tests
- 构建产物核对：dist/index.mjs 1104892→1110520 bytes、lib/client.js 285229→301463 bytes（Sep 27 09:21 刷新）；verify-client-build 输出 [verify-client] OK 关键符号齐全
- 产物层校验：lib/client.js 中 currentReqDetail 残留 0 处、--vscode- 残留 0 处、追溯容器 5 处、覆盖度卡 10 处
- 单元测试：tests/traceability-handler.test.ts 7/7 通过（命令：cd agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/traceability-handler.test.ts）
- 端到端装配器验证：按服务端真实 cwd 调用 assembleStageDetail，4/4 阶段带出 traceability+coverage（对照不传 workspaceRoot 则 0/4）
- 类型检查：本次改动的文件零错误，仓库错误总数 147→137
- docs/requirements/REQ-202609262349-1518/reviews/rtm-verification-review.md
- docs/requirements/REQ-202609262349-1518/tests/rtm-test-evidence.md

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v2-1 | 需求级验收 | ⬜ 待验收 |  |  |
| v2-4 | 需求级验收 | ⬜ 待验收 |  |  |
