---
id: rfc-014-requirement-board
title: RFC 014 需求看板
summary: RFC 014：需求看板（reqboard）设计——状态机、人工闸门与归档。
type: rfc
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [reqboard, pipeline, l2]
---

# RFC 014: 需求看板（Requirement Board）——会话 ↔ 需求打通的需求流水线

- 状态：设计提案（待评审）
- 作者：investor / w-1cee2467
- 日期：2026-09-06
- 参考实现：dsh-taskboard v0.6.4（/Volumes/ORICO/doc/github/dsh-taskboard/dsh-taskboard，Apache-2.0）

## 1. 背景与目标

dsh-taskboard 已验证可行模式：平铺任务看板 + `taskboard_*` 工具 + 会话执行（agents.create + inject/followup + whenIdle 结算）+ worktree 隔离 + 会话事件总线（`session/event`）自动建卡。但它有三个结构性缺口：

1. **无需求层级**：任务平铺，无法表达"一个需求拆成多个任务、跨阶段推进"；
2. **会话归属无判断**：session-sync 是每个外部会话 1:1 无脑建卡，不判断"这个会话属于哪个已有需求/任务"，多会话并行即混乱；
3. **无流水线**：需求从提出到归档的阶段（评审/分析/实施/测试/合并/归档）与人工闸门没有模型。

**目标**：新建插件 `@pi-investment/dashboard-requirement`（代号 reqboard），实现两级模型（需求→任务）、新会话自动归属判定、需求流水线自动编排 + 人工闸门。**核心是"会话和需求模块打通"且"不混乱"**——每个会话在任意时刻有且仅有明确归属，所有归属决策可审计、可改绑。

## 2. 概念模型（三层：需求 → 任务 → 归档）

```
Requirement（需求） 1──n Task（任务） 1──n Execution（执行记录）
                        │                │
                        └── phase/dependsOn（DAG）   └── sessionId（绑定会话）
        │
        └── Archive（归档包）：需求全程产出的文档结构化归集（解决 AI 文档混乱）
```

- **Requirement**：需求文档（文档/UI 链接）、状态机、任务 DAG、需求级分支。
- **Task**：复用 taskboard 任务模型，增加 `requirementId`、`phase`、`dependsOn[]`。
- **Execution**：每次执行的会话绑定、结果、证据（提交/diff/测试输出），沿用 taskboard 结构。
- **Archive（第一层级的"归档"，用户明确为一层）**：AI 在执行全程产出的文档（需求文档、分析稿、review 报告、测试报告、交接说明、复盘）天然散落各处会话与工作区，归档层把它们按需求结构化归集，是"AI 文档混乱"的解法——见 §6a。

## 3. 需求状态机（流水线）

主链 9 态 + 终态旁路：

```
draft → reviewing → analyzing → implementing → testing → verifying → merging → done → archived
          │ 退回                                                             
          └──────── 任意非终态 → canceled（→ archived / 恢复）
```

| 状态 | 含义 | 进入方式 | 闸门 |
|---|---|---|---|
| draft | 新建（含会话自动建的"待归类"需求） | 人建 / classifier 自动建 | — |
| reviewing | 评审中 | 人「提交评审」 | — |
| analyzing | 评审通过，待拆分/拆分中 | **人工闸门：评审通过** | 仅人 |
| implementing | 任务 DAG 确认，实施阶段（并行/串行调度中） | 人工确认拆分结果（或设置自动确认） | 仅人确认 DAG |
| testing | 全部实施类任务 done → 自动进入。**= agent 验收层**：review 会话 + 单元测试任务，证据齐全才放行 | 派生：任务 rollup + **证据闸**（代码级：缺证据不可前进） | 自动+证据闸 |
| verifying | **= 人工验收层**：实际功能测试，人操作验证 | agent 验收通过后进入 | 仅人 |
| merging | 人工验收通过 → 合并代码 | 仅人 | 仅人 |
| done | 合并完成（各仓 --no-ff 合回成功） | 合并执行成功（可由人一键触发，agent 可执行合并但 done 由人确认） | 仅人 |
| archived | 文档归档（需求文档/复盘归入 docs/work-logs 等） | 人「归档」 | 仅人 |

**设计决策一：需求状态 = 派生（derive）+ 闸门（gate）混合。**
- 派生部分（implementing→testing）由任务状态 rollup 自动推进，不需人点；
- 闸门部分（评审通过、人工验收、归档确认）**代码级仅人可操作**——沿用 taskboard "验收权只属于人" 的协议闸哲学，agent 调用直接拒绝，不是提示词约定；
- `blocked` 沿用 taskboard 智慧：横向标记而非状态，任何非终态可携带。

