"""WatchEngine 盯盘规则 API - FastAPI 版（与 Flask watch.py 响应契约一致）"""
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.outbound.repositories.watch_rule_repository import (
    WatchTrigger, WatchRuleRepository, WatchTriggerRepository, rule_to_dict, trigger_to_dict,
)
from qs_watch.application.services.watch_engine.conditions import validate_condition

router = APIRouter(tags=['Watch - 实时盯盘'])

EXPIRES_AT_ERROR = 'expires_at 格式无效（需 ISO 格式，如 2026-07-25T15:00:00）'


def _err(message: str, status: int) -> JSONResponse:
    return JSONResponse({'success': False, 'error': message}, status_code=status)


def _validation_err(message: str, spec: dict = None) -> JSONResponse:
    """校验失败 400：除人读 error 消息外，带**结构化 spec**（合法值枚举）。

    与 409 的 existing_rules 同一理念——agent 被拦后应能**程序化**拿到「该填什么合法值」，
    而不是从自然语言 error 里解析。spec 按校验类型给（账户守卫 → accounts/intents；
    条件校验 → condition_types；action_params → schema 说明）。
    """
    body = {'success': False, 'error': message}
    if spec:
        body['spec'] = spec
    return JSONResponse(body, status_code=400)


def _condition_schema_payload() -> dict:
    """条件入参契约（个股级 + 市场级 + 规则级选项）的**唯一构造点**。

    GET /api/watch/rules/condition-schema 与条件校验 400 的 spec **共用本函数**，
    避免两处漂移。400 响应内联返回完整 schema——agent 被拦后当场拿到该怎么写，
    **无需再调一次 condition-schema 工具**（省一次往返）。"""
    from qs_watch.application.services.watch_engine.conditions import CONDITION_SCHEMA
    from qs_watch.domain.watch.services.market_rule_evaluator import MARKET_CONDITION_SCHEMA
    return {'symbol_level': CONDITION_SCHEMA, 'market_level': MARKET_CONDITION_SCHEMA,
            'rule_level_options': {
                'market_gate': {
                    'desc': '市场环境复合门（流程图 H 节点）：信号成立后查大盘，环境异常只记录不动作',
                    'placement': 'action_params.market_gate',
                    'params': {
                        'index': {'required': False, 'type': '指数代码',
                                  'default': '000001.SH', 'example': '000001.SH'},
                        'max_down_pct': {'required': False, 'type': 'number', 'unit': '%',
                                         'example': -1.5,
                                         'desc': '指数跌幅≤此值即拦截（系统性风险日不接飞刀）'},
                        'max_up_pct': {'required': False, 'type': 'number', 'unit': '%',
                                       'example': 3.0,
                                       'desc': '指数涨幅≥此值即拦截（过热追高保护，可选）'},
                    },
                    'notes': '仅对 pending/escalated 类信号生效；取数失败 fail-open 放行',
                },
            }}


