# RTM YAML 与会话流程图节点集成方案

> 调研日期：2026-09-26  
> 目标 UI：会话页面的流程图节点（node-panel.ts）

---

## 🎯 正确的 UI 位置

**会话流程图节点** = `packages/web/dsh-pmboard/src/client/node-panel.ts`

这是显示在**会话右侧面板**的需求流程节点详情，包含：
- REQ 胶囊 + 需求标题
- 状态胶囊 + 一句话进展
- 各阶段详情（draft/brainstorming/design/decomposing/implementing/accepting/archived）

---

## 📊 现有节点结构分析

### 实施节点（implementing）- 已有双视图

**位置**：`renderImplViews()` 函数（lines 204-212）

**现有内容**：
```typescript
[DAG] [泳道] 两个 Tab

Tab 1 - DAG 视图：
  🔀 任务依赖关系（按最长依赖链分层）
  - Layer 0: t1, t2
  - Layer 1: t3, t4
  - Layer 2: t5

Tab 2 - 泳道视图：
  6 列看板（待开始/开发中/联调中/测试中/待复核/已完成）
  每列显示该状态的任务卡片
```

### 其他节点

- **draft** - 立项信息
- **brainstorming** - 需求文档
- **design** - 设计文档列表
- **decomposing** - 拆分计划 + DAG 层级
- **accepting** - 验收材料 + 验收单统计
- **archived** - 归档文档 + 合并项目

---

## 🚀 集成方案：新增「追溯」Tab

### 方案概述

在 **implementing 节点** 的双视图（DAG/泳道）基础上，**新增第 3 个 Tab：追溯**

```
[DAG] [泳道] [追溯] ← 新增
```

---

## 💡 追溯 Tab 内容设计

### Layout：垂直追溯链

```
┌─────────────────────────────────┐
│ 🔗 追溯链可视化                  │
├─────────────────────────────────┤
│                                 │
│  📋 需求层 (6 个 FR)            │
│  ├─ ✅ FR-1: 删除过时工具        │
│  ├─ ✅ FR-2: Dive Armed 默认化   │
│  └─ ❌ FR-3: xxx (无设计)       │
│                                 │
│  🎨 设计层 (8 个章节)           │
│  ├─ ✅ design/arch#1.1          │
│  │   serves: FR-1 → 2 任务      │
│  ├─ ❌ design/arch#2            │
│  │   serves: FR-2 → 0 任务      │
│  └─ ...                         │
│                                 │
│  ⚙️ 任务层 (8 个任务)           │
│  ├─ ✅ t-354ea0                 │
│  │   implements: design/arch#1.1│
│  │   → 1 测试                   │
│  ├─ ❌ t-0c18e3 (无测试)        │
│  └─ ...                         │
│                                 │
│  📊 覆盖度统计                   │
│  ├─ 设计覆盖: 100% (6/6)        │
│  ├─ 实施覆盖: 100% (8/8)        │
│  └─ 测试覆盖: 25% (2/8)         │
│                                 │
└─────────────────────────────────┘
```

---

## 🔧 实现细节

### 1. 修改 renderImplViews()

```typescript
// packages/web/dsh-pmboard/src/client/node-panel.ts (line 204)

function renderImplViews(
  p: Extract<StageDetail, { stage: 'implementing' }>,
  rtm?: RTMDocument  // ← 新增参数
): string {
  const tasks = p.body.tasks ?? []
  
  return '<div class="dsh-pm-np-tabs">' +
    '<button type="button" class="dsh-pm-np-tab is-active" data-action="np-switch-view" data-view="flow">DAG</button>' +
    '<button type="button" class="dsh-pm-np-tab" data-action="np-switch-view" data-view="list">泳道</button>' +
    '<button type="button" class="dsh-pm-np-tab" data-action="np-switch-view" data-view="trace">追溯</button>' +  // ← 新增 Tab
  '</div>' +
  '<div class="dsh-pm-np-pane" data-pane="flow">...' +
  '<div class="dsh-pm-np-pane" data-pane="list" hidden>...' +
  '<div class="dsh-pm-np-pane" data-pane="trace" hidden>' +  // ← 新增面板
    renderTraceView(rtm, tasks) +
  '</div>'
}
```

### 2. 新增 renderTraceView() 函数

