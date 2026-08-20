#!/usr/bin/env python3
"""
注册模型训练自动化任务到Agent OS调度器

用法：
    python tools/register_model_train_task.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from application.services.agent_os_client import AgentOSClient
import structlog

logger = structlog.get_logger(__name__)


def register_weekly_train():
    """注册每周模型训练任务"""
    client = AgentOSClient()
    
    task = {
        "name": "model_train_auto_weekly",
        "description": "每周一凌晨3点自动模型训练（智能判断是否需要训练）",
        "cron": "0 3 * * 1",  # 周一凌晨3点（数据回填完成后）
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "webhook_body": {
            "job_type": "model_train_auto",
            "description": "每周自动模型训练",
            "params": {
                "model_type": "lightgbm",
                "symbols_limit": 500,
                "lookback_days": 350,
                "force_train": False,  # 智能判断（7天未训练 或 性能<0.55）
                "auto_switch": True,   # 性能提升>=1%时自动切换
                "test_size": 0.2,
            }
        },
        "enabled": True,
    }
    
    try:
        result = client.create_job(task)
        logger.info("✓ 每周训练任务已注册", result=result)
        print(f"✓ 每周训练任务已注册: {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"注册失败: {e}")
        print(f"✗ 注册失败: {e}")
        return None


def register_monthly_train():
    """注册每月模型训练任务（强制训练）"""
    client = AgentOSClient()
    
    task = {
        "name": "model_train_auto_monthly",
        "description": "每月1号凌晨3点强制模型训练（无论性能如何）",
        "cron": "0 3 1 * *",  # 每月1号凌晨3点
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "webhook_body": {
            "job_type": "model_train_auto",
            "description": "每月强制模型训练",
            "params": {
                "model_type": "lightgbm",
                "symbols_limit": 500,
                "lookback_days": 350,
                "force_train": True,   # 强制训练
                "auto_switch": False,  # 不自动切换，需人工审核
                "test_size": 0.2,
            }
        },
        "enabled": True,
    }
    
    try:
        result = client.create_job(task)
        logger.info("✓ 每月训练任务已注册", result=result)
        print(f"✓ 每月训练任务已注册: {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"注册失败: {e}")
        print(f"✗ 注册失败: {e}")
        return None


def list_registered_tasks():
    """列出已注册的训练任务"""
    client = AgentOSClient()
    
    try:
        tasks = client.list_jobs()
        train_tasks = [t for t in tasks if 'model_train' in t.get('name', '')]
        
        print(f"\n已注册的模型训练任务：{len(train_tasks)} 个")
        for task in train_tasks:
            status = "✓ 启用" if task.get('enabled') else "✗ 禁用"
            print(f"  [{status}] {task.get('name')}: {task.get('description')}")
            print(f"       cron: {task.get('cron')}, id: {task.get('id')}")
        
        return train_tasks
    except Exception as e:
        logger.error(f"列表失败: {e}")
        print(f"✗ 列表失败: {e}")
        return []


def main():
    print("=== 模型训练任务注册工具 ===\n")
    
    # 1. 列出现有任务
    print("1. 检查现有任务...")
    existing = list_registered_tasks()
    
    # 2. 注册每周任务
    if not any('weekly' in t.get('name', '') for t in existing):
        print("\n2. 注册每周训练任务...")
        register_weekly_train()
    else:
        print("\n2. 每周任务已存在，跳过")
    
    # 3. 注册每月任务
    if not any('monthly' in t.get('name', '') for t in existing):
        print("\n3. 注册每月训练任务...")
        register_monthly_train()
    else:
        print("\n3. 每月任务已存在，跳过")
    
    # 4. 最终列表
    print("\n4. 最终任务列表:")
    list_registered_tasks()
    
    print("\n✓ 注册完成")
    print("\n提示：")
    print("  - 每周任务：智能判断是否需要训练（7天未训练 或 性能低）")
    print("  - 每月任务：强制训练，用于定期更新模型")
    print("  - 手动触发：curl -X POST http://localhost:5001/internal/scheduler/webhook \\")
    print("              -d '{\"job_type\":\"model_train_auto\",\"params\":{\"force_train\":true}}'")


if __name__ == '__main__':
    main()