> **2026-09-11 修订（用户裁定，v1 落地后）**：上述"在途闸门仅人"在实盘被证明是**流程停摆源**——
> 需求建卡后必须由人点「确认方案」「确认拆分」「验收通过」才能前进，实际结果是 11 条需求
> 全部停在「立项」数日无人推进。用户明确要求"agent 自己推进，不要用户手动点"。
> 因此闸门收缩为**仅终态/破坏性动作**：取消需求、归档（`*→canceled`、`*→archived`）
> 仍是人工闸门；在途步骤（评审→拆分→实施→验收→完成）由窗口 agent 经 `reqboard_move`
> 自行推进，系统另按任务事实派生推进（拆分落库→拆分态；任务开工→实施态；全部完成→验收态）。
> 人工验收仍可发生（人可随时退回/取消），但不再是流程前进的必要条件。
> 现行规则以 `shared/protocol.ts` 的 `HUMAN_ONLY_REQ_TRANSITIONS` / `SYSTEM_REQ_TRANSITIONS`
> 与 `host/rollup.ts` 为准（代码即事实）。

> **2026-09-13 修订（用户裁定，第二轮实盘反馈）**：用户指出三处「看起来有了、其实没有」：
> ①「需求没有对应的时间」——记录上只有 `createdAt/updatedAt`，评审/拆分/实施/验收/归档
> 各自发生在什么时候、每段停留多久，台账里**根本不存在**；
> ②「拆分是真拆分吗」——`decomposing` 只是一个状态名，没有任何代码把需求变成任务
> （实测台账 `tasks` 恒为 0，任务页/甘特图自然无从谈起）；
> ③「有任务页面吗、任务有甘特图吗」——没有。
> 本轮补齐（代码为准）：
> - **状态事件时间线**（`StatusEvent` + `statusHistory`，schemaVersion 3）：每次转移写入
>   `{status, at, by, reason}`；老记录在 Store 加载时由 `createdAt` + 评论留痕反推回填并标
>   `inferred=true`（UI 显式标注「回填」，不把推导值伪装成原始记录）；
> - **真拆分** `reqboard_decompose`：一次调用落库整批任务 DAG（批次内 key 引用 → 真实任务 id，
>   落库前过无环/悬空校验），需求由 rollup 自动进入拆分/实施态；
> - **任务推进** `reqboard_task_move` + 任务闸门与需求同口径：仅「取消/复活」为人工闸门，
>   正常流水线（含任务完成）由执行窗口自行推进（此前 `in_review>done` 仅人可点 → 任务卡永远停在
>   验收 → 需求永远进不了验收，看板再次静止）；
> - **任务页 + 甘特图**：任务总览页（按需求分组：里程碑条 + 甘特图 + 任务清单表）；甘特条按
>   状态分段着色、叠需求里程碑竖线、执行段真实耗时来自 `executions`。

**设计决策二：验收是二层的（用户明确）——先 agent 验收，再人工验收。**
- **第一层 agent 验收（testing 状态）**：独立 review 会话做代码 review + 单元测试任务跑测试，两者都要交出证据（review 报告 + 单测输出，写入 checklist note）。**证据闸是代码级的**：证据不齐，需求不允许从 testing 前进，agent 也无法伪造（证据要附真实命令输出）。
- **第二层人工验收（verifying 状态）**：agent 验收全过后，人做实际功能测试，点「验收通过」才进 merging。
- 两层都过才允许合并——防止"agent 自己验收自己"的单层风险，也不让人做本可由机器做的机械验收。

