---
id: worklog-2026-09-web-liveness-restart-self-heal
title: web-liveness 页面自愈：重启后已开标签页自动刷新（2026-09-16）
summary: 查清"重启后标签页能开发消息没反应"的真因（没人刷新页面），并用免鉴权 SSE 的 graph.rev 比对做成自愈插件。
type: worklog
status: living
updated: 2026-09-16
owners: [agent-dh]
tags: [worklog, page-plugin, restart, dsh]
---

# web-liveness 页面自愈（2026-09-16）

## 症状

`launchctl kickstart -k` 重启 :13080 后，**已经打开的标签页"废"了**：页面能开、能打字、
发出去没反应；只有重新开一个带 token 的 URL 才恢复。

## 排查：三条线索，前两条是错的

1. **误判一：进程级 token 失效**。`launchToken` 确实是每进程重新随机、且没有 config/env 入口
   （`processLaunchToken(owner)` = 模块级 WeakMap + `randomBytes(32)`），**钉不住**。
   但 cookie 的**签名密钥是持久的**（`$DSH_HOME/.credentials.yaml` 的
   `records.client-connection/browser-session.secret`，`cmp` 验证自 9/8 未变），cookie 寿命 30 天
   ⇒ **cookie 跨重启有效**，URL 里那个旧 token 有 cookie 兜着，无害。
   曾把一条 401 当主因，**判错了**——取当前 URL 要用 `agent-dh/scripts/url.sh`，
   别从日志里 `tail -1`（日志里堆着 105 个历史进程的死 token）。
2. **误判二：鉴权把消息挡住了**。实际是消息**发出去但服务端没收到**：UI 先本地回显，
   失败后撤回并弹 toast（`carrierFailure` → `promptError`）——用户看到的就是"没反应"。
3. **真因：没有任何机制在重启后刷新页面**。三条证据：
   - client bundle 是 `Cache-Control: public, max-age=31536000, immutable` + `?rev=<进程 nonce>`，
     唯一能发现新版的入口是 index.html（无缓存头），而没人去重新拉；
   - 框架 HMR（`dsh-client-hmr`）只在**进程运行期间**检测到 bundle 被改写才推 `rebuilt`，
     重启后**不补发**；其客户端对 `graph` 帧显式 `case "graph": break;` 不处理；
   - 我们自己的 5 个页面插件只有 15–20s 的裸 `fetch` 轮询，**没有 reload / 重连逻辑**
     （`location.reload` 在整个 client bundle 里出现 **0 次**）。

## 机制：不用自建探活，框架已经免费推过来了

关键发现（**已实测**）：`GET /plugins/events` 是 `dsh-client-hmr` 常驻挂载的**免鉴权 SSE**，
连上即推 `data: {"type":"graph","graph":{"rev":…}}`。而 `dsh-client-modules` 里
`initialRevisionNonce = randomBytes(8).toString("hex")` 是**进程级 nonce**，`graph.rev = shortHash(…)` 由它派生：

```
graph.rev === window.__DSH_BOOT__.rev  ⟺ 同一进程（含同进程断线重连）→ 什么都不做
graph.rev !== window.__DSH_BOOT__.rev  ⟹ 换过进程 / 换过 bundle       → 刷新
```

⇒ **不需要 host 路由、不需要自建探活端点、不需要轮询**。host 半是空壳，
做成插件包只因为在浏览器里跑代码必须由 `dsh.client` 声明的 client 半提供。

## 交付

- `agent-dh/packages/pages/web-liveness/`（新包，`@pi-investment/web-liveness`）
  - `src/client/watch.ts` 纯判定逻辑（`bootRevOf`/`parseFrame`/`decideGraph`/`shouldReloadNow`/`reloadAllowed`），16 个单测
  - `src/client/index.ts` 副作用编排；`banner.ts`/`styles.ts` 顶部横幅（直接 DOM，不依赖壳 slot）
  - `scripts/verify-client-build.mjs` 产物校验（失败即非零 → 发版拒绝，REQ-31e11f 的教训）
  - `scripts/e2e-restart-reload.mjs` **真浏览器 + 真重启**验收
- `agent-dh/config/cordis.yml` 挂载（→ 同步进 `.dsh-data/profiles/agent-dh/cordis.patch.yml`）

两个闸门（判错两个方向都很难受，所以都做了）：

- **等停手**：页面在后台 → 立刻刷；前台要距最后一次输入（keydown/input/compositionstart/paste/pointerdown）超 5s。
- **防抖**：`sessionStorage['dsh-wlv-reload-at']` + 15s 闸门——防"刷新后仍拿缓存旧 HTML"刷成**死循环**，
  触发即转手动按钮 + warn。
- **降级**（信息不足不动，比乱刷安全）：读不到 `__DSH_BOOT__.rev` 或 90s 内 SSE 无帧 → 只提示、不自动刷。

## 证据

单测：`pnpm test` → 16 passed。
验收（`node …/scripts/e2e-restart-reload.mjs`，退出码 0，独立 headless Chrome，不碰用户浏览器）：

```
加载完成 bootRev=83ece20971df 插件已接管=true
横幅 phase=offline「服务重启中，正在自动重连…… 此期间发送的消息可能发不出去，请稍候」
✅ 页面已刷新：rev 83ece20971df → 85ec057a0ee4
当前 SSE graph.rev : 85ec057a0ee4      自动刷新导航次数 : 1（期望 1）
✅ 通过：重启时提示 + 自动刷新一次 + 刷新后与新进程一致（无死循环）
```

发版链路：boot 图里已出现 `@pi-investment/web-liveness`（`inject: []`，rev `b816527615f5222e-44`），
`/plugins/??@pi-investment/web-liveness/client.js` 返回 200 / 5194 bytes；
`relink-profile.py --check` 25/25 symlink-ok；`dist-packages.py verify` 19/19 通过。

## 遗留

- `start.sh` 从不传 `--no-open`，**每次重启都会新开一个浏览器标签页**（本次未处理）。
- 服务端每次重启进程 nonce 必变 ⇒ 每次重启都会刷新一次，这是预期（旧代码本来就该换掉）。
