# t-b03e8b ExecuteTask 用例：单张子卡闭环

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
ExecuteTask 用例：单张子卡闭环

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
凭证三项任一不过则子卡不 done；存在未 done 子卡时父卡不得 done；改了 packages/pages/*/src 但 lib/client.js 未更新则凭证不过

## 实施方案（implementation）
新增 application/use-cases/ExecuteTask.ts：子卡 in_progress → WorkflowRunner.start → 生成子卡 report → 子卡凭证门（report 非空、文件 mtime≥开工、stopReason=completed；保留 pages 构建新鲜度，豁免窗口活动与 60s 节流）→ 子卡 done。

## 上游产出摘要（dependsSummary）
- 数据契约扩展与迁移兼容
- WorkflowRunner 端口 + 引擎 adapter + 脚本契约门禁

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T18:31:54.501Z，窗口 session-d41c9696-eb63-4a47-9018-68884d1f1fc8）

一张子卡现在能自己跑完一整圈：开工 → 派给子代理干活 → 把产出写成完工记录 → 过三道凭证（有汇报、改了真实存在的文件、任务真跑完了）→ 收工。凭证不过就卡住不让收工，不会出现「没干活也算完成」；父卡在子卡没全完前也收不了工。改了页面插件源码但没重新构建的，同样过不了。

### 完成项

- 新增 application/use-cases/ExecuteTask.ts：claim(in_progress+执行记录) → WorkflowRunner.start → 产出解析生成 report/lastRun → 子卡凭证门 → done（幂等：已 done 直接返回）
- 新增 application/internal/subtask-evidence.ts：子卡三项凭证（report 非空 / 文件 mtime≥开工 / run completed 且产出非空）+ 保留页面构建新鲜度；豁免窗口活动与 60s 节流；附父卡 INV-5 收尾门
- protocol.ts 增 TaskRunEvidence 与 TaskRecord.lastRun（run 证据的持久化载体）
- support.ts assertDoneEvidence 按卡片角色分派：子卡走新口径，父卡先过 INV-5（有未 done 子卡即拒）
- 产出解析不猜文件：子代理只回文本时 filesChanged 为空 → 凭证门拦下（宁可不收工也不编文件）
- 新增 tests/execute-task.test.ts（11 例，覆盖三项凭证、构建新鲜度、引擎缺失、幂等、INV-5）

### 改动文件

- `packages/pages/dsh-pmboard/src/application/use-cases/ExecuteTask.ts`
- `packages/pages/dsh-pmboard/src/application/internal/subtask-evidence.ts`
- `packages/pages/dsh-pmboard/src/application/internal/support.ts`
- `packages/pages/dsh-pmboard/src/shared/protocol.ts`
- `packages/pages/dsh-pmboard/tests/execute-task.test.ts`

### 下一步

t6 懒展开：父卡开工同事务落子卡链

---
