"""股票数据 API - FastAPI 版（从 Flask stock.py 迁移，响应契约保持一致）"""
import uuid
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error,
    sanitize_for_json, _read_watchlist,
    acquire_task, get_running_tasks_snapshot, _load_pipeline_runs, _save_pipeline_runs,
)
from application.services.stock_data_service import stock_data_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Stocks - 股票数据"])


def enrich_stock_data(stock) -> Dict:
    """为股票添加额外信息（价格、涨跌幅、K线天数、因子数量等）。逻辑与 Flask stock.py 一致。"""
    if hasattr(stock, 'symbol'):
        symbol, name = stock.symbol, stock.name
        market, industry = stock.market or '', stock.industry or ''
    else:
        symbol, name = stock['symbol'], stock['name']
        market, industry = stock.get('market', ''), stock.get('industry', '')

    stock_data = {
        'symbol': symbol, 'name': name, 'market': market, 'industry': industry,
        'price': 0.0, 'changePercent': 0.0, 'klineDays': 0, 'factorCount': 0,
        'dataStatus': 'incomplete',
    }
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        klines = ds.kline.get_daily_klines(symbol, start_date, end_date)
        # get_daily_klines 返回 polars DataFrame：klines[-1] 取出来的是
        # 1 行 DataFrame，.get('close') 会抛 AttributeError——先转 dict 列表
        if hasattr(klines, 'to_dicts'):
            klines = klines.to_dicts()
        klines_len = 0
        if klines is not None:
            if hasattr(klines, '__len__'):
                klines_len = len(klines)
            elif hasattr(klines, 'shape'):
                klines_len = klines.shape[0]
        if klines is not None and klines_len > 0:
            latest = klines[-1]
            stock_data['price'] = float(latest.get('close', 0))
            if klines_len >= 2:
                prev_close = float(klines[-2].get('close', 0))
                if prev_close > 0:
                    stock_data['changePercent'] = ((stock_data['price'] - prev_close) / prev_close) * 100
        kline_stats = ds.kline.get_kline_stats(symbol, '2020-01-01', end_date)
        if kline_stats:
            stock_data['klineDays'] = kline_stats.get('count', 0)
        available_factors = ds.factor.get_available_factors(symbol)
        if available_factors:
            stock_data['factorCount'] = len(available_factors)
        if stock_data['klineDays'] > 0 and stock_data['factorCount'] > 0:
            stock_data['dataStatus'] = 'complete'
    except Exception as e:
        logger.warning(f"Failed to enrich stock {symbol}: {e}")
    return stock_data


@router.get('/api/stocks/search')
def search_stocks(q: str = Query(''), page: int = Query(1), pageSize: int = Query(20)):
    q = q.strip()
    if not q:
        return error_response({'error': '搜索关键词不能为空'}, 400)
    page = max(1, page)
    page_size = max(1, min(pageSize, 100))
    offset = (page - 1) * page_size
    try:
        results = ds.stock.search(q, limit=page_size + offset)
        total = len(results)
        stocks = results[offset:offset + page_size]
        enriched = [enrich_stock_data(s) for s in stocks]
        return {'query': q, 'total': total, 'page': page, 'pageSize': page_size, 'stocks': enriched}
    except Exception as e:
        return error_response({'error': str(e)}, 500)


@router.get('/api/stocks/list')
def get_stock_list(market: Optional[str] = Query(None), industry: Optional[str] = Query(None),
                   keyword: str = Query(''), page: int = Query(1), pageSize: int = Query(20)):
    try:
        keyword = keyword.strip()
        page = max(1, page)
        page_size = max(1, min(pageSize, 100))
        if keyword:
            all_stocks = ds.stock.search(keyword, limit=500)
            if market:
                all_stocks = [s for s in all_stocks if (hasattr(s, 'market') and s.market == market) or (isinstance(s, dict) and s.get('market') == market)]
            if industry:
                all_stocks = [s for s in all_stocks if (hasattr(s, 'industry') and s.industry == industry) or (isinstance(s, dict) and s.get('industry') == industry)]
            kw = keyword.lower()
            all_stocks = [s for s in all_stocks
                          if kw in str(getattr(s, 'symbol', None) or s.get('symbol', '')).lower()
                          or kw in str(getattr(s, 'name', None) or s.get('name', '')).lower()]
        else:
            all_stocks = ds.stock.get_all(market=market or None, industry=industry or None, limit=500)
        total = len(all_stocks)
        offset = (page - 1) * page_size
        stocks = all_stocks[offset:offset + page_size]
        enriched = [enrich_stock_data(s) for s in stocks]
        return {'count': total, 'stocks': enriched, 'page': page, 'pageSize': page_size}
    except Exception as e:
        logger.error(f"Failed to get stock list: {e}")
        return error_response({'error': str(e)}, 500)


