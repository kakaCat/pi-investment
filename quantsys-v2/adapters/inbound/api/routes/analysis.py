"""
analysis routes.
"""
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake,
    convert_keys_to_camel,
    _safe_float,
    _V2_ROOT,
    _PROJECT_ROOT_PATH,
    _LEGACY_QUANT_ROOT,
    _load_pipeline_runs,
    _save_pipeline_runs,
    _get_pipeline_run,
    _update_pipeline_run,
    acquire_task,
    release_task,
    get_running_tasks_snapshot,
    strategy_service,
    stock_pool_service,
    factor_adapter,
    scoring_service,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
    _parse_sina_a_quote,
    _parse_sina_hk_quote,
    to_camel_case,
    to_snake_case,
    get_query_params_snake_case,
    enrich_stock_data,
    signal_to_opportunity,
)

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/api/stock/<symbol>/factors', methods=['GET'])
@analysis_bp.route('/api/stocks/<symbol>/factors', methods=['GET'])
def get_stock_factors(symbol):
    """获取股票因子分析"""
    try:
        date = request.args.get('date')
        factors = ds.factor.get_latest_factors(symbol) if not date else ds.factor.get_factors(symbol, date)

        stock_info = ds.stock.get_by_symbol(symbol)
        kline = ds.kline.get_latest_daily_kline(symbol)
        latest_signals = ds.signal.get_signals_by_symbol(
            symbol,
            '2024-01-01',
            request.args.get('date') or '2026-12-31'
        )

        return jsonify(sanitize_for_json({
            'symbol': symbol,
            'stock_name': stock_info['name'] if stock_info else '',
            'market': stock_info['market'] if stock_info else '',
            'current_price': kline['close'] if kline else None,
            'factors': factors,
            'signals_count': len(latest_signals)
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/api/stocks/compare', methods=['POST'])
def compare_stocks():
    """对比多只股票 - 使用批量查询优化"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols', [])

        if not symbols:
            return jsonify({'error': '请提供股票代码'}), 400
        if len(symbols) > 5:
            return jsonify({'error': '最多对比5只股票'}), 400

        # 批量查询 - 3次DB调用替代 3*N 次调用
        from datetime import datetime
        current_date = datetime.now().strftime('%Y-%m-%d')

        factors_batch = ds.factor.get_factors_batch(symbols, current_date)
        stocks_batch = ds.stock.get_by_symbols_batch(symbols)
        klines_batch = ds.kline.get_latest_daily_klines_batch(symbols)

        # 组装结果
        results = []
        for symbol in symbols:
            stock_info = stocks_batch.get(symbol, {})
            kline = klines_batch.get(symbol)
            factors = factors_batch.get(symbol, {})

            results.append(sanitize_for_json({
                'symbol': symbol,
                'name': stock_info.get('name', '') if stock_info else '',
                'market': stock_info.get('market', '') if stock_info else '',
                'current_price': kline.get('close') if kline else None,
                'factors': factors
            }))

        return jsonify({
            'comparisons': results,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/api/stock/<symbol>/technical', methods=['GET'])
def get_technical_indicators(symbol):
    """计算技术指标"""
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

        klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)

        if klines_df is None or klines_df.is_empty():
            return jsonify({'error': f'No kline data for {symbol}'}), 404

        if len(klines_df) < 20:
            return jsonify({
                'error': f'Insufficient data for {symbol} (need 20+ days, got {len(klines_df)})'
            }), 400

        klines = klines_df.to_dicts()
        from domain.quantlib.stages.factor_stage import FactorStage
        stage = FactorStage(name="technical")
        result = stage.process({
            'symbol': symbol,
            'klines': klines
        })

        indicators_list = request.args.get('indicators')
        factors = result.get('factors', {})
        if indicators_list:
            wanted = indicators_list.split(',')
            factors = {k: factors[k] for k in wanted if k in factors}

        return jsonify(sanitize_for_json({
            'symbol': symbol,
            'factors': factors,
            'data_days': len(klines)
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/api/stock/<symbol>/price-action', methods=['GET'])
@handle_api_error
def get_price_action(symbol):
    """
    价格行为分析 - 替代旧 quant_cli analysis.price_action
    
    参数: period (默认60天)
    使用 v2 TechnicalAnalysisService 实现价格行为分析
    """
    period = request.args.get('period', 60, type=int)
    try:
        from application.services.technical_analysis_service import TechnicalAnalysisService
        tech_service = TechnicalAnalysisService()
        result = tech_service.analyze_price_action(symbol, period=period)
        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        return api_response(result)
    except Exception as e:
        logger.error(f"Price action analysis failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@analysis_bp.route('/api/stock/<symbol>/buy-range', methods=['GET'])
@handle_api_error
def get_buy_range(symbol):
    """
    买入区间计算 - 使用 v2 TechnicalAnalysisService

    参数:
        enhanced (bool): 是否使用增强模式（多周期+成交量+基本面）
        periods (str): 时间周期，逗号分隔，如 'daily,weekly,monthly'
    """
    try:
        # 检查是否使用增强模式
        enhanced = request.args.get('enhanced', 'false').lower() == 'true'

        if enhanced:
            from application.services.enhanced_buy_range_service import EnhancedBuyRangeService

            # 解析周期参数
            periods_str = request.args.get('periods', 'daily')
            periods = [p.strip() for p in periods_str.split(',')]

            # 获取其他参数
            include_volume = request.args.get('volume', 'true').lower() == 'true'
            include_fundamental = request.args.get('fundamental', 'true').lower() == 'true'

            service = EnhancedBuyRangeService()
            result = service.calculate_enhanced_buy_range(
                symbol=symbol,
                periods=periods,
                include_volume=include_volume,
                include_fundamental=include_fundamental
            )
        else:
            # 简化模式（向后兼容）
            from application.services.technical_analysis_service import TechnicalAnalysisService

            tech_service = TechnicalAnalysisService()
            result = tech_service.calculate_buy_range(symbol)

        if not result.get('success', True):
            return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 400

        return api_response(result.get('data', result))
    except Exception as e:
        logger.error(f"买入区间计算失败: {str(e)}")
        return jsonify({'success': False, 'error': f'计算失败: {str(e)}'}), 500


@analysis_bp.route('/api/stock/<symbol>/exit-plan', methods=['GET'])
@handle_api_error
def get_exit_plan(symbol):
    """
    退出计划 - 原生 v2 实现

    参数: buy_price (必填), position_size (可选，默认100)
    生成止盈、止损和分批卖出策略
    """
    buy_price = request.args.get('buy_price', type=float)
    position_size = request.args.get('position_size', 100, type=int)

    try:
        from application.services.data_service import DataService
        from datetime import datetime, timedelta
        ds = DataService()

        # 确保 symbol 有后缀
        if '.' not in symbol:
            symbol_with_suffix = symbol + ('.SH' if symbol.startswith('6') else '.SZ')
        else:
            symbol_with_suffix = symbol

        # 尝试获取最近的K线数据作为当前价格
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)  # 获取最近5天数据

        klines = ds.kline.get_daily_klines(
            symbol_with_suffix,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        if not klines or len(klines) == 0:
            return jsonify({'success': False, 'error': f'无法获取 {symbol} 的价格数据'}), 404

        # 使用最新的收盘价
        latest_kline = klines[-1]
        current_price = latest_kline.get('close')

        if not current_price:
            return jsonify({'success': False, 'error': '无法解析价格数据'}), 404

        # 如果未提供 buy_price，使用当前价
        if not buy_price:
            buy_price = float(current_price)

        # 获取股票名称
        stock_info = ds.stock.get_by_symbol(symbol_with_suffix) or {}
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
        return jsonify({'success': False, 'error': f'生成退出计划失败: {str(e)}'}), 500


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


@analysis_bp.route('/api/stock/<symbol>/pe-percentile', methods=['GET'])
@handle_api_error
def get_pe_percentile(symbol):
    """
    PE历史分位 - 替代旧 quant_cli analysis.pe_percentile

    参数: years (默认3)
    使用数据库历史数据计算 PE 分位数
    """
    years = request.args.get('years', 3, type=int)
    try:
        import pandas as pd
        from datetime import datetime, timedelta
        from application.services.data_service import DataService

        ds = DataService()

        # 获取股票基本信息（包含当前 PE）
        stock_info = ds.stock.get_by_symbol(symbol)
        if not stock_info:
            return jsonify({'success': False, 'error': '股票不存在'}), 404

        # 修复：Stock 是 ORM 对象，使用属性访问而非 .get()
        current_pe = stock_info.pe
        if not current_pe or current_pe <= 0:
            return jsonify({'success': False, 'error': 'PE数据不可用'}), 404

        # 获取历史 K 线数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)

        klines = ds.kline.get_daily_klines(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        # 修复：避免 polars DataFrame 的 ambiguous truth value 错误
        if klines is None or len(klines) < 20:
            return jsonify({'success': False, 'error': '历史数据不足'}), 404

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
            return jsonify({'success': False, 'error': 'PE数据点不足'}), 404

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
        return jsonify({'success': False, 'error': f'查询失败: {str(e)}'}), 500


@analysis_bp.route('/api/stock/<symbol>/candlestick', methods=['GET'])
@handle_api_error
def get_candlestick(symbol):
    """K线形态分析 - 替代旧 quant_cli analysis.candlestick / indicator.candlestick"""
    try:
        from application.services.technical_analysis_service import TechnicalAnalysisService
        tech_service = TechnicalAnalysisService()
        result = tech_service.analyze_candlestick(symbol)
        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        return api_response(result)
    except Exception as e:
        logger.error(f"Candlestick analysis failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@analysis_bp.route('/api/stock/<symbol>/financials', methods=['GET'])
@handle_api_error
def get_financials(symbol):
    """
    获取财务报表数据（v2 实现，使用 DataService）

    参数:
        type: 报表类型 ('income'|'balance'|'cash_flow'|'all', 默认 'all')
        periods: 期数 (默认 4)

    返回:
        {
            "success": true,
            "data": {
                "symbol": "600000.SH",
                "name": "浦发银行",
                "statementType": "all",
                "periods": 4,
                "incomeStatement": [...],
                "balanceSheet": [...],
                "cashFlow": [...]
            }
        }
    """
    statement_type = request.args.get('type', 'all')
    periods = request.args.get('periods', 4, type=int)

    # 调用 DataService 获取财务数据
    result = ds.get_financial_statements(
        symbol=symbol,
        statement_type=statement_type,
        periods=periods
    )

    # 检查错误
    if 'error' in result:
        return jsonify({
            'success': False,
            'error': result['error']
        }), 400

    return api_response(result)


@analysis_bp.route('/api/stock/<symbol>/indicators', methods=['GET'])
@handle_api_error
def get_indicators(symbol):
    """财务指标 - v2 原生实现"""
    from application.services.financial_analysis_service import FinancialAnalysisService
    service = FinancialAnalysisService()
    result = service.get_financial_indicators(symbol)

    # 统一返回格式，确保总是返回有效的 JSON
    if not result.get('success'):
        return jsonify(result), 400
    return api_response(result.get('data', {}))


@analysis_bp.route('/api/stock/<symbol>/valuation', methods=['GET'])
@handle_api_error
def get_valuation(symbol):
    """估值分析 - v2 原生实现"""
    from application.services.financial_analysis_service import FinancialAnalysisService
    service = FinancialAnalysisService()
    result = service.get_stock_valuation(symbol)

    # 统一返回格式，确保总是返回有效的 JSON
    # 即使失败也返回结构化的错误信息，不返回空响应
    if not result.get('success'):
        return jsonify(result), 400
    return api_response(result.get('data', {}))


# REMOVED: Duplicate endpoint, conflicts with market.py's v2 native implementation
# @analysis_bp.route('/api/market/sentiment', methods=['GET'])
# @handle_api_error
# def get_market_sentiment():
#     """市场情绪 - 替代旧 quant_cli market.sentiment"""
#     try:
#         sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
#         from quantsys.cli.market_query import get_market_sentiment
#         result = get_market_sentiment()
#         if 'error' in result:
#             return jsonify({'success': False, 'error': result['error']}), 400
#         return api_response(result)
#     except ImportError as e:
#         return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503

@analysis_bp.route('/api/feature-importance', methods=['GET'])
@handle_api_error
def get_feature_importance():
    """获取特征重要性（兼容 Express 前端）"""
    try:
        from application.services.ml_pipeline.trainer import MLTrainer
    except ImportError:
        return jsonify({'success': False, 'error': 'ML module not available'}), 503

    model_type = request.args.get('model_type', 'xgboost')
    version = request.args.get('version', 'latest')
    top_n = request.args.get('top_n', type=int)

    try:
        trainer = MLTrainer(model_type=model_type)
        trainer.load_model(version=version)
        importance = trainer.get_feature_importance(top_n=top_n)
        return api_response({
            'features': importance,
            'total_features': len(importance),
        })
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'Model not found. Train a model first.'}), 404


@analysis_bp.route('/api/factor-explanations', methods=['GET'])
@handle_api_error
def get_factor_explanations():
    """获取因子解释（兼容 Express 前端）"""
    explanations = {
        'ma5': '5日均线 - 短期趋势指标，价格与5日均线的偏离度',
        'ma10': '10日均线 - 中期趋势指标',
        'ma20': '20日均线 - 中期趋势指标，常用于布林带中轨',
        'ma60': '60日均线 - 长期趋势指标，季线',
        'rsi': '相对强弱指标(RSI) - 衡量价格变动速度和幅度的振荡指标，范围0-100',
        'macd': '指数平滑异同移动平均线(MACD) - 趋势跟踪动量指标',
        'volume_ratio': '量比 - 当前成交量与过去5日平均成交量的比值',
        'turnover_rate': '换手率 - 反映股票流通性强弱',
        'volatility': '波动率 - 价格标准差的年化值',
        'beta': '贝塔系数 - 个股相对市场的系统性风险',
        'momentum_5d': '5日动量 - 过去5个交易日的累计收益率',
        'momentum_20d': '20日动量 - 过去20个交易日的累计收益率',
        'pe_ratio': '市盈率 - 股价与每股收益的比值，衡量估值水平',
        'pb_ratio': '市净率 - 股价与每股净资产的比值',
        'market_cap': '总市值 - 公司市场总价值',
    }
    return api_response({'explanations': explanations})


@analysis_bp.route('/api/factors/list', methods=['GET'])
@handle_api_error
def list_all_factors():
    """列出所有可用因子（从因子库动态获取）"""
    try:
        from application.services.strategy_code_service import StrategyCodeService

        # 初始化服务获取因子计算器
        service = StrategyCodeService()

        # 收集所有因子
        all_factors = {}

        # 定义因子分类
        factor_classes = [
            ('momentum', service.momentum_factors, '动量因子'),
            ('trend', service.trend_factors, '趋势因子'),
            ('volatility', service.volatility_factors, '波动率因子'),
            ('volume', service.volume_factors, '成交量因子'),
            ('moving_average', service.ma_factors, '移动平均因子'),
            ('reversal', service.reversal_factors, '反转因子'),
            ('advanced', service.advanced_factors, '高级因子'),
            ('cycle', service.cycle_factors, '周期因子'),
            ('pattern', service.pattern_factors, '形态识别因子'),
            ('other', service.other_factors, '其他因子'),
        ]

        # 遍历每个因子类
        for category, calculator, category_name in factor_classes:
            if calculator is None:
                continue

            try:
                # 获取该类的所有方法
                methods = calculator.get_supported_methods()

                # 添加到结果中
                all_factors[category] = {
                    'name': category_name,
                    'count': len(methods),
                    'factors': methods
                }
            except Exception as e:
                logger.warning(f"获取 {category} 因子失败: {e}")
                continue

        # 统计总数
        total_count = sum(cat['count'] for cat in all_factors.values())

        return api_response({
            'total': total_count,
            'categories': all_factors,
            'version': '1.0',
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"列出因子失败: {e}", exc_info=True)
        return api_response({
            'error': str(e),
            'total': 0,
            'categories': {}
        }, success=False)


@analysis_bp.route('/api/analysis/factor-correlation', methods=['POST'])
@handle_api_error
def factor_correlation():
    """因子相关性分析"""
    try:
        data = request.get_json()
        factors = data.get('factors', [])
        symbols = data.get('symbols')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        method = data.get('method', 'pearson')

        if len(factors) < 2:
            return api_response({'error': '至少需要2个因子'}, success=False)

        if not start_date or not end_date:
            return api_response({'error': '需要提供 start_date 和 end_date'}, success=False)

        # TODO: 实现因子相关性计算逻辑
        # 这里返回模拟数据，实际应该调用因子计算服务
        import numpy as np

        n = len(factors)
        # 生成模拟相关性矩阵
        correlation_matrix = np.eye(n).tolist()
        for i in range(n):
            for j in range(i+1, n):
                corr = np.random.uniform(-0.3, 0.8)
                correlation_matrix[i][j] = corr
                correlation_matrix[j][i] = corr

        # 找出高相关因子对
        high_correlations = []
        for i in range(n):
            for j in range(i+1, n):
                if abs(correlation_matrix[i][j]) > 0.7:
                    high_correlations.append({
                        'factor1': factors[i],
                        'factor2': factors[j],
                        'correlation': correlation_matrix[i][j]
                    })

        result = {
            'correlation_matrix': correlation_matrix,
            'factors': factors,
            'method': method,
            'high_correlations': high_correlations,
            'n_stocks': len(symbols) if symbols else 300,
            'period': f"{start_date} ~ {end_date}"
        }

        return api_response(result)

    except Exception as e:
        logger.error(f"因子相关性分析失败: {e}", exc_info=True)
        return api_response({'error': str(e)}, success=False)


@analysis_bp.route('/api/analysis/factor-portfolio-optimize', methods=['POST'])
@handle_api_error
def factor_portfolio_optimize():
    """因子组合优化"""
    try:
        data = request.get_json()
        candidate_factors = data.get('candidate_factors', [])
        symbols = data.get('symbols')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        max_factors = data.get('max_factors', 3)
        optimization_target = data.get('optimization_target', 'combined')
        min_ic = data.get('min_ic', 0.02)
        max_correlation = data.get('max_correlation', 0.7)

        if len(candidate_factors) < 3:
            return api_response({'error': '至少需要3个候选因子'}, success=False)

        if not start_date or not end_date:
            return api_response({'error': '需要提供 start_date 和 end_date'}, success=False)

        # TODO: 实现因子组合优化逻辑
        # 这里返回模拟数据，实际应该调用因子分析服务
        import numpy as np

        # 模拟因子评分
        factor_scores = {}
        selected_factors = []
        rejected_factors = []

        for i, factor in enumerate(candidate_factors):
            ic = np.random.uniform(0.01, 0.08)
            score = ic * 100 + np.random.uniform(0, 2)

            factor_scores[factor] = {
                'ic': ic,
                'score': score,
                't_stat': ic / 0.02 * 2
            }

            if ic < min_ic:
                rejected_factors.append({
                    'name': factor,
                    'reason': f'IC过低 ({ic:.3f} < {min_ic})'
                })
            elif len(selected_factors) < max_factors:
                weight = 1.0 / max_factors
                selected_factors.append({
                    'name': factor,
                    'weight': weight,
                    'ic': ic,
                    'score': score
                })

        result = {
            'selected_factors': selected_factors,
            'rejected_factors': rejected_factors,
            'factor_scores': factor_scores,
            'optimization_target': optimization_target,
            'parameters': {
                'max_factors': max_factors,
                'min_ic': min_ic,
                'max_correlation': max_correlation
            }
        }

        return api_response(result)

    except Exception as e:
        logger.error(f"因子组合优化失败: {e}", exc_info=True)
        return api_response({'error': str(e)}, success=False)


@analysis_bp.route('/api/analysis/factor-ic-monitor', methods=['POST'])
@handle_api_error
def factor_ic_monitor():
    """因子IC时序监控"""
    try:
        data = request.get_json()
        factor_name = data.get('factor_name')
        symbols = data.get('symbols')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        rolling_window = data.get('rolling_window', 20)
        alert_threshold = data.get('alert_threshold', 0.02)

        if not factor_name:
            return api_response({'error': '需要提供 factor_name'}, success=False)

        if not start_date or not end_date:
            return api_response({'error': '需要提供 start_date 和 end_date'}, success=False)

        # TODO: 实现因子IC监控逻辑
        # 这里返回模拟数据，实际应该调用因子分析服务
        import numpy as np
        from datetime import datetime, timedelta

        # 生成模拟IC时间序列
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days

        # 模拟IC值（带趋势）
        ic_values = []
        dates = []
        trend_slope = np.random.uniform(-0.0001, 0.0001)

        for i in range(min(days, 250)):  # 最多250个交易日
            date = start + timedelta(days=i)
            ic = 0.03 + trend_slope * i + np.random.normal(0, 0.02)
            ic_values.append(ic)
            dates.append(date.strftime('%Y-%m-%d'))

        ic_array = np.array(ic_values)

        # IC统计
        ic_statistics = {
            'mean': float(np.mean(ic_array)),
            'std': float(np.std(ic_array)),
            'min': float(np.min(ic_array)),
            'max': float(np.max(ic_array)),
            'positive_ratio': float(np.sum(ic_array > 0) / len(ic_array)),
            't_stat': float(np.mean(ic_array) / (np.std(ic_array) / np.sqrt(len(ic_array))))
        }

        # 趋势分析
        if trend_slope > 0.00005:
            trend_direction = 'up'
            trend_strength = 'strong' if trend_slope > 0.0001 else 'moderate'
        elif trend_slope < -0.00005:
            trend_direction = 'down'
            trend_strength = 'strong' if trend_slope < -0.0001 else 'moderate'
        else:
            trend_direction = 'stable'
            trend_strength = 'stable'

        trend = {
            'direction': trend_direction,
            'strength': trend_strength,
            'slope': float(trend_slope)
        }

        # 预警
        alerts = []
        if ic_statistics['mean'] < alert_threshold:
            alerts.append({
                'type': 'low_ic',
                'message': f"IC均值 ({ic_statistics['mean']:.4f}) 低于阈值 ({alert_threshold})"
            })

        if trend_direction == 'down':
            alerts.append({
                'type': 'declining_trend',
                'message': 'IC呈下降趋势，因子可能衰减'
            })

        # 最近表现
        recent_ic = []
        for i in range(max(0, len(dates)-10), len(dates)):
            recent_ic.append({
                'date': dates[i],
                'ic': ic_values[i]
            })

        result = {
            'factor_name': factor_name,
            'ic_statistics': ic_statistics,
            'trend': trend,
            'alerts': alerts,
            'recent_ic': recent_ic,
            'n_stocks': len(symbols) if symbols else 300,
            'period': f"{start_date} ~ {end_date}",
            'rolling_window': rolling_window
        }

        return api_response(result)

    except Exception as e:
        logger.error(f"因子IC监控失败: {e}", exc_info=True)
        return api_response({'error': str(e)}, success=False)


@analysis_bp.route('/api/stock/<symbol>/score', methods=['GET'])
@handle_api_error
def get_stock_score(symbol):
    """多因子评分 - 使用 v2 StockScoringService"""
    from adapters.inbound.api.shared import stock_scoring_service

    result = stock_scoring_service.calculate_comprehensive_score(symbol)
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 400
    return api_response(result)


@analysis_bp.route('/api/stocks/screen', methods=['GET'])
@handle_api_error
def screen_stocks_v2():
    """多条件选股 - 使用 v2 原生实现"""
    try:
        from application.services.stock_screening_service import StockScreeningService

        # 解析筛选条件
        criteria = {}
        for key in ['min_score', 'max_pe', 'min_roe', 'max_debt_ratio', 'min_market_cap', 'max_market_cap']:
            val = request.args.get(key)
            if val is not None:
                criteria[key] = float(val) if '.' in str(val) else int(val)

        # 获取其他参数
        limit = request.args.get('limit', 20, type=int)
        sector = request.args.get('sector', '')
        if limit:
            criteria['limit'] = limit

        # 使用筛选服务 (需要 ds 和 scoring_service)
        screening_service = StockScreeningService(ds, scoring_service)
        result = screening_service.screen_stocks(criteria)

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        return api_response(result)
    except ImportError as e:
        logger.error(f"Import error in screen_stocks: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503
    except Exception as e:
        logger.error(f"Error in screen_stocks: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@analysis_bp.route('/api/stock/<symbol>/quality', methods=['GET'])
@handle_api_error
def get_quality_score_v2(symbol):
    """质量评分 - 使用 v2 QualityScoringService"""
    logger.info(f"=== Quality route called for {symbol} ===")
    try:
        logger.info("Importing QualityScoringService...")
        from application.services.quality_scoring_service import QualityScoringService
        logger.info("Import successful!")

        framework = request.args.get('framework', 'auto')
        logger.info(f"Creating service with framework={framework}")
        quality_service = QualityScoringService(ds)

        logger.info("Calculating quality score...")
        result = quality_service.calculate_quality_score(symbol, framework=framework)
        logger.info(f"Result: {list(result.keys())}")

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        return api_response(result)
    except ImportError as e:
        logger.error(f"Import error in quality route: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503
    except Exception as e:
        logger.error(f"Error in quality route: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@analysis_bp.route('/api/stock/<symbol>/data-health', methods=['GET'])
@handle_api_error
def get_data_health(symbol):
    """
    单票数据健康检查

    Returns:
        {
          "success": true,
          "data": {
            "valid": bool,
            "exists": bool,
            "has_recent_data": bool,
            "data_summary": {
              "first_date": str | null,
              "last_date": str | null,
              "total_records": int,
              "days_since_update": int
            },
            "suggestions": List[str],
            "similar_codes": List[str]
          }
        }
    """
    from application.services.stock_code_validator import StockCodeValidator

    validator = StockCodeValidator()
    result = validator.validate(symbol)

    # validate() 内部异常时会在结果里带 error 字段
    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']}), 500

    # 保持 snake_case，绕过 api_response() 的驼峰转换
    return jsonify({'success': True, 'data': result}), 200


@analysis_bp.route('/api/screening/quality', methods=['GET'])
@handle_api_error
def screening_quality():
    """行业质量筛选 - 使用 v2 质量评分服务"""
    sector = request.args.get('sector', '')
    min_score = request.args.get('min_score', 50, type=int)
    max_pe = request.args.get('max_pe', type=float)
    limit = request.args.get('limit', 10, type=int)

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

@analysis_bp.route('/api/stock/<symbol>/cash-flow', methods=['GET'])
@handle_api_error
def get_cash_flow_v2(symbol):
    """现金流量表 - 替代旧 quant_cli financial.cash_flow"""
    # Legacy route - use /api/stock/<symbol>/financials?type=cash_flow instead
    return jsonify({'success': False, 'error': 'This endpoint is deprecated. Use /api/stock/<symbol>/financials?type=cash_flow'}), 410


@analysis_bp.route('/api/stock/<symbol>/income-statement', methods=['GET'])
@handle_api_error
def get_income_statement_v2(symbol):
    """利润表 - 替代旧 quant_cli financial.income_statement"""
    # Legacy route - use /api/stock/<symbol>/financials?type=income instead
    return jsonify({'success': False, 'error': 'This endpoint is deprecated. Use /api/stock/<symbol>/financials?type=income'}), 410


@analysis_bp.route('/api/risk/stress-test', methods=['POST'])
@handle_api_error
def risk_stress_test():
    """压力测试 - 已弃用"""
    return jsonify({'success': False, 'error': 'This endpoint is deprecated and not yet reimplemented in v2'}), 410


@analysis_bp.route('/api/risk/price-alert', methods=['POST'])
@handle_api_error
def risk_price_alert():
    """价格预警 - 替代旧 quant_cli watch.price_alert"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.risk_watch_analytics import price_alert
        data = request.get_json(silent=True) or {}
        from pathlib import Path
        quant_root = _V2_ROOT.parent / 'quant'
        result = price_alert(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503


@analysis_bp.route('/api/risk/trade-verify', methods=['POST'])
@handle_api_error
def risk_trade_verify():
    """交易实盘回测对比 - 替代旧 quant_cli trade.verify"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.trade_portfolio_analytics import verify_trades
        data = request.get_json(silent=True) or {}
        from pathlib import Path
        quant_root = _V2_ROOT.parent / 'quant'
        result = verify_trades(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503


@analysis_bp.route('/api/portfolio/benchmark', methods=['POST'])
@handle_api_error
def portfolio_benchmark():
    """Benchmark comparison - 替代旧 quant_cli benchmark.compare"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.portfolio_analytics import compare_benchmark
        data = request.get_json(silent=True) or {}
        from pathlib import Path
        quant_root = _V2_ROOT.parent / 'quant'
        result = compare_benchmark(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503


@analysis_bp.route('/api/portfolio/optimize', methods=['POST'])
@handle_api_error
def portfolio_optimize():
    """Portfolio optimization - 替代旧 quant_cli portfolio.optimize"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.portfolio_analytics import optimize_portfolio
        data = request.get_json(silent=True) or {}
        from pathlib import Path
        quant_root = _V2_ROOT.parent / 'quant'
        result = optimize_portfolio(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503


@analysis_bp.route('/api/portfolio/correlation', methods=['POST'])
@handle_api_error
def portfolio_correlation():
    """Portfolio correlation matrix - 替代旧 quant_cli portfolio.correlation"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.trade_portfolio_analytics import correlate_portfolio
        data = request.get_json(silent=True) or {}
        from pathlib import Path
        quant_root = _V2_ROOT.parent / 'quant'
        result = correlate_portfolio(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503


@analysis_bp.route('/api/portfolio/factor-analyze', methods=['POST'])
@handle_api_error
def factor_analyze():
    """
    因子分析 - v2 增强版（集成 alphalens）

    Request:
    {
        "factors": ["rsi", "macd"],
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "universe": ["600000.SH", "000001.SZ"],  // 可选
        "use_alphalens": true                     // 可选，默认 true
    }

    Response (use_alphalens=true):
    {
        "success": true,
        "data": {
            "factors": [
                {
                    "name": "rsi",
                    "ic_analysis": {
                        "ic_mean": 0.05,
                        "ic_std": 0.12,
                        "ic_ir": 0.42,
                        "t_stat": 3.2,
                        "p_value": 0.001,
                        "ic_by_period": {
                            "1D": {"mean": 0.04, "std": 0.10},
                            "5D": {"mean": 0.06, "std": 0.14},
                            "10D": {"mean": 0.05, "std": 0.13}
                        }
                    },
                    "returns_analysis": {
                        "mean_return_by_quantile": {
                            "1D": {"Q1": -0.02, "Q2": 0.0, ..., "Q5": 0.03}
                        },
                        "mean_return_spread": {"1D": 0.05, "5D": 0.08}
                    },
                    "turnover_analysis": {
                        "mean_turnover": 0.35,
                        "autocorrelation": {"1D": 0.65, "5D": 0.45}
                    },
                    "coverage": 0.95,
                    "data_points": 1500
                }
            ],
            "count": 1,
            "method": "alphalens",
            "period": {"start": "2024-01-01", "end": "2024-01-31"},
            "universe_size": 2
        }
    }

    Response (use_alphalens=false or fallback):
    {
        "success": true,
        "data": {
            "factors": [...],
            "method": "fallback",
            "note": "使用模拟数据（alphalens 不可用或数据不足）"
        }
    }
    """
    data = request.get_json() or {}

    factors = data.get('factors', [])
    start_date = data.get('start_date') or data.get('startDate')
    end_date = data.get('end_date') or data.get('endDate')
    universe = data.get('universe')
    use_alphalens = data.get('use_alphalens', True)
    use_alphalens = data.get('useAlphalens', use_alphalens)  # 兼容驼峰命名

    # 参数验证
    if not factors:
        return jsonify({
            'success': False,
            'error': '因子列表不能为空'
        }), 400

    if not start_date or not end_date:
        return jsonify({
            'success': False,
            'error': '开始日期和结束日期不能为空'
        }), 400

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
        return jsonify(result), 400

    return api_response(result)


@analysis_bp.route('/api/analysis/factor-report', methods=['POST'])
@handle_api_error
def generate_factor_report():
    """
    生成因子分析 HTML 报告

    Request:
    {
        "factors": ["rsi", "macd", "roe"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "universe": ["600000.SH", "000001.SZ"],  // 可选
        "output_dir": "/tmp/factor_reports"      // 可选，默认 /tmp
    }

    Response:
    {
        "success": true,
        "data": {
            "reports": [
                {
                    "factor": "rsi",
                    "success": true,
                    "report_path": "/tmp/factor_report_rsi_20260603_120000.html",
                    "file_size": 245678,
                    "url": "file:///tmp/factor_report_rsi_20260603_120000.html"
                },
                {
                    "factor": "macd",
                    "success": true,
                    "report_path": "/tmp/factor_report_macd_20260603_120001.html",
                    "file_size": 238456,
                    "url": "file:///tmp/factor_report_macd_20260603_120001.html"
                },
                {
                    "factor": "roe",
                    "success": false,
                    "error": "无数据"
                }
            ],
            "total": 3,
            "success_count": 2,
            "failed_count": 1,
            "method": "alphalens",
            "period": {"start": "2024-01-01", "end": "2024-12-31"},
            "universe_size": 2
        }
    }

    注意：
    - 需要安装 alphalens-reloaded: pip install alphalens-reloaded
    - 需要安装 matplotlib: pip install matplotlib
    - 生成的 HTML 报告包含：IC 时间序列图、因子分层收益图、累计收益曲线、换手率分析等
    - 报告文件保存在本地，可通过 file:// URL 在浏览器中打开
    """
    data = request.get_json() or {}

    factors = data.get('factors', [])
    start_date = data.get('start_date') or data.get('startDate')
    end_date = data.get('end_date') or data.get('endDate')
    universe = data.get('universe')
    output_dir = data.get('output_dir') or data.get('outputDir')

    # 参数验证
    if not factors:
        return jsonify({
            'success': False,
            'error': '因子列表不能为空'
        }), 400

    if not start_date or not end_date:
        return jsonify({
            'success': False,
            'error': '开始日期和结束日期不能为空'
        }), 400

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
        return jsonify({
            'success': False,
            'error': result.get('error', '生成因子报告失败')
        }), 400

    return api_response(result)


@analysis_bp.route('/api/portfolio/factor-decay', methods=['POST'])
@handle_api_error
def factor_decay():
    """因子衰减分析 - 替代旧 quant_cli factor.decay"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.factor_decay import analyze_factor_decay
        data = request.get_json(silent=True) or {}
        from pathlib import Path
        quant_root = _V2_ROOT.parent / 'quant'
        result = analyze_factor_decay(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503


@analysis_bp.route('/api/portfolio/sector-aggregate', methods=['POST'])
@handle_api_error
def sector_aggregate():
    """
    行业聚合分析 - v2 原生实现

    按行业或板块聚合估值、质量、负债率和信号数量

    Request:
    {
        "sector_field": "sector",  // 聚合维度：sector=一级行业，industry=二级行业
        "limit": 20                // 返回结果数量限制
    }

    Response:
    {
        "success": true,
        "data": {
            "sectors": [
                {
                    "name": "银行",
                    "stock_count": 45,
                    "avg_pe": 5.2,
                    "avg_pb": 0.6,
                    "avg_roe": 12.5,
                    "signal_count": 8
                },
                ...
            ],
            "count": 20,
            "sector_field": "sector"
        }
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        sector_field = data.get('sector_field', 'sector')
        limit = data.get('limit', 20)

        # 参数验证
        if sector_field not in ['sector', 'industry']:
            return jsonify({
                'success': False,
                'error': 'sector_field 必须是 "sector" 或 "industry"'
            }), 400

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
            # fallback 链：请求字段 → sector → industry → 未分类
            # （2026-07-28 前 fallback 写错：sector_field='sector' 时 fallback
            # 还是查 sector 本身，sector 列从未填充导致全市场落入「未分类」）
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

        # 未分类股票数（>0 说明 stocks 表 sector/industry 列有缺口）
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
        return jsonify({
            'success': False,
            'error': f'服务器内部错误: {str(e)}'
        }), 500


@analysis_bp.route('/api/portfolio/strategy-optimize', methods=['POST'])
@handle_api_error
def strategy_optimize():
    """
    策略参数网格搜索优化（v2 重写 — 真实回测）。

    入参：
    {
        "strategy_id": 53,
        "symbol": "600000",
        "start_date": "2025-01-01",
        "end_date": "2026-01-01",
        "metric": "sharpe",                # 优化目标：sharpe / return / win_rate / calmar
        "param_grid": {                    # 参数搜索空间
            "rsi_low": [25, 30, 35],
            "rsi_high": [65, 70, 75],
            "trail_pct": [0.03, 0.05, 0.07]
        },
        "initial_capital": 1000000,
        "max_combinations": 50             # 可选，限制最大组合数
    }

    返回：
    {
        "success": true,
        "data": {
            "strategy_id": 53,
            "symbol": "600000",
            "metric": "sharpe",
            "total_combinations": 27,
            "successful": 27,
            "best": {
                "params": {"rsi_low": 30, "rsi_high": 70, "trail_pct": 0.05},
                "score": 2.15,
                "total_return": 0.23,
                "sharpe_ratio": 2.15,
                "max_drawdown": -0.08,
                "win_rate": 0.62
            },
            "top10": [...]
        }
    }
    """
    data = request.get_json(silent=True) or {}
    data = convert_keys_to_snake(data)

    # 参数校验
    strategy_id = data.get('strategy_id')
    if not strategy_id:
        return jsonify({'success': False, 'error': '缺少参数: strategy_id'}), 400

    symbol = data.get('symbol')
    if not symbol:
        return jsonify({'success': False, 'error': '缺少参数: symbol'}), 400

    start_date = data.get('start_date', '2025-01-01')
    end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    metric = data.get('metric', 'sharpe')
    param_grid = data.get('param_grid', {})
    initial_cash = float(data.get('initial_capital', 1000000))
    max_combinations = int(data.get('max_combinations', 50))

    if not param_grid:
        return jsonify({'success': False, 'error': '缺少参数: param_grid'}), 400

    try:
        strategy_id_int = int(strategy_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': f'无效的 strategy_id: {strategy_id}'}), 400

    # 生成所有参数组合（笛卡尔积）
    import itertools
    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]
    combinations = list(itertools.product(*param_values))
    total_combinations = len(combinations)

    logger.info(f"参数优化开始: strategy={strategy_id_int}, symbol={symbol}, 组合数={total_combinations}")

    if total_combinations > max_combinations:
        return jsonify({
            'success': False,
            'error': f'参数组合过多 ({total_combinations})，请缩小搜索范围或提高 max_combinations (当前限制: {max_combinations})'
        }), 400

    from application.services.strategy_code_service import StrategyCodeService
    from concurrent.futures import ThreadPoolExecutor, as_completed

    service = StrategyCodeService()

    # 定义单次回测任务
    def run_single_backtest(idx, combo):
        params_dict = dict(zip(param_names, combo))
        try:
            result = service.backtest_strategy(
                strategy_id=strategy_id_int,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                params_override=params_dict
            )

            # 提取优化指标
            score_map = {
                'sharpe': result.get('sharpe_ratio', 0),
                'return': result.get('total_return', 0),
                'win_rate': result.get('win_rate', 0),
                'calmar': result.get('calmar_ratio', result.get('sharpe_ratio', 0)),
            }
            score = score_map.get(metric, result.get('sharpe_ratio', 0))

            logger.info(f"  组合 [{idx+1}/{total_combinations}]: {params_dict} → score={score:.4f}")

            return {
                'params': params_dict,
                'score': round(float(score), 4),
                'total_return': result['total_return'],
                'sharpe_ratio': result['sharpe_ratio'],
                'max_drawdown': result['max_drawdown'],
                'win_rate': result['win_rate'],
                'profit_factor': result.get('profit_factor', 0),
            }

        except Exception as e:
            logger.warning(f"  组合 [{idx+1}/{total_combinations}] {params_dict} 回测失败: {e}")
            return None

    # 并行执行回测（10 workers）
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(run_single_backtest, idx, combo): idx
            for idx, combo in enumerate(combinations)
        }

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)

    if not results:
        return jsonify({'success': False, 'error': '所有参数组合回测均失败'}), 500

    # 按分数降序排列
    results.sort(key=lambda r: r['score'], reverse=True)

    best = results[0]
    top10 = results[:10]

    return api_response({
        'strategy_id': strategy_id_int,
        'symbol': symbol,
        'metric': metric,
        'total_combinations': total_combinations,
        'successful': len(results),
        'best': best,
        'top10': top10,
    }, message=f'优化完成: 最优参数={best["params"]}, score={best["score"]}')


@analysis_bp.route('/api/portfolio/performance-analyze', methods=['POST'])
@handle_api_error
def performance_analyze():
    """策略表现分析 - 替代旧 quant_cli performance.analyze"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.strategy_analytics import analyze_performance
        data = request.get_json(silent=True) or {}
        from pathlib import Path
        quant_root = _V2_ROOT.parent / 'quant'
        result = analyze_performance(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503


@analysis_bp.route('/api/portfolio/signal-arbitrate', methods=['POST'])
@handle_api_error
def signal_arbitrate():
    """信号仲裁 - 替代旧 quant_cli signal.arbitrate"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.strategy_analytics import arbitrate_signals
        data = request.get_json(silent=True) or {}
        from pathlib import Path
        quant_root = _V2_ROOT.parent / 'quant'
        result = arbitrate_signals(quant_root, data)
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503


@analysis_bp.route('/api/cli/ml-predict', methods=['POST'])
@handle_api_error
def cli_ml_predict():
    """ML预测 — 使用 v2 ML 流水线"""
    symbol_raw = request.args.get('symbol') or (request.get_json(silent=True) or {}).get('symbol')
    if not symbol_raw:
        return jsonify({'success': False, 'error': '缺少参数: symbol'}), 400
    symbol = str(symbol_raw).replace('.SH', '').replace('.SZ', '')
    
    from datetime import datetime as _dt, timedelta as _td
    from application.services.ml_pipeline.feature_engineering import FeatureEngineer
    from application.services.ml_pipeline.predictor import MLPredictor
    from adapters.inbound.api.ml_routes import _resolve_latest_version, _strip_suffix, _normalize_kline
    
    model_type = 'xgboost'
    version = _resolve_latest_version(model_type)
    if not version:
        return jsonify({'success': False, 'error': f'没有可用的 {model_type} 模型，请先训练'}), 200
    
    end_date = _dt.now().strftime('%Y-%m-%d')
    start_date = (_dt.now() - _td(days=180)).strftime('%Y-%m-%d')
    
    try:
        rows = ds.kline.get_daily_klines(symbol, start_date, end_date)
    except Exception as e:
        # Surface the real failure (DB connection, polars parsing, etc.) instead
        # of masking it as "no data". A fetch failure is a 500, not a 400.
        logger.error(f"获取 {symbol} K线失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'获取 {symbol} K线数据失败: {e}'}), 500
    
    if not rows:
        return jsonify({'success': False, 'error': f'{symbol} 无K线数据'}), 400
    
    klines_dict = {symbol: [_normalize_kline(r) for r in rows]}
    
    engineer = FeatureEngineer()
    features_df = engineer.extract_features(klines_dict)
    if features_df.empty:
        return jsonify({'success': False, 'error': '无法提取特征'}), 400
    
    _, X = engineer.prepare_features(features_df, handle_missing='fill', fit_scaler=True)
    
    predictor = MLPredictor(model_type=model_type)
    try:
        predictor.load_model(version=version)  # Loads the trained model
    except FileNotFoundError:
        return jsonify({'success': False, 'error': f'模型文件未找到: {model_type}_{version}'}), 200
    
    # 对齐特征列名：训练特征用大写 (ATR14)，Engineer 用小写 (atr14)
    expected_features = predictor.model.feature_names_in_
    X_columns = set(X.columns)
    missing = set(expected_features) - X_columns
    if missing and len(missing) < len(expected_features) * 0.5:
        # 尝试大写 → 小写映射
        rename_map = {}
        for ef in expected_features:
            if ef not in X_columns and ef.lower() in X_columns:
                rename_map[ef.lower()] = ef
        if rename_map:
            X = X.rename(columns=rename_map)
            for ef in missing:
                if ef not in X.columns:
                    X[ef] = 0.0
        else:
            for ef in missing:
                X[ef] = 0.0
    elif missing:
        for ef in missing:
            X[ef] = 0.0
    X = X[list(expected_features)]
    
    prediction = predictor.predict(X)
    
    prediction = predictor.predict(X)
    signal_col = [c for c in prediction.columns if 'signal' in c.lower() or 'pred' in c.lower()]
    prob_col = [c for c in prediction.columns if 'prob' in c.lower() or 'conf' in c.lower()]
    
    signal_val = str(prediction.iloc[0][signal_col[0]]) if signal_col else str(prediction.iloc[0].iloc[0]) if len(prediction.columns) > 0 else 'hold'
    prob_val = float(prediction.iloc[0][prob_col[0]]) if prob_col else 0.5
    
    return api_response({
        'symbol': symbol,
        'signal': signal_val,
        'confidence': round(prob_val, 4),
        'model_type': model_type,
        'version': version,
    })


@analysis_bp.route('/api/ml/history', methods=['GET'])
@handle_api_error
def ml_history():
    """ML训练历史 - 替代旧 quant_cli ml.history"""
    import glob as _glob, json as _json
    from pathlib import Path

    models_dir = _V2_ROOT.parent / 'quant' / 'quantsys' / 'ml' / 'models'
    files = sorted(
        (Path(f) for f in _glob.glob(str(models_dir / 'training_report_*.json'))
         if 'latest' not in f),
        reverse=True,
    )
    history = []
    for f in files[:20]:
        report = _json.loads(f.read_text(encoding='utf-8'))
        history.append({
            'timestamp': report.get('timestamp'),
            'model_type': report.get('model_type'),
            'n_features': report.get('data', {}).get('n_features'),
            'total_samples': report.get('data', {}).get('total_samples'),
            'cv_accuracy': report.get('cv_results', {}).get('mean_scores', {}).get('accuracy'),
            'cv_auc': report.get('cv_results', {}).get('mean_scores', {}).get('auc'),
            'test_accuracy': report.get('test_metrics', {}).get('accuracy'),
            'test_auc': report.get('test_metrics', {}).get('auc'),
            'class_balance': report.get('data', {}).get('class_balance'),
        })
    return api_response({'count': len(history), 'history': history})


# ─── ZigZag 波段买卖点分析 ──────────────────────────────────

@analysis_bp.route('/api/analysis/data-health', methods=['GET'])
@handle_api_error
def check_data_health():
    """
    数据源健康检查 - 检查K线数据的可用性和完整性

    查询参数:
        symbol: 可选，检查特定股票的数据健康状况

    返回:
    {
        "success": true,
        "data": {
            "overall_health": "good",  // good/warning/critical
            "total_stocks": 100,
            "stocks_with_recent_data": 95,
            "oldest_data_date": "2020-01-01",
            "latest_data_date": "2026-07-17",
            "data_quality_score": 0.95,
            "issues": []
        }
    }
    """
    from adapters.outbound.repositories import KlineORMRepository
    from datetime import datetime, timedelta

    symbol = request.args.get('symbol')
    kline_repo = KlineORMRepository()

    if symbol:
        # 检查特定股票
        all_klines = kline_repo.get_daily_klines(
            symbol=symbol,
            start_date='1990-01-01',
            end_date=datetime.now().strftime('%Y-%m-%d')
        )

        if all_klines is None or len(all_klines) == 0:
            return api_response({
                'symbol': symbol,
                'status': 'no_data',
                'message': '该股票没有K线数据',
                'suggestions': ['请检查股票代码是否正确', '该股票可能未上市或数据未录入']
            })

        klines = all_klines.to_dicts() if hasattr(all_klines, 'to_dicts') else all_klines
        first_date = klines[0].get('trade_date') if klines else None
        last_date = klines[-1].get('trade_date') if klines else None
        total_count = len(klines)

        # 计算数据新鲜度
        if last_date:
            if isinstance(last_date, str):
                last_dt = datetime.strptime(last_date, '%Y-%m-%d')
            else:
                last_dt = last_date
            days_old = (datetime.now() - last_dt).days
        else:
            days_old = 999

        # 评估健康状态
        if days_old <= 5:
            status = 'excellent'
            message = '数据非常新鲜'
        elif days_old <= 30:
            status = 'good'
            message = '数据较新'
        elif days_old <= 90:
            status = 'warning'
            message = '数据有些陈旧'
        else:
            status = 'critical'
            message = '数据严重过期'

        return api_response({
            'symbol': symbol,
            'status': status,
            'message': message,
            'data_range': {
                'start': str(first_date) if first_date else None,
                'end': str(last_date) if last_date else None
            },
            'total_records': total_count,
            'days_since_update': days_old,
            'suitable_for_analysis': total_count >= 100 and days_old <= 90
        })
    else:
        # 全局健康检查
        # 这里简化实现，实际可以查询数据库统计
        return api_response({
            'overall_health': 'good',
            'message': '数据源运行正常',
            'total_stocks_with_data': 'unknown',  # 需要数据库统计
            'recommendation': '使用 ?symbol=600519 检查特定股票'
        })


@analysis_bp.route('/api/analysis/swing-points', methods=['POST'])
@handle_api_error
def analyze_swing_points():
    """
    ZigZag 波段分析 — 根据历史价格波动识别买卖点

    请求体:
    {
        "symbol": "600519",           // 必填：股票代码
        "start_date": "2025-01-01",   // 可选：开始日期，默认1年前
        "end_date": "2026-06-01",     // 可选：结束日期，默认今天
        "min_change": 5.0             // 可选：最小波动幅度%，默认5
    }

    返回:
    {
        "success": true,
        "data": {
            "symbol": "600519",
            "swing_points": [...],    // 拐点列表（高低交替）
            "trades": [...],          // 配对交易列表
            "summary": {...}          // 统计摘要
        }
    }
    """
    from application.services.swing_point_service import SwingPointService

    raw = request.get_json(silent=True) or {}
    params = convert_keys_to_snake(raw)

    svc = SwingPointService()
    result = svc.analyze(params)

    return api_response(sanitize_for_json(result))


@analysis_bp.route('/api/risk/metrics', methods=['POST'])
@handle_api_error
def calculate_risk_metrics():
    """
    计算风险指标 - 使用 empyrical 标准算法

    Request:
    {
        "returns": [0.01, -0.02, 0.015, ...],       // 必填：日收益率序列
        "benchmark_returns": [0.008, -0.01, ...],   // 可选：基准收益率（用于Alpha/Beta）
        "risk_free_rate": 0.02                      // 可选：年化无风险利率（默认2%）
    }

    Response:
    {
        "success": true,
        "data": {
            "sharpe_ratio": 1.25,           // 夏普比率
            "sortino_ratio": 1.45,          // 索提诺比率
            "calmar_ratio": 0.85,           // 卡尔马比率
            "max_drawdown": -0.15,          // 最大回撤
            "alpha": 0.05,                  // Alpha（相对基准）
            "beta": 0.95,                   // Beta（相对基准）
            "var_95": -0.025,               // VaR（95%分位数）
            "cvar_95": -0.035,              // CVaR（条件VaR）
            "annual_return": 0.12,          // 年化收益率
            "annual_volatility": 0.18       // 年化波动率
        }
    }

    注意：
    - 需要安装 empyrical-reloaded
    - returns 应为日收益率（不是累计收益）
    - benchmark_returns 可选，不提供则不计算 Alpha/Beta
    """
    from application.services.risk_metrics_service import RiskMetricsService
    import pandas as pd

    data = request.get_json() or {}

    # 参数验证
    returns = data.get('returns')
    if not returns:
        return jsonify({
            'success': False,
            'error': 'returns 参数不能为空'
        }), 400

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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

