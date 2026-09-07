"""
游戏智能 API 路由 (FastAPI 版本)

迁移自 Flask 的 game_intelligence.py
提供对手行为分析、战场评估、操纵检测等功能
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/game",
    tags=["Game Intelligence"]
)


# ==================== Pydantic 模型 ====================

class OpponentBehaviorResponse(BaseModel):
    """对手行为响应"""
    success: bool = True
    data: Dict


class BattlefieldAssessmentResponse(BaseModel):
    """战场评估响应"""
    success: bool = True
    data: Dict


class ManipulationDetectionResponse(BaseModel):
    """操纵检测响应（与 Flask 版结构一致）"""
    success: bool = True
    data: Dict


# ==================== 路由 ====================


@router.get(
    "/market/opponent-behavior",
    response_model=OpponentBehaviorResponse,
    summary="获取市场对手行为分析",
    description="""
    分析当前市场中各类参与者的行为特征：
    - 散户：情绪化、追涨杀跌
    - 机构：信息优势、资金优势
    - 游资：短线操纵、快进快出

    返回实时的资金流向和市场阶段判断。
    """
)
def get_opponent_behavior():
    """
    获取当前市场参与者行为分析
    
    注意：定义为同步 def，FastAPI 会自动放入线程池执行
    
    Returns:
        OpponentBehaviorResponse: 包含散户、机构、游资的行为分析
    """
    try:
        from application.services.opponent_behavior_service import OpponentBehaviorService
        from adapters.outbound.repositories.stock_pool_repository import StockPoolRepository
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        
        # 初始化服务（提供 pool/kline repo 作为数据源）
        pool_repo = StockPoolRepository()
        kline_repo = KlineORMRepository()
        service = OpponentBehaviorService(
            fund_flow_repo=None,  # W2: fund_flow 数据源暂无，服务需降级处理
        )
        result = service.analyze_current_behavior()
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.exception(f"Failed to analyze opponent behavior: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pools/{pool_id}/battlefield-assessment",
    response_model=BattlefieldAssessmentResponse,
    summary="评估股票池战场优势",
    description="""
    评估指定股票池在当前市场环境下的战场优势：
    - 对手实力分布
    - 博弈阶段判断
    - 优劣势分析
    - 操作建议
    """
)
def get_pool_battlefield_assessment(pool_id: int):
    """
    评估池子战场优势
    
    注意：定义为同步 def，FastAPI 会自动放入线程池执行

    Args:
        pool_id: 股票池ID

    Returns:
        BattlefieldAssessmentResponse: 战场评估结果
    """
    try:
        from application.services.battlefield_assessor import BattlefieldAssessor
        from application.services.opponent_behavior_service import OpponentBehaviorService
        from adapters.outbound.repositories.stock_pool_repository import StockPoolRepository
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        from adapters.outbound.repositories.fund_flow_repository import FundFlowORMRepository
        
        # M2-3 修复：注入 fund_flow_repo 以提升数据质量
        pool_repo = StockPoolRepository()
        kline_repo = KlineORMRepository()
        fund_flow_repo = FundFlowORMRepository()
        opponent_service = OpponentBehaviorService()
        
        service = BattlefieldAssessor(
            pool_repo=pool_repo,
            fund_flow_repo=fund_flow_repo,  # ✅ 修复：注入资金流向数据源
            metrics_repo=None,     # W2: metrics 暂无，不保存快照
            opponent_service=opponent_service
        )
        
        result = service.assess_pool(pool_id)
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.exception(f"Failed to assess battlefield for pool {pool_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/market/manipulation-detect",
    response_model=ManipulationDetectionResponse,
    summary="检测市场操纵行为",
    description="""
    检测市场中的操纵行为：
    - 拉高出货
    - 对敲洗盘
    - 虚假申报
    - 尾盘拉升

    识别后可以选择规避风险或底部捡便宜。
    （路径与返回结构对齐 Flask 版：/api/game/market/manipulation-detect）
    """
)
def detect_manipulation():
    """
    检测市场操纵行为

    Returns:
        ManipulationDetectionResponse:
            data.active_manipulations - 活跃的操纵事件（应避开）
            data.post_manipulation_opportunities - 崩盘后的抄底机会
            data.timestamp - 检测时间

    注意：定义为同步 def，FastAPI 会自动放入线程池执行，
    避免同步 Service 阻塞事件循环。
    """
    try:
        from application.services.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()
        result = detector.detect_market_manipulation()

        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.exception(f"Failed to detect manipulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
