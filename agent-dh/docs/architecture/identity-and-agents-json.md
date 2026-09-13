---
id: identity-and-agents-json
title: 身份系统与 agents.json（待写）
type: architecture
status: stub
updated: 2026-09-13
owners: [w-1cee2467]
tags: [architecture, identity, stub]
---

# 身份系统与 agents.json（stub）

> **本页状态**：`stub`——已被 [术语表](glossary.md) 引用，内容待补。

## 这页要回答的问题

1. `agents.json` 的结构（instance / agents[]：id、name、role、primary、alias_of）与**账户事实源**语义；
2. 身份如何注入提示词（`agent:identity` 段，order 5，在宪法段之前，不进基因组）；
3. 窗口与会话：`session-<uuid>` ↔ 窗口码 `w-<前 8 位>`，多窗口如何区分与协作；
4. 账户边界：本实例自有账户、只读账户、策略线账户；**账户名不得硬编码**的原因与做法；
5. 多实例共存：:13080 与其他 profile 实例的身份隔离。

## 素材在哪

- [账户与交易纪律](../standards/account-and-trading.md)（边界与默认值规则）
- [边界与安全规范](../standards/security-and-boundaries.md)（多实例铁律）
- [agent-dh/CLAUDE.md](../../CLAUDE.md) 的「Agent 身份系统」段
- 运行时事实源：`agent-dh/.dsh-home/profiles/investment/agents.json`

## 相关页面

- [术语表](glossary.md) · [账户与交易纪律](../standards/account-and-trading.md)