def _parse_expires_at(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


@router.get('/api/watch/exec/stats')
def exec_stats(since: Optional[str] = Query(None), until: Optional[str] = Query(None)):
    """执行闭环统计（FR-7）：三态计数 + 处理时延 p50/p95。

    只读聚合；空数据返回 0（时延为空时返回 null，不伪造 0）。
    """
    try:
        since_dt = _parse_expires_at(since) if since else None
        until_dt = _parse_expires_at(until) if until else None
    except ValueError:
        return _err('time_window_invalid: since/until 需 ISO 时间', 400)
    if since_dt and until_dt and until_dt < since_dt:
        return _err('time_window_invalid: until 早于 since', 400)
    from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
    try:
        data = WatchTodoRepository().exec_stats(since=since_dt, until=until_dt)
    except Exception as e:  # noqa: BLE001 - 聚合失败不返回半份数字
        return _err('watch_exec_stats_unavailable: %s' % e, 503)
    return {'success': True, 'data': data}


@router.get('/api/watch/outcomes/stats')
def outcome_stats(rule_id: Optional[int] = Query(None),
                  horizon_td: Optional[int] = Query(None)):
    """预判命中率（2026-10-20 P3 预判验证闭环）：触发后 5/10/20 交易日走势对照的聚合。

    返回按 (rule_id, horizon_td) 分组的 judged/hits/hit_rate/avg_pct；
    hit IS NULL（震荡不定论/方向不可判）的样本不计入分母。
    """
    from adapters.outbound.repositories.watch_outcome_repository import (
        WatchOutcomeRepository,
    )
    try:
        rows = WatchOutcomeRepository().hit_rate(rule_id=rule_id, horizon_td=horizon_td)
    except Exception as e:
        return _err(f'命中率查询失败: {e}', 500)
    return {'success': True, 'data': {'stats': rows}}


@router.get('/api/watch/rules')
def list_rules(symbol: Optional[str] = Query(None), enabled: Optional[str] = Query(None),
               account: Optional[str] = Query(None), rule_state: Optional[str] = Query(None),
               lint: Optional[str] = Query(None)):
    """account=某账户名时仅返回该账户归属 + 通用观察(account 为空)的规则
    （看板按账户展示盯盘）；不传返回全部。

    rule_state=active/invalid/archived 按生命周期三态过滤（2026-10-22）：
    active=在盯盘 / invalid=失效待裁决 / archived=过滤丢弃。

    lint=missing_guidance（REQ-261016155500-4f2a）：只返回四要素（action_params /
    next_action_hint / intent / action_on_trigger）全空的启用规则，并附缺项明细。"""
    rule_repo = WatchRuleRepository()
    enabled_value = None if enabled is None else enabled.lower() == 'true'
    rules = rule_repo.list_rules(symbol=symbol, enabled=enabled_value, account=account,
                                 rule_state=rule_state)
    if lint == 'missing_guidance':
        from qs_watch.domain.watch.services.rule_lint import guidance_state, is_missing_guidance
        hits = [r for r in rules if is_missing_guidance(r)]
        return {'success': True, 'data': {
            'lint': 'missing_guidance',
            'count': len(hits),
            'rules': [{**rule_to_dict(r), 'missing': guidance_state(r)} for r in hits],
        }}
    if lint:
        return _err('未知 lint 类型: %s（目前支持 missing_guidance）' % lint, 400)
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
        # 400 带结构化规范：合法类型枚举 + **内联完整 condition_schema**——
        # agent 被拦后当场拿到该怎么写，无需再调 GET condition-schema（省一次往返）。
        from qs_watch.application.services.watch_engine.conditions import VALID_TYPES
        return _validation_err(str(e), spec={
            'condition_types': sorted(VALID_TYPES),
            'condition_schema': _condition_schema_payload(),
        })
    try:
        expires_at = _parse_expires_at(data.get('expires_at'))
    except ValueError:
        return _err(EXPIRES_AT_ERROR, 400)
    if 'action_params' in data:
        # REQ-261016155500-4f2a：结构化操作指引的领域校验（与更新路径同一判据）
        from qs_watch.domain.watch.models import validate_action_params
        err = validate_action_params(data.get('action_params'))
        if err:
            return _err(err, 400)
    try:
        rule_repo = WatchRuleRepository()
        # 领域数据校验优先（400 先于 409）：没账户的买卖规则先被账户铁律拦，
        # 而非先报 symbol 冲突——数据非法比业务冲突更基础。guard_new_rule 是纯函数
        # 无副作用，create_rule 内部会再拦一次（幂等），这里的预检只为排定响应顺序。
        from qs_watch.domain.watch.services.rule_guard import KNOWN_ACCOUNTS, guard_new_rule
        try:
            guard_new_rule(intent=data.get('intent'), action_hint=data.get('action_hint'),
                           conditions=conditions,
                           account=(data.get('linked_account') or data.get('account') or None),
                           symbol=symbol)
        except ValueError as e:
            # 400 也带结构化规范：合法账户 / intent 枚举，agent 无需解析自然语言 error
            from qs_watch.domain.watch.services.disposition import HOLD_INTENTS, TRADE_INTENTS
            return _validation_err(str(e), spec={
                'accounts': list(KNOWN_ACCOUNTS),
                'intents': sorted(set(TRADE_INTENTS) | set(HOLD_INTENTS) | {'trend_observe'}),
                'account_required_for': list(TRADE_INTENTS),   # 买卖类必须带账户
                'account_optional_for': sorted(set(HOLD_INTENTS) | {'trend_observe'}),
                'symbol': symbol,
            })
        # 失效阈值预检（400 带规范）：正数校验提前到路由层，与账户守卫同一响应结构。
        # 内部 create_rule 的归一就不会再因阈值抛错（预检已拦），响应统一可读。
        from adapters.outbound.repositories.watch_rule_repository import (
            normalize_invalidation_threshold,
        )
        try:
            normalize_invalidation_threshold(data.get('invalidation_threshold_pct'))
        except (ValueError, TypeError) as e:
            return _validation_err(str(e), spec={
                'invalidation_threshold_pct': '正数（%），agent 按规则设定的失效偏离线；'
                                              '不填则用全局默认 20',
                'symbol': symbol,
            })
        # ── 一股票一规则校验（2026-10-22 用户裁定：创建管线守卫）──
        # agent 给某股票建规则时，先告知已有规则及完整内容（existing_rules），
        # 不静默覆盖。agent 看完仍要新建 → 带 force/replace=true 重提，创建成功后
        # 旧规则自动作废（rule_state=archived）。仅约束 scope='symbol' 的个股规则。
        force = bool(data.get('force') or data.get('replace'))
        new_scope = data.get('scope') or 'symbol'
        existing = []
        if new_scope == 'symbol':
            existing = [r for r in rule_repo.list_rules(symbol=symbol, rule_state='active')
                        if (getattr(r, 'scope', None) or 'symbol') == 'symbol']
        if existing and not force:
            return JSONResponse({
                'success': False,
                'error': 'RULE_EXISTS',
                'message': ('标的 %s 已有 %d 条在盯规则（内容见 existing_rules）。'
                            '如确认替换，请带 force=true 重新提交——旧规则将自动作废'
                            '（rule_state=archived，审计保留可回滚）。'
                            % (symbol, len(existing))),
                'existing_rules': [rule_to_dict(r) for r in existing],
            }, status_code=409)
        rule = rule_repo.create_rule(
            symbol=symbol,
            conditions=conditions,
            context=data.get('context'),
            cost_price=data.get('cost_price'),
            active_window=data.get('active_window'),
            expires_at=expires_at,
            created_by=data.get('created_by', 'agent'),
            account=(data.get('account') or data.get('linked_account') or None),
            # 2026-09-11（w-aebfddcd）：账户归一 + intent/action_hint 透传。
            # 透传是必须的：①账户铁律在**仓储层**（create_rule/update_fields）统一拦，"没有账户
            # 不能进入买卖"；②此前 intent 被静默丢弃，声明 entry 的规则实际落库 NULL。
            linked_account=(data.get('linked_account') or data.get('account') or None),
            intent=data.get('intent'),
            action_hint=data.get('action_hint'),
            action_params=data.get('action_params'),
            # RFC 017（2026-10-21，per-rule-interval 卡）：创建即带持仓状态与规则级频率。
            # 两者都是 additive：不给 → 不动 DB 默认（position_state='none' 由服务端默认
            # 兜住、interval_sec 保持 NULL 跟随全局档），存量创建路径行为不变。
            # 非法值由仓储归一抛 ValueError → 上面的 400 分支（不让坏值落库后变成抽奖）。
            position_state=data.get('position_state'),
            interval_sec=data.get('interval_sec'),
            # 失效阈值（2026-10-22 必填语义）：agent 按规则设定，像止盈价/止损价一样是
            # 具体参数；不给 → 仓储层落全局默认，规则上始终有具体值。
            invalidation_threshold_pct=data.get('invalidation_threshold_pct'),
            # 2026-10-23：盯盘 V2 档位（30/600/1800 秒）。不给 → DB 默认 30（最快档），
            # 随后由开盘任务按距离自动归档；给了就按给的值钉死。
            watch_tier=data.get('watch_tier'),
        )
    except ValueError as e:
        # 领域守卫拒绝（没有账户不能进入买卖 / 策略账户不接受盯盘规则）→ 400 而非 500：
        # 这是**调用方数据问题**，必须给出可读原因，不能被当成服务端故障
        return _err(str(e), 400)
    except Exception as e:
        return _err(f'创建失败: {e}', 500)
    # 替换语义（force 确认后）：新建成功 → 旧规则作废（archived）。
    # 先建新再废旧——新规则一定落库，避免「先删旧再建新」的中间窗口期该股票无规则可盯。
    replaced_ids = []
    for old in existing:
        try:
            rule_repo.update_fields(old.id, rule_state='archived')
            replaced_ids.append(old.id)
        except Exception:  # noqa: BLE001 - 单个作废失败不阻断（新规则已生效）
            pass
    out = {'rule': rule_to_dict(rule)}
    if replaced_ids:
        out['replaced_rule_ids'] = replaced_ids
    return {'success': True, 'data': out}


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
    if 'action_params' in data:
        # REQ-261016155500-4f2a：结构化操作指引的领域校验（纯函数，错误文案直接可读）
        from qs_watch.domain.watch.models import validate_action_params
        err = validate_action_params(data.get('action_params'))
        if err:
            return _err(err, 400)
    if 'escalation_policy' in data and not isinstance(data['escalation_policy'], dict):
        return _err('escalation_policy 必须为对象', 400)
    # 2026-10-22 三分支：rule_state 裁决回写（agent 对失效规则的改/删裁决）
    if 'rule_state' in data:
        if data['rule_state'] not in ('active', 'invalid', 'archived'):
            return _err('rule_state 必须为 active/invalid/archived 之一', 400)
        # 裁决「回 active」（改阈值续用）→ 自动清除失效标记，失效状态解除
        if data['rule_state'] == 'active':
            data.setdefault('invalid_reason', None)
            data.setdefault('invalid_at', None)
        # 注意：裁决「退役归 archived」不改 enabled——rule_state='archived' 本身
        # 已让规则退出一切判定（list_by_state 按 rule_state 过滤），避免触发
        # 宪法级止损的停用守卫（guard_disable_rule）。
    # 失效阈值更新（2026-10-22）：给了必须为正数；不给不动（保持现值）
    if 'invalidation_threshold_pct' in data and data['invalidation_threshold_pct'] is not None:
        try:
            data['invalidation_threshold_pct'] = float(data['invalidation_threshold_pct'])
            if data['invalidation_threshold_pct'] <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return _err('invalidation_threshold_pct 必须为正数（%）', 400)

    # 变更留痕（RFC 014 §4.2 非对称护栏的落地基础）：返回改动前后值，供调用方写 decision_audit。
    before_rule = rule_repo.get_by_id(rule_id)
    if before_rule is None:
        return _err('规则不存在', 404)
    before = {k: getattr(before_rule, k, None) for k in data.keys()}

    try:
        rule = rule_repo.update_fields(rule_id, **data)
    except ValueError as e:
        # 领域守卫拒绝（把观察规则改成买卖却不给账户 / 清空买卖规则的账户）→ 400
        return _err(str(e), 400)
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


@router.post('/api/watch/rules/backfill-guidance')
def backfill_guidance():
    """缺指引补全闭环（REQ-261016155500-4f2a）：对 lint 命中的启用规则幂等建 P2
    「补全预案」待办（同规则已有未收敛补全待办则跳过），交处置 agent 回填
    action_params / intent / observation_criterion。幂等可重复调用。"""
    try:
        from qs_watch.application.services.watch_engine.guidance_backfill_service import (
            GuidanceBackfillService,
        )
        result = GuidanceBackfillService.create_default().ensure_todos()
    except Exception as e:  # noqa: BLE001
        return _err(f'补全待办创建失败: {e}', 500)
    return {'success': True, 'data': result}


@router.delete('/api/watch/rules/{rule_id}')
def delete_rule(rule_id: int):
    rule_repo = WatchRuleRepository()
    if rule_repo.get_by_id(rule_id) is None:
        return _err('规则不存在', 404)
    # 级联归档（2026-10-19）：规则删除后其未收敛待办成孤儿，触发链已断——
    # 先埋掉再删规则，否则 SLA 巡检会继续晋升/超时打扰用户（静默，不发回执）。
    from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
    WatchTodoRepository().close_open_by_rule(
        rule_id, close_reason='盯盘规则已删除，此提醒单随之自动归档，无需处理')
    rule_repo.delete_by_id(rule_id)
    return {'success': True}


def _limit_of(limit, default: int = 50, cap: int = 200) -> int:
    try:
        value = int(limit) if limit is not None else default
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, cap))



