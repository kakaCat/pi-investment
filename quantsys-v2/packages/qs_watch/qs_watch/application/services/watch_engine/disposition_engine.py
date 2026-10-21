"""处置决策引擎（RFC 014 v3 重构 P1，2026-09-14）

把「组装 GateContext + 调用 domain decide()」从 WatchEngine 剥出。

为何独立：金额门/增量门/经济门/预算门的输入来自外部（持仓市值、账户总资产
provider），此前与触发主流程混在引擎里，只能通过整体 tick 间接验证；提取后
可用 fake provider 直测。

分层：**判定规则本身仍在 domain/watch/services/disposition.decide()**（纯函数）。
本类只做上下文组装与依赖注入，不复制判定逻辑——避免出现第二份真相。

2026-10-21（卡 `rule-change-linkage`）追加「不执行 → 改规则」联动：

  `DispositionEngine` 负责判定（读），`RuleChangeLinkage` 负责把处置卡的动作项
  （调阈值 / 延期 / 停用 / 退役）**落成真实的 watch_rules 更新**，并写一条带
  `trigger_id` 溯源的 `watch_rule_changes`。两者共用同一条处置卡血缘（trigger/todo），
  因此「卡上说的处置」与「库里留下的变更」能对上账。
"""
import copy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from qs_watch.domain.watch.services.disposition import (
    GateContext, InterventionConfig, decide as decide_disposition, normalize_symbol,
)
from qs_watch.domain.watch.services.rule_guard import (
    DISPOSITION_ACTIONS, guard_disposition_action,
)


class DispositionEngine:
    """介入判据的上下文组装与调用"""

    def __init__(self, state, position_value_provider=None,
                 account_total_provider=None, cfg: Optional[InterventionConfig] = None):
        self.state = state
        self._position_value_provider = position_value_provider
        self._account_total_provider = account_total_provider
        self.cfg = cfg or InterventionConfig()

    # ── 外部依赖取值（失败一律 None → 对应门跳过）──────────────
    def position_value(self, rule) -> Optional[float]:
        if self._position_value_provider is None:
            return None
        try:
            return self._position_value_provider(rule)
        except Exception:
            return None

    def account_total(self, rule=None) -> Optional[float]:
        # 2026-09-13（w-c8cae280）：透传规则，让金额门按规则归属账户取值。
        if self._account_total_provider is None:
            return None
        try:
            return self._account_total_provider(rule)
        except Exception:
            return None

    # ── GateContext 组装 ────────────────────────────────────
    def build_gate(self, rule, cond, quote) -> GateContext:
        '''构建介入判据上下文（RFC 014 v3 §3.2）。数据不足时留 None → 对应门跳过。'''
        ah = rule.action_hint if isinstance(getattr(rule, 'action_hint', None), dict) else {}
        intent = str(getattr(rule, 'intent', '') or ah.get('action_on_trigger') or '').strip()
        norm = normalize_symbol(rule.symbol)
        topic = intent or ah.get('action_on_trigger') or 'unknown'
        amount = None
        ev = None
        if intent in ('exit_stop', 'exit_take_profit', 'exit_reduce', 'add_position', 't_trade'):
            # 持仓级动作：金额 = 持仓市值
            amount = self.position_value(rule)
            if amount is not None:
                ev = amount * 0.05  # 粗估：一个 5% 动作的利害关系
        elif intent == 'entry':
            # 买入意向金额：action_hint.max_position_pct × 账户总资产（若有）
            mpp = ah.get('max_position_pct')
            total = self.account_total(rule)
            if mpp and total:
                amount = float(mpp) / 100.0 * float(total)
                ev = amount * 0.03
        return GateContext(
            intent=intent or None,
            amount_yuan=amount,
            last_intervention_at=self.state.last_intervention.get((norm, topic)),
            expected_value_yuan=ev,
            trigger_kind='price',
            daily_wake_count=self.state.interventions_today,
            change_pct=getattr(quote, 'change_pct', None),
        )

    # ── 判定 ────────────────────────────────────────────────
    def decide(self, rule, cond, quote, escalated: bool,
               escalation_reason: Optional[str] = None):
        """返回 (disposition, reason)；判定规则全部来自 domain 层"""
        gate = self.build_gate(rule, cond, quote)
        return decide_disposition(rule, cond, escalated=escalated, gate=gate,
                                  cfg=self.cfg, escalation_reason=escalation_reason)


