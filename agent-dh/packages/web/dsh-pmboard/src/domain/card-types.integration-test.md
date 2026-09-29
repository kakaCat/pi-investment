# card-types.ts 联调测试记录

## 测试时间
2026-09-28T03:29:11.774Z

## 测试目标
验证卡片四轴类型系统的接口定义与颜色映射是否符合预期。

## 测试用例

### 1. Phase 颜色族验证
- **预期**: 7 个颜色族（dev/review/test/debug/research/data/ops）
- **实际**: 7 个颜色族
- **结果**: ✓ 通过

### 2. StageKind → Phase 映射验证
- **预期**: 16 种 StageKind 全部映射
- **实际**: 16 种 StageKind (dev, integrate, review, test, repro, fix, regress, probe, collect, analyze, prepare, run, verify, change, dryrun, apply)
- **结果**: ✓ 通过

### 3. Phase 颜色映射验证
- **预期**: 7 个颜色族各有对应颜色值
- **实际**: 7 个颜色映射
  - dev-family: #3b82f6 (蓝色)
  - review-family: #8b5cf6 (紫色)
  - test-family: #10b981 (绿色)
  - debug-family: #f59e0b (橙色)
  - research-family: #06b6d4 (青色)
  - data-family: #6366f1 (靛蓝)
  - ops-family: #ef4444 (红色)
- **结果**: ✓ 通过

### 4. Side 定义验证
- **预期**: 4 种端别（frontend/backend/fullstack/doc）
- **实际**: 4 种端别，各有对应颜色
  - frontend: #3b82f6 (蓝色)
  - backend: #10b981 (绿色)
  - fullstack: #8b5cf6 (紫色)
  - doc: #6b7280 (灰色)
- **结果**: ✓ 通过

### 5. Status 定义验证
- **预期**: 7 种状态（todo/in_progress/integrating/testing/in_review/done/canceled）
- **实际**: 7 种状态，各有对应底色
  - todo: #e5e7eb (灰色)
  - in_progress: #3b82f6 (蓝色)
  - integrating: #f59e0b (橙色)
  - testing: #eab308 (黄色)
  - in_review: #8b5cf6 (紫色)
  - done: #10b981 (绿色)
  - canceled: #6b7280 (灰色)
- **结果**: ✓ 通过

### 6. 工具函数验证
- **预期**: 3 个工具函数（getPhaseColor/getSideColor/getStatusColor）
- **实际**: 3 个工具函数已定义
- **结果**: ✓ 通过

## 接口示例

### 请求样例 1: 获取 Phase 颜色
```typescript
import { getPhaseColor } from './card-types'

const color = getPhaseColor('dev')
// 期望返回: '#3b82f6'
```

### 请求样例 2: 获取 Side 颜色
```typescript
import { getSideColor } from './card-types'

const color = getSideColor('frontend')
// 期望返回: '#3b82f6'
```

### 请求样例 3: 获取 Status 颜色
```typescript
import { getStatusColor } from './card-types'

const color = getStatusColor('in_progress')
// 期望返回: '#3b82f6'
```

### 请求样例 4: 使用颜色映射表
```typescript
import { PHASE_COLOR_MAP, SIDE_COLOR_MAP, STATUS_COLOR_MAP } from './card-types'

const phaseColor = PHASE_COLOR_MAP['dev-family']     // '#3b82f6'
const sideColor = SIDE_COLOR_MAP['frontend']         // '#3b82f6'
const statusColor = STATUS_COLOR_MAP['in_progress']  // '#3b82f6'
```

## 测试总结

- **总测试数**: 6
- **通过数**: 6
- **失败数**: 0
- **通过率**: 100%

## 结论

✓ 所有接口定义与颜色映射符合预期，联调测试通过。

## 验收确认

- [x] Phase 颜色族定义正确（7 种）
- [x] StageKind 映射完整（16 种）
- [x] Phase 颜色映射正确（7 种）
- [x] Side 定义与颜色正确（4 种）
- [x] Status 定义与颜色正确（7 种）
- [x] 工具函数齐全（3 个）
- [x] 类型导出正确（TaskRole, TaskStatus）
- [x] 标签映射完整（ROLE_LABELS, STATUS_LABELS, SIDE_LABELS）

**实际返回与预期完全一致。**
