"""后台任务并发控制（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来"""
import threading
from typing import Dict

_running_tasks: Dict[str, str] = {}
_task_lock = threading.Lock()


def acquire_task(task_type: str, run_id: str) -> bool:
    """获取任务执行权限"""
    with _task_lock:
        if task_type in _running_tasks:
            return False
        _running_tasks[task_type] = run_id
        return True


def release_task(task_type: str, run_id: str) -> bool:
    """释放任务执行权限"""
    with _task_lock:
        if _running_tasks.get(task_type) == run_id:
            del _running_tasks[task_type]
            return True
        return False


def get_running_tasks() -> Dict[str, str]:
    """获取当前运行的任务列表"""
    with _task_lock:
        return dict(_running_tasks)


def get_running_tasks_snapshot():
    """获取运行中任务快照（向后兼容）"""
    return get_running_tasks()
