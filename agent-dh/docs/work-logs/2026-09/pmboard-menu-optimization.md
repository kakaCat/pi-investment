# pmboard 菜单优化方案

## 当前问题

1. **菜单入口是按钮，不显示内容** - 点击后打开全屏看板，平时看不到需求列表
2. **样式简陋** - 只有一个图标按钮
3. **无法快速跳转** - 看到需求后还要手动找对应会话

---

## 优化方案

### 方案 A: 下拉菜单（推荐）

**效果**：
```
┌─ Sidebar ────────┐
│ 聊天             │
│ 搜索             │
│ 项目看板 ▼       │  ← 鼠标悬停展开
│   └─────────────┐│
│   【进行中需求】││
│   • REQ-001     ││  ← 点击跳转到对应会话
│     用户登录    ││
│     w-abc123    ││
│     🔄 3/5 任务  ││
│                 ││
│   • REQ-002     ││
│     数据导出    ││
│     w-def456    ││
│     ⬜ 0/3 任务  ││
│   ─────────────┘│
└──────────────────┘
```

**特点**：
- 鼠标悬停自动展开
- 显示需求标题、窗口码、进度
- 点击需求 → 跳转到对应会话
- 不遮挡主界面

### 方案 B: 侧边栏嵌入面板

**效果**：
```
┌─ Sidebar ────────┐
│ 聊天             │
│ 搜索             │
│ ┌──项目看板──┐  │
│ │ REQ-001     │  │
│ │ 用户登录    │  │
│ │ w-abc123    │  │
│ │ 🔄 3/5      │  │
│ ├─────────────┤  │
│ │ REQ-002     │  │
│ │ 数据导出    │  │
│ │ w-def456    │  │
│ │ ⬜ 0/3      │  │
│ └─────────────┘  │
└──────────────────┘
```

**特点**：
- 始终可见
- 占用 sidebar 空间
- 可折叠

---

## 推荐实施：方案 A（下拉菜单）

### 1. 修改菜单按钮（增加 hover 下拉）

```typescript
// packages/pages/dsh-pmboard/src/client/footer-action.ts

export function ReqboardFooterAction(props: FooterActionProps): unknown {
  const { wide } = props
  
  // 新增：下拉菜单容器
  return createElement('div', {
    className: 'dsh-reqboard-menu-container',
    onMouseEnter: () => {
      // 鼠标悬停 → 拉取需求列表并显示下拉菜单
      fetchRequirementsAndShowDropdown()
    },
    onMouseLeave: () => {
      // 鼠标离开 → 隐藏下拉菜单
      hideDropdown()
    }
  }, [
    // 原按钮
    createElement('button', {
      type: 'button',
      className: wide ? 'dsh-reqboard-foot wide' : 'dsh-reqboard-foot rail',
      title: '项目看板',
      onClick: () => {
        // 点击仍然打开全屏看板
        window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { open: true } }))
      }
    }, ...),
    
    // 新增：下拉菜单
    createElement('div', {
      className: 'dsh-reqboard-dropdown',
      style: { display: 'none' } // 默认隐藏，hover 时显示
    }, [
      // 需求列表（动态渲染）
    ])
  ])
}
```

### 2. 新增样式

```css
/* 菜单容器 */
.dsh-reqboard-menu-container {
  position: relative;
}

/* 下拉菜单 */
.dsh-reqboard-dropdown {
  position: absolute;
  left: 100%;
  top: 0;
  width: 280px;
  max-height: 400px;
  overflow-y: auto;
  background: var(--dsw-bg-primary, white);
  border: 1px solid var(--dsw-border, rgba(128,128,128,.2));
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,.15);
  z-index: 1000;
  margin-left: 8px;
}

/* 下拉菜单标题 */
.dsh-reqboard-dropdown-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.1));
  font-weight: 600;
  font-size: 13px;
  color: var(--dsw-text-primary, #333);
}

/* 需求卡片 */
.dsh-reqboard-dropdown-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
  cursor: pointer;
  transition: background 0.15s;
}

.dsh-reqboard-dropdown-item:hover {
  background: var(--dsw-hover, rgba(128,128,128,.08));
}

.dsh-reqboard-dropdown-item:last-child {
  border-bottom: none;
}

/* 需求标题 */
.dsh-reqboard-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--dsw-text-primary, #333);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 窗口码 */
.dsh-reqboard-item-window {
  font-size: 11px;
  color: var(--dsw-text-secondary, #999);
  font-family: monospace;
}

/* 进度条 */
.dsh-reqboard-item-progress {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dsh-reqboard-progress-bar {
  flex: 1;
  height: 4px;
  background: var(--dsw-border, rgba(128,128,128,.15));
  border-radius: 2px;
  overflow: hidden;
}

.dsh-reqboard-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 2px;
  transition: width 0.3s;
}

.dsh-reqboard-progress-text {
  font-size: 11px;
  color: var(--dsw-text-secondary, #999);
  white-space: nowrap;
}

/* 空状态 */
.dsh-reqboard-dropdown-empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--dsw-text-secondary, #999);
  font-size: 13px;
}
```

