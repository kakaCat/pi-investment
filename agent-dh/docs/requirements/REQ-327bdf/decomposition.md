# REQ-327bdf 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| FR-1 | t-001 | t-62e62f | 实现 reqboard_task_execute | todo |
| FR-2 | t-001 | t-62e62f | 实现 reqboard_task_execute | todo |
| FR-2 | t-002 | t-d679bf | 实现 updateTaskCard | todo |
| FR-1 | t-003 | t-f0e869 | 修改 reqboard_decompose | todo |
| FR-1 | t-005 | t-65a30c | 实现 agentGenerateDetailedPlan | todo |
| FR-2 | t-005 | t-65a30c | 实现 agentGenerateDetailedPlan | todo |
| FR-2 | t-004 | t-cee795 | 实现 reqboard_task_status | todo |
| FR-1 | t-006 | t-e4bd73 | E2E 测试 | todo |
| FR-2 | t-006 | t-e4bd73 | E2E 测试 | todo |
| FR-3 | t-006 | t-e4bd73 | E2E 测试 | todo |
| FR-4 | t-007 | t-0cce7c | 单元测试：失败重试 | todo |
| FR-1 | t-008 | t-dd7e97 | 更新用户文档 | todo |
| FR-2 | t-008 | t-dd7e97 | 更新用户文档 | todo |
| —（未声明接收任何条款） | t-009 | t-06c5a2 | 迁移指南 | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t-001 | t-62e62f | 实现 reqboard_task_execute | implement | backend | - | npx vitest run tests/reqboard-task-execute.test.ts 通过 |
| t-002 | t-d679bf | 实现 updateTaskCard | implement | backend | - | grep "✅ 已完成" tasks/t-test-001.md 返回匹配 |
| t-003 | t-f0e869 | 修改 reqboard_decompose | implement | backend | - | test -f tasks.yml 返回非零；todo_write 返回 success |
| t-005 | t-65a30c | 实现 agentGenerateDetailedPlan | implement | backend | - | 返回 data.length === 6 通过 |
| t-004 | t-cee795 | 实现 reqboard_task_status | implement | backend | t-d679bf | 返回 data.progress 在 0-100 范围内通过 |
| t-006 | t-e4bd73 | E2E 测试 | test | backend | t-62e62f, t-d679bf, t-f0e869, t-65a30c | npx vitest run tests/e2e-task-execution.test.ts 通过 |
| t-007 | t-0cce7c | 单元测试：失败重试 | test | backend | t-62e62f | npx vitest run tests/task-retry.test.ts 通过 |
| t-008 | t-dd7e97 | 更新用户文档 | doc | doc | t-62e62f, t-f0e869 | grep "reqboard_task_execute" docs/architecture/project-manual.md 返回匹配 |
| t-009 | t-06c5a2 | 迁移指南 | doc | doc | t-dd7e97 | test -f docs/guides/task-execution-migration.md 返回零 |
