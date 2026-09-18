---
req_id: REQ-d3e61a
kind: design-architecture
owner: w-e1fc9bb5
created: 2026-09-18
---

# 架构设计（serves: FR-12, FR-13）

## D-ARCH-1 三级门禁架构 `serves: FR-12`

现状（已核实 artifact-gates.ts）只有两级，**都查登记状态、不读正文**：

| 级 | 代码 | 查什么 | 本次改动 |
|----|------|--------|---------|
| ① | missing_artifact | 该阶段必备产物**登记了没有** | **不动** |
| ② | artifact_not_confirmed | 对应产物**人确认了没有** | **不动** |
| ③ | **新增**：内容校验 | 文档**正文**是否达标（覆盖/编号/四件套/E2E） | 新增 |

**为什么不改造 ①②**：它们语义清晰、有既有测试覆盖；内容校验与登记校验正交，
混在一起会让"为什么被拒"变模糊（GateFailure.code 需要能区分）。

## D-ARCH-2 模块划分 `serves: FR-12`

```
application/internal/
  artifact-gates.ts        ← 现有，加第三级调用（唯一改动点）
  content-gates.ts         ← 新增：纯函数，无 IO
    ├─ parseDocument(text)         → { clauses, sections, tables, frontmatter }
    ├─ checkClauseCoverage(...)    → { gaps }        (FR-1)
    ├─ checkNumberChain(...)       → { dangling, orphans } (FR-2)
    ├─ checkAcceptanceKit(...)     → { missing }     (FR-10)
    └─ checkE2ECoverage(...)       → { hasE2E }      (FR-11)
```

**边界**：content-gates.ts **不碰文件系统**——读文档由调用方完成（沿用既有
capture-section.ts / ArtifactSync.ts 的读档路径），把字符串传进来。
好处：单测无需 mock fs；同一个函数可被 Dashboard 复用（reportMode：只报不抛）。

## D-ARCH-3 为什么纯函数 `serves: FR-12`

| 理由 | 说明 |
|------|------|
| 可测 | 边界（空文档 / 无编号 / 悬空引用 / 表格残缺）用字符串直接构造 |
| 可复用 | 门禁（拦）+ Dashboard（报）读同一份判定 |
| 无副作用 | 校验动作不改任何状态（对齐非功能：不改状态机） |

## D-ARCH-4 提示词侧架构 `serves: FR-13`

**不改路由**（router.ts 按 (stage, difficulty, category) 五级回退的机制保留），
只**新增 4 个 floor 分片**：

| 新增分片 | 定义「写什么」 | serves |
|---------|--------------|--------|
| brainstorming/doc-standard.md | 需求文档必填节（PRD 体例） | FR-13 |
| planning/design-traceability.md | 每节须标 serves: 编号 | FR-5 |
| decomposing/rtm-table.md | 覆盖对照表 + 每步可观察产出 | FR-1, FR-12 |
| implementing/task-card-contract.md | 任务卡 = agent 提示词的自足契约 | FR-6, FR-10 |

## D-ARCH-5 分类档案（四维） `serves: FR-15`

`CATEGORY_FLOW_PROFILES` 由「stage 单维」扩为**四维**：

| 维 | 内容 | 消费方 |
|----|------|--------|
| `requiredDocs` | 该类型要哪些文档（✅/⚪/❌ 矩阵） | 门禁 |
| `gates` | 该类型生效哪些校验 | 门禁 |
| `fragments` | 该类型注入哪些提示词分片 | 提示词 |
| `rootPrefix` | 根编号前缀（FR- / BUG- / RF- / SP- / DOC- / CH-） | 编号解析 |

**BASE + DELTA 两层**：共同骨架只定义一次，类型专属增量挂 profile——**新增类型只加一条 profile**。

**为什么用 priority:'floor'（D-ARCH-4 续）**：types.ts 注释已定义 floor = "清单/闸门/红旗这类保底件，
预算裁剪永不触碰"——规范的硬结构正是这个语义，**不需要新机制**。
