"""事件限界上下文的端口（一类一文件）"""
from domain.events.ports.IMarketEventProvider import IMarketEventProvider
from domain.events.ports.IMarketEventRepository import IMarketEventRepository

__all__ = ['IMarketEventProvider', 'IMarketEventRepository']