@router.post('/api/stocks/resolve')
def resolve_stock(payload: Dict[str, Any] = Body(default_factory=dict)):
    code = (payload.get('code') or '').strip()
    if not code:
        return error_response({'error': '股票代码不能为空'}, 400)
    try:
        stock = ds.stock.get_by_symbol(code)
        if not stock:
            return error_response({'found': False, 'symbol': code}, 404)
        return {'found': True, 'symbol': stock.symbol, 'name': stock.name,
                'market': stock.market or '', 'industry': stock.industry or ''}
    except Exception as e:
        logger.error(f"Failed to resolve stock {code}: {e}")
        return error_response({'error': str(e)}, 500)


@router.post('/api/stocks/add')
def add_stock(payload: Dict[str, Any] = Body(default_factory=dict)):
    try:
        ds.stock.save(payload)
        return {'success': True, 'symbol': payload.get('symbol')}
    except Exception as e:
        return error_response({'error': str(e)}, 500)


@router.get('/api/stock/{symbol}/announcements')
@handle_api_error
def get_announcements_v2(symbol: str):
    result = stock_data_service.get_announcements(symbol)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.get('/api/stock/{symbol}/news')
@handle_api_error
def get_stock_news_v2(symbol: str, num: int = Query(10)):
    result = stock_data_service.get_news(symbol, num)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.post('/api/stocks/batch-quotes')
