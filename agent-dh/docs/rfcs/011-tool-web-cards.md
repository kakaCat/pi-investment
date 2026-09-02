# RFC 011：工具 Web 自定义卡片（Tool Web Cards）统一实现规范

| 字段 | 值 |
|---|---|
| 状态 | 📋 草案（待实施） |
| 创建 | 2026-09-01 |
| 作者 | agent-dh（w-dc832477） |
| 前置 | 2026-09-01 已将 liangshen 预设 `promotedPresentation` 从 `code` 切换为 `native`（工具调用以顶层卡片展示） |
| 范围 | 所有 `@pi-investment/*` 工具包在 DSH Web UI（:13080）中的调用卡片展示 |

---

## 1. 背景与目标

### 1.1 问题

投资工具（`data_fetch_quote`、`portfolio_trade` 等 48 个）在 Web UI 中默认渲染为**通用卡片（GenericToolCard）**：

- 图标归入 `others`（火花图标），无语义区分
- 输出区直接显示 `output.render` 的文本（默认是一坨 JSON）
- 关键信息（涨跌、盈亏、信号分级）淹没在文本里，不利于盘后复盘与实时监控

### 1.2 目标

建立一套**统一、可复制的规范**，让每个工具可以拥有专属 Web 卡片：

1. **内聚**：展示组件 `card.tsx` 与工具代码同目录（`tools/XxxTool/`）
2. **低门槛**：新工具按模板两步接入（写 card + 注册一行）
3. **可降级**：卡片缺失/报错时自动回退到通用卡片，不影响工具本身
4. **模式无关**：`native` / `code` 两种呈现模式下均生效

### 1.3 非目标

- 不改动 DSH 框架（`@deepseek-ai/*` 包一律不改，只做消费方）
- 不改变工具的 LLM 契约（`parameters` / `output.schema` 不变）
- 不做全量 UI 美化（先做数据可读性，图形化按需）

---

## 2. 机制速览（消费方必读）

### 2.1 渲染链路

```
工具执行完成
  → dsh-tools 调 output.render(args, value) 产出 content 文本块
  → 会话事件 tool/result（native 顶层）或 tool/code-dispatch（code 子调用）
  → 前端归约为 ToolCallTree 节点（含 subCalls 树）
  → 每个节点经 renderSlot("tool.call.toolview", owner, { entryKey: 工具名 })
      ├─ 命中 keyed 注册（key === 工具名）→ 渲染你的 card 组件 ✅
      └─ 未命中 → 回退 GenericToolCard（默认卡片）
```

**关键事实**：

- 子调用（code 模式）与顶层调用（native 模式）走**同一个 keyed 插槽**（`ToolCallBranch` 递归复用），所以本规范两种模式都生效
- `presentationMeta` 只在顶层调用执行（`dsh-tools` 中 `exec.parent === void 0` 才调用），code 模式子调用跳过——**本规范不依赖 presentationMeta**
- 卡片组件拿不到结构化 `value`，只能拿到 `block.argsRaw`（入参 JSON 字符串）和 `block.content`（render 产出的文本块）——因此需要 §5 的数据契约

### 2.2 浏览器加载机制

- 浏览器端按**包**加载：一个包只有一个入口 `/plugins/<包名>/client.js`
- 包通过 `package.json` 的 `"dsh": { "client": { ... } }` 声明 + `exports["./client"]` 被 `dsh-client-modules` 的 node 端发现并服务
- 加载格式为 `window.__ModuleLoader__.load({ id, factory })` 包裹的 bundle；`react`、`@deepseek-ai/*` 等依赖通过 `require()` 从模块表取，必须标记为 external
- **浏览器不跑 TS**：`card.tsx` 必须经构建产出上述格式的 `lib/client.js`

---

## 3. 总体架构

### 3.1 包结构：独立的 `-ui` 包

官方 client 包（如 `dsh-client-ui-cordis`）的 host 端是**空 apply**（占位），浏览器端走 `./client` export。若把 client 声明直接加在 `@pi-investment/investment` 上并在花名册重复挂行，会导致工具被**重复注册**。因此采用独立 UI 包：

```
packages/
├── investment/                        ← 工具包（不动 host 逻辑）
│   └── src/
│       └── tools/
│           ├── DataFetchQuoteTool/
│           │   ├── DataFetchQuoteTool.ts   ← 工具逻辑（已有）
│           │   ├── prompt.ts               ← 提示词 + render（按 §5 扩展）
│           │   └── card.tsx                ← ✅ 本规范新增：该工具专属卡片
│           └── PortfolioTradeTool/
│               └── card.tsx
│
└── investment-ui/                     ← ✅ 本规范新增：Web 卡片聚合包
    ├── package.json                   ← dsh.client 声明 + ./client export
    ├── build.mjs                      ← esbuild 打包脚本（§7）
    └── src/
        ├── client.tsx                 ← 薄入口：只做 keyed 注册聚合
        └── shared/                    ← 卡片公共件
            ├── CardShell.tsx          ← 卡片外壳（标题/状态/展开）
            ├── theme.ts               ← 涨跌红绿、盈亏色等常量
            └── parse.ts               ← argsRaw / content 数据块解析
```

