# REQ-6cbbf7 实施计划 · 持仓看板去掉启动预取（改为打开时才加载）

- 需求：REQ-6cbbf7（bug）
- 窗口：w-ae7eb4c0（角色 investor，实例账户 agent_brain）
- 计划日期：2026-09-13

## 1. 现象

用户原话：「我没点击账户持仓就操作台显示 [dashboard-holdings] 已渲染：账户=agent_brain，账户数=7，持仓行=1 这待办，启动就会加载这个页面数据了」。

证据链：

1. **线上（用户控制台）**：2026-09-13 页面刷新后，**未点击**侧栏「账户持仓」，控制台即出现
   `[dashboard-holdings] 已渲染：账户=agent_brain，账户数=7，持仓行=1`。
2. **源码**：`packages/pages/holdings/src/client/board-mount.ts:256-259`
   `onMount: () => { controller.primeOnMount() }` → `primeOnMount`（:204-207）→
   `fetchAndRender(currentAccount, 'hot')` → 渲染后由 :114-116 打印上述日志。
3. **挂载时机**：`@pi-investment/page-kit` 的 `createBoardShell` 在创建时**同步** `ensureMounted()`
   （`board-shell.ts:73-84`，另有 MutationObserver 兜底）→ 容器在启动时就被挂进会话列，
   显隐只靠 `html[data-dsh-hld-active]`。**挂载 ≠ 用户在看**。

## 2. 根因

容器启动即挂载（page-kit 的既有契约，本身合理），但 holdings 在 `onMount` 里**主动发起了一次取数**。
这就是「没点就加载」。

两点补充事实（决定改动量）：

- 这次预取**省不掉服务端成本**：`parts=hot` 只缩小响应体，`services/portfolio-aggregation.ts:59-68`
  的 `aggregate()` 仍固定 fan-out 4 个上游（v2 `/api/simulation/accounts`、v2 账户状态含持仓与实时行情、
  v2 调度任务、Agent OS :8080 任务），只跳过 trades / watchRules（而这两块在首次打开时反正要 full 补齐）。
- 「打开才加载」的路径**已经存在且完整**：`onOpen → refreshOnOpen()`
  → `refreshModeFor(1, lastData=undefined)` = `'full'`（`services/parts.ts:50-60`；
  `tests/parts.test.ts:67-71` 已锁此契约）→ 首次点击即拉全量（含冷块），看板不会空。

## 3. 方案（最小改动）

1. **删掉挂载取数**：`onMount` 不再调用取数；移除已无调用方的 `primeOnMount`（接口 + 实现）。
2. **把「取数时机」收敛成一个可测纯函数** `fetchPlanFor(event, tick, payload)`：
   - `event='mount'` → `null`（永不取数）——把"挂载不取数"从注释约定升级为**回归锁**；
   - `event='open'` → `refreshModeFor(1, payload)`；
   - `event='poll'` → `refreshModeFor(tick, payload)`。
   `board-mount` 的三处取数入口（open/poll/refresh）统一走它，避免以后再有人给挂载加取数。
3. 同步更新 `services/parts.ts` 顶部注释与 `board-mount.ts` 生命周期注释（记录本次决策与证据）。

## 4. 任务拆分

| key | 标题 | phase | side | 依赖 | 验收 |
|---|---|---|---|---|---|
| t1 | 移除持仓看板挂载预取 | implement | frontend | — | `packages/pages/holdings/src` 中不存在从 `onMount` 出发的取数路径；`grep -n "primeOnMount" packages/pages/holdings/src` 无结果；`tsc --noEmit` 通过 |
| t2 | 取数时机收敛为纯函数 fetchPlanFor | implement | frontend | t1 | `services/parts.ts` 导出 `fetchPlanFor`；`board-mount.ts` 的 open/poll/refresh 全部经它取模式；无其它直连 `refreshModeFor` 的调用点 |
| t3 | 回归测试锁死「挂载不取数」 | test | frontend | t2 | `npx vitest run packages/pages/holdings/tests/parts.test.ts` 全绿；新增用例断言 `fetchPlanFor('mount', …) === null`（含 `payload` 有/无冷块两种情况），且既有用例语义不变 |
| t4 | 重建 client 产物并线上核验 | merge | fullstack | t3 | `pnpm --filter @pi-investment/dashboard-holdings build:client` 成功，`lib/client.js`/`lib/client.cjs` mtime 更新且 grep 不到旧「挂载预热」文案；刷新 :13080 后**启动阶段控制台无任何 holdings 取数日志**，点击侧栏入口后出现 `[dashboard-holdings] open refresh (full)` + `已渲染：…` |

## 5. 可核验签名（改前 / 改后）

| | 控制台签名 |
|---|---|
| 改前（缺陷，用户已实测） | 启动即 `[dashboard-holdings] mount prime (hot)`，紧接 `已渲染：账户=…，账户数=…，持仓行=…` |
| 改后（期望） | 启动阶段**无** holdings 请求与日志；点击侧栏「账户持仓」后才出现 `[dashboard-holdings] open refresh (full)` + `已渲染：…` |

## 6. 验证与留痕

- 单测：`npx vitest run packages/pages/holdings/tests/parts.test.ts`（node 环境，纯函数契约）。
- 构建证据：`lib/client.js` 的 mtime + 文案 grep（改前含 `mount prime`，改后不含）。
- 线上证据：刷新 :13080 后的控制台签名（上表），必要时由用户复核。
- 留痕：`decision_audit(record)` + `memory_write`，按 R-013 标注数据来源与时点（源码行号 / 构建时间 / 控制台观测时刻）。

## 7. 边界与不做的事

- **不改 page-kit 的挂载行为**：容器启动即挂载是共享契约（execution/bulletin/genome/pmboard 共用），本需求只在 holdings 侧停止"挂载即取数"。
- **不改 UI/不加 loading 态**：首次点击已有的 full 取数路径负责把数据补齐。
- **不改日志级别**：`已渲染` 保留为核验签名，改后它不再于启动阶段出现。
- **不扩散到兄弟看板**：pmboard（`board-mount.ts:255-282`）、bulletin（:151-152）、genome（:57-71）同样在 `onMount` 取数，另立需求处理。
- **不做懒挂载**：把 page-kit 容器改为"打开时才 build"牵动共享契约，不在本需求。

## 8. 工作区纪律

本改动落在**主工作区**（`:13080` 的 profile 经 `agent-dh/node_modules/@pi-investment/dashboard-holdings → packages/pages/holdings` 符号链接直接引用该目录，client 产物必须就地构建才生效）。提交时只 add 本需求相关文件；仓库当前存在其它会话的脏改动（`quantsys-v2/**`、`docs/work-logs/**` 等），不并入本提交。
