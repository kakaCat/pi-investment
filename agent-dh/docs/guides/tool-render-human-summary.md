---
title: 工具 render 人话首行约定（renderSmart）
created: 2026-09-21
req: REQ-c48f99
---

# 工具 render 人话首行约定（renderSmart）

> 解决的问题：业务工具在会话框回落 GenericToolCard 时，输出区是裸 JSON 文本墙
> （审计：docs/work-logs/2026-09/session-node-display-audit.md）。GenericToolCard 的
> 输出区与错误摘要都**取渲染文本首行**——首行写人话，零框架改动即可读。

## 约定

工具的 `output.render` 返回文本必须是：

```
<人话摘要：单行，≤120 字符，禁止以 { 或 [ 开头>

<空行>

<JSON 明细（JSON.stringify(value, null, 2)）>
```

## 用法（pmboard 已落地）

```ts
// packages/pages/dsh-pmboard/src/tools/shared.ts
import { renderSmart } from '../shared.js'
import { statusSummary } from '../render-summaries.js'

// 改前：render: renderJson
// 改后：
render: renderSmart(statusSummary),
```

summarize 契约（见 `src/tools/render-summaries.ts`）：

1. **单行**：多行会被首行语义截断（renderSmart 内部再截一次兜底，但作者须保证语义在行首）；
2. **≤120 字符**：超出由 renderSmart 截断；
3. **不 throw**：输入可能是字符串错误值/畸形对象，失败时降级为 `❌ + 首行原因`；
4. **禁以 `{`/`[` 开头**：JSON 明细放摘要之后，由空行分隔；
5. 消息拼接遵守消息卫生门禁（棘轮，tests/message-hygiene.test.ts）：多变量消息用
   `fmt()`，单变量后缀可用模板字面量——禁止 `'中文' + 变量` 单引号拼接。

## 效果

- 展开体：首行即摘要，JSON 明细在下（pre-wrap 滚动区）；
- 错误行：errorSummary 自动取首行 → 错误提示直接可读；
- 与定制卡片（tool.call.toolview keyed 注册）正交：未注册卡片的工具也立即受益。

## 跟进范围

pmboard 13 个工具已完成（REQ-c48f99 t4）。其余插件（investment/trading/intelligence 等）
39 处 `JSON.stringify` render 可按本约定逐步迁移——每次只改一个工具，跑
`npx vitest run tests/plugin-schema.smoke.test.ts`（agent-dh 根）与包内测试后重启验证。
