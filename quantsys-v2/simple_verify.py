#!/usr/bin/env python3
"""
简单验证脚本：测试 APScheduler 能否加载和解析任务
"""
import psycopg2
from datetime import datetime

print("=" * 70)
print("APScheduler 任务加载验证")
print("=" * 70)

# 连接数据库
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='quant_investment',
    user='postgres'
)
cursor = conn.cursor()

# 1. 查询启用的任务
print("\n[1/4] 查询启用的任务...")
cursor.execute("""
    SELECT id, name, task_type, cron_expression, is_enabled, last_run_at, last_status
    FROM quant.scheduler_tasks
    WHERE is_enabled = true
    ORDER BY id
""")
tasks = cursor.fetchall()
print(f"✅ 找到 {len(tasks)} 个启用的任务")

if len(tasks) == 0:
    print("⚠️  没有启用的任务")
    conn.close()
    exit(0)

# 2. 统计任务类型
print("\n[2/4] 统计任务类型...")
type_counts = {}
for task in tasks:
    task_type = task[2]  # task_type 字段
    type_counts[task_type] = type_counts.get(task_type, 0) + 1

for task_type, count in type_counts.items():
    print(f"  - {task_type}: {count} 个")

# 3. 显示前 10 个任务
print("\n[3/4] 前 10 个任务详情:")
for i, task in enumerate(tasks[:10], 1):
    task_id, name, task_type, cron_expr, is_enabled, last_run, last_status = task
    print(f"{i:2d}. [{task_id:3d}] {name}")
    print(f"     类型: {task_type}, Cron: {cron_expr}")
    print(f"     上次运行: {last_run}, 状态: {last_status}")
    print()

# 4. 测试 APScheduler Trigger 创建
print("[4/4] 测试 APScheduler Trigger 创建...")
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

success_count = 0
failed_count = 0
skipped_count = 0

for task in tasks[:20]:  # 测试前 20 个任务
    task_id, name, task_type, cron_expr, *_ = task

    # 跳过 Agent OS 管理的任务
    if cron_expr == "managed_by_agent_os":
        skipped_count += 1
        continue

    try:
        if task_type == 'cron':
            trigger = CronTrigger.from_crontab(cron_expr, timezone='Asia/Shanghai')
        elif task_type == 'delay':
            if cron_expr.startswith('DELAY:'):
                delay_seconds = int(cron_expr.split(':')[1])
                run_at = datetime.now() + timedelta(seconds=delay_seconds)
                trigger = DateTrigger(run_date=run_at, timezone='Asia/Shanghai')
            else:
                raise ValueError(f"Invalid delay format: {cron_expr}")
        elif task_type == 'interval':
            if cron_expr.startswith('INTERVAL:'):
                interval_seconds = int(cron_expr.split(':')[1])
                trigger = IntervalTrigger(seconds=interval_seconds, timezone='Asia/Shanghai')
            else:
                raise ValueError(f"Invalid interval format: {cron_expr}")
        elif task_type == 'once':
            run_at = datetime.fromisoformat(cron_expr)
            trigger = DateTrigger(run_date=run_at, timezone='Asia/Shanghai')
        else:
            raise ValueError(f"Unknown task_type: {task_type}")

        success_count += 1

    except Exception as e:
        failed_count += 1
        print(f"  ❌ 任务 {task_id} ({name}) 解析失败: {e}")

print(f"\n结果: {success_count} 成功, {failed_count} 失败, {skipped_count} 跳过")

if failed_count > 0:
    print("⚠️  有任务解析失败，请检查 cron 表达式")
else:
    print("✅ 所有任务都能正确解析")

conn.close()

print("\n" + "=" * 70)
print("✅ 验证完成")
print("=" * 70)
