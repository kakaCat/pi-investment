"""
Agent Session API 路由
事件摄入（agent syncer）+ 查询/诊断（web 展示）
"""
from flask import Blueprint, jsonify, request
from adapters.inbound.api.decorators import handle_errors
from application.services.session_service import SessionService

agent_sessions_bp = Blueprint('agent_sessions', __name__, url_prefix='/api/sessions')


@agent_sessions_bp.route('/events', methods=['POST'])
@handle_errors
def ingest_events():
    """批量摄入 session 事件（幂等）"""
    body = request.get_json() or {}
    events = body.get('events', [])
    if not isinstance(events, list) or not events:
        return jsonify({'success': False, 'error': 'events 必须是非空数组'}), 400

    result = SessionService().ingest_events(events)
    return jsonify({'success': True, 'data': result})


@agent_sessions_bp.route('', methods=['GET'])
@handle_errors
def list_sessions():
    channel = request.args.get('channel')
    limit = min(int(request.args.get('limit', 50)), 200)
    sessions = SessionService().list_sessions(channel=channel, limit=limit)
    return jsonify({'success': True, 'data': {'sessions': sessions, 'total': len(sessions)}})


@agent_sessions_bp.route('/<path:session_key>', methods=['GET'])
@handle_errors
def get_session(session_key):
    session = SessionService().get_session(session_key)
    if not session:
        return jsonify({'success': False, 'error': '会话不存在'}), 404
    return jsonify({'success': True, 'data': session})


@agent_sessions_bp.route('/<path:session_key>/events', methods=['GET'])
@handle_errors
def get_events(session_key):
    event_type = request.args.get('event_type')
    limit = min(int(request.args.get('limit', 200)), 1000)
    offset = int(request.args.get('offset', 0))
    events = SessionService().get_events(session_key, event_type=event_type, limit=limit, offset=offset)
    return jsonify({'success': True, 'data': {'events': events, 'total': len(events)}})


@agent_sessions_bp.route('/<path:session_key>/diagnosis', methods=['GET'])
@handle_errors
def get_diagnosis(session_key):
    diagnosis = SessionService().get_diagnosis(session_key)
    return jsonify({'success': True, 'data': diagnosis})


@agent_sessions_bp.route('/<path:session_key>/ai-diagnosis', methods=['POST'])
@handle_errors
def ai_diagnosis(session_key):
    """AI 诊断（DeepSeek，缓存）；?refresh=true 强制重新生成"""
    refresh = request.args.get('refresh', '').lower() == 'true'
    try:
        result = SessionService().ai_diagnosis(session_key, refresh=refresh)
    except RuntimeError as e:
        return jsonify({'success': False, 'error': str(e)}), 503
    return jsonify({'success': True, 'data': result})