# ── 条件入参契约 + 回测（2026-10-20 框架适配）────────────────────────────

@router.get('/api/watch/rules/condition-schema')
def get_condition_schema():
    """条件入参契约：全部条件类型的参数说明/单位/示例 + market_gate 规格。
    唯一构造点是 _condition_schema_payload()（与条件校验 400 的 spec 共用，不漂移）。"""
    return _condition_schema_payload()


@router.post('/api/watch/conditions/simulate')
def simulate_condition(body: Dict[str, Any] = Body(default_factory=dict)):
    """把条件 DSL 在日线历史上逐日重放：回答「这条规则过去 N 天会触发几次」。"""
    from qs_watch.application.services.watch_engine.condition_simulator import (
        simulate_conditions,
    )
    symbol = str(body.get('symbol') or '').strip()
    conditions = body.get('conditions')
    if not symbol or not isinstance(conditions, list) or not conditions:
        return _err('symbol 与 conditions（数组）必填', 400)
    try:
        result = simulate_conditions(
            symbol, conditions,
            days=int(body.get('days') or 30),
            cost_price=body.get('cost_price'))
        return {'success': True, 'data': result}
    except ValueError as e:
        return _err('条件非法：%s' % e, 400)
    except RuntimeError as e:
        return _err(str(e), 502)


