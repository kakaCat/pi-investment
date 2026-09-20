# t-6ccc5c 看板「退回返工」收敛为等价入口

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
看板「退回返工」收敛为等价入口

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pnpm --filter dsh-pmboard test 的 T-E4，断言看板 rework 与自动回退行为一致（同一 use-case 调用）。

## 实施方案（implementation）
src/http/routers/verdicts.ts 的 rework 端点复用自动回退 use-case，删除独立分支，避免双实现漂移。

## 上游产出摘要（dependsSummary）
- FR-8 验收失败自动回退实施（application）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T02:33:05.546Z，窗口 session-7cfa4169-c6dd-4608-b5c4-fb5af4f69a54）

看板裁决实现已收敛为与弹框通道同一用例：路由不再内联一份裁决逻辑，改为委托 application 的 applyVerdicts（含 failed 自动回退），消除双实现漂移。

### 完成项

- http/routers/verdicts.ts：删除内联裁决循环（原与 application/internal/verdicts.ts 重复），改为 const applied = applyVerdicts(...)
- 路由保留前置校验（状态/版本/项存在性）以维持既有 400 语义
- 「退回返工」端点保留且幂等：裁决已自动回退后再次调用被拒、不重复建卡（用例已覆盖）

### 改动文件

- `packages/pages/dsh-pmboard/src/http/routers/verdicts.ts`

### 下一步

需求全部任务完成 → rollup 进 accepting

---
