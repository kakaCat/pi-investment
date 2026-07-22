"""WatchEngine 装配：构建引擎 + 后台线程启动"""
import threading
from datetime import datetime, timedelta
from typing import Optional

import structlog

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository,
)
from application.services.agent_notification_service import AgentNotificationService
from application.services.realtime_quote_service_v2 import RealtimeQuoteServiceV2
from application.services.watch_engine.engine import WatchEngine
from application.services.watch_engine.notifier import WatchNotifier

logger = structlog.get_logger(__name__)


def make_avg_volume_provider():
    """近 20 日日均成交量 provider。失败返回 None（volume_surge 降级不判定）"""
    def provider(symbol: str) -> Optional[float]:
        from adapters.outbound.datasources.manager import get_data_provider_manager
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
        result = get_data_provider_manager().get_klines(symbol, 'daily', start, end)
        if not result.get('success'):
            return None
        # data 为 List[KlineData] dataclass（非 dict），用属性访问；兼容 dict 兜底
        volumes = []
        for k in result['data'][-20:]:
            v = k.get('volume') if isinstance(k, dict) else getattr(k, 'volume', None)
            if v:
                volumes.append(v)
        return sum(volumes) / len(volumes) if volumes else None
    return provider


def create_watch_engine() -> WatchEngine:
    notifier = WatchNotifier(
        agent_service=AgentNotificationService(),
        trigger_repo=WatchTriggerRepository(),
    )
    return WatchEngine(
        rule_repo=WatchRuleRepository(),
        quote_service=RealtimeQuoteServiceV2(),
        notifier=notifier,
        avg_volume_provider=make_avg_volume_provider(),
    )


def start_watch_engine_in_thread() -> threading.Thread:
    """daemon 线程启动引擎，随主进程退出"""
    engine = create_watch_engine()
    thread = threading.Thread(target=engine.run_forever, name='watch-engine', daemon=True)
    thread.start()
    logger.info('✓ WatchEngine 已在后台线程启动')
    return thread
