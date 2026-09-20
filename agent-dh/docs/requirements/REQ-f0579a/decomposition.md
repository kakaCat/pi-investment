# REQ-f0579a 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| FR-1 | t1 | t-b96644 | 修 verdicts.ts 覆盖通过丢留痕 | todo |
| FR-2 | t2 | t-f54dcc | 恢复看板视图三处回归 | todo |
| FR-3 | t3 | t-632e7c | 精确化操作条 move-req 断言 | todo |
| FR-4 | t4 | t-0c3303 | 清偿架构门禁债 | todo |
| FR-5 | t5 | t-cee913 | 尺寸拆分、杂项清理与全量终验 | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-b96644 | 修 verdicts.ts 覆盖通过丢留痕 | implement | backend | - | npx vitest run tests/verify-override.test.ts tests/acceptance-archive.test.ts tests/e2e-accept-override.test.ts 全绿；覆盖通过台账含 acceptanceOverride（failed/pending/noMaterials 三字段） |
| t2 | t-f54dcc | 恢复看板视图三处回归 | implement | frontend | - | npx vitest run tests/client-view.test.ts 全绿；buildBoard 输出含 dsh-pm-archived-bar 与「待归档」；产物标签含种类可读名且保留文件名（af8a2ac0 诉求） |
| t3 | t-632e7c | 精确化操作条 move-req 断言 | test | frontend | t-f54dcc | npx vitest run tests/board-info-fixes.test.ts 全绿；b2b37d9b 新增的立项取消 3 用例保持绿 |
| t4 | t-0c3303 | 清偿架构门禁债 | implement | backend | - | npx vitest run tests/output-contract.test.ts tests/layer-boundary.test.ts tests/tools-dispatch.test.ts tests/message-hygiene.test.ts 全绿 |
| t5 | t-cee913 | 尺寸拆分、杂项清理与全量终验 | test | fullstack | t-b96644, t-f54dcc, t-632e7c, t-0c3303 | size-budget 转绿（index.ts、styles/base.ts ≤400 行）；npx vitest run 全量 0 失败；tsc --noEmit 绿；pnpm build 成功且 verify-client-build 通过 |
