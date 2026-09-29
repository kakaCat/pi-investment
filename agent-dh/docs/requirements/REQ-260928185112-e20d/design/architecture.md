# 页面插槽化迁移 · 架构设计 «serves: FR-1, FR-2, FR-3, FR-4»

> REQ-260928185112-e20d（refactor）· 设计文档 1/2
> 文档级 serves: FR-1, FR-2, FR-3, FR-4
> 上游：`docs/requirements/REQ-260928185112-e20d/requirement.md`（已确认）
> 本文写给零上下文执行者：只凭本文 + 需求文档即可实施，无需回看会话。

## 目标（可证伪） «serves: FR-1, FR-2, FR-3, FR-4»

一句话：把「页面 = 会话列 DOM 覆盖层 + `html[data-dsh-*]` 显隐」换成
「页面 = `main` keyed 插槽占用者 + `sidebar.panellist` 条目」，导航交给 `ctx.layout.selectPanel`。

可证伪判据（命令见 migration.md §行为等价验证）：

1. `grep -r "data-dsh-pm-active" packages/web/dsh-pmboard/src` 零命中；
2. 侧栏点击「项目看板」→ 主列渲染看板，且侧栏条目 `aria-current="page"`；
3. 点卡片窗口 chip → 回到对话（`main` 的 entryKey 回落 `conversation`）且目标会话被选中；
4. `pnpm --filter dsh-pmboard build:client` 通过 `verify-client-build.mjs` 三道门。

## 框架契约（已核实，实施以此为准） «serves: FR-1, FR-2, FR-3»

事实来源 = 本仓 `node_modules` 内 `@deepseek-ai/dsh-client-ui-layout@0.1.6-alpha.2`、
`-sidebar`、`-plugin-manager` 的 `lib`（版本对齐 :13080 运行实例）。

### 插槽与 id «serves: FR-1»

- `main`：`kind: 'keyed'`、`scope: 'root'`；注册参数 `{ name: 'main', key: <MainPanelId> }`，
  占用者是 React 组件。保留键 `conversation` 承载对话，其它键不做 Session 绑定。
- `sidebar.panellist`：`kind: 'list'`、`scope: 'root'`；注册参数
  `{ name: 'sidebar.panellist', id: <MainPanelId>, order, label }`，占用者是图标组件（收 `{ size, active }`）。
- `MainPanelId` 的定义就是「侧栏条目与其主列占用者共享的身份」——`main.key` 与 `panellist.id` 必须同源，
  这正是 FR-1 把两端注册收敛进一个 helper 的原因。

### 导航 «serves: FR-2, FR-3»

- `ctx.layout.selectPanel(id | null)`：`null` = 显示当前对话，**不改变当前会话**；
  key 未注册时抛错并保留当前选择（layout 侧 `hasMainPanel` 直接查 `slots.entries("main").options.key`）。
- 侧栏条目点击由 sidebar 自己调 `selectPanel(id)`（`PanelRow` → `onClick: () => selectPanel(id)`）；
  插件不维护显示状态、不注册任何"当前选中"全局量。
- 主列渲染：`MainPanel` 调 `renderSlot('main', {}, { entryKey: activePanelId ?? 'conversation' })`。

### 选中态的可观测证据（E2E 用） «serves: FR-2, FR-3»

sidebar 把每个面板渲染成 `<button aria-label=... aria-current="page"|undefined>`（选中时才有 `aria-current`）。
因此 E2E 用「面板按钮是否有 `aria-current="page"`」判定 `activePanelId`，无需读 React 内部状态。

## 目录结构：一个页面一个文件夹 «serves: FR-1, FR-5»

**结论（回答「能否一个页面一个文件夹」）：能，而且现状就是这个形状**——每个页面已经是独立包
`packages/web/<页面>/`，差异只在 `src/client/` 内的文件。本次重构把「页面插槽化」的新增代码
按同一粒度收进每个页面自己的一个文件夹 `src/client/page/`。

**依赖边界（修正）**：`dsh-pmboard` 是**自包含**包——`package.json` 的依赖只有 `@deepseek-ai/dsh-tools`，
client 侧无任何裸 npm import，且**不依赖 `@pi-investment/page-kit`**（也不得依赖）。
因此 Phase 1 的标准 helper 落在 dsh-pmboard 自己的文件夹内，page-kit 与本需求无关：

