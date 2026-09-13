"""日期归一共用实现测试（2026-09-13 w-c8cae280）

为什么单独测：全库曾有 4 份各自实现的 _as_date，守卫漂移导致"对 date 调 .date()"反复出事。
本组用例把"各形态都要吃、不可解析要显式给 default"钉死，避免再退化。
"""
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

# 向上找到 quantsys-v2 根（含 domain/ 的目录）——不写死层级，避免测试挪位置就崩
_root = Path(__file__).resolve()
while _root.parent != _root and not (_root / "domain").is_dir():
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from domain.common.dates import as_date, as_datetime, as_date_str  # noqa: E402


class TestAsDate:
    @pytest.mark.parametrize("value,expected", [
        (datetime(2026, 9, 13, 15, 30), date(2026, 9, 13)),
        (date(2026, 9, 13), date(2026, 9, 13)),
        ("2026-09-13", date(2026, 9, 13)),
        ("2026-09-13T15:30:00", date(2026, 9, 13)),
        ("2026-09-13 15:30:00+08:00", date(2026, 9, 13)),
        ("  2026-09-13  ", date(2026, 9, 13)),
    ])
    def test_supported_shapes(self, value, expected):
        assert as_date(value) == expected

    @pytest.mark.parametrize("value", ["", "   ", "garbage", 12345, [], {}])
    def test_unparsable_returns_default_not_raise(self, value):
        assert as_date(value) is None
        assert as_date(value, default=date(2000, 1, 1)) == date(2000, 1, 1)

    def test_datetime_is_checked_before_date(self):
        # datetime 是 date 的子类：顺序错会丢时间信息（本用例防的就是顺序退化）
        assert as_date(datetime(2026, 9, 13, 23, 59)) == date(2026, 9, 13)

    def test_none(self):
        assert as_date(None) is None


class TestAsDatetime:
    def test_date_becomes_midnight(self):
        assert as_datetime(date(2026, 9, 13)) == datetime(2026, 9, 13, 0, 0)

    def test_datetime_passthrough_keeps_tz(self):
        aware = datetime(2026, 9, 13, 9, 30)
        assert as_datetime(aware) is aware

    def test_unparsable_uses_default(self):
        fallback = datetime(2000, 1, 1)
        assert as_datetime("nope", default=fallback) is fallback


class TestAsDateStr:
    def test_iso(self):
        assert as_date_str(datetime(2026, 9, 13, 1, 2)) == "2026-09-13"
        assert as_date_str("garbage", default="fallback") == "fallback"

    def test_flag_objects_are_not_dates(self):
        # 曾经的坑：把 datetime.date 误当 datetime 而调 .date()
        d = date(2026, 9, 13)
        assert as_date(d) == d and as_date_str(d) == "2026-09-13"
