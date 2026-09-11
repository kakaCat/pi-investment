"""事件领域服务：归并去重 / 影响判定 / 重要度推断 / 多源合并裁决（RFC 015 §3.1-§3.3）

严格的领域层：**零 I/O、零外部依赖**（不 import requests/akshare/ORM/adapters），
输入是 provider 的原始行（dict）或领域对象，输出是领域对象 + 分歧记录。可独立单测。

四条规则（可质疑，故写清判据）：

R1 证据哈希（evidence_hash）——幂等去重的唯一锚
   hash = sha1(scope | type | 标的集合(升序) | effective_date | normalize_title(title))[:32]
   归一化做三件事：①去掉公司名前缀（"中国船舶:" / "中国船舶工业股份有限公司关于"）；
   ②去掉空白与常见标点；③全角转半角。**不做**语义改写——标题不同的两条公告就是两条事件，
   宁可多留一条，也不要把两件事合并成一件（合并错了会让排雷漏掉风险）。

R2 归并去重（dedupe）
   同一 evidence_hash 只保留**源权威度最高**的一条（巨潮 90 > 证监会 85 > 国务院 80 >
   东财 60 > akshare 50 > 人工 40 > DB 20）。权威度相同时保留先出现者（provider 注册顺序即优先级）。

R3 多源同一事件合并（merge）——RFC §3.3 交叉校验
   不同源的标题不会逐字相同（实测：东财「中国船舶:关于北海造船厂一货轮火灾事故有关情况的公告」
   vs 巨潮「中国船舶工业股份有限公司关于北海造船厂一货轮火灾事故有关情况的公告」），
   故先按 (type, effective_date, symbols) 分桶，再在桶内按标题相似度（difflib 比值 ≥ 0.62）聚类。
   同一簇内保留权威源，**其余源的差异（标题/链接/日期）写入 SourceDivergence**——
   不静默丢弃：分歧本身是信息（法定披露与聚合源的日期不一致时，应以法定披露为准并留痕）。

R4 重要度推断（infer_importance）
   1 低 / 2 中 / 3 高。判据是"这件事能不能改变持仓决策"，不是"新闻热度"：
   - 3：解禁占比高、定增/重大资产重组、监管处罚/立案、财报（个股）；国务院/部委重大政策（宏观）
   - 2：股东会、分红、诉讼仲裁、一般政策
   - 1：其余（业绩说明会、投资者关系活动等）
   provider 显式给 importance 时以其为准（provider 更了解自己的口径），本规则只补 None。
"""
import difflib
import hashlib
import logging
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from domain.events.model import (
    AUTHORITY_MANUAL, EventScope, EventType, MarketEvent, SourceDivergence,
)

logger = logging.getLogger(__name__)

# 标题相似度阈值：同一 (type, 日期, 标的) 桶内，超过该值判为"同一事件"
MERGE_TITLE_SIMILARITY = 0.62

# 公司名前缀（归一化时剥离；实测两源差异正在此处）
_COMPANY_PREFIX = re.compile(
    r'^[\u4e00-\u9fa5A-Za-z0-9（）()·*\s]{2,30}?(?:股份有限公司|集团有限公司|有限公司|公司|集团)?\s*[:：]'
)
# "XX关于…的公告" 形式的引导语（巨潮全称写法）
_ABOUT_PREFIX = re.compile(r'^[\u4e00-\u9fa5A-Za-z0-9（）()·*\s]{2,40}?(?:关于|就)')
_PUNCT = re.compile(r'[\s\u3000\-—－_/\\|,，.。;；:：!！?？"\'“”‘’()（）\[\]【】<>《》]+')
_FULLWIDTH = {ord(c): ord(d) for c, d in zip('０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ',
                                             '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')}