> **2026-09-13 修订（用户要求「需求从创建开始就有流程：brainstorming → writing-plans →
> executing-plans 的中间一部分」）**：需求状态机就是这套流程本身，**状态即阶段**——
> 原先 `reviewing`（评审）到 `decomposing`（拆分）之间缺了 writing-plans 这一段，
> 导致"方案谈定"和"开始拆卡"之间没有可见的落点，计划模式只好挂在旧状态上。
> 现行主链 8 态（泳道一条条对应，代码为准 `shared/protocol.ts`）：
>
> | 状态 | 阶段 | 对应 superpowers |
> |---|---|---|
> | `draft` | 立项 | 想法落卡 |
> | `brainstorming`（原 reviewing，旧名自动迁移） | 头脑风暴 | brainstorming |
> | `planning`（新） | 写计划 | writing-plans（计划在此提交，待人批准） |
> | `decomposing` | 拆分（落库 DAG） | 任务卡落库 |
> | `implementing` | 执行 | executing-plans |
> | `accepting` | 验收 | verification-before-completion |
> | `done` / `archived` | 完成 / 归档 | finishing-a-development-branch |
>
> - 转移表：`brainstorming → planning → decomposing`（原 `brainstorming → decomposing` 直通已移除），
>   `decomposing → planning` 可退回重写计划；
> - **计划只能在 planning 阶段提交**（越级提交返回 `REQBOARD_BAD_STATUS`）；
> - 老台账的 `reviewing` 在 Store 加载时自动迁移为 `brainstorming`（含时间线事件，迁移即真相）；
> - 「计划待批」仍是 planning 的子状态（`plan.approvedAt` 未写入），看板用卡面 chip 表达，不额外占泳道。

## 4. 任务状态机

复用 taskboard 五态（已验证）：`backlog / todo / in_progress / in_review / done` + `canceled`，转移表照抄。新增字段：

- `requirementId: string` — 所属需求（必填）
- `phase: 'doc' | 'ui' | 'analysis' | 'implement' | 'test' | 'review' | 'merge'` — 流水线阶段
- `dependsOn: string[]` — 任务 DAG 边（落库前无环校验）
- `evidence.required: string[]` — 阶段证据要求（如 test 任务必须附单测输出）

**并行/串行语义**：串行 = dependsOn 链；并行 = 同 phase 且互无依赖。调度器只派 `ready` 任务（status==todo 且所有 dependsOn 均 done），并发上限沿用 `MAX_CONCURRENT` 模式。

> **2026-09-13 修订（任务闸门与需求同口径）**：原文「agent 永远到不了 done 的代码闸」在实盘被证明与
> 需求 rollup 直接冲突——任务完成是「需求进验收」的唯一事实来源，把它锁成人操作等于让流程再次停摆。
> 现行 `HUMAN_ONLY_TASK_TRANSITIONS` 仅保留**破坏性动作**：`todo|in_progress|integrating|testing|in_review > canceled`
> 与 `canceled>todo`（复活）；任务完成（`in_review>done`）由执行窗口自行推进，且离开
> `in_progress` 时自动结算执行段（`endedAt` + outcome），甘特图与耗时统计依赖这段真实数据。

## 5. 会话归属判定（核心创新，对 taskboard 的主要增量）

触发点：`session/event` 总线的 `turn/start` + 首条 `user/message`（同 taskboard session-sync 的挂接方式）。三级判定管线：

```
turn/start(新会话)
  ├─ 0. 过滤：subagent/child 会话、reqboard 内部执行会话（sessionId 前缀）→ 永不建卡（沿用 isSubagentSession）
  ├─ 1. 已绑定：本会话已是某 Execution 的 sessionId → 跳过
  ├─ 2. 显式归属：
  │    a. 首条消息含 #REQ-xxx / #t-xxx 标记 → 直接绑定
  │    b. UI 建会话时已选需求/任务（client picker，见 §9）→ 直接绑定
  ├─ 3. 启发式匹配：首条消息 vs 全部 open 需求/任务（标题+描述+标签）打分
  │    score ≥ HIGH  → 自动绑定 + 系统评论留痕（看板可一键改绑）
  │    MID ≤ score < HIGH → 绑定为"候选"，会话标 pending_bind，看板黄条等人确认
  │    score < MID   → 新建 draft 需求（标题=首行，描述=首条消息），进"待归类"区
  └─ 4. draft 需求等人 triage：评审 or 改绑到已有需求 or 删除
```

打分算法（v1 从简，可迭代）：分词 token 重叠 + 需求标签加权 + 工作区路径一致性加分；HIGH/MID 阈值配置化。不上 LLM 判定（hook 路径要低延迟、可解释）；v2 可在"待归类"区加一键 LLM 建议归属（异步、非阻塞）。

**反混乱纪律（"这样就不会混乱"的落点）：**
1. 一个会话同一时刻只归属一个任务（强约束）；换绑 = 显式操作 + 审计留痕；
2. 归属决策全量审计：谁绑的（人/auto-classifier）、依据、分数、时间；
3. 未确认归属的会话集中在看板「待归类」区，不推进任何状态，不会乱飞；
4. 需求/任务卡片带会话 Chip 一键跳转（沿用 taskboard 0.5.4 模式）；
5. 执行会话标题强制 `[REQ-xxx] 任务标题` 前缀，会话列表肉眼可归因。

