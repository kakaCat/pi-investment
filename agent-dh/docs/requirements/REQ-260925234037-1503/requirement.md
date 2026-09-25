# REQ-260925234037-1503：简化 REQ 流水线工具集，全面拥抱 Dive Armed 模式

> 需求类型：feature | 难度：expert | 状态：brainstorming

## 一句话目标

基于 REQ-260925212722-96e7 的 Dive Armed 自动模式，删除过时的手动工具，简化工具集，让 Agent 和用户全面使用自动流程，提升系统可维护性。

## 判定标准（可证伪）

1. ✓ 删除或废弃手动拆分/推进工具（reqboard_decompose/move/task_move）
2. ✓ 保留的工具提示词明确说明使用场景
3. ✓ Dive Armed 成为默认模式（新需求自动 armed）
4. ✓ 文档更新为 Dive-first 方案（工具频率表 + 最佳实践）
5. ✓ E2E 验证：完整需求流程无需手动工具

## 背景与问题

### 背景

REQ-260925212722-96e7 成功实现了 Dive Armed 自动续跑模式：
- ✓ 批准拆分计划后自动通过 jobs.start 后台拆分
- ✓ ReqboardDiveManager 自动续跑机制
- ✓ 父子卡模式自动执行子卡链
- ✓ 减少约 50%+ 手动工具调用

但自动模式与手动工具并存，导致：
- Agent 不知道该用哪个
- 工具集冗余（17个工具，实际只需要一半）
- 维护成本高（两套逻辑要保持一致）

### 用户反馈

用户明确要求：
1. **添加删除工具** - 删除过时的手动工具
2. **全面使用 Dive 方式** - 强制使用自动模式
3. **删除过时代码** - 清理手动模式的遗留代码

## 边界

### 做什么

1. **删除过时工具**（核心）
   - 删除 DecomposeTool/MoveTool/TaskMoveTool 及其代码
   - 删除对应的 use-case 层（Decompose.ts, MoveRequirement.ts, MoveTask.ts）
   - 删除工具注册和导出

2. **Dive Armed 唯一化**
   - reqboard_create/capture：移除 dive_mode 参数，固定为 armed
   - 系统提示词：说明 Dive Armed 是唯一工作方式
   - 配置清理：移除 disarmed 相关文档和示例

3. **保留的核心工具优化**
   - reqboard_task_run：强调这是执行入口
   - reqboard_clear_pause：说明紧急干预场景
   - reqboard_status：显示 dive 状态

4. **文档全面清理**
   - 删除所有手动模式文档
   - 删除 armed vs disarmed 对比
   - 只保留 Dive Armed 工作流程

5. **配置修复**
   - accepting.autoExecute: false → true（验收通过自动归档）

### 不做什么

1. 不改变 Dive 核心机制（已在 REQ-260925212722-96e7 实现）
2. 不删除 Dive 相关代码（task_run/clear_pause 等核心工具保留）
3. 不影响现有需求的 dive.activation 状态（已创建的保持不变）
### 边界之外

- 不涉及任务执行逻辑的改动
- 不涉及门禁规则的变更
- 不涉及验收流程的改动

## 功能点

### 用户与角色

- **Agent**：主要用户，使用简化后的工具集完成需求流程
- **人工用户**：监督者，在门禁点确认，必要时 clear_pause 干预
- **开发者**：维护 reqboard 代码的工程师

### 产品定义

简化后的 reqboard 工具集，以 Dive Armed 自动模式为默认，手动工具标记废弃或受限。

- **FR-1: 删除过时的手动工具**
  - 删除 reqboard_decompose 工具及其代码（DecomposeTool/）
  - 删除 reqboard_move 工具及其代码（MoveTool/）
  - 删除 reqboard_task_move 工具及其代码（TaskMoveTool/）
  - 删除对应的 use-case 层代码（Decompose.ts, MoveRequirement.ts, MoveTask.ts）
  - 删除工具注册代码（从 tools/index.ts 移除）
  - **不保留向后兼容**：Dive Armed 是唯一方式
- **FR-2: Dive Armed 默认化**
  - reqboard_create: 默认 dive.activation = 'armed'
  - reqboard_capture: 默认 dive.activation = 'armed'
  - 添加可选参数 dive_mode: 'armed' | 'disarmed'（向后兼容）
  - 系统提示词：引导优先使用 Dive Armed 模式

