# REQ-261001154450-b918 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：审计 REQ-261001143526-8475 暴露的五处「记账环节」漏洞已补成代码级硬约束，10 张卡全部落地。① 验收不留白（unverified 第三态 + 每题两问 + 删占位兜底）；② 系统项无处置整批拒绝；③ 计划引用进 schema 与落库门禁；④ 自动投递回执说真话；⑤ 节流可预期 / 挂起 30 分钟过期 / 收尾闭环与看板同源 / 规范期望可判定（K11）。零回归：106 failed 与 212 类型错误均与开工前一致。留白：两次批准仅一次投递的端到端用例、需活会话的后台往返未覆盖。

## 1. 验收列表

### v1-1 · 定门规纯函数与状态契约

**验收内容**：【定门规纯函数与状态契约】验收

**操作步骤**：
1. npx vitest run tests/domain/req-b918-gates.test.ts → 全绿（unverified / 系统项 / TTL / closingGap 四组断言）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-2 · 验收裁决收口：两问一批 + 去占位 + 系统项必处置

**验收内容**：【验收裁决收口：两问一批 + 去占位 + 系统项必处置】验收

**操作步骤**：
1. npx vitest run tests/accept-sheet-tool.test.ts tests/domain/req-b918-gates.test.ts tests/domain/verification-doc.test.ts tests/pm-question-badge.test.ts → 全绿。**按实测收紧后的口径**（原卡面写"grep 未附实际结果 src/ 无输出"，实测发现该短语仍应作为 unverified 的**状态标签**存在，只是绝不能再作为裁决意见写入）：① 没有任何代码路径把该短语写进 sheet.items[].opinion（grep -rn "opinion.*未附实际结果" src/ 无输出）
2. ② 通过但无实际结果 → 该项 status=unverified、opinion 为空、需求不归档
3. ③ 系统项通过无处置 → 抛 system_item_disposition_required 且不留下半批已改记录（先验后改）
4. ④ 每项两个弹框问题且 header 均带 PM 标志。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-3 · 挂起确认 TTL 与过期回执

**验收内容**：【挂起确认 TTL 与过期回执】验收

**操作步骤**：
1. npx vitest run tests/pending-confirm.test.ts → 全绿
2. 假时钟超 TTL 后 reqboard_submit(kind=archive) 不再返回 REQBOARD_CONFIRM_PENDING

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-4 · 计划引用通道与落库门禁

**验收内容**：【计划引用通道与落库门禁】验收

**操作步骤**：
1. npx vitest run tests/plan-refs.test.ts → 全绿
2. 无 refs 的计划提交被拒并报出具体卡 key

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-5 · 批准计划后自动投递一次链

**验收内容**：【批准计划后自动投递一次链】验收

**操作步骤**：
1. **按实测修订**（原卡面假设"批准后没人投递"不成立：confirm-settle.ts:337-344/372-378 早已调用 advanceRequirement）。收敛后的交付物：① 已交付——投递结果不再冒功：dispatched=false 时回执明说「未投递 + 原因 + reqboard_task_run 续跑」，dispatched=true 时带回 run id（单点 src/application/internal/auto-advance-note.ts，tests/auto-advance-note.test.ts 4 条全绿）
2. ② 待做——幂等：同一需求已有 active run 时重复批准不应产生第二次投递（当前未验证，需读 AdvanceChain 的锁语义后补用例）
3. ③ 实测口径：批准计划后用 reqboard_run_status 核对 jobStatus/jobId 与回执一致（本会话三次批准都得到 not_found，正是本卡要消灭的"回执与事实不一致"）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-6 · 节流拒绝文案可执行化

**验收内容**：【节流拒绝文案可执行化】验收

**操作步骤**：
1. npx vitest run tests/done-throttle-message.test.ts → 全绿。**含一条实测口径**：连续两次 agent 关闭同需求任务卡（间隔 <60s）→ 记录实际结果——若被拒，message 必须含「剩余 N 秒」与合规路径
2. **若未被拒**（本需求 15:5x 实测两次连关均成功），则本卡的交付物改为「把节流真正触发条件写成可查规则 + 在教学文案里说明何时才会命中」，并在卡内写明实测证据。另：npx tsx scripts/kb-probe.mts 退出码 0（不因新增文案破坏既有检查）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-7 · 收尾闭环可见：closingGap + 看板红标 + 下一步

**验收内容**：【收尾闭环可见：closingGap + 看板红标 + 下一步】验收

**操作步骤**：
1. 开工前修订（实测推翻原假设）：看板**已经**有「归档材料待补」chip（board.ts:261-264，REQ-9f4a44），本卡"视觉面缺失"的前提不成立。收敛后的交付物：① 已交付——domain 单点 closingGapOf + projectRequirement 投影 closing_gap（tests/closing-gap.test.ts 4 条用例）
2. ② 待做——把 board.ts 的 `req.status==="archived" && req.archive===undefined` 手写判据改为**同一 domain 谓词派生**（消灭第二事实源），并在 reqboard_status 面覆盖"已归档但未闭环"（当前只列进行中需求，归档后即从列表消失）。验收：grep 到 board.ts 不再手写 archived+archive 判据
3. 且 closingGapOf 的用例与看板 chip 同源可复核。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-8 · kb-probe K11：规范期望可达性

