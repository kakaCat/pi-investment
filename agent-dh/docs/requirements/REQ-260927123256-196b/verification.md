# REQ-260927123256-196b 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：确认门弹框改为真正阻塞：reqboard_ask_confirm 缺省等到作答/取消/中止才返回（删除「30s 到点自动放行」）；只有显式正数 inline_grace_ms 才走非阻塞逃生舱；阻塞期间登记 ticket 并被停手守卫拦住写路径；中止时留可查挂起记录（reqboard_status.pending_confirms 可见）且写路径继续被拒。8 个测试文件 49 用例全绿。

## 1. 验收列表

### v1-1 · 先定契约：挂起确认能标出「被中止」，判定口径只留一处

**验收内容**：【先定契约：挂起确认能标出「被中止」，判定口径只留一处】验收：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts 全绿：targetConfirmedInLedger 对 plan（approvedAt 已写）与 artifact（该 kind 成组 confirmedAt 已写）分别返回 true、未落章返回 false；markInterrupted 二次调用后 interruptedAt 不变；createdAt 早于中止时间时记录不提前过期。

**操作步骤**：
1. cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts 全绿：targetConfirmedInLedger 对 plan（approvedAt 已写）与 artifact（该 kind 成组 confirmedAt 已写）分别返回 true、未落章返回 false
2. markInterrupted 二次调用后 interruptedAt 不变
3. createdAt 早于中止时间时记录不提前过期。

**预期结果**：按上述步骤执行后满足验收标准：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts 全绿：targetConfirmedInLedger 对 plan（approvedAt 已写）与 artifact（该 kind 成组 confirmedAt 已写）分别返回 true、未落章返回 false；markInterrupted 二次调用后 interruptedAt 不变；createdAt 早于中止时间时记录不提前过期。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 确认弹框改为阻塞等待：人不作答，agent 就停在这一步

**验收内容**：【确认弹框改为阻塞等待：人不作答，agent 就停在这一步】验收：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm.test.ts 全绿：不传宽限 + ask 永不 resolve 时工具 200ms 仍未返回，resolve(确认推进) 后返回 confirmed=true, advanced=true 且返回体无 pending/ticket 键；显式 inline_grace_ms: 20 返回 pending=true 与 pc- 前缀 ticket。

**操作步骤**：
1. cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm.test.ts 全绿：不传宽限 + ask 永不 resolve 时工具 200ms 仍未返回，resolve(确认推进) 后返回 confirmed=true, advanced=true 且返回体无 pending/ticket 键
2. 显式 inline_grace_ms: 20 返回 pending=true 与 pc- 前缀 ticket。

**预期结果**：按上述步骤执行后满足验收标准：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm.test.ts 全绿：不传宽限 + ask 永不 resolve 时工具 200ms 仍未返回，resolve(确认推进) 后返回 confirmed=true, advanced=true 且返回体无 pending/ticket 键；显式 inline_grace_ms: 20 返回 pending=true 与 pc- 前缀 ticket。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 等待期间不许偷偷往下走，状态页能看出在等谁

**验收内容**：【等待期间不许偷偷往下走，状态页能看出在等谁】验收：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts 全绿：阻塞登记的未作答记录使 reqboard_submit/move/task_move/decompose 抛 REQBOARD_CONFIRM_PENDING 且台账零写入；reqboard_status 返回 pending_confirms[0].ticket；台账落章后该数组为空。

**操作步骤**：
1. cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts 全绿：阻塞登记的未作答记录使 reqboard_submit/move/task_move/decompose 抛 REQBOARD_CONFIRM_PENDING 且台账零写入
2. reqboard_status 返回 pending_confirms[0].ticket
3. 台账落章后该数组为空。

**预期结果**：按上述步骤执行后满足验收标准：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts 全绿：阻塞登记的未作答记录使 reqboard_submit/move/task_move/decompose 抛 REQBOARD_CONFIRM_PENDING 且台账零写入；reqboard_status 返回 pending_confirms[0].ticket；台账落章后该数组为空。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 工具说明写清「默认会等你」：显式宽限等于主动放弃等待

**验收内容**：【工具说明写清「默认会等你」：显式宽限等于主动放弃等待】验收：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts 全绿：ASK_CONFIRM_PROMPT 文本含「缺省阻塞」，参数 description 含「缺省」与「阻塞」；defineAskConfirmTool 构造（含新 interrupted 键）不抛 schema 编译错误。

**操作步骤**：
1. cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts 全绿：ASK_CONFIRM_PROMPT 文本含「缺省阻塞」，参数 description 含「缺省」与「阻塞」
2. defineAskConfirmTool 构造（含新 interrupted 键）不抛 schema 编译错误。

