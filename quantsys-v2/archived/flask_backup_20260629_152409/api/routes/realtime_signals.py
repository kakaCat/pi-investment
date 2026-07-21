"""
实时信号 API 路由
"""

from flask import Blueprint, request, jsonify
from application.services.realtime_signal_service import RealtimeSignalService
from loguru import logger

bp = Blueprint('realtime_signals', __name__, url_prefix='/api/realtime-signals')
service = RealtimeSignalService()


@bp.route('/t1/generate', methods=['POST'])
def generate_t1_signals():
    """
    生成 T+1 信号（今日收盘后生成，明日执行）

    Request:
    {
        "strategy_id": "273",
        "symbols": ["600726", "000001"],
        "execution_date": "2026-06-05"  // 可选，默认次日
    }

    Response:
    {
        "success": true,
        "data": [
            {
                "symbol": "600726",
                "entry_price": 9.71,
                "signal_type": "BUY",
                "execution_date": "2026-06-05",
                "mode": "T+1",
                "generated_at": "2026-06-04T15:30:00"
            }
        ]
    }
    """
    try:
        data = request.get_json()
        strategy_id = data.get('strategy_id')
        symbols = data.get('symbols', [])
        execution_date = data.get('execution_date')

        if not strategy_id or not symbols:
            return jsonify({
                'success': False,
                'error': '缺少必填参数: strategy_id, symbols'
            }), 400

        signals = service.generate_t1_signals(strategy_id, symbols, execution_date)

        return jsonify({
            'success': True,
            'data': signals,
            'count': len(signals)
        })

    except Exception as e:
        logger.error(f"生成 T+1 信号失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/filter/executable', methods=['POST'])
def filter_executable():
    """
    过滤可执行信号（检查价格偏离）

    Request:
    {
        "signals": [...],  // 原始信号列表
        "max_gap_pct": 3.0,  // 最大可接受价差（%）
        "check_realtime": true  // 是否检查实时价格
    }

    Response:
    {
        "success": true,
        "data": {
            "executable": [...],  // 可执行信号
            "rejected": [...]     // 被拒绝的信号
        }
    }
    """
    try:
        data = request.get_json()
        signals = data.get('signals', [])
        max_gap_pct = data.get('max_gap_pct', 3.0)
        check_realtime = data.get('check_realtime', True)

        executable = service.filter_executable_signals(
            signals,
            max_gap_pct=max_gap_pct,
            check_realtime=check_realtime
        )

        rejected = [s for s in signals if not s.get('executable', True)]

        return jsonify({
            'success': True,
            'data': {
                'executable': executable,
                'rejected': rejected
            },
            'summary': {
                'total': len(signals),
                'executable': len(executable),
                'rejected': len(rejected)
            }
        })

    except Exception as e:
        logger.error(f"过滤可执行信号失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/morning-scan', methods=['POST'])
def morning_scan():
    """
    早盘扫描（每日 9:00 调用）

    Request:
    {
        "strategy_ids": ["273", "274"],
        "stock_pool": ["600726", "000001", ...],
        "notify": true  // 是否推送通知
    }

    Response:
    {
        "success": true,
        "data": [...],  // 可执行信号列表
        "summary": {
            "total_scanned": 100,
            "signals_generated": 5,
            "executable": 3
        }
    }
    """
    try:
        data = request.get_json()
        strategy_ids = data.get('strategy_ids', [])
        stock_pool = data.get('stock_pool', [])
        notify = data.get('notify', False)

        if not strategy_ids or not stock_pool:
            return jsonify({
                'success': False,
                'error': '缺少必填参数: strategy_ids, stock_pool'
            }), 400

        # 通知回调（可选）
        notification_callback = None
        if notify:
            def send_notification(signals):
                # TODO: 集成飞书/企业微信推送
                logger.info(f"推送 {len(signals)} 个信号")
            notification_callback = send_notification

        signals = service.schedule_morning_scan(
            strategy_ids,
            stock_pool,
            notification_callback
        )

        executable = [s for s in signals if s.get('executable', True)]

        return jsonify({
            'success': True,
            'data': executable,
            'summary': {
                'total_scanned': len(stock_pool),
                'signals_generated': len(signals),
                'executable': len(executable)
            }
        })

    except Exception as e:
        logger.error(f"早盘扫描失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def init_app(app):
    """注册蓝图"""
    app.register_blueprint(bp)
