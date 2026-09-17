# REQ-31e11f 会话进度流程节点可点击查看详情 — 实施计划

> 状态：待批准 · 类型：feature · 绑定窗口：w-8913546f
> 上游文档：[需求文档 requirement.md](./requirement.md)——"做什么/为什么"以它为准，本文只管"怎么做/谁做/怎么验"

## 1. 背景与问题（调查结论）

会话框顶部进度流程条（dsh-pmboard `client/conversation-progress.ts`）与项目看板（`client/view.ts`）
**走两条数据通路、两套口径**，导致"点节点没内容、内容对不上"：

| 事实 | 证据 |
|---|---|
| 看板读全量台账（plan/verification/archive/executions/dependsOn） | `GET /reqboard/state`（routes.ts handleState） |
| 进度条读窄投影：无 executions / dependsOn / verification / archive | `GET /session/:sid/progress`（routes.ts:730-799） |
| FLOW 节点止于 done，**没有归档节点** | conversation-progress.ts:22-30 |
| 阶段→任务过滤引用不存在的 phase 值（'decomposing'/'planning' 等不在 TaskPhase 枚举），点"拆分"等节点永远空白 | conversation-progress.ts:239-247 stageTasksMap |

## 2. 设计约束（用户指定，2026-09-14）

1. **DDD 分层**：domain / application / infrastructure / presentation 职责分离。
2. **模板模式**：节点详情的"骨架固定、内容可变"用 Template Method 落地，双端各一处。
3. **预留"一个项目几个需求"**：LLM 上下文有限，需求拖久了智能降级、越来越难推进——
   数据模型现在就要预留项目分组与需求谱系字段，支持将来"大需求拆成多个子需求"而不必迁移。
4. **拆分/执行尽量多窗口分担**：需求拆分与任务执行优先派给**不同窗口或 subagent**，
   分担单窗口上下文压力；分担结果必须在"实施"节点面板可见可审计。

## 3. 总体设计

### 3.1 DDD 分层落点（packages/pages/dsh-pmboard 内）

```
shared/protocol.ts      Domain：StageKey、StageDetail 判别联合（8 节点内容契约）、
                         StageDetailAssembler 模板骨架接口；Record 预留字段
host/stage-detail.ts    Application：模板基类 assemble() { header, body, timeline, actions }
                         + 8 个节点具体装配器（body 为可变步）
host/routes.ts          Infrastructure 适配：GET /requirements/:id/stage/:stage（薄层）
host/store.ts           Infrastructure：schemaVersion 3→4（可选字段，no-op 迁移）
client/stage-panel.ts   Presentation：StageRenderer 注册表（模板骨架共享面板 chrome，
                         renderBody 按节点分派）+ FLOW 补归档节点 + 点击懒加载
```

### 3.2 模板模式（双端各一处，防再脱节的机制核心）

- **host**：`StageDetailAssembler.assemble(req, tasks)` 固定骨架（节点头 + 时间线切片 +
  操作者标注），抽象步 `buildBody()` 由各节点装配器实现。
- **client**：`renderStagePanel(payload)` 固定骨架（面板头/时间线/底栏），
  `StageRenderers[stage].renderBody()` 渲染可变内容。
- 双端共享同一份 StageDetail shape（domain 层单一定义）——**看板详情抽屉与会话框
  节点面板消费同一接口同一形状**，从机制上消除两套口径，而不是靠纪律维持一致。

### 3.3 节点内容契约（8 节点）

