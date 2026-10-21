"""ML scaler 工件约定与预测留痕的回归测试（2026-10-19 断链修复）

覆盖两个历史断点：
1. 训练侧 fit 了 StandardScaler 但不落盘 → /api/ml/predict 落入 legacy 特征路径（S1 复发形态）；
2. TraceabilityORMRepository.save_ml_prediction 不存在 → ml_predictions 表永远 0 行。
"""
import pickle

import pytest

from application.services.ml_pipeline.artifacts import (
    DEFAULT_MODEL_DIR,
    save_scaler,
    scaler_path,
)
from adapters.outbound.repositories.traceability_repository import (
    MLPrediction,
    TraceabilityORMRepository,
)


class TestScalerArtifacts:
    """scaler 命名/保存是训练侧与预测侧共享的唯一约定"""

    def test_scaler_path_naming(self, tmp_path):
        p = scaler_path("lightgbm", "20261019_033009", tmp_path)
        assert p == tmp_path / "lightgbm_20261019_033009_scaler.pkl"

    def test_scaler_path_default_dir(self):
        p = scaler_path("xgboost", "v1")
        assert p.parent == DEFAULT_MODEL_DIR

    def test_save_scaler_roundtrip(self, tmp_path):
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler().fit([[1.0, 2.0], [3.0, 4.0]])
        path = save_scaler(scaler, "lightgbm", "20261019_120000", tmp_path)

        assert path.exists()
        with open(path, "rb") as f:
            loaded = pickle.load(f)
        assert list(loaded.mean_) == list(scaler.mean_)

    def test_save_scaler_creates_parent_dir(self, tmp_path):
        nested = tmp_path / "a" / "b"
        path = save_scaler(object(), "lightgbm", "v9", nested)
        assert path.exists()


class TestSaveMlPrediction:
    """save_ml_prediction 必须真实存在且写 MLPrediction 行"""

    def test_method_exists_on_repository(self):
        assert hasattr(TraceabilityORMRepository, "save_ml_prediction")

    def test_orm_model_table(self):
        assert MLPrediction.__tablename__ == "ml_predictions"
        assert MLPrediction.__table_args__ == {"schema": "quant"}

    def test_save_ml_prediction_persists_row(self):
        from unittest.mock import PropertyMock, patch

        repo = TraceabilityORMRepository.__new__(TraceabilityORMRepository)
        added = []

        class FakeSession:
            def add(self, row):
                added.append(row)

            def commit(self):
                pass

        with patch.object(type(repo), "session", new_callable=PropertyMock) as mock_session:
            mock_session.return_value = FakeSession()
            repo.save_ml_prediction({
                "execution_id": "exec-1",
                "symbol": "600519",
                "prediction_time": "2026-10-19T15:00:00+08:00",
                "model_type": "lightgbm",
                "model_version": "20261019_033009",
                "feature_count": 32,
                "prediction": 1,
                "confidence": "high",
                "prob_down": 0.24,
                "prob_up": 0.76,
            })

        # FakeSession 不会赋 id，但行必须已被 add 且字段正确
        assert len(added) == 1
        row = added[0]
        assert isinstance(row, MLPrediction)
        assert row.symbol == "600519"
        assert row.model_type == "lightgbm"
        assert row.model_version == "20261019_033009"
        assert row.prediction == 1
        assert row.prob_up == pytest.approx(0.76)
        assert row.prediction_time is not None and row.prediction_time.tzinfo is not None

    def test_save_ml_prediction_failure_returns_minus_one(self):
        from unittest.mock import PropertyMock, patch

        repo = TraceabilityORMRepository.__new__(TraceabilityORMRepository)

        class BoomSession:
            def add(self, row):
                raise RuntimeError("db down")

        repo._safe_rollback = lambda: None
        with patch.object(type(repo), "session", new_callable=PropertyMock) as mock_session:
            mock_session.return_value = BoomSession()
            assert repo.save_ml_prediction({"symbol": "600519"}) == -1
