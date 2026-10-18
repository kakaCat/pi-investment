"""缺指引规则补全闭环（REQ-261016155500-4f2a，2026-10-16）

编排：lint 命中（domain 纯判定 rule_lint.is_missing_guidance）→ 幂等建 P2 补全待办
（TodoService 唯一操作面）→ 交处置 agent 回填 action_params / intent / 变化判据。

幂等：同规则已有未收敛的「补全待办」（action_kind='rule_change' 且 trigger_id IS NULL，
与 meta_review 类 rule_change 待办区分）则跳过——重复调用/重复调度不产生重复待办。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from domain.watch.services.level_resolver import P2
from domain.watch.services.rule_lint import is_missing_guidance

logger = structlog.get_logger(__name__)

#: 补全待办的 action_kind（TODO_AUDIT_ACTION_KINDS 之一）：动的是规则本身。
BACKFILL_ACTION_KIND = 'rule_change'


def _p2_due(now: datetime):
    """P2 due：当日收盘（口径与 engine._todo_due 一致：CONTINUOUS_END，退化 15:00）；
    已过收盘退化为 now+1min，避免 due_at 落在过去被巡检立即晋升。"""
    try:
        from qs_trading.domain.trading.services.market_session_policy import CONTINUOUS_END as _close
    except Exception:  # noqa: BLE001 - 常量缺失时退回最简口径
        from datetime import time as _t
        _close = _t(15, 0)
    day_close = datetime.combine(now.date(), _close)
    due = day_close if day_close > now else now + timedelta(minutes=1)
    return due, max(1, int((due - now).total_seconds()))


class GuidanceBackfillService:
    """缺指引治理：lint 清单 + 幂等补全待办（无状态，依赖注入）"""

    def __init__(self, rule_repo: Any, todo_service: Any,
                 account_resolver: Any = None):
        self._rule_repo = rule_repo
        self._todo_service = todo_service
        #: 规则 → 账户（复用 rule_guard.effective_account 口径；缺省退回 rule.account）
        self._account_resolver = account_resolver

    # ── lint 清单 ──────────────────────────────────────────

    def missing_guidance_rules(self) -> List[Any]:
        return [r for r in self._rule_repo.list_rules(enabled=True)
                if is_missing_guidance(r)]

    # ── 幂等建待办 ──────────────────────────────────────────

    def _account_of(self, rule: Any) -> Optional[str]:
        if self._account_resolver is not None:
            try:
                return self._account_resolver(rule)
            except Exception:  # noqa: BLE001 - 解析失败退回字段值
                return getattr(rule, 'account', None)
        return getattr(rule, 'account', None)

    def ensure_todos(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """对 lint 命中逐条确保存在一条未收敛补全待办；返回 {created, skipped}。"""
        now = now or datetime.now()
        created, skipped = [], []
        for rule in self.missing_guidance_rules():
            open_todos = self._todo_service.list_open_by_rule(
                rule.id, action_kind=BACKFILL_ACTION_KIND, trigger_id_null=True)
            if open_todos:
                skipped.append({'rule_id': rule.id, 'symbol': rule.symbol,
                                'todo_id': open_todos[0].id})
                continue
            due_at, sla = _p2_due(now)
            todo = self._todo_service.create(
                rule.symbol, level=P2, sla_seconds=sla, due_at=due_at,
                account=self._account_of(rule), rule_id=rule.id,
                action_kind=BACKFILL_ACTION_KIND)
            created.append({'rule_id': rule.id, 'symbol': rule.symbol,
                            'todo_id': todo.id})
            logger.info('补全预案待办已建', rule_id=rule.id, symbol=rule.symbol,
                        todo_id=todo.id)
        return {'created': created, 'skipped': skipped,
                'created_count': len(created), 'skipped_count': len(skipped)}

    # ── 默认装配（生产/CLI 共用）────────────────────────────

    @staticmethod
    def create_default() -> 'GuidanceBackfillService':
        from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
        from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
        from application.services.watch_engine.todo_service import TodoService

        def _account(rule):
            from domain.watch.services.rule_guard import effective_account
            return effective_account(rule)

        return GuidanceBackfillService(
            rule_repo=WatchRuleRepository(),
            todo_service=TodoService(repo=WatchTodoRepository()),
            account_resolver=_account,
        )
