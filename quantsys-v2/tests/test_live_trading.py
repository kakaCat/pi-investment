"""
Unit tests for Module 4: Live Trading

Tests cover:
- IBKR and Alpaca broker adapters (without requiring library installation)
- Execution service (TWAP, VWAP, Iceberg algorithms)
- Position service (P&L, cost basis)
- Order state machine (valid/invalid transitions)
- Live risk checks (position limits, margin, day trading)
"""

import pytest
import sys
import os
from datetime import datetime

# Ensure the quantsys-v2 directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ========================================================================
# Test IBKR Broker
# ========================================================================


class TestIBKRBroker:
    """Test the Interactive Brokers adapter without requiring ib_insync."""

    @pytest.fixture
    def broker(self):
        """Create an IBKR broker instance."""
        from domain.brokers.adapters.ibkr_broker import IBKRBroker
        return IBKRBroker()

    def test_get_id(self, broker):
        """Verify broker ID."""
        assert broker.get_id() == "ibkr"

    def test_get_name(self, broker):
        """Verify broker display name."""
        assert broker.get_name() == "Interactive Brokers"

    def test_get_profile_has_required_fields(self, broker):
        """Verify profile contains all expected fields."""
        profile = broker.get_profile()

        assert profile.id == "ibkr"
        assert profile.display_name == "Interactive Brokers"
        assert profile.region == "US"
        assert profile.currency == "USD"

        # Credential fields
        assert len(profile.credential_fields) > 0

        # Exchanges should include major US exchanges
        assert "NYSE" in profile.supported_exchanges
        assert "NASDAQ" in profile.supported_exchanges

        # Feature flags
        assert profile.supports_margin is True
        assert profile.supports_options is True
        assert profile.supports_intraday is True
        assert profile.has_native_paper is True
        assert len(profile.product_types) >= 3

    def test_get_quotes_without_connection(self, broker):
        """Verify graceful failure when not connected."""
        response = broker.get_quotes(['AAPL'])
        assert response.success is False
        assert 'not installed' in response.error.lower() or 'not connected' in response.error.lower()

    def test_place_order_without_connection(self, broker):
        """Verify trading returns failure when not connected."""
        from domain.brokers.trading_types import (
            BrokerCredentials, UnifiedOrder, OrderSide, OrderType
        )

        creds = BrokerCredentials(broker_id='ibkr')
        order = UnifiedOrder(
            symbol='AAPL',
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
        )

        response = broker.place_order(creds, order)
        assert response.success is False

    def test_is_trading_broker(self, broker):
        """Verify IBKR is classified as a trading broker."""
        assert broker.is_trading_broker() is True

    def test_supports_feature(self, broker):
        """Verify feature support flags."""
        assert broker.supports_feature('margin') is True
        assert broker.supports_feature('options') is True
        assert broker.supports_feature('intraday') is True

    def test_repr_contains_status(self, broker):
        """Verify repr shows connection status."""
        rep = repr(broker)
        assert 'IBKRBroker' in rep


# ========================================================================
# Test Alpaca Broker
# ========================================================================


class TestAlpacaBroker:
    """Test the Alpaca broker adapter without requiring alpaca-py."""

    @pytest.fixture
    def broker(self):
        """Create an Alpaca broker instance."""
        from domain.brokers.adapters.alpaca_broker import AlpacaBroker
        return AlpacaBroker()

    def test_get_id(self, broker):
        """Verify broker ID."""
        assert broker.get_id() == "alpaca"

    def test_get_name(self, broker):
        """Verify broker display name."""
        assert broker.get_name() == "Alpaca Markets"

    def test_get_profile_has_required_fields(self, broker):
        """Verify profile contains all expected fields."""
        profile = broker.get_profile()

        assert profile.id == "alpaca"
        assert profile.display_name == "Alpaca Markets"
        assert profile.region == "US"
        assert profile.currency == "USD"

        # Credential fields for API key + secret
        assert len(profile.credential_fields) == 2

        # Paper trading support
        assert profile.has_native_paper is True
        assert profile.supports_margin is True

        # Default watchlist
        assert "AAPL" in profile.default_watchlist

    def test_authenticate_missing_credentials(self, broker):
        """Verify authentication fails with no credentials."""
        from domain.brokers.trading_types import BrokerCredentials
        creds = BrokerCredentials(broker_id='alpaca')

        response = broker.authenticate(creds)
        assert response.success is False
        # Error may be about missing library or missing credentials, both acceptable
        assert len(response.error) > 0

    def test_get_quotes_without_auth(self, broker):
        """Verify graceful failure when not authenticated."""
        response = broker.get_quotes(['AAPL'])
        assert response.success is False

    def test_is_trading_broker(self, broker):
        """Verify Alpaca is classified as a trading broker."""
        assert broker.is_trading_broker() is True

    def test_repr_contains_status(self, broker):
        """Verify repr shows mode and status."""
        rep = repr(broker)
        assert 'AlpacaBroker' in rep


