# Quantsys-v2 定时任务框架优化分析

**日期**: 2026-06-27  
**分析对象**: quantsys-v2 定时任务系统  
**结论**: **不建议引入新框架，建议统一到APScheduler**

---

## 一、现状分析

### 1.1 当前架构问题：**双轨制调度器**

系统中存在**两套独立的调度器实现**，造成架构混乱：

#### **轨道1：自研调度器** (`infrastructure/scheduler/scheduler.py`)
- **代码量**: 1463行
- **特点**:
  - 手写cron表达式解析器
  - 自建任务注册/执行循环
  - 阻塞式run_loop (30秒轮询)
  - PostgreSQL持久化 (`quant.scheduler_tasks`, `quant.scheduler_runs`)
  - 命令模式架构 (8个内置handler)
  
**优点**:
- 完全控制，无外部依赖
- 与数据库深度集成
- 已在 `start_all.py` 中启动运行

**缺点**:
- 重复造轮子（1400+行实现标准功能）
- 维护成本高（需要自己修bug）
- 功能受限（无分布式、无任务链、无高级trigger）
- 30秒轮询精度低，资源浪费

#### **轨道2：APScheduler调度器** (多个实现)
- **已安装**: APScheduler 3.11.2
- **使用场景**:
  - `application/services/smart_scheduler.py` - 智能调度服务
  - `application/services/market_monitor_scheduler.py` - 市场监控
  - `application/services/pool_scan_scheduler.py` - 股票池扫描
  - `application/services/signal_execution_scheduler.py` - 信号执行

**优点**:
- 成熟稳定（PyPI下载量>3000万/月）
- 功能丰富（Cron/Interval/Date多种trigger）
- 社区活跃，bug修复及时
- 更高精度（秒级调度）

**缺点**:
- 与自研调度器并存，造成混乱
- 缺乏统一的任务注册/监控入口

### 1.2 架构图

```
当前状态（双轨制）:
┌────────────────────────────────────────────────────┐
│  start_all.py 启动                                  │
│  ├── REST API (5001)                               │
│  ├── WebSocket (5003)                              │
│  └── Scheduler Process → infrastructure/scheduler  │
│      └── 自研调度器 (1463行，30秒轮询)             │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│  各Service内部独立启动                              │
│  ├── SmartSchedulerService → APScheduler           │
│  ├── MarketMonitorScheduler → APScheduler          │
│  ├── PoolScanScheduler → APScheduler               │
│  └── SignalExecutionScheduler → APScheduler        │
└────────────────────────────────────────────────────┘

问题：
✗ 两套调度系统，任务分散
✗ 无法统一监控和管理
✗ 重复实现相同功能
```

---

## 二、优化建议：**统一到APScheduler**

### 2.1 方案概述

**不引入新框架，而是废弃自研调度器，全面迁移到APScheduler**

**理由**:
1. APScheduler已安装并在多个服务中使用
2. 功能完全覆盖自研调度器
3. 减少1400+行维护代码
4. 统一架构，降低复杂度

### 2.2 迁移方案

#### **Phase 1: 创建统一调度器入口**

创建 `application/services/unified_scheduler.py`:

```python
"""统一调度器服务 - 基于APScheduler"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor

class UnifiedSchedulerService:
    """统一调度器 - 替代自研scheduler"""
    
    def __init__(self):
        jobstores = {
            'default': SQLAlchemyJobStore(url=get_db_url())
        }
        executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'
        )
        
        self._register_all_tasks()
    
    def _register_all_tasks(self):
        """注册所有系统任务"""
        # 迁移自 infrastructure/scheduler 的8个command handlers
        self.scheduler.add_job(
            func=daily_data_pipeline,
            trigger='cron',
            hour=16, minute=30, day_of_week='mon-fri',
            id='daily_data_pipeline',
            name='每日数据更新'
        )
        
        # 注册市场监控任务
        from .market_monitor_scheduler import MarketMonitorScheduler
        monitor = MarketMonitorScheduler()
        monitor.register_to(self.scheduler)
        
        # ... 其他任务
    
    def start(self):
        """启动调度器（非阻塞）"""
        self.scheduler.start()
    
    def shutdown(self):
        """优雅关闭"""
        self.scheduler.shutdown(wait=True)
```

#### **Phase 2: 修改 start_all.py**

