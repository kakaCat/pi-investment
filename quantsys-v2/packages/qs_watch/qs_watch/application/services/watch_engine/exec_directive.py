"""P0 执行指令卡（RFC 017 §2.1.2，2026-10-21 · 卡 `exec-directive-card`）

把「P0 触发 → 到底该执行什么」构造为**结构化、可单测的纯函数产物** `ExecDirective`：

  · 通知侧：P0 卡的「下一步」与结构化动作块（`card_action_text` / `action_params`）；
  · 待办侧：同一条待办挂 `exec_directive`（`_create_watch_todo` 之后原样挂上）。

两侧读**同一个对象**（构造点唯一：`DeliverStage`），因此不会出现「通知说的话」与
「待办要的事」两份口径。

三条纪律（逐条对应本卡验收）：

1. **纯函数**：`build_exec_directive(...)` 只吃输入、不做 I/O。持仓真值的读取（本模块唯一的
   I/O）单独放在 `read_position_facts()`，由调用方（`DeliverStage`）读完再注入——单测因此
   无需 DB 即可覆盖 P0 止损 / 止盈 / 非止损 / 缺账户 / 缺持仓 / T+1 锁仓 / 读失败七种情形。
2. **动作项是结构化枚举，不是自由文本**：三态处置（执行 / 不执行 / 超时）各是一条
   `DispositionAction`，字段全部是枚举或布尔（`ExecState` / `TodoTerminal` / `TodoActionKind`）。
   文案只在渲染时由枚举派生（`render_action_item` / `card_guide_text`），payload 里不存文案。
3. **不自动下单**：本模块只产出「给 agent 的执行口径」，不含任何交易/下单调用
   （RFC §2.4 硬约束：闭环 = 指令 → agent 执行 → 成交回执 → 超时兜底）。

「读不到持仓」的语义（RFC §2.1.2，两面对称）：
  · **读失败**（异常）→ `executable=True` + `evidence['position_read']='degraded'`，
    把核实责任交回 agent——绝不把数据故障伪装成「无需动作」；
  · **确认读到 0 股** → `executable=False` + `no_position`；有总量但可卖为 0 → `t1_locked`。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from qs_watch.domain.watch.services.disposition import (
    intent_of, normalize_symbol,
)
from qs_watch.domain.watch.services.rule_guard import effective_account

#: 执行收敛期限（分钟，RFC §2.1.5：默认 30 分钟；与 P0 提醒 SLA 300s 是两个时钟）
EXEC_SLA_ENV = 'WATCH_EXEC_SLA_MIN'
DEFAULT_EXEC_SLA_MIN = 30

#: `read_position_facts` 的三种读结果（写进 evidence，供复核/统计）
POSITION_READ_OK = 'ok'
POSITION_READ_MISSING = 'missing'
POSITION_READ_DEGRADED = 'degraded'

_POSITION_READ_STATES = (POSITION_READ_OK, POSITION_READ_MISSING, POSITION_READ_DEGRADED)


class ExecAction(str, Enum):
    """执行动作（指令卡的 `action` 字段；只有退出类意图才有可执行动作）。"""

    EXECUTE_STOP_LOSS = 'execute_stop_loss'
    EXECUTE_TAKE_PROFIT = 'execute_take_profit'
    EXECUTE_REDUCE = 'execute_reduce'
    #: 非退出类意图（观察 / 建仓 / 加仓 / 做T）：**不产出执行指令**，如实标 none
    NONE = 'none'


class ExecSide(str, Enum):
    """买卖方向。指令卡只表达卖出侧（入场永远是通知制，RFC §2.4）。"""

    SELL = 'sell'
    NONE = 'none'


class NotExecutableReason(str, Enum):
    """不可执行原因（结构化枚举；渲染文案由它派生，不落库自由文本）。"""

    ACCOUNT_UNKNOWN = 'account_unknown'   # 无归属账户：数据缺陷，先补 linked_account
    NO_POSITION = 'no_position'           # 确认无持仓
    T1_LOCKED = 't1_locked'               # 有持仓但可卖为 0（T+1）
    NOT_EXIT_INTENT = 'not_exit_intent'   # 非退出类意图，本就没有执行指令


class ExecState(str, Enum):
    """三态闭环的「态」（RFC §2.1.3：执行 / 不执行 / 超时）。"""

    EXECUTED = 'executed'
    DECLINED = 'declined'
    TIMEOUT = 'timeout'


class TodoTerminal(str, Enum):
    """已有待办终态枚举（**不新增枚举**，RFC §4 第 5 条）。

    注意：`expired` 故意不在本枚举里——超时是**状态不是终态**，把敞着钱的止损记成
    「已处理」是 RFC 明令禁止的（§2.1.3）。
    """

    HANDLED = 'handled'
    IGNORED = 'ignored'


class TodoActionKind(str, Enum):
    """已有待办 action_kind 白名单里与本闭环相关的两个值。"""

    TRADE = 'trade'
    RULE_CHANGE = 'rule_change'


#: 意图 → 执行动作（唯一映射表；非退出类一律 NONE）
EXIT_ACTION_BY_INTENT: Dict[str, ExecAction] = {
    'exit_stop': ExecAction.EXECUTE_STOP_LOSS,
    'exit_take_profit': ExecAction.EXECUTE_TAKE_PROFIT,
    'exit_reduce': ExecAction.EXECUTE_REDUCE,
}

#: 执行动作 → 中文动词（渲染用，单一副本）
_ACTION_LABELS: Dict[ExecAction, str] = {
    ExecAction.EXECUTE_STOP_LOSS: '立即止损卖出',
    ExecAction.EXECUTE_TAKE_PROFIT: '止盈卖出',
    ExecAction.EXECUTE_REDUCE: '减仓卖出',
    ExecAction.NONE: '',
}

#: 三态 → 中文短标签（渲染用）
_STATE_LABELS: Dict[ExecState, str] = {
    ExecState.EXECUTED: '执行',
    ExecState.DECLINED: '不执行',
    ExecState.TIMEOUT: '超时',
}


@dataclass(frozen=True)
class PositionFacts:
    """持仓真值（唯一 I/O 的产物：`read_position_facts`）。

    `shares_available` 才是可卖量（T+1），**不是** `shares_total`——用错会把
    「持仓 1000、今日可卖 0」写成「可卖 1000」，等于教 agent 下必然被拒的单
    （RFC §2.1.2）。
    """

    shares_total: int = 0
    shares_available: int = 0
    avg_cost: Optional[float] = None


@dataclass(frozen=True)
class DispositionAction:
    """三态处置动作项（**结构化枚举，不是自由文本**）。

    三态的映射（RFC §2.1.3，全部落在既有 todo 枚举上）：

    | state    | terminal | action_kind | 额外要求 |
    |----------|----------|-------------|----------|
    | executed | handled  | trade       | 决策审计 |
    | declined | ignored  | rule_change | 决策审计 + 下次条件（DB CHECK 强制） |
    | timeout  | None     | None        | escalate（L3 催办；**不写 expired**） |
    """

    state: ExecState
    terminal: Optional[TodoTerminal]
    action_kind: Optional[TodoActionKind]
    requires_decision_audit: bool = False
    requires_next_condition: bool = False
    escalate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe 投影（枚举 → 值；None 如实保留）。"""
        return {
            'state': self.state.value,
            'terminal': self.terminal.value if self.terminal is not None else None,
            'action_kind': self.action_kind.value if self.action_kind is not None else None,
            'requires_decision_audit': self.requires_decision_audit,
            'requires_next_condition': self.requires_next_condition,
            'escalate': self.escalate,
        }


