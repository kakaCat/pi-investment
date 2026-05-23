# 指标IDE样式对齐实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将web-frontend项目中的指标IDE页面样式完全对齐原型HTML，确保视觉效果和用户体验的一致性

**Architecture:** 通过覆盖Element Plus默认样式，使用Tailwind色系和原型中的精确样式值。保持Vue组件结构不变，只调整SCSS样式和部分TypeScript配置。采用渐进式修改策略，每个任务独立可测试。

**Tech Stack:** Vue 3, Element Plus, SCSS, ECharts, Tailwind色系

---

## 文件结构

### 修改的文件
- **主组件**: `web-frontend/src/views/IndicatorIDE/index.vue` - 更新样式和图表配置
- **参考原型**: `quant-web-v2-prototype.html` - 样式参考源

### 不创建新文件
所有修改都在现有的 `index.vue` 文件中完成，通过更新 `<style scoped lang="scss">` 部分实现。

---

## Task 1: 更新页面容器和卡片基础样式

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue:806-913` (style section)

- [ ] **Step 1: 备份当前样式**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
cp src/views/IndicatorIDE/index.vue src/views/IndicatorIDE/index.vue.backup
```

- [ ] **Step 2: 更新页面容器背景色**

在 `index.vue` 的 `<style scoped lang="scss">` 部分，找到 `.indicator-ide` 类（约第807行），修改为：

```scss
.indicator-ide {
  padding: 24px; // 对齐原型 p-6
  min-height: 100vh;
  background: #eef2f7; // 从 #f8fafc 改为 #eef2f7
}
```

- [ ] **Step 3: 覆盖Element Plus卡片样式**

在 `.indicator-ide` 样式块之后添加：

```scss
// Element Plus卡片样式覆盖
:deep(.el-card) {
  border-radius: 12px; // rounded-xl
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); // shadow-sm
  border: 1px solid #e2e8f0; // border-slate-200
  background: #ffffff;
}

:deep(.el-card__header) {
  padding: 16px; // p-4
  border-bottom: 1px solid #e2e8f0; // border-slate-200
  background: transparent;
}

:deep(.el-card__body) {
  padding: 16px; // p-4
}
```

- [ ] **Step 4: 启动开发服务器验证**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run dev
```

预期：开发服务器启动，访问 http://localhost:5173 查看指标IDE页面，背景色应为 `#eef2f7`，卡片圆角为12px

- [ ] **Step 5: 提交更改**

```bash
git add src/views/IndicatorIDE/index.vue
git commit -m "style(indicator-ide): update page container and card base styles

- 更新页面背景色为 #eef2f7 对齐原型
- 覆盖 Element Plus 卡片样式（圆角、阴影、边框）
- 统一卡片内边距为 16px"
```

---

## Task 2: 更新代码编辑器样式

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue:850-879` (code-editor styles)

- [ ] **Step 1: 更新代码编辑器容器样式**

找到 `.code-editor` 样式块（约第851行），完全替换为：

```scss
.code-editor {
  flex: 1;
  background: #1f2937; // gray-900，从 #1e1e1e 改为 #1f2937
  border-radius: 8px; // rounded-lg
  overflow: hidden;
  border: none; // 移除原有的 border: 1px solid #333

  .code-textarea {
    width: 100%;
    height: 384px; // h-96，从 min-height: 400px 改为固定 384px
    min-height: 384px;
    padding: 16px;
    background: #1f2937; // 从 #1e1e1e 改为 #1f2937
    color: #4ade80; // green-400，从 #4ec9b0 改为 #4ade80
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.6;
    border: none;
    outline: none;
    resize: none;
    white-space: pre;
    overflow-wrap: normal;
    overflow-x: auto;

    &::placeholder {
      color: #6b7280; // gray-500，从 #6a9955 改为 #6b7280
    }
  }
}
```

- [ ] **Step 2: 添加标签样式**

在 `.code-editor` 样式块之后添加：

```scss
// 代码编辑器标签样式
.text-xs.text-slate-500.uppercase.font-medium {
  font-size: 11px;
  color: #64748b; // slate-500
  text-transform: uppercase;
  font-weight: 500;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}
