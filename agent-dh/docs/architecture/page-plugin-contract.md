---
id: page-plugin-contract
title: 页面插件契约
type: architecture
status: living
updated: 2026-09-16
owners: [w-1cee2467]
tags: [architecture, pages, gui]
---

# 页面插件契约

**这页回答**：做一个 DSH 页面插件（GUI）要满足哪些契约；改动怎么生效。

## 结论先行

1. **两半分明**：host 半（`src/index.ts` + `src/host/*`）注册路由/工具/提示词段，**改完重启**；client 半（`src/client/*`）渲染 UI，**打包后刷新页面**。
2. **client 产物随仓提交**：`lib/client.cjs`（tsdown 产物）→ `lib/client.js`（`wrap-client.mjs` 包成 `window.__ModuleLoader__.load` 形态）；仓库里两者都跟踪。
3. **UI 只走全站令牌**：复用 `.dsh-*` 类与 `var(--dsw-*)` 变量（accent / border / text-primary / hover），**不造第二套按钮或色板**；紧凑尺寸只加尺寸变体。
4. **安全默认**：一切用户文本经 `esc()`；交互用 `data-action` 事件委派；SSE/轮询在卸载时清理监听。
5. **交付证据**：client 改动要能 `grep` 到新增类名/action；host 改动要能看到工具绑定或接口返回（**源码测试不算线上证据**）。
6. **数据源路径不许各自写死**：页面要读的目录（基因组 / 状态 / 库）必须**跟随实际运行的插件**——显式 config > 运行中插件实例 > env > 默认，并在接口里回报「读的是哪个目录、凭什么选的」。实测：迁移后 `dashboard-genome` 仍读旧 home 的**空库**，页面显示为空却「自洽」，一致性诊断全绿 = **假阳性健康**。[复盘](../work-logs/2026-09/dashboard-genome-split-store-fix-20260913.md)

## 服务端接口约定

- 前缀隔离：页面插件自带 `/dashboard/api/<plugin>` 命名空间（如 reqboard 用 `/dashboard/api/reqboard`）；
- 信封统一：`{ success: true, data }` / `{ success: false, error, code }`；闸门类错误映射 403、非法输入 400、找不到 404；
- 实时刷新：`GET /events`（SSE）推台账变更，前端按 revision 重取；轮询兜底。

## 打开文档：走官方右侧栏（不造弹窗）

**页面插件若要「点链接看文档全文」，用官方右侧栏，不要自研弹窗。**

```ts
import { sessionFileAddress } from './file-address.ts'   // 本地实现，逐行对齐官方 grammar
ctx.sidebarRight.openResource(sessionFileAddress(sessionId, path))
// → 官方 @deepseek-ai/dsh-client-ui-sidebar-documentpreview 渲染 Markdown/代码/图片/PDF/HTML
```

要点（REQ-ff20ca 实测，2026-09-16）：

1. **`sidebarRight` 必须声明 `inject`** —— Cordis 4 拒绝访问未声明的服务
   （报 `cannot get property "sidebarRight" without inject`）。该服务由 web-app 随官方 UI 插件组提供；
   声明后插件等待它就绪再激活。**"可选服务就不声明 inject"在这里行不通。**
2. **地址 grammar**：`dsh-resource://file/session/<sessionId>/<path>`（相对路径）/
   `dsh-resource://file/absolute/<path>`（绝对路径）；段编码 `encodeURIComponent` 且保留 `:`（盘符）。
   官方实现在 `@deepseek-ai/dsh-util-workspace-path`；本项目照抄为 `client/file-address.ts`
   （零新增依赖，避免 `pnpm install` 的链接漂移）。
3. **sessionId 来源**：会话槽位注入优先；看板等无会话上下文场景用 sessions 快照「当前会话」。
4. **为什么不用弹窗**：模态弹窗遮挡对话区，破坏「人看文档 → 对话交流改进」的人机回路
   （REQ-31e11f 设计的第一环）。右栏并排常驻，回路才能转起来。

## 依据

- 页面插件 client 半未打包 → 侧边栏入口消失；产物陈旧 → 新按钮不出现；
- 用户反馈"按钮太丑、和整体风格不一致" → 定为只准复用全站令牌；
- 本轮 reqboard：卡面按钮改回 `.dsh-pm-btn` 体系并把 addon 尺寸单独成 `.sm`。

## 相关页面

- [插件与页面插件规范](../standards/plugin-and-pages.md) · [插件模型与装载](plugin-model.md)
- [看板实现细节](../design/dashboard-implementation-detail.md)