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


# 线程引导/库内部帧的路径特征：这些帧永远位于创建点之前，且与泄漏根因无关
_NOISE_FRAME_PARTS = (
    'threading.py',
    'concurrent/futures/thread.py',
    'concurrent/futures/_base.py',
    'concurrent/futures/__init__.py',
    'site-packages/',
    'importlib/_bootstrap',
    'runpy.py',
)


def _capture_origin_stack(max_frames: int = 10):
    """捕获 Session 创建点的应用侧调用栈

    返回 (stack_text, origin)：origin 为最内层应用帧的 "函数@文件:行号"。

    2026-09-11 修复（错误看板 session_leak_detected 126 次无法定位根因）：
    原实现直接 traceback.format_stack()，在 ThreadPoolExecutor 工作线程里创建 Session 时
    前几十帧全是 threading._bootstrap 引导帧，日志按 500 字符截断后只剩引导帧
    （实测 detail 尾部停在 "self._targe"），真实调用方被截掉 → 事件不可行动。
    改为：先剔除引导帧/第三方库帧，再取最靠近创建点的 max_frames 帧。
    """
    try:
        frames = traceback.extract_stack()[:-1]
    except Exception:
        return '', 'unknown'
    _own_file = __file__
    app_frames = [
        f for f in frames
        # 排除本模块自身的帧（否则 origin 会指向 guard 自己，仍定位不到调用方）
        if f.filename != _own_file
        and not any(part in f.filename for part in _NOISE_FRAME_PARTS)
    ]
    kept = app_frames[-max_frames:] if app_frames else frames[-max_frames:]
    if not kept:
        return '', 'unknown'
    origin = f"{kept[-1].name}@{kept[-1].filename}:{kept[-1].lineno}"
    return ''.join(traceback.format_list(kept)), origin


def track_session_creation(session):
    """记录 Session 创建（在 get_session() 中调用）

    Args:
        session: SQLAlchemy Session 实例
    """
    if not _guard_enabled:
        return

    session_id = id(session)
    _stack_text, _origin = _capture_origin_stack()
    _dict_stack = {'traceback': _stack_text, 'origin': _origin}
    with _registry_lock:
        _session_registry[session_id] = {
            'session': weakref.ref(session),
            'created_at': time.time(),
            'thread_id': threading.get_ident(),
            'thread_name': threading.current_thread().name,
            # 只保留应用侧帧：origin 直接指出创建点，stack 供追溯
            **_dict_stack,
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


def _scan_and_clean(now: float) -> Dict[str, int]:
    """扫描注册表：注销无主/空闲条目，只对仍握着活动事务的 Session 报泄漏。

    返回计数 {dead_pruned, idle_unregistered, cleaned, failed}。

    2026-09-11（investor / w-8f2c4cc5）根因修复。线上 995 次 session_leak_detected 构成：
      · 438 次（44%）弱引用已死（Session 早被 GC）却仍被判泄漏 → 纯误报；
      · 其余大量"清理成功"并非真泄漏：代码直接调 session.close()（如 job_executor.finally）时，
        scoped_session 的线程本地注册表仍强引用该对象 → 弱引用存活 → 5 分钟后被判泄漏，
        且清理在 guard 线程里对"属于工作线程的同一对象"执行 rollback——工作线程随后可能
        已用该会话开启新事务，跨线程 rollback 会打掉正常事务。
    现判定：弱引用已死 → 注销（误报）；对象存活但无活动事务 → 只注销，不跨线程 rollback
    （无事务即未持有连接资源）；确有活动事务 → 保留止血（rollback+close）。
    """
    leaked = []
    dead_pruned = 0
    idle_unregistered = 0

    with _registry_lock:
        for session_id, info in list(_session_registry.items()):
            ref = info.get('session')
            session = ref() if ref else None
            if session is None:
                # Session 对象已被 GC：无论是否曾泄漏，现在都不可能还占着资源
                _session_registry.pop(session_id, None)
                dead_pruned += 1
                continue

            age = now - info['created_at']
            if age <= _timeout_seconds:
                continue

            in_transaction = False
            try:
                in_transaction = bool(session.in_transaction())
            except Exception:
                in_transaction = False

            if not in_transaction:
                # 无活动事务 = 未持有连接/事务资源，只是被线程本地注册表持有
                _session_registry.pop(session_id, None)
                idle_unregistered += 1
                logger.warning(
                    "session_unregistered_idle",
                    session_id=session_id,
                    age_seconds=int(age),
                    thread_name=info.get('thread_name'),
                    origin=info.get('origin', 'unknown'),
                )
                continue

            leaked.append((session_id, info, age))

    cleaned = 0
    failed = 0
    for session_id, info, age in leaked:
        session_ref = info['session']
        session = session_ref() if session_ref else None

        logger.error(
            "session_leak_detected",
            session_id=session_id,
            age_seconds=int(age),
            thread_id=info['thread_id'],
            thread_name=info['thread_name'],
            origin=info.get('origin', 'unknown'),  # 创建点（函数@文件:行号）
            traceback=info['traceback'][:2000]  # 已剔除引导帧，放宽预算
        )

        if session is not None:
            try:
                if session.is_active:
                    session.rollback()
                session.close()
                cleaned += 1
                logger.info("leaked_session_cleaned", session_id=session_id)
            except Exception as e:
                # idle-in-transaction timeout 是预期的（PostgreSQL 已关闭连接）
                error_msg = str(e)
                if "idle-in-transaction timeout" in error_msg:
                    logger.warning(
                        "leaked_session_already_closed_by_db",
                        session_id=session_id,
                        reason="idle_in_transaction_timeout"
                    )
                else:
                    failed += 1
                    logger.error(
                        "failed_to_clean_leaked_session",
                        session_id=session_id,
                        error=error_msg
                    )

        with _registry_lock:
            _session_registry.pop(session_id, None)

    return {
        'dead_pruned': dead_pruned,
        'idle_unregistered': idle_unregistered,
        'cleaned': cleaned,
        'failed': failed,
    }


def _guard_loop():
    """后台线程：定期检查泄漏的 Session"""
    logger.info("session_guard_started", timeout=_timeout_seconds)

    while _guard_enabled:
        try:
            stats = _scan_and_clean(time.time())
            if stats['dead_pruned'] or stats['idle_unregistered']:
                logger.info("session_guard_scan", **stats)
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
