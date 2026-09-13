---
id: accounts-and-boundaries
title: 账户模型与边界
type: architecture
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [architecture, accounts]
---

# 账户模型与边界

**这页回答**：系统里有哪些账户、是谁的、我怎么知道自己该操作哪个。

## 结论先行

1. **账户是后端的实体**（模拟盘），由 quantsys-v2 持有；agent 通过工具读写，**默认值来自 `agents.json` 的 `instance.account`**——不是代码里写死的。
2. **本实例（investment profile，:13080）的自有账户 = `agent_brain`（投资脑自营盘）**，归属整个 agent-dh，不属于任何单个窗口。
3. **只读账户**：`agent_virtual` 属 agent-ts（:3002），agent-dh **只读不写**。
4. **不归投资脑的账户**：`v13_simulation` / `v14_simulation` / `v15_simulation` / `chip_simulation` —— 定时策略线的账，其信号与评分**不得作为投资脑的业绩先验**。
5. **不确定就用 `account_list`（只读）查**，不靠记忆；写操作**显式传账户名**。

## 账户发现与默认值链路

```
agents.json（instance.account）      ← 唯一事实源（换账户只改这一处）
    ↓ lifecycle 注入系统提示词 agent:identity 段
工具层默认值 DEFAULT_AGENT_ACCOUNT   ← 代码侧唯一常量（DSH_INVESTMENT_ACCOUNT 可覆盖）
    ↓ 调用时不传 account_name 时使用
后端 quantsys-v2 账户实体            ← 真正记账的地方
```

- 查账户：`account_list`（列出全部模拟账户 + 摘要 + 哪个是本实例默认）；
- 查单个：`account_info`（总资产/现金/持仓市值/盈亏）+ `position_list`（逐只成本、现价、可卖数量）；
- **写操作必须显式传**（`portfolio_trade` / `cancel_pending_order` / `algo_execute` / `m4_circuit_breaker_check` 等）。

## 依据

- R-019 事故：工具层曾把 `agent_virtual` 硬编码为默认账户 → agent-dh 的例行任务在**别人的账**上下单 23 笔，最近一笔 2026-09-10；
- 用户 2026-09-13 裁定：默认值放工具层不做拦截，但**账户名不得硬编码**（写死一处也是同一个 bug）。

## 相关页面

- [账户与交易纪律](../standards/account-and-trading.md) · [身份系统与 agents.json](identity-and-agents-json.md)
- [下单 API 指南](../guides/order-api-guide.md)
