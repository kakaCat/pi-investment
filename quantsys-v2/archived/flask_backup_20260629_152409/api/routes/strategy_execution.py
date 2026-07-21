"""Strategy execution API routes"""
from flask import Blueprint, request, jsonify, Response
import json
from adapters.outbound.repositories.models.strategy_execution import (
    StrategyExecuteRequest,
    StrategyBatchExecuteRequest,
    StrategyPipelineExecuteRequest
)
from application.services.strategy_execution_service import StrategyExecutionService

bp = Blueprint('strategy_execution', __name__, url_prefix='/api/strategies')
service = StrategyExecutionService()


@bp.route('/execute', methods=['POST'])
def execute_single():
    """单股策略执行"""
    try:
        data = request.get_json()
        req = StrategyExecuteRequest(**data)

        result = service.execute_single(req)

        return jsonify({
            'success': True,
            'data': result
        }), 200

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/batch-execute', methods=['POST'])
def execute_batch():
    """批量策略执行（NDJSON 流式）"""
    try:
        data = request.get_json()
        req = StrategyBatchExecuteRequest(**data)

        def generate():
            for item in service.execute_batch(req):
                yield json.dumps(item, ensure_ascii=False) + '\n'

        return Response(
            generate(),
            mimetype='application/x-ndjson',
            status=200
        )

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/pipeline-execute', methods=['POST'])
def execute_pipeline():
    """完整流程执行"""
    try:
        data = request.get_json()
        req = StrategyPipelineExecuteRequest(**data)

        result = service.execute_pipeline(req)

        return jsonify({
            'success': True,
            'data': result
        }), 200

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