| 节点 | body 内容 | 数据来源（已存在） |
|---|---|---|
| 立项 draft | 需求卡（标题/分类/描述）+ 立项窗口 + 时间 | RequirementRecord |
| 需求分析 brainstorming | **需求文档**（超链接打开全文）+ 共创会话 + 评论留痕 + 阶段时间线 | requirement.md 路径 + reviewSessionId/comments/statusHistory |
| 技术设计 planning | **技术设计/计划内容**（plan.md 超链接打开全文）+ 计划任务表 + 批准人/时间 | PlanRecord（+ 已有 /file 接口） |
| 拆分 decomposing | 落库任务 DAG（标题/phase/side/dependsOn/**验收标准与测试内容**）+ 与计划任务表对照 + 拆分操作者 | TaskRecord[] vs plan.tasks |
| 实施 implementing | 每任务执行记录：窗口码/subagent、manual/auto、起止、outcome、evidence；**按窗口分组** | TaskRecord.executions/claimedBy |
| 验收 accepting | 结论 + 证据清单 + 人工 pass/rework + 意见 | VerificationRecord |
| 完成 done | 里程碑时间 + 验收结论摘要 | statusHistory + verification |
| 归档 archived | 目录/文档清单/mergedInto/indexEntry/说明书更新点/归档人 | ArchiveRecord |

**文档超链接机制**：所有文档类内容渲染为可点击链接，点击经已有
`GET /reqboard/file?path=` 读取全文并弹窗展示（看板"文档记录"弹窗同款），不新造通道。

### 3.4 节点产物模型与完成闸门（用户补充，2026-09-14）

- **domain**：`StageArtifact { stage, path, kind, registeredAt, registeredBy }`；
  RequirementRecord 增加 `artifacts?: StageArtifact[]`；`STAGE_ARTIFACT_REQUIREMENTS`
  表定义每节点必备产物 kind。
- **分类流程档案 `CATEGORY_FLOW_PROFILES`**（2026-09-14 用户指定，推广
  ARCHIVE_DOC_RULES 的分类思路到全流水线）：每分类定义启用的阶段子集、必备产物、
  生效硬门——feature 全流水线 5 门；bug/refactor 免需求分析门（4 门，bug 读业务文档+
  复现定位并入修复方案产物）；spike/doc/chore 最简（2 门：验收+归档）。跳过阶段不产生物、
  不设门、不注入提示词；验收与归档门全分类保留（质量底线）。
- **登记钩子**：plan_submit→技术设计产物；decompose→拆分产物（自动生成
  decomposition.md 计划任务表↔任务 id 对照）；**reqboard_task_report（新工具，t3）
  →实施产物**（agent 结构化汇报：completed/files_changed/next_step，host 渲染落盘
  tasks/t-xxx.md；task_move→done 未汇报则产物缺失标红）；verify_submit→verification.md；
  archive_submit→归档材料（已有 ArchiveRecord）。
- **Goal 语义吸收**（合并 pmboard-complete-design.md，2026-09-14 用户确认推荐边界）：
  不建 goal.phases 平行结构——deliverables=artifacts、"已完成内容"从产物链+任务状态
  派生展示；产物登记/闸门拦截经 feishu_notify 发简版通知（复用现有通道，不建
  notify_human 框架；飞书动作按钮另立需求）。
- **闸门**：`assertReqTransition` 前置两级校验——①产物已登记（缺失 code=missing_artifact，
  提示缺哪份文档；存量需求仅标红不拦）；②**五道人工确认门**（2026-09-14 用户裁定）：
  brainstorming→planning 需需求文档人确认（新增）、planning→decomposing 计划批准（既有，
  计划文档须含 UI/前端/后端/测试用例四视角）、decomposing→implementing 拆分清单人确认
  （新增，同时从 SYSTEM_REQ_TRANSITIONS 白名单移除该转移）、accepting→done 验收清单
  （既有）、done→archived 归档方案（既有）。未确认 code=artifact_not_confirmed。
  StageArtifact 增加 confirmedAt/confirmedBy；看板新增 human-only 确认动作与「待确认」chip；
  产物登记即 feishu 通知请人审阅（一键确认+即时通知保流速，避免重回看板静止）。
- **追溯链**：产物文档头部带 REQ id + 上游产物链接；节点面板底部渲染链式 strip
  （需求→计划→拆分→实施→验收→归档）。

### 3.5 阶段提示词钩子（借鉴 superpowers hook 机制，约束 5）

动机：本会话即是反例——从首条消息直接跳到方案，缺少逐阶段深度对话。
superpowers 的答案：hooks.json 注册 SessionStart hook → 脚本把元纪律提示词以
additionalContext 强制注入；各 skill 定义该阶段 HARD-GATE 与人机回路清单。

- **不新造机制，复用两处既有注入点**：
  ①capture.ts「systemPrompt 组装按窗口条件注入」——按窗口绑定需求的当前阶段注入
  该阶段纪律提示词；②capture-hook.ts 事件 hook——需求状态转移后向绑定会话
  followup 注入「已进入 X 阶段」提示。
- **stage-prompts.ts 内容表**（插件内 TS 模块常量，与 capture.ts 字面量同风格；
  **不走 skill**——skill 是模型自主调用，纪律必须确定性注入；同仓同版本可单测）：
  brainstorming=一次一个问题/2-3 方案对比带推荐/分节逐段确认/HARD-GATE 未批准不实现/
  产出 requirement.md；planning=任务表+验收标准+提交前自查（占位/矛盾/模糊/范围）；
  implementing=按卡执行/完成即 task_report/executorHint 优先新窗口或 subagent；
  accepting=证据先行（可复核命令/路径，禁止"功能正常"）/汇总任务汇报；
  归档=按 category 核对必填文档与合并去向。
- **与产物闸门的关系**：提示词管过程纪律（怎么交流），产物闸门管结果凭证
  （有没有文档）——过程+结果双保险防跑偏。

### 3.6 预留"一个项目几个需求"（约束 3）

- `RequirementRecord` 增加可选字段：`projectId?: string`（项目分组锚点）、
  `parentId?: string`（父需求谱系，大需求拆子需求用）。可选 + schemaVersion 升 4
  no-op 迁移——**字段先就位、UI 暂忽略**，将来拆分降级流程落地时零迁移成本。
- 业务语义（后续需求实现）：需求在单窗口跑过久 → 拆成 N 个子需求分给新窗口。

### 3.7 多窗口/subagent 分担（约束 4）

- 数据锚点已具备：`executions[].sessionId`（执行窗口，w-xxx 可推导）、`trigger`
  （auto=编排派发 / manual）、`claimedBy`。subagent 会话 id（subagent-*/child-*）同理可落。