def default_action_items() -> Tuple[DispositionAction, ...]:
    """三态处置动作项（顺序 = 执行 / 不执行 / 超时；纯值，进程内可共享）。"""
    return (
        DispositionAction(
            state=ExecState.EXECUTED,
            terminal=TodoTerminal.HANDLED,
            action_kind=TodoActionKind.TRADE,
            requires_decision_audit=True,
        ),
        DispositionAction(
            state=ExecState.DECLINED,
            terminal=TodoTerminal.IGNORED,
            action_kind=TodoActionKind.RULE_CHANGE,
            requires_decision_audit=True,
            requires_next_condition=True,
        ),
        DispositionAction(
            state=ExecState.TIMEOUT,
            terminal=None,          # 超时是状态不是终态（绝不写 expired）
            action_kind=None,
            escalate=True,
        ),
    )


def render_action_item(item: DispositionAction) -> str:
    """单条处置动作项 → 一句人话（**由枚举派生**，payload 不存这段文本）。"""
    label = _STATE_LABELS[item.state]
    if item.terminal is None:
        return '%s→不落终态（L3 催办，不写 expired）' % label
    bits = ['%s→%s' % (label, item.terminal.value)]
    if item.action_kind is not None:
        bits.append(item.action_kind.value)
    if item.requires_decision_audit:
        bits.append('需决策审计')
    if item.requires_next_condition:
        bits.append('需下次条件')
    return '%s（%s）' % (bits[0], '，'.join(bits[1:]))


