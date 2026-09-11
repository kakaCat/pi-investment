"""政策·个股事件源领域模型（限界上下文：events）

RFC 015 §3.1（2026-09-11，REQ-cf627b，P3）。领域层**零外部依赖**：
本文件只用 dataclasses / enum / typing / 标准库，不得 import 任何框架、ORM、adapters。

背景（为什么需要这个上下文）：
  2026-09-11 农业板块崩盘归因**100% 依赖 web_search 外部新闻**（六部门文件、秋粮丰产、
  小麦托市）；`quant.event_calendar` 原有 67 行**全是宏观**（cpi/pmi/lpr/fomc/交割），
  既没有政策文件，也没有个股财报/解禁/定增。事件源缺失 = 归因与排雷都靠人工搜新闻。

设计要点（可质疑，故全部显式）：
1. **三个维度正交**：`scope`（影响范围）× `type`（事件性质）× `importance`（重要性 1-3）。
   scope 决定"谁受影响"（宏观/行业/个股），type 决定"是什么事"（政策/财报/解禁…）。
   不把两者合成一个枚举——政策既可能是宏观（国务院文件）也可能是行业（部委专项）。
2. **evidence_hash 是幂等与去重的唯一锚**：同一 (scope, type, 标的集合, 生效日, 归一化标题)
   视为同一事件。多源（巨潮/东财）对同一事件给出各自的 title 与 url，
   归一化后能对上就合并，对不上则由 domain service 的相似度聚类兜底。
3. **authority（源权威度）显式建模**：巨潮是**法定披露**（权威），东财是转载聚合，
   akshare 是二次加工，人工策展是兜底。冲突时保留权威源，差异写入 source_divergence
   （RFC §3.3 交叉校验：不静默取其一）。
4. **effective_date 与 announce_date 分开**：解禁/财报有"生效/发生日"与"公告日"两个时间，
   排雷要看 announce（何时知道的），择时要看 effective（何时发生）。混用会得出错误结论。
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, Iterable, List, Optional


class EventScope(str, Enum):
    """事件影响范围（值对象）

    - MACRO      宏观：影响全市场（国务院文件、CPI、FOMC）
    - INDUSTRY   行业：影响某行业/板块（部委专项、行业政策）
    - INDIVIDUAL 个股：只影响特定标的（财报、解禁、定增、股东会）
    """

    MACRO = 'macro'
    INDUSTRY = 'industry'
    INDIVIDUAL = 'individual'

    @classmethod
    def parse(cls, value: 'EventScope | str | None') -> 'EventScope':
        """容错解析（'macro' / '宏观' / 'MACRO' → EventScope.MACRO）

        无法识别时抛 ValueError（fail-loud：宁可入库失败，也不把个股事件静默当宏观）。
        """
        if isinstance(value, EventScope):
            return value
        key = str(value or '').strip().lower()
        aliases = {
            'macro': cls.MACRO, 'market': cls.MACRO, '宏观': cls.MACRO, '全市场': cls.MACRO,
            'industry': cls.INDUSTRY, 'sector': cls.INDUSTRY, '行业': cls.INDUSTRY, '板块': cls.INDUSTRY,
            'individual': cls.INDIVIDUAL, 'stock': cls.INDIVIDUAL, 'company': cls.INDIVIDUAL,
            '个股': cls.INDIVIDUAL, '公司': cls.INDIVIDUAL,
        }
        if key not in aliases:
            raise ValueError(f"无法识别的事件范围: {value!r}（支持 macro/industry/individual 或 宏观/行业/个股）")
        return aliases[key]


class EventType(str, Enum):
    """事件性质（值对象）

    与 `quant.event_calendar.event_type` 的既有宏观取值（cpi_ppi/pmi/lpr/fomc/nbs/
    futures_delivery）**并存不冲突**：宏观行沿用原值，本枚举覆盖新增的政策与个股事件。
    """

    POLICY = 'policy'                          # 政策文件/监管措施
    EARNINGS = 'earnings'                      # 财报/业绩预告/业绩快报
    UNLOCK = 'unlock'                          # 限售股解禁
    PLACEMENT = 'placement'                    # 定增/配股/可转债发行
    SHAREHOLDER_MEETING = 'shareholder_meeting'  # 股东大会
    REGULATORY = 'regulatory'                  # 监管措施/问询/处罚/诉讼仲裁
    DIVIDEND = 'dividend'                      # 分红/送转/除权除息
    OTHER = 'other'                            # 其他公告

    @classmethod
    def parse(cls, value: 'EventType | str | None') -> 'EventType':
        """容错解析（中文别名 → 枚举）；无法识别时抛 ValueError"""
        if isinstance(value, EventType):
            return value
        key = str(value or '').strip().lower()
        aliases = {
            'policy': cls.POLICY, '政策': cls.POLICY,
            'earnings': cls.EARNINGS, 'report': cls.EARNINGS, '财报': cls.EARNINGS,
            '业绩': cls.EARNINGS, '业绩预告': cls.EARNINGS,
            'unlock': cls.UNLOCK, '解禁': cls.UNLOCK, '限售解禁': cls.UNLOCK,
            'placement': cls.PLACEMENT, '定增': cls.PLACEMENT, '增发': cls.PLACEMENT, '配股': cls.PLACEMENT,
            'shareholder_meeting': cls.SHAREHOLDER_MEETING, '股东会': cls.SHAREHOLDER_MEETING,
            '股东大会': cls.SHAREHOLDER_MEETING,
            'regulatory': cls.REGULATORY, '监管': cls.REGULATORY, '问询': cls.REGULATORY,
            '处罚': cls.REGULATORY, '诉讼': cls.REGULATORY,
            'dividend': cls.DIVIDEND, '分红': cls.DIVIDEND, '送转': cls.DIVIDEND,
            'other': cls.OTHER, '其他': cls.OTHER,
        }
        if key not in aliases:
            raise ValueError(f"无法识别的事件类型: {value!r}")
        return aliases[key]

    @property
    def label(self) -> str:
        return {
            EventType.POLICY: '政策', EventType.EARNINGS: '财报', EventType.UNLOCK: '解禁',
            EventType.PLACEMENT: '定增', EventType.SHAREHOLDER_MEETING: '股东会',
            EventType.REGULATORY: '监管', EventType.DIVIDEND: '分红', EventType.OTHER: '其他',
        }[self]


# ── 源权威度（冲突裁决用；数值越高越权威）─────────────────────────────
AUTHORITY_CNINFO = 90        # 巨潮资讯网：法定信息披露平台（RFC §3.3 权威源）
AUTHORITY_CSRC = 85          # 证监会/交易所发布页
AUTHORITY_GOV = 80           # 国务院/发改委发布页
AUTHORITY_EASTMONEY = 60     # 东财公告聚合（转载，时效好但非原始披露）
AUTHORITY_AKSHARE = 50       # akshare 结构化二次加工（解禁排队）
AUTHORITY_MANUAL = 40        # 人工策展兜底（带 operator 标记）
AUTHORITY_DB = 20            # 本地表兜底（stale）

_SOURCE_AUTHORITY = {
    'cninfo_disclosure': AUTHORITY_CNINFO,
    'csrc_policy': AUTHORITY_CSRC,
    'gov_policy': AUTHORITY_GOV,
    'eastmoney_notice': AUTHORITY_EASTMONEY,
    'akshare_unlock': AUTHORITY_AKSHARE,
    'manual_policy_seed': AUTHORITY_MANUAL,
    'database_event': AUTHORITY_DB,
}


def source_authority(source: str, explicit: Optional[int] = None) -> int:
    """源的权威度（provider 可显式给 authority，否则按 name 查表；未知源取最低档+1）"""
    if explicit is not None:
        try:
            return int(explicit)
        except (TypeError, ValueError):
            pass
    return _SOURCE_AUTHORITY.get(str(source or '').strip(), AUTHORITY_DB + 1)


@dataclass(frozen=True)
class SourceDivergence:
    """多源同一事件的分歧记录（RFC §3.3：不静默取其一）

    何时产生：`MarketEventService.merge` 把同一 (type, 日期, 标的) 下、标题相似度达阈值的
    多源事件判为"同一事件"时，若各源的 title/url/日期/重要度存在差异，即记录本对象。
    """

    merge_key: str
    kept_source: str
    kept_title: str
    dropped: List[Dict] = field(default_factory=list)
    reason: str = ''

    def to_dict(self) -> Dict:
        return {
            'merge_key': self.merge_key,
            'kept_source': self.kept_source,
            'kept_title': self.kept_title,
            'dropped': self.dropped,
            'reason': self.reason,
        }


@dataclass
class MarketEvent:
    """市场事件（聚合根）

    必填：event_id（= evidence_hash 的短形式）/ scope / type / title / effective_date。
    其余字段可空——**空值必须语义明确**：
      - announce_date 为 ''：该源不提供公告日（不是"公告日=空字符串"这种假数据）
      - symbols 为空列表：该事件不绑定个股（宏观/行业事件）
      - url 为 ''：该源无原文链接
      - importance 为 None：未推断（由 domain service 的 infer_importance 补）
    """

    event_id: str
    scope: EventScope
    type: EventType
    title: str
    effective_date: str                       # YYYY-MM-DD（事件发生/生效日）
    announce_date: str = ''                   # YYYY-MM-DD（公告/知晓日，可空）
    importance: int = 1                       # 1 低 / 2 中 / 3 高
    symbols: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    source: str = ''
    url: str = ''
    summary: str = ''
    raw: Dict = field(default_factory=dict)
    evidence_hash: str = ''
    authority: int = 0

    def __post_init__(self):
        self.scope = EventScope.parse(self.scope)
        self.type = EventType.parse(self.type)
        self.symbols = [str(s).strip() for s in (self.symbols or []) if str(s).strip()]
        self.industries = [str(i).strip() for i in (self.industries or []) if str(i).strip()]
        try:
            self.importance = int(self.importance if self.importance is not None else 1)
        except (TypeError, ValueError):
            self.importance = 1
        if self.importance not in (1, 2, 3):
            # 越界不静默截断：写清来源，便于发现上游口径错误（如把 5 星制当 3 星制）
            raise ValueError(f"importance 必须为 1-3，收到 {self.importance!r}（事件：{self.title}）")
        self.effective_date = str(self.effective_date or '').strip()[:10]
        self.announce_date = str(self.announce_date or '').strip()[:10]
        if not self.effective_date:
            raise ValueError(f"事件缺 effective_date（无法排序与判 upcoming）：{self.title}")
        if self.authority <= 0:
            self.authority = source_authority(self.source)

    # ------------------------------------------------------------------ 查询

    def affects(self, symbol: str) -> bool:
        """该事件是否影响给定标的

        判定口径（**不含行业推断**，避免"沾边就算"）：
        1. symbols 显式包含该代码 → True（个股事件、或政策文件点名了该标的）
        2. 宏观事件（scope=macro）→ True（影响全市场，任何标的都受影响）
        3. 其余 → False（行业事件需先由调用方把行业映射到标的，本方法不猜）
        """
        code = str(symbol or '').strip()
        if not code:
            return False
        if code in self.symbols:
            return True
        return self.scope == EventScope.MACRO

    def is_upcoming(self, days: int = 7, today: Optional[str] = None) -> bool:
        """是否"未来 N 天内即将发生"（含今天；已过去的事件返回 False）

        用 effective_date（事件发生日）而非 announce_date——盯着的是"什么时候发生"。
        """
        try:
            base = datetime.strptime(str(today)[:10], '%Y-%m-%d').date() if today else date.today()
            target = datetime.strptime(self.effective_date, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return False
        span = max(0, int(days or 0))
        return base <= target <= base + timedelta(days=span)

    @property
    def is_symbol_event(self) -> bool:
        return self.scope == EventScope.INDIVIDUAL or bool(self.symbols)

    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'scope': self.scope.value,
            'type': self.type.value,
            'type_label': self.type.label,
            'title': self.title,
            'effective_date': self.effective_date,
            'announce_date': self.announce_date or None,
            'importance': self.importance,
            'symbols': self.symbols,
            'industries': self.industries,
            'source': self.source,
            'url': self.url,
            'summary': self.summary,
            'evidence_hash': self.evidence_hash or self.event_id,
            'authority': self.authority,
            'raw': self.raw,
        }
