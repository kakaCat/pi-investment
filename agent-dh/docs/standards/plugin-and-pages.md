---
id: std-plugin-and-pages
title: 插件与页面插件规范（Service / 两半 / 样式令牌）
type: standard
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [standards, plugin, pages]
---

# 插件与页面插件规范

**这页回答**：写一个新的 agent-dh 插件（或有 GUI 的页面插件）要遵守什么。

## 结论先行

1. **插件 = cordis Service**：`static inject = ['tools']`；无静态 inject 的页面插件用
   `(ctx as any).inject([...], cb)` 惰性注入（genome / dashboard 系列同款模式）。
2. **页面插件分两半，生效路径不同**：
   - **host 半**（`src/index.ts` + `src/host/*`，tsx 直载）→ **改完必须重启** :13080；
   - **client 半**（`src/client/*`）→ 由 tsdown 打包成 `lib/client.cjs` → `scripts/wrap-client.mjs`
     包成 `lib/client.js`（`window.__ModuleLoader__.load`），**页面刷新即生效**；
     改了 client 不改 host 也要**重新打包并提交 lib 产物**（产物随仓提交）。
3. **样式复用全站令牌**：用既有 `.dsh-*` 类与 `var(--dsw-*)` 令牌（accent/border/text-primary/
   hover 等），**不造第二套按钮/色板**（历史反馈："按钮太丑，和整体风格不一致"）。
4. **一切用户文本经 `esc()` 转义**；交互用 `data-action` 事件委派；SSE/轮询刷新不要重复挂监听。
5. **新插件注册三步**：`package.json`（`main: ./src/index.ts`）→ profile 的 `cordis.patch.yml`
   `- insert:` 块 → `python3 agent-dh/scripts/relink-profile.py`（**别手写 ln**）。

## 关键机制

- 页面插件 `dsh` 字段声明平台与注入槽（`platform: web`、`inject: [slots, sessions, workspaces]`）；
- 客户端产物校验：`grep -c '<新增类名或 action 名>' lib/client.js`（构建成功 ≠ 内容进去了）；
- 面板挂载用 board-shell 模式（`createBoardShell`），激活时隐藏中心列其它子元素。

## 依据

- 页面插件 client 半未打包/产物陈旧 → 按钮消失（"client half fails to load → 侧边栏入口没了"）；
- 视觉返工一次（自造卡片按钮）→ 定为规范：只准用全站令牌；
- 新插件装进 profile 时 `pnpm install` 产生硬链接副本 → 静默旧版本（见构建与发版规范）。

## 自检清单

- [ ] host 改动要不要重启？client 改动重新打包并提交 `lib/` 了吗？
- [ ] 关键类名/action 在 `lib/client.js` 里 grep 得到吗？
- [ ] 有没有引入第二套样式/色板？用户文本转义了吗？
- [ ] 插件注册三步都做了吗（package/cordis patch/relink）？

## 相关页面

- [工具开发规范](tool-development.md)
- [构建与发版规范](build-and-release.md)
- [看板实现细节](../design/dashboard-implementation-detail.md)
