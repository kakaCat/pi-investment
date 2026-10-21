# APScheduler 可配置化功能使用指南

**日期**: 2026-06-27  
**功能**: 数据库驱动的动态任务配置管理

---

## 一、功能概述

APScheduler已完全支持数据库配置，支持：

✅ **数据库存储**: 所有任务配置存储在PostgreSQL  
✅ **动态管理**: 通过REST API增删改查任务  
✅ **热重载**: 修改配置后无需重启系统  
✅ **批量导入**: 从旧scheduler_tasks表导入  
✅ **备份恢复**: 导出/导入配置JSON  
✅ **完整审计**: 记录创建人、更新人、时间戳

---

## 二、数据库表结构

### 配置表：quant.scheduler_task_configs

```sql
CREATE TABLE quant.scheduler_task_configs (
    config_id SERIAL PRIMARY KEY,
    task_name VARCHAR(200) NOT NULL UNIQUE,        -- 任务名称
    description TEXT,                               -- 任务描述
    cron_expression VARCHAR(100) NOT NULL,          -- Cron表达式
    command VARCHAR(100) NOT NULL,                  -- 命令（如 data_update）
    params JSONB DEFAULT '{}',                      -- 任务参数（JSON）
    is_enabled BOOLEAN DEFAULT true,                -- 是否启用
    executor VARCHAR(50) DEFAULT 'default',         -- 执行器类型
    max_instances INTEGER DEFAULT 1,                -- 最大并发实例数
    misfire_grace_time INTEGER DEFAULT 300,         -- 错过执行宽限时间（秒）
    coalesce BOOLEAN DEFAULT true,                  -- 是否合并错过的执行
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);
```

### 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `task_name` | VARCHAR(200) | 任务唯一标识 | "daily_data_update" |
| `cron_expression` | VARCHAR(100) | Cron表达式 | "30 16 * * 1-5" |
| `command` | VARCHAR(100) | 任务命令 | "data_update" |
| `params` | JSONB | 任务参数 | `{"symbols": ["600000"]}` |
| `is_enabled` | BOOLEAN | 是否启用 | true |
| `executor` | VARCHAR(50) | 执行器 | "default" 或 "processpool" |
| `max_instances` | INTEGER | 最大并发数 | 1 |
| `misfire_grace_time` | INTEGER | 错过执行宽限时间 | 300秒 |
| `coalesce` | BOOLEAN | 合并错过执行 | true |

---

## 三、REST API 使用

### 基础URL

```
http://localhost:5001/api/scheduler/config
```

### 3.1 列出所有任务

**请求**:
```bash
GET /api/scheduler/config/tasks
GET /api/scheduler/config/tasks?enabled_only=true
GET /api/scheduler/config/tasks?command=data_update
```

**响应**:
```json
{
  "success": true,
  "total": 22,
  "data": [
    {
      "config_id": 1,
      "task_name": "daily_data_update",
      "cron_expression": "30 16 * * 1-5",
      "command": "data_update",
      "params": {},
      "is_enabled": true,
      "executor": "default",
      "created_at": "2026-06-27T10:00:00"
    }
  ]
}
```

### 3.2 获取单个任务

**请求**:
```bash
GET /api/scheduler/config/tasks/daily_data_update
```

**响应**:
```json
{
  "success": true,
  "data": {
    "task_name": "daily_data_update",
    "cron_expression": "30 16 * * 1-5",
    "command": "data_update",
    "description": "每日数据更新",
    "params": {"symbols": ["600000", "600519"]},
    "is_enabled": true
  }
}
```

### 3.3 创建新任务

**请求**:
```bash
POST /api/scheduler/config/tasks
Content-Type: application/json

{
  "task_name": "my_custom_task",
  "cron_expression": "0 10 * * *",
  "command": "data_update",
  "description": "我的自定义任务",
  "params": {
    "symbols": ["600000"],
    "custom_param": "value"
  },
  "is_enabled": true,
  "executor": "default",
  "max_instances": 1
}
```

**响应**:
```json
{
  "success": true,
  "message": "Task created and registered to scheduler",
  "data": {
    "config_id": 23,
    "task_name": "my_custom_task",
    ...
  }
}
```

### 3.4 更新任务

**请求**:
```bash
PUT /api/scheduler/config/tasks/my_custom_task
Content-Type: application/json

{
  "cron_expression": "0 11 * * *",
  "description": "更新后的描述",
  "params": {"new_key": "new_value"}
}
```

**响应**:
```json
{
  "success": true,
  "message": "Task updated and scheduler reloaded",
  "data": {...}
}
```

### 3.5 删除任务

**请求**:
```bash
DELETE /api/scheduler/config/tasks/my_custom_task
```