- `PlanTask` 增加可选 `executorHint?: 'fresh-window' | 'subagent' | 'current'`，
  decompose 落库透传到 TaskRecord——把"该任务该换上下文执行"的意图变成数据而非口头约定。
- "实施"节点面板**按执行窗口分组渲染**：哪个窗口/subagent 承担了哪几个任务一目了然，
  上下文分担从隐性实践变成可见事实。
- **自足任务卡契约（handoff，约束 6，借鉴 Claude Code Task 模式）**：文档链是接力棒——
  新窗口/subagent 零会话历史，仅凭产物链 + 任务卡即可开工。TaskRecord 增加可选
  `dependsSummary`（上游任务产出摘要，上游 done 时回填）；decompose 时为每任务生成
  tasks/t-xxx.md **任务卡骨架**（目标/背景/验收/范围/上游摘要/executorHint/产物链链接），
  task_report 完成时**追加**汇报到同一文档——任务文档双角色：开工说明书 + 完工记录。
- 接力流程：新窗口领取任务（task_move→in_progress 绑定 sessionId，已有）→ systemPrompt
  注入任务卡与产物链链接 → 执行 → task_report 汇报 → 下一任务由下一窗口接。
- 范围边界：编排器"自动开新窗口派发"的行为若现状缺失，列验证项；不生效则另立后续需求，
  本需求不背。

### 3.8 修复项（顺带）

- 删除 stageTasksMap（引用不存在 phase 值的错误过滤）。
- FLOW 增加 archived 节点。

## 4. 任务表（拆分粒度以此为准）

