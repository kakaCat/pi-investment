"""测试期通知外发守卫（REQ-261003150739-b98d FR-3）

**问题**：pytest 进程能经 `NotificationFacade` → AgentChannel/FeishuChannel **真实外发**通知。
实证（2026-10-03）：跑 `tests/test_false_success_guard.py` 一个文件，真实渠道收到 4 张
`fake_job` 卡片；跑 e2e 手动触发用例再收 2 张 `watch_rule_health`。根因是"打桩点打在了
另一个命名空间"（见 tests/test_false_success_guard.py 的注释与 design/interfaces.md）。


**本模块**是一道**传输层**兜底：给全局 `requests.post/get` 套一层按 URL 分类的包装器，
命中通知接收端就**拦截 + 记账**（返回合成成功响应，不发起真实请求）；未命中则原样放行，
对数据源/HTTP 客户端等测试**完全透明**。


**设计取舍**（为什么不在门面层/渠道模块绑定层动手）：见
`docs/requirements/REQ-261003150739-b98d/design/architecture.md`。


**开关**：`QUANTSYS_NOTIFY_GUARD` = `off`（不安装）|`report`（只拦截记账）|`fail`（另判失败）。
默认值见 `DEFAULT_MODE` —— t3 先以 report 接线（兼容既有用例），t4 再切 fail。


**已知限制（如实登记）**：只覆盖模块级 `requests.post/get`；`requests.Session(...).post`
与其它 HTTP 客户端不经此包装器（当前通知链路不使用 Session）。
"""
from __future__ import annotations

import dataclasses
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

ENV_SWITCH = "QUANTSYS_NOTIFY_GUARD"
MODE_OFF = "off"
MODE_REPORT = "report"
MODE_FAIL = "fail"

#: 默认模式：`fail`（2026-10-03 · t4 切过来的）——未声明的真实外发会让**该用例失败**，
#: 把「打桩点漂移」从静默变成一条红用例。历史：t3 先以 `report` 接线（只拦截记账），
#: 待两处已知漏点修完、通知相关用例清点为零外发后才收紧到此值。
DEFAULT_MODE = MODE_FAIL

#: URL **路径**特征 → 接收端。**不依赖环境变量**，是分类的主判据（配置缺失也拦得住）。
#: 三条都取得足够具体：`/wake` 必须是**整段路径**（`path.rstrip('/') == '/wake'`），
#: 不做子串匹配——否则 `/api/awake` 之类会被误伤。
PATH_MARKERS: Tuple[Tuple[str, str], ...] = (
    ("/api/v1/notifications/send", "agent"),   # AgentChannel → Agent OS 通知网关
    ("/open-apis/bot/", "feishu"),             # 飞书自定义机器人 webhook
)
WAKE_PATH_MARKER = "/wake"

#: 默认端口（配置里没写端口时用它对齐）
_SCHEME_DEFAULT_PORT = {"http": 80, "https": 443}

#: 拦截时返回给调用方的合成响应：让两条渠道都走"成功"分支，不改变被测判定。
_SYNTHETIC_JSON: Dict[str, Any] = {"success": True, "code": 0, "StatusCode": 0}


@dataclasses.dataclass(frozen=True)
class NotifyAttempt:
    """一条被守卫看到的通知外发尝试（仅进程内存，不落盘）。"""

    ts: float
    method: str
    url: str
    sink: str
    test_nodeid: Optional[str]
    blocked: bool = True
    #: 是否真的出网。拦截先于调用真实函数，故恒为 False——这是"零噪声"的硬保证。
    egress: bool = False


class _SyntheticResponse:
    """合成响应：满足 AgentChannel（status_code/success）与 FeishuChannel（code/StatusCode）。"""

    status_code = 200
    text = ""
    headers: Dict[str, str] = {}

    def json(self) -> Dict[str, Any]:
        return dict(_SYNTHETIC_JSON)

    def raise_for_status(self) -> None:  # 兼容 requests 风格调用
        return None


def _authority(parts) -> Tuple[str, Optional[int]]:
    return (parts.hostname, parts.port or _SCHEME_DEFAULT_PORT.get((parts.scheme or "").lower()))


def _configured_authorities() -> Dict[Tuple[str, Optional[int]], str]:
    """从环境/配置取通知接收端的 **authority（主机 + 端口）**（path 特征之外的第二道判据）。

    ``为什么必须带端口``（2026-10-03 · 全量清点实测）：只比主机名时，
    `AGENT_API_URL=http://127.0.0.1:8080` 会让**任何** `127.0.0.1` 请求都被判成通知外发——
    实测 `http://127.0.0.1:9/api/embeddings`、`http://127.0.0.1:5001/api/stocks/resolve`
    都被误拦，整套测试里误伤 **58 个用例**。改为 (主机, 端口) 精确匹配后误伤归零。
    """
    authorities: Dict[Tuple[str, Optional[int]], str] = {}
    pairs = (
        ("AGENT_API_URL", "agent"),
        ("FEISHU_WEBHOOK_URL", "feishu"),
    )
    for env_key, sink in pairs:
        raw = os.environ.get(env_key)
        if not raw:
            try:  # 环境变量没设时退回 settings（惰性、失败不影响分类）
                from infrastructure.config.settings import get_settings

                raw = getattr(get_settings(), env_key.lower(), None)
            except Exception:  # noqa: BLE001
                raw = None
        if not raw:
            continue
        parts = urlsplit(str(raw))
        if parts.hostname:
            authorities[_authority(parts)] = sink
    return authorities


