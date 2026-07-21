"""
定时任务管理 API - FastAPI 异步版本
连接到真实的 scheduler_tasks 表
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
import structlog
from sqlalchemy import text

from infrastructure.persistence.orm.config import get_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])


@router.get("/tasks")
async def get_tasks(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(12, ge=1, le=100, description="每页数量")
):
    """
    获取定时任务列表（分页）

    从真实的 scheduler_tasks 表查询数据

    Query参数:
    - page: 页码，从1开始
    - pageSize: 每页数量，默认12

    返回:
    {
      "success": true,
      "data": {
        "items": [...],
        "total": 6,
        "page": 1,
        "pageSize": 12
      }
    }
    """
    try:
        session = get_session()
        logger.info("get_tasks called", page=page, pageSize=pageSize)

        # 计算偏移量
        offset = (page - 1) * pageSize

        # 查询总数（排除已删除）
        count_query = text("SELECT COUNT(*) FROM scheduler_tasks WHERE deleted_at IS NULL")
        total = session.execute(count_query).scalar()
        logger.info("query_result", total=total, offset=offset, limit=pageSize)

        # 查询分页数据
        query = text("""
            SELECT id, name, enabled, schedule_kind, schedule_expr,
                   payload, created_at, updated_at
            FROM scheduler_tasks
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        result = session.execute(query, {"limit": pageSize, "offset": offset})
        rows = result.fetchall()
        logger.info("rows_fetched", count=len(rows))

        # 转换为字典格式
        items = []
        for row in rows:
            items.append({
                "id": row[0],
                "name": row[1],
                "enabled": row[2],
                "schedule_kind": row[3],
                "schedule_expr": row[4],
                "payload": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "updated_at": row[7].isoformat() if row[7] else None
            })

        return {
            "success": True,
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "pageSize": pageSize
            }
        }
    except Exception as e:
        logger.exception("Failed to get tasks", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """
    获取单个定时任务详情

    参数:
    - task_id: 任务ID

    返回:
    {
      "success": true,
      "data": {
        "id": "task_id",
        "name": "task_name",
        ...
      }
    }
    """
    try:
        session = get_session()

        query = text("""
            SELECT id, name, enabled, schedule_kind, schedule_expr,
                   schedule_at, every_seconds, delay_seconds, anchor_at,
                   payload, compensation_enabled, compensation_check_after,
                   compensation_max_attempts, delete_after_run,
                   created_at, updated_at
            FROM scheduler_tasks
            WHERE id = :task_id AND deleted_at IS NULL
        """)

        result = session.execute(query, {"task_id": task_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        task_data = {
            "id": row[0],
            "name": row[1],
            "enabled": row[2],
            "schedule_kind": row[3],
            "schedule_expr": row[4],
            "schedule_at": row[5].isoformat() if row[5] else None,
            "every_seconds": row[6],
            "delay_seconds": row[7],
            "anchor_at": row[8].isoformat() if row[8] else None,
            "payload": row[9],
            "compensation_enabled": row[10],
            "compensation_check_after": row[11],
            "compensation_max_attempts": row[12],
            "delete_after_run": row[13],
            "created_at": row[14].isoformat() if row[14] else None,
            "updated_at": row[15].isoformat() if row[15] else None
        }

        return {
            "success": True,
            "data": task_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks")
async def create_task(task_data: Dict[str, Any]):
    """
    创建定时任务

    请求体:
    {
      "name": "task_name",
      "schedule": "cron_expression",
      "enabled": true,
      ...
    }

    返回:
    {
      "success": true,
      "data": {
        "id": "new_task_id",
        ...
      }
    }
    """
    try:
        # TODO: 实现任务创建逻辑
        return {
            "success": True,
            "data": {
                "id": "new_task_id",
                "message": "Task creation not yet implemented"
            }
        }
    except Exception as e:
        logger.exception("Failed to create task", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, task_data: Dict[str, Any]):
    """
    更新定时任务

    参数:
    - task_id: 任务ID

    请求体: 任务更新数据

    返回:
    {
      "success": true,
      "message": "Task updated successfully"
    }
    """
    try:
        # TODO: 实现任务更新逻辑
        return {
            "success": True,
            "message": f"Task {task_id} update not yet implemented"
        }
    except Exception as e:
        logger.exception("Failed to update task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """
    删除定时任务

    参数:
    - task_id: 任务ID

    返回:
    {
      "success": true,
      "message": "Task deleted successfully"
    }
    """
    try:
        # TODO: 实现任务删除逻辑
        return {
            "success": True,
            "message": f"Task {task_id} deletion not yet implemented"
        }
    except Exception as e:
        logger.exception("Failed to delete task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: str):
    """
    手动执行定时任务

    参数:
    - task_id: 任务ID

    返回:
    {
      "success": true,
      "message": "Task triggered successfully"
    }
    """
    try:
        # TODO: 实现任务执行逻辑
        return {
            "success": True,
            "message": f"Task {task_id} execution not yet implemented"
        }
    except Exception as e:
        logger.exception("Failed to run task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