@dataclass(frozen=True)
class ExecDirective:
    """单条 P0 触发对应的执行指令（通知与待办的同一事实源）。"""

    action: ExecAction
    symbol: str
    intent: str
    level: Optional[str] = None
    account: Optional[str] = None
    side: ExecSide = ExecSide.NONE
    qty: Optional[int] = None
    ref_price: Optional[float] = None
    trigger_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    executable: bool = False
    not_executable_reason: Optional[NotExecutableReason] = None
    deadline_at: Optional[datetime] = None
    #: 执行期限分钟数（与 deadline_at 同源；渲染「期限 N 分钟」时不依赖当前时钟）
    sla_minutes: Optional[int] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    action_items: Tuple[DispositionAction, ...] = field(default_factory=default_action_items)
    rule_id: Optional[int] = None
    trigger_id: Optional[int] = None
    todo_id: Optional[int] = None

    # ── 溯源 id 回填（构造时触发/待办还不存在；同一血缘只做 replace）──────
    def with_ids(self, *, trigger_id: Any = None, todo_id: Any = None) -> 'ExecDirective':
        """回填触发/待办 id（未给的维度保持原值）。"""
        kwargs: Dict[str, Any] = {}
        if trigger_id is not None:
            kwargs['trigger_id'] = trigger_id
        if todo_id is not None:
            kwargs['todo_id'] = todo_id
        return replace(self, **kwargs) if kwargs else self

    # ── 序列化（payload）────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        """结构化 payload（JSON-safe）：动作项是枚举值，不是文案。"""
        return {
            'action': self.action.value,
            'symbol': self.symbol,
            'intent': self.intent,
            'level': self.level,
            'account': self.account,
            'side': self.side.value,
            'qty': self.qty,
            'ref_price': self.ref_price,
            'trigger_price': self.trigger_price,
            'pnl_pct': self.pnl_pct,
            'executable': self.executable,
            'not_executable_reason': (self.not_executable_reason.value
                                      if self.not_executable_reason is not None else None),
            'deadline_at': (self.deadline_at.isoformat()
                            if self.deadline_at is not None else None),
            'sla_minutes': self.sla_minutes,
            'evidence': dict(self.evidence),
            'action_items': [item.to_dict() for item in self.action_items],
            'rule_id': self.rule_id,
            'trigger_id': self.trigger_id,
            'todo_id': self.todo_id,
        }

    # ── 渲染（通知侧；文案由枚举/字段派生，不参与比较/落库）──────────────
    def card_action_text(self) -> str:
        """P0 卡「下一步」用的执行指令（一句话，缺数据如实标注）。"""
        if self.action is ExecAction.NONE:
            return ('ℹ️ 非退出类触发（意图 %s）：不产出执行指令，按规则指引处置'
                    % (self.intent or '未知'))
        if not self.executable:
            return self._blocked_text()
        bits = [_ACTION_LABELS[self.action]]
        if self.qty is not None:
            qty_text = '%s 可卖 %d 股（T+1）' % (self.symbol, self.qty)
            total = self.evidence.get('shares_total')
            if isinstance(total, int) and total > self.qty:
                # 部分可卖：清仓要分两天，如实说清余量（禁止把「今天能卖」说成「已清仓」）
                qty_text += '，持仓 %d 股（余 %d 股待 T+1 解锁）' % (total, total - self.qty)
            bits.append(qty_text)
        else:
            bits.append('%s 可卖量待核实（持仓读失败）' % self.symbol)
        if self.ref_price is not None:
            price = '参考价 ¥%.2f' % float(self.ref_price)
            if self.pnl_pct is not None:
                price += '（浮%+.2f%%）' % float(self.pnl_pct)
            bits.append(price)
        bits.append('期限 %d 分钟内成交'
                    % int(self.sla_minutes or exec_sla_minutes()))
        return ' · '.join(bits)

    def _blocked_text(self) -> str:
        reason = self.not_executable_reason
        if reason is NotExecutableReason.ACCOUNT_UNKNOWN:
            return ('⚠️ 执行指令不可下达：规则未归属账户（先补 linked_account）· '
                    '勿重试下单，判不动则 ignored + 下次条件')
        if reason is NotExecutableReason.NO_POSITION:
            return ('✅ 无需执行：%s 已无可卖持仓 · 按对账收敛（reconciled:no_position），'
                    '不重复卖出' % self.symbol)
        if reason is NotExecutableReason.T1_LOCKED:
            return ('⏳ 今日不可执行：%s 可卖 0 股（T+1 锁仓，持仓 %s 股）· '
                    '报「今日不可执行」并给下次条件，勿重试下单'
                    % (self.symbol, self.evidence.get('shares_total', 0)))
        if reason is NotExecutableReason.NOT_EXIT_INTENT:
            return 'ℹ️ 非退出类触发（意图 %s）：不产出执行指令' % (self.intent or '未知')
        return '⚠️ 执行指令不可用'

    def card_guide_text(self) -> str:
        """三态处置指引（由 `action_items` 枚举派生，顺序即 action_items 顺序）。"""
        return '三态处置：' + '；'.join(render_action_item(i) for i in self.action_items)

    def card_context(self, plan: Optional[str] = None) -> str:
        """并入「预案」段的指令正文：原预案 + 执行闭环三态。

        预案是规则写的（可能为空）；指令三态是引擎机械结论，必须始终可见。
        """
        parts = [str(plan).strip()] if str(plan or '').strip() else []
        parts.append(self.card_guide_text())
        return '\n'.join(parts)

    def action_params(self) -> Optional[Dict[str, Any]]:
        """结构化动作块（渲染层 `resolve_action` 吃 action/quantity/reference_price）。

        不可执行时返回 None（规则自己的 action_params 继续生效，不拿残缺指令顶替）。
        """
        if self.action is ExecAction.NONE or not self.executable:
            return None
        params: Dict[str, Any] = {
            'action': self.side.value,
            'exec_action': self.action.value,
        }
        if self.qty is not None:
            params['quantity'] = int(self.qty)
        if self.ref_price is not None:
            params['reference_price'] = round(float(self.ref_price), 2)
        if self.deadline_at is not None:
            params['exec_deadline_at'] = self.deadline_at.isoformat()
        return params


