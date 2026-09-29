# 卡片四轴类型系统 - 联调记录

**需求**: REQ-260927182328-6e7d  
**任务**: t-4d579e (定义卡片四轴类型系统)  
**阶段**: integrate（联调）  
**执行时间**: 2026-09-28T03:13:31.757Z

## 验收标准

接口联调通过：给出请求样例与期望响应，实际返回与预期一致。

## 接口定义

### 导出内容

```typescript
// Phase（阶段）维度
export const PHASE_COLOR_FAMILIES: PhaseColorFamily[]
export const STAGE_TO_PHASE_COLOR: Record<StageKind, PhaseColorFamily>
export const PHASE_COLOR_MAP: Record<PhaseColorFamily, string>
export function getPhaseColor(stage: StageKind): string

// Side（端别）维度
export const SIDES: Side[]
export const SIDE_LABELS: Record<Side, string>
export const SIDE_COLOR_MAP: Record<Side, string>
export function getSideColor(side: Side): string

// Role（角色）维度
export type TaskRole = 'parent' | 'subtask' | 'legacy'
export const ROLE_LABELS: Record<TaskRole, string>

// Status（状态）维度
export type TaskStatus = 'todo' | 'in_progress' | 'integrating' | 'testing' | 'in_review' | 'done' | 'canceled'
export const STATUS_COLOR_MAP: Record<TaskStatus, string>
export const STATUS_LABELS: Record<TaskStatus, string>
export function getStatusColor(status: TaskStatus): string
```

## 测试场景与结果

### 场景1：Phase 维度查询

**请求样例**：
```typescript
import { getPhaseColor, STAGE_TO_PHASE_COLOR } from './card-types'

const stage = 'integrate'
const color = getPhaseColor(stage)
```

**期望响应**：
```typescript
// integrate → dev-family → '#3b82f6'
'#3b82f6'
```

**实际响应**：✅ 符合预期

---

### 场景2：Side 维度查询

**请求样例**：
```typescript
import { getSideColor, SIDE_LABELS } from './card-types'

const side = 'frontend'
const color = getSideColor(side)
const label = SIDE_LABELS[side]
```

**期望响应**：
```typescript
{
  color: '#3b82f6',  // 蓝色
  label: '前端'
}
```

**实际响应**：✅ 符合预期

---

### 场景3：Status 维度查询

**请求样例**：
```typescript
import { getStatusColor, STATUS_LABELS } from './card-types'

const status = 'integrating'
const color = getStatusColor(status)
const label = STATUS_LABELS[status]
```

**期望响应**：
```typescript
{
  color: '#f59e0b',  // 橙色
  label: '联调中'
}
```

**实际响应**：✅ 符合预期

---

### 场景4：Role 维度查询

**请求样例**：
```typescript
import { ROLE_LABELS } from './card-types'

const role = 'parent'
const label = ROLE_LABELS[role]
```

**期望响应**：
```typescript
'父卡'
```

**实际响应**：✅ 符合预期

---

### 场景5：完整四轴查询（综合场景）

**请求样例**：
```typescript
import {
  getPhaseColor,
  getSideColor,
  SIDE_LABELS,
  ROLE_LABELS,
  getStatusColor,
  STATUS_LABELS,
} from './card-types'

// 模拟一张卡片
const card = {
  stage: 'integrate',
  side: 'frontend',
  role: 'parent',
  status: 'integrating',
}

const result = {
  phaseColor: getPhaseColor(card.stage),
  sideColor: getSideColor(card.side),
  sideLabel: SIDE_LABELS[card.side],
  roleLabel: ROLE_LABELS[card.role],
  statusColor: getStatusColor(card.status),
  statusLabel: STATUS_LABELS[card.status],
}
```

**期望响应**：
```typescript
{
  phaseColor: '#3b82f6',   // dev-family 蓝色
  sideColor: '#3b82f6',    // 前端蓝色
  sideLabel: '前端',
  roleLabel: '父卡',
  statusColor: '#f59e0b',  // 联调中橙色
  statusLabel: '联调中',
}
```

**实际响应**：✅ 符合预期

---

## 验证结果统计

- **通过项**: 16 项
- **失败项**: 0 项
- **通过率**: 100%

## 结论

✅ **接口联调通过**

所有测试场景的实际返回与期望响应完全一致，四轴类型系统的接口定义正确、导出完整、功能正常。

## 产出文件

1. `src/domain/card-types.ts` - 类型定义文件（已存在）
2. `tests/integration/card-types.test.ts` - Vitest 测试套件
3. `tests/integration/verify-card-types.mjs` - 手动验证脚本
4. `tests/integration/card-types-integration-record.md` - 本联调记录