**响应**:
```json
{
  "success": true,
  "message": "Task deleted and removed from scheduler"
}
```

### 3.6 启用/禁用任务

**启用**:
```bash
POST /api/scheduler/config/tasks/my_custom_task/enable
```

**禁用**:
```bash
POST /api/scheduler/config/tasks/my_custom_task/disable
```

**响应**:
```json
{
  "success": true,
  "message": "Task enabled and registered to scheduler",
  "data": {...}
}
```

### 3.7 热重载调度器

**请求**:
```bash
POST /api/scheduler/config/reload
```

**响应**:
```json
{
  "success": true,
  "message": "Scheduler reloaded from database",
  "loaded_tasks": 22
}
```

### 3.8 从旧表导入

**请求**:
```bash
POST /api/scheduler/config/import/legacy
```

**响应**:
```json
{
  "success": true,
  "imported": 22,
  "message": "Imported 22 tasks from legacy table"
}
```

### 3.9 导出配置（备份）

**请求**:
```bash
GET /api/scheduler/config/export
```

**响应**:
```json
{
  "export_time": "2026-06-27T12:00:00",
  "total_tasks": 22,
  "tasks": [...]
}
```

### 3.10 导入配置（恢复）

**请求**:
```bash
POST /api/scheduler/config/import
Content-Type: application/json

{
  "tasks": [...],
  "overwrite": false
}
```

**响应**:
```json
{
  "success": true,
  "imported": 22,
  "message": "Imported 22 tasks"
}
```

---

## 四、Python API 使用

### 4.1 使用SchedulerConfigService

```python
from application.services.scheduler_config_service import SchedulerConfigService

service = SchedulerConfigService()

# 列出所有任务
configs = service.list_configs(enabled_only=True)

# 获取单个任务
config = service.get_config('daily_data_update')

# 创建新任务
new_task = service.create_config(
    task_name='my_task',
    cron_expression='0 9 * * *',
    command='data_update',
    description='我的任务',
    params={'key': 'value'},
    is_enabled=True
)

# 更新任务
updated = service.update_config(
    'my_task',
    cron_expression='0 10 * * *',
    description='新描述'
)

# 启用/禁用
service.enable_config('my_task')
service.disable_config('my_task')

# 删除任务
service.delete_config('my_task')

# 从旧表导入
imported_count = service.bulk_import_from_legacy()

# 导出/导入
backup = service.export_to_dict()
service.import_from_dict(backup, overwrite=False)
```

### 4.2 使用UnifiedScheduler

```python
from application.services.unified_scheduler import get_unified_scheduler

scheduler = get_unified_scheduler()

# 从数据库加载任务
scheduler.register_from_database()

# 热重载
scheduler.reload_from_database()

# 查看所有任务
jobs = scheduler.get_all_jobs()
for job in jobs:
    print(f"{job.id}: {job.next_run_time}")
```

---

## 五、使用场景

### 场景1：添加新的定时任务

```bash
# 1. 通过API创建
curl -X POST http://localhost:5001/api/scheduler/config/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "hourly_price_check",
    "cron_expression": "0 * 9-14 * * 1-5",
    "command": "data_update",
    "description": "每小时价格检查（交易时段）",
    "params": {"symbols": ["600000", "600519"]},
    "is_enabled": true
  }'

# 2. 任务自动注册到调度器，立即生效
# 无需重启系统！
```

### 场景2：修改任务执行时间

```bash
# 将任务从16:30改为17:00
curl -X PUT http://localhost:5001/api/scheduler/config/tasks/daily_data_update \
  -H "Content-Type: application/json" \
  -d '{
    "cron_expression": "0 17 * * 1-5"
  }'

# 调度器自动重载，新时间立即生效
```

### 场景3：临时禁用任务

```bash
# 禁用任务（不删除配置）
curl -X POST http://localhost:5001/api/scheduler/config/tasks/daily_data_update/disable

# 稍后重新启用
curl -X POST http://localhost:5001/api/scheduler/config/tasks/daily_data_update/enable
```

### 场景4：备份和恢复

```bash
# 导出配置到文件
curl http://localhost:5001/api/scheduler/config/export > scheduler_backup.json

# 恢复配置
curl -X POST http://localhost:5001/api/scheduler/config/import \
  -H "Content-Type: application/json" \
  -d @scheduler_backup.json
```

### 场景5：批量导入旧任务

```bash
# 从旧的scheduler_tasks表导入所有启用的任务
curl -X POST http://localhost:5001/api/scheduler/config/import/legacy
```

---

## 六、Cron表达式参考

### 格式

