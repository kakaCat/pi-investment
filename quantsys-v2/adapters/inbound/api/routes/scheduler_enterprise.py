"""
企业级调度器管理API
提供任务的增删改查、启动停止、手动触发等功能
"""
from flask import Blueprint, request, jsonify
from application.services.enterprise_scheduler import get_scheduler
from adapters.outbound.repositories.scheduler_repository import SchedulerRepository

scheduler_enterprise_bp = Blueprint('scheduler_enterprise', __name__, url_prefix='/api/scheduler')


def _shared_jobstore_job_count() -> int:
    """共享 apscheduler_jobs 表中的任务数。

    scheduler_daemon 的 UnifiedSchedulerService 与本调度器共用该表
    （APScheduler 无跨进程锁）。非空说明 daemon 已持有任务——此时在
    web 进程启动第二个调度器会双重执行所有任务（2026-07-23 code review）。
    """
    from sqlalchemy import create_engine, text
    from infrastructure.persistence.database.base_repository import _resolve_db_dsn

    engine = create_engine(_resolve_db_dsn())
    try:
        with engine.connect() as conn:
            return conn.execute(text('SELECT COUNT(*) FROM apscheduler_jobs')).scalar()
    finally:
        engine.dispose()


@scheduler_enterprise_bp.route('/status', methods=['GET'])
def get_scheduler_status():
    """获取调度器状态"""
    try:
        scheduler = get_scheduler()
        status = scheduler.get_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/start', methods=['POST'])
def start_scheduler():
    """启动调度器

    防护：共享 jobstore 已有任务（daemon 在跑）时拒绝启动第二调度器，
    除非显式 ?force=true（此时调用方确认接受双重执行风险）。
    """
    try:
        force = request.args.get('force', '').lower() == 'true'
        if not force:
            job_count = _shared_jobstore_job_count()
            if job_count > 0:
                return jsonify({
                    'success': False,
                    'error': (
                        f'apscheduler_jobs 已有 {job_count} 个任务（scheduler_daemon 在运行），'
                        f'在本进程启动第二个调度器会双重执行所有任务。'
                        f'确认风险后可用 ?force=true 强制启动。'
                    )
                }), 409

        scheduler = get_scheduler()
        scheduler.start()
        
        return jsonify({
            'success': True,
            'message': 'Scheduler started'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/shutdown', methods=['POST'])
def shutdown_scheduler():
    """关闭调度器"""
    try:
        scheduler = get_scheduler()
        scheduler.shutdown()
        
        return jsonify({
            'success': True,
            'message': 'Scheduler shutdown'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """列出所有任务配置"""
    try:
        repo = SchedulerRepository()
        configs = repo.list_task_configs()
        
        return jsonify({
            'success': True,
            'data': [
                {
                    'task_name': c.task_name,
                    'description': c.description,
                    'cron_expression': c.cron_expression,
                    'command': c.command,
                    'is_enabled': c.is_enabled,
                    'executor': c.executor,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None
                }
                for c in configs
            ]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/tasks/<task_name>', methods=['GET'])
def get_task(task_name):
    """获取任务配置详情"""
    try:
        repo = SchedulerRepository()
        config = repo.get_task_config(task_name)
        
        if not config:
            return jsonify({
                'success': False,
                'error': f'Task {task_name} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'task_name': config.task_name,
                'description': config.description,
                'cron_expression': config.cron_expression,
                'command': config.command,
                'params': config.params,
                'is_enabled': config.is_enabled,
                'executor': config.executor,
                'max_instances': config.max_instances,
                'misfire_grace_time': config.misfire_grace_time,
                'created_at': config.created_at.isoformat() if config.created_at else None,
                'updated_at': config.updated_at.isoformat() if config.updated_at else None
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/tasks/<task_name>/enable', methods=['POST'])
def enable_task(task_name):
    """启用任务"""
    try:
        repo = SchedulerRepository()
        config = repo.update_task_config(task_name, is_enabled=True)
        
        if not config:
            return jsonify({
                'success': False,
                'error': f'Task {task_name} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': f'Task {task_name} enabled'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/tasks/<task_name>/disable', methods=['POST'])
def disable_task(task_name):
    """禁用任务"""
    try:
        repo = SchedulerRepository()
        config = repo.update_task_config(task_name, is_enabled=False)
        
        if not config:
            return jsonify({
                'success': False,
                'error': f'Task {task_name} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': f'Task {task_name} disabled'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/tasks/<task_name>/trigger', methods=['POST'])
def trigger_task(task_name):
    """手动触发任务执行"""
    try:
        scheduler = get_scheduler()
        success = scheduler.trigger_job(task_name)
        
        if not success:
            return jsonify({
                'success': False,
                'error': f'Task {task_name} not found or not running'
            }), 404
        
        return jsonify({
            'success': True,
            'message': f'Task {task_name} triggered'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/jobs', methods=['GET'])
def list_jobs():
    """列出当前运行中的任务"""
    try:
        scheduler = get_scheduler()
        jobs = scheduler.list_jobs()
        
        return jsonify({
            'success': True,
            'data': jobs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_enterprise_bp.route('/history', methods=['GET'])
def get_execution_history():
    """获取任务执行历史"""
    try:
        task_id = request.args.get('task_id')
        limit = int(request.args.get('limit', 100))
        
        repo = SchedulerRepository()
        runs = repo.get_execution_history(job_id=task_id, limit=limit)
        
        return jsonify({
            'success': True,
            'data': [
                {
                    'id': run.id,
                    'task_id': run.task_id,
                    'status': run.status,
                    'started_at': run.started_at.isoformat() if run.started_at else None,
                    'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                    'duration_ms': run.duration_ms,
                    'error': run.error
                }
                for run in runs
            ]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def register_scheduler_enterprise_routes(app):
    """注册调度器管理路由"""
    app.register_blueprint(scheduler_enterprise_bp)
