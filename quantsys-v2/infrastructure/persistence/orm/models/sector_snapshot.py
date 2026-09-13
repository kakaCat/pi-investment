"""板块（行业+概念）快照表（quant.sector_snapshot）。

建立背景（2026-09-14，w-32314d00，REQ-24e15d B2）：
    该表此前**没有 ORM 模型**，读写全在
    `adapters/outbound/datasources/sector_snapshot.py` 里以 text(f"... {_TABLE} ...") 形式存在
    （表名走模块常量插值）。路由/数据源层不该持有 SQL，且表名一旦写错只会静默失败
    （读取侧 except 吞掉 → 返回 None/"无快照"）。收口到模型 + 仓储后，
    表名错误会在导入期就以 UndefinedTable 暴露。

⚠️ 表名是**单数** quant.sector_snapshot（不是 snapshots）。
"""
from sqlalchemy import Column, Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..base import Base

__all__ = ['SectorSnapshot']


class SectorSnapshot(Base):
    """板块快照（每自然日一行，同日 UPSERT 覆盖）

    对应数据库表：quant.sector_snapshot
    主键：snapshot_date
    """
    __tablename__ = 'sector_snapshot'
    __table_args__ = {'schema': 'quant'}

    snapshot_date = Column(Date, primary_key=True, comment='快照日期')
    industries = Column(JSONB, nullable=False, comment='行业板块列表')
    concepts = Column(JSONB, nullable=False, comment='概念板块列表')
    total = Column(Integer, nullable=False, comment='板块总数')
    source = Column(String, nullable=False, comment='数据来源')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SectorSnapshot(date='{self.snapshot_date}', total={self.total})>"
