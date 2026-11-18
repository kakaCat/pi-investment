"""普通盯盘规则 CRUD/batch 的统一授权、审计与失败补偿。

repair 的授权策略由 ``rules.authorizer`` 共享；本服务不复制账户表，也不让路由直接
写仓储。所有成功写均追加 ``quant.watch_rule_changes``，并携带 before/after 与
trigger/todo/decision_audit 血缘。

既有规则仓储与审计仓储分别提交，无法在这里伪装成数据库级单事务。本服务因此采用
明确的补偿语义：单条审计失败恢复该条写入；batch 失败反向补偿本批已完成动作。
补偿失败会随 ``rollback_errors`` 响亮暴露，绝不返回 ``success=True``。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple

from qs_watch.application.services.watch_engine.conditions import validate_condition
from qs_watch.application.services.watch_engine.rules.authorizer import (
    DEFAULT_OPERATOR,
    USER_OPERATOR,
    authorize_rule_account,
)
from qs_watch.domain.watch.ports import (
    WatchRuleChangeError,
    WatchRuleChangeMissingReason,
    WatchRuleChangeRuleNotFound,
)
from qs_watch.domain.watch.services.disposition import intent_of, is_trade_intent
from qs_watch.domain.watch.services.noise_policy import is_rule_write_change_kind
from qs_watch.domain.watch.services.rule_guard import effective_account, guard_new_rule


class WatchRuleChangeMissingAudit(WatchRuleChangeError):
    """agent 普通写缺少事前决策审计号（路由映射 400）。"""
    code = 'watch_rule_change_missing_audit'


class WatchRuleChangeInvalidAudit(WatchRuleChangeError):
    """审计号不存在，或其显式业务实体与本次规则写不一致。"""
    code = 'watch_rule_change_invalid_audit'


class WatchRuleWriteFailed(RuntimeError):
    """写入/审计失败；rollback_errors 非空表示补偿也未完整成功。"""

    def __init__(self, message: str, *, rollback_errors: Optional[List[str]] = None,
                 rollback_attempted: bool = False):
        super().__init__(message)
        self.rollback_errors = list(rollback_errors or [])
        self.rollback_attempted = rollback_attempted


class WatchRuleBatchFailed(RuntimeError):
    """batch 已失败并尝试反向补偿；保留逐项结果与补偿故障供路由原样返回。"""

    def __init__(self, cause: Exception, results: List[Dict[str, Any]], *,
                 rollback_attempted: bool, rollback_errors: List[str]):
        super().__init__(str(cause))
        self.cause = cause
        self.results = results
        self.rollback_attempted = rollback_attempted
        self.rollback_errors = list(rollback_errors)


#: 与 WatchRuleRepository.create_rule 的真实签名对齐；其余元数据在创建后、审计前落地。
_CREATE_BASE_FIELDS = (
    'symbol', 'conditions', 'context', 'cost_price', 'active_window', 'expires_at',
    'created_by', 'account', 'linked_account', 'intent', 'action_hint', 'action_params',
    'position_state', 'interval_sec', 'plan_id', 'invalidation_threshold_pct',
    'watch_tier', 'trigger_channel',
)

#: 普通 PATCH/PUT 与 batch update 允许修改的字段（审计上下文字段刻意不在其中）。
_UPDATE_FIELDS = (
    'enabled', 'conditions', 'context', 'cost_price', 'active_window', 'expires_at',
    'account', 'notify_mode', 'action_hint', 'escalation_policy', 'intent',
    'lifecycle_stage', 'scope', 'target', 'linked_account', 'created_from',
    'next_action_hint', 'review_interval_days', 'review_due_at', 'action_params',
    'ops_notes', 'position_state', 'interval_sec', 'watch_tier', 'plan_id',
    'rule_state', 'invalid_reason', 'invalid_at', 'invalidation_threshold_pct',
    'invalid_escalated_at', 'trigger_channel', 'process_state', 'symbol',
)


def _get(rule: Any, key: str, default: Any = None) -> Any:
    if isinstance(rule, dict):
        return rule.get(key, default)
    return getattr(rule, key, default)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _snapshot(rule: Any, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """规则投影；fields=None 时取全部公开数据属性，供 create 的完整 after 审计。"""
    if rule is None:
        return None
    if fields is None:
        if isinstance(rule, dict):
            keys = [k for k in rule if not str(k).startswith('_')]
        else:
            keys = [k for k in vars(rule) if not str(k).startswith('_')]
    else:
        keys = fields
    return {key: _jsonable(_get(rule, key)) for key in keys}


def _normalize_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(fields)
    if isinstance(out.get('expires_at'), str) and out['expires_at'].strip():
        out['expires_at'] = datetime.fromisoformat(out['expires_at'])
    for key in ('review_due_at', 'invalid_at', 'invalid_escalated_at'):
        if isinstance(out.get(key), str) and out[key].strip():
            out[key] = datetime.fromisoformat(out[key])
    return out


class WatchRuleWriteService:
    """规则写入应用服务；仓储由路由/测试注入，不自行接触 ORM 或 SQL。"""

    def __init__(self, rule_repo: Any, change_repo: Any, *, policy: Any = None,
                 decision_repo: Any = None):
        self._rule_repo = rule_repo
        self._change_repo = change_repo
        self._decision_repo = decision_repo
        self._policy = policy

    @staticmethod
    def context(*, reason: Optional[str], operator: Optional[str],
                decision_audit_id: Optional[str], trigger_id: Optional[int] = None,
                todo_id: Optional[int] = None) -> Dict[str, Any]:
        """所有普通写共用的前置契约：人人要 reason，agent 还要 decision_audit_id。"""
        reason_value = str(reason or '').strip()
        if not reason_value:
            raise WatchRuleChangeMissingReason(
                'reason 必填：普通规则创建/修改/退役与 repair 一样必须留痕')
        operator_value = str(operator or '').strip() or DEFAULT_OPERATOR
        audit_value = str(decision_audit_id or '').strip() or None
        if operator_value != USER_OPERATOR and not audit_value:
            raise WatchRuleChangeMissingAudit(
                'agent 规则写操作必须提供 decision_audit_id（事前决策审计号）')
        return {
            'reason': reason_value,
            'operator': operator_value,
            'changed_by': USER_OPERATOR if operator_value == USER_OPERATOR else 'agent',
            'decision_audit_id': audit_value,
            'trigger_id': trigger_id,
            'todo_id': todo_id,
        }

    def _guard(self, before: Any, fields: Dict[str, Any]) -> Tuple[Optional[str], str]:
        """校验改后账户契约并返回（目标账户, 改后 intent）；同时覆盖改前/改后授权。"""
        data = dict(fields or {})
        intent = data.get('intent', _get(before, 'intent'))
        action_hint = data.get('action_hint', _get(before, 'action_hint'))
        conditions = data.get('conditions', _get(before, 'conditions'))
        if 'linked_account' in data or 'account' in data:
            account = data.get('linked_account') or data.get('account') or None
        else:
            account = effective_account(before) if before is not None else None
        symbol = data.get('symbol', _get(before, 'symbol'))
        guard_new_rule(intent=intent, action_hint=action_hint, conditions=conditions,
                       account=account, symbol=symbol)
        derived = intent_of(SimpleNamespace(
            intent=intent or '', action_hint=action_hint or {}, conditions=conditions or []))
        return account, derived

    def _authorize(self, account: Optional[str], derived_intent: str,
                   ctx: Dict[str, Any]) -> None:
        allow_none = not is_trade_intent(derived_intent)
        authorize_rule_account(
            account,
            ctx['operator'],
            policy=self._policy,
            allow_accountless_observation=allow_none,
        )

    def _validate_audit(self, ctx: Dict[str, Any], *, before: Any = None,
                        fields: Optional[Dict[str, Any]] = None) -> None:
        """事前审计必须真实存在；显式关联实体不得张冠李戴。

        通用 pool/strategy 决策可派生多条规则，因此不强制所有决策都预绑定 rule_id；
        但 stock/account/rule 三类明确实体若与目标不同，必须拒绝。
        """
        if ctx['changed_by'] == USER_OPERATOR:
            return
        if self._decision_repo is None:
            raise WatchRuleChangeInvalidAudit('规则写服务未接决策审计仓储，拒绝写入')
        audit_id = ctx.get('decision_audit_id')
        decision = self._decision_repo.get_decision(audit_id)
        if not decision:
            raise WatchRuleChangeInvalidAudit(f'decision_audit_id 不存在: {audit_id}')
        related_type = str(decision.get('related_entity_type') or '').strip()
        related_id = decision.get('related_entity_id')
        if related_id is None or not related_type:
            return
        data = fields or {}
        related = str(related_id)
        if related_type == 'stock':
            symbol = str(data.get('symbol') or _get(before, 'symbol') or '')
            if symbol and related != symbol:
                raise WatchRuleChangeInvalidAudit(
                    f'审计标的 {related} 与规则标的 {symbol} 不一致')
        elif related_type == 'account':
            account = (data.get('linked_account') or data.get('account')
                       or effective_account(before))
            if account and related != str(account):
                raise WatchRuleChangeInvalidAudit(
                    f'审计账户 {related} 与规则账户 {account} 不一致')
        elif related_type == 'rule':
            rule_id = _get(before, 'id')
            if rule_id is None or related != str(rule_id):
                raise WatchRuleChangeInvalidAudit(
                    f'审计规则 {related} 与目标规则 {rule_id} 不一致')

    def _authorize_existing(self, rule: Any, ctx: Dict[str, Any]) -> None:
        account, derived = self._guard(rule, {})
        self._authorize(account, derived, ctx)

    def _record(self, rule_id: int, kind: str, *, before: Any, after: Any,
                ctx: Dict[str, Any], reason: Optional[str] = None):
        if not is_rule_write_change_kind(kind):
            raise ValueError(f'普通规则写入不支持审计动作: {kind!r}')
        change = self._change_repo.record(
            rule_id,
            ctx['changed_by'],
            kind,
            before=before,
            after=after,
            reason=str(reason or ctx['reason']),
            trigger_id=ctx.get('trigger_id'),
            todo_id=ctx.get('todo_id'),
            decision_audit_id=ctx.get('decision_audit_id'),
        )
        if change is None:
            raise RuntimeError('规则审计写入未返回记录，不能视为成功')
        return change

    @staticmethod
    def _rule_id(rule: Any) -> int:
        value = _get(rule, 'id')
        if value is None:
            raise RuntimeError('规则写入后缺少 id，不能审计')
        return int(value)

    def _cleanup_unaudited_create(self, rule_id: int) -> List[str]:
        try:
            result = self._rule_repo.delete_by_id(rule_id)
            if result is False:
                raise RuntimeError('delete_by_id 返回 False')
            return []
        except Exception as exc:  # noqa: BLE001 - 必须保留补偿失败证据
            return [f'create#{rule_id} 撤销失败: {exc}']

    def _restore_unaudited_fields(self, rule_id: int,
                                  before_fields: Dict[str, Any]) -> List[str]:
        restore = dict(before_fields)
        # 恢复「原本停用的宪法级规则」也要给仓储守卫一个机器理由。
        if restore.get('enabled') is False and not (restore.get('context') or restore.get('ops_notes')):
            restore['ops_notes'] = [{'at': datetime.now().isoformat(), 'by': 'system',
                                     'text': '审计写入失败，恢复原启用状态'}]
        try:
            restored = self._rule_repo.update_fields(rule_id, **restore)
            if restored is None:
                raise RuntimeError('update_fields 返回 None')
            return []
        except Exception as exc:  # noqa: BLE001
            return [f'rule#{rule_id} 原字段恢复失败: {exc}']

    def _execute_create(self, fields: Dict[str, Any],
                        ctx: Dict[str, Any]) -> Tuple[Dict[str, Any], Callable[[], Any]]:
        data = _normalize_fields(fields)
        account, derived = self._guard(None, data)
        self._authorize(account, derived, ctx)
        conditions = data.get('conditions')
        if not isinstance(conditions, list) or not conditions:
            raise ValueError('conditions 必须为非空数组')
        for condition in conditions:
            validate_condition(condition)
        if not str(data.get('symbol') or '').strip():
            raise ValueError('缺少必填参数: symbol')
        if 'action_params' in data:
            from qs_watch.domain.watch.models import validate_action_params
            error = validate_action_params(data.get('action_params'))
            if error:
                raise ValueError(error)

        self._validate_audit(ctx, fields=data)
        base = {key: data[key] for key in _CREATE_BASE_FIELDS if key in data}
        created = self._rule_repo.create_rule(**base)
        if created is None:
            raise WatchRuleWriteFailed('规则创建失败：仓储未返回记录')
        rule_id = self._rule_id(created)
        rule = created
        try:
            metadata_keys = (
                'lifecycle_stage', 'scope', 'target', 'created_from', 'next_action_hint',
                'review_interval_days', 'review_due_at', 'escalation_policy', 'ops_notes',
            )
            metadata = {key: data[key] for key in metadata_keys if key in data and key not in base}
            if metadata:
                rule = self._rule_repo.update_fields(rule_id, **metadata)
                if rule is None:
                    raise RuntimeError('创建后元数据落地失败')
            after = _snapshot(rule)
            change = self._record(rule_id, 'create', before=None, after=after, ctx=ctx)
        except Exception as exc:
            errors = self._cleanup_unaudited_create(rule_id)
            message = f'规则创建未完成，审计/元数据写入失败: {exc}'
            if errors:
                message += '；' + '；'.join(errors)
            raise WatchRuleWriteFailed(
                message, rollback_errors=errors, rollback_attempted=True) from exc

        def undo() -> Any:
            archived = self._rule_repo.update_fields(
                rule_id, enabled=False, rule_state='archived',
                ops_notes=[{'at': datetime.now().isoformat(), 'by': 'system',
                            'text': 'batch 后续动作失败，撤销本批新建规则'}])
            if archived is None:
                raise RuntimeError('新建规则补偿归档失败')
            return self._record(
                rule_id, 'retire', before={'enabled': True, 'rule_state': 'active'},
                after={'enabled': False, 'rule_state': 'archived'}, ctx=ctx,
                reason=f"batch 失败补偿，撤销新建规则（原理由：{ctx['reason']}）")

        return {'rule': rule, 'change': change}, undo

    def _execute_update(self, rule_id: int, fields: Dict[str, Any],
                        ctx: Dict[str, Any]) -> Tuple[Dict[str, Any], Callable[[], Any]]:
        before = self._rule_repo.get_by_id(rule_id)
        if before is None:
            raise WatchRuleChangeRuleNotFound(f'规则 {rule_id} 不存在')
        data = _normalize_fields({key: fields[key] for key in _UPDATE_FIELDS if key in fields})
        if not data:
            raise ValueError('没有可更新字段')
        self._authorize_existing(before, ctx)
        target_account, target_intent = self._guard(before, data)
        self._authorize(target_account, target_intent, ctx)
        if 'conditions' in data:
            if not isinstance(data['conditions'], list) or not data['conditions']:
                raise ValueError('conditions 必须为非空数组')
            for condition in data['conditions']:
                validate_condition(condition)
        if 'action_params' in data:
            from qs_watch.domain.watch.models import validate_action_params
            error = validate_action_params(data.get('action_params'))
            if error:
                raise ValueError(error)

        self._validate_audit(ctx, before=before, fields=data)
        names = list(data)
        before_fields = _snapshot(before, names) or {}
        updated = self._rule_repo.update_fields(rule_id, **data)
        if updated is None:
            raise WatchRuleWriteFailed(f'规则 {rule_id} 更新失败：仓储未返回记录')
        try:
            after_fields = _snapshot(updated, names)
            change = self._record(rule_id, 'update', before=before_fields,
                                  after=after_fields, ctx=ctx)
        except Exception as exc:
            errors = self._restore_unaudited_fields(rule_id, before_fields)
            message = f'规则 {rule_id} 更新审计失败: {exc}'
            if errors:
                message += '；' + '；'.join(errors)
            raise WatchRuleWriteFailed(
                message, rollback_errors=errors, rollback_attempted=True) from exc

        def undo() -> Any:
            errors = self._restore_unaudited_fields(rule_id, before_fields)
            if errors:
                raise RuntimeError('；'.join(errors))
            restored = self._rule_repo.get_by_id(rule_id)
            return self._record(
                rule_id, 'update', before=after_fields,
                after=_snapshot(restored, names), ctx=ctx,
                reason=f"batch 失败补偿，恢复原字段（原理由：{ctx['reason']}）")

        return {'rule': updated, 'change': change}, undo

    def _execute_archive(self, rule_id: int, ctx: Dict[str, Any], *,
                         retire_note: Optional[str] = None) -> Tuple[Dict[str, Any], Callable[[], Any]]:
        before = self._rule_repo.get_by_id(rule_id)
        if before is None:
            raise WatchRuleChangeRuleNotFound(f'规则 {rule_id} 不存在')
        self._authorize_existing(before, ctx)
        self._validate_audit(ctx, before=before)
        note = str(retire_note or ctx['reason']).strip()
        old_notes = _get(before, 'ops_notes') or []
        notes = list(old_notes) + [{'at': datetime.now().isoformat(),
                                    'by': ctx['changed_by'], 'text': f'规则软退役：{note}'}]
        data: Dict[str, Any] = {'enabled': False, 'rule_state': 'archived', 'ops_notes': notes}
        if retire_note:
            data['context'] = f"[报废 {datetime.now().date().isoformat()}] {note}\n{_get(before, 'context') or ''}"
        names = list(data)
        before_fields = _snapshot(before, names) or {}
        archived = self._rule_repo.update_fields(rule_id, **data)
        if archived is None:
            raise WatchRuleWriteFailed(f'规则 {rule_id} 软退役失败：仓储未返回记录')
        try:
            after_fields = _snapshot(archived, names)
            change = self._record(rule_id, 'retire', before=before_fields,
                                  after=after_fields, ctx=ctx)
        except Exception as exc:
            errors = self._restore_unaudited_fields(rule_id, before_fields)
            message = f'规则 {rule_id} 软退役审计失败: {exc}'
            if errors:
                message += '；' + '；'.join(errors)
            raise WatchRuleWriteFailed(
                message, rollback_errors=errors, rollback_attempted=True) from exc

        def undo() -> Any:
            errors = self._restore_unaudited_fields(rule_id, before_fields)
            if errors:
                raise RuntimeError('；'.join(errors))
            restored = self._rule_repo.get_by_id(rule_id)
            return self._record(
                rule_id, 'update', before=after_fields,
                after=_snapshot(restored, names), ctx=ctx,
                reason=f"batch 失败补偿，撤销软退役（原理由：{ctx['reason']}）")

        return {'rule': archived, 'change': change}, undo

    def create(self, fields: Dict[str, Any], **context: Any) -> Dict[str, Any]:
        ctx = self.context(**context)
        return self._execute_create(fields, ctx)[0]

    def update(self, rule_id: int, fields: Dict[str, Any], **context: Any) -> Dict[str, Any]:
        ctx = self.context(**context)
        return self._execute_update(rule_id, fields, ctx)[0]

    def archive(self, rule_id: int, **context: Any) -> Dict[str, Any]:
        ctx = self.context(**context)
        return self._execute_archive(rule_id, ctx)[0]

    def execute_batch(self, actions: List[Dict[str, Any]], *,
                      source_trigger_id: Optional[int], todo_id: Optional[int] = None,
                      **context: Any) -> List[Dict[str, Any]]:
        ctx = self.context(trigger_id=source_trigger_id, todo_id=todo_id, **context)
        completed: List[Tuple[int, Callable[[], Any]]] = []
        results: List[Dict[str, Any]] = []
        for index, raw in enumerate(actions):
            action = dict(raw or {})
            op = str(action.pop('op', '') or '').strip().lower()
            try:
                if op == 'create':
                    action.setdefault('created_from', f'trigger:{source_trigger_id}')
                    result, undo = self._execute_create(action, ctx)
                elif op == 'update':
                    rule_id = action.get('rule_id')
                    if rule_id is None:
                        raise ValueError('update 需要 rule_id')
                    result, undo = self._execute_update(int(rule_id), action, ctx)
                elif op == 'retire':
                    rule_id = action.get('rule_id')
                    if rule_id is None:
                        raise ValueError('retire 需要 rule_id')
                    result, undo = self._execute_archive(
                        int(rule_id), ctx, retire_note=action.get('retire_note'))
                else:
                    raise ValueError('op 必须是 create/update/retire')
                entry = {'index': index, 'success': True, 'op': op,
                         'rule_id': self._rule_id(result['rule']), **result}
                results.append(entry)
                completed.append((index, undo))
            except Exception as exc:  # noqa: BLE001 - 汇总时必须保留原异常供状态映射
                results.append({'index': index, 'success': False, 'op': op or None,
                                'error': getattr(exc, 'code', type(exc).__name__),
                                'message': str(exc)})
                # 当前动作自身的审计失败补偿也属于本批回滚；其失败不能被
                # “此前动作都补偿成功”掩盖。
                rollback_errors: List[str] = list(getattr(exc, 'rollback_errors', []))
                current_rollback_attempted = bool(getattr(exc, 'rollback_attempted', False))
                for completed_index, undo in reversed(completed):
                    entry = next(item for item in results if item['index'] == completed_index)
                    try:
                        rollback_change = undo()
                        entry['initial_success'] = True
                        entry['success'] = False
                        entry['rolled_back'] = True
                        entry['rollback_change'] = rollback_change
                    except Exception as rollback_exc:  # noqa: BLE001
                        entry['rollback_failed'] = True
                        rollback_errors.append(f'action#{completed_index}: {rollback_exc}')
                raise WatchRuleBatchFailed(
                    exc, results,
                    rollback_attempted=(current_rollback_attempted or bool(completed)),
                    rollback_errors=rollback_errors) from exc
        return results
