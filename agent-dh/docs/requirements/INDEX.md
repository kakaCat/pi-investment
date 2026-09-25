---
id: requirements-index
title: 需求档案索引（L3 证据档案）
type: index
status: living
updated: 2026-09-25
owners: [agent-dh]
tags: [reqboard, archive, index, l3]
---

# 需求档案索引

**这页回答**：哪些需求做过、结论是什么、合并到了哪一页。**归档时在上表追加一行**——这是"哪些需求做过、结论在哪"的唯一入口；**进行中**的需求登记在下表，归档时移上去。

## 已归档

| REQ id | 一句话结论 | 类型 | 归档日期 | 需求目录 | 合并去向 |
|---|---|---|---|---|---|
| REQ-260924213231-b1c4 | 修 REQ 流水线设计阶段死锁：登记入口工具化（reqboard_submit kind=design 幂等 + 逐份登记态投影）、G2 闸门按病因分化文案并统一拒绝信封、弹框非阻塞+回执、零参调用、提示词写明登记命令、断点续跑、立项降级不丢文档位置、pm 弹框来源标志 | feature | 2026-09-25 | [REQ-260924213231-b1c4](REQ-260924213231-b1c4/) | [architecture/reqboard-design-stage.md](../architecture/reqboard-design-stage.md)、[guides/reqboard-workflow.md](../guides/reqboard-workflow.md) |
| REQ-e3b6a0 | 闸门确认后置链：五道人工闸门统一织入 H1..H5（推进→压缩→注入→唤醒→留痕）+ pm 专有立项弹框 reqboard_capture + 立项提示硬化 | feature | 2026-09-20 | [REQ-e3b6a0](REQ-e3b6a0/) | [architecture/gate-post-chain.md](../architecture/gate-post-chain.md) |
| REQ-6f39b5 | 项目看板三视图重构：详情页 4Tab+8态进度点、泳道 6 列、列表表格化；流程节点唯一事实源 workflow-stages.md | refactor | 2026-09-17 | [REQ-6f39b5](REQ-6f39b5/) | [architecture/workflow-stages.md](../architecture/workflow-stages.md) |
| REQ-283168 | 看板双视图+会话进度条因 stash 未 pop 被覆盖丢失，已从 stash 恢复入库；防回归进排查手册§E | bug | 2026-09-15 | [REQ-283168](REQ-283168/) | [guides/troubleshooting.md](../guides/troubleshooting.md) |
| REQ-31e11f | 会话框流程条 8 节点可点开看工作记录：StageDetail 契约+模板模式双端+产物闸门+追溯链+接力任务卡+markdown 弹窗；与看板同源同渲染器 | feature | 2026-09-17 | [REQ-31e11f](REQ-31e11f/) | [architecture/reqboard-stage-detail.md](../architecture/reqboard-stage-detail.md)、[README 卷 7](../README.md) |
| REQ-d3e61a | 需求→任务卡「不丢字/看得懂/验得了」：拆分覆盖门禁+统一编号串联+需求侧接收标记（文档面与看板面双红）+验收三方一致性；文档标准从纸面规范落成插件门禁（六类文档+分类文档集+RTM） | feature | 2026-09-18 | [REQ-d3e61a](REQ-d3e61a/) | [architecture/documentation-standard.md](../architecture/documentation-standard.md)、[标准化接入指引](../architecture/documentation-standard-integration-guide.md)、[README 卷 8](../README.md) |
| REQ-81aabd | 需求流水线阶段键 `planning` 全仓改名 `design`（中文「设计」），设计阶段新增四份设计文档「已交/未交」建模（只展示、不改任何闸门）；台账 schemaVersion 6→7 停机迁移 | feature | 2026-09-19 | [REQ-81aabd](REQ-81aabd/) | [architecture/workflow-stages.md](../architecture/workflow-stages.md)、[guides/reqboard-workflow.md](../guides/reqboard-workflow.md) |
| REQ-260923134706-e72f | pmboard 节点详情弹框重做成锚定式面板：点节点就地展开（无遮罩/无底栏），基础信息按节点给、「执行流程」把阶段提示词纪律与真实台账做规定 vs 实际对照（新增 isolation-log 只读端点），实施节点 DAG·泳道双视图；顺带修掉 brainstorming 模板与门禁的定义行矛盾（新增 template-clause-gate 防漂移单测） | feature | 2026-09-23 | [REQ-260923134706-e72f](REQ-260923134706-e72f/) | [architecture/reqboard-node-panel.md](../architecture/reqboard-node-panel.md)、[README 卷 7](../README.md) |
| REQ-260923222557-d3b0 | 节点提示词注入 worktree 规范（implementing 档 + 子任务完成/归档两条事件）+ 弹框超时统一 1 小时（原 10/15 分钟）+ 面板三处口径修正（设计头部取词、文档行可点/未交占位、未到达节点「未开始」） | feature | 2026-09-24 | [REQ-260923222557-d3b0](REQ-260923222557-d3b0/) | [guides/reqboard-workflow.md](../guides/reqboard-workflow.md)、[architecture/pmboard-ui-glossary.md](../architecture/pmboard-ui-glossary.md) |

## 进行中（计划已提交 / 实施中，未归档）

| REQ id | 主题 | 类型 | 档案目录 |
|---|---|---|---|
| REQ-1bb221 | 公告板「我来解决」动作路由统一到公共库（与智能执行同款） | bug | [REQ-1bb221](REQ-1bb221/) |
| REQ-24e15d | quantsys-v2 裸 SQL 全量迁 ORM | refactor | [REQ-24e15d](REQ-24e15d/) |
| REQ-6cbbf7 | 持仓看板去掉启动预取（改为打开时才加载） | bug | [REQ-6cbbf7](REQ-6cbbf7/) |
| REQ-a458a6 | 模型训练自动化治理（门控语义 / 唯一入口 / 新鲜度巡检 / 降噪） | feature | [REQ-a458a6](REQ-a458a6/) |
| REQ-c970e5 | 补齐 v2 六域打标并堵住新建任务不带 domain 的源头 | bug | [REQ-c970e5](REQ-c970e5/) |
| REQ-eeb38c | 补齐双线执行看板 v2 任务业务线分类（11 个未归类） | chore | [REQ-eeb38c](REQ-eeb38c/) |

> 进行中的需求可能由其他窗口新增（未提交前只在本机存在）；本表随归档动作同步。

## 规则

- **档案目录 `REQ-xxxxxx/`** 保留 `requirement.md / plan.md / verification.md / retro.md / notes.md`：回答「当时为什么这么做」，纳入版本控制。
- **不要求 front-matter**：需求档案是**流水证据**（L3），不是 wiki 页面；状态由需求看板管理，避免"两处真相"。它们由本页登记，因此不进 wiki 页面图、不计孤儿。
- **归档 = 存底 + 合并**（两条同时成立才算归档）：材料里写了的合并去向必须真的改到位。
- 规范：[需求归档规范](../architecture/requirement-archive.md)（上位：`docs/DOCUMENT-MANAGEMENT-PLAN.md`）。
- 模板：[`_template/`](_template/)（新需求从这里拷）。

---

## 相关页面

- [需求归档规范](../architecture/requirement-archive.md)
- [需求看板实操（从立项到归档）](../guides/reqboard-workflow.md)
- [工作日志索引](../work-logs/README.md)
- [Wiki 首页](../README.md)
