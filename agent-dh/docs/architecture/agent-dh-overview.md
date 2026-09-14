---
id: agent-dh-overview
title: agent-dh 是什么（子项目说明书）
type: manual
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [overview, l1, agent-dh]
---

# agent-dh 是什么

**这页回答**：agent-dh 在系统里的位置、运行时长什么样、代码怎么组织、改动怎么生效。

## 结论先行

1. **agent-dh 不是独立应用，而是 DSH（DeepSeek Harness）的一个 Profile**：
   一组 cordis 插件 + 系统提示词 + 工具，装载后以内建 agent 身份运行。
2. **运行形态**：`:13080`（launchd 作业 `com.pi-investment.dsh` 托管，KeepAlive + RunAtLoad）；
   DSH_HOME = `agent-dh/.dsh-data`（profile 配置、台账、技能、会话都在这里；2026-09-14 起
   与数据目录合并为同一个，不再有 `.dsh-home` 脚手架层）。
3. **两半生效路径**：host 半（工具、路由、提示词段）**改动需重启**；client 半（页面 UI）
   **打包后刷新页面即生效**。改完不一定生效，是这里最常见的坑（见构建与发版规范）。
4. **对外依赖**：quantsys-v2（`:5001`）提供行情/财务/回测；DeepSeek API 提供模型。
5. **工作组织**：需求看板（reqboard）驱动——立项 → 头脑风暴 → 写计划 → 拆分 → 执行 → 验收（人工审核）→ 完成 → 归档。

## 目录地图

| 路径 | 是什么 |
|---|---|
| `agent-dh/packages/*` | 插件包（investment / trading / intelligence / market / risk / strategy / factor / model / memory / evolution / scheduler / notification / data-manager / lifecycle / genome / competition / learning / evolver / quantsys-v2-manager / solve-kit…） |
| `agent-dh/packages/pages/*` | 页面插件（holdings / execution / dsh-pmboard / genome / bulletin + page-kit） |
| `agent-dh/skills/*/SKILL.md` | 技能（按需加载的 SOP，如 session-briefing、reqboard-plan） |
| `agent-dh/scripts/*` | 运维脚本（relink-profile.py、restart-with-build.sh、wiki_probe.py、self-restart.ts…） |
| `agent-dh/docs/*` | 本 wiki（architecture / guides / protocols / rfcs / standards / design / requirements / work-logs） |
| `agent-dh/.dsh-data/` | 运行时根（= DSH_HOME）：profiles/（配置与 agents.json）、dsh-reqboard.json（看板台账）、skills/、sessions/、storages/、genome/、settings.yaml |
| `agent-dh/config/cordis.yml` | profile 配置模板（实际生效的是 profile 目录下的 cordis.patch.yml） |

## 运行时怎么拼起来

```
DSH 框架（cordis 插件树 + LLM + Web UI）
   ↑ 装载
investor profile（agents.json 身份 + 系统提示词段（基因组/身份/reqboard 引导）+ 工具集）
   ↑ 实现
agent-dh/packages/*（工具与页面插件；dist 或 src 两种加载方式）
   ↓ 调用
quantsys-v2 :5001（数据与回测）  +  DeepSeek API（模型）
```

## 依据

- 根 `CLAUDE.md`（三层架构）与 `agent-dh/CLAUDE.md`（profile 与插件）；
- 本 wiki 首页的「一页速览」就是本页的压缩版（先读它，需要细节再读本页）。

## 相关页面

- [术语表](glossary.md)
- [插件模型与装载](plugin-model.md)（待写）
- [构建与发版规范](../standards/build-and-release.md)
- [agent-dh Wiki 首页](../README.md)
