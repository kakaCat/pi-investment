# t-16cefa 工具说明写清「默认会等你」：显式宽限等于主动放弃等待

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
工具说明写清「默认会等你」：显式宽限等于主动放弃等待

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts 全绿：ASK_CONFIRM_PROMPT 文本含「缺省阻塞」，参数 description 含「缺省」与「阻塞」；defineAskConfirmTool 构造（含新 interrupted 键）不抛 schema 编译错误。

## 实施方案（implementation）
① src/tools/AskConfirmTool/prompt.ts：ASK_CONFIRM_PROMPT 写明弹框路径缺省阻塞、inline_grace_ms = 主动放弃阻塞且须自担超时后 loop 继续的后果。② src/tools/AskConfirmTool/AskConfirmTool.ts：inline_grace_ms 参数 description 同步。③ src/tools/ConfirmReceiptTool/prompt.ts：补被中止记录可凭 ticket 查询。

## 上游产出摘要（dependsSummary）
- 确认弹框改为阻塞等待：人不作答，agent 就停在这一步

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T06:25:01.440Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

工具说明写清「默认会等你」：agent 读到 reqboard_ask_confirm 的提示词与 inline_grace_ms 参数说明，就知道不传宽限 = 阻塞等到作答、显式传正数 = 主动放弃阻塞（超时后 loop 继续跑，后果自负）。

### 完成项

- ASK_CONFIRM_PROMPT 重写为单字面量：含「缺省阻塞」「主动放弃阻塞」与 REQBOARD_CONFIRM_PENDING 的停手说明
- inline_grace_ms 参数 description 同步（含「缺省」「阻塞」「主动放弃阻塞」）
- AskConfirmTool output.schema 增 interrupted 键（中止分支可被绑定层接受）
- ConfirmReceiptTool 提示词补「被中止的挂起记录同样可凭 ticket 查询」并点名 reqboard_confirm_receipt

### 改动文件

- `packages/web/dsh-pmboard/src/tools/AskConfirmTool/prompt.ts`
- `packages/web/dsh-pmboard/src/tools/AskConfirmTool/AskConfirmTool.ts`
- `packages/web/dsh-pmboard/src/tools/ConfirmReceiptTool/prompt.ts`

### 下一步

t5 全分支测试固化后进入验收

---