### 3. 新增 API 获取需求列表

```typescript
// packages/pages/dsh-pmboard/src/client/api.ts

export async function fetchRequirementsSummary(): Promise<RequirementSummary[]> {
  const res = await fetch('/dashboard/api/reqboard/requirements/summary')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

interface RequirementSummary {
  id: string
  title: string
  status: string
  sourceSessionId: string
  windowCode: string // w-abc123
  tasksDone: number
  tasksTotal: number
  percentage: number
}
```

### 4. 后端 API（新增）

```typescript
// packages/pages/dsh-pmboard/src/host/routes.ts

router.get('/requirements/summary', async (_req, res) => {
  const snapshot = store.snapshot()
  
  const summary = snapshot.requirements
    .filter(r => r.status !== 'archived' && r.status !== 'canceled')
    .map(req => {
      const tasks = snapshot.tasks.filter(t => t.requirementId === req.id)
      const done = tasks.filter(t => t.status === 'done').length
      
      return {
        id: req.id,
        title: req.title,
        status: req.status,
        sourceSessionId: req.sourceSessionId,
        windowCode: windowCodeFromSessionId(req.sourceSessionId),
        tasksDone: done,
        tasksTotal: tasks.length,
        percentage: tasks.length > 0 ? Math.round((done / tasks.length) * 100) : 0,
      }
    })
    .sort((a, b) => {
      // 按状态排序：implementing > planning > brainstorming > ...
      const order = ['implementing', 'planning', 'brainstorming', 'decomposing', 'accepting', 'done', 'draft']
      return order.indexOf(a.status) - order.indexOf(b.status)
    })
  
  res.json(summary)
})
```

### 5. 点击跳转逻辑

```typescript
// 点击需求 → 跳转到对应会话
function handleRequirementClick(req: RequirementSummary) {
  // 使用现有的 session-jump 工具
  jumpToSession(req.sourceSessionId)
}
```

---

## 实施步骤

1. ✅ **后端 API**（30分钟）
   - 新增 `GET /requirements/summary` 路由
   
2. ✅ **前端下拉菜单**（1小时）
   - 修改 footer-action.ts
   - 新增下拉菜单组件
   - 绑定 hover 事件
   
3. ✅ **样式优化**（30分钟）
   - 添加下拉菜单样式
   - 需求卡片样式
   - 进度条样式
   
4. ✅ **跳转集成**（15分钟）
   - 点击需求 → jumpToSession

**总计**：约 2 小时

---

## 效果演示

### 鼠标悬停前
```
┌─ Sidebar ────┐
│ 项目看板 🗂️  │
└──────────────┘
```

### 鼠标悬停后
```
┌─ Sidebar ────┐────────────────────────┐
│ 项目看板 🗂️  │ 【进行中需求 (3)】     │
└──────────────┘ ├───────────────────────┤
                 │ • REQ-001 用户登录功能│
                 │   w-abc123            │
                 │   ▓▓▓▓▓░░░ 60% (3/5)  │
                 ├───────────────────────┤
                 │ • REQ-002 数据导出    │
                 │   w-def456            │
                 │   ░░░░░░░░ 0% (0/3)   │
                 ├───────────────────────┤
                 │ • REQ-003 性能优化    │
                 │   w-ghi789            │
                 │   ▓▓▓▓▓▓▓░ 80% (4/5)  │
                 └───────────────────────┘
```

点击任意需求 → 自动跳转到对应会话窗口

---

**要开始实施吗？**