```

- [ ] **Step 3: 在浏览器中验证**

访问 http://localhost:5173，导航到指标IDE页面，检查：
- 代码编辑器背景色为深灰色 `#1f2937`
- 代码文字颜色为绿色 `#4ade80`
- 编辑器高度为 384px

- [ ] **Step 4: 提交更改**

```bash
git add src/views/IndicatorIDE/index.vue
git commit -m "style(indicator-ide): update code editor styles

- 更新编辑器背景色为 #1f2937 (gray-900)
- 更新代码文字颜色为 #4ade80 (green-400)
- 固定编辑器高度为 384px
- 移除边框，统一圆角为 8px"
```

---

## Task 3: 更新图表容器样式和配置

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue:881-888` (preview-card styles)
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue:710-797` (renderChart function)

- [ ] **Step 1: 更新图表容器样式**

找到 `.preview-card` 样式块（约第881行），修改为：

```scss
.preview-card {
  .chart-container {
    height: 220px; // 从 280px 改为 220px，对齐原型
    background: #0a0a0f; // 保持不变
    border-radius: 8px; // rounded-lg
    overflow: hidden;
  }
}
```

- [ ] **Step 2: 更新ECharts配置中的grid设置**

找到 `renderChart` 函数中的 `option` 对象（约第711行），确保 `grid` 配置为：

```typescript
grid: {
  left: 50,
  right: 50,
  top: 40,
  bottom: 40,
  containLabel: true
},
```

- [ ] **Step 3: 验证图表显示**

在浏览器中：
1. 点击"运行"按钮触发图表渲染
2. 检查图表容器高度为 220px
3. 检查图表背景为深色 `#0a0a0f`
4. 检查图表内容正常显示，没有被裁剪

- [ ] **Step 4: 提交更改**

```bash
git add src/views/IndicatorIDE/index.vue
git commit -m "style(indicator-ide): update chart container height

- 调整图表容器高度从 280px 到 220px 对齐原型
- 确保 ECharts grid 配置正确
- 保持深色背景主题"
```

---

