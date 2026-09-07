"""Strategy execution request and response models"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class StrategyExecuteRequest(BaseModel):
    """单股策略执行请求"""
    symbol: str = Field(..., description="股票代码")
    strategy_name: str = Field(..., alias='strategyName', description="策略名称")
    date: Optional[str] = Field(None, description="执行日期 YYYY-MM-DD")
    persist: bool = Field(True, description="是否持久化")
    return_details: bool = Field(True, description="是否返回详细指标")

    model_config = {"populate_by_name": True}

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        if not v or not v.strip():
            raise ValueError("symbol cannot be empty")
        return v.strip()

    @field_validator('strategy_name')
    @classmethod
    def validate_strategy_name(cls, v):
        if not v or not v.strip():
            raise ValueError("strategy_name cannot be empty")
        return v.strip()


class StrategyBatchExecuteRequest(BaseModel):
    """批量策略执行请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    strategy_name: str = Field(..., alias='strategyName', description="策略名称")
    date: Optional[str] = Field(None, description="执行日期")
    persist: bool = Field(True, description="是否持久化")
    min_confidence: Optional[float] = Field(None, ge=0, le=1, description="最低置信度")

    model_config = {"populate_by_name": True}

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v):
        if not v or len(v) == 0:
            raise ValueError("symbols cannot be empty")
        return [s.strip() for s in v if s.strip()]


class StrategyPipelineExecuteRequest(BaseModel):
    """完整流程执行请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    strategy_name: str = Field(..., alias='strategyName', description="策略名称")
    create_orders: bool = Field(False, description="是否创建订单")
    risk_check: bool = Field(True, description="是否风控检查")

    model_config = {"populate_by_name": True}

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v):
        if not v or len(v) == 0:
            raise ValueError("symbols cannot be empty")
        return [s.strip() for s in v if s.strip()]


class StrategySignalResponse(BaseModel):
    """策略信号响应"""
    signal_id: Optional[str] = None
    symbol: str
    signal_type: str  # BUY/SELL/HOLD
    confidence: float
    entry_price: float
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    position_size: Optional[float] = None
    indicators: Optional[dict] = None


class PipelineExecutionResponse(BaseModel):
    """流程执行响应"""
    execution_date: str
    duration_ms: int
    signals_generated: int
    signals_approved: int
    signals_rejected: int
    orders_created: int
    rejection_reasons: dict
    orders: List[dict]
