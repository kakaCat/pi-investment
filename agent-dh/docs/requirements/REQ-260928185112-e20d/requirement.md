# 需求说明（REQ-260928185112-e20d）

## 一句话目标

把项目看板从「往会话列贴 DOM + `html[data-dsh-pm-active]` 属性显隐」迁移到 DSH 原生页面机制
（`main` keyed 插槽 + `sidebar.panellist` 条目 + `ctx.layout.selectPanel`），
使"打开看板 / 回到对话 / 跳转会话"成为**框架级导航语义**，而不是插件自己维护的 DOM 覆盖层；
并产出其余 7 个同款面板的迁移清单与标准 helper。

## 背景与证据（2026-09-28 实测）

1. **用户报告**：点看板卡片上的「窗口 w-xxxx」chip 不切换会话。E2E（Playwright + :13080）实测根因：
   `openSession` **已经**切换了会话（`mainReference.sessionId` 与页面标题都变了），
   但看板是挂在会话列的 DOM 覆盖层、靠 `html[data-dsh-pm-active]` 显隐，**不参与布局导航** → 用户眼里仍是看板。
2. **框架其实已经做对了**：`dsh-client-ui-workspace` 的 `replaceMain` 在切会话时调用
   `ctx.layout.selectPanel(null)`（语义="显示当前对话"）——是看板**没接入**这套机制，所以指令对它无效。
3. **补丁兜底**：现以 `closeHostPanel()`（session-jump.ts，w-7f4acab0 2026-09-28）手工模拟
   `selectPanel(null)`。本需求的目标之一就是**消灭这个补丁**。
4. **不是看板一个插件**：`packages/web` 下 8 个面板（dsh-pmboard / execution / atb / taskboard / ssh /
   hld / bbd / gen）全部使用同款 conversation 覆盖层模式；全仓库 `slots.inject` 只出现
   `sidebar.footer.action`、`conversation.session.header.utilities`、`tool.call.toolview`，
   **无一处使用 `main` 插槽**。同款代码 = 同款 bug 批发。

## 框架契约（设计依据）

- `dsh-client-ui-layout/lib/types/client/service.d.ts`：
  - `MainPanelId` = *"Identity shared by a sidebar panel entry and its main-slot occupant"*；
  - `selectPanel(panelId | null)`：*"Select a global central panel **without changing the current Session**. null displays the current Conversation"*；key 未注册时**抛错**并保留当前选择。
- `dsh-client-ui-layout/lib/types/client/index.d.ts`：`main` 为 keyed/root 插槽；
  保留键 `conversation` 承载对话，*"other keys receive no Session binding"*。
- 官方样例 `dsh-client-ui-plugin-manager`：同一次 apply 里注册 `main`（`key: PANEL_ID`）与
  `sidebar.panellist`（`id: PANEL_ID`）；侧栏条目点击由 sidebar 自己调用 `selectPanel(id)`。
- **壳无 URL 路由**：实测 `openSession` 后 URL 仍为 `/`；故本需求**不引入路由**。

## 边界（做什么 / 不做什么）

**本次做**：
1. Phase 1 — 看板样板：`main` 插槽 + `sidebar.panellist` 条目 + 薄 React 宿主挂载现有命令式看板；
   跳会话改为 `selectPanel(null)` + `openSession(sid)`；删除 `closeHostPanel()`、
   board-shell 状态机（open/close/toggle/互斥属性/`ACTIVATE_EVENT`/MutationObserver 兜底/外部点击关闭）
   与全部 `html[data-dsh-pm-active]` CSS 依赖；E2E 验收。
2. Phase 2 — 其余 7 个面板的**迁移清单**（逐个标注入口/属性/CSS/工作量/风险）+ 标准 helper 落地。

**本次不做**：
1. 不改看板业务逻辑与视觉设计（只换挂载与导航方式，功能等价）；
2. 不把命令式看板重写为 React（薄宿主 + `ref` 挂载即可，控制改造面）；
3. 不动 reqboard 数据层与 `/dashboard/api/reqboard/*` HTTP 路由；
4. 不引入 URL 路由（壳不支持）；
5. Phase 2 只产出清单，不在本需求内批量改完 7 个插件（避免单需求过大）。

## 功能点

- **FR-1 页面注册标准 helper**：`registerPagePanel(ctx, { id, label, Component })` —— 一处同时注册
  `main` 与 `sidebar.panellist`，保证两端 id 同源（`MainPanelId` 契约），供后续插件复用。
- **FR-2 看板页面化**：薄 React 宿主（`useRef` + `useEffect`）把现有命令式看板 DOM 挂进中央列；
  轮询按 `usePanelInfo().activePanelId` 挂载/卸载（替代"开着才轮询"）。
- **FR-3 跳转语义归位**：跳会话 = `selectPanel(null)` + `openSession(sid)`；已归档会话仍渲染为
  **可点按钮**并给出明确原因（不静默、不置灰不可点）；删除 `closeHostPanel()` 补丁。