**预期结果**：按上述步骤执行后满足验收标准：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts 全绿：ASK_CONFIRM_PROMPT 文本含「缺省阻塞」，参数 description 含「缺省」与「阻塞」；defineAskConfirmTool 构造（含新 interrupted 键）不抛 schema 编译错误。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 把等待语义的每条分支都钉成测试

**验收内容**：【把等待语义的每条分支都钉成测试】验收：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/contract-shapes.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts 全绿（0 failed）。

**操作步骤**：
1. cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/contract-shapes.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts 全绿（0 failed）。

**预期结果**：按上述步骤执行后满足验收标准：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/contract-shapes.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts 全绿（0 failed）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 老调用方与既有确认链路不回退，流程文档同步

**验收内容**：【老调用方与既有确认链路不回退，流程文档同步】验收：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm.test.ts packages/web/dsh-pmboard/tests/confirm-receipt.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts 全绿；grep -rn "非阻塞投递：30s" agent-dh/docs/architecture/reqboard-pipeline-flow.md 无输出（旧表述已删）；git diff -- agent-dh/.dsh-data/dsh-reqboard.json 无 schema 字段新增。

**操作步骤**：
1. cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm.test.ts packages/web/dsh-pmboard/tests/confirm-receipt.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts 全绿
2. grep -rn "非阻塞投递：30s" agent-dh/docs/architecture/reqboard-pipeline-flow.md 无输出（旧表述已删）
3. git diff -- agent-dh/.dsh-data/dsh-reqboard.json 无 schema 字段新增。

**预期结果**：按上述步骤执行后满足验收标准：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm.test.ts packages/web/dsh-pmboard/tests/confirm-receipt.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts 全绿；grep -rn "非阻塞投递：30s" agent-dh/docs/architecture/reqboard-pipeline-flow.md 无输出（旧表述已删）；git diff -- agent-dh/.dsh-data/dsh-reqboard.json 无 schema 字段新增。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 先定契约：挂起确认能标出「被中止」，判定口径只留一处·研发

**验收内容**：【先定契约：挂起确认能标出「被中止」，判定口径只留一处·研发】验收：命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts → 看到 Test Files 1 passed / Tests 9 passed；断言 targetConfirmedInLedger（plan/artifact）、markInterrupted 幂等与未知 ticket、过期基准 (interruptedAt ?? createdAt)+ttl；证据 docs/requirements/REQ-260927123256-196b/evidence/t-a0c273-dev.md

**操作步骤**：
1. 命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts → 看到 Test Files 1 passed / Tests 9 passed
2. 断言 targetConfirmedInLedger（plan/artifact）、markInterrupted 幂等与未知 ticket、过期基准 (interruptedAt ?? createdAt)+ttl
3. 证据 docs/requirements/REQ-260927123256-196b/evidence/t-a0c273-dev.md

**预期结果**：按上述步骤执行后满足验收标准：命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts → 看到 Test Files 1 passed / Tests 9 passed；断言 targetConfirmedInLedger（plan/artifact）、markInterrupted 幂等与未知 ticket、过期基准 (interruptedAt ?? createdAt)+ttl；证据 docs/requirements/REQ-260927123256-196b/evidence/t-a0c273-dev.md

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 先定契约：挂起确认能标出「被中止」，判定口径只留一处·联调

**验收内容**：【先定契约：挂起确认能标出「被中止」，判定口径只留一处·联调】验收：命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts → 看到 Test Files 1 passed / Tests 7 passed；断言注册表方法对未知/跨窗口/过期均不抛、回执走共享谓词、端口运行时形状为 5 方法

**操作步骤**：
1. 命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts → 看到 Test Files 1 passed / Tests 7 passed
2. 断言注册表方法对未知/跨窗口/过期均不抛、回执走共享谓词、端口运行时形状为 5 方法

**预期结果**：按上述步骤执行后满足验收标准：命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts → 看到 Test Files 1 passed / Tests 7 passed；断言注册表方法对未知/跨窗口/过期均不抛、回执走共享谓词、端口运行时形状为 5 方法

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-9 · 先定契约：挂起确认能标出「被中止」，判定口径只留一处·复核

**验收内容**：【先定契约：挂起确认能标出「被中止」，判定口径只留一处·复核】验收：打开 docs/requirements/REQ-260927123256-196b/evidence/t-738238-review.md → 看到 R1–R12 逐条判定与 §3 命令输出；复核命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts → 7 passed

**操作步骤**：
1. 打开 docs/requirements/REQ-260927123256-196b/evidence/t-738238-review.md → 看到 R1–R12 逐条判定与 §3 命令输出
2. 复核命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts → 7 passed

**预期结果**：按上述步骤执行后满足验收标准：打开 docs/requirements/REQ-260927123256-196b/evidence/t-738238-review.md → 看到 R1–R12 逐条判定与 §3 命令输出；复核命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts → 7 passed

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-10 · 先定契约：挂起确认能标出「被中止」，判定口径只留一处·测试

