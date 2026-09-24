# 拆分计划 · 统一追溯链逻辑：全链路展示中文化

> REQ-260922182638-0777 · feature / simple（轻档）· 窗口 w-89aa3b25 · 2026-09-22
> 依据：design/architecture.md（A-1~A-5）、design/interfaces.md（I-1~I-4）、design/test-cases.md（T-1~T-3）
> 摸底已于 2026-09-22 本窗口实测复核（grep 六处映射表全部命中，与设计文档清单一致）。

## 1. 目标与做法（一段）

把 dsh-pmboard 前端六处各自为政的「产物种类/文件名 → 中文名」映射收敛为唯一事实源模块
`src/shared/artifact-labels.ts`（纯函数、零 IO、client/host 双向安全），六处调用点全部改为 import；
追溯链（client/stage-panel.ts）做两处标签逻辑改造：design 多份产物主标签由裸文件名改为中文文档名
（tooltip 保留完整路径）、task_detail 由「任务卡×N」折叠改为逐张展开且带任务名称
（经 artifact.path ↔ StageTaskRef.cardDoc 精确匹配取 title，匹配不到降级「任务卡（t-xxx）」）；
配套单测防漂移护栏（新增规范文件名/kind 未配中文名即红）。
不动协议、不动枚举、不动数据模型、不动后端；纯展示层取值变更，单 commit 可 revert。

## 2. 改动盘点（对照设计文档逐份）

### 新增

| 文件 | 内容 | 依据 |
|------|------|------|
| `packages/web/dsh-pmboard/src/shared/artifact-labels.ts` | 唯一事实源：KIND_LABELS（7 种 ArtifactKind + ui/proposal/retro/notes 扩展）、KIND_ICONS、DOC_FILE_LABELS（10 个规范文件名）+ artifactKindLabel / docFileLabel / taskCardLabel 三函数（未知值中文兜底+原文附注，任何输入不 throw） | interfaces.md I-1~I-3 |
| `packages/web/dsh-pmboard/tests/artifact-labels.test.ts` | TC-001~TC-005：映射完整性逐条断言 + 未知值兜底 + 防漂移护栏（effectiveDesignDocs 产出文件名 ∈ DOC_FILE_LABELS 键集） | test-cases.md T-1 |

### 修改

| 文件 | 现状（实测行号） | 改造 | 依据 |
|------|------|------|------|
| `src/client/stage-panel.ts` | L60 私有 ARTIFACT_KIND_LABELS（7 项）；L88 traceNodeLabel 对 design 裸显 basename；L562-569 task_detail 折叠「任务卡×N」 | 删本地表；traceNodeLabel 改用 artifactKindLabel / docFileLabel；task_detail 逐条渲染，标签 = taskCardLabel(path, taskTitleByCardDoc(payload) 解析的 title)；缺失红字「（缺失）」分支不变 | architecture.md A-3#1 / A-4 |
| `src/client/views/artifacts.ts` | L18 导出 ARTIFACT_KIND_LABELS（重复定义），L78/L107 chips 取标签 | 删表，两处改 artifactKindLabel(g.kind)；导出符号经全仓 grep 确认无外部 import，可直接删 | A-3#2 / I-4 |
| `src/client/views/verification.ts` | L16 DOC_KIND_META（12 项 icon+label）；L189 ARCHIVE_DOC_KIND_LABELS（requirement 译「需求说明」，已漂移） | DOC_KIND_META 保留导出形状，label 由 KIND_LABELS、icon 由 KIND_ICONS 供给；ARCHIVE_DOC_KIND_LABELS 删除，L175 改 artifactKindLabel(d.kind)（「需求说明」→「需求文档」统一） | A-3#3/#4 |
| `src/client/toolviews/shared.ts` + `rows/submit.ts` + `rows/ask-confirm.ts` | shared.ts:138 SUBMIT_KIND 仅 4 项（缺 design/decomposition/task_detail）；ask-confirm.ts:9 另有 KIND_CN 补丁表 | 删 SUBMIT_KIND / KIND_CN，统一 artifactKindLabel（缺的三种 kind 自动补齐中文名） | A-3#5 |
| `src/tools/render-summaries.ts` | L24 SUBMIT_KIND_CN（host 侧工具回执） | 删表，import artifactKindLabel（plan 统一「拆分计划（旧版）」，术语漂移消除） | A-3#6 |
| `tests/stage-panel.test.ts` | 已有「追溯链」describe（L418） | 扩展 TC-006：design 多份显示中文文档名、task_detail 逐张带名称展开、缺失产物红字保留 | T-1 TC-006 |

### 删除

- 六处本地映射表本体（见上表「现状」列）；无文件级删除、无数据迁移。

## 3. 任务表

