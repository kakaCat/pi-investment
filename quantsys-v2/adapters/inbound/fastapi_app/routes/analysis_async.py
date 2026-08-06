"""分析 API - FastAPI 版（迁移 web 实际使用的分析端点，响应契约保持一致）

覆盖：/api/backtest（backtest.py）、/api/compute/factors（jobs.py）、
/api/stock/{symbol}/technical（analysis.py）。复用各文件的辅助函数与同一 ds 单例。
（原 analysis_async.py 的 factors/klines/compare/swing-points 为 FastAPI-only/死端点，web 未使用，已替换。）
"""
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body, Request
import structlog

from adapters.shared import _V2_ROOT
from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error, sanitize_for_json,
    convert_keys_to_snake, convert_keys_to_camel, strategy_service, scoring_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Analysis - 分析"])


# ============ /api/backtest（backtest.py） ============

@router.post('/api/backtest')
def run_backtest(payload: Optional[Dict[str, Any]] = Body(None)):
    """运行回测 - 支持 strategy_name、strategy_id 或 indicator_id"""
    from adapters.shared.backtest_helpers import (
        save_simple_backtest, run_pe_mean_reversion_backtest, run_pb_mean_reversion_backtest,
    )
    raw_data = payload or {}
    data = convert_keys_to_snake(raw_data)

    if 'strategy' in data and 'strategy_name' not in data:
        data['strategy_name'] = data['strategy']

    if 'indicator_id' in data and 'strategy_name' not in data:
        try:
            indicator_id = int(data['indicator_id'])
            data['strategy_name'] = f"indicator_{indicator_id}"
        except (ValueError, TypeError) as e:
            return error_response({'error': f'无效的 indicator_id: {e}'}, 400)

    if 'strategy_id' in data and 'strategy_name' not in data:
        try:
            strat = strategy_service.get_strategy(int(data['strategy_id']))
            if not strat:
                return error_response({'error': f'策略不存在: {data["strategy_id"]}'}, 404)
            data['strategy_name'] = strat.get('name') or f"strategy_{data['strategy_id']}"
        except (ValueError, TypeError) as e:
            return error_response({'error': f'无效的 strategy_id: {e}'}, 400)

    if 'parameters' not in data and isinstance(data.get('params'), dict):
        data['parameters'] = data['params']

    if 'parameters' in data and isinstance(data['parameters'], dict):
        params = data['parameters']
        param_mappings = {
            'fast_period': 'ma_short', 'slow_period': 'ma_long', 'rsi_period': 'rsi_period',
            'short_period': 'ma_short', 'long_period': 'ma_long',
            'pe_heavy_buy': 'pe_heavy_buy', 'pe_batch_buy': 'pe_batch_buy', 'pe_reduce': 'pe_reduce',
            'pe_liquidate': 'pe_liquidate', 'eps_start': 'eps_start', 'eps_end': 'eps_end',
            'stop_loss_pct': 'stop_loss_pct', 'take_profit_pct': 'take_profit_pct',
            'dividend_yield': 'dividend_yield',
            'pb_heavy_buy': 'pb_heavy_buy', 'pb_batch_buy': 'pb_batch_buy', 'pb_reduce': 'pb_reduce',
            'pb_liquidate': 'pb_liquidate', 'roe_mean': 'roe_mean',
        }
        for source_key, target_key in param_mappings.items():
            if source_key in params and target_key not in data:
                data[target_key] = params[source_key]
        del data['parameters']
    data.pop('params', None)

    if 'initial_cash' in data and 'initial_capital' not in data:
        data['initial_capital'] = data['initial_cash']

    required = ['strategy_name', 'symbol', 'start_date', 'end_date', 'initial_capital']
    for field in required:
        if field not in data:
            return error_response({'error': f'缺少必需参数: {field}'}, 400)

    strategy_name = data['strategy_name'].lower()
    if 'indicator' not in strategy_name:
        if 'ma' in strategy_name or 'cross' in strategy_name:
            if 'ma_short' not in data:
                return error_response({'error': '移动平均策略缺少参数: ma_short (或 fastPeriod)'}, 400)
            if 'ma_long' not in data:
                return error_response({'error': '移动平均策略缺少参数: ma_long (或 slowPeriod)'}, 400)
        elif 'rsi' in strategy_name:
            if 'rsi_period' not in data:
                return error_response({'error': 'RSI策略缺少参数: rsi_period (或 rsiPeriod)'}, 400)

    try:
        workflow_data = ds.get_backtest_workflow_data(
            data['symbol'], data['start_date'], data['end_date'], period=data.get('period'))
        klines = workflow_data['klines']
        if not klines:
            return error_response({'error': '没有K线数据'}, 400)
        initial_capital = float(data['initial_capital'])
        if 'pe' in strategy_name and 'mean' in strategy_name:
            result = run_pe_mean_reversion_backtest(data, klines, initial_capital)
        elif 'pb' in strategy_name and 'mean' in strategy_name:
            result = run_pb_mean_reversion_backtest(data, klines, initial_capital)
        else:
            result = save_simple_backtest(data, klines, initial_capital)
        result = convert_keys_to_camel(result)
        return sanitize_for_json(result)
    except Exception as e:
        return error_response({'error': str(e)}, 500)


