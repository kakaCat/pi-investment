# 拆分计划文档

**需求ID**: REQ-260928222643-4d34  
**需求标题**: 节点面板加「去项目看板」入口（方案②）并下掉执行流程块  
**类型 / 难度**: feature / 重档（需求分析阶段由轻档单向升级：出现「打开后定位到该需求详情」这第二个未定决策）  
**创建时间**: 2026-09-28  
**设计输入**: `design/architecture.md`、`interfaces.md`、`data-model.md`、`frontend.md`、`use-cases.md`、`test-cases.md`（均已落章确认）  
**改动面**: `packages/web/dsh-pmboard`（浏览器侧页面插件，单侧前端改动；不动台账、不动后端路由、不动看板既有行为）

> 交付口径：面板状态行「项目看板 ↗」→ 一次性交接 → 看板直接打开**该需求详情**；同时把「🔄 执行流程」整块（连标题行）与它的两次无用拉取从面板侧下掉。

---

## 1. 代码层面变更盘点

### 1.1 新增文件（2 源码 + 2 测试）

| 文件 | 内容 | 设计落点 | 服务条款 |
|---|---|---|---|
| `packages/web/dsh-pmboard/src/client/board-focus.ts` | 模块级**一次性**交接持有器：`requestBoardFocus` / `takeBoardFocus` / `clearBoardFocus` / `peekBoardFocus`（零 import，同 `page-runtime.ts` 依赖纪律） | I-1、T-2 | FR-2 |
| `packages/web/dsh-pmboard/src/client/board-entry.ts` | 入口校验纯函数：`activateBoardEntry(reqId, deps)` + `boardEntryFailureMessage(reason, reqId, detail?)`（纯函数 + 依赖注入，无 React/DOM/fetch） | I-2 | FR-3 |
| `packages/web/dsh-pmboard/tests/board-focus.test.ts` | TC-6：取走即清 / 幂等 / 空值不登记 | I-1、T-2、T-3 | FR-2 |
| `packages/web/dsh-pmboard/tests/board-entry.test.ts` | TC-9~TC-13：三种失败 + 成功路径 + 失败零副作用 | I-2、I-6 | FR-3 |

### 1.2 修改文件（4 源码 + 3 测试）

| 文件 | 改动内容 | 设计落点 | 服务条款 |
|---|---|---|---|
| `src/client/node-panel.ts` | ① `renderHead`（L292-305）内、相对时间之后追加 `<button type="button" class="dsh-pm-np-board-entry" data-action="np-board-entry" data-req=…>`，文案固定「项目看板 ↗」（跳过分支与正常分支共用 `renderHead` → 7 节点自动全覆盖）；② 删除 `renderProcessFold(payload, processCtx)` 调用（L344）、`ProcessFoldContext` 构造（L331-335）、`NodePanelInput.injection/isolation`（L42-43）与相关 import（L30-36）；③ 同步文件头注释（L10） | I-3、I-4、T-4 | FR-1、FR-4、FR-5 |
| `src/client/conversation-progress.ts` | ① 删除注入/隔离两条留痕的 import、state（L113-115）、拉取 effect（L182-198）与 props 传参（L354-355）；② `closePanel` 声明上移到 `if (!detailOpen) return` 之前（纯搬移）；③ 新增 document 级 `np-board-entry` 点击委派：`activateBoardEntry` 校验 → `ok=false` 就地提示且**不切页**；`ok=true` 关面板 + `layout.selectPanel(PANEL_ID)`；④ 新增 `entryError` state 与 `role="alert"` 的 `.dsh-pm-np-entry-err` 提示渲染 | P-3、I-2、I-6 | FR-1、FR-2、FR-3、FR-5 |
| `src/client/styles/node-panel.ts` | 新增 `.dsh-pm-np-board-entry`（`flex:none` + `min-height`，不裁切、可点）与 `.dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err`（红字就地提示）两条作用域内规则 | P-2、P-5 | FR-1、FR-3 |
| `src/client/board-mount.ts` | `createBoardAttachment`（L177）内把 `let mode: ViewMode = { kind: 'board' }`（L180）改为挂载时读一次 `takeBoardFocus()`：有值 → `{kind:'req', reqId}`，无值 → `{kind:'board'}`；陈旧 id 走**既有**回退（L240），不新增分支 | I-5、T-3 | FR-2 |
| `tests/node-panel.test.ts` | 反写 TC-2（改为断言输出**不含**「🔄 执行流程」）、删除 TC-4「执行流程三段」整组；新增 TC-1（入口存在 + 文案逐字）、TC-2′（分类跳过态也含入口）、TC-5（面板侧零留痕拉取的静态断言） | TC-1~TC-5 | FR-1、FR-4、FR-5 |
| `tests/node-panel-styles.test.ts` | 新增 TC-14：`.dsh-pm-np-board-entry` 含 `flex:none` 与 `min-height`、`.dsh-pm-np-head` 仍 `flex-wrap:wrap`；既有「每条选择器含 `.dsh-pm-np` / `.dsh-pm-cprog-detail-panel` / `:root`」断言继续全绿 | P-2 | FR-1 |
| `tests/board-attach.test.ts` | 复用既有假容器 + `fetch`/`EventSource` 桩，新增 TC-7（`requestBoardFocus('REQ-a')` → 挂载后走 `buildReqDetail`，且 `peekBoardFocus()` 已清）与 TC-8（陈旧 id → 默认看板、再挂载仍默认）；文件头补 `serves:` 声明 | I-5、T-3 | FR-2 |

