# 数据模型设计

> REQ-260925212722-96e7: REQ 流水线 Dive 模式重构

## RequirementDive 接口 «serves: FR-1, FR-8»

### 数据结构 «serves: FR-8»

```typescript
interface RequirementDive {
  // 核心状态
  phase: "active" | "paused" | "blocked" | "complete";
  activation: "armed" | "disarmed";
  
  // 阶段管理
  currentStage: StageType;  // brainstorming | design | decomposing | implementing | accepting
  stagesCompleted: StageType[];
  
  // 回合控制
  roundsInStage: number;
  maxRoundsPerStage: number;
  
  // 失败控制
  pausedReason?: string;
  blockedReason?: string;
  
  // 元数据
  createdAt: number;
  updatedAt: number;
}

type StageType = 
  | "brainstorming"
  | "design"
  | "decomposing"
  | "implementing"
  | "accepting"
  | "archived";
```

### 字段说明 «serves: FR-1»

**phase** - Dive 生命周期阶段
- `active`: 正常运行中，可以自动续跑
- `paused`: 暂停，需要用户干预
- `blocked`: 阻塞，连续失败超过阈值
- `complete`: 完成，需求已归档

**activation** - 锁定状态
- `armed`: 锁定，启用自动流程，禁止手动工具
- `disarmed`: 解锁，允许手动操作

**currentStage** - 当前所在阶段
- 对应需求的 status 字段
- 用于确定下一步应该做什么

**stagesCompleted** - 已完成的阶段列表
- 用于防止重复执行
- 用于恢复续跑时的上下文

**roundsInStage** - 当前阶段已执行的回合数
- 每次 followup 递增
- 达到 maxRoundsPerStage 时进入 blocked

**maxRoundsPerStage** - 当前阶段最大回合数
- 从 STAGE_CONFIGS 读取
- 防止无限循环

**pausedReason** - 暂停原因
- 自动拆分失败: "auto_decompose_failed"
- 门禁检查失败: "gate_check_failed: design_incomplete"
- 用户手动暂停: "user_paused"

**blockedReason** - 阻塞原因
- 连续失败: "consecutive_failures: 3"
- 超过最大回合: "max_rounds_exceeded"

## Requirement 扩展 «serves: FR-1»

### 现有结构 «serves: FR-1»

```typescript
interface Requirement {
  id: string;
  title: string;
  category: string;
  status: StageType;
  // ... 其他字段
}
```

### 扩展后 «serves: FR-1»

```typescript
interface Requirement {
  id: string;
  title: string;
  category: string;
  status: StageType;
  // ... 其他字段
  
  // 新增：可选字段，老需求为 undefined
  dive?: RequirementDive;
}
```

### 数据库 Schema 变更 «serves: FR-1»

**表**: `requirements`

**新增列**: `dive` (JSONB, nullable)

**迁移方式**:
```sql
-- 添加可选列
ALTER TABLE requirements 
ADD COLUMN dive JSONB DEFAULT NULL;

-- 创建索引（用于查询 armed 的需求）
CREATE INDEX idx_requirements_dive_activation 
ON requirements ((dive->>'activation'));

-- 创建索引（用于查询 active 的需求）
CREATE INDEX idx_requirements_dive_phase 
ON requirements ((dive->>'phase'));
```

**回滚方式**:
```sql
-- 删除索引
DROP INDEX IF EXISTS idx_requirements_dive_activation;
DROP INDEX IF EXISTS idx_requirements_dive_phase;

-- 删除列
ALTER TABLE requirements 
DROP COLUMN IF EXISTS dive;
```

**数据兼容性**:
- 老需求: `dive = null` → 手动模式
- 新需求: `dive = { ... }` → 自动模式
- 不需要数据迁移

## StageConfig 配置 «serves: FR-8»

### 数据结构 «serves: FR-8»

```typescript
interface StageConfig {
  requiresConfirmation: boolean;  // 是否需要用户确认
  autoExecute: boolean;           // 确认后是否自动续跑
  maxRounds: number;              // 该阶段最大回合数
}

const STAGE_CONFIGS: Record<StageType, StageConfig> = {
  brainstorming: { 
    requiresConfirmation: true,   // 需求文档需确认
    autoExecute: true,            // 确认后自动进入 design
    maxRounds: 5
  },
  design: { 
    requiresConfirmation: true,   // 设计文档需确认
    autoExecute: true,
    maxRounds: 5
  },
  decomposing: { 
    requiresConfirmation: true,   // 拆分计划需批准
    autoExecute: true,            // 批准后自动拆分+执行
    maxRounds: 3
  },
  implementing: { 
    requiresConfirmation: false,  // 任务自动执行
    autoExecute: true,            // 全自动
    maxRounds: 50
  },
  accepting: { 
    requiresConfirmation: true,   // 验收需人工审核
    autoExecute: false,           // 不自动归档
    maxRounds: 5
  },
  archived: {
    requiresConfirmation: false,
    autoExecute: false,
    maxRounds: 1
  }
};
```

### 配置说明 «serves: FR-8»

- **requiresConfirmation**: 决定是否需要弹框让用户确认
- **autoExecute**: 决定确认后是否自动续跑
- **maxRounds**: 防止无限循环的安全阀

## RTM 数据模型 «serves: FR-4, FR-5, FR-6»

### RTM 文件结构（现有） «serves: FR-4, FR-5, FR-6»

```json
{
  "functional_requirements": [
    {
      "id": "FR-1",
      "title": "Dive 状态管理",
      "design_refs": [],      // 设计门禁检查这个
      "task_refs": [],        // 拆分门禁检查这个
      "acceptance_status": "pending"  // 验收门禁检查这个
    }
  ]
}
```

### 门禁检查逻辑 «serves: FR-4, FR-5, FR-6»

**设计门禁**: 检查 `design_refs.length > 0`
**拆分门禁**: 检查 `task_refs.length > 0`
**验收门禁**: 检查 `acceptance_status === "passed"`

## 数据一致性 «serves: FR-1»

### 状态同步规则 «serves: FR-1, FR-2»

1. **requirement.status** 是主状态
2. **requirement.dive.currentStage** 必须与 status 一致
3. 推进 status 时同步更新 dive.currentStage

### 原子性保证 «serves: FR-1, FR-2»

- 使用事务保证 status 和 dive 字段同时更新
- 失败时回滚，不允许不一致状态

### 并发控制 «serves: FR-1, FR-2»

- 使用乐观锁（version 字段）
- 更新前检查 version，不一致则重试