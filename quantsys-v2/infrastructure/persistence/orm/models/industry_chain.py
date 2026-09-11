"""产业链图谱 ORM 模型（RFC 015 §2.5，REQ-cf627b，P2）

三张表（quant schema）：
- industry_chain        产业链（聚合根）
- industry_chain_node   环节节点（含 upstream_of / downstream_of 有向关系 + keywords）
- industry_chain_member 链成员（唯一键 (chain_id, symbol, node_id)；含 evidence / confidence / as_of）

设计说明：
- member 的 symbol 外键引用 quant.stocks(symbol)：**不在股票表里的代码不得入库**
  （仓储层用 known_symbols 先过滤并如实回报被丢弃的代码，而不是让外键报错炸掉整条链）。
- upstream_of / downstream_of / keywords 用 JSONB 存（数组语义，PG 原生，读写不经字符串拼装）。
- 同一 symbol 可出现在同链不同 node（真实经营事实，如中国巨石=玻纤纱+电子布），
  唯一键因此是三元组而不是 (chain_id, symbol)。
"""
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from ..base import Base

__all__ = ['IndustryChain', 'IndustryChainNode', 'IndustryChainMember']


class IndustryChain(Base):
    """产业链（聚合根）→ quant.industry_chain"""

    __tablename__ = 'industry_chain'
    __table_args__ = (
        Index('idx_industry_chain_updated', 'updated_at'),
        {'schema': 'quant'},
    )

    chain_id = Column(String(80), primary_key=True, comment='产业链 ID（如 fiberglass_pcb）')
    name = Column(String(200), nullable=False, comment='产业链名称（如 玻纤·电子布·PCB链）')
    description = Column(Text, comment='一句话描述')
    rationale = Column(Text, comment='策展理由（人工判断，可质疑）')
    curator = Column(String(80), comment='策展人/窗口署名')
    source = Column(String(40), nullable=False, server_default='curated', comment='数据来源 provider')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return f"<IndustryChain(chain_id='{self.chain_id}', name='{self.name}')>"


class IndustryChainNode(Base):
    """环节节点 → quant.industry_chain_node（唯一键 (chain_id, node_id)）"""

    __tablename__ = 'industry_chain_node'
    __table_args__ = (
        UniqueConstraint('chain_id', 'node_id', name='uq_industry_chain_node'),
        Index('idx_industry_chain_node_stage', 'chain_id', 'stage'),
        {'schema': 'quant'},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(
        String(80),
        ForeignKey('quant.industry_chain.chain_id', ondelete='CASCADE'),
        nullable=False,
        comment='所属产业链',
    )
    node_id = Column(String(120), nullable=False, comment='环节 ID（链内唯一）')
    name = Column(String(200), nullable=False, comment='环节名称')
    stage = Column(String(20), nullable=False, comment='upstream/midstream/downstream/terminal')
    upstream_of = Column(JSONB, comment='下游 node_id 列表（有向关系）')
    downstream_of = Column(JSONB, comment='上游 node_id 列表（有向关系）')
    keywords = Column(JSONB, comment='主营构成归位关键词（用于把标的归到本环节）')
    rationale = Column(Text, comment='环节切分理由（人工判断）')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<IndustryChainNode(chain_id='{self.chain_id}', node_id='{self.node_id}')>"


class IndustryChainMember(Base):
    """链成员 → quant.industry_chain_member（唯一键 (chain_id, symbol, node_id)）"""

    __tablename__ = 'industry_chain_member'
    __table_args__ = (
        UniqueConstraint('chain_id', 'symbol', 'node_id', name='uq_industry_chain_member'),
        Index('idx_industry_chain_member_symbol', 'symbol'),
        Index('idx_industry_chain_member_chain_node', 'chain_id', 'node_id'),
        {'schema': 'quant'},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(
        String(80),
        ForeignKey('quant.industry_chain.chain_id', ondelete='CASCADE'),
        nullable=False,
        comment='所属产业链',
    )
    node_id = Column(String(120), nullable=False, comment='所属环节 ID')
    symbol = Column(
        Text,
        ForeignKey('quant.stocks.symbol', ondelete='CASCADE'),
        nullable=False,
        comment='股票代码（外键：不在 stocks 表的代码不得入库）',
    )
    name = Column(String(80), comment='股票名称')
    stage = Column(String(20), nullable=False, comment='环节位置')
    role = Column(String(40), comment='龙头/二线/弹性标的')
    exposure_ratio = Column(Float, comment='主营占比（0-1 小数，非百分数）')
    exposure_basis = Column(Text, comment='占比口径来源（如「主营构成：玻纤及其制品相关」）')
    exposure_as_of = Column(String(20), comment='占比时点（报告期 YYYY-MM-DD）')
    evidence = Column(Text, comment='归位证据（可追溯文本）')
    evidence_kind = Column(String(20), comment='主营构成/产品构成/策展/行业分类/概念成分')
    confidence = Column(String(10), comment='high/medium/low')
    source = Column(String(40), comment='主张来源 provider')
    conflict = Column(Text, comment='证据冲突备注（未裁决时必填）')
    as_of = Column(DateTime, default=datetime.now, comment='本次落库时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return (f"<IndustryChainMember(chain_id='{self.chain_id}', node_id='{self.node_id}', "
                f"symbol='{self.symbol}')>")
