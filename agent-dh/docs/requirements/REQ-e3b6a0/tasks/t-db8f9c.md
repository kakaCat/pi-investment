# t-db8f9c 修投递死链路：AgentDeliverer 统一投递形状

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
修投递死链路：AgentDeliverer 统一投递形状

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

① grep -rnE "^[[:space:]]*agents\??\.?[[:space:]]*\.?followup\(" packages/pages/dsh-pmboard/src 返回 0 命中（语句位置的死调用；注释里的历史写法不计）；② npx vitest run tests/agent-deliverer.test.ts 全绿（7/7：在线 → delivered=true 且消息形状为 {id,role:user,content,source}；离线 / 无 followup / followup 抛错 / agents.get 抛错 / 服务缺失 → delivered=false 且不抛）；③ 既有催办路径断言仍全绿：npx vitest run tests/capture-hook.test.ts 通过（含 4 条里程碑超时提醒断言）；④ 全量 npx vitest run 与 pristine HEAD 基线 diff 后新增失败为 0

## 实施方案（implementation）
新增 adapters/AgentDeliverer.ts；index.ts 的 onStagePrompt 改用它；CaptureHook 催办路径补测试

## 上游产出摘要（dependsSummary）
- 实测 V1 契约：surface replace 是否唤醒 driver

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T03:59:30.983Z，窗口 session-878da638-a076-4266-ae40-70a2390060f2）

投递死链路修好：新增 adapters/AgentDeliverer.ts 作为唯一投递实现（三态全判、永不抛、结构复刻 createUserMessage 形状以规避本包解析不到 @deepseek-ai/dsh-llm），并把组合根 index.ts 的 onStagePrompt 从 agents.followup(id,msg) 改过来。这一修同时救活两个自诞生起从未生效的功能：状态转移纪律注入（REQ-31e11f t5）与产物超时 30 分钟催办（REQ-2e9473 t09）。

### 完成项

- 新增 src/adapters/AgentDeliverer.ts：正确形状 agents.get(windowKey)?.followup({id,role,content,source})；agents 服务缺失 / 窗口离线 / 无 followup / followup 抛错 / agents.get 抛错 五种失败全部返回 {delivered:false, reason} 且不抛
- 消息结构复刻 createUserMessage（读源码确认其实现为 deepFreeze(structuredClone({...input, role:"user", id: brandString(randomUUID())}))），故不 import @deepseek-ai/dsh-llm——本包依赖树解析不到该包（NodeIsolationAdapter 文件头记过同一坑），import 会让 tests/apply-wiring.test.ts 连带炸掉
- ports.ts 增 DeliveryResult + AgentDeliveryPort
- index.ts 组合根构造单一 deliverer 实例，onStagePrompt 改用它（成功 debug / 失败 warn 并带 reason）
- 新增 tests/agent-deliverer.test.ts 7 用例（AC-5.1/5.2 全覆盖）
- 死调用精确判据（语句位置）grep -rnE "^\s*agents\??\.?\s*\.?followup\(" src → 0 命中；原写法仅作为反面教材留在注释里
- 门禁核验：tsc 无新增错误（仅剩基线 update-task-card.ts 一条）；全量 vitest 与 pristine HEAD 基线逐条 diff → 新增失败 0（14 vs 15）

### 改动文件

- `packages/pages/dsh-pmboard/src/adapters/AgentDeliverer.ts`
- `packages/pages/dsh-pmboard/src/application/ports.ts`
- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/tests/agent-deliverer.test.ts`

### 下一步

t5 H2 压缩接线（h2-compact 调 isolateNodeContext + 输入包自足判定，挂到 t3 框架）；t6 H3 注入 + 难度映射

---