### 1.3 删除文件

无。`src/client/node-panel-process.ts` 与 `tests/node-panel-process-map.test.ts` **保留**（requirement 明示「函数可留」：只断调用，不删函数）。

### 1.4 明确不动（防顺手改）

| 对象 | 处置 |
|---|---|
| `src/client/api.ts` 的 `fetchInjectionInfo` / `fetchIsolationLog` | 保留（看板等消费方仍用） |
| `src/client/board-mount.ts:721` 的 `api.fetchInjectionInfo(...)` 调用 | 保留（反面断言：恰好 1 处，防止「按整目录 grep 一把删」改坏看板） |
| 后端 `GET /dashboard/api/reqboard/injection-log`、`/isolation-log` 路由与采集链路 | 保留 |
| 看板既有行为（泳道/列表/筛选/排序/详情页结构/SSE/轮询/事件委派/自动链控制面） | 逐字不动 |
| 台账字段与 `REQBOARD_SCHEMA_VERSION` | 不动（无迁移、无回填；无新增派生/审计数据 → `data_contracts.json` 无需登记） |

---

## 2. 任务拆分与依赖

### 2.1 任务列表

| 任务ID | 任务名称 | phase | side | 依赖 | 服务条款 |
|---|---|---|---|---|---|
| t1 | 数据契约：新增一次性交接持有器 `board-focus.ts` | implement | frontend | - | FR-2 |
| t2 | 接口契约：新增入口校验与失败提示 `board-entry.ts` | implement | frontend | t1 | FR-3 |
| t3 | 面板改造：`node-panel.ts` 加入口按钮 + 下掉执行流程块与入参 | implement | frontend | t1, t2 | FR-1, FR-4, FR-5 |
| t4 | 接线：`conversation-progress.ts` 点击→校验→关面板→切看板；删两条留痕拉取 | implement | frontend | t1, t2, t3 | FR-1, FR-2, FR-3, FR-5 |
| t5 | 消费：`board-mount.ts` 挂载时 `takeBoardFocus()` 初始化 mode | implement | frontend | t1 | FR-2 |
| t6 | 样式：入口按钮与失败提示两条作用域内规则 | ui | frontend | t3, t4 | FR-1, FR-3 |
| t7 | 迁移与兼容：无 schema 变更 + 旧调用方/看板消费方不回归 | test | frontend | t4, t5 | FR-4, FR-5 |
| t8 | 构建发版与端到端人工验收（TC-15） | merge | fullstack | t3, t4, t5, t6, t7 | FR-1, FR-2, FR-3, FR-4, FR-5 |

### 2.2 依赖关系（只能依赖**前面已定义**的 key）

```
t1 (board-focus 数据契约)
 ├─> t2 (board-entry 接口契约) ──┐
 │                               ├─> t3 (node-panel 入口 + 下掉执行流程)
 │                               │     └─> t4 (conversation-progress 接线) ──┬─> t6 (样式)
 │                               │                                          └─┬─> t7 (迁移与兼容)
 └───────────────────────────────┴─> t5 (board-mount 消费) ──────────────────┘
t3, t4, t5, t6, t7 ──> t8 (构建发版 + 端到端人工验收)
```

---

## 3. 需求条款 ↔ 任务覆盖对照表（RTM）

