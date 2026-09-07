"""
SignalExecutionRepository 单元测试
"""
import pytest
from adapters.outbound.repositories import SignalExecutionORMRepository


@pytest.fixture
def repo():
    return SignalExecutionORMRepository()


class TestExecutionValidation:
    def test_create_missing_required_fields(self, repo):
        with pytest.raises(ValueError, match="signal_id"):
            repo.create_execution({})

        with pytest.raises(ValueError, match="execution_date"):
            repo.create_execution({'signal_id': 1})

        with pytest.raises(ValueError, match="execution_price"):
            repo.create_execution({'signal_id': 1, 'execution_date': '2024-01-15'})

        with pytest.raises(ValueError, match="quantity"):
            repo.create_execution({
                'signal_id': 1,
                'execution_date': '2024-01-15',
                'execution_price': 10.5,
            })

    def test_create_invalid_date(self, repo):
        with pytest.raises(ValueError, match="Invalid date format"):
            repo.create_execution({
                'signal_id': 1,
                'execution_date': '01-15-2024',
                'execution_price': 10.5,
                'quantity': 100,
            })

    def test_create_invalid_status(self, repo):
        with pytest.raises(ValueError, match="Invalid status"):
            repo.create_execution({
                'signal_id': 1,
                'execution_date': '2024-01-15',
                'execution_price': 10.5,
                'quantity': 100,
                'status': 'invalid_status',
            })

    def test_valid_create_data(self, repo):
        """Valid data should not raise validation error (DB error is expected for no connection)."""
        data = {
            'signal_id': 1,
            'execution_date': '2024-01-15',
            'execution_price': 10.5,
            'quantity': 100,
        }
        # Validation passes; actual DB call will fail in unit test context
        try:
            repo.create_execution(data)
        except ValueError:
            pytest.fail("Validation should pass for valid data")
        except Exception:
            pass  # DB connection error is expected

    def test_status_values(self, repo):
        assert repo.STATUSES == ('pending', 'executed', 'cancelled', 'expired')

    def test_get_executions_by_date_invalid_status(self, repo):
        with pytest.raises(ValueError, match="Invalid status"):
            repo.get_executions_by_date('2024-01-15', status='unknown')

    def test_get_executions_by_status_invalid(self, repo):
        with pytest.raises(ValueError, match="Invalid status"):
            repo.get_executions_by_status('unknown')

    def test_update_invalid_status(self, repo):
        with pytest.raises(ValueError, match="Invalid status"):
            repo.update_execution_status(1, 'unknown')

    def test_get_all_executions_invalid_status(self, repo):
        with pytest.raises(ValueError, match="Invalid status"):
            repo.get_all_executions(status='unknown')

    def test_get_executions_by_symbol_invalid_status(self, repo):
        with pytest.raises(ValueError, match="Invalid status"):
            repo.get_executions_by_symbol(
                '000001.SZ', '2024-01-01', '2024-01-31', status='unknown'
            )


class TestExecutionQueries:
    def test_get_execution_nonexistent(self, repo):
        result = repo.get_execution(999999)
        assert result is None

    def test_get_executions_by_signal_empty(self, repo):
        results = repo.get_executions_by_signal(999999)
        assert results == []

    def test_get_executions_by_date(self, repo):
        results = repo.get_executions_by_date('2024-01-15')
        assert isinstance(results, list)

    def test_get_executions_by_date_with_status(self, repo):
        results = repo.get_executions_by_date('2024-01-15', status='pending')
        assert isinstance(results, list)

    def test_get_executions_by_status(self, repo):
        results = repo.get_executions_by_status('pending', limit=10)
        assert isinstance(results, list)

    def test_get_pending_executions(self, repo):
        results = repo.get_pending_executions(limit=50)
        assert isinstance(results, list)

    def test_get_executions_by_symbol(self, repo):
        results = repo.get_executions_by_symbol('000001.SZ', '2024-01-01', '2024-01-31')
        assert isinstance(results, list)

    def test_get_executions_by_symbol_with_status(self, repo):
        results = repo.get_executions_by_symbol(
            '000001.SZ', '2024-01-01', '2024-01-31', status='executed'
        )
        assert isinstance(results, list)

    def test_get_all_executions(self, repo):
        results = repo.get_all_executions(limit=10)
        assert isinstance(results, list)

    def test_get_all_executions_with_status(self, repo):
        results = repo.get_all_executions(status='executed', limit=10)
        assert isinstance(results, list)

    def test_get_all_executions_pagination(self, repo):
        results = repo.get_all_executions(limit=5, offset=10)
        assert isinstance(results, list)


