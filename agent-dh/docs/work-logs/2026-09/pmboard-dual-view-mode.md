# pmboard 双视图模式实施方案

## 目标

在项目看板页面增加**列表视图**和**泳道视图**切换。

---

## 设计

### 视图切换按钮

```
┌─ 项目看板 ──────────────────────────┐
│ 📊 项目看板    [📋 列表] [📊 泳道✓] │
├──────────────────────────────────────┤
```

### 列表视图

```
┌──────────────────────────────────────┐
│ REQ-001 用户登录功能                  │
│ ─────────────────────────────────────│
│ 窗口: w-abc123  |  状态: 实施中      │
│ 进度: ████████░░░░ 60% (3/5 任务)    │
│ 最后更新: 2026-09-15 14:30          │
│ [查看详情] [跳转会话]                │
├──────────────────────────────────────┤
│ REQ-002 数据导出功能                  │
│ ─────────────────────────────────────│
│ 窗口: w-def456  |  状态: 技术设计    │
│ 进度: ░░░░░░░░░░ 0% (0/3 任务)      │
│ 最后更新: 2026-09-14 10:20          │
│ [查看详情] [跳转会话]                │
└──────────────────────────────────────┘
```

### 泳道视图（保持现有）

```
┌─立项──┬─需求分析┬─技术设计┬─实施───┐
│ REQ-  │         │         │ REQ-   │
│ 003   │         │         │ 001    │
│       │         │         │ REQ-   │
│       │         │         │ 002    │
└───────┴─────────┴─────────┴────────┘
```

---

## 实施步骤

### 1. 增加视图状态管理（20分钟）

```typescript
// packages/pages/dsh-pmboard/src/client/types.ts

export type BoardViewMode = 'lanes' | 'list'

export interface BoardState {
  // ... 现有字段
  viewMode: BoardViewMode  // 新增
}
```

### 2. 新增列表视图渲染函数（1小时）

```typescript
// packages/pages/dsh-pmboard/src/client/view.ts

/**
 * 渲染列表视图
 */
export function buildListView(cards: ReqCard[]): string {
  if (cards.length === 0) {
    return buildEmpty('暂无进行中的需求')
  }

  const items = cards.map(card => {
    const { req, doneCount, totalCount } = card
    const percentage = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
    
    return `
      <div class="dsh-pm-list-item" data-action="view-req" data-req-id="${esc(req.id)}">
        <div class="dsh-pm-list-header">
          <h3 class="dsh-pm-list-title">${esc(req.id)} ${esc(req.title)}</h3>
          <span class="dsh-pm-list-badge ${statusClass(req.status)}">${statusLabel(req.status)}</span>
        </div>
        
        <div class="dsh-pm-list-meta">
          <span class="dsh-pm-list-window">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8s3.58 8 8 8 8-3.58 8-8-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6z"/>
            </svg>
            ${windowCodeFromSessionId(req.sourceSessionId)}
          </span>
          <span class="dsh-pm-list-time">${formatTime(req.updatedAt)}</span>
        </div>
        
        <div class="dsh-pm-list-progress">
          <div class="dsh-pm-progress-bar">
            <div class="dsh-pm-progress-fill" style="width: ${percentage}%"></div>
          </div>
          <span class="dsh-pm-progress-text">${percentage}% (${doneCount}/${totalCount} 任务)</span>
        </div>
        
        <div class="dsh-pm-list-actions">
          <button class="dsh-pm-list-btn" data-action="view-req" data-req-id="${esc(req.id)}">
            查看详情
          </button>
          <button class="dsh-pm-list-btn primary" data-action="jump-session" data-session-id="${esc(req.sourceSessionId)}">
            跳转会话 →
          </button>
        </div>
      </div>
    `
  }).join('')

  return `
    <div class="dsh-pm-list-view">
      ${items}
    </div>
  `
}

function statusClass(status: string): string {
  const map: Record<string, string> = {
    draft: 'status-draft',
    brainstorming: 'status-brainstorming',
    planning: 'status-planning',
    decomposing: 'status-decomposing',
    implementing: 'status-implementing',
    accepting: 'status-accepting',
    done: 'status-done',
  }
  return map[status] || 'status-default'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    draft: '立项',
    brainstorming: '需求分析',
    planning: '技术设计',
    decomposing: '拆分',
    implementing: '实施中',
    accepting: '验收',
    done: '完成',
  }
  return map[status] || status
}
```

### 3. 增加视图切换按钮（30分钟）

