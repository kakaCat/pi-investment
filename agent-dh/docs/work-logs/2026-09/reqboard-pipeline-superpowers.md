---
id: wl-2026-09-reqboard-pipeline-superpowers
title: 项目看板：需求流水线对齐 superpowers 三段式（状态即阶段）
type: worklog
status: archived
updated: 2026-09-13
owners: [w-1cee2467]
tags: [worklog, 2026-09]
---

# 项目看板：需求流水线对齐 superpowers 三段式（状态即阶段）

- **日期**：2026-09-13
- **窗口**：w-1cee2467
- **分支**：feat/reqboard-flow → main
- **用户要求（原文）**：「我希望的需求从创建开始就有流程，brainstorming → writing-plans → executing-plans 的中间的一部分」

## 问题

上一轮加了「计划模式」，但它是挂在旧状态机上的补丁：`reviewing`（评审）之后直接跳 `decomposing`（拆分），
**writing-plans 这一段在流程里没有落点**——需求从创建到交付，中间少了一格，人看不出"现在走到哪了"。

## 改动：需求主链 8 态

| 状态 | 阶段 | 谁推进 |
|---|---|---|
| `draft` | 立项 | 人（两问弹框 / 看板建卡） |
| `brainstorming`（原 `reviewing`） | 头脑风暴 | 窗口接手自动进入；窗口自行推进 |
| `planning`（**新增**） | 写计划 | 窗口 `reqboard_move` → planning，再提交计划 |
| `decomposing` | 拆分（落库 DAG） | 计划获批后 `reqboard_decompose` → rollup 自动 |
| `implementing` | 执行 | 任务开工自动进入；`reqboard_task_move` 逐项 |
| `accepting` | 验收 | 任务全 done 自动进入 |
| `done` / `archived` | 完成 / 归档 | 窗口自报完成；归档仅人 |

- 转移表新增 `brainstorming→planning`、`planning→decomposing`、`decomposing→planning`（退回重写计划）；
- **越级被拒**：计划只允许在 `planning` 提交（`REQBOARD_BAD_STATUS`）；拆分仍要求计划已批准（`REQBOARD_PLAN_NOT_APPROVED`）；
- rollup R3 规则改为 `planning + 任务存在 → decomposing`（任务能落库 ⇔ 计划已获人批准）；
- **旧名迁移**：`LEGACY_REQ_STATUS_ALIASES` 把老台账的 `reviewing`（含时间线事件）在 Store 加载时迁到 `brainstorming`——迁移即真相，不改语义只改名；
- 看板泳道 7 列（立项/头脑风暴/写计划/拆分/执行/验收/完成），阶段标签换成 superpowers 词汇（评审→头脑风暴、实施→执行）；
- 卡片动作跟着阶段走：开始头脑风暴 → 写计划 → 落库拆分 → 开始执行 → 提交验收 → 验收通过 → 归档；
- 绑定窗口提示段（`capture.ts`）与 skill（`agent-dh/skills/reqboard-plan`）同步：流水线表 + "别越级"铁律。

## 验证

- **单测 167 passed / 13 files**（状态机/转移/闸门/rollup/路由/计划模式/客户端渲染全量更新为新流程）。
- 类型检查：与 main 基线逐条比对，唯一差异仍是 `Cannot find name 'window'` 这一类既有噪声（11 → 16 处）。
- client 产物重建：`lib/client.js` 59022 bytes（含 头脑风暴 / 写计划 / planning 泳道）。
- 迁移：Store 加载即把 `reviewing` 映射为 `brainstorming`（含 statusHistory），下次写盘持久化。

## 生效方式

- client 半（泳道/标签/卡面动作）→ 刷新页面。
- host 半（新状态、迁移、闸门）→ 重启 13080。
