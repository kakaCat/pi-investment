"""
决策追踪 API 路由
提供决策记录、查询和报告接口
"""
from flask import Blueprint, jsonify, request
from adapters.inbound.api.decorators import handle_errors
from application.services.decision_service import DecisionService

decision_tracking_bp = Blueprint('decision_tracking', __name__, url_prefix='/api/decisions')


@decision_tracking_bp.route('/record', methods=['POST'])
@handle_errors
def record_decision():
    """
    记录一个决策

    POST /api/decisions/record

    Request Body:
        {
            "decision_type": "create_pool",
            "context": {
                "market_phase": "accumulation",
                "date": "2026-06-25"
            },
            "parameters": {
                "name": "恐慌抄底池",
                "filter": {...}
            },
            "reasoning": "散户恐慌抛售，机构建仓，创建抄底池",
            "related_entity_type": "pool",
            "related_entity_id": "5"
        }

    Returns:
        {
            "success": true,
            "data": {
                "decision_id": "dec_xxx",
                "decision_type": "create_pool",
                ...
            }
        }
    """
    decision_data = request.get_json()
    
    service = DecisionService()
    decision = service.record_decision(decision_data)
    
    return jsonify({
        'success': True,
        'data': decision
    })


@decision_tracking_bp.route('/<decision_id>', methods=['GET'])
@handle_errors
def get_decision(decision_id):
    """
    获取单个决策

    GET /api/decisions/{decision_id}

    Returns:
        {
            "success": true,
            "data": {...}
        }
    """
    service = DecisionService()
    decision = service.get_decision(decision_id)
    
    if not decision:
        return jsonify({
            'success': False,
            'error': '决策不存在'
        }), 404
    
    return jsonify({
        'success': True,
        'data': decision
    })


@decision_tracking_bp.route('/history', methods=['GET'])
@handle_errors
def get_decision_history():
    """
    查询决策历史

    GET /api/decisions/history?entity_type=pool&entity_id=5&limit=50

    Query Parameters:
        entity_type: 实体类型（可选）
        entity_id: 实体ID（可选）
        decision_type: 决策类型（可选）
        limit: 返回数量（默认50）

    Returns:
        {
            "success": true,
            "data": [...]
        }
    """
    entity_type = request.args.get('entity_type')
    entity_id = request.args.get('entity_id')
    decision_type = request.args.get('decision_type')
    limit = int(request.args.get('limit', 50))
    
    service = DecisionService()
    decisions = service.get_decision_history(
        entity_type=entity_type,
        entity_id=entity_id,
        decision_type=decision_type,
        limit=limit
    )
    
    return jsonify({
        'success': True,
        'data': decisions
    })


@decision_tracking_bp.route('/report', methods=['GET'])
@handle_errors
def get_decision_report():
    """
    生成决策报告

    GET /api/decisions/report?entity_type=pool&entity_id=5

    Query Parameters:
        entity_type: 实体类型（必需）
        entity_id: 实体ID（必需）

    Returns:
        {
            "success": true,
            "data": {
                "total_decisions": 10,
                "by_type": {...},
                "success_rate": 0.75,
                ...
            }
        }
    """
    entity_type = request.args.get('entity_type')
    entity_id = request.args.get('entity_id')
    
    if not entity_type or not entity_id:
        return jsonify({
            'success': False,
            'error': '缺少必需参数: entity_type, entity_id'
        }), 400
    
    service = DecisionService()
    report = service.generate_decision_report(entity_type, entity_id)
    
    return jsonify({
        'success': True,
        'data': report
    })


@decision_tracking_bp.route('/pool-changes/<int:pool_id>', methods=['GET'])
@handle_errors
def get_pool_changes(pool_id):
    """
    查询池子变更历史

    GET /api/decisions/pool-changes/{pool_id}

    Returns:
        {
            "success": true,
            "data": [...]
        }
    """
    service = DecisionService()
    changes = service.get_pool_change_history(pool_id=pool_id)
    
    return jsonify({
        'success': True,
        'data': changes
    })
