"""政策·个股事件源限界上下文（RFC 015 §3，P3）"""
from domain.events.model import (
    AUTHORITY_AKSHARE, AUTHORITY_CNINFO, AUTHORITY_CSRC, AUTHORITY_DB,
    AUTHORITY_EASTMONEY, AUTHORITY_GOV, AUTHORITY_MANUAL,
    EventScope, EventType, MarketEvent, SourceDivergence, source_authority,
)
from domain.events.service import MarketEventService

__all__ = [
    'EventScope', 'EventType', 'MarketEvent', 'SourceDivergence', 'source_authority',
    'MarketEventService',
    'AUTHORITY_CNINFO', 'AUTHORITY_CSRC', 'AUTHORITY_GOV', 'AUTHORITY_EASTMONEY',
    'AUTHORITY_AKSHARE', 'AUTHORITY_MANUAL', 'AUTHORITY_DB',
]
