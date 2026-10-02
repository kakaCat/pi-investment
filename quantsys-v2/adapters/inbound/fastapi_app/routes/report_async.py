"""报告 API - FastAPI 版（从 Flask health.py 的 /api/report/daily 迁移）

Flask 直接 jsonify(sanitize_for_json(...)) 返回原始 key，不做 camelCase 转换，故同样处理。
"""
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import structlog

from adapters.inbound.fastapi_app.shared import risk_repo, sanitize_for_json, signal_repo

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Report - 报告"])


@router.get('/api/report/daily')
def get_daily_report(date: Optional[str] = Query(None)):
    """获取每日报告"""
    try:
        # 2026-10-02（REQ-261001145152-3982 审查）：**按仓储契约传参，并把"缺参"回成 400**。
        # `get_risk_metrics()` 的契约是「symbol 与 metric_date 至少给一个」，而此处原先
        # **一个都不传**直接调用 → 仓储抛 ValueError("symbol和metric_date至少需要提供一个")，
        # 又被下面的 `except Exception` 兜成 500，于是线上该端点报
        # 「服务器内部错误：symbol和metric_date至少需要提供一个」——把**调用方缺参**
        # 冒充成了服务器故障（tests/migration parity 抓到：GET /api/report/daily 500）。
        risk_summary = risk_repo.get_risk_metrics(metric_date=date) or {}
        signals = signal_repo.get_latest_signals(limit=10)
        return sanitize_for_json({
            'date': date or risk_summary.get('metric_date'),
            'risk_summary': risk_summary,
            'signals': signals,
            'signal_count': len(signals),
        })
    except ValueError as e:
        # 缺参 / 参数非法 → 400（调用方错误）
        return JSONResponse(status_code=400, content={'success': False, 'error': str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': str(e)})
