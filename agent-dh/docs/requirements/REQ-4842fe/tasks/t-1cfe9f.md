# t-1cfe9f WorkflowRunner 端口 + 引擎 adapter + 脚本契约门禁

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
WorkflowRunner 端口 + 引擎 adapter + 脚本契约门禁

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

含 ctx.subagent 的脚本在生成阶段即被门禁拒绝；真实引擎冒烟：最简脚本跑通且 stopReason=completed、dispose 后无悬挂；引擎缺失时显式失败（不静默成功）
验证：npx vitest run tests/workflow-script-contract.test.ts；真实引擎冒烟：npx tsx packages/pages/dsh-pmboard/scripts/workflow-engine-smoke.ts（输出 stopReason=completed）。

## 实施方案（implementation）
application/ports.ts 增 WorkflowRunner 端口；新增 adapters/WorkflowEngineRunner.ts 唯一封装 ctx.workflowEngine.start（await run.result + finally dispose，stopReason 非 completed 翻译为 ok:false）；新增子卡脚本生成器（仅 agent/phase/log）与静态门禁 assertScriptContract（hook 白名单）。

## 上游产出摘要（dependsSummary）
- domain：stageKind 枚举与子卡映射表

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T18:29:51.301Z，窗口 session-d41c9696-eb63-4a47-9018-68884d1f1fc8）

子卡现在能真的把活派给子代理去干：插件里加了一条唯一的执行通道，把「跑一次工作流」收敛成一个调用，并且生成脚本时会先做静态检查——一旦脚本里出现历史事故里的写法（用不存在的 ctx、调被禁的工具、把状态改动写进脚本），在生成阶段就直接失败，不带着错脚本去跑。引擎不可用时明确报失败，不会假装成功。

### 完成项

- ports.ts 增 WorkflowRunner 端口（WorkflowRunOutcome/WorkflowStartInput）并挂到 UseCaseDeps.workflow（缺省即显式失败）
- 新增 adapters/WorkflowEngineRunner.ts：唯一封装 ctx.workflowEngine.start，await result + finally dispose，stopReason 非 completed 翻译为 ok:false
- 新增 application/internal/workflow-script.ts：WORKFLOW_HOOKS 白名单（agent/parallel/pipeline/phase/log）+ assertScriptContract + generateSubtaskScript（生成即过门禁）
- 契约门禁先剥离字符串字面量再扫描，避免 prompt 文本里的示例被误伤
- index.ts 注入 workflowEngine 服务并装配 runner（引擎缺失时 debug 留痕）
- 新增 tests/workflow-script-contract.test.ts（11 例，含适配器三态翻译）；真实引擎冒烟 scripts/workflow-engine-smoke.ts 通过

### 改动文件

- `packages/pages/dsh-pmboard/src/application/ports.ts`
- `packages/pages/dsh-pmboard/src/application/internal/workflow-script.ts`
- `packages/pages/dsh-pmboard/src/adapters/WorkflowEngineRunner.ts`
- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/tests/workflow-script-contract.test.ts`
- `packages/pages/dsh-pmboard/scripts/workflow-engine-smoke.ts`

### 下一步

t5 ExecuteTask：子卡 in_progress → run → report → 凭证 → done 的闭环

---