## Task 4: 更新指标库列表样式

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue:813-837` (indicator-library styles)

- [ ] **Step 1: 更新指标库容器样式**

找到 `.indicator-library` 样式块（约第813行），完全替换为：

```scss
.indicator-library {
  height: calc(100vh - 200px);
  overflow-y: auto;

  .indicator-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px; // p-2
    border-radius: 4px; // rounded
    cursor: pointer;
    transition: all 0.2s;
    border: 1px solid transparent; // 添加透明边框

    &:hover {
      background: #f9fafb; // gray-50，从 #f1f5f9 改为 #f9fafb
    }

    &.active {
      background: #eff6ff; // blue-50，从 #dbeafe 改为 #eff6ff
      border-color: #bfdbfe; // blue-200，从 #3b82f6 改为 #bfdbfe
      color: #1e3a8a; // blue-900，从 #1e40af 改为 #1e3a8a
      font-weight: 500;
    }
  }
}
```

- [ ] **Step 2: 添加搜索框样式覆盖**

在 `.indicator-library` 样式块之后添加：

```scss
// 搜索框样式覆盖
:deep(.el-input) {
  .el-input__wrapper {
    border-radius: 8px; // rounded-lg
    border: 1px solid #e2e8f0; // border-slate-200
    padding: 8px 12px;
    
    &:hover {
      border-color: #cbd5e1; // slate-300
    }
    
    &.is-focus {
      border-color: #3b82f6; // blue-500
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
  }
}
```

- [ ] **Step 3: 验证列表交互**

在浏览器中：
1. 悬停在指标列表项上，检查背景色为 `#f9fafb`
2. 点击选中一个指标，检查激活状态背景色为 `#eff6ff`，边框为 `#bfdbfe`
3. 在搜索框中输入文字，检查聚焦状态样式

- [ ] **Step 4: 提交更改**

```bash
git add src/views/IndicatorIDE/index.vue
git commit -m "style(indicator-ide): update indicator library list styles

- 更新列表项悬停背景色为 #f9fafb (gray-50)
- 更新激活状态背景色为 #eff6ff (blue-50)
- 更新激活状态边框为 #bfdbfe (blue-200)
- 添加搜索框样式覆盖"
```

---

## Task 5: 更新按钮样式系统

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue` (add button style overrides)

- [ ] **Step 1: 添加按钮颜色覆盖样式**

在样式部分末尾（约第910行之前）添加：

```scss
// 按钮样式系统覆盖
:deep(.el-button) {
  border-radius: 8px; // rounded-lg
  padding: 8px 16px; // px-4 py-2
  font-size: 13px; // text-sm
  font-weight: 500; // font-medium
  height: auto;
  
  .el-icon {
    margin-right: 4px;
  }
}

// 运行按钮 - 绿色
:deep(.el-button--success) {
  background-color: #16a34a; // green-600
  border-color: #16a34a;
  
  &:hover {
    background-color: #15803d; // green-700
    border-color: #15803d;
  }
}

// 保存按钮 - 蓝色
:deep(.el-button--primary) {
  background-color: #2563eb; // blue-600
  border-color: #2563eb;
  
  &:hover {
    background-color: #1d4ed8; // blue-700
    border-color: #1d4ed8;
  }
}

// 发布按钮 - 紫色
:deep(.el-button--warning) {
  background-color: #9333ea; // purple-600
  border-color: #9333ea;
  color: #ffffff;
  
  &:hover {
    background-color: #7e22ce; // purple-700
    border-color: #7e22ce;
  }
}

// 复制按钮 - 默认样式
:deep(.el-button--default) {
  background-color: #ffffff;
  border-color: #e2e8f0; // border-slate-200
  color: #334155; // text-slate-700
  
  &:hover {
    background-color: #f8fafc; // bg-slate-50
    border-color: #cbd5e1;
  }
}
```

- [ ] **Step 2: 验证按钮样式**

在浏览器中检查所有按钮：
1. 运行按钮：绿色背景 `#16a34a`
2. 保存按钮：蓝色背景 `#2563eb`
3. 发布按钮：紫色背景 `#9333ea`
4. 复制按钮：白色背景，灰色边框
5. 所有按钮圆角为 8px

- [ ] **Step 3: 提交更改**

```bash
git add src/views/IndicatorIDE/index.vue
git commit -m "style(indicator-ide): update button styles to match prototype

- 运行按钮使用 green-600/700
- 保存按钮使用 blue-600/700
- 发布按钮使用 purple-600/700
- 复制按钮使用 slate 色系
- 统一按钮圆角为 8px，内边距为 8px 16px"
```

---

## Task 6: 更新回测结果卡片样式

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue:890-898` (backtest-card styles)

- [ ] **Step 1: 更新回测卡片样式**

找到 `.backtest-card` 样式块（约第890行），完全替换为：

```scss
.backtest-card {
  .grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px; // gap-3
    margin-bottom: 16px;
    
    > div {
      padding: 0; // 移除背景和内边距
      background: transparent; // 从 #f8fafc 改为透明
      border-radius: 0; // 从 8px 改为 0
      
      p:first-child {
        font-size: 13px;
        color: #475569; // text-slate-600
        margin-bottom: 4px;
      }
      
      p:last-child {
        font-size: 20px; // text-xl
        font-weight: 700; // font-bold
        line-height: 1.25;
      }
    }
  }
  
  // 回测按钮
  :deep(.el-button) {
    width: 100%;
    background-color: #ea580c; // orange-600
    border-color: #ea580c;
    color: #ffffff;
    
    &:hover {
      background-color: #c2410c; // orange-700
      border-color: #c2410c;
    }
  }
}
```

- [ ] **Step 2: 验证回测结果显示**

在浏览器中：
1. 运行指标并查看回测结果
2. 检查数值网格布局为 2 列，间距 12px
3. 检查数值背景为透明（无背景色）
4. 检查回测按钮为橙色 `#ea580c`

