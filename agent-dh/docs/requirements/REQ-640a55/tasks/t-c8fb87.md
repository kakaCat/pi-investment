# t-c8fb87 让拆分骨架直出任务卡三要素节

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
让拆分骨架直出任务卡三要素节

## 解决什么问题
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
reqboard_decompose 后读 docs/requirements/<REQ>/tasks/<id>.md：## 在做什么 / ## 解决什么问题 / ## 得到什么结果 三节均在且正文非空；卡文件缺失时 reqboard_task_report 自造的骨架头同样含三节。npx vitest run tests/handoff.test.ts tests/decompose-tools.test.ts 全绿。

## 实施方案（implementation）
改 packages/pages/dsh-pmboard/src/application/use-cases/Decompose.ts:297-327 的骨架数组：## 目标→## 在做什么、## 背景摘要（context）→## 解决什么问题、## 验收标准→## 得到什么结果（范围/实施方案/上游产出摘要/执行方式提示保留，顺序按三要素打头）；改 ReportTask.ts:69-81 的兜底骨架头补三节；同步 tests/handoff.test.ts:100/171-173/260-261 的标题断言。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-19T11:24:33.396Z，窗口 session-98f2b4b4-cfff-4a90-baa9-214fc15d99d2）

拆分骨架与 task_report 兜底骨架头现在都直出业务三要素节（## 在做什么 / ## 解决什么问题 / ## 得到什么结果），两条建卡路径同构；改名做成原子操作——同步改掉 AmendTaskAcceptance 的段定位正则（新旧标题二选一命中），避免 T-9 改卡通道静默失效。

### 完成项

- Decompose 骨架改名：## 目标→## 在做什么、## 背景摘要（context）→## 解决什么问题、## 验收标准→## 得到什么结果；范围/实施方案/上游产出摘要/执行方式提示保留，并加契约注释说明这三节是门禁契约
- ReportTask 兜底骨架头补齐三节（此前只有 # 标题 + > 验收标准 引用块），两条建卡路径同构
- 空节兜底：context 为空 → 「（未填写——开工前补充这张卡要解决的业务问题）」，acceptance 为空 → 「（未填写）」
- 原子改名：AmendTaskAcceptance.ts 段定位正则改为 /^##\s*(?:得到什么结果|验收标准)/ —— 旧卡（存量）继续可改，新卡也能改
- tests/handoff.test.ts 新增「三要素都在且正文非空」断言（逐节切到下一个 ## 为止再判空），并同步 4 处标题断言与 1 处用例名
- 反向验证：把骨架节名改回 ## 目标 → handoff 3 条用例变红并报「缺少骨架节 ## 在做什么」；还原后全绿
- 回归：npx vitest run → 98 文件 / 1265 条全绿（基线 97/1250）；4 个聚焦文件 59 条全绿

### 改动文件

- `packages/pages/dsh-pmboard/src/application/use-cases/Decompose.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/ReportTask.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/AmendTaskAcceptance.ts`
- `packages/pages/dsh-pmboard/tests/handoff.test.ts`

### 下一步

t-fb5e66：把三要素门禁接上执行链（拆分出口 + 单卡结单），并给本需求剩余老式卡补三要素节。

---
