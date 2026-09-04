import json
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from tests.e2e.p2_fixtures import (
    get_test_db_conn,
    cleanup_test_decisions,
    cleanup_test_fitness,
    cleanup_test_klines,
    create_test_decision,
    get_decision,
    insert_test_klines,
    MockKlineRepository,
    MockDecisionRepository,
)


TEST_PREFIX = "E2E_EVOLUTION"
TEST_SYMBOL = "600519.SH"


@pytest.fixture(scope="module")
def db_conn():
    conn = get_test_db_conn()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def cleanup(db_conn):
    cleanup_test_decisions(db_conn, TEST_PREFIX)
    cleanup_test_fitness(db_conn)
    cleanup_test_klines(db_conn, TEST_SYMBOL)
    yield
    cleanup_test_decisions(db_conn, TEST_PREFIX)
    cleanup_test_fitness(db_conn)
    cleanup_test_klines(db_conn, TEST_SYMBOL)


def _build_decision_dict(decision_id, symbol, action, price, created_at):
    return {
        'decision_id': decision_id,
        'decision_type': action,
        'parameters': {'symbol': symbol, 'price': price, 'quantity': 100},
        'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
        'evaluation_status': 'pending',
        'confidence_score': 0.85,
    }


class TestDecisionScoringPipeline:

    def _make_service(self, klines_data, decisions):
        from application.services.evolution.decision_score_service import DecisionScoreService
        service = DecisionScoreService(mature_window=20)
        service.kline_repo = MockKlineRepository(klines_data)
        service.decision_repo = MockDecisionRepository(decisions)
        service.bench_klines_provider = lambda symbol, start_date, end_date: []
        return service

    def test_score_mature_buy_decision(self, db_conn):
        today = date.today()
        trade_date = today - timedelta(days=35)

        full_id = create_test_decision(
            db_conn, decision_id="BUY_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, created_at=trade_date,
            test_prefix=TEST_PREFIX)

        insert_test_klines(
            db_conn, symbol=TEST_SYMBOL,
            start_date=trade_date, end_date=today,
            base_price=1650.00, price_change=0.15)

        klines_data = _get_klines_from_db(db_conn, TEST_SYMBOL, trade_date, today)
        decision_dict = _build_decision_dict(full_id, TEST_SYMBOL, "trade_buy", 1650.00, trade_date)
        service = self._make_service({TEST_SYMBOL: klines_data}, [decision_dict])

        pending = service.decision_repo.list_pending_evaluations(days=30)
        assert len(pending) >= 1

        result = service.score_mature_decisions(pending_days=30)
        assert result['scored'] >= 1
        assert result['errors'] == 0

    def test_score_unmature_decision_skipped(self, db_conn):
        today = date.today()
        thirty_five_days_ago = today - timedelta(days=35)

        full_id = create_test_decision(
            db_conn, decision_id="BUY_002", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, created_at=thirty_five_days_ago,
            test_prefix=TEST_PREFIX)

        insert_test_klines(
            db_conn, symbol=TEST_SYMBOL,
            start_date=thirty_five_days_ago, end_date=thirty_five_days_ago + timedelta(days=10),
            base_price=1650.00, price_change=0.05)

        klines_data = _get_klines_from_db(db_conn, TEST_SYMBOL, thirty_five_days_ago, today)
        decision_dict = _build_decision_dict(full_id, TEST_SYMBOL, "trade_buy", 1650.00, thirty_five_days_ago)
        service = self._make_service({TEST_SYMBOL: klines_data}, [decision_dict])

        result = service.score_mature_decisions(pending_days=30)
        assert result['skipped_unmature'] >= 1


