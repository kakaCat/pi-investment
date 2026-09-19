# REQ-308b9a 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| FR-9 | t1 | t-b45ad8 | 扩展验收项状态与通过判据（domain） | todo |
| FR-8 | t2 | t-20a647 | FR-8 验收失败自动回退实施（application） | todo |
| FR-7 | t3 | t-552eeb | verification.md 结构化生成 + 9 类文档完整性检查 | todo |
| FR-7 | t4 | t-df5d0c | 裁决后回填验收结果表 | todo |
| FR-7 | t5 | t-0c40e9 | 弹框补操作步骤 + 题干按长度纪律截短 | todo |
| FR-8 | t6 | t-6ccc5c | 看板「退回返工」收敛为等价入口 | todo |
| FR-7 | t7 | t-3935ea | 测试与门禁 | todo |
| FR-8 | t7 | t-3935ea | 测试与门禁 | todo |
| FR-9 | t7 | t-3935ea | 测试与门禁 | todo |
| FR-7 | t8 | t-1fa603 | 文档同步（PRD 与指南） | todo |
| FR-8 | t8 | t-1fa603 | 文档同步（PRD 与指南） | todo |
| FR-9 | t8 | t-1fa603 | 文档同步（PRD 与指南） | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-b45ad8 | 扩展验收项状态与通过判据（domain） | implement | backend | - | 跑 pnpm --filter dsh-pmboard test，tests/domain/acceptance-sheet.test.ts 的新增用例 T-U1~T-U4 全绿。 |
| t2 | t-20a647 | FR-8 验收失败自动回退实施（application） | implement | backend | t-b45ad8 | 跑 pnpm --filter dsh-pmboard test，tests/verdicts-and-rework.test.ts 的 T-I1/T-I2/T-I3/T-I4 全绿；T-I2 故障注入断言整笔回滚（状态与任务均不变）。 |
| t3 | t-552eeb | verification.md 结构化生成 + 9 类文档完整性检查 | implement | backend | t-b45ad8 | 跑 pnpm --filter dsh-pmboard test，T-U5/T-U6/T-U7/T-I7/T-I8 全绿；生成的 docs/requirements/<REQ>/verification.md 包含验收列表/测试报告/文档完整性检查/验收结果四段。 |
| t4 | t-df5d0c | 裁决后回填验收结果表 | implement | backend | t-20a647, t-552eeb | 跑 pnpm --filter dsh-pmboard test，tests/verdicts-and-rework.test.ts 的 T-I9 断言 verification.md 的验收结果表包含 编号/验收项/状态/验收人/验收时间 五列。 |
| t5 | t-0c40e9 | 弹框补操作步骤 + 题干按长度纪律截短 | implement | fullstack | t-552eeb | 跑 pnpm --filter dsh-pmboard test 的 T-E3，断言题干 ≤220 字且弹框可见操作步骤、选项不被挤出可视区。 |
| t6 | t-6ccc5c | 看板「退回返工」收敛为等价入口 | implement | backend | t-20a647 | 跑 pnpm --filter dsh-pmboard test 的 T-E4，断言看板 rework 与自动回退行为一致（同一 use-case 调用）。 |
| t7 | t-3935ea | 测试与门禁 | test | fullstack | t-df5d0c, t-0c40e9, t-6ccc5c | pnpm --filter dsh-pmboard test 全绿 + node packages/pages/dsh-pmboard/scripts/verify-client-build.mjs exit=0 + tsc 0 错误。 |
| t8 | t-1fa603 | 文档同步（PRD 与指南） | doc | doc | t-20a647, t-552eeb | 跑 grep 核对：REQ-99b58f/requirement.md、REQ-a8d582/requirement.md、agent-dh/docs/guides/reqboard-workflow.md 三处各含明确标注（落地/作废/更新），且无悬空引用。 |
