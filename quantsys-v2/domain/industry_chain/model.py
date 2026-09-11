"""产业链图谱领域模型（限界上下文：industry_chain）

RFC 015 §2.1（2026-09-11，REQ-cf627b，P2）。领域层**零外部依赖**：
本文件仅用 dataclasses / enum / typing，不得 import 任何框架、ORM、adapters。

设计要点（可质疑，故全部显式）：
- 拓扑（ChainNode 的上下游关系）是**人工策展**的知识，不是上游数据 → 唯一权威源是
  domain/industry_chain/seed/*.yaml（经 CuratedChainProvider），**不可降级**（RFC §2.3 级别 0）。
- 成员归位（某标的属于哪个环节）必须有**证据**：evidence 字符串 + confidence 分级。
  分级口径（RFC §2.3）：主营构成 > 行业分类 > 概念成分；人工策展居中（有 rationale 但非财报口径）。
- 「同一标的同时属于多个环节」是合法事实（如中国巨石：玻纤纱 + 电子布），
  member 唯一键为 (chain_id, symbol, node_id)；「同一标的被归到**不同阶段(stage)**」
  才是冲突，由 service.py 的冲突裁决处理。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ChainStage(str, Enum):
    """环节位置（值对象：链上的相对位置，不是行业分类）"""

    UPSTREAM = 'upstream'
    MIDSTREAM = 'midstream'
    DOWNSTREAM = 'downstream'
    TERMINAL = 'terminal'

    @classmethod
    def parse(cls, value: 'ChainStage | str') -> 'ChainStage':
        """容错解析（'upstream' / '上游' / 'UPSTREAM' → ChainStage.UPSTREAM）

        无法识别时抛 ValueError（fail-loud：宁可整链构建失败，也不把环节静默归到别处）。
        """
        if isinstance(value, ChainStage):
            return value
        key = str(value or '').strip().lower()
        aliases = {
            'upstream': cls.UPSTREAM, 'up': cls.UPSTREAM, '上游': cls.UPSTREAM,
            'midstream': cls.MIDSTREAM, 'mid': cls.MIDSTREAM, '中游': cls.MIDSTREAM, '中': cls.MIDSTREAM,
            'downstream': cls.DOWNSTREAM, 'down': cls.DOWNSTREAM, '下游': cls.DOWNSTREAM,
            'terminal': cls.TERMINAL, 'end': cls.TERMINAL, '终端': cls.TERMINAL, '终端应用': cls.TERMINAL,
        }
        if key not in aliases:
            raise ValueError(f"无法识别的环节位置: {value!r}（支持 upstream/midstream/downstream/terminal 或 上游/中游/下游/终端）")
        return aliases[key]

    @property
    def label(self) -> str:
        return {'upstream': '上游', 'midstream': '中游', 'downstream': '下游', 'terminal': '终端'}[self.value]


class EvidenceKind(str, Enum):
    """归位证据类型（决定 confidence 与冲突裁决时的优先级）

    - MAIN_BUSINESS  主营构成（东财 F10 / 同花顺 F10）：**唯一硬证据**，带营收占比
    - PRODUCT_PROFILE 产品构成（同花顺 F10 产品名称/主营描述）：关键词证据，无占比
    - CURATED        人工策展（seed 里的代表标的，带 rationale）
    - INDUSTRY_CLASS 行业分类（新浪行业等）
    - CONCEPT        概念成分（低置信，只作候选与补全）
    """

    MAIN_BUSINESS = '主营构成'
    PRODUCT_PROFILE = '产品构成'
    CURATED = '策展'
    INDUSTRY_CLASS = '行业分类'
    CONCEPT = '概念成分'

    @classmethod
    def parse(cls, value: 'EvidenceKind | str') -> 'EvidenceKind':
        if isinstance(value, EvidenceKind):
            return value
        text = str(value or '').strip()
        for kind in cls:
            if kind.value == text:
                return kind
        # 容错：上游 provider 常用英文标识
        by_key = {
            'main_business': cls.MAIN_BUSINESS, 'revenue': cls.MAIN_BUSINESS, 'zygc': cls.MAIN_BUSINESS,
            'product': cls.PRODUCT_PROFILE, 'product_profile': cls.PRODUCT_PROFILE,
            'curated': cls.CURATED, 'seed': cls.CURATED,
            'industry': cls.INDUSTRY_CLASS, 'industry_class': cls.INDUSTRY_CLASS, 'sector': cls.INDUSTRY_CLASS,
            'concept': cls.CONCEPT,
        }
        if text.lower() in by_key:
            return by_key[text.lower()]
        raise ValueError(f"无法识别的证据类型: {value!r}")

    @property
    def priority(self) -> int:
        '''冲突裁决优先级（高者胜，**五级互不相同**，避免"同级并列"制造假冲突）

        主营构成(5) > 人工策展(4) > 产品构成(3) > 行业分类(2) > 概念成分(1)。
        为什么策展(4)高于产品构成(3)：策展带 rationale 且经人复核，产品构成是机器关键词匹配
        （2026-09-11 实测：中远海控的 THS 产品名出现"船舶"，被同时归到造船与航运；
        若两者同级就会产出大量"未裁决冲突"噪声）。
        为什么产品构成(3)高于行业分类(2)：前者是公司自己的产品口径，后者是第三方行业标签。
        '''
        return {
            EvidenceKind.MAIN_BUSINESS: 5,
            EvidenceKind.CURATED: 4,
            EvidenceKind.PRODUCT_PROFILE: 3,
            EvidenceKind.INDUSTRY_CLASS: 2,
            EvidenceKind.CONCEPT: 1,
        }[self]

    @property
    def confidence(self) -> str:
        """证据 → 置信度分级（主营构成 > 行业分类/产品构成 > 概念成分）"""
        return {
            EvidenceKind.MAIN_BUSINESS: CONFIDENCE_HIGH,
            EvidenceKind.PRODUCT_PROFILE: CONFIDENCE_MEDIUM,
            EvidenceKind.CURATED: CONFIDENCE_MEDIUM,
            EvidenceKind.INDUSTRY_CLASS: CONFIDENCE_MEDIUM,
            EvidenceKind.CONCEPT: CONFIDENCE_LOW,
        }[self]


# 置信度取值（repository/UI/工具按此排序展示）
CONFIDENCE_HIGH = 'high'
CONFIDENCE_MEDIUM = 'medium'
CONFIDENCE_LOW = 'low'
CONFIDENCE_ORDER = {CONFIDENCE_HIGH: 3, CONFIDENCE_MEDIUM: 2, CONFIDENCE_LOW: 1}


@dataclass(frozen=True)
class RevenueExposure:
    """主营占比（值对象）：ratio 为**占营收比例的小数**（0-1），basis 是口径来源

    ratio 单位纪律（2026-09-11 教训：分红 provider 读错列名致全 0 被误读为"不分红"）：
    上游给的可能是百分数（97.3）或小数（0.973）。**provider 负责归一为小数**，
    本值对象对越界值一律抛错，禁止静默接受——否则 0.973% 与 97.3% 无法区分。
    """

    ratio: float
    basis: str = ''
    as_of: str = ''

    def __post_init__(self):
        try:
            value = float(self.ratio)
        except (TypeError, ValueError):
            raise ValueError(f"主营占比必须是数字，收到 {self.ratio!r}")
        if value != value:  # NaN
            raise ValueError("主营占比为 NaN（上游字段缺失时 provider 应返回 None，而不是 NaN）")
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"主营占比越界: {value}（契约要求 0-1 的小数；百分数须由 provider 除以 100 归一）"
            )
        object.__setattr__(self, 'ratio', value)

    @property
    def pct(self) -> float:
        """百分数形式（展示用）"""
        return round(self.ratio * 100, 2)

    def to_dict(self) -> Dict:
        return {'ratio': self.ratio, 'pct': self.pct, 'basis': self.basis, 'as_of': self.as_of}


@dataclass
class ChainMember:
    """链成员（实体：某标的在某链某环节的归位主张 + 证据）

    唯一性：(chain_id, symbol, node_id)；同一 symbol 可出现在不同 node（合法），
    但同一 symbol 落到不同 stage 时必须由 service 裁决冲突。
    """

    symbol: str
    name: str
    stage: ChainStage
    exposure: Optional[RevenueExposure] = None
    role: str = ''
    evidence: str = ''
    confidence: str = CONFIDENCE_LOW
    node_id: str = ''
    node_name: str = ''
    evidence_kind: str = EvidenceKind.CURATED.value
    source: str = ''
    conflict: str = ''
    # 是否为"主环节"（同一标的跨环节时按证据优先级/占比裁出的主归位）
    primary: bool = False

    def __post_init__(self):
        self.stage = ChainStage.parse(self.stage)
        if self.confidence not in CONFIDENCE_ORDER:
            raise ValueError(f"非法置信度: {self.confidence!r}（支持 high/medium/low）")

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'name': self.name,
            'stage': self.stage.value,
            'stage_label': self.stage.label,
            'node_id': self.node_id,
            'node_name': self.node_name,
            'role': self.role,
            'evidence': self.evidence,
            'evidence_kind': self.evidence_kind,
            'confidence': self.confidence,
            'exposure': self.exposure.to_dict() if self.exposure else None,
            'source': self.source,
            'conflict': self.conflict or None,
            'primary': self.primary,
        }


@dataclass
class ChainNode:
    """环节节点（实体：链上的一个环节 + 有向上下游关系）

    字段读法（全仓统一，勿再歧义）：
      X.upstream_of   = [「X 是它们的上游」的 node_id] → 即 X 的**下游节点**
      X.downstream_of = [「X 是它们的下游」的 node_id] → 即 X 的**上游节点**
    例（玻纤链）：glass_fiber_yarn.upstream_of=[electronic_yarn_cloth] 表示"玻纤纱是电子布的上游"；
                 electronic_yarn_cloth.downstream_of=[glass_fiber_yarn] 表示"电子布是玻纤纱的下游"。

    拓扑由人工策展给出，seed 中两个方向都要写，并由 domain service 做**对称性校验**
    （A 说"我是 B 的上游"，B 必须说"我是 A 的下游"），不一致直接失败——
    冗余声明用来互相校验，而不是各说各话。
    """

    node_id: str
    name: str
    stage: ChainStage
    upstream_of: List[str] = field(default_factory=list)
    downstream_of: List[str] = field(default_factory=list)
    rationale: str = ''
    keywords: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.stage = ChainStage.parse(self.stage)
        self.upstream_of = list(self.upstream_of or [])
        self.downstream_of = list(self.downstream_of or [])
        self.keywords = list(self.keywords or [])

    def to_dict(self) -> Dict:
        return {
            'node_id': self.node_id,
            'name': self.name,
            'stage': self.stage.value,
            'stage_label': self.stage.label,
            'upstream_of': self.upstream_of,
            'downstream_of': self.downstream_of,
            'rationale': self.rationale,
            'keywords': self.keywords,
        }


@dataclass(frozen=True)
class EvidenceConflict:
    """证据冲突记录（可人工复核；不静默取其一，RFC §2.3）

    - claims: 每个数据源对同一标的的归位主张 [{source, node_id, stage, evidence_kind, ratio}]
    - resolved: 是否已按优先级裁决（False = 同级证据互相矛盾，需人工确认）
    """

    symbol: str
    reason: str
    claims: List[Dict] = field(default_factory=list)
    winner_node_id: str = ''
    winner_stage: str = ''
    resolved: bool = True
    resolution: str = ''

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'reason': self.reason,
            'claims': self.claims,
            'winner_node_id': self.winner_node_id,
            'winner_stage': self.winner_stage,
            'resolved': self.resolved,
            'resolution': self.resolution,
        }


@dataclass
class IndustryChain:
    """产业链（聚合根）"""

    chain_id: str
    name: str
    nodes: List[ChainNode] = field(default_factory=list)
    members: List[ChainMember] = field(default_factory=list)
    description: str = ''
    rationale: str = ''
    source: str = ''
    as_of: str = ''

    # ------------------------------------------------------------------ 查询

    def members_at(self, stage: 'ChainStage | str') -> List[ChainMember]:
        """该环节位置上的全部成员"""
        target = ChainStage.parse(stage)
        return [m for m in self.members if m.stage == target]

    def symbol_stages(self, symbol: str) -> List[ChainStage]:
        """某标的在本链中出现的环节位置（去重保序；不在链中返回 []）"""
        seen: List[ChainStage] = []
        for member in self.members:
            if member.symbol == str(symbol).strip():
                if member.stage not in seen:
                    seen.append(member.stage)
        return seen

    def members_of_node(self, node_id: str) -> List[ChainMember]:
        return [m for m in self.members if m.node_id == node_id]

    def node(self, node_id: str) -> Optional[ChainNode]:
        for item in self.nodes:
            if item.node_id == node_id:
                return item
        return None

    def members_by_stage(self) -> Dict[str, List[ChainMember]]:
        """按环节位置分组（稳定顺序：上游→中游→下游→终端）"""
        grouped: Dict[str, List[ChainMember]] = {stage.value: [] for stage in ChainStage}
        for member in self.members:
            grouped[member.stage.value].append(member)
        return grouped

    def nodes_by_stage(self) -> Dict[str, List[ChainNode]]:
        grouped: Dict[str, List[ChainNode]] = {stage.value: [] for stage in ChainStage}
        for node in self.nodes:
            grouped[node.stage.value].append(node)
        return grouped

    def to_dict(self) -> Dict:
        return {
            'chain_id': self.chain_id,
            'name': self.name,
            'description': self.description,
            'rationale': self.rationale,
            'source': self.source,
            'as_of': self.as_of,
            'node_count': len(self.nodes),
            'member_count': len(self.members),
            'symbol_count': len({m.symbol for m in self.members}),
            'nodes': [n.to_dict() for n in self.nodes],
            'by_stage': {
                stage: [m.to_dict() for m in members]
                for stage, members in self.members_by_stage().items()
            },
        }
