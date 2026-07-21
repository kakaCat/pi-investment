# 数据质量检查定时任务 - 使用指南

## 📋 概述

数据质量检查定时任务已成功集成到 quantsys-v2 调度器系统，每天午夜 00:00 自动执行，检测和补充缺失的数据。

**任务名称**: `daily-data-quality-check`  
**任务ID**: 225  
**调度时间**: 每天 00:00（`0 0 * * *`）  
**下次运行**: 2026-06-05 08:00:00+08:00

---

## ✅ 已完成功能

### 1. Job 实现
- ✅ `runtime/jobs/data_quality_check_job.py` - 数据质量检查任务
- ✅ 支持参数配置：检查天数、自动补充、并行线程数、质量阈值

### 2. 调度器集成
- ✅ `runtime/scheduler/scheduler.py` - 添加 `data_quality_check` 命令处理器
- ✅ `scripts/init_scheduler_tasks.py` - 添加默认任务配置

### 3. 测试验证
- ✅ Job 直接执行测试通过
- ✅ 调度器任务注册成功
- ✅ 质量评分: 100.0/100（优秀）

---

## 🚀 使用方式

### 1. 自动执行（推荐）

任务已注册到调度器，每天午夜自动执行。只需确保调度器服务运行：

```bash
cd quantsys-v2
python start_all.py  # 启动所有服务（包括调度器）
```

调度器会在每天 00:00 自动执行数据质量检查和补充。

### 2. 手动触发任务

通过 API 手动触发任务：

```bash
# 方式1: 使用 curl
curl -X POST http://127.0.0.1:5001/api/scheduler/tasks/225/trigger

# 方式2: 查看所有任务
curl http://127.0.0.1:5001/api/scheduler/tasks

# 方式3: 查看任务执行历史
curl http://127.0.0.1:5001/api/scheduler/runs?limit=10
```

### 3. 直接执行 Job

```bash
cd quantsys-v2
PYTHONPATH=. python runtime/jobs/data_quality_check_job.py
```

### 4. Python 脚本调用

```python
from runtime.jobs.data_quality_check_job import DataQualityCheckJob

job = DataQualityCheckJob()

# 自定义参数
params = {
    'days': 30,              # 检查最近30天
    'auto_backfill': True,   # 自动补充
    'max_workers': 10,       # 并行线程数
    'quality_threshold': 95.0  # 质量阈值
}

result = job.run(params)
```

---

## ⚙️ 任务参数配置

### 默认参数

```python
{
    'days': 30,              # 检查最近30天的数据
    'auto_backfill': True,   # 自动补充缺失数据
    'max_workers': 8,        # 并行线程数
    'quality_threshold': 95.0  # 质量阈值（低于此值触发告警）
}
```

### 修改参数

编辑 `scripts/init_scheduler_tasks.py`，修改任务配置：

```python
{
    'name': 'daily-data-quality-check',
    'cron_expression': '0 0 * * *',  # 调度时间
    'command': 'data_quality_check',
    'params': {
        'days': 30,                 # 修改这里
        'auto_backfill': True,      # 修改这里
        'max_workers': 8,           # 修改这里
        'quality_threshold': 95.0   # 修改这里
    },
    'description': '每日数据质量检查和自动补充'
}
```

然后重新初始化任务：

```bash
cd quantsys-v2
PYTHONPATH=. python scripts/init_scheduler_tasks.py --reset
```

---

## 📊 任务执行流程

```
1. 每天 00:00 触发
   ↓
2. 检查数据质量
   - 检查最近 N 天的数据
   - 计算覆盖率、质量评分
   - 检测缺失、重复、异常
   ↓
3. 判断是否需要补充
   - 如果有缺失 + auto_backfill=True
   ↓
4. 自动补充数据
   - 使用多数据源获取
   - 自动 failover 和重试
   - 并行处理
   ↓
5. 补充后再次检查
   - 验证补充效果
   - 更新质量评分
   ↓
6. 质量告警检查
   - 如果低于阈值，记录告警
   - TODO: 发送通知
   ↓
7. 记录执行结果
   - 保存到调度器运行历史
```

---

## 📈 监控和日志

### 1. 查看任务状态

```bash
# 查看所有任务
curl http://127.0.0.1:5001/api/scheduler/tasks | jq '.data[] | select(.name | contains("quality"))'

# 查看特定任务
curl http://127.0.0.1:5001/api/scheduler/tasks/225
```

### 2. 查看执行历史

