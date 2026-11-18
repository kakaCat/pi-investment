"""V2 条件求值所需的行情数据 provider。"""
from datetime import datetime, timedelta
from typing import Optional

import structlog

from qs_kernel.domain.ports.datasource_ports import IDataProviderManager
from qs_market_data.adapters.outbound.datasources.manager import get_data_provider_manager

logger = structlog.get_logger(__name__)


def make_avg_volume_provider():
    def provider(symbol: str) -> Optional[float]:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
        bare_symbol = symbol.split('.')[0]
        result: IDataProviderManager = get_data_provider_manager().get_klines(
            bare_symbol, 'daily', start, end)
        if not result.get('success'):
            logger.warning('均量获取失败，volume_surge 降级', symbol=symbol)
            return None
        volumes = []
        for item in result['data'][-20:]:
            value = item.get('volume') if isinstance(item, dict) else getattr(item, 'volume', None)
            if value:
                volumes.append(value)
        if not volumes:
            logger.warning('均量获取失败，volume_surge 降级', symbol=symbol, reason='empty_volumes')
            return None
        return sum(volumes) / len(volumes)
    return provider


def make_fund_flow_provider():
    from qs_market_data.adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
    datasource = FundFlowDataSource()
    cache: dict = {}

    def provider(symbol: str):
        from datetime import date
        bare = symbol.split('.')[0]
        key = (bare, date.today())
        if key in cache:
            return cache[key]
        try:
            result = datasource.get_stock_fund_flow(bare, days=5)
            summary = (result or {}).get('summary') or {}
            out = {
                'total_main_net_inflow_yi': round(
                    float(summary.get('total_main_net_inflow', 0)) / 1e8, 2),
                'consecutive_inflow_days': int(summary.get('consecutive_inflow_days') or 0),
                'trend': summary.get('trend'),
                'days': 5,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning('资金流向取数失败（fund_flow 条件降级）', symbol=bare, error=str(exc))
            out = None
        cache[key] = out
        return out
    return provider


def make_kline_closes_provider():
    cache: dict = {}

    def provider(symbol: str):
        from datetime import date, timedelta
        bare = symbol.split('.')[0]
        key = (bare, date.today())
        if key in cache:
            return cache[key]
        try:
            end = date.today().strftime('%Y-%m-%d')
            start = (date.today() - timedelta(days=240)).strftime('%Y-%m-%d')
            result = get_data_provider_manager().get_klines(bare, 'daily', start, end)
            if not result.get('success') or not result.get('data'):
                cache[key] = None
                return None
            closes = []
            for item in result['data'][-130:]:
                close = item.get('close') if isinstance(item, dict) else getattr(item, 'close', None)
                if close is not None:
                    closes.append(float(close))
            out = tuple(closes) if len(closes) >= 25 else None
        except Exception as exc:  # noqa: BLE001
            logger.warning('日线收盘取数失败（MA/RSI 条件降级）', symbol=bare, error=str(exc))
            out = None
        cache[key] = out
        return out
    return provider