| 根编号 | 需求条款摘要 | 接收任务 |
|---|---|---|
| FR-1 | 面板状态行新增「项目看板 ↗」入口，7 个节点（含分类跳过）全显示 | t3、t4、t6、t8 |
| FR-2 | 点入口 = 打开看板并定位到该需求详情；面板关闭、会话不切 | t1、t4、t5、t8 |
| FR-3 | 目标不可达时不切页 + 就地提示原因（不静默/不白屏/不「切过去看到列表」） | t2、t4、t6、t8 |
| FR-4 | 下掉「🔄 执行流程」折叠块（连标题行都不出现） | t3、t7、t8 |
| FR-5 | 面板不再拉取注入/隔离留痕；后端与看板消费方保留 | t3、t4、t7、t8 |

---

## 4. 任务详细说明

### Task 1: 数据契约 · 一次性交接持有器
«serves: FR-2»

**key**: t1  
**title**: 新增一次性交接持有器 src/client/board-focus.ts  
**phase**: implement  
**side**: frontend  
**depends_on**: []  
**requirement_refs**: ["FR-2"]

**description**:
看板的 `mode` 是**挂载闭包内**的局部变量（`board-mount.ts:180`），宿主又是 keyed 插槽（切走即卸载）。故「谁在何时把 REQ id 交给看板」只能靠**模块级一次性持有器**：面板点击时登记，看板挂载时消费即清。不落 storage、不进 URL、不挂 `window` —— 非粘滞（刷新/再次进入看板必回默认视图）。

**implementation**:
1. 新建 `packages/web/dsh-pmboard/src/client/board-focus.ts`。文件头注明：零 import（同 `page-runtime.ts` 依赖纪律）；一次性语义（取走即清）。
2. 模块级 `let pendingReqId: string | undefined`，导出四个函数：
   - `requestBoardFocus(reqId: string): void` —— `trim()` 后空串/纯空白 → 清空（不登记空意图）；非空 → 登记（只存 id，不存标题/阶段等可推导信息，避免两份真相）；
   - `takeBoardFocus(): string | undefined` —— 读后**立即**置 `undefined`（消费即清）；
   - `clearBoardFocus(): void` —— 幂等清空（失败路径与测试收尾）；
   - `peekBoardFocus(): string | undefined` —— 只读探测（不消费），仅供单测/诊断；生产路径不得用它判断后仍假设未被消费。
3. 全程不抛错（无 IO、无解析）；不写 `localStorage`/`sessionStorage`、不解析 `location.hash`/`URLSearchParams`。
4. 新建 `tests/board-focus.test.ts`，首行写 `// serves: FR-2`，覆盖 TC-6：① `requestBoardFocus('REQ-a')` → `takeBoardFocus()` 得 `'REQ-a'`；② 立刻再 `takeBoardFocus()` 得 `undefined`；③ `clearBoardFocus()` 后 `peekBoardFocus()` 得 `undefined`；④ `requestBoardFocus('  ')` 后 `takeBoardFocus()` 得 `undefined`。

**acceptance**:
- `cd packages/web/dsh-pmboard && npx vitest run tests/board-focus.test.ts` 全绿（TC-6 四条断言通过）。
- `grep -c "export function" src/client/board-focus.ts` 输出 `4`（四个导出齐备）。
- `grep -n "localStorage\|sessionStorage\|URLSearchParams\|location.hash" src/client/board-focus.ts` 无匹配（exit 1）——证明一次性、非粘滞。

### Task 2: 接口契约 · 入口校验与失败提示
«serves: FR-3»

**key**: t2  
**title**: 新增入口校验纯函数 src/client/board-entry.ts  
**phase**: implement  
**side**: frontend  
**depends_on**: [t1]  
**requirement_refs**: ["FR-3"]

**description**:
「先校验、后切页」的机械保证：`activateBoardEntry` 按 ①`layout` 可用性 → ②`reqId` 形状 → ③台账可达性 → ④`requestFocus` 顺序执行；任一前置失败返回 `{ok:false, reason, message}` 且**零副作用**（未登记意图、未导航）。产品上对应 FR-3：到不了就当场说清原因并留在原页。

