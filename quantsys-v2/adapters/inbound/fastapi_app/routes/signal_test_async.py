"""信号测试日志 API - FastAPI 版（从 Flask signal_test.py 迁移，响应契约保持一致）

复用同一 SignalTestLog / StrategyPerformanceORMRepository / StrategyFactory。
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import structlog

from adapters.inbound.fastapi_app.shared import error_response, handle_api_error
from adapters.shared.services import signal_test_log
from adapters.outbound.repositories import StrategyPerformanceORMRepository

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Signal Test - 信号测试"])

_test_log = signal_test_log
_perf_repo = StrategyPerformanceORMRepository()


@router.post('/api/signal-test/record')
@handle_api_error
def record_signal(payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    required = ['symbol', 'strategy_name', 'action']
    missing = [f for f in required if f not in data]
    if missing:
        return error_response({'success': False, 'error': f'缺少必需字段: {missing}'}, 400)
    record_id = _test_log.record_signal(data)
    return {'success': True, 'id': record_id}


@router.post('/api/signal-test/verify')
@handle_api_error
def verify_signals(payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    days_after = data.get('days_after', 5)
    result = _test_log.verify_pending(days_after=days_after)
    return {'success': True, **result}


@router.get('/api/signal-test/stats')
@handle_api_error
def get_stats(strategy: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
              end_date: Optional[str] = Query(None)):
    result = _test_log.get_stats(strategy, start_date, end_date)
    return {'success': True, **result}


@router.post('/api/signal-test/run-strategy')
@handle_api_error
def run_strategy_and_record(payload: Optional[Dict[str, Any]] = Body(None)):
    """对指定股票运行多因子波段策略，记录信号。"""
    data = payload or {}
    symbol = (data.get('symbol') or '').strip()
    if not symbol:
        return error_response({'success': False, 'error': 'symbol 不能为空'}, 400)

    strategy_name = data.get('strategy', 'multi_factor_swing')
    days = int(data.get('days', 120))

    # 1. 获取 K 线数据
    try:
        from adapters.outbound.repositories import KlineORMRepository
        kline_repo = KlineORMRepository()
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
        klines = kline_repo.get_daily_klines(symbol, start_date, end_date)
    except Exception as e:
        return error_response({'success': False, 'error': f'{symbol} 获取K线失败: {e}'}, 500)

    # get_daily_klines 返回 polars DataFrame：bool(df) 抛 TypeError、
    # klines[-1] 取出 1 行 DataFrame 再 .get 抛 AttributeError——先转 dict 列表
    if hasattr(klines, 'to_dicts'):
        klines = klines.to_dicts()

    if not klines or len(klines) < 30:
        return error_response({'success': False, 'error': f'{symbol} K线数据不足 ({len(klines) if klines else 0}条)'}, 400)

    # 2. 获取实时价格（最新K线收盘价）
    signal_price = float(klines[-1].get('close', 0))
    signal_date = klines[-1].get('trade_date', klines[-1].get('date', datetime.now().strftime('%Y-%m-%d')))

    # 3. 获取股票名称
    stock_info = {}
    try:
        from adapters.outbound.repositories import StockORMRepository
        stock_repo = StockORMRepository()
        stock_info = stock_repo.get_by_symbol(symbol) or {}
    except Exception:
        pass
    stock_name = stock_info.get('name', '')

    # 4. 获取资金流数据（使用 v2 原生 SentimentService，替代已删除的 quant_cli）
    fund_flow_data = None
    try:
        from application.services.sentiment_service import SentimentService
        from adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
        fund_flow_source = FundFlowDataSource()
        sentiment_service = SentimentService(fund_flow_source)
        ff_result = sentiment_service.get_stock_fund_flow(symbol, days=10)
        if ff_result and isinstance(ff_result, dict) and 'data' in ff_result:
            # SentimentService 返回格式与旧 quant_cli 不同，适配之
            fund_flow_data = ff_result.get('data', [])
    except Exception:
        pass  # 资金流不可用時静默降级

    # 5. 运行策略
    from domain.backtest.engine.strategy_factory import StrategyFactory
    if not StrategyFactory._registry:
        StrategyFactory.auto_discover()
    try:
        strategy = StrategyFactory.create(strategy_name)
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)

    try:
        raw_signal = strategy.generate_signal(klines, fund_flow_data=fund_flow_data)
    except Exception as e:
        return error_response({'success': False, 'error': f'策略执行失败: {e}'}, 500)

    # 6. 补充信号元数据
    signal = {
        'symbol': symbol,
        'name': stock_name,
        'strategy_name': strategy.name if strategy.name != 'MultiFactorSwingStrategy' else 'multi_factor_swing',
        'signal_date': signal_date,
        'action': raw_signal.get('action', 'hold'),
        'confidence': raw_signal.get('confidence', 0),
        'signal_price': signal_price,
        'entry_price': raw_signal.get('entry_price', signal_price),
        'stop_loss': raw_signal.get('stop_loss_price'),
        'reason': raw_signal.get('reason', ''),
        'details': raw_signal.get('details', {}),
    }

    # 7. 记录到测试表
    record_id = None
    if signal['action'] in ('buy', 'sell') and signal['confidence'] > 0.5:
        record_id = _test_log.record_signal(signal)

    return {'success': True, 'signal': {**signal, 'record_id': record_id}}
