# REQ-260922182638-0777 统一追溯链逻辑：全链路展示中文化

> 立项：2026-09-22，窗口 session-89aa3b25（investor / w-89aa3b25），feature / simple（轻档）
> v2（2026-09-22 用户补充）：「需求文档→architecture.md→interfaces.md→拆分计划→任务卡 我希望是中文，还有节点的文档，都要展示」——
> 在「种类中文化」之上扩两点：①**文件名级中文化**（追溯链不再裸显 architecture.md / interfaces.md）②**节点文档全展示**（任务卡不再折叠为「任务卡×N」，逐张列出且**带任务名称**——StageTaskRef.title 现成可取，artifact.path ↔ task.cardDoc 匹配即可解析，无需后端改动）。

## L1 一句话目标 + 可证伪判定标准

**目标**：把 dsh-pmboard 前端散落的「产物种类（ArtifactKind）→ 中文名」与「节点文档文件名 → 中文名」两层映射收敛为**唯一事实源模块**，追溯链 / 文档记录区 / 产物确认 chips / 工具回执 / 归档清单全部引用同一映射；同一对象在各区块显示同一中文名；节点产出的每份文档（design 全套、拆分计划、逐张任务卡）都在追溯链可见；未知 kind / 未知文件名不裸显英文原文。

**可证伪判定**（跑什么、看到什么算完成）：

1. `grep -rn "需求文档" agent-dh/packages/web/dsh-pmboard/src` —— kind 中文映射定义只剩**一处**，其余文件全部 import 引用；
2. 浏览器打开任一有 design 多份产物 + 任务卡的进行中需求详情页：追溯链显示形如
   「需求文档 → 架构文档 → 接口文档 → 拆分计划 → 任务卡 · 实现映射模块 → …」**全中文**（任务卡带任务名称）——
   不得出现 `architecture.md` / `interfaces.md` 等裸文件名作主标签，不得出现「任务卡×N」折叠，不得出现任何英文枚举原文（requirement / design / decomposition / task_detail / verification / archive 等）；
3. 同一 kind 跨区块术语一致：归档清单里的 requirement 由「需求说明」统一为「需求文档」；
4. 人为构造未知 kind / 未知文件名 → 显示「产物（xxx）」「设计文档（foo.md）」式中文兜底+原文附注，而非裸英文。

## 产品定义

面向项目看板用户与执行窗口的中文展示层统一：产物种类与节点文档文件名在全链路（追溯链 / 文档记录 / 产物 chips / 工具回执 / 归档清单）显示同一中文名，节点产出的每份文档逐份可见。详见上方 L1 目标与可证伪判定。

## 用户与角色

- **看板用户（人）**：在需求详情页与会话流程节点面板阅读追溯链/文档区，靠中文名一眼识别每份产物，不再需要辨认 architecture.md 等英文文件名；
- **执行窗口（agent）**：写文档与登记产物的角色不受影响（契约不变），只在工具回执里看到中文摘要；
- **维护者（人/agent）**：新增 kind 或规范文件名时，由防漂移单测拦截未配中文名的遗漏。

## 边界（L2 范围边界，≤3 条）

