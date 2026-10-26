"""WatchEngine 装配：构建引擎 + 后台线程启动"""
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Mapping, Optional
from qs_kernel.domain.ports.datasource_ports import IDataProviderManager

import structlog

from qs_market_data.adapters.outbound.datasources.manager import get_data_provider_manager

from qs_agenthub.application.services.agent_notification_service import AgentNotificationService  # 2026-10-19：L1 → qs_agenthub 真身
from qs_market_data.application.services.realtime_quote_service_v2 import RealtimeQuoteServiceV2
from qs_watch.application.services.watch_engine.confirm_verify_pipeline import (
    ConfirmVerifyPipeline,
)
from qs_watch.application.services.watch_engine.engine import (
    WatchEngine, elapsed_trading_fraction,
)
from qs_watch.application.services.watch_engine.liquidity_check_service import (
    LiquidityCheckService,
)
from qs_watch.application.services.watch_engine.sector_resonance_service import (
    SectorResonanceService,
)
from qs_watch.application.services.watch_engine.notifier import WatchNotifier
from qs_watch.application.services.watch_engine.digest_service import WatchDigestService
from qs_watch.application.services.watch_engine.intervention_ledger import InterventionLedger

from qs_watch.application.services.watch_engine.meta_review_service import WatchMetaReviewService
from qs_watch.application.services.watch_engine.position_lifecycle_service import PositionLifecycleService
from qs_watch.application.services.watch_engine.market_watch_service import MarketWatchService
from qs_watch.application.services.watch_engine.held_sector_map import HeldSectorMapService
from qs_watch.application.services.watch_engine.outcome_backfill_service import OutcomeBackfillService
from qs_market_data.adapters.outbound.datasources.market_state_provider import MarketStateProvider

from qs_watch.application.services.watch_engine._repo_resolver import (
    news_alert_repo,
    news_source,
    pool_member_source,
    sim_position_repo,
    sim_repo,
    todo_repo,
    watch_digest_state_repo,
    watch_intervention_repo,
    watch_outcome_repo,
    watch_pool_binding_repo,
    watch_rule_repo,
    watch_trigger_repo,
)

logger = structlog.get_logger(__name__)


def make_avg_volume_provider():
    """近 20 日日均成交量 provider。失败返回 None（volume_surge 降级不判定）"""
    def provider(symbol: str) -> Optional[float]:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
        # 归一化为裸代码：akshare 只接受 6 位代码，DB miss 时 fallback 会失败
        bare_symbol = symbol.split('.')[0]
        result: IDataProviderManager = get_data_provider_manager().get_klines(bare_symbol, 'daily', start, end)
        if not result.get('success'):
            logger.warning('均量获取失败，volume_surge 降级', symbol=symbol)
            return None
        # data 为 List[KlineData] dataclass（非 dict），用属性访问；兼容 dict 兜底
        volumes = []
        for k in result['data'][-20:]:
            v = k.get('volume') if isinstance(k, dict) else getattr(k, 'volume', None)
            if v:
                volumes.append(v)
        if not volumes:
            logger.warning('均量获取失败，volume_surge 降级', symbol=symbol, reason='empty_volumes')
            return None
        return sum(volumes) / len(volumes)
    return provider


def make_fund_flow_provider():
    """近5日主力资金流向 provider（2026-10-20）：返回 {total_main_net_inflow_yi, days} 或 None。

    数据源 eastmoney 走代理偶发失败——失败返回 None（fund_flow 条件降级不判定），
    同 symbol 当日缓存（日内资金流向盘中会变，缓存到午夜）。
    """
    from qs_market_data.adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
    ds = FundFlowDataSource()
    cache: dict = {}

    def provider(symbol: str):
        from datetime import date
        bare = symbol.split('.')[0]
        key = (bare, date.today())
        if key in cache:
            return cache[key]
        try:
            r = ds.get_stock_fund_flow(bare, days=5)
            s = (r or {}).get('summary') or {}
            out = {
                'total_main_net_inflow_yi': round(float(s.get('total_main_net_inflow', 0)) / 1e8, 2),
                'consecutive_inflow_days': int(s.get('consecutive_inflow_days') or 0),
                'trend': s.get('trend'),
                'days': 5,
            }
        except Exception as e:  # noqa: BLE001 - 取数失败降级
            logger.warning('资金流向取数失败（fund_flow 条件降级）', symbol=bare, error=str(e))
            out = None
        cache[key] = out
        return out
    return provider


def make_kline_closes_provider():
    """日线收盘序列 provider（2026-10-20，ma_break/rsi 算料）：最近 ~130 根升序收盘。

    走白名单内 qs_market_data 的 DataProviderManager（DB→akshare 自动降级）；
    同 symbol 当日缓存。失败返回 None（条件降级不判定）。
    """
    from datetime import date, timedelta
    cache: dict = {}

    def provider(symbol: str):
        bare = symbol.split('.')[0]
        key = (bare, date.today())
        if key in cache:
            return cache[key]
        try:
            end = date.today().strftime('%Y-%m-%d')
            start = (date.today() - timedelta(days=240)).strftime('%Y-%m-%d')
            result = get_data_provider_manager().get_klines(bare, 'daily', start, end)
            if not result.get('success') or not result.get('data'):
                cache[key] = None
                return None
            closes = []
            for k in result['data'][-130:]:
                c = k.get('close') if isinstance(k, dict) else getattr(k, 'close', None)
                if c is not None:
                    closes.append(float(c))
            out = tuple(closes) if len(closes) >= 25 else None
        except Exception as e:  # noqa: BLE001
            logger.warning('日线收盘取数失败（MA/RSI 条件降级）', symbol=bare, error=str(e))
            out = None
        cache[key] = out
        return out
    return provider


