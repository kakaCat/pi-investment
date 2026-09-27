# 数据模型


定义 RTM YAML 文件和台账的完整数据模型，使所有数据结构清晰且类型安全，验收标准：所有接口的输入输出类型定义完整，TypeScript 编译无类型错误。


## 台账数据模型（serves: FR-2）

详见 [ledger-schema.md](./ledger-schema.md)，包括：
- 需求对象新增 `artifacts[]` 字段
- 任务对象新增 `designServes[]` 和 `implements` 字段
- schemaVersion 8 → 9

## RTM 文件数据模型（serves: FR-1）

详见 [rtm-file-structure.md](./rtm-file-structure.md)，包括：
- 7 个 RTM YAML 文件的完整 schema
- 通用结构（metadata / inputs / outputs / traceability / coverage）
- 各节点特定字段定义

## TypeScript 类型定义（serves: FR-1, FR-2）

```typescript
// packages/web/dsh-pmboard/src/rtm/types.ts

export interface RTMFile {
  metadata: RTMMetadata
  inputs?: Record<string, any>
  outputs?: Record<string, any>
  traceability?: TraceabilityMap
  coverage?: Coverage
  lifecycle?: LifecycleData
  [key: string]: any
}

export interface RTMMetadata {
  version: number
  requirement_id: string
  stage: Stage
  generated_at: string
  generator: string
  task_id?: string
}

export type Stage = 'lifecycle' | 'brainstorming' | 'design' | 'decomposing' | 'implementing' | 'accepting'

export interface TraceabilityMap {
  fr_to_design?: Record<string, string[]>
  design_to_tasks?: Record<string, string[]>
  task_to_tests?: Record<string, string[]>
  fr_to_tasks?: Record<string, string[]>
}

export interface Coverage {
  design?: CoverageDetail
  implementation?: CoverageDetail
  testing?: CoverageDetail
}

export interface CoverageDetail {
  total_frs?: number
  covered_frs?: number
  total_designs?: number
  covered_designs?: number
  total_tasks?: number
  tested_tasks?: number
  uncovered: string[]
  rate: number
}

export interface LifecycleData {
  current_stage: string
  stages: Record<string, StageStatus>
}

export interface StageStatus {
  status: 'pending' | 'in_progress' | 'completed'
  started_at?: string
  completed_at?: string
}

// 台账扩展类型（见 ledger-schema.md）
export interface Artifact {
  kind: 'requirement' | 'design' | 'plan' | 'verification' | 'archive'
  path: string
  stage: string
  confirmed?: boolean
  confirmedAt?: number
}
```


```bash
# TypeScript 编译检查
cd packages/web/dsh-pmboard
npx tsc --noEmit

# 预期：无类型错误
```