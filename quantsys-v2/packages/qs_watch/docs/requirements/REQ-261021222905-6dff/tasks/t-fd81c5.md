# t-fd81c5 实现 trading_plan 工具双端（agent-dh 投资脑 + agent-ts fin-agent）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 trading_plan 工具双端（agent-dh 投资脑 + agent-ts fin-agent）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

双端工具契约测试绿：action 参数正确透传、请求形态一致、4xx 透传、缺账户不发请求。验证：① agent-dh `npx vitest run packages/tools/investment/tests/trading-plan-tool.test.ts`（5 passed）；② agent-ts `npx jest src/infrastructure/tools/__tests__/trading-plan-tool.test.ts`（2 passed，断言 plan.* 15 条路由在册与 PATCH 派发）；③ 4xx 透传：`curl -s -X POST http://127.0.0.1:5001/api/plans -H 'content-type: application/json' -d '{"account":"x","name":"y","horizon":"day","spec":{}}'` 应返回 400 且 code=PLAN_SPEC_INVALID（工具原样透传该错误码）。

## 实施方案（implementation）
agent-dh packages/tools 新增 TradingPlanTool（S-14）+ agent-ts src/infrastructure/tools 新增 trading-plan-tool（S-15）：action 枚举覆盖 IF-1~IF-15；账户取 agents.json 的 instance.account（不写死）；后端 PLAN_* 错误码原样透传；缺账户 AGENT_ACCOUNT_MISSING。

## 上游产出摘要（dependsSummary）
- 实现计划生命周期路由与编译预览

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:25:57.079Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

trading_plan 工具双端落地：共享客户端 13 方法 + 投资脑完整工具 + fin-agent 路由与工具，双端测试 7 例绿。

### 完成项

- quantsys-v2-client 新增 13 个计划方法（list/get/create/patch/apply/activate/pause/resume/close/preview/today/stats/reflect/reflections/blocked）
- agent-dh：TradingPlanTool（15 动作、账户取 DEFAULT_AGENT_ACCOUNT/agents.json、写操作带 actor=agent）+ prompt + 工厂注册
- agent-ts：V2_ROUTES 扩 PATCH 与 plan.* 15 条；新增 trading_plan 工具并注册进 groups/index
- agent-dh vitest 5 例绿（today/映射/patch 透传/缺参拦截/未知 action）；agent-ts jest 2 例绿（路由在册/PATCH 派发）
- 账户不写死：默认取实例账户常量；错误由后端 PLAN_* 原样透传

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2-client/src/client.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/tools/investment/src/tools/TradingPlanTool/TradingPlanTool.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/tools/investment/src/tools/TradingPlanTool/prompt.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/tools/investment/src/tools/TradingPlanTool/index.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/tools/investment/src/index.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/tools/investment/tests/trading-plan-tool.test.ts`
- `/Users/yunpeng/pi-investment/agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`
- `/Users/yunpeng/pi-investment/agent-ts/src/infrastructure/tools/trading/trading-plan-tool.ts`
- `/Users/yunpeng/pi-investment/agent-ts/src/infrastructure/tools/groups.ts`
- `/Users/yunpeng/pi-investment/agent-ts/src/infrastructure/tools/index.ts`
- `/Users/yunpeng/pi-investment/agent-ts/src/infrastructure/tools/__tests__/trading-plan-tool.test.ts`

### 下一步

t15 全量收口测试与端到端冒烟

---