def _build_pool_watch_service():
    """池级盯盘装配（2026-10-20）：绑定仓储 + 池成员来源 + 规则仓储。

    池表（stock_pools）归 qs_sourcing 领域——这里经 PoolMemberSource 只读访问
    （L1 暂留引用，登记在包 CLAUDE.md 边界清单）。
    """

    from qs_watch.application.services.watch_engine.pool_watch_service import PoolWatchService
    return PoolWatchService(
        watch_pool_binding_repo(), pool_member_source(), watch_rule_repo())


def _build_news_watch_service(bridge=None):
    """消息监控装配（2026-10-20）：新闻来源 + 已报留痕 + 持仓（盯盘适用三账户）。

    sender 走盯盘群回执通道；未注入时服务只留痕不发（可观测、测试友好）。
    """

    from qs_watch.application.services.watch_engine.news_watch_service import (
        NewsWatchService,
    )
    from qs_watch.application.services.watch_engine.watch_channels import (
        send_watch_receipt,
    )

    def _sender(payload):
        return send_watch_receipt(payload)

    return NewsWatchService(
        news_source=news_source(), alert_repo=news_alert_repo(),
        position_repo=sim_position_repo(),
        accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
        sender=_sender, bridge=bridge)


# ── 确认核验流水线装配（2026-10-20，机会闭环 M2）────────────────────────
#: 开关：生产默认启用；显式 false 回滚到「确认即入触发流水线」的旧路径。
#: 未启用 = pipeline=None，引擎行为与改造前完全一致（引擎侧已有回归用例）。
CONFIRM_VERIFY_ENABLED_ENV = 'WATCH_CONFIRM_VERIFY_ENABLED'

#: 流动性阈值：装配方的**显式生产默认**（env 可覆盖）。
#: 服务本身对「阈值未配置」保持 skipped（不猜默认值）；这里给默认值是因为
#: 生产不装配阈值等于该阶段永久不校验——那是「装了但没启用」的假装配。
DEFAULT_MIN_AMOUNT = 5_000_000.0        # 成交额下限 500 万
DEFAULT_MIN_VOLUME_RATIO = 1.0          # 量比下限 1.0
DEFAULT_TRAP_BIG_ORDER_RATIO = 0.4      # 大单占比 ≥ 40% 进入诱骗候选

MIN_AMOUNT_ENV = 'WATCH_CONFIRM_VERIFY_MIN_AMOUNT'
MIN_VOLUME_RATIO_ENV = 'WATCH_CONFIRM_VERIFY_MIN_VOLUME_RATIO'
TRAP_BIG_ORDER_RATIO_ENV = 'WATCH_CONFIRM_VERIFY_TRAP_BIG_ORDER_RATIO'

#: 候选池 id：给了就用 stock_pools 成员做板块映射候选集；
#: 没给则回退到「盯盘规则标的」候选集（生产最贴近的口径，不瞎猜某个池）。
SECTOR_RESONANCE_POOL_ENV = 'WATCH_SECTOR_RESONANCE_POOL_ID'

#: 板块映射重建线程：启动后先等一会（不抢宿主启动），之后按服务 TTL（默认 6h）重建；
#: 失败 5 分钟后重试。重建在独立 daemon 线程，tick 热路径只读快照。
RESONANCE_REFRESH_START_DELAY_SEC = 5.0
RESONANCE_REFRESH_FAIL_BACKOFF_SEC = 300.0

# ── 政策盯盘扫描线程（2026-10-21 政策盯盘闭环）────────────────────────────
#: 开关（缺省启用）：显式 false → 不起 daemon，引擎/其余旁路行为完全不变。
POLICY_WATCH_ENABLED_ENV = 'WATCH_POLICY_WATCH_ENABLED'
#: 扫描间隔（秒，缺省 5 分钟）；非法/过小值按默认或下限处理，不阻断装配。
POLICY_SCAN_INTERVAL_ENV = 'WATCH_POLICY_SCAN_INTERVAL_SEC'
DEFAULT_POLICY_SCAN_INTERVAL_SEC = 300.0
POLICY_SCAN_MIN_INTERVAL_SEC = 30.0
#: 启动后先等一会再扫（不抢宿主 lifespan）；扫描异常后 60s 重试（不按整轮间隔空等）。
POLICY_SCAN_START_DELAY_SEC = 15.0
POLICY_SCAN_FAIL_BACKOFF_SEC = 60.0
#: 线程名（运维/用例按名字识别；不要与 watch-engine 主循环混为一谈）
POLICY_SCAN_THREAD_NAME = 'watch-policy-scan'

#: `build_confirm_verify_pipeline` 的「未显式传 news_service」哨兵：
#: None 表示调用方明确说「消息服务不可用」，不能再偷偷重建一次。
_AUTO = object()


def _confirm_verify_enabled() -> bool:
    return os.getenv(CONFIRM_VERIFY_ENABLED_ENV, 'true').strip().lower() in (
        '1', 'true', 'yes', 'on')


def _env_positive_float(name: str, default: float) -> float:
    """读正数 env；缺省/非法/非正 → 用默认值并记日志（可诊断，不阻断装配）。"""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning('确认核验阈值配置非法，使用默认值', key=name,
                       value=str(raw), default=default)
        return default
    if value <= 0:
        logger.warning('确认核验阈值必须为正数，使用默认值', key=name,
                       value=value, default=default)
        return default
    return value


def _liquidity_thresholds_from_env() -> dict:
    return {
        'min_amount': _env_positive_float(MIN_AMOUNT_ENV, DEFAULT_MIN_AMOUNT),
        'min_volume_ratio': _env_positive_float(
            MIN_VOLUME_RATIO_ENV, DEFAULT_MIN_VOLUME_RATIO),
        'trap_big_order_ratio': _env_positive_float(
            TRAP_BIG_ORDER_RATIO_ENV, DEFAULT_TRAP_BIG_ORDER_RATIO),
    }


def _build_liquidity_check_service() -> LiquidityCheckService:
    """流动性核验服务：阈值来自 env（缺省用显式生产默认）。"""
    return LiquidityCheckService(_liquidity_thresholds_from_env())


