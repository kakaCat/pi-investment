"""WatchEngine 盯盘规则 API - FastAPI 版（与 Flask watch.py 响应契约一致）"""
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository, rule_to_dict, trigger_to_dict,
)
from application.services.watch_engine.conditions import validate_condition

router = APIRouter(tags=['Watch - 实时盯盘'])

EXPIRES_AT_ERROR = 'expires_at 格式无效（需 ISO 格式，如 2026-07-25T15:00:00）'


def _err(message: str, status: int) -> JSONResponse:
    return JSONResponse({'success': False, 'error': message}, status_code=status)


def _parse_expires_at(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


@router.get('/api/watch/rules')
def list_rules(symbol: Optional[str] = Query(None), enabled: Optional[str] = Query(None),
               account: Optional[str] = Query(None)):
    """account=某账户名时仅返回该账户归属 + 通用观察(account 为空)的规则
    （看板按账户展示盯盘）；不传返回全部。"""
    rule_repo = WatchRuleRepository()
    enabled_value = None if enabled is None else enabled.lower() == 'true'
    rules = rule_repo.list_rules(symbol=symbol, enabled=enabled_value, account=account)
    return {'success': True, 'data': {'rules': [rule_to_dict(r) for r in rules]}}


@router.post('/api/watch/rules')
def create_rule(payload: Dict[str, Any] = Body(default_factory=dict)):
    data = payload or {}
    symbol = (data.get('symbol') or '').strip()
    conditions = data.get('conditions')
    if not symbol:
        return _err('缺少必填参数: symbol', 400)
    if not conditions:
        return _err('缺少必填参数: conditions（非空数组）', 400)
    if not isinstance(conditions, list):
        return _err('conditions 必须为数组', 400)
    try:
        for cond in conditions:
            validate_condition(cond)
    except ValueError as e:
        return _err(str(e), 400)
    try:
        expires_at = _parse_expires_at(data.get('expires_at'))
    except ValueError:
        return _err(EXPIRES_AT_ERROR, 400)
    try:
        rule_repo = WatchRuleRepository()
        rule = rule_repo.create_rule(
            symbol=symbol,
            conditions=conditions,
            context=data.get('context'),
            cost_price=data.get('cost_price'),
            active_window=data.get('active_window'),
            expires_at=expires_at,
            created_by=data.get('created_by', 'agent'),
            account=(data.get('account') or None),
        )
    except Exception as e:
        return _err(f'创建失败: {e}', 500)
    return {'success': True, 'data': {'rule': rule_to_dict(rule)}}


def _update_rule(rule_id: int, payload: Dict[str, Any]):
    rule_repo = WatchRuleRepository()
    data = dict(payload or {})
    if 'conditions' in data:
        if not isinstance(data['conditions'], list):
            return _err('conditions 必须为数组', 400)
        try:
            for cond in data['conditions']:
                validate_condition(cond)
        except ValueError as e:
            return _err(str(e), 400)
    if 'expires_at' in data:
        try:
            data['expires_at'] = _parse_expires_at(data['expires_at'])
        except ValueError:
            return _err(EXPIRES_AT_ERROR, 400)
    rule = rule_repo.update_fields(rule_id, **data)
    if rule is None:
        return _err('规则不存在', 404)
    return {'success': True, 'data': {'rule': rule_to_dict(rule)}}


@router.put('/api/watch/rules/{rule_id}')
def update_rule_put(rule_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    return _update_rule(rule_id, payload)


@router.patch('/api/watch/rules/{rule_id}')
def update_rule_patch(rule_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    return _update_rule(rule_id, payload)


@router.delete('/api/watch/rules/{rule_id}')
def delete_rule(rule_id: int):
    rule_repo = WatchRuleRepository()
    if rule_repo.get_by_id(rule_id) is None:
        return _err('规则不存在', 404)
    rule_repo.delete_by_id(rule_id)
    return {'success': True}


def _limit_of(limit, default: int = 50, cap: int = 200) -> int:
    try:
        value = int(limit) if limit is not None else default
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, cap))


@router.get('/api/watch/triggers')
def list_triggers(symbol: Optional[str] = Query(None),
                  disposition: Optional[str] = Query(None),
                  limit: Optional[str] = Query(None)):
    """触发记录。disposition 可过滤处置状态（待处置/已归档/去重合并/已升级等）。"""
    trigger_repo = WatchTriggerRepository()
    triggers = trigger_repo.list_triggers(
        symbol=symbol, disposition=disposition, limit=_limit_of(limit))
    return {'success': True, 'data': {'triggers': [trigger_to_dict(t) for t in triggers]}}


@router.get('/api/watch/triggers/stats')
def trigger_disposition_stats(date: Optional[str] = Query(None)):
    """处置率统计（REQ-f08def 验收指标数据源）。

    处置率 = 已收敛终态 / (已收敛 + pending + escalated)；
    legacy_unknown（状态机上线前的历史数据）不计入分母，避免美化指标。
    agent_wakeups_estimate = escalated + L2 触发的去重合并数（估算实际唤醒量级）。
    """
    from application.services.watch_engine.disposition import UNRESOLVED, is_resolved
    trigger_repo = WatchTriggerRepository()
    rows = trigger_repo.list_triggers(limit=200)
    day = date or datetime.now().strftime('%Y-%m-%d')
    rows = [t for t in rows if t.triggered_at and t.triggered_at.strftime('%Y-%m-%d') == day]
    buckets = {}
    for t in rows:
        buckets[t.disposition or 'legacy_unknown'] = buckets.get(t.disposition or 'legacy_unknown', 0) + 1
    resolved = sum(v for k, v in buckets.items() if is_resolved(k))
    unresolved = sum(v for k, v in buckets.items() if k in UNRESOLVED)
    denom = resolved + unresolved
    return {'success': True, 'data': {
        'date': day,
        'total': len(rows),
        'by_disposition': buckets,
        'resolved': resolved,
        'unresolved': unresolved,
        'disposition_rate': round(resolved / denom, 4) if denom else None,
        'escalated_to_agent': buckets.get('escalated', 0),
    }}


@router.get('/api/watch/triggers/unresolved')
def list_unresolved_triggers(date: Optional[str] = Query(None), limit: Optional[str] = Query(None)):
    """盘后未处置清单（pending/escalated）——把"触发后没人管"变成可追的待办。"""
    from application.services.watch_engine.disposition import UNRESOLVED
    trigger_repo = WatchTriggerRepository()
    day = date or datetime.now().strftime('%Y-%m-%d')
    rows = trigger_repo.list_triggers(dispositions=UNRESOLVED, limit=_limit_of(limit, 200))
    rows = [t for t in rows if t.triggered_at and t.triggered_at.strftime('%Y-%m-%d') == day]
    by_symbol = {}
    for t in rows:
        key = str(t.symbol).split('.')[0]
        by_symbol.setdefault(key, []).append(t.disposition)
    return {'success': True, 'data': {
        'date': day,
        'count': len(rows),
        'by_symbol': {k: {'count': len(v), 'dispositions': sorted(set(v))} for k, v in by_symbol.items()},
        'triggers': [trigger_to_dict(t) for t in rows],
    }}


@router.patch('/api/watch/triggers/{trigger_id}')
def update_trigger_disposition(trigger_id: int,
                               payload: Dict[str, Any] = Body(default_factory=dict)):
    """处置一条触发：handled（有动作）/ ignored（知悉但不动作，必须带 reason）/ expired。

    这是闭环的最后一环——把 200 条 agent_response=null 的死账变成有终态的账。
    """
    disposition = str(payload.get('disposition') or '').strip()
    allowed = {'handled', 'ignored', 'expired', 'pending'}
    if disposition not in allowed:
        return _err(f'disposition 必须是 {sorted(allowed)} 之一', 400)
    reason = payload.get('reason')
    if disposition == 'ignored' and not str(reason or '').strip():
        return _err('ignored 必须填写 reason（为什么知悉但不动作）', 400)
    trigger_repo = WatchTriggerRepository()
    try:
        trigger = trigger_repo.update_disposition(
            trigger_id, disposition, reason=reason,
            by=str(payload.get('by') or 'agent'))
    except ValueError as e:
        return _err(str(e), 400)
    if trigger is None:
        return _err('触发记录不存在', 404)
    return {'success': True, 'data': {'trigger': trigger_to_dict(trigger)}}

@router.get('/api/watch/triggers/digest')
def trigger_digest(since: Optional[str] = Query(None), limit: Optional[str] = Query(None)):
    """待处置摘要（REQ-f08def Phase 2）—— agent 摘要式批量唤醒的载荷。

    设计要点（RFC 014 §4.5 / §6）：
    1) **gate=false 时调用方必须直接退出，不唤醒 agent** —— 这是"唤醒次数与触发数解耦"的关键：
       队列空则零 LLM；队列非空则不论多少条都只唤醒一次。
    2) 载荷里带 `text`（紧凑文本）：唤醒提示词可直接内嵌，agent 无需再发工具调用取数（省 token）。
    3) 按标的聚合：一次跌穿常产生同标的多条触发，聚合后 agent 按"标的"而不是按"触发"决策。
    """
    from application.services.watch_engine.disposition import UNRESOLVED
    trigger_repo = WatchTriggerRepository()
    rule_repo = WatchRuleRepository()
    rows = trigger_repo.list_triggers(dispositions=UNRESOLVED, limit=_limit_of(limit, 200))
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            rows = [t for t in rows if t.triggered_at and t.triggered_at >= since_dt]
        except ValueError:
            return _err('since 需为 ISO 时间，如 2026-09-11T13:00:00', 400)

    rules = {r.id: r for r in rule_repo.list_rules()}
    groups: Dict[str, Dict[str, Any]] = {}
    for t in rows:
        sym = str(t.symbol).split('.')[0]
        g = groups.setdefault(sym, {'symbol': sym, 'count': 0, 'items': [], 'dispositions': {}})
        g['count'] += 1
        g['dispositions'][t.disposition] = g['dispositions'].get(t.disposition, 0) + 1
        rule = rules.get(t.rule_id)
        cond = t.condition or {}
        params = cond.get('params') or {}
        hint = (getattr(rule, 'action_hint', None) or {}) if rule is not None else {}
        ctx = (getattr(rule, 'context', None) or '') if rule is not None else ''
        g['items'].append({
            'trigger_id': t.id,
            'rule_id': t.rule_id,
            'disposition': t.disposition,
            'trigger_price': float(t.trigger_price) if t.trigger_price is not None else None,
            'triggered_at': t.triggered_at.isoformat() if t.triggered_at else None,
            'condition': f"{cond.get('type')} {params.get('direction', '')} {params.get('price', params.get('pct', ''))}".strip(),
            'trigger_level': hint.get('trigger_level'),
            'suggested_action': hint.get('action_on_trigger'),
            'plan': ctx[:160],
            'reason': (t.disposition_reason or '')[:120],
        })

    # 紧凑文本：唤醒提示词直接内嵌，省一次工具调用
    lines = []
    for sym, g in sorted(groups.items(), key=lambda kv: kv[1]['count'], reverse=True):
        first = min((i['triggered_at'] or '') for i in g['items'])
        disp = '/'.join(f'{k}×{v}' for k, v in sorted(g['dispositions'].items()))
        lines.append(f"[{sym}] {g['count']}条（{disp}）首发 {first[11:19] if first else '-'}")
        for it in g['items'][:4]:
            lvl = it['trigger_level'] or 'L1'
            act = it['suggested_action'] or '-'
            lines.append(f"  - #{it['trigger_id']} 规则{it['rule_id']} {lvl}/{act} "
                         f"{it['condition']} 现价{it['trigger_price']}"
                         + (f" | 预案：{it['plan']}" if it['plan'] else ''))
        if g['count'] > 4:
            lines.append(f"  … 另有 {g['count'] - 4} 条同标的触发")

    by_disposition: Dict[str, int] = {}
    for t in rows:
        by_disposition[t.disposition] = by_disposition.get(t.disposition, 0) + 1

    return {'success': True, 'data': {
        'gate': len(rows) > 0,
        'count': len(rows),
        'by_disposition': by_disposition,
        'group_count': len(groups),
        'groups': list(groups.values()),
        'text': chr(10).join(lines),
    }}
