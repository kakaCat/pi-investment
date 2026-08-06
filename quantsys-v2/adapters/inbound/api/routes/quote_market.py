"""
quote_market routes.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request

import requests

import logging

logger = logging.getLogger(__name__)

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    _aggregate_weekly,
    _aggregate_monthly,
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

from application.services.realtime_quote_service import RealtimeQuoteService

quote_market_bp = Blueprint('quote_market', __name__)

@quote_market_bp.route('/api/stocks/<symbol>', methods=['GET'])
@handle_api_error
def get_stock_detail(symbol):
    """获取个股详情 + 最新价格（兼容 Express 前端）"""
    stock = ds.stock.get_by_symbol(symbol)
    if not stock:
        return jsonify({'success': False, 'error': f'Stock not found: {symbol}'}), 404

    enriched = enrich_stock_data(stock)

    try:
        latest = ds.kline.get_latest_daily_kline(symbol)
        if latest:
            enriched['price'] = float(latest.get('close', enriched.get('price', 0)))
    except Exception:
        pass

    return api_response(enriched)


def _get_db_quote(symbol: str):
    """
    从数据库获取最新K线数据作为行情

    Args:
        symbol: 股票代码

    Returns:
        API response dict or None
    """
    try:
        latest = ds.kline.get_latest_daily_kline(symbol)
        if latest and latest.get("close"):
            stock = ds.stock.get_by_symbol(symbol) or {}
            return {
                "symbol": symbol,
                "name": stock.get("name", symbol),
                "price": float(latest["close"]),
                "change_pct": float(latest.get("change_pct", 0) or 0),
                "high": float(latest.get("high", 0) or 0),
                "low": float(latest.get("low", 0) or 0),
                "open": float(latest.get("open", 0) or 0),
                "volume": float(latest.get("volume", 0) or 0),
                "trade_date": latest.get("trade_date", ""),
                "source": "db_fallback",
            }
    except Exception as e:
        logging.getLogger(__name__).warning(f"DB quote failed for {symbol}: {e}")

    return None


@quote_market_bp.route('/api/stock/<symbol>/quote', methods=['GET'])
@handle_api_error
def get_stock_quote(symbol):
    """
    实时行情端点

    参数:
        source: 数据源模式 (realtime|db|auto, 默认: realtime)
            - realtime: 使用 RealtimeQuoteService 获取实时数据
            - db: 直接查询数据库
            - auto: 实时失败后 fallback 到数据库

    数据源优先级（realtime/auto 模式）:
        tencent → sina → eastmoney → akshare（与 DataProviderManager.quote_providers 一致）
    """
    # 参数验证
    source = request.args.get('source', 'realtime').lower()
    if source not in ['realtime', 'db', 'auto']:
        return jsonify({
            "success": False,
            "error": f"Invalid source parameter: {source}. Must be one of: realtime, db, auto"
        }), 400

    clean_symbol = re.sub(r'[^A-Za-z0-9.]', '', symbol)

    # db 模式：直接查询数据库
    if source == 'db':
        db_result = _get_db_quote(clean_symbol)
        if db_result:
            return api_response(db_result)
        return jsonify({"success": False, "error": f"无法从数据库获取 {symbol} 的行情"}), 404

    # realtime 或 auto 模式：直连 DataProviderManager（拿到各数据源失败原因，供 agent 诊断）
    quote_result = None
    try:
        from adapters.outbound.datasources import get_data_provider_manager
        quote_result = get_data_provider_manager().get_quote(clean_symbol)
    except Exception as e:
        logging.getLogger(__name__).warning(f"DataProviderManager.get_quote failed for {symbol}: {e}")

    if quote_result and quote_result.get('success'):
        quote_data = quote_result['data']
        # 转换 QuoteData 为 API 响应格式
        result = {
            "symbol": quote_data.symbol,
            "name": quote_data.name,
            "price": quote_data.price,
            "open": quote_data.open,
            "high": quote_data.high,
            "low": quote_data.low,
            "prev_close": quote_data.prev_close,
            "volume": quote_data.volume,
            "amount": quote_data.amount,
            "change": quote_data.change,
            "change_pct": quote_data.change_pct,
            "source": quote_data.source,
            "timestamp": quote_data.timestamp,
        }
        return api_response(result)

    # realtime 模式：所有数据源失败，返回 502 + 诊断信息
    if source == 'realtime':
        return jsonify(_build_quote_failure_body(symbol, quote_result)), 502

    # auto 模式：fallback 到数据库
    db_result = _get_db_quote(clean_symbol)
    if db_result:
        return api_response(db_result)

    return jsonify(_build_quote_failure_body(symbol, quote_result)), 502


def _build_quote_failure_body(symbol: str, quote_result) -> dict:
    """组装 quote 失败的结构化诊断响应体（供 agent 自我纠正）"""
    if quote_result:
        error_msg = quote_result.get('error', 'All data providers failed')
        attempted = quote_result.get('attempted_sources', [])
        provider_errors = quote_result.get('provider_errors', {})
    else:
        error_msg, attempted, provider_errors = '行情服务异常', [], {}

    if attempted:
        error_text = f"{error_msg} (尝试数据源: {', '.join(attempted)})"
    else:
        error_text = f"无法获取 {symbol} 的实时行情：{error_msg}"

    return {
        "success": False,
        "error": error_text,
        "provider_errors": provider_errors,
        "suggestion": _quote_failure_suggestion(symbol, provider_errors),
    }


def _quote_failure_suggestion(symbol: str, provider_errors: dict) -> str:
    """根据各数据源的具体失败原因，生成可行动的修复建议（供 agent 自我纠正）"""
    joined = ' '.join(provider_errors.values())
    hints = []

    code = symbol.split('.')[0]
    if symbol.endswith('.HK') or (code.isdigit() and len(code) <= 5):
        hints.append(
            f"疑似港股代码：本接口主要支持 6 位 A 股代码，港股请尝试 {code.zfill(5)}.HK 格式"
        )
    if any(k in joined for k in ('timeout', 'Timeout', 'Connection', 'RemoteDisconnected', '502', 'Max retries')):
        hints.append("存在网络型失败：数据源可能临时限流/封禁，可稍后重试")
    if code.isdigit() and len(code) == 6:
        hints.append("请检查代码是否正确、是否已上市/已退市")
    if not hints:
        hints.append("请检查代码格式（A股为 6 位数字，可带 .SH/.SZ 后缀）")
    hints.append("也可用 source=db 查询本地缓存（如有）")

    return '；'.join(hints)


def _kline_failure_suggestion(symbol: str, period: str, provider_errors: dict) -> str:
    """根据各数据源的具体失败原因，生成可行动的修复建议（供 agent 自我纠正）"""
    joined = ' '.join(provider_errors.values())
    hints = []

    if '无法映射' in joined:
        hints.append(
            "代码无法映射到任何数据源：A股个股为 60/68(沪)、00/30(深)、4/8/92(北) 开头；"
            "深市指数用 399xxx（如创业板指 399006、深成指 399001）；"
            "上证指数(000xxx段)与深市个股代码歧义，暂不支持"
        )
    if symbol.split('.')[0].startswith('000'):
        hints.append(
            "000xxx 按深市个股解析（000001=平安银行）；"
            "若你想查的是上证指数，当前不支持，可改用深市指数 399001"
        )
    if any(k in joined for k in ('timeout', 'Timeout', 'Connection', 'RemoteDisconnected', '502', 'Max retries')):
        hints.append("存在网络型失败：数据源可能临时限流/封禁，可稍后重试，或缩短日期范围")
    if '数据库无' in joined and len(provider_errors) > 1:
        hints.append("本地数据库无该代码缓存（指数/冷门标的属正常），关键在网络源是否可用")
    if period != 'daily':
        hints.append("周/月线由日线聚合，分钟线仅支持个股最近30天；可先用 daily 验证代码本身是否可取数")
    if not hints:
        hints.append("请检查：代码是否正确（6位数字）、是否已上市/已退市、日期范围内是否有交易")

    return '；'.join(hints)


@quote_market_bp.route('/api/stock/<symbol>/history', methods=['GET'])
@handle_api_error
def get_stock_history(symbol):
    """
    OHLCV 历史数据 - 替代旧 quant_cli stock.history

    支持多数据源自动降级：database (主) → akshare (备)

    参数:
        - period: daily|weekly|monthly|1m|5m|15m|30m (默认 daily)
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        - limit: 返回数据点数 (默认60, 最大200)
        - source: 数据源选择 (auto|db|akshare, 默认 auto)

    日/周/月线优先从数据库获取，分钟线使用akshare实时查询（仅A股，最近30天）
    """
    from adapters.outbound.datasources import get_data_provider_manager

    period = request.args.get('period', 'daily')
    limit = min(request.args.get('limit', 60, type=int), 200)
    source = request.args.get('source', 'auto').lower()

    end_date = request.args.get('end_date') or datetime.now().strftime('%Y-%m-%d')
    if not request.args.get('start_date'):
        lookback_days = {"daily": limit + 20, "weekly": limit * 10 + 20, "monthly": limit * 35 + 20}
        # 分钟级数据默认查询最近2天
        if period in ['1m', '5m', '15m', '30m', '60m']:
            lookback_days[period] = 2
        start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=lookback_days.get(period, limit+20))
        start_date = start_dt.strftime('%Y-%m-%d')
    else:
        start_date = request.args.get('start_date')

    # 使用多数据源管理器
    provider_manager = get_data_provider_manager()

    try:
        result = provider_manager.get_klines(symbol, period, start_date, end_date)

        if not result['success']:
            error_msg = result.get('error', 'No kline data available')
            attempted = result.get('attempted_sources', [])
            provider_errors = result.get('provider_errors', {})
            return jsonify({
                "success": False,
                "error": f"{error_msg} (尝试数据源: {', '.join(attempted)})",
                "provider_errors": provider_errors,
                "suggestion": _kline_failure_suggestion(symbol, period, provider_errors),
            }), 404

        # 转换 KlineData 列表为 API 响应格式
        klines = result['data']
        data_source = result['source']

        records = []
        for kline in klines:
            records.append({
                "date": kline.date,
                "open": kline.open,
                "high": kline.high,
                "low": kline.low,
                "close": kline.close,
                "volume": kline.volume,
                "change_pct": kline.change_pct,
            })

        # 应用周期聚合（如果需要）
        if period == 'weekly':
            records = _aggregate_weekly(records)
        elif period == 'monthly':
            records = _aggregate_monthly(records)

        # 限制返回数量
        records = records[-limit:]

        payload = {
            "symbol": symbol,
            "period": period,
            "count": len(records),
            "data": records,
            "source": data_source,  # 标识实际使用的数据源
        }
        # 000xxx 存在歧义：既是深市个股（如 000001 平安银行），也常被用来
        # 指上证指数。当前一律按深市个股解析，显式告知调用方防止静默错查。
        if symbol.split('.')[0].startswith('000'):
            payload["note"] = (
                "注意: 000xxx 代码按深市个股解析"
                "（000001=平安银行，而非上证指数）；上证指数K线暂不支持"
            )
        return api_response(payload)

    except Exception as e:
        logger.error(f"Failed to get kline data for {symbol}: {e}")
        return jsonify({
            "success": False,
            "error": f"获取K线数据失败: {str(e)}"
        }), 500


@quote_market_bp.route('/api/stock/<symbol>/valuation', methods=['GET'])
@handle_api_error
def get_stock_valuation(symbol):
    """
    估值分析 - 替代旧 quant_cli analysis.valuation + analysis.pe_percentile
    
    返回: PE/PB/格雷厄姆公允价值/估值状态
    """
    stock = ds.stock.get_by_symbol(symbol)
    if not stock:
        return jsonify({"success": False, "error": f"Stock not found: {symbol}"}), 404

    # Convert ORM object to dict if needed
    stock_dict = stock.to_dict() if hasattr(stock, 'to_dict') else stock

    pe = _safe_float(stock_dict.get('pe', 0))
    pb = _safe_float(stock_dict.get('pb', 0))
    market_cap = _safe_float(stock_dict.get('market_cap', 0))
    name = stock_dict.get('name', symbol)

    eps = _safe_float(stock_dict.get('eps', 0))
    graham_fair_value = round(eps * 28.5, 2) if eps > 0 else None

    if pe <= 0:
        status = "expensive"  # Loss-making
        detail = "公允价值" if graham_fair_value else "（亏损/无PE数据，法尔值不可用）"
    elif pe < 15:
        status = "cheap"
        detail = "公允价值" if graham_fair_value else ""
    elif pe < 40:
        status = "fair"
        detail = "公允价值" if graham_fair_value else ""
    else:
        status = "expensive"
        detail = "公允价值" if graham_fair_value else ""

    klines = ds.kline.get_daily_klines(symbol, 
        (datetime.now() - timedelta(days=365*3)).strftime('%Y-%m-%d'),
        datetime.now().strftime('%Y-%m-%d'))
    
    pe_percentile = None
    pe_median = None
    pe_high = None
    pe_low = None
    # get_daily_klines 返回 polars DataFrame：bool(df) 抛 TypeError、
    # 迭代/k.get 也不兼容——先转 dict 列表
    if hasattr(klines, 'to_dicts'):
        klines = klines.to_dicts()
    if klines and pe > 0:
        closes = [float(k.get('close', 0)) for k in klines if float(k.get('close', 0)) > 0]
        if closes:
            pe_high = round(max(closes) * pe / float(klines[-1]['close']), 2) if klines[-1].get('close') else None

    result = {
        "symbol": symbol,
        "name": name,
        "pe": pe,
        "pb": pb,
        "market_cap_billion": round(market_cap / 1e8, 2) if market_cap else 0,
        "fair_value_estimate": graham_fair_value,
        "valuation_status": status,
        "status_text": {"cheap": "低估", "fair": "合理", "expensive": "高估"}.get(status, "未知"),
    }
    
    if pe_percentile is not None:
        result["pe_percentile"] = pe_percentile
        result["pe_median"] = pe_median
        result["pe_high"] = pe_high
        result["pe_low"] = pe_low

    return api_response(result)


# REMOVED: 重复路由已迁移到 market.py 的 get_sectors_v2()
# 原因：与 market.py:@market_bp.route('/api/market/sectors') 冲突
# 如需使用，请调用 /api/market/sectors（统一使用 market.py 的实现）
# 删除时间：2026-06-16
#
# @quote_market_bp.route('/api/market/sectors', methods=['GET'])
# @handle_api_error
# def get_market_sectors():
#     """
#     行业板块列表 - 替代旧 quant_cli market.sectors
#
#     数据源: akshare → 东方财富行业板块
#     """
#     try:
#         import akshare as ak
#         frame = ak.stock_board_industry_name_em()
#         if frame is None or frame.empty:
#             return jsonify({"success": False, "error": "No sector data available"}), 502
#
#         sectors = []
#         for _, row in frame.iterrows():
#             sectors.append({
#                 'name': str(row.get('板块名称', '')),
#                 'code': str(row.get('板块代码', '')),
#                 'stock_count': _safe_float(row.get('上市股票数', 0), decimals=0),
#                 'change_pct': _safe_float(row.get('涨跌幅', 0)),
#                 'volume': _safe_float(row.get('成交量', 0), decimals=0),
#             })
#
#         return api_response({'sectors': sectors, 'count': len(sectors)})
#     except ImportError:
#         return jsonify({"success": False, "error": "akshare not available"}), 503
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 502


