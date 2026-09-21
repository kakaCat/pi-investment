---
req_id: REQ-c48f99
doc: design/data-model
serves: FR-2, FR-3, FR-4
status: design
---

# REQ-c48f99 设计 · 数据模型

## 1. 输入数据形态（会话事件 block）  `serves: FR-1, FR-4'

卡片不新增任何持久化数据，只读会话事件投影出的 block：

| 形态 | 字段 | 用途 |
|---|---|---|
| RunningToolCall | `argsRaw: string`（JSON 原文） | 运行中折叠行摘要 |
| ToolResultNode | `call.argsRaw`、`content: [{type:'text',text}]`、`isError`、`error.code` | 完成后摘要+展开体+错误态 |

**约束**：argsRaw 可能是流式半截 JSON——parseArgs 必须 try/catch，失败返回 undefined（FR-4）。

## 2. 中文映射表（集中 shared.ts）  `serves: FR-2`

```ts
TASK_MOVE_TO:   in_progress=开工 / testing=送测 / integrating=联调 / in_review=送审 / done=完工 / todo=退回 / canceled=取消
SUBMIT_KIND:    requirement=需求文档 / plan=拆分计划 / verification=验收材料 / archive=归档材料
AUDIT_ACTION:   record=留痕 / evaluate=评估
WATCH_ACTION:   create=新建 / enable=启用 / disable=禁用 / delete=删除
TRADE_ACTION:   BUY=买入 / SELL=卖出
```

未知枚举值兜底 = 原文显示（不新增中文猜测）。

## 3. 卡片摘要数据流  `serves: FR-2, FR-3, FR-4`

```
block
 ├─ parseArgs(argsRaw)          → 参数对象（失败 → fallbackRow）
 ├─ resultJson(content)         → 结果对象（失败 → 仅用 args 出摘要）
 └─ summarize(args, result)     → { icon, line, detailFields[] }
        错误态优先：isError → 红 icon + 结果首行
```

**不变式**：summarize 对任何输入（含 undefined/畸形）都返回可渲染结构，返回值为 null 唯一
合法含义 = 交 fallbackRow。

## 4. renderSmart 输出数据形态  `serves: FR-5`

`<摘要单行（≤120字符）>\n\n<JSON.stringify(value,null,2)>`——纯文本，content type 恒为
`text`，与现有 renderJson 消费方（GenericToolCard pre-wrap 输出区、首行摘要、errorSummary）
完全兼容，无迁移需求。
