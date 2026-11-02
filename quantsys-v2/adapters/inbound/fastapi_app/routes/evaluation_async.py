"""投资评价与业绩归因只读 API（A 项第一期）。"""
from typing import Optional

from fastapi import APIRouter, Query

from adapters.inbound.fastapi_app.shared import api_response, handle_api_error
from application.services.investment_evaluation_service import InvestmentEvaluationService

router = APIRouter(tags=["Evaluation - 投资评价"])


@router.get("/api/evaluation/report")
@handle_api_error
def get_evaluation_report(
    account_name: str = Query(..., min_length=1, max_length=50, description="调用方显式指定的模拟账户"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD；缺省取全部可得历史"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD；缺省今天"),
    annual_cost_rate: float = Query(0.02, ge=0, le=1, description="年化资金成本率，默认 2%"),
):
    """返回账户经济账、投资能力账和全局未归属信号账；不写库、不交易。"""
    report = InvestmentEvaluationService().build_report(
        account_name=account_name.strip(),
        start_date=start_date,
        end_date=end_date,
        annual_cost_rate=annual_cost_rate,
    )
    return api_response(report)