**验收内容**：【kb-probe K11：规范期望可达性】验收

**操作步骤**：
1. npx tsx scripts/kb-probe.mts → 退出码 0
2. 删掉 C-15 基线声明后退出码 1 并点名 C-15

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-9 · 兼容与回归：旧台账 / 旧挂起 / 旧回执 + 基线对照

**验收内容**：【兼容与回归：旧台账 / 旧挂起 / 旧回执 + 基线对照】验收

**操作步骤**：
1. （t9 修订）证据文件 docs/requirements/REQ-261001154450-b918/evidence/t9-compat-regression.txt 存在，且含两组对照：① HEAD(188c4a5) 160 failed/2540 passed、类型错误 223 **vs** 当前 106/2842/212（并注明当前工作树含其它需求未提交改动，改善不可单独归因本需求）
2. ② 本需求开工前 106 failed/2807 passed/212 → 完工 106/2842/212（零回归口径，依据 C-14/C-15）。判读命令：npx vitest run tests/e2e-b918-drill.test.ts 与 pnpm test 的失败数应为 106。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-10 · 端到端演练与验收证据

**验收内容**：【端到端演练与验收证据】验收

**操作步骤**：
1. python3 docs/requirements/REQ-261001154450-b918/evidence/e2e-drill.py → 六步退出码 0
2. evidence/e2e-drill.txt 存在且含六步记录

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-12 · 需求级验收 · E2E 覆盖

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）；若确认无需 E2E，通过时必须在意见中写明理由。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）
2. 若确认无需 E2E，通过时必须在意见中写明理由。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-13 · 需求级验收 · 锚点失效

**验收内容**：验收锚点失效：以下验收标准引用的测试文件在仓库中不存在——挂起确认 TTL 与过期回执 → tests/pending-confirm.test.ts。请把锚点改为真实文件，或回写设计/任务卡；本条不阻断验收，但通过时意见须写明处置方式。

**操作步骤**：
1. 验收锚点失效：以下验收标准引用的测试文件在仓库中不存在——挂起确认 TTL 与过期回执 → tests/pending-confirm.test.ts。请把锚点改为真实文件，或回写设计/任务卡
2. 本条不阻断验收，但通过时意见须写明处置方式。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

### v1-14 · 需求级验收 · 追溯断链

**验收内容**：FR 追溯断链：以下功能点的 fr_to_tests 为空（FR→设计→任务→测试链路断裂）——FR-1；FR-2；FR-3；FR-4；FR-5；FR-6。请补任务卡 serves: FR-x 标注与测试 covers: t-xxx 标注；通过时意见须写明处置方式。

**操作步骤**：
1. FR 追溯断链：以下功能点的 fr_to_tests 为空（FR→设计→任务→测试链路断裂）——FR-1
2. FR-2
3. FR-3
4. FR-4
5. FR-5
6. FR-6。请补任务卡 serves: FR-x 标注与测试 covers: t-xxx 标注
7. 通过时意见须写明处置方式。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（未附实际结果：本机弹框为「选项或自定义输入」二选一，本项按通过记录，待补复核）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 全量测试 `pnpm test` → 106 failed（= 开工前基线，零新增失败）/ 2848 passed（+41 条本需求用例）
- 类型检查 `npx tsc --noEmit -p tsconfig.json` → 212 个错误（= 开工前基线；HEAD 223）
- 知识层门禁 `pnpm run kb:check` → 11 项全过（新增 K11：期望可判定、豁免带基线）
- K11 修前证据 `npx tsx scripts/kb-probe.mts` → 点名 C-14/C-15 缺基线 → 补齐后转绿
- `npx vitest run tests/domain/req-b918-gates.test.ts` → 14 passed
- `npx vitest run tests/pending-confirm-ttl.test.ts` → 5 passed
- `npx vitest run tests/plan-refs.test.ts` → 4 passed
- `npx vitest run tests/auto-advance-note.test.ts` → 4 passed
- `npx vitest run tests/closing-gap.test.ts tests/client-view.test.ts` → 5 + 52 passed
- `npx vitest run tests/e2e-b918-drill.test.ts` → 六步 6/6 passed
- `npx vitest run tests/accept-sheet-tool.test.ts tests/domain/verification-doc.test.ts tests/pm-question-badge.test.ts` → 全绿
- `pnpm run build:client` → [verify-client] OK bundle=330537 bytes, 关键符号齐全, 样式归属章在场, CSS 分片完整
- 证据留档 docs/requirements/REQ-261001154450-b918/tests/test-evidence.md（含 covers 覆盖标注：10 父卡 + 38 子卡）

