# Agent定时任务集成指南

**日期**: 2026-06-27  
**功能**: Agent可以操作quantsys-v2的定时任务系统

---

## 一、功能概述

Agent现在可以通过 `AgentSchedulerTool` 来：

✅ **创建提醒任务** - 在未来某个时间提醒自己  
✅ **创建周期任务** - 设置每日、每小时等周期性任务  
✅ **查询任务列表** - 查看自己创建的所有任务  
✅ **查询任务状态** - 检查任务是否正常运行  
✅ **取消任务** - 删除不需要的任务  
✅ **接收提醒** - 通过调度器在指定时间接收提醒

---

## 二、快速开始

### 2.1 Python API

```python
from application.services.agent_scheduler_tool import AgentSchedulerTool

# 初始化工具
tool = AgentSchedulerTool(api_base_url="http://localhost:5001")

# 1. 在10分钟后提醒自己
result = tool.create_self_reminder_in_minutes(
    minutes=10,
    message="检查数据处理结果"
)
print(result['message'])
# ✅ 已创建提醒任务，将在 2026-06-27 15:30 提醒你: 检查数据处理结果

# 2. 创建每日提醒
result = tool.create_daily_reminder(
    hour=9,
    minute=30,
    message="查看今日市场开盘情况",
    task_name="daily_market_check"
)
print(result['message'])
# ✅ 已创建周期任务: 每日09:30提醒

# 3. 查看所有任务
result = tool.list_agent_tasks()
print(f"共有 {result['total']} 个任务")
for task in result['tasks']:
    print(f"  - {task['task_name']}: {task['description']}")

# 4. 取消任务
result = tool.cancel_task("daily_market_check")
print(result['message'])
# ✅ 已取消任务: agent_recurring_default_agent_daily_market_check
```

---

## 三、API方法详解

### 3.1 create_self_reminder_in_minutes()

**用途**: 快速创建一个N分钟后的提醒

**参数**:
- `minutes` (int): 多少分钟后提醒
- `message` (str): 提醒消息
- `task_name` (str, 可选): 任务名称

**返回**:
```python
{
    "success": True,
    "task_name": "agent_reminder_default_agent_reminder_1703660000",
    "message": "✅ 已创建提醒任务...",
    "remind_at": "2026-06-27T15:30:00"
}
```

**使用场景**:
- Agent处理完数据后，10分钟后检查结果
- Agent启动耗时任务，30分钟后检查进度
- Agent需要短期延迟提醒

**示例**:
```python
# Agent刚完成数据处理
result = tool.create_self_reminder_in_minutes(
    minutes=10,
    message="检查数据处理结果是否正常"
)
```

### 3.2 create_daily_reminder()

**用途**: 创建每日固定时间的提醒

**参数**:
- `hour` (int): 小时 (0-23)
- `minute` (int): 分钟 (0-59)
- `message` (str): 提醒消息
- `task_name` (str): 任务名称

**返回**:
```python
{
    "success": True,
    "task_name": "agent_recurring_default_agent_daily_market_check",
    "message": "✅ 已创建周期任务...",
    "cron_expression": "30 9 * * *"
}
```

**使用场景**:
- 每天早上9:30检查市场开盘
- 每天下午4:30检查收盘数据
- 每天晚上9:00生成日报

**示例**:
```python
# 每天9:30提醒
tool.create_daily_reminder(
    hour=9,
    minute=30,
    message="检查市场开盘情况，关注异常波动",
    task_name="morning_market_check"
)
```

### 3.3 create_recurring_task()

**用途**: 创建自定义周期性任务

**参数**:
- `task_name` (str): 任务名称
- `cron_expression` (str): Cron表达式
- `command` (str): 命令（通常用 "agent_reminder"）
- `description` (str): 任务描述
- `params` (dict, 可选): 任务参数
- `agent_id` (str, 可选): Agent ID

**Cron表达式示例**:
```python
"0 9 * * *"           # 每天9:00
"30 16 * * 1-5"       # 工作日16:30
"*/15 9-14 * * 1-5"   # 工作日9:00-14:59每15分钟
"0 */2 * * *"         # 每2小时
"0 9 * * 1"           # 每周一9:00
```

**使用场景**:
- 交易时段每15分钟检查信号
- 每小时检查系统状态
- 每周一生成周报

**示例**:
```python
# 交易时段每15分钟提醒
tool.create_recurring_task(
    task_name="trading_monitor",
    cron_expression="*/15 9-14 * * 1-5",
    command="agent_reminder",
    description="交易时段信号监控",
    params={
        "message": "检查交易信号",
        "priority": "high"
    }
)
```

### 3.4 list_agent_tasks()

