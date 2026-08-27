"""M6-1 归因分析 API

端点：
- GET /api/learning/attribution  规则表现归因分析
"""
from typing import Optional

from fastapi import APIRouter, Query
import structlog

from adapters.inbound.fastapi_app.shared import api_response, error_response, handle_api_error
from application.services.attribution_service import AttributionService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Learning - 学习飞轮"])


@router.get('/api/learning/attribution')
@handle_api_error
def get_attribution_analysis(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    min_samples: int = Query(3, description="最小样本数")
):
    """规则表现归因分析
    
    分析各规则（R-xxx）的引用次数、胜率、平均收益，生成优化建议
    
    Returns:
        {
            "success": true,
            "data": {
                "summary": {
                    "total_trades": 100,
                    "trades_with_rules": 80,
                    "unique_rules": 10,
                    "attribution_rate": 0.8
                },
                "rule_stats": [
                    {
                        "rule_id": "R-001",
                        "count": 20,
                        "win_rate": 0.75,
                        "avg_pnl": 0.08,
                        "recommendation": "strengthen"
                    },
                    ...
                ],
                "recommendations": {
                    "strengthen": ["R-001", "R-005"],
                    "deprecate": ["R-008"]
                }
            }
        }
    """
    service = AttributionService()
    
    result = service.analyze_rule_performance(
        start_date=start_date,
        end_date=end_date,
        min_samples=min_samples
    )
    
    return api_response(result)
