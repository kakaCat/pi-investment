"""事件日历 ORM Repository（特殊日子：宏观发布/央行议息/财报/交割等）

数据流：初始化脚本/手动 → quant.event_calendar 表 → API /api/events → 每日检查任务/Agent 工具
设计文档：docs/work-logs/2026-09/event-calendar-system-design.md
"""
from datetime import datetime, date, time as dtime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, SmallInteger, DateTime, Date, Time, Text
from sqlalchemy.dialects.postgresql import JSONB

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base


class EventCalendar(Base):
    __tablename__ = 'event_calendar'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    event_type = Column(String(32), nullable=False)     # cpi/ppi/pmi/gdp/nbs/lpr/fomc/us_cpi/nfp/earnings/futures_delivery/policy/other
    event_date = Column(Date, nullable=False)           # 事件日期
    event_time = Column(Time)                            # 发布时刻，NULL=盘中/全天
    title = Column(String(200), nullable=False)         # "8月CPI发布"
    description = Column(Text)                           # 预期值/前值/背景
    symbol = Column(String(20))                          # 关联标的（财报/交割/解禁），宏观事件为 NULL
    market = Column(String(8), default='CN')             # CN/US
    importance = Column(SmallInteger, default=1)         # 1低 2中 3高
    status = Column(String(16), default='pending')       # pending/notified/collected/reviewed/skipped
    source = Column(String(50))                          # nbs/fed/pboc/exchange/manual/akshare
    meta = Column(JSONB)                                 # 扩展：预期/前值/采集结果/影响评估
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


def event_to_dict(ev: EventCalendar) -> dict:
    """序列化为 API 响应 dict（snake_case，与现有契约风格一致）"""
    return {
        'id': ev.id,
        'event_type': ev.event_type,
        'event_date': ev.event_date.isoformat() if ev.event_date else None,
        'event_time': ev.event_time.strftime('%H:%M') if ev.event_time else None,
        'title': ev.title,
        'description': ev.description,
        'symbol': ev.symbol,
        'market': ev.market,
        'importance': ev.importance,
        'status': ev.status,
        'source': ev.source,
        'meta': ev.meta,
        'created_at': ev.created_at.isoformat() if ev.created_at else None,
        'updated_at': ev.updated_at.isoformat() if ev.updated_at else None,
    }


def _parse_time(t) -> Optional[dtime]:
    """把 'HH:MM' 字符串或 None 转为 time 对象"""
    if t is None or isinstance(t, dtime):
        return t
    if isinstance(t, str):
        try:
            return datetime.strptime(t, '%H:%M').time()
        except ValueError:
            return None
    return None


class EventCalendarRepository(BaseORMRepository[EventCalendar]):
    """事件日历查询/维护。核心查询：未来 N 天待处理事件（每日检查任务用）。"""
    model = EventCalendar

    def list_upcoming(self, days_ahead: int = 2, status: tuple = ('pending', 'notified')) -> List[EventCalendar]:
        """查未来 N 天待处理事件（含今天）。每日检查任务核心调用。"""
        try:
            today = date.today()
            end = date.fromordinal(today.toordinal() + max(0, days_ahead))
            return (self.session.query(self.model)
                    .filter(self.model.event_date >= today,
                            self.model.event_date <= end,
                            self.model.status.in_(status))
                    .order_by(self.model.event_date.asc(), self.model.importance.desc())
                    .all())
        except Exception as e:
            import structlog
            structlog.get_logger(__name__).error("list_upcoming failed", error=str(e))
            return []

    def list_range(self, start: Optional[date] = None, end: Optional[date] = None,
                   event_type: Optional[str] = None, status: Optional[str] = None,
                   symbol: Optional[str] = None, limit: int = 200) -> List[EventCalendar]:
        """范围查询：按日期区间/类型/状态/标的过滤。"""
        try:
            q = self.session.query(self.model)
            if start:
                q = q.filter(self.model.event_date >= start)
            if end:
                q = q.filter(self.model.event_date <= end)
            if event_type:
                q = q.filter(self.model.event_type == event_type)
            if status:
                q = q.filter(self.model.status == status)
            if symbol:
                q = q.filter(self.model.symbol == symbol)
            return q.order_by(self.model.event_date.asc()).limit(limit).all()
        except Exception as e:
            import structlog
            structlog.get_logger(__name__).error("list_range failed", error=str(e))
            return []

    def upsert(self, event_type: str, event_date: date, title: str, **fields) -> Optional[EventCalendar]:
        """按 (event_type, event_date, title) 幂等创建：已存在则更新，不存在则插入。"""
        try:
            existing = (self.session.query(self.model)
                        .filter_by(event_type=event_type, event_date=event_date, title=title)
                        .first())
            if existing:
                for k, v in fields.items():
                    if hasattr(existing, k) and v is not None:
                        if k == 'event_time':
                            v = _parse_time(v)
                        setattr(existing, k, v)
                existing.updated_at = datetime.now()
                return self.update(existing)
            obj = EventCalendar(
                event_type=event_type,
                event_date=event_date,
                title=title,
                event_time=_parse_time(fields.get('event_time')),
                description=fields.get('description'),
                symbol=fields.get('symbol'),
                market=fields.get('market', 'CN'),
                importance=fields.get('importance', 1),
                status=fields.get('status', 'pending'),
                source=fields.get('source', 'manual'),
                meta=fields.get('meta'),
            )
            return self.create(obj)
        except Exception as e:
            import structlog
            structlog.get_logger(__name__).error("upsert failed", error=str(e), title=title)
            return None

    def mark_status(self, event_id: int, status: str, meta_patch: Optional[dict] = None) -> Optional[EventCalendar]:
        """更新状态（并可选合并 meta）。状态机：pending→notified→collected→reviewed / skipped。"""
        obj = self.get_by_id(event_id)
        if not obj:
            return None
        obj.status = status
        if meta_patch:
            merged = dict(obj.meta or {})
            merged.update(meta_patch)
            obj.meta = merged
        obj.updated_at = datetime.now()
        return self.update(obj)


_repo: Optional[EventCalendarRepository] = None


def get_event_calendar_repo() -> EventCalendarRepository:
    """进程级单例（与现有仓储模式一致）"""
    global _repo
    if _repo is None:
        _repo = EventCalendarRepository()
    return _repo
