"""Agent 任务派发端点（2026-10-20）。

为什么需要：派单要成为**系统能力**而不是某个人的脚本。agent 侧工具
（agent-dh 的 dispatch_task）与调度任务都调这里，信封/报告要求/留痕只实现一份
（qs_notification.application.agent_task_dispatch）。

契约：
  POST /api/agent/dispatch
  body: {title, instruction, event?, target?, requires_report?, urgency?}
  200  {"success": true,  "data": {...dispatch_agent_task 结果...}}
  502  {"success": false, "error": "...", "status": "<wake 状态>"}

提醒：status='ok' 只代表 wake 通道收下，不代表执行（2026-10-20 v4 source 事故）。
验收看目标会话回合 + 结果落库 + 飞书报告卡。
"""
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from qs_notification.application import dispatch_agent_task

router = APIRouter(tags=['Agent - 任务派发'])

VALID_URGENCY = ('normal', 'high', 'critical')


class DispatchRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    instruction: str = Field(..., min_length=1)
    event: str = Field(default='agent_task', max_length=64)
    target: str = Field(default='agent-dh', max_length=32)
    requires_report: bool = True
    urgency: str = 'normal'


@router.post('/api/agent/dispatch')
def dispatch(req: DispatchRequest):
    if req.urgency not in VALID_URGENCY:
        return JSONResponse(
            {'success': False, 'error': f'urgency 必须是 {VALID_URGENCY} 之一'},
            status_code=400,
        )
    try:
        result = dispatch_agent_task(
            title=req.title,
            instruction=req.instruction,
            event=req.event,
            target=req.target,
            requires_report=req.requires_report,
            urgency=req.urgency,
        )
    except Exception as exc:  # noqa: BLE001 - 派发失败要如实回给调用方，不能静默
        return JSONResponse({'success': False, 'error': str(exc)[:300]}, status_code=502)

    if result.get('status') != 'ok':
        # 通道没确认收下（timeout/error/disabled/skipped/not_configured）——如实报失败
        return JSONResponse(
            {'success': False, 'status': result.get('status'),
             'error': f"wake 未确认送达（status={result.get('status')}）", 'data': result},
            status_code=502,
        )
    return {'success': True, 'data': result}
