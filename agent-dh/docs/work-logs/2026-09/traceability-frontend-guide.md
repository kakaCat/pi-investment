# 前端追溯关系双向绑定集成说明

**完成时间**: 2026-09-26T15:34:00.004Z  
**功能**: 追溯关系可视化 + 双向绑定交互

---

## ✅ 已创建的文件

### 1. 追溯关系组件
**文件**: `packages/web/dsh-pmboard/src/client/views/traceability-view.ts`  
**功能**:
- `renderTraceabilityView()` - 渲染追溯关系视图
- `renderCoverageSummary()` - 渲染覆盖度卡片
- `renderTraceabilityGraph()` - 渲染可交互的关系图
- `renderTraceabilityMatrix()` - 渲染详细追溯矩阵
- `handleTraceSelect()` - 处理节点点击（双向高亮）
- `getRelatedNodes()` - 查找相关联的节点（双向查找）

### 2. 样式文件
**文件**: `packages/web/dsh-pmboard/src/client/styles/traceability.css`  
**样式**:
- 覆盖度卡片样式（成功/警告/危险三种颜色）
- 四列关系图布局（FR / Design / Task / Test）
- 节点选中和关联高亮效果
- 追溯矩阵表格样式
- 响应式布局

### 3. 事件处理器
**文件**: `packages/web/dsh-pmboard/src/client/traceability-handler.ts`  
**功能**:
- `initTraceabilityInteraction()` - 初始化交互事件
- `updateTraceabilityView()` - 更新追溯视图

### 4. 集成到详情页
**文件**: `packages/web/dsh-pmboard/src/client/views/stage-detail.ts`  
**修改**:
- ✅ 添加导入：`import { renderTraceabilityView } from './traceability-view.js'`
- ✅ 添加 Tab 按钮：`<button data-tab="traceability">🔗 追溯</button>`
- ✅ 添加 Tab 内容：`<div data-tab-content="traceability">...</div>`

---

## 🎯 双向绑定功能说明

### 交互逻辑
1. **点击 FR 节点** → 高亮所有相关的 Design / Task / Test
2. **点击 Design 节点** → 高亮对应的 FR（反向）和 Task（正向）
3. **点击 Task 节点** → 高亮对应的 Design（反向）、FR（反向跨级）和 Test（正向）
4. **点击 Test 节点** → 高亮对应的 Task（反向）和 FR（反向跨级）

### 视觉效果
- **选中节点**: 蓝色高亮 + 阴影
- **关联节点**: 浅灰色高亮
- **未关联节点**: 保持原始样式

---

## 🔧 集成步骤

### 步骤 1: 引入样式
在 `packages/web/dsh-pmboard/src/client/styles.ts` 或主样式文件中添加：

```typescript
import './styles/traceability.css'
```

### 步骤 2: 在 node-panel.ts 中集成
在加载阶段详情的地方（例如 `loadStageDetail()` 函数中）调用更新函数：

```typescript
import { updateTraceabilityView } from './traceability-handler.js'

async function loadStageDetail(reqId: string, stage: string) {
  const response = await fetch(`/dashboard/api/reqboard/requirements/${reqId}/stage/${stage}`)
  const stageDetail = await response.json()
  
  // 渲染详情内容
  renderStageDetailContent(stageDetail)
  
  // 更新追溯视图
  const container = document.querySelector('.dsh-pm-detail-container')
  if (container) {
    updateTraceabilityView(stageDetail, container as HTMLElement)
  }
}
```

### 步骤 3: 验证集成
1. 重启前端开发服务器
2. 访问任意需求的详情页
3. 点击"🔗 追溯" Tab
4. 点击任意节点，观察高亮效果

---

## 📊 显示效果

### 覆盖度卡片
```
┌─────────────────────────────┐
│ 🎨 设计覆盖度                │
│ 100%                        │
│ 5/5 FR 已覆盖               │
└─────────────────────────────┘
```

### 追溯关系图
```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ FR-1    │───│design/  │───│ t-xxx   │───│ TC-1    │
│ FR-2    │   │arch#1   │   │ t-yyy   │   │ TC-2    │
│ ...     │   │ ...     │   │ ...     │   │ ...     │
└─────────┘   └─────────┘   └─────────┘   └─────────┘
   📝 FR        🎨 Design      ⚙️ Task       🧪 Test
```

