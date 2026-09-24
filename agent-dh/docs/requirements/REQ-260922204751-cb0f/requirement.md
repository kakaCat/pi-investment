---
req_id: "REQ-260922204751-cb0f"
title: "实施过程中展示代码 diff（pmboard）"
status: brainstorming
owner: "session-bbfc9a7a"
category: spike
---

# 需求说明（REQ-260922204751-cb0f）

> 状态：需求分析（brainstorming） · 窗口 session-bbfc9a7a（w-bbfc9a7a） · 立据：2026-09-22
> 分类：Spike（**研究即实施**，产物 = 这篇报告本身，不落产品代码）。
> 时间盒：1 天——到期必须出结论，哪怕结论是「技术可行但成本高于收益」。

> **落盘位置（过渡期双路径，2026-09-22 design 节点补记）**：闸门与产物自动登记把路径写死在
> `docs/requirements/<REQ>/`（`src/application/internal/design-gates.ts`、`content-gate-wiring.ts`、
> `src/adapters/ArtifactSync.ts`），而本需求立项时 `docBasePath=docs/rfcs/`（节点输入包的 requirement
> 链接仍解析到这里）。故正文以**两处内容逐字一致**的副本落盘：
> `docs/rfcs/REQ-260922204751-cb0f/requirement.md` 与
> `docs/requirements/REQ-260922204751-cb0f/requirement.md`。**修改正文须同步两份**（两份除本注与
> §修订记录 外逐字相同）。闸门路径硬编码属独立缺陷，系统性修复见 §数据与方法 末条。


## 背景与动机

**用户原话（直接人工消息，2026-09-22，本窗口）**：

> 实施过程中 diff，我们可以实现一个展示吗

**现状（实测，非推测）**：

| # | 事实 | 证据（来源 + 时点） |
|---|---|---|
| 1 | 任务卡的「📁 修改文件」区**不是真数据**：它用正则解析 `execution.evidence` 里的自由文本 `路径 (+45, -12)` | 读 `src/client/views/stage-panel.ts:231-260` 的 `renderImplementContent`（2026-09-22） |
| 2 | 该区当前**恒空**：实测 4 张在途卡（REQ-9494f9）的 `executions[].evidence` 全为空数组 → 页面渲染「暂无文件变更记录」 | `curl :13080/dashboard/api/reqboard/state`（2026-09-22），取 `t-f0dcf2`/`t-0f54a6` 等 |
| 3 | 真实数据只到**文件名**这一层：`task.lastReport.filesChanged` | 写：`src/application/use-cases/ReportTask.ts:129`；读：state 接口实测返回 `lastReport` |
| 4 | 客户端 `TaskRecord` 类型**根本没声明** `lastReport`，所以连文件名都没渲染 | `src/client/types.ts:201-233`（2026-09-22） |
| 5 | 本包 `src/` **零 git、零 child_process**；同仓有可用先例 | `grep child_process` 于本包 src 得 0 处；先例 = `packages/tools/lifecycle/src/git.ts:1`（dsh 进程内 `execFileSync('git', …)`） |
| 6 | git 与路径口径都就绪：`git 2.39.5`；仓库根 `/Users/yunpeng/pi-investment`；pmboard `workspaceRoot=/Users/yunpeng/pi-investment/agent-dh`；`git -C <workspaceRoot> diff --relative` 的输出路径与 `filesChanged` **同口径** | 实测（2026-09-22）：`git -C …/agent-dh diff --relative --numstat` → `packages/web/dsh-pmboard/src/adapters/CaptureHook.ts` |
| 7 | **关键坑**：只看「工作区 diff」会得到空结果——REQ-9494f9 两张卡的文件 `git diff` 无输出（改动已 commit）。必须在**任务开工时记基线 HEAD**，之后 `git diff <基线>` 才既有已提交也有未提交的改动 | 实测（2026-09-22）：`git -C …/agent-dh diff --relative -- packages/solve-kit/src/host.ts` 无输出；以 2 天前 HEAD 作基线得 `0 增 / 301 删` |

