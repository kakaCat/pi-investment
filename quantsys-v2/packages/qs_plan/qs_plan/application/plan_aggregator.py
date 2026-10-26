"""PlanAggregator：盘前「今日计划」聚合视图（t7 · IF-10 · FR-3）

一屏给出：激活计划 + 每标的条件就绪度 + 环境闸 verdict + 持仓差额 + 未决待办数。

口径：
- **无计划 = 200 + empty=true**（空列表是正常响应，不是错误）；
- 环境闸/持仓/待办二源不可用 → 对应字段标 skipped/None，**绝不用 0 冒充事实**；
- 只读，不写任何表。
"""
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from qs_plan.domain.plan import STATUS_ACTIVE, STATUS_CLOSING, STATUS_HOLDING

LIVE_STATUSES = [STATUS_ACTIVE, STATUS_HOLDING, STATUS_CLOSING]

SKIPPED = {'status': 'skipped', 'reason': '数据源不可用'}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlanAggregator:
    def __init__(self, repo,
                 env_gate_provider: Optional[Callable[[], Dict[str, Any]]] = None,
                 position_provider: Optional[Callable[[str, str], Any]] = None,
                 todo_provider: Optional[Callable[[str], Any]] = None,
                 now_fn: Callable[[], datetime] = _utcnow):
        self.repo = repo
        self._env = env_gate_provider
        self._pos = position_provider
        self._todo = todo_provider
        self._now = now_fn

    def build(self, account: str) -> Dict[str, Any]:
        plans = self.repo.list_plans(account, statuses=LIVE_STATUSES)
        if not plans:
            return {'empty': True, 'plans': [], 'generated_at': self._now().isoformat(),
                    'note': '该账户当前没有激活中的计划'}
        env_gate = self._safe_env()
        pending_todos = self._safe_todo(account)
        items = []
        for p in plans:
            targets = []
            for t in (p.spec.get('targets') or []):
                symbol = t.get('symbol')
                if not symbol:
                    continue
                targets.append({
                    'symbol': symbol,
                    'budget_pct': t.get('budget_pct'),
                    'role': t.get('role'),
                    'position': self._safe_position(account, symbol),
                })
            items.append({
                'plan': {
                    'id': p.id, 'name': p.name, 'status': p.status,
                    'version': p.version, 'horizon': p.horizon,
                    'review_due_at': (p.review_due_at.isoformat()
                                      if p.review_due_at else None),
                    'reflection_overdue_count': p.reflection_overdue_count,
                },
                'targets': targets,
                'entry': (p.spec.get('entry') or {}),
                'exit': (p.spec.get('exit') or {}),
                'env_gate': env_gate,
                'pending_todos': pending_todos,
            })
        return {'empty': False, 'plans': items,
                'generated_at': self._now().isoformat()}

    def _safe_env(self) -> Dict[str, Any]:
        if self._env is None:
            return dict(SKIPPED, reason='未接入市场快照（fail-open）')
        try:
            return self._env() or dict(SKIPPED)
        except Exception:  # noqa: BLE001
            return dict(SKIPPED, reason='环境闸读取异常（fail-open）')

    def _safe_todo(self, account: str) -> Optional[int]:
        if self._todo is None:
            return None
        try:
            return int(self._todo(account))
        except Exception:  # noqa: BLE001
            return None

    def _safe_position(self, account: str, symbol: str) -> Any:
        if self._pos is None:
            return None
        try:
            return self._pos(account, symbol)
        except Exception:  # noqa: BLE001
            return None
