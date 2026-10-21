"""消息监控已报留痕 ORM（2026-10-20）"""
from sqlalchemy import JSON, Column, DateTime, Integer, String, func

from ..base import Base


class WatchNewsAlert(Base):
    """盯盘消息监控的已报留痕：同一条新闻（symbol+标题哈希）只报一次"""
    __tablename__ = 'watch_news_alerts'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    title_hash = Column(String(64), nullable=False)
    title = Column(String(300), nullable=False, server_default='')
    matched_words = Column(JSON, nullable=True, comment='命中词列表')
    tier = Column(String(10), nullable=False, server_default='soft',
                  comment='critical=强提醒（立案/退市/处罚…）；soft=弱提醒（减持/问询…）')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
