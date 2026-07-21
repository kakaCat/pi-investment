"""
学习系统 API 路由
提供学习分析和参数优化接口
"""
from flask import Blueprint, jsonify, request
from adapters.inbound.api.decorators import handle_errors
from application.services.learning_engine import LearningEngine

learning_system_bp = Blueprint('learning_system', __name__, url_prefix='/api/learning')


@learning_system_bp.route('/analyze', methods=['POST'])
@handle_errors
def analyze_and_learn():
    """
    从历史决策中学习

    POST /api/learning/analyze

    Request Body:
        {
            "domain": "sector:白酒"  // 可选
        }

    Returns:
        {
            "success": true,
            "data": {
                "domain": "sector:白酒",
                "sample_size": 20,
                "success_rate": 0.85,
                "lessons_learned": [...],
                "failed_patterns": [...],
                "optimizations": [...]
            }
        }
    """
    data = request.get_json() or {}
    domain = data.get('domain')

    engine = LearningEngine()
    result = engine.learn_from_decisions(domain)

    return jsonify({
        'success': True,
        'data': result
    })


@learning_system_bp.route('/optimize', methods=['POST'])
@handle_errors
def optimize_parameter():
    """
    优化特定参数

    POST /api/learning/optimize

    Request Body:
        {
            "domain": "sector:白酒",
            "parameter": "min_roe"
        }

    Returns:
        {
            "success": true,
            "data": {
                "parameter": "min_roe",
                "current_value": 15,
                "optimal_value": 18,
                "improvement": {...}
            }
        }
    """
    data = request.get_json()
    domain = data.get('domain')
    parameter = data.get('parameter')

    if not domain or not parameter:
        return jsonify({
            'success': False,
            'error': '缺少必需参数: domain, parameter'
        }), 400

    engine = LearningEngine()
    result = engine.optimize_parameters(domain, parameter)

    return jsonify({
        'success': True,
        'data': result
    })


@learning_system_bp.route('/report', methods=['GET'])
@handle_errors
def get_learning_report():
    """
    获取学习报告

    GET /api/learning/report

    Returns:
        {
            "success": true,
            "data": {
                "total_decisions": 100,
                "overall_success_rate": 0.75,
                "by_domain": {...},
                "top_optimizations": [...],
                "knowledge_growth": {...}
            }
        }
    """
    engine = LearningEngine()
    report = engine.generate_learning_report()

    return jsonify({
        'success': True,
        'data': report
    })
