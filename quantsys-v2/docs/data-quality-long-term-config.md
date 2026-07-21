# 数据质量管理系统 - 定时任务配置指南

## 📋 当前配置

### 默认定时任务配置

```python
{
    'name': 'daily-data-quality-check',
    'cron_expression': '0 0 * * *',  # 每天午夜 00:00
    'command': 'data_quality_check',
    'params': {
        'days': 30,              # ⚠️ 当前仅检查最近30天
        'auto_backfill': True,
        'max_workers': 8,
        'quality_threshold': 95.0
    }
}
```

**问题**: 默认只检查最近30天，无法检测2年前的历史数据缺失。

---

## ✅ 解决方案：调整检查范围

### 方案1: 修改定时任务参数（推荐）

编辑 `scripts/init_scheduler_tasks.py`，修改 `days` 参数：

```python
{
    'name': 'daily-data-quality-check',
    'cron_expression': '0 0 * * *',
    'command': 'data_quality_check',
    'params': {
        'days': 730,             # ✅ 改为730天（2年）
        'auto_backfill': True,
        'max_workers': 8,
        'quality_threshold': 95.0
    },
    'description': '每日数据质量检查和自动补充（检查2年数据）'
}
```

**重新注册任务**:
```bash
cd quantsys-v2
PYTHONPATH=. python scripts/init_scheduler_tasks.py --reset
```

### 方案2: 创建额外的周度任务

保留每日任务检查最近30天，增加周度任务检查2年数据：

```python
DEFAULT_TASKS = [
    # 每日任务：快速检查最近30天
    {
        'name': 'daily-data-quality-check',
        'cron_expression': '0 0 * * *',  # 每天 00:00
        'command': 'data_quality_check',
        'params': {
            'days': 30,
            'auto_backfill': True,
            'max_workers': 8,
            'quality_threshold': 95.0
        },
        'description': '每日数据质量检查（最近30天）'
    },
    
    # 周度任务：深度检查2年数据
    {
        'name': 'weekly-data-quality-deep-check',
        'cron_expression': '0 2 * * 0',  # 每周日凌晨 02:00
        'command': 'data_quality_check',
        'params': {
            'days': 730,          # 检查2年
            'auto_backfill': True,
            'max_workers': 10,
            'quality_threshold': 95.0
        },
        'description': '每周深度数据质量检查（2年数据）'
    }
]
```

**优点**:
- 每日任务快速（30天，几秒完成）
- 每周任务深度（2年数据，全面检查）
- 既保证日常维护，又能发现历史缺失

---

## 🎯 推荐配置

### 小规模（< 100只股票）

```python
{
    'days': 730,         # 2年数据
    'max_workers': 10    # 并行数
}
```

**性能**: 100股票 × 2年 ≈ 30-60秒

### 中规模（100-500只股票）

```python
# 每日任务
{
    'days': 90,          # 3个月
    'max_workers': 8
}

# 周度任务
{
    'days': 730,         # 2年
    'max_workers': 15
}
```

### 大规模（> 500只股票）

```python
# 每日任务
{
    'days': 30,          # 1个月
    'max_workers': 8
}

# 周度任务
{
    'days': 365,         # 1年（不是2年，避免超时）
    'max_workers': 20
}

# 月度任务
{
    'days': 730,         # 2年
    'max_workers': 30
}
```

---

## 📊 性能参考

| 检查范围 | 股票数 | 预计耗时 | 推荐频率 |
|---------|--------|---------|---------|
| 7天 | 100 | < 5秒 | 每天 |
| 30天 | 100 | < 10秒 | 每天 |
| 90天 | 100 | < 30秒 | 每天/每周 |
| 365天 | 100 | < 2分钟 | 每周 |
| 730天 | 100 | < 5分钟 | 每周/每月 |
| 730天 | 500 | < 20分钟 | 每周 |

---

## 🔧 手动执行2年数据检查

### 方式1: Python脚本

```bash
cd quantsys-v2
python -c "
from runtime.jobs.data_quality_check_job import DataQualityCheckJob

job = DataQualityCheckJob()
result = job.run({
    'days': 730,
    'auto_backfill': True,
    'max_workers': 10
})
print(result)
"
```