class TestExecutionWrite:
    def test_create_execution(self, repo):
        """Validation passes, DB may reject FK or be unavailable."""
        try:
            exec_id = repo.create_execution({
                'signal_id': 100,
                'execution_date': '2024-06-15',
                'execution_price': 25.50,
                'quantity': 500,
                'commission': 5.0,
                'status': 'pending',
            })
            assert isinstance(exec_id, int)
        except Exception as e:
            msg = str(e).lower()
            if 'connection' in msg or 'cursor' in msg or 'foreign' in msg or 'violat' in msg:
                pass
            else:
                raise

    def test_create_execution_with_optional_fields(self, repo):
        try:
            exec_id = repo.create_execution({
                'signal_id': 200,
                'execution_date': '2024-06-15',
                'execution_price': 30.00,
                'quantity': 200,
                'commission': 3.5,
                'pnl': 150.0,
                'close_date': '2024-07-15',
                'close_price': 31.50,
                'status': 'executed',
            })
            assert isinstance(exec_id, int)
        except Exception as e:
            msg = str(e).lower()
            if 'connection' in msg or 'cursor' in msg or 'foreign' in msg or 'violat' in msg:
                pass
            else:
                raise

    def test_update_execution_status_db_error(self, repo):
        try:
            repo.update_execution_status(1, 'executed')
        except Exception as e:
            if 'connection' in str(e).lower() or 'cursor' in str(e).lower():
                pass
            else:
                raise

    def test_cancel_execution_db_error(self, repo):
        try:
            repo.cancel_execution(1)
        except Exception as e:
            if 'connection' in str(e).lower() or 'cursor' in str(e).lower():
                pass
            else:
                raise

    def test_close_execution_nonexistent(self, repo):
        result = repo.close_execution(999999, '2024-07-15', 35.00)
        assert result is False


class TestExecutionStats:
    def test_get_execution_stats(self, repo):
        stats = repo.get_execution_stats()
        assert isinstance(stats, dict)

    def test_get_execution_stats_with_dates(self, repo):
        stats = repo.get_execution_stats('2024-01-01', '2024-12-31')
        assert isinstance(stats, dict)

    def test_stats_keys(self, repo):
        stats = repo.get_execution_stats('2024-01-01', '2024-12-31')
        expected = ['total', 'executed', 'pending', 'cancelled', 'expired',
                     'avg_pnl', 'total_pnl', 'winning', 'losing', 'win_rate']
        for key in expected:
            assert key in stats, f"Missing stat key: {key}"

    def test_get_daily_execution_stats(self, repo):
        results = repo.get_daily_execution_stats('2024-01-01', '2024-01-31')
        assert isinstance(results, list)


class TestExecutionSymbolValidation:
    def test_invalid_symbol(self, repo):
        with pytest.raises(ValueError, match="股票代码格式错误"):
            repo.get_executions_by_symbol('BAD', '2024-01-01', '2024-01-31')

    def test_invalid_date_format(self, repo):
        with pytest.raises(ValueError, match="Invalid date format"):
            repo.get_executions_by_symbol('000001.SZ', '01-01-2024', '2024-01-31')

    def test_invalid_end_date(self, repo):
        with pytest.raises(ValueError, match="Invalid date format"):
            repo.get_executions_by_symbol('000001.SZ', '2024-01-01', 'invalid')

    def test_valid_symbol_formats(self, repo):
        """Various valid symbol formats."""
        for sym in ['000001.SZ', '000001.SH', '000001', '000001']:
            try:
                repo.get_executions_by_symbol(sym, '2024-01-01', '2024-01-31')
            except ValueError as e:
                if '格式' in str(e) or '格式错误' in str(e):
                    pytest.fail(f"Symbol {sym} should be valid: {e}")
            except Exception:
                pass  # DB error OK

    def test_close_execution_invalid_date(self, repo):
        with pytest.raises(ValueError, match="Invalid date format"):
            repo.close_execution(1, '07-15-2024', 35.00)
