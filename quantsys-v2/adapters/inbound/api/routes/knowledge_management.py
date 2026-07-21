"""
知识管理 API 路由
提供知识查询和应用接口
"""
from flask import Blueprint, jsonify, request
from adapters.inbound.api.decorators import handle_errors
from application.services.knowledge_service import KnowledgeService

knowledge_management_bp = Blueprint('knowledge_management', __name__, url_prefix='/api/knowledge')


@knowledge_management_bp.route('/active', methods=['GET'])
@handle_errors
def get_active_knowledge():
    """
    获取活跃知识

    GET /api/knowledge/active?domain=sector:白酒

    Query Parameters:
        domain: 知识领域（可选）

    Returns:
        {
            "success": true,
            "data": [
                {
                    "id": "know_001",
                    "domain": "sector:白酒",
                    "knowledge_type": "timing_rule",
                    "content": {...},
                    "confidence": 0.85,
                    "validation_count": 20,
                    "success_count": 17
                }
            ]
        }
    """
    domain = request.args.get('domain')

    service = KnowledgeService()
    knowledge_list = service.get_active_knowledge(domain)

    return jsonify({
        'success': True,
        'data': knowledge_list
    })


@knowledge_management_bp.route('/apply', methods=['POST'])
@handle_errors
def apply_knowledge():
    """
    应用知识到当前决策

    POST /api/knowledge/apply

    Request Body:
        {
            "market_phase": "accumulation",
            "sector": "白酒",
            "action": "create_pool"
        }

    Returns:
        {
            "success": true,
            "data": [
                {
                    "knowledge_id": "know_001",
                    "rule": "在accumulation阶段创建白酒池",
                    "confidence": 0.85,
                    "suggestions": [
                        "建议min_roe>=18%",
                        "预期收益8.5%",
                        "持有7天"
                    ]
                }
            ]
        }
    """
    context = request.get_json()

    service = KnowledgeService()
    recommendations = service.apply_knowledge(context)

    return jsonify({
        'success': True,
        'data': recommendations
    })


@knowledge_management_bp.route('/summary', methods=['GET'])
@handle_errors
def get_knowledge_summary():
    """
    获取知识库摘要

    GET /api/knowledge/summary

    Returns:
        {
            "success": true,
            "data": {
                "total_knowledge": 50,
                "by_domain": {...},
                "by_type": {...},
                "high_confidence": 15,
                "medium_confidence": 25,
                "low_confidence": 10
            }
        }
    """
    service = KnowledgeService()
    summary = service.get_knowledge_summary()

    return jsonify({
        'success': True,
        'data': summary
    })


@knowledge_management_bp.route('/<knowledge_id>/validate', methods=['POST'])
@handle_errors
def validate_knowledge(knowledge_id):
    """
    验证知识

    POST /api/knowledge/{knowledge_id}/validate

    Request Body:
        {
            "success": true
        }

    Returns:
        {
            "success": true,
            "data": {...}
        }
    """
    data = request.get_json()
    success = data.get('success', False)

    service = KnowledgeService()
    updated = service.validate_knowledge(knowledge_id, success)

    return jsonify({
        'success': True,
        'data': updated
    })
