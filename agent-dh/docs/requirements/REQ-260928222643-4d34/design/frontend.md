---
requirement_refs: [FR-1, FR-2, FR-3, FR-4]
sides: [frontend]
---

# 前端设计（REQ-260928222643-4d34）

> 读者：改 `node-panel.ts` / `styles/node-panel.ts` / `conversation-progress.ts` 的前端开发者。
> 原型（可点击）：`design/prototypes/node-panel-board-entry.html`（本目录，非交付物，仅结构/交互说明）。

## P-1 入口落位与结构 `serves: FR-1`

**落位**：`.dsh-pm-np-head`（状态胶囊 + 一句话 + 相对时间）内、相对时间**之后**。

```html
<div class="dsh-pm-np-head">
  <span class="dsh-pm-np-head-state" data-state="current">设计中</span>
  <span class="dsh-pm-np-head-title">…一句话进展…</span>
  <span class="dsh-pm-np-head-time">12 分钟前</span>
  <button type="button" class="dsh-pm-np-board-entry"
          data-action="np-board-entry" data-req="REQ-xxx"
          title="打开项目看板并定位到该需求">项目看板 ↗</button>
</div>
```

**为什么写进 `renderHead`**：`renderNodePanel` 有两条出口——`enabled=false` 的早退分支与正常分支，
两条**都**先调 `renderHead`。入口写在这里，「7 个节点全显示（含分类跳过）」就是结构性保证，
而不是 7 处补丁（FR-1 的判定恰好用跳过态验）。

**不引入新的交互依赖**：原生 `<button>`，走既有 document 级 `click` 委派（与 `np-switch-view`、`open-doc` 同款）。

## P-2 窄面板换行与可点性 `serves: FR-1`

已知代价：面板宽度 `min(720px, calc(100vw - 130px))`，head 行内容变多后在窄面板会换行——
**接受换行**（`.dsh-pm-np-head` 已有 `flex-wrap: wrap`），但要求**不被裁切、可点**。

新增两条规则（都落在 `styles/node-panel.ts`，选择器含 `.dsh-pm-np` / `.dsh-pm-cprog-detail-panel`——
既有作用域断言 `tests/node-panel-styles.test.ts` 必须继续全绿）：

```css
/* 入口按钮：不压缩、不裁切，保留可点面积 */
.dsh-pm-np-board-entry {
  flex: none; min-height: 20px; padding: 1px 8px; border-radius: 980px;
  font-size: 11.5px; line-height: 18px; white-space: nowrap; cursor: pointer;
  border: 1px solid var(--dsh-pm-np-blue); color: var(--dsh-pm-np-blue); background: transparent;
}
.dsh-pm-np-board-entry:hover { background: rgba(0,113,227,.08); }

/* 失败提示：面板内就地可见（不静默） */
.dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err {
  color: #c0392b; font-size: 12px; line-height: 1.5; padding: 6px 2px;
}
```

**不做的事**：不动 `.dsh-pm-np-head-time` 的 `margin-left: auto`（保持相对时间右对齐的既有观感）；
不引入新的设计令牌/颜色变量（复用 `--dsh-pm-np-blue` 与既有红）。

## P-3 交互与失败提示的可见性 `serves: FR-2, FR-3`

**点击处理**（`conversation-progress.ts` 内新增一个 document 级委派 effect，与既有两个同款）：

```ts
const t = target.closest('[data-action="np-board-entry"]')
const reqId = t.getAttribute('data-req') ?? ''
setEntryError('')                                    // 每次点击先清旧提示
const verdict = await activateBoardEntry(reqId, {    // 纯函数：先校验
  isKnown: async (id) => (await fetchState()).requirements.some(r => r.id === id),
  requestFocus: requestBoardFocus,
  layout: getPageLayout(),
})
if (!verdict.ok) { setEntryError(verdict.message); return }   // 不切页
closePanel()                                          // 关面板
getPageLayout()!.selectPanel(PANEL_ID)                // 切到项目看板（导航唯一来源）
```

**实现约束（易错点）**：`closePanel` 目前定义在 `if (!detailOpen) return …` **之后**（`conversation-progress.ts:330`），
而 hooks/委派 effect 必须无条件声明在早退之前——实现时把 `closePanel` 的声明**上移**到早退之前
（纯搬移，无行为变化）。

**失败提示的渲染位置**：`panelChildren` 内、紧邻节点面板容器之前，`role="alert"`，
样式类 `.dsh-pm-np-entry-err`。选择器写成
`.dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err` 以同时满足「作用域内」与「面板内可见」。

**为什么不用 `window.alert`/`console`**：requirement 要求「就地发现场原因」；
`board-mount.jumpResultMessage` 的既有约定是返回消息，但那里是 console——本需求显式要求**可见**。

## P-4 下掉执行流程后的面板结构 `serves: FR-4`

`renderNodePanel` 输出结构（改后）：

```
<div class="dsh-pm-np">
  renderHead(...)                ← REQ 行 + 状态行（含「项目看板 ↗」）
  renderInfoFold(...)            ← ℹ️ 基础信息（实施节点无此块）
  renderImplViews(...)           ← 仅实施节点：[DAG][泳道]
  ← 此处原本是 renderProcessFold(payload, processCtx)，整段删除
</div>
```

同步删除：`ProcessFoldContext` / `renderProcessFold` 的 import、`processCtx` 构造、
`NodePanelInput.injection`/`isolation` 两个字段及其类型 import，
以及文件头注第 8-10 行里对「🔄 执行流程」的描述（注释与实现同步，避免下一轮读码被误导）。

`node-panel-process.ts` 与 `tests/node-panel-process-map.test.ts` **保留不动**（函数可留）。

## P-5 视觉一致性 `serves: FR-1`

| 项 | 取值 | 理由 |
|---|---|---|
| 按钮形态 | 980px 胶囊（与 `.dsh-pm-np-head-state` 同款圆角语言） | 落在同一行不突兀 |
| 字号 | 11.5px（与状态胶囊一致） | 同排元素同级 |
| 颜色 | `var(--dsh-pm-np-blue)` 描边 + 透明底，hover 淡蓝 | 复用既有令牌，不新增颜色 |
| 文案 | `项目看板 ↗`（**固定**，人已裁定） | 不用动词变体（避免每次渲染文案漂移） |
| 图标 | 无（只用 ↗ 字符） | 不引入图标资源 |