**implementation**:
1. 新建 `packages/web/dsh-pmboard/src/client/board-entry.ts`（纯函数 + 依赖注入，无 React / 无 DOM / 不直接 fetch）。
2. 定义 `type BoardEntryFailure = 'nav-unavailable' | 'req-missing' | 'ledger-unreachable'`；`boardEntryFailureMessage(reason, reqId, detail?)`；`interface BoardEntryDeps { isKnown(reqId): Promise<boolean>; requestFocus(reqId): void; layout: { selectPanel(id: string | null): void } | undefined }`；`type BoardEntryVerdict = {ok:true} | {ok:false; reason; message}`；`activateBoardEntry(reqId, deps): Promise<BoardEntryVerdict>`。
3. 顺序与文案（与 `interfaces.md` I-2 错误码表逐字一致）：
   - `nav-unavailable`：`deps.layout === undefined` → 「页面导航服务不可用（layout 未注入），请刷新页面后重试」；
   - `req-missing`：`reqId` 为空或非 `REQ-` 形状，或 `isKnown` 返回 `false` → 「需求 {id} 不在台账（可能已归档或被删除），未跳转」；**空 id 不打接口**（`isKnown` 零调用）；
   - `ledger-unreachable`：`isKnown()` 抛错（含 8s 超时）→ 「无法确认需求是否可达（台账接口失败：{detail}），未跳转」；
   - 全通过 → `deps.requestFocus(reqId)` 后返回 `{ok:true}`。
4. 新建 `tests/board-entry.test.ts`，首行写 `// serves: FR-3`，用桩 deps 覆盖 TC-9/10/11/12/13。

**acceptance**:
- `cd packages/web/dsh-pmboard && npx vitest run tests/board-entry.test.ts` 全绿（TC-9~TC-13）。
- 三种失败路径断言 `requestFocus` 调用 **0** 次、`layout.selectPanel` 调用 **0** 次（TC-13 零副作用）；空 `reqId` 时 `isKnown` 调用 0 次。
- 成功路径断言 `requestFocus` **恰好 1 次**且参数为该 id（TC-12）；三种失败 message 文案均被断言。

### Task 3: 面板改造 · 入口按钮 + 下掉执行流程块
«serves: FR-1, FR-4, FR-5»

**key**: t3  
**title**: node-panel.ts 加入口按钮并删除执行流程块调用与入参  
**phase**: implement  
**side**: frontend  
**depends_on**: [t1, t2]  
**requirement_refs**: ["FR-1", "FR-4", "FR-5"]

**description**:
入口写进 `renderHead`——它是 `enabled=false` 早退分支与正常分支**共用**的头部，故「7 个节点全显示（含本分类跳过）」是结构性保证，而非 7 处补丁。同时删除面板末尾的 `renderProcessFold` 调用与 `injection`/`isolation` 入参（FR-4/FR-5）。

**implementation**:
1. `src/client/node-panel.ts` 的 `renderHead`（L292-305）末尾追加：`<button type="button" class="dsh-pm-np-board-entry" data-action="np-board-entry" data-req="<esc(req.id)>" title="打开项目看板并定位到该需求">项目看板 ↗</button>`（文案**固定**，含尾随空格 + ↗）。
2. 删除 L31-36 中 `renderProcessFold`、`ProcessFoldContext`、`InjectionInfoEntry` 的 import（`STAGE_STATE_WORD`、`IsolationLogEntry` 若仅此处用一并处理）。
3. 删除 `NodePanelInput` 的 `injection?`/`isolation?`（L42-43）、`processCtx`（L331-335）与 `renderProcessFold(payload, processCtx)`（L344）。`stage` 早退分支（L324-329）除共用 `renderHead` 外不额外接线。
4. 更新文件头注释（L10 去掉「🔄 执行流程」描述），注释与实现同步。
5. 同步 `tests/node-panel.test.ts`：反写 TC-2 为 `not.toContain('🔄 执行流程')`；删除 TC-4「执行流程三段」整组；新增 TC-1（输出含 `项目看板 ↗` + `data-action="np-board-entry"` + `data-req="REQ-test-1"`，且位于 `.dsh-pm-np-head` 内、`.dsh-pm-np-head-time` 之后）、TC-2′（跳过态同时含「本分类跳过该节点」与入口）、TC-5（静态断言面板侧三文件零留痕拉取 + `board-mount.ts` 恰好 1 处 `fetchInjectionInfo`）。

**acceptance**:
- `cd packages/web/dsh-pmboard && grep -n "renderProcessFold" src/client/node-panel.ts` 无匹配（exit 1，函数可留但调用已断）。
- `grep -n "injection\|isolation" src/client/node-panel.ts` 无匹配（入参/类型 import 已清）。
- `npx vitest run tests/node-panel.test.ts` 全绿：TC-1/TC-2/TC-2′/TC-3/TC-5 通过，7 节点渲染输出**均不含**「🔄 执行流程」。
- `npx vitest run tests/node-panel-process-map.test.ts` 仍全绿（`node-panel-process.ts` 保留、未误删）。

