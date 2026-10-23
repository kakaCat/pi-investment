"""板块共振核验服务（2026-10-20，确认核验流水线的一环）

用户场景：盯盘确认了一只「候选池」标的的异动（放量突破/破位），但**个股为什么会动**
决定这条信号值不值得跟——整个板块同步异动 = 有主线资金，个股独立异动 = 消息/游资/噪声。
本服务回答一件事：**该标的的异动是板块共振，还是孤立异动？**

口径（写死在这里，避免各调用方各说各话）：
  1) **候选池口径标的→板块映射**：只对候选池标的做映射。做法是反查——按板块列表
     逐块取成分股，与候选池标的求交集；**首个命中的板块即主板块**（板块列表行业在前、
     概念在后，故行业板块优先）。映射是重活（每板块一次外呼），只在 sidecar/重建入口
     跑，快照带 TTL；tick/确认热路径只读快照。
  2) **同板块核心标的**：核心 = 板块内总市值居前 `core_size` 只（无市值字段时按成分
     顺序），**剔除核验标的自身**（否则自己跟自己共振）。也可由调用方用 `core_by_sector`
     显式指定某个板块的核心名单。
  3) **同步异动**：核心标的与核验标的**同向**（同涨/同跌）且 |涨跌幅| ≥ `sync_pct`。
       · 同步数 ≥ `min_synced` 且 同步数/有行情核心标的数 ≥ `min_sync_ratio` → 共振成立；
       · 否则 → **孤立异动**，reason 里写清降级理由（差多少、同向最大幅度多少）。
  4) **映射缺失 = 不校验**：映射未构建/已过期/该标的不在映射里时，返回
     `status='skipped' / verified=False / degraded=True`，reason 明确「不校验」。
     **绝不把缺数据当成「未共振」**——前者是不下结论，后者是下了相反的结论。

取数边界（仓内 Data Access Rules）：默认经 qs_market_data 的 DataProviderManager
（不直连 akshare）；`sector_source` / `quote_source` 均可注入端口替身，单测零外呼。
"""
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

STATUS_RESONANT = 'resonant'
STATUS_ISOLATED = 'isolated'
STATUS_SKIPPED = 'skipped'

STATUS_LABELS = {
    STATUS_RESONANT: '板块共振',
    STATUS_ISOLATED: '孤立异动',
    STATUS_SKIPPED: '不校验',
}

__all__ = [
    'PeerObservation',
    'SectorResonanceResult',
    'SectorResonanceService',
    'STATUS_ISOLATED',
    'STATUS_LABELS',
    'STATUS_RESONANT',
    'STATUS_SKIPPED',
]

#: 默认异动阈值（%）：核验标的 |涨跌幅| 不到这条线，本身不算「异动」，无需共振核验
DEFAULT_ABNORMAL_PCT = 1.5
#: 默认同步阈值（%）：核心标的与核验标的同向且幅度达到这条线才算「同步异动」
DEFAULT_SYNC_PCT = 1.0
#: 默认至少同步家数 / 默认同步占比下限
DEFAULT_MIN_SYNCED = 1
DEFAULT_MIN_SYNC_RATIO = 0.5
#: 默认核心标的数
DEFAULT_CORE_SIZE = 5
#: 映射快照 TTL（秒）：板块成分日间基本不变，6h 够
DEFAULT_TTL_SEC = 6 * 3600
#: 单次重建最多遍历的板块数（防爆量外呼；东财行业+概念约 400+，候选池标的多为行业）
DEFAULT_MAX_BOARDS = 120


# ── 结果对象 ────────────────────────────────────────────────

@dataclass(frozen=True)
class PeerObservation:
    """一只核心标的的核验观测（只有真的取到行情才进这里）"""

    symbol: str
    name: Optional[str]
    change_pct: float
    synced: bool
    market_cap: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        return {'symbol': self.symbol, 'name': self.name,
                'change_pct': self.change_pct, 'synced': self.synced,
                'market_cap': self.market_cap}