# ── 事件类型关键词（顺序即优先级：先匹到先定；不放"公司"这种高频词）──────────
_TYPE_KEYWORDS: List[Tuple[EventType, Tuple[str, ...]]] = [
    (EventType.UNLOCK, ('解除限售', '限售股上市流通', '限售股份上市流通', '解禁', '限售流通')),
    (EventType.PLACEMENT, ('向特定对象发行', '非公开发行', '可转换公司债券', '配股', '定增',
                           '发行股票', '募集资金', '向不特定对象发行')),
    # ⚠️ 词表纪律（2026-09-11 实测）：'业绩预增/预减/预盈/预亏' 是公告标题里的实际用词，
    # 只写 '业绩预告' 会把「2026年半年度业绩预增公告」判成 other（实测），漏掉财报类事件。
    (EventType.EARNINGS, ('业绩预告', '业绩预增', '业绩预减', '业绩预盈', '业绩预亏', '业绩快报',
                          '年度报告', '半年度报告', '季度报告', '财务会计报告', '主要经营数据',
                          '业绩说明会')),
    (EventType.DIVIDEND, ('利润分配', '分红', '派息', '权益分派', '转增', '除权除息')),
    (EventType.SHAREHOLDER_MEETING, ('股东大会', '股东会', '持有人会议')),
    (EventType.REGULATORY, ('问询函', '关注函', '监管函', '行政处罚', '立案调查', '纪律处分',
                            '诉讼', '仲裁', '风险提示', '退市风险', '重大事故', '事故',
                            '警示函', '整改', '违规', '被处罚', '重大违法')),
    # ⚠️ 词表纪律（2026-09-11 **两轮**实测踩坑，务必保留本注释）：
    # ① 不得含"公告/决定/规定"——任意公告都带这些词，实测把"…火灾事故有关情况的公告"判成 policy；
    # ② 也不得含"通知/管理办法/条例/规划"——公司公告大量使用（实测 14 条被误判，如
    #    "关于获得《药品补充申请批准通知书》的公告"、"…高级管理人员薪酬管理办法"）。
    # 因此 POLICY 词表**只保留发行主体名**（这些词出现在公司公告标题里几乎只可能是政策文件）。
    # 政策类 provider 本身会显式给 type='policy'，本词表只是标题层的兜底。
    (EventType.POLICY, ('国务院', '中共中央', '发展改革委', '国家发改委', '证监会', '财政部',
                        '工业和信息化部', '人民银行', '海关总署', '国家能源局', '税务总局',
                        '市场监管总局', '指导意见', '政策文件')),
]

# ── 范围判定（政策类文本 → 宏观/行业）─────────────────────────────
_INDIVIDUAL_HINTS = ('公司', '本行', '本公司', '控股子公司', '证券', '股份')

_HIGH_IMPACT_INDUSTRIES = ('半导体', '集成电路', '新能源', '光伏', '锂电', '军工', '航空航天',
                           '房地产', '银行', '保险', '券商', '医药', '农业', '粮食', '电力',
                           '煤炭', '钢铁', '汽车', '算力', '人工智能')


def normalize_title(title: str) -> str:
    """标题归一化（用于 evidence_hash 与相似度比对，**不改变原文**）

    实测依据（2026-09-11 打样）：
      东财：中国船舶:关于北海造船厂一货轮火灾事故有关情况的公告
      巨潮：中国船舶工业股份有限公司关于北海造船厂一货轮火灾事故有关情况的公告
    两者剥掉公司名前缀与标点后一致 → 归一化后可作为同一事件的锚。
    """
    text = str(title or '').translate(_FULLWIDTH).strip()
    for _ in range(2):  # 可能同时有"XX公司:"与"XX关于"，剥两轮
        before = text
        text = _COMPANY_PREFIX.sub('', text)
        text = _ABOUT_PREFIX.sub('', text)
        if text == before:
            break
    text = _PUNCT.sub('', text)
    return text.lower()