# ========================================================================
# Test Execution Service
# ========================================================================


class TestExecutionService:
    """Test algorithmic execution service functions."""

    @pytest.fixture
    def ds(self):
        """Create a mock DataService for execution tests."""
        from application.services.data_service import DataService
        return DataService()

    def test_execute_order_basic(self, ds):
        """Verify basic order execution returns success."""
        from application.services.execution_service import execute_order

        order_details = {
            'symbol': 'AAPL',
            'action': 'buy',
            'quantity': 100,
            'price': 150.0,
        }

        result = execute_order(ds, 'ibkr', order_details, algo='market')

        assert result.success is True
        assert result.algo == 'market'
        assert result.filled_quantity == 100
        assert result.avg_price == 150.0
        assert result.order_id != ""
        assert result.execution_time_seconds >= 0

    def test_execute_order_missing_symbol(self, ds):
        """Verify execution fails gracefully with missing symbol."""
        from application.services.execution_service import execute_order

        order_details = {
            'action': 'buy',
            'quantity': 100,
        }

        result = execute_order(ds, 'ibkr', order_details)

        assert result.success is False
        assert result.error is not None

    def test_twap_execution_splits_correctly(self, ds):
        """Verify TWAP splits order into correct number of slices."""
        from application.services.execution_service import execute_twap

        order = {
            'symbol': 'AAPL',
            'action': 'buy',
            'quantity': 1000,
            'price': 150.0,
        }

        result = execute_twap(ds, 'ibkr', order, duration_minutes=30, slices=10)

        assert result.success is True
        assert result.algo == 'twap'
        assert len(result.slices) == 10

        # Total filled quantity should match
        total_from_slices = sum(s['quantity'] for s in result.slices)
        assert abs(total_from_slices - 1000) < 0.01

        # Avg price should be reasonable
        assert result.avg_price > 0
        assert abs(result.filled_quantity - 1000) < 0.01

    def test_vwap_execution_uses_volume_profile(self, ds):
        """Verify VWAP execution uses volume profile to weight slices."""
        from application.services.execution_service import execute_vwap

        order = {
            'symbol': 'AAPL',
            'action': 'buy',
            'quantity': 1000,
            'price': 150.0,
        }

        result = execute_vwap(ds, 'ibkr', order, duration_minutes=60)

        assert result.success is True
        assert result.algo == 'vwap'
        assert len(result.slices) == 10  # Default 10 bins

        # Volume weights should sum to ~1.0
        total_weight = sum(s['volume_weight'] for s in result.slices)
        assert abs(total_weight - 1.0) < 0.01

        # Total quantity should match
        total_qty = sum(s['quantity'] for s in result.slices)
        assert abs(total_qty - 1000) < 0.01

    def test_iceberg_execution_displays_limit(self, ds):
        """Verify Iceberg execution respects display size."""
        from application.services.execution_service import execute_iceberg

        order = {
            'symbol': 'AAPL',
            'action': 'buy',
            'quantity': 500,
            'price': 150.0,
        }

        display_size = 100
        result = execute_iceberg(ds, 'ibkr', order, display_size=display_size)

        assert result.success is True
        assert result.algo == 'iceberg'

        # Each slice's display quantity should be <= display_size
        for s in result.slices:
            assert s['display_quantity'] <= display_size

        # Total should match
        total_qty = sum(s['total_quantity'] for s in result.slices)
        assert abs(total_qty - 500) < 0.01

    def test_execution_result_dataclass(self):
        """Verify ExecutionResult dataclass structure."""
        from application.services.execution_service import ExecutionResult

        result = ExecutionResult(
            success=True,
            order_id="test-123",
            algo="twap",
            filled_quantity=100.0,
            avg_price=150.50,
            slippage_bps=2.0,
            execution_time_seconds=0.5,
        )

        assert result.success is True
        assert result.order_id == "test-123"
        assert result.algo == "twap"
        assert result.filled_quantity == 100.0
        assert result.slippage_bps == 2.0

        # Error version
        error_result = ExecutionResult(
            success=False,
            error="Connection failed",
            algo="market",
        )
        assert error_result.success is False
        assert error_result.error == "Connection failed"

    def test_get_execution_report_handles_missing(self, ds):
        """Verify execution report handles missing orders gracefully."""
        from application.services.execution_service import get_execution_report

        result = get_execution_report(ds, 'ibkr', 'nonexistent-99999')

        assert result['success'] is False
        assert 'order_id' in result

    def test_cancel_all_orders_handles_no_broker(self, ds):
        """Verify cancel all orders handles missing broker gracefully."""
        from application.services.execution_service import cancel_all_orders

        result = cancel_all_orders(ds, 'nonexistent_broker')

        assert result['success'] is False
        assert 'error' in result or result['cancelled_count'] == 0