```typescript
/**
 * 渲染追溯链视图（从 rtm.yml 读取数据）
 */
function renderTraceView(rtm: RTMDocument | undefined, tasks: StageTaskRef[]): string {
  if (!rtm) {
    return '<div class="dsh-pm-np-pane-caption">⏳ 加载追溯数据中...</div>' +
      '<div class="dsh-pm-np-empty">追溯数据生成中，请稍候</div>'
  }
  
  const parts: string[] = []
  
  // 覆盖度统计卡片
  parts.push(renderTraceCoverage(rtm.coverage))
  
  // 需求层
  parts.push('<div class="dsh-pm-np-trace-level">' +
    '<div class="dsh-pm-np-sec-label">📋 需求层 (' + rtm.requirements.length + ')</div>' +
    '<div class="dsh-pm-np-trace-items">' +
      rtm.requirements.map(fr => {
        const hasDesign = rtm.design_sections.some(ds => ds.serves.includes(fr.id))
        return '<div class="dsh-pm-np-trace-item ' + (hasDesign ? 'is-covered' : 'is-uncovered') + '">' +
          '<span class="dsh-pm-np-trace-icon">' + (hasDesign ? '✅' : '❌') + '</span>' +
          '<span class="dsh-pm-np-trace-label">' + esc(fr.id) + ': ' + esc(fr.title) + '</span>' +
          (!hasDesign ? '<span class="dsh-pm-np-tag-warn">无设计</span>' : '') +
        '</div>'
      }).join('') +
    '</div>' +
  '</div>')
  
  // 设计层
  parts.push('<div class="dsh-pm-np-trace-level">' +
    '<div class="dsh-pm-np-sec-label">🎨 设计层 (' + rtm.design_sections.length + ')</div>' +
    '<div class="dsh-pm-np-trace-items">' +
      rtm.design_sections.map(ds => {
        const hasTasks = rtm.tasks.some(t => (t.implements_design ?? []).includes(ds.ref))
        return '<div class="dsh-pm-np-trace-item ' + (hasTasks ? 'is-covered' : 'is-uncovered') + '">' +
          '<span class="dsh-pm-np-trace-icon">' + (hasTasks ? '✅' : '❌') + '</span>' +
          '<span class="dsh-pm-np-trace-label">' + esc(ds.ref) + '</span>' +
          '<span class="dsh-pm-np-trace-meta">← serves ' + ds.serves.join(', ') + '</span>' +
          (!hasTasks ? '<span class="dsh-pm-np-tag-warn">无任务</span>' : '') +
        '</div>'
      }).join('') +
    '</div>' +
  '</div>')
  
  // 任务层
  parts.push('<div class="dsh-pm-np-trace-level">' +
    '<div class="dsh-pm-np-sec-label">⚙️ 任务层 (' + rtm.tasks.length + ')</div>' +
    '<div class="dsh-pm-np-trace-items">' +
      rtm.tasks.map(t => {
        const hasTests = (rtm.test_cases ?? []).some(tc => (tc.covers_tasks ?? []).includes(t.id))
        return '<div class="dsh-pm-np-trace-item ' + (hasTests ? 'is-covered' : 'is-uncovered') + '">' +
          '<span class="dsh-pm-np-trace-icon">' + (hasTests ? '✅' : '❌') + '</span>' +
          '<span class="dsh-pm-np-trace-label">' + esc(t.id) + ': ' + esc(t.title) + '</span>' +
          '<span class="dsh-pm-np-trace-meta">← implements ' + (t.implements_design ?? []).join(', ') + '</span>' +
          (!hasTests ? '<span class="dsh-pm-np-tag-warn">无测试</span>' : '') +
        '</div>'
      }).join('') +
    '</div>' +
  '</div>')
  
  return '<div class="dsh-pm-np-pane-caption">🔗 需求追溯链（四级完整追溯）</div>' +
    '<div class="dsh-pm-np-trace">' + parts.join('') + '</div>'
}

/**
 * 渲染覆盖度统计卡片
 */
function renderTraceCoverage(coverage: TraceabilityCoverage): string {
  return '<div class="dsh-pm-np-stats">' +
    '<div class="dsh-pm-np-stat ' + (coverage.design_coverage.status === 'complete' ? 'is-pass' : 'is-warn') + '">' +
      '<span class="dsh-pm-np-stat-label">设计覆盖</span>' +
      '<span class="dsh-pm-np-stat-value">' + coverage.design_coverage.coverage_rate + '%</span>' +
      '<span class="dsh-pm-np-stat-detail">' + coverage.design_coverage.covered + '/' + coverage.design_coverage.total + ' FR</span>' +
    '</div>' +
    '<div class="dsh-pm-np-stat ' + (coverage.implementation_coverage.status === 'complete' ? 'is-pass' : 'is-warn') + '">' +
      '<span class="dsh-pm-np-stat-label">实施覆盖</span>' +
      '<span class="dsh-pm-np-stat-value">' + coverage.implementation_coverage.coverage_rate + '%</span>' +
      '<span class="dsh-pm-np-stat-detail">' + coverage.implementation_coverage.covered + '/' + coverage.implementation_coverage.total + ' 设计</span>' +
    '</div>' +
    '<div class="dsh-pm-np-stat ' + (coverage.test_coverage.status === 'complete' ? 'is-pass' : 'is-warn') + '">' +
      '<span class="dsh-pm-np-stat-label">测试覆盖</span>' +
      '<span class="dsh-pm-np-stat-value">' + coverage.test_coverage.coverage_rate + '%</span>' +
      '<span class="dsh-pm-np-stat-detail">' + coverage.test_coverage.tested + '/' + coverage.test_coverage.total + ' 任务</span>' +
    '</div>' +
  '</div>'
}
```

