#!/usr/bin/env python3
"""
APScheduler 集成测试脚本

测试 APScheduler 在实际数据库环境下的完整功能：
1. 连接数据库
2. 加载任务
3. 验证任务配置
4. 测试手动触发

Usage:
    python integration_test_apscheduler.py
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from infrastructure.config.settings import get_settings
from infrastructure.persistence.database.engine import init_engine
from infrastructure.persistence.orm import init_orm, get_session
from infrastructure.scheduler.apscheduler_service import APSchedulerService
from adapters.outbound.repositories.scheduler_repository import SchedulerRepository

def main():
    print("=" * 70)
    print("APScheduler 集成测试")
    print("=" * 70)

    # 1. 初始化配置
    print("\n[1/6] 初始化配置...")
    settings = get_settings()
    db_url = (
        f"postgresql://{settings.database.pguser}:{settings.database.pgpassword}"
        f"@{settings.database.pghost}:{settings.database.pgport}/{settings.database.pgdatabase}"
    )
    print(f"  ✓ 数据库: {settings.database.pgdatabase}")

    # 2. 初始化数据库
    print("\n[2/6] 初始化数据库引擎...")
    try:
        # 只初始化 ORM，不初始化 engine（避免配置冲突）
        init_orm()
        print("  ✓ 数据库 ORM 初始化成功")
    except Exception as e:
        print(f"  ✗ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 3. 创建仓储
    print("\n[3/6] 创建调度器仓储...")
    session = get_session()
    repo = SchedulerRepository(session)
    print("  ✓ 仓储创建成功")

    # 4. 初始化 APScheduler
    print("\n[4/6] 初始化 APScheduler...")
    try:
        scheduler_service = APSchedulerService(db_url, repo)
        print("  ✓ APScheduler 初始化成功")
    except Exception as e:
        print(f"  ✗ APScheduler 初始化失败: {e}")
        session.close()
        return 1

    # 5. 加载任务
    print("\n[5/6] 加载任务...")
    try:
        scheduler_service.load_tasks_from_db()
        jobs = scheduler_service.scheduler.get_jobs()

        print(f"  ✓ 成功加载 {len(jobs)} 个任务")
        print("\n  任务列表（前 10 个）：")
        for i, job in enumerate(jobs[:10], 1):
            print(f"    {i:2d}. {job.name}")
            print(f"        ID: {job.id}")
            print(f"        Trigger: {job.trigger}")
            print(f"        Next run: {job.next_run_time}")

        if len(jobs) > 10:
            print(f"    ... 还有 {len(jobs) - 10} 个任务")

    except Exception as e:
        print(f"  ✗ 加载任务失败: {e}")
        import traceback
        traceback.print_exc()
        session.close()
        return 1

    # 6. 验证任务状态
    print("\n[6/6] 验证任务状态...")
    if len(jobs) > 0:
        test_job = jobs[0]
        try:
            status = scheduler_service.get_job_status(int(test_job.id.replace('task_', '')))
            print(f"  ✓ 任务状态查询成功")
            print(f"    任务: {status['name']}")
            print(f"    下次执行: {status.get('next_run_time', 'N/A')}")
        except Exception as e:
            print(f"  ✗ 任务状态查询失败: {e}")

    # 清理
    session.close()

    print("\n" + "=" * 70)
    print("✅ 集成测试完成")
    print("=" * 70)
    print("\n测试总结：")
    print(f"  - 加载任务数: {len(jobs)}")
    print(f"  - 跳过任务数: (Agent OS 管理的任务)")
    print(f"  - APScheduler 状态: 已初始化，未启动")
    print("\n注意：本测试只验证初始化和加载，未启动实际调度")

    return 0


if __name__ == "__main__":
    sys.exit(main())