def compute_evidence_hash(scope, type_, symbols: Sequence[str], effective_date: str, title: str) -> str:
    """证据哈希（R1）：同一锚的事件 hash 相同 → 幂等去重的依据"""
    scope_v = EventScope.parse(scope).value
    type_v = EventType.parse(type_).value
    sym = ';'.join(sorted(str(s).strip() for s in (symbols or []) if str(s).strip()))
    key = '|'.join([scope_v, type_v, sym, str(effective_date or '').strip()[:10], normalize_title(title)])
    return hashlib.sha1(key.encode('utf-8')).hexdigest()[:32]


def infer_event_type(title: str, default: EventType = EventType.OTHER) -> EventType:
    """标题 → 事件类型（关键词优先，匹不到返回 default）

    为什么不用更聪明的模型：事件类型直接驱动"要不要挂盯盘规则/要不要排除持仓"，
    一旦误判就是资金风险。关键词表可审计、可复现，误判也能定位到具体词条。
    """
    text = str(title or '')
    if not text.strip():
        return default
    for event_type, keywords in _TYPE_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return event_type
    return default


def infer_scope(title: str, type_: EventType, symbols: Sequence[str]) -> EventScope:
    """推断事件范围：有标的 → 个股；政策类无标的 → 宏观/行业"""
    if symbols:
        return EventScope.INDIVIDUAL
    if type_ in (EventType.POLICY,):
        text = str(title or '')
        if any(h in text for h in _HIGH_IMPACT_INDUSTRIES) or ('行业' in text and '全行业' not in text):
            return EventScope.INDUSTRY
        return EventScope.MACRO
    return EventScope.MACRO


def infer_importance(scope, type_, title: str = '', symbols: Sequence[str] = (),
                     extra: Optional[Dict] = None) -> int:
    """重要度推断（R4）：只有 provider 未给出 importance 时才调用"""
    scope_v = EventScope.parse(scope)
    type_v = EventType.parse(type_)
    text = str(title or '')
    extra = extra or {}

    if type_v in (EventType.EARNINGS, EventType.UNLOCK, EventType.PLACEMENT):
        # 财报/解禁/定增：直接影响持仓与流动性 → 默认 3（解禁按占比降级见下）
        if type_v == EventType.UNLOCK:
            ratio = extra.get('ratio') or extra.get('占流通市值比例')
            try:
                ratio_f = float(ratio)
            except (TypeError, ValueError):
                ratio_f = None
            if ratio_f is not None and ratio_f < 0.01:      # 解禁占比 <1% 流通市值：影响有限
                return 2
            return 3
        return 3
    if type_v == EventType.REGULATORY:
        if any(k in text for k in ('立案', '处罚', '退市', '重大违法', '重大事故')):
            return 3
        return 2
    if type_v == EventType.DIVIDEND:
        return 2
    if type_v == EventType.SHAREHOLDER_MEETING:
        return 2
    if type_v == EventType.POLICY:
        if scope_v == EventScope.INDUSTRY or any(h in text for h in _HIGH_IMPACT_INDUSTRIES):
            return 3 if any(h in text for h in _HIGH_IMPACT_INDUSTRIES) else 2
        if any(k in text for k in ('国务院', '中共中央', '发展改革委', '证监会')):
            return 3
        return 2
    return 1