### 3. 修改 renderNodePanel() 入口

```typescript
// line 303
export function renderNodePanel(input: NodePanelInput & { rtm?: RTMDocument }): string {
  // ...
  
  const implViews = stage === 'implementing' 
    ? renderImplViews(payload as Extract<StageDetail, { stage: 'implementing' }>, input.rtm)  // ← 传入 rtm
    : ''
  
  // ...
}
```

---

## 📈 数据流

```
批准计划
  ↓
生成 rtm.yml (confirm-settle.ts)
  ↓
GET /api/requirements/:id/rtm
  ↓
React 组件 fetch RTM 数据
  ↓
renderNodePanel({ ..., rtm })
  ↓
renderImplViews() 的追溯 Tab
```

---

## 🎨 样式补充

```css
/* packages/web/dsh-pmboard/src/client/styles/node-panel.ts */

.dsh-pm-np-trace {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dsh-pm-np-trace-level {
  border-left: 3px solid var(--border-color);
  padding-left: 12px;
}

.dsh-pm-np-trace-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.dsh-pm-np-trace-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  background: var(--bg-subtle);
}

.dsh-pm-np-trace-item.is-covered {
  border-left: 3px solid var(--success-color);
}

.dsh-pm-np-trace-item.is-uncovered {
  border-left: 3px solid var(--error-color);
}

.dsh-pm-np-trace-icon {
  flex-shrink: 0;
  font-size: 16px;
}

.dsh-pm-np-trace-label {
  font-weight: 500;
}

.dsh-pm-np-trace-meta {
  color: var(--text-secondary);
  font-size: 12px;
  margin-left: auto;
}

.dsh-pm-np-tag-warn {
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--warning-bg);
  color: var(--warning-color);
  font-size: 11px;
}
```

---

## ⏱️ 实施工作量

| 任务 | 工作量 |
|------|--------|
| 1. RTM YAML 生成器（后端） | 3-4小时 |
| 2. API 端点（GET /api/requirements/:id/rtm） | 1小时 |
| 3. renderTraceView() 函数 | 2小时 |
| 4. renderTraceCoverage() 函数 | 1小时 |
| 5. 修改 renderImplViews() | 0.5小时 |
| 6. 修改 renderNodePanel() 入口 | 0.5小时 |
| 7. React 组件集成（fetch RTM） | 1小时 |
| 8. 样式调整 | 1小时 |
| 9. 测试验证 | 2小时 |
| **总计** | **12-13小时** |

---

## ✅ 优势

1. **原生集成** - 直接在现有的双视图基础上新增，无需重构
2. **用户体验** - Tab 切换流畅，追溯信息与任务信息平级
3. **性能优化** - RTM YAML 缓存，避免每次实时解析
4. **降级友好** - RTM 不存在时显示加载中，不阻塞其他功能
5. **视觉统一** - 复用现有 node-panel 样式，保持一致性

---

## 🔄 对比之前的方案

| 维度 | 之前方案（需求详情页） | 当前方案（会话节点） |
|------|---------------------|-------------------|
| **位置** | 需求详情页的 Tab | 会话右侧流程节点 |
| **可见性** | 需要点进详情页 | 流程图节点直接展示 |
| **上下文** | 与需求详情绑定 | 与会话流程绑定 |
| **用户习惯** | 查看详细信息 | 快速查看进度 |
| **集成难度** | 中等 | 较低（已有双视图） |

---

## 💡 未来增强

### Phase 2：交互式追溯

- 点击 FR → 高亮所有相关设计/任务
- 点击设计 → 展开任务列表
- 点击任务 → 打开任务卡文档

### Phase 3：追溯链搜索

- 搜索框：输入 FR-1 → 高亮相关链路
- 过滤器：只看未覆盖项

---

## ✅ 推荐决策

**立即实施**：
1. ✅ 阶段1 - RTM YAML 生成（核心）
2. ✅ 阶段2 - API 端点
3. ✅ 阶段3 - 会话节点追溯 Tab

**工期**：2 个工作日（约 12-13 小时）

---

**下一步**：您是否确认立项实施？我可以立即开始实现！
