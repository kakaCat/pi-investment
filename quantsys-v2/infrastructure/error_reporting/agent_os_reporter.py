

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

logger = logging.getLogger(__name__)
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

# ---------------- 测试/CI 隔离（P0，2026-09-10 w-8f2c4cc5） ----------------
# 背景：install() 把 ERROR Handler 挂到根 logger 后，**pytest 全量跑一遍会把测试夹具里
# 刻意触发的错误当作生产错误灌进 Agent OS 错误看板**：2026-09-10 15:30 / 22:29-22:34 /
# 23:31 三次跑批共上报 441 条 open 事件、覆盖 49 个消息族（boom / fake-task /
# tests.mocks / InvalidClassName / quant.secret_table / eastmoney reset 等全部可在
# tests/ 目录找到对应夹具），占当日 open 事件 96%——生产错误看板被测试噪音淹没，
# 真实故障（如 ml_models 缺陷）反而被埋在下面。
# 规则：pytest 进程内一律不上报；需要验证上报链路本身的测试显式开
# AGENT_OS_ERROR_REPORT_FORCE=1。
_FORCE_ENV = "AGENT_OS_ERROR_REPORT_FORCE"
_OFF_ENV = "AGENT_OS_ERROR_REPORTING"
_TRUTHY = ("1", "true", "yes", "on")


def _pytest_running() -> bool:
    """判断当前进程是否 pytest 运行（PYTEST_CURRENT_TEST 由 pytest 每个测试设置）。"""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    if os.getenv("PYTEST_VERSION") or os.getenv("PYTEST_ADDOPTS"):
        return True
    return "pytest" in sys.modules


def reporting_disabled() -> bool:
    """是否抑制上报（测试隔离优先于显式关闭）。FORCE 仅用于测试上报链路本身。"""
    if os.getenv(_FORCE_ENV, "").strip().lower() in _TRUTHY:
        return False
    if os.getenv(_OFF_ENV, "").strip().lower() in ("off", "0", "false", "no"):
        return True
    return _pytest_running()

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
# 规则（2026-09-10 重构为 Sentry 式分层）：①堆栈优先（detail 有 traceback 时按帧序列
# 取指纹，入参差异天然合并）；②无堆栈时 msg 通用参数化兜底——抹 uuid/hex/ISO时间
# 等日志元数据 + 通用数字参数化（\d+(\.\d+)*(\.[A-Za-z]{2,4})? 覆盖股票代码/价格/数量/
# 行号等一切入参数字，不再用"6位股票代码"这类业务规则过拟合）。
_VOLATILE_JSON_KEYS = ("trace_id", "timestamp", "ts", "time", "request_id", "span_id", "run_id")
# 结构化日志的「根因文本」字段（按优先级），与 Go jsonEssenceKeys 对齐
_JSON_ESSENCE_KEYS = ("event", "message", "msg", "error", "exception", "detail")
# 纯文本通道的 logger 前缀（模块路径形态，至少含一个点且小写开头）：与 Go reLoggerPrefix 同规则。
# 限定形态是为了不误伤 "TypeError: xxx" 这类异常名开头（无点、首字母大写）。
_RE_LOGGER_PREFIX = re.compile(r"^[a-z_][a-z0-9_]*(?:\.[a-z0-9_]+)+:\s+")
_RE_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_RE_HEX_LONG = re.compile(r"(?<![0-9a-zA-Z])[0-9a-fA-F]{16,}(?![0-9a-zA-Z])")
_RE_HEX8 = re.compile(r"(?<![0-9a-zA-Z])[0-9a-fA-F]{8}(?![0-9a-zA-Z])")
_RE_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
# 通用数字参数化：连续数字段（含小数点分段与 .SH 类字母后缀）→ <num>
_RE_NUMBER = re.compile(r"\d+(?:\.\d+)*(?:\.[A-Za-z]{2,4})?")
# traceback 帧：File "path", line N, in func
_RE_TB_FRAME = re.compile(r'File "([^"]+)", line \d+, in (\w+)')


def normalize_msg(msg: str) -> str:
    """归一化错误消息：抹掉 trace_id/timestamp/uuid 等易变段，使同根因错误同指纹。

    2026-09-11（w-8f2c4cc5）：JSON 通道与文本通道此前指纹不同——structlog JSON 落盘的
    指纹取「去掉易变键后的整段 JSON」，纯文本 logger 落盘的取「剥掉 logger 前缀的事件
    文案」，两者天然不等，一次异常因此生成 2 条事件（实测 00:52 SchedulerService.add_task
    TypeError）。现两端口径统一为「取事件文案本身（event/message/msg）」。
    """
    s = (msg or "").strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                for k in _VOLATILE_JSON_KEYS:
                    obj.pop(k, None)
                essence = _json_essence_text(obj)
                if essence is not None:
                    s = essence
                else:
                    s = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))  # 紧凑格式对齐 Go json.Marshal
        except Exception:  # noqa: BLE001 —— 非 JSON 按文本处理
            pass
    s = _RE_LOGGER_PREFIX.sub("", s)
    s = _RE_UUID.sub("<uuid>", s)
    s = _RE_ISO_TS.sub("<ts>", s)
    s = _RE_HEX_LONG.sub("<hex>", s)
    s = _RE_HEX8.sub("<hex8>", s)
    s = _RE_NUMBER.sub("<num>", s)
    return s


def _json_essence_text(obj: dict) -> Optional[str]:
    """取结构化日志的根因文本：语义键的值按顺序以 | 拼接，无则 None。

    只取 event 会漏掉「event 是通用标签、error 才是根因」的日志形态；拼接既保持通道间
    可比（同一事件文案在 JSON 与文本通道一致），又避免不同故障因共用标签被合并。
    与 Go jsonEssenceText 同规则。
    """
    parts = [v for v in (obj.get(k) for k in _JSON_ESSENCE_KEYS)
             if isinstance(v, str) and v.strip()]
    return "|".join(parts) if parts else None


def _stack_fingerprint_input(detail: Optional[str]) -> Optional[str]:
    """从 detail 的 traceback 提取帧序列（basename:func，不含行号——代码微调行号变
    但根因相同应合并）。无堆栈返回 None。"""
    if not detail:
        return None
    frames = _RE_TB_FRAME.findall(detail)
    if not frames:
        return None
    return "|".join(f"{f.rsplit('/', 1)[-1]}:{fn}" for f, fn in frames)


def _fingerprint(msg: str, task_id: Optional[Any], detail: Optional[str] = None) -> str:
    """分层指纹：堆栈帧序列优先（同根因异入参天然合并）；无堆栈回退 msg 通用参数化。"""
    stack = _stack_fingerprint_input(detail)
    tid = task_id if task_id is not None else ""
    if stack:
        raw = f"{_SOURCE}|{tid}|stack|{stack}"
    else:
        raw = f"{_SOURCE}|{tid}|{normalize_msg(msg)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]  # 截断 40 位对齐 Go 端


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
    payload["fingerprint"] = _fingerprint(payload["msg"], task_id, payload.get("detail"))
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
    if reporting_disabled():
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
            if reporting_disabled():
                return
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
    if reporting_disabled():
        log.info("Agent OS 结构化错误上报已抑制（测试进程或显式关闭）")
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