### 方式2: TypeScript Agent工具

```typescript
data_quality_manage({
  action: 'check',
  start_date: '2024-06-04',  // 2年前
  end_date: '2026-06-04',
  include_report: true
})
```

### 方式3: REST API

```bash
curl -X POST http://127.0.0.1:5001/api/data/check \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-06-04",
    "end_date": "2026-06-04",
    "include_report": true
  }'
```

---

## 💡 最佳实践建议

### 1. 分层检查策略（推荐）

```
每日任务（00:00）:
  └─ 检查最近30天 → 快速发现新问题

每周任务（周日 02:00）:
  └─ 检查最近2年 → 深度检查历史数据

首次部署:
  └─ 手动执行一次2年检查 → 补齐历史数据
```

### 2. 逐步扩大范围

```bash
# 第1周：检查并补充最近3个月
data_quality_manage({
  action: 'backfill',
  start_date: '2026-03-04',
  max_workers: 10
})

# 第2周：检查并补充最近6个月
data_quality_manage({
  action: 'backfill',
  start_date: '2025-12-04',
  max_workers: 10
})

# 第3周：检查并补充最近1年
data_quality_manage({
  action: 'backfill',
  start_date: '2025-06-04',
  max_workers: 10
})

# 第4周：检查并补充最近2年
data_quality_manage({
  action: 'backfill',
  start_date: '2024-06-04',
  max_workers: 10
})
```

### 3. 监控补充进度

```bash
# 查看最近的执行记录
curl http://127.0.0.1:5001/api/scheduler/runs?task_id=225&limit=10

# 查看质量评分趋势
curl http://127.0.0.1:5001/api/scheduler/runs?task_id=225 | \
  jq '.data[] | {date: .created_at, score: .result.data_quality_score}'
```

---

## 🚀 立即行动

### 步骤1: 修改配置

编辑 `quantsys-v2/scripts/init_scheduler_tasks.py`:

```python
# 找到这一行
'days': 30,

# 改为
'days': 730,  # 或选择其他天数
```

### 步骤2: 重新初始化任务

```bash
cd quantsys-v2
PYTHONPATH=. python scripts/init_scheduler_tasks.py --reset
```

### 步骤3: 手动执行一次（补充历史数据）

```bash
cd quantsys-v2
python -c "
from runtime.jobs.data_quality_check_job import DataQualityCheckJob
job = DataQualityCheckJob()
job.run({'days': 730, 'auto_backfill': True, 'max_workers': 10})
"
```

### 步骤4: 验证结果

```bash
# 查看执行结果
curl http://127.0.0.1:5001/api/scheduler/runs?task_id=225&limit=1

# 或手动检查
python -c "
from services.data_quality_service import DataQualityService
service = DataQualityService()
result = service.check_data_quality(start_date='2024-06-04')
print(f'质量评分: {result[\"summary\"][\"data_quality_score\"]}/100')
"
```

---

## ⚠️ 注意事项

### 1. 性能影响

- 检查730天数据比30天慢约10-20倍
- 建议在低峰时段（凌晨）执行
- 大规模股票池建议分批处理

### 2. 数据源限流

- 补充大量历史数据可能触发API限流
- 建议适当降低 `max_workers`（5-10）
- 分多次执行，避免一次性补充过多

### 3. 数据库压力

- 大量写入可能影响数据库性能
- 建议在系统空闲时执行
- 监控数据库连接数和负载

---

## 📚 总结

**当前状态**:
- ✅ 定时任务已部署（每天00:00）
- ⚠️ 默认仅检查30天
- ✅ 支持调整检查范围

**解决方案**:
- 修改 `days` 参数为 730（2年）
- 或创建周度任务深度检查
- 首次部署手动补充历史数据

**推荐配置**:
```python
# 每日任务：快速检查
'days': 30

# 每周任务：深度检查
'days': 730
```

**立即执行**:
```bash
cd quantsys-v2
PYTHONPATH=. python scripts/init_scheduler_tasks.py --reset
```

---

**配置完成后，系统将自动维护2年历史数据！** 🚀