> 卡片组件源码住在各工具目录（内聚），`investment-ui` 通过相对路径 import 并在构建时打包进单一 bundle。**入口薄聚合是浏览器"一包一入口"的硬约束，不可省略。**

### 3.2 新增工具卡片的接入流程（两步）

1. 在 `packages/<工具包>/src/tools/<XxxTool>/card.tsx` 按 §6 模板写组件
2. 在 `packages/investment-ui/src/client.tsx` 加一行 `reg("<tool_name>", XxxCard)`

---

## 4. 命名与目录规范

| 项 | 规范 | 示例 |
|---|---|---|
| 卡片文件 | 工具目录下 `card.tsx` | `tools/DataFetchQuoteTool/card.tsx` |
| 组件名 | `<工具名驼峰>Card` | `QuoteCard`、`TradeCard` |
| 注册 key | 工具的 **wire 名**（DSH 定义里的 `name`，非类名） | `data_fetch_quote` |
| UI 包命名 | `<工具包名>-ui` | `investment-ui`、`trading-ui`（如需分包） |
| 花名册行 id | `ui-<工具包名>` | `ui-investment` |

> 多包原则：先只建 `investment-ui` 一个包，注册全部投资工具卡片；卡片数量超过 ~15 个再按域拆分（`trading-ui` 等）。

---

## 5. 数据契约（render 与 card 的约定）

卡片组件**拿不到**工具的原始返回值，数据只能从两个地方来：

| 来源 | 内容 | 用途 |
|---|---|---|
| `block.argsRaw` | 入参 JSON 字符串 | `JSON.parse` 得入参（如 symbol、action） |
| `block.content` | `output.render` 产出的 `[{type:'text', text}]` 数组 | 结果数据 |

### 5.1 render 输出约定（v1）

工具的 `output.render` 统一返回**两个文本块**：

```typescript
// packages/investment/src/tools/DataFetchQuoteTool/prompt.ts
output: {
  schema: { /* ...不变... */ },
  render: (args, value) => [
    // 块 1：人话摘要 —— 通用卡片/CLI/日志直接显示这块
    { type: 'text', text: `📈 ${args.symbol} ¥${value.price}（${value.change_pct >= 0 ? '+' : ''}${value.change_pct}%）` },
    // 块 2：结构化数据 —— 自定义卡片解析这块；必须带 __card 标记
    { type: 'text', text: JSON.stringify({ __card: 'data_fetch_quote', data: value }) },
  ],
}
```

**约定**：

- 块 1 必须独立可读（不依赖块 2），它是无卡片环境的唯一展示
- 块 2 必须包含 `__card: "<tool_name>"` 字段作为识别标记
- 卡片从 `block.content` **从后往前**找第一个可 `JSON.parse` 且 `__card === 本工具名` 的块；找不到则降级渲染块 1 文本（≈ 通用卡片）
- 通用卡片会把两块都显示出来（块 2 是 JSON 原文）——可接受；如介意，后续版本再优化

### 5.2 卡片 props 契约

组件从插槽拿到的 props（与 `GenericToolCard` 一致）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `callId` | string | 本次调用 ID |
| `toolName` | string | 工具 wire 名 |
| `block` | object | 调用节点（两种形态，见下） |
| `cwd` / `home` | string | 会话工作目录 / 用户目录 |
| `openFile` | fn | 打开文件（一般不用） |
| `inspect` | fn | 打开详情面板 |

`block` 两态（组件必须都处理）：

```typescript
// 运行中：还没有结果
{ callId, name, argsRaw, time, subCalls: [] }

// 已结算（kind 字段存在即已结算）
{ kind: 'tool-result', callId, call: { name, argsRaw },
  content: [{type:'text', text}...],        // ← render 产出
  isError: boolean, error?: { name, code }, // code === 'interrupted' 表示被中断
  subCalls: [] }
```

---

## 6. card.tsx 编写规范

### 6.1 标准模板