# ═══════════════════════════════════════════════════════════════════════════
# 处置卡「不执行」→ 改规则联动（2026-10-21 · 卡 rule-change-linkage）
# ═══════════════════════════════════════════════════════════════════════════

class RuleChangeAction(str, Enum):
    """处置卡（P0「不执行」态）可落地的四类规则动作（枚举 = 唯一动作词汇表）。"""

    ADJUST_THRESHOLD = 'adjust_threshold'   # 调阈值：把价格线调出噪音带
    POSTPONE = 'postpone'                   # 延期：把到期/复核时间往后推
    DISABLE = 'disable'                     # 停用：关掉规则，保留生命周期阶段
    RETIRE = 'retire'                       # 退役：关掉规则并终结生命周期


#: 动作 → `watch_rule_changes.change_kind`（唯一映射，不散落调用方）。
#: threshold/retire 复用既有词汇（同一类变更不造第二个名字）；disable/postpone 是
#: 联动新增的处置动作词汇——该列没有 CHECK 约束（见迁移
#: `20261021_watch_rule_changes_trigger_trace.py` 的列注释同步）。
CHANGE_KIND_BY_ACTION: Dict[RuleChangeAction, str] = {
    RuleChangeAction.ADJUST_THRESHOLD: 'threshold',
    RuleChangeAction.POSTPONE: 'postpone',
    RuleChangeAction.DISABLE: 'disable',
    RuleChangeAction.RETIRE: 'retire',
}

#: 动作 → 人读标签（渲染 ops_notes 注记用，单一副本）
ACTION_LABELS: Dict[RuleChangeAction, str] = {
    RuleChangeAction.ADJUST_THRESHOLD: '调阈值',
    RuleChangeAction.POSTPONE: '延期',
    RuleChangeAction.DISABLE: '停用',
    RuleChangeAction.RETIRE: '退役',
}

#: 处置卡「延期」的默认顺延天数（调用方可用 `params={'days': n}` 覆写）
DEFAULT_POSTPONE_DAYS = 1

#: 退役写入的 lifecycle_stage——与引擎「止损使命完成自动退役」同值（closed），
#: 不新造生命周期词汇（tracking/holding/closed 是既有全集）。
RETIRED_LIFECYCLE_STAGE = 'closed'

#: ops_notes 注记的来源标记（复盘按它筛出「处置卡联动」产生的变更）
LINKAGE_NOTE_SOURCE = 'watch_engine/rule_linkage'

#: 条件 DSL 的最大嵌套深度（与 `watch_engine.conditions.MAX_NESTING_DEPTH` 同口径；
#: 本模块不 import 判定层，避免为一次字段改写把整条判定链拉进来）
MAX_CONDITION_DEPTH = 3


@dataclass(frozen=True)
class RuleChangeOutcome:
    """一次处置卡规则变更的结果（规则真值 + 审计行 + 写了哪些字段）。"""

    action: RuleChangeAction
    change_kind: str
    rule_id: int
    fields: Dict[str, Any]
    rule: Any
    change: Any
    reason: str
    trigger_id: int
    todo_id: Optional[int] = None
    decision_audit_id: Optional[str] = None


def _coerce_action(action) -> RuleChangeAction:
    """动作归一：接受枚举或字符串（大小写不敏感）；未知值响亮拒绝。"""
    if isinstance(action, RuleChangeAction):
        return action
    raw = str(getattr(action, 'value', action) or '').strip().lower()
    try:
        return RuleChangeAction(raw)
    except ValueError:
        raise ValueError('未知的处置卡规则动作：%r（允许 %s）'
                         % (action, ' / '.join(DISPOSITION_ACTIONS))) from None


