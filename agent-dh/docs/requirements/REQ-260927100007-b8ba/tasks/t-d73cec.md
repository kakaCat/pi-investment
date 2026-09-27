# t-d73cec Dive 采集半停止直投 + 投递白名单

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
Dive 采集半停止直投 + 投递白名单

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/dive-manager-alignment.test.ts tests/dive-round-driver.test.ts 通过：同阶段连续两条人类消息 → onStagePrompt 0 次、不产生额外轮次；armed+active 时投递且 source.kind==="dive"。

## 实施方案（implementation）
删 session-driver.ts driveIdle 的阶段纪律投递（保留 injectionLog 留痕与 R1）；里程碑催办改为登记+requestDrive，由 round 半在 armed+active 时投递；在 reqboard-dive-mode.md 补「投递白名单」节。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T03:45:55.862Z，窗口 session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8）

Dive 采集半不再自己往会话里塞消息：阶段纪律不再重复投递（它本就在每次请求的 system prompt 里，旧投递会额外起一轮"只有纪律、没有提问"的 agent loop），里程碑催办改成"只登记"，armed+active 时由 round 半按回合投递、其余情况只写一条台账评论——一条人类消息不再换来两轮 loop。

### 完成项

- 采集半零投递：删除 driveIdle 的阶段纪律直投（保留注入留痕与节点结算信号）
- 里程碑催办改为登记 onMilestoneNotice；round 半新增 queueReminder，经 requestDrive→createRoundMessage 投递（source.kind=dive、走预留/准入计数），投递失败放回不静默丢
- 组合根按投递白名单分流：armed+active→round 半；非 armed→只写台账 comment；round 未装配→响亮 warn
- reqboard-dive-mode.md「投递白名单」与节点流程图同步（白名单：pending-confirm wake / 闸门链 H4 / 失败告警）
- 测试：dive 相关 5 文件 95/95 全绿；capture-hook / acceptance-criteria / isolate-node-context 三条旧契约改写为"采集半零投递 + 留痕照旧"

### 改动文件

- `packages/web/dsh-pmboard/src/application/dive/session-driver.ts`
- `packages/web/dsh-pmboard/src/application/dive/round-driver.ts`
- `packages/web/dsh-pmboard/src/application/dive/idle-capture-actions.ts`
- `packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts`
- `packages/web/dsh-pmboard/tests/capture-hook.test.ts`
- `packages/web/dsh-pmboard/tests/acceptance-criteria.test.ts`
- `packages/web/dsh-pmboard/tests/isolate-node-context.test.ts`
- `packages/web/dsh-pmboard/tests/dive-session-driver-wiring.test.ts`
- `packages/web/dsh-pmboard/tests/dive-manager-alignment.test.ts`
- `packages/web/dsh-pmboard/tests/dive-round-driver.test.ts`

---