class MarketEventService:
    """事件领域规则（纯计算，无 I/O）"""

    # ---------------------------------------------------------------- 行 → 领域

    def build_event(self, row: Dict) -> MarketEvent:
        """provider 行契约 → MarketEvent（缺 effective_date 直接抛错，不编造日期）"""
        symbols = [str(s).strip() for s in (row.get('symbols') or []) if str(s).strip()]
        title = str(row.get('title') or '').strip()
        if not title:
            raise ValueError(f"事件行缺 title：{row!r}")
        explicit_type = row.get('type')
        try:
            event_type = EventType.parse(explicit_type) if explicit_type else infer_event_type(title)
        except ValueError:
            event_type = infer_event_type(title)
        scope_raw = row.get('scope')
        if scope_raw:
            scope = EventScope.parse(scope_raw)
        else:
            scope = infer_scope(title, event_type, symbols)
        effective = str(row.get('effective_date') or row.get('announce_date') or '').strip()[:10]
        if not effective:
            raise ValueError(f"事件行缺 effective_date（拒绝用今天兜底）：{title}")
        importance = row.get('importance')
        if importance is None:
            importance = infer_importance(scope, event_type, title, symbols, row.get('raw'))
        evidence = str(row.get('evidence_hash') or '').strip() or compute_evidence_hash(
            scope, event_type, symbols, effective, title)
        return MarketEvent(
            event_id=evidence[:16],
            scope=scope,
            type=event_type,
            title=title,
            effective_date=effective,
            announce_date=str(row.get('announce_date') or '').strip()[:10],
            importance=int(importance),
            symbols=symbols,
            industries=[str(i) for i in (row.get('industries') or []) if str(i).strip()],
            source=str(row.get('source') or ''),
            url=str(row.get('url') or ''),
            summary=str(row.get('summary') or ''),
            raw=row.get('raw') if isinstance(row.get('raw'), dict) else {},
            evidence_hash=evidence,
            authority=int(row.get('authority') or 0),
        )

    def parse_rows(self, rows: Iterable[Dict]) -> Tuple[List[MarketEvent], List[Dict]]:
        """行集合 → 领域对象集合

        Returns:
            (events, rejected)——rejected 是**如实回报**的丢弃行（缺日期/缺标题等），
            绝不静默吞掉：丢弃量异常通常意味着上游改版（列名变了）。
        """
        events: List[MarketEvent] = []
        rejected: List[Dict] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                events.append(self.build_event(row))
            except Exception as exc:  # noqa: BLE001 —— 单行坏数据不应炸掉整批
                rejected.append({'reason': f'{type(exc).__name__}: {exc}',
                                 'title': str(row.get('title') or '')[:80],
                                 'source': str(row.get('source') or '')})
        return events, rejected

    # ------------------------------------------------------------ R2 归并去重

    @staticmethod
    def dedupe(events: Iterable[MarketEvent]) -> List[MarketEvent]:
        """R2：同一 evidence_hash 保留权威度最高者（同权威度保留先出现者）"""
        best: Dict[str, MarketEvent] = {}
        for event in events:
            key = event.evidence_hash or event.event_id
            current = best.get(key)
            if current is None or event.authority > current.authority:
                best[key] = event
        return list(best.values())

    @staticmethod
    def affects(events: Iterable[MarketEvent], symbol: str) -> List[MarketEvent]:
        """影响判定（委托 MarketEvent.affects，此处提供集合级入口）"""
        return [e for e in events if e.affects(symbol)]

    # ------------------------------------------------------------ R3 多源合并

    def merge(self, events: Sequence[MarketEvent]) -> Tuple[List[MarketEvent], List[SourceDivergence]]:
        """R3：多源同一事件合并（保留权威源，差异记入 SourceDivergence）

        步骤：①按 (type, effective_date, symbols) 分桶；
             ②桶内按标题相似度 ≥ MERGE_TITLE_SIMILARITY 聚类（贪心，与簇首比较）；
             ③每簇保留 authority 最大者，其余写入 divergence.dropped。
        分桶键含 symbols 而非 title：两源对同一公告的标题差异最大，正好不能用 title 当键。
        """
        merged: List[MarketEvent] = []
        divergences: List[SourceDivergence] = []

        buckets: Dict[Tuple[str, str, str], List[MarketEvent]] = {}
        for event in events:
            key = (event.type.value, event.effective_date, ';'.join(sorted(event.symbols)))
            buckets.setdefault(key, []).append(event)

        for key, bucket in buckets.items():
            used = [False] * len(bucket)
            bucket_sorted = sorted(bucket, key=lambda e: e.authority, reverse=True)
            index_of = {id(e): i for i, e in enumerate(bucket)}
            for event in bucket_sorted:
                if used[index_of[id(event)]]:
                    continue
                cluster = [event]
                used[index_of[id(event)]] = True
                for other in bucket_sorted:
                    if used[index_of[id(other)]]:
                        continue
                    if self._similar(event.title, other.title):
                        cluster.append(other)
                        used[index_of[id(other)]] = True
                winner = max(cluster, key=lambda e: (e.authority, e.importance))
                merged.append(winner)
                if len(cluster) > 1:
                    dropped = [{
                        'source': e.source,
                        'title': e.title,
                        'url': e.url,
                        'effective_date': e.effective_date,
                        'announce_date': e.announce_date,
                        'authority': e.authority,
                    } for e in cluster if e is not winner]
                    divergences.append(SourceDivergence(
                        merge_key='|'.join(key),
                        kept_source=winner.source,
                        kept_title=winner.title,
                        dropped=dropped,
                        reason=('多源同一事件：保留权威度最高的 %s（%d），其余 %d 源差异留痕'
                                % (winner.source, winner.authority, len(dropped))),
                    ))
        return merged, divergences

    @staticmethod
    def _similar(a: str, b: str) -> bool:
        """标题相似度（归一化后 difflib 比值；任一方为空 → False）"""
        na, nb = normalize_title(a), normalize_title(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        return difflib.SequenceMatcher(None, na, nb).ratio() >= MERGE_TITLE_SIMILARITY

    # --------------------------------------------------------------- 便捷入口

    def prepare(self, rows: Iterable[Dict]) -> Dict:
        """行集合 → (events, divergences, rejected) 的完整领域流水线

        顺序：parse_rows → dedupe(R2) → merge(R3)。去重在前，避免同一源重复行参与聚类。
        """
        events, rejected = self.parse_rows(rows)
        deduped = self.dedupe(events)
        merged, divergences = self.merge(deduped)
        return {
            'events': merged,
            'divergences': divergences,
            'rejected': rejected,
            'parsed': len(events),
            'deduped': len(deduped),
        }

    @staticmethod
    def watch_suggestions(events: Sequence[MarketEvent], days: int = 30) -> List[Dict]:
        """事件 → 盯盘规则建议（**只产出建议，不建规则**；RFC §3.2 link_to_watchlist）

        判据：只有"有明确发生时点 + 影响个股"的事件才值得挂规则：
          - 解禁（unlock）：挂 effective_date 前的价格/波动提醒（解禁前后流动性变化）
          - 财报（earnings）：挂披露日提醒
          - 定增/股东会：仅提示，不自动建议（时点常变，噪声大）
        返回建议的 condition 用 watch_manage 支持的表达式语法描述，供人或 agent 复核后创建。
        """
        out: List[Dict] = []
        for event in events:
            if not event.symbols or not event.is_upcoming(days):
                continue
            if event.type not in (EventType.UNLOCK, EventType.EARNINGS):
                continue
            for symbol in event.symbols:
                out.append({
                    'symbol': symbol,
                    'event_type': event.type.value,
                    'effective_date': event.effective_date,
                    'importance': event.importance,
                    'title': event.title,
                    'source': event.source,
                    'url': event.url,
                    'suggested_rule_name': f"{symbol} {event.type.label}提醒 {event.effective_date}",
                    'suggested_condition': (
                        f"price<{event.raw.get('price_hint')}" if event.raw.get('price_hint')
                        else 'price>0'  # 占位：真实阈值须由人/agent 结合价格与仓位决定，不自动编造
                    ),
                    'note': ('解禁日前后流动性变化显著，建议在 %s 前设置提醒并复核仓位'
                             % event.effective_date) if event.type == EventType.UNLOCK else
                            ('财报披露日 %s，建议提前复核持仓的业绩预期' % event.effective_date),
                    'auto_created': False,
                })
        return out