### Task 4: 接线 · 会话头点击委派与失败提示
«serves: FR-1, FR-2, FR-3, FR-5»

**key**: t4  
**title**: conversation-progress.ts 接线点击→校验→关面板→切看板，并删两条留痕拉取  
**phase**: implement  
**side**: frontend  
**depends_on**: [t1, t2, t3]  
**requirement_refs**: ["FR-1", "FR-2", "FR-3", "FR-5"]

**description**:
消费端接线：document 级 click 委派先 `activateBoardEntry` 校验；失败就地提示且**不切页**，成功则关面板并 `layout.selectPanel(PANEL_ID)`（导航唯一来源）。同时删除只为已下掉的执行流程块服务的两条留痕 state/effect/props（FR-5）。

**implementation**:
1. `src/client/conversation-progress.ts`：删除 L19 的 `fetchInjectionInfo`/`fetchIsolationLog` import、L113-115 的 `injection`/`isolation` state、L182-198 的拉取 effect、L354-355 的 props 传参及相关类型 import（`InjectionInfoEntry`/`IsolationLogEntry`）。
2. 新增 `entryError` state；把 `closePanel` 声明（原 L330）**上移**到 `if (!detailOpen) return …`（L327）之前（纯搬移，无行为变化），使 hooks/effect 无条件声明在早退之前。
3. 新增第三个 document 级 click 委派 effect（与既有 `np-switch-view` 同款）：`closest('[data-action="np-board-entry"]')` → 取 `data-req` → `setEntryError('')` → `await activateBoardEntry(reqId, { isKnown: async id => (await fetchState()).requirements.some(r => r.id === id), requestFocus: requestBoardFocus, layout: getPageLayout() })`；`!verdict.ok` → `setEntryError(verdict.message); return`（不切页）；否则 `closePanel()` + `getPageLayout()?.selectPanel(PANEL_ID)`。
4. `panelChildren` 中、节点面板容器之前插入 `entryError` 非空时渲染的 `role="alert"` 文本，类名 `.dsh-pm-np-entry-err`（就地可见，不用 `console`/`window.alert`）。
5. import 来源：`requestBoardFocus` 来自 `./board-focus.ts`、`activateBoardEntry` 来自 `./board-entry.ts`、`getPageLayout` 来自 `./page/page-runtime.ts`、`PANEL_ID` 来自 `./dom.ts`、`fetchState` 来自 `./api.ts`（复用既有读同一台账的接口，不新增网络契约）。

**acceptance**:
- `cd packages/web/dsh-pmboard && grep -rn "fetchInjectionInfo\|fetchIsolationLog" src/client/conversation-progress.ts src/client/node-panel.ts` 无匹配（exit 1，FR-5 面板侧零引用）。
- `grep -n "np-board-entry\|activateBoardEntry\|selectPanel(PANEL_ID)\|dsh-pm-np-entry-err" src/client/conversation-progress.ts` 四个符号**全部命中**（接线齐备）。
- `grep -n "closePanel" src/client/conversation-progress.ts` 显示的声明行号**小于** `if (!detailOpen) return` 所在行号（上移生效）。
- `pnpm run typecheck` 通过（无类型错误）。

### Task 5: 消费 · 看板挂载时读取定位意图
«serves: FR-2»

**key**: t5  
**title**: board-mount.ts 挂载时 takeBoardFocus 初始化 mode  
**phase**: implement  
**side**: frontend  
**depends_on**: [t1]  
**requirement_refs**: ["FR-2"]

**description**:
看板 `mode` 是挂载闭包内局部变量，故只能在 `createBoardAttachment` 挂载时从模块级持有器读一次；取走即清保证「被定位」是一次性状态。

**implementation**:
1. `src/client/board-mount.ts` 顶部 `import { takeBoardFocus } from './board-focus.ts'`。
2. `createBoardAttachment`（L177）内 L180 `let mode: ViewMode = { kind: 'board' }` 改为：先 `const focusReqId = takeBoardFocus()`，再 `let mode: ViewMode = focusReqId !== undefined ? { kind: 'req', reqId: focusReqId } : { kind: 'board' }`（每次挂载最多消费一次）。
3. 其余一律不动：`render()` 的既有回退（L240：req 不在 → `mode={kind:'board'}`）、`fetchAll`、SSE、轮询、事件委派、`open-req` 动作。
4. 复用 `tests/board-attach.test.ts` 既有假容器 + `fetch`/`EventSource` 桩：新增 TC-7（先 `requestBoardFocus('REQ-a')`，`fetch` 返回含 REQ-a 的状态 → `container.innerHTML` 走 `buildReqDetail` 路径且 `peekBoardFocus()` 为 `undefined`）与 TC-8（`requestBoardFocus('REQ-gone')` + 桩状态不含该 id → 渲染默认看板、不抛错；再次挂载仍默认）；文件头补 `serves: FR-2`。

