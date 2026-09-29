---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
---

# 测试用例设计（REQ-260928222643-4d34）

> 读者：写/改本包 client 测试的开发者。用例**从设计文档推导**（被测对象列回指 `I-x`/`P-x`/`T-x`）。
> **标注口径**：本仓门禁要求每个 H2 **及以下**章节都带 `serves: FR-x`（H1 除外），否则判孤儿章节；
> 用例头的 `serves:` 即模板里的 `validates:`（用例从设计推导，服务同一条 FR）。
> `covers: t-xxx` 的任务卡号在拆分节点回填（本节点尚无任务卡，不编造 id）。

## 用例总览 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

| 用例 | 验证什么 | 被测对象（设计落点） | 层级 |
|---|---|---|---|
| TC-1 | 入口存在且文案固定 | I-3、P-1 | 单测 |
| TC-2 | 分类跳过节点也带入口 | I-3（`renderHead` 共用） | 单测 |
| TC-3 | 面板不再出现「🔄 执行流程」 | I-4、P-5 | 单测 |
| TC-4 | 渲染器不再调用 `renderProcessFold` | I-4 | 静态断言 |
| TC-5 | 面板打开不再打两条留痕接口 | I-7 | 静态断言 |
| TC-6 | 一次性持有器语义（取走即清 / 幂等 / 空值） | I-1、T-2、T-3 | 单测 |
| TC-7 | 看板挂载消费定位并进入需求详情 | I-5 | 单测 |
| TC-8 | 陈旧/不存在 id 回退默认视图（非粘滞） | T-3、I-5 | 单测 |
| TC-9 | `layout` 未注入 → 不切页 + 提示原因 | I-2、I-6 | 单测 |
| TC-10 | REQ 不在台账 → 不切页 + 提示原因 | I-2、I-6 | 单测 |
| TC-11 | 台账接口失败 → 不切页 + 提示原因 | I-2、I-6 | 单测 |
| TC-12 | 成功路径：登记意图 + 关面板 + 切到 PANEL_ID | I-2、I-6 | 单测 |
| TC-13 | 失败路径零副作用（未登记意图、未导航） | I-6 | 单测 |
| TC-14 | 入口样式作用域内 + 不被裁切可点 | P-2 | 样式断言 |
| TC-15 | 端到端：点入口直达该需求详情（人工） | FR-2、FR-3 | E2E（人工） |

---

### TC-1 入口存在且文案固定 `serves: FR-1`

**测试目标**（被测对象 I-3/P-1）：`renderNodePanel` 输出含固定文案「项目看板 ↗」与 `data-action="np-board-entry"`。

**前置条件**：构造最小 `StageOverview`（任一节点 `enabled=true`）+ `requirement.id='REQ-test-1'`。

**测试步骤**：
1. 调 `renderNodePanel({overview, stage:'design', requirement})`。

**预期结果**：
- 输出含 `项目看板 ↗`（逐字，含 ↗）；
- 输出含 `data-action="np-board-entry"` 且 `data-req="REQ-test-1"`；
- 该按钮出现在 `.dsh-pm-np-head` 内、`.dsh-pm-np-head-time` 之后。

**覆盖场景**：正常流程 / 无相对时间（timeline 为空）仍渲染入口。

### TC-2 分类跳过节点也带入口 `serves: FR-1`

**测试目标**（被测对象 I-3）：`enabled=false` 的节点（走 `renderHead` + 早退分支）同样含入口。

**测试步骤**：把目标节点的 `enabled` 置 `false`，重跑 `renderNodePanel`。

**预期结果**：输出含「本分类跳过该节点」**且**含「项目看板 ↗」（两条同时成立）。

**覆盖场景**：边界——早退分支不丢入口（这是把入口写进共用 `renderHead` 的理由）。

### TC-3 面板不再出现执行流程块 `serves: FR-4`

**测试目标**（被测对象 I-4/P-5）：任意节点渲染输出都不含「🔄 执行流程」。