## 5b. 计划模式（Plan Mode，2026-09-13 修订后新增）

> **用户要求（原文）**：「如何拆分需要 agent 介入的 / 我希望的是 superpowers 这个 skill 的
> plan 模式版本」——拆分不能是 agent 拿到需求就自由发挥拆卡，而要走**先出计划、人批准、
> 再落库**的路径（对应 superpowers 的 brainstorming → writing-plans → executing-plans）。
>
> **设计**：闸门从"每个中间状态都要人点"（2026-09-11 之前的做法，导致流程停摆）改为
> **只在计划上闸一次**：
> - 需求进入 `reviewing` 后，窗口 agent 必须先把方案写成**实施计划**——
>   工作区计划文档（`docs/requirements/REQ-xxxxxx/plan.md`）+ 一段人能读懂的摘要 +
>   **任务表**（key/title/phase/side/depends_on/acceptance）；
> - 计划经 `reqboard_plan_submit` 提交到 ledger，泳道卡面出现「计划待批」；
> - **人在看板点「批准计划」** = 批准拆分方案本身（`POST /req/plan/approve`，
>   仅人能调；退回走 `/req/plan/reject` 且必须给理由）；
> - 未批准时 `reqboard_decompose` **代码级拒绝**（`REQBOARD_PLAN_NOT_APPROVED`）——
>   HARD GATE 与 superpowers 一致；
> - 批准后 `reqboard_decompose` 只是把批准过的任务表**落库**（传 tasks 时 key 集合必须与
>   计划一致，否则 `REQBOARD_PLAN_MISMATCH`：批了 A 不能落库 B）；
> - **重新提交计划会作废旧批准**（改过的方案不能沿用上一轮点头）。
>
> **为什么粒度写在计划里**：如果任务粒度等到落库时才由 agent 临时决定，人唯一的把关点就只剩
> 「已拆分」这个状态——看到的是结果，看不到取舍。把任务表写进计划，人批的就是拆分方案本身。
>
> **配套**：`agent-dh/skills/reqboard-plan/SKILL.md`（plan 模式 SOP：三类路径判定、
> 计划文档结构、任务 right-sizing、bite-sized 步骤、执行纪律、必须停下来问人的条件、
> 反模式清单）；绑定窗口的提示段（`capture.ts`）注入同一套纪律。

## 6. 需求拆分（Decomposition）

- 触发：**计划经人批准后**由执行窗口 agent 落库（人在看板也可点「+ 任务」手工补卡）。未经批准的计划不可拆分。
- 执行：window agent 调 `reqboard_decompose` 一次性落库整批任务 DAG（自身即 LLM，不需要 host
  另起「分析会话」）；工具负责结构正确性：批次内 `key` → 真实任务 id 映射、依赖只能是同批 key
  或本需求已有任务、落库前过 DAG 校验（无环/无悬空/无自依赖）。
- **不设确认闸门**：拆分粒度是干活的人自己的判断，落库即进拆分态（`reviewing → decomposing` 由
  rollup 自动完成）；人仍可随时取消需求或改依赖。
- 兜底：拆分失败不写库（mutator 抛错即整笔回滚，revision 不 bump），需求停在原状态，人可手工建任务——
  主流程永不因拆分失败而卡死。

> **2026-09-13 修订（用户要求「验收 有人工审核」「归档 要有项目文档设计，文档如何合并，
> 不同问题如何记录文档」）——两处均按代码级闸门落地**：
>
> - **验收人工审核**：`accepting>done` 收回为人工闸门（agent 可提交验收材料，但"过"必须人点）。
>   `reqboard_verify_submit` 提交 summary + evidence（可复核的命令/输出/路径）；
>   `POST /req/verify/pass|rework`（退回返工必须写意见，需求回 `implementing`）；
>   没有验收材料时人也不能过（证据闸）。
> - **归档 = 文档合并 + 人工拍板**：`reqboard_archive_submit` 准备
>   `{dir, docs[], mergedInto[], indexEntry}`，由 `ARCHIVE_DOC_RULES` 按需求类型校验
>   （feature→architecture/guides，bug→known-issues + retro，spike→research + retro，
>   refactor→architecture/work-logs + retro，chore→work-logs；需求目录形状亦校验）；
>   人点 `POST /req/archive` 才进 `archived`。规范与模板：
>   `agent-dh/docs/architecture/requirement-archive.md` +
>   `agent-dh/docs/requirements/_template/`。

