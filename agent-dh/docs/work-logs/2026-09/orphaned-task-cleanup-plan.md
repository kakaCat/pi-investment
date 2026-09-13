---
id: wl-2026-09-orphaned-task-cleanup-plan
title: 僵尸任务清理机制实现方案
type: worklog
status: archived
updated: 2026-09-09
owners: [agent-dh]
tags: [worklog, 2026-09]
---

# 僵尸任务清理机制实现方案

## 一、在智能执行看板展示（推荐）

### 1. 扩展数据结构

```typescript
// packages/pages/execution/src/client/types.ts 新增
export interface OrphanedTask {
  id?: string | number
  name?: string
  scheduleExpr?: string
  lastRunAt?: string | null    // 最后执行时间
  createdAt?: string           // 创建时间
  inScheduler?: boolean        // 是否在调度器中（应为 false）
  inDatabase?: boolean         // 是否在数据库中（应为 true）
  daysSinceLastRun?: number    // 距上次执行天数
}

export interface BoardData {
  // ... 现有字段
  orphanedTasks?: OrphanedTask[]  // 新增：僵尸任务列表
}
```

### 2. 后端 API（Agent OS）

需要在 Agent OS 添加以下接口：

```
GET /api/scheduler/orphaned-tasks
返回：{
  success: true,
  data: {
    orphanedTasks: [
      {
        id: "480ffd36-...",
        name: "daily_recall_audit",
        lastRunAt: "2026-09-09T19:00:00Z",
        daysSinceLastRun: 0,
        inScheduler: false,
        inDatabase: true
      }
    ]
  }
}

DELETE /api/scheduler/orphaned-tasks/:id
清理指定僵尸任务
```

### 3. 看板 UI 展示

在智能执行看板新增区域（建议放在「错误事件」下方）：

```
┌─────────────────────────────────────────┐
│ 僵尸任务 (Orphaned Tasks)  [清理全部]   │
├─────────────────────────────────────────┤
│ ⚠️ daily_recall_audit                   │
│   最后执行：9-09 19:00 (0天前)          │
│   状态：数据库存在，调度器未加载         │
│   [清理]                                 │
├─────────────────────────────────────────┤
│ ⚠️ old_task_name                        │
│   最后执行：8-10 10:00 (30天前)         │
│   状态：数据库存在，调度器未加载         │
│   [清理]                                 │
└─────────────────────────────────────────┘
```

### 4. 实现步骤

**Phase 1: Agent OS 后端（Go）**
1. 在 `internal/kernel/scheduler/` 添加 `orphaned_detector.go`
2. 实现 `DetectOrphanedTasks()` 方法：
   - 从数据库获取所有任务
   - 从调度器获取活跃任务
   - 对比差异，找出僵尸任务
3. 添加 HTTP handler：`/api/scheduler/orphaned-tasks`
4. 添加清理接口：`DELETE /api/scheduler/orphaned-tasks/:id`

**Phase 2: execution 看板前端**
1. 扩展 `BoardData` 类型（已说明）
2. 修改 `view.ts`，新增僵尸任务区块渲染
3. 修改 `board-mount.ts`，添加清理按钮事件
4. API 调用：`DELETE /dashboard/api/board/orphaned/:id`

**Phase 3: execution host 半**
1. 修改 `/dashboard/api/board` 路由
2. 调用 Agent OS 的 orphaned-tasks API
3. 转发清理请求

## 二、自动清理机制（长期）

### 方案 A：调度器启动时清理

```go
// internal/kernel/scheduler/scheduler.go
func (s *Scheduler) Start() error {
    // 启动时清理僵尸任务
    if err := s.CleanupOrphanedTasks(30); err != nil {
        logger.Warn("Failed to cleanup orphaned tasks", "error", err)
    }
    // ... 原有启动逻辑
}

func (s *Scheduler) CleanupOrphanedTasks(daysThreshold int) error {
    orphaned := s.DetectOrphanedTasks()
    for _, task := range orphaned {
        if task.DaysSinceLastRun > daysThreshold {
            logger.Info("Auto-archiving orphaned task", 
                "name", task.Name, 
                "lastRun", task.LastRunAt)
            s.db.ArchiveTask(task.ID)
        }
    }
}
```

### 方案 B：定时清理任务

添加一个系统任务 `orphaned-task-cleanup`：
- 每周日凌晨 2:00 执行
- 清理超过 30 天未执行的僵尸任务
- 记录清理日志

## 三、实现优先级

| 阶段 | 内容 | 工作量 | 价值 |
|------|------|--------|------|
| P0 | Agent OS 检测 API | 2-3h | 高 |
| P0 | execution 看板展示 | 1-2h | 高 |
| P1 | 手动清理功能 | 1h | 中 |
| P2 | 自动清理机制 | 2h | 中 |

**总工作量：6-8 小时**

## 四、立即可做

不等后端实现，先在 execution 看板做**模拟展示**：

1. 在 `BoardData` 添加 `orphanedTasks` 字段（可选）
2. host 半暂时返回空数组 `[]`
3. view 层实现 UI 渲染（数据为空时不显示）
4. 等 Agent OS API 就绪后，只需修改 host 半的数据获取逻辑

这样可以先把 UI 框架搭好，后端实现后无缝对接。

---

**推荐路径**：先做 P0（检测 + 展示），再做 P1（手动清理），最后做 P2（自动清理）。
