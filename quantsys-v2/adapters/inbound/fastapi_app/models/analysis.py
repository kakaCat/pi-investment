"""
分析工具的 Pydantic 模型

包括 Swing Points 分析等
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date


class SwingPointsRequest(BaseModel):
    """ZigZag 波段分析请求"""
    symbol: str = Field(..., description="股票代码，如 600519", example="600519")
    start_date: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD", example="2025-01-01")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD", example="2026-06-01")
    min_change: float = Field(5.0, ge=1.0, le=30.0, description="最小波动幅度百分比", example=5.0)
    lookback_days: Optional[int] = Field(None, ge=30, le=1000, description="回溯天数（可选）")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "600519",
                "start_date": "2025-01-01",
                "end_date": "2026-06-01",
                "min_change": 5.0
            }
        }


class SwingPoint(BaseModel):
    """单个拐点"""
    date: str = Field(..., description="日期")
    price: float = Field(..., description="价格")
    type: str = Field(..., description="拐点类型：high 或 low")
    change_pct: float = Field(..., description="相对上一个拐点的变化百分比")


class Trade(BaseModel):
    """交易配对"""
    buy_date: str
    buy_price: float
    sell_date: str
    sell_price: float
    return_pct: float
    holding_days: int


class SwingPointsSummary(BaseModel):
    """波段分析统计摘要"""
    total_trades: int = Field(..., description="总交易次数")
    win_count: int = Field(..., description="盈利次数")
    loss_count: int = Field(..., description="亏损次数")
    win_rate: float = Field(..., description="胜率百分比")
    total_return: float = Field(..., description="总收益率百分比")
    avg_return: float = Field(..., description="平均收益率百分比")
    max_return: float = Field(..., description="最大单笔收益百分比")
    max_loss: float = Field(..., description="最大单笔亏损百分比")
    avg_holding_days: float = Field(..., description="平均持仓天数")


class SwingPointsResponse(BaseModel):
    """ZigZag 波段分析响应"""
    success: bool = True
    data: Dict = Field(..., description="分析结果数据")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "symbol": "600519",
                    "period": {
                        "start": "2025-06-29",
                        "end": "2026-06-29"
                    },
                    "min_change": 5.0,
                    "kline_count": 241,
                    "swing_points": [
                        {
                            "date": "2025-07-24",
                            "price": 1499.0,
                            "type": "high",
                            "change_pct": 0.0
                        }
                    ],
                    "trades": [],
                    "summary": {
                        "total_trades": 6,
                        "win_count": 6,
                        "loss_count": 0,
                        "win_rate": 100.0,
                        "total_return": 65.49,
                        "avg_return": 8.85,
                        "max_return": 18.61,
                        "max_loss": 5.15,
                        "avg_holding_days": 11.5
                    }
                }
            }
        }
