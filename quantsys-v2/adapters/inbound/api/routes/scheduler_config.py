"""
调度器配置管理 API

提供RESTful API来动态管理定时任务配置
"""
from flask import Blueprint, request, jsonify
import logging

from application.services.scheduler_config_service import SchedulerConfigService
from application.services.unified_scheduler import get_unified_scheduler

logger = logging.getLogger(__name__)

scheduler_config_bp = Blueprint('scheduler_config', __name__, url_prefix='/api/scheduler/config')


@scheduler_config_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """列出所有任务配置

    Query Parameters:
        enabled_only: bool - 只返回启用的任务
        command: str - 按命令过滤

    Returns:
        {
            "success": true,
            "data": [
                {
                    "task_name": "daily_data_update",
                    "cron_expression": "30 16 * * 1-5",
                    "command": "data_update",
                    "is_enabled": true,
                    ...
                }
            ]
        }
    """
    try:
        service = SchedulerConfigService()

        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        command = request.args.get('command')

        configs = service.list_configs(enabled_only=enabled_only, command=command)

        return jsonify({
            "success": True,
            "data": configs,
            "total": len(configs)
        })

    except Exception as e:
        logger.error(f"List tasks failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/tasks/<task_name>', methods=['GET'])
def get_task(task_name):
    """获取单个任务配置

    Returns:
        {
            "success": true,
            "data": {...}
        }
    """
    try:
        service = SchedulerConfigService()
        config = service.get_config(task_name)

        if not config:
            return jsonify({
                "success": False,
                "error": f"Task not found: {task_name}"
            }), 404

        return jsonify({
            "success": True,
            "data": config
        })

    except Exception as e:
        logger.error(f"Get task failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建新任务配置

    Request Body:
        {
            "task_name": "my_task",
            "cron_expression": "0 9 * * *",
            "command": "data_update",
            "description": "任务描述",
            "params": {"key": "value"},
            "is_enabled": true,
            "executor": "default",
            "max_instances": 1
        }

    Returns:
        {
            "success": true,
            "data": {...},
            "message": "Task created and registered to scheduler"
        }
    """
    try:
        data = request.json

        # 验证必填字段
        required = ['task_name', 'cron_expression', 'command']
        for field in required:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400

        service = SchedulerConfigService()

        # 创建配置
        config = service.create_config(
            task_name=data['task_name'],
            cron_expression=data['cron_expression'],
            command=data['command'],
            description=data.get('description'),
            params=data.get('params', {}),
            is_enabled=data.get('is_enabled', True),
            executor=data.get('executor', 'default'),
            max_instances=data.get('max_instances', 1),
            created_by=request.headers.get('X-User', 'api')
        )

        # 如果启用，立即注册到调度器
        if config['is_enabled']:
            try:
                scheduler = get_unified_scheduler()
                scheduler._register_config(config)
                message = "Task created and registered to scheduler"
            except Exception as e:
                logger.warning(f"Failed to register task to scheduler: {e}")
                message = "Task created but failed to register to scheduler"
        else:
            message = "Task created (disabled)"

        return jsonify({
            "success": True,
            "data": config,
            "message": message
        }), 201

    except Exception as e:
        logger.error(f"Create task failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/tasks/<task_name>', methods=['PUT'])
def update_task(task_name):
    """更新任务配置

    Request Body:
        {
            "cron_expression": "0 10 * * *",
            "description": "新的描述",
            "params": {"new_key": "new_value"},
            ...
        }

    Returns:
        {
            "success": true,
            "data": {...},
            "message": "Task updated and scheduler reloaded"
        }
    """
    try:
        data = request.json
        data['updated_by'] = request.headers.get('X-User', 'api')

        service = SchedulerConfigService()
        config = service.update_config(task_name, **data)

        # 重新加载调度器
        try:
            scheduler = get_unified_scheduler()
            scheduler.reload_from_database()
            message = "Task updated and scheduler reloaded"
        except Exception as e:
            logger.warning(f"Failed to reload scheduler: {e}")
            message = "Task updated but failed to reload scheduler"

        return jsonify({
            "success": True,
            "data": config,
            "message": message
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
    except Exception as e:
        logger.error(f"Update task failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/tasks/<task_name>', methods=['DELETE'])
def delete_task(task_name):
    """删除任务配置

    Returns:
        {
            "success": true,
            "message": "Task deleted and removed from scheduler"
        }
    """
    try:
        service = SchedulerConfigService()
        deleted = service.delete_config(task_name)

        if not deleted:
            return jsonify({
                "success": False,
                "error": f"Task not found: {task_name}"
            }), 404

        # 从调度器移除
        try:
            scheduler = get_unified_scheduler()
            job_id = f"db_{task_name}"
            scheduler.remove_job(job_id)
            message = "Task deleted and removed from scheduler"
        except Exception as e:
            logger.warning(f"Failed to remove task from scheduler: {e}")
            message = "Task deleted but failed to remove from scheduler"

        return jsonify({
            "success": True,
            "message": message
        })

    except Exception as e:
        logger.error(f"Delete task failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/tasks/<task_name>/enable', methods=['POST'])
def enable_task(task_name):
    """启用任务

    Returns:
        {
            "success": true,
            "data": {...},
            "message": "Task enabled and registered to scheduler"
        }
    """
    try:
        service = SchedulerConfigService()
        config = service.enable_config(task_name)

        # 注册到调度器
        try:
            scheduler = get_unified_scheduler()
            scheduler._register_config(config)
            message = "Task enabled and registered to scheduler"
        except Exception as e:
            logger.warning(f"Failed to register task: {e}")
            message = "Task enabled but failed to register to scheduler"

        return jsonify({
            "success": True,
            "data": config,
            "message": message
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
    except Exception as e:
        logger.error(f"Enable task failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/tasks/<task_name>/disable', methods=['POST'])
def disable_task(task_name):
    """禁用任务

    Returns:
        {
            "success": true,
            "data": {...},
            "message": "Task disabled and removed from scheduler"
        }
    """
    try:
        service = SchedulerConfigService()
        config = service.disable_config(task_name)

        # 从调度器移除
        try:
            scheduler = get_unified_scheduler()
            job_id = f"db_{task_name}"
            scheduler.remove_job(job_id)
            message = "Task disabled and removed from scheduler"
        except Exception as e:
            logger.warning(f"Failed to remove task: {e}")
            message = "Task disabled but task not found in scheduler"

        return jsonify({
            "success": True,
            "data": config,
            "message": message
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
    except Exception as e:
        logger.error(f"Disable task failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/reload', methods=['POST'])
def reload_scheduler():
    """重新从数据库加载所有任务配置（热重载）

    Returns:
        {
            "success": true,
            "message": "Scheduler reloaded from database"
        }
    """
    try:
        scheduler = get_unified_scheduler()
        scheduler.reload_from_database()

        jobs = scheduler.get_all_jobs()
        db_jobs = [j for j in jobs if j.id.startswith('db_')]

        return jsonify({
            "success": True,
            "message": "Scheduler reloaded from database",
            "loaded_tasks": len(db_jobs)
        })

    except Exception as e:
        logger.error(f"Reload scheduler failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/import/legacy', methods=['POST'])
def import_from_legacy():
    """从旧的scheduler_tasks表批量导入

    Returns:
        {
            "success": true,
            "imported": 22,
            "message": "Imported 22 tasks from legacy table"
        }
    """
    try:
        service = SchedulerConfigService()
        imported_count = service.bulk_import_from_legacy()

        return jsonify({
            "success": True,
            "imported": imported_count,
            "message": f"Imported {imported_count} tasks from legacy table"
        })

    except Exception as e:
        logger.error(f"Import from legacy failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/export', methods=['GET'])
def export_config():
    """导出所有任务配置（备份）

    Returns:
        {
            "export_time": "2026-06-27T...",
            "total_tasks": 22,
            "tasks": [...]
        }
    """
    try:
        service = SchedulerConfigService()
        data = service.export_to_dict()

        return jsonify(data)

    except Exception as e:
        logger.error(f"Export config failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@scheduler_config_bp.route('/import', methods=['POST'])
def import_config():
    """导入任务配置（恢复）

    Request Body:
        {
            "tasks": [...],
            "overwrite": false
        }

    Returns:
        {
            "success": true,
            "imported": 22,
            "message": "Imported 22 tasks"
        }
    """
    try:
        data = request.json
        overwrite = data.get('overwrite', False)

        service = SchedulerConfigService()
        imported_count = service.import_from_dict(data, overwrite=overwrite)

        return jsonify({
            "success": True,
            "imported": imported_count,
            "message": f"Imported {imported_count} tasks"
        })

    except Exception as e:
        logger.error(f"Import config failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
