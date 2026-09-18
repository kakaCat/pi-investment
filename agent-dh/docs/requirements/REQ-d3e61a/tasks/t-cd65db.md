# t-cd65db 验收单说人话：你能看懂每项在确认什么

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
验收单说人话：你能看懂每项在确认什么

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：fullstack

## 验收标准
现网真实验收单 → 判定不合格；重述后每项返回可读的业务结果描述

## 实施方案（implementation）
验收单每项增加业务语言重述字段；前端渲染需求级+任务级并列

## 上游产出摘要（dependsSummary）
- 验收项必须能照着验

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T14:37:22.907Z，窗口 session-e1fc9bb5-906c-4d20-92fc-cbd5f3e2a512）

验收单说人话完成：验收项从「只放一串命令」改为「【业务标题】验收：怎么验」——用户一眼看出这项在确认什么业务结果；并迁移两条断言（语义不变，只是文案按新格式升级）。

### 完成项

- AcceptanceSheetSpec 任务级 criterion 改为 fmt('【{title}】验收：{detail}')：先业务结果、后怎么验。标题即业务语言（由 T-10 的三要素约束保证），detail 是无验收标准时的"交付完成"兜底
- 设计取舍：不新增字段——`VerificationItem` 在 protocol.ts（被占）里，且前端渲染只读 criterion；把业务语言并进 criterion 是零协议改动的正解
- 标题为空回退到 id（不产生空的【】）；需求级项保持人工写的业务常量（不套【】格式，避免形式主义）
- tests/sheet-business-language.test.ts 6 条：新格式、无标准兜底、空标题回退、需求级保持常量，以及一条**回归对照**——旧格式（只有命令）过不了"先说业务"判据，而新格式能过（证明这次改动确实解决了"看不懂"）
- 迁移两条既有断言：domain/acceptance-sheet.test.ts:44 与 verification-sheet.test.ts:60（代码里写明"验的是顺序与来源，语义不变，只是文案随格式升级"）
- 全量 1113 passed / 失败回到基线 6 个、tsc 改动面 0 错误、client 产物重建且与备份逐字节一致

### 改动文件

- `packages/pages/dsh-pmboard/src/domain/workflow/AcceptanceSheetSpec.ts`
- `packages/pages/dsh-pmboard/tests/sheet-business-language.test.ts`
- `packages/pages/dsh-pmboard/tests/domain/acceptance-sheet.test.ts`
- `packages/pages/dsh-pmboard/tests/verification-sheet.test.ts`

### 下一步

剩余 5 张卡：T-5/T-6/T-13/T-14/T-17/T-18 —— 多为落点被占或依赖未满足，需先核实占用面是否已释放。

---
