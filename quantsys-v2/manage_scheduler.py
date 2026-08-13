#!/usr/bin/env python3
"""
Scheduler 任务管理工具
用于管理和测试 scheduler_task_configs 表
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ 已加载环境变量: {env_path}")

from adapters.outbound.repositories.scheduler_config_repository import SchedulerConfigORMRepository

def list_tasks():
    """列出所有任务"""
    repo = SchedulerConfigORMRepository()
    query = repo.session.query(repo.model)
    all_tasks = query.order_by(repo.model.created_at.desc()).all()

    print(f"\n数据库中的任务数: {len(all_tasks)}")

    if all_tasks:
        print("\n任务列表:")
        for i, task in enumerate(all_tasks, 1):
            status = "✅" if task.is_enabled else "❌"
            print(f"{i}. {status} {task.task_name}")
            print(f"   描述: {task.description}")
            print(f"   Cron: {task.cron_expression}")
            print(f"   命令: {task.command}")
            print(f"   创建: {task.created_at}")
            print()
    else:
        print("\n❌ 没有任务数据")

    return len(all_tasks)

def create_test_task():
    """创建测试任务"""
    repo = SchedulerConfigORMRepository()

    test_data = {
        'task_name': 'test_daily_sync',
        'description': '每日数据同步测试任务',
        'cron_expression': '0 9 * * *',
        'command': 'sync_data',
        'params': {'source': 'test'},
        'is_enabled': True,
        'created_by': 'admin'
    }

    try:
        task = repo.create_task_config(test_data)
        print(f"\n✅ 创建测试任务成功:")
        print(f"   ID: {task.id}")
        print(f"   名称: {task.task_name}")
        print(f"   描述: {task.description}")
        return task
    except Exception as e:
        print(f"\n❌ 创建失败: {e}")
        return None

def test_api():
    """测试 API 端点"""
    import requests

    print("\n测试 API 端点...")
    try:
        response = requests.get("http://127.0.0.1:5001/api/scheduler/tasks?page=1&pageSize=12")
        if response.status_code == 200:
            data = response.json()
            total = data.get('data', {}).get('total', 0)
            print(f"✅ API 调用成功，返回 {total} 个任务")
            return True
        else:
            print(f"❌ API 返回错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return False

def main():
    print("=" * 60)
    print("Scheduler 任务管理工具")
    print("=" * 60)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'list':
            list_tasks()
        elif command == 'create':
            create_test_task()
            list_tasks()
        elif command == 'test':
            test_api()
        elif command == 'all':
            print("\n1. 列出现有任务")
            count = list_tasks()

            if count == 0:
                print("\n2. 创建测试任务")
                create_test_task()
                list_tasks()

            print("\n3. 测试 API")
            test_api()
        else:
            print(f"未知命令: {command}")
            print_usage()
    else:
        print_usage()

def print_usage():
    print("\n使用方法:")
    print("  python manage_scheduler.py list      # 列出所有任务")
    print("  python manage_scheduler.py create    # 创建测试任务")
    print("  python manage_scheduler.py test      # 测试 API")
    print("  python manage_scheduler.py all       # 执行所有操作")

if __name__ == "__main__":
    main()