@dataclass(frozen=True)
class SectorResonanceResult:
    """共振核验结果（调用方按 status/verified/passed 分流）

    三态语义（别混）：
      · resonant：核验通过——同板块核心标的同步异动；
      · isolated：核验不通过——孤立异动，`reason` 是**降级理由**；
      · skipped ：**不校验**——数据缺失/标的不在映射/自身未达异动阈值，
                  `verified=False`、`passed=None`，调用方应 fail-open 并如实标注，
                  不得据此判「共振成立」或「孤立异动」。
    """

    symbol: str
    sector: Optional[str]
    status: str
    verified: bool
    reason: str
    subject_change_pct: Optional[float] = None
    direction: Optional[str] = None          # 'up' / 'down'
    core_peers: Tuple[str, ...] = ()         # 被选为核心标的的代码（含缺行情的）
    peers: Tuple[PeerObservation, ...] = ()  # 实际取到行情的核心标的
    synced: Tuple[str, ...] = ()
    quoted_peers: int = 0
    sync_ratio: Optional[float] = None
    core_basis: Optional[str] = None         # 'market_cap' / 'order' / 'explicit'
    missing_peer_quotes: Tuple[str, ...] = ()
    skip_code: Optional[str] = None
    degraded: bool = False
    thresholds: Dict[str, Any] = field(default_factory=dict)

    # ── 调用方友好别名（确认流水线按 passed 分流）────────────────
    @property
    def passed(self) -> Optional[bool]:
        """True=共振成立；False=孤立异动；None=不校验（数据缺失）。"""
        if not self.verified:
            return None
        return self.status == STATUS_RESONANT

    @property
    def ok(self) -> Optional[bool]:
        return self.passed

    @property
    def resonance(self) -> Optional[bool]:
        return self.passed

    @property
    def verdict(self) -> str:
        """status 别名（与 LiquidityCheckResult / EnvironmentGateDecision 的风格一致）。"""
        return self.status

    @property
    def label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def missing(self) -> Tuple[str, ...]:
        """缺失行情的核心标的（与 liquidity 的 missing 同口径）。"""
        return self.missing_peer_quotes

    @property
    def skipped(self) -> bool:
        return self.status == STATUS_SKIPPED

    @property
    def downgraded(self) -> bool:
        return self.status == STATUS_ISOLATED

    @property
    def fail_open(self) -> bool:
        """不校验时是否应放行（本服务的口径：放行但标注，不拦信号）。"""
        return self.skipped

    @property
    def downgrade_reason(self) -> Optional[str]:
        return self.reason if self.status == STATUS_ISOLATED else None

    def as_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'sector': self.sector,
            'status': self.status,
            'verdict': self.status,
            'label': self.label,
            'skipped': self.skipped,
            'verified': self.verified,
            'passed': self.passed,
            'reason': self.reason,
            'subject_change_pct': self.subject_change_pct,
            'direction': self.direction,
            'core_peers': list(self.core_peers),
            'peers': [p.as_dict() for p in self.peers],
            'synced': list(self.synced),
            'quoted_peers': self.quoted_peers,
            'sync_ratio': self.sync_ratio,
            'core_basis': self.core_basis,
            'missing_peer_quotes': list(self.missing_peer_quotes),
            'skip_code': self.skip_code,
            'degraded': self.degraded,
            'thresholds': dict(self.thresholds),
        }

    def to_dict(self) -> Dict[str, Any]:
        """as_dict 别名（与 LiquidityCheckResult / EnvironmentGateDecision 命名一致）。"""
        return self.as_dict()


# ── 默认数据源适配（qs_market_data；仅在使用时导入，避免包初始化耦合）──

def _unwrap(result: Any) -> Any:
    """剥 manager 结果壳：{'success','data': MarketData} → MarketData.data → dict。

    2026-10-20 两次实测形状：manager 返回 {'success': True, 'data': MarketData}，
    MarketData 里还有一层 .data；两层都要剥（与 held_sector_map 同款兼容）。
    """
    data = result.get('data') if isinstance(result, dict) else getattr(result, 'data', None)
    if data is not None and not isinstance(data, dict):
        data = getattr(data, 'data', None)
    return data


