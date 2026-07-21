"""
自动化任务管理 API 路由 - ORM版本
提供任务创建、管理、触发等接口

完全使用ORM，不再直接执行SQL
"""
from flask import Blueprint, request, jsonify
from typing import Dict, Any
import logging

from application.services.smart_scheduler import get_scheduler
from application.services.condition_monitor import get_condition_monitor
from application.services.feishu_service import get_feishu_service
from application.services.scheduler_config_service import SchedulerConfigService

logger = logging.getLogger(__name__)

automation_bp = Blueprint('automation', __name__, url_prefix='/api/automation')

# 初始化服务
_scheduler_config_service = SchedulerConfigService()


# ========== 任务管理 ==========

@automation_bp.route('/tasks', methods=['GET'])
def list_automation_tasks():
    """列出所有自动化任务（使用ORM）"""
    try:
        # 查询参数
        task_type = request.args.get('task_type')
        is_enabled = request.args.get('is_enabled')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # 使用ORM服务
        enabled_only = is_enabled and is_enabled.lower() == 'true'
        tasks = _scheduler_config_service.list_configs(
            enabled_only=enabled_only,
            command=task_type
        )

        # 分页
        total = len(tasks)
        paginated_tasks = tasks[offset:offset + limit]

        return jsonify({
            'success': True,
            'data': {
                'tasks': paginated_tasks,
                'total': total,
                'limit': limit,
                'offset': offset
            }
        })

    except Exception as e:
        logger.error(f"Error listing automation tasks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
            ORDER BY priority DESC, created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])

        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'task_name': row[1],
                'task_type': row[2],
                'schedule_config': row[3],
                'condition_rules': row[4],
                'agent_tool': row[5],
                'params': row[6],
                'priority': row[7],
                'is_enabled': row[8],
                'last_run_at': row[9].isoformat() if row[9] else None,
                'next_run_at': row[10].isoformat() if row[10] else None,
                'created_at': row[11].isoformat() if row[11] else None,
                'description': row[12]
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'tasks': tasks,
                'total': total,
                'limit': limit,
                'offset': offset
            }
        })

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@automation_bp.route('/tasks', methods=['POST'])
def create_automation_task():
    """创建自动化任务"""
    try:
        data = request.json

        # 验证必需字段
        required_fields = ['task_name', 'task_type', 'agent_tool']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f"Missing required field: {field}"
                }), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO quant.automation_tasks (
                task_name, task_type, schedule_config, condition_rules,
                agent_tool, api_endpoint, params, priority, is_enabled,
                description, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['task_name'],
            data['task_type'],
            data.get('schedule_config'),
            data.get('condition_rules'),
            data['agent_tool'],
            data.get('api_endpoint'),
            data.get('params', {}),
            data.get('priority', 5),
            data.get('is_enabled', True),
            data.get('description'),
            data.get('created_by', 'system')
        ))

        task_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Created automation task: {data['task_name']} (id={task_id})")

        return jsonify({
            'success': True,
            'data': {
                'task_id': task_id,
                'task_name': data['task_name']
            }
        }), 201

    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@automation_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_automation_task(task_id: int):
    """更新自动化任务"""
    try:
        data = request.json

        conn = get_db_connection()
        cursor = conn.cursor()

        # 构建更新语句
        update_fields = []
        params = []

        allowed_fields = [
            'schedule_config', 'condition_rules', 'params',
            'priority', 'is_enabled', 'description'
        ]

        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                params.append(data[field])

        if not update_fields:
            return jsonify({
                'success': False,
                'error': 'No fields to update'
            }), 400

        params.append(task_id)

        cursor.execute(f"""
            UPDATE quant.automation_tasks
            SET {', '.join(update_fields)}
            WHERE id = %s
        """, params)

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Updated automation task: {task_id}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Failed to update task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@automation_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_automation_task(task_id: int):
    """删除自动化任务"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM quant.automation_tasks
            WHERE id = %s
        """, (task_id,))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Deleted automation task: {task_id}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Failed to delete task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@automation_bp.route('/tasks/<int:task_id>/trigger', methods=['POST'])
def trigger_automation_task(task_id: int):
    """手动触发任务"""
    try:
        params = request.json or {}

        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取任务信息
        cursor.execute("""
            SELECT task_name, agent_tool, params
            FROM quant.automation_tasks
            WHERE id = %s
        """, (task_id,))

        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404

        task_name = row[0]
        cursor.close()
        conn.close()

        # 触发任务
        scheduler = get_scheduler()
        run_id = scheduler.trigger_task(task_name, params)

        logger.info(f"Manually triggered task: {task_name} (run_id={run_id})")

        return jsonify({
            'success': True,
            'data': {
                'run_id': run_id,
                'task_name': task_name
            }
        })

    except Exception as e:
        logger.error(f"Failed to trigger task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@automation_bp.route('/tasks/<int:task_id>/enable', methods=['POST'])
def enable_automation_task(task_id: int):
    """启用任务"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE quant.automation_tasks
            SET is_enabled = true
            WHERE id = %s
        """, (task_id,))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Enabled automation task: {task_id}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Failed to enable task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@automation_bp.route('/tasks/<int:task_id>/disable', methods=['POST'])
