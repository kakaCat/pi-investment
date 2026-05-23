# 全局原型主题系统设计

## 目标

创建一个全局样式系统，自动将web-frontend项目中的所有20个页面与quant-web-v2-prototype.html原型的样式对齐，减少手动调整工作。

## 背景

- 已完成：indicator-ide页面通过8个任务成功对齐原型样式
- 问题：还有19个页面（scheduler等）存在样式不一致
- 挑战：逐页手动调整工作量大（20页 × 8任务 = 160任务）
- 解决方案：创建全局样式文件，自动覆盖80%的页面，特殊情况单独处理

## 架构方案

### 单文件方案

创建单个SCSS文件 `prototype-theme.scss`，包含所有全局样式：

```
web-frontend/src/assets/styles/
├── global.css              # 现有文件，保持不变
└── prototype-theme.scss    # 新建文件，500-800行
```

### 导入顺序

在 `main.ts` 中按以下顺序导入：

```typescript
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'  // 1. Element Plus默认样式
import './assets/styles/global.css'    // 2. 项目基础样式
import './assets/styles/prototype-theme.scss'  // 3. 原型主题覆盖
```

**优先级**: prototype-theme.scss > global.css > Element Plus

## 设计详情

### 1. 颜色系统

从原型HTML提取Tailwind颜色值，定义为CSS变量：

```scss
:root {
  // Slate系列
  --slate-50: #f8fafc;
  --slate-100: #f1f5f9;
  --slate-200: #e2e8f0;
  --slate-300: #cbd5e1;
  --slate-400: #94a3b8;
  --slate-500: #64748b;
  --slate-600: #475569;
  --slate-700: #334155;
  --slate-800: #1e293b;
  --slate-900: #0f172a;

  // Gray系列
  --gray-50: #f9fafb;
  --gray-100: #f3f4f6;
  --gray-200: #e5e7eb;
  --gray-300: #d1d5db;
  --gray-400: #9ca3af;
  --gray-500: #6b7280;
  --gray-600: #4b5563;
  --gray-700: #374151;
  --gray-800: #1f2937;
  --gray-900: #111827;

  // Blue系列
  --blue-50: #eff6ff;
  --blue-100: #dbeafe;
  --blue-200: #bfdbfe;
  --blue-300: #93c5fd;
  --blue-400: #60a5fa;
  --blue-500: #3b82f6;
  --blue-600: #2563eb;
  --blue-700: #1d4ed8;
  --blue-800: #1e40af;
  --blue-900: #1e3a8a;

  // Green系列
  --green-50: #f0fdf4;
  --green-100: #dcfce7;
  --green-200: #bbf7d0;
  --green-300: #86efac;
  --green-400: #4ade80;
  --green-500: #22c55e;
  --green-600: #16a34a;
  --green-700: #15803d;
  --green-800: #166534;
  --green-900: #14532d;

  // Red系列
  --red-50: #fef2f2;
  --red-100: #fee2e2;
  --red-200: #fecaca;
  --red-300: #fca5a5;
  --red-400: #f87171;
  --red-500: #ef4444;
  --red-600: #dc2626;
  --red-700: #b91c1c;
  --red-800: #991b1b;
  --red-900: #7f1d1d;

  // Purple系列
  --purple-50: #faf5ff;
  --purple-100: #f3e8ff;
  --purple-200: #e9d5ff;
  --purple-300: #d8b4fe;
  --purple-400: #c084fc;
  --purple-500: #a855f7;
  --purple-600: #9333ea;
  --purple-700: #7e22ce;
  --purple-800: #6b21a8;
  --purple-900: #581c87;

  // Orange系列
  --orange-50: #fff7ed;
  --orange-100: #ffedd5;
  --orange-200: #fed7aa;
  --orange-300: #fdba74;
  --orange-400: #fb923c;
  --orange-500: #f97316;
  --orange-600: #ea580c;
  --orange-700: #c2410c;
  --orange-800: #9a3412;
  --orange-900: #7c2d12;
}
```

### 2. Element Plus组件覆盖

覆盖最常用的3个组件，使用`:deep()`选择器：

```scss
// 卡片组件
:deep(.el-card) {
  border-radius: 12px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  border: 1px solid var(--slate-200);
  background-color: white;
  
  .el-card__header {
    padding: 16px;
    border-bottom: 1px solid var(--slate-200);
  }
  
  .el-card__body {
    padding: 16px;
  }
}

// 按钮组件
:deep(.el-button) {
  border-radius: 8px;
  font-weight: 500;
  padding: 8px 16px;
  
  &.el-button--primary {
    background-color: var(--blue-600);
    border-color: var(--blue-600);
    
    &:hover {
      background-color: var(--blue-700);
      border-color: var(--blue-700);
    }
  }
  
  &.el-button--success {
    background-color: var(--green-600);
    border-color: var(--green-600);
    
    &:hover {
      background-color: var(--green-700);
      border-color: var(--green-700);
    }
  }
  
  &.el-button--warning {
    background-color: var(--orange-600);
    border-color: var(--orange-600);
    
    &:hover {
      background-color: var(--orange-700);
      border-color: var(--orange-700);
    }
  }
  
  &.el-button--danger {
    background-color: var(--red-600);
    border-color: var(--red-600);
    
    &:hover {
      background-color: var(--red-700);
      border-color: var(--red-700);
    }
  }
  
  &.el-button--info {
    background-color: var(--purple-600);
    border-color: var(--purple-600);
    
    &:hover {
      background-color: var(--purple-700);
      border-color: var(--purple-700);
    }
  }
}

// 输入框组件
:deep(.el-input) {
  .el-input__wrapper {
    border-radius: 8px;
    border: 1px solid var(--slate-200);
    box-shadow: none;
    
    &:hover {
      border-color: var(--slate-300);
    }
    
    &.is-focus {
      border-color: var(--blue-600);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
  }
  
  .el-input__inner {
    color: var(--slate-900);
    
    &::placeholder {
      color: var(--slate-400);
    }
  }
}
```

