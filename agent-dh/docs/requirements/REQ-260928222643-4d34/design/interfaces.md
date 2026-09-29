---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
---

# 接口设计（REQ-260928222643-4d34）

> 读者：改本包客户端的开发者。所有接口都在**浏览器侧**，无 HTTP 契约变更。
> 编号 `I-x` 供拆分与测试引用（测试用例的「被测对象」列回指这里）。

## I-1 一次性交接持有器 `board-focus.ts` `serves: FR-2`

```typescript
// src/client/board-focus.ts —— 零 import（同 page-runtime.ts 依赖纪律）

/** 登记一次「请把看板定位到该需求」的意图。空串/空白 → 视为清除（不登记）。 */
export function requestBoardFocus(reqId: string): void

/** 取走意图并立即清空（消费即清）。无意图 → undefined。 */
export function takeBoardFocus(): string | undefined

/** 清空意图（用于失败路径与测试收尾；幂等）。 */
export function clearBoardFocus(): void

/** 只读探测（不消费）——仅为单测与诊断；生产路径不得用它做判断后仍假设未被消费。 */
export function peekBoardFocus(): string | undefined
```

| 项 | 契约 |
|---|---|
| 返回 | `takeBoardFocus` 返回 `string`（`REQ-` 开头）或 `undefined` |
| 错误 | **不抛错**（无 IO、无解析）；非法输入按清除处理 |
| 幂等 | `clearBoardFocus` 幂等；连续两次 `takeBoardFocus` 第二次必为 `undefined` |
| 边界 | `requestBoardFocus('')` / 纯空白 → 清空，不登记空意图 |

## I-2 入口校验与失败提示 `board-entry.ts` `serves: FR-3`

```typescript
// src/client/board-entry.ts —— 纯函数 + 依赖注入，无 React / 无 DOM / 无直接 fetch

/** 入口失败的三种原因（互斥）。 */
export type BoardEntryFailure = 'nav-unavailable' | 'req-missing' | 'ledger-unreachable'

/** 失败原因 → 人话（纯函数，单测友好；与 board-mount.jumpResultMessage 同款约定）。 */
export function boardEntryFailureMessage(
  reason: BoardEntryFailure,
  reqId: string,
  detail?: string,
): string

export interface BoardEntryDeps {
  /** 该 REQ 是否在台账（注入 api.fetchState 的投影，便于单测） */
  isKnown(reqId: string): Promise<boolean>
  /** 登记一次性定位意图（注入 I-1 的 requestBoardFocus） */
  requestFocus(reqId: string): void
  /** 页面导航服务；undefined = 未注入（由调用方从 getPageLayout() 取） */
  layout: { selectPanel(id: string | null): void } | undefined
}

export type BoardEntryVerdict =
  | { ok: true }
  | { ok: false; reason: BoardEntryFailure; message: string }

/**
 * 校验 + 登记（**不切页**：切页由调用方在 ok=true 后执行）。
 * 顺序：① layout 可用性 → ② reqId 形状 → ③ 台账可达性 → ④ requestFocus。
 */
export function activateBoardEntry(reqId: string, deps: BoardEntryDeps): Promise<BoardEntryVerdict>
```

**返回值语义**（"先校验、后切页"的机械保证）：

| 返回 | 副作用 | 调用方该做什么 |
|---|---|---|
| `{ok:true}` | 已调用 `requestFocus(reqId)` | 关面板 + `layout.selectPanel(PANEL_ID)` |
| `{ok:false, reason, message}` | **零副作用**（未登记意图、未导航） | 把 `message` 就地显示；留在原页 |

**错误码表**：

| reason | 触发 | message（原文，含原因） |
|---|---|---|
| `nav-unavailable` | `deps.layout === undefined` | 页面导航服务不可用（layout 未注入），请刷新页面后重试 |
| `req-missing` | `reqId` 为空/非 `REQ-` 形状，或 `isKnown` 返回 false | 需求 {id} 不在台账（可能已归档或被删除），未跳转 |
| `ledger-unreachable` | `isKnown()` 抛错（含 8s 超时） | 无法确认需求是否可达（台账接口失败：{detail}），未跳转 |

**顺序契约的理由**：`layout` 检查在前 = 无网络成本、最先排除「注定跳不动」的情况；
`reqId` 形状检查在联网前 = 不拿空 id 打接口；台账检查最后 = 唯一需要 IO 的一步。