**测试步骤**：对 7 个节点各渲染一次面板。

**预期结果**：每次 `expect(html).not.toContain('🔄 执行流程')`；`<details>` 折叠块只剩 `ℹ️ 基础信息`
（实施节点只剩 [DAG][泳道] 两视图）。

**覆盖场景**：正常 / 跳过态 / 实施节点（无基础信息块）。

### TC-4 渲染器不再调用执行流程块 `serves: FR-4`

**测试目标**（被测对象 I-4）：静态断言 `src/client/node-panel.ts` 无 `renderProcessFold` 字样。

**测试步骤**：`grep -n "renderProcessFold" src/client/node-panel.ts`。

**预期结果**：exit 1（无匹配）。**函数本体可留**（`node-panel-process.ts` 不删）。

### TC-5 面板打开不再拉两条留痕 `serves: FR-5`

**测试目标**（被测对象 I-7）：静态断言面板侧三文件零引用。

**测试步骤**：
```bash
grep -rn "fetchInjectionInfo\|fetchIsolationLog" src/client/conversation-progress.ts src/client/node-panel.ts
grep -c "fetchInjectionInfo" src/client/board-mount.ts
```

**预期结果**：第一条 exit 1（无匹配）；第二条输出恰好 `1`（看板自己的消费方**未被误删**）。

**覆盖场景**：异常——防止「按整目录 grep 一把删」把看板行为改坏。

### TC-6 一次性持有器语义 `serves: FR-2`

**测试目标**（被测对象 I-1/T-2/T-3）：see-once 语义。

**测试步骤**：① `requestBoardFocus('REQ-a')` → `takeBoardFocus()`；② 立刻再 `takeBoardFocus()`；
③ `clearBoardFocus()` 后 `peekBoardFocus()`；④ `requestBoardFocus('  ')`。

**预期结果**：① 返回 `'REQ-a'`；② 返回 `undefined`（取走即清）；③ `undefined`（幂等）；④ 不登记空意图，
`takeBoardFocus()` 为 `undefined`。

### TC-7 看板挂载消费定位 `serves: FR-2`

**测试目标**（被测对象 I-5）：`createBoardAttachment` 挂载时把 `mode` 初始化到需求详情。

**步骤/预期**：先 `requestBoardFocus('REQ-a')`，再以假 `container` + 桩 `api.fetchState`（返回含 REQ-a）
挂载 → 断言容器 HTML 用的是 `buildReqDetail` 路径（而非 `buildBoard`）；且 `peekBoardFocus()` 为 `undefined`。

### TC-8 陈旧 id 回退默认视图 `serves: FR-2`

**测试目标**（被测对象 T-3/I-5）：定位目标不存在时的降级。

**步骤/预期**：`requestBoardFocus('REQ-gone')` + 桩 `fetchState` 不含该 id → 挂载后渲染**默认看板**，
不白屏、不抛错；且再次挂载仍为默认视图（**非粘滞**）。

### TC-9 `layout` 未注入 `serves: FR-3`

**测试目标**（被测对象 I-2/I-6）：`activateBoardEntry('REQ-a', {layout: undefined, ...})`。

**预期结果**：`{ok:false, reason:'nav-unavailable'}`；`message` 含「导航服务不可用」；`requestFocus` **未被调用**。

### TC-10 REQ 不在台账 `serves: FR-3`

**测试目标**（被测对象 I-2/I-6）：`layout` 可用但 `isKnown` 返回 `false`。

**预期结果**：`{ok:false, reason:'req-missing'}`；`message` 含该 id 与「不在台账」；无副作用。
空 `reqId`（`''`）同款判 `req-missing`，且**不打接口**（`isKnown` 零调用）。

### TC-11 台账接口失败 `serves: FR-3`

**测试目标**（被测对象 I-2/I-6）：`isKnown` 抛错（模拟 8s 超时）。

**预期结果**：`{ok:false, reason:'ledger-unreachable'}`；`message` 含「无法确认需求是否可达」与失败原因；无副作用。