- **FR-3: 核心工具提示词优化**
  - reqboard_task_run: 强调这是 Dive Armed 的执行入口
  - reqboard_clear_pause: 说明 break glass 紧急场景
  - reqboard_status: 添加 dive 状态显示（armed/disarmed/phase/rounds）
  - reqboard_ask_confirm: 说明门禁点的作用

- **FR-4: 错误提示优化**
  - armed 锁错误：包含当前状态 + 推荐操作（等待/clear_pause）
  - 废弃工具调用：提示使用 task_run 替代
  - 工具不可用：说明何时可用（disarmed 模式）

- **FR-5: 文档全面更新**
  - dive-mode-usage.md: Dive-first 方案，删除手动模式章节
  - 工具使用频率表：高频（status/task_run/ask_confirm）、低频（clear_pause）、废弃（decompose/move/task_move）
  - armed vs disarmed 选择指南：默认 armed，仅调试用 disarmed
  - break glass 操作指南：何时需要 clear_pause

- **FR-6: accepting 阶段配置修复**
  - stage-configs.ts: accepting.autoExecute: false → true
  - 验收通过后自动归档，无需手动推进

## 验收标准


1. **代码层面**
   - reqboard_decompose/move/task_move 工具目录已删除（grep 验证不存在）
   - use-case 层对应代码已删除（Decompose.ts 等）
   - tools/index.ts 不再导出这些工具
   - accepting.autoExecute = true（grep 验证）
   - create/capture 默认 armed（代码审查）

2. **文档层面**
   - dive-mode-usage.md 为 Dive-first 方案，无手动模式说明
   - 工具列表不包含已删除工具
   - armed/disarmed 选择指南已删除（只有 armed）

3. **E2E 验证**
   - 创建新需求 → 自动 armed
   - 全流程无需手动工具（task_run + clear_pause 即可）
   - 验收通过后自动归档

4. **清理确认**
   - 无遗留的 decompose/move/task_move 引用
   - 单元测试已移除相关测试
   - 类型定义已更新


### 实施路径

1. **工具层**（packages/web/dsh-pmboard/src/tools/）
   - DecomposeTool/MoveTool/TaskMoveTool: 标记 DEPRECATED，添加 armed 检查
   - CreateTool/CaptureTool: 默认 armed，添加 dive_mode 参数
   - StatusTool: 添加 dive 状态显示
   - 提示词文件（prompt.ts）: 更新说明

2. **应用层**（packages/web/dsh-pmboard/src/application/）
   - use-cases/Decompose.ts: armed 检查 + 友好错误
   - use-cases/MoveRequirement.ts: armed 检查 + 友好错误
   - use-cases/MoveTask.ts: armed 检查 + 友好错误
   - dive/stage-configs.ts: accepting.autoExecute 改 true

3. **文档层**（docs/）
   - guides/dive-mode-usage.md: 重写为 Dive-first
   - guides/reqboard-workflow.md: 更新工具使用
   - architecture/reqboard-dive-mode.md: 补充废弃说明

### 风险与缓解

**风险1**: 现有 Agent 可能仍调用废弃工具
- **缓解**: 友好错误提示 + 系统提示词引导

**风险2**: 用户习惯手动模式
- **缓解**: 保留 disarmed 选项 + 文档说明

**风险3**: 特殊场景需要手动干预
- **缓解**: clear_pause + disarmed 模式仍可用

## 优先级

**高优先级** - 简化架构 + 提升可维护性

---

变更历史：
- 2026-09-25: 初始创建
- 2026-09-25: 根据用户反馈扩大范围，升级为重档（删除工具 + 全面 Dive）

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-354ea0、t-0c18e3、t-d29db5、t-4be897、t-26255f |
| FR-2 | ✅ 已完成（有证据） | t-26255f、t-6734bf |
| FR-3 | ✅ 已完成（有证据） | t-26255f |
| FR-4 | ✅ 已完成（有证据） | t-6734bf |
| FR-5 | ✅ 已接收 | t-2e885d |
| FR-6 | ✅ 已接收 | t-f0e25a、t-6734bf |

> 无未接收条款（6 条全部有落点）。

<!-- reqboard:marks:end -->