- **FR-4 旧机制清除**：`board-shell.ts` 的 open/close/toggle/isActive、互斥属性表、
  `dsh-panel-activate` 广播、MutationObserver 兜底挂载、外部点击关闭；`styles.ts` 中所有
  `html[data-dsh-pm-active]` 选择器；侧栏入口从 `sidebar.footer.action` 改为 `sidebar.panellist` 条目。
- **FR-5 迁移清单**：其余 7 个面板逐个给出「现有入口 / 依赖属性 / 关联 CSS / 改造工作量 / 风险」，
  产出可直接排期的清单文档。

## 可证伪判定标准

1. 侧栏点击「项目看板」→ 中央列渲染看板，且 `activePanelId === 'dsh-pmboard'`；
2. 点卡片窗口 chip → 看板页退出、对话显示、目标会话选中
   （`activePanelId === null` 且 `mainReference.sessionId` === 目标会话）；
   归档会话点击给出明确原因而非静默；
3. `pnpm build:client` 通过 `verify-client-build.mjs` 哨兵门禁（含污染注入拦截）；
4. `grep -r "data-dsh-pm-active" packages/web/dsh-pmboard/src` **零命中**；
5. 迁移清单文件存在，7 项每项含入口/属性/CSS/工作量/风险五列；
6. 插件 schema 冒烟测试（`apps/web/tests/plugin-schema.smoke.test.ts`）不因本次改动失败。

## 现状

> serves: FR-1, FR-4

- 看板以 `board-shell.ts` 的**命令式覆盖层**形态挂载：`ensureMounted()` 用 `conversationColumn()` 把容器
  append 到会话列，`MutationObserver` 兜底；开着时给 `<html>` 打 `data-dsh-pm-active`，
  由 CSS 覆盖会话列；互斥靠 `OTHER_ACTIVE_ATTRS` 逐个清除兄弟面板的属性；`ACTIVATE_EVENT` 广播面板名。
- 入口是侧栏底部按钮 `sidebar.footer.action`（`footer-action.ts`），与"中央面板选择"无关。
- 跳会话 `session-jump.ts` 只做 `uiWorkspace.openSession(sid)`；因为面板不是 `main` 面板，
  框架在 `replaceMain` 里给的 `selectPanel(null)` 对看板无效，只能靠 `closeHostPanel()` 手工收面板。
- 同款实现另有 7 个面板（execution / atb / taskboard / ssh / hld / bbd / gen），全仓库无一处使用 `main` 插槽。

## 目标结构

> serves: FR-1, FR-2

- **页面注册**：每个页面插件一次注册两端同 id（`MainPanelId`）——
  `main`（`key: id`，占用者 = React 组件）与 `sidebar.panellist`（`id`、`order`、`label`）。
- **导航**：打开 = `ctx.layout.selectPanel(id)`；回对话 = `ctx.layout.selectPanel(null)`；
  侧栏条目点击由 sidebar 自己触发 `selectPanel(id)`，插件不维护显示状态。
- **挂载**：`main` 占用者是薄 React 宿主（`useRef` 容器 + `useEffect`），
  把现有命令式看板 DOM 挂进中央列；`usePanelInfo().activePanelId` 驱动轮询挂载/卸载。
- **跳会话**：`selectPanel(null)` + `openSession(sid)` 两句，删除 `closeHostPanel()`。
- **标准 helper**：`registerPagePanel(ctx, { id, label, Component })` 收敛两端注册，供后续 7 个插件复用。

## 行为不变式

> serves: FR-2, FR-3, FR-4

1. **业务行为等价**：看板的数据获取（`/dashboard/api/reqboard/*` + SSE）、渲染结构、点击语义
   （打开需求/任务/阶段、分页、评论、验收单、返工）全部不变；本需求只替换**挂载与导航方式**。
2. **跳会话结果等价**：点击窗口/会话 chip 后到达的状态不变——目标会话被选中
   （`mainReference.sessionId === 目标`）、对话可见（`activePanelId === null`）、
   归档会话给出明确原因而非静默。
3. **零数据/接口破坏**：不改 `queue.json`、`dsh-reqboard.json`、HTTP 路由与协议类型；
   后端 `/dashboard/api/reqboard/*` 响应形状不变。
4. **可回滚**：迁移前后是两套挂载方式，回滚 = 还原 `board-shell.ts` 与属性 CSS（同一提交内可逆）。
5. **门禁不退化**：`verify-client-build` 哨兵（逐行注入污染检测）与插件 schema 冒烟测试保持通过。

## 相关

- 拆分计划：`decomposition.md`；设计：`design/`；验收：`verification.md`；复盘：`retro.md`
- 关联缺陷：2026-09-28 跳转 bug（本需求 FR-3 消灭其补丁）
- 工作窗口：w-7f4acab0（投资脑）

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t1 |
| FR-2 | ✅ 已接收 | t2、t3 |
| FR-3 | ✅ 已接收 | t4 |
| FR-4 | ✅ 已接收 | t5 |
| FR-5 | ✅ 已接收 | t7 |

> 无未接收条款（5 条全部有落点）。

<!-- reqboard:marks:end -->
