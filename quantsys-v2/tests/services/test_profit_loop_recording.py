"""盈亏闭环落库（_record_strategy_performance）单测（2026-10-19）

断点 C 修复的契约钉扎：
- SELL 成交 → strategy_performance.create() 被调用，字段口径正确
  （pnl_pct = 小数率 ×100；holding_days = 卖出日 - 持仓开仓日）；
- 归因优先级：order.strategy_name > signal_id 反查 > 'unattributed'（不伪造）；
- 无信号时 signal_date = 持仓开仓日，依据写进 params_snapshot.signal_date_basis；
- 缺数据（entry_price / realized_pnl_rate 为 None）→ 不落库（不按 0 记）；
- 落库异常被吞（审计不能拖垮已成交主链路）。
"""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from qs_trading.application.services.account_trading_service import (
    AccountTradingService,
)

PERF_REPO_PATH = (
    'adapters.outbound.repositories.strategy_performance_repository'
    '.StrategyPerformanceORMRepository'
)


def _svc(session=None):
    svc = AccountTradingService.__new__(AccountTradingService)
    svc.repo = SimpleNamespace(session=session or MagicMock())
    return svc


def _run(svc, **kw):
    defaults = dict(
        account_name='agent_virtual', symbol='600519',
        order=SimpleNamespace(id=11, signal_id=None, strategy_name=None),
        trade_id=99, exit_price=1800.0, entry_price=1700.0,
        pos_opened_at=datetime(2026, 10, 10, 10, 30),
        realized_pnl=950.0, realized_pnl_rate=0.0095,
        trade_date=date(2026, 10, 19),
    )
    defaults.update(kw)
    with patch(PERF_REPO_PATH) as repo_cls:
        svc._record_strategy_performance(**defaults)
    return repo_cls


class TestProfitLoopRecording:
    def test_signal_attribution_writes_percent_and_holding_days(self):
        svc = _svc()
        order = SimpleNamespace(id=11, signal_id='777', strategy_name='range-breakout-v1')
        sig = SimpleNamespace(signal_date=date(2026, 10, 15), strategy_id='163')
        svc.repo.session.query.return_value.filter.return_value.first.return_value = sig

        repo_cls = _run(svc, order=order)

        kw = repo_cls.return_value.create.call_args.kwargs
        assert kw['strategy_name'] == 'range-breakout-v1'       # 订单实名优先
        assert kw['signal_date'] == date(2026, 10, 15)          # 有信号取信号日
        assert kw['entry_price'] == 1700.0
        assert kw['exit_price'] == 1800.0
        assert kw['pnl_pct'] == 0.95                            # 0.0095 ×100，百分数契约
        assert kw['holding_days'] == 9                          # 10-10 → 10-19
        assert kw['source'] == 'paper'
        assert kw['params_snapshot']['attribution'] == 'signal'
        assert kw['params_snapshot']['signal_id'] == '777'

    def test_unattributed_falls_back_to_position_open_date(self):
        repo_cls = _run(_svc())  # order 无 signal_id/strategy_name

        kw = repo_cls.return_value.create.call_args.kwargs
        assert kw['strategy_name'] == 'unattributed'
        assert kw['signal_date'] == date(2026, 10, 10)          # 持仓开仓日
        assert kw['params_snapshot']['attribution'] == 'unattributed'
        assert kw['params_snapshot']['signal_date_basis'] == 'position_open_date'

    def test_missing_entry_price_skips_record(self):
        repo_cls = _run(_svc(), entry_price=None)
        repo_cls.return_value.create.assert_not_called()

    def test_missing_pnl_rate_skips_record(self):
        repo_cls = _run(_svc(), realized_pnl_rate=None)
        repo_cls.return_value.create.assert_not_called()

    def test_create_failure_is_swallowed(self):
        svc = _svc()
        with patch(PERF_REPO_PATH) as repo_cls:
            repo_cls.return_value.create.side_effect = RuntimeError('db down')
            svc._record_strategy_performance(  # 不抛 = 通过
                account_name='agent_virtual', symbol='600519',
                order=SimpleNamespace(id=11, signal_id=None, strategy_name=None),
                trade_id=99, exit_price=1800.0, entry_price=1700.0,
                pos_opened_at=None, realized_pnl=950.0, realized_pnl_rate=0.0095,
                trade_date=date(2026, 10, 19))

    def test_no_position_date_falls_back_to_trade_date(self):
        repo_cls = _run(_svc(), pos_opened_at=None)
        kw = repo_cls.return_value.create.call_args.kwargs
        assert kw['signal_date'] == date(2026, 10, 19)
        assert kw['holding_days'] == 0
        assert kw['params_snapshot']['signal_date_basis'] == 'trade_date_fallback'
