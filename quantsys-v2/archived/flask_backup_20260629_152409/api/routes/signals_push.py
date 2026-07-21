"""
实时信号推送路由

提供信号推送、订阅管理等API
"""
from flask import Blueprint, request, jsonify
from adapters.inbound.api.websocket import get_connection_manager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

signals_bp = Blueprint('signals_push', __name__, url_prefix='/api/signals')


@signals_bp.route('/push', methods=['POST'])
def push_signal():
    """
    推送信号到所有WebSocket客户端

    请求体:
    {
        "symbol": "600519.SH",
        "name": "贵州茅台",
        "action": "buy",  // buy/sell/hold
        "price": 1850.50,
        "strategy": "多因子波段策略v9",
        "reasons": ["RSI超卖", "MACD金叉"],
        "risk_level": "low",  // low/medium/high
        "confidence": 0.85,
        "metadata": {...}  // 可选的额外数据
    }

    返回:
    {
        "success": true,
        "message": "信号已推送",
        "clients_notified": 3
    }
    """
    try:
        data = request.get_json()

        # 参数验证
        required_fields = ['symbol', 'action', 'price', 'strategy']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'缺少必填字段: {field}'
                }), 400

        # 构造信号消息
        signal_message = {
            'type': 'trading_signal',
            'symbol': data['symbol'],
            'name': data.get('name', data['symbol']),
            'action': data['action'],
            'price': data['price'],
            'strategy': data['strategy'],
            'reasons': data.get('reasons', []),
            'risk_level': data.get('risk_level', 'medium'),
            'confidence': data.get('confidence', 0),
            'metadata': data.get('metadata', {}),
            'timestamp': datetime.now().isoformat()
        }

        # 推送到所有连接的客户端
        conn_mgr = get_connection_manager()
        clients_count = conn_mgr.broadcast('signal', signal_message)

        logger.info(f"信号已推送: {signal_message['action']} {signal_message['name']} @ {signal_message['price']}, 通知 {clients_count} 个客户端")

        return jsonify({
            'success': True,
            'message': '信号已推送',
            'clients_notified': clients_count
        })

    except Exception as e:
        logger.error(f"推送信号失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@signals_bp.route('/history', methods=['GET'])
def get_signal_history():
    """
    获取今日信号历史

    查询参数:
    - date: 日期 (YYYY-MM-DD), 默认今日
    - action: 过滤动作 (buy/sell), 可选
    - symbol: 过滤股票代码, 可选

    返回:
    {
        "success": true,
        "signals": [...],
        "total": 10
    }
    """
    try:
        # TODO: 实现信号历史查询（需要在数据库中存储信号）
        # 临时返回空列表
        return jsonify({
            'success': True,
            'signals': [],
            'total': 0,
            'message': '信号历史功能待实现'
        })

    except Exception as e:
        logger.error(f"查询信号历史失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@signals_bp.route('/stats', methods=['GET'])
def get_signal_stats():
    """
    获取信号统计

    返回:
    {
        "success": true,
        "stats": {
            "today_total": 10,
            "today_buy": 6,
            "today_sell": 4,
            "accuracy_rate": 0.65,  // 近期准确率
            "avg_confidence": 0.75
        }
    }
    """
    try:
        # TODO: 实现信号统计（需要从数据库查询）
        return jsonify({
            'success': True,
            'stats': {
                'today_total': 0,
                'today_buy': 0,
                'today_sell': 0,
                'accuracy_rate': 0,
                'avg_confidence': 0
            },
            'message': '信号统计功能待实现'
        })

    except Exception as e:
        logger.error(f"查询信号统计失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@signals_bp.route('/subscribe', methods=['POST'])
def subscribe_symbols():
    """
    订阅特定股票的信号

    请求体:
    {
        "symbols": ["600519.SH", "000858.SZ"],
        "strategies": ["53", "54"]  // 可选
    }

    返回:
    {
        "success": true,
        "message": "订阅成功"
    }
    """
    try:
        data = request.get_json()

        if 'symbols' not in data or not isinstance(data['symbols'], list):
            return jsonify({
                'success': False,
                'error': '缺少 symbols 参数或格式错误'
            }), 400

        # TODO: 实现订阅逻辑（可以存储在 Redis 或内存中）
        # 当有订阅的股票产生信号时，优先推送

        return jsonify({
            'success': True,
            'message': f'已订阅 {len(data["symbols"])} 只股票',
            'note': '订阅功能待完善'
        })

    except Exception as e:
        logger.error(f"订阅失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