class _WatchRuleCandidateSource:
    """盯盘规则标的 → 板块映射候选集（`SectorResonanceService` 端口实现）。

    「候选池」在盯盘语境里就是**正在盯的标的**：两段式伏击确认后要判断这次异动
    是不是板块共振，候选集天然是启用的规则标的。仓储**惰性构造**——装配流水线
    本身不碰数据库（宿主启动不被 DB 可用性阻塞），只有重建线程才读。
    """

    def __init__(self, rule_repo=None):
        self._rule_repo = rule_repo

    def get_members(self, pool_id=None):  # noqa: ARG002 - 端口签名，候选集与池 id 无关
        repo = self._rule_repo or watch_rule_repo()
        out = []
        for rule in (repo.list_enabled() or []):
            symbol = str(getattr(rule, 'symbol', '') or '').strip()
            if symbol:
                out.append({'symbol': symbol})
        return out


def _sector_resonance_pool_id() -> Optional[int]:
    raw = os.getenv(SECTOR_RESONANCE_POOL_ENV, '').strip()
    if not raw:
        return None
    try:
        pool_id = int(raw)
    except (TypeError, ValueError):
        logger.warning('WATCH_SECTOR_RESONANCE_POOL_ID 非法，回退到盯盘规则候选集',
                       value=raw)
        return None
    if pool_id <= 0:
        logger.warning('WATCH_SECTOR_RESONANCE_POOL_ID 必须为正整数，回退到盯盘规则候选集',
                       value=pool_id)
        return None
    return pool_id


def _build_sector_resonance_service() -> SectorResonanceService:
    """板块共振核验服务：显式池 id → stock_pools 成员；否则盯盘规则标的。"""
    pool_id = _sector_resonance_pool_id()
    if pool_id is not None:

        return SectorResonanceService(candidate_source=pool_member_source(),
                                      pool_id=pool_id)
    return SectorResonanceService(candidate_source=_WatchRuleCandidateSource(),
                                  pool_id=0)


def make_liquidity_quote_provider(avg_volume_provider=None,
                                  now_fn: Callable[[], datetime] = datetime.now):
    """引擎轻量 quote → 流动性核验所需盘口视图（成交额/量比）。

    引擎 `QuoteData` 有 amount/volume；量比不可直接取，按「当日成交量 ÷ 同期均量」
    折算（与 volume_surge 同口径：20 日均量 × 已过交易时间比例）。均量按
    (标的, 日期) 缓存，单次确认最多一次 K 线取数；取数失败 → 不填量比，
    由服务如实 skipped（fail-open）。

    `big_order_ratio` 当前行情源没有该字段，**不臆造**：quote 自带才透传，
    否则留给服务按「数据不足」跳过——宁可少一道判定，不可伪造盘口结论。
    """
    cache: dict = {}

    def _avg_volume(bare: str, day) -> Optional[float]:
        key = (bare, day)
        if key not in cache:
            try:
                avg = avg_volume_provider(bare) if avg_volume_provider else None
                cache[key] = float(avg) if avg else None
            except Exception as e:  # noqa: BLE001 - 取数失败降级为不填量比
                logger.warning('流动性核验均量取数失败（量比降级）', symbol=bare,
                               error=str(e))
                cache[key] = None
        return cache[key]

    def provider(symbol: str, quote: Any) -> dict:
        bare = str(symbol or '').split('.')[0]
        now = now_fn()
        payload = {'symbol': bare}

        def _get(*names):
            for name in names:
                if isinstance(quote, Mapping):
                    value = quote.get(name)
                else:
                    value = getattr(quote, name, None)
                if value is not None:
                    return value
            return None

        amount = _get('amount', 'turnover')
        if amount is not None:
            try:
                if float(amount) > 0:
                    payload['amount'] = float(amount)
            except (TypeError, ValueError):
                pass

        big_order = _get('big_order_ratio', 'large_order_ratio', 'big_order_pct')
        if big_order is not None:
            try:
                payload['big_order_ratio'] = float(big_order)
            except (TypeError, ValueError):
                pass

        volume_ratio = _get('volume_ratio', 'vol_ratio')
        if volume_ratio is not None:
            try:
                if float(volume_ratio) > 0:
                    payload['volume_ratio'] = float(volume_ratio)
            except (TypeError, ValueError):
                pass
        else:
            volume = _get('volume')
            avg = _avg_volume(bare, now.date()) if volume else None
            if avg and avg > 0:
                baseline = avg * min(1.0, max(elapsed_trading_fraction(now), 0.01))
                try:
                    payload['volume_ratio'] = float(volume) / baseline
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
        return payload

    return provider


def build_confirm_verify_pipeline(news_service=_AUTO, avg_volume_provider=None):
    """装配确认核验流水线（news/liquidity/sector 三服务 + ConfirmVerifyPipeline）。

    返回：
      · 正常 → `ConfirmVerifyPipeline`（生产装配，引擎在 staged_break 确认后调用）；
      · 开关关闭 → None（未装配路径，引擎行为与改造前一致）；
      · 任一服务装配失败 → None + error 日志（带 stage/error，引擎照常启动）。

    这里的「失败降级为 None」是刻意的：核验是旁路，装不上就不装，
    绝不让宿主启动被一个旁路服务拖死；日志必须能定位是哪一段、什么错。
    """
    if not _confirm_verify_enabled():
        logger.info('确认核验流水线未启用（%s=false）——staged 确认即入触发流水线'
                    % CONFIRM_VERIFY_ENABLED_ENV)
        return None

    stage = 'news'
    try:
        if news_service is _AUTO:
            news_service = _build_news_watch_service()
        if news_service is None:
            raise RuntimeError('消息监控服务缺失（NewsWatchService 不可用）')

        stage = 'liquidity'
        liquidity_service = _build_liquidity_check_service()

        stage = 'sector'
        resonance_service = _build_sector_resonance_service()

        stage = 'pipeline'
        pipeline = ConfirmVerifyPipeline(
            news_service=news_service,
            liquidity_service=liquidity_service,
            resonance_service=resonance_service,
            liquidity_quote_provider=make_liquidity_quote_provider(
                avg_volume_provider),
        )
    except Exception as e:  # noqa: BLE001 - 旁路装配失败降级，不阻断引擎启动
        logger.error(
            '确认核验流水线装配失败（%s），降级为未装配（引擎照常启动）'
            % stage, stage=stage, error=str(e))
        return None

    thresholds = liquidity_service.thresholds
    logger.info(
        '确认核验流水线已装配（news/liquidity/sector 三服务就位）',
        min_amount=thresholds.min_amount,
        min_volume_ratio=thresholds.min_volume_ratio,
        trap_big_order_ratio=thresholds.trap_big_order_ratio,
        resonance_pool=_sector_resonance_pool_id(),
    )
    return pipeline


