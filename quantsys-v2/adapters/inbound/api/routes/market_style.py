"""
市场风格检测 API 路由
"""
from flask import Blueprint, jsonify, request
from adapters.inbound.api.shared import api_response, handle_api_error, get_query_params_snake_case
import logging

logger = logging.getLogger(__name__)

market_style_bp = Blueprint('market_style', __name__)


@market_style_bp.route('/api/market/style', methods=['GET'])
@handle_api_error
def detect_market_style():
    """
    检测市场风格
    
    GET /api/market/style?lookback_days=60
    """
    params = get_query_params_snake_case()
    lookback_days = int(params.get('lookback_days', 60))
    
    try:
        from application.services.market_style_detector import MarketStyleDetector
        
        detector = MarketStyleDetector()
        result = detector.detect_market_style(lookback_days)
        
        return api_response(result)
        
    except Exception as e:
        logger.error(f"市场风格检测失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