相关代码：`src/application/use-cases/ReportTask.ts`、`src/http/routers/artifacts.ts`（文件白名单 `classify()`）、`src/client/views/stage-panel.ts`、`src/client/open-doc.ts`。

## 目标

**一句话目标**：让 pmboard 的任务卡在**实施过程中**就显示「这次实施到底改了哪些文件的哪些行」——数据直接来自 git（`git diff <开工基线>` 的 unified diff），不是 agent 自述的自由文本。

**可证伪判定标准**（跑什么、看到什么算完成）：

1. 打开任一在途任务卡（实施节点）→「修改文件」区显示**真实 diff**（含 `+/-` 行与上下文），而不是「暂无文件变更记录」；
2. 随机抽 1 个文件，与 `git -C <workspaceRoot> diff <基线> --relative -- <该文件>` 的输出**逐字比对一致**；
3. 拿不到 diff 时必须出现**显式降级标记**（`baseline_unavailable` / `truncated=true`），**不允许**用空 diff 冒充「无改动」。

| 编号 | 目标 | 价值（解决什么/对谁） | 衡量指标 | 目标值 |
|---|---|---|---|---|
| G1 | pmboard 上能看见「这次实施**到底改了什么**」 | 人与验收方不再只看文件名与自述，减少「说改了、实际没改/改错」的盲区 | 在途任务卡上可展开的 unified diff | 有真实 `+/-` 行与上下文 |
| G2 | diff 来源**可核验**，不是又一层自由文本 | 与 R-013 同精神：数据须有来源与时点 | diff 逐字对应 `git diff <基线>` 输出 | 抽样 1 文件逐字一致 |
| G3 | 实施**过程中**可见（不只在汇报时点） | 早发现跑偏，降低返工成本 | 任务开工到首次可见 diff 的延迟 | 开工后即可见 |
| G4 | 降级不撒谎 | 基线失效/git 不可用必须说「不可用」，不能显示空 diff 冒充「没改动」 | 降级路径有明确文案与标记 | 无静默空结果 |

## 非目标

- N1 不做逐行评论 / code review 工作流（评审仍走 review 节点与评论）。
- N2 不做 `git blame`、历史版本对比、跨任务/跨需求 diff。
- N3 不把 diff 当验收证据的唯一来源（凭证仍以任务汇报 + 文件 mtime 凭证门为准，见 `src/application/internal/subtask-evidence.ts`）——diff 是**展示**，不是**凭证**。
- N4 不支持非 git 工作区（本仓库是 git 仓库，够用）。

## 边界（≤3 条 · 没写进来的本次不做）

1. **只交研究报告，不落产品代码**：本需求是 spike，产物=这篇报告（含推荐方案、代价与风险）；真正改代码（git 适配器 / task 字段 / HTTP 端点 / 客户端渲染）**另立 feature/refactor 需求**。
2. **只做「任务卡上的只读展示」**：不做逐行评论 / code review 工作流（N1），不做 `git blame` / 历史版本对比 / 跨任务跨需求 diff（N2）；diff 是**展示不是凭证**，验收凭证仍以任务汇报 + 文件 mtime 凭证门为准（N3）。
3. **不扩大技术面**：不引入第三方 diff 库（服务端只出 unified diff 文本、渲染在客户端）；不放宽文件访问白名单（端点必须复用 `src/http/routers/artifacts.ts` 的 `classify()` 口径）；不支持非 git 工作区（N4）；不顺手修「spike/doc/chore 走不到 implementing」的流水线断点（SP-6，属独立缺陷）。

## 轻档依据与升级信号（L3）

**为什么可走轻档**：本节点改动面 **0 行产品代码**（spike 的产物就是这篇报告）；没有需要在需求分析阶段**新开**的决策分支——3 条产品决策（D1~D3）已收敛且各带推荐值，随本报告一并请人拍板即可；不涉及架构调整、不新增子系统。**注意**：推荐方案在**将来实施时**会给 task 记录加 `diffBaseline` 字段（数据模型变更）——正因如此，实施必须另立 feature 需求走完整 design + 拆分，本节点不碰。

