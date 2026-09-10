"""v2 → Agent OS 结构化错误上报（REQ-a42aa4 Batch C，2026-09-10 w-f4aa1f6a）

背景
----
Agent OS worker 被动 tail v2 launchd 日志收集错误（collect_channel=log_tail），
局限（用户确认后本批修复）：
  1) task_id / task_name 恒为 null —— 日志行没有结构化任务上下文；
  2) 多行 Traceback 被逐行切碎成多条噪音事件；
  3) 会话 JSON / tqdm 进度等噪音行被当 error 收走。
本模块让 v2 **主动**把运行时错误事件 POST 到 Agent OS ingest
（POST /api/v1/scheduler/error-events，source=v2，服务端按 fingerprint 去重计数），
错误发生点即携带 task 上下文与完整堆栈（detail 单字段），解决 1/2；3 由调用点
白名单化（只在真正错误路径上报，绝不整日志流搬运）解决。

纯标准库实现（urllib + threading + queue），无第三方依赖；失败静默退避重试 1 次，
绝不抛回调用方；自带风暴保护（同 logger+消息 60s 冷却），可安全挂在根 logger 上。

接线点（见各文件内注释）：
  * job_executor.execute_scheduled_job —— 计划任务失败（含 JobRegistry inner failed，
    此前该路径从不打 ERROR 日志，只写 scheduler_runs）→ 带 task_id/task_name/run_id；
  * adapters/.../exception_handlers.py —— HTTP 未处理异常 / QuantSys 系统级异常；
  * main.py —— install() 把 ERROR 级 Handler 挂到根 logger（覆盖后台线程/非 HTTP 路径）。

环境变量：
  AGENT_OS_ERROR_INGEST_URL   默认 http://127.0.0.1:8080/api/v1/scheduler/error-events
  AGENT_OS_ERROR_REPORTING    设 "off" 关闭（默认 on）
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import re
import socket
import sys
import threading
import time
import traceback
import urllib.request
from typing import Any, Optional

_DEFAULT_INGEST = "http://127.0.0.1:8080/api/v1/scheduler/error-events"
_SOURCE = "v2"
_SELF_PREFIX = "infrastructure.error_reporting"

log = logging.getLogger(_SELF_PREFIX + ".agent_os_reporter")

# ---------------- 异步发送（队列 + 单 daemon 线程） ----------------
_tasks: "queue.Queue[dict]" = queue.Queue(maxsize=512)
_worker_started = False
_worker_lock = threading.Lock()
_send_lock = threading.Lock()
_last_send_failure: dict = {}


def _ensure_worker() -> None:
    global _worker_started
    if _worker_started:
        return
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_worker_loop, name="agent-os-error-reporter", daemon=True)
        t.start()
        _worker_started = True


def _ingest_url() -> str:
    return os.getenv("AGENT_OS_ERROR_INGEST_URL", _DEFAULT_INGEST)


def _post(payload: dict) -> bool:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    req = urllib.request.Request(
        _ingest_url(), data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        resp.read(256)
    return True


def _worker_loop() -> None:
    while True:
        try:
            item = _tasks.get(timeout=2.0)
        except queue.Empty:
            continue
        except Exception:
            return
        ok = False
        for attempt in (0, 1):
            try:
                ok = _post(item)
                if ok:
                    break
            except Exception as e:  # noqa: BLE001 —— 上报失败绝不抛回
                if attempt == 0:
                    time.sleep(0.4)
                last = e
        if not ok:
            now = time.time()
            if now - _last_send_failure.get("ts", 0) > 60:  # 每分钟最多记一次
                _last_send_failure["ts"] = now
                log.warning("agent-os ingest POST failed (dropped): %s", getattr(last, "reason", last))


# ---------------- 指纹归一化（P0，2026-09-10 w-f4aa1f6a） ----------------
# 背景：msg 原文直接哈希 → 同一根因错误因 trace_id/timestamp 等易变段产生不同指纹，
# 重复上报不合并（79de0df7 与 f34b889e 同为 shutdown(timeout) 却两行），且服务端
# "resolved 后同指纹复现自动复开"机制对这类错误完全失效（假解决逃逸检测）。
# 规则：JSON 行先删易变键再规范化序列化；文本抹 uuid/hex/ISO时间/毫秒时间戳。
_VOLATILE_JSON_KEYS = ("trace_id", "timestamp", "ts", "time", "request_id", "span_id", "run_id")
_RE_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_RE_HEX_LONG = re.compile(r"(?<![0-9a-zA-Z])[0-9a-fA-F]{16,}(?![0-9a-zA-Z])")
_RE_HEX8 = re.compile(r"(?<![0-9a-zA-Z])[0-9a-fA-F]{8}(?![0-9a-zA-Z])")
_RE_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_RE_EPOCH_MS = re.compile(r"(?<!\d)\d{13,}(?!\d)")


def normalize_msg(msg: str) -> str:
    """归一化错误消息：抹掉 trace_id/timestamp/uuid 等易变段，使同根因错误同指纹。"""
    s = (msg or "").strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                for k in _VOLATILE_JSON_KEYS:
                    obj.pop(k, None)
                s = json.dumps(obj, sort_keys=True, ensure_ascii=False)
        except Exception:  # noqa: BLE001 —— 非 JSON 按文本处理
            pass
    s = _RE_UUID.sub("<uuid>", s)
    s = _RE_ISO_TS.sub("<ts>", s)
    s = _RE_HEX_LONG.sub("<hex>", s)
    s = _RE_HEX8.sub("<hex8>", s)
    s = _RE_EPOCH_MS.sub("<num>", s)
    return s


def _fingerprint(msg: str, task_id: Optional[Any]) -> str:
    raw = f"{_SOURCE}|{task_id if task_id is not None else ''}|{normalize_msg(msg)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _enqueue(msg: str, *, detail: Optional[str] = None, level: str = "error",
             task_id: Optional[Any] = None, task_name: Optional[str] = None,
             logger_name: Optional[str] = None, extra: Optional[dict] = None,
             metadata: Optional[dict] = None) -> None:
    payload: dict = {
        "source": _SOURCE,
        "level": level,
        "msg": (msg or "?").strip()[:2000],
    }
    if detail:
        payload["detail"] = detail[:20000]
    if task_id is not None:
        payload["task_id"] = str(task_id)
    if task_name:
        payload["task_name"] = str(task_name)[:200]
    md: dict = {"channel": "structured_reporter", "host": socket.gethostname()}
    if logger_name:
        md["logger"] = logger_name
    if metadata:
        md.update(metadata)
    payload["metadata"] = md
    payload["fingerprint"] = _fingerprint(payload["msg"], task_id)
    if extra:
        payload["extra"] = extra
    try:
        _tasks.put_nowait(payload)
    except queue.Full:
        pass  # 队列满直接丢——绝不阻塞业务


# ---------------- 对外 API ----------------

def report_event(msg: str, *, detail: Optional[str] = None, level: str = "error",
                 task_id: Optional[Any] = None, task_name: Optional[str] = None,
                 logger_name: Optional[str] = None, metadata: Optional[dict] = None) -> None:
    """主动上报一条结构化错误事件（不依赖日志路径）。"""
    if os.getenv("AGENT_OS_ERROR_REPORTING") == "off":
        return
    _ensure_worker()
    _enqueue(msg, detail=detail, level=level, task_id=task_id, task_name=task_name,
             logger_name=logger_name, metadata=metadata)


def report_exception(exc: BaseException, *, task_id: Optional[Any] = None,
                     task_name: Optional[str] = None, context: Optional[dict] = None,
                     metadata: Optional[dict] = None) -> None:
    """把已捕获异常（含堆栈）结构化上报。detail=完整 traceback 单字段。"""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    msg = f"{exc.__class__.__name__}: {exc}"[:2000]
    md = dict(metadata or {})
    if context:
        md["context"] = context
    report_event(msg, detail=tb, task_id=task_id, task_name=task_name,
                 logger_name=exc.__class__.__module__, metadata=md)


class AgentOSErrorLogHandler(logging.Handler):
    """根 logger ERROR Handler：ERROR/CRITICAL 记录 → 结构化上报。

    风暴保护：同 (logger, msg前80字符) 60s 冷却；自身上报失败/内部日志永远不上报
    （前缀 _SELF_PREFIX 直接跳过），杜绝递归风暴。
    """

    def __init__(self, level: int = logging.ERROR) -> None:
        super().__init__(level=level)
        self._cooldown: dict = {}

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 —— logging 要求
        try:
            if record.name.startswith(_SELF_PREFIX):
                return
            now = time.monotonic()
            exc = record.exc_info
            # 堆栈 fallback（A 方案，2026-09-10 w-f4aa1f6a）：except 块内 logger.error 未显式传
            # exc_info=True 时（如 structlog 风格调用），取当前线程活跃异常补齐 traceback。
            if not (exc and exc[2] is not None):
                si = sys.exc_info()
                if si[2] is not None:
                    exc = si
            msg = record.getMessage().strip()
            if not msg and exc:
                msg = f"{exc[0].__name__}: {exc[1]}"
            key = f"{record.name}|{normalize_msg(msg)[:80]}"
            last = self._cooldown.get(key, 0.0)
            if now - last < 60.0:
                return
            self._cooldown[key] = now
            if len(self._cooldown) > 512:
                self._cooldown.clear()
            detail: Optional[str] = None
            if exc and exc[2] is not None:
                detail = "".join(traceback.format_exception(*exc))
            md: dict = {"thread": record.threadName or "", "channel": "log_handler"}
            if record.name:
                md["logger"] = record.name
            ctx_id = getattr(_ctx_store, "task_id", None)
            ctx_name = getattr(_ctx_store, "task_name", None)
            if ctx_id is None and hasattr(record, "task_id"):
                ctx_id = record.task_id
            if ctx_name is None and hasattr(record, "task_name"):
                ctx_name = record.task_name
            _ensure_worker()
            _enqueue(msg, detail=detail, level=(record.levelname or "error").lower(),
                     task_id=ctx_id, task_name=ctx_name,
                     logger_name=record.name, metadata=md)
        except Exception:  # noqa: BLE001 —— Handler 绝不允许抛异常（logging 规范）
            pass


# ---------------- 线程级任务上下文 ----------------
# 计划任务执行器（job_executor）入口 set/clear，使该线程上任意 ERROR 日志
# （含深层 logger.exception）都能携带 task_id/task_name，根治"task 恒 null"。

_ctx_store = threading.local()


def set_task_context(task_id: Optional[Any] = None, task_name: Optional[str] = None) -> None:
    _ctx_store.task_id = task_id
    _ctx_store.task_name = task_name


def clear_task_context() -> None:
    _ctx_store.task_id = None
    _ctx_store.task_name = None


_installed = False
_install_lock = threading.Lock()


def install(level: int = logging.ERROR) -> bool:
    """把 Handler 挂到根 logger（幂等）。返回是否本次新装。"""
    global _installed
    if os.getenv("AGENT_OS_ERROR_REPORTING") == "off":
        return False
    with _install_lock:
        if _installed:
            return False
        try:
            root = logging.getLogger()
            root.addHandler(AgentOSErrorLogHandler(level))
            root.setLevel(min(root.level or logging.NOTSET, logging.ERROR))
            _ensure_worker()
            _installed = True
            log.info("Agent OS 结构化错误上报已启用 → %s", _ingest_url())
            return True
        except Exception:  # noqa: BLE001
            return False