# ============ /api/compute/factors（jobs.py） ============

@router.post('/api/compute/factors')
def compute_factors(payload: Optional[Dict[str, Any]] = Body(None)):
    """计算因子（支持单个symbol或批量symbols）"""
    from adapters.shared.fund_flow_helpers import (
        _inject_fund_flow_to_klines, _fetch_financial_data, _extract_fund_flow_factors,
    )
    data = payload or {}
    symbol = data.get('symbol')
    symbols = data.get('symbols', [])
    requested_factors = data.get('factors', [])
    include_fundamental = data.get('include_fundamental', False)

    if not include_fundamental and requested_factors:
        fundamental_names = {'fscore', 'earnings_quality'}
        if fundamental_names & set(requested_factors):
            include_fundamental = True

    all_symbols = list(symbols) if symbols else []
    if symbol and symbol not in all_symbols:
        all_symbols.append(symbol)
    if not all_symbols:
        return error_response({'error': '缺少symbol或symbols参数'}, 400)

    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
        from domain.quantlib.stages.factor_stage import FactorStage

        results = []
        for sym in all_symbols:
            klines_df = ds.kline.get_daily_klines(sym, start_date, end_date)
            if klines_df is None or klines_df.is_empty():
                results.append({'symbol': sym, 'error': 'No kline data'})
                continue
            klines = klines_df.to_dicts()
            klines = _inject_fund_flow_to_klines(klines, sym)
            financial_data = None
            if include_fundamental:
                financial_data = _fetch_financial_data(sym)
            stage = FactorStage(name="factors", factor_names=requested_factors if requested_factors else None)
            stage_input = {'symbol': sym, 'klines': klines}
            if financial_data:
                stage_input['financial_data'] = financial_data
            if requested_factors:
                stage_input['requested_factors'] = requested_factors
            result = stage.process(stage_input)
            factors = result.get('factors', {})
            fund_factors = _extract_fund_flow_factors(klines)
            factors.update(fund_factors)
            last_row = klines[-1]
            latest_date = last_row.get('trade_date') or last_row.get('date') or ''
            ds.factor.save_factors(sym, str(latest_date), factors)
            results.append({
                'symbol': sym, 'date': str(latest_date),
                'factor_count': len(factors), 'factors': factors,
            })
        return sanitize_for_json({'success': True, 'results': results, 'count': len(results)})
    except Exception as e:
        return error_response({'error': str(e)}, 500)


# ============ /api/stock/{symbol}/technical（analysis.py） ============

@router.get('/api/stock/{symbol}/technical')
def get_technical_indicators(symbol: str, indicators: Optional[str] = Query(None)):
    """计算技术指标"""
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
        klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
        if klines_df is None or klines_df.is_empty():
            return error_response({'error': f'No kline data for {symbol}'}, 404)
        if len(klines_df) < 20:
            return error_response({
                'error': f'Insufficient data for {symbol} (need 20+ days, got {len(klines_df)})'}, 400)
        klines = klines_df.to_dicts()
        from domain.quantlib.stages.factor_stage import FactorStage
        stage = FactorStage(name="technical")
        result = stage.process({'symbol': symbol, 'klines': klines})
        factors = result.get('factors', {})
        if indicators:
            wanted = indicators.split(',')
            factors = {k: factors[k] for k in wanted if k in factors}
        return sanitize_for_json({'symbol': symbol, 'factors': factors, 'data_days': len(klines)})
    except Exception as e:
        return error_response({'error': str(e)}, 500)


# ============ /api/stock/{symbol}/factors（analysis.py） ============

@router.get('/api/stock/{symbol}/factors')
@router.get('/api/stocks/{symbol}/factors')
def get_stock_factors(symbol: str, date: Optional[str] = Query(None)):
    """获取股票因子分析（与 Flask analysis.py 一致）"""
    try:
        factors = ds.factor.get_latest_factors(symbol) if not date else ds.factor.get_factors(symbol, date)
        stock_info = ds.stock.get_by_symbol(symbol)
        kline = ds.kline.get_latest_daily_kline(symbol)
        latest_signals = ds.signal.get_signals_by_symbol(symbol, '2024-01-01', date or '2026-12-31')
        return sanitize_for_json({
            'symbol': symbol,
            'stock_name': stock_info['name'] if stock_info else '',
            'market': stock_info['market'] if stock_info else '',
            'current_price': kline['close'] if kline else None,
            'factors': factors,
            'signals_count': len(latest_signals),
        })
    except Exception as e:
        return error_response({'error': str(e)}, 500)