def exec_sla_minutes(environ: Optional[Dict[str, str]] = None) -> int:
    """执行收敛期限（分钟）：`WATCH_EXEC_SLA_MIN`，非法/缺省 → 30。"""
    env = os.environ if environ is None else environ
    raw = str(env.get(EXEC_SLA_ENV) or '').strip()
    if not raw:
        return DEFAULT_EXEC_SLA_MIN
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return DEFAULT_EXEC_SLA_MIN
    return value if value >= 1 else DEFAULT_EXEC_SLA_MIN


def action_for_intent(intent: Optional[str]) -> ExecAction:
    """意图 → 执行动作（表驱动；未知/非退出类 → NONE）。"""
    return EXIT_ACTION_BY_INTENT.get(str(intent or '').strip(), ExecAction.NONE)


def is_exec_directive_intent(intent: Optional[str]) -> bool:
    """该意图是否会产出执行指令（= 退出类三兄弟：止损 / 止盈 / 减仓）。"""
    return action_for_intent(intent) is not ExecAction.NONE


def build_exec_directive(
    *,
    rule: Any,
    level: Optional[str],
    now: datetime,
    trigger_price: Optional[float] = None,
    intent: Optional[str] = None,
    account: Optional[str] = None,
    position: Optional[PositionFacts] = None,
    position_read: str = POSITION_READ_OK,
    condition: Optional[str] = None,
    distance_ratio: Optional[float] = None,
    sla_minutes: Optional[int] = None,
    trigger_id: Optional[int] = None,
    todo_id: Optional[int] = None,
) -> ExecDirective:
    """构造单条执行指令（**纯函数**：不查库、不发送、不下单）。

    Args:
        rule: 规则对象（只读 `symbol` / `intent` / `cost_price` / 账户字段）。
        level: 触发级别（P0 才在流水线里构造；缺省如实留 None）。
        now: 判定时刻（执行期限 = now + SLA）。
        trigger_price: 触发时价格。
        intent: 显式意图；缺省按 `disposition.intent_of(rule)` 推导（与分级/处置同源）。
        account: 显式账户；缺省按 `rule_guard.effective_account`（linked_account 优先）。
        position: 持仓真值（`read_position_facts` 的产物）；None + `position_read='missing'`
            = 确认无持仓。
        position_read: `ok` / `missing` / `degraded`（见模块 docstring 的两面对称语义）。
        condition / distance_ratio: 判定依据（进 evidence，供复核）。
        sla_minutes: 执行期限分钟数；缺省读 `WATCH_EXEC_SLA_MIN`（默认 30）。
        trigger_id / todo_id: 溯源 id（构造时通常还没有，之后 `with_ids` 回填）。

    Returns:
        `ExecDirective`：动作 + 执行参数 + 三态处置动作项（结构化枚举）。

    「读不到持仓」的判定顺序（先结构后数值）：
        无账户 → account_unknown（读不到就别假装读过）
        读失败 → degraded（executable=True，交 agent 核实）
        无持仓 / 0 股 → no_position
        有总量但可卖 0 → t1_locked
    """
    read_state = str(position_read or POSITION_READ_OK).strip().lower()
    if read_state not in _POSITION_READ_STATES:
        raise ValueError('未知的持仓读取状态：%r（允许 %s）'
                         % (position_read, '/'.join(_POSITION_READ_STATES)))

    resolved_intent = str(intent or intent_of(rule) or '').strip()
    action = action_for_intent(resolved_intent)
    symbol = normalize_symbol(getattr(rule, 'symbol', ''))
    resolved_account = (effective_account(rule) if account is None
                        else (str(account).strip() or None))
    ref_price = _ref_price(rule, position)
    trigger_price = _as_float(trigger_price)
    pnl_pct = _pnl_pct(trigger_price, ref_price)
    evidence: Dict[str, Any] = {
        'condition': condition,
        'distance_ratio': distance_ratio,
        'level': str(level or '').strip().upper() or None,
        'intent': resolved_intent,
        'position_read': read_state,
        'shares_total': (int(position.shares_total) if position is not None else None),
        'shares_available': (int(position.shares_available) if position is not None else None),
        'trigger_price': trigger_price,
    }

    directive = ExecDirective(
        action=action,
        symbol=symbol,
        intent=resolved_intent,
        level=str(level or '').strip().upper() or None,
        account=resolved_account,
        side=ExecSide.NONE,
        qty=None,
        ref_price=ref_price,
        trigger_price=trigger_price,
        pnl_pct=pnl_pct,
        executable=False,
        evidence=evidence,
        rule_id=getattr(rule, 'id', None),
        trigger_id=trigger_id,
        todo_id=todo_id,
    )

    if action is ExecAction.NONE:
        return replace(directive, not_executable_reason=NotExecutableReason.NOT_EXIT_INTENT)

    directive = replace(directive, side=ExecSide.SELL)
    sla = (sla_minutes if isinstance(sla_minutes, int) and sla_minutes >= 1
           else exec_sla_minutes())
    directive = replace(directive, sla_minutes=int(sla))

    if not resolved_account:
        return replace(directive,
                       not_executable_reason=NotExecutableReason.ACCOUNT_UNKNOWN)

    if read_state == POSITION_READ_DEGRADED:
        # 读失败 ≠ 没持仓：照喊、交 agent 核实（RFC §2.1.2）
        return replace(directive, executable=True, deadline_at=_deadline(now, sla))

    if position is None or int(position.shares_total) <= 0:
        return replace(directive, not_executable_reason=NotExecutableReason.NO_POSITION)

    if int(position.shares_available) <= 0:
        return replace(directive, not_executable_reason=NotExecutableReason.T1_LOCKED)

    return replace(directive, executable=True,
                   qty=int(position.shares_available),
                   deadline_at=_deadline(now, sla))