def _start_sector_resonance_refresher(pipeline) -> Optional[threading.Thread]:
    """独立 daemon 线程重建板块映射（6h TTL / 失败 5 分钟重试）。

    为什么不在 tick/确认热路径：重建要逐板块取成分（最多 120 个板块的外呼），
    放热路径会拖慢引擎主循环。线程只读写服务自己的快照，与引擎生命周期解耦；
    重建失败只记日志——共振阶段按 fail-open 跳过，不拦信号。
    """
    service = getattr(pipeline, 'resonance_service', None)
    refresh = getattr(service, 'refresh', None)
    if not callable(refresh):
        return None
    interval = float(getattr(service, '_ttl', 6 * 3600) or 6 * 3600)

    def _loop():
        threading.Event().wait(min(RESONANCE_REFRESH_START_DELAY_SEC, interval))
        while True:
            delay = interval
            try:
                out = refresh()
                if isinstance(out, Mapping) and out.get('built'):
                    logger.info('候选池板块映射已重建（共振阶段可用）',
                                mapped=out.get('mapped'),
                                sectors=out.get('sectors_scanned'))
                else:
                    logger.info('候选池板块映射未重建（共振阶段 fail-open 跳过）',
                                detail=out)
            except Exception as e:  # noqa: BLE001 - 重建失败只降级，不拦信号
                logger.error('候选池板块映射重建失败（共振阶段 fail-open，稍后重试）',
                             error=str(e))
                delay = RESONANCE_REFRESH_FAIL_BACKOFF_SEC
            finally:
                # 会话收尾（2026-10-21, w-6224baac）：后台线程每轮归还 scoped session
                # ——否则连接 idle in transaction ~300s 被 PG 强杀，session_guard 报
                # session_leak_detected（error_events 3267a4ad / a6780ec3）。
                # 与 engine.tick 主循环同一约定。
                try:
                    from qs_kernel.infrastructure.persistence.orm import close_session
                    close_session()
                except Exception:
                    pass
            threading.Event().wait(delay)

    thread = threading.Thread(target=_loop, name='watch-sector-resonance',
                              daemon=True)
    thread.start()
    logger.info('候选池板块映射重建线程已启动（daemon）', interval_sec=interval)
    return thread


# ── 政策盯盘扫描装配（2026-10-21）──────────────────────────────────────
def _policy_watch_enabled() -> bool:
    return os.getenv(POLICY_WATCH_ENABLED_ENV, 'true').strip().lower() in (
        '1', 'true', 'yes', 'on')


def _policy_scan_interval() -> float:
    """扫描间隔（秒）：缺省 5 分钟；非法值用默认；过小值抬到下限并告警。"""
    raw = os.getenv(POLICY_SCAN_INTERVAL_ENV)
    if raw is None or not str(raw).strip():
        return DEFAULT_POLICY_SCAN_INTERVAL_SEC
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning('政策盯盘扫描间隔配置非法，使用默认值',
                       key=POLICY_SCAN_INTERVAL_ENV, value=str(raw),
                       default=DEFAULT_POLICY_SCAN_INTERVAL_SEC)
        return DEFAULT_POLICY_SCAN_INTERVAL_SEC
    if value <= 0:
        logger.warning('政策盯盘扫描间隔必须为正数，使用默认值',
                       key=POLICY_SCAN_INTERVAL_ENV, value=value,
                       default=DEFAULT_POLICY_SCAN_INTERVAL_SEC)
        return DEFAULT_POLICY_SCAN_INTERVAL_SEC
    if value < POLICY_SCAN_MIN_INTERVAL_SEC:
        logger.warning('政策盯盘扫描间隔过小，抬到下限',
                       key=POLICY_SCAN_INTERVAL_ENV, value=value,
                       min=POLICY_SCAN_MIN_INTERVAL_SEC)
        return POLICY_SCAN_MIN_INTERVAL_SEC
    return value


