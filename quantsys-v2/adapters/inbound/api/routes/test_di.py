"""
使用依赖注入的测试路由

演示如何在 Flask 路由中使用 @inject 装饰器。
"""
from flask import Blueprint, jsonify, current_app
from infrastructure.di.decorators import inject

test_di_bp = Blueprint('test_di', __name__)


@test_di_bp.route('/api/test/di/health', methods=['GET'])
def test_di_health():
    """
    测试依赖注入系统是否正常工作

    不使用任何服务注入，仅验证容器是否可用。
    """
    try:
        # 检查容器是否存在
        if not hasattr(current_app, 'container'):
            return jsonify({
                'success': False,
                'message': 'DI container not initialized',
                'di_enabled': False
            }), 500

        container = current_app.container

        return jsonify({
            'success': True,
            'message': 'DI container is working',
            'di_enabled': True,
            'container_type': str(type(container).__name__)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'DI health check failed: {str(e)}',
            'di_enabled': False
        }), 500


@test_di_bp.route('/api/test/di/services', methods=['GET'])
def test_di_services():
    """
    测试容器中有哪些服务可用
    """
    try:
        if not hasattr(current_app, 'container'):
            return jsonify({
                'success': False,
                'message': 'DI container not initialized'
            }), 500

        container = current_app.container

        # 列出容器中的所有服务
        available_services = []
        for attr_name in dir(container):
            if not attr_name.startswith('_') and attr_name not in ['config', 'providers']:
                available_services.append(attr_name)

        return jsonify({
            'success': True,
            'available_services': sorted(available_services),
            'service_count': len(available_services)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to list services: {str(e)}'
        }), 500


@test_di_bp.route('/api/test/di/inject-demo', methods=['GET'])
@inject
def test_di_inject_demo(data_service):
    """
    演示自动注入 data_service

    这个路由会自动从容器获取 data_service 并注入。
    """
    try:
        # 验证服务已注入
        if data_service is None:
            return jsonify({
                'success': False,
                'message': 'data_service not injected'
            }), 500

        # 获取一些基本信息
        service_info = {
            'type': str(type(data_service).__name__),
            'has_stock_repo': hasattr(data_service, 'stock'),
            'has_kline_repo': hasattr(data_service, 'kline'),
        }

        return jsonify({
            'success': True,
            'message': 'Service injected successfully',
            'service_info': service_info
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Injection failed: {str(e)}'
        }), 500
