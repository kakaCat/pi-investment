"""
MLflow管理测试 - Team B
"""
import pytest
import sys
import os


from domain.quantlib.ml.mlflow_manager import MLflowManager


class TestMLflowManager:
    """MLflow管理测试"""

    @pytest.fixture
    def manager(self):
        """创建管理器实例"""
        return MLflowManager(experiment_name="test_experiment")

    def test_initialization(self, manager):
        """测试初始化"""
        assert manager is not None
        assert manager.experiment_name == "test_experiment"

    def test_start_end_run(self, manager):
        """测试开始和结束运行"""
        run_id = manager.start_run("test_run")
        assert run_id is not None

        manager.end_run()
        assert manager.current_run is None

    def test_log_params(self, manager):
        """测试记录参数"""
        manager.start_run()
        manager.log_params({'param1': 'value1', 'param2': 42})
        manager.end_run()

    def test_log_metrics(self, manager):
        """测试记录指标"""
        manager.start_run()
        manager.log_metrics({'accuracy': 0.95, 'loss': 0.05})
        manager.end_run()

    def test_log_model(self, manager):
        """测试记录模型"""
        from sklearn.linear_model import LinearRegression
        model = LinearRegression()

        manager.start_run()
        model_uri = manager.log_model(model, "test_model")
        assert model_uri is not None
        manager.end_run()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