```
* * * * *
│ │ │ │ └─── 星期几 (0-6, 0=Sunday)
│ │ │ └───── 月份 (1-12)
│ │ └─────── 日期 (1-31)
│ └───────── 小时 (0-23)
└─────────── 分钟 (0-59)
```

### 常用示例

| Cron表达式 | 说明 |
|-----------|------|
| `0 9 * * *` | 每天9:00 |
| `30 16 * * 1-5` | 工作日16:30 |
| `0 2 * * 0` | 每周日02:00 |
| `*/5 * * * *` | 每5分钟 |
| `0 */2 * * *` | 每2小时 |
| `0 9 1 * *` | 每月1号09:00 |
| `0 9 * * 1` | 每周一09:00 |
| `*/5 9-14 * * 1-5` | 工作日09:00-14:59每5分钟 |

---

## 七、最佳实践

### 7.1 任务命名

✅ **推荐**:
- `daily_data_update` - 清晰描述频率和功能
- `weekly_report_generation` - 有意义的名称
- `hourly_price_check` - 包含时间信息

❌ **不推荐**:
- `task1`, `task2` - 无意义
- `test`, `temp` - 不专业

### 7.2 参数管理

```json
{
  "params": {
    "symbols": ["600000", "600519"],
    "lookback_days": 30,
    "threshold": 0.05,
    "notify_on_failure": true
  }
}
```

### 7.3 错误处理

- ✅ 设置合理的 `misfire_grace_time`（错过执行宽限时间）
- ✅ 使用 `coalesce: true` 合并错过的执行
- ✅ 设置 `max_instances: 1` 避免并发冲突

### 7.4 性能优化

- CPU密集任务使用 `executor: "processpool"`
- IO密集任务使用 `executor: "default"`（线程池）
- 避免同一时间大量任务执行（分散Cron时间）

---

## 八、监控和调试

### 8.1 查看运行中的任务

```python
from application.services.unified_scheduler import get_unified_scheduler

scheduler = get_unified_scheduler()
jobs = scheduler.get_all_jobs()

for job in jobs:
    print(f"ID: {job.id}")
    print(f"Name: {job.name}")
    print(f"Next run: {job.next_run_time}")
    print(f"Trigger: {job.trigger}")
    print()
```

### 8.2 查看执行历史

```sql
-- 查看最近的执行记录
SELECT * FROM quant.scheduler_runs
ORDER BY started_at DESC
LIMIT 20;

-- 查看失败的任务
SELECT * FROM quant.scheduler_runs
WHERE status = 'failed'
ORDER BY started_at DESC;
```

### 8.3 日志查看

```bash
# 查看调度器日志
tail -f logs/scheduler.log

# 过滤特定任务
tail -f logs/scheduler.log | grep "daily_data_update"
```

---

## 九、故障排查

### 问题1：任务没有执行

**检查清单**:
1. ✅ 任务是否启用？`is_enabled = true`
2. ✅ Cron表达式是否正确？
3. ✅ 调度器是否运行？
4. ✅ 任务是否注册到调度器？

**解决方法**:
```bash
# 重新加载调度器
curl -X POST http://localhost:5001/api/scheduler/config/reload

# 检查任务状态
curl http://localhost:5001/api/scheduler/config/tasks/task_name
```

### 问题2：任务执行失败

**检查清单**:
1. ✅ 查看日志中的错误信息
2. ✅ 检查command是否有对应的handler
3. ✅ 检查params参数是否正确

**解决方法**:
```sql
-- 查看失败详情
SELECT * FROM quant.scheduler_runs
WHERE task_id = (
    SELECT config_id FROM quant.scheduler_task_configs
    WHERE task_name = 'task_name'
)
AND status = 'failed'
ORDER BY started_at DESC
LIMIT 1;
```

### 问题3：配置修改不生效

**解决方法**:
```bash
# 手动触发热重载
curl -X POST http://localhost:5001/api/scheduler/config/reload
```

---

## 十、总结

### 核心优势

✅ **完全可配置**: 所有任务配置存储在数据库  
✅ **动态管理**: 通过API增删改查，无需修改代码  
✅ **热重载**: 配置变更立即生效，无需重启  
✅ **易于备份**: JSON导出/导入  
✅ **完整审计**: 记录所有变更历史  

### 下一步

```bash
# 1. 启动系统
python start_all.py

# 2. 导入旧任务（首次）
curl -X POST http://localhost:5001/api/scheduler/config/import/legacy

# 3. 热重载调度器
curl -X POST http://localhost:5001/api/scheduler/config/reload

# 4. 开始使用API管理任务！
```

---

**文档版本**: 1.0  
**最后更新**: 2026-06-27  
**维护者**: PI Investment System Team