## 6a. 归档层设计（解决 AI 文档混乱，用户明确为一层）

**问题**：AI 执行全程产出大量文档——需求文档、分析稿、review 报告、测试输出、交接说明、复盘——散落在会话记录、工作区各处，事后找不到、对不上号。

**解法：归档目录约定 + 状态机强制归集。**

1. **需求目录约定**：需求创建即开 `docs/requirements/REQ-xxx/`（工作区内），子目录固定：
   ```
   docs/requirements/REQ-xxx/
   ├── requirement.md     # 需求文档（创建/评审产出）
   ├── analysis/          # 分析稿、拆分 DAG 记录
   ├── reviews/           # agent 验收层的 review 报告
   ├── tests/             # 单测输出证据
   └── handover.md        # 交接说明 / 复盘
   ```
2. **协议强制**：工作协议（提示词 section）要求所有任务产出文档必须落进所属需求目录对应子目录；执行报告中的"产物"字段必须引用这些路径（证据闸校验路径存在）。
3. **归档动作（archived）**：人点「归档」时，插件把 `docs/requirements/REQ-xxx/` 整目录移动到 `docs/work-logs/YYYY-MM/REQ-xxx-<标题>/`（对齐本仓库文档放置规范），台账记录归档路径；看板归档视图可按月浏览、可跳转。
4. **归档清单是 done 的前置**：需求进 done 前校验归档清单（requirement.md 存在、reviews/ 非空、tests/ 非空），缺项列红，确认后才放行——文档没归集完的需求不允许"完成"。

## 7. 流水线编排（OrchestratorService）

host 侧服务，订阅 ledger 变化 + 会话事件：

1. **调度**：扫描 ready 任务 → ExecutionService 派发（照抄 taskboard：`agents.create({sessionId, meta:{cwd}, agentOptions, setup})` → `inject` 框架行 + `followup` 任务体 → `whenIdle` 结算）；并发上限共享。
2. **阶段推进**：phase rollup 自动推需求状态（implementing→testing→verifying）；到闸门停住等人。
3. **worktree 隔离**：需求级分支 `req/<REQ-id>`、任务分支 `task/<task-id>`（沿用 taskboard git face；多仓镜像模式可后续引入）；merging 阶段逐仓 `--no-ff` 合回，冲突原样报告不自动解决。
4. **测试阶段证据**：test 任务必须附单测运行输出（checklist note 证据）；review 任务由独立会话执行（可指定不同模型/preset 做代码 review）；证据缺失则 testing 不推进。
5. **启动对账**：进程重启时将 running 执行标记失败、任务退回 todo（照抄 reconcile）。

## 8. 存储

`dsh-reqboard.json`（DSH 主目录）：`{ schemaVersion, revision, requirements[], tasks[], triages[] }`。照抄 TaskStore 模式：串行写队列、原子写（temp+fsync+rename）、损坏隔离、深冻快照、订阅 → SSE。需求与任务同账本（一致性优于拆两文件，量级无压力）。

**schemaVersion 3（2026-09-13）**：需求与任务各带 `statusHistory: StatusEvent[]`（创建 + 每次转移一条）。
加载时对缺字段的老记录就地回填（`backfillRequirementHistory` / `backfillTaskHistory`，全部标
`inferred=true`），下一次写盘自然持久化——迁移不阻塞启动，也不静默改写历史语义。

## 9. 路由与 UI

- 路由：`/dashboard/api/reqboard/*` REST + SSE（与 execution 插件的 `/dashboard/api/board*` 命名空间错开）。
- client 看板：**需求泳道视图**（行=需求，列=需求状态，卡上显示任务进度 n/m + 流水线阶段条 + 创建时间/当前态停留时长）；需求详情页 = **时间线** + 任务 DAG 图 + 任务五列小看板 + **甘特图** + 评论/执行记录/证据/合并块。
- **任务页**（页头「任务」入口）：跨需求任务总览——按需求分组，每组给里程碑条 + 甘特图 + 任务清单表（id/标题/状态/阶段/端侧/依赖/创建/耗时），行可点进任务详情。
- **甘特图**：横轴时间、每行一个任务、条形**按状态分段着色**（数据源就是 `statusHistory`），叠加需求里程碑竖线与「现在」线，悬停显示某段状态的起止与时长；执行段耗时来自 `executions` 真实记录。
- 「待归类」区：pending_bind 会话 + draft 需求，确认/改绑/删除操作。
- 新会话 picker（增强，需验证 DSH client 扩展点）：在新会话对话框注入"归属需求/任务"下拉；若扩展点不可用，fallback = 看板内「绑定会话」操作 + `#REQ-xxx` 消息标记。