@quote_market_bp.route('/api/market/sector/<path:sector>', methods=['GET'])
@handle_api_error
def get_sector_stocks(sector):
    """
    行业/概念板块成分筛选 - 替代旧 quant_cli screening.sector

    参数: sector (板块名称), max_pe, limit
    数据来源: DataProviderManager -> EastmoneySectorProvider（多数据源统一层）
    """
    from adapters.outbound.datasources import get_data_provider_manager

    max_pe = request.args.get('max_pe', type=float)
    limit = min(request.args.get('limit', 30, type=int), 50)

    try:
        result = get_data_provider_manager().get_sector_stocks(sector)

        if not result.get('success'):
            # 所有数据源网络失败
            error_msg = result.get('error', 'No sector data available')
            attempted = result.get('attempted_sources', [])
            return jsonify({
                "success": False,
                "error": f"{error_msg} (尝试数据源: {', '.join(attempted)})"
            }), 502

        payload = result['data'].data  # MarketData.data dict
        if not payload.get('found'):
            return jsonify({"success": False, "error": f"Sector not found: {sector}"}), 404

        stocks = payload.get('stocks', [])
        if not stocks:
            return jsonify({"success": False, "error": f"No stocks found in {sector}"}), 404

        # 统一字段：market_cap(元) -> market_cap_billion(亿元)
        for s in stocks:
            s['market_cap_billion'] = round((s.pop('market_cap', 0) or 0) / 1e8, 2)

        if max_pe:
            stocks = [s for s in stocks if not (s['pe'] > max_pe and s['pe'] > 0)]
        stocks = stocks[:limit]

        return api_response({
            'sector': sector,
            'sector_code': payload.get('sector_code'),
            'stocks': sorted(stocks, key=lambda x: x['market_cap_billion'], reverse=True),
            'count': len(stocks),
            'source': result.get('source'),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 502


@quote_market_bp.route('/api/stocks/market/overview', methods=['GET'])
@handle_api_error
def get_market_overview():
    """市场概览（兼容 Express 前端）"""
    market = request.args.get('market')
    overview = ds.get_market_overview(market=market)
    return api_response(overview)

@quote_market_bp.route('/api/stock/<symbol>/klines', methods=['GET'])
def get_stock_klines(symbol):
    """获取K线数据"""
    try:
        # 统一转换为不带后缀的格式
        clean_symbol = symbol.split('.')[0] if '.' in symbol else symbol

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'daily')
        limit = request.args.get('limit', 100, type=int)

        if not start_date or not end_date:
            from datetime import datetime, timedelta
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (datetime.now() - timedelta(days=limit)).strftime('%Y-%m-%d')

        # 判断是日线还是分钟线
        # 日线格式: daily, 1d, 1D, day
        # 分钟线格式: 1m, 5m, 15m, 30m, 60m, 1h, 4h 等
        daily_periods = ['daily', '1d', '1D', 'day', 'D', 'd']

        if period in daily_periods:
            # 日线数据
            klines = ds.kline.get_daily_klines(
                clean_symbol, start_date, end_date,
                fields=['symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']
            )
        else:
            # 分钟线数据
            start_ts = f"{start_date} 00:00:00" if ' ' not in str(start_date) else start_date
            end_ts = f"{end_date} 23:59:59" if ' ' not in str(end_date) else end_date
            klines = ds.kline.get_minute_klines(
                clean_symbol,
                start_ts,
                end_ts,
                fields=['symbol', 'trade_datetime', 'open', 'high', 'low', 'close', 'volume', 'amount']
            )
            # 转换为 dict 列表并添加 trade_date 字段
            if hasattr(klines, 'to_dicts'):
                klines = klines.to_dicts()
            if isinstance(klines, list):
                for kline in klines:
                    if 'trade_datetime' in kline and 'trade_date' not in kline:
                        kline['trade_date'] = str(kline['trade_datetime'])

        # 检查 klines 是否为空（兼容 Polars DataFrame 和 list）
        if klines is None or (hasattr(klines, 'is_empty') and klines.is_empty()) or (isinstance(klines, list) and len(klines) == 0):
            return jsonify({'error': f'No kline data for {symbol}'}), 404

        # 如果是 DataFrame，转换为 dict 列表
        if hasattr(klines, 'to_dicts'):
            klines = klines.to_dicts()

        return jsonify({
            'symbol': clean_symbol,
            'count': len(klines),
            'klines': sanitize_for_json(klines[-limit:])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
