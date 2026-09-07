"""测试StrategyRepository"""
import pytest
from adapters.outbound.repositories import StrategyORMRepository


class TestStrategyRepository:
    """测试策略仓储"""

    @pytest.fixture
    def strategy_repo(self, db_connection):
        """创建策略仓储实例"""
        repo = StrategyORMRepository()
        repo.db = db_connection
        return repo

    @pytest.fixture
    def test_strategy_id(self, db_connection):
        """创建测试策略并返回ID"""
        cursor = db_connection.cursor()

        # 插入测试策略
        cursor.execute("""
            INSERT INTO quant.strategy_configs
            (strategy_name, strategy_type, parameters, validation_status, is_active)
            VALUES ('测试策略', 'custom', '{}', 'valid', true)
            RETURNING id
        """)
        result = cursor.fetchone()
        strategy_id = result['id']
        db_connection.commit()
        cursor.close()

        yield strategy_id

        # 清理：删除测试策略
        cursor = db_connection.cursor()
        cursor.execute("DELETE FROM quant.strategy_configs WHERE id = %s", (strategy_id,))
        db_connection.commit()
        cursor.close()

    def test_update_validation_status(self, strategy_repo, test_strategy_id):
        """测试更新策略验证状态"""
        # Act - 更新为 invalid
        result = strategy_repo.update_validation_status(test_strategy_id, 'invalid')

        # Assert
        assert result is not None
        assert result['validation_status'] == 'invalid'

        # 验证数据库中的值
        strategy = strategy_repo.get_by_id(test_strategy_id)
        assert strategy['validation_status'] == 'invalid'

        # Cleanup - 恢复为 valid
        strategy_repo.update_validation_status(test_strategy_id, 'valid')

    def test_update_validation_status_with_errors(self, strategy_repo, test_strategy_id):
        """测试更新策略验证状态并记录错误信息"""
        # Act
        error_msg = "语法错误：第10行缺少括号"
        result = strategy_repo.update_validation_status(
            test_strategy_id,
            'invalid',
            errors=error_msg
        )

        # Assert
        assert result is not None
        assert result['validation_status'] == 'invalid'
        assert result['validation_errors'] == error_msg

        # Cleanup
        strategy_repo.update_validation_status(test_strategy_id, 'valid', errors=None)

    def test_update_validation_status_invalid_status(self, strategy_repo, test_strategy_id):
        """测试使用无效的状态值"""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            strategy_repo.update_validation_status(test_strategy_id, 'unknown')

        assert "status 必须是" in str(exc_info.value)

    def test_update_validation_status_nonexistent_strategy(self, strategy_repo):
        """测试更新不存在的策略"""
        # Act
        result = strategy_repo.update_validation_status(999999, 'valid')

        # Assert
        assert result is None

    def test_save_validation_report(self, strategy_repo, test_strategy_id):
        """测试保存验证报告"""
        # Arrange
        report_data = {
            'strategy_id': test_strategy_id,
            'score': 75.5,
            'status': 'passed',
            'annual_return': 0.15,
            'sharpe_ratio': 1.8,
            'max_drawdown': -0.12,
            'win_rate': 0.62,
            'profit_factor': 2.1,
            'backtest_count': 400,
            'error_count': 5,
            'start_date': '2024-05-27',
            'end_date': '2026-05-27'
        }

        # Act
        report_id = strategy_repo.save_validation_report(report_data)

        # Assert
        assert report_id is not None
        assert isinstance(report_id, int)
