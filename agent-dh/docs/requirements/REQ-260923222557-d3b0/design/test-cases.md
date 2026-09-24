---
requirement_refs: [FR-1, FR-2, FR-3, FR-5, FR-8, FR-9, FR-10]
---

# 测试用例（REQ-260923222557-d3b0）

## 测试策略 <!-- serves: FR-8, FR-9, FR-10 -->

渲染修正以 vitest 单测为硬门（锚点 `tests/stage-panel.test.ts` 及 node-panel 用例）；提示词文本走既有 fragments 快照/基线测试（tests/fixtures/stage-prompts-baseline-*.json，新增文本须更新基线）；超时改值后全量回归 + 线上抽样。

## 用例表 <!-- serves: FR-8, FR-9, FR-10 -->

| 编号 | 被测对象（设计锚点） | 输入 | 期望 |
|---|---|---|---|
| TC-1 | interfaces.md#stageHeadSummary | design 节点、无 plan、designDocs 2/5 已交 | 返回「设计文档 2/5 已交」 |
| TC-2 | interfaces.md#stageHeadSummary | design 节点、有 plan（旧管线） | 返回计划类旧文案（兼容） |
| TC-3 | interfaces.md#stageHeadSummary | designDocs 交齐且已确认 | 返回「设计已确认」 |
| TC-4 | interfaces.md#renderHead | stageRowState=pending（预览未到达节点） | 状态词「未开始」，不出现「已拆分」 |
| TC-5 | interfaces.md#renderHead | state=current/done | 取词与改前一致 |
| TC-6 | interfaces.md#renderDesignInfo | submitted=true 行 | 渲染为 docItem（含 data-action=open-doc） |
| TC-7 | interfaces.md#renderDecomposingInfo | 无 decompositionDoc | 出现「⬜ 拆分计划：decomposition.md（未交）」占位行 |
| TC-8 | data-model.md#数值契约 | grep LIMITS 消费方 | 无 600_000/900_000 硬编码残留；两常量=3_600_000 |

## 线上验收（E2E） <!-- serves: FR-1, FR-5 -->

1. 本需求确认设计进 decomposing 时弹框：>10 分钟不超时（旧值 600s 已过）即证明 FR-5 生效。
2. 进 implementing 后 agent 会话可见 worktree 创建提示（self_system_prompt 可查）。
3. 构建门禁：`pnpm build:client` + verify-client-build 通过；`npx vitest run`（pmboard）全绿。
