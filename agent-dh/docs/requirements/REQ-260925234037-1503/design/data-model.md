# 数据模型设计

**需求**: REQ-260925234037-1503  
**版本**: 1.0  
**更新**: 2026-09-25



### Requirement 数据模型 `serves: FR-2`


#### dive 字段（不变） `serves: FR-2`

本次变更**不修改**数据模型，只改变创建时的默认值。

**类型定义**（保持不变）：
```typescript
interface RequirementDive {
  /** 自动流程开关：armed（启用）/ disarmed（禁用） */
  activation: 'armed' | 'disarmed'
  
  /** 执行阶段：idle（空闲）/ active（进行中）/ paused（暂停） */
  phase: 'idle' | 'active' | 'paused'
  
  /** 当前阶段的续跑回合数 */
  roundsInStage: number
  
  /** 暂停原因（仅 phase=paused 时有值） */
  pausedReason?: string
}

interface Requirement {
  id: string
  title: string
  category: 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore'
  status: RequirementStatus
  dive: RequirementDive  // Dive 状态
  // ... 其他字段
}
```


#### 创建时默认值变更 `serves: FR-2`

**修改前**：
```typescript
// CreateTool / CaptureTool
const requirement: Requirement = {
  // ...
  dive: {
    activation: dive_mode || 'armed',  // 可选，默认 armed
    phase: 'idle',
    roundsInStage: 0
  }
}
```

**修改后**：
```typescript
// CreateTool / CaptureTool
const requirement: Requirement = {
  // ...
  dive: {
    activation: 'armed',  // 固定值，移除参数
    phase: 'idle',
    roundsInStage: 0
  }
}
```



### StageConfig 数据模型 `serves: FR-6`


#### 配置结构（不变） `serves: FR-1, FR-2`

```typescript
interface StageConfig {
  /** 是否需要人工确认才能推进到下一阶段 */
  requiresConfirmation: boolean
  
  /** 是否自动执行任务（implementing 阶段适用） */
  autoExecute: boolean
  
  /** 每阶段最大回合数限制（防止无限循环） */
  maxRounds: number
  
  /** 阶段描述 */
  description: string
}
```


#### accepting 阶段配置变更 `serves: FR-6`

**修改前**：
```typescript
{
  requiresConfirmation: true,
  autoExecute: false,  // ← Bug：验收通过后不自动归档
  maxRounds: 5,
  description: '验收阶段，需人工验收'
}
```

**修改后**：
```typescript
{
  requiresConfirmation: true,
  autoExecute: true,   // ← 修复：验收通过后自动归档
  maxRounds: 5,
  description: '验收阶段，需人工验收，通过后自动归档'
}
```

## 数据迁移 <!-- serves: FR-1, FR-2 -->


### 无需迁移 `serves: FR-1, FR-2`

本次变更**不需要数据迁移**：

1. **dive 字段结构不变**
   - 类型定义保持不变
   - 现有数据完全兼容
   
2. **只改变新建行为**
   - 现有需求的 dive.activation 保持不变
   - disarmed 需求继续正常工作
   
3. **配置变更即时生效**
   - StageConfig 是代码配置
   - 重启后立即生效
   - 不影响现有需求


### 数据完整性 `serves: FR-1, FR-2`


#### 约束条件（不变） `serves: FR-1, FR-2`

```typescript
// dive.activation 的可选值
type Activation = 'armed' | 'disarmed'

// dive.phase 的可选值
type Phase = 'idle' | 'active' | 'paused'

// roundsInStage 的约束
roundsInStage >= 0

// pausedReason 的约束
if (phase === 'paused') {
  pausedReason !== undefined
} else {
  pausedReason === undefined
}
```


#### 数据验证（保持不变） `serves: FR-1, FR-2`

现有的数据验证逻辑无需修改：

```typescript
function validateRequirementDive(dive: RequirementDive): boolean {
  // 验证 activation
  if (!['armed', 'disarmed'].includes(dive.activation)) {
    return false
  }
  
  // 验证 phase
  if (!['idle', 'active', 'paused'].includes(dive.phase)) {
    return false
  }
  
  // 验证 roundsInStage
  if (dive.roundsInStage < 0) {
    return false
  }
  
  // 验证 pausedReason
  if (dive.phase === 'paused' && !dive.pausedReason) {
    return false
  }
  if (dive.phase !== 'paused' && dive.pausedReason) {
    return false
  }
  
  return true
}
```

## 数据库影响 <!-- serves: FR-1, FR-6 -->


### 无影响 `serves: FR-1, FR-2`

本次变更**不影响数据库**：

1. **表结构不变**
   - requirements 表结构保持不变
   - dive 字段 JSON 结构不变
   
2. **索引不变**
   - 无需新增索引
   - 现有索引继续有效
   
3. **查询不变**
   - 现有查询逻辑无需修改
   - 性能特征保持不变

## 状态转换图 <!-- serves: FR-2 -->


### Dive 状态机（不变） `serves: FR-1, FR-2`

```
┌──────────────────────────────────────────┐
│          Requirement Created             │
│     dive.activation = 'armed'            │
│     dive.phase = 'idle'                  │
└──────────────────┬───────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │   phase: idle   │
         └────────┬─────────┘
                  │
                  │ DiveManager 检测到续跑条件
                  ▼
         ┌─────────────────┐
         │  phase: active  │◄────────┐
         └────────┬─────────┘         │
                  │                   │
                  │ 续跑完成          │
                  ▼                   │
         ┌─────────────────┐         │
         │   phase: idle   │─────────┘
         └────────┬─────────┘
                  │
                  │ 触发暂停条件（错误/达到 maxRounds）
                  ▼
         ┌─────────────────┐
         │  phase: paused  │
         │  + pausedReason │
         └────────┬─────────┘
                  │
                  │ clear_pause
                  ▼
         ┌─────────────────┐
         │   phase: idle   │
         └─────────────────┘
```


### activation 的作用 `serves: FR-1, FR-2`

```
activation: 'armed'    → DiveManager 自动续跑
activation: 'disarmed' → DiveManager 跳过（不再新创建）
```

## 数据示例 <!-- serves: FR-2 -->


### 新建需求（固定 armed） `serves: FR-1, FR-2`

```json
{
  "id": "REQ-260925234037-1503",
  "title": "简化 REQ 流水线工具集",
  "category": "feature",
  "status": "brainstorming",
  "dive": {
    "activation": "armed",
    "phase": "idle",
    "roundsInStage": 0
  }
}
```


### 旧需求（保持 disarmed） `serves: FR-1, FR-2`

```json
{
  "id": "REQ-older-requirement",
  "title": "某个旧需求",
  "category": "feature",
  "status": "design",
  "dive": {
    "activation": "disarmed",  // 保持不变
    "phase": "idle",
    "roundsInStage": 0
  }
}
```


### 暂停状态 `serves: FR-1, FR-2`

```json
{
  "id": "REQ-some-requirement",
  "title": "某个需求",
  "dive": {
    "activation": "armed",
    "phase": "paused",
    "roundsInStage": 10,
    "pausedReason": "达到最大回合数限制 (maxRounds=10)"
  }
}
```

## 回滚影响 <!-- serves: FR-1, FR-2, FR-6 -->


### 数据兼容性 `serves: FR-1, FR-2`

回滚代码后：
- ✅ 所有 armed 需求继续正常工作
- ✅ 可以重新创建 disarmed 需求
- ✅ 无数据损坏风险


### 回滚步骤 `serves: FR-1, FR-2`

1. 恢复代码（git revert）
2. 重启服务
3. 无需数据迁移或修复

**回滚成本**：低（纯代码级回滚）