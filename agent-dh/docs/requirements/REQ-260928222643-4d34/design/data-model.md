---
requirement_refs: [FR-1, FR-2, FR-3]
---

# 数据模型设计（REQ-260928222643-4d34）

> 读者：待改 `board-focus.ts` / `board-mount.ts` / `node-panel.ts` 的开发者。
> 结论先行：**台账与持久化零变更**；本需求只新增一份**内存态、一次性**的交接意图。

## T-1 持久化数据契约：无变更 `serves: FR-2, FR-3`

| 数据 | 改前 | 改后 | 说明 |
|---|---|---|---|
| 台账（`dsh-reqboard.json` / 分片 `queue.json`） | 无本需求字段 | **无新增、无修改** | 不写「谁被定位过」 |
| `REQBOARD_SCHEMA_VERSION` | 现役版本 | **不动** | 无迁移、无回填 |
| 后端路由 `/injection-log`、`/isolation-log` | 存在且被消费 | **原样保留** | FR-5 只动面板这一侧 |
| 浏览器存储（`localStorage` / `sessionStorage` / URL） | — | **不使用** | 用 storage/URL 会让定位变成粘滞状态 |

「被定位」是**一次性**状态：不落盘、不进 URL、不进 storage。刷新或再次进入看板必然回默认视图。

## T-2 新增内存态：交接意图 `serves: FR-2`

```typescript
// src/client/board-focus.ts（模块级，非 React state、非全局 window 属性）
// 语义：至多一条「待被看板消费的定位意图」；生命周期短于一次页面切换。
let pendingReqId: string | undefined
```

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `pendingReqId` | `string \| undefined` | — | 非空、`REQ-` 前缀、已 trim；`undefined` = 无意图 | 唯一字段。不存标题/阶段等可推导信息（避免两份真相） |

**为什么不存更多字段**：看板的 `mode` 只需要 `reqId`；标题、阶段、任务都由 `fetchState()` 现取。
多存一份就有漂移风险（本仓「两份真相」教训）。

## T-3 状态生命周期与不粘滞保证 `serves: FR-2, FR-3`

| 时点 | 动作 | 不变量 |
|---|---|---|
| 点击入口 | 校验通过后 `requestBoardFocus(reqId)`（校验失败**不写**） | 只有「确定能到达」的意图才入栈 |
| 看板挂载 | `takeBoardFocus()` **取走即清**，据此初始化 `mode` | 读操作即消费；同一意图不可能被消费两次 |
| 该 REQ 已不在台账 | 走看板既有回退：`mode = {kind:'board'}`（`board-mount.ts:240`） | 陈旧 id 退化为默认视图，不白屏、不报错 |
| 刷新 / 再次进入看板 | 模块内存随页面重载清空；同页内已被 take 清空 | **非粘滞**（FR-2 判定的第 3 条） |
| HMR / 面板 dispose | 不依赖 `dispose` 清理（take-once 已自清） | 无悬挂状态资源 |

**并发与竞态**：入口点击与看板挂载在同一页面、同一 JS 线程串行发生（`selectPanel` 之后宿主才
`useEffect` 挂载），不存在「两次点击覆盖一次消费」的窗口；两次连续点击 → 后写覆盖前写，
且两次都指向同一 `reqId`（同一面板同一需求），可接受。

## T-4 面板入参数据契约变更 `serves: FR-4, FR-5`

```typescript
// src/client/node-panel.ts
export interface NodePanelInput {
  overview: StageOverview
  stage: StageKey
  requirement: { id: string; title: string; promptDifficulty?: string | null; category?: string }
  injection?: InjectionInfoEntry[]   // ← 删除（FR-5：面板不再拉取，入参随之消失）
  isolation?: IsolationLogEntry[]    // ← 删除
}
```

| 变更项 | 旧行为 | 新行为 | 迁移 |
|---|---|---|---|
| `injection` / `isolation` 入参 | 面板据此渲染「🔄 执行流程」的 规定 vs 实际 对照 | 字段不存在；调用方不再传 | 无外部调用方（唯一调用点是 `conversation-progress.ts`，同批修改）；`InjectionInfoEntry`/`IsolationLogEntry` 的 import 一并删除 |

**注意**：`api.ts` 的 `fetchInjectionInfo` / `fetchIsolationLog` **不是**本次的数据契约变更对象——
它们是 API 层公开函数，看板（`board-mount.ts:721`）与其它消费方仍在用，原样保留。

## T-5 派生数据：无新增 `serves: FR-1`

本需求不新增任何派生/审计数据，故 `quantsys-v2/config/data_contracts.json` **无需登记**
（R-020 登记义务只覆盖派生/审计数据；本次无新增）。台账侧零写入意味着无新的悬空引用面。
