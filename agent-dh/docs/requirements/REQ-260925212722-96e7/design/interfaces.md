# 接口设计

## 核心接口

### RequirementDive 接口

```typescript
interface RequirementDive {
  /** 当前所处阶段（与 RequirementStatus 对应） */
  phase: 'brainstorming' | 'design' | 'decomposing' | 'implementing' | 'accepting'
  
  /** 激活状态：armed=自动续跑启用，disarmed=手动模式 */
  activation: 'armed' | 'disarmed'
  
  /** 当前阶段已执行的回合数 */
  roundsInStage: number
  
  /** 每阶段最大回合数限制（防止无限循环） */
  maxRoundsPerStage: number
  
  /** 当前子阶段（如 implementing 中的具体任务） */
  currentStage?: string
  
  /** 暂停原因（阻塞时记录，clear_pause 清除） */
  pausedReason?: string
  
  /** 最后活跃时间（Unix 时间戳 ms） */
  lastActiveAt?: number
}
```

### GateResult 接口

```typescript
interface GateResult {
  passed: boolean
  code?: string
  message?: string
  gaps?: string[]
  orphan_clauses?: string[]
  failed_clauses?: Array<{ id: string; status: string }>
}
```

### StageConfig 接口

```typescript
interface StageConfig {
  requiresConfirmation: boolean  // 是否需要用户确认
  autoExecute: boolean           // 确认后是否自动续跑
  maxRounds: number              // 该阶段最大回合数
  description?: string           // 阶段说明
}
```

## 用例接口

### ReqboardDiveManager

```typescript
class ReqboardDiveManager {
  /**
   * 检查需求是否处于 Dive 模式并需要续跑
   * @param agentId Agent ID
   * @param requirementId 需求 ID（可选）
   * @returns 是否发起了续跑
   */
  async checkAndContinue(agentId: string, requirementId?: string): Promise<boolean>
  
  /**
   * 检查需求是否应该续跑
   * @param requirement 需求对象
   * @returns 是否应该续跑
   */
  private shouldContinue(requirement: Requirement): boolean
}
```

### 门禁接口

```typescript
/**
 * 设计门禁：检查 FR 设计覆盖度
 */
async function checkDesignGate(requirement: Requirement): Promise<GateResult>

/**
 * 任务覆盖门禁：检查 FR 任务接收度
 */
async function checkTaskCoverageGate(requirement: Requirement): Promise<GateResult>

/**
 * 验收门禁：检查 FR 验收完成度
 */
async function checkAcceptanceGate(requirement: Requirement): Promise<GateResult>
```

## 工具接口

### reqboard_clear_pause

```typescript
interface ClearPauseArgs {
  requirement_id?: string  // 需求 ID（可选，默认当前窗口绑定的需求）
}

interface ClearPauseResult {
  success: boolean
  requirement_id: string
  cleared: {
    pausedReason?: string
    disarmed: boolean
  }
  message: string
}
```

## 接口变更兼容性

- RequirementDive 作为可选字段添加到 Requirement，保持向后兼容
- 所有门禁接口返回统一的 GateResult 格式
- 用例接口保持现有签名不变，内部增加 armed 检查逻辑