- [ ] **Step 3: 提交更改**

```bash
git add src/views/IndicatorIDE/index.vue
git commit -m "style(indicator-ide): update backtest result card styles

- 移除数值网格背景色，改为透明
- 调整网格间距为 12px (gap-3)
- 回测按钮使用 orange-600/700
- 统一文字颜色为 slate-600"
```

---

## Task 7: 添加响应式设计样式

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue` (add responsive styles)

- [ ] **Step 1: 添加中等屏幕断点样式**

在样式部分末尾添加：

```scss
// 响应式设计 - 中等屏幕 (1180px)
@media (max-width: 1180px) {
  .indicator-ide {
    padding: 18px;
    
    .grid.grid-cols-12 {
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }
    
    .col-span-3,
    .col-span-5,
    .col-span-4 {
      grid-column: span 6 / span 6;
    }
  }
}
```

- [ ] **Step 2: 添加移动端断点样式**

继续添加：

```scss
// 响应式设计 - 移动端 (760px)
@media (max-width: 760px) {
  .indicator-ide {
    padding: 14px;
    
    .grid.grid-cols-12 {
      grid-template-columns: 1fr;
    }
    
    .col-span-3,
    .col-span-5,
    .col-span-4 {
      grid-column: auto;
    }
    
    .code-editor .code-textarea {
      height: 300px;
      min-height: 300px;
    }
    
    .preview-card .chart-container {
      height: 180px;
    }
  }
}
```

- [ ] **Step 3: 测试响应式布局**

在浏览器中：
1. 调整窗口宽度到 1180px 以下，检查布局变为 2 列
2. 调整窗口宽度到 760px 以下，检查布局变为单列
3. 检查代码编辑器和图表高度在移动端正确调整

- [ ] **Step 4: 提交更改**

```bash
git add src/views/IndicatorIDE/index.vue
git commit -m "style(indicator-ide): add responsive design styles

- 添加 1180px 断点，布局变为 2 列
- 添加 760px 断点，布局变为单列
- 调整移动端代码编辑器高度为 300px
- 调整移动端图表高度为 180px"
```

---

## Task 8: 最终验证和清理

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue`

- [ ] **Step 1: 运行完整的样式验证清单**

在浏览器中逐项检查：

```bash
# 启动开发服务器（如果未运行）
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run dev
```

验证清单：
- [ ] 页面背景色为 `#eef2f7`
- [ ] 卡片圆角为 12px，边框为 `#e2e8f0`
- [ ] 代码编辑器背景为 `#1f2937`，文字色为 `#4ade80`
- [ ] 图表容器高度为 220px，背景为 `#0a0a0f`
- [ ] 运行按钮为绿色 (`#16a34a`)
- [ ] 保存按钮为蓝色 (`#2563eb`)
- [ ] 发布按钮为紫色 (`#9333ea`)
- [ ] 复制按钮为灰色边框样式
- [ ] 指标库激活项为蓝色背景 (`#eff6ff`)
- [ ] 回测结果数值背景为透明
- [ ] 响应式布局在 1180px 和 760px 断点正常工作

- [ ] **Step 2: 对比原型HTML验证**

```bash
# 在浏览器中打开原型HTML
open /Users/mac/Documents/ai/pi-investment/quant-web-v2-prototype.html
```

并排对比：
1. 打开原型HTML，导航到指标IDE部分
2. 打开Vue实现的指标IDE页面
3. 逐个元素对比颜色、间距、圆角
4. 记录任何仍存在的差异

