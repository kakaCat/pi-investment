"""WatchEngine 装配：构建引擎 + 后台线程启动"""
import threading
from datetime import datetime, timedelta
from typing import Optional
from domain.ports.datasource_ports import IDataProviderManager

import structlog

from adapters.outbound.datasources.manager import get_data_provider_manager
from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository
)
from application.services.agent_notification_service import AgentNotificationService
from application.services.realtime_quote_service_v2 import RealtimeQuoteServiceV2
from application.services.watch_engine.engine import WatchEngine
from application.services.watch_engine.notifier import WatchNotifier
from adapters.outbound.repositories.simulation_position_repository import SimulationPositionRepository

logger = structlog.get_logger(__name__)


def make_avg_volume_provider():
    """近 20 日日均成交量 provider。失败返回 None（volume_surge 降级不判定）"""
    def provider(symbol: str) -> Optional[float]:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
        # 归一化为裸代码：akshare 只接受 6 位代码，DB miss 时 fallback 会失败
        bare_symbol = symbol.split('.')[0]
        result: IDataProviderManager = get_data_provider_manager().get_klines(bare_symbol, 'daily', start, end)
        if not result.get('success'):
            logger.warning('均量获取失败，volume_surge 降级', symbol=symbol)
            return None
        # data 为 List[KlineData] dataclass（非 dict），用属性访问；兼容 dict 兜底
        volumes = []
        for k in result['data'][-20:]:
            v = k.get('volume') if isinstance(k, dict) else getattr(k, 'volume', None)
            if v:
                volumes.append(v)
        if not volumes:
            logger.warning('均量获取失败，volume_surge 降级', symbol=symbol, reason='empty_volumes')
            return None
        return sum(volumes) / len(volumes)
    return provider


def create_watch_engine() -> WatchEngine:
    notifier = WatchNotifier(
        trigger_repo=WatchTriggerRepository(),
    )
    _pos_repo = SimulationPositionRepository()

    def position_value_provider(rule):
        # 介入判据金额门：持仓级动作影响金额 = 该标的持仓市值
        account = getattr(rule, 'account', None) or 'agent_virtual'
        symbol = str(getattr(rule, 'symbol', '')).split('.')[0]
        try:
            pos = _pos_repo.get_position(account, symbol)
            if pos is None:
                return None
            return float(getattr(pos, 'market_value', 0) or 0)
        except Exception:
            return None

    def account_total_provider():
        # 介入判据金额门：账户总资产
        try:
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
            status = SimulationORMRepository().get_account_status('agent_virtual')
            if isinstance(status, dict):
                return float(status.get('total_value') or 0) or None
            return float(getattr(status, 'total_value', 0) or 0) or None
        except Exception:
            return None

    return WatchEngine(
        rule_repo=WatchRuleRepository(),
        quote_service=RealtimeQuoteServiceV2(),
        notifier=notifier,
        avg_volume_provider=make_avg_volume_provider(),
        position_value_provider=position_value_provider,
        account_total_provider=account_total_provider,
    )


def start_watch_engine_in_thread() -> tuple[WatchEngine, threading.Thread]:
    """daemon 线程启动引擎，随主进程退出。返回 (engine, thread) 供调用方留存句柄优雅停止"""
    engine = create_watch_engine()
    thread = threading.Thread(target=engine.run_forever, name='watch-engine', daemon=True)
    thread.start()
    logger.info('✓ WatchEngine 已在后台线程启动')
    return engine, thread
