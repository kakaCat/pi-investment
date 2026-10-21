"""
进度推送工具类

用于批量任务的实时进度推送（通过 WebSocket）
"""
import logging
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class ProgressEmitter:
    """进度发射器 - 用于批量任务的进度推送"""

    def __init__(self, task_id: str, total: int, emit_func: Optional[Callable] = None):
        """
        初始化进度发射器

        Args:
            task_id: 任务ID
            total: 总步骤数
            emit_func: WebSocket emit 函数（可选，用于实时推送）
        """
        self.task_id = task_id
        self.total = total
        self.current = 0
        self.emit_func = emit_func
        self.start_time = datetime.now()
        self.last_message = ""

    def update(self, increment: int = 1, message: str = ""):
        """
        更新进度

        Args:
            increment: 进度增量（默认1）
            message: 当前步骤描述
        """
        self.current += increment
        self.last_message = message

        progress_data = {
            'task_id': self.task_id,
            'current': self.current,
            'total': self.total,
            'percentage': round((self.current / self.total) * 100, 1) if self.total > 0 else 0,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }

        # 推送到 WebSocket
        if self.emit_func:
            try:
                self.emit_func('progress', progress_data)
            except Exception as e:
                logger.warning(f"进度推送失败: {e}")

        # 记录日志
        logger.info(f"[{self.task_id}] 进度: {self.current}/{self.total} - {message}")

        return progress_data

    def complete(self, message: str = "任务完成"):
        """
        标记任务完成

        Args:
            message: 完成消息
        """
        elapsed = (datetime.now() - self.start_time).total_seconds()

        complete_data = {
            'task_id': self.task_id,
            'current': self.total,
            'total': self.total,
            'percentage': 100,
            'message': message,
            'elapsed_seconds': round(elapsed, 2),
            'completed': True,
            'timestamp': datetime.now().isoformat()
        }

        if self.emit_func:
            try:
                self.emit_func('progress', complete_data)
            except Exception as e:
                logger.warning(f"完成通知推送失败: {e}")

        logger.info(f"[{self.task_id}] 完成: {message} (耗时: {elapsed:.2f}秒)")

        return complete_data

    def error(self, error_message: str):
        """
        标记任务失败

        Args:
            error_message: 错误消息
        """
        elapsed = (datetime.now() - self.start_time).total_seconds()

        error_data = {
            'task_id': self.task_id,
            'current': self.current,
            'total': self.total,
            'percentage': round((self.current / self.total) * 100, 1) if self.total > 0 else 0,
            'message': error_message,
            'elapsed_seconds': round(elapsed, 2),
            'error': True,
            'timestamp': datetime.now().isoformat()
        }

        if self.emit_func:
            try:
                self.emit_func('progress', error_data)
            except Exception as e:
                logger.warning(f"错误通知推送失败: {e}")

        logger.error(f"[{self.task_id}] 失败: {error_message}")

        return error_data


def create_progress_emitter(task_id: str, total: int, socketio=None, room: str = None) -> ProgressEmitter:
    """
    创建进度发射器（工厂函数）

    Args:
        task_id: 任务ID
        total: 总步骤数
        socketio: Flask-SocketIO 实例（可选）
        room: WebSocket 房间名（可选，默认广播）

    Returns:
        ProgressEmitter 实例
    """
    emit_func = None

    if socketio:
        def emit_wrapper(event, data):
            if room:
                socketio.emit(event, data, room=room)
            else:
                socketio.emit(event, data, broadcast=True)

        emit_func = emit_wrapper

    return ProgressEmitter(task_id, total, emit_func)