def _field_of(rule, name, default=None):
    """规则字段读取：ORM 对象与 dict 投影同口（仓储两条轨都在用）。"""
    if isinstance(rule, dict):
        return rule.get(name, default)
    return getattr(rule, name, default)


def _rule_id_of(rule) -> Optional[int]:
    value = _field_of(rule, 'id')
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _positive_int(value, name: str) -> int:
    """正整数校验（None/布尔/负数/非数字一律拒绝——审计 id 不接受 0 或 '-1'）。"""
    if value is None or isinstance(value, bool):
        raise ValueError('%s 必须是正整数：%r' % (name, value))
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError('%s 必须是正整数：%r' % (name, value)) from None
    if number < 1:
        raise ValueError('%s 必须是正整数：%r' % (name, value))
    return number


def _wall_clock(value):
    """aware datetime → 去 tzinfo 的墙钟值（watch_rules 时间列是朴素本地时间）。"""
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _as_datetime(value) -> Optional[datetime]:
    """规则时间字段归一（datetime/date/ISO 字符串；解析不了 → None，不臆造）。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return _wall_clock(value)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    try:
        return _wall_clock(datetime.fromisoformat(str(value)))
    except (TypeError, ValueError):
        return None


def _iso(value) -> Optional[str]:
    parsed = _as_datetime(value)
    return parsed.isoformat() if parsed is not None else None


def _rewrite_price_thresholds(conditions: List[Any], price: float,
                              direction: Optional[str] = None,
                              depth: int = 0) -> Tuple[List[Any], int]:
    """把价格条件的阈值改写为 price（返回**新列表** + 命中条件数，不改原对象）。

    覆盖三种载体（都是 watch 条件 DSL 的既有形状）：
      · `price_break`           → params.price（direction 可选同改）
      · `staged_break`          → params.touch.price（两段式伏击的触及线）
      · `combined`              → params.conditions 递归（受 MAX_CONDITION_DEPTH 限制）
    命中 0 条时由调用方响亮拒绝——「调阈值」没有可调对象就是假动作。
    """
    out: List[Any] = []
    hits = 0
    for cond in conditions or []:
        if not isinstance(cond, dict):
            out.append(cond)
            continue
        ctype = str(cond.get('type') or '')
        if ctype == 'price_break':
            new_cond = dict(cond)
            params = dict(new_cond.get('params') or {})
            params['price'] = price
            if direction:
                params['direction'] = direction
            new_cond['params'] = params
            out.append(new_cond)
            hits += 1
        elif ctype == 'staged_break':
            new_cond = dict(cond)
            params = dict(new_cond.get('params') or {})
            touch = dict(params.get('touch') or {})
            touch['price'] = price
            if direction:
                touch['direction'] = direction
            params['touch'] = touch
            new_cond['params'] = params
            out.append(new_cond)
            hits += 1
        elif ctype == 'combined' and depth < MAX_CONDITION_DEPTH:
            new_cond = dict(cond)
            params = dict(new_cond.get('params') or {})
            nested, nested_hits = _rewrite_price_thresholds(
                params.get('conditions') or [], price, direction, depth + 1)
            params['conditions'] = nested
            new_cond['params'] = params
            out.append(new_cond)
            hits += nested_hits
        else:
            out.append(cond)
    return out, hits


def _append_ops_note(rule, action: RuleChangeAction, reason: str,
                     now: datetime, trigger_id: int) -> List[Dict[str, Any]]:
    """把这次处置写进规则 ops_notes（与引擎止损退役同格式：{at, by, text}）。

    为什么同时写规则注记（审计表已有 reason）：规则本体的「谁在什么时候动过我」
    在规则详情页/规则列表就能看见，不必先反查审计表；两条留痕互不替代。
    """
    notes = _field_of(rule, 'ops_notes')
    if isinstance(notes, list):
        notes = list(notes)
    elif notes in (None, '', {}):
        notes = []
    else:
        notes = [notes]
    notes.append({
        'at': now.isoformat(),
        'by': LINKAGE_NOTE_SOURCE,
        'action': action.value,
        'trigger_id': trigger_id,
        'text': '[处置卡%s] %s' % (ACTION_LABELS[action], reason),
    })
    return notes


class RuleChangeLinkage:
    """处置卡「不执行」→ 规则更新 + 审计溯源（2026-10-21 · 卡 rule-change-linkage）

    与 `DispositionEngine` 的分工：后者只判定（读），本类只落地（写）。

    四条写入纪律（每条都有对应测试，可被改坏证伪）：

    1. **真更新**：四个动作都必须落成 `watch_rules` 的字段变更，不是只写审计的假动作
       （阈值改 conditions / 延期改 expires_at+review_due_at / 停用改 enabled /
       退役改 enabled+lifecycle_stage）；
    2. **可溯源**：每条审计都必须带 `trigger_id`（来源触发）——缺则**在写任何东西之前**
       拒绝；`todo_id`/`decision_audit_id` 有则透传；
    3. **不绕守卫**：规则更新一律走仓储 `update_fields`——宪法级止损规则的停用/退役
       必须随附理由（`rule_guard` 的既有卡口，本类再次前置拦截以获得领域异常）；
    4. **理由必填**：`watch_rule_changes.reason` NOT NULL + R-020，空理由拒绝。

    端口（构造注入，便于无 DB 单测）：
      · rule_repo  ：`update_fields(rule_id, **fields) -> rule|None`，
                     可选 `get_by_id(rule_id)`（`apply_for_decline` 用）；
      · change_repo：`record(rule_id, changed_by=..., change_kind=..., before=...,
                     after=..., reason=..., trigger_id=..., todo_id=...,
                     decision_audit_id=...) -> change`。
    """

    def __init__(self, rule_repo, change_repo, now_fn=None,
                 default_postpone_days: int = DEFAULT_POSTPONE_DAYS):
        self._rule_repo = rule_repo
        self._change_repo = change_repo
        self._now_fn = now_fn
        self._default_postpone_days = _positive_int(
            default_postpone_days, 'default_postpone_days')

    # ── 唯一写入口 ───────────────────────────────────────────
    def apply(self, rule, action, *, reason, trigger_id, todo_id: Optional[int] = None,
              decision_audit_id: Optional[str] = None, params: Any = None,
              changed_by: str = 'agent',
              now: Optional[datetime] = None) -> RuleChangeOutcome:
        """把处置卡的一条动作项落地为规则更新 + 审计留痕。

        Args:
            rule: 规则对象（ORM 或 dict 投影；只读 id/字段，不就地修改）。
            action: `RuleChangeAction` 或等值字符串。
            reason: 变更理由（**必填非空**，写进审计与 ops_notes）。
            trigger_id: 溯源触发 id（**必填正整数**，联动审计的来源凭据）。
            todo_id/decision_audit_id: 处置卡血缘（有则透传）。
            params: 动作参数（调阈值 `{'price': x, 'direction': 'above'|'below'}`；
                延期 `{'days': n}`）。
            changed_by: agent / user / system（与审计表 CHECK 同集）。
            now: 判定时刻（测试注入；缺省读 now_fn 再缺省 datetime.now()）。

        Returns:
            `RuleChangeOutcome`（含新规则投影与审计行）。

        Raises:
            ConstitutionalRuleSilentDisable: 宪法级止损规则无理由停用/退役
                （在写库之前抛出，规则与审计都未被改动）。
            ValueError: 未知动作 / 缺 trigger_id / 缺理由 / 参数缺失或非法 /
                规则不存在。
        """
        action_value = _coerce_action(action)
        reason_text = str(reason or '').strip()

        # ① 守卫先行：未知动作 + 宪法级止损的停用/退役理由——在写任何东西之前拒绝。
        guard_disposition_action(rule, action_value, reason=reason_text)

        # ② 通用必填（R-020）：审计表 reason NOT NULL，空理由在这里就拦，不靠 DB 报错。
        if not reason_text:
            raise ValueError('reason 必填：规则变更必须写明理由（R-020，空理由无法复盘）')

        # ③ 溯源必填：没有触发的规则变更无法复盘，宁可拒绝也不写半条。
        trigger = _positive_int(trigger_id, 'trigger_id')
        todo = None if todo_id is None else _positive_int(todo_id, 'todo_id')

        rule_id = _rule_id_of(rule)
        if rule_id is None:
            raise ValueError('规则缺少 id，无法落地规则变更')

        current = (_wall_clock(now) if now is not None
                   else _wall_clock(self._now_fn() if self._now_fn is not None
                                    else datetime.now()))
        payload = params if isinstance(params, Mapping) else {}

        # ④ 算「要写什么」（纯计算；任何参数问题都在这里抛，尚未写库）
        fields, before, after = self._changes_for(rule, action_value, payload, current)
        fields = dict(fields, ops_notes=_append_ops_note(
            rule, action_value, reason_text, current, trigger))

        # ⑤ 规则真更新（走仓储既有卡口，不绕 SQL）
        updated = self._rule_repo.update_fields(rule_id, **fields)
        if updated is None:
            raise ValueError('规则 %s 不存在（update_fields 返回 None）' % rule_id)

        # ⑥ 审计留痕（trigger_id 溯源；失败向上抛——变化已发生，必须让人知道没记上）
        change_kind = CHANGE_KIND_BY_ACTION[action_value]
        change = self._change_repo.record(
            rule_id,
            changed_by=changed_by,
            change_kind=change_kind,
            before=before,
            after=after,
            reason=reason_text,
            trigger_id=trigger,
            todo_id=todo,
            decision_audit_id=decision_audit_id,
        )
        return RuleChangeOutcome(
            action=action_value, change_kind=change_kind, rule_id=rule_id,
            fields=fields, rule=updated, change=change, reason=reason_text,
            trigger_id=trigger, todo_id=todo,
            decision_audit_id=decision_audit_id)

    # ── 从执行指令（P0「不执行」态）落地 ─────────────────────
    def apply_for_decline(self, directive, action, *, reason, params: Any = None,
                          decision_audit_id: Optional[str] = None,
                          changed_by: str = 'agent', now: Optional[datetime] = None,
                          rule=None) -> RuleChangeOutcome:
        """从 P0 执行指令（处置卡「不执行」态）落地一次规则变更。

        溯源 id 直接取自指令（`rule_id` / `trigger_id` / `todo_id`）——调用方不再
        各自拼装，避免「审计挂到别的触发上」这种断链（复盘时最难查的一类）。
        `rule` 可由调用方传入（已在上下文里），缺省按 `rule_id` 从仓储取。
        """
        trigger_id = getattr(directive, 'trigger_id', None)
        todo_id = getattr(directive, 'todo_id', None)
        rule_obj = rule if rule is not None else self._load_rule(
            getattr(directive, 'rule_id', None))
        if rule_obj is None:
            raise ValueError('执行指令无可落地规则（rule_id=%r）：先用 rule_repo 确认规则存在'
                             % (getattr(directive, 'rule_id', None),))
        return self.apply(rule_obj, action, reason=reason, trigger_id=trigger_id,
                          todo_id=todo_id, decision_audit_id=decision_audit_id,
                          params=params, changed_by=changed_by, now=now)

    # ── 各动作的字段计算（纯函数式；不写库）──────────────────
    def _changes_for(self, rule, action: RuleChangeAction, params: Mapping,
                     now: datetime) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """返回 (要写入的字段, 审计 before, 审计 after)——审计只含**涉及的字段**。"""
        if action is RuleChangeAction.ADJUST_THRESHOLD:
            return self._threshold_change(rule, params)
        if action is RuleChangeAction.POSTPONE:
            return self._postpone_change(rule, params, now)
        if action is RuleChangeAction.DISABLE:
            return ({'enabled': False},
                    {'enabled': _field_of(rule, 'enabled', True)},
                    {'enabled': False})
        return self._retire_change(rule)

    def _threshold_change(self, rule, params: Mapping):
        """调阈值：把价格线（price_break / staged_break / combined 内）改成新值。"""
        raw_price = params.get('price', params.get('threshold'))
        if raw_price is None:
            raise ValueError('调阈值必须给出 params.price（新阈值）——'
                             '没有目标值的动作是假动作（E1）')
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            raise ValueError('params.price 必须是数值：%r' % (raw_price,)) from None
        if not price > 0:
            raise ValueError('params.price 必须为正数：%r' % (raw_price,))

        raw_direction = params.get('direction')
        direction = str(raw_direction or '').strip().lower() or None
        if direction is not None and direction not in ('above', 'below'):
            raise ValueError("params.direction 只能是 'above' / 'below'：%r" % (raw_direction,))

        conditions = _field_of(rule, 'conditions')
        if not isinstance(conditions, list) or not conditions:
            raise ValueError('规则没有 conditions，调阈值无落地对象（拒绝假动作）')

        rewritten, hits = _rewrite_price_thresholds(conditions, price, direction)
        if not hits:
            raise ValueError('规则没有可调阈值的价格条件（price_break / staged_break），'
                             '调阈值无落地对象（拒绝假动作）')
        return ({'conditions': rewritten},
                {'conditions': copy.deepcopy(conditions)},
                {'conditions': rewritten})

    def _postpone_change(self, rule, params: Mapping, now: datetime):
        """延期：顺延复核时间；规则本就有到期时间的，一并顺延（没有就不硬造）。"""
        raw_days = params.get('days', params.get('postpone_days',
                                                self._default_postpone_days))
        days = _positive_int(raw_days, 'params.days')
        old_expires = _as_datetime(_field_of(rule, 'expires_at'))
        old_review = _as_datetime(_field_of(rule, 'review_due_at'))

        fields: Dict[str, Any] = {'review_due_at': now + timedelta(days=days)}
        if old_expires is not None:
            # 已到期/即将到期都从「此刻」起算，避免顺延后仍是过去时间（等于没延）
            anchor = old_expires if old_expires > now else now
            fields['expires_at'] = anchor + timedelta(days=days)

        before = {'expires_at': old_expires.isoformat() if old_expires else None,
                  'review_due_at': old_review.isoformat() if old_review else None}
        # after 与 before 同键集：到期时间没被触碰时如实留 None（不因"没写"而缺键，
        # 否则复盘要区分「键缺失」与「值为空」——那是两回事）。
        after = {'expires_at': (fields['expires_at'].isoformat()
                                if 'expires_at' in fields else None),
                 'review_due_at': fields['review_due_at'].isoformat()}
        return fields, before, after

    def _retire_change(self, rule):
        """退役：关掉规则并终结生命周期（lifecycle_stage=closed，与引擎自动退役同值）。"""
        return ({'enabled': False, 'lifecycle_stage': RETIRED_LIFECYCLE_STAGE},
                {'enabled': _field_of(rule, 'enabled'),
                 'lifecycle_stage': _field_of(rule, 'lifecycle_stage')},
                {'enabled': False, 'lifecycle_stage': RETIRED_LIFECYCLE_STAGE})

    # ── 规则读取（仅 apply_for_decline 用；兼容两条仓储端口命名）──────────
    def _load_rule(self, rule_id):
        if rule_id is None:
            return None
        for name in ('get_by_id', 'get_rule'):
            loader = getattr(self._rule_repo, name, None)
            if callable(loader):
                return loader(rule_id)
        raise ValueError('规则仓储缺少 get_by_id/get_rule，无法按 rule_id 取规则')
