"""
Strategy execution API routes - FastAPI 异步版本
迁移自 Flask adapters/inbound/api/routes/strategy_execution.py
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import structlog
import json

from adapters.outbound.repositories.models.strategy_execution import (
    StrategyExecuteRequest,
    StrategyBatchExecuteRequest,
    StrategyPipelineExecuteRequest
)
from application.services.strategy_execution_service import StrategyExecutionService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/strategies",
    tags=["Strategy Execution - 策略执行"]
)


# ==================== Pydantic 响应模型 ====================

class ApiResponse(BaseModel):
    """标准 API 响应"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


# ==================== 路由端点 ====================

@router.post("/execute", response_model=ApiResponse, summary="单股策略执行")
async def execute_single(request: StrategyExecuteRequest):
    """
    单股策略执行

    对单只股票执行策略，生成交易信号

    Args:
        request: 策略执行请求
            - symbol: 股票代码
            - strategy_name: 策略名称
            - date: 执行日期（可选）
            - persist: 是否持久化（默认 True）
            - return_details: 是否返回详细指标（默认 True）

    Returns:
        {
            "success": true,
            "data": {
                "symbol": "600000",
                "signal_type": "BUY",
                "confidence": 0.85,
                "entry_price": 10.5,
                "stop_loss": 9.8,
                "target_price": 12.0,
                "indicators": {...}
            }
        }

    Example:
        POST /api/strategies/execute
        {
            "symbol": "600000",
            "strategyName": "GridPro-v4.0",
            "date": "2026-06-29",
            "persist": true
        }
    """
    try:
        service = StrategyExecutionService()
        result = service.execute_single(request)

        return {
            "success": True,
            "data": result
        }

    except ValueError as e:
        logger.warning(f"参数错误: {e}")
        return {
            "success": False,
            "error": str(e)
        }

    except Exception as e:
        logger.exception(f"策略执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-execute", summary="批量策略执行（NDJSON 流式）")
async def execute_batch(request: StrategyBatchExecuteRequest):
    """
    批量策略执行（NDJSON 流式响应）

    对多只股票批量执行策略，实时返回进度和结果

    Args:
        request: 批量执行请求
            - symbols: 股票代码列表
            - strategy_name: 策略名称
            - date: 执行日期（可选）
            - persist: 是否持久化（默认 True）
            - min_confidence: 最低置信度过滤（可选）

    Returns:
        NDJSON 流式响应，每行一个 JSON 对象：
        {"symbol": "600000", "progress": 1, "total": 100, "result": {...}}
        {"symbol": "000001", "progress": 2, "total": 100, "result": {...}}
        ...

    Example:
        POST /api/strategies/batch-execute
        {
            "symbols": ["600000", "000001", "600519"],
            "strategyName": "GridPro-v4.0",
            "persist": true,
            "minConfidence": 0.6
        }

    Response (NDJSON):
        {"symbol":"600000","progress":1,"total":3,"status":"success","result":{...}}
        {"symbol":"000001","progress":2,"total":3,"status":"success","result":{...}}
        {"symbol":"600519","progress":3,"total":3,"status":"success","result":{...}}
    """
    try:
        service = StrategyExecutionService()

        # 使用异步生成器进行流式响应
        async def generate():
            """异步生成器：逐个返回执行结果"""
            # 注意：当前 service.execute_batch 是同步迭代器
            # 在生产环境中应该改为真正的异步实现
            for item in service.execute_batch(request):
                yield json.dumps(item, ensure_ascii=False) + '\n'

        return StreamingResponse(
            generate(),
            media_type='application/x-ndjson',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'  # 禁用 nginx 缓冲
            }
        )

    except ValueError as e:
        logger.warning(f"参数错误: {e}")
        # 流式响应中的错误处理
        async def error_stream():
            yield json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False) + '\n'

        return StreamingResponse(
            error_stream(),
            media_type='application/x-ndjson',
            status_code=400
        )

    except Exception as e:
        logger.exception(f"批量执行失败: {e}")
        async def error_stream():
            yield json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False) + '\n'

        return StreamingResponse(
            error_stream(),
            media_type='application/x-ndjson',
            status_code=500
        )


@router.post("/pipeline-execute", response_model=ApiResponse, summary="流水线策略执行")
async def execute_pipeline(request: StrategyPipelineExecuteRequest):
    """
    完整流程执行

    执行完整的策略流水线：信号生成 → 风控检查 → 订单创建

    Args:
        request: 流水线执行请求
            - symbols: 股票代码列表
            - strategy_name: 策略名称
            - create_orders: 是否创建订单（默认 False）
            - risk_check: 是否风控检查（默认 True）

    Returns:
        {
            "success": true,
            "data": {
                "execution_date": "2026-06-29",
                "duration_ms": 1500,
                "signals_generated": 10,
                "signals_approved": 7,
                "signals_rejected": 3,
                "orders_created": 5,
                "rejection_reasons": {
                    "low_confidence": 2,
                    "high_risk": 1
                },
                "orders": [...]
            }
        }

    Example:
        POST /api/strategies/pipeline-execute
        {
            "symbols": ["600000", "000001"],
            "strategyName": "GridPro-v4.0",
            "createOrders": false,
            "riskCheck": true
        }
    """
    try:
        service = StrategyExecutionService()
        result = service.execute_pipeline(request)

        return {
            "success": True,
            "data": result
        }

    except ValueError as e:
        logger.warning(f"参数错误: {e}")
        return {
            "success": False,
            "error": str(e)
        }

    except Exception as e:
        logger.exception(f"流水线执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