## I-3 面板入口 DOM 契约 `serves: FR-1`

`renderHead` 输出（相对时间之后追加）：

```html
<button type="button"
        class="dsh-pm-np-board-entry"
        data-action="np-board-entry"
        data-req="REQ-260928222643-4d34"
        title="打开项目看板并定位到该需求">项目看板 ↗</button>
```

| 项 | 契约 | 判定 |
|---|---|---|
| 文案 | **固定**为 `项目看板 ↗`（含尾随空格 + ↗，与需求原文逐字一致） | 输出 HTML 含该串 |
| 位置 | `.dsh-pm-np-head` 内、`.dsh-pm-np-head-time` **之后**（同排） | 同容器内出现顺序 |
| 覆盖 | 7 个节点全含（含 `enabled=false` 的「本分类跳过该节点」）——因写在共用 `renderHead` 内 | 跳过态输出同样含该串 |
| 载体 | 原生 `<button type="button">`（可键盘聚焦、非 `<a>`） | 不引入新交互库 |
| 标识 | `data-action="np-board-entry"`（走既有 document 级 click 委派） | 与 `np-switch-view`/`open-doc` 同款 |
| 数据 | `data-req` = 当前需求 id（来自`input.requirement.id`，不新拉接口） | 无网络调用即渲染 |

## I-4 面板入参契约变更 `serves: FR-4, FR-5`

见 data-model.md T-4。要点：`NodePanelInput` **删除** `injection` / `isolation`；
`renderNodePanel` 的调用方（`conversation-progress.ts`）同步停止传参。
`renderNodePanel(input): string` 的函数形状与返回类型不变（仍是纯字符串渲染，便于单测）。

## I-5 看板挂载点消费契约 `serves: FR-2`

```typescript
// src/client/board-mount.ts —— createBoardAttachment 内，mode 初始化处
const focusReqId = takeBoardFocus()                      // 每次挂载最多消费一次
let mode: ViewMode = focusReqId !== undefined
  ? { kind: 'req', reqId: focusReqId }                   // 定位到需求详情
  : { kind: 'board' }                                    // 默认：泳道/列表
```

| 项 | 契约 |
|---|---|
| 消费次数 | 每次 `attachBoard` 恰好 `takeBoardFocus()` 一次；`dispose` 不重置（清空已由 take 完成） |
| 陈旧 id | 若该 req 不在 `fetchState()` 结果里 → 走**既有**回退 `mode={kind:'board'}`（`board-mount.ts:240`），不新增分支 |
| `activeStage` | 既有的「刷新时重置为需求当前状态」逻辑（`board-mount.ts:284-289`）自动生效，无需改 |
| 不改的部分 | 视图渲染 `view.ts`、SSE、轮询、事件委派、`open-req` 等动作**逐字不动** |

## I-6 不变量（实现时不得违反） `serves: FR-2, FR-3`

1. **导航唯一来源**：切页只能经 `layout.selectPanel(...)`；不得直接操作 DOM/URL/路由。
2. **先校验后切页**：`activateBoardEntry` 返回 `ok:false` 时**零导航、零意图登记**。
3. **一次性**：交接意图只用 `takeBoardFocus` 消费；不得读第二次、不得缓存进 `state`。
4. **失败必须可见**：失败路径不得只 `console.log`（requirement：「不接受点了没反应」）。
5. **动面板不动看板**：看板既有行为（含它自己的 `fetchInjectionInfo` 消费）不得改动。

## I-7 明确不变更的接口（防顺手改） `serves: FR-4, FR-5`

| 接口 | 位置 | 处置 |
|---|---|---|
| `fetchInjectionInfo(windowKey, k)` | `src/client/api.ts:53` | **保留**（看板还用它） |
| `fetchIsolationLog(windowKey, k)` | `src/client/api.ts:68` | **保留**（后端路由与采集链路均保留） |
| `GET /dashboard/api/reqboard/injection-log` | host 侧 | **保留** |
| `GET /dashboard/api/reqboard/isolation-log` | host 侧 | **保留** |
| `renderProcessFold(payload, ctx)` | `src/client/node-panel-process.ts` | **保留函数**，仅删除唯一调用点 |
| `PANEL_ID` / `selectPanel` / `page-runtime` | `src/client/dom.ts`、`page-runtime.ts` | 只读复用，不改签名 |
