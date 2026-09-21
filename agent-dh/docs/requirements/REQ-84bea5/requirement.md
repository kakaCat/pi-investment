---
req: REQ-84bea5
title: 修复：需求流水线「批准计划→自动开跑」断链（实施阶段未走 workflow 自动链）
category: feature
status: brainstorming
created: 2026-09-21
window: w-8375f8a6
---

# REQ-84bea5 修复「批准计划→自动开跑」断链

## 1. 背景与证据（实测定位）

用户在 REQ-2d1c74 实施阶段发现「没有用 workflow 的功能」。实测确认：该需求全程 0 次
`reqboard_task_run`/`reqboard_task_execute`，46 次 `reqboard_task_move` 手工推进；台账无
autoRun、无子卡、无 advance 历史。放大到全看板：53 需求 / 248 任务 / 241 条执行记录，
autoRun 全缺省、子卡 0 张——**自动链（REQ-4842fe）交付后从未真正跑起来过**。

### 1.1 断链根因（逐层坐实）

批准计划弹框返回原文（REQ-2d1c74 会话实录）：

> 自动拆分/开跑失败（计划已批准，可手动调 reqboard_decompose 重试）：reqboard_decompose
> 未执行：以下需求条款既没有被任何任务卡接收、也没有标「本轮不做」——FR-1~FR-6。
> （requirement_uncovered）

1. **事实源错配（根因）**：覆盖门禁（`Decompose.ts:183` →
   `content-gate-wiring.ts:85`）只从任务对象上读 `requirement_refs`；而
   ①`reqboard_submit(kind=plan)` 的 tasks schema 没有该字段且
   `additionalProperties:false`（`SubmitTool.ts:48-64`）；
   ②`normalizePlanTasks`（`protocol.ts:691-732`）按白名单规整会静默丢弃未知字段——
   **plan.tasks 对象结构上不可能携带 refs**，凡需求文档带 FR 编号，批准后自动拆分必然被拦。
2. **与设计意图自相矛盾**：`Decompose.ts:168` 注释明写「任务↔需求编号的绑定不落库，
   随 decomposition.md 的 RTM 覆盖表持久化——它本就是规范里的 RTM 核心」；提交侧
   （`collectTaskRefs`→`taskRefsFromDecomposition`）读的正是这份 RTM。**提交认文档、
   拆分认对象**，两个口径不一致。
3. **失败静默降级**：`AskConfirm.ts:295-299` 的 catch 把开跑失败吞成一句返回 note——
   无系统评论、无告警、autoRun 不置位；需求以「手动」徽标进实施，看板控制面
   （`renderAutoControls` 仅在 autoRun 有值时渲染）**完全不出现**，人事后既看不到失败、
   也没有入口重新开跑。
4. **既有测试没抓住**：`tests/auto-chain-approval.test.ts` 的种子需求没有 requirement.md
   （`docs.exists` 短路），覆盖门禁根本不执行——绿灯是假通过（与基因组「契约测试脱节」
   教训同款）。

### 1.2 同源残留：plan.md 验收门禁（用户 2026-09-21 弹框确认并入）

2026-09-21「拆分计划挪到拆分阶段」裁定后，最新流程不再生成 plan.md（实测
`docs/requirements/REQ-2d1c74/` 只有 decomposition.md；裁定前的 REQ-c48f99 等 34 个
目录留有 plan.md）。但验收 9 类文档清单（`DocCompleteness.ts:37`）仍把
`plan.md（拆分计划）` 列为必交，`SubmitVerification.ts:107-112` 缺了即
REQBOARD_DOC_INCOMPLETE 硬拒——**REQ-2d1c74 走到验收提交必被卡**（第 2 类与第 7 类
decomposition.md 重复，属裁定迁移未清干净的残留）。

### 1.3 用户已确认的决策点（2026-09-21，本会话弹框）

1. **修复目标**：两者都做——主修断链（让批准后真能开跑），同时补失败响亮兜底。
2. **refs 事实源**：decomposition.md 的 RTM 表是对的，plan 对象是错的；最新的流程
   不应再生成 plan.md（代码已确认，见 §1.2）。
3. **范围**：plan.md 验收残留并入本需求一起修，不另立。

## 2. 产品定义

让「批准拆分计划 → 自动落卡 → 自动开跑」这条 REQ-4842fe 交付的主链**真实可用**：
覆盖门禁的事实源统一到 decomposition.md 的 RTM 表（与设计意图一致）；自动开跑失败
必须响亮（评论 + 告警 + 显式标记），不再静默退化为手动；验收文档清单与最新流程对齐，
不再硬要一份新流程不生成的 plan.md。

## 3. 用户与角色

- **主要用户**：人类用户——批准计划后能确信"链真的开跑了"；开跑失败时当场收到告警，
  而不是几天后凭感觉发现"好像没用 workflow"。
- **次要用户**：执行窗口 agent——手工兜底路径（decompose + move）不再是无告警的默认
  结局；恢复入口（reqboard_task_run / 看板控制面）在失败后可达。

## 4. 功能点

