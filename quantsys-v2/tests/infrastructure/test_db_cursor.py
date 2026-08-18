"""db_cursor 与 validators 基建测试。"""
import pytest


class TestDbCursor:
    def test_read_returns_dict_rows(self):
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor() as cursor:
            cursor.execute("SELECT 1 AS one")
            row = cursor.fetchone()
        assert isinstance(row, dict)
        assert row["one"] == 1

    def test_write_commits_when_commit_true(self):
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                "CREATE TEMP TABLE t_db_cursor_wp1 (id int)"
            )
        # TEMP TABLE 随连接归池 rollback 消失属正常；此处只验证不抛异常

    def test_exception_rolls_back_and_reraises(self):
        from infrastructure.persistence.database.engine import db_cursor
        with pytest.raises(Exception, match="boom_wp1"):
            with db_cursor(commit=True) as cursor:
                raise Exception("boom_wp1")

    def test_connection_returned_to_pool(self):
        """连续获取超过 pool_size 次数不阻塞 = 连接确实归还。"""
        from infrastructure.persistence.database.engine import db_cursor
        for _ in range(15):
            with db_cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()


class TestValidators:
    def test_validate_symbol_accepts_plain(self):
        from infrastructure.persistence.database.validators import validate_symbol
        assert validate_symbol("600519") is True

    def test_validate_symbol_accepts_suffix(self):
        from infrastructure.persistence.database.validators import validate_symbol
        assert validate_symbol("600519.SH") is True
        assert validate_symbol("000001.sz") is True

    def test_validate_symbol_rejects_empty(self):
        from infrastructure.persistence.database.validators import validate_symbol
        with pytest.raises(ValueError, match="股票代码不能为空"):
            validate_symbol("")

    def test_validate_symbol_rejects_bad_format(self):
        from infrastructure.persistence.database.validators import validate_symbol
        with pytest.raises(ValueError, match="股票代码格式错误"):
            validate_symbol("ABC123")

    def test_validate_date(self):
        from infrastructure.persistence.database.validators import validate_date
        assert validate_date("2026-08-18") is True
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date("2026/08/18")

    def test_validate_positive_number(self):
        from infrastructure.persistence.database.validators import validate_positive_number
        assert validate_positive_number(1.5, "price") is True
        with pytest.raises(ValueError, match="must be positive"):
            validate_positive_number(0, "price")