# ── 池级盯盘绑定（2026-10-20 选池↔盯盘接线）────────────────────────────

def _pool_watch_service():
    from adapters.outbound.repositories.watch_pool_binding_repository import (
        PoolMemberSource, WatchPoolBindingRepository,
    )
    from qs_watch.application.services.watch_engine.pool_watch_service import PoolWatchService
    return PoolWatchService(
        WatchPoolBindingRepository(), PoolMemberSource(),
        __import__('adapters.outbound.repositories.watch_rule_repository',
                   fromlist=['WatchRuleRepository']).WatchRuleRepository())


@router.get('/api/watch/pools')
def list_pools_for_binding():
    """可绑定的池清单（stock_pools 只读摘要）。"""
    return {'pools': _pool_watch_service()._pool_source.list_pools()}


@router.get('/api/watch/pool-bindings')
def list_pool_bindings(enabled: bool = True):
    return {'bindings': _pool_watch_service().list_bindings(enabled=enabled)}


@router.post('/api/watch/pool-bindings')
def create_pool_binding(body: dict):
    svc = _pool_watch_service()
    pool_id = int(body.get('pool_id') or 0)
    if pool_id <= 0:
        return {'ok': False, 'error': 'pool_id 必填'}, 400
    pools = {pp['id']: pp for pp in svc._pool_source.list_pools()}
    if pool_id not in pools:
        return {'ok': False, 'error': '池 #%s 不存在' % pool_id}, 404
    fields = {
        'pool_id': pool_id,
        'pool_name': pools[pool_id].get('name') or '',
        'conditions_template': body.get('conditions_template'),
        'use_member_points': bool(body.get('use_member_points', True)),
        'member_points_mode': body.get('member_points_mode') or 'breakout',
        'intent': body.get('intent') or 'trend_observe',
        'account': body.get('account'),
        'cooldown_sec': body.get('cooldown_sec'),
        'max_members': int(body.get('max_members') or 100),
    }
    try:
        binding = svc.create_binding(**fields)
        summary = svc.reconcile_binding(binding)
        return {'ok': True, 'binding': binding, 'first_sync': summary}
    except ValueError as e:
        return {'ok': False, 'error': str(e)}, 400
    except RuntimeError as e:
        return {'ok': False, 'error': str(e)}, 413


