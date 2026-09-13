---
id: plugin-model
title: 插件模型与装载（待写）
type: architecture
status: stub
updated: 2026-09-13
owners: [w-1cee2467]
tags: [architecture, plugin, stub]
---

# 插件模型与装载（stub）

> **本页状态**：`stub`——已被 [agent-dh 是什么](agent-dh-overview.md) 与 [术语表](glossary.md) 引用，
> 内容待补。补页时按下面的问题清单写，并把 status 改为 `living`。

## 这页要回答的问题

1. cordis 插件是什么：`Service` / `inject` / `Config` 三件套，加载顺序与依赖注入语义；
2. 一个插件的生命周期：注册 → 装载 → 生效（host 半重启 / client 半刷新）；
3. 工具注册与命名空间；多插件同名工具会怎样；
4. 页面插件的槽位（slots）注入与"激活时隐藏中心列"的挂载模式；
5. 常见坑：schema 铁律违规致启动崩溃、dist 陈旧致工具不存在、profile 硬链接断链。

## 素材在哪

- [工具开发规范](../standards/tool-development.md)（schema 铁律与 Service 样例）
- [插件与页面插件规范](../standards/plugin-and-pages.md)（两半分工与产物）
- [agent-dh/CLAUDE.md](../../CLAUDE.md)（插件清单与开发流程）
- 参考实现：`packages/scheduler/src/index.ts`（最小 Service 插件）、`packages/pages/dsh-pmboard/src/index.ts`（含 host/client 两半）

## 相关页面

- [agent-dh 是什么](agent-dh-overview.md) · [术语表](glossary.md) · [构建与发版规范](../standards/build-and-release.md)