1. **做**：两层映射收敛唯一事实源（一处定义、处处 import）——kind 层（7+ 种）与文件名层（requirement.md→需求文档、design/architecture.md→架构文档、design/data-model.md→数据模型、design/interfaces.md→接口文档、design/test-cases.md→测试用例、design/migration.md→迁移方案、decomposition.md→拆分计划、tasks/*.md→任务卡）；五区块（追溯链 / 文档记录 / 产物 chips / 工具回执 / 归档清单）术语统一。
2. **做**：追溯链节点文档全展示——design 逐份（沿用逐条渲染，标签改中文）、任务卡由「任务卡×N」**展开为逐张**（标签 = 「任务卡 · <任务名称>」，名称取 StageTaskRef.title，经 artifact.path ↔ task.cardDoc 匹配；匹配不到时降级为「任务卡（t-xxx）」编号形态）；未知兜底「中文 + 原文附注」；防再漂移机制（单测断言映射完整性，新增 kind 未配中文名时测试拦截）。
3. **不做**：不改数据模型与登记协议——ArtifactKind 枚举、reqboard_submit 契约、ArtifactSync/syncReqArtifacts 逻辑全部不变；不新增「扫描目录展示未登记散落文件」的后端能力（未登记文件本轮不展示）；不改 dsh-pmboard 以外插件。

## L3 轻路径依据 + 单向升级

改动面小：纯前端展示层——新增 1 个共享映射模块 + 4 处映射表收敛引用 + 追溯链 2 处标签逻辑改造（design 文件名→中文、任务卡 ×N→逐张），无新决策点、不动架构、不动数据模型。

**升级信号（任一出现即停手升重档）**：「都要展示」被证实需要后端目录扫描能力（展示未登记文件）/ 追溯链结构本身要重设计 / 需要改 ArtifactKind 枚举或登记协议 / 出现第二个未定决策。

## 现状证据（摸底实测，2026-09-22，w-89aa3b25）

同一套产物种类，dsh-pmboard 前端存在 **4 处各自为政的中文映射表**，注释互相声称「保持一致」但已实质漂移：

| # | 位置 | 映射表 | 覆盖 kind 数 | 兜底行为 |
|---|------|--------|---|---|
| 1 | src/client/stage-panel.ts:60 | ARTIFACT_KIND_LABELS（追溯链专用） | 7 | ?? kind 裸显英文 |
| 2 | src/client/views/artifacts.ts:18 | ARTIFACT_KIND_LABELS（chips/确认按钮，同名重复定义） | 7 | ?? kind 裸显英文 |
| 3 | src/client/views/verification.ts:16 | DOC_KIND_META（文档记录区） | 12 | ?? kind 裸显英文 |
| 4 | src/client/toolviews/shared.ts:138 | SUBMIT_KIND（工具回执行） | 4（缺 design/decomposition/task_detail） | cnLabel 未命中返回英文原文 |

漂移实例：

- verification.ts:189 ARCHIVE_DOC_KIND_LABELS 把 requirement 译作「**需求说明**」，其余三处均为「**需求文档**」；
- 追溯链（stage-panel.ts:88-93 traceNodeLabel）对 design 同类多份**裸显文件名**（architecture.md / interfaces.md）——用户 2026-09-22 点名要中文；
- 追溯链对 task_detail **折叠为「任务卡×N」**（stage-panel.ts:562-569）——用户要求节点文档逐张展示；
- toolviews 的 SUBMIT_KIND 缺 design/decomposition/task_detail，工具回执遇到这些 kind 直接显示英文枚举。

## 接口 / 数据契约（feature 档）

- **对外出口**：新增（或指定）唯一映射模块（建议 `src/client/artifact-labels.ts`），导出两个查询函数：
  - `artifactKindLabel(kind: string): string` —— 产物种类 → 中文名，未知 kind 返回「产物（原枚举值）」；
  - `docFileLabel(path: string, kind?: string): string` —— 文档路径 → 中文文档名（按 basename 命中文件名映射表；未命中返回「<kind中文>（<文件名>）」附注形态）。
  现有 4 处调用点全部改为 import；映射表本体随函数同址。render-summaries.ts 的 SUBMIT_KIND_CN 一并收敛。
- **数据契约**：无新增/变更字段；ArtifactKind 枚举、StageArtifact 形状、产物登记协议不变。任务卡名称从已有 StageDetail payload 的任务清单解析（StageTaskRef.title，经 artifact.path ↔ StageTaskRef.cardDoc 匹配），不新增后端字段。
- **迁移与兼容**：纯展示层行为变更，无数据迁移；未知 kind/文件名的显示形态变化（英文原文 → 中文兜底+附注）属预期变更，验收中显式核对。
- **可回滚**：单 commit 可 revert，无副作用面。

## 功能点（验收锚点）

### FR-1: 映射收敛为唯一事实源
4 处 kind 中文映射表 + render-summaries 的 SUBMIT_KIND_CN 收敛为一处定义、处处 import；`grep -rn "需求文档" agent-dh/packages/web/dsh-pmboard/src` 映射定义只剩一处。

### FR-2: 全链路术语一致且无英文裸显
追溯链 / 📁 文档记录 / 产物 chips / 工具回执 / 归档清单五处，同一 kind 显示同一中文名（归档 requirement 由「需求说明」统一为「需求文档」），任何区块不得出现英文枚举原文。

### FR-3: 未知值中文兜底 + 防再漂移
未知 kind 显示「产物（原枚举值）」；未知文件名显示「<kind中文>（<文件名>）」；配套防漂移机制（单测或类型约束）保证新增 kind / 新规范文件名未配中文名时被测试拦住。

### FR-4: 文件名级中文化（2026-09-22 用户补充）
追溯链与文档记录区的主标签不再裸显文件名：architecture.md→架构文档、interfaces.md→接口文档、data-model.md→数据模型、test-cases.md→测试用例、migration.md→迁移方案、requirement.md→需求文档、decomposition.md→拆分计划；文件名仍可从 tooltip / 路径列查得（排查线索不丢）。

### FR-5: 节点文档全展示（2026-09-22 用户补充）
追溯链覆盖节点全部已登记文档：design 每份产物各占一节（现有逐条行为保留，标签换中文）；任务卡**逐张列出且带任务名称**（「任务卡 · <任务名称>」，如「任务卡 · 新增 artifact-labels 映射模块」；名称匹配不到时降级「任务卡（t-xxx）」），不再折叠为「任务卡×N」；缺失必备产物的红字「（缺失）」行为保留不变。

## UI 原型（改造前/后对照）

[prototype.html](./prototype.html) —— 5 个受影响区块的改造前后像素级对照，黄色底纹 = 全部差异点；含统一映射表（kind 层 + 文件名层）终稿与验收核对清单。本次只改「显示名取值」一个变量，布局/图标/颜色/交互零变化。

## L4 批准闸门 + 下一步

- 本产物（requirement.md）经 reqboard_ask_confirm(target=artifact, kind=requirement) 人工确认后方可进入 design；
- **下一步：design** —— 设计文档落 docs/requirements/REQ-260922182638-0777/design/，同样经人工确认后才拆分。

## L5 产物清单

- 本文件：docs/requirements/REQ-260922182638-0777/requirement.md
- UI 原型：docs/requirements/REQ-260922182638-0777/prototype.html（改造前/后对照，应用户要求补齐；v2 同步文件名中文化与任务卡展开）

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已完成（有证据） | t-85eedd、t-3d33c3、t-67a5c9、t-86ae1e |
| FR-2 | ✅ 已完成（有证据） | t-3d33c3、t-67a5c9、t-86ae1e、t-9d9cf9 |
| FR-3 | ✅ 已完成（有证据） | t-85eedd、t-9d9cf9 |
| FR-4 | ✅ 已完成（有证据） | t-bdbab2 |
| FR-5 | ✅ 已完成（有证据） | t-bdbab2 |

> 无未接收条款（5 条全部有落点）。

<!-- reqboard:marks:end -->