@router.post('/api/watch/pool-bindings/{binding_id}/sync')
def sync_pool_binding(binding_id: int):
    svc = _pool_watch_service()
    binding = svc.get_binding(binding_id)
    if binding is None:
        return {'ok': False, 'error': '绑定不存在'}, 404
    try:
        return {'ok': True, 'summary': svc.reconcile_binding(binding)}
    except RuntimeError as e:
        return {'ok': False, 'error': str(e)}, 413


@router.delete('/api/watch/pool-bindings/{binding_id}')
def delete_pool_binding(binding_id: int, retire_rules: bool = True):
    """删绑定；retire_rules=true 时顺带收摊其生成的规则（默认收）。"""
    svc = _pool_watch_service()
    binding = svc.get_binding(binding_id)
    if binding is None:
        return {'ok': False, 'error': '绑定不存在'}, 404
    svc.update_binding(binding_id, enabled=False)
    retired = 0
    if retire_rules:
        from qs_watch.application.services.watch_engine.pool_watch_service import (
            binding_created_from,
        )
        cf = binding_created_from(binding_id)
        for r in svc._rule_repo.list_rules(enabled=True):
            if str(getattr(r, 'created_from', '') or '') == cf:
                svc._rule_repo.update_fields(
                    r.id, enabled=False,
                    next_action_hint='池绑定 #%d 已删除，自动收摊' % binding_id)
                retired += 1
    return {'ok': True, 'binding_disabled': binding_id, 'rules_retired': retired}