## 10. Agent 工具（reqboard_*）与协议

> 实际落地（2026-09-13 现状）：`reqboard_create`（创建即立项，两问弹框作答 = 立项门）/ `reqboard_status`
> （本窗口绑定 + `next_actions`）/ `reqboard_move`（需求推进）/ `reqboard_decompose`（真拆分：落库任务 DAG）/
> `reqboard_plan_submit`（计划模式：提交实施计划待人批准）/ `reqboard_decompose`（落库已批准的计划 → 任务 DAG）/
> `reqboard_task_move`（任务推进）。以下清单为原始设计意图，命名与粒度以代码为准。

- `reqboard_req_list / get / create / update / move` — move 带闸门：取消/归档 **agent 调用直接拒绝**（代码闸）。
- `reqboard_task_list / get / create / update / move / checklist / report` — 沿用 taskboard 语义，done 仅人。
- `reqboard_bind_session`（手动绑定/改绑，留痕）/ `reqboard_classify`（手动触发重判）。
- `reqboard_decompose`（触发拆分 / 确认拆分结果）。
- 系统提示词 section 注入流水线工作协议（照抄 protocol-text 模式：认领纪律、证据要求、交接时序、失败回退路径）。

### 10a. 人工确认门：双通道落章（REQ-ff20ca，2026-09-16）

五道人工确认门（`ARTIFACT_CONFIRM_GATES`）的确认动作支持**两个等效通道**：

| 通道 | 入口 | 落库字段 |
|---|---|---|
| 看板一键确认 | 需求卡按钮（`POST req/artifact/confirm`、`req/plan/approve`） | `confirmedVia/approvedVia = 'board'` |
| **会话确认** | agent 用 `ask_user_question` 请人确认 → `reqboard_confirm_artifact` 落章 | `confirmedVia/approvedVia = 'session'` + `evidence`（用户答复原文）+ `sessionId` |

**为什么需要会话通道**：回路的第一环是「人看文档 → 对话交流改进」，若确认只能在看板点，
agent 拿到用户的口头确认也无法落章（`REQBOARD_HUMAN_GATE`），回路断在最后一米。
审计不变量：`evidence` + `sessionId` 必须落库——agent 不能"自称已确认"而不留痕。

**门禁判定同步改造**：`brainstorming>planning`、`decomposing>implementing` 从
"谁调用"（仅人）改为**"产物是否已确认"**（来源不限）；未确认仍拒绝并给出两条通道提示。
取消 / 验收通过 / 归档类决定**仍只能由人操作**。agent 侧同时补上了产物闸门校验
（此前只有看板 API 有——agent 可绕过，属实现缺口）。

**补登记入口**：`reqboard_requirement_submit` 补上 brainstorming 阶段产物登记
（此前 `registerArtifact` 只在 decompose/plan_submit/verify_submit/task_report 中调用，
requirement 产物无入口 → 看板确认按钮 400 → 门永远过不去）。

## 11. 与 dsh-taskboard 的关系

- 新插件独立运行，**不依赖** taskboard；复制其验证过的模块模式（store / protocol / session-events / execution / git face），数据模型升级为两级。Apache-2.0 许可允许。
- 两插件可共存（taskboard 管散任务，reqboard 管需求流水线），但**会话自动同步必须互斥**：同开时 reqboard 分类器优先，taskboard 的 `syncExternalSessions` 须关闭（README 说明 + reqboard 启动时检测并警告）。

## 12. 里程碑（每个 M 独立可交付、可验证）

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M1 | 数据模型 + store + 协议（两级状态机/闸门/DAG 校验）+ CRUD 路由 | vitest 单测 + curl 全链路 |
| M2 | 会话归属判定管线（三级）+ 待归类区数据 + 审计 | 模拟 session 事件单测 + 实测新会话自动建 draft |
| M3 | 看板 UI（泳道/详情/DAG/绑定确认/会话跳转） | GUI 人工验收 |
| M4 | LLM 拆分 + 确认闸门 + 无环校验 | 真实需求拆分 E2E |
| M5 | 编排执行（DAG 调度 + worktree + settle + 对账） | 并行/串行混合 E2E |
| M6 | 二层验收（agent 证据闸 + 人工验收）+ 合并 + 归档目录归集动作 | 完整流水线 E2E（含归档清单前置校验） |

## 13. 风险与开放问题

