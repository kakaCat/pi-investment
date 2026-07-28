"""
V14集成到quantsys-v2项目

执行步骤:
1. 将V14任务注册到scheduler_task_config表
2. 启动quantsys-v2统一服务
3. V14会自动加载并执行

注意: quantsys-v2使用数据库配置管理所有定时任务，不需要修改代码
"""
import os
os.environ['OMP_NUM_THREADS'] = '1'

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from infrastructure.persistence.database.engine import init_engine
from adapters.outbound.repositories.scheduler_repository import SchedulerRepository


def register_v14_task():
    """将V14任务注册到scheduler"""

    print("="*70)
    print(" V14任务注册到quantsys-v2 Scheduler ")
    print("="*70)
    print()

    # 初始化数据库
    init_engine()
    repo = SchedulerRepository()

    # V14任务配置
    v14_config = {
        'task_name': 'v14_daily_trading',
        'description': 'V14量化交易每日检查（P0优化版，7天周期，5只持仓）',
        'command': 'infrastructure.jobs.strategy_trading_job.v14_daily_check',
        'cron_expression': '30 15 * * 1-5',  # 交易日每天15:30
        'params': {
            'model_path': 'live_trading/models/v14_p0_model.json',
            'factors_path': 'live_trading/models/v14_p0_valid_factors.json',
            'enable_stop_loss': True,
            'enable_rebalance': True,
            'account_name': 'v14_simulation'
        },
        'enabled': True,
        'executor': 'default',
        'timeout': 600  # 10分钟超时
    }

    try:
        # 检查是否已存在
        existing = repo.get_task_config('v14_daily_trading')

        if existing:
            print("⚠️  V14任务已存在，更新配置...")
            # 根据实际API调整
            success = repo.update_task_config(
                task_name='v14_daily_trading',
                description=v14_config['description'],
                cron_expression=v14_config['cron_expression'],
                command=v14_config['command'],
                params=v14_config['params'],
                enabled=v14_config['enabled'],
                executor=v14_config.get('executor'),
                timeout=v14_config.get('timeout')
            )
            print("✅ V14任务配置已更新")
        else:
            print("创建V14任务配置...")
            # 根据实际API调整
            success = repo.create_task_config(
                task_name=v14_config['task_name'],
                description=v14_config['description'],
                cron_expression=v14_config['cron_expression'],
                command=v14_config['command'],
                params=v14_config['params'],
                is_enabled=v14_config['enabled'],  # 注意：参数名是is_enabled
                executor=v14_config.get('executor', 'default')
            )
            print("✅ V14任务已注册到scheduler")

        print()
        print("任务配置详情:")
        print(f"  任务名称: {v14_config['task_name']}")
        print(f"  描述: {v14_config['description']}")
        print(f"  执行时间: 交易日每天15:30")
        print(f"  调仓周期: 7天")
        print(f"  账户: v14_simulation")
        print(f"  状态: 已启用")

        print()
        print("="*70)
        print(" ✅ V14集成完成 ")
        print("="*70)
        print()
        print("下一步:")
        print("1. 启动quantsys-v2统一服务:")
        print("   python scheduler_daemon.py")
        print()
        print("2. V14任务将自动加载并在交易日15:30执行")
        print()
        print("3. 查看运行日志:")
        print("   tail -f logs/scheduler_daemon.log")

        return True

    except Exception as e:
        print(f"❌ 注册失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = register_v14_task()
    sys.exit(0 if success else 1)
