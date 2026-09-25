# 架构设计

**需求**: REQ-260925234037-1503  
**版本**: 1.0  
**更新**: 2026-09-25



### 工具层架构变更 `serves: FR-1`


#### 删除的工具（FR-1） `serves: FR-1`

删除三个手动工具及其完整目录：

1. **DecomposeTool** (`packages/web/dsh-pmboard/src/tools/DecomposeTool/`)
   - 文件：index.ts, DecomposeTool.ts, prompt.ts
   - 功能：手动拆分需求到任务
   - 删除原因：已被 Dive Armed 自动拆分替代

2. **MoveTool** (`packages/web/dsh-pmboard/src/tools/MoveTool/`)
   - 文件：index.ts, MoveTool.ts, prompt.ts
   - 功能：手动推进需求状态
   - 删除原因：已被 DiveManager 自动推进替代

3. **TaskMoveTool** (`packages/web/dsh-pmboard/src/tools/TaskMoveTool/`)
   - 文件：index.ts, TaskMoveTool.ts, prompt.ts
   - 功能：手动推进任务状态
   - 删除原因：已被父子卡自动执行替代


#### 删除的 use-case 层 `serves: FR-1`

删除对应的业务逻辑文件：

1. **Decompose.ts** (`packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`)
   - 拆分需求逻辑
   - 依赖：RequirementRepository, TaskRepository

2. **MoveRequirement.ts** (`packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`)
   - 推进需求状态逻辑
   - 依赖：RequirementRepository

3. **MoveTask.ts** (`packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts`)
   - 推进任务状态逻辑
   - 依赖：TaskRepository


#### 工具注册变更 `serves: FR-1`

**文件**: `packages/web/dsh-pmboard/src/tools/index.ts`

删除导出：
```typescript
// 删除这些行
export { defineDecomposeTool } from './DecomposeTool/index.js'
export { defineMoveTool } from './MoveTool/index.js'
export { defineTaskMoveTool } from './TaskMoveTool/index.js'
```

保留的工具：
- CreateTool, CaptureTool, StatusTool
- SubmitTool, AskConfirmTool, ConfirmReceiptTool
- AcceptSheetTool, TaskExecuteTool (task_run), TaskReportTool
- AdvanceTool, RunStatusTool, TaskStatusTool
- NoteInterruptionTool, ClearPauseTool



### Dive Armed 默认化架构 `serves: FR-2`


#### CreateTool 变更 `serves: FR-1, FR-2`

**文件**: `packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts`

移除 `dive_mode` 参数，固定初始化为 armed：

```typescript
// 删除参数
parameters: {
  // 移除 dive_mode?: 'armed' | 'disarmed'
}

// 固定初始化
const requirement: Requirement = {
  // ...
  dive: {
    activation: 'armed',  // 固定值，不可选
    phase: 'idle',
    roundsInStage: 0
  }
}
```


#### CaptureTool 变更 `serves: FR-1, FR-2`

**文件**: `packages/web/dsh-pmboard/src/tools/CaptureTool/CaptureTool.ts`

同样移除 `dive_mode` 参数：

```typescript
// 立项弹框移除 dive_mode 问项
// 创建时固定 armed
```


### 依赖关系分析 `serves: FR-1, FR-2`


#### 被删除工具的影响范围 `serves: FR-1, FR-2`

1. **工具层依赖**（直接删除）：
   - 无其他工具依赖这三个工具
   - 工具间相互独立

2. **use-case 层依赖**（需清理）：
   - Decompose → RequirementRepository, TaskRepository
   - MoveRequirement → RequirementRepository
   - MoveTask → TaskRepository
   - 这些 Repository 被其他 use-case 使用，保留

3. **系统提示词引用**（需清理）：
   - 提示词中提到 reqboard_decompose 的地方
   - 提示词中提到 reqboard_move 的地方
   - 提示词中提到 reqboard_task_move 的地方

4. **文档引用**（需清理）：
   - dive-mode-usage.md 中的手动模式章节
   - reqboard-workflow.md 中的工具使用说明


### 架构图 `serves: FR-1, FR-2`


#### 删除前（17个工具） `serves: FR-1, FR-2`

```
Tools Layer (17)
├── 需求管理: create, capture, status, move (删), submit, ask_confirm
├── 拆分: decompose (删)
├── 任务管理: task_move (删), task_run, task_report, task_status
├── 执行控制: advance, run_status
├── 验收: accept_sheet
├── 辅助: confirm_receipt, note_interruption, clear_pause
```


#### 删除后（14个工具） `serves: FR-1, FR-2`

```
Tools Layer (14)
├── 需求管理: create, capture, status, submit, ask_confirm
├── 任务管理: task_run, task_report, task_status
├── 执行控制: advance, run_status
├── 验收: accept_sheet
├── 辅助: confirm_receipt, note_interruption, clear_pause
```


### 迁移策略 `serves: FR-1, FR-2`


#### 现有需求 `serves: FR-1, FR-2`

- 已创建的需求保持 dive.activation 不变
- disarmed 需求仍可正常工作
- 工具删除不影响现有需求数据


#### 新需求 `serves: FR-1, FR-2`

- 全部固定为 armed
- 无法创建 disarmed 需求
- 必须使用 Dive Armed 工作流程


### 回滚方案 `serves: FR-1, FR-2`

如果需要回滚：

1. **恢复工具代码**：从 git 历史恢复三个工具目录
2. **恢复 use-case**：恢复三个 use-case 文件
3. **恢复工具注册**：在 tools/index.ts 恢复导出
4. **恢复参数**：在 CreateTool/CaptureTool 恢复 dive_mode 参数

**回滚成本**：低（代码级回滚，无数据迁移）


### 风险评估 `serves: FR-1, FR-2`

1. **低风险**：工具删除不影响数据模型
2. **低风险**：现有需求不受影响
3. **中风险**：Agent 可能尝试调用已删除工具
   - 缓解：更新系统提示词
   - 缓解：工具调用失败会有明确错误

4. **低风险**：用户可能习惯手动模式
   - 缓解：Dive Armed 已验证可用
   - 缓解：clear_pause 提供紧急干预