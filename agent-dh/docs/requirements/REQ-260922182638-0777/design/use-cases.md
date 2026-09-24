---
requirement_refs: FR-2, FR-4, FR-5
---

# 用例 · 统一追溯链逻辑：全链路展示中文化

> REQ-260922182638-0777 · 用户视角五区块改造后所见（对照 prototype.html 改造后列）。

## U-1 追溯链（stage-panel）`serves: FR-4, FR-5`

用户打开需求详情任一节点，追溯链显示「需求文档 → 架构文档 → 接口文档 → 拆分计划 → 任务卡 · 新增映射模块 → 任务卡 · 收敛六处引用 → 验收材料」：design 每份各占一节显示中文文档名，任务卡逐张列出带任务名称，未知 kind 显示「产物（new_proposal）」。
鼠标悬停任一节点 tooltip 仍显示完整路径（排查线索不丢）；缺必备产物时链尾红字「验收材料（缺失）」行为不变。

## U-2 文档记录区与归档清单（views/verification）`serves: FR-2, FR-4`

文档区每行 = 「种类中文名 · 文档中文名 + 真实路径列」（如「设计文档 · 架构文档  docs/.../design/architecture.md」）；未知 kind 行显示「产物（extras_review） · review.html」，图标归属不变。
归档清单的 requirement 由「需求说明」统一为「需求文档」，与其他区块逐字一致。

## U-3 产物确认 chips 与工具回执（artifacts / toolviews / render-summaries）`serves: FR-2`

泳道卡面五道确认门 chips 全中文（✓ 需求文档 / ⏳ 设计文档 / ✗ 验收材料），未知 kind chip 显示「产物（mystery_kind）」。
会话流工具卡片回执显示「提交 设计文档 · 架构文档」「提交 任务卡 · t-1a2b3c.md」，design/decomposition/task_detail 不再裸显英文枚举。
