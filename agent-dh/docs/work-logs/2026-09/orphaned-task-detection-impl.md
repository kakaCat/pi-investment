
# 僵尸任务检测实现方案

## 一、当前 Agent OS 任务存储机制

### 1. 数据流
```
PostgreSQL (tasks 表)
    ↓
TaskRepository.GetScheduledTasks()
    ↓
Scheduler.loadTasksAndDependencies()
    ↓
Scheduler.scheduleTask() → cron 调度器
    ↓
调度器内存中的任务集合
```

### 2. 关键方法

| 方法 | 用途 | 过滤条件 |
|------|------|---------|
| `List(enabledOnly)` | 获取所有任务 | `enabled = true` (可选) |
| `GetScheduledTasks()` | 获取可调度任务 | `enabled = true AND cron IS NOT NULL` |
| `scheduleTask()` | 将任务加载到 cron 调度器 | 已过滤 |

### 3. 僵尸任务产生原因

- **场景 1**：任务被禁用 (`enabled = false`)，但未删除
- **场景 2**：任务 cron 配置为空，无法被调度
- **场景 3**：任务加载失败（如 cron 表达式错误），未进入调度器
- **场景 4**：历史遗留任务（如 `daily_recall_audit`），webhook_url 指向不存在的服务

## 二、检测逻辑实现

### 方法 1：对比数据库 vs 调度器内存

```go
// internal/kernel/scheduler/orphaned_detector.go
package scheduler

import (
    "context"
    "time"
    "github.com/google/uuid"
)

type OrphanedTask struct {
    ID               uuid.UUID `json:"id"`
    Name             string    `json:"name"`
    ScheduleExpr     string    `json:"scheduleExpr"`
    LastRunAt        *time.Time `json:"lastRunAt"`
    CreatedAt        time.Time `json:"createdAt"`
    InScheduler      bool      `json:"inScheduler"`
    InDatabase       bool      `json:"inDatabase"`
    DaysSinceLastRun int       `json:"daysSinceLastRun"`
    Enabled          bool      `json:"enabled"`
    Reason           string    `json:"reason"` // 为什么是僵尸任务
}

func (s *Scheduler) DetectOrphanedTasks(ctx context.Context) ([]*OrphanedTask, error) {
    // 1. 从数据库获取所有任务（包括禁用的）
    allTasks, err := s.taskRepo.List(ctx, false)
    if err != nil {
        return nil, err
    }

    // 2. 从调度器获取已加载的任务 ID 集合
    s.mu.RLock()
    scheduledIDs := make(map[uuid.UUID]bool)
    // 假设调度器有一个 map 存储已调度任务
    for id := range s.tasks {
        scheduledIDs[id] = true
    }
    s.mu.RUnlock()

    // 3. 对比差异
    var orphaned []*OrphanedTask
    now := time.Now()
    
    for _, task := range allTasks {
        inScheduler := scheduledIDs[task.ID]
        
        // 僵尸任务：存在于数据库，但未在调度器中
        if !inScheduler {
            // 获取最后执行时间
            lastRun, _ := s.taskRunRepo.GetLastRun(ctx, task.ID)
            
            var lastRunAt *time.Time
            var daysSince int
            if lastRun != nil {
                lastRunAt = &lastRun.StartedAt
                daysSince = int(now.Sub(lastRun.StartedAt).Hours() / 24)
            } else {
                daysSince = int(now.Sub(task.CreatedAt).Hours() / 24)
            }
            
            // 判断原因
            reason := determineOrphanedReason(task)
            
            orphaned = append(orphaned, &OrphanedTask{
                ID:               task.ID,
                Name:             task.Name,
                ScheduleExpr:     task.Cron,
                LastRunAt:        lastRunAt,
                CreatedAt:        task.CreatedAt,
                InScheduler:      false,
                InDatabase:       true,
                DaysSinceLastRun: daysSince,
                Enabled:          task.Enabled,
                Reason:           reason,
            })
        }
    }
    
    return orphaned, nil
}

func determineOrphanedReason(task *types.Task) string {
    if !task.Enabled {
        return "任务已禁用"
    }
    if task.Cron == "" {
        return "缺少 cron 表达式"
    }
    if task.WebhookURL != "" {
        return "webhook URL 可能不可达"
    }
    return "加载失败或配置错误"
}
```

### 方法 2：检查数据库中长期未执行的任务

```go
func (r *TaskRepository) GetStaleT asks(ctx context.Context, daysThreshold int) ([]*types.Task, error) {
    query := `
        SELECT t.id, t.name, t.cron, t.enabled, t.created_at, 
               MAX(tr.started_at) as last_run_at
        FROM tasks t
        LEFT JOIN task_runs tr ON t.id = tr.task_id
        GROUP BY t.id
        HAVING MAX(tr.started_at) IS NULL 
            OR MAX(tr.started_at) < NOW() - INTERVAL '$1 days'
        ORDER BY last_run_at ASC NULLS FIRST
    `
    // ... 执行查询
}
```