def build_policy_watch_service(news_service=_AUTO, bridge=None):
    """装配政策盯盘路由服务（2026-10-21）。

    · 新闻来源：`PolicyNewsSource`（全市场财经新闻，ADR-001 只走统一数据访问层）；
    · 板块→成分：服务内 `SectorConstituentIndex`（复用 sector_resonance_service 的
      板块适配与 `policy_lexicon` 的板块别名口径，**不维护第二份**）；
    · 持仓：三账户（与新闻监控/持仓板块映射同一口径）；
    · 候选池：**复用**共振核验的候选集口径（`WATCH_SECTOR_RESONANCE_POOL_ID` →
      stock_pools 成员；未配置 → 盯盘规则标的），不另立第二个「候选池」定义；
    · 确认核验查询：`NewsWatchService.scan_candidates`（候选池只读口径，不发卡）；
    · 发卡：`watch_channels.send_watch_receipt`（既有 P0/P2 路由）。

    返回 None = 开关关闭或装配失败（daemon 不起；引擎与其余旁路行为不变）。
    任何装配异常都降级记日志，**绝不阻断宿主启动**。
    """
    if not _policy_watch_enabled():
        logger.info('政策盯盘扫描未启用（%s=false）' % POLICY_WATCH_ENABLED_ENV)
        return None

    stage = 'import'
    try:
        from qs_watch.application.services.watch_engine.policy_news_source import (
            PolicyNewsSource,
        )
        from qs_watch.application.services.watch_engine.policy_watch_service import (
            PolicyWatchService,
        )
        from qs_watch.application.services.watch_engine.watch_channels import (
            send_watch_receipt,
        )

        stage = 'news_source'
        source = PolicyNewsSource()

        stage = 'candidates'
        pool_id = _sector_resonance_pool_id()
        if pool_id is not None:
            candidate_source = pool_member_source()
        else:
            candidate_source = _WatchRuleCandidateSource()

        stage = 'news_service'
        if news_service is _AUTO:
            try:
                news_service = _build_news_watch_service()
            except Exception as e:  # noqa: BLE001 - 只降级「候选池确认核验」这一段
                logger.error('政策盯盘确认核验查询装配失败（候选池命中将标注未核验，'
                             '持仓 P0/P2 路由不受影响）', error=str(e))
                news_service = None

        stage = 'service'
        service = PolicyWatchService(
            news_source=source,
            position_repo=sim_position_repo(),
            accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
            candidate_source=candidate_source,
            candidate_pool_id=pool_id or 0,
            alert_repo=news_alert_repo(),
            news_service=news_service,
            sender=send_watch_receipt,
            bridge=bridge,
        )
    except Exception as e:  # noqa: BLE001 - 旁路装配失败降级，不阻断宿主启动
        logger.error('政策盯盘扫描装配失败，降级为不启动（引擎照常运行）',
                     stage=stage, error=str(e))
        return None

    logger.info('政策盯盘扫描已装配（政策新闻 → 板块 → 持仓 P0/P2 / 候选池确认核验）',
                candidate_pool=(pool_id if pool_id is not None else 'watch_rules'),
                interval_sec=_policy_scan_interval())
    return service


def start_policy_watch_scanner(engine=None, stop_event=None, service=None):
    """起独立 daemon 扫描线程（与引擎主循环解耦，**不动 engine**）。

    Args:
        engine: 可选引擎实例——只读 `engine.news_watch_service` 复用同一份消息服务
            （候选池确认核验查询口），不改引擎的构造/生命周期。
        stop_event: 可选停止信号（测试用；生产靠进程退出 daemon 自动结束）。
        service: 可选已装配服务（测试注入）。

    Returns:
        (service, thread)；开关关闭/装配失败 → (None, None)（不会抛）。
    """
    if service is None:
        service = build_policy_watch_service(
            bridge=getattr(engine, 'news_todo_bridge', None),
            news_service=(getattr(engine, 'news_watch_service', None)
                          if engine is not None else _AUTO))
    if service is None:
        return None, None
    interval = _policy_scan_interval()

    def _stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    def _wait(seconds: float) -> None:
        if stop_event is not None:
            stop_event.wait(seconds)
        else:
            threading.Event().wait(seconds)

    def _loop():
        # 先等一会再扫：宿主启动期（lifespan 里其它 bootstrap）不抢 I/O。
        _wait(min(POLICY_SCAN_START_DELAY_SEC, interval))
        while not _stopped():
            delay = interval
            try:
                out = service.scan()
                if isinstance(out, Mapping) and out.get('skipped'):
                    logger.warning('政策盯盘扫描未完成（fail-open，非「无利空」）',
                                   reason=out.get('reason'))
                else:
                    detail = out if isinstance(out, Mapping) else {}
                    logger.info(
                        '政策盯盘扫描轮次完成',
                        records=detail.get('records'),
                        alerts=len(detail.get('alerts') or ()),
                        confirm=(detail.get('confirm') or {}).get('queried'),
                        unrelated=detail.get('unrelated'),
                        mapping_missing=detail.get('mapping_missing'))
            except Exception as e:  # noqa: BLE001 - 扫描异常只降级，不杀线程
                logger.error('政策盯盘扫描异常（下轮重试）', error=str(e))
                delay = POLICY_SCAN_FAIL_BACKOFF_SEC
            finally:
                # 会话收尾（与引擎主循环/共振重建线程同一约定）：后台线程每轮归还
                # scoped session，否则连接 idle in transaction 会被 PG 强杀。
                try:
                    from qs_kernel.infrastructure.persistence.orm import close_session
                    close_session()
                except Exception:
                    pass
            _wait(delay)
        logger.info('政策盯盘扫描线程已停止')

    thread = threading.Thread(target=_loop, name=POLICY_SCAN_THREAD_NAME,
                              daemon=True)
    thread.start()
    logger.info('政策盯盘扫描线程已启动（daemon）', interval_sec=interval)
    return service, thread


def build_watch_loop_services():
    """按开关装配闭环服务（REQ-c9f899 t12 §6-项8）——**可单测的纯装配决策**。

    返回 (runtime_store, todo_service, receipt_service, sla_job, self_heal_service)。
    默认全关（WATCH_TODO_ENABLED=false / WATCH_SELF_HEAL_ENABLED=false /
    WATCH_RUNTIME_PERSIST_ENABLED=false）→ 全 None，引擎行为与改造前**一致**。
    与进程外定时任务共用同一份 watch_loop_wiring 装配函数，避免两条真相。
    任一装配异常都降级（回旧路径/内存态）并记日志，绝不阻断引擎启动。
    """
    from qs_watch.application.services.watch_engine import watch_loop_wiring as _wiring

    runtime_store = None
    if _wiring.watch_runtime_persist_enabled():
        try:
            runtime_store = _wiring.build_runtime_store()
            logger.info('运行态持久化已显式装配（WATCH_RUNTIME_PERSIST_ENABLED=true）')
        except Exception as e:  # noqa: BLE001 - 装配失败降级为内存态，不阻断启动
            logger.error('运行态持久化装配失败，降级为内存态（冷却重启会丢）', error=str(e))
            runtime_store = None

    todo_service = receipt_service = sla_job = self_heal_service = None
    if _wiring.watch_todo_enabled():
        try:
            todo_service = _wiring.build_todo_service()
            receipt_service = _wiring.build_receipt_service()
            sla_job = _wiring.build_sla_job(receipt_service=receipt_service)
            logger.info('盯盘闭环已装配（WATCH_TODO_ENABLED=true）')
        except Exception as e:  # noqa: BLE001 - 装配失败回旧路径（不建待办），不阻断启动
            logger.error('盯盘闭环装配失败，降级为旧路径（不建待办）', error=str(e))
            todo_service = receipt_service = sla_job = None
        if todo_service is not None and _wiring.watch_self_heal_enabled():
            try:
                self_heal_service = _wiring.build_self_heal_service(todo_service)
                logger.info('规则自愈已装配（WATCH_SELF_HEAL_ENABLED=true）')
            except Exception as e:  # noqa: BLE001
                logger.error('规则自愈装配失败（抑噪/修复不可用）', error=str(e))
                self_heal_service = None

    return runtime_store, todo_service, receipt_service, sla_job, self_heal_service


