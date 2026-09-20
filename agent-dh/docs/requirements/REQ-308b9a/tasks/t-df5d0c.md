# t-df5d0c 裁决后回填验收结果表

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
裁决后回填验收结果表

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pnpm --filter dsh-pmboard test，tests/verdicts-and-rework.test.ts 的 T-I9 断言 verification.md 的验收结果表包含 编号/验收项/状态/验收人/验收时间 五列。

## 实施方案（implementation）
verdicts 落地后按新 sheet 重渲染并覆写 docs/requirements/<REQ>/verification.md 的「验收结果」段。

## 上游产出摘要（dependsSummary）
- FR-8 验收失败自动回退实施（application）
- verification.md 结构化生成 + 9 类文档完整性检查

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T02:26:29.122Z，窗口 session-7cfa4169-c6dd-4608-b5c4-fb5af4f69a54）

FR-7 收尾：裁决落库后自动重渲染 verification.md，把「验收结果」表按最新裁决回填（含编号/验收项/状态/验收人/验收时间）。

### 完成项

- application/internal/verification-doc-writer.ts：两通道共用的回填单点（缺 docs 端口则跳过，不阻断裁决）
- AcceptSheet（弹框路径）与 http/routers/verdicts.ts（看板路径）在裁决后均调用回填
- RouterCtx.deps / ReqboardRouteDeps 增加可选 docs 端口；index.ts 注入 FileDocRepository
- tests/verdicts-and-rework.test.ts 新增 T-I9（断言回填后的结果表五列与状态）

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/verification-doc-writer.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/AcceptSheet.ts`
- `packages/pages/dsh-pmboard/src/http/routers/verdicts.ts`
- `packages/pages/dsh-pmboard/src/http/routers/shared.ts`
- `packages/pages/dsh-pmboard/src/http/routes.ts`
- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/tests/verdicts-and-rework.test.ts`
- `packages/pages/dsh-pmboard/lib/client.js`
- `packages/pages/dsh-pmboard/lib/client.cjs`

### 下一步

t8 文档同步（t7 门禁受基线 14 个既有失败阻塞，需先还债）

---