def _deadline(now: datetime, sla_minutes: int) -> datetime:
    return now + timedelta(minutes=int(sla_minutes))


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ref_price(rule: Any, position: Optional[PositionFacts]) -> Optional[float]:
    """参考价：规则成本价优先 → 持仓均价 → None（不臆造）。"""
    for candidate in (getattr(rule, 'cost_price', None),
                      None if position is None else position.avg_cost):
        value = _as_float(candidate)
        if value is not None and value > 0:
            return value
    return None


def _pnl_pct(trigger_price: Optional[float], ref_price: Optional[float]) -> Optional[float]:
    if trigger_price is None or not ref_price:
        return None
    return round((trigger_price - ref_price) / ref_price * 100.0, 2)


# ── 唯一的 I/O：持仓真值读取（失败 fail-open，绝不默认「没有持仓」）────────────

_POSITION_REPO = None


def _default_position_repo():
    """懒建持仓仓储（与 factory 的 position_value_provider 同一实现，不另造取数口径）。

    `adapters.outbound.repositories.simulation_*` 是 `qs_watch` 包边界里**暂留的 L1
    引用**（见 `packages/qs_watch/CLAUDE.md`「依赖边界」）：持仓/模拟账户仓储在
    trading 项目化时迁出，届时本函数改为端口注入即可，调用方（构建器）不感知。
    """
    global _POSITION_REPO
    if _POSITION_REPO is None:
        from adapters.outbound.repositories.simulation_position_repository import (
            SimulationPositionRepository,
        )
        _POSITION_REPO = SimulationPositionRepository()
    return _POSITION_REPO


