---
id: pkg-pages-web-liveness-readme
title: @pi-investment/web-liveness · 页面自愈（重启后标签页不再变砖）
summary: 监听框架免鉴权的 /plugins/events SSE，发现服务端换过进程就自动刷新已打开的标签页。
type: package
status: living
updated: 2026-09-16
owners: [agent-dh]
tags: [package]
---

# @pi-investment/web-liveness · 页面自愈

修的事故：**:13080 一重启，已经开着的标签页就"废"了** —— 页面能开、消息发不出去，
只能手动开一个新标签页。根因不是鉴权（cookie 跨重启有效，见 `dsh-web-401-token-root-cause`），
而是**没有任何机制在重启后刷新页面**：

1. client bundle 是 `Cache-Control: public, max-age=31536000, immutable` + `?rev=<进程 nonce>`，
   唯一能发现新版本的入口是 index.html，而没人去重新拉它；
2. 框架自带的 HMR 只在**进程运行期间**发现 bundle 被改写才推 `rebuilt`，重启后不补发，
   且客户端对 `graph` 帧显式 `break` 不处理；
3. 我们自己的页面插件只做裸 `fetch` 轮询，没有任何 reload / 重连感知。

于是重启后页面一直跑旧代码：发出去的消息服务端收不到，UI 先本地回显再撤回，用户看到的就是"没反应"。

## 机制：不用自建探活，框架已经把答案免费推过来了

`GET /plugins/events` 是 `dsh-client-hmr` 常驻挂载的**免鉴权 SSE**，连上即推一帧
`{"type":"graph","graph":{"rev":"…"}}`。关键在于这个 `rev` 的构成：
`dsh-client-modules` 的 `initialRevisionNonce = randomBytes(8).toString("hex")` 是**进程级 nonce**，
`graph.rev = shortHash(…)` 由它派生。于是：

```
graph.rev === window.__DSH_BOOT__.rev   ⟺  同一个进程（含同进程断线重连）→ 什么都不做
graph.rev !== window.__DSH_BOOT__.rev   ⟹  服务端换过进程（或 bundle 换过版）→ 刷新
```

所以本插件**没有 host 路由、没有自建探活端点、没有轮询**——host 半是空壳
（`src/index.ts` 一行日志），做成插件包只是因为在浏览器里跑代码必须由 `dsh.client` 声明的 client 半提供。

## 状态机

| 状态 | 触发 | 表现 |
|---|---|---|
| `ok` | 收到与 boot 一致的 graph 帧 | 横幅收起 |
| `offline` | SSE 断开超过 1s | 顶部横幅"服务重启中，正在自动重连…… 此期间发送的消息可能发不出去，请稍候" |
| `stale` | graph 帧的 rev 与 boot 不一致 | 等用户停手后**自动刷新**；停不下来就横幅提示 + "立即刷新"按钮 |

自动刷新的两个闸门（`src/client/watch.ts`，16 个单测钉住边界）：

- **等停手**：页面在后台 → 立刻刷；前台则要求距最后一次输入（keydown/input/compositionstart/paste/pointerdown）
  超过 `DEFAULT_QUIET_MS`（5s）——避免把正在打的字刷掉。
- **防抖**：`sessionStorage['dsh-wlv-reload-at']` 记录上次刷新时刻，`RELOAD_GUARD_MS`（15s）内不再自动刷。
  这一条是**防死循环**的：如果刷新后仍然拿到缓存的旧 HTML，会再次判定 stale 而无限刷新，
  此时转为横幅 + 手动按钮，并打 warn 日志。

**降级**（信息不足时不动，比乱刷安全）：读不到 `window.__DSH_BOOT__.rev`（框架换了 boot 注入形状）
或 `/plugins/events` 在 `STREAM_UNAVAILABLE_MS`（90s）内始终无帧 → 只保留提示，不做自动刷新。

## 开发

```bash
cd agent-dh/packages/pages/web-liveness
pnpm test          # 单测（判定逻辑，纯函数）
pnpm build:client  # src/client/*.ts → lib/client.cjs → wrap → lib/client.js（+ 产物校验）
```

`pnpm build:client` 末尾的 `verify-client-build.mjs` 会断言产物存在、体积正常、关键符号齐全，
**失败即非零退出**——`restart-with-build.sh` 的 `[4/7]` 会扫到并拒绝发版（REQ-31e11f 的教训：
构建失败却静默发版，浏览器继续吃旧包，表现是"改了没用"）。

## 验收

单测证明不了"重启时浏览器真的会刷新"，所以有一个真浏览器验收脚本（**会重启 :13080**）：

```bash
node agent-dh/packages/pages/web-liveness/scripts/e2e-restart-reload.mjs
```

它拉起一个**独立**的 headless Chrome（临时 profile，不碰你正在用的浏览器）→ 读 `__DSH_BOOT__.rev`
→ 真 `launchctl kickstart -k` 重启 → 断言：横幅提示了 / 页面自动刷新了 / 刷新后 rev 等于新进程的 SSE rev
/ 导航计数**恰好 1 次**（没刷成死循环）。2026-09-16 实测通过（退出码 0）。

## 已知边界

- 只在**同源页面**有效：判定依赖 `window.__DSH_BOOT__` 与同源 SSE。
- 服务端**重启后进程 nonce 必变**，所以每次重启都会刷新一次；这是预期（旧代码本来就该换掉）。
- 与 `?rev=` 的浏览器缓存共存：刷新会重新拉 index.html（无缓存头），因此能拿到新 rev 的 bundle。