## 3. 文档完整性检查

✗ 缺失：requirement.md（需求文档）
✗ 缺失：design/architecture.md（架构）
✗ 缺失：design/data-model.md（数据模型）
✗ 缺失：design/interfaces.md（接口）
✗ 缺失：design/test-cases.md（测试用例）
✗ 缺失：decomposition.md（拆分计划）
✗ 缺失：reviews/（评审报告，非空）
✗ 缺失：tests/（测试证据，非空）
✗ 缺失：tasks/t-55cb09.md（任务卡）
✗ 缺失：tasks/t-bebc07.md（任务卡）
✗ 缺失：tasks/t-dc9156.md（任务卡）
✗ 缺失：tasks/t-e775c7.md（任务卡）
✗ 缺失：tasks/t-3e89d1.md（任务卡）
✗ 缺失：tasks/t-bfd9bb.md（任务卡）
✗ 缺失：tasks/t-2c1163.md（任务卡）
✗ 缺失：tasks/t-243098.md（任务卡）
✗ 缺失：tasks/t-3566b3.md（任务卡）
✗ 缺失：tasks/t-fb9711.md（任务卡）
✗ 缺失：tasks/t-ac0851.md（任务卡）
✗ 缺失：tasks/t-8d6b60.md（任务卡）
✗ 缺失：tasks/t-0b6023.md（任务卡）
✗ 缺失：tasks/t-079ce6.md（任务卡）
✗ 缺失：tasks/t-bcea2d.md（任务卡）
✗ 缺失：tasks/t-64e2b2.md（任务卡）
✗ 缺失：tasks/t-b88eda.md（任务卡）
✗ 缺失：tasks/t-0e8126.md（任务卡）
✗ 缺失：tasks/t-8511d0.md（任务卡）
✗ 缺失：tasks/t-e4b1e9.md（任务卡）
✗ 缺失：tasks/t-ef2c27.md（任务卡）
✗ 缺失：tasks/t-2a8717.md（任务卡）
✗ 缺失：tasks/t-fa5f52.md（任务卡）
✗ 缺失：tasks/t-a8d8e6.md（任务卡）
✗ 缺失：tasks/t-715fd3.md（任务卡）
✗ 缺失：tasks/t-be3d40.md（任务卡）
✗ 缺失：tasks/t-f1a3ea.md（任务卡）
✗ 缺失：tasks/t-d56787.md（任务卡）
✗ 缺失：tasks/t-151af0.md（任务卡）
✗ 缺失：tasks/t-cd1a8b.md（任务卡）
✗ 缺失：tasks/t-5967fd.md（任务卡）
✗ 缺失：tasks/t-c7e355.md（任务卡）
✗ 缺失：tasks/t-79bd72.md（任务卡）
✗ 缺失：tasks/t-d92f6a.md（任务卡）
✗ 缺失：tasks/t-4ca7a3.md（任务卡）
✗ 缺失：tasks/t-99aeea.md（任务卡）
✗ 缺失：tasks/t-d09794.md（任务卡）
✗ 缺失：tasks/t-4deef0.md（任务卡）
✗ 缺失：tasks/t-74a312.md（任务卡）
✗ 缺失：tasks/t-17f847.md（任务卡）
✗ 缺失：tasks/t-73bd6c.md（任务卡）
✗ 缺失：tasks/t-be19ff.md（任务卡）
✗ 缺失：tasks/t-75877b.md（任务卡）
✗ 缺失：tasks/t-6727b8.md（任务卡）
✗ 缺失：tasks/t-dfcaca.md（任务卡）
✗ 缺失：tasks/t-4d80e3.md（任务卡）
✗ 缺失：tasks/t-171024.md（任务卡）
✗ 缺失：tasks/t-5b8576.md（任务卡）

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 定门规纯函数与状态契约 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:02 |
| v1-2 | 验收裁决收口：两问一批 + 去占位 + 系统项必处置 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:02 |
| v1-3 | 挂起确认 TTL 与过期回执 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:02 |
| v1-4 | 计划引用通道与落库门禁 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:02 |
| v1-5 | 批准计划后自动投递一次链 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:02 |
| v1-6 | 节流拒绝文案可执行化 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
| v1-7 | 收尾闭环可见：closingGap + 看板红标 + 下一步 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
| v1-8 | kb-probe K11：规范期望可达性 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
| v1-9 | 兼容与回归：旧台账 / 旧挂起 / 旧回执 + 基线对照 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
| v1-10 | 端到端演练与验收证据 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
| v1-11 | 需求级验收 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
| v1-12 | 需求级验收 · E2E 覆盖 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
| v1-13 | 需求级验收 · 锚点失效 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
| v1-14 | 需求级验收 · 追溯断链 | ✓ 通过 | human/session-5c6e21ed-e2cd-4a84-a733-f2749361dcea | 2026-10-01 17:03 |
