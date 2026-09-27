# t-8d4af7 读方改造 D：门禁、查询与 Dive

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
读方改造 D：门禁、查询与 Dive

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① `npx vitest run src/application/internal/` 全绿；② RTM/覆盖门禁读到的任务键集断言一致（TC-8.9）；③ 全仓残留静态检查：`grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks' src/` 命中数为 0（TC-8.12）；④ `npx tsc --noEmit` 退出码 0。

## 实施方案（implementation）
改 src/application/internal/*（plan-landing、lazy-expand、rollup、rtm-yaml、rework-update、verdicts、failure-handling、support、confirm-settle、agent-handle、capture-section、verification-doc-writer）、src/application/query/*（QueryState、QueryStageDetail、QueryRequirementToken）、src/application/dive/idle-capture-actions.ts、src/application/gate/handlers/h3-inject.ts。完成后跑全仓 grep 断言零残留。

## 上游产出摘要（dependsSummary）
- 台账 schema v9：移除 tasks

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T14:12:34.501Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

门禁、查询与 Dive 这一层对任务的读取全部改走队列，全仓"还在读台账任务"的残留从 92 处清到 0。其中一处特别值得记：给系统提示词注入"当前任务"的那段代码是**同步**接口，而任务入口是异步的——改成"同步快照 + 变更订阅"并严格区分三态（没加载 / 加载了但是空的 / 有任务），**没加载时整体不显示任务块，而不是显示"没有任务"**；刷新失败则保留上一次快照并留日志，不会因为一次抖动把整段提示语清空。

### 完成项

- internal/ 10 文件（support/agent-handle/failure-handling/lazy-expand/rework-update/verdicts/verification-doc-writer/rtm-yaml/capture-section/node-settlement）改经 taskStore 或加 tasks 入参（D4）
- query/ 4 文件（QueryState/QueryStageDetail/QueryStageOverview/QueryRequirementToken）+ dive/ 2 文件 + gate/handlers/{h3-inject,h2-compact} 全部改造
- gate-wiring.ts（D17）：提示词段的同步缓存 + subscribe 刷新；三态（未加载/已加载为空/有值）——未加载时整体略过任务块，不谎报「没有任务」；刷新失败保留上次快照并 logger 留痕
- wiring/pm-capture-root.ts：补 taskStore 注入（组合根直传实例，避免惰性 getter 在构造期求值的时序 bug）
- 全仓残留静态检查（ledger.tasks|snapshot().tasks|changed.tasks）从 92 归零；注释字面串一并清理（0 必须是代码+注释都干净的 0）
- Lead 独立复核：src 中带本次改造签名的类型错误 0；pnpm build 退出码 0；plugin-schema 冒烟 21 passed

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/support.ts`
- `packages/web/dsh-pmboard/src/application/internal/capture-section.ts`
- `packages/web/dsh-pmboard/src/application/query/QueryState.ts`
- `packages/web/dsh-pmboard/src/application/dive/idle-capture-actions.ts`
- `packages/web/dsh-pmboard/src/application/gate/handlers/h3-inject.ts`
- `packages/web/dsh-pmboard/src/gate-wiring.ts`
- `packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts`

### 下一步

t-e77b06 看板实测回归（待投产窗口）

---