def disable_automation_task(task_id: int):
    """禁用任务"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE quant.automation_tasks
            SET is_enabled = false
            WHERE id = %s
        """, (task_id,))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Disabled automation task: {task_id}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Failed to disable task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 执行历史 ==========

@automation_bp.route('/runs', methods=['GET'])
def list_automation_runs():
    """查询任务执行历史"""
    try:
        task_id = request.args.get('task_id', type=int)
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        conn = get_db_connection()
        cursor = conn.cursor()

        # 构建查询
        where_clauses = []
        params = []

        if task_id:
            where_clauses.append("task_id = %s")
            params.append(task_id)

        if status:
            where_clauses.append("status = %s")
            params.append(status)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 查询总数
        cursor.execute(f"""
            SELECT COUNT(*) FROM quant.automation_runs {where_sql}
        """, params)
        total = cursor.fetchone()[0]

        # 查询执行记录
        cursor.execute(f"""
            SELECT r.id, r.task_id, r.run_id, r.trigger_type, r.trigger_by,
                   r.started_at, r.completed_at, r.status, r.result,
                   r.error_message, r.execution_time_ms, t.task_name
            FROM quant.automation_runs r
            JOIN quant.automation_tasks t ON r.task_id = t.id
            {where_sql}
            ORDER BY r.started_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])

        runs = []
        for row in cursor.fetchall():
            runs.append({
                'id': row[0],
                'task_id': row[1],
                'run_id': row[2],
                'trigger_type': row[3],
                'trigger_by': row[4],
                'started_at': row[5].isoformat() if row[5] else None,
                'completed_at': row[6].isoformat() if row[6] else None,
                'status': row[7],
                'result': row[8],
                'error_message': row[9],
                'execution_time_ms': row[10],
                'task_name': row[11]
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'runs': runs,
                'total': total,
                'limit': limit,
                'offset': offset
            }
        })

    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 条件监控 ==========

@automation_bp.route('/monitors', methods=['GET'])
def list_condition_monitors():
    """列出条件监控器"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, monitor_name, condition_type, condition_expression,
                   check_interval, triggered_task_id, is_active,
                   last_check_at, last_triggered_at, trigger_count, description
            FROM quant.condition_monitors
            ORDER BY is_active DESC, created_at DESC
        """)

        monitors = []
        for row in cursor.fetchall():
            monitors.append({
                'id': row[0],
                'monitor_name': row[1],
                'condition_type': row[2],
                'condition_expression': row[3],
                'check_interval': row[4],
                'triggered_task_id': row[5],
                'is_active': row[6],
                'last_check_at': row[7].isoformat() if row[7] else None,
                'last_triggered_at': row[8].isoformat() if row[8] else None,
                'trigger_count': row[9],
                'description': row[10]
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {'monitors': monitors}
        })

    except Exception as e:
        logger.error(f"Failed to list monitors: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@automation_bp.route('/monitors', methods=['POST'])
def create_condition_monitor():
    """创建条件监控器"""
    try:
        data = request.json

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO quant.condition_monitors (
                monitor_name, condition_type, condition_expression,
                check_interval, triggered_task_id, is_active, description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['monitor_name'],
            data['condition_type'],
            data['condition_expression'],
            data.get('check_interval', 60),
            data.get('triggered_task_id'),
            data.get('is_active', True),
            data.get('description')
        ))

        monitor_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Created condition monitor: {data['monitor_name']} (id={monitor_id})")

        return jsonify({
            'success': True,
            'data': {'monitor_id': monitor_id}
        }), 201

    except Exception as e:
        logger.error(f"Failed to create monitor: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 健康检查 ==========

@automation_bp.route('/health', methods=['GET'])
def automation_health():
    """自动化系统健康检查"""
    try:
        scheduler = get_scheduler()

        # 查询统计信息
        conn = get_db_connection()
        cursor = conn.cursor()

        # 今日任务统计
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM quant.automation_runs
            WHERE started_at >= CURRENT_DATE
        """)
        row = cursor.fetchone()
        tasks_today = row[0] or 0
        success_today = row[1] or 0
        failed_today = row[2] or 0

        success_rate = success_today / tasks_today if tasks_today > 0 else 0

        cursor.close()
        conn.close()

        return jsonify({
            'status': 'healthy',
            'components': {
                'scheduler': {
                    'status': 'running' if scheduler.scheduler.running else 'stopped',
                    'active_jobs': len(scheduler.task_registry)
                },
                'database': {
                    'status': 'connected'
                }
            },
            'statistics': {
                'tasks_today': tasks_today,
                'success_rate': round(success_rate, 2),
                'failed_today': failed_today
            }
        })

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
