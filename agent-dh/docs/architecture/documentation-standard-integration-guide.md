---
title: 文档规范融入插件实施指南
version: 2.0
status: draft
owner: REQ-d3e61a
created: 2026-09-18
related_doc: documentation-standard.md
note: v2 已按 dsh-pmboard 真实代码核实挂载点；v1 中的 gates/、prompt-injection.ts、templates/ 路径为推想，不存在
---

# 文档规范融入插件实施指南（v2 · 对齐真实代码）

**前置**：documentation-standard.md 定义六类文档「写什么、什么格式」。
**本文**：把这些要求落到 dsh-pmboard 的**具体文件**，说清哪些已有、哪些要新增、哪些不该做。

---

## 0. 挂载点总览（已核实）

| 规范层 | 真实挂载点 | 现状 | 要做的事 |
|--------|-----------|------|---------|
| 门禁层 | src/application/internal/artifact-gates.ts | 已有两级闸门，**只查状态不查内容** | 扩展第三级：内容闸门 |
| 提示词层 | src/domain/prompt/fragments/ + router.ts + types.ts | 已有 5 阶段 × 7 分类 × 2 难度分片，floor 机制在位 | 新增 4 个 floor 分片 |
| 模板层 | 无 templates 目录 | 产物由 agent 写、SubmitTool 登记 | **建议不做**（见 §3） |
| 可观测层 | src/client/views/ + src/client/render/ | 已有需求详情/看板视图 | 后置 |

---

## 1. 门禁层 — 扩展 assertArtifactGates

### 1.1 现有机制（真实签名）

```
export function assertArtifactGates(
  req: RequirementRecord,
  from: RequirementStatus,
  to: RequirementStatus,
): GateFailure | undefined

export interface GateFailure {
  code: 'missing_artifact' | 'artifact_not_confirmed'
  kind: ArtifactKind
  message: string
}
```

调用时机（源码注释原话）：**在 assertReqTransition 之后、真正写盘之前**。

现有两级：
- ① missing_artifact — 该分类该阶段的必备产物是否已登记
- ② artifact_not_confirmed — 对应 kind 的产物是否经人确认（confirmedAt）

分类感知：CATEGORY_FLOW_PROFILES 过滤该分类生效的门（bug 免需求门，spike/doc/chore 只保留验收+归档门）。
**存量需求（artifacts 为空）不硬拦，只标记** —— 这就是现成的豁免期机制。

### 1.2 关键认知：现有闸门不读文档内容

现有两级查的都是**登记状态**（登记了没有 / 确认了没有）。
规范要求的 M 类闸门查的是**文档正文**（条款有没有被覆盖 / 章节有没有 serves 标注）。
两者正交 → 作为**第三级**加入，不替换现有逻辑。

### 1.3 扩展设计

```
export type GateFailure = {
  code:
    | 'missing_artifact'      // 现有①
    | 'artifact_not_confirmed' // 现有②
    | 'requirement_uncovered'  // 新：R# 无任务覆盖
    | 'design_orphan'          // 新：设计章节无 serves: R#
    | 'tbd_not_cleared'         // 新：实施前仍存 [TBD]
    | 'no_e2e_case'             // 新：测试策略缺 E2E 层级
  kind: ArtifactKind
  message: string
  /** 新：结构化缺口清单，供 agent 精确修复与 UI 标红 */
  gaps?: string[]
}
```

新闸门挂在哪一道门：

