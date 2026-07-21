"""
sectors routes - 行业轮动相关端点
"""
import logging
from flask import Blueprint, jsonify, request

from adapters.inbound.api.shared import (
    api_response,
    handle_api_error,
    convert_keys_to_snake,
    sanitize_for_json,
    sector_rotation_service,
)

logger = logging.getLogger(__name__)

sectors_bp = Blueprint('sectors', __name__)


@sectors_bp.route('/api/sectors/ranking', methods=['GET', 'POST'])
@handle_api_error
def get_sector_ranking():
    """获取行业排名

    GET /api/sectors/ranking?market=A&limit=10&minScore=0.5
    POST /api/sectors/ranking
    {
        "market": "A",
        "limit": 10,
        "minScore": 0.5
    }
    """
    if request.method == 'POST':
        data = request.get_json() or {}
        snake_data = convert_keys_to_snake(data)
    else:
        snake_data = {
            'market': request.args.get('market', 'A'),
            'limit': int(request.args.get('limit', 10)),
            'min_score': float(request.args.get('minScore', 0.0))
        }

    market = snake_data.get('market', 'A')
    limit = min(int(snake_data.get('limit', 10)), 50)
    min_score = float(snake_data.get('min_score', 0.0))

    try:
        sectors = sector_rotation_service.get_sector_ranking(
            market=market,
            limit=limit,
            min_score=min_score
        )

        from datetime import datetime
        result = {
            'success': True,
            'sectors': sanitize_for_json(sectors),
            'total': len(sectors),
            'market': market,
            'timestamp': datetime.now().isoformat()
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"获取行业排名失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
