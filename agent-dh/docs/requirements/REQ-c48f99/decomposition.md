---
req_id: REQ-c48f99
kind: decomposition
created: 2026-09-21
window: w-85447f15
---

# REQ-c48f99 拆分计划

## 改动盘点（对照 design/ 四件套）

**新增**：
- `packages/pages/dsh-pmboard/src/client/toolviews/index.ts` —— bizToolviews 注册入口（FR-1）
- `packages/pages/dsh-pmboard/src/client/toolviews/shared.ts` —— 契约纯函数 + BizRow 布局 + fallbackRow + 中文映射（FR-1/FR-2/FR-4）
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/*.ts` —— 9 张卡片（FR-2/FR-3）
- `packages/pages/dsh-pmboard/tests/toolviews.test.ts` —— 四档单测（FR-2/FR-4）
- `docs/guides/tool-render-human-summary.md` —— 人话首行约定指南（FR-5 的沉淀）

**修改**：
- `packages/pages/dsh-pmboard/src/client/index.ts` —— apply() 挂载 bizToolviews（FR-1）
- `packages/pages/dsh-pmboard/src/tools/shared.ts` —— 新增 renderSmart，renderJson 保留（FR-5）
- `packages/pages/dsh-pmboard/src/tools/*/`（13 个工具）—— render 引用逐换 renderSmart(summarize)（FR-5）
- `docs/README.md` —— 索引挂指南链接

**删除**：无。

**迁移与兼容**：renderJson 保留不删（旧调用方零影响）；定制卡片 keyed 命中才替换通用行，
未注册工具（bash/read/edit 等）走原路（FR-6）；旧会话历史节点用新渲染逻辑实时重渲染，无数据迁移。

## 任务表

见 reqboard_submit(kind=plan) 的 tasks 参数（t1 契约 → t2 骨架示范卡 → t3 其余 8 卡 / t4 renderSmart → t5 兼容验证 → t6 E2E 实测 → t7 指南文档）。
