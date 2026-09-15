# 需求进度条实施总结

## 目标

在对话框顶部显示**流程图式的需求进度条**，让用户随时知道 agent 做到哪里了。

---

## 已完成 ✅

### 1. 前端组件
- **文件**: `packages/pages/dsh-pmboard/src/client/requirement-progress.ts`
- **功能**: 渲染需求进度条（折叠/展开态）
- **内容**:
  - 流程图（立项 → 需求分析 → 技术设计 → 拆分 → 实施 → 验收 → 完成）
  - 任务列表（✅ 已完成、🔄 进行中、⬜ 待办）
  - 已完成内容列表

---

## 待完成

### 2. 添加样式（10分钟）

**文件**: `packages/pages/dsh-pmboard/src/client/styles.ts`

在 CSS 常量（第 8 行的模板字符串）末尾添加：

```css
/* ============================================ */
/* 需求进度条（会话顶部）                        */
/* ============================================ */

.req-progress-bar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 20px;
  border-radius: 8px;
  margin: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.req-progress-bar:hover {
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.5);
  transform: translateY(-2px);
}

/* ... 其余样式见 requirement-progress.ts 注释 */
```

### 3. 后端 API（30分钟）

**文件**: `packages/pages/dsh-pmboard/src/host/routes.ts`

新增路由：

```typescript
// GET /dashboard/api/reqboard/session/:sessionId/progress
// 返回该会话绑定需求的进度数据

router.get('/session/:sessionId/progress', async (req, res) => {
  const { sessionId } = req.params
  const snapshot = store.snapshot()
  
  // 找到该会话的需求
  const requirement = snapshot.requirements.find(r => 
    r.sourceSessionId === sessionId &&
    isOpenReq(r)
  )
  
  if (!requirement) {
    return res.json({ hasRequirement: false })
  }
  
  // 计算任务进度
  const tasks = snapshot.tasks.filter(t => t.requirementId === requirement.id)
  const done = tasks.filter(t => t.status === 'done').length
  
  // 提取已完成内容
  const completedContent = tasks
    .filter(t => t.status === 'done' && t.completionReport)
    .map(t => t.completionReport!.summary)
  
  res.json({
    requirement: {
      id: requirement.id,
      title: requirement.title,
      status: requirement.status,
      objective: requirement.goal?.objective
    },
    progress: {
      total: tasks.length,
      done,
      percentage: tasks.length > 0 ? Math.round((done / tasks.length) * 100) : 0
    },
    tasks: tasks.map(t => ({
      id: t.id,
      title: t.title,
      status: t.status,
      duration: t.executions.reduce((sum, e) => sum + (e.endAt ? e.endAt - e.startAt : 0), 0)
    })),
    completedContent
  })
})
```

### 4. 前端集成（1小时）

**方案 A: 注入到 DSH Shell**（推荐）

在 `packages/pages/dsh-pmboard/src/index.ts` 中注册一个**会话级 UI 注入点**：

```typescript
// 监听会话创建/切换
ctx.on('session/active', async ({ sessionId }) => {
  // 查询该会话的需求进度
  const progress = await fetch(`/dashboard/api/reqboard/session/${sessionId}/progress`)
    .then(r => r.json())
  
  // 注入到会话顶部
  if (progress.hasRequirement) {
    injectProgressBar(sessionId, progress)
  }
})

function injectProgressBar(sessionId: string, data: any) {
  // 找到会话容器
  const sessionContainer = document.querySelector(`[data-session-id="${sessionId}"]`)
  if (!sessionContainer) return
  
  // 渲染进度条
  const html = renderRequirementProgress(data, false)
  
  // 插入到顶部
  const progressEl = document.createElement('div')
  progressEl.innerHTML = html
  sessionContainer.prepend(progressEl.firstChild!)
  
  // 绑定点击事件（折叠/展开）
  progressEl.addEventListener('click', () => {
    const expanded = progressEl.dataset.expanded === 'true'
    progressEl.dataset.expanded = String(!expanded)
    progressEl.innerHTML = renderRequirementProgress(data, !expanded)
  })
}
```

**方案 B: 独立挂载点**（更简单）

在 DSH Shell 中增加一个全局挂载点：

```html
<!-- apps/web/src/components/ConversationView.vue -->
<div class="conversation-container">
  <div id="req-progress-mount"></div>  <!-- 新增挂载点 -->
  <div class="messages">...</div>
</div>
```

pmboard 插件检测到挂载点后自动渲染。

### 5. 数据刷新（30分钟）

**实时更新进度**：

```typescript
// 每次任务状态变更后，通知前端刷新
store.on('task-updated', ({ taskId, requirementId }) => {
  // SSE 推送更新
  sseManager.broadcast('requirement-progress-update', {
    requirementId,
    taskId
  })
})

// 前端监听 SSE
eventSource.addEventListener('requirement-progress-update', (e) => {
  const { requirementId } = JSON.parse(e.data)
  // 重新拉取数据并更新 UI
  refreshProgressBar(requirementId)
})
```

---

## 实施顺序

1. ✅ **前端组件**（已完成）
2. ⏳ **样式**（10分钟）- 立即做
3. ⏳ **后端 API**（30分钟）- 然后做
4. ⏳ **前端集成**（1小时）- 核心工作
5. ⏳ **数据刷新**（30分钟）- 优化体验

**总计**: 约 2-3 小时完成基础版本

---

## 效果预览

### 折叠态（默认）
```
┌─────────────────────────────────────────────┐
│ 需求: 实现用户登录 ▼                        │
│ ✅ → ✅ → ✅ → 🔄 → ⬜ → ⬜   3/5 任务完成(60%) │
└─────────────────────────────────────────────┘
```

### 展开态（点击后）
```
┌─────────────────────────────────────────────┐
│ 需求: 实现用户登录 ▲                        │
│                                              │
│ 为什么做：新用户系统需要登录认证             │
│                                              │
│ 流程进度：                                   │
│ ✅立项 → ✅需求分析 → ✅技术设计 → 🔄实施 → ⬜验收│
│                                              │
│ 任务详情：(3/5 完成)                         │
│ ✅ 登录API (2h)                              │
│ ✅ 登录页面 (1.5h)                           │
│ ✅ 单元测试 (1h)                             │
│ 🔄 集成测试 (进行中, 0.5h)                  │
│ ⬜ 文档更新 (待办)                           │
│                                              │
│ 已完成内容：                                 │
│ • 登录API已实现并通过单测                    │
│ • 登录页面UI完成                             │
│ • 单元测试覆盖率85%                          │
└─────────────────────────────────────────────┘
```

---

## 关键设计决策

### Q: 为什么不用新工具，而是用 SystemPrompt 引导？

**A**: 减少侵入性
- Agent 用自己的工具（`memory_write`、`decision_audit`）
- pmboard 只提供数据结构和查询 API
- 通过 SystemPrompt 引导行为，而非强制工具

### Q: 数据从哪里来？

**A**: 多源聚合
- 任务状态：`tasks.status`
- 完成内容：从 `memory_write` 或 `decision_audit` 提取
- 执行时长：`tasks.executions`

### Q: 如何保持实时性？

**A**: SSE 推送 + 定时刷新
- 任务状态变更 → SSE 推送
- 前端每 30 秒轮询一次（兜底）

---

**下一步：添加样式 → 后端 API → 前端集成**