```tsx
// packages/investment/src/tools/DataFetchQuoteTool/card.tsx
import React from "react";
import { findCardData, parseArgs } from "../../../../investment-ui/src/shared/parse";

export function QuoteCard(props: any) {
  const { block } = props;
  const args = parseArgs(block.argsRaw ?? block.call?.argsRaw);

  // 运行中
  if (!("kind" in block)) {
    return <div className="pic-card pic-running">⏳ 查询 {args?.symbol} 行情中…</div>;
  }
  // 失败 / 中断
  if (block.isError) {
    return <div className="pic-card pic-error">❌ {block.error?.name}: {block.error?.code}</div>;
  }
  // 成功：取数据块，降级到人话文本
  const payload = findCardData(block.content, "data_fetch_quote");
  if (!payload) {
    return <div className="pic-card">{block.content.map((b: any) => b.text).join("\n")}</div>;
  }
  const q = payload.data;
  const up = q.change_pct >= 0;
  return (
    <div className="pic-card">
      <span className="pic-symbol">{args?.symbol}</span>
      <span className={up ? "pic-up" : "pic-down"}>
        ¥{q.price} {up ? "▲" : "▼"}{Math.abs(q.change_pct)}%
      </span>
      <span className="pic-vol">量 {q.volume}</span>
    </div>
  );
}
```

### 6.2 样式规范

- 类名统一 `pic-` 前缀（PI Card），避免与官方样式冲突
- 颜色语义：**涨红 `pic-up` / 跌绿 `pic-down`**（A股习惯），盈亏同理
- CSS 在 `investment-ui/src/client.tsx` 的 `apply()` 里一次性注入，仿官方做法（`data-plugin-css` 标记防重复）：

```typescript
function injectCss() {
  const tag = "pic-card-css";
  if (document.querySelector(`style[data-plugin-css="${tag}"]`)) return;
  const el = document.createElement("style");
  el.dataset.pluginCss = tag;
  el.textContent = `.pic-card{...} .pic-up{color:#e54545} .pic-down{color:#1ba784} ...`;
  document.head.appendChild(el);
}
```

### 6.3 禁止项

- ❌ 卡片里发网络请求（数据必须来自 `render` 契约；需要更多数据就扩 render）
- ❌ 卡片里调用 Node API（浏览器环境）
- ❌ 未处理运行中/失败态（四态必须齐全：running / ok / error / interrupted）
- ❌ 直接 `JSON.parse` 不 try（数据块缺失时必须降级，不得白屏）

---

## 7. 构建规范

### 7.1 产物格式

`investment-ui/lib/client.js` 必须是 ModuleLoader 外壳格式：

```js
window.__ModuleLoader__.load({
  id: "@pi-investment/investment-ui",
  factory: (require) => {
    const React = require("react");
    /* ...打包进来的组件代码... */
    return { apply };   // cordis 插件入口
  }
});
```

### 7.2 esbuild 构建脚本（`investment-ui/build.mjs`）

```js
import { build } from "esbuild";

await build({
  entryPoints: ["src/client.tsx"],
  bundle: true,
  format: "cjs",
  outfile: "lib/client.js",
  jsx: "automatic",
  // 这些依赖由浏览器模块表提供，禁止打进 bundle
  external: [
    "react", "react/jsx-runtime",
    "@deepseek-ai/dsh-client-runtime",
    "@deepseek-ai/dsh-client-ui-tool",
    "@deepseek-ai/dsh-client-ui-primitives",
  ],
  banner: { js: 'window.__ModuleLoader__.load({ id: "@pi-investment/investment-ui", factory: (require) => { const module = { exports: {} }; const exports = module.exports;' },
  footer: { js: "return module.exports; } });" },
});
```

`package.json` 加：

```json
{
  "scripts": { "build:client": "node build.mjs" }
}
```

> 官方包用 `tsdown`，效果相同；选 esbuild 是因为仓库已有依赖、配置直观。二者皆可，产物格式必须符合 §7.1。

---

## 8. 注册与上线

### 8.1 `investment-ui/package.json`

```json
{
  "name": "@pi-investment/investment-ui",
  "version": "0.1.0",
  "type": "module",
  "main": "lib/index.js",
  "exports": {
    ".": { "default": "./lib/index.js" },
    "./client": { "default": "./lib/client.js" }
  },
  "dsh": {
    "client": {
      "inject": [
        "@deepseek-ai/dsh-client-runtime",
        "@deepseek-ai/dsh-client-ui-tool"
      ],
      "platform": "web"
    }
  }
}
```

`lib/index.js`（host 占位，**必须为空 apply**）：

```js
export function apply() {}
```

### 8.2 profile 依赖与花名册

1. `~/.dsh/profiles/investment/package.json` 加依赖：

```json
"@pi-investment/investment-ui": "link:../../../pi-investment/agent-dh/packages/investment-ui"
```

2. `~/.dsh/profiles/investment/cordis.patch.yml` 加花名册行：

```yaml
- insert:
    - id: ui-investment
      name: '@pi-investment/investment-ui'
