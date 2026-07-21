"""缠论分析 API 路由"""
from flask import Blueprint, request, jsonify
from application.services.chan_service import ChanService

chan_bp = Blueprint('chan', __name__, url_prefix='/api/chan')


@chan_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    缠论分析接口

    Request Body:
        {
            "symbol": "600519.SH",
            "startDate": "2024-01-01",  // 可选
            "endDate": "2024-12-31",    // 可选
            "buypointTypes": ["1买", "2买"]  // 可选
        }

    Response:
        {
            "symbol": "600519.SH",
            "trend_type": "上涨",
            "bis": [...],
            "segments": [...],
            "zhongshus": [...],
            "buypoints": [...],
            "klines": [...]
        }
    """
    try:
        data = request.json

        if not data or 'symbol' not in data:
            return jsonify({
                "error": "缺少必需参数: symbol"
            }), 400

        symbol = data['symbol']
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        buypoint_types = data.get('buypointTypes')

        service = ChanService()
        result = service.analyze(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            buypoint_types=buypoint_types
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": f"缠论分析失败: {str(e)}"
        }), 500


@chan_bp.route('/buypoints/latest', methods=['GET'])
def get_latest_buypoints():
    """
    获取最近的买卖点信号（跨股票）

    Query Parameters:
        - limit: 返回数量，默认20
        - type: 买卖点类型过滤，如 "1买,2买"

    Response:
        {
            "items": [
                {
                    "symbol": "600519.SH",
                    "type": "1买",
                    "price": 1850.0,
                    "date": "2024-06-15",
                    "confidence": 0.9,
                    "position_ratio": 1.0,
                    "reason": "下跌背驰"
                },
                ...
            ],
            "total": 20
        }
    """
    try:
        # TODO: 实现跨股票的买卖点查询
        # 需要数据库存储历史分析结果，或者实时计算股票池

        return jsonify({
            "items": [],
            "total": 0,
            "message": "功能开发中"
        })

    except Exception as e:
        return jsonify({
            "error": f"查询失败: {str(e)}"
        }), 500


@chan_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "chan-analysis"
    })