1. **分类误判** → 保守阈值 + 人确认 + 可改绑 + 全审计；宁可多进"待归类"也不错绑。
2. **LLM 拆分质量** → 人确认闸门托底；拆分协议随经验迭代（经验库沉淀"拆得好/坏"案例）。
3. **双插件抢会话** → §11 互斥策略。
4. **新会话对话框 client 扩展点**是否开放未验证 → §9 fallback 保底。
5. **需求级 vs 任务级分支**合并复杂度（多任务分支先后合回需求分支再合主干）→ M5 先用任务分支直合主干 + 需求分支可选，E2E 后再定。
6. 本仓库多会话并行开发纪律：实现时必须独立 worktree（`feat/reqboard`），合回 main 前端口/IP 固定值复查。

---

## 15. 分层重构与工具收敛（REQ-47939a，2026-09-17）

**背景**：插件长到 15,413 行后暴露六类债务（单文件垄断 2,946 行 / 规则散布四处 / 用例不可复用 /
规则无法独立单测 / 客户端膨胀 / 既有资产未复用）。根因是**领域规则没有独立归属地**——只能跟着
调用者长，第一个调用者写在工具里，第二个调用者（HTTP）只好再写一遍。

**做法**：按 DDD 拆四层，依赖单向向内，并把"适配层不得含领域规则"变成**可失败的机械门禁**。

```
domain/（纯规则，零 I/O）← application/（用例，只依赖 ports.ts）← adapters/（I/O 唯一入口）
                                          ↑
                        tools/ · http/ · client/（薄适配）
```

**同期收敛**：13 个 agent 工具 → 9 个（入口数量变化，语义逐一对应）。收敛后工具面：

| 收敛后工具 | 覆盖原入口 |
|-----------|-----------|
| `reqboard_create` | create |
| `reqboard_status` | status |
| `reqboard_move` | move |
| `reqboard_decompose` | decompose |
| `reqboard_task_move` | task_move |
| `reqboard_task_report` | task_report |
| `reqboard_submit(kind=requirement\|plan\|verification\|archive)` | 四个 submit —— 壳合并、内里四个独立用例、表驱动分派 |
| `reqboard_ask_confirm` | ask_confirm + confirm_artifact |
| `reqboard_accept_sheet` | accept_sheet |

规范表述见 [各阶段职责规范](../architecture/workflow-stages.md) 的「工具面」一节；本节前的 §10 描述的是
收敛**之前**的 API，作为当时记录保留（history 只增不改）。

**四条可复用的经验**（都来自本需求的实测，不是设计推演）：

1. **门禁必须能证明自己扫到了东西**。契约扫描器一度因漏掉"条件展开字段" `...(cond ? {k} : {})`
   而假绿；层边界门禁一度只匹配 `===`，于是 `src/http/` 的 8 处 `status !== '...'` 全部漏过。
   两次都不是"没写检查"，而是"检查没看"。故所有门禁都带**命中下限自检**并与**故障注入**配套
   （注入原洞形态必须变红）。
2. **"换个花样的绕过"比不写更危险**。把 `statusIs(x, 'accepting')` 这类**通用比较器**放进 domain，
   只是搬走了运算符、规则仍留在适配层。最终口径取最粗暴的一条：**适配层不得出现任何独立的
   状态名字面量**，判定一律用按意图命名的领域函数（`isAccepting`/`isVerifiableStage`/…）。
3. **续版/派生语义要问"没被处理过的去哪了"**。验收单返工续版原只带 failed 项，pending（未裁决）
   项被静默丢弃 → 极端路径"返工后全过即可归档，而若干项从未被裁决"。凡"上一版存在但新一版不出现"
   的字段，都要确认它是"已完成"还是"被丢弃"。
4. **卡面里的"复用 X 实现"与"不依赖 X 的运行环境"可能不可兼得**。迁移脚本被要求"纯 .mjs 不依赖 tsx"
   又"复用运行时 backfill 算法"——纯 .mjs 只能重抄一份，等于造第二套时间线语义。开工前先验证
   这类组合能否同时成立，否则只剩"语义分叉"或"偷偷绕开"两条错路。

**产物索引**：需求档案 `docs/requirements/REQ-47939a/`（requirement.md · plan.md · design/ 四份 ·
decomposition.md · implementation.md · verification.md · migration-report.md）。

## 14. 执行链加固（REQ-2e9473，2026-09-17）

