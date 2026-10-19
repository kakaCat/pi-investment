"""规则自愈应用服务（REQ-c9f899 R6 / t8，2026-09-18）

用户原话（需求 §1 v3 意见）：「触发多次了，是不是需要 agent 来调整一下规则，延长时间或者
修改规则」——反复触发的**处置对象是规则本身**，不是"再叫一次 agent 去交易"（I2）。

两条能力：

1) scan(now) —— 抑噪（自动、零 token、即时）
   按 rule 聚合 watch_triggers 的**按日触发次数**（不依赖内存，R10），超阈值则顺序执行：
     ① 置抑噪态（watch_rules.noise_state='suppressed' + suppress_until）
     ② 用 TodoService 建「修规则」待办（level=P1，action_kind='rule_change'，owner 按账户）
     ③ 写一条 watch_rule_changes（changed_by='system', change_kind='suppress'）
   顺序固定、缺一不可：先抑噪（立刻不再逐条推送）再派活（有人真正去修）。

2) apply_repair(...) —— 修复（授权 + 审计 + 清抑噪）
   修复动作枚举 REPAIR_ACTIONS（cooldown/threshold/split/merge/retire，见 noise_policy）+
   抑噪态两动作 suppress/unsuppress。**授权按账户**（R3/I5）：
     · agent 自有账户（route_owner → autonomy=autonomous）→ agent 可自主变更并留痕；
     · 用户账户 / 未登记账户（owner_kind='user' 或 autonomy=remind_only）→ **只有
       operator='user' 才放行**，agent 直接改抛 WatchRuleChangeUnauthorized（路由层 403）；
     · 策略账户（out_of_scope）→ agent 不得变更（用户本人可）——盯盘不介入策略账户（R3）。

**幂等判据（同一规则同一日不重复建「修规则」待办）**：用 quant.watch_rule_changes 判——
change_repo.exists_since(rule_id, 'suppress', 今日 00:00) 为真即跳过。为什么不用「待办存在性」：
待办表可能因其它路径（迁移回填、人工建单）已有同规则的 rule_change 待办，那不能证明
"今天已经自愈过"；而 suppress 审计行只由本服务的 scan 写入，是自愈是否已发生的**唯一凭据**
（append-only，不会被后续修复改写）。代价：跨日若上一条修规则待办仍未收敛会再建一条——
这是 R6「反复触发每日都要有人管」的刻意行为，跨日合并属后续任务。

范围边界（诚实标注，避免越权）：
  · 修复动作分两族（2026-10-19，E1 振荡修复）：
    - **配置类**（cooldown/threshold/retire）必须**真正落地 watch_rules 配置变更**
      （经 IWatchRuleNoiseRepository.apply_config_repair）才算修复——落地成功才允许
      mark_repaired 清抑噪；落地失败抛错、抑噪态保留。此前"只写审计不改配置"的假修复
      会造成 suppress→repair→unsuppress→suppress 振荡；
    - split/merge 无法机械落地（涉及多规则结构变更）→ **拒绝**（WatchRuleChangeInvalidKind），
      请走规则 CRUD 手工处理；
    - **抑噪态类**（suppress/unsuppress）只改投递级别，照旧。
  · 抑噪只改投递级别，不改判定结果（architecture §5「不做的事」）：真信号仍进 L3，聚合里可见。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from qs_watch.domain.watch.ports import (
    IWatchRuleChangeRepository,
    IWatchRuleNoiseRepository,
    WatchRuleChangeInvalidKind,
    WatchRuleChangeMissingReason,
    WatchRuleChangeRuleNotFound,
    WatchRuleChangeUnauthorized,
)
from qs_watch.domain.watch.services import noise_policy
from qs_watch.domain.watch.services.level_resolver import P1, sla_seconds_for
from qs_watch.domain.watch.services.owner_router import OWNER_USER, route_owner
from qs_watch.domain.watch.services.rule_guard import effective_account

logger = structlog.get_logger(__name__)

#: 「修规则」待办的级别（R6：交 agent / 你拍板 → P1 待决策）
REPAIR_TODO_LEVEL = P1

#: operator 取该值表示"用户本人确认"；其余一律视为 agent 代改（授权最保守）
USER_OPERATOR = 'user'

#: 可机械落地的配置类修复动作（真正改 watch_rules 配置才算修复，E1）
CONFIG_REPAIR_ACTIONS = ('cooldown', 'threshold', 'retire')

#: 无法机械落地的配置类动作（涉及多规则结构变更）→ apply_repair 响亮拒绝
NON_MECHANICAL_REPAIR_ACTIONS = ('split', 'merge')

#: 抑噪态类动作（只改投递级别，不改配置）
NOISE_STATE_ACTIONS = ('suppress', 'unsuppress')


def _iso(value) -> Optional[str]:
    """datetime → ISO 字符串（None 透传）"""
    return value.isoformat() if value is not None else None


def _jsonable_rule(rule: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """规则最小投影 → 可 JSON 序列化的 dict（datetime → ISO）

    ⚠️ 不做日期转换会让 JSONResponse 在序列化时 500（同 receipt_to_dict 的教训）。
    """
    if rule is None:
        return None
    out = dict(rule)
    for key in ('suppress_until', 'last_repair_at'):
        out[key] = _iso(out.get(key))
    return out


class NoiseSelfHealService:
    """反复触发 → 抑噪 + 修规则待办 + 授权修复（无状态，仓储/待办服务由构造注入）"""

    def __init__(self, rule_repo: IWatchRuleNoiseRepository,
                 change_repo: IWatchRuleChangeRepository,
                 todo_service: Any,
                 policy: Any = None, *,
                 window_days: int = noise_policy.DEFAULT_WINDOW_DAYS,
                 suppress_hours: float = noise_policy.DEFAULT_SUPPRESS_HOURS,
                 max_triggers_per_day: int = noise_policy.DEFAULT_MAX_TRIGGERS_PER_DAY,
                 min_consecutive_days: int = noise_policy.DEFAULT_MIN_CONSECUTIVE_DAYS,
                 min_avg_per_day: float = noise_policy.DEFAULT_MIN_AVG_PER_DAY):
        self._rule_repo = rule_repo
        self._change_repo = change_repo
        self._todo_service = todo_service
        #: WatchDeliveryPolicy（可注入；缺省由 route_owner 用默认策略）——不缓存账户映射内容
        self._policy = policy
        self._window_days = int(window_days)
        self._suppress_hours = float(suppress_hours)
        self._max_triggers_per_day = int(max_triggers_per_day)
        self._min_consecutive_days = int(min_consecutive_days)
        self._min_avg_per_day = float(min_avg_per_day)

    # ── 抑噪扫描 ────────────────────────────────────────────

    def scan(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """扫描全部规则的按日触发，超阈值者抑噪并派「修规则」待办。

        返回 {scanned, suppressed:[...], skipped:[...]}——用于定时任务日志与测试断言；
        任何仓储/待办失败都向上抛（不得把"自愈没跑"伪装成"没有噪音规则"）。
        """
        current = now or datetime.now()
        today = current.date()
        since = current - timedelta(days=self._window_days)

        daily = self._rule_repo.daily_counts(since=since, until=current)
        suppressed: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        for rule_id in sorted(daily):
            counts = daily.get(rule_id) or {}
            summary = noise_policy.summarize(counts, today)
            if not self._is_noisy(summary):
                continue

            rule = self._rule_repo.get_rule(rule_id)
            if rule is None:
                # 悬空触发（规则已删）：不自愈（没有可抑噪的规则），登记供排查
                skipped.append({'rule_id': rule_id, 'reason': 'rule_missing'})
                continue

            account = effective_account(rule)
            route = route_owner(account, self._policy)
            if route.out_of_scope:
                # 策略账户规则属数据缺陷：盯盘不介入，不自愈（R3）
                skipped.append({'rule_id': rule_id, 'account': account,
                                'reason': 'out_of_scope'})
                continue

            if self._already_healed_today(rule_id, current):
                # 日幂等：同一规则同一日只建一条「修规则」待办、只写一条抑噪审计
                skipped.append({'rule_id': rule_id, 'account': account,
                                'reason': 'already_healed_today'})
                continue

            try:
                open_todo = self._open_repair_todo(rule_id)
            except Exception as e:  # noqa: BLE001 - fail-closed：查询失败本轮跳过该规则自愈
                # E4：此前查询失败返回 None 照样新建待办（与"宁可不新建"的注释相反）。
                # 幂等判据不可信时**什么都不做**——不抑噪、不建待办、不写审计，
                # 记 error 日志等下一轮（否则可能在已有待办的情况下重复建单）。
                logger.error('待办幂等查询失败（fail-closed：本轮跳过该规则自愈）',
                             rule_id=rule_id, error=str(e))
                skipped.append({'rule_id': rule_id, 'account': account,
                                'reason': 'todo_query_failed'})
                continue
            if open_todo is not None:
                # 待办幂等（REQ-261016155500-4f2a；实测 10-16 规则 #250/#255：P2 补全
                # 待办未关闭，自愈又建 P1 修规则待办 = 同规则双待办）：抑噪照做（状态机
                # 动作，跨日仍超阈值要持续压住），但**不新建待办**——收口交给现有那条
                # （补全/修复任一级别均可），抑噪审计里关联现有待办 id 以便溯源。
                skipped.append({'rule_id': rule_id, 'account': account,
                                'reason': 'open_repair_todo_exists'})

            reason = self._noise_reason(summary)
            until = noise_policy.suppress_until(current, hours=self._suppress_hours)
            self._rule_repo.mark_suppressed(rule_id, until, now=current)
            todo = (None if open_todo is not None
                    else self._create_repair_todo(rule, account, rule_id, current, reason))
            if todo is None:
                todo = open_todo
            change = self._change_repo.record(
                rule_id, changed_by='system', change_kind='suppress',
                before={'noise_state': rule.get('noise_state'),
                        'suppress_until': _iso(rule.get('suppress_until'))},
                after={'noise_state': 'suppressed', 'suppress_until': _iso(until),
                       'suppress_hours': self._suppress_hours},
                reason=reason, todo_id=getattr(todo, 'id', None),
            )
            suppressed.append({
                'rule_id': rule_id, 'account': account, 'symbol': rule.get('symbol'),
                'trigger_today': summary['trigger_today'],
                'consecutive_days': summary['consecutive_days'],
                'avg_per_day': summary['avg_per_day'],
                'todo_id': getattr(todo, 'id', None),
                'change_id': getattr(change, 'id', None),
                'suppress_until': _iso(until),
                'reason': reason,
            })
            logger.info('规则已抑噪并派修规则待办', rule_id=rule_id, account=account,
                        todo_id=getattr(todo, 'id', None), reason=reason)

        return {'scanned': len(daily), 'suppressed': suppressed, 'skipped': skipped}

    # ── 修复 ────────────────────────────────────────────────

    def apply_repair(self, rule_id: int, change_kind: str, params: Any = None,
                     reason: Optional[str] = None, operator: Optional[str] = None,
                     decision_audit_id: Optional[str] = None,
                     now: Optional[datetime] = None) -> Dict[str, Any]:
        """执行一次规则修复（授权 → 校验 → 配置落地 → 审计 → 清抑噪态）。

        校验顺序（先校输入再查库，与 TodoService.close 同纪律）：
          reason 必填 → change_kind 白名单 → 规则存在 → 授权 →
          （配置类动作：算落地内容并**真正落库**）→ 落审计 → 改抑噪态。
        配置类修复（cooldown/threshold/retire）落地成功才允许 mark_repaired 清抑噪；
        split/merge 无法机械落地 → WatchRuleChangeInvalidKind（E1：拒绝假修复）。
        返回 {'rule': 最新投影, 'change': 审计行}；授权失败抛 WatchRuleChangeUnauthorized（403）。
        """
        reason_value = str(reason or '').strip()
        if not reason_value:
            raise WatchRuleChangeMissingReason(
                'reason 必填：规则变更必须写明理由（为什么改，R6/R-020）')

        kind = str(change_kind or '').strip().lower()
        if not noise_policy.is_change_kind(kind):
            raise WatchRuleChangeInvalidKind(
                f'change_kind={change_kind!r} 不在 {list(noise_policy.CHANGE_KINDS)} 内')

        current = now or datetime.now()
        rule = self._rule_repo.get_rule(rule_id)
        if rule is None:
            raise WatchRuleChangeRuleNotFound(f'规则 {rule_id} 不存在')

        account = effective_account(rule)
        operator_value = str(operator or '').strip() or 'agent'
        route = self._authorize(account, operator_value)

        if noise_policy.is_repair_action(kind):
            # 配置类修复：先算落地内容并**真正落库**（split/merge 与缺参在写任何东西之前
            # 拒绝；落库失败向上抛、抑噪态保留）——绝不允许"只写审计不改配置"的假修复
            # 去清抑噪，那正是 suppress→repair→unsuppress→suppress 振荡的根因（E1）。
            config_after = self._config_repair_after(rule, kind, params)
            self._rule_repo.apply_config_repair(rule_id, kind, config_after)

        change = self._change_repo.record(
            rule_id,
            changed_by=(USER_OPERATOR if operator_value == USER_OPERATOR else 'agent'),
            change_kind=kind,
            before={'noise_state': rule.get('noise_state'),
                    'suppress_until': _iso(rule.get('suppress_until'))},
            after=params if params is not None else {},
            reason=reason_value, decision_audit_id=decision_audit_id,
        )

        if kind == 'suppress':
            until = noise_policy.suppress_until(current, hours=self._suppress_hours)
            self._rule_repo.mark_suppressed(rule_id, until, now=current)
        else:
            # 含 unsuppress 与全部 REPAIR_ACTIONS：修复完成 → 清抑噪态、恢复原级别（R6）
            self._rule_repo.mark_repaired(rule_id, now=current)

        fresh = self._rule_repo.get_rule(rule_id)
        logger.info('规则变更已留痕', rule_id=rule_id, change_kind=kind,
                    changed_by=change.changed_by, operator=operator_value,
                    owner_kind=route.owner_kind, autonomy=route.autonomy)
        return {'rule': _jsonable_rule(fresh), 'change': change}

    # ── 读（GET /api/watch/rules/{id}/noise）────────────────

    def noise_status(self, rule_id: int, now: Optional[datetime] = None) -> Dict[str, Any]:
        """规则抑噪态 + 触发统计（纯读）。

        trigger_days = **截至今日的连续触发天数**（阈值判据本身的口径）；窗口内有触发的
        天数另以 active_days 给出，逐日明细以 trigger_days_detail 给出——三者含义不同，
        不合并（防"看着像连续其实是断档"的误读）。
        """
        current = now or datetime.now()
        rule = self._rule_repo.get_rule(rule_id)
        if rule is None:
            raise WatchRuleChangeRuleNotFound(f'规则 {rule_id} 不存在')
        daily = self._rule_repo.daily_counts(since=current - timedelta(days=self._window_days),
                                             until=current)
        summary = noise_policy.summarize(daily.get(rule_id) or {}, current.date())
        projection = _jsonable_rule(rule) or {}
        return {
            'rule_id': rule_id,
            'symbol': projection.get('symbol'),
            'account': effective_account(rule),
            'noise_state': projection.get('noise_state'),
            'suppress_until': projection.get('suppress_until'),
            'is_suppressed': noise_policy.is_suppressed(
                projection.get('noise_state'), rule.get('suppress_until'), current),
            'self_heal_count': int(projection.get('self_heal_count') or 0),
            'last_repair_at': projection.get('last_repair_at'),
            'trigger_today': summary['trigger_today'],
            'trigger_days': summary['consecutive_days'],
            'avg_per_day': summary['avg_per_day'],
            'active_days': summary['active_days'],
            'trigger_days_detail': summary['trigger_days'],
            'thresholds': {
                'max_triggers_per_day': self._max_triggers_per_day,
                'min_consecutive_days': self._min_consecutive_days,
                'min_avg_per_day': self._min_avg_per_day,
                'window_days': self._window_days,
            },
            'should_suppress': self._is_noisy(summary),
        }

    # ── 内部 ────────────────────────────────────────────────

    def _config_repair_after(self, rule: Dict[str, Any], kind: str,
                             params: Any) -> Dict[str, Any]:
        """配置类修复的落地内容（按规则现状 + params 计算；无法机械落地 → 响亮拒绝）。

        返回 dict 即 apply_config_repair 的 after（列白名单 enabled/conditions 见适配器）：
          · cooldown  → 每条条件写 cooldown_sec（params.cooldown_sec 必填）
          · threshold → 每条条件的 params.price 改写（params.price 必填；direction 可同改）
          · retire    → enabled=False（宪法级止损规则除外：2026-10-20 裁定不许自愈退役）
          · split/merge → WatchRuleChangeInvalidKind（多规则结构变更，走规则 CRUD 手工处理）
        """
        payload = params if isinstance(params, dict) else {}
        if kind in NON_MECHANICAL_REPAIR_ACTIONS:
            raise WatchRuleChangeInvalidKind(
                f'{kind} 无法机械落地（涉及多规则结构变更）：请通过规则 CRUD 手工处理；'
                f'本服务拒绝"只写审计不改配置"的假修复（会引发抑噪振荡，E1）')
        if kind == 'retire':
            # 宪法级守卫（2026-10-20 用户裁定，与 rule_guard.guard_disable_rule 同源）：
            # apply_config_repair 走裸 SQL 绕过 update_fields 的停用卡口，故在此拦截——
            # 止损规则不许被自愈流程退役（止损反复触发是"保护网在工作"，不是噪音）。
            from qs_watch.domain.watch.services.disposition import CONSTITUTIONAL_INTENTS
            if (rule.get('intent') or '') in CONSTITUTIONAL_INTENTS:
                raise WatchRuleChangeInvalidKind(
                    f'规则 {rule.get("id")} 是宪法级止损规则（intent={rule.get("intent")}），'
                    f'不允许自愈退役——止损反复触发是保护网在工作，不是噪音；'
                    f'如阈值失真请走人工修复并随附理由（ops_notes/context）')
            return {'enabled': False}

        conditions = rule.get('conditions') or []
        if (not isinstance(conditions, list) or not conditions
                or not all(isinstance(c, dict) for c in conditions)):
            raise WatchRuleChangeInvalidKind(
                f'规则 {rule.get("id")} 的 conditions 为空或形状非法，{kind} 无落地对象：'
                f'拒绝假修复（E1）')

        if kind == 'cooldown':
            sec = payload.get('cooldown_sec')
            if sec is None:
                raise WatchRuleChangeInvalidKind(
                    'cooldown 修复必须给出 params.cooldown_sec（新冷却秒数）——'
                    '没有目标值的"修复"是假修复（E1）')
            return {'conditions': [dict(cond, cooldown_sec=int(sec)) for cond in conditions]}

        # threshold
        price = payload.get('price')
        if price is None:
            raise WatchRuleChangeInvalidKind(
                'threshold 修复必须给出 params.price（新阈值）——'
                '没有目标值的"修复"是假修复（E1）')
        out = []
        for cond in conditions:
            new_cond = dict(cond)
            new_params = dict(new_cond.get('params') or {})
            new_params['price'] = float(price)
            if payload.get('direction') in ('above', 'below'):
                new_params['direction'] = payload['direction']
            new_cond['params'] = new_params
            out.append(new_cond)
        return {'conditions': out}

    def _is_noisy(self, summary: Dict[str, Any]) -> bool:
        return noise_policy.should_suppress(
            summary['trigger_today'], summary['consecutive_days'], summary['avg_per_day'],
            max_triggers_per_day=self._max_triggers_per_day,
            min_consecutive_days=self._min_consecutive_days,
            min_avg_per_day=self._min_avg_per_day)

    def _noise_reason(self, summary: Dict[str, Any]) -> str:
        return noise_policy.noise_reason(
            summary['trigger_today'], summary['consecutive_days'], summary['avg_per_day'],
            max_triggers_per_day=self._max_triggers_per_day,
            min_consecutive_days=self._min_consecutive_days,
            min_avg_per_day=self._min_avg_per_day)

    def _already_healed_today(self, rule_id: int, now: datetime) -> bool:
        """日幂等判据：今日 00:00 起是否已有该规则的 suppress 审计行"""
        day_start = datetime(now.year, now.month, now.day)
        return bool(self._change_repo.exists_since(rule_id, 'suppress', day_start))

    def _open_repair_todo(self, rule_id: int):
        """该规则未收敛的 rule_change 待办（补全/修复任一，跨级别）；无则 None。

        待办幂等判据（与 GuidanceBackfillService 同一 list_open_by_rule 口径）：
        有则不新建——同规则双待办会让 agent 重复收口（实测 10-16 规则 #250/#255）。

        失败语义（E4，2026-10-19）：查询失败**向上抛**，由 scan 捕获后 fail-closed
        跳过该规则本轮自愈——查询失败时"按无待办处理"会重复建单（与注释相反）。
        """
        rows = self._todo_service.list_open_by_rule(
            rule_id, action_kind='rule_change')
        return rows[0] if rows else None

    def _create_repair_todo(self, rule: Dict[str, Any], account: Optional[str],
                            rule_id: int, now: datetime, reason: str) -> Any:
        """建「修规则」待办（P1，action_kind='rule_change'；owner 由 TodoService 按账户路由）"""
        sla = sla_seconds_for(REPAIR_TODO_LEVEL) or 1800
        return self._todo_service.create(
            str(rule.get('symbol') or ''), level=REPAIR_TODO_LEVEL, sla_seconds=sla,
            due_at=now + timedelta(seconds=sla), account=account, rule_id=rule_id,
            action_kind='rule_change')

    def _authorize(self, account: Optional[str], operator: str):
        """授权判定（R3/I5）：用户账户规则只有 operator='user' 能动；agent 只动自有账户。

        判定完全复用 route_owner（单一事实源），不新造账户映射：
          · out_of_scope（策略账户）→ agent 不得变更（用户本人可）
          · owner_kind='user' 或 autonomy='remind_only'（含未登记账户/空账户）→ 只允许 user
          · autonomy='autonomous'（agent 自有账户）→ agent 可自主变更并留痕
        """
        route = route_owner(account, self._policy)
        if operator == USER_OPERATOR:
            return route
        if route.out_of_scope:
            raise WatchRuleChangeUnauthorized(
                f'账户 {account!r} 盯盘不介入（out_of_scope），agent 不得变更其规则：{route.reason}')
        if route.owner_kind == OWNER_USER or route.autonomy != 'autonomous':
            raise WatchRuleChangeUnauthorized(
                f'账户 {account!r} 的规则须用户本人确认（owner_kind={route.owner_kind}, '
                f'autonomy={route.autonomy}），agent 不得直接变更：{route.reason}')
        return route