### 3. 通用组件样式

定义原型中反复出现的UI模式：

```scss
// 页面容器
.page-container {
  background-color: var(--slate-100);
  min-height: 100vh;
  padding: 24px;
}

// 标题样式
.section-title {
  font-size: 12px;
  color: var(--slate-500);
  text-transform: uppercase;
  font-weight: 500;
  letter-spacing: 0.05em;
  margin-bottom: 12px;
}

// 代码编辑器容器
.code-editor-container {
  background-color: var(--gray-800);
  border-radius: 8px;
  padding: 16px;
  
  .code-text {
    color: var(--green-400);
    font-family: 'Monaco', 'Menlo', monospace;
    font-size: 13px;
    line-height: 1.6;
  }
}

// 图表容器
.chart-container {
  background-color: white;
  border-radius: 8px;
  padding: 16px;
  height: 220px;
}

// 统计卡片
.stat-card {
  background-color: white;
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--slate-200);
  
  .stat-label {
    font-size: 12px;
    color: var(--slate-500);
    margin-bottom: 4px;
  }
  
  .stat-value {
    font-size: 24px;
    font-weight: 600;
    color: var(--slate-900);
  }
}
```

### 4. 工具类

补充常用工具类，与Tailwind配合使用：

```scss
// 间距工具
.gap-tight { gap: 8px; }
.gap-normal { gap: 12px; }
.gap-loose { gap: 16px; }

// 文本颜色（涨跌）
.text-up { color: var(--green-600); }
.text-down { color: var(--red-600); }
.text-neutral { color: var(--slate-500); }

// 背景色（状态）
.bg-success-light { background-color: var(--green-50); }
.bg-warning-light { background-color: var(--orange-50); }
.bg-danger-light { background-color: var(--red-50); }

// 边框
.border-light { border: 1px solid var(--slate-200); }
.border-medium { border: 1px solid var(--slate-300); }

// 阴影
.shadow-card { box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); }
.shadow-elevated { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
```

### 5. 响应式设计

统一断点和响应式规则：

```scss
// 断点定义
$breakpoint-tablet: 1180px;
$breakpoint-mobile: 760px;

// 响应式容器
.responsive-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  
  @media (max-width: $breakpoint-tablet) {
    grid-template-columns: repeat(2, 1fr);
  }
  
  @media (max-width: $breakpoint-mobile) {
    grid-template-columns: 1fr;
  }
}

// 响应式padding
.page-container {
  padding: 24px;
  
  @media (max-width: $breakpoint-mobile) {
    padding: 16px;
  }
}
```

## 实现策略

### 自动覆盖范围

全局样式将自动处理：
- 所有使用el-card的页面（卡片圆角、边框、阴影）
- 所有使用el-button的页面（按钮颜色、圆角）
- 所有使用el-input的页面（输入框样式）
- 所有使用.page-container的页面（背景色、padding）
- 所有使用.section-title的页面（标题样式）

### 特殊情况处理

约4个页面可能需要页面级调整：
- 复杂布局页面（如dashboard）
- 特殊交互页面（如图表编辑器）
- 自定义组件较多的页面

这些页面在全局样式基础上，添加页面级的`:deep()`覆盖。

## 测试策略

### 测试范围

测试所有20个页面：
1. indicator-ide（已对齐，验证不被破坏）
2. scheduler
3. dashboard
4. portfolio
5. backtest
6. signals
7. risk-monitor
8. market-overview
9. stock-detail
10. factor-analysis
11. strategy-builder
12. performance-report
13. trade-history
14. position-management
15. alert-settings
16. system-settings
17. user-profile
18. help-docs
19. about
20. login

### 测试方法

1. **视觉对比**：打开原型HTML和实际页面，对比关键元素
2. **响应式测试**：测试1180px和760px断点
3. **交互测试**：确保按钮、输入框等交互正常
4. **回归测试**：确保indicator-ide页面不被破坏

### 验收标准

- 卡片圆角12px，边框slate-200
- 按钮圆角8px，颜色匹配原型
- 输入框圆角8px，focus状态正确
- 页面背景slate-100
- 标题样式统一（12px, uppercase, slate-500）
- 响应式布局正常

## 预期效果

- **覆盖率**：80%的页面自动对齐，无需手动调整
- **工作量**：从160任务减少到约20任务（1个全局文件 + 4个特殊页面）
- **维护性**：样式集中管理，修改一处全局生效
- **一致性**：所有页面自动保持与原型一致

## 风险和缓解

### 风险1：全局样式影响现有页面

**缓解**：
- 使用`:deep()`限制作用域
- 优先级设计合理（prototype-theme.scss最后导入）
- 充分测试所有页面

### 风险2：特殊页面需要更多调整

**缓解**：
- 预留页面级覆盖机制
- 全局样式设计为可覆盖
- 逐步迭代优化

### 风险3：Element Plus版本升级冲突

**缓解**：
- 只覆盖稳定的样式属性
- 避免依赖内部实现细节
- 定期测试和更新