| key | title | phase | side | depends_on | requirement_refs |
|-----|-------|-------|------|------------|------------------|
| t1 | 新增 artifact-labels 唯一事实源模块与防漂移单测 | implement | fullstack | — | FR-1, FR-3 |
| t2 | 收敛文档区两处引用（artifacts / verification） | implement | frontend | t1 | FR-1, FR-2 |
| t3 | 收敛 client 工具回执引用（toolviews 三文件） | implement | frontend | t1 | FR-1, FR-2 |
| t4 | 收敛 host 工具回执引用（render-summaries） | implement | backend | t1 | FR-1, FR-2 |
| t5 | 追溯链标签改造（文件名中文 + 任务卡逐张展开） | implement | frontend | t1 | FR-4, FR-5 |
| t6 | 兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对） | review | fullstack | t2, t3, t4, t5 | FR-2, FR-3 |

契约卡（t1）先行，实现/接线卡全部 depends_on t1；t6 为迁移与兼容卡（旧调用方残留核查 + 全量验收），承接兼容验证。
卡不跨层：t1=接口/数据契约层；t2/t3=client 接线；t4=host 接线；t5=client 追溯链渲染；t6=验收核查。


### 3.1 RTM 覆盖表（需求条款 ↔ 任务卡，落库后回填真实任务 id）

> REQ-84bea5 FR-1：任务↔需求编号的绑定不落 TaskRecord，规范载体是本表（decompose 覆盖门禁与接收状态均从此解析）。
> 每行一条绑定（根编号列只放一个编号，解析器 collectIds 只取首个）。

| 任务编号 | 任务标题 | 根编号 | 交付说明 |
|----------|----------|--------|----------|
| t-85eedd | 新增 artifact-labels 唯一事实源模块与防漂移单测 | FR-1 | 两层映射收敛的唯一事实源模块 |
| t-85eedd | 新增 artifact-labels 唯一事实源模块与防漂移单测 | FR-3 | 未知值中文兜底 + 防漂移护栏单测 |
| t-3d33c3 | 收敛文档区两处引用（artifacts / verification） | FR-1 | 文档区改 import 唯一事实源 |
| t-3d33c3 | 收敛文档区两处引用（artifacts / verification） | FR-2 | 归档清单 requirement 统一为「需求文档」 |
| t-67a5c9 | 收敛 client 工具回执引用（toolviews 三文件） | FR-1 | 工具回执改 import 唯一事实源 |
| t-67a5c9 | 收敛 client 工具回执引用（toolviews 三文件） | FR-2 | design/decomposition/task_detail 中文名补齐 |
| t-86ae1e | 收敛 host 工具回执引用（render-summaries） | FR-1 | host 侧工具回执改 import |
| t-86ae1e | 收敛 host 工具回执引用（render-summaries） | FR-2 | plan 术语统一「拆分计划（旧版）」 |
| t-bdbab2 | 追溯链标签改造（文件名中文 + 任务卡逐张展开） | FR-4 | design 主标签文件名中文化 |
| t-bdbab2 | 追溯链标签改造（文件名中文 + 任务卡逐张展开） | FR-5 | 任务卡逐张展开且带任务名称 |
| t-9d9cf9 | 兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对） | FR-2 | 五区块术语一致性验收 |
| t-9d9cf9 | 兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对） | FR-3 | 兜底形态与防漂移单测验收 |

### t1 · 新增 artifact-labels 唯一事实源模块与防漂移单测

**implementation**：
1. 新建 `src/shared/artifact-labels.ts`（与 protocol.ts 同层，纯函数零依赖）：导出 KIND_LABELS / KIND_ICONS / DOC_FILE_LABELS 三张 Readonly 表（内容与 interfaces.md I-3 终稿逐字一致）+ artifactKindLabel(kind) / docFileLabel(path, kind?) / taskCardLabel(path, title?) 三函数，兜底契约按 I-2（未知 kind→「产物（原值）」；未知文件名→「<kind中文>（<文件名>）」；docFileLabel 段边界后缀匹配）。
2. 新建 `tests/artifact-labels.test.ts`：TC-001 全表逐条断言；TC-002 未知 kind/空串不 throw；TC-003 DOC_FILE_LABELS 全表命中 + 未知文件名兜底；TC-004 taskCardLabel 两分支；TC-005 防漂移护栏——import effectiveDesignDocs（application/internal/category-doc-sets.ts:81）对六种 category 产出的全部规范文件名断言 ∈ DOC_FILE_LABELS 键集。

**acceptance**：`cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/artifact-labels.test.ts` 全绿（TC-001~005）；`pnpm typecheck` 通过。

### t2 · 收敛文档区两处引用（artifacts / verification）

**implementation**：
1. `src/client/views/artifacts.ts`：删 L18 ARTIFACT_KIND_LABELS 表，L78/L107 改 `artifactKindLabel(g.kind)` / `artifactKindLabel(kind)`（删 `?? kind` 兜底）。
2. `src/client/views/verification.ts`：DOC_KIND_META 保留导出形状 `{icon,label}`，取值改为 KIND_ICONS / KIND_LABELS 供给；删 L189 ARCHIVE_DOC_KIND_LABELS，L175 改 artifactKindLabel(d.kind)。

