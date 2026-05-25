#!/usr/bin/env python3
"""
测试定时任务调度器

快速验证调度器是否正常工作
"""

import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

def test_task():
    """测试任务 - 每10秒执行一次"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 测试任务执行成功")

def main():
    print("=" * 60)
    print("定时任务调度器测试")
    print("=" * 60)
    print()
    print("测试任务将每10秒执行一次")
    print("按 Ctrl+C 停止测试")
    print()

    scheduler = BlockingScheduler(timezone='Asia/Shanghai')

    # 添加测试任务 - 每10秒执行一次
    scheduler.add_job(
        test_task,
        IntervalTrigger(seconds=10),
        id='test_task',
        name='测试任务'
    )

    print(f"下次执行时间: {scheduler.get_jobs()[0].next_run_time}")
    print()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n测试结束")
        scheduler.shutdown()

if __name__ == '__main__':
    main()
