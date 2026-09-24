# t-e932fc 弹框改非阻塞投递并加回执工具·研发

> 子卡（父卡 t-5f2a65 · 阶段 dev） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
弹框改非阻塞投递并加回执工具·研发

## 解决什么问题
子卡阶段：研发

## 得到什么结果（验收标准）

本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts 全绿；questions.ask 永不 resolve + 宽限 20ms → 返回 pending=true 且 ticket 非空、不抛错；作答后 reqboard_confirm_receipt(ticket) 返回 confirmed=true, advanced=true 且台账 confirmedAt 已写；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-e932fc.md

## 实施方案
改 packages/web/dsh-pmboard/src/domain/limits.ts（confirmInlineGraceMs）；新增 packages/web/dsh-pmboard/src/adapters/PendingConfirmRegistry.ts、packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts、packages/web/dsh-pmboard/src/tools/ConfirmReceiptTool/ConfirmReceiptTool.ts；改 packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts（宽限赛跑/挂起/后台落章）、packages/web/dsh-pmboard/src/index.ts（注册工具+装配）；新增 packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts。

[子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 执行与完工记录
- workflow run：2026-09-25 00:40:23（stopReason=completed，产出非空=True）
- 改动文件：
  - packages/web/dsh-pmboard/src/application/internal/pending-confirm.ts
  - packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts
  - packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts
  - packages/web/dsh-pmboard/src/tools/ConfirmReceiptTool/ConfirmReceiptTool.ts
  - packages/web/dsh-pmboard/src/tools/ConfirmReceiptTool/prompt.ts
  - packages/web/dsh-pmboard/src/tools/ConfirmReceiptTool/index.ts
  - packages/web/dsh-pmboard/src/tools/AskConfirmTool/AskConfirmTool.ts
  - packages/web/dsh-pmboard/src/tools/render-summaries.ts
  - packages/web/dsh-pmboard/src/tools/index.ts
  - packages/web/dsh-pmboard/src/index.ts
  - packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts
  - packages/web/dsh-pmboard/tests/apply-wiring.test.ts
  - packages/web/dsh-pmboard/tests/output-contract.test.ts
  - packages/web/dsh-pmboard/tests/tools-dispatch.test.ts
- 完成项：
  - AskConfirm 改非阻塞投递：questions.ask 与宽限计时器赛跑（raceAsk）——宽限内作答走与改造前逐字一致的同步落章/推进；超宽限登记 ticket 并立即返回 pending=true（不判失败），后台续跑落章/推进/回填/唤醒（AgentDeliveryPort）
  - 新增 ConfirmReceipt 用例：ticket 窗口绑定 + 过期判定，未知/跨窗口/过期 → REQBOARD_UNKNOWN_TICKET；confirmed 以台账为准（产物 confirmedAt / 计划 approvedAt），advanced/from/to 由 statusHistory 的确认推进事件还原（原因常量取自 confirm-settle 单点）
  - 新增 reqboard_confirm_receipt 工具（三段式 ConfirmReceiptTool.ts + prompt.ts + index.ts），输出字段与 interfaces.md I-4 一一对应；只读超时 LIMITS.timeoutReadMs
  - index.ts 装配 PendingConfirmRegistry（UseCaseDeps.pendingConfirms）并注册新工具（工具数 13→14，日志同步）
  - AskConfirmTool 增 inline_grace_ms 入参（非法值显式 REQBOARD_INVALID_INPUT）与 pending/ticket 输出声明，满足 output.schema additionalProperties:false
  - 落章/推进唯一实现复用既有 application/internal/confirm-settle.ts（未改），赛跑/挂起机制独立成 application/internal/pending-confirm.ts，AskConfirm.ts 收缩至约 200 行
  - 新增 tests/ask-confirm-pending.test.ts（11 用例，覆盖 TC-5/6/7/8/20 + 未装配注册表旧阻塞语义 + 非法宽限 + 跨窗口 ticket + 后台否定项）
  - 同步受本次改动影响的既有门禁测试：工具注册表 13→14（apply-wiring）、工具目录 12→13（tools-dispatch）、RESPONSE_SOURCES 增 ConfirmReceipt（output-contract）
- 执行段：2 次（末次 2026-09-25 00:34:25，outcome=succeeded）