@handle_api_error
def get_batch_quotes_v2(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbols = payload.get('symbols', [])
    if not symbols:
        return error_response({'success': False, 'error': 'symbols required'}, 400)
    result = stock_data_service.get_batch_quotes(symbols)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.get('/api/stock/{symbol}/insider-trades')
@handle_api_error
def get_insider_trades_v2(symbol: str, days: int = Query(30)):
    # 注意：Flask 中 sentiment.py 与 stock.py 重复注册了该路径，实际生效的是
    # sentiment.py 的版本（SentimentDataSource，返回 summary/sentiment）。
    # 为与 Flask 实际行为保持 parity，此处复制 sentiment.py 的实现。
    # TODO(P-sentiment): sentiment 域迁移时将此端点并入 sentiment_async 并去重。
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource
    source = SentimentDataSource()
    result = source.get_insider_trades(symbol, days)
    return api_response(result)


@router.get('/api/stock/{symbol}/peers')
@handle_api_error
def get_peers(symbol: str):
    result = stock_data_service.compare_peers(symbol)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.get('/api/stocks/my-stocks')
@handle_api_error
def get_my_stocks():
    positions: List[Dict] = []
    watchlist: List[Dict] = []
    try:
        db = ds.portfolio.db
        if db:
            cursor = db.cursor()
            cursor.execute("""SELECT EXISTS (SELECT FROM information_schema.tables
                              WHERE table_schema = 'quant' AND table_name = 'positions')""")
            has_new_schema = cursor.fetchone()['exists']
            if has_new_schema:
                cursor.execute("""SELECT symbol, name FROM quant.positions
                                  WHERE status = 'open' ORDER BY entry_date DESC""")
                positions = [{'symbol': r['symbol'], 'name': r.get('name', '')} for r in cursor.fetchall()]
            else:
                holdings = ds.portfolio.get_all_holdings()
                positions = [{'symbol': h['symbol'], 'name': h.get('name', '')} for h in holdings]
            cursor.close()
    except Exception:
        pass
    try:
        wl = _read_watchlist()
        watchlist = [{'symbol': i['symbol'], 'name': i.get('name', '')} for i in wl.get('items', [])]
    except Exception:
        pass
    return api_response({'positions': positions, 'watchlist': watchlist})


@router.post('/api/stocks/batch')
def get_stocks_batch(payload: Dict[str, Any] = Body(default_factory=dict)):
    try:
        symbols = payload.get('symbols', [])
        if not symbols or not isinstance(symbols, list):
            return error_response({'success': False, 'error': 'symbols参数必须是数组'}, 400)
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        repo = StockORMRepository()
        result: Dict[str, Any] = {}
        for symbol in symbols:
            try:
                stock = repo.get_by_symbol(symbol)
                if stock:
                    result[symbol] = {'symbol': stock.symbol, 'name': stock.name,
                                      'exchange': getattr(stock, 'exchange', None)}
            except Exception:
                continue
        return {'success': True, 'data': result}
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ K线数据（quote_market.py，P9 补 StockDetail 缺口） ============

@router.get('/api/stock/{symbol}/klines')
def get_stock_klines(symbol: str, start_date: Optional[str] = Query(None),
                     end_date: Optional[str] = Query(None), period: str = Query('daily'),
                     limit: int = Query(100)):
    """获取K线数据（与 Flask quote_market.py 一致）"""
    try:
        clean_symbol = symbol.split('.')[0] if '.' in symbol else symbol
        if not start_date or not end_date:
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (datetime.now() - timedelta(days=limit)).strftime('%Y-%m-%d')

        daily_periods = ['daily', '1d', '1D', 'day', 'D', 'd']
        if period in daily_periods:
            klines = ds.kline.get_daily_klines(
                clean_symbol, start_date, end_date,
                fields=['symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
        else:
            start_ts = f"{start_date} 00:00:00" if ' ' not in str(start_date) else start_date
            end_ts = f"{end_date} 23:59:59" if ' ' not in str(end_date) else end_date
            klines = ds.kline.get_minute_klines(
                clean_symbol, start_ts, end_ts,
                fields=['symbol', 'trade_datetime', 'open', 'high', 'low', 'close', 'volume', 'amount'])
            if hasattr(klines, 'to_dicts'):
                klines = klines.to_dicts()
            if isinstance(klines, list):
                for kline in klines:
                    if 'trade_datetime' in kline and 'trade_date' not in kline:
                        kline['trade_date'] = str(kline['trade_datetime'])

        if klines is None or (hasattr(klines, 'is_empty') and klines.is_empty()) or (isinstance(klines, list) and len(klines) == 0):
            return error_response({'error': f'No kline data for {symbol}'}, 404)
        if hasattr(klines, 'to_dicts'):
            klines = klines.to_dicts()
        return {'symbol': clean_symbol, 'count': len(klines), 'klines': sanitize_for_json(klines[-limit:])}
    except Exception as e:
        return error_response({'error': str(e)}, 500)


# ============ K线数据更新（pipeline.py，P9 补 StockDetail 缺口） ============

@router.post('/api/stocks/data-update-klines')
@handle_api_error
def data_update_klines(payload: Optional[Dict[str, Any]] = Body(None)):
    try:
        data = payload or {}
        symbols_raw = data.get('symbols', [])
        days = data.get('days', 730)

        if isinstance(symbols_raw, str) and symbols_raw.strip():
            symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
        elif isinstance(symbols_raw, list):
            symbols = symbols_raw
        else:
            symbols = []

        if not isinstance(days, int) or days < 1:
            return error_response({'success': False, 'error': 'days 参数必须是大于 0 的整数'}, 400)

        run_id = f"#D-{str(uuid.uuid4())[:8].upper()}"
        if not acquire_task('data_update', run_id):
            existing = get_running_tasks_snapshot().get('data_update', '?')
            return error_response({'success': False, 'error': f'数据更新已在运行中 (run_id={existing})'}, 409)

        now = datetime.now().isoformat()
        run_record = {
            'runId': run_id, 'run_id': run_id, 'status': 'running', 'startTime': now,
            'symbols': symbols if symbols else ['ALL'], 'stages': ['data_update'],
            'stages_list': ['data_update'], 'logs': [f'[{now}] K线数据更新触发: {run_id}, days={days}'],
            'signalCount': 0, 'factorCount': 0, 'days': days,
        }
        runs = _load_pipeline_runs()
        runs.append(run_record)
        _save_pipeline_runs(runs)

        from adapters.shared.pipeline_exec import _execute_pipeline_stages_with_error_handling
        from infrastructure.concurrency.thread_manager import submit_background
        submit_background(
            "api-bg", _execute_pipeline_stages_with_error_handling,
            run_id, symbols if symbols else ['000001.SZ'], ['data_update'], 'data_update',
            days=days)
        return api_response({'success': True, 'run_id': run_id, 'symbols': symbols if symbols else 'ALL',
                             'days': days, 'message': f'K线更新已触发，run_id={run_id}'})
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/data/update')
@handle_api_error
def data_update(payload: Optional[Dict[str, Any]] = Body(None)):
    """触发数据更新（agent data.update 调度命令）— 与 data-update-klines 同一机制"""
    try:
        data = payload or {}
        symbols_raw = data.get('symbols', [])
        days = data.get('days', 730)

        if isinstance(symbols_raw, str) and symbols_raw.strip():
            symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
        elif isinstance(symbols_raw, list):
            symbols = symbols_raw
        else:
            symbols = []

        if not isinstance(days, int) or days < 1:
            return error_response({'success': False, 'error': 'days 参数必须是大于 0 的整数'}, 400)

        run_id = f"#D-{str(uuid.uuid4())[:8].upper()}"
        if not acquire_task('data_update', run_id):
            existing = get_running_tasks_snapshot().get('data_update', '?')
            return error_response({'success': False, 'error': f'数据更新已在运行中 (run_id={existing})'}, 409)

        now = datetime.now().isoformat()
        run_record = {
            'runId': run_id, 'run_id': run_id, 'status': 'running', 'startTime': now,
            'symbols': symbols if symbols else ['ALL'], 'stages': ['data_update'],
            'stages_list': ['data_update'], 'logs': [f'[{now}] K线数据更新触发: {run_id}, days={days}'],
            'signalCount': 0, 'factorCount': 0, 'days': days,
        }
        runs = _load_pipeline_runs()
        runs.append(run_record)
        _save_pipeline_runs(runs)

        from adapters.shared.pipeline_exec import _execute_pipeline_stages_with_error_handling
        from infrastructure.concurrency.thread_manager import submit_background
        submit_background(
            "api-bg", _execute_pipeline_stages_with_error_handling,
            run_id, symbols if symbols else ['000001.SZ'], ['data_update'], 'data_update',
            days=days)
        return api_response({'success': True, 'run_id': run_id, 'symbols': symbols if symbols else 'ALL',
                             'days': days, 'message': f'数据更新已触发，run_id={run_id}'})
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ 实时行情（quote_market.py，agent data_fetch_quote 缺口补齐） ============

def _get_db_quote(symbol: str):
    """从数据库获取最新K线数据作为行情（与 Flask quote_market.py 一致）。"""
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
        logger.warning(f"DB quote failed for {symbol}: {e}")
    return None


def _build_quote_failure_body(symbol: str, quote_result: Optional[dict]) -> dict:
    """组装 quote 失败的结构化诊断响应体（供 agent 自我纠正）。与 Flask quote_market.py 镜像。"""
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
    """根据各数据源的具体失败原因，生成可行动的修复建议（供 agent 自我纠正）。与 Flask quote_market.py 镜像。"""
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


@router.get('/api/stock/{symbol}/quote')
@handle_api_error
def get_stock_quote(symbol: str, source: str = Query('realtime')):
    """实时行情端点（source: realtime|db|auto，数据源优先级 akshare→sina→eastmoney→tencent→netease）"""
    source = source.lower()
    if source not in ['realtime', 'db', 'auto']:
        return error_response({"success": False, "error": f"Invalid source parameter: {source}. Must be one of: realtime, db, auto"}, 400)

    clean_symbol = re.sub(r'[^A-Za-z0-9.]', '', symbol)

    if source == 'db':
        db_result = _get_db_quote(clean_symbol)
        if db_result:
            return api_response(db_result)
        return error_response({"success": False, "error": f"无法从数据库获取 {symbol} 的行情"}, 404)

    # realtime 或 auto 模式：直连 DataProviderManager（拿到各数据源失败原因，供 agent 诊断）
    quote_result = None
    try:
        from adapters.outbound.datasources import get_data_provider_manager
        quote_result = get_data_provider_manager().get_quote(clean_symbol)
    except Exception as e:
        logger.warning(f"DataProviderManager.get_quote failed for {symbol}: {e}")

    if quote_result and quote_result.get('success'):
        quote_data = quote_result['data']
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

    if source == 'realtime':
        return error_response(_build_quote_failure_body(symbol, quote_result), 502)

    # auto 模式：fallback 到数据库
    db_result = _get_db_quote(clean_symbol)
    if db_result:
        return api_response(db_result)
    return error_response(_build_quote_failure_body(symbol, quote_result), 502)

