---
id: plugin-model
title: 插件模型与装载
type: architecture
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [architecture, plugin, cordis]
---

# 插件模型与装载

**这页回答**：agent-dh 的插件是什么、怎么被加载、改完怎么才能生效、常见坑在哪。

## 结论先行

1. **插件 = cordis 的 Service 模块**：一个 npm 包（`@pi-investment/xxx`），在 `apply()` 或 Service 构造函数里向框架注册能力（工具、路由、提示词段、页面）。
2. **两类加载方式并存**：`package.json` 的 `main` 指向 `dist/index.mjs`（**需构建**）或 `src/index.ts`（**tsx 直载**）。当前走 src 的有：agent-os-manager、core-tool、evolver、learning、quantsys-v2-manager、solve-kit，以及全部页面插件（bulletin、dsh-pmboard、execution、genome(pages)、holdings、page-kit）。
3. **页面插件分两半**：host 半（工具/路由/提示词段）改动**需重启**；client 半（浏览器 UI）由 tsdown 打包进 `lib/client.js`，**刷新页面即生效**。
4. **注册三步**（新插件）：`package.json` → profile 的 `cordis.patch.yml` 插 `- insert:` 块 → `python3 agent-dh/scripts/relink-profile.py`（**别手写 ln**）。
5. **工具名在同一实例内是全局键**：项目用前缀区分归属（`reqboard_*`、`pool_*`、`data_fetch_*`…）；命名前先看 [工具清单](TOOLS_INVENTORY.md) 避免撞名。

## 装载链路

```
DSH 框架（cordis 容器）
  └─ 读 profile 配置（cordis.patch.yml）：插件清单 + 每个插件的 config
       └─ 逐个 import 插件包（main → dist 或 src）
            └─ Service 构造 / apply(ctx)：注册工具、路由、提示词段、页面
                 └─ 运行时：模型经工具层调用；页面经 webServer 提供
```

- **依赖注入**：`static inject = ['tools']`；没有静态 inject 的（页面插件）用惰性注入 `(ctx as any).inject([...], cb)`，服务缺失时降级放行。
- **配置**：`Config = z.object({...})`（schemastery）；profile 里的 `config:` 覆盖默认值。**跨包推断类型要加显式注解**，否则 dts 内联 .pnpm 路径会让构建失败。
- **工具注册**：`ctx.tools.register(defineTool({...}))`；schema 铁律见 [工具开发规范](../standards/tool-development.md)。
- **提示词段**：`ctx.systemPrompt.section({ name, order, text })`；`text` 可以是函数（按装配上下文动态求值，返回空串即不注入）。

## 页面插件的两半

| | host 半 | client 半 |
|---|---|---|
| 入口 | `src/index.ts` + `src/host/*` | `src/client/index.ts` |
| 加载 | tsx 直载（改完**重启** :13080） | tsdown 打包 `lib/client.cjs` → `wrap-client.mjs` 包成 `lib/client.js` |
| 生效 | 重启后 | **刷新页面**即生效 |
| 产物 | 无（源码直载） | `lib/client.js` **随仓提交** |
| 交付校验 | 工具能绑定 / 路由能返回 | `grep -c <新类名或 action> lib/client.js` |

页面插件的 `package.json` 里还有 `dsh` 字段声明平台与槽位：`{ "client": { "platform": "web", "inject": ["slots","sessions","workspaces"] } }`。

## 常见坑（都真发生过）

- **改了源码没生效**：包走 dist 却没 build；profile 是硬链接副本（`relink-profile.py --check` 能查出）→ 见 [构建与发版规范](../standards/build-and-release.md)。
- **启动即崩（UNSUPPORTED_SCHEMA）**：工具 schema 缺 `additionalProperties` → 见 [工具开发规范](../standards/tool-development.md)。
- **页面按钮/面板不出现**：client 半没重新打包，或产物没提交 → 重新打包并 grep 校验。
- **构建"成功"但内容没进去**：构建失败会先清空 dist → 必须校验产物（文件在 + 符号命中）。

## 依据

- `agent-dh/CLAUDE.md`（插件开发流程与「pnpm build 不是部署」铁律）；
- 2026-09-11 硬链接副本事故、dist 陈旧致工具未注册、intelligence 构建失败清空 dist；
- 本轮实测：各包 `package.json` 的 `main` 字段（12 个 src 包，其余 dist）。

## 相关页面

- [agent-dh 是什么](agent-dh-overview.md) · [术语表](glossary.md)
- [插件与页面插件规范](../standards/plugin-and-pages.md) · [构建与发版规范](../standards/build-and-release.md)
- [工具清单](TOOLS_INVENTORY.md)
