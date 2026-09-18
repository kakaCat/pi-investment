"""盯盘规则自愈 API - FastAPI 版（REQ-c9f899 R6 / t8，2026-09-18）

端点（interfaces.md §1.2）：

  GET  /api/watch/rules/{rule_id}/noise   规则抑噪态 + 触发统计
  POST /api/watch/rules/{rule_id}/repair  执行规则修复/抑噪（{change_kind, params, reason,
                                          operator?, decision_audit_id?}）

响应风格照 routes/watch_todo_async.py：成功 {'success': True, 'data': {...}}；
错误 {'success': False, 'error': <稳定错误码>, 'message': <人读原因>}。

错误码 → HTTP（interfaces §4）：
  watch_rule_change_unauthorized       403  （用户账户规则被 agent 直接改）
  watch_rule_change_invalid_kind       400  （change_kind 非法）
  watch_rule_change_missing_reason     400  （reason 缺失）
  watch_rule_change_rule_not_found     404

operator 缺省为 'agent'（路由是 agent 的自动化入口）；用户本人在前端操作须显式传
operator='user'——**默认值刻意保守**：不传就是 agent 身份，因此改用户账户规则必然 403，
绝不会"因为没传 operator 就被放行"。

⚠️ 本文件**不**注册到 main.py——路由注册统一由 t12 处理（任务边界）。
"""
from typing import Any, Dict

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from adapters.outbound.repositories.watch_rule_change_repository import (
    WatchRuleChangeRepository, change_to_dict,
)
from adapters.outbound.repositories.watch_rule_noise_repository import WatchRuleNoiseRepository
from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
from application.services.watch_engine.noise_self_heal_service import NoiseSelfHealService
from application.services.watch_engine.todo_service import TodoService
from domain.watch.ports import WatchRuleChangeError

router = APIRouter(tags=['Watch - 规则自愈'])

#: 稳定错误码 → HTTP 状态（interfaces.md §4）
_STATUS_BY_CODE = {
    'watch_rule_change_unauthorized': 403,
    'watch_rule_change_invalid_kind': 400,
    'watch_rule_change_missing_reason': 400,
    'watch_rule_change_rule_not_found': 404,
}

#: 缺省 operator（保守：不传 = agent 身份，改用户账户规则必 403）
DEFAULT_OPERATOR = 'agent'


def _err(code: str, message: str = '') -> JSONResponse:
    """错误响应：稳定错误码 + 人读原因（HTTP 状态由错误码映射）"""
    status = _STATUS_BY_CODE.get(code, 500)
    return JSONResponse({'success': False, 'error': code, 'message': message or code},
                        status_code=status)


def _service() -> NoiseSelfHealService:
    """服务工厂（单测/route 测试可替换；无状态，故每次请求新建亦安全）"""
    return NoiseSelfHealService(
        WatchRuleNoiseRepository(), WatchRuleChangeRepository(),
        TodoService(WatchTodoRepository()))


@router.get('/api/watch/rules/{rule_id}/noise')
def get_rule_noise(rule_id: int):
    """规则抑噪态 + 触发统计（trigger_today / trigger_days=连续天数 / self_heal_count ...）"""
    try:
        data = _service().noise_status(rule_id)
    except WatchRuleChangeError as e:
        return _err(e.code, e.message)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({'success': False, 'error': 'internal_error',
                             'message': f'查询规则抑噪态失败: {e}'}, status_code=500)
    return {'success': True, 'data': data}


@router.post('/api/watch/rules/{rule_id}/repair')
def repair_rule(rule_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    """执行规则修复/抑噪：授权校验（403）+ 白名单（400）+ reason 必填（400）→ 落审计"""
    data = payload or {}
    operator = str(data.get('operator') or '').strip() or DEFAULT_OPERATOR
    try:
        result = _service().apply_repair(
            rule_id,
            data.get('change_kind'),
            params=data.get('params'),
            reason=data.get('reason'),
            operator=operator,
            decision_audit_id=data.get('decision_audit_id'),
        )
    except WatchRuleChangeError as e:
        return _err(e.code, e.message)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({'success': False, 'error': 'internal_error',
                             'message': f'规则修复失败: {e}'}, status_code=500)
    return {'success': True,
            'data': {'rule': result['rule'], 'change': change_to_dict(result['change'])}}
