---
requirement_refs: [FR-5, FR-6, FR-7]
---

# 数据模型（REQ-260923222557-d3b0）

## TL;DR <!-- serves: FR-5 -->

**无数据模型变更**：不改台账 schema、不改 StageDetail/StageOverview 契约、不新增表。变更仅是数值常量与文本资产。

## 数值契约变更 <!-- serves: FR-5, FR-6, FR-7 -->

| 字段 | 类型 | 约束 | 变更 |
|---|---|---|---|
| `LIMITS.timeoutInteractiveMs` | number(ms) | >0，交互类工具弹框等待上限 | 600_000 → 3_600_000 |
| `LIMITS.timeoutSheetMs` | number(ms) | >0，验收单分批弹框等待上限 | 900_000 → 3_600_000 |

消费方（全部读常量、无硬编码，grep 可证）：AskConfirmTool / CaptureTool / TaskExecuteTool / AdvanceTool / AcceptSheetTool。非 reqboard 工具超时不受影响（边界）。

## 文本资产 <!-- serves: FR-1, FR-2, FR-3 -->

三份 worktree 提示词为**文本即数据**：fragments 源文件入仓，`generated/fragments.ts` 由构建脚本（scripts/inline-prompt-fragments.mjs）再生成，禁止手改生成物。

## 渲染层无持久化变更 <!-- serves: FR-8, FR-9, FR-10 -->

FR-8/9/10 只改 client 渲染函数，不触碰台账读写路径；面板展示的「未开始/占位行」均为渲染期派生，不落库。