def read_position_facts(
    account: Optional[str],
    symbol: Optional[str],
    *,
    repo: Any = None,
) -> Tuple[Optional[PositionFacts], str]:
    """读取持仓真值（`shares_available` 为可卖量）。

    Returns:
        `(PositionFacts | None, read_state)`，read_state ∈ `ok` / `missing` / `degraded`：
          · 无账户 → `(None, 'degraded')`——**不能**说是「没持仓」，调用方应据此走
            account_unknown 分支（build 里先判账户，故此返回值只作兜底）；
          · 读到零持仓 → `(None, 'missing')`；
          · 读异常 → `(None, 'degraded')`（fail-open；RFC §2.1.2）。
    """
    acct = str(account or '').strip()
    sym = normalize_symbol(symbol)
    if not acct or not sym:
        return None, POSITION_READ_DEGRADED
    try:
        reader = repo if repo is not None else _default_position_repo()
        pos = reader.get_position(acct, sym)
    except Exception:  # noqa: BLE001 - 读失败 fail-open，由 evidence 如实标注 degraded
        return None, POSITION_READ_DEGRADED
    if pos is None:
        return None, POSITION_READ_MISSING
    try:
        return PositionFacts(
            shares_total=int(getattr(pos, 'shares_total', 0) or 0),
            shares_available=int(getattr(pos, 'shares_available', 0) or 0),
            avg_cost=_as_float(getattr(pos, 'avg_cost', None)),
        ), POSITION_READ_OK
    except (TypeError, ValueError):
        return None, POSITION_READ_DEGRADED
