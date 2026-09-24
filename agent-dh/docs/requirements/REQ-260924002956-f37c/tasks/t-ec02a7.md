# t-ec02a7 回归：肯定路径不变 + 无 from 文案边界 + 全量 vitest

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
回归：肯定路径不变 + 无 from 文案边界 + 全量 vitest

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
npx vitest run packages/web/dsh-pmboard 全绿（0 failed）；边界断言存在且通过：有 from 的闸门负分支含「节点仍在」、肯定路径 enqueue=1。

## 实施方案（implementation）
在 tests/gate-handlers.test.ts 与 tests/gate-aware-questions.test.ts 补上述边界断言；执行全量包测试并摘录统计（passed/failed）。

## 上游产出摘要（dependsSummary）
- 修复：题目拆两段 + 拒绝短路 + G0 挪段 + H4 无 from 不编现状

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-23T16:40:51.797Z，窗口 session-4799e386-677d-431b-bb36-c752ad82640b）

回归卡把"不许修反"的两侧都钉住了：有 from 的闸门照旧印「节点仍在 {from}」，肯定路径照旧两段合计四问且 G0 只登记一次。本次范围内 6 个文件 87 条测试全绿；全量包仍有 96 条红，逐条取证全部来自隔壁窗口的在飞重构（tsc/尺寸/层边界/地址段），本次未引入——唯一被我引入的那条 output-contract 已修复。

### 完成项

- tests/gate-handlers.test.ts：新增「有 from 的闸门负分支仍印节点仍在 {from}」——断言 from='design' 时文案含「节点仍在 design」（防把 H4 改反）
- tests/gate-aware-questions.test.ts：新增「肯定路径对照」——两段合计题目 id 恰为 name/category/difficulty/doc_location、gate 只为第二段声明（undefined→G0）、chain.enqueued=1、pending 的 gate=G0
- 本次范围测试全绿：output-contract + capture-tool + gate-aware-questions + gate-handlers + capture.test + ask-confirm = 6 文件 87 条通过
- 全量包实测：npx vitest run packages/web/dsh-pmboard → 1674 passed / 96 failed（13 个文件）；13 个文件全部是隔壁窗口在飞改动造成，非本次引入
- 归属取证：① typecheck 的 23 条 TS 报错不落在我改的三个文件（全在 template/resolve.ts、gate-wiring.ts 等）② size-budget 唯一超标项是 src/index.ts=431 行（我没动）③ layer-boundary 唯一越界项是 application/internal/diag-log.ts -> node:path（我没动）④ 13 个红文件里只有 template-address-injection.test.ts 引用我改的模块（只 import createH4ResumeHandler），它那两条红在 boundSectionText/buildNodeInputPackage 的地址段断言（design/feature 肯定路径），与 H4 负分支无关
- 另：本次曾引入 1 条红（output-contract 的 defineCaptureTool 扫描出新增返回键 ok/out）——已改掉（失败回执不再用自造包装对象），复跑 output-contract 转绿，全量数字由 97 failed 降到 96 failed

### 改动文件

- `agent-dh/packages/web/dsh-pmboard/tests/gate-handlers.test.ts`
- `agent-dh/packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts`
- `agent-dh/packages/web/dsh-pmboard/src/application/use-cases/CaptureRequirement.ts`

### 下一步

t-a8ed88 真机验证卡：需重启加载新代码（且要在未绑定窗口走一次拒绝路径）。当前全量 0 failed 未达（隔壁窗口在飞改动 96 条红），留待人在验收门裁定。

---
