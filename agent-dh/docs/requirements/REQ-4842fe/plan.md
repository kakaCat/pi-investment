# REQ-4842fe 实施计划：任务子任务化 + 事件链自动驱动

> 本计划经人批准后方可进入拆分（reqboard_decompose）。批准同时放行原「确认拆分清单」门（两门合并，见 requirement §6.2 FR-16）。

**目标**：任务卡之下增加固定模板的子任务层；批准计划后由事件链自动驱动逐张子卡执行（每张 = 一次独立 workflow run），跑到需求进验收，全程零人工点击。
**做法**：枝干（调度/状态机/凭证/rollup）留在插件宿主代码；叶子（干活）交给已在位的 `ctx.workflowEngine`；脚本只用官方五个 hook，生成即过契约门禁。
**全局约束**（逐条来自 requirement，实施不得突破）：
- 不依赖被禁用的 `tool-workflow`；子卡执行只经 `ctx.workflowEngine`（design/architecture §3）
- 脚本只允许 `agent/parallel/pipeline/phase/log`，禁 `ctx.`、`subagent`、工具名（design/workflow-engine-contract §4）
- 存量卡（无 parentId）行为完全不变，纯加字段不 bump schemaVersion、不做存量迁移（design/data-model §7）
- domain 不得 import 运行时 `@deepseek-ai/*`；`ctx.workflowEngine` 只出现在 adapter（design/architecture §2）
- 失败不自动重试；自动链不得重开 done 卡；取消/重开/回退上游均为人工资格动作（design/data-model §6）
- TDD：每张卡先写失败测试再实现（design/test-cases.md 对应用例）

## 任务表

| key | 任务 | phase | side | 依赖 | 覆盖条款 |
|---|---|---|---|---|---|
| t1 | domain：stageKind 枚举与子卡映射表 | implement | backend | - | FR-1, FR-1b |
| t2 | domain：子卡四态状态机 + 人工门 + 需求回退转移 | implement | backend | t1 | FR-5, FR-14 |
| t3 | 数据契约扩展与迁移兼容 | implement | backend | t1 | FR-2 |
| t4 | WorkflowRunner 端口 + 引擎 adapter + 脚本契约门禁 | implement | backend | t1 | FR-4, FR-6 |
| t5 | ExecuteTask 用例：单张子卡闭环 | implement | backend | t3, t4 | FR-6 |
| t6 | 懒展开：父卡开工同事务落子卡链 | implement | backend | t3 | FR-3 |
| t7 | AdvanceChain 用例：事件链执行器 | implement | backend | t5, t6 | FR-11, FR-12 |
| t8 | 失败暂停、告警弹框与返工回上游 | implement | fullstack | t7 | FR-7, FR-13, FR-14, FR-15 |
| t9 | 并发上限与冲突两级防线 | implement | backend | t7 | FR-9, FR-10 |
| t10 | 工具面与批准计划接线（合并拆分确认门） | implement | backend | t7 | FR-8, FR-11, FR-16 |
| t11 | 看板 UI：父子卡展示与 autoRun 控制面 | ui | frontend | t6, t10 | FR-12, FR-16 |
| t12 | 端到端验收与文档更新 | test | fullstack | t8, t9, t10, t11 | FR-4, FR-11 |

## 任务细节（实施方案与可证伪验收）

### t1 domain：stageKind 枚举与子卡映射表

- 依赖：无　覆盖条款：FR-1, FR-1b
- 实施方案：新增 src/domain/task/SubtaskTemplate.ts（纯数据+纯函数，零 I/O）：StageKind 联合类型、类型→子卡集合映射表（feature/refactor/bug/doc/chore/spike/research/data/ops/review-only，未映射回退 dev→review）、validateExplicitStages（枚举/非空/去重）、buildSubtaskSpecs（含链内依赖与 acceptance 模板）。新增 tests/SubtaskTemplate.spec.ts。
- 验收（可跑）：pnpm vitest run 中 SubtaskTemplate 用例全绿：8 类映射正确、未映射回退 dev→review、非法 stages（自由文本/空/重复）分别返回明确错误

### t2 domain：子卡四态状态机 + 人工门 + 需求回退转移

