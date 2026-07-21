"""
博弈预警 API 路由
提供实时博弈预警查询和订阅接口
"""
from flask import Blueprint, jsonify, request
from adapters.inbound.api.decorators import handle_errors
from application.services.game_alert_service import GameAlertService

game_alert_bp = Blueprint('game_alert', __name__, url_prefix='/api/alerts')


@game_alert_bp.route('/check', methods=['GET'])
@handle_errors
def check_alerts():
    """
    检查当前预警

    GET /api/alerts/check

    Returns:
        {
            "success": true,
            "data": [
                {
                    "alert_id": "alert_xxx",
                    "type": "opportunity",
                    "level": "high",
                    "title": "抄底机会",
                    "message": "...",
                    "action": "建议建仓",
                    "symbols": ["600519.SH"]
                }
            ]
        }
    """
    service = GameAlertService()
    alerts = service.check_alerts()

    return jsonify({
        'success': True,
        'data': alerts
    })


@game_alert_bp.route('/statistics', methods=['GET'])
@handle_errors
def get_statistics():
    """
    获取预警统计

    GET /api/alerts/statistics

    Returns:
        {
            "success": true,
            "data": {
                "total_alerts": 10,
                "by_type": {...},
                "by_level": {...},
                "recent_alerts": [...]
            }
        }
    """
    service = GameAlertService()
    stats = service.get_alert_statistics()

    return jsonify({
        'success': True,
        'data': stats
    })


@game_alert_bp.route('/subscribe', methods=['POST'])
@handle_errors
def subscribe_alerts():
    """
    订阅预警

    POST /api/alerts/subscribe

    Request Body:
        {
            "user_id": "user_001",
            "preferences": {
                "alert_types": ["opportunity", "risk"],
                "min_level": "medium",
                "symbols": ["600519.SH"]
            }
        }

    Returns:
        {
            "success": true,
            "data": {
                "user_id": "user_001",
                "subscribed": true
            }
        }
    """
    data = request.get_json()
    user_id = data.get('user_id')
    preferences = data.get('preferences', {})

    if not user_id:
        return jsonify({
            'success': False,
            'error': '缺少user_id参数'
        }), 400

    service = GameAlertService()
    result = service.subscribe_alerts(user_id, preferences)

    return jsonify({
        'success': True,
        'data': result
    })
