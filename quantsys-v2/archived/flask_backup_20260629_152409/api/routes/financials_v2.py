"""Financial Data V2 API Routes.

Enhanced financial data endpoints with caching and circuit breaker.
"""

import logging
from flask import Blueprint, jsonify, request
from adapters.inbound.api.shared import api_response, handle_api_error
from application.services.enhanced_financial_data_service import get_enhanced_financial_service

logger = logging.getLogger(__name__)

financials_v2_bp = Blueprint('financials_v2', __name__)


@financials_v2_bp.route('/api/v2/stock/<symbol>/financials', methods=['GET'])
@handle_api_error
def get_financial_data_v2(symbol):
    """Get financial data V2 with caching and circuit breaker.

    Query Parameters:
        statement_type: income/balance/cash_flow/all (default: all)
        periods: number of periods (default: 4)
        source: auto/fresh/cache_only (default: auto)

    Response:
        {
            "success": true,
            "data": {...},
            "cached": true,
            "source": "sina_web"
        }
    """
    statement_type = request.args.get('statement_type', 'all')
    periods = int(request.args.get('periods', 4))
    source = request.args.get('source', 'auto')

    # Validate source parameter
    if source not in ('auto', 'fresh', 'cache_only'):
        return jsonify({
            'success': False,
            'error': f"Invalid source parameter: {source}. Must be auto/fresh/cache_only"
        }), 400

    service = get_enhanced_financial_service()
    data = service.get_financial_data(symbol, statement_type, periods, source)

    # 直接展开 to_dict() 内容，添加 cached 字段
    result = data.to_dict() if hasattr(data, 'to_dict') else data.__dict__
    result['cached'] = service.was_cache_hit()

    # 直接返回 jsonify，避免 api_response 的二次包装
    return jsonify({
        'success': True,
        'data': result
    })


@financials_v2_bp.route('/api/v2/financials/stats', methods=['GET'])
@handle_api_error
def get_stats():
    """Get service statistics.

    Response:
        {
            "success": true,
            "stats": {
                "total_requests": 100,
                "cache_hits": 70,
                "cache_hit_rate": "70.0%",
                ...
            }
        }
    """
    service = get_enhanced_financial_service()
    stats = service.get_stats()

    return api_response({'stats': stats})


@financials_v2_bp.route('/api/v2/financials/cache/clear', methods=['POST'])
@handle_api_error
def clear_cache():
    """Clear cache.

    Response:
        {
            "success": true,
            "message": "缓存已清空"
        }
    """
    service = get_enhanced_financial_service()
    service.clear_cache()

    return api_response({'message': '缓存已清空'})


@financials_v2_bp.route('/api/v2/financials/stats/reset', methods=['POST'])
@handle_api_error
def reset_stats():
    """Reset statistics (keep cache and circuit breaker state).

    Response:
        {
            "success": true,
            "message": "统计信息已重置"
        }
    """
    service = get_enhanced_financial_service()
    service.reset_stats()

    return api_response({'message': '统计信息已重置'})
