# t-fd25e0 端到端验收与文档更新

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
端到端验收与文档更新

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
pnpm vitest run 既有用例不退化；真实台账副本读取+渲染无异常；层边界门禁通过（domain 无运行时 dsh import、ctx.workflowEngine 仅在 adapter）；verification.md 含可复核证据

## 实施方案（implementation）
跑通并留证：主用例（零点击跑到 accepting）、故障注入、返工、并发；写 docs/requirements/REQ-4842fe/verification.md；更新 agent-dh 项目说明书相关章节。

## 上游产出摘要（dependsSummary）
- 失败暂停、告警弹框与返工回上游
- 并发上限与冲突两级防线
- 工具面与批准计划接线（合并拆分确认门）
- 看板 UI：父子卡展示与 autoRun 控制面

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T19:08:14.315Z，窗口 session-d41c9696-eb63-4a47-9018-68884d1f1fc8）

端到端验收跑通并留下可复核证据：dsh-pmboard 全量 126 文件 / 1512 例全绿；用真实台账副本（revision 2185、51 需求、234 任务）跑了一遍看板渲染，零异常；层边界（domain 无运行时依赖、workflowEngine 只在 adapter）与插件 schema 冒烟都过；验收材料写进 verification.md，说明书补了「子任务层与自动链控制面」一节。

### 完成项

- 全量回归：cd packages/pages/dsh-pmboard && npx vitest run → 126 文件 / 1512 例全绿
- 真实台账副本读取 + 渲染：/tmp/render-check.mts 只读副本（rev 2185 / 51 需求 / 234 任务）→ 泳道 51024B、列表 19230B，零异常
- 层边界证据：domain 无 node:/@deepseek-ai/ 运行时 import；ctx.workflowEngine 实现只在 adapters/WorkflowEngineRunner.ts（其余为注释）
- 插件 schema 冒烟 20/20（本需求把 dsh-pmboard 补进 PLUGINS）
- 消息/尺寸门禁收绿：把并发窗口新增的 popupInstructionFor 6 行拼接式文案改为「逐行数组 + join + fmt」（行为不变）→ adapters 回到基线 5
- 写 docs/requirements/REQ-4842fe/verification.md（含复现命令、已知缺口、并发说明）
- 更新说明书章节：docs/architecture/reqboard-stage-detail.md §6「子任务层与自动链控制面」+ front-matter updated

### 改动文件

- `docs/requirements/REQ-4842fe/verification.md`
- `docs/architecture/reqboard-stage-detail.md`
- `packages/pages/dsh-pmboard/src/adapters/FailureAlert.ts`

### 下一步

交付材料备齐，交棒 accepting（reqboard_submit kind=verification）待人工裁决。

---
