---
req_id: REQ-d3e61a
stage: planning
kind: 技术设计文档集
status: pending_approval
owner: w-e1fc9bb5
created: 2026-09-18
---

# REQ-d3e61a 技术设计文档集（planning 阶段产物）

> **本阶段只回答「怎么做」。** 任务 DAG 与"分几步、每步完成什么"属 **decomposing 阶段**的
> 拆分文档（decomposition.md）——本文件**不写工序**（见 §7）。

## 1. 目标（一句话）

把**文档标准**落成**插件里的文档校验**：插件在每个节点按标准核对文档**正文**，
不达标即拦——让"需求写了但没做"在**拆分那一刻**被拦下。

## 2. 挂载点（已对真实代码核实）

| 落点 | 真实文件 | 现状 | 改动 |
|------|---------|------|------|
| 门禁 | packages/pages/dsh-pmboard/src/application/internal/artifact-gates.ts | 已有两级闸门（missing_artifact / artifact_not_confirmed），**只查登记状态、不读正文** | **加第三级**：内容校验 |
| 内容校验 | .../src/application/internal/content-gates.ts（新增） | 不存在 | 纯函数：条款覆盖 / 编号串联 / 验收四件套 / E2E |
| 提示词 | .../src/domain/prompt/fragments/... + router.ts | 已有 5 阶段 × 7 分类 × 2 难度 + priority:'floor' 机制 | 加 4 个 **floor** 分片（不改路由） |
| 分类档案 | CATEGORY_FLOW_PROFILES | 仅 stage 单维 | 扩为「文档集 + 门禁 + 提示词 + 根前缀」四维 |
| 标准文档 | agent-dh/docs/architecture/documentation-standard.md | 已产出草案 | 定稿 + 被门禁引用 |

## 3. 关键设计决策

1. **加第三级，不改前两级**——现有 missing_artifact / artifact_not_confirmed 语义与测试完全不动（非功能：不改状态机）。
2. **纯函数 + IO 分离**——content-gates.ts 只接收字符串、返回缺口清单，不碰文件系统 → 单测便宜、可被 Dashboard 复用。
3. **豁免复用既有语义**——存量需求 isLegacy（artifacts 为空）**不硬拦**，不新造豁免参数。
4. **标准唯一事实源**——门禁与提示词**引用**标准文档的语义，不复制内容（FR-13）。
5. **阶段不越层**——本阶段只出技术设计；任务 DAG 交 decomposing（§7）。

## 4. 设计文档索引

| 文档 | 内容 | serves |
|------|------|--------|
| `design/architecture.md` | 三级门禁架构、模块划分、floor 分片 | FR-12, FR-13 |
| `design/data-model.md` | 编号模型、校验结果、三方一致性模型（无新增表） | FR-2, FR-4, FR-9 |
| `design/interfaces.md` | 函数签名、错误码、工具参数变更、前后端协作 | FR-1, FR-6, FR-10, FR-12 |
| `design/ui.md` | 基本无 UI 交付（显式声明 3 处变更） | FR-3, FR-7, FR-9 |
| `design/test-cases.md` | 8 单元 + 4 集成 + **2 E2E** | FR-11 |
| `design/migration.md` | 存量豁免、灰度、回滚（无 DB 迁移） | FR-12, FR-13 |

## 5. 风险

| 风险 | 缓解 |
|------|------|
| 闸门太严 → 频繁拦截 | MVP 先上 2 道（覆盖门禁 / 编号串联），观察 1–2 周拦截率与误报率再加 |
| 存量需求上线即全红 | 复用 isLegacy 不硬拦；只警告 |
| **接线冲突** | dsh-pmboard 正被另一窗口改（实测 526 文件：498 未跟踪 + 28 已修改；分支 agent-self/20260917-232700）→ **等其落地后开独立 worktree** |
| 校验开销 | 文档解析为本地字符串处理，单次 < 1s（非功能要求） |

## 6. 开工前置条件（不满足不开工）

1. 技术设计文档集获人工批准；
2. dsh-pmboard 的并行改动落地、工作区回到可安全开 worktree 的状态；
3. 三个 [TBD] 清零（编号前缀与既有 t-xxxxxx 共存 / 豁免判定字段 / 批次顺序确认）。

## 7. 本阶段**不**产出什么（越层禁止）

| 不产出 | 归哪个阶段 | 为什么 |
|--------|-----------|--------|
| 任务编号表 / 依赖 DAG / "分几步" / 每步完成什么 | **decomposing** | 那是拆分文档的职责；写在设计里会让"缺失在哪一层"无法判定 |

> 提审时随本文件附带的**任务表**（18 项）是**审批用的将来任务表**——
> 它的文档落点是 decomposing 阶段的 `decomposition.md`，不是本文档的一部分。
