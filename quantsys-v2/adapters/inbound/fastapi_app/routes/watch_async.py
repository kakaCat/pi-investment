"""WatchEngine 盯盘规则 API - FastAPI 版（与 Flask watch.py 响应契约一致）"""
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.outbound.repositories.watch_rule_repository import (
    WatchTrigger, WatchRuleRepository, WatchTriggerRepository, rule_to_dict, trigger_to_dict,
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
    items = [rule_to_dict(r) for r in rules]
    # 2026-09-11（REQ-733c5e, w-348bf585）：补权威 triggered_count。
    # rule_to_dict 此前不含该字段，下游工具层只好多查一次 /api/watch/triggers 自算（双口径），
    # 且曾因此把「触发 4 次」误显示为 0。统一由后端给出 COUNT(watch_triggers) GROUP BY rule_id。
    counts = None
    try:
        rows = WatchTriggerRepository().session.query(WatchTrigger.rule_id).all()
        counts = {}
        for (rid,) in rows:
            if rid is not None:
                counts[rid] = counts.get(rid, 0) + 1
    except Exception:  # noqa: BLE001 - 统计失败不阻塞规则列表，置 None 让下游勿按 0 理解
        counts = None
    for it in items:
        it['triggered_count'] = counts.get(it.get('id'), 0) if counts is not None else None
    return {'success': True, 'data': {'rules': items}}


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
    if 'action_hint' in data and not isinstance(data['action_hint'], dict):
        return _err('action_hint 必须为对象', 400)
    if 'escalation_policy' in data and not isinstance(data['escalation_policy'], dict):
        return _err('escalation_policy 必须为对象', 400)

    # 变更留痕（RFC 014 §4.2 非对称护栏的落地基础）：返回改动前后值，供调用方写 decision_audit。
    before_rule = rule_repo.get_by_id(rule_id)
    if before_rule is None:
        return _err('规则不存在', 404)
    before = {k: getattr(before_rule, k, None) for k in data.keys()}

    rule = rule_repo.update_fields(rule_id, **data)
    if rule is None:
        return _err('规则不存在', 404)
    changes = [k for k, v in before.items() if str(v) != str(getattr(rule, k, None))]
    return {'success': True, 'data': {'rule': rule_to_dict(rule), 'changed_fields': changes}}


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
    from domain.watch.services.disposition import UNRESOLVED, is_resolved
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
    from domain.watch.services.disposition import UNRESOLVED
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
    """待处置摘要（REQ-f08def）—— agent 摘要式批量唤醒的载荷。

    2026-09-11 重构：构建逻辑下沉到 WatchDigestService，与「引擎内置唤醒门」共用同一份实现。
    原实现与本路由并存会产生两处口径——摘要门改了聚合方式，路由就会不一致。
    """
    from application.services.watch_engine.digest_service import WatchDigestService
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            return _err('since 需为 ISO 时间，如 2026-09-11T13:00:00', 400)
    svc = WatchDigestService(
        trigger_repo=WatchTriggerRepository(),
        rule_repo=WatchRuleRepository(),
        limit=_limit_of(limit, 200),
    )
    return {'success': True, 'data': svc.build_digest(since=since_dt)}


@router.post('/api/watch/rules/batch')
def batch_reconfigure_rules(payload: Dict[str, Any] = Body(default_factory=dict)):
    # 规则重配置批量接口（REQ-f08def P2，RFC 014 v3 §7.4）。
    # 为什么批量：检查点输出=一次规则重配置（买入+挂卖出规则/加仓/清仓收摊），
    # 天然是多条一起动；逐条调既不原子也无法归因到同一触发。
    # 强制审计：reason + source_trigger_id 必填（重配置必须可回溯到触发）。
    actions = payload.get('actions')
    if not isinstance(actions, list) or not actions:
        return _err('actions 必须为非空数组', 400)
    reason = str(payload.get('reason') or '').strip()
    source_trigger_id = payload.get('source_trigger_id')
    if not reason:
        return _err('reason 必填（规则重配置的依据）', 400)
    if source_trigger_id is None:
        return _err('source_trigger_id 必填（重配置必须可回溯到触发）', 400)
    rule_repo = WatchRuleRepository()
    results = []
    for i, act in enumerate(actions):
        op = act.get('op')
        try:
            if op == 'create':
                conds = act.get('conditions') or []
                if not isinstance(conds, list) or not conds:
                    results.append({'index': i, 'success': False, 'error': 'create 需要非空 conditions'})
                    continue
                for c in conds:
                    validate_condition(c)
                rule = rule_repo.create_rule(
                    symbol=act.get('symbol'), conditions=conds,
                    context=act.get('context'), cost_price=act.get('cost_price'),
                    active_window=act.get('active_window'),
                    expires_at=_parse_expires_at(act.get('expires_at')),
                    created_by=act.get('created_by') or 'agent',
                    account=act.get('account'))
                meta = {k: act[k] for k in ('intent', 'lifecycle_stage', 'scope', 'target',
                        'linked_account', 'next_action_hint', 'review_interval_days',
                        'action_hint', 'escalation_policy') if k in act}
                meta['created_from'] = act.get('created_from') or ('trigger:' + str(source_trigger_id))
                if meta:
                    rule_repo.update_fields(rule.id, **meta)
                results.append({'index': i, 'success': True, 'op': 'create', 'rule_id': rule.id})
            elif op == 'update':
                rid = act.get('rule_id')
                if rid is None:
                    results.append({'index': i, 'success': False, 'error': 'update 需要 rule_id'})
                    continue
                if rule_repo.get_by_id(rid) is None:
                    results.append({'index': i, 'success': False, 'error': '规则 ' + str(rid) + ' 不存在'})
                    continue
                fields = {k: act[k] for k in (
                    'enabled', 'conditions', 'context', 'cost_price', 'active_window',
                    'expires_at', 'account', 'notify_mode', 'action_hint', 'escalation_policy',
                    'intent', 'lifecycle_stage', 'scope', 'target', 'linked_account',
                    'next_action_hint', 'review_interval_days', 'review_due_at') if k in act}
                if 'conditions' in fields:
                    for c in fields['conditions']:
                        validate_condition(c)
                if 'expires_at' in fields:
                    fields['expires_at'] = _parse_expires_at(fields['expires_at'])
                rule_repo.update_fields(rid, **fields)
                results.append({'index': i, 'success': True, 'op': 'update', 'rule_id': rid})
            elif op == 'retire':
                rid = act.get('rule_id')
                if rid is None:
                    results.append({'index': i, 'success': False, 'error': 'retire 需要 rule_id'})
                    continue
                old = rule_repo.get_by_id(rid)
                if old is None:
                    results.append({'index': i, 'success': False, 'error': '规则 ' + str(rid) + ' 不存在'})
                    continue
                banner = act.get('retire_note') or ('报废（来源触发 #' + str(source_trigger_id) + '）')
                ctx = (old.context or '') if old else ''
                rule_repo.update_fields(rid, enabled=False,
                    context='[报废 ' + datetime.now().strftime('%Y-%m-%d') + '] ' + banner + chr(10) + ctx)
                results.append({'index': i, 'success': True, 'op': 'retire', 'rule_id': rid})
            else:
                results.append({'index': i, 'success': False, 'error': 'op 必须是 create/update/retire'})
        except Exception as e:
            results.append({'index': i, 'success': False, 'error': str(e)})
    ok = sum(1 for r in results if r.get('success'))
    return {'success': True, 'data': {'results': results, 'ok': ok, 'failed': len(results) - ok,
            'reason': reason, 'source_trigger_id': source_trigger_id}}