# ============ /api/stock/{symbol}/price-action（analysis.py） ============

@router.get('/api/stock/{symbol}/price-action')
@handle_api_error
def get_price_action(symbol: str, period: int = Query(60)):
    """价格行为分析"""
    try:
        from application.services.technical_analysis_service import TechnicalAnalysisService
        tech_service = TechnicalAnalysisService()
        result = tech_service.analyze_price_action(symbol, period=period)
        if 'error' in result:
            return error_response({'success': False, 'error': result['error']}, 400)
        return api_response(result)
    except Exception as e:
        logger.error(f"Price action analysis failed: {e}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ /api/stock/{symbol}/buy-range（analysis.py） ============

@router.get('/api/stock/{symbol}/buy-range')
@handle_api_error
def get_buy_range(symbol: str,
                  enhanced: str = Query('false'),
                  periods: str = Query('daily'),
                  volume: str = Query('true'),
                  fundamental: str = Query('true')):
    """买入区间计算（简化模式 + 增强模式）"""
    try:
        if enhanced.lower() == 'true':
            from application.services.enhanced_buy_range_service import EnhancedBuyRangeService

            period_list = [p.strip() for p in periods.split(',')]
            include_volume = volume.lower() == 'true'
            include_fundamental = fundamental.lower() == 'true'

            service = EnhancedBuyRangeService()
            result = service.calculate_enhanced_buy_range(
                symbol=symbol,
                periods=period_list,
                include_volume=include_volume,
                include_fundamental=include_fundamental
            )
        else:
            from application.services.technical_analysis_service import TechnicalAnalysisService

            tech_service = TechnicalAnalysisService()
            result = tech_service.calculate_buy_range(symbol)

        if not result.get('success', True):
            return error_response(
                {'success': False, 'error': result.get('error', 'Unknown error')}, 400)

        return api_response(result.get('data', result))
    except Exception as e:
        logger.error(f"买入区间计算失败: {str(e)}")
        return error_response({'success': False, 'error': f'计算失败: {str(e)}'}, 500)


# ============ /api/stock/{symbol}/exit-plan（analysis.py） ============

def _get_exit_recommendation(profit_pct):
    """根据当前盈亏给出建议"""
    if profit_pct < -8:
        return {'action': '立即止损', 'reason': '已触发严格止损线', 'urgency': 'high'}
    elif profit_pct < -5:
        return {'action': '警戒观察', 'reason': '接近止损线，密切关注', 'urgency': 'medium'}
    elif profit_pct < 5:
        return {'action': '持有观察', 'reason': '尚未达到止盈目标', 'urgency': 'low'}
    elif profit_pct < 10:
        return {'action': '考虑减仓', 'reason': '接近第一止盈目标', 'urgency': 'low'}
    elif profit_pct < 20:
        return {'action': '分批止盈', 'reason': '建议卖出30%锁定利润', 'urgency': 'medium'}
    elif profit_pct < 30:
        return {'action': '继续减仓', 'reason': '建议再卖出30%', 'urgency': 'medium'}
    else:
        return {'action': '大部止盈', 'reason': '建议卖出剩余持仓的大部分', 'urgency': 'high'}


def _format_exit_plan(plan):
    """格式化退出计划为文本"""
    lines = [
        f"═══ 退出计划：{plan['symbol']} {plan['name']} ═══",
        "",
        f"买入价格：¥{plan['buy_price']:.2f}",
        f"当前价格：¥{plan['current_price']:.2f}",
        f"持仓数量：{plan['position_size']} 股",
        f"当前盈亏：{plan['profit_pct']:+.2f}% (¥{plan['profit_amount']:+.2f})",
        "",
        "─── 止损策略 ───",
        f"严格止损：¥{plan['stop_loss']['strict']:.2f} (-8%)",
        f"警戒线　：¥{plan['stop_loss']['warning']:.2f} (-5%)",
        "",
        "─── 止盈策略（分批卖出）───",
        f"目标一：¥{plan['take_profit']['target_1']['price']:.2f} (+10%) → 卖出30%",
        f"目标二：¥{plan['take_profit']['target_2']['price']:.2f} (+20%) → 卖出30%",
        f"目标三：¥{plan['take_profit']['target_3']['price']:.2f} (+30%) → 卖出40%",
        "",
        "─── 当前建议 ───",
        f"操作：{plan['recommendation']['action']}",
        f"理由：{plan['recommendation']['reason']}",
        f"紧急程度：{plan['recommendation']['urgency'].upper()}",
    ]
    return '\n'.join(lines)


@router.get('/api/stock/{symbol}/exit-plan')
@handle_api_error
def get_exit_plan(symbol: str,
                  buy_price: Optional[float] = Query(None),
                  position_size: int = Query(100)):
    """退出计划 - 止盈、止损和分批卖出策略"""
    try:
        from application.services.data_service import DataService
        data_service = DataService()

        # 确保 symbol 有后缀
        if '.' not in symbol:
            symbol_with_suffix = symbol + ('.SH' if symbol.startswith('6') else '.SZ')
        else:
            symbol_with_suffix = symbol

        # 尝试获取最近的K线数据作为当前价格
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)  # 获取最近5天数据

        klines = data_service.kline.get_daily_klines(
            symbol_with_suffix,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        # get_daily_klines 返回 polars DataFrame：bool(df) 抛 TypeError、
        # klines[-1] 取出 1 行 DataFrame 再 .get 抛 AttributeError——先转 dict 列表
        if hasattr(klines, 'to_dicts'):
            klines = klines.to_dicts()

        if not klines or len(klines) == 0:
            return error_response(
                {'success': False, 'error': f'无法获取 {symbol} 的价格数据'}, 404)

        # 使用最新的收盘价
        latest_kline = klines[-1]
        current_price = latest_kline.get('close')

        if not current_price:
            return error_response({'success': False, 'error': '无法解析价格数据'}, 404)

        # 如果未提供 buy_price，使用当前价
        if not buy_price:
            buy_price = float(current_price)

        # 获取股票名称
        stock_info = data_service.stock.get_by_symbol(symbol_with_suffix) or {}
        stock_name = stock_info.get('name', symbol)

        # 计算收益率
        profit_pct = ((current_price - buy_price) / buy_price) * 100
        profit_amount = (current_price - buy_price) * position_size

        # 生成退出计划
        exit_plan = {
            'symbol': symbol,
            'name': stock_name,
            'buy_price': buy_price,
            'current_price': current_price,
            'position_size': position_size,
            'profit_pct': round(profit_pct, 2),
            'profit_amount': round(profit_amount, 2),

            # 止损策略（-8% 严格止损，-5% 警戒）
            'stop_loss': {
                'strict': round(buy_price * 0.92, 2),
                'warning': round(buy_price * 0.95, 2)
            },

            # 止盈策略（分三档）
            'take_profit': {
                'target_1': {'price': round(buy_price * 1.10, 2), 'pct': 10, 'sell_ratio': 0.3},
                'target_2': {'price': round(buy_price * 1.20, 2), 'pct': 20, 'sell_ratio': 0.3},
                'target_3': {'price': round(buy_price * 1.30, 2), 'pct': 30, 'sell_ratio': 0.4}
            },

            # 当前建议
            'recommendation': _get_exit_recommendation(profit_pct)
        }

        # 格式化输出
        formatted = _format_exit_plan(exit_plan)

        return api_response({'exit_plan': exit_plan, 'formatted': formatted})

    except Exception as e:
        return error_response({'success': False, 'error': f'生成退出计划失败: {str(e)}'}, 500)


# ============ /api/stock/{symbol}/pe-percentile（analysis.py） ============

@router.get('/api/stock/{symbol}/pe-percentile')
@handle_api_error
def get_pe_percentile(symbol: str, years: int = Query(3)):
    """PE历史分位 - 使用数据库历史数据计算 PE 分位数"""
    try:
        import pandas as pd
        from application.services.data_service import DataService

        data_service = DataService()

        # 获取股票基本信息（包含当前 PE）
        stock_info = data_service.stock.get_by_symbol(symbol)
        if not stock_info:
            return error_response({'success': False, 'error': '股票不存在'}, 404)

        # 修复：Stock 是 ORM 对象，使用属性访问而非 .get()
        current_pe = stock_info.pe
        if not current_pe or current_pe <= 0:
            return error_response({'success': False, 'error': 'PE数据不可用'}, 404)

        # 获取历史 K 线数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)

        klines = data_service.kline.get_daily_klines(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        # 修复：避免 polars DataFrame 的 ambiguous truth value 错误
        if klines is None or len(klines) < 20:
            return error_response({'success': False, 'error': '历史数据不足'}, 404)

        # 修复：处理 polars DataFrame - 转换为字典列表
        import polars as pl
        if isinstance(klines, pl.DataFrame):
            klines = klines.to_dicts()

        # 计算历史 PE（价格 / 当前股价 * 当前PE）
        latest_price = klines[-1].get('close', 0)
        pe_values = []
        for kline in klines:
            price = kline.get('close', 0)
            if latest_price > 0:
                # 假设 EPS 不变，历史 PE = 历史价格 / 最新价格 * 当前PE
                historical_pe = (price / latest_price) * current_pe
                if historical_pe > 0:
                    pe_values.append(historical_pe)

        if len(pe_values) < 20:
            return error_response({'success': False, 'error': 'PE数据点不足'}, 404)

        # 计算分位数
        pe_series = pd.Series(pe_values)
        # 修复：明确计算布尔值的 sum，避免 DataFrame ambiguous truth value 错误
        count_below = int((pe_series < current_pe).sum())
        total_count = len(pe_series)
        percentile = (count_below / total_count * 100) if total_count > 0 else 0.0

        result = {
            'symbol': symbol,
            'name': stock_info.name,
            'current_pe': round(float(current_pe), 2),
            'current_price': round(float(latest_price), 2),
            'percentile': round(percentile, 2),
            'min_pe': round(float(pe_series.min()), 2),
            'max_pe': round(float(pe_series.max()), 2),
            'mean_pe': round(float(pe_series.mean()), 2),
            'median_pe': round(float(pe_series.median()), 2),
            'data_points': len(pe_values),
            'years': years,
            'interpretation': '低估' if percentile < 30 else '合理' if percentile < 70 else '高估'
        }

        return api_response(result)
    except Exception as e:
        import traceback
        logger.error(f"PE百分位查询失败: {traceback.format_exc()}")
        return error_response({'success': False, 'error': f'查询失败: {str(e)}'}, 500)


# ============ /api/stock/{symbol}/candlestick（analysis.py） ============

@router.get('/api/stock/{symbol}/candlestick')
@handle_api_error
def get_candlestick(symbol: str):
    """K线形态分析"""
    try:
        from application.services.technical_analysis_service import TechnicalAnalysisService
        tech_service = TechnicalAnalysisService()
        result = tech_service.analyze_candlestick(symbol)
        if 'error' in result:
            return error_response({'success': False, 'error': result['error']}, 400)
        return api_response(result)
    except Exception as e:
        logger.error(f"Candlestick analysis failed: {e}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ /api/stock/{symbol}/indicators（analysis.py） ============

@router.get('/api/stock/{symbol}/indicators')
@handle_api_error
def get_indicators(symbol: str):
    """财务指标 - v2 原生实现"""
    from application.services.financial_analysis_service import FinancialAnalysisService
    service = FinancialAnalysisService()
    result = service.get_financial_indicators(symbol)

    # 统一返回格式，确保总是返回有效的 JSON
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


# ============ /api/stock/{symbol}/valuation（analysis.py） ============

@router.get('/api/stock/{symbol}/valuation')
@handle_api_error
def get_valuation(symbol: str):
    """估值分析 - v2 原生实现"""
    from application.services.financial_analysis_service import FinancialAnalysisService
    service = FinancialAnalysisService()
    result = service.get_stock_valuation(symbol)

    # 统一返回格式，确保总是返回有效的 JSON
    # 即使失败也返回结构化的错误信息，不返回空响应
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


# ============ /api/stock/{symbol}/score（analysis.py） ============

@router.get('/api/stock/{symbol}/score')
@handle_api_error
def get_stock_score(symbol: str):
    """多因子评分 - 使用 v2 StockScoringService"""
    from adapters.shared import stock_scoring_service

    result = stock_scoring_service.calculate_comprehensive_score(symbol)
    if 'error' in result:
        return error_response({'success': False, 'error': result['error']}, 400)
    return api_response(result)


# ============ /api/stock/{symbol}/quality（analysis.py） ============

@router.get('/api/stock/{symbol}/quality')
@handle_api_error
def get_quality_score_v2(symbol: str, framework: str = Query('auto')):
    """质量评分 - 使用 v2 QualityScoringService"""
    try:
        from application.services.quality_scoring_service import QualityScoringService

        quality_service = QualityScoringService(ds)
        result = quality_service.calculate_quality_score(symbol, framework=framework)

        if 'error' in result:
            return error_response({'success': False, 'error': result['error']}, 400)
        return api_response(result)
    except ImportError as e:
        logger.error(f"Import error in quality route: {e}", exc_info=True)
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)
    except Exception as e:
        logger.error(f"Error in quality route: {e}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ /api/stock/{symbol}/data-health（analysis.py） ============

@router.get('/api/stock/{symbol}/data-health')
@handle_api_error
def get_data_health(symbol: str):
    """单票数据健康检查（保持 snake_case，绕过 api_response 的驼峰转换）"""
    from application.services.stock_code_validator import StockCodeValidator

    validator = StockCodeValidator()
    result = validator.validate(symbol)

    # validate() 内部异常时会在结果里带 error 字段
    if result.get('error'):
        return error_response({'success': False, 'error': result['error']}, 500)

    # 保持 snake_case，绕过 api_response() 的驼峰转换
    return {'success': True, 'data': result}


# ============ /api/market/sentiment（market.py，analysis.py 中同名端点已注释，以此为准） ============

@router.get('/api/market/sentiment')
@handle_api_error
def get_market_sentiment():
    """市场情绪分析 - v2 原生实现"""
    from application.services.market_sentiment_service import MarketSentimentService

    # 初始化服务
    sentiment_service = MarketSentimentService(ds)

    # 分析市场情绪
    result = sentiment_service.analyze_market_sentiment()

    if 'error' in result:
        return error_response({'success': False, 'error': result['error']}, 400)

    return api_response(result)


# ============ /api/stocks/screen（analysis.py） ============

@router.get('/api/stocks/screen')
@handle_api_error
def screen_stocks_v2(request: Request):
    """多条件选股 - 使用 v2 原生实现"""
    try:
        from application.services.stock_screening_service import StockScreeningService

        # 解析筛选条件
        criteria = {}
        for key in ['min_score', 'max_pe', 'min_roe', 'max_debt_ratio', 'min_market_cap', 'max_market_cap']:
            val = request.query_params.get(key)
            if val is not None:
                criteria[key] = float(val) if '.' in str(val) else int(val)

        # 获取其他参数（对齐 Flask request.args.get('limit', 20, type=int)：非法值回落默认）
        raw_limit = request.query_params.get('limit')
        try:
            limit = int(raw_limit) if raw_limit is not None else 20
        except (ValueError, TypeError):
            limit = 20
        if limit:
            criteria['limit'] = limit

        # 使用筛选服务 (需要 ds 和 scoring_service)
        screening_service = StockScreeningService(ds, scoring_service)
        result = screening_service.screen_stocks(criteria)

        if 'error' in result:
            return error_response({'success': False, 'error': result['error']}, 400)
        return api_response(result)
    except ImportError as e:
        logger.error(f"Import error in screen_stocks: {e}", exc_info=True)
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)
    except Exception as e:
        logger.error(f"Error in screen_stocks: {e}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ /api/screening/quality（analysis.py） ============

@router.get('/api/screening/quality')
@handle_api_error
def screening_quality(sector: str = Query(''),
                      min_score: int = Query(50),
                      max_pe: Optional[float] = Query(None),
                      limit: int = Query(10)):
    """行业质量筛选 - 使用 v2 质量评分服务"""
    # 使用 v2 的质量评分和筛选功能
    from application.services.stock_screening_service import StockScreeningService

    criteria = {'min_score': min_score, 'limit': limit}
    if max_pe:
        criteria['max_pe'] = max_pe

    screening_service = StockScreeningService(ds, scoring_service)
    result = screening_service.screen_stocks(criteria)

    # 如果指定了行业，进行过滤
    if sector and 'stocks' in result:
        result['stocks'] = [s for s in result['stocks'] if s.get('sector') == sector]
        result['matched'] = len(result['stocks'])

    return api_response(result)


# ============ /api/risk/stress-test（analysis.py） ============

@router.post('/api/risk/stress-test')
@handle_api_error
def risk_stress_test():
    """压力测试 - 已弃用"""
    return error_response(
        {'success': False, 'error': 'This endpoint is deprecated and not yet reimplemented in v2'},
        410)


# ============ /api/risk/price-alert（analysis.py） ============

@router.post('/api/risk/price-alert')
@handle_api_error
def risk_price_alert(payload: Optional[Dict[str, Any]] = Body(None)):
    """价格预警 - 替代旧 quant_cli watch.price_alert"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.risk_watch_analytics import price_alert
        data = payload or {}
        quant_root = _V2_ROOT.parent / 'quant'
        result = price_alert(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)


# ============ /api/risk/trade-verify（analysis.py） ============

@router.post('/api/risk/trade-verify')
@handle_api_error
def risk_trade_verify(payload: Optional[Dict[str, Any]] = Body(None)):
    """交易实盘回测对比 - 替代旧 quant_cli trade.verify"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.trade_portfolio_analytics import verify_trades
        data = payload or {}
        quant_root = _V2_ROOT.parent / 'quant'
        result = verify_trades(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)


# ============ /api/risk/metrics（analysis.py） ============

@router.post('/api/risk/metrics')
@handle_api_error
def calculate_risk_metrics(payload: Optional[Dict[str, Any]] = Body(None)):
    """计算风险指标 - 使用 empyrical 标准算法"""
    from application.services.risk_metrics_service import RiskMetricsService
    import pandas as pd

    data = payload or {}

    # 参数验证
    returns = data.get('returns')
    if not returns:
        return error_response({
            'success': False,
            'error': 'returns 参数不能为空'
        }, 400)

    benchmark_returns = data.get('benchmark_returns') or data.get('benchmarkReturns')
    risk_free_rate = data.get('risk_free_rate') or data.get('riskFreeRate', 0.02)

    try:
        # 转换为 pandas Series
        returns_series = pd.Series(returns)
        benchmark_series = pd.Series(benchmark_returns) if benchmark_returns else None

        # 计算风险指标
        risk_service = RiskMetricsService(risk_free=risk_free_rate)
        metrics = risk_service.calculate_all_metrics(
            returns=returns_series,
            benchmark_returns=benchmark_series
        )

        return api_response(metrics)

    except Exception as e:
        logger.error(f"计算风险指标失败: {e}", exc_info=True)
        return error_response({
            'success': False,
            'error': str(e)
        }, 500)


# ============ /api/portfolio/benchmark（analysis.py） ============

@router.post('/api/portfolio/benchmark')
@handle_api_error
def portfolio_benchmark(payload: Optional[Dict[str, Any]] = Body(None)):
    """Benchmark comparison - 替代旧 quant_cli benchmark.compare"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.portfolio_analytics import compare_benchmark
        data = payload or {}
        quant_root = _V2_ROOT.parent / 'quant'
        result = compare_benchmark(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)


# ============ /api/portfolio/optimize（analysis.py） ============

@router.post('/api/portfolio/optimize')
@handle_api_error
def portfolio_optimize(payload: Optional[Dict[str, Any]] = Body(None)):
    """Portfolio optimization - 替代旧 quant_cli portfolio.optimize"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.portfolio_analytics import optimize_portfolio
        data = payload or {}
        quant_root = _V2_ROOT.parent / 'quant'
        result = optimize_portfolio(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)


# ============ /api/portfolio/correlation（analysis.py） ============

@router.post('/api/portfolio/correlation')
@handle_api_error
def portfolio_correlation(payload: Optional[Dict[str, Any]] = Body(None)):
    """Portfolio correlation matrix - 替代旧 quant_cli portfolio.correlation"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.trade_portfolio_analytics import correlate_portfolio
        data = payload or {}
        quant_root = _V2_ROOT.parent / 'quant'
        result = correlate_portfolio(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)


# ============ /api/portfolio/factor-analyze（analysis.py） ============

@router.post('/api/portfolio/factor-analyze')
@handle_api_error
def factor_analyze(payload: Optional[Dict[str, Any]] = Body(None)):
    """因子分析 - v2 增强版（集成 alphalens）"""
    data = payload or {}

    factors = data.get('factors', [])
    start_date = data.get('start_date') or data.get('startDate')
    end_date = data.get('end_date') or data.get('endDate')
    universe = data.get('universe')
    use_alphalens = data.get('use_alphalens', True)
    use_alphalens = data.get('useAlphalens', use_alphalens)  # 兼容驼峰命名

    # 参数验证
    if not factors:
        return error_response({
            'success': False,
            'error': '因子列表不能为空'
        }, 400)

    if not start_date or not end_date:
        return error_response({
            'success': False,
            'error': '开始日期和结束日期不能为空'
        }, 400)

    # 调用 DataService 分析因子
    result = ds.analyze_factors(
        factors=factors,
        start_date=start_date,
        end_date=end_date,
        universe=universe,
        use_alphalens=use_alphalens
    )

    # 检查错误
    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result)


# ============ /api/portfolio/factor-decay（analysis.py） ============

@router.post('/api/portfolio/factor-decay')
@handle_api_error
def factor_decay(payload: Optional[Dict[str, Any]] = Body(None)):
    """因子衰减分析 - 替代旧 quant_cli factor.decay"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.factor_decay import analyze_factor_decay
        data = payload or {}
        quant_root = _V2_ROOT.parent / 'quant'
        result = analyze_factor_decay(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)


# ============ /api/portfolio/sector-aggregate（analysis.py） ============

@router.post('/api/portfolio/sector-aggregate')
@handle_api_error
def sector_aggregate(payload: Optional[Dict[str, Any]] = Body(None)):
    """行业聚合分析 - v2 原生实现（按行业或板块聚合估值、质量、负债率和信号数量）"""
    try:
        data = payload or {}
        sector_field = data.get('sector_field', 'sector')
        limit = data.get('limit', 20)

        # 参数验证
        if sector_field not in ['sector', 'industry']:
            return error_response({
                'success': False,
                'error': 'sector_field 必须是 "sector" 或 "industry"'
            }, 400)

        # 使用 DataService 进行行业聚合分析
        from application.services.data_service import DataService
        ds_local = DataService()

        # 获取所有股票的基本信息（排除停牌退市股）
        stocks = ds_local.stock.get_all(include_suspended=False)

        if not stocks:
            return api_response({
                'sectors': [],
                'count': 0,
                'sector_field': sector_field,
                'message': '无股票数据'
            })

        # 按行业聚合
        from collections import defaultdict
        sector_stats = defaultdict(lambda: {
            'stocks': [],
            'pe_values': [],
            'pb_values': [],
            'roe_values': [],
            'signal_count': 0
        })

        for stock_raw in stocks:
            # 修复：Stock 是 ORM 对象，需要先转为字典
            stock = stock_raw.to_dict() if hasattr(stock_raw, 'to_dict') else stock_raw
            # fallback 链：请求字段 → sector → industry → 未分类（与 Flask parity）
            sector_name = (stock.get(sector_field)
                           or stock.get('sector')
                           or stock.get('industry')
                           or '未分类')
            if not sector_name:
                sector_name = '未分类'

            sector_stats[sector_name]['stocks'].append(stock.get('symbol'))

            # 收集估值指标
            pe = stock.get('pe_ratio') or stock.get('pe')
            if pe and pe > 0:
                sector_stats[sector_name]['pe_values'].append(float(pe))

            pb = stock.get('pb_ratio') or stock.get('pb')
            if pb and pb > 0:
                sector_stats[sector_name]['pb_values'].append(float(pb))

            roe = stock.get('roe')
            if roe and roe > 0:
                sector_stats[sector_name]['roe_values'].append(float(roe))

        # 计算聚合指标
        import statistics
        sectors_result = []

        for sector_name, stats in sector_stats.items():
            result_item = {
                'name': sector_name,
                'stock_count': len(stats['stocks']),
                'avg_pe': round(statistics.mean(stats['pe_values']), 2) if stats['pe_values'] else None,
                'avg_pb': round(statistics.mean(stats['pb_values']), 2) if stats['pb_values'] else None,
                'avg_roe': round(statistics.mean(stats['roe_values']), 2) if stats['roe_values'] else None,
                'signal_count': stats['signal_count']  # TODO: 从信号表查询
            }
            sectors_result.append(result_item)

        # 按股票数量降序排序
        sectors_result.sort(key=lambda x: x['stock_count'], reverse=True)

        # 未分类股票数（与 Flask parity）
        unclassified_count = next(
            (s['stock_count'] for s in sectors_result if s['name'] == '未分类'), 0)

        # 限制返回数量
        if limit:
            sectors_result = sectors_result[:limit]

        return api_response({
            'sectors': sectors_result,
            'count': len(sectors_result),
            'sector_field': sector_field,
            'total_stocks': len(stocks),
            'unclassified_count': unclassified_count,
            'degraded': unclassified_count > len(stocks) * 0.5,
        })

    except Exception as e:
        logger.error(f"行业聚合分析失败: {e}", exc_info=True)
        return error_response({
            'success': False,
            'error': f'服务器内部错误: {str(e)}'
        }, 500)


# ============ /api/portfolio/performance-analyze（analysis.py） ============

@router.post('/api/portfolio/performance-analyze')
@handle_api_error
def performance_analyze(payload: Optional[Dict[str, Any]] = Body(None)):
    """策略表现分析 - 替代旧 quant_cli performance.analyze"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.strategy_analytics import analyze_performance
        data = payload or {}
        quant_root = _V2_ROOT.parent / 'quant'
        result = analyze_performance(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)


# ============ /api/portfolio/signal-arbitrate（analysis.py） ============

@router.post('/api/portfolio/signal-arbitrate')
@handle_api_error
def signal_arbitrate(payload: Optional[Dict[str, Any]] = Body(None)):
    """信号仲裁 - 替代旧 quant_cli signal.arbitrate"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.strategy_analytics import arbitrate_signals
        data = payload or {}
        quant_root = _V2_ROOT.parent / 'quant'
        result = arbitrate_signals(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return error_response({'success': False, 'error': f'Module not available: {e}'}, 503)


# ============ /api/analysis/factor-report（analysis.py） ============

@router.post('/api/analysis/factor-report')
@handle_api_error
def generate_factor_report(payload: Optional[Dict[str, Any]] = Body(None)):
    """生成因子分析 HTML 报告"""
    data = payload or {}

    factors = data.get('factors', [])
    start_date = data.get('start_date') or data.get('startDate')
    end_date = data.get('end_date') or data.get('endDate')
    universe = data.get('universe')
    output_dir = data.get('output_dir') or data.get('outputDir')

    # 参数验证
    if not factors:
        return error_response({
            'success': False,
            'error': '因子列表不能为空'
        }, 400)

    if not start_date or not end_date:
        return error_response({
            'success': False,
            'error': '开始日期和结束日期不能为空'
        }, 400)

    # 调用 DataService 生成报告
    result = ds.generate_factor_report(
        factors=factors,
        start_date=start_date,
        end_date=end_date,
        universe=universe,
        output_dir=output_dir
    )

    # 检查错误
    if not result.get('success'):
        return error_response({
            'success': False,
            'error': result.get('error', '生成因子报告失败')
        }, 400)

    return api_response(result)


# ============ /api/analysis/swing-points（analysis.py） ============

@router.post('/api/analysis/swing-points')
@handle_api_error
def analyze_swing_points(payload: Optional[Dict[str, Any]] = Body(None)):
    """ZigZag 波段分析 — 根据历史价格波动识别买卖点"""
    from application.services.swing_point_service import SwingPointService

    raw = payload or {}
    params = convert_keys_to_snake(raw)

    svc = SwingPointService()
    result = svc.analyze(params)

    return api_response(sanitize_for_json(result))