def classify(
    url: str,
    *,
    hosts: Optional[Dict[Tuple[str, Optional[int]], str]] = None,
) -> Optional[str]:
    """把 URL 分类到通知接收端：`'agent' | 'feishu' | 'wake' | None`（None = 与通知无关，放行）。

    判据顺序：**先路径特征**（最精确），**再 authority（主机 + 端口）精确匹配**。
    纯函数、零 IO，可直接单测。

    `hosts` 形如 `{("127.0.0.1", 8080): "agent"}`（可注入，便于单测）。
    """
    if not url:
        return None
    parts = urlsplit(str(url))
    path = parts.path or ""
    for marker, sink in PATH_MARKERS:
        if marker in path:
            return sink
    if path.rstrip("/") == WAKE_PATH_MARKER:
        return "wake"
    table = _configured_authorities() if hosts is None else hosts
    if parts.hostname:
        return table.get(_authority(parts))
    return None


class GuardHandle:
    """守卫句柄：安装/卸载包装器、记账、断言。"""

    def __init__(self, mode: str = DEFAULT_MODE) -> None:
        self.mode = mode
        self._attempts: List[NotifyAttempt] = []
        self._orig: Dict[str, Callable] = {}
        self._current_nodeid: Optional[str] = None
        self._installed = False

    # ── 生命周期 ──────────────────────────────────────────────────────────
    def install(self) -> "GuardHandle":
        """幂等安装：把全局 requests.post/get 换成按 URL 分类的包装器。"""
        if self._installed:
            return self
        import requests

        self._orig["post"] = requests.post
        self._orig["get"] = requests.get
        requests.post = self._wrap("post", self._orig["post"])
        requests.get = self._wrap("get", self._orig["get"])
        self._installed = True
        return self

    def uninstall(self) -> None:
        if not self._installed:
            return
        import requests

        for name, orig in self._orig.items():
            setattr(requests, name, orig)
        self._orig.clear()
        self._installed = False

    # ── 记账接口（设计契约，别改名：interfaces.md 已写死） ────────────────
    def attempts(self) -> List[NotifyAttempt]:
        return list(self._attempts)

    def intercepted(self) -> int:
        return len(self._attempts)

    def real_egress_count(self) -> int:
        """真正出网的通知请求数——拦截先于真实调用，故恒为 0。"""
        return sum(1 for a in self._attempts if a.egress)

    def offenders(self) -> List[str]:
        """发生过未声明外发的用例 nodeid（去重、排序）。"""
        return sorted({a.test_nodeid for a in self._attempts if a.test_nodeid})

    def set_current_test(self, nodeid: Optional[str]) -> None:
        self._current_nodeid = nodeid

    def attempts_for(self, nodeid: Optional[str]) -> List[NotifyAttempt]:
        return [a for a in self._attempts if a.test_nodeid == nodeid]

    def assert_no_real_egress(self) -> None:
        n = self.real_egress_count()
        if n:
            raise AssertionError(
                f"守卫记录到 {n} 次真实通知外发："
                + "; ".join(a.url for a in self._attempts if a.egress)
            )

    def failure_for(self, nodeid: Optional[str]) -> Optional[str]:
        """fail 模式下，某用例若发生未声明外发 → 返回失败信息（否则 None）。"""
        if self.mode != MODE_FAIL:
            return None
        hits = self.attempts_for(nodeid)
        if not hits:
            return None
        urls = "; ".join(f"{a.sink}: {a.method.upper()} {a.url}" for a in hits[:3])
        return (
            f"本用例发生真实通知外发 {len(hits)} 次（{urls}）——测试漏桩；"
            "请把桩打在实现所在模块"
            "（见 docs/requirements/REQ-261003150739-b98d/design/interfaces.md）"
        )

    def summary_line(self) -> str:
        return (
            f"notify-guard intercepted={self.intercepted()} "
            f"egress={self.real_egress_count()} offenders={self.offenders()}"
        )

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _wrap(self, method: str, original: Callable) -> Callable:
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            url = kwargs.get("url")
            if url is None and args:
                url = args[0]
            sink = classify(url) if isinstance(url, str) else None
            if sink is None:
                # 非通知接收端：完全透明地走真实实现（数据源/HTTP 客户端测试不受影响）
                return original(*args, **kwargs)
            self._attempts.append(
                NotifyAttempt(
                    ts=time.time(),
                    method=method,
                    url=str(url),
                    sink=sink,
                    test_nodeid=self._current_nodeid,
                )
            )
            return _SyntheticResponse()

        _wrapper.__name__ = f"guarded_requests_{method}"  # type: ignore[attr-defined]
        return _wrapper


#: 守卫生效时的单例；`install_notify_guard()` 反复调用返回同一个。
_HANDLE: Optional[GuardHandle] = None


def mode_from_env() -> str:
    raw = (os.environ.get(ENV_SWITCH) or "").strip().lower()
    if raw in (MODE_OFF, MODE_REPORT, MODE_FAIL):
        return raw
    return DEFAULT_MODE


def install_notify_guard(mode: Optional[str] = None) -> Optional[GuardHandle]:
    """按开关安装守卫。mode=`off` 时返回 None（完全不介入）。幂等。"""
    global _HANDLE
    resolved = mode or mode_from_env()
    if resolved == MODE_OFF:
        return None
    if _HANDLE is None:
        _HANDLE = GuardHandle(resolved)
    else:
        _HANDLE.mode = resolved
    return _HANDLE.install()


def current_handle() -> Optional[GuardHandle]:
    return _HANDLE


def reset_for_tests() -> None:
    """仅供单测：卸下包装器并清空记账与单例。"""
    global _HANDLE
    if _HANDLE is not None:
        _HANDLE.uninstall()
    _HANDLE = None
