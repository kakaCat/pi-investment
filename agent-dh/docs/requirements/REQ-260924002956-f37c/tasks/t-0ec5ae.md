# t-0ec5ae 修复：题目拆两段 + 拒绝短路 + G0 挪段 + H4 无 from 不编现状

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
修复：题目拆两段 + 拒绝短路 + G0 挪段 + H4 无 from 不编现状

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
t1 的三个测试文件全绿；跑 npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/capture.test.ts 肯定路径仍绿（四问合计 4 问、创建后状态 brainstorming）；git diff --stat 只含 capture-mapping.ts / CaptureRequirement.ts / h4-resume.ts（可含测试文件）。

## 实施方案（implementation）
按 design/design.md「修复方案」三处改动落地；不动绑定检查/弹框不可用/缺名称/创建推进等其它分支；改完跑 t1 的命令确认转绿。

## 上游产出摘要（dependsSummary）
- 固化拒绝路径复现：加三条失败用例（红）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-23T16:39:12.558Z，窗口 session-4799e386-677d-431b-bb36-c752ad82640b）

拒绝路径现在是终端路径：选了「不需要立项」不再追问类型/难度/文档位置（第二段根本不发起），也不再被登记成一次闸门作答、不再回发「闸门待改进」；而正常立项照旧一次问完四问并在同一次调用内创建。三条原红用例转绿，肯定路径用例未受影响。

### 完成项

- capture-mapping.ts：拆出 buildCaptureIntentQuestions（第 1 段=立项意愿+名称，含 ✖️ 不需要立项）与 buildCaptureDetailQuestions（第 2 段=类型/难度/文档位置）；buildCaptureQuestions 保留为两段拼接的兼容导出（四问内容与顺序逐字不变）
- CaptureRequirement.ts：新增 askOrFail（两段共用同一套失败语义，文案与改造前逐字一致）；第一段 ask **不带 gate**，命中拒绝前缀即写拒绝留痕 + 立即 return notCreated（不发起第二段，回执不再带未作答三问的 defaults_used）；第二段 ask 带 gate:'G0'，最终 mapped = 两段答案合并
- h4-resume.ts：负分支改为「有 from 才写节点仍在 {from}，无 from 只写 {gate} 未通过」
- 跑 npx vitest run capture-tool / gate-aware-questions / gate-handlers / capture.test.ts：4 files passed，55 tests passed（含 t1 三条原红用例与肯定路径四问口径）
- git diff 自查：本次仅改 3 个源文件 + 3 个测试文件；工作区其余改动均是隔壁窗口在飞的前序改动，未触碰

### 改动文件

- `agent-dh/packages/web/dsh-pmboard/src/application/internal/capture-mapping.ts`
- `agent-dh/packages/web/dsh-pmboard/src/application/use-cases/CaptureRequirement.ts`
- `agent-dh/packages/web/dsh-pmboard/src/application/gate/handlers/h4-resume.ts`
- `agent-dh/packages/web/dsh-pmboard/tests/capture-tool.test.ts`
- `agent-dh/packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts`
- `agent-dh/packages/web/dsh-pmboard/tests/gate-handlers.test.ts`

### 下一步

t-ec02a7 回归卡：补"有 from 的闸门仍印节点仍在"与"肯定路径 G0 入队 1 次"两条边界断言，并跑全量包测试。

---