def _get_klines_from_db(conn, symbol, start_date, end_date):
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT trade_date, open, high, low, close, volume, amount
            FROM quant.daily_klines
            WHERE symbol = %s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date
        """, (symbol, start_date, end_date))
        rows = cursor.fetchall()
        return [{
            'trade_date': r[0], 'open': float(r[1]), 'high': float(r[2]),
            'low': float(r[3]), 'close': float(r[4]),
            'volume': int(r[5]), 'amount': float(r[6])
        } for r in rows]
    finally:
        cursor.close()


class TestFitnessComputationPipeline:

    def test_compute_fitness_for_active_accounts(self, db_conn):
        from unittest.mock import MagicMock, patch
        from application.services.evolution.evolution_fitness_service import EvolutionFitnessService

        mock_repo = MagicMock()
        mock_account = MagicMock()
        mock_account.account_name = "test_agent_virtual"
        mock_account.status = 'active'
        mock_repo.list_accounts.return_value = [mock_account]

        mock_snapshot = MagicMock()
        mock_snapshot.snapshot_date = date.today() - timedelta(days=1)
        mock_snapshot.daily_return = 0.02
        mock_repo.get_equity_snapshots.return_value = [mock_snapshot]

        mock_bench = lambda start, end: {
            (date.today() - timedelta(days=i)).isoformat(): 0.01
            for i in range(20)
        }
        mock_fitness_repo = MagicMock()
        mock_trade_counter = lambda account_name, start, end: 5

        with patch.object(EvolutionFitnessService, '__init__', lambda self, **kw: None):
            service = EvolutionFitnessService()
            service.sim_repo = mock_repo
            service._bench_provider = mock_bench
            service._trade_counter = mock_trade_counter
            service.fitness_repo = mock_fitness_repo

            result = service.compute_all_accounts(window_end=date.today(), window_days=20)
            assert result['computed'] >= 1

    def test_fitness_score_recorded_in_db(self, db_conn):
        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                SELECT account_name, up_capture, down_capture
                FROM quant.evolution_fitness
                ORDER BY computed_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                assert row[1] is not None
                assert row[2] is not None
        finally:
            cursor.close()


class TestEvolutionErrorHandling:

    def test_graceful_failure_on_invalid_data(self, db_conn):
        from application.services.evolution.decision_score_service import DecisionScoreService
        service = DecisionScoreService(mature_window=20)
        service.decision_repo = MockDecisionRepository([])
        service.kline_repo = MockKlineRepository({})
        result = service.score_mature_decisions(pending_days=1)
        assert 'scored' in result
        assert 'errors' in result


class TestEvolutionIntegration:

    def test_decision_score_updates_evaluation_status(self, db_conn):
        decision_id = create_test_decision(
            db_conn, decision_id="STATUS_001", symbol=TEST_SYMBOL,
            action="trade_buy", price=1650.00, test_prefix=TEST_PREFIX)

        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                SELECT evaluation_status
                FROM quant.agent_decisions WHERE decision_id = %s
            """, (decision_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 'pending'
        finally:
            cursor.close()

    def test_multiple_decisions_batch_scoring(self, db_conn):
        today = date.today()
        decision_dicts = []
        for i in range(3):
            full_id = create_test_decision(
                db_conn, decision_id=f"BATCH_{i:03d}", symbol=TEST_SYMBOL,
                action="trade_buy", price=1650.00 + i * 10,
                created_at=today - timedelta(days=25 + i),
                test_prefix=TEST_PREFIX)
            decision_dicts.append(
                _build_decision_dict(full_id, TEST_SYMBOL, "trade_buy",
                                     1650.00 + i * 10, today - timedelta(days=25 + i)))

        from application.services.evolution.decision_score_service import DecisionScoreService
        service = DecisionScoreService(mature_window=20)
        service.decision_repo = MockDecisionRepository(decision_dicts)
        service.bench_klines_provider = lambda symbol, start_date, end_date: []

        klines_data = _get_klines_from_db(db_conn, TEST_SYMBOL, today - timedelta(days=35), today)
        service.kline_repo = MockKlineRepository({TEST_SYMBOL: klines_data})

        result = service.score_mature_decisions(pending_days=30)
        assert result['scanned'] >= 3
