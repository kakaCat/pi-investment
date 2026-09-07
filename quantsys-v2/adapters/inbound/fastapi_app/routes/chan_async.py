"""缠论分析 API - FastAPI 版（从 Flask chan.py 迁移，响应契约保持一致）

Flask 用 request.json + jsonify(result) 直接返回，故同样处理。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
import structlog

from adapters.shared.services import chan_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Chan - 缠论"])


@router.post('/api/chan/analyze')
def analyze(payload: Optional[Dict[str, Any]] = Body(None)):
    """缠论分析接口"""
    try:
        data = payload or {}
        if not data or 'symbol' not in data:
            return JSONResponse(status_code=400, content={"error": "缺少必需参数: symbol"})
        symbol = data['symbol']
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        buypoint_types = data.get('buypointTypes')

        result = chan_service.analyze(
            symbol=symbol, start_date=start_date, end_date=end_date,
            buypoint_types=buypoint_types)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"缠论分析失败: {str(e)}"})


@router.get('/api/chan/buypoints/latest')
def get_latest_buypoints():
    """获取最近的买卖点信号（跨股票）- 功能开发中"""
    try:
        return {"items": [], "total": 0, "message": "功能开发中"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"查询失败: {str(e)}"})


@router.get('/api/chan/health')
def health_check():
    """健康检查"""
    return {"status": "ok", "service": "chan-analysis"}