**用途**: 列出Agent创建的所有任务

**参数**:
- `agent_id` (str, 可选): Agent ID

**返回**:
```python
{
    "success": True,
    "total": 3,
    "tasks": [
        {
            "task_name": "agent_reminder_...",
            "description": "...",
            "cron_expression": "0 9 * * *",
            "is_enabled": True,
            ...
        }
    ]
}
```

**使用场景**:
- 查看自己创建了哪些任务
- 检查任务配置
- 管理任务

**示例**:
```python
result = tool.list_agent_tasks()
print(f"我有 {result['total']} 个任务:")
for task in result['tasks']:
    print(f"  - {task['task_name']}: {task['description']}")
```

### 3.5 cancel_task()

**用途**: 取消（删除）任务

**参数**:
- `task_name` (str): 任务名称（完整或部分）

**返回**:
```python
{
    "success": True,
    "message": "✅ 已取消任务: agent_recurring_default_agent_daily_market_check"
}
```

**使用场景**:
- 不再需要某个提醒
- 临时禁用某个监控
- 清理过期任务

**示例**:
```python
# 可以使用完整名称
tool.cancel_task("agent_recurring_default_agent_daily_market_check")

# 也可以使用部分名称（如果唯一）
tool.cancel_task("daily_market_check")
```

### 3.6 get_task_status()

**用途**: 查询任务状态

**参数**:
- `task_name` (str): 任务名称

**返回**:
```python
{
    "success": True,
    "task": {...},
    "message": "任务 'xxx' 状态: 启用"
}
```

---

## 四、使用场景

### 场景1: 数据处理后的延迟检查

```python
# Agent启动了一个耗时的数据处理任务
print("正在处理数据...")
# ... 处理逻辑 ...

# 10分钟后提醒自己检查结果
tool.create_self_reminder_in_minutes(
    minutes=10,
    message="检查数据处理结果是否正常"
)
print("已设置10分钟后的提醒")
```

### 场景2: 每日例行检查

```python
# Agent需要每天早上检查市场
tool.create_daily_reminder(
    hour=9,
    minute=30,
    message="查看市场开盘情况，关注异常波动",
    task_name="morning_market_check"
)
```

### 场景3: 交易时段实时监控

```python
# Agent需要在交易时段频繁检查
tool.create_recurring_task(
    task_name="trading_monitor",
    cron_expression="*/15 9-14 * * 1-5",  # 工作日9:00-14:59每15分钟
    command="agent_reminder",
    description="交易时段信号监控",
    params={"message": "检查交易信号，准备决策"}
)
```

### 场景4: 周期性报告生成

```python
# 每周一9:00生成周报
tool.create_recurring_task(
    task_name="weekly_report",
    cron_expression="0 9 * * 1",
    command="agent_reminder",
    description="每周报告生成",
    params={"message": "生成上周投资报告"}
)
```

### 场景5: 任务管理

```python
# 查看所有任务
result = tool.list_agent_tasks()
print(f"当前有 {result['total']} 个任务")

# 取消不需要的任务
for task in result['tasks']:
    if "old" in task['task_name']:
        tool.cancel_task(task['task_name'])
        print(f"已取消: {task['task_name']}")
```

---

## 五、提醒通知机制

### 5.1 提醒如何触发

当定时任务到达执行时间时：

1. ✅ APScheduler调度器触发任务
2. ✅ 调用 `handle_agent_reminder()` handler
3. ✅ Handler尝试通过 `AgentNotificationService` 发送通知
4. ✅ 同时记录到日志（作为备份）

### 5.2 接收提醒的方式

**方式1: 通过日志查看**
```bash
tail -f logs/scheduler.log | grep "Agent Reminder"
# 🔔 Agent Reminder for default_agent: 检查数据处理结果
```

**方式2: 通过通知服务**（如果已配置）
- WebSocket推送
- 邮件通知
- 飞书/钉钉通知

**方式3: 查询数据库**
```sql
SELECT * FROM quant.scheduler_runs
WHERE task_name LIKE 'agent_reminder_%'
ORDER BY started_at DESC;
```

---

## 六、测试

### 6.1 功能测试

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 运行功能测试
python scripts/test_agent_scheduler.py --test
```

### 6.2 场景演示

```bash
# 运行使用场景演示
python scripts/test_agent_scheduler.py --demo
```

### 6.3 手动测试

```python
from application.services.agent_scheduler_tool import AgentSchedulerTool

tool = AgentSchedulerTool()

# 创建一个1分钟后的提醒
result = tool.create_self_reminder_in_minutes(
    minutes=1,
    message="测试提醒"
)
print(result)

