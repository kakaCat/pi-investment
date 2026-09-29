# 接口设计 · 页面插槽化迁移 «serves: FR-1, FR-2, FR-3»

> 上游 `design/architecture.md`（§标准 helper / §导航 / §目录结构）；事实源 = 实施后代码。

## 1. 插件内标准接口：「一次注册两端」 «serves: FR-1»

```ts
// packages/web/dsh-pmboard/src/client/page/page-panel.ts
export function registerPagePanel(ctx: { slots?: SlotRegistrar }, spec: PagePanelSpec): () => void

export interface SlotRegistrar {
  inject(slot: string, thunk: () => unknown): unknown
  register(options: Record<string, unknown>, occupant: unknown): unknown
}
```

行为约定（可证伪）：
1. `main` → `register({ name:'main', key: spec.id }, spec.Component)`；
2. `sidebar.panellist` → `register({ name:'sidebar.panellist', id: spec.id, order: spec.order ?? 0, label: spec.label }, spec.Icon ?? 占位)`；
3. 两处 id **只来自 `spec.id`**；
4. 返回幂等 disposer（重复调用只撤销一轮）；
5. `ctx.slots` 缺失 → 抛 `Error('[page-panel] ctx.slots unavailable（inject 缺 "slots"）')`，由页面 `apply()` 记录，不静默降级。

## 2. 框架接口（只读消费，本需求不改框架） «serves: FR-2, FR-3»

| 接口 | 契约要点 | 来源 |
|---|---|---|
| `ctx.slots.inject(slot, thunk)` / `ctx.slots.register(options, occupant)` | 插槽声明可晚于插件 apply；register 的 options.name 必须等于 slot | dsh-client-ui-layout |
| `ctx.layout.selectPanel(id \| null)` | `null` = 显示当前对话、**不改当前 Session**；未知 key 抛错并保留当前选择 | dsh-client-ui-layout |
| `uiWorkspace.openSession(sid)` | 切换当前会话（壳无 URL 路由，URL 保持 `/`） | dsh-client-ui-workspace |
| `usePanelInfo().activePanelId` | 选中态单一真相；null = 对话 | dsh-client-ui-layout |

## 3. 宿主与跳转接口 «serves: FR-2, FR-3»

- **薄宿主** `BoardPanelHost`（`page/host.ts`）：`useRef` 容器 + `useEffect` 调 `attachBoard(container)`；卸载时 dispose；挂载/卸载按 `usePanelInfo().activePanelId` 驱动。
- **挂载** `attachBoard(container)`（`board-mount.ts:845`）：把现有命令式看板 DOM 挂进中央列；壳生命周期下沉到宿主。
- **跳会话**（`session-jump.ts`）：`selectPanel(null)` + `uiWorkspace.openSession(sid)` 两句；已归档会话渲染为**可点按钮 + 明确原因**（不静默、不置灰不可点）。删除 `closeHostPanel()` 补丁。

## 4. 依赖边界与注入 «serves: FR-1»

- `dsh-pmboard` **自包含**：`package.json` 依赖仅 `@deepseek-ai/dsh-tools`；client 侧零裸 npm import，**不依赖 `@pi-investment/page-kit`**（也不得依赖）。
- `inject` 双处同源：`src/client/index.ts` 的模块 `inject` 与 `package.json dsh.client.inject` 各含 `slots`、`layout`。

## 5. HTTP 接口（不改） «serves: FR-4»

`/dashboard/api/reqboard/*` 的路由与响应形状**不变**：本需求不新增/删除任何路由或字段，后端零改动。
