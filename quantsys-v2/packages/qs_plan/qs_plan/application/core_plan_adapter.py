"""core_plan 批次 → draft 交易计划（t14 · FR-9 · P2）

口径：
- core_plan.json 是**组合层**建仓计划（批次数/金额/标的）；本适配器只做「批次 → draft 计划」；
- 生成物一律 draft，**不自动激活**（激活仍需要人/agent 确认，D-1 终判口径）；
- 幂等：同名（core-plan-b{batch}-{symbol}）draft 计划已存在 → 跳过；
- 文件缺失/过期/账户不符 → CorePlanUnavailable（路由转 422）。
"""
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

STALE_DAYS = 7


class CorePlanUnavailable(RuntimeError):
    pass


def _default_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / 'config' / 'core_plan.json'


class CorePlanAdapter:
    def __init__(self, plan_service, core_plan_path: Optional[str] = None,
                 now_fn=lambda: datetime.now(timezone.utc)):
        self._svc = plan_service
        self._path = Path(core_plan_path) if core_plan_path else _default_path()
        self._now = now_fn

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            raise CorePlanUnavailable('core_plan.json 不存在：%s' % self._path)
        try:
            data = json.loads(self._path.read_text(encoding='utf-8'))
        except Exception as e:  # noqa: BLE001
            raise CorePlanUnavailable('core_plan.json 解析失败：%s' % e)
        generated = str(data.get('generated_at') or '')
        try:
            gen_date = datetime.fromisoformat(generated).date()
        except ValueError:
            raise CorePlanUnavailable('core_plan.generated_at 缺失或非法：%r' % generated)
        if (self._now().date() - gen_date) > timedelta(days=STALE_DAYS):
            raise CorePlanUnavailable('core_plan 已过期（generated_at=%s）' % gen_date)
        return data

    def from_batch(self, account: str, batch: int, actor: str = 'agent') -> Dict[str, Any]:
        data = self.load()
        if data.get('account') not in (None, account):
            raise CorePlanUnavailable('计划账户 %r 与请求账户 %r 不一致'
                                      % (data.get('account'), account))
        batches = ((data.get('execution_plan') or {}).get('batches') or [])
        target = next((b for b in batches if int(b.get('batch') or 0) == int(batch)), None)
        if target is None:
            raise CorePlanUnavailable('批次 %s 不在 core_plan 中' % batch)
        total = float(data.get('account_total') or 0) or 0.0
        existing = {p.name for p in self._svc.list(account) or []}
        created: List[int] = []
        skipped: List[str] = []
        for item in (target.get('detail') or []):
            symbol = item.get('symbol')
            if not symbol:
                continue
            name = 'core-plan-b%s-%s' % (batch, symbol)
            if name in existing:
                skipped.append(name)
                continue
            amount = float(item.get('amount') or 0)
            budget = round(amount / total * 100, 4) if total else None
            spec = {
                'targets': [{'symbol': symbol, 'budget_pct': budget or 5, 'role': 'core'}],
                # 入场条件 **不发明**：core_plan 只给目标持仓，择时归 agent（D-1 终判）。
                # pending=true 时编译器只编止损；agent 补条件后 apply 才生成入场规则。
                'entry': {'conditions': [], 'combinator': 'all_of', 'pending': True,
                          'note': '入场条件待补：core_plan 只给目标持仓，不给择时'},
                'exit': {'stop_loss': {'type': 'pct', 'value': 8}},
                'monitoring': {'news': True},
                'schedule': {'interval_sec': 60},
            }
            plan = self._svc.create(account=account, name=name, horizon='swing',
                                    spec=spec, created_by=actor, actor=actor)
            created.append(plan.id)
        return {'batch': batch, 'created': created, 'skipped': skipped,
                'source': str(self._path)}
