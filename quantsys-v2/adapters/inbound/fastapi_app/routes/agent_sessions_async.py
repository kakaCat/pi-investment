"""Agent Session API - FastAPI 版（parity 迁移自 Flask agent_sessions.py）

事件摄入（agent syncer）+ 查询/诊断（web 展示）。
契约与 Flask 蓝图逐字节对齐：原始 dict 响应（不走 api_response 的 camelCase 转换）、
相同状态码（400 空 events / 404 会话不存在 / 503 LLM 不可用）。
"""
from typing import Optional
from datetime import datetime, date

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse
from werkzeug.http import http_date
import structlog

from adapters.shared.services import session_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Agent Sessions - 会话事件"])


def _flask_serialize(obj):
    """与 Flask jsonify 默认序列化对齐：datetime → RFC 1123 GMT（parity 关键）。

    Flask DefaultJSONProvider 用 werkzeug.http_date 序列化 datetime；
    FastAPI 默认 ISO 格式，不转换则响应体与 Flask 不一致。
    """
    if isinstance(obj, datetime):
        return http_date(obj)
    if isinstance(obj, date):
        return http_date(datetime(obj.year, obj.month, obj.day))
    if isinstance(obj, dict):
        return {k: _flask_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_flask_serialize(v) for v in obj]
    return obj


def _service():
    return session_service


@router.post('/api/sessions/events')
def ingest_events(body: dict = Body(...)):
    """批量摄入 session 事件（幂等）"""
    try:
        events = (body or {}).get('events', [])
        if not isinstance(events, list) or not events:
            return JSONResponse({'success': False, 'error': 'events 必须是非空数组'}, status_code=400)

        result = _service().ingest_events(events)
        return {'success': True, 'data': _flask_serialize(result)}
    except Exception as e:
        logger.error(f"sessions.ingest_events failed: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': f'服务器内部错误: {e}'}, status_code=500)


@router.get('/api/sessions')
def list_sessions(channel: Optional[str] = Query(None), limit: int = Query(50)):
    try:
        sessions = _service().list_sessions(channel=channel, limit=min(limit, 200))
        return {'success': True, 'data': _flask_serialize({'sessions': sessions, 'total': len(sessions)})}
    except Exception as e:
        logger.error(f"sessions.list failed: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': f'服务器内部错误: {e}'}, status_code=500)


# 注意：更具体的路由必须先注册——Starlette 按注册顺序匹配，
# {session_key:path} 会贪婪吞掉 ".../events" 等后缀（Flask/Werkzeug 则自动按具体度排序）。
@router.get('/api/sessions/{session_key:path}/events')
def get_events(session_key: str, event_type: Optional[str] = Query(None),
               limit: int = Query(200), offset: int = Query(0)):
    try:
        events = _service().get_events(session_key, event_type=event_type,
                                       limit=min(limit, 1000), offset=offset)
        return {'success': True, 'data': _flask_serialize({'events': events, 'total': len(events)})}
    except Exception as e:
        logger.error(f"sessions.get_events failed: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': f'服务器内部错误: {e}'}, status_code=500)


@router.get('/api/sessions/{session_key:path}/diagnosis')
def get_diagnosis(session_key: str):
    try:
        diagnosis = _service().get_diagnosis(session_key)
        return {'success': True, 'data': _flask_serialize(diagnosis)}
    except Exception as e:
        logger.error(f"sessions.get_diagnosis failed: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': f'服务器内部错误: {e}'}, status_code=500)


@router.post('/api/sessions/{session_key:path}/ai-diagnosis')
def ai_diagnosis(session_key: str, refresh: str = Query('')):
    """AI 诊断（DeepSeek，缓存）；?refresh=true 强制重新生成"""
    try:
        result = _service().ai_diagnosis(session_key, refresh=refresh.lower() == 'true')
        return {'success': True, 'data': _flask_serialize(result)}
    except RuntimeError as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=503)
    except Exception as e:
        logger.error(f"sessions.ai_diagnosis failed: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': f'服务器内部错误: {e}'}, status_code=500)


@router.get('/api/sessions/{session_key:path}')
def get_session(session_key: str):
    try:
        session = _service().get_session(session_key)
        if not session:
            return JSONResponse({'success': False, 'error': '会话不存在'}, status_code=404)
        return {'success': True, 'data': _flask_serialize(session)}
    except Exception as e:
        logger.error(f"sessions.get failed: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': f'服务器内部错误: {e}'}, status_code=500)

