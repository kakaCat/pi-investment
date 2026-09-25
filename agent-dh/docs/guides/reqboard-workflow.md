---
id: guide-reqboard-workflow
title: 需求看板实操（从立项到归档）
type: guide
status: living
updated: 2026-09-25
owners: [w-1cee2467]
tags: [guide, reqboard, workflow]
---

# 需求看板实操（reqboard）

**这页回答**：一个需求从冒出来到归档，具体敲哪些工具、卡在哪、错了怎么办。

## 结论先行

1. **流程即状态**：立项 → 需求分析 → 设计 → 拆分 → 实施 → 验收（人工审核）→ 归档。状态由窗口自己推；
   **人工闸门 = 四道产物确认门 + 取消**（2026-09-21 用户裁定口径）：
   确认需求文档 G1（`brainstorming > design`）、**确认设计文档 G2**（`design > decomposing`——设计阶段只写设计文档）、
   **批准拆分计划 G3**（`decomposing > implementing`——拆分计划只在拆分阶段提交，批准即自动拆分落卡并开跑）、
   验收通过 G4（`accepting > archived`，**通过即自动归档**），
   以及取消（`* > canceled`）与取消后归档（`canceled > archived`）。
   事实源：`packages/pages/dsh-pmboard/src/domain/gate/GateCatalog.ts`（`GATE_CATALOG`）+
   `domain/requirement/RequirementStatus.ts`（`HUMAN_ONLY_REQ_TRANSITIONS`，两者由测试互锁一致）。
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
| 设计 | 窗口 | `reqboard_move({to: "design"})` → 只写设计文档（`design/*.md`，落盘即产物）——**不写拆分计划、不含任务表** | 设计节点逐份显示设计文档「已交/未交」（条件必交带徽标、豁免项灰显） |
| **确认设计文档（G2）** | **人** | 看板/弹框一键确认（`reqboard_ask_confirm({target: "artifact", kind: "design"})`——一次确认 = 全部设计文档**成组落章**） | 文档集交齐且全确认 → `design → decomposing` 放行；缺交/缺确认被拦（`design_doc_incomplete`）；文档含任务表特征被拦（`design_contains_decomposition`） |
| 拆分 | 窗口 + 人 | `reqboard_submit({kind: "plan"})`（拆分阶段提交拆分计划）→ **人批准**（`reqboard_ask_confirm({target: "plan"})` 或看板「批准计划」） | 批准即自动 `reqboard_decompose` 落卡 + 进实施开跑（门合并）；任务卡 + 需求进 `decomposing → implementing` |
| 执行 | 窗口 | 每个任务 `reqboard_task_move`（todo→in_progress→integrating→testing→in_review→done） | 开工自动开执行段；全 done → 自动 `accepting` |
| 交验收 | 窗口 | `reqboard_submit({kind: "verification", summary, evidence})` | 验收材料入库，生成验收单（逐项待验） |
| **验收** | **人** | 看板验收单逐项勾「通过 / 改进」（`reqboard_accept_sheet`，一次最多 10 项）；点「验收通过」时先弹不合格项确认框（REQ-a8d582 FR-1） | 全通过 → `accepting → archived`（**通过即归档，无 `done` 中转**）；有未过项 → **自动回退 `implementing` 并生成返工卡**（REQ-308b9a FR-8，推翻 REQ-a8d582 FR-2）；带不合格或尚无材料的通过须显式覆盖并留痕（FR-4），按钮在验收态即展示（FR-3） |
| 补归档材料 | 窗口 | `reqboard_submit({kind: "archive", dir, docs, merged_into, index_entry, manual_updates})` | 写 `archivePath` + 归档索引（`docs/requirements/INDEX.md`）；ACCEPT→ARCHIVED 已自动完成，**无需再点归档** |

> `done` 是历史遗留状态（代码里 `done: []`——不再进入、也不允许从它转出），存量 `done` 需求按历史记录保留；新流程一律 `accepting → archived`。

## 各阶段的硬要求

