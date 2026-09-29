# t-00bed8 自动链任务执行与接手推进改经执行助手并带快照

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
自动链任务执行与接手推进改经执行助手并带快照

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
cd packages/web/dsh-pmboard && npx vitest run tests/advance-chain.test.ts tests/execute-task.test.ts 通过；grep -rn "executions.push(" src/application src/http 无输出（写点仅助手内）。

## 实施方案（implementation）
AdvanceChain.ts:141 改 openExecution、:169-171 改 closeExecutions、:205 rollup 补 snapshot；ExecuteTask.ts:222 改 openExecution（outcome=failed 的 born-failed 不写 start）、:255-258 与 :269-271 改 closeExecutions；自动链会话码用 safeWindowKey(deps, exec) 解析（system 视为无会话），解析不到则不写快照。pm-capture-root.ts:133 的 applyPickupAdvance 传 snapshot: snapshotProviderFor(deps, windowKey)；src/index.ts:166 启动对账 applyTaskRollup/applyPickupReconcile 明确不传 snapshot。

## 上游产出摘要（dependsSummary）
- 新增执行快照收敛助手（任务执行唯一写入口）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T06:55:10.957Z，窗口 session-4ac706ad-a118-4505-b6ac-ce9355d92f5d）

自动链里的任务执行也改经统一执行助手并带上写时快照：父卡开工/子卡执行写 start、收尾写 end/delta；接手推进按有无会话决定是否带快照，启动对账等无会话路径诚实不传。t-00bed8 与四张子卡全部完成。

### 完成项

- AdvanceChain 父卡开工改经 openExecution、收尾改经 closeExecutions、rollup 补 snapshot 提供者；会话码经 safeWindowKey 解析（system → 无会话，不写快照）
- ExecuteTask 子卡执行改经 openExecution（born-failed 不写 start）、完工/失败改经 closeExecutions
- pm-capture-root 的 applyPickupAdvance 传 snapshotProviderFor；src/index.ts 启动对账明确不传 snapshot（无会话不伪造）
- grep -rn "executions.push(" src/application src/http → 仅 token-usage.ts 助手内（FR-8 唯一写点）
- npx vitest run tests/advance-chain.test.ts tests/execute-task.test.ts → 2 files / 19 tests 全绿
- 实施链 dev→integrate→review→test 全部 done，FINALIZE_PARENT 完成

### 改动文件

- `src/application/use-cases/AdvanceChain.ts`
- `src/application/use-cases/ExecuteTask.ts`
- `src/wiring/pm-capture-root.ts`
- `src/index.ts`

### 下一步

继续实施链下一张卡 t-a6293c（读路径把快照缺失与不可得同等计入 degraded）

---
