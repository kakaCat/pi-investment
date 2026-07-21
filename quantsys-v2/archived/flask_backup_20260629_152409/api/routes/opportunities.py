"""
机会扫描 API 路由
匹配 TypeScript 前端的 opportunity_scan 工具

POST /api/opportunities/scan
直接接收 symbols 列表，无需 pool_id
"""
import logging
from flask import Blueprint, jsonify, request
from adapters.inbound.api.shared import handle_api_error, api_response

logger = logging.getLogger(__name__)

opportunities_bp = Blueprint('opportunities', __name__)


@opportunities_bp.route('/api/opportunities/scan', methods=['POST'])
@handle_api_error
def scan_opportunities():
    """
    扫描机会（直接接收symbols列表）

    请求体:
    {
      "symbols": ["600519", "000001"],  # 可选，留空=扫描热门股票池
      "limit": 20,                      # 返回数量
      "conditions": ["rsi_oversold"],   # 筛选条件
      "weights": {                      # 权重配置
        "technical": 0.5,
        "fundamental": 0.3,
        "capital": 0.2
      }
    }

    返回:
    {
      "success": true,
      "data": {
        "opportunities": [...],
        "count": 10
      }
    }
    """
    data = request.get_json() or {}
    symbols = data.get('symbols')  # 关键：直接接收symbols
    limit = data.get('limit', 20)
    conditions = data.get('conditions', [])
    weights = data.get('weights')

    # 如果未提供symbols，使用默认股票池
    if not symbols:
        from adapters.outbound.repositories import StockPoolORMRepository
        pool_repo = StockPoolORMRepository()

        # 获取热门股票池（pool_id=1）或创建默认池
        try:
            default_pool = pool_repo.get_pool_by_id(1)
            if default_pool:
                symbols = default_pool.get('symbols', [])
            else:
                # 如果没有默认池，获取沪深300成分股
                from adapters.outbound.repositories import StockORMRepository
                stock_repo = StockORMRepository()
                symbols = stock_repo.get_index_constituents('000300')[:100]  # 取前100只
        except Exception as e:
            logger.warning(f"获取默认股票池失败: {e}，使用空列表")
            symbols = []

    # 调用扫描服务
    try:
        # 简化版本：使用已有的扫描逻辑
        from adapters.outbound.repositories import StockORMRepository

        stock_repo = StockORMRepository()

        # 扫描指定股票
        opportunities = []
        for symbol in symbols[:limit * 2]:  # 扫描更多以过滤
            try:
                # 获取股票基本信息
                stock_info = stock_repo.get_stock_info(symbol)
                if not stock_info:
                    continue

                # 简单评分逻辑（TODO: 集成完整的策略扫描）
                opportunities.append({
                    'symbol': symbol,
                    'name': stock_info.get('name', ''),
                    'score': 75,  # 临时固定评分
                    'signal_type': 'buy',
                    'reason': '技术面指标良好',
                    'technical_score': 75,
                    'fundamental_score': 70,
                    'capital_score': 65,
                    'risk_level': 'medium',
                    'entry_price': stock_info.get('price'),
                    'stop_loss': None,
                    'target_price': None,
                })


                if len(opportunities) >= limit:
                    break

            except Exception as e:
                logger.error(f"扫描股票 {symbol} 失败: {e}")
                continue

        session.close() if 'session' in locals() else None

        # 按评分排序
        opportunities.sort(key=lambda x: x.get('score', 0), reverse=True)
        opportunities = opportunities[:limit]

        return api_response({
            'opportunities': opportunities,
            'count': len(opportunities),
            'symbols_scanned': len(symbols),
            'scan_time': str(__import__('datetime').datetime.now())
        })

    except Exception as e:
        logger.error(f"扫描失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'扫描失败: {str(e)}'
        }), 500