class _ManagerSectorSource:
    """DataProviderManager → 板块端口（行业在前、概念在后，保持数据源顺序）"""

    def __init__(self, manager):
        self._manager = manager

    def list_sectors(self) -> List[str]:
        data = _unwrap(self._manager.get_sector_list())
        if not isinstance(data, dict):
            raise RuntimeError('板块列表获取失败: %r' % (data,))
        names: List[str] = []
        for key in ('industries', 'concepts'):
            for item in data.get(key) or []:
                name = item.get('name') if isinstance(item, dict) else None
                if name and str(name) not in names:
                    names.append(str(name))
        if not names:
            raise RuntimeError('板块列表为空（数据源异常）')
        return names

    def get_members(self, sector: str) -> List[Dict[str, Any]]:
        data = _unwrap(self._manager.get_sector_stocks(sector))
        if not isinstance(data, dict) or not data.get('found'):
            return []
        out = []
        for row in data.get('stocks') or []:
            if not isinstance(row, dict):
                continue
            out.append({'symbol': row.get('symbol'), 'name': row.get('name'),
                        'market_cap': row.get('market_cap')})
        return out


class _ManagerQuoteSource:
    """DataProviderManager → 批量行情端口"""

    def __init__(self, manager):
        self._manager = manager

    def get_quotes(self, symbols: Iterable[str]) -> Dict[str, Any]:
        return self._manager.get_quotes(list(symbols))


# ── 工具函数 ────────────────────────────────────────────────

def _bare_symbol(value: Any) -> str:
    """'600519.SH' / 'sh600519' / ' 600519 ' → '600519'（映射/行情统一裸码）"""
    text = str(value or '').strip().upper()
    if not text:
        return ''
    if '.' in text:
        text = text.split('.', 1)[0]
    if len(text) > 6 and text[:2] in ('SH', 'SZ', 'BJ') and text[2:].isdigit():
        text = text[2:]
    return text


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == '':
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if isfinite(num) else None


def _extract_change(value: Any) -> Optional[float]:
    """从 quote（dict/对象/裸数字）里取涨跌幅（%）；缺字段返回 None（不拿 0 冒充）。"""
    if value is None:
        return None
    if isinstance(value, bool):   # bool 是 int 子类，明确排除
        return None
    if isinstance(value, (int, float)):
        return _to_float(value)
    if isinstance(value, Mapping):
        for key in ('change_pct', 'pct', 'changePercent', 'change_percent'):
            pct = _to_float(value.get(key))
            if pct is not None:
                return pct
        price = _to_float(value.get('price'))
        prev_close = _to_float(value.get('prev_close'))
        if price is not None and prev_close:
            return (price - prev_close) / prev_close * 100.0
        return None
    for attr in ('change_pct', 'pct', 'changePercent'):
        pct = _to_float(getattr(value, attr, None))
        if pct is not None:
            return pct
    price = _to_float(getattr(value, 'price', None))
    prev_close = _to_float(getattr(value, 'prev_close', None))
    if price is not None and prev_close:
        return (price - prev_close) / prev_close * 100.0
    return None


def _normalize_quotes(raw: Any) -> Dict[str, Any]:
    """行情容器归一：{'success','data':{sym: quote}} / {sym: quote} → {裸码: quote}"""
    if raw is None:
        return {}
    data = raw
    if isinstance(raw, Mapping) and 'data' in raw:
        # manager 结果壳 {'success','data': {...}}；调用方直接传 {sym: quote} 时走 else 分支
        data = raw.get('data')
    if not isinstance(data, Mapping):
        return {}
    out: Dict[str, Any] = {}
    for key, value in data.items():
        sym = _bare_symbol(key)
        # 只收「像标的」的键：manager 失败结果里的 success/error 等键不能被当成标的
        if sym and any(ch.isdigit() for ch in sym):
            out[sym] = value
    return out


# ── 服务 ────────────────────────────────────────────────────

