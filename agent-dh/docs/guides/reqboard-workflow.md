---
id: guide-reqboard-workflow
title: 需求看板实操（从立项到归档）
type: guide
status: living
updated: 2026-09-19
owners: [w-1cee2467]
tags: [guide, reqboard, workflow]
---

# 需求看板实操（reqboard）

**这页回答**：一个需求从冒出来到归档，具体敲哪些工具、卡在哪、错了怎么办。

## 结论先行

1. **流程即状态**：立项 → 需求分析 → 设计 → 拆分 → 实施 → 验收（人工审核）→ 归档。状态由窗口自己推；
   **人工闸门 = 四道产物确认门 + 取消**：确认需求文档（`brainstorming > design`）、批准拆分计划（`design > decomposing`）、
   确认拆分清单（`decomposing > implementing`）、验收通过（`accepting > archived`，**通过即自动归档**），
   以及取消（`* > canceled`）与取消后归档（`canceled > archived`）。
   事实源：`packages/pages/dsh-pmboard/src/domain/gate/GateCatalog.ts`（`GATE_CATALOG`）+
   `domain/requirement/RequirementStatus.ts`（`HUMAN_ONLY_REQ_TRANSITIONS`，两者由测试互锁一致）。
   ⚠️ 本节此前有两处错：把「批准拆分计划」的边记成 `decomposing → implementing`（实为 `design → decomposing`），
   且**漏了 `decomposing > implementing` 这道「确认拆分清单」**——2026-09-20 按代码更正（同文件第 31-33 行的流程表一直是正确的）。
2. **一个窗口同时只绑一个进行中需求**；立项前先想清楚"这是不是值得立项的工作"。
3. **拆分不是创作**：落库的是**已批准计划里的任务表**，不许临场发挥。
4. **验收要有证据**：交"做了什么 + 怎么验的 + 看到什么"，人在看板决定过或退。
5. **归档 = 存底 + 合并**：需求目录留过程，结论并进既有规范目录，并申报说明书更新点。

## 全流程（工具 → 人 → 产物）

| 步骤 | 谁 | 调用 | 产物 / 状态 |
|---|---|---|---|
| 立项 | 窗口 + 人 | 先 `ask_user_question` 两问（名称 / 类型）→ `reqboard_create` | 需求卡（`draft`），当前窗口随之绑定 |
| 接手 | 系统 | 窗口在该需求上继续工作时 rollup 自动推进 | `draft → brainstorming` |
| 需求分析 | 窗口 | 读代码 / 查数据，跟人把方向谈定（**不写代码**） | 需求文档（`docs/requirements/<REQ>/requirement.md`） |
| **确认需求文档** | **人** | 看板/弹框一键确认（`reqboard_ask_confirm({target: "artifact", kind: "requirement"})`） | `brainstorming → design` 解锁 |
| 设计 | 窗口 | `reqboard_move({to: "design"})` → 写设计文档（`design/*.md`）+ 拆分计划 → `reqboard_submit({kind: "plan"})` | 设计节点逐份显示设计文档「已交/未交」；卡面出现「拆分计划待批」 |
| **批准拆分计划** | **人** | 看板点「批准计划」（`POST /req/plan/approve`） | 拆分解锁 |
| 拆分 | 窗口 | `reqboard_decompose`（不传 tasks = 落库计划） | 任务卡 + 需求进 `decomposing` |
| 执行 | 窗口 | 每个任务 `reqboard_task_move`（todo→in_progress→integrating→testing→in_review→done） | 开工自动开执行段；全 done → 自动 `accepting` |
| 交验收 | 窗口 | `reqboard_submit({kind: "verification", summary, evidence})` | 验收材料入库，生成验收单（逐项待验） |
| **验收** | **人** | 看板验收单逐项勾「通过 / 改进」（`reqboard_accept_sheet`，一次最多 10 项）；点「验收通过」时先弹不合格项确认框（REQ-a8d582 FR-1） | 全通过 → `accepting → archived`（**通过即归档，无 `done` 中转**）；有未过项 → **自动回退 `implementing` 并生成返工卡**（REQ-308b9a FR-8，推翻 REQ-a8d582 FR-2）；带不合格或尚无材料的通过须显式覆盖并留痕（FR-4），按钮在验收态即展示（FR-3） |
| 补归档材料 | 窗口 | `reqboard_submit({kind: "archive", dir, docs, merged_into, index_entry, manual_updates})` | 写 `archivePath` + 归档索引（`docs/requirements/INDEX.md`）；ACCEPT→ARCHIVED 已自动完成，**无需再点归档** |

> `done` 是历史遗留状态（代码里 `done: []`——不再进入、也不允许从它转出），存量 `done` 需求按历史记录保留；新流程一律 `accepting → archived`。

## 各阶段的硬要求

- **拆分计划**：必须含**任务表**（key / title / phase / side / depends_on / acceptance）；摘要要人能读懂；拆分计划只在 `design` 阶段提交（越级报 `REQBOARD_BAD_STATUS`）。设计阶段还会逐份核对设计文档（`design/architecture.md`、`data-model.md`、`interfaces.md`、`test-cases.md`，按需求类型增减）的「已交/未交」——只展示，不作闸门。
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
| `REQBOARD_PLAN_NOT_APPROVED` | 计划没批准就拆 | 先 `reqboard_submit({kind: "plan"})` 并请人批准 |
| `REQBOARD_PLAN_MISMATCH` | 落库内容 ≠ 批准的计划 | 要改方案就重新提交计划并重新批准 |
| `REQBOARD_HUMAN_GATE` | 撞人工闸门（验收通过 / 取消 / 归档） | 请人操作，agent 不可代替 |
| `REQBOARD_TASK_NOT_FOUND` | 任务 id 不存在 | 用看板任务页确认 id |
| `invalid_transition` / `invalid_dag` / `invalid_input` / `human_gate` | 路由层同义错误 | 同上；`invalid_dag` 检查依赖是否成环 / 悬空 |

## 依据

- [RFC 014 需求看板](../rfcs/014-requirement-board.md)（状态机与闸门的设计与历次修订）；
- [需求归档规范](../architecture/requirement-archive.md)（文档合并矩阵与金字塔生长规则）；
- 2026-09-11 用户裁定：在途状态由 agent 自行推进；2026-09-13：验收通过收回为人工闸门、归档需备材料；2026-09-19：节点键 `planning` 改名 `design`（中文「设计」），旧键由台账迁移 v6→v7 一次性改写（REQ-81aabd）；2026-09-20：REQ-a8d582 —— 验收态即展示「验收通过」、点击先弹不合格项确认框、逐项裁决不再自动打回（退回由人点）、带不合格/无材料的通过须显式覆盖并写 `acceptanceOverride` 留痕；2026-09-20：REQ-308b9a —— 验收项新增 `not_verifiable`（不可验收须写原因、不阻断通过）、裁决含 failed 自动回退实施、9 类文档门 + 四段式 `verification.md`（含结果表回填）。

## 相关页面

- [需求归档规范](../architecture/requirement-archive.md) · [需求归档索引](../requirements/INDEX.md)
- [留痕与文档规范](../standards/audit-and-docs.md) · [故障排查手册](troubleshooting.md)