- 依赖：t1　覆盖条款：FR-5, FR-14
- 实施方案：改 src/domain/task/TaskStatus.ts：新增 SUBTASK_TRANSITIONS 与 role 参数（parent/subtask/legacy），子卡禁入 integrating/testing/in_review；HUMAN_ONLY_TASK_TRANSITIONS 增 done>in_progress 与 done>canceled。改 src/domain/requirement/RequirementStatus.ts：implementing 增加 design 并列入 HUMAN_ONLY_REQ_TRANSITIONS。补单测。
- 验收（可跑）：子卡 in_progress→integrating 被拒；子卡失败 in_progress→todo 成功且 attempt+1；done→in_progress 仅人（agent 调用返回 REQBOARD_HUMAN_GATE）；implementing→design 仅人；legacy 卡转移行为不变

### t3 数据契约扩展与迁移兼容

- 依赖：t1　覆盖条款：FR-2
- 实施方案：改 src/shared/protocol.ts：TaskRecord 增 parentId/stageKind/attempt/revisions（CardRevision，append-only），RequirementRecord 增 autoRun；补 INV-1/2/3 校验（悬空 parentId、角色字段互斥、幂等展开）。
- 验收（可跑）：旧台账（无新字段）可读且看板渲染正常、行为不变；重复触发懒展开子卡数量不变；悬空 parentId 触发 INV-1 校验错误

### t4 WorkflowRunner 端口 + 引擎 adapter + 脚本契约门禁

- 依赖：t1　覆盖条款：FR-4, FR-6
- 实施方案：application/ports.ts 增 WorkflowRunner 端口；新增 adapters/WorkflowEngineRunner.ts 唯一封装 ctx.workflowEngine.start（await run.result + finally dispose，stopReason 非 completed 翻译为 ok:false）；新增子卡脚本生成器（仅 agent/phase/log）与生成后静态门禁 assertScriptContract（hook 白名单，禁 ctx./subagent/工具名）。
- 验收（可跑）：含 ctx.subagent 的脚本在生成阶段即被门禁拒绝；真实引擎冒烟：最简脚本跑通且 stopReason=completed、dispose 后无悬挂；引擎缺失时显式失败（不静默成功）

### t5 ExecuteTask 用例：单张子卡闭环

