# card-types.ts 接口联调记录

**日期**: 2026-09-28
**子卡**: t-4d579e（integrate 阶段）

## 联调目标
验证四轴类型系统（Phase/Side/Role/Status）的 TypeScript 接口定义是否正确导出和使用。

## 测试用例

### 1. Phase（阶段）颜色族
- **枚举数量**: 7 种颜色族
- **映射表**: STAGE_TO_PHASE_COLOR（16 种 StageKind → 7 种颜色族）
- **颜色值**: PHASE_COLOR_MAP（7 种颜色族 → CSS 颜色值）

### 2. Side（端别）
- **枚举数量**: 4 种（frontend/backend/fullstack/doc）
- **中文标签**: SIDE_LABELS
- **颜色映射**: SIDE_COLOR_MAP

### 3. Role（角色）
- **来源**: 重导出 TaskRole（parent/subtask/legacy）
- **中文标签**: ROLE_LABELS

### 4. Status（状态）
- **枚举数量**: 7 种状态
- **中文标签**: STATUS_LABELS
- **底色映射**: STATUS_COLOR_MAP（6 种颜色，canceled 与 todo 共用灰色）

### 5. 工具函数
- `getPhaseColor(stage: StageKind): string`
- `getSideColor(side: Side): string`
- `getStatusColor(status: TaskStatus): string`

## 测试结果

```

=== 1. Phase 颜色族（7种）===
PHASE_COLOR_FAMILIES: [
  'dev-family',
  'review-family',
  'test-family',
  'debug-family',
  'research-family',
  'data-family',
  'ops-family'
]
PHASE_COLOR_MAP: {
  'dev-family': '#3b82f6',
  'review-family': '#8b5cf6',
  'test-family': '#10b981',
  'debug-family': '#f59e0b',
  'research-family': '#06b6d4',
  'data-family': '#6366f1',
  'ops-family': '#ef4444'
}

=== 2. StageKind → Phase 映射 ===
示例：dev -> dev-family
示例：test -> test-family
示例：review -> review-family

=== 3. Side（端别，4种）===
SIDES: [ 'frontend', 'backend', 'fullstack', 'doc' ]
SIDE_LABELS: { frontend: '前端', backend: '后端', fullstack: '全栈', doc: '文档' }
SIDE_COLOR_MAP: {
  frontend: '#3b82f6',
  backend: '#10b981',
  fullstack: '#8b5cf6',
  doc: '#6b7280'
}

=== 4. Role（角色）===
ROLE_LABELS: { parent: '父卡', subtask: '子卡', legacy: '存量卡' }

=== 5. Status（状态，7种）===
STATUS_LABELS: {
  todo: '待开始',
  in_progress: '进行中',
  integrating: '联调中',
  testing: '测试中',
  in_review: '待复核',
  done: '已完成',
  canceled: '已取消'
}
STATUS_COLOR_MAP: {
  todo: '#e5e7eb',
  in_progress: '#3b82f6',
  integrating: '#f59e0b',
  testing: '#eab308',
  in_review: '#8b5cf6',
  done: '#10b981',
  canceled: '#6b7280'
}

=== 6. 工具函数验证 ===
getPhaseColor("dev"): #3b82f6
getSideColor("frontend"): #3b82f6
getStatusColor("in_progress"): #3b82f6

=== ✅ 接口联调通过 ===

```

## 验收结论

✅ **接口联调通过**

- [x] 类型定义导出正常
- [x] 枚举值可访问
- [x] 映射表数据完整
- [x] 工具函数运行正常

## 文件路径

- **类型定义**: `packages/web/dsh-pmboard/src/domain/card-types.ts`
- **联调记录**: `packages/web/dsh-pmboard/docs/integration/card-types-integration.md`