```typescript
// packages/pages/dsh-pmboard/src/client/view.ts

export function buildBoard(state: BoardState): string {
  const cards = toReqCards(state)
  const { viewMode } = state
  
  // 视图切换按钮
  const viewSwitcher = `
    <div class="dsh-pm-view-switcher">
      <button 
        class="dsh-pm-view-btn ${viewMode === 'list' ? 'active' : ''}"
        data-action="switch-view"
        data-view="list"
        title="列表视图">
        📋 列表
      </button>
      <button 
        class="dsh-pm-view-btn ${viewMode === 'lanes' ? 'active' : ''}"
        data-action="switch-view"
        data-view="lanes"
        title="泳道视图">
        📊 泳道
      </button>
    </div>
  `
  
  // 根据 viewMode 渲染不同视图
  const content = viewMode === 'list' 
    ? buildListView(cards)
    : buildLanesView(cards)  // 现有的泳道视图
  
  return `
    <div class="dsh-pm-board">
      <div class="dsh-pm-head">
        <h1 class="dsh-pm-title">📊 项目看板</h1>
        ${viewSwitcher}
      </div>
      <div class="dsh-pm-content">
        ${content}
      </div>
    </div>
  `
}

// 将现有的泳道渲染逻辑提取为 buildLanesView
function buildLanesView(cards: ReqCard[]): string {
  // ... 现有的泳道渲染代码
}
```

### 4. 事件处理（30分钟）

```typescript
// packages/pages/dsh-pmboard/src/client/board-mount.ts

function handleAction(e: Event) {
  // ... 现有事件处理
  
  // 新增：视图切换
  if (action === 'switch-view') {
    const view = target.dataset.view as BoardViewMode
    if (view) {
      state.viewMode = view
      render()
    }
    return
  }
  
  // 新增：跳转会话
  if (action === 'jump-session') {
    const sessionId = target.dataset.sessionId
    if (sessionId) {
      jumpToSession(sessionId)
    }
    return
  }
}
```

### 5. 样式（1小时）

```css
/* 视图切换按钮 */
.dsh-pm-view-switcher {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.dsh-pm-view-btn {
  padding: 6px 16px;
  border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
  border-radius: 6px;
  background: transparent;
  color: var(--dsw-text-secondary, #666);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.dsh-pm-view-btn:hover {
  background: var(--dsw-hover, rgba(128,128,128,.08));
  color: var(--dsw-text-primary, #333);
}

.dsh-pm-view-btn.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: transparent;
}

/* 列表视图 */
.dsh-pm-list-view {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.dsh-pm-list-item {
  background: var(--dsw-bg-secondary, #f8f9fa);
  border: 1px solid var(--dsw-border, rgba(128,128,128,.15));
  border-radius: 8px;
  padding: 16px;
  transition: all 0.2s;
  cursor: pointer;
}

.dsh-pm-list-item:hover {
  border-color: #667eea;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
  transform: translateY(-2px);
}

/* 列表项头部 */
.dsh-pm-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.dsh-pm-list-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--dsw-text-primary, #333);
}

.dsh-pm-list-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-implementing {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.status-planning {
  background: #ffd93d;
  color: #333;
}

.status-brainstorming {
  background: #6bcf7f;
  color: white;
}

/* 元信息 */
.dsh-pm-list-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--dsw-text-secondary, #999);
}

.dsh-pm-list-window {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: monospace;
}

/* 进度条 */
.dsh-pm-list-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.dsh-pm-progress-bar {
  flex: 1;
  height: 6px;
  background: var(--dsw-border, rgba(128,128,128,.15));
  border-radius: 3px;
  overflow: hidden;
}

.dsh-pm-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 3px;
  transition: width 0.3s;
}

.dsh-pm-progress-text {
  font-size: 12px;
  color: var(--dsw-text-secondary, #999);
  white-space: nowrap;
  min-width: 90px;
}

/* 操作按钮 */
.dsh-pm-list-actions {
  display: flex;
  gap: 8px;
}

.dsh-pm-list-btn {
  padding: 6px 16px;
  border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
  border-radius: 6px;
  background: transparent;
  color: var(--dsw-text-secondary, #666);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.dsh-pm-list-btn:hover {
  background: var(--dsw-hover, rgba(128,128,128,.08));
  color: var(--dsw-text-primary, #333);
  border-color: var(--dsw-border, rgba(128,128,128,.4));
}

.dsh-pm-list-btn.primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: transparent;
}

.dsh-pm-list-btn.primary:hover {
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  transform: translateY(-1px);
}
```

---

## 实施顺序

1. ✅ **类型定义**（10分钟）- 增加 `BoardViewMode`
2. ✅ **列表视图渲染**（1小时）- `buildListView` 函数
3. ✅ **视图切换按钮**（30分钟）- 修改 `buildBoard`
4. ✅ **事件处理**（30分钟）- 切换视图、跳转会话
5. ✅ **样式**（1小时）- 列表视图样式

**总计**：约 3 小时

---

## 效果对比

### 列表视图（新增）
- ✅ 一目了然看到所有需求
- ✅ 进度条直观
- ✅ 一键跳转会话
- ✅ 适合快速浏览

### 泳道视图（保留）
- ✅ 可视化流程
- ✅ 拖拽管理（如果实现）
- ✅ 适合项目管理视角

---

**要开始实施吗？**
