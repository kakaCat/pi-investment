# 模型训练自动化 - 实施方案对比

## 现状分析

quantsys-v2 **已实现**的能力：
- ✅ 训练任务处理器（`handle_model_train_auto`）
- ✅ Webhook接收端点（`/internal/scheduler/webhook`）
- ✅ 任务注册表（`_TASK_HANDLERS`）

quantsys-v2 **缺少**的能力：
- ❌ 内置定时调度器（无APScheduler等）
- ❌ Agent OS未运行（设计中依赖外部Agent OS）

## 解决方案对比

### 方案1：系统Cron（推荐，最简单）✅

**原理**：使用操作系统的cron直接调用训练任务

**优点**：
- 零依赖，系统自带
- 稳定可靠
- 日志清晰

**缺点**：
- 需要手动配置cron

**实施**：

```bash
# 1. 创建调用脚本
cat > /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh << 'SCRIPT'
#!/bin/bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh

python3 << 'PYEOF'
from application.services.scheduler_tasks import handle_model_train_auto
import json

result = handle_model_train_auto({
    "model_type": "lightgbm",
    "symbols_limit": 500,
    "force_train": False,
    "auto_switch": True,
})

print(json.dumps(result, indent=2))
PYEOF
SCRIPT

chmod +x tools/cron_train_model.sh

# 2. 配置cron
crontab -e
# 添加：每周一凌晨3点执行
0 3 * * 1 /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh >> /tmp/model-train-cron.log 2>&1
```

---

### 方案2：添加内置APScheduler ⚙️

**原理**：在quantsys-v2内集成APScheduler

**优点**：
- 与FastAPI集成，启动即可用
- 动态管理（API增删改任务）
- 支持复杂调度逻辑

**缺点**：
- 需要修改代码
- 增加依赖

**实施**：

```python
# 1. 安装依赖
pip install apscheduler

# 2. 创建调度器模块
# infrastructure/scheduler/builtin_scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from application.services.scheduler_tasks import handle_model_train_auto

scheduler = BackgroundScheduler()

def register_tasks():
    # 每周一03:00
    scheduler.add_job(
        lambda: handle_model_train_auto({"force_train": False}),
        CronTrigger(day_of_week='mon', hour=3, minute=0),
        id='model_train_weekly'
    )

def start():
    register_tasks()
    scheduler.start()

# 3. 在FastAPI启动时启动调度器
# adapters/inbound/fastapi_app/main.py
@app.on_event("startup")
async def startup_scheduler():
    from infrastructure.scheduler.builtin_scheduler import start
    start()
```

---

### 方案3：使用Agent OS（原设计）🔧

**原理**：启动独立的Agent OS服务作为调度引擎

**优点**：
- 完整的任务管理Web UI
- 与原设计一致
- 支持复杂任务编排

**缺点**：
- 需要运行额外服务
- 依赖外部组件

**实施**：

```bash
# 1. 启动Agent OS（假设已安装）
agent-os start --port 8080

# 2. 注册任务
python tools/register_model_train_task.py

# 3. Agent OS定时调用 /internal/scheduler/webhook
```

---

### 方案4：Celery Beat（企业级）🏢

**原理**：使用Celery分布式任务队列

**优点**：
- 分布式执行
- 支持重试、监控
- 企业级方案

**缺点**：
- 需要Redis/RabbitMQ
- 架构复杂

**实施**：略（需要大量基础设施）

---

## 推荐方案：系统Cron + Wrapper脚本

**最适合当前场景**，原因：
1. ✅ 零依赖，立即可用
2. ✅ 不需要修改quantsys-v2代码
3. ✅ 稳定可靠
4. ✅ 日志清晰（重定向到文件）

### 完整实施步骤

```bash
# 1. 创建调用脚本
cd /Users/yunpeng/pi-investment/quantsys-v2
cat > tools/cron_train_model.sh << 'SCRIPT'
#!/bin/bash
# 模型训练定时任务（系统cron调用）

LOG_FILE="/tmp/model-train-$(date +%Y%m%d).log"
echo "=== 模型训练开始 $(date) ===" >> "$LOG_FILE"

cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh

python3 << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
from application.services.scheduler_tasks import handle_model_train_auto
import json
from datetime import datetime

print(f"\n[{datetime.now()}] 调用 handle_model_train_auto")

result = handle_model_train_auto({
    "model_type": "lightgbm",
    "symbols_limit": 500,
    "lookback_days": 350,
    "force_train": False,  # 智能判断
    "auto_switch": True,   # 性能提升时自动切换
    "test_size": 0.2,
})

print(f"\n[{datetime.now()}] 训练结果:")
print(json.dumps(result, indent=2, ensure_ascii=False))

if result.get("status") == "success":
    print(f"\n✓ 训练成功: {result.get('version')}")
    print(f"  训练准确率: {result.get('train_accuracy')}")
    print(f"  测试准确率: {result.get('test_accuracy')}")
elif result.get("status") == "skipped":
    print(f"\n⊙ 跳过训练: {result.get('reason')}")
else:
    print(f"\n✗ 训练失败: {result.get('error')}")
    exit(1)
PYEOF

echo "=== 模型训练结束 $(date) ===" >> "$LOG_FILE"
SCRIPT

chmod +x tools/cron_train_model.sh

# 2. 手动测试
./tools/cron_train_model.sh

# 3. 配置cron
crontab -e
# 添加以下行（每周一凌晨3点）：
# 0 3 * * 1 /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh

# 验证cron配置
crontab -l | grep model
```

### 监控与日志

```bash
# 查看最新日志
tail -100 /tmp/model-train-$(date +%Y%m%d).log

# 查看历史日志
ls -lh /tmp/model-train-*.log

# 实时监控
tail -f /tmp/model-train-$(date +%Y%m%d).log
```

### 额外功能

**每月强制训练**：
```bash
# 在crontab中再添加一行（每月1号凌晨3点）
0 3 1 * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model_force.sh
```

```bash
# tools/cron_train_model_force.sh
#!/bin/bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh
python3 -c "
from application.services.scheduler_tasks import handle_model_train_auto
handle_model_train_auto({'force_train': True, 'auto_switch': False})
" >> /tmp/model-train-force.log 2>&1
```

---

## 总结

| 方案 | 复杂度 | 依赖 | 推荐度 |
|------|--------|------|--------|
| **系统Cron** | ⭐ 简单 | 无 | ⭐⭐⭐⭐⭐ 强烈推荐 |
| APScheduler | ⭐⭐ 中等 | 需修改代码 | ⭐⭐⭐ 可选 |
| Agent OS | ⭐⭐⭐ 复杂 | 外部服务 | ⭐⭐ 备选 |
| Celery Beat | ⭐⭐⭐⭐ 很复杂 | Redis等 | ⭐ 过度设计 |

**当前最佳实践**：使用系统Cron + 上面的wrapper脚本，简单可靠。

---

**创建时间**：2026-08-20  
**更新时间**：2026-08-20
