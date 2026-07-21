"""
实时行情 API V2 - 只返回真实实时数据

特性：
- 只返回真实实时数据（不降级到数据库）
- 优化数据源优先级（腾讯 → 东方财富 → 新浪 → AkShare → 网易）
- 熔断机制（失败源1分钟内不访问）
- 缓存机制（5秒缓存）
- 失败时返回浏览器访问链接
"""
import re
import logging
from flask import Blueprint, jsonify, request

from adapters.inbound.api.shared import api_response, handle_api_error
from application.services.realtime_quote_service_v2 import RealtimeQuoteServiceV2

logger = logging.getLogger(__name__)

quote_v2_bp = Blueprint('quote_v2', __name__)

# 全局实例（单例模式，共享缓存和熔断器）
_quote_service = None


def get_quote_service() -> RealtimeQuoteServiceV2:
    """获取全局 quote service 实例"""
    global _quote_service
    if _quote_service is None:
        _quote_service = RealtimeQuoteServiceV2(
            cache_ttl=5,                    # 缓存5秒
            circuit_breaker_cooldown=60     # 熔断60秒
        )
    return _quote_service


@quote_v2_bp.route('/api/v2/stock/<symbol>/quote', methods=['GET'])
@handle_api_error
def get_realtime_quote_v2(symbol):
    """
    实时行情 API V2 - 只返回真实实时数据

    特性：
    - 不降级到数据库（只返回真实实时数据）
    - 优化数据源优先级：腾讯 → 东方财富 → 新浪 → AkShare → 网易
    - 失败的数据源1分钟内不再访问（熔断机制）
    - 成功数据缓存5秒（减少API调用）
    - 所有数据源都失败时，返回浏览器访问链接

    参数：
        symbol: 股票代码（如 600519 或 600519.SH）

    返回：
        成功时：
        {
            "success": true,
            "data": {
                "symbol": "600519",
                "name": "贵州茅台",
                "price": 1270.26,
                "open": 1304.00,
                "high": 1310.00,
                "low": 1276.00,
                "prev_close": 1281.91,
                "volume": 5247700,
                "amount": 6779894500.0,
                "change": -11.65,
                "change_pct": -0.91,
                "source": "tencent",
                "timestamp": "2026-06-04T14:30:15.123456",
                "cached": false
            }
        }

        失败时：
        {
            "success": false,
            "error": "所有数据源都无法获取实时行情",
            "browser_links": {
                "tencent": "https://gu.qq.com/sh600519",
                "eastmoney": "https://quote.eastmoney.com/sh600519.html",
                "sina": "https://finance.sina.com.cn/realstock/company/sh600519/nc.shtml",
                "xueqiu": "https://xueqiu.com/S/SH600519",
                "tonghuashun": "https://stockpage.10jqka.com.cn/600519/"
            },
            "suggestion": "请使用浏览器访问以上链接查看实时行情"
        }
    """
    # 清理股票代码
    clean_symbol = re.sub(r'[^A-Za-z0-9.]', '', symbol)

    # 自动添加市场后缀（如果缺失）
    if '.' not in clean_symbol:
        if clean_symbol.startswith('6'):
            clean_symbol = f"{clean_symbol}.SH"
        else:
            clean_symbol = f"{clean_symbol}.SZ"

    # 获取服务实例
    service = get_quote_service()

    # 尝试获取实时行情
    quote_data = service.get_realtime_quote(clean_symbol)

    if quote_data:
        # 成功获取实时数据
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
            "cached": False  # TODO: 从服务层传递此信息
        }
        return api_response(result)

    # 所有数据源都失败 - 返回浏览器访问链接
    browser_links = service.get_browser_links(clean_symbol)

    return jsonify({
        "success": False,
        "error": "所有数据源都无法获取实时行情",
        "browser_links": browser_links,
        "suggestion": "请使用浏览器访问以上链接查看实时行情"
    }), 502


@quote_v2_bp.route('/api/v2/quote/stats', methods=['GET'])
@handle_api_error
def get_quote_stats():
    """
    获取实时行情服务统计信息

    返回：
    {
        "success": true,
        "stats": {
            "total_requests": 100,
            "cache_hits": 45,
            "cache_hit_rate": "45.0%",
            "success_count": 90,
            "failure_count": 10,
            "success_rate": "90.0%",
            "provider_stats": {
                "tencent": {"success": 50, "failure": 5, "skipped": 0},
                "eastmoney": {"success": 30, "failure": 3, "skipped": 2},
                "sina": {"success": 10, "failure": 2, "skipped": 5},
                "akshare": {"success": 0, "failure": 0, "skipped": 10},
                "netease": {"success": 0, "failure": 0, "skipped": 10}
            },
            "circuit_breaker_status": {
                "sina": {"blocked": true, "remaining_seconds": 45}
            },
            "cache_stats": {
                "total_entries": 20,
                "fresh_entries": 15,
                "ttl_seconds": 5
            }
        }
    }
    """
    service = get_quote_service()
    stats = service.get_stats()

    return api_response({"stats": stats})


@quote_v2_bp.route('/api/v2/quote/cache/clear', methods=['POST'])
@handle_api_error
def clear_cache():
    """
    清空行情缓存

    返回：
    {
        "success": true,
        "message": "缓存已清空"
    }
    """
    service = get_quote_service()
    service.clear_cache()

    return api_response({"message": "缓存已清空"})


@quote_v2_bp.route('/api/v2/quote/stats/reset', methods=['POST'])
@handle_api_error
def reset_stats():
    """
    重置统计信息（保留缓存和熔断器状态）

    返回：
    {
        "success": true,
        "message": "统计信息已重置"
    }
    """
    service = get_quote_service()
    service.reset_stats()

    return api_response({"message": "统计信息已重置"})


@quote_v2_bp.route('/api/v2/quote/browser-links/<symbol>', methods=['GET'])
@handle_api_error
def get_browser_links(symbol):
    """
    获取股票的浏览器访问链接

    参数：
        symbol: 股票代码

    返回：
    {
        "success": true,
        "symbol": "600519.SH",
        "links": {
            "tencent": "https://gu.qq.com/sh600519",
            "eastmoney": "https://quote.eastmoney.com/sh600519.html",
            "sina": "https://finance.sina.com.cn/realstock/company/sh600519/nc.shtml",
            "xueqiu": "https://xueqiu.com/S/SH600519",
            "tonghuashun": "https://stockpage.10jqka.com.cn/600519/"
        }
    }
    """
    # 清理股票代码
    clean_symbol = re.sub(r'[^A-Za-z0-9.]', '', symbol)

    # 自动添加市场后缀
    if '.' not in clean_symbol:
        if clean_symbol.startswith('6'):
            clean_symbol = f"{clean_symbol}.SH"
        else:
            clean_symbol = f"{clean_symbol}.SZ"

    service = get_quote_service()
    links = service.get_browser_links(clean_symbol)

    return api_response({
        "symbol": clean_symbol,
        "links": links
    })
