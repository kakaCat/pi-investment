"""成交回执同步（RFC 017 §2.1.4，卡 `fill-event-sync`，2026-10-21）

解决什么：执行闭环的最后一环——P0 止损指令发出去了、agent 也卖了，但**没有任何代码
回头收敛 watch 侧**：待办永远挂着、止损规则还在盯一个已经没有立场的标的、
`position_state` 停在旧值，只能等 L3 一轮轮催人或 agent 记得手动 close。

本服务是 trading 成交事实的**唯一消费点**（端口 `IFillListener` 定义在 trading 侧的
`application/trading/paper_trading_engine.py`，实现落在这里）：

  ① 成交 → 持仓状态翻转（`position_state`：`>0` holding / `=0` none，作用于该
     `(账户, 标的)` 的全部规则）；
  ② 卖出且该标的剩余持仓为 0 → 未收敛 **P0 执行待办**收敛为 `handled`
     （`action_kind='trade'` + 可核验 `decision_audit_id`）；
  ③ 触发收敛（`watch_triggers.disposition='handled'`）并把执行时延
     `{trade_id, price, latency_sec, source}` 合并进 `detail.exec`（**只写一次**）；
  ④ 该标的 `exit_*` 族规则即时退役（复用 `PositionLifecycleService._retire` 语义）。

五条纪律（逐条对应验收）：

1. **任何来源的卖出成交都收敛**：watch 指令 / IntradayMonitor 兜底 / 人工卖出
   在成交事实上没有区别——`source` 只进留痕（`close_reason` + `detail.exec`），
   **不作为收敛判据**。
2. **部分成交不算执行**：卖出后仍有持仓 → 待办保持未收敛，只回 `status='partial'`。
3. **幂等**：待办已终态（`TodoService.close` 抛 `WatchTodoAlreadyClosed`）→ 跳过，
   不二次收敛；`detail.exec` 已存在 → 不二次写时延（重复事件不留第二种时延）。
4. **读不到持仓就什么都不做**（fail-closed）：与 `exec_directive.read_position_facts`
   同一 I/O 口径；`degraded` 时**绝不**把数据故障写成「已清仓」（那会退役真实持仓的
   止损规则，等于亲手拆保护网）。
5. **绝不抛错**：每个阶段独立 try/except，异常只进 `errors` 并记日志；trading 侧还会
   再包一层 try/except。**成交落库永远不受回执影响**。

组合根装配（一行，幂等；`watch_bootstrap` 里调用即可，未装配 = 引擎照常跑）：

    from qs_watch.application.services.watch_engine.fill_sync_service import (
        register_fill_listener,
    )
    register_fill_listener()

依赖方向：`qs_watch → trading` 单向（RFC §4.2）。本模块**不 import** trading 的实现，
只在 `_default_registrar()` 内惰性取 trading 侧的注册函数，避免把交易引擎拖进 watch
的 import 图。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

import structlog

from qs_watch.application.services.watch_engine.exec_directive import (
    POSITION_READ_DEGRADED,
    POSITION_READ_MISSING,
    POSITION_READ_OK,
    read_position_facts,
)
from qs_watch.application.services.watch_engine.position_lifecycle_service import (
    PositionLifecycleService,
)
from qs_watch.domain.watch.ports import WatchTodoAlreadyClosed
from qs_watch.domain.watch.services.disposition import normalize_symbol
from qs_watch.domain.watch.services.rule_guard import effective_account

logger = structlog.get_logger(__name__)

#: 待办扫描上限（P0 未收敛待办通常个位数；给足余量但不做全表拉取）
DEFAULT_TODO_SCAN_LIMIT = 200

#: 执行待办的两个口径（只对「P0 + trade」收敛；rule_change/observe 不属执行闭环）
_EXEC_LEVEL = 'P0'
_EXEC_ACTION_KIND = 'trade'

#: 成交动作（只认这两个；其它一律视为坏事件，不猜）
_ACTIONS = ('buy', 'sell')


# ── 小工具（纯函数，便于单测）─────────────────────────────────────────────

def _field(source: Any, name: str, default: Any = None) -> Any:
    """统一读字段：事件既可能是 trading 侧的 `FillEvent`（对象），也可能是 dict。"""
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_naive(value: Any) -> Optional[datetime]:
    """datetime / ISO 字符串 → naive datetime（None 透传）。

    触发时刻（`watch_triggers.triggered_at`）是 naive，`filled_at` 可能带时区：
    统一剥掉 tzinfo 再相减，避免 aware/naive 相减直接 TypeError。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        except ValueError:
            return None
        return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
    return None