# 等待1分钟，查看日志
# tail -f logs/scheduler.log | grep "Agent Reminder"
```

---

## 七、最佳实践

### 7.1 任务命名

✅ **推荐**:
```python
task_name="daily_market_check"     # 清晰描述
task_name="trading_monitor"        # 有意义
task_name="weekly_report"          # 包含频率
```

❌ **不推荐**:
```python
task_name="task1"                  # 无意义
task_name="test"                   # 不专业
task_name="temp"                   # 临时性
```

### 7.2 提醒消息

✅ **推荐**:
```python
message="检查数据处理结果是否正常"           # 具体明确
message="查看市场开盘情况，关注异常波动"     # 包含行动指导
message="生成周报并发送给用户"               # 清晰的任务
```

❌ **不推荐**:
```python
message="检查"                              # 太简略
message="提醒"                              # 没有内容
```

### 7.3 定期清理

```python
# 定期清理过期的一次性任务
result = tool.list_agent_tasks()
for task in result['tasks']:
    # 如果是一次性提醒且已过期
    if "reminder_" in task['task_name']:
        # 检查是否已执行
        # 如果已执行，删除任务
        tool.cancel_task(task['task_name'])
```

### 7.4 错误处理

```python
try:
    result = tool.create_daily_reminder(
        hour=9,
        minute=30,
        message="每日检查",
        task_name="daily_check"
    )
    if result['success']:
        print(f"✅ {result['message']}")
    else:
        print(f"❌ {result.get('error', 'Unknown error')}")
except Exception as e:
    print(f"❌ 创建任务失败: {e}")
```

---

## 八、集成到Agent

### 8.1 在Agent代码中使用

```python
# 在Agent的初始化中
class MyAgent:
    def __init__(self):
        self.scheduler_tool = AgentSchedulerTool()
    
    def process_data(self):
        """处理数据"""
        print("开始处理数据...")
        # ... 数据处理逻辑 ...
        
        # 10分钟后提醒检查结果
        self.scheduler_tool.create_self_reminder_in_minutes(
            minutes=10,
            message="检查数据处理结果"
        )
    
    def setup_daily_routine(self):
        """设置每日例行任务"""
        self.scheduler_tool.create_daily_reminder(
            hour=9,
            minute=30,
            message="早间市场检查",
            task_name="morning_routine"
        )
```

### 8.2 在Agent决策流程中使用

```python
def make_decision(self):
    """Agent决策流程"""
    
    # 1. 分析数据
    analysis_result = self.analyze_market()
    
    # 2. 如果需要延迟决策
    if analysis_result['need_wait']:
        wait_minutes = analysis_result['wait_minutes']
        self.scheduler_tool.create_self_reminder_in_minutes(
            minutes=wait_minutes,
            message=f"重新评估{analysis_result['target']}的投资机会"
        )
        return "已设置延迟决策提醒"
    
    # 3. 立即决策
    return self.execute_decision()
```

---

## 九、故障排查

### Q1: 创建任务失败？

**检查清单**:
1. ✅ quantsys-v2是否已启动？`python start_all.py`
2. ✅ API是否可访问？`curl http://localhost:5001/health`
3. ✅ Cron表达式是否正确？
4. ✅ 查看错误信息：`result.get('error')`

### Q2: 提醒没有触发？

**检查清单**:
1. ✅ 任务是否已创建？`tool.list_agent_tasks()`
2. ✅ 任务是否启用？检查 `is_enabled`
3. ✅ 调度器是否运行？查看日志
4. ✅ 时间是否正确？检查cron表达式

### Q3: 如何查看提醒记录？

```bash
# 查看调度器日志
tail -f logs/scheduler.log | grep "Agent Reminder"

# 查看执行历史
psql -d quant_investment -c "
SELECT * FROM quant.scheduler_runs
WHERE task_name LIKE 'agent_reminder_%'
ORDER BY started_at DESC
LIMIT 10;
"
```

---

## 十、总结

### 核心功能

✅ Agent可以创建定时任务  
✅ Agent可以设置提醒  
✅ Agent可以管理自己的任务  
✅ 完全集成到quantsys-v2调度系统  

### 典型工作流

1. **Agent决策** → 需要延迟检查
2. **创建提醒** → `create_self_reminder_in_minutes()`
3. **时间到达** → 调度器触发提醒
4. **Agent收到** → 通过日志/通知查看
5. **继续工作** → Agent继续处理

### 下一步

- 测试各项功能
- 集成到Agent决策流程
- 配置通知服务（可选）
- 监控任务执行情况

---

**文档版本**: 1.0  
**最后更新**: 2026-06-27  
**状态**: ✅ **可用**
