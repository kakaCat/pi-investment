import pytest
from domain.quantlib.core.validators import validate_symbol, validate_date, validate_required, validate_positive

class TestValidateSymbol:
    def test_valid(self):
        assert validate_symbol("000001") == True

    def test_empty(self):
        with pytest.raises(ValueError):
            validate_symbol("")

    def test_wrong_length(self):
        try:
            result = validate_symbol("1234")
            assert result is False or result is None
        except ValueError:
            pass  # Also acceptable

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
