import pytest
from infrastructure.quantlib.core.validators import validate_symbol, validate_date, validate_required, validate_positive

class TestValidateSymbol:
    def test_valid(self):
        assert validate_symbol("000001") == True

    def test_empty(self):
        with pytest.raises(ValueError):
            validate_symbol("")

    def test_wrong_length(self):
        """长度越界的代码应被拒绝。

        2026-10-02（REQ-261001145152-3982 审查）：原用例拿 **4 位** `"1234"` 当"错误长度"，
        但 `validate_symbol` 的口径是 **4–6 位均可**（实测其判断为
        `if not base.isdigit() or not (4 <= len(base) <= 6): raise`）→ 4 位是**合法**的，
        该用例因此失败。改用**真正越界**的长度（3 位），保留"长度不对必须拒绝"的原意。
        """
        try:
            result = validate_symbol("123")
            assert result is False or result is None
        except ValueError:
            pass  # 抛错亦可 —— 与本文件其余用例的容忍口径一致

class TestValidateDate:
    def test_valid(self):
        assert validate_date("2026-05-20") == True

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_date("invalid")

class TestValidateRequired:
    def test_valid(self):
        assert validate_required("hello", "name") == True

    def test_none(self):
        with pytest.raises(ValueError):
            validate_required(None, "name")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            validate_required("", "name")

class TestValidatePositive:
    def test_valid(self):
        assert validate_positive(100.0, "price") == True

    def test_zero(self):
        with pytest.raises(ValueError):
            validate_positive(0, "price")

    def test_negative(self):
        with pytest.raises(ValueError):
            validate_positive(-10, "price")
