"""
SignalExecutionRepository 单元测试
"""
import pytest
from adapters.outbound.repositories import SignalExecutionORMRepository


@pytest.fixture
def repo():
    return SignalExecutionORMRepository()


    # 2026-09-14（w-c8cae280）已删除 get_executions_by_symbol 相关用例（含非法入参那组）：
    # signal_executions 表**没有 symbol 列**（只有 signal_id + relationship），按标的查需 join 信号表；
    # 仓库层已有 get_executions_by_signal(signal_id)，且生产调用数 0 → 属数据模型决定的能力边界。
class TestExecutionValidation:
    """2026-10-23 重写：仓储契约已从 dict 入参改为位置参数
    （create_execution(signal_id, execution_date, execution_price, quantity, ...)），
    并补齐入参校验（此前非法日期/状态直接落库或被吞成 None）。"""

    def test_create_missing_required_fields(self, repo):
        # 位置参数缺失由 Python 自身拒绝
        with pytest.raises(TypeError):
            repo.create_execution(1, '2024-01-15', 10.5)  # 缺 quantity

        # 传空值走仓储校验
        with pytest.raises(ValueError, match="signal_id"):
            repo.create_execution(None, '2024-01-15', 10.5, 100)
        with pytest.raises(ValueError, match="execution_date"):
            repo.create_execution(1, '', 10.5, 100)
        with pytest.raises(ValueError, match="execution_price"):
            repo.create_execution(1, '2024-01-15', None, 100)
        with pytest.raises(ValueError, match="quantity"):
            repo.create_execution(1, '2024-01-15', 10.5, None)
        with pytest.raises(ValueError, match="execution_price"):
            repo.create_execution(1, '2024-01-15', 0, 100)
        with pytest.raises(ValueError, match="quantity"):
            repo.create_execution(1, '2024-01-15', 10.5, 0)

    def test_create_invalid_date(self, repo):
        with pytest.raises(ValueError, match="Invalid date format"):
            repo.create_execution(1, '01-15-2024', 10.5, 100)

    def test_create_invalid_status(self, repo):
        with pytest.raises(ValueError, match="Invalid status"):
            repo.create_execution(1, '2024-01-15', 10.5, 100, status='invalid_status')

    def test_valid_create_data(self, repo):
        """合法入参不应抛校验错误（无连接时仓储吞掉 DB 错并返回 None）。"""
        result = repo.create_execution(1, '2024-01-15', 10.5, 100)
        # 校验通过；DB 不可用时返回 None，可用时有 id
        assert result is None or getattr(result, 'id', None) is not None

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
        """合法入参：可用时返回记录，不可用时 None（仓储吞 DB 错）。"""
        result = repo.create_execution(
            100, '2024-06-15', 25.50, 500, commission=5.0, status='pending')
        assert result is None or getattr(result, 'id', None) is not None

    def test_create_execution_with_status_executed(self, repo):
        """status 可显式指定（合法值内）。"""
        result = repo.create_execution(
            200, '2024-06-15', 30.00, 200, commission=3.5, status='executed')
        assert result is None or getattr(result, 'id', None) is not None
        # close_date/close_price/pnl 由 close_execution 负责，不在创建时提供

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
    def test_close_execution_invalid_date(self, repo):
        with pytest.raises(ValueError, match="Invalid date format"):
            repo.close_execution(1, '07-15-2024', 35.00)
