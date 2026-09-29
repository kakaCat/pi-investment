# card-types.ts 联调测试报告

**测试时间**: 2026-09-28T03:32:51.260Z
**测试文件**: packages/web/dsh-pmboard/src/__integration_test__/card-types.integration.ts
**测试结果**: ✅ 通过

## 请求样例

```typescript
import {
  getPhaseColor,
  getSideColor,
  getStatusColor,
  STAGE_TO_PHASE_COLOR,
  SIDE_COLOR_MAP,
  STATUS_COLOR_MAP
} from '../domain/card-types.js';

// 示例 1: 获取阶段颜色
const devColor = getPhaseColor('dev');        // 期望: #3b82f6 (蓝色)
const reviewColor = getPhaseColor('review');  // 期望: #8b5cf6 (紫色)

// 示例 2: 获取端别颜色
const feColor = getSideColor('frontend');     // 期望: #3b82f6 (蓝色)
const beColor = getSideColor('backend');      // 期望: #10b981 (绿色)

// 示例 3: 获取状态颜色
const todoColor = getStatusColor('todo');     // 期望: #e5e7eb (灰色)
const doneColor = getStatusColor('done');     // 期望: #10b981 (绿色)
```

## 实际响应

### Phase 颜色族系统
- 颜色族数量: 7
- StageKind 映射: 16 项
- 颜色值映射: 7 项
- 一致性: ✅

### Side 类型系统
- Side 数量: 4
- 标签/颜色映射: 各 4 项
- 一致性: ✅

### Status 类型系统
- 颜色/标签映射: 各 7 项
- 一致性: ✅

## 验证结论

接口联调通过，所有导出项符合预期：
- ✅ Phase 颜色族系统完整（7 色族 + 16 StageKind 映射）
- ✅ Side 类型系统完整（4 项 + 标签 + 颜色）
- ✅ Status 类型系统完整（7 项 + 标签 + 颜色）
- ✅ 三个工具函数正常工作
