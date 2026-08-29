"""
ORM Session 泄漏检测和自动清理

功能：
1. 检测长时间未关闭的 Session
2. 自动回滚和关闭泄漏的 Session
3. 记录泄漏点的调用栈（开发调试用）

用法：
    # 在应用启动时启用
    from infrastructure.persistence.orm.session_guard import enable_session_guard
    enable_session_guard(timeout=300)  # 5 分钟超时
"""

import threading
import time
import traceback
import weakref
from typing import Dict, Optional
import structlog

logger = structlog.get_logger(__name__)

# 全局 Session 跟踪
_session_registry: Dict[int, Dict] = {}
_registry_lock = threading.Lock()
_guard_thread: Optional[threading.Thread] = None
_guard_enabled = False
_timeout_seconds = 300  # 默认 5 分钟


def track_session_creation(session):
    """记录 Session 创建（在 get_session() 中调用）

    Args:
        session: SQLAlchemy Session 实例
    """
    if not _guard_enabled:
        return

    session_id = id(session)
    with _registry_lock:
        _session_registry[session_id] = {
            'session': weakref.ref(session),
            'created_at': time.time(),
            'thread_id': threading.get_ident(),
            'thread_name': threading.current_thread().name,
            'traceback': ''.join(traceback.format_stack()[:-1])  # 排除当前帧
        }


def track_session_close(session):
    """记录 Session 关闭（在 close_session() 中调用）

    Args:
        session: SQLAlchemy Session 实例
    """
    if not _guard_enabled:
        return

    session_id = id(session)
    with _registry_lock:
        _session_registry.pop(session_id, None)


def _guard_loop():
    """后台线程：定期检查泄漏的 Session"""
    logger.info("session_guard_started", timeout=_timeout_seconds)

    while _guard_enabled:
        try:
            now = time.time()
            leaked_sessions = []

            with _registry_lock:
                for session_id, info in list(_session_registry.items()):
                    age = now - info['created_at']
                    if age > _timeout_seconds:
                        leaked_sessions.append((session_id, info, age))

            # 处理泄漏的 Session
            for session_id, info, age in leaked_sessions:
                session_ref = info['session']
                session = session_ref() if session_ref else None

                logger.error(
                    "session_leak_detected",
                    session_id=session_id,
                    age_seconds=int(age),
                    thread_id=info['thread_id'],
                    thread_name=info['thread_name'],
                    traceback=info['traceback'][:500]  # 截断避免日志过大
                )

                # 尝试清理
                if session is not None:
                    try:
                        if session.is_active:
                            session.rollback()
                        session.close()
                        logger.info(
                            "leaked_session_cleaned",
                            session_id=session_id
                        )
                    except Exception as e:
                        logger.error(
                            "failed_to_clean_leaked_session",
                            session_id=session_id,
                            error=str(e)
                        )

                # 从注册表移除
                with _registry_lock:
                    _session_registry.pop(session_id, None)

        except Exception as e:
            logger.error("session_guard_error", error=str(e), exc_info=True)

        time.sleep(60)  # 每分钟检查一次


def enable_session_guard(timeout: int = 300):
    """启用 Session 泄漏检测

    Args:
        timeout: Session 超时时间（秒），默认 300 (5分钟)
    """
    global _guard_enabled, _guard_thread, _timeout_seconds

    if _guard_enabled:
        logger.warning("session_guard_already_enabled")
        return

    _timeout_seconds = timeout
    _guard_enabled = True

    _guard_thread = threading.Thread(
        target=_guard_loop,
        name="session-guard",
        daemon=True
    )
    _guard_thread.start()

    logger.info("session_guard_enabled", timeout=timeout)


def disable_session_guard():
    """禁用 Session 泄漏检测"""
    global _guard_enabled
    _guard_enabled = False
    logger.info("session_guard_disabled")


def get_session_stats() -> Dict:
    """获取当前 Session 统计信息

    Returns:
        dict: 统计信息
    """
    with _registry_lock:
        now = time.time()
        active_sessions = len(_session_registry)
        age_distribution = {
            '<1min': 0,
            '1-5min': 0,
            '5-10min': 0,
            '>10min': 0
        }

        for info in _session_registry.values():
            age = now - info['created_at']
            if age < 60:
                age_distribution['<1min'] += 1
            elif age < 300:
                age_distribution['1-5min'] += 1
            elif age < 600:
                age_distribution['5-10min'] += 1
            else:
                age_distribution['>10min'] += 1

        return {
            'active_sessions': active_sessions,
            'age_distribution': age_distribution,
            'guard_enabled': _guard_enabled,
            'timeout_seconds': _timeout_seconds
        }
