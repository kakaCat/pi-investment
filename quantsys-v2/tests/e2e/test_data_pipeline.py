import time
import pytest
from datetime import date, timedelta

from tests.e2e.p2_fixtures import get_test_db_conn


@pytest.fixture(scope="module")
def db_conn():
    conn = get_test_db_conn()
    yield conn
    conn.close()


class TestCircuitBreaker:

    def test_breaker_starts_closed(self):
        from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)
        assert not breaker.is_open()

    def test_breaker_opens_after_threshold(self):
        from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        def failing():
            raise ConnectionError("fail")

        for _ in range(3):
            try:
                breaker.call(failing)
            except Exception:
                pass

        assert breaker.is_open()

    def test_breaker_rejects_when_open(self):
        from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing():
            raise ConnectionError("fail")

        for _ in range(2):
            try:
                breaker.call(failing)
            except Exception:
                pass

        with pytest.raises(Exception):
            breaker.call(lambda: "should not run")

    def test_breaker_reset(self):
        from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing():
            raise ConnectionError("fail")

        for _ in range(2):
            try:
                breaker.call(failing)
            except Exception:
                pass

        assert breaker.is_open()
        breaker.reset()
        assert not breaker.is_open()

    def test_breaker_allows_after_timeout(self):
        from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=2, timeout=1)

        def failing():
            raise ConnectionError("fail")

        for _ in range(2):
            try:
                breaker.call(failing)
            except Exception:
                pass

        assert breaker.is_open()
        time.sleep(1.5)
        result = breaker.call(lambda: "recovered")
        assert result == "recovered"


class TestDataIntegrity:

    def test_klines_data_complete(self, db_conn):
        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                SELECT symbol, trade_date, open, high, low, close, volume
                FROM quant.daily_klines
                WHERE symbol = '600519.SH'
                ORDER BY trade_date DESC LIMIT 5
            """)
            rows = cursor.fetchall()
            for row in rows:
                assert row[2] is not None
                assert row[3] is not None
                assert row[4] is not None
                assert row[5] is not None
                assert row[6] is not None
                assert row[3] >= row[4]
                assert row[3] >= row[2]
                assert row[3] >= row[5]
        finally:
            cursor.close()

    def test_no_duplicate_klines(self, db_conn):
        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                SELECT symbol, trade_date, COUNT(*)
                FROM quant.daily_klines
                GROUP BY symbol, trade_date
                HAVING COUNT(*) > 1
                LIMIT 10
            """)
            duplicates = cursor.fetchall()
            assert len(duplicates) == 0
        finally:
            cursor.close()


class TestDataProviderManager:

    def test_get_provider_health(self):
        from adapters.outbound.datasources.manager import DataProviderManager
        m = DataProviderManager()
        health = m.get_provider_health()
        assert isinstance(health, dict)
        assert len(health) > 0
        for name, info in health.items():
            assert 'success' in info
            assert 'failure' in info
            assert 'consecutive_failures' in info

    def test_get_provider_stats(self):
        from adapters.outbound.datasources.manager import DataProviderManager
        m = DataProviderManager()
        stats = m.get_provider_stats()
        assert isinstance(stats, dict)

    def test_reset_circuit_breakers(self):
        from adapters.outbound.datasources.manager import DataProviderManager
        m = DataProviderManager()
        m.reset_circuit_breakers()
        health = m.get_provider_health()
        for name, info in health.items():
            if 'circuit_state' in info:
                assert info['circuit_state'] == 'closed'


class TestFailureRecovery:

    def test_breaker_state_dict(self):
        from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=3, timeout=60, name="test_breaker")
        state = breaker.get_state()
        assert state['name'] == "test_breaker"
        assert state['failure_threshold'] == 3
        assert 'state' in state
        assert 'is_available' in state

    def test_breaker_decorator(self):
        from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        @breaker.decorator
        def success_func():
            return "ok"

        result = success_func()
        assert result == "ok"
        assert not breaker.is_open()
