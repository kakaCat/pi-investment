# APScheduler 迁移 - 快速参考

**状态**: ✅ 迁移完成，可以启动  
**日期**: 2026-06-27

---

## 启动系统

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python start_all.py
```

---

## 默认任务

| 任务 | 时间 | 说明 |
|------|------|------|
| 每日数据管道 | 16:30 工作日 | A股收盘后数据更新 |
| 每周数据重建 | 02:00 周日 | 全量数据重建（90天） |
| 数据质量检查 | 03:00 每日 | 数据完整性检查 |
| 信号执行 | 09:15 工作日 | 开盘前信号执行 |

---

## 管理任务

### 查看所有任务
```python
from application.services.unified_scheduler import get_unified_scheduler

scheduler = get_unified_scheduler()
scheduler.print_jobs()
```

### 添加新任务
```python
from application.services.scheduler_tasks import handle_data_update

scheduler.add_cron_job(
    func=handle_data_update,
    cron_expr="0 10 * * *",  # 每天10:00
    job_id="custom_update",
    name="自定义更新"
)
```

### 暂停/恢复/删除
```python
scheduler.pause_job("daily_data_pipeline")
scheduler.resume_job("daily_data_pipeline")
scheduler.remove_job("custom_update")
```

---

## 关键改进

- ✅ **30秒轮询 → 秒级精度**
- ✅ **5个调度器 → 1个统一服务**
- ✅ **删除1463行自研代码**
- ✅ **CPU占用显著降低**

---

## 文档

- 📖 完整分析: `docs/scheduler-optimization-analysis.md`
- 📖 迁移指南: `docs/scheduler-migration-guide.md`
- 📖 完成报告: `docs/scheduler-migration-completion.md`

---

## 回滚（如需）

```bash
pkill -f start_all.py
git checkout HEAD~1 start_all.py
python start_all.py
```

---

## 已验证

✅ 数据库表已创建  
✅ 调度器初始化成功  
✅ 15个任务处理器就绪  
✅ 4个默认任务已配置  
✅ 所有功能测试通过