```

3. 生效链路：**构建 → 重启 dsh web → 浏览器强刷（Cmd+Shift+R）**

### 8.3 开发期热更新

官方 client 包的热更（client-hmr）依赖 dsh 源码仓的 `pnpm run dev:web` watcher，profile 场景不可用。本仓库开发期每次改卡片：**`pnpm build:client` → 重启 → 强刷**。可在 `investment-ui` 加 `pnpm dev`（esbuild watch）省去手动构建，但重启与强刷不可省。

---

## 9. 验收清单

每个卡片上线前逐项打勾：

- [ ] `pnpm build:client` 产物为 ModuleLoader 格式（`head -c 200 lib/client.js` 见 `__ModuleLoader__.load`）
- [ ] 浏览器 DevTools Network 里 `/plugins/@pi-investment/investment-ui/client.js` 返回 200
- [ ] 触发一次该工具调用，对话中出现自定义卡片（非通用卡片）
- [ ] 四态验证：running（调用中显示加载态）/ ok / error（构造一次失败）/ 数据块缺失时降级不白屏
- [ ] 通用卡片回退仍正常（临时把注册 key 改错名验证）
- [ ] `output.render` 块 1 人话摘要在 CLI / 日志中独立可读

---

## 10. 回滚方案

| 层级 | 操作 |
|---|---|
| 单个卡片异常 | `client.tsx` 删掉对应 `reg(...)` 行 → 构建 → 重启 → 强刷；自动回退通用卡片 |
| 整个 UI 包异常 | `cordis.patch.yml` 删掉 `ui-investment` 行 → 重启 |
| render 契约异常 | 块 2 缺失时卡片自动降级显示块 1，无需回滚 |

任何情况下工具本身的 LLM 契约与执行逻辑不受影响。

---

## 11. 已知坑（实测沉淀）

1. **同名重复注册**：花名册行的包若与工具包同名，host apply 会执行两次导致工具重复注册报错——必须独立 `-ui` 包 + 空 apply
2. **presentationMeta 不可靠**：仅 native 顶层调用触发，code 子调用跳过——卡片数据一律走 render 块契约
3. **浏览器不跑 TS**：直接引用 `src/*.tsx` 不会生效，必须构建；`window is not defined` 说明 host/browser 代码混了
4. **external 漏标**：`react` 打进 bundle 会出现多份 React 导致 hooks 报错（`Invalid hook call`）
5. **缓存**：浏览器强刷前的 `?rev=` 由 boot manifest 控制，重启后必须强刷才拿新 manifest
6. **cordis.patch.yml 的 `!!js` 标签**：该文件是 cordis 方言，不能用标准 js-yaml 校验

---

## 12. 实施计划

| 阶段 | 内容 | 产出 |
|---|---|---|
| Phase 1 | 关键工具 render 人话化（`portfolio_trade` / `account_info` / `data_fetch_quote` / `position_list`） | 纯后端，立即改善可读性 |
| Phase 2 | 搭 `investment-ui` 骨架 + 一张示范卡（`data_fetch_quote`）跑通全链路 | 构建脚本、注册、首卡可见 |
| Phase 3 | 按本规范批量推广，优先交易链路工具 | 覆盖清单见 §9 验收 |
| Phase 4（可选） | 图形化（迷你K线、持仓盈亏条） | 按需 |

---

## 附录 A：关键源码索引（DSH 0.1.1-rc.2）

| 机制 | 位置 |
|---|---|
| 通用卡片与 variant 表 | `@deepseek-ai/dsh-client-ui-tool/lib/client.js`（`TOOL_VARIANTS`、`GenericToolCard`、`toolRowModel`） |
| keyed 插槽分发 | 同上（`ToolCall` → `renderSlot("tool.call.toolview", owner, { entryKey: toolName })`） |
| 子调用树渲染 | 同上（`ToolCallTree` / `ToolCallBranch`，子调用复用同一插槽） |
| render / presentationMeta 执行 | `@deepseek-ai/dsh-tools/lib/index.js:3405-3430` |
| 官方卡片范本 | `@deepseek-ai/dsh-client-ui-cordis/lib/client.js:1372`（keyed 注册）+ `card-model.js`（解析 argsRaw/content） |
| 浏览器模块装载 | `@deepseek-ai/dsh-client-modules/lib/client.js`（`__DSH_BOOT__` manifest / `__ModuleLoader__`） |
| 花名册声明位置 | `dsh-web-app/cordis.patch.yml:155-235`（browser plugin roster 段） |
