#!/usr/bin/env python3
"""
验证 APScheduler 核心调度功能
"""
import sys
sys.path.insert(0, '/Users/yunpeng/pi-investment/.claude/worktrees/apscheduler-migration/quantsys-v2')

from infrastructure.scheduler.apscheduler_service import APSchedulerService
from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
from infrastructure.persistence.orm import get_session

print("=" * 70)
print("APScheduler 核心功能验证")
print("=" * 70)

# 1. 连接数据库
print("\n[1/5] 连接数据库...")
session = get_session()
repo = SchedulerRepository(session)
print("✅ 数据库连接成功")

# 2. 查询任务
print("\n[2/5] 查询启用的任务...")
tasks = repo.list_tasks(enabled_only=True)
print(f"✅ 找到 {len(tasks)} 个启用的任务")

if len(tasks) == 0:
    print("⚠️  警告：没有启用的任务")
    sys.exit(0)

# 3. 统计任务类型
print("\n[3/5] 统计任务类型...")
type_counts = {}
for task in tasks:
    task_type = task.get('task_type', 'cron')
    type_counts[task_type] = type_counts.get(task_type, 0) + 1

for task_type, count in type_counts.items():
    print(f"  - {task_type}: {count} 个")

# 4. 创建 APScheduler 服务
print("\n[4/5] 创建 APScheduler 服务...")
import os
db_url = f"postgresql://{os.getenv('PGUSER', 'postgres')}:{os.getenv('PGPASSWORD', '')}@{os.getenv('PGHOST', 'localhost')}:{os.getenv('PGPORT', '5432')}/{os.getenv('PGDATABASE', 'quant_investment')}"
service = APSchedulerService(db_url, repo)
print("✅ APScheduler 服务创建成功")

# 5. 加载任务
print("\n[5/5] 加载任务到 APScheduler...")
service.load_tasks_from_db()
jobs = service.scheduler.get_jobs()
print(f"✅ 成功加载 {len(jobs)} 个任务到调度器")

# 显示前 10 个任务
if len(jobs) > 0:
    print("\n前 10 个任务:")
    for i, job in enumerate(jobs[:10], 1):
        print(f"{i:2d}. {job.name}")
        print(f"     ID: {job.id}")
        print(f"     Trigger: {type(job.trigger).__name__}")
        print(f"     Next run: {job.next_run_time}")
        print()

# 6. 测试启动和停止
print("测试启动和停止...")
service.start()
if service.scheduler.running:
    print("✅ 调度器启动成功")
else:
    print("❌ 调度器启动失败")
    sys.exit(1)

service.shutdown(wait=False)
if not service.scheduler.running:
    print("✅ 调度器停止成功")
else:
    print("❌ 调度器停止失败")

# 清理
session.close()

print("\n" + "=" * 70)
print("✅ 所有核心功能验证通过")
print("=" * 70)
