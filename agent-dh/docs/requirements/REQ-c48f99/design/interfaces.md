---
req_id: REQ-c48f99
doc: design/interfaces
serves: FR-1, FR-2, FR-3, FR-4, FR-5
status: design
---

# REQ-c48f99 设计 · 接口

## 1. toolview 注册接口（client 侧）  `serves: FR-1`

```ts
// 参照 ui-tool ask-question-toolview 模式，在 bizToolviews.apply(ctx) 中：
ctx.slots.inject('tool.call.toolview', () =>
  ctx.slots.register(
    { name: 'tool.call.toolview', key: '<工具名>', locale: 'conversation' },
    RowComponent))
```

首批 key 清单（9 个）：`reqboard_task_move` / `reqboard_submit` / `reqboard_ask_confirm` /
`reqboard_status` / `reqboard_capture` / `memory_write` / `decision_audit` /
`portfolio_trade` / `watch_manage`。

## 2. Row 组件入参契约  `serves: FR-1, FR-4`

```ts
interface ToolviewOwner {
  callId: string
  toolName: string
  block: RunningToolCall | ToolResultNode  // 运行中 { argsRaw }；已完成 { call.argsRaw, content, isError, error? }
  cwd: string
  home: string
  openFile: (path: string) => void
  loadImage: (path: string) => void
  inspect: () => void
}
```

**错误码/异常约定**：组件内部任何解析失败不得 throw——渲染层异常会中断会话框；
一律回落 fallbackRow（FR-4）。

## 3. 卡片显示契约（折叠行 / 展开体）  `serves: FR-2, FR-3`

| key | 折叠行（FR-2） | 展开体要点（FR-3） |
|---|---|---|
| reqboard_task_move | `✅ t-xxx → 完工`（icon 随 to 变，error 红） | from→to、reason、requirement_status |
| reqboard_submit | `📄 提交验收材料 · REQ-xxx` | summary、evidence 列表 |
| reqboard_ask_confirm | `🔔 请求确认设计 · 已确认并推进` / `· 未确认` | question、用户选择、feedback |
| reqboard_status | `📊 看板 · 未绑定 / N 个进行中需求` | open_requirements（id+title+status）、next_actions |
| reqboard_capture | `🌱 立项 · <需求名>` | category/difficulty、reason |
| memory_write | `🧠 记忆 · experience · <tags>` | content 全文、importance |
| decision_audit | `📝 决策留痕 · trade_buy · 600519` | reasoning、parameters |
| portfolio_trade | `💰 买入 600519 ×1000 @12.34 · 已成交` | reason、amount、order_id、status |
| watch_manage | `👁 盯盘 · 新建 · 600519 price>15` | name、condition、expires_at |

行摘要数据源优先级：结果 JSON 关键字段 > args 关键字段 > 兜底首行。

## 4. renderSmart 接口（host 侧）  `serves: FR-5`

```ts
// packages/pages/dsh-pmboard/src/tools/shared.ts
// 改前
export const renderJson = (_args, value) => [{ type:'text', text: JSON.stringify(value,null,2) }]
// 改后（新增，renderJson 保留兼容，逐工具迁移）
export const renderSmart = (summarize: (v: any) => string) => (_args: unknown, value: unknown) =>
  [{ type: 'text', text: summarize(value) + '\n\n' + JSON.stringify(value, null, 2) }]
```

13 个 pmboard 工具各配一句 summarize（如 task_move：`✅ t-xxx 开工（todo → in_progress）`）。
摘要行 ≤120 字符，必须是单行（通用卡输出区与 errorSummary 取首行）。
