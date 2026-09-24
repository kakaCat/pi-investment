# t-dbed6b progress 接口透出 promptDifficulty

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
progress 接口透出 promptDifficulty

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

怎么验：① `cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/session-progress.test.ts` → 4 用例绿（有 promptDifficulty 的需求透出该值、老记录透出 null）；② `curl -s 'http://127.0.0.1:13080/dashboard/api/reqboard/session/<sessionId>/progress'` 看 data.requirement.promptDifficulty 字段：有值/为 null。

## 实施方案（implementation）
stages.ts 加一行字段透传；conversation-progress.ts 接口类型加可选字段；在既有 stages/api 测试里补 TC-10 两条断言（有字段/无字段）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-23T06:57:38.568Z，窗口 session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d）

progress 接口透出 promptDifficulty：stages.ts requirement 对象补 promptDifficulty: target.promptDifficulty ?? null；conversation-progress.ts ProgressPayload 类型同步加可选字段；session-progress 测试补 TC-10（有记录透出值/老记录透出 null），4 用例全绿。

### 完成项

- stages.ts progress requirement += promptDifficulty
- conversation-progress.ts ProgressPayload += promptDifficulty?: string | null
- tests/session-progress.test.ts +TC-10 两条断言

### 改动文件

- `src/http/routers/stages.ts`
- `src/client/conversation-progress.ts`
- `tests/session-progress.test.ts`

### 下一步

t4 节点面板渲染器 node-panel.ts

---