```python
def run_scheduler():
    """启动统一调度器"""
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
    
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 旧版：from infrastructure.scheduler.scheduler import SchedulerService
    # 新版：使用APScheduler
    from application.services.unified_scheduler import UnifiedSchedulerService
    
    scheduler = UnifiedSchedulerService()
    scheduler.start()
    
    print("[Scheduler] APScheduler已启动 (非阻塞)")
    
    # 保持进程运行
    import signal, time
    stop_event = threading.Event()
    
    def shutdown_handler(sig, frame):
        print("[Scheduler] 收到停止信号")
        scheduler.shutdown()
        stop_event.set()
    
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    
    stop_event.wait()  # 阻塞等待停止信号
```

#### **Phase 3: 数据迁移**

将 `quant.scheduler_tasks` 中的任务定义迁移到APScheduler:

```python
# scripts/migrate_scheduler_to_apscheduler.py
"""迁移自研调度器任务到APScheduler"""

def migrate_tasks():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 读取旧任务
    cursor.execute("""
        SELECT task_id, name, schedule_expr, command, payload
        FROM quant.scheduler_tasks
        WHERE enabled = true
    """)
    
    tasks = cursor.fetchall()
    
    scheduler = UnifiedSchedulerService()
    
    for task in tasks:
        # 解析cron表达式
        cron_parts = task['schedule_expr'].split()
        
        # 注册到APScheduler
        scheduler.scheduler.add_job(
            func=get_command_handler(task['command']),
            trigger='cron',
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2],
            month=cron_parts[3],
            day_of_week=cron_parts[4],
            id=f"migrated_{task['task_id']}",
            name=task['name'],
            kwargs=task['payload']
        )
    
    print(f"✓ 已迁移 {len(tasks)} 个任务")
```

#### **Phase 4: 废弃旧代码**

```bash
# 归档自研调度器
mv infrastructure/scheduler/scheduler.py \
   infrastructure/scheduler/scheduler.py.deprecated

# 更新文档
echo "已废弃，请使用 application/services/unified_scheduler.py" \
   > infrastructure/scheduler/README.md
```

---

## 三、与主流框架对比

### 3.1 备选框架评估

| 框架 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **APScheduler** | ✓ 已安装<br>✓ 轻量级<br>✓ 易集成 | ✗ 单机（无分布式） | ✓ **本项目首选** |
| **Celery** | ✓ 分布式<br>✓ 任务队列<br>✓ 监控 | ✗ 重量级<br>✗ 需Redis/RabbitMQ<br>✗ 学习曲线陡 | 大规模异步任务 |
| **RQ** | ✓ 简单<br>✓ 基于Redis | ✗ 功能有限<br>✗ 需Redis | 简单队列任务 |
| **Dramatiq** | ✓ 高性能<br>✓ 可靠性 | ✗ 需消息队列<br>✗ 社区较小 | 高并发任务 |
| **自研调度器** | ✓ 完全控制 | ✗ 1463行维护成本<br>✗ 功能受限 | ✗ **建议废弃** |

### 3.2 为什么不推荐Celery？

虽然Celery是行业标准，但对本项目来说**过度设计**：

**Celery的复杂度**:
```
需要引入的组件:
1. Celery本身 (~50MB)
2. 消息队列 (Redis/RabbitMQ)
3. 结果后端 (Redis/数据库)
4. Celery Beat (定时任务)
5. Flower (监控UI)

配置复杂度:
- celeryconfig.py
- broker配置
- worker管理
- 序列化器选择
- 任务路由规则
```

**本项目特点**:
- **单机部署**（无分布式需求）
- **任务简单**（数据更新、信号扫描）
- **已有PostgreSQL**（无需额外消息队列）
- **团队规模小**（1-2人维护）

**结论**: APScheduler完全够用，Celery是杀鸡用牛刀。

---

## 四、实施计划

### 4.1 优先级

**P0 - 必须做（1-2天）**:
1. ✓ 创建 `UnifiedSchedulerService`
2. ✓ 迁移8个command handlers到新调度器
3. ✓ 修改 `start_all.py` 启动逻辑
4. ✓ 测试核心任务（daily_data_pipeline）

**P1 - 应该做（3-5天）**:
5. ✓ 统一各Service的调度器到UnifiedScheduler
6. ✓ 数据迁移脚本 (quant.scheduler_tasks → APScheduler)
7. ✓ 更新API路由 (`api/routes/scheduler.py`)
8. ✓ 监控面板（复用APScheduler的job查询API）

**P2 - 可以做（按需）**:
9. ○ 归档旧调度器代码
10. ○ 性能测试对比报告
11. ○ 编写迁移文档

