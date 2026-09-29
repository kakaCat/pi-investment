# 数据模型 · 页面插槽化迁移 «serves: FR-1, FR-2, FR-3, FR-4»

> 上游：`design/architecture.md`（框架契约，版本对齐 :13080 运行的 `@deepseek-ai/dsh-client-ui-layout@0.1.6-alpha.2`）。
> 代码事实源：`packages/web/dsh-pmboard/src/client/page/page-panel.ts`、`page/register.ts`、`page/host.ts`。

## 1. 范围声明：本需求不动任何持久化数据 «serves: FR-4»

**零数据/接口破坏（行为不变式 #3）**：不改 `docs/requirements/<REQ>/queue.json`、不改 `dsh-reqboard.json` 台账、不改 `/dashboard/api/reqboard/*` 的响应形状。本需求只替换**挂载与导航方式**，故本节描述的是**运行时（内存）模型**，不是数据库/台账模型。

## 2. 运行时模型 «serves: FR-1, FR-2»

### 2.1 MainPanelId（页面身份）
- 定义：侧栏条目与其主列占用者**共享的字符串身份**（框架契约原文 "Identity shared by a sidebar panel entry and its main-slot occupant"）。
- 取值：`dsh-pmboard`（`page/register.ts` 的 `PANEL_ID`；`src/client/dom.ts:15 export const PANEL_ID = PANEL_NAME`）。
- **不变量 I-1**：`main.key === sidebar.panellist.id === spec.id`；两端只从 `spec.id` 取，**不可能只改一端**（FR-1 的可证伪点，由 `tests/client-page-panel.test.ts` 断言）。

### 2.2 两端插槽注册记录（框架侧；插件只写不读）

| 端 | 插槽（kind/scope） | 注册键 | 占用者 | 备注 |
|---|---|---|---|---|
| 主列 | `main`（keyed / root） | `{ name:'main', key: spec.id }` | React 组件（`spec.Component`） | 保留键 `conversation` 承载对话；其它键不做 Session 绑定 |
| 侧栏 | `sidebar.panellist`（list / root） | `{ name:'sidebar.panellist', id: spec.id, order, label }` | 图标组件（收 `{ size, active }`） | 点击由 sidebar 自己调 `selectPanel(id)` |

### 2.3 PagePanelSpec（helper 入参）

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `id` | string | 是 | MainPanelId：`main.key` 与 `panellist.id` 的同源来源 |
| `label` | string | 是 | 侧栏条目文案（同时作 accessible name） |
| `order` | number | 否（默认 0） | 侧栏排序（升序，并列保持注册顺序）；看板取 110 |
| `Component` | unknown（React 组件） | 是 | 主列占用者，收 main 插槽标准 props |
| `Icon` | unknown（React 组件） | 否 | 收 `{ size, active }`；缺省为渲染 null 的占位组件（保证两端始终成对注册） |

### 2.4 选中态（框架持有，插件不持有） «serves: FR-3»

- `activePanelId` 由 `ctx.layout` 单一持有；`null` = 显示当前对话（**不改变当前 Session**）。
- 插件**不维护** open/close/toggle/isActive，也不注册任何"当前选中"全局量——这是 FR-4 拆除 `board-shell` 状态机的依据。
- 可观测代理：sidebar 把选中项渲染为 `<button aria-current="page">`，E2E 据此判定，无需读 React 内部状态。

## 3. 生命周期 «serves: FR-1»

- 注册：页面 `apply()` 期间调 `registerPagePanel`（内部用 `slots.inject` 包一层，容忍插槽晚于插件声明）。
- 卸载 / HMR：helper 返回的**幂等 disposer** 依次撤销两次注册；重复调用无副作用（HMR 重复 apply 安全）。
- `ctx.slots` 缺失：抛 `Error('[page-panel] ctx.slots unavailable（inject 缺 "slots"）')`——**响亮失败，不降级为"页面静默不存在"**。

## 4. 迁移映射（旧模型 → 新模型） «serves: FR-4»

| 旧（已删） | 新 |
|---|---|
| `html[data-dsh-pm-active]` 属性显隐 + CSS 覆盖会话列 | `main` 插槽占用 + `selectPanel(id/null)` |
| `board-shell.ts` open/close/toggle + `OTHER_ACTIVE_ATTRS` 互斥 | 框架 `activePanelId` 单一真相 |
| `ACTIVATE_EVENT` 广播面板名 | 侧栏条目点击 → `selectPanel(id)` |
| `closeHostPanel()` 手工模拟回对话 | `selectPanel(null)` |
| `MutationObserver` 兜底挂载 + 外部点击关闭 | React 宿主 `useEffect` 生命周期 |