**acceptance**:
- `cd packages/web/dsh-pmboard && npx vitest run tests/board-attach.test.ts` 全绿（既有挂载生命周期用例不回归 + 新增 TC-7/TC-8 通过）。
- TC-7 断言 `peekBoardFocus()` 在挂载后为 `undefined`（消费即清）、`container.innerHTML` 含该需求 id 的详情标记；TC-8 断言连续两次挂载都渲染默认看板（非粘滞）。
- `grep -n "takeBoardFocus" src/client/board-mount.ts` 恰好命中 1 处消费调用。

### Task 6: 样式 · 入口按钮与失败提示
«serves: FR-1, FR-3»

**key**: t6  
**title**: styles/node-panel.ts 新增入口按钮与失败提示两条规则  
**phase**: ui  
**side**: frontend  
**depends_on**: [t3, t4]  
**requirement_refs**: ["FR-1", "FR-3"]

**description**:
窄面板下 head 行会换行（`.dsh-pm-np-head` 已有 `flex-wrap: wrap`）——接受换行，但要求**不被裁切、可点**；失败提示要在面板内就地可见。

**implementation**:
1. `src/client/styles/node-panel.ts` 新增 `.dsh-pm-np-board-entry { flex: none; min-height: 20px; padding: 1px 8px; border-radius: 980px; font-size: 11.5px; line-height: 18px; white-space: nowrap; cursor: pointer; border: 1px solid var(--dsh-pm-np-blue); color: var(--dsh-pm-np-blue); background: transparent; }` 与其 `:hover` 规则。
2. 新增 `.dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err { color: #c0392b; font-size: 12px; line-height: 1.5; padding: 6px 2px; }`。
3. 不动 `.dsh-pm-np-head-time` 的 `margin-left: auto`；不新增设计令牌/颜色变量（复用 `--dsh-pm-np-blue` 与既有红）。
4. `tests/node-panel-styles.test.ts` 新增 TC-14：断言两条规则的作用域（含 `.dsh-pm-np` / `.dsh-pm-cprog-detail-panel`）、`.dsh-pm-np-board-entry` 规则含 `flex: none` 与 `min-height`、`.dsh-pm-np-head` 仍含 `flex-wrap: wrap`。

**acceptance**:
- `cd packages/web/dsh-pmboard && npx vitest run tests/node-panel-styles.test.ts` 全绿（TC-14 + 既有「每条选择器含 `.dsh-pm-np` / `.dsh-pm-cprog-detail-panel` / `:root`」断言全过）。
- `grep -n "dsh-pm-np-board-entry\|dsh-pm-np-entry-err" src/client/styles/node-panel.ts` 两条规则均命中；`grep -c "flex-wrap" src/client/styles/node-panel.ts` 大于 0（换行不裁切保留）。

### Task 7: 迁移与兼容 · 无数据迁移 + 旧行为与消费方不回归
«serves: FR-4, FR-5»

**key**: t7  
**title**: 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归  
**phase**: test  
**side**: frontend  
**depends_on**: [t4, t5]  
**requirement_refs**: ["FR-4", "FR-5"]

**description**:
本需求**无数据迁移、无 schema 变更**（不新增台账字段、不动 `REQBOARD_SCHEMA_VERSION`、不新增派生/审计数据）；唯一调用方 `NodePanelInput` 已随 t3/t4 同批修改。本卡把「不误删、不粘滞、可回滚」做成可执行的静态与反面断言。