**一旦出现以下任一信号，立即停手并升级为重档**（升级单向，不许反向降级）：

1. 有人要求**在本需求内直接实现**（而非另立 feature/refactor）——会改 task 记录（新增 `diffBaseline` 字段），属数据模型变更；
2. 研究过程中出现 **D1~D3 之外、且无推荐值**的第二个未定决策；
3. 结论要求**改架构 / 新增子系统**（如把 git 读取做成独立服务或独立包）。

## 验收标准

- [ ] SP-1 ~ SP-6 每条都有明确答案，且答案带证据（命令原文/代码位置/实测输出），无「可能/大概」式结论。
- [ ] 结论节给出**唯一推荐方案**及其代价，并列出被否决方案与否决理由。
- [ ] 报告末尾给出「实施候选验收清单」（可执行：跑什么命令、看到什么算过），供后续实施需求直接复用。
- [ ] 报告落盘路径可被看板「文档记录」打开（`docs/rfcs/REQ-260922204751-cb0f/requirement.md`）。

## 待答问题

- **SP-1: diff 从哪来？** 候选：① git 基线 diff（开工记 `HEAD`，端点实时算）② agent 在 `reqboard_task_report` 里上报 diff 文本 ③ 两者都要（git 实时 + 上报作归档证据）。
- **SP-2: 文件归属怎么定？** 任务改了哪些文件，在它汇报前是**未知**的。候选口径：`lastReport.filesChanged` ∪ 需求级 `artifacts(kind=task_output)` ∪ 「`git status --porcelain` 中 mtime ≥ 开工时刻的文件」。启发式够不够用？
- **SP-3: 共享工作区的污染怎么界定？** 同工作区多窗口/人工并行编辑（实测当下 `git status --porcelain` 有 **59** 个脏文件）。不收窄会混入别人的改动；收窄后同一文件里仍可能混入他方改动——怎么如实标注？
- **SP-4: 基线失效怎么办？** 基线 sha 可能被 rebase / `git gc` / 切分支搞失效，降级行为是什么？
- **SP-5: 展示在哪、多细？** 位置：任务卡实施节点 / 需求详情新增「代码变更」Tab / 两处。粒度：摘要（文件 + 增删行数）/ 逐文件展开完整 diff / 全文平铺。
- **SP-6: 「spike/doc/chore 三类走不到 implementing」这个断点是否随本需求一并修？**

## 数据与方法

