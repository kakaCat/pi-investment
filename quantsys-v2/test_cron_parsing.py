#!/usr/bin/env python3
"""
测试 APScheduler 能否解析数据库中的 cron 表达式
"""
from apscheduler.triggers.cron import CronTrigger
import subprocess
import json

print("=" * 70)
print("测试 APScheduler 解析核心调度任务")
print("=" * 70)

# 从数据库查询启用的任务
result = subprocess.run([
    'psql', '-d', 'quant_investment', '-t', '-A', '-F', '|', '-c',
    "SELECT id, name, cron_expression FROM quant.scheduler_tasks WHERE is_enabled = true AND cron_expression != 'managed_by_agent_os' ORDER BY id"
], capture_output=True, text=True)

if result.returncode != 0:
    print(f"❌ 查询数据库失败: {result.stderr}")
    exit(1)

tasks = []
for line in result.stdout.strip().split('\n'):
    if line:
        parts = line.split('|')
        if len(parts) == 3:
            tasks.append({
                'id': int(parts[0]),
                'name': parts[1],
                'cron_expression': parts[2]
            })

print(f"\n找到 {len(tasks)} 个启用的任务\n")

# 测试每个任务的 cron 表达式
success_count = 0
failed_tasks = []

for task in tasks:
    task_id = task['id']
    name = task['name']
    cron_expr = task['cron_expression']

    try:
        # 尝试解析 cron 表达式
        trigger = CronTrigger.from_crontab(cron_expr, timezone='Asia/Shanghai')

        # 计算下次运行时间（使用当前时间作为基准）
        from datetime import datetime
        import pytz
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        next_run = trigger.get_next_fire_time(None, now)

        success_count += 1
        print(f"✅ [{task_id:3d}] {name}")
        print(f"    Cron: {cron_expr}")
        print(f"    下次运行: {next_run}")
        print()

    except Exception as e:
        failed_tasks.append({
            'id': task_id,
            'name': name,
            'cron_expression': cron_expr,
            'error': str(e)
        })
        print(f"❌ [{task_id:3d}] {name}")
        print(f"    Cron: {cron_expr}")
        print(f"    错误: {e}")
        print()

print("=" * 70)
print(f"结果统计: {success_count}/{len(tasks)} 成功")
print("=" * 70)

if failed_tasks:
    print("\n失败的任务:")
    for task in failed_tasks:
        print(f"  - {task['name']} (ID: {task['id']})")
        print(f"    Cron: {task['cron_expression']}")
        print(f"    错误: {task['error']}")
    print("\n⚠️  有任务解析失败，核心调度功能可能有问题！")
    exit(1)
else:
    print("\n✅ 所有任务都能被 APScheduler 正确解析！")
    print("✅ 核心调度功能正常！")
    exit(0)
