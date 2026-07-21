import pytest
from unittest.mock import MagicMock
from infrastructure.persistence.database.base_repository import BaseRepository

class TestBaseRepository:
    def test_validate_symbol_valid(self):
        repo = BaseRepository()
        assert repo._validate_symbol("000001") == True
        assert repo._validate_symbol("000001") == True

    def test_validate_symbol_empty(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_symbol("")

    def test_validate_symbol_wrong_length(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_symbol("1234")

    def test_validate_symbol_none(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_symbol(None)

    def test_validate_date_valid(self):
        repo = BaseRepository()
        assert repo._validate_date("2026-05-20") == True

    def test_validate_date_invalid_month(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_date("2026-13-01")

    def test_validate_date_invalid_format(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_date("invalid")

    def test_validate_positive_number_valid(self):
        repo = BaseRepository()
        assert repo._validate_positive_number(100.0, "price") == True

    def test_validate_positive_number_zero(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_positive_number(0, "price")

    def test_validate_positive_number_negative(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_positive_number(-10, "price")

    def test_to_domain_object_identity(self):
        repo = BaseRepository()
        row = {"symbol": "000001", "name": "浦发银行"}
        assert repo._to_domain_object(row) == row

    def test_to_db_row_identity(self):
        repo = BaseRepository()
        obj = {"symbol": "000001", "name": "浦发银行"}
        assert repo._to_db_row(obj) == obj


class TestConnectionLifecycle:
    """连接生命周期测试：验证 Engine 池连接归还、释放幂等、context manager。

    这些测试覆盖 SQLAlchemy Engine 迁移后的关键路径，全程用 mock，
    不接触真实数据库。
    """

    @pytest.fixture
    def fake_engine(self, monkeypatch):
        """Mock 全局 Engine,测试后还原。"""
        import infrastructure.persistence.database.engine as engine_module

        saved_engine = engine_module._engine
        saved_initialized = engine_module._engine_initialized

        # 创建 mock Engine
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_dbapi_conn = MagicMock()

        # SQLAlchemy Connection 对象有 .connection 属性指向底层 DBAPI conn
        mock_conn.connection = mock_dbapi_conn
        mock_engine.connect.return_value = mock_conn

        engine_module._engine = mock_engine
        engine_module._engine_initialized = True

        try:
            yield mock_engine, mock_conn
        finally:
            engine_module._engine = saved_engine
            engine_module._engine_initialized = saved_initialized

    def test_engine_connection_returned_on_close(self, fake_engine):
        """Engine 池连接 close() 时应调用 SQLAlchemy Connection.close() 归还池。"""
        mock_engine, mock_conn = fake_engine

        repo = BaseRepository()
        # 触发 lazy 连接获取
        _ = repo._get_connection()

        assert repo._sqlalchemy_conn is mock_conn
        assert repo.db is mock_conn.connection

        repo.close()
        mock_conn.close.assert_called_once()
        assert repo._sqlalchemy_conn is None
        assert repo.db is None

    def test_release_is_idempotent(self, fake_engine):
        """重复释放只归还一次。"""
        mock_engine, mock_conn = fake_engine

        repo = BaseRepository()
        _ = repo._get_connection()

        repo.close()
        repo.close()
        repo.__del__()

        # close 只调用一次
        assert mock_conn.close.call_count == 1

    def test_context_manager_releases(self, fake_engine):
        """with 语句退出时自动归还连接。"""
        mock_engine, mock_conn = fake_engine

        with BaseRepository() as repo:
            _ = repo._get_connection()

        mock_conn.close.assert_called_once()

    def test_external_connection_not_released(self):
        """外部传入的连接不应被 close() 释放。"""
        # 用 spec 限制 mock 的属性,避免自动生成 .connection.cursor 被误判为 SQLAlchemy Connection
        external_conn = MagicMock(spec=['cursor', 'commit', 'rollback', 'close'])
        repo = BaseRepository(db_connection=external_conn)

        assert repo.db is external_conn
        assert repo._owns_connection is False

        repo.close()
        # 外部连接不归还
        external_conn.close.assert_not_called()

    def test_get_cursor_triggers_lazy_connection(self, fake_engine):
        """_get_cursor() 应 lazy 触发连接获取。"""
        mock_engine, mock_conn = fake_engine
        mock_dbapi_conn = mock_conn.connection
        mock_cursor = MagicMock()
        mock_dbapi_conn.cursor.return_value = mock_cursor

        repo = BaseRepository()
        # 初始未连接
        assert repo._sqlalchemy_conn is None

        cursor = repo._get_cursor()

        # lazy 连接已建立
        mock_engine.connect.assert_called_once()
        mock_dbapi_conn.cursor.assert_called_once()
        assert cursor is mock_cursor

