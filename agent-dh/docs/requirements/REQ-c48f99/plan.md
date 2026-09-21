---
req_id: REQ-c48f99
doc: plan
status: approved
date: 2026-09-21
---

# REQ-c48f99 实施计划：业务工具定制卡片 + 人话首行

**目标**：会话框业务工具节点「折叠态一眼看懂动作、展开态首行即人话」。
**做法**：①dsh-pmboard client 新增 toolviews 模块，经 tool.call.toolview keyed 插槽注册 9 张
定制卡（折叠行=中文动作摘要，展开=结构化字段，畸形兜底不白屏）；②pmboard host 侧 renderJson
升级 renderSmart（首行中文摘要 + JSON 明细），13 个工具逐配 summarize。

**全局约束**（逐条来自 requirement/design，实施未突破）：
- 只做展示层：不改工具行为、后端 API、会话事件模型；
- 不动 DSH 框架（ui-tool 包 mtime 未变，零回归由 keyed 插槽机制保证）；
- keyed 命中替换通用行 → 每卡必须自带 fallbackRow，禁止 throw/白屏（FR-4）；
- client 零新增 bare npm 依赖（自包含原则）；样式注入 <style>，不用 CSS module；
- 消息卫生棘轮：新增中文消息用 fmt()/模板字面量，禁单引号拼接；
- 构建门禁：verify-client-build WRAP_SENTINEL 必过；dist/lib 新鲜才可关任务。

## 任务表

| key | 任务 | phase | side | 依赖 | 覆盖条款 |
|---|---|---|---|---|---|
| t1 | 契约卡：toolviews 数据契约 + 纯函数 + renderSmart 签名 | implement | frontend | - | FR-1, FR-4 |
| t2 | 骨架接线：注册入口 + BizRow 布局 + task_move 示范卡 | implement | frontend | t1 | FR-1, FR-2, FR-3 |
| t3 | 其余 8 张业务卡片 | implement | frontend | t2 | FR-2, FR-3, FR-4 |
| t4 | renderSmart 人话首行：13 工具逐配 summarize | implement | backend | t1 | FR-5 |
| t5 | 迁移与兼容验证（只读验证卡） | test | fullstack | t2,t3,t4 | FR-5, FR-6 |
| t6 | 端到端实测验收（E1-E4）+ 留证 | review | fullstack | t3,t4,t5 | FR-2~FR-6 |
| t7 | 指南文档：render 人话首行约定 | doc | doc | t4 | FR-5 |

## 验收口径

E1 三连不同 to 的 task_move 折叠行两两不同含中文动作；E2 reqboard_status 展开首行中文摘要；
E3 bash/read/edit 零回归；E4 畸形 block 兜底不白屏。
