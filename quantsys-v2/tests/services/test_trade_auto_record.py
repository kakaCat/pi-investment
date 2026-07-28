"""成交后自动决策记账测试（C2：审计轨迹不再依赖 LLM 自觉）"""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from application.services.account_trading_service import (
    AccountTradingService, TradingError,
)


def _make_service():
    svc = AccountTradingService.__new__(AccountTradingService)
    svc.repo = MagicMock()
    svc.calendar = MagicMock()
    svc.calendar.is_trading_day.return_value = True
    svc.now_fn = lambda: datetime(2026, 7, 28, 10, 0)  # 交易时段内
    return svc


def _setup_account(svc):
    account = MagicMock()
    account.status = 'active'
    account.cash_available = Decimal("100000")
    account.cash_frozen = Decimal("0")
    account.total_value = Decimal("100000")
    account.initial_capital = Decimal("100000")
    account.peak_value = Decimal("100000")
    account.cumulative_return = Decimal("0")
    svc.repo.get_account.return_value = account
    svc.repo.get_account_for_update.return_value = account
    svc.repo.get_all_positions.return_value = []
    svc.repo.get_trades_by_account.return_value = []
    svc.repo.create_order.return_value = MagicMock(id=1)
    svc.repo.add_trade.return_value = 1
    return account


class TestTradeAutoRecord:
    def test_successful_buy_auto_records_decision(self):
        svc = _make_service()
        _setup_account(svc)
        svc._get_price = lambda symbol: 10.0

        with patch("application.services.decision_service.DecisionService") as MockDS:
            svc.execute_trade(
                account_name="agent_virtual",
                action="buy",
                symbol="600519",
                shares=100,
                reason="测试：自动记账验证买入",
            )
            assert MockDS.return_value.record_decision.called
            payload = MockDS.return_value.record_decision.call_args[0][0]
            assert payload["decision_type"] == "trade_buy"
            assert payload["parameters"]["symbol"] == "600519"
            assert payload["context"]["auto_recorded"] is True

    def test_record_failure_does_not_break_trade(self):
        svc = _make_service()
        _setup_account(svc)
        svc._get_price = lambda symbol: 10.0

        with patch("application.services.decision_service.DecisionService") as MockDS:
            MockDS.return_value.record_decision.side_effect = Exception("db down")
            result = svc.execute_trade(
                account_name="agent_virtual",
                action="buy",
                symbol="600519",
                shares=100,
                reason="测试：记账失败不影响成交",
            )
            assert result["order_status"] == "filled"