### TC-12 成功路径 `serves: FR-2`

**测试目标**（被测对象 I-2/I-6）：`layout` 可用 + `isKnown` 真。

**预期结果**：`{ok:true}`；`requestFocus` **恰好调用 1 次**且参数为该 id。

### TC-13 失败路径零副作用 `serves: FR-3`

**测试目标**（被测对象 I-6 第 2/3 条不变量）：三种失败原因逐一遍历。

**预期结果**：每种情形下 `requestFocus` 调用次数 = 0；`layout.selectPanel` 调用次数 = 0。

### TC-14 入口样式：作用域内 + 不被裁切可点 `serves: FR-1`

**测试目标**（被测对象 P-2）：`NODE_PANEL_CSS` 含 `.dsh-pm-np-board-entry` 规则，且不破坏
既有「每条选择器必须含 `.dsh-pm-np` / `.dsh-pm-cprog-detail-panel` / `:root`」断言。

**预期结果**：新规则选择器含 `.dsh-pm-np-board-entry`；该规则含 `flex: none`（不被压扁）与
`min-height`（可点面积）；`.dsh-pm-np-head` 仍保留 `flex-wrap: wrap`（窄面板换行不裁切）。

### TC-15 端到端（人工，:13080） `serves: FR-2, FR-3`

**测试目标**：真实页面上的三步闭环。

**测试步骤**：
1. 会话里点开流程条任一节点（含分类跳过节点）。
2. 点「项目看板 ↗」。
3. 刷新页面，再看项目看板。
4. 用不存在的 REQ 触发入口（临时改 `data-req` 或走桩）。

**预期结果**：① 入口出现、面板无「🔄 执行流程」行；② 切到项目看板并显示**该需求详情**，节点面板关闭、
会话未被切走；③ 看板回默认视图（非粘滞）；④ 仍停在会话页 + 可见失败提示（不静默、不白屏、不是列表）。

---

## 测试文件与覆盖度 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

**约定**：下表点名的测试文件，实现时须在**前 20 行**写入 `serves: FR-x` 头注释——否则验收面的
孤儿用例检查（`testFileHasServesHeader`）会点名它们（警告级，不应出现）。

| 需求条款 | 测试用例 | 实际文件 | 覆盖状态 |
|---|---|---|---|
| FR-1 | TC-1, TC-2, TC-14 | tests/node-panel.test.ts | ✅ 计划覆盖 |
| FR-4 | TC-3, TC-4 | tests/node-panel.test.ts | ✅ 计划覆盖 |
| FR-4 | TC-14 | tests/node-panel-styles.test.ts | ✅ 计划覆盖 |
| FR-5 | TC-5 | tests/node-panel.test.ts | ✅ 计划覆盖 |
| FR-2 | TC-6, TC-7, TC-8, TC-12 | tests/board-focus.test.ts | ✅ 计划覆盖（新建） |
| FR-2 | TC-7, TC-8 | tests/board-entry.test.ts | ✅ 计划覆盖（新建） |
| FR-3 | TC-9, TC-10, TC-11, TC-13 | tests/board-entry.test.ts | ✅ 计划覆盖（新建） |
| FR-2, FR-3 | TC-15 | tests/node-panel.test.ts | ⏳ 端到端（人工执行，不自动化） |

**已知需改写的既有断言**（不新增用例、只反写语义）：

| 文件 | 位置 | 现状 | 改为 |
|---|---|---|---|
| `tests/node-panel.test.ts` | TC-2（`基础信息 details open、执行流程 details 收起`） | 断言存在不带 `open` 的执行流程 `<details>` | 断言输出**不含** `🔄 执行流程`；基础信息折叠语义不变 |
| `tests/node-panel.test.ts` | TC-4（`执行流程三段`） | 断言执行流程三段齐全 | 整组删除（其守护对象已不在面板） |
| `tests/node-panel-process-map.test.ts` | — | 守护 `node-panel-process.ts` 的对照表 | **不动**（函数保留，本文件仍有效） |
