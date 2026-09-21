---
req_id: REQ-c48f99
doc: reviews/self-review
status: submitted
date: 2026-09-21
---

# REQ-c48f99 自审（交付前）

## 1. 对着需求逐条自查

| 需求条款 | 落点 | 自评 |
|---|---|---|
| FR-1 定制卡片注册通道（9 工具 keyed 注册） | src/client/toolviews/index.ts（BIZ_CARDS 9 张，逐卡 try/catch） | ✅ bundle 探针 9 key 全命中 |
| FR-2 折叠行=中文动作摘要、两两可区分 | rows/*.ts summarize（行=结果 JSON>args>兜底） | ✅ 用户目检确认 + vitest「两两不同」断言 |
| FR-3 展开体=结构化字段 | CardSummary.details（from→to/reason/状态等字段对） | ✅ 用户目检可见，非裸 JSON |
| FR-4 畸形数据兜底不白屏 | shared.ts 不 throw 契约 + BizRow 双 try/catch + FallbackRow | ✅ vitest 9 例畸形→null→fallbackRow；GUI 实战未遇真实畸形 block，降级标注 |
| FR-5 renderSmart 人话首行 | src/tools/render-summaries.ts 13 函数 + 13 工具迁移 | ✅ 会话事件实证首行中文 + renderJson 引用=1 |
| FR-6 未注册工具零回归 | 未触碰 ui-tool/其他插件 | ✅ git 维度 0 改动 + 用户目检一致 |

## 2. 边界自查

- 只做展示层 ✅（无 API/事件模型改动）；不动框架 ✅；todo_write 未动 ✅（框架已有卡）。
- 降级标注两条：旧会话重渲染用户未单独目检（同管线推定）；E4 GUI 实战复核待真实畸形 block 出现。

## 3. 遗留与跟进

- 其余插件 39 处 JSON.stringify render 可按 docs/guides/tool-render-human-summary.md 逐步迁移（不在本需求范围）；
- 方案 C（框架层长 turn 折叠、todo 会话级进度面板、SUMMARY_KEYS per-tool 上游配置）另行立项。
