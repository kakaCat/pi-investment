"""消息监控服务（2026-10-20）：流程图 M/N 节点——突发消息 → 破坏逻辑评估 → 提前离场提醒

闭环：
  持仓标的（盯盘适用账户）→ 轮询新闻+公告 → 严重度词表分两级匹配 →
  已报留痕去重（同一条只报一次）→ 发卡到盯盘群（critical 即时单发 / soft 聚合弱提醒）→
  agent/用户评估「是否破坏交易逻辑」并决策（盯盘不直连交易，铁律不变）。

运行窗口：工作日 08:00-22:00（公告常在盘后发布，次日决策要用）。
节流：默认 15 分钟一轮（env WATCH_NEWS_SCAN_INTERVAL_SEC），sidecar 每次拍都调用、
服务内部到期才真扫——与走势回填同款纪律。

两种口径（2026-10-20 · 机会闭环 M2 二次核验）：
  · scan()：持仓口径——节流 + 已报留痕 + 发卡，行为与初版一致；
  · scan_candidates() / query_negative_news()：候选池口径（只读）——不看窗口、不做节流、
    不写已报留痕、不发卡，供确认核验流水线随时问「这只票有没有突发利空」。
    候选池不是持仓：把候选池命中写进持仓留痕，会让持仓扫描的幂等键提前命中而漏报，
    等于悄悄改了口径，故候选池模式与持仓留痕完全隔离。

取数失败不炸：单标的失败记日志跳过（下轮重试），整轮失败向上抛（sidecar 记错）。

词表配置化（2026-10-21）：分级词表已收进 `policy_lexicon`（配置数据，不是散落判断）——
个股 / 政策 / 行业三套口径共用同一份分级实现。本模块的 CRITICAL_WORDS / SOFT_WORDS /
NOISE_WORDS 是**个股词表的转发别名**（词表逐字不变，既有调用方与用例不受影响），
classify() 默认仍走个股口径、行为与初版逐字一致；需要政策/行业口径时给
`classify(title, sector=..., policy=True)` 或直接注入 `policy_lexicon.Lexicon`。
"""
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import structlog

from qs_watch.application.services.watch_engine import policy_lexicon

logger = structlog.get_logger(__name__)

#: 个股强提醒词（= policy_lexicon.STOCK_CRITICAL，2026-10-20 初版词表逐字保留）
CRITICAL_WORDS = policy_lexicon.STOCK_CRITICAL
#: 个股弱提醒词（= policy_lexicon.STOCK_SOFT）
SOFT_WORDS = policy_lexicon.STOCK_SOFT
#: 个股噪声词（= policy_lexicon.STOCK_NOISE）
NOISE_WORDS = policy_lexicon.STOCK_NOISE

#: 严重度排序（critical 压过 soft）；持仓扫描取最高 tier 的口径与此同源
_TIER_ORDER = policy_lexicon.TIER_ORDER

DEFAULT_ACCOUNTS = ('agent_virtual', 'agent_brain', 'user_main_simulation')
DEFAULT_INTERVAL_SEC = 900.0

MODE_HELD = 'held'
MODE_CANDIDATE_POOL = 'candidate_pool'


def _interval() -> float:
    try:
        return max(60.0, float(os.getenv('WATCH_NEWS_SCAN_INTERVAL_SEC',
                                         str(DEFAULT_INTERVAL_SEC))))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SEC


def classify(title: str, lexicon=None, *, sector: Optional[str] = None,
             policy: bool = False, include_stock: bool = False) -> tuple:
    """标题分两级：返回 (tier, [命中词])。tier ∈ critical|soft|none。

    2026-10-21 词表可注入：lexicon 给 `policy_lexicon.Lexicon`（或
    {critical,soft,noise} 字典）即用该词表；也可按 sector / policy 选口径。
    **不传任何词表时走个股词表，行为与初版逐字一致**（既有用例即契约）。
    """
    return policy_lexicon.classify(title, lexicon, sector=sector, policy=policy,
                                   include_stock=include_stock)


def in_scan_window(now: datetime) -> bool:
    """工作日 08:00-22:00（盘后公告也要接，次日开盘前决策）。"""
    return now.weekday() < 5 and 8 <= now.hour < 22