**acceptance**：`grep -n "ARTIFACT_KIND_LABELS\|ARCHIVE_DOC_KIND_LABELS" src/client/views/` 无任何命中；`pnpm vitest run tests/artifact-confirm-board.test.ts tests/verification-sheet.test.ts` 全绿；`pnpm typecheck` 通过。

### t3 · 收敛 client 工具回执引用（toolviews 三文件）

**implementation**：`src/client/toolviews/shared.ts` 删 L138 SUBMIT_KIND 表；`rows/submit.ts` L12 与 `rows/ask-confirm.ts` L9/L14 删 KIND_CN 补丁与 `cnLabel(...) ?? kind`，统一改 artifactKindLabel(kind)（design/decomposition/task_detail 中文名自动补齐）。

**acceptance**：`grep -n "SUBMIT_KIND\|KIND_CN" src/client/toolviews/` 无任何命中；`pnpm vitest run tests/toolviews-cards.test.ts tests/toolviews-contract.test.ts` 全绿；`pnpm typecheck` 通过。

### t4 · 收敛 host 工具回执引用（render-summaries）

**implementation**：`src/tools/render-summaries.ts` 删 L24 SUBMIT_KIND_CN 表，L50 改 artifactKindLabel(kind)；确认 plan 渲染为「拆分计划（旧版）」。

**acceptance**：`grep -n "SUBMIT_KIND_CN" src/tools/` 无任何命中；`pnpm vitest run tests/render-summaries.test.ts` 全绿（含 plan→「拆分计划（旧版）」断言，若既有断言为旧文案则同步修正）；`pnpm typecheck` 通过。

### t5 · 追溯链标签改造（文件名中文 + 任务卡逐张展开）

**implementation**（`src/client/stage-panel.ts`）：
1. 删 L60 ARTIFACT_KIND_LABELS 表，三处 `?? kind` 兜底改 artifactKindLabel(kind)。
2. traceNodeLabel（L88）：单份产物→artifactKindLabel(kind)；MULTI_DOC_KINDS（design）→docFileLabel(artifact.path, kind)；tooltip（title 属性 displayDocPath 完整路径）不动。
3. renderTraceChain（L562-569）：删 task_detail「×N」折叠分支，与 design 一样逐条渲染；新增 `taskTitleByCardDoc(payload)`——payload.body 为 Decompose/Implement 节点体时取 tasks 建 cardDoc→title 映射，artifact.path 精确匹配命中用 StageTaskRef.title，标签 = taskCardLabel(path, title)；匹配不到降级「任务卡（t-xxx）」。缺失必备产物红字「（缺失）」分支（L583-590）保持不变。
4. `tests/stage-panel.test.ts`「追溯链」describe 扩展 TC-006：design 多份显示「架构文档」「接口文档」；task_detail 逐张显示「任务卡 · <名称>」与降级「任务卡（t-xxx）」；断言不再出现「任务卡×」；缺失产物红字保留。

**acceptance**：`pnpm vitest run tests/stage-panel.test.ts` 全绿（含 TC-006 新增断言）；`grep -n "ARTIFACT_KIND_LABELS" src/client/stage-panel.ts` 无任何命中；`pnpm typecheck` 通过。

### t6 · 兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对）

**implementation**：
1. 跑 test-cases.md T-2 全部四条验收命令并留输出；旧表名全仓 grep（ARTIFACT_KIND_LABELS / SUBMIT_KIND / ARCHIVE_DOC_KIND_LABELS / KIND_CN）确认除 DOC_KIND_META 兼容导出外无残留。
2. `pnpm typecheck && pnpm build`（含 verify-client-build WRAP_SENTINEL 哨兵）通过。
3. 浏览器人工核对（T-3）：:13080 打开本需求（REQ-260922182638-0777，有 design 五份产物 + 任务卡）详情页，对照 prototype.html §1–§5 黄底差异逐项核对：追溯链全中文、无「任务卡×N」、无英文枚举；归档清单 requirement=「需求文档」；未知值兜底形态「产物（mystery_kind）」「设计文档（foo.md）」经测试数据核对。
4. 核对结论写进需求留痕（reqboard_task_report）。

**acceptance**：①`grep -rn "'需求文档'" src` 映射定义只剩 src/shared/artifact-labels.ts 一处；②`pnpm vitest run tests/artifact-labels.test.ts tests/stage-panel.test.ts` 全绿；③`pnpm typecheck && pnpm build` 通过；④浏览器核对清单逐项打勾并留痕（哪页看到什么）。

## 4. 升级信号复确认

本轮仍满足轻档：无后端改动、无新决策点、无协议/枚举变更。若实施中发现「都要展示」需要后端目录扫描或追溯链结构重设计，立即停手升重档（对齐 requirement.md L3）。