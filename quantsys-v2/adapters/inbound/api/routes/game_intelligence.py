"""
博弈情报 API 路由
提供对手行为分析、战场评估和操纵检测接口
"""
from flask import Blueprint, jsonify
from adapters.inbound.api.decorators import handle_errors
from application.services.opponent_behavior_service import OpponentBehaviorService
from application.services.battlefield_assessor import BattlefieldAssessor
from application.services.manipulation_detector import ManipulationDetector

game_intelligence_bp = Blueprint('game_intelligence', __name__, url_prefix='/api/game')


@game_intelligence_bp.route('/market/opponent-behavior', methods=['GET'])
@handle_errors
def get_opponent_behavior():
    """
    获取当前市场参与者行为分析

    GET /api/game/market/opponent-behavior

    Returns:
        {
            "success": true,
            "data": {
                "retail": {
                    "behavior": "panic_selling",
                    "net_flow": -5000000000,
                    "emotion_index": 20.0,
                    "common_mistakes": ["割肉在低位"],
                    "description": "散户正在恐慌性抛售，情绪极度悲观"
                },
                "institution": {
                    "behavior": "accumulating",
                    "net_flow": 3500000000,
                    "target_sectors": ["医药", "消费"],
                    "position_change": "increasing",
                    "description": "机构正在建仓，看好后市"
                },
                "hot_money": {
                    "behavior": "inactive",
                    "target_stocks": [],
                    "activity_level": "low"
                },
                "market_phase": "accumulation",
                "risk_appetite": "low",
                "opportunity_map": {
                    "take_from_retail": [{
                        "strategy": "bottom_fishing",
                        "confidence": 0.85,
                        "expected_return": "+5% ~ +10%",
                        "reason": "散户恐慌抛售，机构逢低吸纳"
                    }]
                },
                "timestamp": "2026-06-25T20:00:00"
            }
        }

    Examples:
        >>> curl http://localhost:5001/api/game/market/opponent-behavior
    """
    service = OpponentBehaviorService()
    result = service.analyze_current_behavior()

    return jsonify({
        'success': True,
        'data': result
    })


@game_intelligence_bp.route('/pools/<int:pool_id>/battlefield-assessment', methods=['GET'])
@handle_errors
def get_pool_battlefield_assessment(pool_id):
    """
    评估池子战场优势

    GET /api/game/pools/{pool_id}/battlefield-assessment

    Returns:
        {
            "success": true,
            "data": {
                "pool_id": 1,
                "battlefield_score": 78.5,
                "opponent_strength": {
                    "retail_pressure": "low",
                    "institution_interest": "high",
                    "hot_money_risk": "medium"
                },
                "game_phase": "early_accumulation",
                "advantages": [
                    "散户恐慌抛售，筹码便宜",
                    "机构正在悄悄建仓"
                ],
                "disadvantages": [
                    "成交量偏低，流动性不足"
                ],
                "recommendation": "accumulate",
                "urgency": "high",
                "confidence": 0.85
            }
        }

    Examples:
        >>> curl http://localhost:5001/api/game/pools/1/battlefield-assessment
    """
    assessor = BattlefieldAssessor()
    result = assessor.assess_pool(pool_id)

    return jsonify({
        'success': True,
        'data': result
    })


@game_intelligence_bp.route('/market/manipulation-detect', methods=['GET'])
@handle_errors
def detect_market_manipulation():
    """
    检测市场操纵行为

    GET /api/game/market/manipulation-detect

    Returns:
        {
            "success": true,
            "data": {
                "active_manipulations": [
                    {
                        "symbol": "000XXX.SZ",
                        "manipulation_type": "pump_and_dump",
                        "stage": "distribution",
                        "confidence": 0.92,
                        "signals": ["连续3天涨停", "龙虎榜显示游资活跃"],
                        "fair_value": 8.5,
                        "current_price": 12.3,
                        "deviation": "+45%",
                        "action": "avoid",
                        "risk_level": "extreme"
                    }
                ],
                "post_manipulation_opportunities": [
                    {
                        "symbol": "000YYY.SZ",
                        "stage": "collapse_complete",
                        "collapsed_from": 15.2,
                        "current_price": 8.1,
                        "fair_value": 10.5,
                        "upside": "+30%",
                        "action": "bottom_fishing"
                    }
                ]
            }
        }

    Examples:
        >>> curl http://localhost:5001/api/game/market/manipulation-detect
    """
    detector = ManipulationDetector()
    result = detector.detect_market_manipulation()

    return jsonify({
        'success': True,
        'data': result
    })
