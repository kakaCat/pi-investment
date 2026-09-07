"""事件日历 API - FastAPI 版

特殊日子（宏观发布/央行议息/财报/交割）的日历查询与维护。
数据流：初始化脚本/手动 → quant.event_calendar → 本 API → 每日检查任务/Agent 工具
设计文档：docs/work-logs/2026-09/event-calendar-system-design.md
"""
from datetime import datetime, date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import error_response
from adapters.outbound.repositories.event_calendar_repository import (
    get_event_calendar_repo, event_to_dict,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Events - 事件日历"])

VALID_STATUSES = {'pending', 'notified', 'collected', 'reviewed', 'skipped'}


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


@router.get('/api/events/upcoming')
def get_upcoming_events(days: int = Query(default=2, ge=0, le=30)):
    """查未来 N 天待处理事件（含今天）。每日检查任务核心调用。"""
    try:
        repo = get_event_calendar_repo()
        events = repo.list_upcoming(days_ahead=days)
        return {
            'success': True,
            'days': days,
            'count': len(events),
            'events': [event_to_dict(e) for e in events],
        }
    except Exception as e:
        logger.error("get_upcoming_events failed", error=str(e))
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/events')
def list_events(
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """范围查询事件日历：按日期区间/类型/状态/标的过滤。默认查近30天。"""
    try:
        repo = get_event_calendar_repo()
        start_d = _parse_date(start)
        end_d = _parse_date(end)
        # 默认窗口：近 30 天（不含参数时）
        if start_d is None and end_d is None:
            today = date.today()
            start_d = date.fromordinal(today.toordinal() - 7)
            end_d = date.fromordinal(today.toordinal() + 30)
        events = repo.list_range(
            start=start_d, end=end_d,
            event_type=event_type, status=status, symbol=symbol, limit=limit,
        )
        return {
            'success': True,
            'count': len(events),
            'events': [event_to_dict(e) for e in events],
        }
    except Exception as e:
        logger.error("list_events failed", error=str(e))
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/events/{event_id}')
def get_event(event_id: int):
    """按 ID 查单个事件。"""
    try:
        repo = get_event_calendar_repo()
        obj = repo.get_by_id(event_id)
        if not obj:
            return error_response({'success': False, 'error': f'事件不存在 id={event_id}'}, 404)
        return {'success': True, 'event': event_to_dict(obj)}
    except Exception as e:
        logger.error("get_event failed", error=str(e), event_id=event_id)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/events')
def create_event(payload: Dict[str, Any] = Body(default_factory=dict)):
    """创建事件（手动/初始化脚本）。"""
    event_type = (payload.get('event_type') or '').strip()
    event_date_s = payload.get('event_date')
    title = (payload.get('title') or '').strip()
    if not event_type or not event_date_s or not title:
        return error_response({'success': False, 'error': 'event_type/event_date/title 必填'}, 400)
    event_date = _parse_date(event_date_s)
    if not event_date:
        return error_response({'success': False, 'error': 'event_date 格式应为 YYYY-MM-DD'}, 400)
    try:
        repo = get_event_calendar_repo()
        obj = repo.upsert(
            event_type=event_type,
            event_date=event_date,
            title=title,
            event_time=payload.get('event_time'),
            description=payload.get('description'),
            symbol=payload.get('symbol'),
            market=payload.get('market', 'CN'),
            importance=payload.get('importance', 1),
            status=payload.get('status', 'pending'),
            source=payload.get('source', 'manual'),
            meta=payload.get('meta'),
        )
        if not obj:
            return error_response({'success': False, 'error': '创建失败'}, 500)
        return {'success': True, 'event': event_to_dict(obj)}
    except Exception as e:
        logger.error("create_event failed", error=str(e), title=title)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.patch('/api/events/{event_id}')
def update_event(event_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    """更新事件状态/结果/影响评估。status 变更走状态机。"""
    try:
        repo = get_event_calendar_repo()
        obj = repo.get_by_id(event_id)
        if not obj:
            return error_response({'success': False, 'error': f'事件不存在 id={event_id}'}, 404)

        status = payload.get('status')
        meta_patch = payload.get('meta') if isinstance(payload.get('meta'), dict) else None
        if status is not None:
            if status not in VALID_STATUSES:
                return error_response({'success': False, 'error': f'非法 status：{status}'}, 400)
            obj = repo.mark_status(event_id, status, meta_patch)
        elif meta_patch:
            obj = repo.mark_status(event_id, obj.status, meta_patch)
        else:
            # 其他字段直接更新
            for k in ('title', 'description', 'symbol', 'market', 'importance', 'source', 'event_time'):
                if k in payload and payload[k] is not None and hasattr(obj, k):
                    v = payload[k]
                    if k == 'event_time':
                        from adapters.outbound.repositories.event_calendar_repository import _parse_time
                        v = _parse_time(v)
                    setattr(obj, k, v)
            if 'event_date' in payload and payload['event_date']:
                d = _parse_date(payload['event_date'])
                if d:
                    obj.event_date = d
            obj.updated_at = datetime.now()
            obj = repo.update(obj)

        return {'success': True, 'event': event_to_dict(obj)}
    except Exception as e:
        logger.error("update_event failed", error=str(e), event_id=event_id)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.delete('/api/events/{event_id}')
def delete_event(event_id: int):
    """删除事件。"""
    try:
        repo = get_event_calendar_repo()
        ok = repo.delete_by_id(event_id)
        if not ok:
            return error_response({'success': False, 'error': f'事件不存在 id={event_id}'}, 404)
        return {'success': True, 'deleted': event_id}
    except Exception as e:
        logger.error("delete_event failed", error=str(e), event_id=event_id)
        return error_response({'success': False, 'error': str(e)}, 500)