def latency_seconds(filled_at: Any, started_at: Any) -> Optional[float]:
    """执行时延（秒，1 位小数）：成交时刻 - 触发/建单时刻；缺失返回 None。

    负值（时钟回拨/数据错位）按 0 记并留日志——时延是观测量，不拿它做判定。
    """
    filled = _as_naive(filled_at)
    started = _as_naive(started_at)
    if filled is None or started is None:
        return None
    delta = (filled - started).total_seconds()
    if delta < 0:
        logger.warning('执行时延为负（时钟/数据错位，按 0 记）',
                       filled_at=filled.isoformat(), started_at=started.isoformat())
        delta = 0.0
    return round(delta, 1)


def _normalize_event(event: Any) -> Optional[Dict[str, Any]]:
    """事件归一（不猜）：缺账户/标的/动作 → None，调用方按坏事件处理。"""
    symbol = normalize_symbol(_field(event, 'symbol'))
    account = str(_field(event, 'account_name', None)
                  or _field(event, 'account', None) or '').strip()
    action = str(_field(event, 'action', '') or '').strip().lower()
    if not symbol or not account or action not in _ACTIONS:
        return None
    audit = _field(event, 'decision_audit_id', None)
    trade_id = _field(event, 'trade_id', None)
    order_id = _field(event, 'order_id', None)
    return {
        'account': account,
        'symbol': symbol,
        'action': action,
        'shares': _as_int(_field(event, 'shares', 0)),
        'price': _as_float(_field(event, 'price', 0.0)),
        'trade_id': _as_int(trade_id) if trade_id is not None else None,
        'order_id': _as_int(order_id) if order_id is not None else None,
        'decision_audit_id': (str(audit).strip() or None) if audit is not None else None,
        'filled_at': _as_naive(_field(event, 'filled_at', None)) or datetime.now(),
        'source': str(_field(event, 'source', None) or 'unknown').strip(),
        'reason': _field(event, 'reason', None),
    }