- **样本**：1 个仓库（`/Users/yunpeng/pi-investment`，git 2.39.5）、1 个在途 implementing 需求（REQ-9494f9，4 张任务卡）、本包源码通读（client 视图 / http 路由 / 用例 / 适配器 / 端口）。
- **口径**：代码事实以**当前工作区源码**为准（2026-09-22，`main` 分支，未提交改动 59 个文件）；路径口径以 `workspaceRoot`（= `…/agent-dh`）为准；git 行为以**实际执行命令的输出**为准。
- **交接前复核（2026-09-22，本窗口第二次实测）**：报告 7 条现状事实与 SP-6 断点在提交前重新核验，全部原样成立——`renderImplementContent` 仍以正则解析 `execution.evidence`；`TaskRecord` 仍无 `lastReport`（`grep lastReport src/client/types.ts` 命中 0）；本包 `src/` 仍 **0** 处 `child_process`；`REQ_TRANSITIONS.draft=['brainstorming','canceled']`（无 `draft→implementing`）与 `CATEGORY_FLOW_PROFILES.spike.stages=['draft','implementing','accepting','archived']` 逐字未变。台账侧补一条更强的数：**184/268** 张任务卡已有 `lastReport.filesChanged`（数据早就在，只是没渲染；在途卡 `t-f0dcf2`/`t-0f54a6` 的 `executions[].evidence` 仍全为空数组）。基线口径再验：`git -C …/agent-dh diff --relative --numstat b24fb9ed -- packages/solve-kit/src/host.ts` → `0 增 / 301 删`（与初稿一致），而对照 `HEAD~3` 为**空**——**基线必须早于改动**，这正是「开工时记 HEAD」而非「事后猜基线」的直接证据。脏文件数是快照不是常量（初稿实测 59，复核时 71）。
- **顺带实测到的第二个闸门旁路（与本次落盘位置有关）**：本需求立项时选了 `docBasePath=docs/rfcs/`，而代码级内容闸门里的路径是**写死**的——`checkRequirementDocFormatGate` 读 `docs/requirements/<REQ>/requirement.md`，`checkDesignServesGate` / `checkDesignCompletenessGate` 读 `docs/requirements/<REQ>/design/`（`src/application/internal/content-gate-wiring.ts:155+`、`src/application/internal/design-gates.ts:113+`）。`docs.exists(...)===false` 时这些闸门**直接 return undefined（静默放行）**。即：文档放 `docs/rfcs/` 会让「功能编号规范」「设计章节 serves 追溯」「设计文档集完整性」三道闸门**全部不生效**。本次是 spike、产物为单篇报告，影响可控；但**下一个 design 节点若沿 `docs/rfcs/<REQ>/design/` 落盘，同样不会过闸门也不会被拦**——如实记在此处，供后续决策（改为 `docs/requirements/<REQ>/` 或先修闸门路径适配 `docBasePath`）。
- **样本充分性（R-016 精神）**：本报告是**可行性论证**，不是统计结论——样本量小（1 仓库 / 1 需求），故只对「能不能做、坑在哪、代价多少」下结论，**不对「上线后收益多少」下结论**。
- **顺带实测到的流水线断点**：`CATEGORY_FLOW_PROFILES.spike.stages = ['draft','implementing','accepting','archived']`（`src/shared/protocol.ts:323`）声明「研究即实施、跳过 brainstorming/design/decomposing」；但 ① `reqboard_capture` **无条件**把新需求推进到 `brainstorming`（`src/application/use-cases/CaptureRequirement.ts:58-78,176-177`）② 状态机 `REQ_TRANSITIONS` 无 `draft→implementing` / `brainstorming→implementing`（`src/domain/requirement/RequirementStatus.ts:56-70`）。实测：对本需求（spike，当前 brainstorming）调 `reqboard_move to=implementing` → 被拒 `invalid_transition`。**即：spike/doc/chore 三类的流程档案在状态机上落不了地**（只能沿 feature 线性路径爬，而那条路的产物集对这三类是错的）。

## 结论

**总判定：可以做（置信度：高）**——diff 数据在服务端就能拿到，路径口径**天然与台账一致**（实测：`git -C <workspaceRoot> diff --relative` 的输出就是 `filesChanged` 的写法），插件跑 git 有同仓先例（lifecycle），客户端渲染 unified diff 不需要新依赖。

**推荐方案（SP-1 ~ SP-5 的答案；三条产品决策见下表，可被用户推翻）**：

1. **来源（SP-1）**＝ git 基线 diff：任务 `task_move → in_progress` 时记 `task.diffBaseline = { head: <短 sha>, at }`；端点实时算 `git -C <workspaceRoot> diff <head> --relative --no-color -- <scope>`。
2. **归属（SP-2）**＝ 台账优先，启发式兜底：`lastReport.filesChanged` ∪ 需求级 `artifacts(kind=task_output)`；**仅当两者皆空**时才启用「mtime ≥ 开工时刻」的启发式，并在界面上如实标注「（启发式，尚未汇报）」。
3. **污染（SP-3）**＝ 收窄 + 标注 + 不冒充凭证：范围收窄到本任务文件；标题固定写「工作区当前状态 vs 开工基线」；tooltip 写明「同一文件若被他人/他窗口同时改动也会一并显示，不能作为验收凭证」。
4. **基线失效（SP-4）**＝ 响亮降级：`git cat-file -e <sha>` 校验；失效则返回 `degraded: 'baseline_unavailable'` + 原因文案，界面只列文件名（来自 `filesChanged`）并标红「基线不可用」——**绝不返回空 diff 冒充「无改动」**。
5. **位置与粒度（SP-5）**＝ 任务卡（实施节点）优先，把现在恒空的「修改文件」区换成真 diff；顶部「N 文件 +X -Y」摘要，逐文件默认收起、点开看红绿逐行；单文件与整体各设截断阈值（建议单文件 2000 行 / 响应 < 512KB），超限标 `truncated`。
6. **SP-6** ＝ **不在本需求内修**（影响面在状态机与捕获工具，属独立缺陷；本次只把它的实测证据留在这里）。

