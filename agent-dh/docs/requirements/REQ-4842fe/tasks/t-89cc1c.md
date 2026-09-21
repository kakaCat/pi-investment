# t-89cc1c 失败暂停、告警弹框与返工回上游

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
失败暂停、告警弹框与返工回上游

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：fullstack

## 得到什么结果

失败后子卡退回并留痕、autoRun=false、高优告警发出、后续卡不执行；无任何自动重跑；弹框三选各自生效；退上游重批准后卡数不变且被改卡有 revisions(update)；自动链不产生 done→in_progress
验证：npx vitest run tests/failure-handling.test.ts（8 例）；代码可查：src/adapters/FailureAlert.ts 的 popupInstructionFor（弹框指令壳，告知窗口如何发起会话内弹框）。

## 实施方案（implementation）
失败分类 → 子卡退回+attempt+1+revisions(rollback)+失败评论 → autoRun=false → feishu_notify(high) + ask_user_question 三选处置；「退回上游」走 implementing→design（人工门），重批准计划后就地更新受影响父卡并写 revisions(update)；补 done→in_progress 重开与 revisions(reopen)。

## 上游产出摘要（dependsSummary）
- AdvanceChain 用例：事件链执行器

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T18:38:05.567Z，窗口 session-d41c9696-eb63-4a47-9018-68884d1f1fc8）

干活失败时不再闷头重试：失败的子卡退回重来一次（记下第几次尝试和失败原因），整条自动链立刻停住并发出高优告警，把「卡在哪、为什么、可怎么处理」讲清楚；人看完可以选重跑、退回上游重新描述需求、或取消，选哪个就按哪个走。退回上游重批计划时是改旧卡、不新增卡，并且每张被改的卡都留下修订记录。

### 完成项

- 新增 application/internal/failure-handling.ts：失败分类 + rollbackSubtask（退回 todo + attempt+1 + revisions(rollback) + 失败评论 + 执行记录置失败）+ appendRevision
- AdvanceChain 失败分支：先回退子卡再暂停，并调用 alert 端口发高优告警（含卡位/原因/已做处理/可选处置）
- 新增 application/use-cases/HandleFailure.ts：openFailurePopup 三选弹框 + handleFailureChoice（重跑/退回上游/取消）
- 新增 application/internal/rework-update.ts：重批准计划后就地更新既有父卡（不新增卡），逐卡 revisions(update)
- MoveTask 增 done→in_progress 重开的 revisions(reopen) 留痕
- ports 增 FailureAlertPort；新增 adapters/FailureAlert.ts（日志 + 会话投递，best-effort 永不抛）并接线
- 新增 tests/failure-handling.test.ts（8 例）+ tests/helpers/plan-task.ts；全量 122 文件 1484 例通过

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/failure-handling.ts`
- `packages/pages/dsh-pmboard/src/application/internal/rework-update.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/HandleFailure.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/AdvanceChain.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/MoveTask.ts`
- `packages/pages/dsh-pmboard/src/adapters/FailureAlert.ts`
- `packages/pages/dsh-pmboard/src/application/ports.ts`
- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/tests/failure-handling.test.ts`

### 下一步

t9 并发上限与冲突两级防线

---

> **口径修订（2026-09-21，用户裁定；requirement §8 #17）**：失败后的交互面**只有会话内弹框**。
> 上文 implementation 里写的 `feishu_notify(high)` 作废；实装 = 弹框文本经 alert 端口投递到来源会话
> （`adapters/FailureAlert.ts`，best-effort 永不抛），宿主日志仅作排障留痕；不发飞书、不接通知面。
> 需求 §6.6 与 `design/observability` §3 已同步改写。