def create_watch_engine() -> WatchEngine:
    _pos_repo = sim_position_repo()
    _sim_repo = sim_repo()   # 复用单例：原实现在闭包内每次调用新建（每 tick 每规则一次）
    # 均量 provider 只建一次：引擎 volume_surge 与确认核验的「量比」共用同一取数口径
    # （同一份 20 日均量，不另造第二套算法）。
    _avg_volume_provider = make_avg_volume_provider()

    def position_value_provider(rule):
        # 介入判据金额门：持仓级动作影响金额 = 该标的持仓市值
        # 2026-09-13（w-c8cae280，独立审阅 M4）：无归属账户的规则不再借用 agent_virtual 的持仓
        # —— 那会让『通用观察』规则按别人的持仓市值过金额门；无账户即跳过该门（返回 None）。
        account = getattr(rule, 'account', None)
        if not account:
            return None
        symbol = str(getattr(rule, 'symbol', '')).split('.')[0]
        try:
            pos = _pos_repo.get_position(account, symbol)
            if pos is None:
                return None
            return float(getattr(pos, 'market_value', 0) or 0)
        except Exception:
            return None

    def account_total_provider(rule=None):
        # 介入判据金额门：账户总资产
        # 2026-09-13（w-c8cae280，独立审阅 M4）：原实现恒用 agent_virtual 的总资产当所有规则的门槛。
        # 现优先用规则归属账户；无归属时用 agent-dh 自有账户（可用 WATCH_ENGINE_DEFAULT_ACCOUNT 覆盖）。
        account = (getattr(rule, 'account', None) if rule is not None else None) \
            or os.getenv('WATCH_ENGINE_DEFAULT_ACCOUNT', 'agent_brain')
        try:
            status = _sim_repo.get_account_status(account)
            if isinstance(status, dict):
                return float(status.get('total_value') or 0) or None
            return float(getattr(status, 'total_value', 0) or 0) or None
        except Exception:
            return None

    # 通知器：金额门取数复用**同一个** account_total_provider（REQ-c9f899 t12 §6-项2，
    # 勿另造第二份账户取数口径；缺数据时 provider 返回 None → 金额门关闭，不抛错）。
    # 标的名解析走 StockNameResolver 端口（与 SLA 巡检同一实现，单一取数口径）；
    # 装配失败降级 None → notifier 回退旧直连路径（名称是渲染增益，不阻断启动）。
    try:
        from qs_watch.application.services.watch_engine import watch_loop_wiring as _w
        _name_resolver = _w.build_name_resolver()
    except Exception:  # noqa: BLE001
        _name_resolver = None
    notifier = WatchNotifier(
        trigger_repo=watch_trigger_repo(),
        account_total_provider=account_total_provider,
        name_resolver=_name_resolver,
    )

    _market_watch = MarketWatchService(
        rule_repo=watch_rule_repo(),
        trigger_repo=watch_trigger_repo(),
        state_provider=MarketStateProvider(),
        # P2 市场环境联动（2026-10-19）：持仓→板块映射，账户口径与 P5 生命周期一致
        # （agent 三账户；v13/v14 传统量化策略自有日检闭环，不进盯盘联动）。
        # 每日重建由引擎 sidecar 驱动（refresh_held_boards），tick 只读缓存。
        held_sector_map=HeldSectorMapService(
            position_repo=sim_position_repo(),
            accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
        ),
    )

    # 摘要门（REQ-f08def P2/P4）：唤醒走 AgentNotificationService → POST /wake（官方通道）。
    #
    # ⚠️ 默认关闭，必须显式 WATCH_DIGEST_ENABLED=true 才生效（2026-09-11 w-c8cae280）。
    # 原因不是技术：摘要门一旦运行会真的唤醒 agent 去处置待处置触发，而这些触发里
    # 含真实买卖预案（如 300750「下破333=挂单建仓≤10%」）→ 可能产生真实委托。
    # 按 RFC 014 v3 §3.4（L3 交接态）：替用户决定下单是越权，故默认关，等明确授权。
    import os as _os
    if _os.getenv('WATCH_DIGEST_ENABLED', 'false').lower() == 'true':
        digest_service = WatchDigestService(
            trigger_repo=watch_trigger_repo(),
            rule_repo=watch_rule_repo(),
            agent_service=AgentNotificationService(
                # 唤醒是 fire-and-forget：agent 离线时绝不能用默认 300s 超时（AGENT_TIMEOUT）
                # 把引擎主循环卡死——2026-10-16 实测每轮循环被卡 ~5 分钟，心跳周期性
                # 「丢失」误报。10s 足够局域网唤醒投递；失败按原路径留痕下轮重试。
                timeout=int(os.getenv('WATCH_DIGEST_WAKE_TIMEOUT_SEC', '10'))),
            state_repo=watch_digest_state_repo(),   # 端口实现（ADR-001：SQL 只在适配器层）
            market_watch_service=_market_watch,        # 摘要内嵌市场状态（P6）
            # 影子模式默认**开**（fail-safe）：只写日志不发唤醒；显式 WATCH_DIGEST_DRY_RUN=false
            # 才是真开（会叫 agent 处置，agent 自有账户可自主下单）。
            dry_run=_os.getenv('WATCH_DIGEST_DRY_RUN', 'true').lower() != 'false',
        )
    else:
        digest_service = None
        import structlog as _structlog
        _structlog.get_logger(__name__).info(
            '摘要门未启用（WATCH_DIGEST_ENABLED != true）—— 触发照常落库归档，但不唤醒 agent')

    # 闭环装配（REQ-c9f899 t12 §6-项8）：默认全关 → 全 None（行为与改造前一致）
    runtime_store, todo_service, receipt_service, sla_job, self_heal_service = \
        build_watch_loop_services()

    # 消息 → P1 待办桥（FR-3）：todo_service 存在才装配；失败降级为只发卡。
    news_todo_bridge = None
    if todo_service is not None:
        try:
            from qs_watch.application.services.watch_engine.news_todo_bridge import (
                NewsTodoBridge,
            )
            news_todo_bridge = NewsTodoBridge(todo_service, todo_repo=todo_repo())
        except Exception as e:  # noqa: BLE001 - 桥是增益，不阻断引擎启动
            logger.error('消息待办桥装配失败，降级为只发卡', error=str(e))

    # 消息监控服务：引擎 sidecar 的持仓消息扫描与确认核验的「利空核验」共用**同一实例**
    # （同一条新闻源/留痕口径，不建两份）。装配失败只降级（扫描/利空核验不可用），
    # 不阻断引擎启动——消息面是旁路增益，不是引擎存活的必要条件。
    try:
        # 只在桥存在时传参：既保持 monkeypatch 无参口径兼容，也不让 None 影响旧行为
        _news_watch_service = (
            _build_news_watch_service(bridge=news_todo_bridge)
            if news_todo_bridge is not None else _build_news_watch_service())
    except Exception as e:  # noqa: BLE001 - 装配失败降级为关闭
        logger.error('消息监控服务装配失败，降级为关闭（消息扫描/利空核验不可用）',
                     error=str(e))
        _news_watch_service = None

    # 确认核验流水线（2026-10-20，机会闭环 M2）：生产默认装配；未装配 = None，
    # 引擎行为与改造前一致。装配失败只降级并记日志，绝不阻断引擎启动。
    if _news_watch_service is None:
        _confirm_verify_pipeline = None
        if _confirm_verify_enabled():
            logger.error(
                '确认核验流水线装配失败（news），降级为未装配（引擎照常启动）',
                stage='news', error='消息监控服务缺失（NewsWatchService 不可用）')
    else:
        _confirm_verify_pipeline = build_confirm_verify_pipeline(
            news_service=_news_watch_service,
            avg_volume_provider=_avg_volume_provider,
        )

    engine = WatchEngine(
        rule_repo=watch_rule_repo(),
        quote_service=RealtimeQuoteServiceV2(),
        notifier=notifier,
        avg_volume_provider=_avg_volume_provider,
        fund_flow_provider=make_fund_flow_provider(),
        kline_closes_provider=make_kline_closes_provider(),
        position_value_provider=position_value_provider,
        account_total_provider=account_total_provider,
        digest_service=digest_service,
        # P4 介入记账：预算计数落库；P7 元触发复核：规则健康度回到 agent
        ledger=InterventionLedger(watch_intervention_repo()),
        meta_review_service=WatchMetaReviewService(
            rule_repo=watch_rule_repo(),
            trigger_repo=watch_trigger_repo(),
        ),
        # P5 持仓生命周期联动：规则使命跟着交易走
        pool_watch_service=_build_pool_watch_service(),
        news_watch_service=_news_watch_service,
        # 确认核验流水线（2026-10-20，机会闭环 M2）：staged_break 确认后跑
        # 利空/流动性/板块共振三道；None = 未装配（回滚/装配失败），行为不变。
        confirm_verify_pipeline=_confirm_verify_pipeline,
        position_lifecycle_service=PositionLifecycleService(
            rule_repo=watch_rule_repo(),
            position_repo=sim_position_repo(),
            # 2026-10-19 修正：此前默认只盯 agent_virtual——user_main（用户真身）与
            # agent_brain 的持仓联动（清仓收摊/补挂止损/阶段推进/成本同步）从不执行，
            # 是 #128 徐工止损规则触发后永远挂着的结构性根因。
            accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
        ),
        # P6 市场级盯盘：取数走 IMarketStateProvider 端口，实现是 MarketStateProvider 适配器
        market_watch_service=_market_watch,
        # 闭环装配（REQ-c9f899 t12）：默认 None → 行为与改造前一致。
        # 2026-10-19：receipt_service/sla_job/self_heal_service 不再注入引擎
        # （死注入已清——SLA/回执在 inbound 定时任务侧，自愈由 interval job 调起），
        # 它们仍由 build_watch_loop_services 装配供 wiring/定时任务使用。
        runtime_state_store=runtime_store,
        todo_service=todo_service,
        # 观察聚合缓冲（REQ-261016155500-4f2a wt:validate:1）：无判据 observe 15min 合屏
        observe_agg=_build_observe_aggregator(),
        # P3 预判验证闭环（2026-10-20）：走势回填，sidecar 每日一次；
        # 取数走 qs_market_data 单例（服务内惰性取），仓储 L1 暂留同其它 watch 仓储。
        outcome_backfill_service=OutcomeBackfillService(
            outcome_repo=watch_outcome_repo()),
    )

    # 供政策扫描线程复用同一座桥（避免各建一份、各算一套去重）
    engine.news_todo_bridge = news_todo_bridge

    # 成交回执闭环接线（RFC 017 §2.1.4，2026-10-21）：trading 成交落库后回调 watch
    # 收敛执行待办（trigger handled + 规则退役 + position_state 翻转 + 时延落 detail）。
    # 组合根职责：未注册 = 回调 no-op（行为与改造前一致）；装配失败只降级记日志，
    # 绝不阻断引擎启动（成交照常落库，回执缺失可从事后巡检发现）。
    _register_fill_sync_listener(engine, todo_service)
    return engine