**背景**：REQ-6f39b5（看板详情页优化）复盘暴露七类执行链缺陷（详见 REQ-2e9473 需求文档
§1 A-G）。本节记录加固后的**行为约定**——实现见 `packages/pages/dsh-pmboard/`，
阶段语义事实源见 `docs/architecture/workflow-stages.md`。

### 14.1 确认通道（三通道原则）

关键确认（节点推进/计划批准/验收/产物确认）的落章依据必须是**系统能独立见证的用户行为**：

| 通道 | 形式 | 说明 |
|---|---|---|
| 弹框（首选） | `reqboard_ask_confirm` | 一次调用原子完成「弹框 → 落章 → 推进」；用户点肯定项即推进 |
| 看板按钮（永久兜底） | 需求卡「确认产物/批准计划/验收通过」 | agent 未发起弹框时人可主动点，永不死锁 |
| 文字确认（核验后有效） | `reqboard_confirm_artifact` | evidence 必须引用 60min 窗内真实用户消息原文（capture-hook 核验） |

- `reqboard_move` 被人门拒绝时返回**问题卡**（含可直接喂给 ask_confirm 的参数）。
- 产物登记超 30min 未确认 → capture-hook 向绑定窗口注入里程碑提醒。
- subagent/无 UI 通道时 ask_confirm 返回 `fallback=board`（降级不死锁）。

### 14.2 实施防假完成（done 凭证门）

`reqboard_task_move → done` 四重校验（代码级拒绝）：

1. **汇报前置**：必须有 `reqboard_task_report` 且 completed/files_changed 至少其一非空；
2. **真实动作**：开工以来有干活类工具痕迹，或汇报文件真实存在且 mtime 晚于开工；
3. **批量关闭节流**：同需求 60s 内已有其他任务被关闭 → 拒（`deps.doneThrottleMs` 可配）；
4. **构建新鲜度**：页面插件任务（`packages/pages/*/src/`）转 done 前要求 `lib/client.js`
   存在且新于 src 最新改动。

### 14.3 阶段产物边界（W7）

- **planning（技术设计）**：代码层面设计（改表/设计模式/框架选型/代码规范/UI/测试用例），
  产物是**一套文档**；`plan_submit` 的 tasks **可省略**（不含最终任务 DAG）。
- **decomposing（拆分）**：代码层面**新增/修改/删除**盘点 + 工作流划分/工作量预估 +
  任务卡创作（四要素：做什么/怎么做[implementation]/可证伪 acceptance/依赖）。
  计划空表时 `decompose` **必须传 tasks**（REQBOARD_TASKS_REQUIRED）。
- 任务卡质量由 `normalizePlanTasks` 强制：缺 implementation 或 acceptance 空话/缺锚点 → 拒；
  依赖按数组顺序解析，**前向引用提交时即打回**（防落库时 invalid_dag）。

### 14.4 验收单与返工回路（W6）

- `reqboard_verify_submit` 生成**逐项验收单**（VerificationSheet：每任务验收标准 + 需求级标准，
  逐项带证据）；evidence 中的工作区路径**校验真实存在**。
- `POST /dashboard/api/reqboard/req/verdicts`：人逐项裁决（passed/failed + 意见，版本匹配防并发错版）。
- 有不通过项 → 需求打回 implementing + 为每个未过项**自动生成关联返工任务**（承接原任务
  phase/side/scope + 验收意见）；修复后重交，v2 只含未过项（**断点续验**，已过项不重验）。

### 14.5 产物自动登记（W4）

- `docs/requirements/<REQ>/` **落盘即产物**：board 状态端点与 stage 详情渲染前
  `syncReqArtifacts` 扫描补登（`autoDiscovered` 标记 + mtime + size）。
- `task_report` 的 files_changed 自动上浮为需求级 `task_output` 产物。
- `archive_submit` 对目录内未列入清单的文件返回 `unlisted_files` 警告。

### 14.6 文档演进留痕（W8）

- 需求文档/计划**已确认/已批准后再重交** = 变更 → `change_note` **必填**
  （REQBOARD_CHANGELOG_REQUIRED），变更即作废旧确认/旧批准并记 changelog。
- 上游变更自动标记下游"待同步"（requirement→plan/decomposition；plan→decomposition）；
  下游重交销标；未销标时 `reqboard_move`/`verify_submit` 返回 `doc_sync_warning`。

### 14.7 回归防线

`tests/fault-injection.test.ts` 逐条复现七类事故（A-G）并断言硬门拦截；
`tests/stage-prompts.test.ts` 对阶段纪律做**措辞锁定**（防回退）。