- [ ] **Step 3: 删除备份文件**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
rm src/views/IndicatorIDE/index.vue.backup
```

- [ ] **Step 4: 运行构建测试**

```bash
npm run build
```

预期：构建成功，无错误或警告

- [ ] **Step 5: 最终提交**

```bash
git add src/views/IndicatorIDE/index.vue
git commit -m "style(indicator-ide): complete style alignment with prototype

完成指标IDE页面样式对齐：
- 所有颜色使用 Tailwind slate 色系
- 统一圆角和间距系统
- Element Plus 样式完全覆盖
- 响应式设计完整实现
- 通过所有验证清单项"
```

---

## 验证清单总结

完成所有任务后，确保以下所有项目都已验证通过：

### 视觉样式
- [ ] 页面背景色 `#eef2f7`
- [ ] 卡片圆角 12px，边框 `#e2e8f0`
- [ ] 代码编辑器背景 `#1f2937`，文字 `#4ade80`
- [ ] 图表容器高度 220px，背景 `#0a0a0f`

### 交互元素
- [ ] 运行按钮绿色 `#16a34a`
- [ ] 保存按钮蓝色 `#2563eb`
- [ ] 发布按钮紫色 `#9333ea`
- [ ] 复制按钮灰色边框
- [ ] 指标库激活项蓝色 `#eff6ff`

### 布局和响应式
- [ ] 桌面端 12 列栅格正常
- [ ] 1180px 断点 2 列布局正常
- [ ] 760px 断点单列布局正常
- [ ] 移动端高度调整正确

### 功能测试
- [ ] 所有按钮点击正常
- [ ] 指标列表选择正常
- [ ] 代码编辑器输入正常
- [ ] 图表渲染正常
- [ ] 构建无错误

---

## 潜在问题和解决方案

### 问题1: Element Plus样式优先级不够
**症状**: 自定义样式未生效，仍显示Element Plus默认样式

**解决方案**:
```scss
// 如果 :deep() 不够，添加 !important
:deep(.el-card) {
  border-radius: 12px !important;
}
```

### 问题2: 图表渲染后高度不正确
**症状**: 图表容器高度设置为220px，但实际显示不同

**解决方案**:
```typescript
// 在 renderChart 函数中，确保在 setOption 之前设置容器高度
const chartContainer = chartRef.value
if (chartContainer) {
  chartContainer.style.height = '220px'
}
setOption(option)
```

### 问题3: 响应式断点不触发
**症状**: 调整窗口大小时布局未改变

**解决方案**:
```scss
// 确保媒体查询在 scoped 样式之外，或使用 :deep()
@media (max-width: 1180px) {
  :deep(.grid.grid-cols-12) {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}
```

### 问题4: 颜色在不同浏览器显示不一致
**症状**: 颜色在Chrome和Safari中显示略有差异

**解决方案**:
```scss
// 使用精确的十六进制颜色值，避免使用颜色名称
// 确保所有颜色都是6位十六进制格式
color: #4ade80; // 正确
color: #4ae; // 错误，可能导致不一致
```

---

## 实施注意事项

1. **渐进式修改**: 每个任务独立完成并提交，便于回滚
2. **频繁验证**: 每个任务完成后立即在浏览器中验证
3. **保持备份**: Task 1 创建了备份文件，出问题时可以恢复
4. **对比原型**: 经常与原型HTML对比，确保一致性
5. **测试响应式**: 在不同屏幕尺寸下测试布局
6. **检查构建**: 最后运行构建确保没有引入错误

---

## 完成标准

所有以下条件都满足时，认为实施完成：

1. ✅ 所有8个任务的步骤都已完成
2. ✅ 验证清单中所有项目都通过
3. ✅ 与原型HTML视觉效果一致
4. ✅ 所有交互功能正常工作
5. ✅ 响应式布局在所有断点正常
6. ✅ 构建成功无错误
7. ✅ 所有更改已提交到git

完成后，指标IDE页面将与原型HTML完全一致，提供统一的用户体验。
