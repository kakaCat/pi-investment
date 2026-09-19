# REQ-a8d582 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| FR-1 | t1 | t-9f7594 | 验收态按钮常显 + 「验收通过」二次确认弹框 | todo |
| FR-3 | t1 | t-9f7594 | 验收态按钮常显 + 「验收通过」二次确认弹框 | todo |
| FR-2 | t2 | t-e783cc | 验收裁决只记录，不再自动打回 | todo |
| FR-2 | t3 | t-111acb | 返工任务改由「退回返工」生成 | todo |
| FR-1 | t4 | t-2320d9 | 通过动作的覆盖语义与台账留痕 | todo |
| FR-4 | t4 | t-2320d9 | 通过动作的覆盖语义与台账留痕 | todo |
| FR-1 | t5 | t-ee0945 | 端到端链路与全量回归（含 client 产物重建） | todo |
| FR-2 | t5 | t-ee0945 | 端到端链路与全量回归（含 client 产物重建） | todo |
| FR-3 | t5 | t-ee0945 | 端到端链路与全量回归（含 client 产物重建） | todo |
| FR-4 | t5 | t-ee0945 | 端到端链路与全量回归（含 client 产物重建） | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-9f7594 | 验收态按钮常显 + 「验收通过」二次确认弹框 | implement | frontend | - | cd agent-dh/packages/pages/dsh-pmboard && npx vitest run tests/board-info-fixes.test.ts tests/client-view.test.ts 全绿；其中含断言"accepting 且无 verification 时操作条包含 data-action=verify-pass 且不再包含旧提示文案"；手工在 :13080 看板点「验收通过」，弹框可见、选取消后无任何请求。 |
| t2 | t-e783cc | 验收裁决只记录，不再自动打回 | implement | backend | - | 新建路由用例并 cd agent-dh/packages/pages/dsh-pmboard && npx vitest run tests/verdicts-and-rework.test.ts 全绿：POST /req/verdicts 带 1 项 failed 后，需求 status 仍返回 accepting、任务总数不变、返回 note 包含"退回返工"字样（按新语义更新既有断言）。 |
| t3 | t-111acb | 返工任务改由「退回返工」生成 | implement | backend | t-e783cc | 在 tests/verdicts-and-rework.test.ts 新增用例并 npx vitest run tests/verdicts-and-rework.test.ts 全绿：调 POST /req/verify/rework（带 note）后断言需求 status 返回 implementing、新增任务数等于 failed 项数、卡内含验收意见原文；状态已不在验收态时再次调用被拒绝（状态不变）。 |
| t4 | t-2320d9 | 通过动作的覆盖语义与台账留痕 | implement | backend | t-e783cc | npx vitest run tests/verify-override.test.ts tests/acceptance-archive.test.ts 全绿，四条断言全过：①有 failed 不带 confirm_override → 返回 400 且状态不变；②带 confirm_override → 返回 archived 且 verification.override 包含 at/by/detail、评论可查到原因原文；③验收态无 verification 带 confirm_override → 返回 archived 且不报 missing_artifact；④全过且材料齐全时不带 override → 正常返回 archived 无 400。旧台账（无该字段）读取与渲染不报错。 |
| t5 | t-ee0945 | 端到端链路与全量回归（含 client 产物重建） | test | fullstack | t-9f7594, t-111acb, t-2320d9 | npx vitest run 全绿（含新增 e2e-accept-override.test.ts）；pnpm build 退出码 0 且 dist 产物存在（grep 命中新逻辑符号）；:13080 看板上逐条记录并通过：①全过直接通过 ②有不合格弹框后取消（状态不变）③有不合格确认覆盖通过（评论可见留痕）④无材料确认覆盖通过。 |