### FR-1: 覆盖门禁事实源统一到 decomposition.md RTM
`assertClauseCoverageGate` 的 refs 取值从「仅任务对象」改为「任务对象 ∪
decomposition.md RTM 表」（`taskRefsFromDecomposition` 既有解析复用）：任一来源声明
接收即算有落点。效果是：按规范在 RTM 表里标注了绑定的计划（如 REQ-2d1c74），批准后
自动拆分不再被 requirement_uncovered 误拦，自动开跑链恢复；两个来源都未声明的条款
仍按现状拒绝（门禁不削弱）。RTM 表解析不到（表缺失/表头不符）时保持"无法比对"语义，
不把"没记录"误判成"已覆盖"。

### FR-2: 自动开跑失败响亮化
`AskConfirm` 自动拆分/开跑的 catch 路径不得只写返回 note：①写系统评论（含失败原因
与人工恢复指引）；②复用 `deps.alert`（FailureAlert）发高优告警；③在需求台账上留下
显式标记（如 advance.pausedReason），使看板能呈现「自动链未开跑」与手动模式的区别——
具体呈现形态（徽标文案/控制面入口）归设计阶段定，但"失败在看板上不可见"的现状必须
消除。恢复路径：人修复后手动 reqboard_decompose + reqboard_task_run（既有工具），
提示词/评论里写清。

### FR-3: plan.md 从验收必交清单移除
`DocCompleteness.ts` 的 VERIFICATION_DOC_CLASSES 删除第 2 类
`plan.md（拆分计划）`（第 7 类 decomposition.md 保持必交）；同步清理引用残留：
`RequirementStatus.ts:27` 阶段注释、`docs/requirements/_template/`、以及
文档/提示词中"写 plan.md"的表述。存量 34 个 plan.md 文件不删不动；已交 plan.md 的
存量需求不受影响（多出的文件无害）。`req.plan` 记录本身保留（批准弹框与落卡仍消费
其 path/summary/tasks），本 FR 只移除"plan.md 是必交文档"这一口径。

### FR-4: 回归安全
①新增断链复现测试：种子需求带 requirement.md（含 FR 编号）+ plan payload 无 refs +
decomposition.md 含 RTM → askConfirm(target=plan) 批准后 autoRun===true、任务落库、
链推进（修复前该测试必须红，修复后绿——先红后绿作为证据）；②双源皆空时仍
requirement_uncovered 且评论+告警各一条（断言）；③无 plan.md 有 decomposition.md 时
checkDocCompleteness 通过；④`npx vitest run`（dsh-pmboard）全绿，isLegacy 豁免语义
不回退。

## 5. 边界

1. **不改 refs 落库决策**：TaskRecord 不新增字段，绑定仍随 decomposition.md RTM 持久化
   （维持 Decompose.ts:168 既有设计）；`reqboard_submit` 工具 schema 不加
   requirement_refs——用户已裁定 plan 对象不是正源，不往错误方向扩写入链。
2. **不动自动链引擎本体**：AdvanceChain/ExecuteTask/WorkflowEngineRunner 语义不改；
   本需求修的是"进链前的接线"与"失败的可观测性"。
3. **存量 plan.md 不清理**：34 个历史文件保留作档案；_template 同步改但不追溯改历史需求。
4. **REQ-2d1c74 不回填**：它已手工实施过半（4 done / 1 in_progress / 2 todo），继续手工
   做完即可，不为它重开自动链；但其验收会被 §1.2 的雷卡住，FR-3 须先于它提交验收上线。
5. **告警通道复用既有**：`deps.alert`（FailureAlert→弹框指令壳），不新建通知渠道。

## 6. 验收口径

1. `npx vitest run tests/auto-chain-approval.test.ts` 新增用例：带 FR 编号 + RTM 的
   种子需求批准后 autoRun===true 且子卡链落库（**先红后绿**，两次输出留证）；
2. 双源皆无 refs 的种子：批准仍被拒 requirement_uncovered，且台账新增一条
   「自动开跑失败」系统评论、alert 被调用一次（vitest 断言）；
3. `checkDocCompleteness` 输入无 plan.md、有其余 8 类时 passed===true（vitest 用例）；
4. `grep -n "plan.md" src/domain/workflow/DocCompleteness.ts src/domain/requirement/RequirementStatus.ts docs/requirements/_template/` 无必交/指引残留；
5. `npx vitest run`（dsh-pmboard 包）全绿。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |

> 🔴 **未被接收（4 条）**：FR-1、FR-2、FR-3、FR-4

<!-- reqboard:marks:end -->

## 7. 关键源码索引（定位留证）

- 断链现场：`src/application/use-cases/AskConfirm.ts:240-300`（门合并自动开跑+catch 静默）
- 覆盖门禁：`src/application/use-cases/Decompose.ts:164-186`、
  `src/application/internal/content-gate-wiring.ts:56-99`（refs 只读对象）
- RTM 正源解析：`src/application/internal/content-trace.ts:129-166`
  （taskRefsFromDecomposition / collectTaskRefs）
- plan 写入链（用户裁定不扩）：`src/tools/SubmitTool/SubmitTool.ts:48-64`、
  `src/shared/protocol.ts:488-511,691-732`
- plan.md 残留：`src/domain/workflow/DocCompleteness.ts:11,37`、
  `src/application/use-cases/SubmitVerification.ts:78-112`、
  `src/domain/requirement/RequirementStatus.ts:27`
- 假绿灯测试：`tests/auto-chain-approval.test.ts`（种子无 requirement.md，门禁短路）
- 实证：`docs/requirements/REQ-2d1c74/`（无 plan.md；会话实录 0 次 task_run）