| key | 任务 | phase/side | 依赖 | 验收标准 |
|---|---|---|---|---|
| t1 | Domain 契约：StageDetail + StageArtifact（含 confirmedAt/confirmedBy）+ 闸门规则表（产物存在门+五道人工确认门）+ CATEGORY_FLOW_PROFILES 分类流程档案 + 预留字段（含 TaskRecord.dependsSummary 上游产出摘要）+ schema 升版 | implement/backend | — | 编译过；8 节点 shape + 产物 shape + 提示词映射 + 分类档案齐备；HUMAN_ONLY/SYSTEM 转移表更新（decomposing>implementing 入人工门、移出 system 白名单）；老台账加载回归单测通过 |
| t2 | host 节点详情接口（模板装配器 + 路由） | implement/backend | t1 | 8 节点 GET 均返回契约块（含产物与文档路径）；非法参数 400/404；路由单测过 |
| t3 | reqboard_task_report 任务完成汇报工具 | implement/backend | t1 | agent 提交 completed/files_changed/next_step；host 向 decompose 生成的任务卡骨架追加汇报（tasks/t-xxx.md 双角色：开工说明书+完工记录）并登记实施产物；重复汇报幂等；工具 schema 冒烟过 |
| t4 | 产物登记钩子 + 完成闸门（产物存在门+五道人工确认门）+ 阶段通知简版 | implement/backend | t1,t3 | plan/decompose/verify/archive 四处登记 + t3 汇报登记；decomposition.md/verification.md 自动落盘；decompose 同时生成每任务 tasks/t-xxx.md 自足任务卡骨架（目标/背景/范围/验收/上游摘要/executorHint/产物链链接）；缺产物 missing_artifact、五门未确认 artifact_not_confirmed 且提示待确认产物（两级校验均按 CATEGORY_FLOW_PROFILES 过滤该分类启用的阶段与门）；存量仅标记；登记/拦截发 feishu 通知请人审阅；看板 human-only 确认动作路由 |
| t5 | 阶段提示词钩子（stage-prompts.ts 插件内常量 + 双注入点接线，不走 skill） | implement/backend | t1 | 状态转移后绑定会话下一回合收到对应阶段纪律提示词；systemPrompt 组装注入按当前阶段生效；5 份提示词常量覆盖 HARD-GATE/一次一个问题/方案对比/分节确认要点；单测验证映射与触发 |
| t6 | client 节点面板（模板骨架 + 渲染器 + 产物链接 + 追溯链 + 缺产物标红 + 分类流程图） | ui/frontend | t1 | 逐节点渲染；产物/文档链接可点开；面板底部产物链；缺产物/待确认标红；流程图按分类档案渲染（跳过节点标灰"本分类跳过"）；渲染单测过 |
| t7 | 看板同源化 + 产物 chips + 五门确认入口 + 已完成内容派生展示 | implement/fullstack | t2,t4,t6 | 看板与会话框同节点同数据源；产物 ✓/✗ 与「待确认」chip 两处一致；每道门一键确认按钮（human-only）；派生展示无 goal 平行结构 |
| t8 | 测试补齐与全量回归 | test/backend | t4,t5,t7 | pmboard 全部 vitest 绿（含闸门/汇报/登记/提示词注入用例）+ plugin-schema 冒烟绿 |
| t9 | 构建部署实测与文档更新 | merge/fullstack | t8 | :13080 实测 8 节点点击有内容、产物可点开、缺产物被拦、汇报落盘、阶段提示词注入；架构文档更新 |

## 5. 整体验收标准

1. 会话框进度条 8 个节点（含归档）点击均展示该节点契约内容，与看板数据一致。
2. "实施"节点按窗口/subagent 分组展示执行记录（谁做的、怎么做、结果、证据）。
3. "验收"节点展示证据清单与人工审核结论；"归档"节点展示归档逻辑（去向+索引+说明书更新点）。
4. RequirementRecord/PlanTask 预留字段就位且向后兼容（老台账正常加载）。
5. 双端渲染共享同一契约 shape——新增节点只需改 domain + 一个装配器 + 一个渲染器。
6. 六类节点产物自动登记/落盘可查可点开；缺产物节点标红；新需求缺产物推进被代码级拦截。
7. 任一节点面板可沿产物链向上追溯到需求文档。
8. reqboard_task_report 汇报自动渲染为实施产物文档；"已完成内容"派生展示无需 goal 平行结构。
9. 阶段转移后绑定会话自动收到该阶段纪律提示词（brainstorming 含一次一个问题/方案对比/分节确认）。
10. 五道人工确认门生效：未确认转移被拒（artifact_not_confirmed）；看板一键确认后放行；产物登记即发审阅通知。
