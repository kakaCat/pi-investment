"""_collect_signals ORM/dict 兼容回归测试（2026-08-13）

事故：signal_repo.get_signals_by_date 在 ORM 重构后返回 Signal 对象列表，
而 SignalExecutionScheduler._collect_signals 按 dict 假设调 s.get('status')
→ AttributeError: 'Signal' object has no attribute 'get' → DailyOrchestrator
MARKET_OPEN phase 报错，signals_ready 推送自 08-05 起静默丢失
（daily_orchestrator_state.last_error 与 ~/v2-api.log 均可见）。

既有 test_orchestrator_signals_ready.py 全部 mock 掉 _collect_signals，
所以没挡住这个 bug——本测试直接打真实方法。
"""
from unittest.mock import MagicMock

from application.services.signal_execution_scheduler import SignalExecutionScheduler


def _make_scheduler_with_repo(signals):
    sched = object.__new__(SignalExecutionScheduler)
    sched.signal_repo = MagicMock()
    sched.signal_repo.get_signals_by_date.return_value = signals
    return sched


class TestCollectSignalsOrmCompat:
    def test_orm_objects_converted_to_dicts(self):
        """repo 返回 ORM Signal 对象：必须转 dict 并按 status 过滤"""
        from infrastructure.persistence.orm.models.signal import Signal
        from datetime import date
        orm_signals = [
            Signal(symbol='600519', name='贵州茅台', signal_date=date(2026, 8, 13),
                   action='BUY', action_type=1, strategy_id='179', status='pending'),
            Signal(symbol='000858', name='五粮液', signal_date=date(2026, 8, 13),
                   action='SELL', action_type=2, strategy_id='178', status='executed'),
        ]
        sched = _make_scheduler_with_repo(orm_signals)

        result = sched._collect_signals('2026-08-13')

        assert len(result) == 1  # executed 被过滤
        assert result[0]['symbol'] == '600519'
        assert result[0]['status'] == 'pending'
        assert result[0]['action'] == 'BUY'
        assert isinstance(result[0], dict)

    def test_dicts_passthrough(self):
        """repo 返回 dict（旧契约/其他实现）：原样工作"""
        dicts = [
            {'symbol': '600519', 'status': 'pending', 'action': 'BUY'},
            {'symbol': '000858', 'status': 'expired', 'action': 'SELL'},
        ]
        sched = _make_scheduler_with_repo(dicts)

        result = sched._collect_signals('2026-08-13')

        assert len(result) == 1
        assert result[0]['symbol'] == '600519'

    def test_empty(self):
        sched = _make_scheduler_with_repo([])
        assert sched._collect_signals('2026-08-13') == []