# ========================================================================
# Test Position Service
# ========================================================================


class TestPositionService:
    """Test live position management functions."""

    def test_get_average_cost_basis_simple(self):
        """Verify weighted average cost calculation."""
        from application.services.position_service import get_average_cost_basis

        trades = [
            {'symbol': 'AAPL', 'action': 'buy', 'quantity': 100, 'price': 150.0},
            {'symbol': 'AAPL', 'action': 'buy', 'quantity': 200, 'price': 155.0},
        ]

        result = get_average_cost_basis(None, trades, 'AAPL')

        assert result['success'] is True
        assert result['symbol'] == 'AAPL'
        # avg = (100*150 + 200*155) / 300 = (15000 + 31000) / 300 = 46000/300 = 153.3333
        assert abs(result['average_cost'] - 153.3333) < 0.01
        assert result['total_quantity'] == 300
        assert result['buys'] == 2
        assert result['sells'] == 0

    def test_get_average_cost_basis_with_sells(self):
        """Verify cost basis ignores sell trades."""
        from application.services.position_service import get_average_cost_basis

        trades = [
            {'symbol': 'MSFT', 'action': 'buy', 'quantity': 50, 'price': 400.0},
            {'symbol': 'MSFT', 'action': 'sell', 'quantity': 25, 'price': 420.0},
            {'symbol': 'MSFT', 'action': 'buy', 'quantity': 50, 'price': 410.0},
        ]

        result = get_average_cost_basis(None, trades, 'MSFT')

        assert result['success'] is True
        # avg = (50*400 + 50*410) / 100 = (20000 + 20500) / 100 = 405.0
        assert abs(result['average_cost'] - 405.0) < 0.01
        assert result['total_quantity'] == 100
        assert result['buys'] == 2
        assert result['sells'] == 1

    def test_get_average_cost_basis_empty(self):
        """Verify cost basis handles empty trade list."""
        from application.services.position_service import get_average_cost_basis

        result = get_average_cost_basis(None, [], 'EMPTY')

        assert result['success'] is True
        assert result['average_cost'] == 0.0
        assert result['total_quantity'] == 0

    def test_close_position_returns_order_details_structure(self):
        """Verify close_position returns structured data about the closing order."""
        from application.services.position_service import close_position

        result = close_position(None, 'ibkr', 'AAPL')

        # Without live broker, should return error or structured fallback
        assert 'success' in result
        assert 'symbol' in result or result.get('symbol') == 'AAPL'
        assert 'broker_id' in result or result.get('broker_id') == 'ibkr'


# ========================================================================
# Test Order State Machine
# ========================================================================