def _register_fill_sync_listener(engine, todo_service) -> None:
    """把 FillSyncService 注册为 trading 的成交监听（IFillListener 组合根装配）。

    任何装配异常只降级：成交路径不依赖回执，注册失败 = 未装配的旧行为。
    """
    try:
        from application.trading.paper_trading_engine import register_fill_listener
        from qs_watch.application.services.watch_engine.fill_sync_service import (
            FillSyncService,
        )

        listener = FillSyncService(
            rule_repo=engine.rule_repo,
            todo_service=todo_service,
            todo_repo=todo_repo(),
            trigger_repo=watch_trigger_repo(),
            position_repo=sim_position_repo(),
            lifecycle=getattr(engine, 'position_lifecycle_service', None),
            plan_progress=_plan_progress_port(),
        )
        register_fill_listener(listener)
        logger.info('成交回执同步已装配（IFillListener → FillSyncService）')
    except Exception as e:  # noqa: BLE001 - 回执是增益链路，不阻断引擎启动
        logger.error('成交回执同步装配失败，降级为未装配（成交照常落库）',
                     error=str(e))


def _plan_progress_port():
    """计划推进端口（REQ-261021222905-6dff）：装配失败 = None（回执行为不变）。"""
    try:
        from adapters.outbound.repositories.plan_progress_port import PlanProgressPort
        return PlanProgressPort()
    except Exception as e:  # noqa: BLE001
        logger.error('计划推进端口装配失败，回执不推进计划（成交照常）', error=str(e))
        return None