## 三、API 实现

### 1. 检测接口

```go
// internal/api/scheduler_handler.go
func (h *SchedulerHandler) GetOrphanedTasks(c *gin.Context) {
    ctx := c.Request.Context()
    
    orphaned, err := h.scheduler.DetectOrphanedTasks(ctx)
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(200, gin.H{
        "success": true,
        "data": gin.H{
            "orphanedTasks": orphaned,
            "count": len(orphaned),
        },
    })
}
```

### 2. 清理接口

```go
func (h *SchedulerHandler) DeleteOrphanedTask(c *gin.Context) {
    taskID := c.Param("id")
    id, err := uuid.Parse(taskID)
    if err != nil {
        c.JSON(400, gin.H{"error": "invalid task ID"})
        return
    }
    
    ctx := c.Request.Context()
    
    // 软删除：设置 enabled = false + 添加 archived_at 字段
    // 或硬删除：直接从数据库删除
    if err := h.taskRepo.Delete(ctx, id); err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(200, gin.H{
        "success": true,
        "message": "Orphaned task deleted",
    })
}
```

### 3. 路由注册

```go
// internal/api/router.go
func SetupRoutes(r *gin.Engine, h *SchedulerHandler) {
    api := r.Group("/api")
    {
        scheduler := api.Group("/scheduler")
        {
            scheduler.GET("/orphaned-tasks", h.GetOrphanedTasks)
            scheduler.DELETE("/orphaned-tasks/:id", h.DeleteOrphanedTask)
        }
    }
}
```

## 四、前端集成（execution 看板）

### 1. 调用 API

```typescript
// packages/pages/execution/src/index.ts (host 半)
async function fetchBoardData(): Promise<BoardData> {
    // 现有数据获取逻辑...
    
    // 新增：获取僵尸任务
    let orphanedTasks: OrphanedTask[] = []
    try {
        const orphRes = await fetch('http://localhost:8080/api/scheduler/orphaned-tasks')
        const orphJson = await orphRes.json()
        if (orphJson.success) {
            orphanedTasks = orphJson.data.orphanedTasks || []
        }
    } catch (e) {
        console.warn('Failed to fetch orphaned tasks:', e)
    }
    
    return {
        // ... 现有字段
        orphanedTasks,
    }
}
```

### 2. UI 渲染

```typescript
// packages/pages/execution/src/client/view.ts
function renderOrphanedTasks(tasks: OrphanedTask[]): string {
    if (!tasks || tasks.length === 0) return ''
    
    const rows = tasks.map(t => `
        <tr class="orphaned-task" data-task-id="${t.id}">
            <td>⚠️ ${esc(t.name)}</td>
            <td>${t.lastRunAt ? fmtClock(t.lastRunAt) : '从未执行'}</td>
            <td>${t.daysSinceLastRun}天前</td>
            <td>${esc(t.reason)}</td>
            <td>
                <button class="cleanup-btn" data-task-id="${t.id}">清理</button>
            </td>
        </tr>
    `).join('')
    
    return `
        <div class="orphaned-section">
            <h3>僵尸任务 (${tasks.length})</h3>
            <table>
                <thead>
                    <tr>
                        <th>任务名称</th>
                        <th>最后执行</th>
                        <th>距今</th>
                        <th>原因</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `
}
```

## 五、实现清单

### Phase 1: 后端检测（2-3h）
- [ ] 创建 `orphaned_detector.go`
- [ ] 实现 `DetectOrphanedTasks()`
- [ ] 实现 `determineOrphanedReason()`
- [ ] 添加 `GetOrphanedTasks` API handler
- [ ] 注册路由
- [ ] 单元测试

### Phase 2: 后端清理（1h）
- [ ] 实现 `DeleteOrphanedTask` API handler
- [ ] 添加软删除支持（可选）
- [ ] 测试清理功能

### Phase 3: 前端展示（1-2h）
- [ ] 扩展 `BoardData` 类型
- [ ] host 半调用 orphaned-tasks API
- [ ] view 层渲染僵尸任务区块
- [ ] 添加清理按钮事件
- [ ] 测试 UI 交互

### Phase 4: 自动清理（可选，2h）
- [ ] 调度器启动时清理逻辑
- [ ] 或添加定时清理任务
- [ ] 配置清理阈值（默认 30 天）

---

**关键洞察**：僵尸任务检测的核心是**对比数据库全量 vs 调度器已加载集合**，而不是依赖任务执行记录。这样可以发现所有未被加载的任务，包括从未执行过的。