- 依赖：t3, t4　覆盖条款：FR-6
- 实施方案：新增 application/use-cases/ExecuteTask.ts：子卡 in_progress（开执行记录）→ WorkflowRunner.start → 由产出生成子卡 report（filesChanged/命令/证据）→ 子卡凭证门（report 非空、文件 mtime≥开工、stopReason=completed；保留 pages 构建新鲜度，豁免窗口活动与 60s 节流）→ 子卡 done。
- 验收（可跑）：凭证三项任一不过则子卡不 done；存在未 done 子卡时父卡不得 done；改了 packages/pages/*/src 但 lib/client.js 未更新则凭证不过

### t6 懒展开：父卡开工同事务落子卡链

- 依赖：t3　覆盖条款：FR-3
- 实施方案：改 application/use-cases/MoveTask.ts：普通卡转 in_progress 时在同一 mutate 内按映射表或显式 stages 落子卡链（首卡继承父卡 dependsOn、链内前序依赖、acceptance 模板），写留痕评论；已有子卡则幂等跳过。
- 验收（可跑）：用例 tests/LazyExpand.spec.ts 全绿：开工后查询返回完整子卡链且 stageKind 顺序与映射表一致；展开与状态变更落在同一 revision；重复开工后子卡数量不变（不产生第二套）

### t7 AdvanceChain 用例：事件链执行器

- 依赖：t5, t6　覆盖条款：FR-11, FR-12
- 实施方案：新增 application/use-cases/AdvanceChain.ts：事件类型 OPEN_PARENT/RUN_SUBTASK/FINALIZE_PARENT/ROLLUP/PAUSE；每需求单飞锁（进程内 + 台账 advance.lockAt，stale 15min 可接管）；幂等选择（状态即事实）；启动恢复扫描（autoRun=true 且非 accepting）；停滞熔断（连续 noop 达阈值→PAUSE）；事件日志写 advance-log.md 与台账。
- 验收（可跑）：重复触发同一事件为 noop 且 revision 不变；并发触发被单飞锁挡下（无双重执行）；连续 noop 达阈值触发熔断；杀进程后重启可续跑至完成；autoRun=false 后无新事件、置回 true 并触发一次即续跑

### t8 失败暂停、告警弹框与返工回上游

- 依赖：t7　覆盖条款：FR-7, FR-13, FR-14, FR-15
- 实施方案：失败分类（agent null / stopReason 非 completed / 凭证不过 / 跨卡覆盖）→ 子卡退回+attempt+1+revisions(rollback)+失败评论 → autoRun=false → **只有会话内弹框**：ask_user_question 三选处置（不发飞书、不接通知面；宿主日志仅排障）；「退回上游」走 implementing→design（人工门），重批准计划后就地更新受影响父卡（不增卡）并写 revisions(update)；补 done→in_progress 重开路径与 revisions(reopen)。
- 验收（可跑）：失败后子卡退回并留痕、autoRun=false、会话内弹框抛出（唯一交互面）、后续卡不执行；无任何自动重跑；弹框三选各自生效；退上游重批准后卡数不变且被改卡有 revisions(update)；自动链不产生 done→in_progress

### t9 并发上限与冲突两级防线

- 依赖：t7　覆盖条款：FR-9, FR-10
- 实施方案：domain/limits.ts 增 MAX_PARALLEL_PARENTS=3（可配）；MoveTask 开工校验同需求 in_progress 父卡数；decompose 增冲突拦截（互无依赖父卡 implementation 文件集合交集即拒并列出冲突文件）；运行期兜底（子卡 filesChanged 文件 mtime 落在另一在跑父卡的子卡窗口内→判跨卡覆盖失败）；子卡 dependsOn 禁跨父卡。
- 验收（可跑）：同需求第 4 张父卡开工被拒（REQBOARD_PARENT_LIMIT）；两张互不依赖父卡的链并行且都完成后 rollup 正常；跨父卡依赖被拒；拆分期重叠拒绝并列出冲突文件；构造 mtime 冲突则该子卡判失败并暂停

### t10 工具面与批准计划接线（合并拆分确认门）

- 依赖：t7　覆盖条款：FR-8, FR-11, FR-16
- 实施方案：新增 tools/AdvanceTool（reqboard_task_run，出参见 design/interfaces §1.1）并注册到 tools/index.ts、src/index.ts 与冒烟测试 PLUGINS；改造批准计划路径：批准即自动 decompose + autoRun=true + 触发首个事件，decomposing>implementing 随批准放行，更新弹框文案；TaskExecuteTool 下线或改薄壳（不得再依赖 ctx.tools.workflow）。
- 验收（可跑）：批准计划后不再调用任何人工工具即可跑到 accepting；全程不出现「确认拆分清单」弹框；批准弹框文案含自动开跑说明；新工具 schema 冒烟通过；代码中不存在 ctx.tools.workflow 调用

### t11 看板 UI：父子卡展示与 autoRun 控制面

- 依赖：t6, t10　覆盖条款：FR-12, FR-16
- 实施方案：改 src/client 渲染：父卡可折叠展开子卡（stageKind 徽标 + attempt）、需求卡进度（父卡 x/y、子卡 x/y）、自动状态徽标（运行中/已暂停/熔断/手动）、控制面（暂停/继续/终止，终止需确认）；存量卡标 [手动] 且无子卡区。
- 验收（可跑）：目视验收：父卡展开显示子卡链与进度、徽标随 autoRun 变化、暂停后无新事件、存量卡外观与现状一致（不回归）

### t12 端到端验收与文档更新

- 依赖：t8, t9, t10, t11　覆盖条款：FR-4, FR-11
- 实施方案：跑通并留证：主用例（零点击跑到 accepting）、故障注入（子卡失败暂停）、返工（退上游后就地更新）、并发（上限与并行）；写 docs/requirements/REQ-4842fe/verification.md（命令+输出摘要+日志路径）；更新 agent-dh 项目说明书相关章节（任务模型、实施流水线、workflow 引擎消费方式）。
- 验收（可跑）：pnpm vitest run 既有用例不退化；真实台账副本读取+渲染无异常；层边界门禁通过（domain 无运行时 dsh import、ctx.workflowEngine 仅在 adapter）；verification.md 含可复核证据；说明书更新点已合入

## 交付顺序说明

接口优先（t1 映射表 → t2/t3 领域与契约 → t4 端口与 adapter），再实现叶子（t5）与懒展开（t6），再接事件链（t7），然后失败与返工（t8）、并发（t9）、工具与批准接线（t10）、UI（t11），最后端到端验收（t12）。t8/t9 可并行；t11 依赖 t6 与 t10。
