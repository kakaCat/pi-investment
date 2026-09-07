"""
Pydantic 模型 - 游戏智能模块

定义游戏智能相关的请求和响应模型
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime


# ==================== 对手行为分析 ====================

class OpponentFlowDetail(BaseModel):
    """对手资金流向详情"""
    net_flow: float = Field(..., description="净流入金额（元）")
    buy_volume: float = Field(..., description="买入量")
    sell_volume: float = Field(..., description="卖出量")
    sentiment: str = Field(..., description="情绪状态")


class OpponentBehavior(BaseModel):
    """对手行为分析"""
    retail: OpponentFlowDetail = Field(..., description="散户行为")
    institution: OpponentFlowDetail = Field(..., description="机构行为")
    hot_money: OpponentFlowDetail = Field(..., description="游资行为")
    market_phase: str = Field(..., description="市场阶段")
    opportunity_map: Dict = Field(default_factory=dict, description="机会地图")
    timestamp: datetime = Field(default_factory=datetime.now, description="分析时间")


class OpponentBehaviorResponse(BaseModel):
    """对手行为分析响应"""
    success: bool = True
    data: OpponentBehavior


# ==================== 战场评估 ====================

class BattlefieldAssessment(BaseModel):
    """战场评估"""
    pool_id: int = Field(..., description="股票池ID")
    battlefield_score: float = Field(..., ge=0, le=100, description="战场评分")
    opponent_strength: Dict = Field(..., description="对手实力分布")
    game_phase: str = Field(..., description="博弈阶段")
    advantages: List[str] = Field(default_factory=list, description="优势列表")
    disadvantages: List[str] = Field(default_factory=list, description="劣势列表")
    recommendation: str = Field(..., description="操作建议")
    urgency: str = Field(..., description="紧急程度")
    confidence: float = Field(..., ge=0, le=1, description="置信度")


class BattlefieldAssessmentResponse(BaseModel):
    """战场评估响应"""
    success: bool = True
    data: BattlefieldAssessment


# ==================== 操纵检测 ====================

class ManipulationSignal(BaseModel):
    """操纵信号"""
    symbol: str = Field(..., description="股票代码")
    manipulation_type: str = Field(..., description="操纵类型")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    evidence: List[str] = Field(default_factory=list, description="证据列表")
    risk_level: str = Field(..., description="风险等级")
    recommendation: str = Field(..., description="操作建议")


class ManipulationDetectionResponse(BaseModel):
    """操纵检测响应"""
    success: bool = True
    data: List[ManipulationSignal]
    total: int = Field(..., description="检测到的信号数量")


# ==================== 通用响应 ====================

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误")
