---
id: reqboard-token-usage
title: 需求看板的 Token 消耗（过程消耗 + 提示词成本）
summary: 看板怎么记录与展示「每个流程节点/每个任务」的 token 消耗，以及固定系统提示词与 reqboard 注入提示词的成本；含缺失语义与自检命令。
type: architecture
status: living
updated: 2026-09-18
owners: [w-b11b0a40]
tags: [reqboard, token, page-plugin, observability]
---

# 需求看板的 Token 消耗

**这页回答**：看板上那些 token 数字从哪来、怎么算、为什么有的地方是「无快照」；固定系统提示词与注入提示词各烧了多少。
需求 REQ-a33899（feature）。

## 结论先行

1. **两条口径，禁止混用**：
   - **过程消耗**（每个流程节点 / 每次任务执行）＝ **写时快照**落台账，节点/任务消耗 = 两次会话累计值之差；
   - **提示词成本**（固定系统提示词 / reqboard 注入提示词）＝ **读时装配**，只有字符数可测，按固定密度折成估算 token，**不落台账**。
2. **缺失 ≠ 0**：取不到快照就显示「无快照」并给 `null`/缺省，绝不补 0（0 表示"确实一次都没花"）。
3. **一切估算都标「估算」**：费用按模型单价折算、提示词按字符折算，都不冒充 provider 上报值（R-013）。
4. **三处展示，同一套数据三种密度**：看板卡面（累计徽章）→ 会话顶部流程条（每节点）→ 需求详情页「🪙 Token」tab（全量 + 下钻 + 提示词成本）。

## 过程消耗：写时快照（schema v6）

| 项 | 说明 |
|----|------|
| 数据源 | DSH `sessionProjections.stateOf(session, "tokenUsage")` → 四桶 `uncachedInputTokens / outputTokens / cacheReadTokens / cacheWriteTokens` |
| 落点 | `StatusEvent.tokenSnapshot`（每次节点转移）、`ExecutionRecord.tokenUsage.start/end/delta`（每次任务执行） |
| 聚合 | `RequirementRecord.tokenUsage.byStage + totals`（写路径增量维护，读路径 O(1)） |
| 算法 | 节点消耗 = 进入该节点的快照 → 离开该节点的快照之差；**同 sessionId 才相减**，负分量截断为 0 |
| 台账版本 | `REQBOARD_SCHEMA_VERSION` 5 → 6；新字段**全部可选**，v5 及更早台账直接可载入（读路径不自动迁移） |

**已知边界（诚实标注，不粉饰）**：

- **人从看板点按钮推进没有会话上下文** → 那一段没有快照，显示「无快照」；
- **一个会话同时推进多个需求** → 差值含同期其他工作的消耗（详情 tab 的口径提示条写明）；
- **subagent 子会话本期不并入**；
- 历史需求（功能上线前）没有快照 → 详情 tab 显示 `degraded=true`，各节点「无快照」。

## 提示词成本：读时装配

| 块 | 数据源 | 口径 |
|----|--------|------|
| 🧱 固定系统提示词 | `systemPrompt.assemble()` 的 `sections / contexts / tools`（每次请求实时装配，并返回每段正文供查看） | 逐段字符数 → 估算 token；每回合 = 各段 + 上下文 + 工具 schema；**回合数不可得时不给累计** |
| 💉 注入提示词 | `<DSH_HOME>/state/prompt-injection-log.json`（reqboard 既有留痕：routeKey/fragmentIds/charCount/windowKey/at） | 只统计**能匹配到该需求窗口**的留痕（原始 sessionId ∪ 窗口码）；无可匹配窗口 → 不归因（宁可空，不张冠李戴） |

字符 → token 用 `TOKENS_PER_CHAR = 0.25`（与 DSH token-meter 的固定密度 `CHARS_PER_TOKEN = 4` 一致）。
已知偏差：CJK 真实密度更高，中文占比高时会**低估**——所以 UI 一律标注「估算」。

## 接口

| 接口 | 用途 |
|------|------|
| `GET /dashboard/api/reqboard/requirements/:id/token` | 单需求全量：`byStage`（含任务下钻）+ `systemPrompt` + `injections` + `degraded` |
| `GET /session/:sessionId/progress` 扩展 | 每节点 `nodes[].tokens`（会话顶部流程条） |
| `GET /state` 扩展 | 每需求 `tokenTotals`（卡面徽章；无快照的需求不出现该键） |

## 展示位置

- **需求详情页「🪙 Token」tab**：常显汇总卡 + 四个折叠块（按流程节点 / 固定系统提示词 / 注入提示词 / 口径说明）；
  固定系统提示词与注入提示词**每段/每条可展开看具体内容**。设计见 `docs/requirements/REQ-a33899/design/ui.md` 与原型 `token-ui.html`。
- **会话顶部流程条**：节点名行内水平加 token（示例「实施 428.5k」）；无快照只显示名称。
- **看板卡面 / 列表**：`🪙 460.0k` 累计徽章；无数据不渲染（零噪音）。

## 自检（怎么证明它在工作）

    cd agent-dh/packages/pages/dsh-pmboard
    pnpm test          # 含 tests/token-usage / session-probe-token / ledger-v6-token / token-endpoint / prompt-cost / token-tab / token-card
    pnpm typecheck
    pnpm build:client && grep -c 'data-tab="token"' lib/client.js   # 产物里有 Token tab
    curl -s localhost:13080/dashboard/api/reqboard/requirements/<REQ>/token | head -c 800

    # 台账迁移（v5 → v6，链式；对副本先 dry-run 再 apply）
    node --import tsx/esm scripts/migrate-ledger.ts --file <ledger> --dry-run
    node --import tsx/esm scripts/migrate-ledger.ts --file <ledger> --apply
    node --import tsx/esm scripts/migrate-ledger.ts --file <ledger> --verify

> 注意：源码级测试通过 ≠ 线上生效（本仓铁律）。改完 host 半必须发版（`scripts/restart-with-build.sh`），
> client 半重建后刷新页面；验收证据要取线上返回，而不是只贴单测输出。

## 相关页面

- [需求节点详情系统（stage-detail）](reqboard-stage-detail.md)：Token tab 所在页面的骨架与产物闸门；
- [页面插件契约](page-plugin-contract.md)：host/client 两半、接口信封、样式令牌纪律；
- [构建与发版规范](../standards/build-and-release.md)：为什么"改了源码"不等于"已生效"；
- [数据与降级规范](../standards/data-and-degradation.md)：来源/时点标注与降级口径。