class SectorResonanceService:
    """板块共振核验（映射快照 + 核心标的同步异动判定）

    Args:
        sector_source: 板块端口（`list_sectors()` / `get_members(sector)`）；
            None = 首次使用时懒加载 DataProviderManager。
        quote_source: 行情端口（`get_quotes(symbols)` / callable / dict）；
            None = 首次使用时懒加载 DataProviderManager；也可在 check(quotes=...) 直接给。
        candidate_source: 候选池端口（`get_members(pool_id)`）；
            配合 `pool_id` 让 `refresh()` 自行取候选池标的。
        pool_id: 候选池 id（候选池口径）；不给则 `refresh()` 需显式传 candidates。
        core_by_sector: 显式核心名单 {板块: [symbol...]}；不给则按总市值前 N。
        now_fn: 时钟注入（TTL 测试用）。
    """

    def __init__(self, sector_source=None, quote_source=None, candidate_source=None,
                 pool_id: Optional[int] = None, core_by_sector: Optional[Mapping[str, Iterable]] = None,
                 ttl_sec: int = DEFAULT_TTL_SEC, now_fn: Callable[[], datetime] = datetime.now,
                 abnormal_pct: float = DEFAULT_ABNORMAL_PCT,
                 sync_pct: float = DEFAULT_SYNC_PCT,
                 min_synced: int = DEFAULT_MIN_SYNCED,
                 min_sync_ratio: float = DEFAULT_MIN_SYNC_RATIO,
                 core_size: int = DEFAULT_CORE_SIZE,
                 max_boards: int = DEFAULT_MAX_BOARDS):
        if abnormal_pct <= 0:
            raise ValueError('abnormal_pct 必须为正数（%）')
        if sync_pct <= 0:
            raise ValueError('sync_pct 必须为正数（%）')
        if min_synced < 1:
            raise ValueError('min_synced 至少为 1')
        if not 0 < min_sync_ratio <= 1:
            raise ValueError('min_sync_ratio 必须在 (0, 1]')
        if core_size < 1:
            raise ValueError('core_size 至少为 1')
        self._sector_source = sector_source
        self._quote_source = quote_source
        self._candidate_source = candidate_source
        self._pool_id = pool_id
        self._core_by_sector = {str(k): tuple(v or ()) for k, v in (core_by_sector or {}).items()}
        self._ttl = ttl_sec
        self._now = now_fn
        self._abnormal_pct = float(abnormal_pct)
        self._sync_pct = float(sync_pct)
        self._min_synced = int(min_synced)
        self._min_sync_ratio = float(min_sync_ratio)
        self._core_size = int(core_size)
        self._max_boards = int(max_boards)

        self._map: Dict[str, str] = {}
        self._members: Dict[str, List[Dict[str, Any]]] = {}
        self._built_at: Optional[datetime] = None
        self._degraded = False
        self._last_error: Optional[str] = None

    # ── 映射：候选池标的 → 板块 ────────────────────────────────

    def refresh(self, force: bool = False,
                candidates: Optional[Iterable[Any]] = None) -> Dict[str, Any]:
        """重建「候选池标的 → 板块」快照（sidecar/日频入口；不在确认热路径跑）。

        Args:
            force: True = 忽略 TTL 强制重建。
            candidates: 候选池标的（symbol 或 {symbol:...}）；None = 用 candidate_source
                + pool_id 取候选池成员。两者都没有 → built=False（不瞎猜）。

        Returns:
            {'built': bool, 'mapped': n, 'unmapped': [...], 'sectors_scanned': n,
             'degraded': bool, ...}。失败保留旧快照（stale 比空好）并置 degraded。
        """
        if not force and self._fresh():
            return {'built': False, 'skipped': 'TTL 未到期',
                    'mapped': len(self._map), 'degraded': self._degraded}
        try:
            wanted = self._resolve_candidates(candidates)
        except Exception as e:  # noqa: BLE001 - 候选池读取失败降级，不影响旧快照
            self._degraded = True
            self._last_error = '候选池读取失败: %s' % e
            logger.error('候选池标读取失败，保留旧板块映射', error=str(e))
            return {'built': False, 'degraded': True, 'reason': self._last_error,
                    'mapped': len(self._map)}
        if not wanted:
            return {'built': False, 'degraded': False,
                    'reason': '未提供候选池标的（candidates 为空且未装配 candidate_source/pool_id）',
                    'mapped': len(self._map)}

        try:
            source = self._sector()
            names = list(source.list_sectors() or ())
        except Exception as e:  # noqa: BLE001 - 取数失败降级
            self._degraded = True
            self._last_error = '板块列表获取失败: %s' % e
            logger.error('板块列表获取失败，保留旧板块映射', error=str(e))
            return {'built': False, 'degraded': True, 'reason': self._last_error,
                    'mapped': len(self._map)}
        if not names:
            self._degraded = True
            self._last_error = '板块列表为空（数据源异常）'
            logger.error(self._last_error)
            return {'built': False, 'degraded': True, 'reason': self._last_error,
                    'mapped': len(self._map)}

        new_map: Dict[str, str] = {}
        new_members: Dict[str, List[Dict[str, Any]]] = {}
        remaining = set(wanted)
        scanned = 0
        for name in names[:self._max_boards]:
            if not remaining:
                break
            scanned += 1
            try:
                rows = source.get_members(name) or []
            except Exception as e:  # noqa: BLE001 - 单板块失败不拖垮整批
                logger.warning('板块成分获取失败（跳过该板块）', board=name, error=str(e))
                continue
            members: List[Dict[str, Any]] = []
            for row in rows:
                if isinstance(row, str):
                    row = {'symbol': row}
                if not isinstance(row, Mapping):
                    continue
                sym = _bare_symbol(row.get('symbol'))
                if not sym:
                    continue
                members.append({'symbol': sym, 'name': row.get('name'),
                                'market_cap': _to_float(row.get('market_cap'))})
            if not members:
                continue
            hit = [m for m in members if m['symbol'] in remaining]
            if not hit:
                continue
            # 首个命中的板块即主板块（行业板块在列表前面，故行业优先于概念）
            new_members[name] = members
            for member in hit:
                new_map[member['symbol']] = name
                remaining.discard(member['symbol'])

        # 原子换快照：读者要么看到旧快照、要么看到新快照
        self._map, self._members = new_map, new_members
        self._built_at = self._now()
        self._degraded = False
        self._last_error = None
        logger.info('候选池板块映射已重建', mapped=len(new_map),
                    sectors=len(new_members), scanned=scanned)
        return {'built': True, 'mapped': len(new_map), 'unmapped': sorted(remaining),
                'sectors_scanned': scanned, 'degraded': False}

    def mapping(self) -> Dict[str, str]:
        """当前有效快照（symbol → 板块）；未构建/已过期返回 {}（调用方据此「不校验」）。"""
        return dict(self._map) if self._fresh() else {}

    def sector_of(self, symbol: Any) -> Optional[str]:
        return self.mapping().get(_bare_symbol(symbol))

    def members_of(self, sector: str) -> List[Dict[str, Any]]:
        """某板块的成分快照（仅主板块命中的板块才有缓存）；过期/未知返回 []。"""
        if not self._fresh():
            return []
        return [dict(m) for m in self._members.get(str(sector), ())]

    def refresh_status(self) -> Dict[str, Any]:
        """映射健康度（供 /api/watch 摘要或日志检查）。"""
        return {'built': self._built_at is not None,
                'fresh': self._fresh(),
                'mapped': len(self._map) if self._fresh() else 0,
                'degraded': self._degraded,
                'last_error': self._last_error}

    # ── 核验 ──────────────────────────────────────────────────

    def check(self, symbol: Any, change_pct: Optional[float] = None, *,
              quote: Any = None, sector: Optional[str] = None,
              quotes: Optional[Mapping[str, Any]] = None) -> SectorResonanceResult:
        """核验单只标的的板块共振。

        Args:
            symbol: 核验标的（裸码/带后缀均可）。
            change_pct: 标的涨跌幅（%）；None 时从 quote/quotes/行情端口取。
            quote: 标的行情对象（dict/QuoteData，含 change_pct 或 price+prev_close）。
            sector: 显式板块（跳过映射；仍会从缓存/数据源取成分）。一般不用给。
            quotes: 预取行情 {symbol: quote|change_pct}；给了就不再外呼。

        返回三态结果；映射缺失/行情缺失返回 skipped（不校验），绝不臆造结论。
        """
        sym = _bare_symbol(symbol)
        if not sym:
            return self._skip(symbol=str(symbol), sector=None, code='invalid_symbol',
                              reason='无效标的代码，共振核验不校验。')
        thresholds = self._thresholds()

        # 1) 板块归属：显式 > 候选池映射（缺失/过期 → 不校验）
        map_fresh = self._fresh()
        if sector is None:
            if not map_fresh:
                if self._built_at is None:
                    code = 'mapping_not_built'
                    tail = '候选池→板块映射尚未构建（请先 refresh(candidates)）'
                else:
                    code = 'mapping_expired'
                    tail = '候选池→板块映射已过期（TTL %ss）' % self._ttl
                if self._last_error:
                    tail += '；最近一次重建失败：%s' % self._last_error
                return self._skip(sym, None, code,
                                  '板块映射缺失：%s——共振核验降级为「不校验」；'
                                  '不认定共振成立，也不认定孤立异动。' % tail,
                                  thresholds=thresholds)
            sector = self._map.get(sym)
            if not sector:
                return self._skip(
                    sym, None, 'symbol_not_mapped',
                    '板块映射缺失：%s 不在候选池口径板块映射中（候选池标的×板块成分反查未命中）'
                    '——共振核验降级为「不校验」；不认定共振成立，也不认定孤立异动。' % sym,
                    thresholds=thresholds)
        else:
            sector = str(sector)

        members = self._members_for(sector)

        # 2) 标的涨跌幅（缺失 → 不校验）
        pct = _to_float(change_pct)
        if pct is None and quote is not None:
            pct = _extract_change(quote)
        qmap: Dict[str, Any] = _normalize_quotes(quotes) if quotes else {}
        if pct is None and sym in qmap:
            pct = _extract_change(qmap[sym])
        if pct is None:
            fetched = self._fetch_quotes([sym])
            if sym in fetched:
                pct = _extract_change(fetched[sym])
                qmap.setdefault(sym, fetched[sym])
        if pct is None:
            return self._skip(
                sym, sector, 'subject_quote_missing',
                '核验标的行情缺失：%s 未取到涨跌幅——共振核验降级为「不校验」；'
                '不认定共振成立，也不认定孤立异动。' % sym,
                thresholds=thresholds)

        # 3) 自身未达异动阈值 → 无需共振核验（也是「不校验」，但不是数据缺失）
        if abs(pct) < self._abnormal_pct:
            return self._skip(
                sym, sector, 'not_abnormal',
                '标的涨跌幅 %+.2f%% 未达异动阈值 %.2f%%——不构成需核验的异动，'
                '共振核验不校验。' % (pct, self._abnormal_pct),
                subject_change_pct=pct, thresholds=thresholds, degraded=False)

        direction = 'up' if pct > 0 else 'down'

        # 4) 板块成分缺失（映射在但成分取不到）→ 不校验，别把「取不到」当「没有核心标的」
        if not members:
            return self._skip(
                sym, sector, 'sector_members_missing',
                '板块「%s」成分数据缺失（映射命中但成分股未取到）——共振核验降级为'
                '「不校验」；不认定共振成立，也不认定孤立异动。' % sector,
                subject_change_pct=pct, direction=direction,
                thresholds=thresholds, degraded=True)

        # 5) 核心标的（板块内总市值前 N，剔除自身）
        core = self._select_core(sector, members, sym)
        if not core:
            return self._skip(
                sym, sector, 'no_core_peers',
                '板块「%s」内无其他可核验核心标的（成分 %d 只，剔除自身后为空）'
                '——共振核验不校验；不臆造共振结论。' % (sector, len(members)),
                subject_change_pct=pct, direction=direction,
                thresholds=thresholds, degraded=False)
        core_syms = [m['symbol'] for m in core]

        # 6) 核心标的行情（缺失逐一标注；一只都没取到 → 不校验，不当成孤立）
        need = [s for s in core_syms if s not in qmap]
        if need:
            qmap.update(self._fetch_quotes(need))
        observations: List[PeerObservation] = []
        missing: List[str] = []
        for member in core:
            peer = member['symbol']
            pct_peer = _extract_change(qmap.get(peer))
            if pct_peer is None:
                missing.append(peer)
                continue
            same_direction = (pct_peer > 0) if direction == 'up' else (pct_peer < 0)
            synced = bool(same_direction and abs(pct_peer) >= self._sync_pct)
            observations.append(PeerObservation(
                symbol=peer, name=member.get('name'), change_pct=pct_peer,
                synced=synced, market_cap=member.get('market_cap')))
        if not observations:
            return self._skip(
                sym, sector, 'peer_quotes_missing',
                '同板块核心标的行情缺失（%d 只均未取到涨跌幅）——共振核验降级为'
                '「不校验」；不认定共振成立，也不认定孤立异动。' % len(core),
                subject_change_pct=pct, direction=direction,
                core_peers=tuple(core_syms), missing_peer_quotes=tuple(missing),
                core_basis=self._core_basis(sector, core), thresholds=thresholds,
                degraded=True)

        synced_obs = [o for o in observations if o.synced]
        quoted = len(observations)
        ratio = len(synced_obs) / quoted
        resonant = len(synced_obs) >= self._min_synced and ratio >= self._min_sync_ratio
        core_basis = self._core_basis(sector, core)
        missing_tail = ('（另有 %d 只核心标的行情缺失：%s）'
                        % (len(missing), '、'.join(missing))) if missing else ''

        if resonant:
            examples = '、'.join('%s %+.2f%%' % (o.symbol, o.change_pct)
                                for o in synced_obs[:3])
            reason = ('板块共振成立：%s「%s」同向核心标的 %d/%d 只同步异动'
                      '（要求 ≥%d 只且占比 ≥%.0f%%，实际 %.0f%%；%s）%s'
                      % (sym, sector, len(synced_obs), quoted, self._min_synced,
                         self._min_sync_ratio * 100, ratio * 100, examples, missing_tail))
            status, verified = STATUS_RESONANT, True
        else:
            same_dir = [o for o in observations if
                        ((o.change_pct > 0) if direction == 'up' else (o.change_pct < 0))]
            strongest = max(same_dir, key=lambda o: abs(o.change_pct)) if same_dir else None
            strongest_text = ('同向最大 %s %+.2f%%' % (strongest.symbol, strongest.change_pct)
                              if strongest else '无同向核心标的')
            reason = ('孤立异动（降级理由）：%s「%s」核心标的 %d/%d 只同向异动'
                      '（同向且 |涨跌幅| ≥%.2f%%；要求 ≥%d 只且占比 ≥%.0f%%，'
                      '实际 %.0f%%）；%s——判定为个股独立异动，不按板块共振加权。%s'
                      % (sym, sector, len(synced_obs), quoted, self._sync_pct,
                         self._min_synced, self._min_sync_ratio * 100, ratio * 100,
                         strongest_text, missing_tail))
            status, verified = STATUS_ISOLATED, True

        return SectorResonanceResult(
            symbol=sym, sector=sector, status=status, verified=verified, reason=reason,
            subject_change_pct=pct, direction=direction,
            core_peers=tuple(core_syms), peers=tuple(observations),
            synced=tuple(o.symbol for o in synced_obs), quoted_peers=quoted,
            sync_ratio=ratio, core_basis=core_basis,
            missing_peer_quotes=tuple(missing), thresholds=thresholds)

    def verify(self, symbol: Any, change_pct: Optional[float] = None, **kwargs) -> SectorResonanceResult:
        """`check` 的别名（确认核验流水线用 verify 语义更直观）。"""
        return self.check(symbol, change_pct, **kwargs)

    # ── 内部：候选/板块/行情 ───────────────────────────────────

    def _resolve_candidates(self, candidates: Optional[Iterable[Any]]) -> List[str]:
        if candidates is not None:
            return self._dedupe_symbols(candidates)
        if self._candidate_source is None or self._pool_id is None:
            return []
        members = self._candidate_source.get_members(int(self._pool_id)) or []
        return self._dedupe_symbols(members)

    @staticmethod
    def _dedupe_symbols(items: Iterable[Any]) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in items or ():
            raw = item.get('symbol') if isinstance(item, Mapping) else item
            sym = _bare_symbol(raw)
            if sym and any(ch.isdigit() for ch in sym) and sym not in seen:
                seen.add(sym)
                out.append(sym)
        return out

    def _sector(self):
        if self._sector_source is None:
            from qs_market_data.adapters.outbound.datasources.manager import (
                get_data_provider_manager,
            )
            self._sector_source = _ManagerSectorSource(get_data_provider_manager())
        return self._sector_source

    def _quote(self):
        if self._quote_source is None:
            from qs_market_data.adapters.outbound.datasources.manager import (
                get_data_provider_manager,
            )
            self._quote_source = _ManagerQuoteSource(get_data_provider_manager())
        return self._quote_source

    def _fetch_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """批量取行情并归一成 {裸码: quote}；失败返回 {}（调用方按缺失降级）。"""
        symbols = [s for s in dict.fromkeys(_bare_symbol(x) for x in symbols) if s]
        if not symbols:
            return {}
        try:
            source = self._quote()
            if isinstance(source, Mapping):
                raw: Any = source
            elif hasattr(source, 'get_quotes'):
                raw = source.get_quotes(symbols)
            elif callable(source):
                raw = source(symbols)
            else:
                raw = source
        except Exception as e:  # noqa: BLE001 - 行情失败降级为缺失
            logger.warning('核心标的行情获取失败（按缺失处理）', symbols=symbols, error=str(e))
            return {}
        return _normalize_quotes(raw)

    def _members_for(self, sector: str) -> List[Dict[str, Any]]:
        if self._fresh():
            cached = self._members.get(sector)
            if cached:
                return [dict(m) for m in cached]
        # 显式 sector / 快照未覆盖该板块：按需取一次成分（确认阶段低频，可接受）
        if self._sector_source is None and not self._fresh():
            return []
        try:
            source = self._sector()
            rows = source.get_members(sector) or []
        except Exception as e:  # noqa: BLE001
            logger.warning('板块成分按需获取失败', board=sector, error=str(e))
            return []
        members: List[Dict[str, Any]] = []
        for row in rows:
            if isinstance(row, str):
                row = {'symbol': row}
            if not isinstance(row, Mapping):
                continue
            sym = _bare_symbol(row.get('symbol'))
            if sym:
                members.append({'symbol': sym, 'name': row.get('name'),
                                'market_cap': _to_float(row.get('market_cap'))})
        return members

    def _select_core(self, sector: str, members: List[Dict[str, Any]],
                     subject: str) -> List[Dict[str, Any]]:
        """板块内核心标的：显式名单 > 总市值前 N（无市值按成分顺序），剔除自身。"""
        pool = [m for m in members if m['symbol'] != subject]
        explicit = self._core_by_sector.get(sector)
        if explicit:
            wanted = {_bare_symbol(s) for s in explicit if _bare_symbol(s)}
            return [m for m in pool if m['symbol'] in wanted][:self._core_size]
        if not pool:
            return []
        has_cap = any(m.get('market_cap') is not None for m in pool)
        if has_cap:
            pool = sorted(pool,
                          key=lambda m: (m.get('market_cap') is not None,
                                         m.get('market_cap') or 0.0),
                          reverse=True)
        return pool[:self._core_size]

    def _core_basis(self, sector: str, core: List[Dict[str, Any]]) -> Optional[str]:
        if not core:
            return None
        if self._core_by_sector.get(sector):
            return 'explicit'
        return 'market_cap' if any(m.get('market_cap') is not None for m in core) else 'order'

    # ── 内部：结果构造 ─────────────────────────────────────────

    def _thresholds(self) -> Dict[str, Any]:
        return {'abnormal_pct': self._abnormal_pct, 'sync_pct': self._sync_pct,
                'min_synced': self._min_synced,
                'min_sync_ratio': self._min_sync_ratio,
                'core_size': self._core_size}

    def _skip(self, symbol: str, sector: Optional[str], code: str, reason: str, *,
              subject_change_pct: Optional[float] = None,
              direction: Optional[str] = None,
              core_peers: Tuple[str, ...] = (),
              missing_peer_quotes: Tuple[str, ...] = (),
              core_basis: Optional[str] = None,
              thresholds: Optional[Dict[str, Any]] = None,
              degraded: bool = True) -> SectorResonanceResult:
        return SectorResonanceResult(
            symbol=_bare_symbol(symbol) or symbol, sector=sector,
            status=STATUS_SKIPPED, verified=False, reason=reason,
            subject_change_pct=subject_change_pct, direction=direction,
            core_peers=core_peers, missing_peer_quotes=missing_peer_quotes,
            core_basis=core_basis, skip_code=code, degraded=degraded,
            thresholds=thresholds or self._thresholds())

    def _fresh(self) -> bool:
        if self._built_at is None:
            return False
        return (self._now() - self._built_at).total_seconds() < self._ttl
