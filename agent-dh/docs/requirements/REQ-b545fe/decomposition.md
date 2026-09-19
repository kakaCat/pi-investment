# REQ-b545fe 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| —（未声明接收任何条款） | t1 | t-7a84fe | 核心迁移助手（internal/token-usage.ts） | todo |
| —（未声明接收任何条款） | t2 | t-668a47 | MoveRequirement 改用迁移助手 | todo |
| —（未声明接收任何条款） | t3 | t-80f68f | AskConfirm 改用迁移助手 | todo |
| —（未声明接收任何条款） | t4 | t-1ae215 | rollup 改用迁移助手 + 可选快照提供者 | todo |
| —（未声明接收任何条款） | t5 | t-29883d | AcceptSheet 归档 + verdicts 打回改用迁移助手 | todo |
| —（未声明接收任何条款） | t6 | t-ee3911 | HTTP 路由快照接入（routers/tasks.ts） | todo |
| —（未声明接收任何条款） | t7 | t-5efb06 | 端到端验证 + 文档更新 | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-7a84fe | 核心迁移助手（internal/token-usage.ts） | implement | backend | - | 单测：假快照调用断言 byStage 累加+事件带快照；snap=undefined 调用断言不累加+事件无快照 |
| t2 | t-668a47 | MoveRequirement 改用迁移助手 | implement | backend | t-7a84fe | 回归测试 artifact-gates/rollup/plan-mode 全绿；单测补充 move 带快照断言 byStage 累加 |
| t3 | t-80f68f | AskConfirm 改用迁移助手 | implement | backend | t-7a84fe | tests/artifact-gates.test.ts 通过；单测补充 brainstorming→planning 推进断言 brainstorming 节点 byStage 累加 |
| t4 | t-1ae215 | rollup 改用迁移助手 + 可选快照提供者 | implement | backend | t-7a84fe | tests/routes-rollup.test.ts 全绿；单测补充有/无快照提供者两种场景，断言 byStage 正确累加或诚实不累加 |
| t5 | t-29883d | AcceptSheet 归档 + verdicts 打回改用迁移助手 | implement | backend | t-7a84fe | tests/accept-sheet-tool.test.ts、tests/verdicts-and-rework.test.ts 全绿；单测补充归档+打回路径断言 accepting 节点 byStage 累加 |
| t6 | t-ee3911 | HTTP 路由快照接入（routers/tasks.ts） | implement | backend | t-1ae215 | 单测：模拟 HTTP POST /tasks/:id/move 带 sessionId，mock tokenSnapshot，断言 rollup 派生推进带快照结算；既有 routes 测试通过 |
| t7 | t-5efb06 | 端到端验证 + 文档更新 | test | doc | t-668a47, t-80f68f, t-1ae215, t-29883d, t-ee3911 | 测试需求 byStage 包含全部6个经过节点；流程图节点全部有token；pnpm test/typecheck/build:client 全绿；docs/architecture/reqboard-token-usage.md 已更新 |