```
packages/web/
├── dsh-pmboard/src/client/            ← 自包含，不引用 page-kit
│   ├── page/page-panel.ts      ← 新增：registerPagePanel（Phase 1 标准 helper 落点）
│   ├── page/register.ts        ← 新增：main + sidebar.panellist 两端注册（id=dsh-pmboard）
│   ├── page/host.ts            ← 新增：薄 React 宿主（useRef + useEffect）
│   ├── board-mount.ts          ← 改造：导出 attachBoard(container)，壳生命周期下沉到宿主
│   ├── board-shell.ts          ← 删除（FR-4）
│   ├── session-jump.ts         ← 改造：删 closeHostPanel，改 selectPanel(null)
│   └── dom.ts                  ← 改造：删 ACTIVE_ATTR / OTHER_ACTIVE_ATTRS
├── execution/src/client/page/…   ← Phase 2 目标形态；本需求只出清单，不改其源码（已依赖 page-kit）
├── holdings/src/client/page/…    ← 同上
├── genome/src/client/page/…      ← 同上
└── bulletin/src/client/page/…    ← 同上
```

**本次代码改动只落在 `packages/web/dsh-pmboard/`（含它自己的 `package.json`）**；
其余 4 个页面包与 `page-kit` 的源码**一行不改**（它们只出现在 migration.md 的迁移清单里）。

为什么 helper 不放进「每个页面一个文件夹」：两端 id 同源是**框架契约**（`MainPanelId`），
复制 5 份必然漂移（本仓「两份真相」教训）——但这条纪律在 Phase 1 只作用于 dsh-pmboard **包内**：
helper 是该包的一个模块，由 `page/register.ts` 引用，仍是「一处定义、两端使用」。
其余 4 个面板已依赖 page-kit，Phase 2 的复用落点（page-kit 收编 / 各自自包含）在拆分阶段按包定；
本设计只固定**契约**（签名与 id 同源语义），不预先断言落点。

## 标准 helper：registerPagePanel «serves: FR-1, FR-2»

### 接口契约 «serves: FR-1»

落点：`packages/web/dsh-pmboard/src/client/page/page-panel.ts`（Phase 1 该包自包含；其余 4 包的复用落点见 §目录结构）。

```ts
// packages/web/dsh-pmboard/src/client/page/page-panel.ts
export interface PagePanelSpec {
  /** 主列 key 与侧栏条目 id 的同源身份（MainPanelId） */
  id: string
  /** 侧栏条目文案 */
  label: string
  /** 侧栏条目排序（升序，并列保持注册顺序），默认 0 */
  order?: number
  /** 主列占用者：React 组件（收 main 插槽标准 props） */
  Component: unknown
  /** 侧栏图标：React 组件（收 { size, active }）；缺省用内置通用图标 */
  Icon?: unknown
}

export interface SlotRegistrar {
  inject(slot: string, thunk: () => unknown): unknown
  register(options: Record<string, unknown>, occupant: unknown): unknown
}

/** 一次注册两端；返回幂等 disposer。ctx.slots 缺失时抛错（响亮，不静默）。 */
export function registerPagePanel(ctx: { slots?: SlotRegistrar }, spec: PagePanelSpec): () => void
```

### 行为约定 «serves: FR-1, FR-2»

1. `main` 注册：`{ name: 'main', key: spec.id }` + `spec.Component`；
2. `sidebar.panellist` 注册：`{ name: 'sidebar.panellist', id: spec.id, order: spec.order ?? 0, label: spec.label }`；
3. 两处 id 只来自 `spec.id`（同源 = FR-1 的可证伪点：不可能只改一端）；
4. disposer 依次撤销两次注册，可重复调用（HMR re-apply 安全）；
5. `ctx.slots` 缺失 → 抛 `Error('[page-panel] ctx.slots unavailable（inject 缺 "slots"）')`，
   由页面 `apply()` 的 try/catch 记录——**不降级为"页面静默不存在"**。

### 使用样板 «serves: FR-2»

```ts
// packages/web/dsh-pmboard/src/client/page/register.ts
export function registerPmboardPage(ctx: ApplyContext): () => void {
  return registerPagePanel(ctx, {
    id: PANEL_ID,            // 'dsh-pmboard'：main.key 与 panellist.id 同一常量
    label: '项目看板',
    order: 110,
    Component: BoardPanelHost,
  })
}
```

## 看板页面化 «serves: FR-2»

### 薄宿主 «serves: FR-2»

```tsx
function BoardPanelHost() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (ref.current === null) return
    const dispose = attachBoard(ref.current)   // 现有命令式看板原样挂上
    return dispose
  }, [])
  return createElement('div', { ref, className: 'dsh-pm-view', 'data-dsh-pm-view': '' })
}
```

