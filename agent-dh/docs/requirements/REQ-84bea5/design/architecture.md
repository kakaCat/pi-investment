---
requirement: REQ-84bea5
title: 架构设计
created: 2026-09-21
requirement_refs: [FR-1, FR-2, FR-3, FR-4]
---

# 修复「批准计划→自动开跑」断链 - 架构设计

> serves: FR-1, FR-2, FR-3, FR-4

## 1. 问题根因（架构层面）（serves: FR-1, FR-2）

**断链根因**：批准计划弹框的自动拆分/开跑链路有三处架构问题：

1. **事实源错配**：覆盖门禁（`assertClauseCoverageGate`）只从任务对象读 `requirement_refs`，而 plan 对象结构上不可能携带该字段（schema 无此键且 `additionalProperties: false`，`normalizePlanTasks` 会静默丢弃）—— **提交侧认文档、拆分侧认对象，两个口径不一致**。

2. **失败静默降级**：`AskConfirm.ts` 的 catch 把开跑失败吞成一句返回 note，无系统评论、无告警、`autoRun` 不置位 —— **看板控制面完全不出现，人无法发现失败也没有恢复入口**。

3. **假绿灯测试**：`tests/auto-chain-approval.test.ts` 的种子需求没有 requirement.md（`docs.exists` 短路），覆盖门禁根本不执行 —— **测试绿灯是假通过**。

## 2. 架构修复方案（serves: FR-1, FR-2, FR-3）

### 2.1 覆盖门禁双源合并（serves: FR-1）

**设计原则**：事实源统一到 decomposition.md RTM 表（与 Decompose.ts:168 注释的既有设计一致）。

**改动点**：
- 文件：`src/application/internal/content-gate-wiring.ts`
- 函数：`assertClauseCoverageGate`
- 逻辑：从"仅任务对象"改为"任务对象 ∪ decomposition.md RTM"

**架构约束**：
- RTM 表解析失败时返回空数组（不把"没记录"误判为"已覆盖"）
- 两个来源任一声明接收即算有落点（Set 去重取并集）
- 不改 `reqboard_submit` schema（plan 对象不是正源）
- 不改 TaskRecord 落库（绑定仍随 RTM 持久化）

### 2.2 失败响亮化架构（serves: FR-2）

**设计原则**：失败必须可观测、可恢复。

**三层响亮化**：
1. **台账层**：写系统评论（含失败原因与恢复路径）
2. **告警层**：调用 `deps.alert`（FailureAlert）发高优告警
3. **状态层**：在 `advance.pausedReason` 标记失败原因（区分手动模式与自动链失败）

**改动点**：
- 文件：`src/application/use-cases/AskConfirm.ts`
- 位置：自动拆分/开跑的 catch 路径（约 L295-299）
- 扩展：`RequirementRecord.advance` 新增 `pausedReason?: string`

**恢复路径**：
- 人修复问题后手动调用 `reqboard_decompose` + `reqboard_task_run`
- 看板控制面呈现失败状态（具体 UI 设计在前端实现阶段）

### 2.3 验收文档架构对齐（serves: FR-3）

**设计原则**：验收清单与最新流程一致（2026-09-21 裁定：拆分计划在拆分阶段写，不再生成 plan.md）。

**改动点**：
- 文件：`src/domain/workflow/DocCompleteness.ts`
- 删除：`VERIFICATION_DOC_CLASSES` 第 2 类 `plan.md（拆分计划）`
- 保留：第 7 类 `decomposition.md（拆分计划）`
- 清理：`RequirementStatus.ts` 注释、`_template/plan.md` 模板

**向后兼容**：
- 存量 34 个 plan.md 文件保留作档案
- 已交 plan.md 的存量需求不受影响（多出的文档无害）

## 3. 数据流与时序（serves: FR-1, FR-2）

### 3.1 正常流程（修复后）（serves: FR-1）

```
用户批准计划（reqboard_ask_confirm target=plan）
  ↓
AskConfirm 自动拆分/开跑
  ↓
assertClauseCoverageGate 检查覆盖
  ├─ 读任务对象 requirement_refs（兼容旧路径）
  ├─ 读 decomposition.md RTM 表（新增）
  └─ 两者取并集 → 与 requirement.md FR 条款比对
  ↓
覆盖通过 → reqboard_decompose 落库任务卡
  ↓
自动开跑子卡链（reqboard_task_run）
  ↓
需求状态推进到 implementing，advance.autoRun = true
```

### 3.2 失败流程（修复后）（serves: FR-2）

```
assertClauseCoverageGate 检查覆盖
  ↓
双源皆无 refs → 抛 requirement_uncovered
  ↓
catch 路径（修复后）：
  ├─ 写系统评论（失败原因 + 恢复指引）
  ├─ 调用 deps.alert（level: high）
  └─ 标记 advance.pausedReason
  ↓
返回给用户（note: "自动开跑失败..."）
  ↓
看板显示失败标记（有 pausedReason 且无 autoRun）
  ↓
人工修复后调用 reqboard_decompose 重试
```

## 4. 边界与约束（serves: FR-1, FR-2, FR-3）

1. **不改 refs 落库决策**：TaskRecord 不新增字段，绑定仍随 decomposition.md RTM 持久化
2. **不动自动链引擎本体**：AdvanceChain / ExecuteTask / WorkflowEngineRunner 语义不改
3. **存量 plan.md 不清理**：34 个历史文件保留作档案
4. **告警通道复用既有**：`deps.alert`（FailureAlert），不新建通知渠道

## 5. 依赖关系（serves: FR-4）

- FR-2（失败响亮化）依赖数据契约扩展（`pausedReason` 字段）
- FR-4（回归测试）依赖 FR-1/FR-2/FR-3 全部实现
- 其余任务无相互依赖，可并行实施

## 6. 风险与缓解（serves: FR-1, FR-2, FR-3, FR-4）

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| RTM 解析失败误判为"已覆盖" | 未覆盖的条款被放行 | 解析失败时返回空数组，门禁仍拒绝 |
| alert 接口未定义 | 编译失败 | 先实现 FailureAlert 占位或 mock |
| 测试环境依赖 | 种子需求需 mock 文件系统 | 使用 temp 目录创建真实文件 |
| 存量需求回归 | 已交 plan.md 的需求被误拒 | 验收门禁只移除"必交"要求，不删除已交文件 |