**implementation**:
1. 反面断言（看板消费方未被误删）：`grep -c "fetchInjectionInfo" src/client/board-mount.ts` 恰好 `1`；`grep -n "export function fetchInjectionInfo\|export function fetchIsolationLog" src/client/api.ts` 两条均命中。
2. 保留断言（函数可留、后端路由保留）：`grep -n "export function renderProcessFold" src/client/node-panel-process.ts` 命中；host 路由文件中 `/injection-log`、`/isolation-log` 两条路由仍存在。
3. 调用方收敛：`grep -rn "NodePanelInput" src/` 仅 `node-panel.ts`（定义）与 `conversation-progress.ts`（使用）命中，无遗留调用方传 `injection`/`isolation`。
4. 非粘滞断言：`grep -rn "localStorage\|sessionStorage\|URLSearchParams\|location.hash" src/client/board-focus.ts src/client/board-entry.ts` 无匹配。
5. 变更面核对：`git diff --name-only` 的文件集合属于本计划 1.1/1.2 清单；`git diff src/shared/protocol.ts` 显示 `REQBOARD_SCHEMA_VERSION` 所在行**未变**。
6. 回滚路径写进验收材料：`git revert <本次提交>` → `pnpm build:client`（过哨兵）→ `agent-dh/scripts/restart-with-build.sh`；台账与后端零残留。

**acceptance**:
- `cd packages/web/dsh-pmboard && grep -c "fetchInjectionInfo" src/client/board-mount.ts` 输出 `1`（反面断言：看板消费方保留）；`grep -rn "fetchInjectionInfo\|fetchIsolationLog" src/client/conversation-progress.ts src/client/node-panel.ts` 无匹配。
- `grep -n "export function renderProcessFold" src/client/node-panel-process.ts` 命中；host 路由文件中 `injection-log`、`isolation-log` 均命中（后端接口保留）。
- `grep -rn "NodePanelInput" src/` 仅 `node-panel.ts` 与 `conversation-progress.ts` 命中，且 `grep -n "injection,\|isolation," src/client/conversation-progress.ts` 无匹配。
- `git diff --name-only` 与计划清单一致，`git diff src/shared/protocol.ts` 无 `REQBOARD_SCHEMA_VERSION` 行改动。

### Task 8: 构建发版与端到端人工验收
«serves: FR-1, FR-2, FR-3, FR-4, FR-5»

**key**: t8  
**title**: 重建客户端产物并发版，完成 TC-15 端到端人工验收  
**phase**: merge  
**side**: fullstack  
**depends_on**: [t3, t4, t5, t6, t7]  
**requirement_refs**: ["FR-1", "FR-2", "FR-3", "FR-4", "FR-5"]

**description**:
dsh-pmboard 是从 `dist` 加载的页面插件——只改源码不 build 等于没改。本卡负责：全量测试 + 构建门 + 发版 + 在 :13080 上做 TC-15 的人工四步闭环。

**implementation**:
1. 全量测试：`cd packages/web/dsh-pmboard && npx vitest run`（含新老用例）。
2. 构建门：`pnpm build:client`（内部 `tsdown` + `wrap-client.mjs` + `verify-client-build.mjs`，必须过 WRAP_SENTINEL 哨兵与产物校验）与 `pnpm run typecheck`。
3. 发版：`agent-dh/scripts/restart-with-build.sh`（校验符号链接 → 构建 → bootout → bootstrap），等待 :13080 健康。
4. TC-15 端到端（人工，:13080）：① 会话里点开流程条任一节点（含分类跳过节点）→ 状态行出现「项目看板 ↗」，面板里**没有**「🔄 执行流程」那一行；② 点入口 → 切到项目看板并显示**这条需求的详情**（Token/追溯/条款接收/验收单），节点面板关闭、会话未被切走；③ 刷新页面 → 看板回默认视图（非粘滞）；④ 用不存在/错误的 REQ 触发 → 仍停在会话页 + 可见失败提示（不静默、不白屏、不是列表）。
5. 记录 `pnpm build:client` 与 `npx vitest run` 的输出摘要作为验收材料。

**acceptance**:
- `cd packages/web/dsh-pmboard && npx vitest run` 全绿（0 failed）；`pnpm run typecheck` 退出码 0。
- `pnpm build:client` 退出码 0 且 `node scripts/verify-client-build.mjs` 校验通过（WRAP_SENTINEL 无污染）。
- 打开 :13080 → 会话节点面板：状态行含「项目看板 ↗」、面板不含「🔄 执行流程」；点入口后看板显示该需求详情且节点面板关闭；刷新后看板回默认视图；用错误 REQ 触发仍停在会话页并有可见失败提示（TC-15 四步逐条截图留证）。

---

## 5. 边界校验

### 5.1 不超范围

