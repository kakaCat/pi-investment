"""
配置管理API - 基于数据库实现
"""
from flask import Blueprint, request, jsonify
from adapters.outbound.repositories.automation_repository import (
    AutomationTaskRepository,
    AutomationTask
)
from infrastructure.persistence.orm import get_db_session
from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__, url_prefix='/api/config')


def _task_to_dict(task: AutomationTask) -> Dict[str, Any]:
    """将任务对象转换为字典"""
    return {
        'id': task.id,
        'task_name': task.task_name,
        'task_type': task.task_type,
        'enabled': task.is_enabled,
        'schedule': task.schedule_config.get('cron') if task.schedule_config else None,
        'description': task.description,
        'priority': task.priority,
        'agent_tool': task.agent_tool,
        'last_run_at': task.last_run_at.isoformat() if task.last_run_at else None,
        'next_run_at': task.next_run_at.isoformat() if task.next_run_at else None
    }


@config_bp.route('/automation', methods=['GET'])
def get_automation_config():
    """获取自动化配置 - 从数据库读取"""
    try:
        session = get_db_session()
        repo = AutomationTaskRepository(session)

        tasks = repo.list_all()

        # 转换为原有的 JSON 格式以保持兼容性
        config = {
            'tasks': {},
            'rules': {
                'auto_create_pool': False,
                'auto_create_pool_threshold': 85,
                'auto_risk_control': True,
                'auto_risk_control_threshold': 40,
                'risk_control_action': 'alert',
                'auto_learning': True,
                'learning_evaluation_days': 7,
                'knowledge_extraction': 'success_only'
            },
            'notification': {
                'feishu_enabled': False,
                'feishu_webhook': '',
                'feishu_content': ['critical_alerts', 'daily_report'],
                'email_enabled': False,
                'email_address': ''
            },
            'limits': {
                'max_pools': 10,
                'max_position_per_pool': 100000,
                'max_daily_trades': 20,
                'daily_loss_limit': 5000
            }
        }

        # 填充任务配置
        for task in tasks:
            config['tasks'][task.task_name] = {
                'enabled': task.is_enabled,
                'schedule': task.schedule_config.get('cron') if task.schedule_config else '',
                'description': task.description or ''
            }

        session.close()
        return jsonify({'success': True, 'data': config})

    except Exception as e:
        logger.error(f"Error getting automation config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/automation', methods=['POST'])
def save_automation_config():
    """保存自动化配置 - 写入数据库"""
    try:
        config = request.json
        session = get_db_session()
        repo = AutomationTaskRepository(session)

        # 更新任务配置
        if 'tasks' in config:
            for task_name, task_config in config['tasks'].items():
                existing_task = repo.get_by_name(task_name)

                if existing_task:
                    # 更新现有任务
                    updates = {
                        'is_enabled': task_config.get('enabled', True),
                        'schedule_config': {'cron': task_config.get('schedule', '')},
                        'description': task_config.get('description', '')
                    }
                    repo.update_task(task_name, updates)
                else:
                    # 创建新任务
                    task_data = {
                        'task_name': task_name,
                        'task_type': 'scheduled',
                        'schedule_config': {'cron': task_config.get('schedule', '')},
                        'is_enabled': task_config.get('enabled', True),
                        'description': task_config.get('description', ''),
                        'priority': 5
                    }
                    repo.create_task(task_data)

        session.close()
        return jsonify({'success': True, 'message': '配置保存成功'})

    except Exception as e:
        logger.error(f"Error saving automation config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/automation/tasks', methods=['GET'])
def list_automation_tasks():
    """获取所有自动化任务列表"""
    try:
        session = get_db_session()
        repo = AutomationTaskRepository(session)

        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        tasks = repo.list_all(enabled_only=enabled_only)

        result = [_task_to_dict(task) for task in tasks]

        session.close()
        return jsonify({'success': True, 'data': result})

    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/automation/tasks/<task_name>', methods=['GET'])
def get_automation_task(task_name: str):
    """获取单个任务详情"""
    try:
        session = get_db_session()
        repo = AutomationTaskRepository(session)

        task = repo.get_by_name(task_name)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404

        result = _task_to_dict(task)
        session.close()
        return jsonify({'success': True, 'data': result})

    except Exception as e:
        logger.error(f"Error getting task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/automation/tasks/<task_name>', methods=['PUT'])
def update_automation_task(task_name: str):
    """更新任务配置"""
    try:
        updates = request.json
        session = get_db_session()
        repo = AutomationTaskRepository(session)

        # 转换字段名
        if 'enabled' in updates:
            updates['is_enabled'] = updates.pop('enabled')

        if 'schedule' in updates:
            updates['schedule_config'] = {'cron': updates.pop('schedule')}

        success = repo.update_task(task_name, updates)
        session.close()

        if success:
            return jsonify({'success': True, 'message': '任务更新成功'})
        else:
            return jsonify({'success': False, 'error': 'Task not found'}), 404

    except Exception as e:
        logger.error(f"Error updating task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/automation/tasks/<task_name>/toggle', methods=['POST'])
def toggle_automation_task(task_name: str):
    """启用/禁用任务"""
    try:
        session = get_db_session()
        repo = AutomationTaskRepository(session)

        task = repo.get_by_name(task_name)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404

        # 切换状态
        new_status = not task.is_enabled
        repo.update_task(task_name, {'is_enabled': new_status})

        session.close()
        return jsonify({
            'success': True,
            'message': f'任务已{"启用" if new_status else "禁用"}',
            'enabled': new_status
        })

    except Exception as e:
        logger.error(f"Error toggling task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/notification', methods=['GET'])
def get_notification_config():
    """获取通知配置"""
    try:
        # 通知配置暂时返回默认值，后续可以单独建表存储
        default_notification = {
            'feishu_enabled': False,
            'feishu_webhook': '',
            'feishu_content': ['critical_alerts', 'daily_report'],
            'email_enabled': False,
            'email_address': ''
        }
        return jsonify({'success': True, 'data': default_notification})
    except Exception as e:
        logger.error(f"Error getting notification config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/notification', methods=['POST'])
def save_notification_config():
    """保存通知配置"""
    try:
        notification_config = request.json
        # TODO: 将通知配置保存到单独的表中
        # 目前仅返回成功，后续实现时补充
        return jsonify({'success': True, 'message': '通知配置保存成功'})
    except Exception as e:
        logger.error(f"Error saving notification config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/automation/tasks/<task_name>/execute', methods=['POST'])
def execute_automation_task(task_name: str):
    """手动执行自动化任务"""
    try:
        from datetime import datetime
        from adapters.outbound.repositories.automation_repository import AutomationRunRepository
        import uuid

        session = get_db_session()
        task_repo = AutomationTaskRepository(session)
        run_repo = AutomationRunRepository(session)

        # 获取任务
        task = task_repo.get_by_name(task_name)
        if not task:
            session.close()
            return jsonify({'success': False, 'error': 'Task not found'}), 404

        # 创建执行记录
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run_data = {
            'task_id': task.id,
            'run_id': run_id,
            'trigger_type': 'manual',
            'trigger_by': 'user',
            'started_at': datetime.now(),
            'status': 'running'
        }
        run = run_repo.create_run(run_data)

        # 根据任务类型执行对应的工具
        result = None
        error = None

        try:
            if task.agent_tool == 'market_monitor':
                result = _execute_market_monitor_task(task_name)
            elif task.agent_tool == 'learning_engine':
                result = _execute_learning_task(task_name)
            else:
                result = {'message': f'Task {task_name} executed', 'tool': task.agent_tool}

            # 更新执行记录为成功
            run_repo.update_run(run_id, {
                'status': 'success',
                'completed_at': datetime.now(),
                'result': result
            })

            # 更新任务的最后执行时间
            task_repo.update_task(task_name, {'last_run_at': datetime.now()})

        except Exception as e:
            error = str(e)
            logger.error(f"Task execution failed: {e}")
            # 更新执行记录为失败
            run_repo.update_run(run_id, {
                'status': 'failed',
                'completed_at': datetime.now(),
                'error_message': error
            })

        session.close()

        if error:
            return jsonify({
                'success': False,
                'error': error,
                'run_id': run_id
            }), 500
        else:
            return jsonify({
                'success': True,
                'message': f'任务 {task_name} 执行完成',
                'run_id': run_id,
                'result': result
            })

    except Exception as e:
        logger.error(f"Error executing task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _execute_market_monitor_task(task_name: str) -> Dict[str, Any]:
    """执行市场监控任务"""
    from adapters.outbound.data_sources.stock_data_source import StockDataSource

    try:
        ds = StockDataSource()

        # 获取市场概况
        market_summary = {
            'task': task_name,
            'executed_at': datetime.now().isoformat(),
            'market_status': 'analyzed'
        }

        # 这里可以调用更多的市场分析逻辑
        logger.info(f"Market monitor task {task_name} executed")

        return market_summary
    except Exception as e:
        logger.error(f"Market monitor task failed: {e}")
        raise


def _execute_learning_task(task_name: str) -> Dict[str, Any]:
    """执行学习任务"""
    try:
        learning_result = {
            'task': task_name,
            'executed_at': datetime.now().isoformat(),
            'learning_status': 'completed',
            'insights_generated': 0
        }

        logger.info(f"Learning task {task_name} executed")
        return learning_result
    except Exception as e:
        logger.error(f"Learning task failed: {e}")
        raise
