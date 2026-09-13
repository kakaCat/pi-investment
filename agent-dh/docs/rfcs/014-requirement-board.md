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
