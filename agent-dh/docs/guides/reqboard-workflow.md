---
id: guide-reqboard-workflow
title: 需求看板实操（从立项到归档）
type: guide
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [guide, reqboard, workflow]
---

# 需求看板实操（reqboard）

**这页回答**：一个需求从冒出来到归档，具体敲哪些工具、卡在哪、错了怎么办。

## 结论先行

1. **流程即状态**：立项 → 头脑风暴 → 写计划 → 拆分 → 执行 → 验收（人工审核）→ 完成 → 归档。状态由窗口自己推，**只有四处需要人**：批准计划、验收通过、归档、取消。
2. **一个窗口同时只绑一个进行中需求**；立项前先想清楚"这是不是值得立项的工作"。
3. **拆分不是创作**：落库的是**已批准计划里的任务表**，不许临场发挥。
4. **验收要有证据**：交"做了什么 + 怎么验的 + 看到什么"，人在看板决定过或退。
5. **归档 = 存底 + 合并**：需求目录留过程，结论并进既有规范目录，并申报说明书更新点。

## 全流程（工具 → 人 → 产物）

| 步骤 | 谁 | 调用 | 产物 / 状态 |
|---|---|---|---|
| 立项 | 窗口 + 人 | 先 `ask_user_question` 两问（名称 / 类型）→ `reqboard_create` | 需求卡（`draft`），当前窗口随之绑定 |
| 接手 | 系统 | 窗口在该需求上继续工作时 rollup 自动推进 | `draft → brainstorming` |
| 探索 | 窗口 | 读代码 / 查数据，跟人把方向谈定（**不写代码**） | 方案共识 |
| 写计划 | 窗口 | `reqboard_move({to: "planning"})` → 写计划文档 → `reqboard_plan_submit` | 泳道卡面出现「计划待批」 |
| **批准** | **人** | 看板点「批准计划」（`POST /req/plan/approve`） | 拆分解锁 |
| 拆分 | 窗口 | `reqboard_decompose`（不传 tasks = 落库计划） | 任务卡 + 需求进 `decomposing` |
| 执行 | 窗口 | 每个任务 `reqboard_task_move`（todo→in_progress→testing→in_review→done） | 开工自动开执行段；全 done → 自动 `accepting` |
| 交验收 | 窗口 | `reqboard_verify_submit({summary, evidence})` | 验收材料入库，等人审核 |
| **验收** | **人** | 看板「验收通过」/「退回返工」（`/req/verify/pass` 或 `/req/verify/rework`） | `accepting → done`，或退回 `implementing` 返工 |
| 备归档 | 窗口 | `reqboard_archive_submit({dir, docs, merged_into, index_entry, manual_updates})` | 归档材料入库 |
| **归档** | **人** | 看板「归档」（`POST /req/archive`） | `done → archived`，写 `archivePath` 与归档索引 |

## 各阶段的硬要求

- **计划**：必须含**任务表**（key / title / phase / side / depends_on / acceptance）；摘要要人能读懂；计划只在 `planning` 阶段提交（越级报 `REQBOARD_BAD_STATUS`）。
- **拆分**：落库内容只能等于批准的计划——key 集合不一致报 `REQBOARD_PLAN_MISMATCH`（防止"批了 A 落库 B"）。
- **任务**：依赖只能指向同需求内任务；`todo → done` 是非法跳步；开工记一段执行时间（甘特图与耗时统计的数据源）。
- **验收材料**：evidence 必须可复核（命令 + 输出摘要 / 报告路径 / 截图路径），禁止"功能正常"这类空话。
- **归档材料**：需求目录须形如 `docs/requirements/REQ-xxxxxx`（或 `agent-dh/docs/requirements/...`）；必填文档与合并去向按需求类型限定——feature → architecture|guides；bug → guides|architecture；refactor → adr|architecture；spike → rfcs|architecture|strategy-research；doc → docs/；chore → work-logs；**feature / refactor / spike 必须申报 `manual_updates`**（改了哪份文档的哪一节）。

## 常见错误码与处置

| 错误码 | 含义 | 怎么办 |
|---|---|---|
| `REQBOARD_NO_BOUND_REQ` | 本窗口没有绑定需求 | 先立项（或确认在正确的窗口里做） |
| `REQBOARD_NOT_BOUND_TO_WINDOW` | 想动的是别的窗口的需求 | 只推自己的需求；跨窗口先交接 |
| `REQBOARD_WINDOW_BOUND` | 本窗口已有进行中需求 | 先推进 / 归档旧的，再立新的 |
| `REQBOARD_BAD_STATUS` | 当前状态不允许该动作 | 照提示"先 reqboard_move 到 X" |
| `REQBOARD_PLAN_NOT_APPROVED` | 计划没批准就拆 | 先 `reqboard_plan_submit` 并请人批准 |
| `REQBOARD_PLAN_MISMATCH` | 落库内容 ≠ 批准的计划 | 要改方案就重新提交计划并重新批准 |
| `REQBOARD_HUMAN_GATE` | 撞人工闸门（验收通过 / 取消 / 归档） | 请人操作，agent 不可代替 |
| `REQBOARD_TASK_NOT_FOUND` | 任务 id 不存在 | 用看板任务页确认 id |
| `invalid_transition` / `invalid_dag` / `invalid_input` / `human_gate` | 路由层同义错误 | 同上；`invalid_dag` 检查依赖是否成环 / 悬空 |

## 依据

- [RFC 014 需求看板](../rfcs/014-requirement-board.md)（状态机与闸门的设计与历次修订）；
- [需求归档规范](../architecture/requirement-archive.md)（文档合并矩阵与金字塔生长规则）；
- 2026-09-11 用户裁定：在途状态由 agent 自行推进；2026-09-13：验收通过收回为人工闸门、归档需备材料。

## 相关页面

- [需求归档规范](../architecture/requirement-archive.md) · [需求归档索引](../requirements/INDEX.md)
- [留痕与文档规范](../standards/audit-and-docs.md) · [故障排查手册](troubleshooting.md)
