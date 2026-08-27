"""M6-2 周报生成 API

端点：
- GET /api/reports/weekly  生成周报
- GET /api/reports/weekly/latest  获取最新一期周报
"""
from typing import Optional

from fastapi import APIRouter, Query
import structlog

from adapters.inbound.fastapi_app.shared import api_response, error_response, handle_api_error
from application.services.weekly_report_service import WeeklyReportService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Reports - 报告"])


@router.get('/api/reports/weekly')
@handle_api_error
def generate_weekly_report(
    week_start: Optional[str] = Query(None, description="周开始日期 YYYY-MM-DD（默认上周一）"),
    week_end: Optional[str] = Query(None, description="周结束日期 YYYY-MM-DD（默认上周日）"),
    format: str = Query('json', description="输出格式：json/markdown")
):
    """生成周报
    
    汇总指定周的交易表现、信号质量、规则归因
    
    Returns:
        {
            "success": true,
            "data": {
                "period": {"start": "2026-08-18", "end": "2026-08-24", "week_num": 34},
                "summary": {
                    "total_signals": 20,
                    "avg_win_rate_5d": 0.6,
                    "avg_return_5d": 0.05
                },
                "attribution": {...},
                "highlights": [...],
                "recommendations": [...]
            }
        }
    """
    service = WeeklyReportService()
    
    report = service.generate_weekly_report(
        week_start=week_start,
        week_end=week_end
    )
    
    if format == 'markdown':
        markdown = service.format_markdown(report)
        return api_response({
            'format': 'markdown',
            'content': markdown,
            'meta': report['period']
        })
    
    return api_response(report)


@router.get('/api/reports/weekly/latest')
@handle_api_error
def get_latest_weekly_report(
    format: str = Query('json', description="输出格式：json/markdown")
):
    """获取最新一期周报
    
    自动计算上周时间范围并生成周报
    
    Returns:
        与 /api/reports/weekly 相同
    """
    service = WeeklyReportService()
    
    # 默认生成上周周报
    report = service.generate_weekly_report()
    
    if format == 'markdown':
        markdown = service.format_markdown(report)
        return api_response({
            'format': 'markdown',
            'content': markdown,
            'meta': report['period']
        })
    
    return api_response(report)


@router.post('/api/reports/weekly/push')
@handle_api_error
def push_weekly_report_to_feishu(
    week_start: Optional[str] = Query(None, description="周开始日期 YYYY-MM-DD（默认上周一）"),
    week_end: Optional[str] = Query(None, description="周结束日期 YYYY-MM-DD（默认上周日）"),
    feishu_webhook: Optional[str] = Query(None, description="飞书 webhook URL（可选，不提供则从环境变量读取）")
):
    """生成周报并推送到飞书
    
    功能：
    - 生成指定周的周报（默认上周）
    - 推送到飞书群（卡片消息格式）
    
    Returns:
        {
            "success": true,
            "data": {
                "report": {...},
                "markdown": "...",
                "push_result": {
                    "success": true,
                    "message": "飞书推送成功"
                }
            }
        }
    """
    # 如果未提供 webhook，尝试从环境变量读取
    if not feishu_webhook:
        import os
        feishu_webhook = os.getenv('FEISHU_WEEKLY_REPORT_WEBHOOK')
        
        if not feishu_webhook:
            return error_response(
                "未提供飞书 webhook URL，且环境变量 FEISHU_WEEKLY_REPORT_WEBHOOK 未设置",
                status_code=400
            )
    
    service = WeeklyReportService()
    
    result = service.generate_and_push(
        week_start=week_start,
        week_end=week_end,
        feishu_webhook=feishu_webhook
    )
    
    if result['success']:
        return api_response(result)
    else:
        return error_response(
            result['push_result'].get('error', '推送失败'),
            status_code=500
        )