- 只改 `packages/web/dsh-pmboard` 客户端与本需求文档：2 个新增源码 + 4 个修改源码 + 4 个测试文件（含 board-attach 扩展）。
- 不改台账字段 / `REQBOARD_SCHEMA_VERSION` / 后端路由；不删 `api.ts` 的两个查询、不删 `node-panel-process.ts`。
- 不动看板既有行为（泳道/列表/筛选/排序/详情结构/SSE/轮询/事件委派/自动链控制面）。
- 不加方案①/③/④ 的其它入口位置，不动侧栏「项目看板」入口与流程条本身。

### 5.2 卡可独立验收

- 每张卡的 acceptance 都是可执行命令 + 可观测输出（vitest / grep / typecheck / build / 页面操作）。
- 契约卡（t1/t2）先于实现卡；实现卡 `depends_on` 其契约卡；接线（t4/t5）与接口/数据/样式分卡，不跨层。

### 5.3 与设计无矛盾

- 落点、错误码文案、DOM 契约、一次性语义、作用域样式均逐条对齐 `design/architecture.md`、`interfaces.md`（I-1~I-7）、`data-model.md`（T-1~T-5）、`frontend.md`（P-1~P-5）。
- 测试用例对齐 `design/test-cases.md`（TC-1~TC-15）；TC-15 为人工端到端，其余为可自动化单测/静态断言。
- 对 requirement.md 原始验收命令的唯一修正：把「整目录 grep 两条留痕」收紧为「**面板侧三文件零引用** + 看板消费方恰好 1 处」，与「不动看板与后端」的边界一致（见 t7）。

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解（落在哪张卡） |
|---|---|---|
| 改 dist 包只改源码不 build → 上线后看不到变化 | 交付物等于没改 | t8 强制 `pnpm build:client`（过哨兵）+ `restart-with-build.sh` |
| 按整目录 grep 删留痕，误删看板消费方（`board-mount.ts:721`） | 看板「本次注入了什么」块失效 | t3/t7 反面断言：面板侧零引用 + `board-mount.ts` 恰好 1 处 |
| 交接状态落 storage/URL → 粘滞 | 刷新/再次进入看板仍钉在旧需求 | t1 非粘滞静态断言 + t5 TC-8 二次挂载仍默认 |
| 跳过态漏入口 | FR-1 判定失败（7 节点全显示） | t3 入口写进两分支共用的 `renderHead`；TC-2′ 用跳过态验 |
| `closePanel` 在早退之后声明，hooks 无条件调用报错 | 面板渲染异常 | t4 明确把声明上移到早退之前，acceptance 断言行号顺序 |
| 失败路径只 console 不显示 | 用户「点了没反应」 | t2 message 纯函数 + t4 `role="alert"` 就地渲染 + t8 E2E④ |

### 回滚方案

本需求为前端页面插件改动，无台账/后端残留：

```bash
git revert <本次交付提交>                            # 回退源码
cd packages/web/dsh-pmboard && pnpm build:client     # 重建客户端产物（过哨兵）
cd /Users/yunpeng/pi-investment/agent-dh && ./scripts/restart-with-build.sh
```

---

## 7. 验收门禁（全部任务完成后的整体标准）

1. `cd packages/web/dsh-pmboard && npx vitest run` 全绿；`pnpm run typecheck` 通过。
2. `pnpm build:client` 过构建门与 WRAP_SENTINEL 哨兵。
3. 面板侧：7 节点（含分类跳过）状态行均含「项目看板 ↗」；面板渲染输出不含「🔄 执行流程」。
4. 导航：点入口切到项目看板并显示该需求详情；失败时留在原页并有可见原因提示。
5. 非粘滞：刷新 / 再次进入看板回默认视图。
6. 边界：看板消费方与后端接口零改动；台账与 `REQBOARD_SCHEMA_VERSION` 零改动。

---

## 8. 总结

**改动规模**：2 新增源码（约 90 行）+ 4 修改源码 + 4 测试文件；`packages/web/dsh-pmboard` 单侧。
**任务数量**：8（契约 2 + 实现 2 + 接线/消费 2 + 样式 1 + 兼容 1 + 构建验收 1）。
**关键路径**：t1 → t2 → t3 → t4 → t6 → t8（t5/t7 可并行汇入 t8）。
**风险等级**：低—中（纯前端、无数据迁移；主要风险是「改 dist 不 build」与「误删看板消费方」，均已用命令级断言兜住）。

本计划严格对照已确认设计文档推导，每张卡都给可证伪的验收命令；批准后由 `reqboard_decompose` 落库并进入实施。
