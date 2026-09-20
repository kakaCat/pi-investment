# REQ-6cbbf7 需求文档 · 持仓看板去掉启动预取（改为打开时才加载）

- 类型：bug
- 窗口：w-ae7eb4c0（角色 investor）
- 日期：2026-09-13
- 关联计划：docs/requirements/REQ-6cbbf7/plan.md

## 1. 背景与用户原话

> 「我没点击账户持仓就操作台显示 [dashboard-holdings] 已渲染：账户=agent_brain，账户数=7，持仓行=1 这待办，启动就会加载这个页面数据了」

用户刷新 :13080 后**未点击**侧栏「账户持仓」，控制台即出现 holdings 的取数与渲染日志——看板在用户没有打开它的时候就加载了数据。

## 2. 缺陷现象（可证伪）

刷新页面、不做任何点击，控制台出现：

- `[dashboard-holdings] mount prime (hot)`
- `[dashboard-holdings] 已渲染：账户=agent_brain，账户数=7，持仓行=1`

（用户 2026-09-13 实测；源码链路见 plan.md §1）

## 3. 期望行为

- **启动/刷新阶段**：holdings 看板不发起任何取数请求、无取数日志；
- **首次点击侧栏「账户持仓」**：触发 full 取数并正常渲染，控制台出现 `[dashboard-holdings] open refresh (full)` + `已渲染：…`，看板不为空。

## 4. 根因（已定位）

- page-kit `createBoardShell` 在创建时**同步挂载**容器（execution/bulletin/genome/pmboard 共用的共享契约，本身合理）；
- 但 holdings 在 `onMount` 里**主动取数**：`board-mount.ts` onMount → `primeOnMount` → `fetchAndRender(currentAccount, 'hot')`。**挂载 ≠ 用户在看，但取数已发生**；
- 这次 hot 预取**省不掉服务端成本**（`aggregate()` 仍固定 fan-out 4 个上游，只缩小响应体）；而首次打开的 full 取数路径**已经存在且完整**（`onOpen → refreshOnOpen → refreshModeFor(1, undefined) = 'full'`），删掉预取看板不会空。

## 5. 需求条款

- **FR-1**：挂载（mount）不得触发任何取数——删除 onMount 取数调用与已无调用方的 `primeOnMount`。
- **FR-2**：首次打开（open）必须走既有 full 取数路径并正常渲染，不出现空看板。
- **FR-3**：轮询（poll）取数节奏保持现状，不改变。
- **FR-4**：「挂载不取数」须有回归测试锁死（可断言的纯函数契约），防止回潮。
- **FR-5**：client 产物就地重建后线上可核验：启动阶段无 holdings 日志，点击后出现 `open refresh (full)`。

## 6. 边界（明确不做）

- 不改 page-kit 的挂载行为（共享契约，牵动兄弟看板）；
- 不改 UI、不加 loading 态（首次打开的 full 路径负责补齐数据）；
- 不改日志级别（`已渲染` 保留为核验签名，改后它不应在启动阶段出现）；
- 不扩散到 pmboard / bulletin / genome 等同样在 onMount 取数的兄弟看板（另立需求）；
- 不做懒挂载（改 page-kit 容器为"打开时才 build"不在本需求）。
