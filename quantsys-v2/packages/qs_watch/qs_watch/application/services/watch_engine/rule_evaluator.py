"""规则取数保护器（RFC 014 v3 重构 P1，2026-09-14）

从 WatchEngine 剥出「20 日均量取数保护」：按日缓存 / 硬超时 / 连续失败熔断。

为什么独立：这是 2026-09-11 事故的修复（外部 K 线降级链离线时单 tick 实测
127s，把 60s 的 tick 拖成两分钟、10s 快档形同虚设）。它的分支最多（在途
future + 超时 + 熔断 + 失败 TTL），此前只能在引擎整体里间接验证。

⚠️ 职责边界：**EvalContext 组装仍在 WatchEngine._build_ctx**。原因不是分层
洁癖，而是既有测试（tests/e2e/test_watch_engine_flow_e2e.py）通过
engine._get_avg_volume = lambda ... 替换取数入口来隔离外部源；把取数调用
搬进本类会让该替换失效、测试语义漂移。故本类只做取数保护，入口仍由引擎转发。

行为等价：超时/熔断/TTL 的默认值与口径不变；时间由调用方注入（不持 now_fn）。
"""
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


class RuleEvaluator:
    """均量取数保护：取不到就快速放弃，绝不拖住 tick"""

    def __init__(self, avg_volume_provider: Optional[Callable[[str], Optional[float]]] = None,
                 timeout_sec: Optional[float] = None,
                 fail_ttl_sec: Optional[float] = None,
                 breaker_n: Optional[int] = None):
        self.avg_volume_provider = avg_volume_provider
        self._avg_volume_cache: Dict[str, float] = {}
        self._avg_volume_fail: Dict[str, datetime] = {}
        self._avg_volume_inflight: Dict[str, Any] = {}
        self._avg_volume_cache_date = None
        self._avg_volume_timeout_sec = (timeout_sec if timeout_sec is not None
                                        else float(os.getenv('WATCH_AVG_VOLUME_TIMEOUT_SEC', '1.0')))
        self._avg_volume_fail_ttl_sec = (fail_ttl_sec if fail_ttl_sec is not None
                                         else float(os.getenv('WATCH_AVG_VOLUME_FAIL_TTL_SEC', '600')))
        self._avg_volume_breaker_n = (breaker_n if breaker_n is not None
                                      else int(os.getenv('WATCH_AVG_VOLUME_BREAKER_N', '3')))
        self._avg_volume_consec_fail = 0
        self._avg_volume_blocked_until: Optional[datetime] = None
        self._avg_volume_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='avgvol')

    def reset_daily(self, now: datetime) -> None:
        """跨天清空均量缓存（原为引擎 _reset_daily_state_if_needed 的一部分）"""
        self._avg_volume_cache.clear()
        self._avg_volume_fail.clear()
        self._avg_volume_cache_date = now.date()

    def get_avg_volume(self, symbol: str, now: datetime) -> Optional[float]:
        """20 日均量：按日缓存 + 硬超时 + 失败熔断

        取不到就快速放弃（按"无均量"处理，相关条件当次跳过）；连续失败达阈值
        则整体熔断一段时间，避免每个标的都去撞同一堵墙。
        """
        if self.avg_volume_provider is None:
            return None
        if self._avg_volume_cache_date != now.date():
            self._avg_volume_cache.clear()
            self._avg_volume_fail.clear()
            self._avg_volume_cache_date = now.date()
        if self._avg_volume_blocked_until is not None and now < self._avg_volume_blocked_until:
            return None
        if symbol in self._avg_volume_cache:
            return self._avg_volume_cache[symbol]
        failed_at = self._avg_volume_fail.get(symbol)
        if failed_at is not None and (now - failed_at).total_seconds() < self._avg_volume_fail_ttl_sec:
            return None
        fut = self._avg_volume_inflight.get(symbol)
        if fut is None:
            fut = self._avg_volume_pool.submit(self.avg_volume_provider, symbol)
            self._avg_volume_inflight[symbol] = fut
        try:
            value = fut.result(timeout=self._avg_volume_timeout_sec)
        except FuturesTimeout:
            # 在途 future 保留：完成后再回收（下次命中即取到值），不每 tick 重新发起
            self.note_failure(symbol, now, '超时 %.1fs' % self._avg_volume_timeout_sec)
            return None
        except Exception as e:  # noqa: BLE001 - 任何取数异常都不该影响 tick
            self._avg_volume_inflight.pop(symbol, None)
            self.note_failure(symbol, now, str(e))
            return None
        self._avg_volume_inflight.pop(symbol, None)
        if value:
            self._avg_volume_cache[symbol] = float(value)
            self._avg_volume_consec_fail = 0
            return self._avg_volume_cache[symbol]
        self.note_failure(symbol, now, '空值')
        return None

    def note_failure(self, symbol: str, now: datetime, why: str) -> None:
        self._avg_volume_fail[symbol] = now
        self._avg_volume_consec_fail += 1
        if self._avg_volume_consec_fail >= self._avg_volume_breaker_n:
            self._avg_volume_blocked_until = now + timedelta(seconds=self._avg_volume_fail_ttl_sec)
            logger.warning('均量取数连续失败，熔断 %ds（期内按无均量处理）',
                           symbol=symbol, reason=why, ttl=self._avg_volume_fail_ttl_sec)
        else:
            logger.warning('均量取数失败（按无均量处理）', symbol=symbol, reason=why)