**验收内容**：【先定契约：挂起确认能标出「被中止」，判定口径只留一处·测试】验收：命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts → 看到 Test Files 2 passed / Tests 20 passed；证据 docs/requirements/REQ-260927123256-196b/evidence/t-db1d48-test.md

**操作步骤**：
1. 命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts → 看到 Test Files 2 passed / Tests 20 passed
2. 证据 docs/requirements/REQ-260927123256-196b/evidence/t-db1d48-test.md

**预期结果**：按上述步骤执行后满足验收标准：命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts → 看到 Test Files 2 passed / Tests 20 passed；证据 docs/requirements/REQ-260927123256-196b/evidence/t-db1d48-test.md

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

### v1-12 · 需求级验收

**验收内容**：孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——packages/web/dsh-pmboard/tests/ask-confirm.test.ts、packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts、packages/web/dsh-pmboard/tests/contract-shapes.test.ts、packages/web/dsh-pmboard/tests/output-contract.test.ts、packages/web/dsh-pmboard/tests/tools-schema.test.ts。请补 serves: 声明，或说明为何无需映射。

**操作步骤**：
1. 孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——packages/web/dsh-pmboard/tests/ask-confirm.test.ts、packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts、packages/web/dsh-pmboard/tests/contract-shapes.test.ts、packages/web/dsh-pmboard/tests/output-contract.test.ts、packages/web/dsh-pmboard/tests/tools-schema.test.ts。请补 serves: 声明，或说明为何无需映射。

**预期结果**：按上述步骤执行后满足验收标准：孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——packages/web/dsh-pmboard/tests/ask-confirm.test.ts、packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts、packages/web/dsh-pmboard/tests/contract-shapes.test.ts、packages/web/dsh-pmboard/tests/output-contract.test.ts、packages/web/dsh-pmboard/tests/tools-schema.test.ts。请补 serves: 声明，或说明为何无需映射。

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

- 命令 node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/contract-shapes.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts → Test Files 8 passed / Tests 49 passed（0 failed）
- FR-1/FR-3 判定：packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts 5 passed（ask 永不 resolve 时 200ms 仍未返回；resolve 后 confirmed/advanced 且无 pending/ticket）
- FR-2/FR-4 判定：packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts 5 passed（未作答+台账未落章 → 写路径抛 REQBOARD_CONFIRM_PENDING 且台账零写入；台账落章即放行）
- FR-4 投影判定：packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts 4 passed（pending_confirms 逐字段投影 + 陈旧记录过滤 + interrupted 标记）
- FR-5 判定：packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts 3 passed + packages/web/dsh-pmboard/tests/tools-schema.test.ts 4 passed（文案含「缺省阻塞」；defineAskConfirmTool 构造含 interrupted 键通过）
- FR-6 判定：packages/web/dsh-pmboard/tests/contract-shapes.test.ts 8 passed + packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts 11 passed（端口 5 方法、PendingConfirmationOutcome 4 键不变、回执链路不退化）
- 联调判定：packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts 7 passed
- 证据文档：docs/requirements/REQ-260927123256-196b/tests/test-evidence.md；docs/requirements/REQ-260927123256-196b/reviews/review-report.md；docs/requirements/REQ-260927123256-196b/evidence/test-evidence.md
- 文档同步证据：docs/architecture/reqboard-pipeline-flow.md G1/G2 已改写为「缺省阻塞；仅显式正数宽限走逃生舱」
- 预存在失败（动手前基线复跑即红，目标文件不在本需求交付面）：packages/web/dsh-pmboard/tests/ask-confirm.test.ts 1 条（闸门问题卡文案，其他窗口改动）、packages/web/dsh-pmboard/tests/output-contract.test.ts 4 条（Advance/ClearPause/RunStatus/TaskMove）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 先定契约：挂起确认能标出「被中止」，判定口径只留一处 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-2 | 确认弹框改为阻塞等待：人不作答，agent 就停在这一步 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-3 | 等待期间不许偷偷往下走，状态页能看出在等谁 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-4 | 工具说明写清「默认会等你」：显式宽限等于主动放弃等待 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-5 | 把等待语义的每条分支都钉成测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-6 | 老调用方与既有确认链路不回退，流程文档同步 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-7 | 先定契约：挂起确认能标出「被中止」，判定口径只留一处·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-8 | 先定契约：挂起确认能标出「被中止」，判定口径只留一处·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-9 | 先定契约：挂起确认能标出「被中止」，判定口径只留一处·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-10 | 先定契约：挂起确认能标出「被中止」，判定口径只留一处·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-11 | 需求级验收 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-12 | 需求级验收 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
| v1-14 | 需求级验收 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 14:32 |