# ── 消息监控（2026-10-20 流程图 M/N）────────────────────────────────────

def _news_service():
    from adapters.outbound.repositories.watch_news_repository import (
        NewsAlertRepository, WatchNewsSource,
    )
    from adapters.outbound.repositories.simulation_position_repository import (
        SimulationPositionRepository,
    )
    from qs_watch.application.services.watch_engine.news_watch_service import (
        NewsWatchService,
    )
    from qs_watch.application.services.watch_engine.watch_channels import (
        send_watch_receipt,
    )
    return NewsWatchService(
        news_source=WatchNewsSource(), alert_repo=NewsAlertRepository(),
        position_repo=SimulationPositionRepository(),
        accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
        sender=lambda p: send_watch_receipt(p))


@router.post('/api/watch/news-scan')
def news_scan_manual():
    """手动触发一轮消息监控（平时由 sidecar 自动跑，15 分钟节流）。"""
    svc = _news_service()
    svc._last_scan_at = None        # 手动触发跳过节流
    return svc.scan()


@router.get('/api/watch/news-alerts')
def news_alerts(limit: int = 50):
    from adapters.outbound.repositories.watch_news_repository import NewsAlertRepository
    return {'alerts': NewsAlertRepository().recent(limit=limit)}


# ── 一屏简报（2026-10-20 框架适配）：agent「现在该看什么」────────────────

@router.get('/api/watch/brief')
def watch_brief(symbol: str, account: Optional[str] = Query(None)):
    """单标的盯盘简报：行情+成本+规则距离+未决触发+近48h消息命中，一张卡。"""
    from adapters.outbound.repositories.simulation_position_repository import (
        SimulationPositionRepository,
    )
    from adapters.outbound.repositories.watch_news_repository import NewsAlertRepository
    from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
    bare = symbol.split('.')[0]
    out = {'symbol': bare, 'quote': None, 'position': None, 'rules': [],
           'open_triggers': [], 'recent_news_hits': [], 'suppressed': False}

    try:
        from qs_market_data.adapters.outbound.datasources.manager import (
            get_data_provider_manager,
        )
        q = get_data_provider_manager().get_quote(bare)
        if q.get('success') and q.get('data'):
            d = q['data']
            price = getattr(d, 'price', None) or (d.get('price') if isinstance(d, dict) else None)
            prev = getattr(d, 'prev_close', None) or (d.get('prev_close') if isinstance(d, dict) else None)
            out['quote'] = {'price': float(price) if price else None,
                            'prev_close': float(prev) if prev else None}
    except Exception as e:  # noqa: BLE001
        out['quote_error'] = str(e)[:120]

    try:
        pos_repo = SimulationPositionRepository()
        for acct in ('agent_virtual', 'agent_brain', 'user_main_simulation'):
            try:
                pos = pos_repo.get_position(acct, bare)
            except Exception:  # noqa: BLE001
                continue
            if pos is not None and float(getattr(pos, 'market_value', 0) or 0) > 0:
                cost = float(getattr(pos, 'avg_cost', 0) or 0)
                px = out['quote'] and out['quote'].get('price')
                out['position'] = {
                    'account': acct,
                    'shares': float(getattr(pos, 'shares_total', 0) or 0),
                    'avg_cost': cost,
                    'pnl_pct': round((px - cost) / cost * 100, 2) if (px and cost) else None,
                }
                break
    except Exception as e:  # noqa: BLE001
        out['position_error'] = str(e)[:120]

    try:
        rules = WatchRuleRepository().list_rules(symbol=bare, enabled=True)
        px = out['quote'] and out['quote'].get('price')
        for r in rules:
            conds = []
            for c in (r.conditions or []):
                pp = (c.get('params') or {})
                t = c.get('type')
                if t == 'price_break' and pp.get('price') and px:
                    dist = (float(pp['price']) - px) / px * 100
                    conds.append({'type': t, 'threshold': float(pp['price']),
                                  'direction': pp.get('direction'),
                                  'distance_pct': round(dist, 2)})
                else:
                    conds.append({'type': t, 'params': {k: pp.get(k) for k in
                                                        ('price', 'pct', 'days', 'direction')}})
            out['rules'].append({
                'id': r.id, 'intent': r.intent,
                'level': (r.action_hint or {}).get('trigger_level'),
                'suppressed': bool(getattr(r, 'noise_state', None) == 'suppressed'),
                'conditions': conds,
                'next_action_hint': getattr(r, 'next_action_hint', None),
            })
        out['suppressed'] = any(r['suppressed'] for r in out['rules'])
    except Exception as e:  # noqa: BLE001
        out['rules_error'] = str(e)[:120]

    try:
        from qs_watch.domain.watch.services.disposition import UNRESOLVED
        from adapters.outbound.repositories.watch_rule_repository import WatchTriggerRepository
        rows = [t for t in WatchTriggerRepository().list_triggers(symbol=bare, limit=50)
                if t.disposition in UNRESOLVED][:5]
        out['open_triggers'] = [
            {'id': t.id, 'disposition': t.disposition, 'triggered_at': t.triggered_at.isoformat(),
             'reason': (t.disposition_reason or '')[:100]} for t in rows]
    except Exception as e:  # noqa: BLE001
        out['triggers_error'] = str(e)[:120]

    try:
        hits = [a for a in NewsAlertRepository().recent(limit=200)
                if a['symbol'] == bare][:3]
        out['recent_news_hits'] = hits
    except Exception as e:  # noqa: BLE001
        out['news_error'] = str(e)[:120]

    return {'success': True, 'data': out}