def _build_observe_aggregator():
    """观察聚合缓冲装配：发送走盯盘群回执通道（watch_symbol 频道）。

    开关 WATCH_OBSERVE_AGG（默认开）；关闭时返回 None = 引擎完全退回即时单发。
    """
    from qs_watch.application.services.watch_engine.observe_aggregator import (
        OBSERVE_AGG_ENABLED, ObserveAggregator,
    )
    if not OBSERVE_AGG_ENABLED:
        return None

    def _sender(title: str, content: str) -> bool:
        from qs_watch.application.services.watch_engine.watch_channels import send_watch_receipt
        return send_watch_receipt({
            'kind': 'observe_digest',    # 聚合卡专用 kind（非三段回执语义，不落 receipts 表）
            'os_channel': 'watch_symbol',
            'message': '%s\n%s' % (title, content),
        })

    return ObserveAggregator(sender=_sender)


def start_watch_engine_in_thread() -> tuple[WatchEngine, threading.Thread]:
    """daemon 线程启动引擎，随主进程退出。返回 (engine, thread) 供调用方留存句柄优雅停止"""
    engine = create_watch_engine()
    thread = threading.Thread(target=engine.run_forever, name='watch-engine', daemon=True)
    thread.start()
    # 独立心跳写线程：存活信号与主循环各阶段耗时解耦（主循环被慢 I/O 卡住时
    # 巡检不再误报「心跳丢失」；2026-10-16 事故修补）。
    engine.spawn_heartbeat_thread()
    # 板块映射重建线程（确认核验·共振阶段的快照来源）：装配了流水线才起；
    # 独立 daemon，失败只降级不阻断。放在线程启动后，不抢宿主 lifespan。
    _start_sector_resonance_refresher(
        getattr(engine, 'confirm_verify_pipeline', None))
    # 政策盯盘扫描线程（2026-10-21 政策盯盘闭环）：政策新闻 → 板块 → 持仓/候选池。
    # 独立 daemon、与主循环解耦（**不动 engine**）；装配/启动失败只降级记日志，
    # 绝不让宿主启动被这条旁路拖死。
    try:
        start_policy_watch_scanner(engine)
    except Exception as e:  # noqa: BLE001 - 旁路启动失败不阻断宿主
        logger.error('政策盯盘扫描线程启动失败（引擎照常运行）', error=str(e))
    logger.info('✓ WatchEngine 已在后台线程启动')
    return engine, thread


def start_watch_sidecars_in_thread() -> WatchEngine:
    """只启动 V1 的**旁路服务**（不起判定循环）—— V2 接管盯盘判定时的过渡形态。

    2026-10-24 用户裁定「V2 上线、V1 下线」。V1 的 tick 判定循环由 V2 定时任务取代，
    但 V1 引擎线程同时承载这些**不可丢**的旁路服务：

      - sidecar：摘要门 / 元触发复核 / 持仓生命周期联动（含新仓自动补止损）/
        持仓板块映射 / 走势回填 / 池级盯盘对账 / 消息监控 / 收盘体检日报
      - 心跳写线程（引擎存活信号）
      - 板块共振快照刷新、政策盯盘扫描

    这些能力 V2 尚未复制；直接把整个 V1 线程停掉会导致「新仓不再自动补止损」
    「新闻/回填/对账静默停摆」。本函数只建引擎对象并拉起旁路线程，**不跑
    ``run_forever``**，因此不会产生任何 V1 触发/通知（判定权已交给 V2）。
    V2 未接管前不要单独使用本函数。
    """
    engine = create_watch_engine()
    engine.spawn_heartbeat_thread()
    engine._ensure_sidecar_thread()  # noqa: SLF001 - 同包生命周期入口
    _start_sector_resonance_refresher(
        getattr(engine, 'confirm_verify_pipeline', None))
    try:
        start_policy_watch_scanner(engine)
    except Exception as e:  # noqa: BLE001 - 旁路启动失败不阻断宿主
        logger.error('政策盯盘扫描线程启动失败（旁路服务照常运行）', error=str(e))
    logger.info('✓ WatchEngine V1 旁路服务已启动（判定循环未启动，判定归 V2）')
    return engine
