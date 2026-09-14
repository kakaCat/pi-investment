---
id: identity-and-agents-json
title: 身份系统与 agents.json
type: architecture
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [architecture, identity, accounts]
---

# 身份系统与 agents.json

**这页回答**：我是谁、账户从哪来、多窗口与多实例怎么区分。

## 结论先行

1. **身份登记表 = 运行时 profile 目录下的 `agents.json`**（本实例：`agent-dh/.dsh-data/profiles/agent-dh/agents.json`；单一来源是 `.dsh-data/agents.json`，start.sh 只在 profile 缺该文件时拷过去），结构为 `{ instance, agents[], rules }`。
2. **账户的唯一事实源是 `instance.account`**（agent 条目可用 `account` 覆盖）；**任务、提示词、代码里禁止写死账户名**——换账户只改这一处。本实例为 `agent_brain`（投资脑自营盘）。
3. **身份进提示词但不进基因组**：lifecycle 插件注册 `agent:identity` 段（order 5，在宪法段之前），因此身份**不参与进化**、不会被基因组更新覆盖。
4. **窗口 = DSH 会话**：会话 id 形如 `session-<uuid>`，窗口码取前 8 位（如 `w-1cee2467`）；同角色不同窗口是**独立个体**，协作与归因都要带窗口码。
5. **多实例共存**：:13080 是 investment profile；同机还可能有主实例（:3080）与其他 profile。停止/重启必须精确到实例（见 [边界与安全规范](../standards/security-and-boundaries.md)）。

## agents.json 实例（真实内容，已脱敏结构）

```json
{
  "instance": {
    "id": "investment",
    "name": "PI 投资顾问",
    "port": 13080,
    "account": "agent_brain",
    "account_label": "投资脑自营盘",
    "dsh_home": "<repo>/agent-dh/.dsh-data",
    "genome_dir": "<repo>/agent-dh/.dsh-data/genome"
  },
  "agents": [
    { "id": "investor", "name": "PI 投资顾问·投资脑", "role": "投资决策与分析", "primary": true },
    { "id": "agent-dh", "name": "PI 投资顾问·工程脑", "role": "代码维护/自修复/自进化", "alias_of": "investor" }
  ],
  "rules": {
    "identity_in_prompt": true,
    "sign_outputs": true,
    "account_source_of_truth": "instance.account（可在 agent 条目覆盖）；例行任务与提示词禁止写死账户名"
  }
}
```

- `agents[]` 的 `id/name/role` 决定"我是谁"；`alias_of` 表示同一主体的别名（工程脑是投资脑在工程任务上的化名）。
- `rules` 是纪律声明（身份写入提示词、外发消息署名、账户事实源），改它等于改口径，要同步本页与规范。

## 账户边界（谁的钱能动）

| 账户 | 归属 | 权限 |
|---|---|---|
| `agent_brain` | agent-dh 自营盘（整个 agent-dh，不属于单个窗口） | **可读写** |
| `agent_virtual` | agent-ts（fin-agent，:3002） | **只读** |
| `v13/v14/v15/chip_simulation` | 定时策略线 | 不归投资脑，其信号不作为本实例信号源 |

不确定有哪些账户时用 `account_list`（只读）查，**不靠记忆**；写操作必须显式传账户。

## 窗口与会话

- 每个窗口是独立个体：分析、决策、经验记录都要带 `角色 ID + 窗口编码` 双署名；
- 需求看板的绑定键就是会话 id（`sourceSessionId`），窗口↔需求在卡面显示为 `w-xxxxxxxx`；
- 跨窗口协作：公告板发悬赏档帖（需先问用户确认）或由用户牵线；不要替别的窗口推状态。

## 依据

- R-019（账户边界与"账户名不得写死"）：曾因工具层把 `agent_virtual` 硬编码为默认账户，导致 agent-dh 的例行任务在**别人的账**上下单 23 笔；
- `agents.json` 的 `rules.account_source_of_truth` 原文；lifecycle 插件的 `agent:identity` 段（order 5）。

## 相关页面

- [账户与交易纪律](../standards/account-and-trading.md) · [边界与安全规范](../standards/security-and-boundaries.md)
- [术语表](glossary.md) · [agent-dh/CLAUDE.md](../../CLAUDE.md)
