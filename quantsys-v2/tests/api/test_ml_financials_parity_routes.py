"""FastAPI parity 路由测试：/api/ml/models + /api/v2/stock/{symbol}/financials

回归背景（2026-08-11）：5001 切 FastAPI 后这两个端点只剩 Flask 实现，
agent 的 model_list / data_fetch_financial 工具 404。
另覆盖 _resolve_latest_version 的"DB 记录指向已丢失模型文件"回退。

注：本环境 starlette.testclient 依赖 httpx2（未安装），
故直接调用 handler 函数而非 TestClient（与 tests/api 中现有失败用例同因）。
"""
from unittest.mock import MagicMock, patch

from adapters.inbound.fastapi_app.routes import ml_async, financials_async
from adapters.shared import ml_helpers


class TestMlModelsList:
    def test_list_models_returns_flask_contract(self):
        repo = MagicMock()
        repo.list_models.return_value = [
            {"model_type": "xgboost", "version": "20260524_121831", "status": "ready"},
        ]
        with patch.object(ml_async, "_get_model_repo", return_value=repo):
            body = ml_async.ml_models_list(model_type=None, status="ready", limit=20)
        assert body["success"] is True
        assert body["total"] == 1
        assert body["models"][0]["version"] == "20260524_121831"
        repo.list_models.assert_called_once_with(None, "ready", 20)

    def test_list_models_passes_filters(self):
        repo = MagicMock()
        repo.list_models.return_value = []
        with patch.object(ml_async, "_get_model_repo", return_value=repo):
            body = ml_async.ml_models_list(model_type="xgboost", status="ready", limit=5)
        assert body["success"] is True
        assert body["total"] == 0
        repo.list_models.assert_called_once_with("xgboost", "ready", 5)


class TestFinancialsV2:
    def _make_service(self):
        service = MagicMock()
        data = MagicMock()
        data.to_dict.return_value = {
            "income_statement": [{"date": "2026-03-31"}],
            "balance_sheet": [],
            "cash_flow": [],
            "source": "sina_web",
        }
        service.get_financial_data.return_value = data
        service.was_cache_hit.return_value = True
        return service

    def test_financials_flat_snake_contract(self):
        service = self._make_service()
        with patch.object(financials_async, "get_enhanced_financial_service", return_value=service):
            body = financials_async.get_financial_data_v2(
                symbol="002241", statement_type="all", periods=4, source="auto",
            )
        # 保持 Flask 契约：flat + snake_case + cached 字段（dict 直接返回 = 200）
        assert isinstance(body, dict)
        assert body["success"] is True
        assert body["data"]["income_statement"][0]["date"] == "2026-03-31"
        assert body["data"]["cached"] is True
        service.get_financial_data.assert_called_once_with("002241", "all", 4, "auto")

    def test_financials_rejects_invalid_source(self):
        resp = financials_async.get_financial_data_v2(
            symbol="002241", statement_type="all", periods=4, source="bogus",
        )
        assert resp.status_code == 400
        import json as _j
        assert _j.loads(resp.body)["success"] is False

    def test_financials_service_error_returns_500(self):
        service = MagicMock()
        service.get_financial_data.side_effect = RuntimeError("数据源全挂")
        with patch.object(financials_async, "get_enhanced_financial_service", return_value=service):
            resp = financials_async.get_financial_data_v2(
                symbol="002241", statement_type="all", periods=4, source="auto",
            )
        assert resp.status_code == 500
        import json as _j
        assert _j.loads(resp.body)["success"] is False


class TestResolveLatestVersion:
    """DB 元数据指向已删除的 .pkl 时必须回退到文件系统真实存在的模型"""

    def test_db_record_with_missing_file_falls_back_to_fs(self, tmp_path, monkeypatch):
        # 文件系统只有旧模型
        (tmp_path / "xgboost_20260524_121831.pkl").write_bytes(b"pk")
        monkeypatch.setattr(ml_helpers, "MODEL_DIR", tmp_path)

        repo = MagicMock()
        repo.get_by_type_version.return_value = {
            "version": "20260603_121103",  # DB 最新，但文件已丢失
            "train_date": "2026-06-03T12:11:03+08:00",
        }
        monkeypatch.setattr(ml_helpers, "_get_model_repo", lambda: repo)

        assert ml_helpers._resolve_latest_version("xgboost") == "20260524_121831"

    def test_db_record_with_existing_file_wins(self, tmp_path, monkeypatch):
        (tmp_path / "xgboost_20260524_121831.pkl").write_bytes(b"pk")
        (tmp_path / "xgboost_20260603_121103.pkl").write_bytes(b"pk")
        monkeypatch.setattr(ml_helpers, "MODEL_DIR", tmp_path)

        repo = MagicMock()
        repo.get_by_type_version.return_value = {
            "version": "20260603_121103",
            "train_date": "2026-06-03T12:11:03+08:00",
        }
        monkeypatch.setattr(ml_helpers, "_get_model_repo", lambda: repo)

        assert ml_helpers._resolve_latest_version("xgboost") == "20260603_121103"

    def test_no_db_no_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ml_helpers, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ml_helpers, "_get_model_repo", lambda: None)

        assert ml_helpers._resolve_latest_version("xgboost") is None
