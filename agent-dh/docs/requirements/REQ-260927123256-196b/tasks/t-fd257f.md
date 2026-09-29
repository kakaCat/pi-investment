# t-fd257f 等待期间不许偷偷往下走，状态页能看出在等谁

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
等待期间不许偷偷往下走，状态页能看出在等谁

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts 全绿：阻塞登记的未作答记录使 reqboard_submit/move/task_move/decompose 抛 REQBOARD_CONFIRM_PENDING 且台账零写入；reqboard_status 返回 pending_confirms[0].ticket；台账落章后该数组为空。

## 实施方案（implementation）
① src/application/internal/support.ts：assertNoPendingConfirm 改用 livePendingConfirm，拒绝消息含 ticket、「收到作答前不得产出下游产物」与三条恢复路径（取回执 / 看板确认 / 重新发起）。② src/application/query/QueryState.ts：返回体增 pending_confirms（字段见 design/interfaces.md I-2）。③ src/tools/StatusTool/StatusTool.ts：output.schema 声明 pending_confirms。

## 上游产出摘要（dependsSummary）
- 先定契约：挂起确认能标出「被中止」，判定口径只留一处

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T06:23:44.790Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

等待期间不再偷偷往下走：停手守卫改为「未作答 **且** 台账未落章」才拦（人已通过看板/证据作答的陈旧记录不再死锁）；reqboard_status 新增 pending_confirms，状态页能看出在等谁、是否被中止。

### 完成项

- assertNoPendingConfirm 复用 pending-guard.livePendingConfirm（判定口径单点），拒绝文案含 ticket + 三条恢复路径
- QueryState 返回体增 pending_confirms 投影（ticket/requirement_id/target/kind/created_at/interrupted/blocked_tools/recovery）
- StatusTool output.schema 声明 pending_confirms
- confirm-pending-guard 补 TC-9（台账落章即放行）；status-pending-confirm 新增 4 用例

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/support.ts`
- `packages/web/dsh-pmboard/src/application/query/QueryState.ts`
- `packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts`
- `packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts`
- `packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts`

### 下一步

t5 全分支测试固化后进入验收

---