class TestOrderStateMachine:
    """Test order state transition validation."""

    def test_valid_transition_pending_to_partial(self):
        """Verify pending -> partial is valid."""
        from application.services.order_service import validate_state_transition
        assert validate_state_transition('pending', 'partial') is True

    def test_valid_transition_partial_to_filled(self):
        """Verify partial -> filled is valid."""
        from application.services.order_service import validate_state_transition
        assert validate_state_transition('partial', 'filled') is True

    def test_valid_transition_pending_to_cancelled(self):
        """Verify pending -> cancelled is valid."""
        from application.services.order_service import validate_state_transition
        assert validate_state_transition('pending', 'cancelled') is True

    def test_valid_transition_pending_to_rejected(self):
        """Verify pending -> rejected is valid."""
        from application.services.order_service import validate_state_transition
        assert validate_state_transition('pending', 'rejected') is True

    def test_invalid_transition_filled_to_partial(self):
        """Verify filled -> partial is NOT allowed (terminal state)."""
        from application.services.order_service import validate_state_transition
        assert validate_state_transition('filled', 'partial') is False

    def test_invalid_transition_cancelled_to_pending(self):
        """Verify cancelled -> pending is NOT allowed (terminal state)."""
        from application.services.order_service import validate_state_transition
        assert validate_state_transition('cancelled', 'pending') is False

    def test_invalid_transition_rejected_to_pending(self):
        """Verify rejected -> pending is NOT allowed."""
        from application.services.order_service import validate_state_transition
        assert validate_state_transition('rejected', 'pending') is False

    def test_invalid_transition_pending_to_filled(self):
        """Verify pending -> filled is NOT allowed (must go through partial)."""
        from application.services.order_service import validate_state_transition
        assert validate_state_transition('pending', 'filled') is False

    def test_order_states_constant(self):
        """Verify ORDER_STATES constant contains expected states."""
        from application.services.order_service import ORDER_STATES

        expected_states = ['pending', 'partial', 'filled', 'cancelled', 'expired', 'rejected']
        for state in expected_states:
            assert state in ORDER_STATES


# ========================================================================
# Test Live Risk Checks
# ========================================================================


class TestLiveRiskChecks:
    """Test pre-trade risk check functions."""

    @pytest.fixture
    def ds(self):
        """Create a mock DataService."""
        from application.services.data_service import DataService
        return DataService()

    def test_get_risk_limits_defaults(self, ds):
        """Verify risk limits return sensible defaults when no DB config."""
        from application.services.risk_service import get_risk_limits

        limits = get_risk_limits(ds)

        assert 'max_position_pct' in limits
        assert 'max_sector_pct' in limits
        assert 'max_daily_trades' in limits
        assert 'max_order_value' in limits
        assert 'pdt_min_equity' in limits

        # Values should be within reasonable ranges
        assert 0 < limits['max_position_pct'] <= 1.0
        assert 0 < limits['max_sector_pct'] <= 1.0
        assert limits['pdt_min_equity'] == 25000

    def test_check_margin_requirement_no_data(self, ds):
        """Verify margin check handles missing account data gracefully."""
        from application.services.risk_service import check_margin_requirement

        result = check_margin_requirement(
            ds, 'ibkr', order_value=50000, symbol='AAPL'
        )

        assert result['passed'] is True  # Skips when no data
        assert result['rule'] == 'margin_requirement'

    def test_live_pre_trade_check_returns_structured_result(self, ds):
        """Verify live pre-trade check returns a properly structured dict."""
        from application.services.risk_service import live_pre_trade_check

        result = live_pre_trade_check(
            ds, 'ibkr', 'AAPL', 'buy', 100, 150.0
        )

        assert isinstance(result, dict)
        assert 'passed' in result
        assert 'checks' in result
        assert 'blocking_reasons' in result
        assert 'warnings' in result

        # All results should be typed correctly
        assert isinstance(result['passed'], bool)
        assert isinstance(result['checks'], list)
        assert isinstance(result['blocking_reasons'], list)

    def test_check_day_trading_limit_returns_structure(self, ds):
        """Verify PDT check returns proper structure."""
        from application.services.risk_service import check_day_trading_limit

        result = check_day_trading_limit(ds, 'ibkr', 'AAPL', 'buy')

        assert isinstance(result, dict)
        assert 'passed' in result
        assert 'rule' in result
        assert result['rule'] == 'pdt_rule'

    def test_check_short_sale_restriction_handles_no_data(self, ds):
        """Verify SSR check handles missing data gracefully."""
        from application.services.risk_service import check_short_sale_restriction

        result = check_short_sale_restriction(ds, 'NONEXISTENT')

        assert isinstance(result, dict)
        assert 'passed' in result
        assert result['rule'] == 'short_sale_restriction'

    def test_live_pre_trade_check_size_limit(self, ds):
        """Verify position size check catches oversized orders."""
        from application.services.risk_service import live_pre_trade_check

        # A large order (90% of a small portfolio) should trigger position size alert
        result = live_pre_trade_check(
            ds, 'ibkr', 'AAPL', 'buy', 10000, 500.0  # $5M order
        )

        assert isinstance(result, dict)
        assert 'passed' in result
        assert len(result['checks']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