class FillSyncService:
    """成交回执同步服务（实现 trading 侧 `IFillListener` 的 `on_fill`）。

    构造参数全部端口注入（不在这里 new 仓储，组合根负责装配）：

    Args:
        rule_repo: `IWatchRuleRepository`（读 `list_rules`，写 `set_position_state`/
            `update_fields`）——持仓状态与规则退役都经它。
        todo_service: `TodoService`（首选；close 带终态/审计校验与幂等语义）。
        todo_repo: 未注入 `todo_service` 时的退路（`list_pending`/`close`）。
        trigger_repo: `WatchTriggerRepository`（`get_by_id` / `update` /
            `update_disposition`）；缺省则跳过 trigger 侧的处置与时延落账（只做
            待办与规则收敛，如实回报 `detail_written=False`）。
        position_repo: 持仓真值读口（`get_position(account, symbol)`）；
            缺省走 `exec_directive._default_position_repo()`（与 P0 指令卡同一实现）。
        lifecycle: `PositionLifecycleService`（复用 `_retire` 语义）；缺省惰性构造。
        todo_scan_limit: 未收敛待办扫描上限。
        now_fn: 时钟注入（测试用；缺省 `datetime.now`）。
    """

    def __init__(
        self,
        *,
        rule_repo: Any,
        todo_service: Any = None,
        todo_repo: Any = None,
        trigger_repo: Any = None,
        position_repo: Any = None,
        lifecycle: Any = None,
        todo_scan_limit: int = DEFAULT_TODO_SCAN_LIMIT,
        now_fn: Any = None,
    ):
        self.rule_repo = rule_repo
        self.todo_service = todo_service
        self.todo_repo = todo_repo
        self.trigger_repo = trigger_repo
        self.position_repo = position_repo
        self.lifecycle = lifecycle
        self.todo_scan_limit = int(todo_scan_limit or DEFAULT_TODO_SCAN_LIMIT)
        self._now = now_fn or datetime.now

    # ── 端口入口（IFillListener.on_fill）────────────────────────────────

    def on_fill(self, event: Any) -> Dict[str, Any]:
        """成交事件入口：**永不抛错**，返回结构化结果供日志/回执/单测断言。"""
        try:
            fill = _normalize_event(event)
        except Exception as e:  # noqa: BLE001 - 坏事件不得打挂调用方
            logger.error('成交事件解析异常（回执跳过）', error=str(e))
            return {'event': 'fill_sync', 'status': 'invalid', 'errors': [str(e)]}
        if fill is None:
            logger.warning('成交事件字段不全（缺账户/标的/动作），跳过同步（不自造事实）',
                           raw=_safe_repr(event))
            return {'event': 'fill_sync', 'status': 'invalid',
                    'errors': ['缺 account_name/symbol 或 action 不在 buy/sell']}

        errors: List[str] = []
        result: Dict[str, Any] = {
            'event': 'fill_sync',
            'account': fill['account'],
            'symbol': fill['symbol'],
            'action': fill['action'],
            'shares': fill['shares'],
            'price': fill['price'],
            'trade_id': fill['trade_id'],
            'source': fill['source'],
        }
        try:
            result.update(self._sync(fill, errors))
        except Exception as e:  # noqa: BLE001 - 兜底：成交已落库，回执失败只记日志
            logger.error('成交回执同步异常（成交已落库，不影响成交）',
                         account=fill['account'], symbol=fill['symbol'],
                         trade_id=fill['trade_id'], error=str(e))
            errors.append('sync: %s' % e)
            result['status'] = 'error'
        result['errors'] = errors
        return result

    # ── 主流程（每个阶段独立兜底）──────────────────────────────────────

    def _sync(self, fill: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
        # 结果形状固定（每个分支都带全量键，消费方无需按 status 猜字段）
        out: Dict[str, Any] = {
            'status': 'ok',
            'position_read': None,
            'position_state': None,
            'shares_total': None,
            'rules_updated': [],
            'converged_todos': [],
            'latency_sec': None,
            'detail_written': False,
            'audit_degraded': False,
            'retired_rules': [],
        }
        position, read_state = self._read_position(fill)
        out['position_read'] = read_state

        # fail-closed：读不到持仓绝不翻转状态（数据故障 ≠ 已清仓）
        if read_state != POSITION_READ_OK and read_state != POSITION_READ_MISSING:
            logger.warning('持仓真值读取失败：本次不翻转状态、不收敛待办（fail-closed）',
                           account=fill['account'], symbol=fill['symbol'],
                           action=fill['action'], trade_id=fill['trade_id'])
            out['status'] = 'degraded'
            return out

        shares_total = int(getattr(position, 'shares_total', 0) or 0)
        new_state = 'holding' if shares_total > 0 else 'none'
        out['position_state'] = new_state
        out['shares_total'] = shares_total
        out['rules_updated'] = self._sync_position_state(fill, new_state, errors)

        # 买入只翻状态（建仓 → holding）；收敛/退役只在卖出侧
        if fill['action'] != 'sell':
            out['status'] = 'ok'
            return out

        if shares_total > 0:
            # 部分成交不算执行（RFC §2.1：待办保持未收敛，只记 progress）
            logger.info('卖出后仍有持仓：待办不收敛（部分成交不算执行）',
                        account=fill['account'], symbol=fill['symbol'],
                        shares_total=shares_total, trade_id=fill['trade_id'])
            out['status'] = 'partial'
            return out

        converged, latency, detail_written, audit_degraded = self._converge(fill, errors)
        out['converged_todos'] = converged
        out['latency_sec'] = latency
        out['detail_written'] = detail_written
        out['audit_degraded'] = audit_degraded
        out['retired_rules'] = self._retire_exit_rules(fill, errors)
        out['status'] = 'executed' if converged else 'converged_no_todo'
        return out

    # ── ① 持仓状态翻转 ───────────────────────────────────────────────

    def _read_position(self, fill: Dict[str, Any]) -> Tuple[Any, str]:
        try:
            return read_position_facts(fill['account'], fill['symbol'],
                                       repo=self.position_repo)
        except Exception as e:  # noqa: BLE001 - read_position_facts 自己兜底，这里双保险
            logger.error('持仓真值读取异常（fail-closed）',
                         account=fill['account'], symbol=fill['symbol'], error=str(e))
            return None, POSITION_READ_DEGRADED

    def _rules_of(self, fill: Dict[str, Any]) -> List[Any]:
        """该 `(账户, 标的)` 的规则（账户取 effective_account，空账户规则不在作用域）。"""
        try:
            rules = self.rule_repo.list_rules() or []
        except Exception as e:  # noqa: BLE001 - 失败由调用方记入 errors
            raise RuntimeError('规则读取失败: %s' % e) from e
        out: List[Any] = []
        for rule in rules:
            if normalize_symbol(getattr(rule, 'symbol', '')) != fill['symbol']:
                continue
            rule_account = str(effective_account(rule) or '').strip()
            # 无账户的是观察规则：成交无法证明它的立场已结束 → 不写它的状态
            if not rule_account or rule_account != fill['account']:
                continue
            out.append(rule)
        return out

    def _sync_position_state(self, fill: Dict[str, Any], new_state: str,
                             errors: List[str]) -> List[Any]:
        try:
            rules = self._rules_of(fill)
        except Exception as e:  # noqa: BLE001
            errors.append('rules_read: %s' % e)
            logger.error('规则读取失败：持仓状态未同步（回执继续）',
                         account=fill['account'], symbol=fill['symbol'], error=str(e))
            return []
        updated: List[Any] = []
        for rule in rules:
            current = str(getattr(rule, 'position_state', None) or '').strip().lower()
            if current == new_state:
                continue
            try:
                self.rule_repo.set_position_state(getattr(rule, 'id', None), new_state)
                updated.append(getattr(rule, 'id', None))
            except Exception as e:  # noqa: BLE001 - 单条失败不影响其余规则
                errors.append('position_state[%s]: %s' % (getattr(rule, 'id', None), e))
                logger.error('持仓状态写入失败', rule_id=getattr(rule, 'id', None),
                             symbol=fill['symbol'], error=str(e))
        if updated:
            logger.info('持仓状态已翻转', account=fill['account'], symbol=fill['symbol'],
                        position_state=new_state, rule_ids=updated)
        return updated

    # ── ② 执行待办收敛 + ③ 触发处置/时延 ──────────────────────────────

    def _open_exec_todos(self, fill: Dict[str, Any], errors: List[str]) -> List[Any]:
        """该 `(账户, 标的)` 未收敛的 **P0 执行**待办（trade；空账户按数据缺陷一并收敛）。"""
        try:
            rows = self._list_pending()
        except Exception as e:  # noqa: BLE001 - 读失败如实记 errors，不静默当"没有待办"
            errors.append('todo_read: %s' % e)
            logger.error('未收敛待办读取失败（收敛跳过，成交已落库）',
                         account=fill['account'], symbol=fill['symbol'], error=str(e))
            raise
        out: List[Any] = []
        for todo in rows or []:
            if str(getattr(todo, 'terminal', '') or '').strip():
                continue
            if normalize_symbol(getattr(todo, 'symbol', '')) != fill['symbol']:
                continue
            level = str(getattr(todo, 'level', '') or '').strip().upper()
            if level and level != _EXEC_LEVEL:
                continue
            kind = str(getattr(todo, 'action_kind', '') or '').strip().lower()
            if kind and kind != _EXEC_ACTION_KIND:
                continue
            account = str(getattr(todo, 'account', '') or '').strip()
            if account and account != fill['account']:
                continue
            out.append(todo)
        return out

    def _list_pending(self) -> List[Any]:
        if self.todo_service is not None:
            return list(self.todo_service.list(level=_EXEC_LEVEL,
                                               limit=self.todo_scan_limit) or [])
        if self.todo_repo is not None:
            return list(self.todo_repo.list_pending(level=_EXEC_LEVEL,
                                                    limit=self.todo_scan_limit) or [])
        return []

    def _converge(self, fill: Dict[str, Any],
                  errors: List[str]) -> Tuple[List[Any], Optional[float], bool, bool]:
        """清仓收敛：关闭执行待办 + 触发 handled + 时延落 detail（幂等）。"""
        converged: List[Any] = []
        latency: Optional[float] = None
        detail_written = False
        audit_degraded = False
        try:
            todos = self._open_exec_todos(fill, errors)
        except Exception:
            return converged, latency, detail_written, audit_degraded
        if not todos:
            logger.info('清仓成交但无未收敛执行待办（人工/兜底卖出同口径）',
                        account=fill['account'], symbol=fill['symbol'],
                        source=fill['source'], trade_id=fill['trade_id'])
            return converged, latency, detail_written, audit_degraded

        for todo in todos:
            todo_id = getattr(todo, 'id', None)
            audit_id = fill['decision_audit_id']
            if not audit_id:
                # 拿不到决策审计号：退化为成交标记（如实标 audit_degraded，不虚报审计）
                audit_degraded = True
                audit_id = self._degraded_audit_id(fill)
            reason = self._close_reason(fill)
            try:
                closed = self._close_todo(todo_id, reason, audit_id)
            except WatchTodoAlreadyClosed:
                logger.info('重复成交事件：执行待办已终态，跳过（幂等）',
                            todo_id=todo_id, trade_id=fill['trade_id'])
                continue
            except Exception as e:  # noqa: BLE001 - 单条失败不影响其余待办
                errors.append('todo_close[%s]: %s' % (todo_id, e))
                logger.error('执行待办关闭失败（成交已落库）', todo_id=todo_id,
                             trade_id=fill['trade_id'], error=str(e))
                continue
            if closed is None:
                logger.info('执行待办在关闭前已收敛（并发抢先），跳过',
                            todo_id=todo_id, trade_id=fill['trade_id'])
                continue
            converged.append(todo_id)
            written, seconds = self._record_exec_detail(todo, closed, fill,
                                                        audit_degraded, errors)
            detail_written = detail_written or written
            if seconds is not None:
                latency = seconds
        return converged, latency, detail_written, audit_degraded

    def _close_todo(self, todo_id: Any, reason: str, audit_id: str) -> Any:
        if self.todo_service is not None:
            return self.todo_service.close(
                todo_id, 'handled', close_reason=reason, action_kind=_EXEC_ACTION_KIND,
                decision_audit_id=audit_id, closed_by='fill_sync')
        if self.todo_repo is None:
            raise RuntimeError('未装配待办端口（todo_service/todo_repo 均为空）')
        closed = self.todo_repo.close(todo_id, 'handled', close_reason=reason,
                                      action_kind=_EXEC_ACTION_KIND,
                                      decision_audit_id=audit_id,
                                      closed_by='fill_sync')
        if closed is None:
            raise WatchTodoAlreadyClosed('待办 %s 已终态（仓储返回 None）' % todo_id)
        return closed

    def _degraded_audit_id(self, fill: Dict[str, Any]) -> str:
        if fill['trade_id'] is not None:
            return 'trade:%s' % fill['trade_id']
        return 'fill:%s' % (fill['filled_at'].isoformat() if fill['filled_at'] else 'unknown')

    @staticmethod
    def _close_reason(fill: Dict[str, Any]) -> str:
        """收敛原因（**记来源**：任何来源的卖出成交都收敛，来源只进留痕）。"""
        trade = (' #%s' % fill['trade_id']) if fill['trade_id'] is not None else ''
        return ('成交回执：%s 卖出成交%s（%d 股 @ ¥%.2f），持仓已清零 → 执行完成'
                % (fill['source'], trade, fill['shares'], fill['price']))

    def _record_exec_detail(self, todo: Any, closed: Any, fill: Dict[str, Any],
                            audit_degraded: bool,
                            errors: List[str]) -> Tuple[bool, Optional[float]]:
        """触发处置 handled + `detail.exec` 时延落账（只写一次）。"""
        repo = self.trigger_repo
        trigger_id = getattr(closed, 'trigger_id', None) or getattr(todo, 'trigger_id', None)
        if repo is None or trigger_id is None:
            logger.info('触发仓储未装配/无 trigger_id：跳过触发处置与时延落账',
                        todo_id=getattr(todo, 'id', None), trigger_id=trigger_id)
            return False, None

        trigger = None
        try:
            trigger = repo.get_by_id(trigger_id)
        except Exception as e:  # noqa: BLE001 - 读不到只降级，收敛已生效
            errors.append('trigger_read[%s]: %s' % (trigger_id, e))
            logger.warning('触发读取失败（时延落账降级）', trigger_id=trigger_id, error=str(e))

        started = getattr(trigger, 'triggered_at', None) if trigger is not None else None
        started = started or getattr(todo, 'created_at', None)
        seconds = latency_seconds(fill['filled_at'], started)

        patch = {
            'trade_id': fill['trade_id'],
            'price': fill['price'],
            'shares': fill['shares'],
            'latency_sec': seconds,
            'source': fill['source'],
            'filled_at': fill['filled_at'].isoformat() if fill['filled_at'] else None,
            'audit_degraded': bool(audit_degraded),
        }
        written = self._patch_detail(trigger_id, trigger, patch, errors)

        try:
            repo.update_disposition(
                trigger_id, 'handled',
                reason='executed: %s' % self._close_reason(fill),
                by='fill_sync')
        except Exception as e:  # noqa: BLE001 - 触发处置失败不影响待办收敛
            errors.append('trigger_disposition[%s]: %s' % (trigger_id, e))
            logger.error('触发处置回写失败（待办已收敛）', trigger_id=trigger_id, error=str(e))
        return written, seconds

    def _patch_detail(self, trigger_id: Any, trigger: Any, patch: Dict[str, Any],
                      errors: List[str]) -> bool:
        """把 `{...}` 合并进 `watch_triggers.detail.exec`（已有则跳过 = 时延只写一次）。

        仓储显式口径优先（`merge_detail` / `patch_detail`，未来适配器可无痛替换）；
        否则退回「读 ORM 对象 → 合并 → 通用 `update`」——与仓储其它方法同一事务口径，
        不引入裸 SQL（ADR-001：SQL 只在适配器层）。
        """
        repo = self.trigger_repo
        if repo is None or trigger_id is None:
            return False
        merge = getattr(repo, 'merge_detail', None) or getattr(repo, 'patch_detail', None)
        if callable(merge):
            try:
                merge(trigger_id, {'exec': dict(patch)})
                return True
            except Exception as e:  # noqa: BLE001 - 显式口径失败退回通用写入
                logger.warning('触发 detail 显式合并失败（退回通用 update）',
                               trigger_id=trigger_id, error=str(e))
        if trigger is None:
            return False
        detail = dict(getattr(trigger, 'detail', None) or {})
        if detail.get('exec'):
            logger.info('触发 detail.exec 已存在：不二次写时延（幂等）',
                        trigger_id=trigger_id)
            return False
        detail['exec'] = dict(patch)
        try:
            setattr(trigger, 'detail', detail)
        except Exception as e:  # noqa: BLE001 - 只读对象：交给仓储显式口径
            errors.append('trigger_detail_patch[%s]: %s' % (trigger_id, e))
            logger.error('触发 detail 合并失败', trigger_id=trigger_id, error=str(e))
            return False
        updater = getattr(repo, 'update', None)
        if not callable(updater):
            errors.append('trigger_detail_patch[%s]: 仓储无通用 update' % trigger_id)
            return False
        try:
            updater(trigger)
            return True
        except Exception as e:  # noqa: BLE001
            errors.append('trigger_detail_patch[%s]: %s' % (trigger_id, e))
            logger.error('触发 detail 落库失败（收敛已生效）',
                         trigger_id=trigger_id, error=str(e))
            return False

    # ── ④ exit 族即时退役 ─────────────────────────────────────────────

    def _retire_exit_rules(self, fill: Dict[str, Any], errors: List[str]) -> List[Any]:
        why = ('已清仓（%s 卖出成交%s），卖出规则族收摊；如需继续跟踪请另建观察规则'
               % (fill['source'],
                  (' #%s' % fill['trade_id']) if fill['trade_id'] is not None else ''))
        try:
            lifecycle = self.lifecycle or PositionLifecycleService(
                rule_repo=self.rule_repo, position_repo=self.position_repo,
                accounts=(fill['account'],))
            retired = lifecycle.retire_exit_rules(fill['account'], fill['symbol'], why)
        except Exception as e:  # noqa: BLE001 - 退役失败不拖垮回执
            errors.append('retire: %s' % e)
            logger.error('清仓退役失败（成交回执其余部分已生效）',
                         account=fill['account'], symbol=fill['symbol'], error=str(e))
            return []
        if retired:
            logger.info('清仓后卖出规则族已退役', account=fill['account'],
                        symbol=fill['symbol'], rule_ids=[r.get('rule_id') for r in retired])
        return list(retired or [])


def _safe_repr(value: Any, limit: int = 200) -> str:
    try:
        text = repr(value)
    except Exception:  # noqa: BLE001
        return '<unrepr>'
    return text[:limit]


# ── 组合根装配（一行，幂等）──────────────────────────────────────────────

#: 组合根注册后的单例（重复注册同一实例，避免多条回执各建一套仓储）
_FILL_SYNC_SERVICE: Optional[FillSyncService] = None


def build_fill_sync_service(**overrides: Any) -> FillSyncService:
    """按生产装配构造服务（仓储懒建，不在 import 期连库）。

    仓储经 DI 组合根（`_repo_resolver` 单点）装配；待办服务走
    `watch_loop_wiring.build_todo_service`（含 owner agent 派单），与生产装配同源。
    """
    from qs_watch.application.services.watch_engine._repo_resolver import (
        sim_position_repo,
        watch_rule_repo,
        watch_trigger_repo,
    )
    from qs_watch.application.services.watch_engine.watch_loop_wiring import (
        build_todo_service,
    )

    rule_repo = overrides.pop('rule_repo', None) or watch_rule_repo()
    position_repo = overrides.pop('position_repo', None) or sim_position_repo()
    lifecycle = overrides.pop('lifecycle', None) or PositionLifecycleService(
        rule_repo=rule_repo, position_repo=position_repo)
    return FillSyncService(
        rule_repo=rule_repo,
        todo_service=overrides.pop('todo_service', None) or build_todo_service(),
        trigger_repo=overrides.pop('trigger_repo', None) or watch_trigger_repo(),
        position_repo=position_repo,
        lifecycle=lifecycle,
        **overrides,
    )


def _default_registrar() -> Any:
    """trading 侧的注册函数（惰性 import：不让 watch 的 import 图拖进交易引擎）。"""
    from application.trading.paper_trading_engine import (
        register_fill_listener as _trading_register,
    )
    return _trading_register


def register_fill_listener(service: Optional[FillSyncService] = None, *,
                           registrar: Any = None) -> Optional[FillSyncService]:
    """组合根注册（幂等）：把本服务挂到 trading 侧的成交回调端口。

    用法（`watch_bootstrap` / factory 一行）::

        from qs_watch.application.services.watch_engine.fill_sync_service import (
            register_fill_listener,
        )
        register_fill_listener()

    纪律：注册失败只记日志并返回 None——回执是闭环增益，**绝不阻断宿主启动**；
    重复调用复用同一实例（`_FILL_SYNC_SERVICE`），不会每次新建一套仓储。
    """
    global _FILL_SYNC_SERVICE
    try:
        svc = service or _FILL_SYNC_SERVICE or build_fill_sync_service()
        register = registrar or _default_registrar()
        register(svc)
    except Exception as e:  # noqa: BLE001 - 装配失败降级，宿主照常运行
        logger.error('成交回执监听器注册失败（引擎照常运行，回执暂不生效）',
                     error=str(e))
        return None
    _FILL_SYNC_SERVICE = svc
    logger.info('fill_sync_service_registered', service=type(svc).__name__)
    return svc


def get_fill_sync_service() -> Optional[FillSyncService]:
    """已注册的成交回执服务（未装配返回 None；统计/排障用）。"""
    return _FILL_SYNC_SERVICE