不重写命令式看板：`attachBoard(container)` 只是把现有 `board-mount.ts` 里 `onMount` 的内容
（事件委派、`fetchAll`、SSE 订阅）原样挂到宿主给的容器上，返回值就是原来的清理函数。

### 轮询与订阅的生命周期 «serves: FR-2»

- 现状：`board-shell.ts` 用 `setInterval(tick, 20000)`，仅打开时 tick；`pauseOnHidden` 另听 `visibilitychange`。
- 目标：宿主挂载即"在看"——轮询/SSE 随 `attachBoard` 起、随 disposer 止；`visibilitychange` 保留。
- `usePanelInfo().activePanelId` 作防御性门闩：keyed 插槽切 key 会卸载上一个占用者
  （`RenderOpts.overlay` 的存在正是为 chain 保留"不被卸载"语义，说明 keyed 默认卸载），
  故正常路径下挂载≈在看；仍订阅 `activePanelId`，`!== PANEL_ID` 时跳过轮询——两种语义下行为一致。

## 跳转语义归位 «serves: FR-3»

- `session-jump.ts`：删除 `closeHostPanel()`（它手工模拟 `selectPanel(null)`）。
- `jumpToSession`：先 `layout.selectPanel(null)`（回对话），再 `uiWorkspace.openSession(sid)`（切会话）；
  目标会话即当前会话时同样先回对话，只省掉 `openSession`。
- 归档会话：保持现状（可点按钮 + `data-archived="true"` + 明确 title/alert 文案），**不置灰不可点**。
- `layout` 来源：`apply()` 把 `ctx.layout` 交给页面运行环境对象（模块级 `pageRuntime`），
  `session-jump` 经它读——与现有 `window.__dshPmCtx` 惰性读同款，但不再新增全局。
- 声明：模块 `export const inject` 增加 `'layout'`（Cordis 服务访问守卫要求），
  `package.json` 的 `dsh.client.inject` 同步（保持 boot 图口径与现状一致）。

### 调用方与依赖清单（refactor 必交） «serves: FR-3, FR-4»

| 被改文件 | 谁调用它 | 它调用谁 |
|---|---|---|
| `src/client/page/page-panel.ts`（新） | `page/register.ts` | — |
| `src/client/page/register.ts`（新） | `src/client/index.ts` 的 `apply` | `./page-panel.registerPagePanel` |
| `src/client/page/host.ts`（新） | `main` 插槽渲染器 | `board-mount.attachBoard`、`usePanelInfo` |
| `board-mount.ts` | `host.ts`、测试 | `session-jump`、`view`、`api` |
| `session-jump.ts` | `board-mount`、`footer-action` | `ctx.layout`、`ctx.uiWorkspace` |
| `board-shell.ts`（删） | `board-mount`（现） | — |
| `dom.ts` | 全 `client/` | — |

验证"没漏"：删除后 `grep -rn "board-shell\|createBoardShell\|ACTIVE_ATTR\|OTHER_ACTIVE_ATTRS\|closeHostPanel\|ACTIVATE_EVENT" packages/web/dsh-pmboard/src`
应只剩注释/无命中；`pnpm --filter dsh-pmboard test` 全绿。

## 行为不变式与回滚 «serves: FR-2, FR-3, FR-4»

1. **业务等价**：数据获取（`/dashboard/api/reqboard/*` + SSE）、渲染结构、点击语义不变；只换挂载与导航。
2. **跳转结果等价**：目标会话选中 + 对话可见；归档给出明确原因。
3. **零数据/接口破坏**：不动 `queue.json` / `dsh-reqboard.json` / HTTP 路由。
4. **可回滚**：新旧是两套挂载；回滚 = 还原 `board-shell.ts`、属性 CSS、`index.ts` 的注册（同提交内可逆）。
5. **门禁不退化**：`build:client` 三闸 + 插件 schema 冒烟测试保持通过。

## 边界（本设计不做） «serves: FR-4, FR-5»

- 不改看板业务逻辑与视觉；不把命令式看板重写成 React（薄宿主 + `ref` 挂载）。
- 不动 reqboard 数据层与 `/dashboard/api/reqboard/*`。
- 不引入 URL 路由（壳无路由，实测 `openSession` 后仍为 `/`）。
- 其余页面只产出清单与 helper，**不在本需求内改代码**。
- 不新增 npm 依赖；client 侧 import 仍只含 react 与已 `noExternal` 的包。
