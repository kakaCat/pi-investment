"""agent 完成处置：保存结构化裁决，更新状态并由 V2 发盯盘群。"""
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional

from . import notify_feishu


class AgentCompletionError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


def _payload(data: Dict[str, Any]) -> Dict[str, Any]:
    action = str(data.get('action') or '').strip()
    reason = str(data.get('reason') or '').strip()
    disposition = str(data.get('disposition') or 'handled').strip()
    if not action:
        raise AgentCompletionError('action 必填', 400)
    if not reason:
        raise AgentCompletionError('reason 必填', 400)
    if disposition not in ('handled', 'ignored'):
        raise AgentCompletionError('disposition 只能是 handled/ignored', 400)
    return {
        'action': action,
        'reason': reason,
        'disposition': disposition,
        'account': data.get('account'),
        'qty': data.get('qty'),
    }


def _judgment(trigger, rule):
    detail = trigger.detail or {}
    price = float(trigger.trigger_price) if trigger.trigger_price is not None else None
    return SimpleNamespace(
        intent=detail.get('intent') or getattr(rule, 'intent', None),
        hit_conditions=[{
            'condition': trigger.condition or {},
            'value': price,
            'message': detail.get('message') or '条件触发',
        }],
        quote=SimpleNamespace(symbol=trigger.symbol, price=price),
    )


def complete_agent_trigger(trigger_id: int, data: Dict[str, Any], *,
                           trigger_repo, rule_repo,
                           feishu_sender: Callable[[str, str], bool],
                           now: Optional[datetime] = None) -> Dict[str, Any]:
    decision = _payload(data or {})
    trigger = trigger_repo.get_by_id(trigger_id)
    if trigger is None:
        raise AgentCompletionError('触发记录不存在', 404)
    rule = rule_repo.get_by_id(trigger.rule_id)
    if rule is None:
        raise AgentCompletionError('触发关联规则不存在', 404)

    previous = dict(trigger.agent_response or {})
    if previous.get('notification_delivered'):
        _finalize(trigger_id, trigger.rule_id, previous, trigger_repo, rule_repo)
        return {'trigger_id': trigger_id, 'delivered': True,
                'deduplicated': True, 'agent_response': previous}

    response = {
        **decision,
        'agent': str(data.get('by') or data.get('agent') or 'agent-ts'),
        'completed_at': (now or datetime.now()).isoformat(),
        'notification_entry': notify_feishu.ENTRY_AFTER_AGENT,
        'notification_delivered': False,
    }
    trigger_repo.save_agent_response(trigger_id, response)
    delivery = notify_feishu.send(
        rule, _judgment(trigger, rule), getattr(rule, 'position_state', None),
        entry=notify_feishu.ENTRY_AFTER_AGENT,
        sender=feishu_sender,
        agent_result=decision,
    )
    if not delivery.delivered:
        response['notification_error'] = delivery.error or 'sender_returned_false'
        trigger_repo.save_agent_response(trigger_id, response)
        raise AgentCompletionError(f"agent 裁决已保存，但盯盘群发送失败: {response['notification_error']}", 502)

    response['notification_delivered'] = True
    response.pop('notification_error', None)
    trigger_repo.save_agent_response(trigger_id, response)
    _finalize(trigger_id, trigger.rule_id, response, trigger_repo, rule_repo)
    return {
        'trigger_id': trigger_id,
        'delivered': True,
        'deduplicated': False,
        'entry': delivery.entry,
        'title': delivery.title,
        'body': delivery.body,
        'agent_response': response,
    }


def _finalize(trigger_id: int, rule_id: int, response: Dict[str, Any],
              trigger_repo, rule_repo) -> None:
    trigger_repo.mark_notified(trigger_id, True)
    trigger = trigger_repo.update_disposition(
        trigger_id, response['disposition'], reason=response['reason'],
        by=response.get('agent') or 'agent')
    if trigger is None:
        raise AgentCompletionError('触发记录在状态回写时消失', 404)
    rule = rule_repo.update_fields(rule_id, process_state='processed')
    if rule is None:
        raise AgentCompletionError('规则在状态回写时消失', 404)
