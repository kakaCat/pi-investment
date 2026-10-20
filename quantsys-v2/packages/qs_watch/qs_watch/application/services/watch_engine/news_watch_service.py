"""消息监控服务（2026-10-20）：流程图 M/N 节点——突发消息 → 破坏逻辑评估 → 提前离场提醒

闭环：
  持仓标的（盯盘适用账户）→ 轮询新闻+公告 → 严重度词表分两级匹配 →
  已报留痕去重（同一条只报一次）→ 发卡到盯盘群（critical 即时单发 / soft 聚合弱提醒）→
  agent/用户评估「是否破坏交易逻辑」并决策（盯盘不直连交易，铁律不变）。

运行窗口：工作日 08:00-22:00（公告常在盘后发布，次日决策要用）。
节流：默认 15 分钟一轮（env WATCH_NEWS_SCAN_INTERVAL_SEC），sidecar 每次拍都调用、
服务内部到期才真扫——与走势回填同款纪律。

取数失败不炸：单标的失败记日志跳过（下轮重试），整轮失败向上抛（sidecar 记错）。
"""
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 强提醒词：可能直接破坏交易逻辑的事件（2026-10-20 初版词表，可调）
CRITICAL_WORDS = (
    '立案', '退市', '爆雷', '违规', '处罚', '罚款', '破产', '债务违约', '逾期',
    '巨亏', '商誉减值', '清仓式减持', '强制平仓', '爆仓', 'st风险', '退市风险',
    '暂停上市', '终止上市', '重大诉讼', '实控人失联', '资金占用', '违规担保',
)
#: 弱提醒词：需要关注但未必破坏逻辑
SOFT_WORDS = (
    '减持', '问询函', '警示函', '监管函', '质押', '亏损', '预亏', '裁员',
    '高管辞职', '高管离职', '解禁', '定增', '再融资', '关联交易', '变更会计师',
)
#: 噪声词：标题含这些时降权（业绩说明/回复类公告通常已消化）
NOISE_WORDS = ('业绩说明会', '调研', '回复关注函', '补充公告', '更正公告',
               '摘要', '英文版')

DEFAULT_ACCOUNTS = ('agent_virtual', 'agent_brain', 'user_main_simulation')
DEFAULT_INTERVAL_SEC = 900.0


def _interval() -> float:
    try:
        return max(60.0, float(os.getenv('WATCH_NEWS_SCAN_INTERVAL_SEC',
                                         str(DEFAULT_INTERVAL_SEC))))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SEC


def classify(title: str) -> tuple:
    """标题分两级：返回 (tier, [命中词])。tier ∈ critical|soft|none。"""
    t = str(title or '')
    if any(w in t for w in NOISE_WORDS) and not any(w in t for w in CRITICAL_WORDS):
        return 'none', []
    hits = [w for w in CRITICAL_WORDS if w in t]
    if hits:
        return 'critical', hits
    hits = [w for w in SOFT_WORDS if w in t]
    if hits:
        return 'soft', hits
    return 'none', []


def in_scan_window(now: datetime) -> bool:
    """工作日 08:00-22:00（盘后公告也要接，次日开盘前决策）。"""
    return now.weekday() < 5 and 8 <= now.hour < 22


class NewsWatchService:
    """持仓消息监控（无状态；来源/留痕/持仓/发送器构造注入）。"""

    def __init__(self, news_source, alert_repo, position_repo,
                 accounts=DEFAULT_ACCOUNTS, sender: Optional[Callable] = None,
                 interval_sec: Optional[float] = None):
        self._news = news_source
        self._alerts = alert_repo
        self._positions = position_repo
        self._accounts = tuple(accounts)
        self._sender = sender
        self._interval = float(interval_sec) if interval_sec else _interval()
        self._last_scan_at: Optional[datetime] = None

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
                items = self._news.fetch_news(sym, limit=15) or []
            except Exception as e:  # noqa: BLE001 - 单标的失败不炸整轮
                errors += 1
                logger.error('新闻获取失败（跳过该标的）', symbol=sym, error=str(e))
                continue
            fresh = [it for it in items if self._fresh(it, now)]
            hits = []
            for it in fresh:
                tier, words = classify(it['title'])
                if tier != 'none':
                    hits.append({'item': it, 'tier': tier, 'words': words})
            # 每标的每轮最多报 1 张卡（critical 优先，只报最高 tier）
            if not hits:
                skipped.append(sym)
                continue
            tier_order = {'critical': 0, 'soft': 1}
            hits.sort(key=lambda h: tier_order[h['tier']])
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

        out = {'scanned': True, 'symbols': len(symbols), 'reported': len(reported),
               'details': reported, 'skipped': len(skipped), 'errors': errors,
               'at': now.isoformat()}
        logger.info('消息监控扫描完成', **{k: out[k] for k in
                    ('symbols', 'reported', 'skipped', 'errors')})
        return out

    # ── 内部 ────────────────────────────────────────────────
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
