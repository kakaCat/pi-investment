"""兼容入口；实现已迁移到 V2。"""
from qs_watch.application.services.watch_engine.v2.market_watch_service import (
    MARKET_SCOPES,
    MarketWatchService,
)

__all__ = ['MARKET_SCOPES', 'MarketWatchService']