| 新闸门 | 触发阶段（from） | 说明 |
|--------|-----------------|------|
| no_e2e_case | brainstorming | requirement.md §5 无 E2E 行 |
| design_orphan | planning | design/*.md 有章节缺 serves: R# |
| requirement_uncovered | planning | R# 无任务覆盖且在分解表未标「本轮不做」 |
| tbd_not_cleared | planning→decomposing | 复用既有 planApproved 那道门的挂载点 |

任务级闸门（任务卡无 requirement_refs / 验收不可执行）挂在 **src/application/use-cases/MoveTask.ts**，
不属 artifact-gates。

### 1.4 新增文件：content-gates.ts

把「读文档 → 判定」做成**纯函数**，与 IO 解耦，单测便宜：

```
// src/application/internal/content-gates.ts（新增）
export function checkRequirementCoverage(reqMd: string, taskCards: string[]): { gaps: string[] }
export function checkDesignTraceability(designDocs: string[], reqIds: string[]): { orphans: string[] }
export function checkTbdClearance(docs: string[]): { items: string[] }
export function checkE2ECoverage(reqMd: string): { hasE2E: boolean }
```

由 artifact-gates.ts 在第三级调用，读文件由调用方传入字符串（沿用 capture-section.ts / ArtifactSync.ts 已有的读档路径）。

---

## 2. 提示词层 — 加 floor 分片（不改 router）

### 2.1 现有机制（真实）

- router.ts 按 (stage, difficulty, category) 选分片，5 级回退
- types.ts：Difficulty = 'light' | 'heavy'，DEFAULT_DIFFICULTY = 'light'
- types.ts 第 53 行注释原话：priority='floor' = 清单/闸门/红旗这类**保底件**，预算裁剪永不触碰
- common/iron-rules.md 已是 floor 保底件

### 2.2 做法：只加文件，不动机制

规范里「每类文档必填节」的硬结构，写成 floor 分片挂到对应阶段：

| 新增分片 | 内容 |
|---------|------|
| brainstorming/doc-standard.md | 需求文档六节必填（问题三要素 / R 清单 / 边界 / 可证伪标准 / 测试策略含 E2E / [TBD]） |
| planning/design-traceability.md | 每节必须标 **serves: R#**；接口契约表必填列 |
| decomposing/rtm-table.md | 覆盖对照表格式（需求条款 → 任务卡 → 设计章节 → 用例） |
| implementing/task-card-contract.md | 任务卡 = 提示词：requirement_refs 必填、实施方案给文件路径、验收给可执行命令 |

**为什么是 floor**：规范是保底件，不能被 token 预算裁掉 —— 正好匹配既有语义，不需要新机制。

---

## 3. 模板层 — 建议不做（诚实结论）

仓库**没有** templates 目录；产物由 agent 自己写，经 SubmitTool / capture-section.ts 登记。

「从模板填空」是新增能力，且与「agent 自己写文档」的现有范式存在张力。建议先不做，理由：
1. M 类闸门已能保证「缺节被拦」——模板只是省事，不是正确性来源；
2. 没有证据表明 agent 卡在「不知道写什么」（卡的是「不知道要写什么才算覆盖」→ 那是闸门+提示词的活）；
3. 过早固定模板会抑制特殊需求的表达。

这属于规范 §10 的 future tooling，等闸门跑 1-2 周、看清真实卡点再定。

---

## 4. 可观测层 — 复用现有 client，后置

src/client/views/ 已有需求详情与看板视图。「追溯视图」= 解析 decomposition.md 的覆盖表后渲染，
数据源是 content-gates 的同一批纯函数（reportMode 下不抛错、只返回缺口）。可后置到闸门稳定之后。

---

## 5. 落地顺序

1. content-gates.ts 纯函数 + 单测（零副作用，风险最低，可先做）
2. 接入 assertArtifactGates 第三级（存量需求 isLegacy 不硬拦 = 天然豁免期，无需另造 exemptionDate 参数）
3. 4 个 floor 分片
4. 观察 1-2 周拦截率/误报率，再决定模板层与可观测层

---

## 6. 与既有闸门的对应关系（不重复造）

| 规范要求 | 已有实现 | 结论 |
|---------|---------|------|
| 节点产物就位 | missing_artifact | 复用 |
| 人工确认批准 | artifact_not_confirmed | 复用 |
| 计划已批准 | planApproved | 复用 |
| 分类差异（bug 免需求门等） | CATEGORY_FLOW_PROFILES | 复用 |
| 存量需求豁免 | isLegacy 不硬拦 | 复用 |
| 条款覆盖 / 设计追溯 / TBD 清零 / E2E 存在 | 无 | **新增（4 项）** |

结论：规范的增量只有 4 个**内容闸门** + 4 个 floor 分片，其余全部复用既有机制。

---

## 7. 风险

| 风险 | 缓解 |
|------|------|
| 接线冲突：dsh-pmboard 正被另一窗口改动 | 等其落地后再开工，不并行改同一包 |
| 闸门太严 → 频繁拦截 | 先上 2 个（coverage / design_orphan），观察 1-2 周 |
| 存量需求不合规 | isLegacy 不硬拦已提供豁免，无需另造参数 |

---

**最后更新**：2026-09-18  **所属需求**：REQ-d3e61a  **状态**：draft（待批准）