**代价（估）**：服务端 1 个 git 适配器 + 1 个 task 字段 + 1 个 HTTP 端点（含白名单复用与截断）；客户端 1 处类型补齐 + 1 个 diff 渲染器 + 样式。约半天到一天。

**主要风险**：① 共享工作区污染（SP-3，缓解见上）② 基线失效（SP-4，响亮降级）③ 大 diff 卡顿（SP-5，服务端截断 + 客户端虚拟滚动按需）④ 安全（diff 端点**必须**复用 `classify()`，不得退化成任意文件读取）。

**被否决的候选**：**单独用 agent 上报 diff**（SP-1 ②）——实施**过程中**看不到，而用户原话正是「实施过程中」；只在汇报时点有 diff，等于把「看不见」推迟到「汇报时才看得见」。可作 P1 增量（归档证据，与 N3 呼应）。

## 待裁决（3 条产品决策）

| 编号 | 决策 | 推荐 | 备选 |
|---|---|---|---|
| D1 | diff 来源 | git 基线 diff | agent 上报 / 两者都要 |
| D2 | 展示位置 | 任务卡实施节点 | 需求详情新增「代码变更」Tab / 两处 |
| D3 | 展示粒度 | 逐文件展开完整 diff（带摘要） | 只给摘要（文件 + 增删行数） |

## 附录 · 实施候选验收清单（供后续实施需求复用）

- [ ] 打开 `http://127.0.0.1:13080/dashboard#pmboard`，进入任一 implementing 需求的任务卡（实施节点），「修改文件」区显示真实 diff（含 `+/-` 与上下文）；随机抽 1 个文件与 `git -C …/agent-dh diff <基线> --relative -- <该文件>` 的输出**逐字比对一致**。
- [ ] `curl 'http://127.0.0.1:13080/dashboard/api/reqboard/task/<在途任务 id>/diff'` 返回 200，且 `data.files[].patch` 非空、`data.files[].added/deleted` 与 `--numstat` 一致。
- [ ] 越界请求（`path=/etc/passwd`、含 `..` 或反斜杠）返回 403/404 **且响应体不含文件内容**。
- [ ] 构造失效基线（传一个不存在的 sha）→ 接口返回 `degraded='baseline_unavailable'` 与原因，**不返回 500、不返回空 diff**。
- [ ] 构造 >2000 行的单文件改动 → 返回 `truncated=true`，响应体 < 512KB，界面有「已截断」提示。

## 修订记录

| 日期 | 修改内容 | 修改人 |
|---|---|---|
| 2026-09-22 | 初稿：现状实测 7 条、SP-1~SP-6、推荐方案与风险、实施候选验收清单 | 窗口 session-bbfc9a7a（w-bbfc9a7a） |
| 2026-09-22 | brainstorming 节点收口：补 L1 一句话目标 + 可证伪判定标准；边界收紧为 3 条；新增 L3 轻档依据与单向升级信号；补交接前复核附记（含 184/268 有 lastReport）与「闸门旁路」实测发现 | 窗口 session-bbfc9a7a（w-bbfc9a7a） |

| 2026-09-22 | design 节点：正文以逐字一致的两份副本落盘（闸门硬编码路径 `docs/requirements/` 与立项 `docBasePath=docs/rfcs/`）；待答问题 SP-1~SP-6 归一为可解析的编号定义位（`**SP-n: 标题**`）以支撑下游「编号串联」门禁；**实质结论未改动**。`reqboard_requirement_submit` 仅限 brainstorming 阶段，故本次未重落章 | 窗口 session-bbfc9a7a（w-bbfc9a7a） |