"""盯盘 V2 定时任务 —— 只做编排，不重写业务（REQ-261022235419-2299）

职责边界（刻意的"薄"）：

    门（周末/节假日/非交易时段 → 返回 []，零取价零写库）
      → 查本档规则
      → 逐票取价
      → 调既有判定链（失效 → 分类 → 判定 → 投递前归档 → 路由投递）
      → 回写 notified，成功路由才提交循环计数
      → 触发循环固定快档；其余按距离重算 watch_rules.watch_tier

档位计算全部在 `tier.py`（纯函数）；本模块不实现任何判定/通知逻辑。

5 个任务（scheduler_tasks 由迁移 20261023_watch_rules_tier 播种）：
    watch_open_am   09:25  全部规则重算档位
    watch_open_pm   13:00  全部规则重算档位（午休后重新定档）
    watch_scan_30s  30 秒  本档=30  规则：判定 + 归档 + 重算档位
    watch_scan_10m  10 分钟 本档=600 规则
    watch_scan_30m  30 分钟 本档=1800 规则
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from qs_ops.application.jobs.job_protocol import Job, JobResult

from . import tier
from .engine import WatchEngineV2, create_engine_v2

logger = structlog.get_logger(__name__)


# ── 时段门 ────────────────────────────────────────────────────────────

def is_trading_day(now: Optional[datetime] = None) -> bool:
    """交易日判定（周末/节假日/未知一律 False = fail-closed）。"""
    from qs_ops.application.services.trading_day_guard import TradingDayGuard

    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    try:
        return bool(TradingDayGuard.is_trading_day(now.date()))
    except Exception:  # noqa: BLE001 - 判定器异常时宁可零事件，不要在未知日开火
        logger.error('v2.trading_day_guard_failed', at=now.isoformat())
        return False


def in_watch_window(now: Optional[datetime] = None) -> bool:
    """盯盘窗口：交易日 + 连续竞价（09:30–11:30 / 13:00–15:00）。

    周末、节假日、盘前、午休、盘后一律 False —— 调用方拿到 False 必须
    `return {'events': []}`，不取价、不写库。
    """
    from qs_trading.domain.trading.services.market_session_policy import (
        MarketSessionPolicy,
    )

    now = now or datetime.now()
    if not is_trading_day(now):
        return False
    phase = MarketSessionPolicy.phase_for(now.time(), is_trading_day=True)
    return bool(MarketSessionPolicy.is_market_open(phase))


# ── 依赖解析（生产实现；测试全部注入）──────────────────────────────────

_QUOTE_SERVICE = None


def _rule_repo():
    from ..core._repo_resolver import watch_rule_repo
    return watch_rule_repo()


def _trigger_repo():
    from ..core._repo_resolver import watch_trigger_repo
    return watch_trigger_repo()


def _quote_service():
    global _QUOTE_SERVICE
    if _QUOTE_SERVICE is None:
        from qs_market_data.application.services.realtime_quote_service_v2 import (
            RealtimeQuoteServiceV2,
        )
        _QUOTE_SERVICE = RealtimeQuoteServiceV2()
    return _QUOTE_SERVICE


def _build_engine(rule_repo, quote_service) -> WatchEngineV2:
    """判定引擎：未注入投递依赖时 = 影子（只判定，不投递）。"""
    return create_engine_v2(rule_repo=rule_repo, quote_service=quote_service)


def _fetch_quotes(symbols, quote_service) -> Dict[str, Any]:
    """逐票取价（行情服务暂无批量接口；本层单票失败只让该票失明）。"""
    quotes: Dict[str, Any] = {}
    for symbol in dict.fromkeys(s for s in symbols if s):
        try:
            quotes[symbol] = quote_service.get_realtime_quote(symbol)
        except Exception as exc:  # noqa: BLE001 - 单票故障不拖垮整批
            logger.warning('v2.quote_failed', symbol=symbol, error=str(exc))
            quotes[symbol] = None
    return quotes


def _current_tier(rule) -> int:
    """规则当前档位读口径：非法/缺列 → 默认档（保证首拍能扫到）。"""
    return tier.normalize_tier(getattr(rule, 'watch_tier', None)) or tier.DEFAULT_TIER


def _rules_of_tier(rule_repo, tier_sec: int) -> List[Any]:
    from .market_watch_service import MARKET_SCOPES
    return [rule for rule in (rule_repo.list_by_state('active') or [])
            if _current_tier(rule) == tier_sec
            and getattr(rule, 'scope', None) not in MARKET_SCOPES]


def _refresh_tiers(rule_repo, rules, quotes, outcomes=None, assessments=None) -> int:
    """触发循环固定快档；其余按条件评估距离或价格线距离定档。"""
    from . import router
    active_cycles = set()
    for outcome in outcomes or []:
        if not outcome or outcome[0] != 'trigger':
            continue
        rule, judgment, route, delivery = outcome[1], outcome[2], outcome[3], outcome[4]
        if (getattr(judgment, 'observe_only', False)
                or str(getattr(rule, 'trigger_channel', 'agent')) == 'direct'):
            continue
        completed = (route is not None and route.route == router.ROUTE_DIRECT
                     and route.cycle_count == router.CYCLE_LEN
                     and bool(getattr(delivery, 'delivered', False)))
        if not completed:
            active_cycles.add(getattr(rule, 'id', None))

    changed = 0
    for rule in rules:
        quote = quotes.get(getattr(rule, 'symbol', None))
        if quote is None:
            continue
        judgment = (assessments or {}).get(getattr(rule, 'id', None))
        if getattr(rule, 'id', None) in active_cycles:
            new_tier = tier.TIER_FAST
        elif judgment is not None and getattr(judgment, 'degraded', False):
            new_tier = _current_tier(rule)
        elif judgment is not None and getattr(judgment, 'distance_ratio', None) is not None:
            new_tier = tier.tier_of(judgment.distance_ratio * 100.0)
        else:
            new_tier = tier.tier_for(rule, getattr(quote, 'price', None),
                                     prev_close=getattr(quote, 'prev_close', None))
        if new_tier is None or new_tier == _current_tier(rule):
            continue
        try:
            rule_repo.update_fields(rule.id, watch_tier=new_tier)
            rule.watch_tier = new_tier
            changed += 1
        except Exception as exc:  # noqa: BLE001 - 单条失败不阻断其余
            logger.error('v2.tier_update_failed', rule_id=getattr(rule, 'id', None),
                         error=str(exc))
    return changed


# ── 归档（边沿触发：同条件持续为真只落一次，回落后重新武装）─────────────

def reset_latch() -> None:
    from . import archive
    archive.reset_latch()


def _archive(outcomes, rules, trigger_repo) -> int:
    """兼容既有调用；定时任务由 engine 在投递前后分别调用归档器。"""
    from .archive import TriggerArchive
    archiver = TriggerArchive(trigger_repo)
    for rule in rules:
        archiver.evaluated(rule)
    for outcome in outcomes or []:
        if not outcome or outcome[0] != 'trigger':
            continue
        _, rule, judgment = outcome[0], outcome[1], outcome[2]
        archiver.evaluated(rule)
        if archiver.before_delivery(rule, judgment):
            archiver.after_delivery(judgment, outcome[4] if len(outcome) > 4 else None)
    archiver.finish()
    return archiver.written


# ── 两个入口 ──────────────────────────────────────────────────────────

def open_scan(*, now: Optional[datetime] = None, rule_repo=None,
              quote_service=None) -> Dict[str, Any]:
    """开盘任务：全部 active 规则 → 取价 → 重算档位 → 回写（不判定、不投递）。"""
    now = now or datetime.now()
    if not is_trading_day(now):
        return {'events': [], 'skipped': 'not_trading_day'}

    repo = rule_repo or _rule_repo()
    from .market_watch_service import MARKET_SCOPES
    from .rule_policy import in_active_window
    rules = [rule for rule in (repo.list_by_state('active') or [])
             if getattr(rule, 'scope', None) not in MARKET_SCOPES
             and in_active_window(rule, now)]
    quotes = _fetch_quotes([r.symbol for r in rules],
                           quote_service or _quote_service())
    changed = _refresh_tiers(repo, rules, quotes)
    return {'events': [], 'scanned': len(rules), 'tier_changed': changed,
            'quotes': sum(1 for q in quotes.values() if q is not None)}


def scan(tier_sec: int, *, now: Optional[datetime] = None, rule_repo=None,
         quote_service=None, trigger_repo=None,
         engine: Optional[WatchEngineV2] = None) -> Dict[str, Any]:
    """档位任务：本档规则 → 取价 → 既有判定链 → 归档 → 重算档位。"""
    if tier_sec not in tier.VALID_TIERS:
        raise ValueError(f'非法档位: {tier_sec!r}（只允许 {tier.VALID_TIERS}）')

    now = now or datetime.now()
    if not in_watch_window(now):
        return {'events': [], 'skipped': 'outside_session'}

    import time
    started = time.monotonic()
    repo = rule_repo or _rule_repo()
    from .rule_policy import in_active_window
    rules = [rule for rule in _rules_of_tier(repo, tier_sec)
             if in_active_window(rule, now)]
    eng = engine or _build_engine(repo, quote_service or _quote_service())
    quotes = (_fetch_quotes([r.symbol for r in rules], quote_service or _quote_service())
              if rules else {})
    from . import router
    from .archive import TriggerArchive
    archiver = TriggerArchive(trigger_repo or _trigger_repo(), now=now)
    outcomes = []
    assessments = {}
    market = {'scanned': 0, 'triggered': 0, 'degraded': []}
    try:
        if tier_sec == tier.TIER_FAST and hasattr(eng, 'run_market_chain'):
            market = eng.run_market_chain(archive=archiver, now=now)
            outcomes.extend(market.pop('outcomes'))
        if rules:
            outcomes.extend(eng.run_chain(
                rules, quotes, archive=archiver, now=now, assessments=assessments))
    finally:
        archiver.finish()
        flush_state = getattr(eng, 'flush_state', None)
        if callable(flush_state):
            flush_state()

    delivery_failed = 0
    for outcome in outcomes:
        if outcome[0] == 'invalidation':
            delivery_failed += int(outcome[3] is not None
                                   and not getattr(outcome[3], 'delivered', False))
            continue
        route, delivery = outcome[3], outcome[4]
        if route is not None and route.route in (router.ROUTE_AGENT, router.ROUTE_DIRECT):
            skipped = bool(getattr(delivery, 'skipped', False))
            delivery_failed += int(not getattr(delivery, 'delivered', False) and not skipped)
    changed = _refresh_tiers(repo, rules, quotes, outcomes, assessments)
    degraded = sum(bool(getattr(judgment, 'degraded', False))
                   for judgment in assessments.values())
    degraded += len(market.get('degraded') or [])
    staged_pending = getattr(eng, 'staged_pending', lambda: 0)()
    return {'tier': tier_sec, 'scanned': len(rules), 'events': len(outcomes),
            'archived': archiver.written, 'tier_changed': changed,
            'delivery_failed': delivery_failed, 'archive_failed': archiver.failed,
            'quotes': sum(q is not None for q in quotes.values()),
            'degraded': degraded, 'staged_pending': staged_pending,
            'market_scanned': market.get('scanned', 0),
            'market_triggered': market.get('triggered', 0),
            'duration_ms': int((time.monotonic() - started) * 1000)}


# ── 定时任务对接（框架只认 Job；这里只做参数转发 + 结果包装）────────────

class _WatchJob(Job):
    """盯盘 V2 定时任务的公共包装（子类只声明 name 与 handler）。"""

    def __init__(self, engine: Optional[WatchEngineV2] = None):
        self._engine = engine

    @property
    def description(self) -> str:
        return '盯盘 V2 定时任务'

    @property
    def timeout_seconds(self) -> int:
        return 60

    def _run(self) -> Dict[str, Any]:  # 子类实现
        raise NotImplementedError

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            details = self._run()
            if details.get('skipped'):
                return JobResult.ok(self.name, message=f"skipped: {details['skipped']}",
                                    **details)
            if details.get('delivery_failed') or details.get('archive_failed'):
                error = (f"delivery_failed={details.get('delivery_failed', 0)}, "
                         f"archive_failed={details.get('archive_failed', 0)}")
                return JobResult.fail(self.name, error)
            return JobResult.ok(self.name, message='done', **details)
        except Exception as exc:  # noqa: BLE001 - 统一转 JobResult.fail
            logger.error('v2.scheduled_job_failed', job=self.name, error=str(exc))
            return JobResult.fail(self.name, str(exc))


class WatchOpenAmJob(_WatchJob):
    name = 'watch_open_am'
    description = '盯盘V2：上午开盘，全部规则重算档位'

    def _run(self):
        return open_scan()


class WatchOpenPmJob(_WatchJob):
    name = 'watch_open_pm'
    description = '盯盘V2：下午开盘，全部规则重算档位'

    def _run(self):
        return open_scan()


class WatchScanJob(_WatchJob):
    """三个档位任务共用一个类：档位由构造参数决定。"""

    def __init__(self, tier_sec: int, engine: Optional[WatchEngineV2] = None):
        super().__init__(engine)
        self._tier_sec = tier_sec

    @property
    def name(self) -> str:
        return {tier.TIER_FAST: 'watch_scan_30s',
                tier.TIER_MID: 'watch_scan_10m',
                tier.TIER_SLOW: 'watch_scan_30m'}[self._tier_sec]

    @property
    def description(self) -> str:
        return f'盯盘V2：{self._tier_sec}秒档规则判定'

    def _run(self):
        return scan(self._tier_sec, engine=self._engine)


def build_watch_v2_jobs(engine: Optional[WatchEngineV2] = None) -> List[Job]:
    """5 个 Job（供宿主 main.py 注册进 JobRegistry）。"""
    return [
        WatchOpenAmJob(engine),
        WatchOpenPmJob(engine),
        WatchScanJob(tier.TIER_FAST, engine),
        WatchScanJob(tier.TIER_MID, engine),
        WatchScanJob(tier.TIER_SLOW, engine),
    ]
