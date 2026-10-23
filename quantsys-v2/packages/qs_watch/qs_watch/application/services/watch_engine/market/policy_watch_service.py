"""政策盯盘路由服务（2026-10-21 政策盯盘闭环）：政策新闻 → 板块 → 成分股 → 与我有关

闭环（本卡 = 解析路由 + 扫描装配，**不动引擎**）：
    PolicyNewsSource 取全市场财经新闻
      → 政策词表/行业词表分级（`policy_lexicon` 唯一口径）
      → 命中板块（行业词表 + 板块名/别名）→ 行情板块 → 成分股
      → ∩（持仓 ∪ 候选池）
      → 持仓命中 → 既有 P0/P2 新闻卡路由（kind=news_alert，critical→P0 / soft→P2）
        候选池命中 → 确认核验查询（NewsWatchService.scan_candidates 只读口径，不发卡）
      → 与两条都不相交 → 不打扰（unrelated，只计数）

三条纪律（也是验收口径）：

  1) **只告警「与我有关」**：告警集合 = 板块成分 ∩ 持仓；候选池标的**不发卡**，
     只进确认核验查询（候选池是观察对象，不是持仓，把候选池命中写成 P0/P2 卡片
     就是消息洪水）。无关板块（如持仓只有半导体、新闻命中医药）不产生任何卡片。
  2) **映射缺失 fail-open**：板块映射取不到（数据源挂/板块列表为空/该板块在行情板块
     里认不出）时，本轮**不下结论**——item 标 skipped + reason，绝不把「没映射」
     当成「与我无关」，也绝不凭残缺映射乱告警。
  3) **板块映射复用现有口径，不维护第二份**：
     · 板块名 → canonical 板块：`policy_lexicon.normalize_sector / resolve_sector /
       SECTOR_ALIASES`（词表配置是唯一真相）；
     · 行情板块列表/成分：`sector_resonance_service._ManagerSectorSource`（与确认核验
       的共振阶段**同一个**取数适配器，含两层剥壳）与 `_bare_symbol`（同一套裸码归一）；
     · TTL 与 `sector_resonance_service.DEFAULT_TTL_SEC` 同一口径（6h，板块成分日间不变）。
     本模块**没有**第二张别名表、第二套裸码归一、第二个 manager 剥壳实现。

取数失败口径（与 policy_news_source / 新闻监控同源）：
    · 新闻取数失败 → scan 返回 skipped=True + reason，**不等于「无政策利空」**；
    · 持仓读取失败 → 该账户跳过并记 error（degraded），不阻塞其余账户；
    · 候选池读取失败 → 候选集为空 + degraded，持仓路由照常。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import structlog

from qs_watch.application.services.watch_engine import policy_lexicon
from qs_watch.application.services.watch_engine.policy_news_source import (
    PolicyNewsSource,
)
# 复用现有口径（**禁止第二份**）：行情板块/成分取数适配、裸码归一、TTL。
# 这两个名字带下划线是因为它们住在共振核验模块里，但口径是全包共用的。
from qs_watch.application.services.watch_engine.sector_resonance_service import (
    DEFAULT_TTL_SEC as SECTOR_MAP_TTL_SEC,
    _ManagerSectorSource,
    _bare_symbol,
)

logger = structlog.get_logger(__name__)

__all__ = [
    'ACTIONS',
    'ACTION_ALERT',
    'ACTION_CONFIRM',
    'ACTION_SKIPPED',
    'ACTION_UNRELATED',
    'DEFAULT_ACCOUNTS',
    'DEFAULT_MAX_ALERTS_PER_SCAN',
    'DEFAULT_MAX_BOARDS_PER_SECTOR',
    'DEFAULT_MAX_CONFIRM_PER_SCAN',
    'LEVEL_P0',
    'LEVEL_P2',
    'PolicyWatchService',
    'SectorConstituentIndex',
    'detect_sectors',
]

#: 严重度（转发 policy_lexicon 的同一套常量，不在本模块另立口径）
TIER_CRITICAL = policy_lexicon.TIER_CRITICAL
TIER_SOFT = policy_lexicon.TIER_SOFT
TIER_NONE = policy_lexicon.TIER_NONE
_TIER_ORDER = policy_lexicon.TIER_ORDER

#: 盯盘适用账户（与 news_watch_service / held_sector_map 同一口径）
DEFAULT_ACCOUNTS = ('agent_virtual', 'agent_brain', 'user_main_simulation')

#: 单个板块最多并几个行情板块（新能源会横跨光伏设备/风电设备/电池…，但要有上限，
#: 防一条新闻触发十几个外呼把 5 分钟一轮的扫描拖长）
DEFAULT_MAX_BOARDS_PER_SECTOR = 12
#: 单轮最多发几张持仓政策卡（板块级利空可能命中一屏持仓；超出计数为 truncated）
DEFAULT_MAX_ALERTS_PER_SCAN = 20
#: 单轮最多拿几只候选池标的去跑确认核验查询（每只一次外呼，必须有上限）
DEFAULT_MAX_CONFIRM_PER_SCAN = 8
#: 候选池确认查询的去重记忆条数（进程内；避免同一条政策新闻每轮重复核验同一标的）
DEFAULT_QUERY_MEMORY = 4096

#: 既有 P0/P2 路由（与 news_watch_service._send 同一组 level 语义：
#: send_watch_receipt 里 P0 → risk_stop 高优位，P2 → watch_symbol）
LEVEL_P0 = 'P0'
LEVEL_P2 = 'P2'
#: 卡片类型（watch_channels._KIND_LABELS['news_alert'] = 消息监控）
ALERT_KIND = 'news_alert'

ACTION_ALERT = 'alert'            # 持仓命中 → 发 P0/P2 卡
ACTION_CONFIRM = 'confirm'        # 仅候选池命中 → 确认核验查询（不发卡）
ACTION_UNRELATED = 'unrelated'    # 与持仓/候选池都不相交 → 不打扰
ACTION_SKIPPED = 'skipped'        # 未路由（未命中词表 / 映射缺失 / 宏观无板块）
ACTIONS = (ACTION_ALERT, ACTION_CONFIRM, ACTION_UNRELATED, ACTION_SKIPPED)

#: 板块名后缀（与 policy_lexicon.normalize_sector 同源，用于「板块名包含别名」判定）
_ASCII_TOKEN = re.compile(r'^[A-Za-z0-9]+$')


# ── 基础工具（全部委托现有口径，不新建映射表）────────────────────────

def _text(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _read(obj: Any, *keys: str) -> Any:
    """从 Mapping 或对象属性取第一个非 None 值（持仓行/池成员两种形状都吃）。"""
    if obj is None:
        return None
    for key in keys:
        if isinstance(obj, Mapping):
            value = obj.get(key)
        else:
            value = getattr(obj, key, None)
        if value is not None:
            return value
    return None


def _tier_max(*tiers: Optional[str]) -> str:
    """取最高严重度（critical 压过 soft，none 最低）。"""
    best = TIER_NONE
    for tier in tiers:
        candidate = str(tier or TIER_NONE)
        if candidate not in _TIER_ORDER:
            continue
        if best == TIER_NONE or _TIER_ORDER[candidate] < _TIER_ORDER[best]:
            best = candidate
    return best


def _unique(items: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for item in items or ():
        text = _text(item)
        if text and text not in out:
            out.append(text)
    return out


def _contains_token(text: str, token: str) -> bool:
    """板块名/别名是否出现在标题里（中文子串；ASCII 词按词边界，避免 'ai' 命中 said）。"""
    if not text or not token:
        return False
    if _ASCII_TOKEN.match(token):
        pattern = r'(?<![A-Za-z0-9])%s(?![A-Za-z0-9])' % re.escape(token)
        return re.search(pattern, text, re.IGNORECASE) is not None
    return token in text


def _sector_tokens(sector: Optional[str]) -> Tuple[str, ...]:
    """板块 → 名称/别名集合（**只从 policy_lexicon 的 SECTOR_ALIASES 派生**）。"""
    canonical = (policy_lexicon.resolve_sector(sector)
                 or policy_lexicon.normalize_sector(sector))
    tokens: List[str] = []
    for token in (policy_lexicon.normalize_sector(sector), canonical):
        if token and token not in tokens:
            tokens.append(token)
    for alias, target in policy_lexicon.SECTOR_ALIASES.items():
        if target == canonical and alias not in tokens:
            tokens.append(alias)
    return tuple(tokens)


def _named_sectors(title: str) -> Set[str]:
    """标题里点名的板块（canonical 键；命中 = 板块名或别名出现在标题里）。"""
    text = _text(title)
    if not text:
        return set()
    named: Set[str] = set()
    for sector in policy_lexicon.INDUSTRY_LEXICONS:
        if any(_contains_token(text, token) for token in _sector_tokens(sector)):
            named.add(sector)
    return named


def detect_sectors(title: str) -> List[Dict[str, Any]]:
    """标题 → 命中的板块列表（行业词表口径；纯函数，不取数）。

    返回条目：{'sector': canonical, 'tier': critical|soft|none,
               'words': [命中词], 'basis': 'name'|'lexicon'}

    判定规则（与 resolve 的分流配合）：
      · **点名**（标题出现板块名/别名）→ basis='name'，即便行业词表没命中也会列出
        （tier=none），最终是否告警由政策词表/其它板块的严重度决定；
      · **词表命中但没点名** → basis='lexicon'，只在「这确实是政策新闻」时才路由
        （否则「多家公司宣布扩产」这类通用词会把所有扩产板块都拉进来）。
    顺序固定（INDUSTRY_LEXICONS 声明序），便于日志与用例断言。
    """
    text = _text(title)
    if not text:
        return []
    named = _named_sectors(text)
    out: List[Dict[str, Any]] = []
    for sector, lexicon in policy_lexicon.INDUSTRY_LEXICONS.items():
        tier, words = lexicon.classify(text)
        if sector in named:
            out.append({'sector': sector, 'tier': tier,
                        'words': list(words), 'basis': 'name'})
        elif tier != TIER_NONE:
            out.append({'sector': sector, 'tier': tier,
                        'words': list(words), 'basis': 'lexicon'})
    # 点名但行业词表一条没命中（如「半导体板块午后拉升」）：也要列出来，
    # 让上层用政策口径/整体严重度决定是否打扰，而不是静默当成「没命中板块」。
    for sector in policy_lexicon.INDUSTRY_LEXICONS:
        if sector in named and not any(item['sector'] == sector for item in out):
            out.append({'sector': sector, 'tier': TIER_NONE,
                        'words': [], 'basis': 'name'})

    # 兜底：机构名类政策标题往往不带板块别名（「证监会：…」没有「券商」二字）。
    # 只有**一条板块都没识别出来**时才用政策→默认板块提示，避免覆盖别名口径；
    # basis='hint' 让留痕能区分「标题点名」与「按机构推断」。
    if not out:
        for sector in policy_lexicon.sector_hints_for(text):
            if sector in policy_lexicon.INDUSTRY_LEXICONS:
                out.append({'sector': sector, 'tier': TIER_NONE,
                            'words': [], 'basis': 'hint'})
    return out


# ── 板块 → 行情板块 → 成分股（复用 sector_resonance_service 的取数适配）──

class SectorConstituentIndex:
    """canonical 板块 → 行情板块名 → 成分股（带 TTL 快照，不在扫描热路径反复外呼）。

    取数**只**经现有板块适配器（`_ManagerSectorSource`：list_sectors / get_members，
    与确认核验的共振阶段同一实现）；板块名匹配**只**用 policy_lexicon 的
    normalize/resolve/SECTOR_ALIASES——本类不持有任何板块别名数据。

    fail-open：列表/成分取不到时返回 `mapping_missing=True` + reason，
    调用方据此标 skipped（**不下结论**），绝不返回空集合冒充「该板块没有成分股」。
    """

    def __init__(self, sector_source: Any = None,
                 ttl_sec: float = SECTOR_MAP_TTL_SEC,
                 now_fn: Callable[[], datetime] = datetime.now,
                 max_boards_per_sector: int = DEFAULT_MAX_BOARDS_PER_SECTOR):
        self._sector_source = sector_source
        self._ttl = max(float(ttl_sec or SECTOR_MAP_TTL_SEC), 1.0)
        self._now = now_fn
        self._max_boards = max(int(max_boards_per_sector or 0), 1)
        self._boards: List[str] = []
        self._boards_at: Optional[datetime] = None
        self._members: Dict[str, Tuple[datetime, List[str]]] = {}
        self.degraded: bool = False
        self.last_error: Optional[str] = None

    # ── 查板块 ──────────────────────────────────────────────
    def boards_for(self, sector: Optional[str]) -> List[str]:
        """canonical 板块 → 行情板块名列表（数据源顺序；认不出返回 []）。"""
        canonical = (policy_lexicon.resolve_sector(sector)
                     or policy_lexicon.normalize_sector(sector))
        if not canonical:
            return []
        return [name for name in self._list_boards()
                if self._board_matches(name, canonical)]

    def members_for(self, sector: Optional[str]) -> Dict[str, Any]:
        """canonical 板块 → 成分股并集。

        返回 {'sector','boards','symbols': set,'missing_boards': [...],
              'mapping_missing': bool,'reason': str}
        `mapping_missing=True` 的三种情形：板块列表取不到 / 该板块认不出行情板块 /
        命中的板块成分全部取数失败。调用方必须 fail-open（skipped），不得据此判「无关」。
        """
        canonical = (policy_lexicon.resolve_sector(sector)
                     or policy_lexicon.normalize_sector(sector))
        out: Dict[str, Any] = {'sector': canonical, 'boards': [],
                               'symbols': set(), 'missing_boards': [],
                               'mapping_missing': False, 'reason': ''}
        if not canonical:
            out.update(mapping_missing=True, reason='空板块名（无法映射）')
            return out
        boards = self.boards_for(canonical)
        if not boards:
            # 兜底（2026-10-21）：行情板块认不出时，直接用 canonical 名向数据层要成分
            # ——数据层的板块成分已有「东财主源 → 新浪粗口径 → 持久化快照」三级兜底。
            fallback = self._members_of(canonical)
            if fallback:
                out.update(boards=[canonical], symbols=set(fallback), coarse=True,
                           reason='板块名未匹配行情板块，回退 canonical 成分（粗口径）')
                return out
            out.update(mapping_missing=True,
                       reason='板块映射缺失：「%s」在行情板块里认不出（fail-open，不据此判无关）'
                              % canonical)
            return out
        out['boards'] = list(boards[:self._max_boards])
        symbols: Set[str] = set()
        for board in out['boards']:
            rows = self._members_of(board)
            if rows is None:            # 该板块取数失败（不拖垮其余板块）
                out['missing_boards'].append(board)
                continue
            symbols.update(rows)
        out['symbols'] = symbols
        if not symbols:
            # 兜底（2026-10-21）：行情板块成分全部失败时，用 canonical 名再要一次
            # （走数据层的三级兜底：东财 → 新浪粗口径 → 持久化快照）。
            fallback = self._members_of(canonical)
            if fallback:
                out.update(symbols=set(fallback), coarse=True,
                           reason='行情板块成分取数失败，回退 canonical 成分（粗口径）')
                return out
            out.update(mapping_missing=True,
                       reason='板块成分取数失败（%s），fail-open 不据此判无关'
                              % ('、'.join(out['missing_boards']) or canonical))
        return out

    def refresh(self, force: bool = False) -> Dict[str, Any]:
        """清空快照（下轮重取）。返回规模供日志/用例断言。"""
        if not force and self._boards_at is not None and self._fresh(self._boards_at):
            return {'refreshed': False, 'boards': len(self._boards),
                    'members': len(self._members)}
        self._boards, self._boards_at = [], None
        self._members = {}
        return {'refreshed': True, 'boards': 0, 'members': 0}

    # ── 内部 ────────────────────────────────────────────────
    def _source(self):
        if self._sector_source is None:
            # 惰性 import + 惰性解析：模块导入不拉起 qs_market_data 重依赖
            from qs_market_data.adapters.outbound.datasources.manager import (
                get_data_provider_manager,
            )
            self._sector_source = _ManagerSectorSource(get_data_provider_manager())
        return self._sector_source

    def _fresh(self, at: Optional[datetime]) -> bool:
        if at is None:
            return False
        try:
            return (self._now() - at).total_seconds() < self._ttl
        except Exception:   # noqa: BLE001 - 时钟异常按过期处理（重取一次）
            return False

    def _list_boards(self) -> List[str]:
        if self._boards and self._fresh(self._boards_at):
            return self._boards
        try:
            source = self._source()
            names = list(source.list_sectors() or ())
        except Exception as e:  # noqa: BLE001 - fail-open：映射缺失，不炸扫描线程
            self.degraded = True
            self.last_error = '%s: %s' % (type(e).__name__, e)
            logger.warning('行情板块列表获取失败（板块路由 fail-open）',
                           error=self.last_error)
            return []
        names = [str(name).strip() for name in names if str(name or '').strip()]
        if not names:
            # 空列表不缓存：数据源偶发空返回时下一轮还有机会
            self.degraded = True
            self.last_error = '板块列表为空（数据源异常）'
            logger.warning('行情板块列表为空（板块路由 fail-open）')
            return []
        self._boards, self._boards_at = names, self._now()
        self.degraded = False
        return self._boards

    def _members_of(self, board: str) -> Optional[List[str]]:
        cached = self._members.get(board)
        if cached is not None and self._fresh(cached[0]):
            return list(cached[1])
        try:
            source = self._source()
            rows = source.get_members(board) or []
        except Exception as e:  # noqa: BLE001 - 单板块失败返回 None（调用方记 missing）
            logger.warning('板块成分获取失败（该板块按缺失处理）',
                           board=board, error='%s: %s' % (type(e).__name__, e))
            return None
        symbols: List[str] = []
        for row in rows:
            raw = _read(row, 'symbol') if isinstance(row, Mapping) else row
            sym = _bare_symbol(raw)
            if sym:
                symbols.append(sym)
        self._members[board] = (self._now(), symbols)
        return list(symbols)

    @staticmethod
    def _board_matches(board: str, canonical: str) -> bool:
        """行情板块名是否属于 canonical 板块（名称/别名/包含关系，全部查 policy_lexicon）。"""
        name = policy_lexicon.normalize_sector(board)
        if not name or not canonical:
            return False
        if name == canonical:
            return True
        resolved = policy_lexicon.resolve_sector(name)
        if resolved and resolved == canonical:
            return True
        tokens = set(_sector_tokens(canonical))
        tokens.add(canonical)
        return any(_contains_token(name, token)
                   for token in tokens if len(token) >= 2)


# ── 路由服务 ────────────────────────────────────────────────

class PolicyWatchService:
    """政策新闻 → 板块 → 成分股 → 持仓/候选池 的路由与告警（无状态，除去重记忆）。

    依赖全部构造注入（测试零外呼、零连库）：
      · news_source    —— 全市场政策新闻源（`PolicyNewsSource.fetch()`）
      · sector_index   —— 板块→成分（默认 `SectorConstituentIndex`，复用现有取数适配）
      · position_repo  —— 持仓仓储（`get_all_positions(account)`）
      · candidate_source —— 候选池成员端口（`get_members(pool_id)`；与共振核验同一口径）
      · alert_repo     —— 已报留痕（幂等键 symbol+title；与新闻监控同一张表）
      · news_service   —— 确认核验查询口（`scan_candidates(symbols)`，只读、不发卡）
      · sender         —— 发卡（默认 watch_channels.send_watch_receipt，P0/P2 既有路由）

    两个开关口径（本模块只负责路由，不自行节流）：
      · 扫描频率由装配方（factory daemon 线程）决定；
      · `max_alerts_per_scan` / `max_confirm_per_scan` 是单轮上限，防一轮扫出消息洪水。
    """

    def __init__(self, news_source: Any = None, *,
                 sector_index: Optional[SectorConstituentIndex] = None,
                 position_repo: Any = None,
                 accounts: Sequence[str] = DEFAULT_ACCOUNTS,
                 candidate_source: Any = None,
                 candidate_pool_id: int = 0,
                 alert_repo: Any = None,
                 news_service: Any = None,
                 sender: Optional[Callable[[Mapping[str, Any]], Any]] = None,
                 max_alerts_per_scan: int = DEFAULT_MAX_ALERTS_PER_SCAN,
                 max_confirm_per_scan: int = DEFAULT_MAX_CONFIRM_PER_SCAN,
                 query_memory: int = DEFAULT_QUERY_MEMORY,
                 now_fn: Callable[[], datetime] = datetime.now):
        self._news = news_source if news_source is not None else PolicyNewsSource()
        self._index = sector_index if sector_index is not None else SectorConstituentIndex()
        self._positions = position_repo
        self._accounts = tuple(accounts or ())
        self._candidates = candidate_source
        self._pool_id = int(candidate_pool_id or 0)
        self._alerts = alert_repo
        self._news_service = news_service
        self._sender = sender
        self._max_alerts = max(int(max_alerts_per_scan or 0), 0)
        self._max_confirm = max(int(max_confirm_per_scan or 0), 0)
        self._query_memory_cap = max(int(query_memory or 0), 1)
        self._queried: Dict[Tuple[str, str], None] = {}
        self._now = now_fn

    # ── 纯解析路由（单测入口，不取数、不发卡）───────────────────
    def resolve(self, records: Sequence[Mapping[str, Any]],
                holdings: Iterable[Any] = (),
                candidates: Iterable[Any] = (),
                *, now: Optional[datetime] = None) -> Dict[str, Any]:
        """新闻 → 板块 → 成分 → ∩持仓/候选池（只做解析与判定，不产生副作用）。

        返回 {'items': [...], 'alerts': [...], 'confirms': [...],
              'unrelated': n, 'skipped': n, 'mapping_missing': n, 'records': n}

        item.action 语义见 ACTION_*；`skipped` 的 reason 必须能区分「未命中词表」
        与「映射缺失」——前者是不相关，后者是不下结论（fail-open）。
        """
        held = {_bare_symbol(s) for s in (holdings or ()) if _bare_symbol(s)}
        pool = {_bare_symbol(s) for s in (candidates or ()) if _bare_symbol(s)}
        at = now or self._now()
        items: List[Dict[str, Any]] = []
        alerts: List[Dict[str, Any]] = []
        confirms: List[Dict[str, Any]] = []
        unrelated = skipped = mapping_missing = 0

        for record in records or ():
            if not isinstance(record, Mapping):
                continue
            title = _text(record.get('title'))
            base = {'title': title,
                    'time': _text(record.get('time')),
                    'source': _text(record.get('source')),
                    'url': _text(record.get('url'))}
            if not title:
                items.append(dict(base, action=ACTION_SKIPPED, tier=TIER_NONE,
                                  words=[], sectors=[], boards=[],
                                  alert_symbols=[], confirm_symbols=[],
                                  reason='空标题（不可判定）'))
                skipped += 1
                continue

            policy_tier, policy_words = policy_lexicon.classify(title, policy=True)
            hits = detect_sectors(title)
            # 词表命中但没点名板块的，只有「确实是政策新闻」才路由：
            # 「多家公司宣布扩产」命中多个板块的通用软词，不该把一屏持仓都叫起来。
            entries = [hit for hit in hits
                       if hit['basis'] == 'name' or policy_tier != TIER_NONE]
            if not entries:
                reason = ('命中政策词但未映射板块（宏观口径，本卡不路由）'
                          if policy_tier != TIER_NONE else '未命中政策/行业词表')
                items.append(dict(base, action=ACTION_SKIPPED, tier=policy_tier,
                                  words=list(policy_words), sectors=[], boards=[],
                                  alert_symbols=[], confirm_symbols=[],
                                  reason=reason))
                skipped += 1
                continue

            # 只点了板块名、没有任何政策/行业风险词（行情/复盘类）→ 不打扰，
            # 也**不必**去取板块成分（省一次外呼）。
            overall = _tier_max(policy_tier, *[hit['tier'] for hit in entries])
            if overall == TIER_NONE:
                items.append(dict(
                    base, action=ACTION_SKIPPED, tier=TIER_NONE, words=[],
                    sectors=[hit['sector'] for hit in entries], boards=[],
                    alert_symbols=[], confirm_symbols=[],
                    reason='未命中政策/行业风险词（行情/复盘类不打扰）'))
                skipped += 1
                continue

            resolved: List[Dict[str, Any]] = []
            missing: List[str] = []
            for entry in entries:
                try:
                    mapping = self._index.members_for(entry['sector'])
                except Exception as e:  # noqa: BLE001 - 映射异常 fail-open，不炸扫描
                    logger.warning('板块成分映射异常（该板块按缺失处理）',
                                   sector=entry['sector'],
                                   error='%s: %s' % (type(e).__name__, e))
                    mapping = {'mapping_missing': True, 'reason': str(e),
                               'boards': [], 'symbols': set()}
                if mapping.get('mapping_missing'):
                    missing.append(entry['sector'])
                    continue
                tier = _tier_max(policy_tier, entry['tier'])
                resolved.append({
                    'sector': entry['sector'],
                    'basis': entry['basis'],
                    'tier': tier,
                    'words': _unique(list(policy_words) + list(entry['words'])),
                    'boards': list(mapping.get('boards') or ()),
                    'symbols': set(mapping.get('symbols') or ()),
                })

            symbols: Set[str] = set()
            for entry in resolved:
                symbols |= entry['symbols']
            if not symbols:
                items.append(dict(
                    base, action=ACTION_SKIPPED,
                    tier=_tier_max(policy_tier,
                                   *[hit['tier'] for hit in entries]),
                    words=_unique(list(policy_words)
                                  + [w for hit in entries for w in hit['words']]),
                    sectors=[entry['sector'] for entry in resolved],
                    boards=[], alert_symbols=[], confirm_symbols=[],
                    mapping_missing=missing,
                    reason='板块映射缺失（fail-open，本轮不据此判定「与我无关」）'))
                skipped += 1
                mapping_missing += 1
                continue

            hit_holdings = sorted(held & symbols)
            hit_candidates = sorted((pool - held) & symbols)
            tiers = [entry['tier'] for entry in resolved]
            tier = _tier_max(policy_tier, *tiers)
            words = _unique(list(policy_words)
                            + [w for hit in entries for w in hit['words']])
            sectors = _unique(entry['sector'] for entry in resolved)
            boards = _unique(b for entry in resolved for b in entry['boards'])
            item = dict(base, tier=tier, words=words, sectors=sectors,
                        boards=boards, alert_symbols=hit_holdings,
                        confirm_symbols=hit_candidates, mapping_missing=missing)
            if hit_holdings:
                item['action'] = ACTION_ALERT
                item['reason'] = '持仓命中政策板块（%s）' % '、'.join(sectors)
            elif hit_candidates:
                item['action'] = ACTION_CONFIRM
                item['reason'] = '仅候选池命中（%s）→ 确认核验查询，不发卡' % '、'.join(sectors)
            else:
                item['action'] = ACTION_UNRELATED
                item['reason'] = '与持仓/候选池都不相交（不打扰）'
                unrelated += 1
            # 两条路由**并行**：持仓发 P0/P2 卡，候选池（且非持仓）进确认核验查询。
            # 同一只票若既是持仓又在候选池，只走持仓路由（不重复打扰）。
            for symbol in hit_holdings:
                alerts.append({'symbol': symbol, 'title': title, 'tier': tier,
                               'words': words, 'sectors': sectors,
                               'boards': boards, 'time': base['time'],
                               'url': base['url'], 'at': at.isoformat()})
            for symbol in hit_candidates:
                confirms.append({'symbol': symbol, 'title': title, 'tier': tier,
                                 'sectors': sectors, 'at': at.isoformat()})
            items.append(item)

        # 同一标的+同一标题在一轮里只留一条（源已按标题去重，这里兜底）
        alerts = _dedupe_by(alerts, ('symbol', 'title'))
        confirms = _dedupe_by(confirms, ('symbol', 'title'))
        return {'items': items, 'alerts': alerts, 'confirms': confirms,
                'unrelated': unrelated, 'skipped': skipped,
                'mapping_missing': mapping_missing, 'records': len(records or ())}

    # ── 扫描（factory daemon 线程每轮调用）──────────────────────
    def scan(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """取新闻 → 路由 → 持仓发卡 / 候选池确认核验。

        `skipped=True` 表示本轮**没有完成核验**（取数失败），不能当成「无政策利空」；
        `empty=True` 才是源健康但确实没数据。
        """
        at = now or self._now()
        out: Dict[str, Any] = {
            'scanned': True, 'at': at.isoformat(), 'skipped': False, 'reason': '',
            'empty': False, 'provider': '', 'records': 0,
            'holdings': 0, 'candidates': 0, 'degraded': False, 'target_errors': [],
            'unrelated': 0, 'skipped_items': 0, 'mapping_missing': 0,
            'alerts': [], 'alerts_failed': [], 'alerts_deduped': 0,
            'alerts_truncated': 0, 'confirm': {'queried': 0, 'skipped': False,
                                               'reason': ''},
            'items': [],
        }

        fetched = self._fetch()
        if not isinstance(fetched, Mapping):
            out.update(skipped=True, reason='新闻源返回非 Mapping（契约不符）')
            return out
        out['provider'] = _text(fetched.get('provider'))
        if fetched.get('skipped'):
            out.update(skipped=True,
                       reason=_text(fetched.get('reason')) or '政策新闻取数失败')
            logger.warning('政策盯盘扫描跳过（取数失败，fail-open）',
                           reason=out['reason'])
            return out

        records = [rec for rec in (fetched.get('records') or ())
                   if isinstance(rec, Mapping)]
        out['records'] = len(records)
        out['empty'] = bool(fetched.get('empty')) or not records
        if not records:
            out['reason'] = _text(fetched.get('reason')) or '新闻源健康但无数据'
            return out

        holdings, candidates, target_errors = self._targets()
        out['holdings'], out['candidates'] = len(holdings), len(candidates)
        out['target_errors'] = target_errors

        plan = self.resolve(records, holdings, candidates, now=at)
        # 降级标记放在 resolve 之后：板块取数是在 resolve 里发生的，
        # 提前取 index.degraded 会漏掉「本轮刚失败」。
        out['degraded'] = bool(target_errors) or bool(
            getattr(self._index, 'degraded', False))
        out['items'] = plan['items']
        out['unrelated'] = plan['unrelated']
        out['skipped_items'] = plan['skipped']
        out['mapping_missing'] = plan['mapping_missing']

        sent, failed, deduped, truncated = self._dispatch_alerts(plan['alerts'], at)
        out['alerts'] = sent
        out['alerts_failed'] = failed
        out['alerts_deduped'] = deduped
        out['alerts_truncated'] = truncated
        out['confirm'] = self._dispatch_confirms(plan['confirms'], at)

        logger.info('政策盯盘扫描完成',
                    records=out['records'], related=len(plan['alerts']),
                    alerts=len(sent), confirm=out['confirm'].get('queried'),
                    unrelated=out['unrelated'], mapping_missing=out['mapping_missing'],
                    skipped_items=out['skipped_items'])
        return out

    # ── 取数与目标集合 ──────────────────────────────────────────
    def _fetch(self) -> Mapping[str, Any]:
        try:
            result = self._news.fetch()
        except Exception as e:  # noqa: BLE001 - fail-open：取数异常不炸扫描线程
            return {'records': [], 'skipped': True,
                    'reason': '取数异常：%s: %s' % (type(e).__name__, e)}
        return result if isinstance(result, Mapping) else {}

    def _targets(self) -> Tuple[Set[str], Set[str], List[str]]:
        """持仓 ∪ 候选池（裸码集合）。失败如实记 errors，不静默当「没有持仓」。"""
        errors: List[str] = []
        holdings: Set[str] = set()
        if self._positions is not None:
            for account in self._accounts:
                try:
                    rows = self._positions.get_all_positions(account) or []
                except Exception as e:  # noqa: BLE001 - 单账户失败跳过，不炸整轮
                    errors.append('%s: %s: %s' % (account, type(e).__name__, e))
                    logger.error('持仓读取失败（该账户跳过）', account=account,
                                 error=str(e))
                    continue
                for row in rows:
                    symbol = _bare_symbol(_read(row, 'symbol'))
                    shares = _read(row, 'shares_total', 'shares')
                    try:
                        holding = float(shares or 0) > 0
                    except (TypeError, ValueError):
                        holding = False
                    if symbol and holding:
                        holdings.add(symbol)

        candidates: Set[str] = set()
        if self._candidates is not None:
            try:
                rows = self._candidates.get_members(self._pool_id) or []
            except Exception as e:  # noqa: BLE001 - 候选池失败不阻塞持仓路由
                errors.append('candidates: %s: %s' % (type(e).__name__, e))
                logger.error('候选池成员读取失败（候选口径跳过）', error=str(e))
            else:
                for row in rows:
                    symbol = _bare_symbol(_read(row, 'symbol'))
                    if symbol:
                        candidates.add(symbol)
        return holdings, candidates, errors

    # ── 发卡（持仓命中，既有 P0/P2 路由）─────────────────────────
    def _dispatch_alerts(self, alerts: Sequence[Mapping[str, Any]],
                         now: datetime) -> Tuple[List[Dict[str, Any]],
                                                 List[Dict[str, Any]], int, int]:
        sent: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        deduped = truncated = 0
        batch = list(alerts or ())
        if self._max_alerts >= 0 and len(batch) > self._max_alerts:
            truncated = len(batch) - self._max_alerts
            batch = batch[:self._max_alerts]
            logger.warning('政策盯盘单轮告警数超上限（超出部分只留日志，不发卡）',
                           total=len(alerts or ()), cap=self._max_alerts,
                           truncated=truncated)

        for alert in batch:
            symbol = _text(alert.get('symbol'))
            title = _text(alert.get('title'))
            tier = _text(alert.get('tier')) or TIER_SOFT
            if not symbol or not title:
                continue
            # 已报留痕（与新闻监控同一张表同一幂等键）：同一条政策新闻对同一标的只报一次
            if self._alerts is not None:
                try:
                    recorded = self._alerts.record(symbol, title,
                                                   list(alert.get('words') or ()),
                                                   tier)
                except Exception as e:  # noqa: BLE001 - 去重不可用时不发（避免每轮重复）
                    failed.append({'symbol': symbol, 'error': '留痕失败: %s' % e,
                                   'reason': '去重留痕不可用'})
                    logger.error('政策告警留痕失败（本轮不发，避免重复刷屏）',
                                 symbol=symbol, error=str(e))
                    continue
                if recorded is None:
                    deduped += 1
                    continue

            payload = {
                'kind': ALERT_KIND,
                'level': LEVEL_P0 if tier == TIER_CRITICAL else LEVEL_P2,
                'message': self._alert_message(symbol, alert, now),
            }
            try:
                ok = self._send(payload) if self._sender is not None else True
            except Exception as e:  # noqa: BLE001 - 单张卡失败不炸整轮
                failed.append({'symbol': symbol, 'error': str(e),
                               'reason': '发送异常'})
                logger.error('政策盯盘发卡失败', symbol=symbol, error=str(e))
                continue
            if ok:
                sent.append({'symbol': symbol, 'tier': tier,
                             'level': payload['level'],
                             'sectors': list(alert.get('sectors') or ())})
            else:
                failed.append({'symbol': symbol, 'error': '发送返回 False',
                               'reason': '未送达'})
        return sent, failed, deduped, truncated

    def _send(self, payload: Mapping[str, Any]) -> Any:
        sender = self._sender
        if sender is None:
            return True
        return sender(dict(payload))

    def _alert_message(self, symbol: str, alert: Mapping[str, Any],
                       now: datetime) -> str:
        """持仓政策卡正文（与新闻监控 news_alert 卡同风格：先说结论再说证据）。"""
        tier = _text(alert.get('tier'))
        critical = tier == TIER_CRITICAL
        label = ('🚨 政策命中持仓【强提醒】' if critical
                 else '⚠️ 政策命中持仓【关注】')
        lines = ['%s %s（%s）' % (label, symbol, now.strftime('%m-%d %H:%M')),
                 '板块：%s' % ('、'.join(alert.get('sectors') or ()) or '（未映射）')]
        boards = list(alert.get('boards') or ())
        if boards:
            lines.append('行情板块：%s' % '、'.join(boards[:5]))
        words = list(alert.get('words') or ())
        if words:
            lines.append('命中词：%s' % '、'.join(words[:8]))
        lines.append('消息：%s' % _text(alert.get('title'))[:120])
        time_text = _text(alert.get('time'))
        if time_text:
            lines.append('时间：%s' % time_text[:19])
        url = _text(alert.get('url'))
        if url:
            lines.append('链接：%s' % url[:200])
        lines.append('处置建议：%s' % (
            'critical 级先评估是否破坏原交易逻辑（必要时提前离场）' if critical
            else '先看板块是否持续发酵，再决定是否调整持仓逻辑'))
        return '\n'.join(lines)

    # ── 确认核验查询（候选池命中，只读、不发卡）──────────────────
    def _dispatch_confirms(self, confirms: Sequence[Mapping[str, Any]],
                           now: datetime) -> Dict[str, Any]:
        """候选池命中 → `NewsWatchService.scan_candidates`（候选池只读口径）。

        与持仓路由**完全隔离**：不写已报留痕、不发卡、不看窗口——
        候选池不是持仓，写进持仓留痕会让持仓扫描的幂等键提前命中而漏报
        （news_watch_service 的口径纪律）。本模块只用进程内记忆避免同一条
        政策新闻每轮重复核验同一标的。
        """
        pending: List[str] = []
        titles: Dict[str, str] = {}
        for confirm in confirms or ():
            symbol = _text(confirm.get('symbol'))
            title = _text(confirm.get('title'))
            if not symbol or not title:
                continue
            key = (symbol, title)
            if key in self._queried:
                continue
            if symbol not in pending:
                pending.append(symbol)
            titles.setdefault(symbol, title)

        if not pending:
            return {'queried': 0, 'skipped': False, 'reason': '',
                    'symbols': [], 'truncated': 0}
        truncated = 0
        if self._max_confirm >= 0 and len(pending) > self._max_confirm:
            truncated = len(pending) - self._max_confirm
            pending = pending[:self._max_confirm]

        query = getattr(self._news_service, 'scan_candidates', None)
        if not callable(query):
            return {'queried': 0, 'skipped': True,
                    'reason': '确认核验查询未装配（候选池命中未核验）',
                    'symbols': [], 'truncated': truncated}
        try:
            result = query(pending, now=now)
        except Exception as e:  # noqa: BLE001 - 核验失败如实标注，不炸扫描线程
            logger.error('候选池确认核验查询失败', symbols=pending, error=str(e))
            return {'queried': 0, 'skipped': True,
                    'reason': '确认核验查询失败：%s' % e,
                    'symbols': list(pending), 'truncated': truncated}

        for symbol in pending:
            self._remember((symbol, titles.get(symbol, '')))
        return {'queried': len(pending), 'skipped': False, 'reason': '',
                'symbols': list(pending), 'truncated': truncated,
                'result': result}

    def _remember(self, key: Tuple[str, str]) -> None:
        """进程内去重记忆（有上限，超出按插入序淘汰最旧的）。"""
        if not key[1]:
            return
        self._queried[key] = None
        while len(self._queried) > self._query_memory_cap:
            oldest = next(iter(self._queried))
            self._queried.pop(oldest, None)


def _dedupe_by(items: Sequence[Mapping[str, Any]],
               keys: Sequence[str]) -> List[Dict[str, Any]]:
    """按给定字段组合去重（保序）。"""
    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[Any, ...]] = set()
    for item in items or ():
        key = tuple(item.get(name) for name in keys)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(item))
    return out