@router.get('/api/watch/triggers')
def list_triggers(symbol: Optional[str] = Query(None),
                  disposition: Optional[str] = Query(None),
                  limit: Optional[str] = Query(None),
                  since: Optional[str] = Query(None)):
    """触发记录。disposition 过滤；since（ISO 时间）= 增量轮询（agent 信号感知通道）。"""
    trigger_repo = WatchTriggerRepository()
    triggers = trigger_repo.list_triggers(
        symbol=symbol, disposition=disposition, limit=_limit_of(limit))
    if since:
        from datetime import datetime as _dt
        try:
            since_ts = _dt.fromisoformat(since.replace('Z', '+00:00'))
            if since_ts.tzinfo is not None:
                since_ts = since_ts.astimezone().replace(tzinfo=None)
            triggers = [t for t in triggers
                        if t.triggered_at is not None and t.triggered_at >= since_ts]
        except (ValueError, TypeError):
            return {'success': False, 'error': 'since 非法（要求 ISO 时间）'}
    return {'success': True, 'data': {'triggers': [trigger_to_dict(t) for t in triggers]}}


@router.get('/api/watch/triggers/stats')
def trigger_disposition_stats(date: Optional[str] = Query(None)):
    """处置率统计（REQ-f08def 验收指标数据源）。

    处置率 = 已收敛终态 / (已收敛 + pending + escalated)；
    legacy_unknown（状态机上线前的历史数据）不计入分母，避免美化指标。
    agent_wakeups_estimate = escalated + L2 触发的去重合并数（估算实际唤醒量级）。
    """
    from qs_watch.domain.watch.services.disposition import UNRESOLVED, is_resolved
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
    from qs_watch.domain.watch.services.disposition import UNRESOLVED
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
    from qs_watch.domain.watch.services.disposition import UNRESOLVED
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
            # REQ-f08def P1：意图与阶段——agent 拿到触发就知道该回答什么问题
            'intent': getattr(rule, 'intent', None),
            'lifecycle_stage': getattr(rule, 'lifecycle_stage', None),
            'next_action_hint': getattr(rule, 'next_action_hint', None),
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
                meta['created_from'] = (act.get('created_from') or ('trigger:' + str(source_trigger_id)))[:80]
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
