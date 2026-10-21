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
        # 2026-10-20 修复：get_risk_metrics() 无参必抛 ValueError（需 symbol 或
        # metric_date 至少其一）→ 本路由此前必 500。日报语义 = 最近一天整体
        # 风险摘要，改走专用方法。
        risk_summary = risk_repo.get_latest_risk_metrics_overall() or {}
        signals = signal_repo.get_latest_signals(limit=10)
        return sanitize_for_json({
            'date': date or risk_summary.get('metric_date'),
            'risk_summary': risk_summary,
            'signals': signals,
            'signal_count': len(signals),
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': str(e)})
