# t-74ab2d 弹框改非阻塞投递并加回执工具·联调

> 子卡（父卡 t-5f2a65 · 阶段 integrate） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
弹框改非阻塞投递并加回执工具·联调

## 解决什么问题
子卡阶段：联调

## 得到什么结果（验收标准）
接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-74ab2d-integrate.md，在 filesChanged 中列出该文件

## 实施方案
改 packages/web/dsh-pmboard/src/domain/limits.ts（confirmInlineGraceMs）；新增 packages/web/dsh-pmboard/src/adapters/PendingConfirmRegistry.ts、packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts、packages/web/dsh-pmboard/src/tools/ConfirmReceiptTool/ConfirmReceiptTool.ts；改 packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts（宽限赛跑/挂起/后台落章）、packages/web/dsh-pmboard/src/index.ts（注册工具+装配）；新增 packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts。

[子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 执行与完工记录
- workflow run：2026-09-25 00:42:29（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-74ab2d-integrate.md
- 完成项：
  - 读接口契约：I-3（reqboard_ask_confirm 宽限赛跑/挂起）与 I-4（reqboard_confirm_receipt 回执）实现已在位：AskConfirm.ts + internal/pending-confirm.ts、ConfirmReceipt.ts、ConfirmReceiptTool.ts、adapters/PendingConfirmRegistry.ts、src/index.ts 装配
  - 用临时探针 tests/__probe-t74ab2d.test.ts（跑完即删）对 I-3/I-4 发真实工具调用，做「请求样例 → 期望响应 → 实际返回」三方逐字段对照：7/7 例 MATCH
  - 覆盖 C1 超宽限挂起（pending=true + pc- ticket，不判失败、台账未动）、C2 宽限内作答=旧阻塞语义（无 pending/ticket 键）、C3 后台落章后回执（confirmed=true/advanced=true/brainstorming→design，台账 confirmedAt 已写 + 唤醒窗口 1 次）、C4 未知 ticket → REQBOARD_UNKNOWN_TICKET、C5 挂起未作答如实 confirmed=false、C6a 工具壳契约（name/required(ticket)/响应键集）、C6b index.ts 组合根装配
  - 运行父卡验收命令 tests/ask-confirm-pending.test.ts + tests/ask-confirm.test.ts → 22/22 绿
  - 运行接口层回归 tools-schema/output-contract/tools-dispatch/apply-wiring → 31/31 绿
  - 如实记录 size-budget 仍红：仅 index.ts = 442 行（HEAD 基线已 433 行，分解计划指定 T-12 修绿），无新增超标文件
  - 把联调记录（含三方对照表、命令与输出摘要、结论）写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-74ab2d-integrate.md
  - 删除临时探针 tests/__probe-t74ab2d.test.ts 与一次性 dump 探针 tests/__dump-t74ab2d.test.ts（复核 No such file or directory）；未修改任何实现或测试源码
- 执行段：1 次（末次 2026-09-25 00:40:24，outcome=succeeded）