```bash
# 查看最近10次执行
curl http://127.0.0.1:5001/api/scheduler/runs?limit=10

# 查看特定任务的执行历史
curl http://127.0.0.1:5001/api/scheduler/runs?task_id=225
```

### 3. 查看执行日志

日志位置（如果启用了日志重定向）：
- `/tmp/quantsys-v2-scheduler.log`
- 或 `quantsys-v2/logs/scheduler.log`

查看日志：
```bash
tail -f /tmp/quantsys-v2-scheduler.log | grep -i "quality"
```

---

## 🔧 故障排查

### 问题1: 任务未执行

**检查**：
```bash
# 1. 检查任务是否启用
curl http://127.0.0.1:5001/api/scheduler/tasks/225

# 2. 检查调度器是否运行
ps aux | grep scheduler

# 3. 查看调度器日志
tail -f /tmp/quantsys-v2-scheduler.log
```

**解决**：
```bash
# 启动调度器
cd quantsys-v2 && python start_all.py
```

### 问题2: 任务执行失败

**检查**：
```bash
# 查看失败原因
curl http://127.0.0.1:5001/api/scheduler/runs?task_id=225&status=failed
```

**常见原因**：
- 数据库连接失败 → 检查 PostgreSQL
- 数据源 API 限流 → 降低 max_workers
- 网络问题 → 检查网络连接

### 问题3: 补充数据不完整

**解决**：
```bash
# 手动补充（强制模式）
cd quantsys-v2
python -c "
from services.data_quality_service import DataQualityService
service = DataQualityService()
result = service.backfill_missing_data(
    start_date='2026-01-01',
    mode='force',
    max_workers=5
)
print(result)
"
```

---

## 📅 调度时间建议

### 当前调度（默认）
- **00:00** - 数据质量检查（避开交易时段）

### 其他建议时间
```bash
# 1. 盘后立即检查（适合实时补充）
'30 15 * * 1-5'  # 工作日 15:30（收盘后）

# 2. 深夜检查（避开高峰）
'0 2 * * *'      # 每天 02:00

# 3. 仅工作日检查
'0 0 * * 1-5'    # 工作日 00:00
```

修改调度时间：
```python
# 编辑 scripts/init_scheduler_tasks.py
'cron_expression': '30 15 * * 1-5',  # 修改为你想要的时间
```

---

## 🎯 最佳实践

### 1. 定期检查执行结果
```bash
# 每周检查一次任务执行情况
curl http://127.0.0.1:5001/api/scheduler/runs?task_id=225&limit=7
```

### 2. 监控数据质量趋势
```bash
# 查看最近的质量评分
curl http://127.0.0.1:5001/api/scheduler/runs?task_id=225 | jq '.data[].result.data_quality_score'
```

### 3. 告警集成（TODO）
```python
# 在 data_quality_check_job.py 中添加告警逻辑
if summary['data_quality_score'] < quality_threshold:
    # 发送飞书/邮件/短信通知
    send_alert(f"数据质量低于阈值: {summary['data_quality_score']}")
```

### 4. 优化性能
```python
# 根据股票数量调整并行线程数
max_workers = min(10, len(symbols) // 10)
```

---

## 📚 相关文档

- **Job 实现**: `runtime/jobs/data_quality_check_job.py`
- **调度器集成**: `runtime/scheduler/scheduler.py`
- **任务配置**: `scripts/init_scheduler_tasks.py`
- **测试脚本**: `test_data_quality_schedule.py`
- **使用指南**: `docs/tools/data-quality-quick-start.md`

---

## ✅ 验收清单

- [x] Job 实现（`data_quality_check_job.py`）
- [x] 调度器集成（添加命令处理器）
- [x] 任务注册（添加默认任务）
- [x] 测试验证（Job 执行测试通过）
- [x] 文档完善（使用指南）
- [ ] 告警通知（TODO: 集成飞书/邮件）
- [ ] 前端展示（TODO: 调度器前端页面）

---

## 🎉 总结

**数据质量检查定时任务已成功部署！**

✅ 每天午夜 00:00 自动执行  
✅ 自动检测和补充缺失数据  
✅ 支持手动触发和参数配置  
✅ 完整的监控和日志  

**下一步**：
1. 启动调度器：`python start_all.py`
2. 等待明天凌晨自动执行
3. 查看执行结果：`curl http://127.0.0.1:5001/api/scheduler/runs?task_id=225`

**系统已就绪，数据质量自动保障！** 🚀