class NewsWatchService:
    """持仓消息监控（无状态；来源/留痕/持仓/发送器构造注入）。

    词表口径（2026-10-21）：默认个股词表（行为与初版逐字一致）；要扫政策/行业口径时
    注入 `lexicon=`（优先）或 `sector=` / `policy=True`，判定走 policy_lexicon 同一实现。
    """

    def __init__(self, news_source, alert_repo, position_repo,
                 accounts=DEFAULT_ACCOUNTS, sender: Optional[Callable] = None,
                 interval_sec: Optional[float] = None,
                 lexicon: Any = None, sector: Optional[str] = None,
                 policy: bool = False, bridge: Any = None):
        self._news = news_source
        self._alerts = alert_repo
        self._positions = position_repo
        self._accounts = tuple(accounts)
        self._sender = sender
        self._interval = float(interval_sec) if interval_sec else _interval()
        self._last_scan_at: Optional[datetime] = None
        self._lexicon = lexicon
        self._sector = sector
        self._policy = bool(policy)
        # 消息 → P1 待办桥（REQ-261021194640-69b8 FR-3）。未注入 = 只发卡（旧行为）。
        self._bridge = bridge

    # ── 词表口径 ────────────────────────────────────────────
    def _active_lexicon(self):
        """本轮扫描用的词表；未注入任何口径时返回 None（= 个股默认，行为逐字不变）。"""
        if self._lexicon is not None:
            return self._lexicon
        if self._policy or self._sector:
            return policy_lexicon.lexicon_for(self._sector, policy=self._policy)
        return None

    # ── 主入口（sidecar 每拍调用，内部节流）────────────────────
    def scan(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now()
        if not in_scan_window(now):
            return {'scanned': False, 'reason': '非扫描窗口（工作日 08:00-22:00）'}
        if (self._last_scan_at is not None
                and (now - self._last_scan_at).total_seconds() < self._interval):
            return {'scanned': False, 'reason': '节流中',
                    'last_scan_at': self._last_scan_at.isoformat()}
        self._last_scan_at = now

        symbols = self._held_symbols()
        reported, skipped, errors = [], [], 0
        for sym in symbols:
            try:
                items = self._fetch_news(sym, limit=15)
            except Exception as e:  # noqa: BLE001 - 单标的失败不炸整轮
                errors += 1
                logger.error('新闻获取失败（跳过该标的）', symbol=sym, error=str(e))
                continue
            fresh, hits = self._classify_fresh(
                items, now, self._active_lexicon())
            # 每标的每轮最多报 1 张卡（critical 优先，只报最高 tier）
            if not hits:
                skipped.append(sym)
                continue
            hits.sort(key=lambda h: _TIER_ORDER[h['tier']])
            top_tier = hits[0]['tier']
            picked = [h for h in hits if h['tier'] == top_tier][:5]
            # 逐条幂等留痕（已报过的跳过）
            new_hits = []
            for h in picked:
                rec = self._alerts.record(sym, h['item']['title'],
                                          h['words'], h['tier'])
                if rec is not None:
                    new_hits.append(h)
            if not new_hits:
                skipped.append(sym)
                continue
            if self._send(sym, new_hits, now):
                reported.append({'symbol': sym, 'tier': top_tier,
                                 'count': len(new_hits),
                                 'titles': [h['item']['title'][:40] for h in new_hits]})
                self._dispatch_bridge(sym, top_tier, new_hits)

        out = {'scanned': True, 'symbols': len(symbols), 'reported': len(reported),
               'details': reported, 'skipped': len(skipped), 'errors': errors,
               'at': now.isoformat()}
        logger.info('消息监控扫描完成', **{k: out[k] for k in
                    ('symbols', 'reported', 'skipped', 'errors')})
        return out

    # ── 候选池口径（机会闭环 M2 二次核验；只读，不碰持仓留痕）──────
    def query_negative_news(self, symbol: str, now: Optional[datetime] = None,
                            limit: int = 15) -> Dict[str, Any]:
        """单标的利空查询（只读，供二次核验当闸用）。

        与 scan() 的差别：不看运行窗口、不做节流、不写已报留痕、不发卡——
        核验流水线可以随时问「这只票现在有没有突发利空」，反复问同一标的不改变任何状态。

        返回：
          symbol / has_negative（任一命中即 True，含 soft）/
          tier（最高一级：critical > soft > none）/
          hits（最高 tier 至多 5 条，带 title/words/time/source/url）/
          checked（48h 内参与判定的条数）/ total（取回条数）/
          skipped / error —— 取数失败时 skipped=True、error=原文、
          has_negative=False（fail-open：不因取数故障冤枉标的，交由调用方标注「未核验」）。
        """
        now = now or datetime.now()
        bare = str(symbol or '').split('.')[0]
        out = {'symbol': bare, 'has_negative': False, 'tier': 'none', 'hits': [],
               'checked': 0, 'total': 0, 'skipped': False, 'error': None,
               'at': now.isoformat()}
        if not bare:
            out['skipped'] = True
            out['error'] = '空标的'
            return out
        try:
            items = self._fetch_news(bare, limit=limit)
        except Exception as e:  # noqa: BLE001 - 取数失败不影响调用方继续核验其它项
            logger.error('利空查询取数失败', symbol=bare, error=str(e))
            out['skipped'] = True
            out['error'] = str(e)
            return out
        fresh, hits = self._classify_fresh(items, now, self._active_lexicon())
        out['total'] = len(items)
        out['checked'] = len(fresh)
        if not hits:
            return out
        hits.sort(key=lambda h: _TIER_ORDER[h['tier']])
        top_tier = hits[0]['tier']
        picked = [h for h in hits if h['tier'] == top_tier][:5]
        out['has_negative'] = True
        out['tier'] = top_tier
        out['hits'] = [{'title': str(h['item'].get('title') or ''),
                        'tier': h['tier'], 'words': list(h['words']),
                        'time': str(h['item'].get('time') or ''),
                        'source': str(h['item'].get('source') or ''),
                        'url': str(h['item'].get('url') or '')}
                       for h in picked]
        return out

    def scan_candidates(self, symbols, now: Optional[datetime] = None,
                        limit: int = 15) -> Dict[str, Any]:
        """候选池标的扫描模式（只读）：批量查给定标的的突发利空。

        · 不读持仓（position_repo 可为 None）、不写留痕、不发卡——候选池命中若写进
          持仓留痕，会让持仓扫描的幂等键提前命中而漏报，故与持仓口径完全隔离；
        · 单标的取数失败只计入 skipped 并在明细里带 error，不炸整轮；
        · symbols 可给列表或单个代码字符串（'300750.SZ'），标的去重并统一成
          裸代码（'300750.SZ' → '300750'），空值忽略。

        返回 {scanned, mode: 'candidate_pool', symbols, negative, critical, soft,
              clean, skipped, details, at}；details 是逐标的的
              query_negative_news 结果（含 hits，可直接归档失败样本理由）。
        """
        if isinstance(symbols, str):   # 单个代码字符串不该被逐字符拆开
            symbols = [symbols]
        now = now or datetime.now()
        uniq: List[str] = []
        for s in (symbols or []):
            bare = str(s or '').split('.')[0]
            if bare and bare not in uniq:
                uniq.append(bare)

        details = [self.query_negative_news(sym, now=now, limit=limit)
                   for sym in uniq]
        critical = sum(1 for r in details if r['tier'] == 'critical')
        soft = sum(1 for r in details if r['tier'] == 'soft')
        skipped = sum(1 for r in details if r['skipped'])
        out = {'scanned': True, 'mode': MODE_CANDIDATE_POOL,
               'symbols': len(uniq), 'negative': critical + soft,
               'critical': critical, 'soft': soft,
               'clean': len(uniq) - critical - soft - skipped,
               'skipped': skipped, 'details': details, 'at': now.isoformat()}
        logger.info('候选池消息扫描完成', **{k: out[k] for k in
                    ('symbols', 'negative', 'critical', 'soft', 'skipped')})
        return out

    # ── 内部 ────────────────────────────────────────────────
    def _fetch_news(self, symbol: str, limit: int = 15) -> List[Dict[str, Any]]:
        return self._news.fetch_news(symbol, limit=limit) or []

    @staticmethod
    def _classify_fresh(items: List[Dict[str, Any]], now: datetime,
                        lexicon=None) -> tuple:
        """48h 内新鲜条目 + 分级命中列表（持仓/候选池两种口径共用同一套词表判定）。

        lexicon=None 时走个股默认词表（行为与初版逐字一致）。
        """
        fresh = [it for it in items if NewsWatchService._fresh(it, now)]
        hits = []
        for it in fresh:
            tier, words = classify(it.get('title'), lexicon)
            if tier != 'none':
                hits.append({'item': it, 'tier': tier, 'words': words})
        return fresh, hits

    def _held_symbols(self) -> List[str]:
        if self._positions is None:
            return []
        out = []
        for acct in self._accounts:
            try:
                rows = self._positions.get_all_positions(acct) or []
            except Exception as e:  # noqa: BLE001
                logger.error('持仓读取失败（该账户跳过）', account=acct, error=str(e))
                continue
            for p in rows:
                shares = (getattr(p, 'shares_total', None)
                          or (p.get('shares_total') if isinstance(p, dict) else 0))
                sym = (getattr(p, 'symbol', None)
                       or (p.get('symbol') if isinstance(p, dict) else ''))
                if shares and sym:
                    bare = str(sym).split('.')[0]
                    if bare not in out:
                        out.append(bare)
        return out

    def _dispatch_bridge(self, symbol: str, tier: str, hits: List[Dict[str, Any]]) -> None:
        """critical 命中 → 建 P1 待办并唤醒；桥未注入/失败都不影响发卡。"""
        if self._bridge is None or str(tier or '').lower() != 'critical':
            return
        try:
            self._bridge.dispatch([{
                'tier': 'critical',
                'symbol': symbol,
                'account': self._account_of(symbol),
                'titles': [h['item']['title'] for h in hits],
                'words': [w for h in hits for w in (h.get('words') or [])],
                'source': 'news',
            }])
        except Exception as e:  # noqa: BLE001 - 建单失败不回噬扫描/发卡
            logger.error('消息待办分派失败（发卡已生效）', symbol=symbol, error=str(e))

    def _account_of(self, symbol: str) -> Optional[str]:
        """持仓账户解析：同标的多账户时取第一个（归属路由口径与引擎一致）。"""
        if self._positions is None:
            return None
        bare = str(symbol or '').split('.')[0]
        for acct in self._accounts:
            try:
                rows = self._positions.get_all_positions(acct) or []
            except Exception:  # noqa: BLE001
                continue
            for p in rows:
                sym = getattr(p, 'symbol', None) or (p.get('symbol') if isinstance(p, dict) else '')
                if str(sym).split('.')[0] == bare:
                    return acct
        return None

    @staticmethod
    def _fresh(item: Dict[str, Any], now: datetime) -> bool:
        """48 小时内的新闻/公告才算突发（老公告匹配词再狠也是旧闻）。"""
        raw = str(item.get('time') or '').strip()
        if not raw:
            return True   # 无时间戳：保守视为新鲜（宁可多报一次，靠留痕去重）
        ts = None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%d %H:%M'):
            try:
                ts = datetime.strptime(raw[:19], fmt)
                break
            except ValueError:
                continue
        if ts is None:
            return True
        if ts.year < 2000:
            return False
        return ts >= now - timedelta(hours=48)

    def _send(self, sym: str, hits: List[Dict[str, Any]], now: datetime) -> bool:
        """发卡到盯盘群；sender 缺失或未注入时只留痕不发（行为可观测）。"""
        if self._sender is None:
            logger.info('消息监控命中（未注入 sender，只留痕）', symbol=sym,
                        tier=hits[0]['tier'])
            return True
        tier = hits[0]['tier']
        label = ('🚨 持仓突发【强提醒】' if tier == 'critical'
                 else '⚠️ 持仓消息【关注】')
        lines = ['%s %s（%s）' % (label, sym, now.strftime('%m-%d %H:%M')),
                 '以下消息可能%s，请评估是否破坏原交易逻辑：'
                 % ('**直接破坏交易逻辑**' if tier == 'critical' else '影响持仓逻辑')]
        for h in hits:
            words = '、'.join(h['words'])
            lines.append('• [%s] %s' % (words, h['item']['title'][:80]))
        lines.append('处置建议：critical 级先评估提前离场；soft 级结合走势再定。')
        try:
            return bool(self._sender({'kind': 'news_alert', 'message': '\n'.join(lines),
                                      'level': 'P0' if tier == 'critical' else 'P2'}))
        except Exception as e:  # noqa: BLE001 - 发送失败留痕已在，不炸主流程
            logger.error('消息监控发卡失败', symbol=sym, error=str(e))
            return False