### 4.2 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 任务丢失 | 高 | 迁移前备份数据库，保留旧代码7天 |
| 调度精度变化 | 中 | 逐个任务验证执行时间 |
| 依赖冲突 | 低 | APScheduler已安装且无冲突 |
| 团队学习成本 | 低 | APScheduler文档完善，API简单 |

### 4.3 回滚方案

```python
# 如果迁移失败，立即回滚
def rollback():
    # 1. 恢复 start_all.py 旧版本
    git checkout HEAD~1 start_all.py
    
    # 2. 重启服务
    pkill -f start_all.py
    python start_all.py
    
    # 3. 验证旧调度器运行
    ps aux | grep scheduler
```

---

## 五、技术细节

### 5.1 APScheduler高级特性

#### **持久化Job Store**
```python
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

jobstores = {
    'default': SQLAlchemyJobStore(
        url='postgresql://user:pass@localhost/quant_investment',
        tablename='apscheduler_jobs'  # 新表，不影响旧数据
    )
}
```

#### **任务执行器**
```python
executors = {
    'default': ThreadPoolExecutor(20),  # IO密集任务
    'processpool': ProcessPoolExecutor(5)  # CPU密集任务
}

# 使用示例
scheduler.add_job(
    heavy_computation,
    executor='processpool'  # 指定使用进程池
)
```

#### **失败重试**
```python
from apscheduler.triggers.cron import CronTrigger

scheduler.add_job(
    func=risky_task,
    trigger=CronTrigger(hour=9, minute=30),
    max_instances=1,
    misfire_grace_time=300,  # 5分钟内miss仍执行
    coalesce=True,  # 合并多次miss为一次执行
    replace_existing=True  # 覆盖同ID任务
)
```

### 5.2 监控和日志

#### **事件监听器**
```python
from apscheduler.events import (
    EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, 
    EVENT_JOB_MISSED, EVENT_JOB_ADDED
)

def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
        # 发送告警通知
        send_alert(event.job_id, event.exception)
    else:
        logger.info(f"Job {event.job_id} completed")

scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
```

#### **任务查询API**
```python
# 获取所有任务
jobs = scheduler.get_jobs()
for job in jobs:
    print(f"{job.id}: next_run={job.next_run_time}")

# 暂停/恢复
scheduler.pause_job('daily_data_pipeline')
scheduler.resume_job('daily_data_pipeline')

# 动态修改
scheduler.reschedule_job(
    'daily_data_pipeline',
    trigger='cron',
    hour=17, minute=0  # 改到17:00
)
```

---

## 六、总结

### 6.1 核心建议

**不要引入新框架，统一到APScheduler**

**原因**:
1. ✓ APScheduler已安装且在用，无需新依赖
2. ✓ 功能完全覆盖自研调度器（且更强大）
3. ✓ 减少1463行维护代码
4. ✓ 统一架构，降低团队认知负担
5. ✓ 社区成熟，长期维护有保障

### 6.2 不推荐的方案

| 方案 | 为什么不推荐 |
|------|--------------|
| 继续维护自研调度器 | 重复造轮子，维护成本高 |
| 引入Celery | 过度设计，增加系统复杂度 |
| 两套系统并存 | 架构混乱，监控困难 |

### 6.3 预期收益

**代码层面**:
- 删除1463行自研代码
- 统一4个独立调度器为1个
- API简化：`scheduler.add_job()` vs 自研的复杂command注册

**运维层面**:
- 监控统一（所有任务在一个调度器）
- 日志统一（APScheduler标准日志格式）
- 调试方便（可用APScheduler CLI工具）

**性能层面**:
- 从30秒轮询 → 秒级精确调度
- 支持线程池/进程池执行器
- 减少CPU空转（事件驱动 vs 轮询）

---

## 七、下一步行动

**立即执行**:
1. [ ] 创建 `application/services/unified_scheduler.py`
2. [ ] 编写迁移脚本 `scripts/migrate_to_apscheduler.py`
3. [ ] 在测试环境验证

**需要确认**:
- [ ] 是否保留 `quant.scheduler_tasks` 表？（建议：保留作为任务配置源）
- [ ] 旧任务执行历史如何处理？（建议：归档到 `quant.scheduler_runs_archive`）
- [ ] 是否需要Web UI？（建议：P2阶段考虑集成APScheduler Dashboard）

**文档更新**:
- [ ] 更新 `quantsys-v2/CLAUDE.md`
- [ ] 创建 `docs/scheduler-migration-guide.md`
- [ ] 更新 API文档