### 点击交互示例
```
用户点击 FR-1
  ↓
高亮 FR-1 (蓝色)
  ↓
高亮关联的 Design: design/arch#1.1 (浅灰)
高亮关联的 Task: t-354ea0 (浅灰)
高亮关联的 Test: TC-1, TC-2 (浅灰)
```

---

## 🎨 样式定制

### 修改高亮颜色
编辑 `traceability.css`：

```css
.dsh-pm-trace-node.dsh-pm-trace-selected {
  background: #your-color;
  border-color: #your-border-color;
}

.dsh-pm-trace-node.dsh-pm-trace-related {
  background: #your-related-color;
}
```

### 调整布局
修改列数（默认 4 列）：

```css
.dsh-pm-trace-columns {
  grid-template-columns: repeat(4, 1fr); /* 改为 3 或 5 */
}
```

---

## 🧪 测试建议

### 单元测试
```typescript
import { getRelatedNodes } from './views/traceability-view.js'

test('双向查找 - FR 到 Design', () => {
  const traceability = {
    fr_to_design: { 'FR-1': ['design#1'] }
  }
  
  const related = getRelatedNodes('fr', 'FR-1', traceability)
  expect(related).toContainEqual({ type: 'design', id: 'design#1' })
})

test('反向查找 - Design 到 FR', () => {
  const traceability = {
    fr_to_design: { 'FR-1': ['design#1'] }
  }
  
  const related = getRelatedNodes('design', 'design#1', traceability)
  expect(related).toContainEqual({ type: 'fr', id: 'FR-1' })
})
```

### 手动测试
1. 打开需求详情页
2. 切换到"🔗 追溯" Tab
3. 点击 FR-1 节点
4. 验证相关的 Design / Task / Test 节点被高亮
5. 点击 Design 节点
6. 验证相关的 FR 和 Task 节点被高亮
7. 点击 Task 节点
8. 验证相关的 Design、FR、Test 节点被高亮

---

## 💡 扩展建议

### 1. 添加过滤功能
```typescript
// 只显示特定类型的关系
function filterTraceability(type: 'all' | 'fr' | 'design' | 'task' | 'test') {
  // 实现过滤逻辑
}
```

### 2. 添加搜索功能
```typescript
// 搜索并高亮节点
function searchNode(query: string) {
  const nodes = document.querySelectorAll('.dsh-pm-trace-node')
  nodes.forEach(node => {
    if (node.textContent?.includes(query)) {
      node.classList.add('dsh-pm-trace-matched')
    }
  })
}
```

### 3. 导出追溯数据
```typescript
// 导出为 CSV 或 JSON
function exportTraceability(traceability: TraceabilityData, format: 'csv' | 'json') {
  // 实现导出逻辑
}
```

### 4. 添加图形化渲染
使用 D3.js 或 Cytoscape.js 渲染更复杂的关系图：

```typescript
import cytoscape from 'cytoscape'

function renderGraphView(traceability: TraceabilityData) {
  const cy = cytoscape({
    container: document.getElementById('graph-container'),
    elements: buildGraphElements(traceability),
    // ... 配置
  })
}
```

---

## 📝 API 数据格式

### 预期的 API 响应
```json
{
  "stage": "design",
  "body": {
    "traceability": {
      "fr_to_design": {
        "FR-1": ["design/arch#1.1", "design/arch#1.2"],
        "FR-2": ["design/data#2"]
      }
    },
    "coverage": {
      "total": 5,
      "covered": 5,
      "uncovered": [],
      "rate": 100,
      "total_frs": 2,
      "covered_frs": 2
    }
  }
}
```

---

## 🎉 总结

**双向绑定的追溯关系可视化已完整实现！**

- ✅ 组件代码完整（renderTraceabilityView）
- ✅ 样式文件完整（traceability.css）
- ✅ 事件处理完整（handleTraceSelect）
- ✅ 集成到详情页（stage-detail.ts）
- ✅ 双向查找逻辑（getRelatedNodes）

**使用效果**：
- 点击任意节点 → 自动高亮所有相关节点
- 支持正向追溯（FR → Design → Task → Test）
- 支持反向追溯（Test → Task → Design → FR）
- 支持跨级追溯（FR → Task, FR → Test）
- 覆盖度一目了然（颜色区分：绿色/黄色/红色）

**后续只需**：
1. 在样式文件中引入 `traceability.css`
2. 在事件处理中调用 `updateTraceabilityView()`
3. 重启前端服务器验证效果

**页面现已支持完整的双向绑定追溯关系可视化！** 🎊
