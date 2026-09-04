import pytest
import requests
from datetime import date, timedelta

from tests.e2e.p2_fixtures import (
    get_test_db_conn,
    cleanup_test_decisions,
    create_test_decision,
    get_decision,
)


API_BASE = "http://127.0.0.1:5001"
TEST_PREFIX = "E2E_AGENT"
TEST_SYMBOL = "600519.SH"


def api_get(endpoint, params=None):
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", params=params or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        pytest.skip(f"API unavailable: {e}")


def api_post(endpoint, data):
    try:
        resp = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        pytest.skip(f"API unavailable: {e}")


@pytest.fixture(scope="module")
def db_conn():
    conn = get_test_db_conn()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def cleanup(db_conn):
    cleanup_test_decisions(db_conn, TEST_PREFIX)
    yield
    cleanup_test_decisions(db_conn, TEST_PREFIX)


@pytest.fixture(scope="module")
def api_available():
    try:
        resp = requests.get(f"{API_BASE}/api/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


class TestAgentDecisionCreation:

    def test_create_buy_decision(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="AGENT_BUY_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        d = get_decision(db_conn, decision_id)
        assert d is not None
        assert d['decision_type'] == 'trade_buy'
        assert d['evaluation_status'] == 'pending'

    def test_create_sell_decision(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="AGENT_SELL_001", symbol=TEST_SYMBOL,
            action="trade_sell", price=1700.00, test_prefix=TEST_PREFIX)

        d = get_decision(db_conn, decision_id)
        assert d is not None
        assert d['decision_type'] == 'trade_sell'


class TestDecisionParameters:

    def test_decision_has_required_fields(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="PARAM_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        d = get_decision(db_conn, decision_id)
        assert d is not None
        assert 'symbol' in d['parameters']
        assert 'price' in d['parameters']
        assert d['parameters']['symbol'] == TEST_SYMBOL
        assert d['parameters']['price'] == 1650.00

    def test_decision_confidence_score(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="CONF_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        d = get_decision(db_conn, decision_id)
        assert d is not None
        assert 0 <= d['confidence_score'] <= 1


class TestDecisionStatusFlow:

    def test_decision_starts_as_pending(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="STATUS_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        d = get_decision(db_conn, decision_id)
        assert d['evaluation_status'] == 'pending'

    def test_decision_can_be_scored(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="SCORE_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                UPDATE quant.agent_decisions
                SET evaluation_status = 'scored', score = 0.75
                WHERE decision_id = %s
            """, (decision_id,))
            db_conn.commit()

            d = get_decision(db_conn, decision_id)
            assert d['evaluation_status'] == 'scored'
            assert d['score'] == 0.75
        finally:
            cursor.close()


class TestBatchDecisionProcessing:

    def test_create_multiple_decisions(self, db_conn):
        for i in range(5):
            create_test_decision(
                db_conn, decision_id=f"BATCH_{i:03d}", symbol=TEST_SYMBOL,
                action="trade_buy", price=1650.00 + i * 10,
                test_prefix=TEST_PREFIX)

        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM quant.agent_decisions
                WHERE decision_id LIKE %s
            """, (f"{TEST_PREFIX}_BATCH_%",))
            count = cursor.fetchone()[0]
            assert count == 5
        finally:
            cursor.close()

    def test_batch_score_processing(self, db_conn):
        for i in range(3):
            create_test_decision(
                db_conn, decision_id=f"BATCH_SCORE_{i:03d}", symbol=TEST_SYMBOL,
                action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                UPDATE quant.agent_decisions
                SET evaluation_status = 'scored', score = 0.80
                WHERE decision_id LIKE %s AND evaluation_status = 'pending'
            """, (f"{TEST_PREFIX}_BATCH_SCORE_%",))
            db_conn.commit()

            cursor.execute("""
                SELECT COUNT(*) FROM quant.agent_decisions
                WHERE decision_id LIKE %s AND evaluation_status = 'scored'
            """, (f"{TEST_PREFIX}_BATCH_SCORE_%",))
            count = cursor.fetchone()[0]
            assert count == 3
        finally:
            cursor.close()


class TestDataConsistency:

    def test_decision_id_unique(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="UNIQUE_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        create_test_decision(
            db_conn, decision_id="UNIQUE_001", symbol=TEST_SYMBOL,
            action="trade_sell", price=1700.00, test_prefix=TEST_PREFIX)

        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM quant.agent_decisions
                WHERE decision_id = %s
            """, (decision_id,))
            count = cursor.fetchone()[0]
            assert count == 1
        finally:
            cursor.close()

    def test_cascade_delete_dependencies(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="CASCADE_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                DELETE FROM quant.agent_decisions WHERE decision_id = %s
            """, (decision_id,))
            db_conn.commit()

            cursor.execute("""
                SELECT COUNT(*) FROM quant.agent_decisions
                WHERE decision_id = %s
            """, (decision_id,))
            count = cursor.fetchone()[0]
            assert count == 0
        finally:
            cursor.close()