- **设计文档集（G2 硬门，REQ-2d1c74）**：feature 必交五份（`design/architecture.md`、`data-model.md`、`interfaces.md`、`test-cases.md`、`use-cases.md`）；需求 front-matter 声明 `sides: frontend/backend` 时对应 `frontend.md`/`backend.md` 条件必交；`design_exempt: 文件名=理由` 可豁免（空理由/键名写错不生效）。未交齐或未全部经人确认 → design→decomposing 被代码级拒绝；设计文档含任务表特征（depends_on 表头等）→ 确认被拒，挪到拆分阶段。
- **拆分计划**：摘要要人能读懂；任务表（key / title / phase / side / depends_on / acceptance / implementation）可随计划提交、也可留到 `reqboard_decompose` 时创作；拆分计划只在 `decomposing` 阶段提交（越级报 `REQBOARD_BAD_STATUS`）；**人批准 = 落卡的唯一钥匙**。
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
| `design_doc_incomplete` | 设计文档集未交齐或未全部确认（G2） | 按返回的 gaps 清单补齐 design/*.md 并全部确认 |
| `design_contains_decomposition` | 设计文档里检出任务表/拆分计划特征 | 把该内容挪到拆分阶段（decomposition.md）后再确认 |
| `REQBOARD_ARTIFACT_NOT_OPENABLE` / `REQBOARD_FILE_MISSING` | 登记产物路径是伪路径/越界/没落盘 | 先落盘再登记；路径写工作区相对形态（别用 brace/..`） |
| `invalid_transition` / `invalid_dag` / `invalid_input` / `human_gate` | 路由层同义错误 | 同上；`invalid_dag` 检查依赖是否成环 / 悬空 |

## 节点提示词里的 worktree 规范与弹框超时（REQ-260923222557-d3b0）

**这节回答**：多个窗口并行时怎么不互相踩 Git，以及"等我想清楚再点确认"还会不会被超时打断。

- **worktree 规范随节点提示词下发**（只注入规范文本，不硬编码、不强制执行 git 命令——由 agent 按实际情况判断）：
  - `implementing` 节点：路由提示词里多一段 Worktree 规范——创建
    `git worktree add .worktrees/REQ-<号>/ -b feature/REQ-<号>`、子任务完成在 worktree 内 commit 一次作检查点、
    归档时合并回主线并 `git worktree remove` 清理；
  - **子任务完成**（`reqboard_task_move` → `done`）与**需求归档**（`accepting` → `archived`）两个时点走
    "事件型提示词"（`src/domain/prompt/worktree-events.ts`）：把 `{id}` / `{task_id}` / `{task_title}`
    替换后注入，前者提醒"该 commit 检查点"、后者提醒"合并并删除 worktree"；
  - 注入**尽力而为**：投递失败不阻断状态转移（故障注入用例锁定）。
- **弹框超时统一 1 小时**（2026-09-23 用户裁定）：`src/domain/limits.ts` 的 `timeoutInteractiveMs` /
  `timeoutSheetMs` 由 10 分钟 / 15 分钟改为 `3_600_000`；五个"需人弹框"工具
  （`reqboard_ask_confirm` / `reqboard_capture` / `reqboard_task_execute` / `reqboard_task_run` /
  `reqboard_accept_sheet`）全部引用该常量，无硬编码字面量。
  ⚠️ **例外**：PTC（`run_code`）模式的单次预算（默认 120000ms、上限 600000ms）**覆盖嵌套工具等待**，
  所以 PTC 窗口里弹框最多等 10 分钟——"给用户 1 小时"的前提是**原生工具调用**的窗口。
- 怎么复核：`npx vitest run tests/concurrency-limits.test.ts`（常量锁定 + 旧值扫描）、
  `npx vitest run tests/worktree-injection.test.ts`（两条事件注入路径 + 投递失败仍转移）。

## 弹框非阻塞、零参调用、断点续跑与立项降级（REQ-260924213231-b1c4）

一次实测事故（设计阶段被 G2 拦 20 分钟、弹框 120s 超时、零参调用被拒）收口出的五处工具面修复：

- **弹框超宽限不再判失败**：`reqboard_ask_confirm` 超宽限返回 `{success:true, confirmed:false, pending:true, ticket:"pc-…"}`；
  人作答后（后台落章 + 推进）用 `reqboard_confirm_receipt(ticket)` 取回执；未知/过期 ticket → `REQBOARD_UNKNOWN_TICKET`；
  未装配挂起确认端口 = 旧的阻塞语义（兼容）。**注意 PTC 窗口仍受调用方 10 分钟预算约束**（见上一节）。
- **零参工具可直接调**：`tools.reqboard_status()` 等价 `{}`。载体是根 `package.json` 的 `pnpm.patchedDependencies`
  → `patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch`（单行 `value: (args = {})`）。
- **断点可续跑**：交棒工具写 `RequirementRecord.interruption`（`reason="checkpoint"`），回合异常结束按 `turn/end`
  的真实原因补写；下一次节点输入包带「## 断点」节。**字段缺省 = 整节不渲染**，存量需求输出逐字不变。
- **立项降级路径不丢「文档位置」**：`reqboard_create` 增 `doc_location`；不传则回落 `docs/requirements/<REQ>/`
  并在返回体与台账留痕 `defaults_used`（与弹框路径对等）。
- **pm 弹框带来源标志**：pm 侧构造的问题 header 统一前缀，人**不读正文**也能分辨是不是 pm 在问；
  宿主原生 `ask_user_question` 不变。

怎么复核：`cd packages/web/dsh-pmboard && npx vitest run ask-confirm-pending zero-arg-binding interruption-checkpoint create-doc-location pm-question-badge`。

## 依据

- [RFC 014 需求看板](../rfcs/014-requirement-board.md)（状态机与闸门的设计与历次修订）；
- [需求归档规范](../architecture/requirement-archive.md)（文档合并矩阵与金字塔生长规则）；
- 2026-09-11 用户裁定：在途状态由 agent 自行推进；2026-09-13：验收通过收回为人工闸门、归档需备材料；2026-09-19：节点键 `planning` 改名 `design`（中文「设计」），旧键由台账迁移 v6→v7 一次性改写（REQ-81aabd）；2026-09-20：REQ-a8d582 —— 验收态即展示「验收通过」、点击先弹不合格项确认框、逐项裁决不再自动打回（退回由人点）、带不合格/无材料的通过须显式覆盖并写 `acceptanceOverride` 留痕；2026-09-20：REQ-308b9a —— 验收项新增 `not_verifiable`（不可验收须写原因、不阻断通过）、裁决含 failed 自动回退实施、9 类文档门 + 四段式 `verification.md`（含结果表回填）。

## 相关页面

- [需求归档规范](../architecture/requirement-archive.md) · [需求归档索引](../requirements/INDEX.md)
- [留痕与文档规范](../standards/audit-and-docs.md) · [故障排查手册](troubleshooting.md)
