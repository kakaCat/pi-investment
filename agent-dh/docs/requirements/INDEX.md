---
id: requirements-index
title: 需求档案索引（L3 证据档案）
type: index
status: living
updated: 2026-09-14
owners: [agent-dh]
tags: [reqboard, archive, index, l3]
---

# 需求档案索引

**这页回答**：哪些需求做过、结论是什么、合并到了哪一页。**归档时在上表追加一行**——这是"哪些需求做过、结论在哪"的唯一入口；**进行中**的需求登记在下表，归档时移上去。

## 已归档

| REQ id | 一句话结论 | 类型 | 归档日期 | 需求目录 | 合并去向 |
|---|---|---|---|---|---|
| _（暂无）_ | | | | | |

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
