"""
分红数据 API 路由
"""
from flask import Blueprint, request, jsonify
import logging

from application.services.dividend_service import DividendService
from adapters.inbound.api.decorators import handle_errors

logger = logging.getLogger(__name__)

# 创建 Blueprint
dividends_bp = Blueprint('dividends', __name__)

# 初始化服务
service = DividendService()


@dividends_bp.route('/api/stock/<symbol>/dividends', methods=['GET'])
@handle_errors
def get_dividends(symbol):
    """
    获取单股分红数据

    Args:
        symbol: 股票代码（路径参数）
        years: 查询最近N年（查询参数，默认10）

    Returns:
        JSON: 分红数据
    """
    years = request.args.get('years', 10, type=int)

    logger.info(f"GET /api/stock/{symbol}/dividends - years={years}")

    result = service.get_stock_dividends(symbol, years)

    return jsonify(result)


@dividends_bp.route('/api/dividends/screen', methods=['POST'])
@handle_errors
def screen_dividends():
    """
    筛选高股息股票

    Request Body:
        {
            "min_yield": float,
            "min_years": int,
            "min_payout_ratio": float,
            "max_payout_ratio": float,
            "limit": int
        }

    Returns:
        JSON: 筛选结果
    """
    params = request.get_json() or {}

    logger.info(f"POST /api/dividends/screen - params={params}")

    result = service.screen_dividend_stocks(params)

    return jsonify(result)


@dividends_bp.route('/api/dividends/calendar', methods=['GET'])
@handle_errors
def dividend_calendar():
    """
    分红日历

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        event: 事件类型 (ex_dividend/record_date/pay_date)

    Returns:
        JSON: 分红日历
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    event = request.args.get('event', 'ex_dividend')

    # 参数验证
    if not start_date or not end_date:
        logger.warning("Missing required parameters: start_date or end_date")
        return jsonify({
            "success": False,
            "error": "start_date and end_date are required"
        }), 400

    logger.info(f"GET /api/dividends/calendar - {start_date} to {end_date}, event={event}")

    result = service.get_dividend_calendar(start_date, end_date, event)

    return jsonify(result)
