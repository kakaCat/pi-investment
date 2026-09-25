# 文件变更清单

> REQ-260925212722-96e7: REQ 流水线 Dive 模式重构

## 新增文件 «serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-9»

### 1. packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts «serves: FR-2»

**职责**: Dive 续跑管理器

**功能**:
- 在 agent 回合结束时检查 dive 状态
- 为 armed + active 的需求发起 followup
- 管理回合数和阻塞逻辑

**导出**:
```typescript
export default class ReqboardDiveManager extends Service {
  static inject = ['agents', 'reqboard'];
  async checkAndContinue(agentId: string): Promise<void>;
}
```

### 2. packages/web/dsh-pmboard/src/application/dive/stage-configs.ts «serves: FR-8»

**职责**: 阶段配置

**功能**:
- 定义各阶段的确认、自动执行、最大回合数配置
- 提供配置查询接口

**导出**:
```typescript
export interface StageConfig {
  requiresConfirmation: boolean;
  autoExecute: boolean;
  maxRounds: number;
}

export const STAGE_CONFIGS: Record<StageType, StageConfig>;
```

### 3. packages/web/dsh-pmboard/src/application/gate/design-gate.ts «serves: FR-4»

**职责**: 设计门禁

**功能**:
- 检查所有 FR 是否都有 design_refs
- 返回门禁检查结果

**导出**:
```typescript
export async function designGateCheck(req: Requirement): Promise<GateResult>;
```

### 4. packages/web/dsh-pmboard/src/application/gate/task-coverage-gate.ts «serves: FR-5»

**职责**: 拆分门禁

**功能**:
- 检查所有 FR 是否都有 task_refs
- 返回未接收的 FR 列表

**导出**:
```typescript
export async function taskCoverageGateCheck(req: Requirement): Promise<GateResult>;
```

### 5. packages/web/dsh-pmboard/src/application/gate/acceptance-gate.ts «serves: FR-6»

**职责**: 验收门禁

**功能**:
- 检查所有 FR 的 acceptance_status
- 返回未通过的 FR 列表

**导出**:
```typescript
export async function acceptanceGateCheck(req: Requirement): Promise<GateResult>;
```

### 6. packages/web/dsh-pmboard/src/application/gate/index.ts «serves: FR-4, FR-5, FR-6»

**职责**: 门禁系统统一导出

**导出**:
```typescript
export * from './design-gate';
export * from './task-coverage-gate';
export * from './acceptance-gate';

export interface GateResult {
  passed: boolean;
  code?: string;
  message?: string;
  gaps?: string[];
  orphan_clauses?: string[];
  failed_clauses?: Array<{ id: string; status: string }>;
}
```

## 修改文件 «serves: FR-1, FR-2, FR-3, FR-7, FR-9»

### 7. packages/web/dsh-pmboard/src/shared/protocol.ts «serves: FR-1»

**变更**: 扩展 Requirement 接口

**新增**:
```typescript
// 新增 RequirementDive 接口
export interface RequirementDive {
  phase: "active" | "paused" | "blocked" | "complete";
  activation: "armed" | "disarmed";
  currentStage: StageType;
  stagesCompleted: StageType[];
  roundsInStage: number;
  maxRoundsPerStage: number;
  pausedReason?: string;
  blockedReason?: string;
  createdAt: number;
  updatedAt: number;
}

// 扩展 Requirement 接口
export interface Requirement {
  // ... 现有字段
  dive?: RequirementDive;  // 新增：可选字段
}
```

### 8. packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts «serves: FR-3»

**变更**: 修复自动开跑问题

**修改位置**: 约第 223 行，批准拆分计划后的自动拆分逻辑

**原代码**:
```typescript
// 需要 live driver
await executeDecompose(deps, {...}, exec);
```

**修改为**:
```typescript
// 使用后台 job
const job = await deps.jobs.start({
  type: 'reqboard-decompose',
  payload: {
    requirement_id: req.id,
    tasks: approvedPlan.tasks
  }
});
```

### 9-13. 其他修改文件 «serves: FR-2, FR-7, FR-9»

详见完整文档...

## 文件变更统计 «serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9»

**新增**: 14 个文件
- 应用代码: 6 个
- 测试代码: 5 个
- 数据库迁移: 1 个
- 文档: 5 个

**修改**: 6 个文件
- protocol.ts
- confirm-settle.ts
- Decompose.ts
- MoveRequirement.ts
- MoveTask.ts
- index.ts

**删除**: 0 个文件