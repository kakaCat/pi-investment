"""sanitize_for_json 契约测试（2026-09-11, w-8f2c4cc5）

根因链：sanitize_for_json 曾对未知类型 return obj，导致响应边界 500：
① /api/backtest/results：BacktestResult（有 to_dict、非 dict）→ json.dumps TypeError
② /api/signals：Signal.metadata 是 SQLAlchemy MetaData（tables→Table→metadata 自引用环）
   → FastAPI jsonable_encoder 无限递归 RecursionError
本测试锁定「sanitize 结果必然可 JSON 序列化」这一契约。
"""
import json
import dataclasses
import datetime
import decimal
import enum

from adapters.shared.json_helpers import sanitize_for_json


class _Color(enum.Enum):
    RED = 'red'


@dataclasses.dataclass
class _Point:
    x: int
    y: int


class _WithToDict:
    def __init__(self, name):
        self.name = name

    def to_dict(self):
        return {'name': self.name}


class _Unknown:
    """模拟 SQLAlchemy MetaData：无 to_dict、无 isoformat、不可 JSON 序列化"""

    def __str__(self):
        return '<Unknown>'


def _roundtrip(obj):
    return json.loads(json.dumps(sanitize_for_json(obj)))


def test_nan_and_inf_become_none():
    assert _roundtrip([float('nan'), float('inf'), 1.5]) == [None, None, 1.5]


def test_objects_with_to_dict_are_serializable():
    assert _roundtrip(_WithToDict('a')) == {'name': 'a'}


def test_dataclass_supported():
    assert _roundtrip(_Point(1, 2)) == {'x': 1, 'y': 2}


def test_enum_set_decimal_bytes_supported():
    out = _roundtrip({'e': _Color.RED, 's': {1, 2}, 'd': decimal.Decimal('1.50'), 'b': b'ok'})
    assert out['e'] == 'red'
    assert sorted(out['s']) == [1, 2]
    assert float(out['d']) == 1.5
    assert out['b'] == 'ok'


def test_unknown_object_falls_back_to_str_not_crash():
    assert _roundtrip({'meta': _Unknown()}) == {'meta': '<Unknown>'}


def test_self_referential_container_is_broken_not_infinite():
    cyclic = {'name': 'root'}
    cyclic['self'] = cyclic
    assert _roundtrip(cyclic) == {'name': 'root', 'self': None}


def test_datetime_isoformat_kept():
    out = _roundtrip({'t': datetime.datetime(2026, 9, 11, 0, 39, 0)})
    assert out['t'].startswith('2026-09-11T00:39:00')


def test_multi_level_nesting_and_depth_guard():
    deep = cur = {}
    for i in range(40):
        cur['next'] = {}
        cur = cur['next']
    json.dumps(sanitize_for_json(deep))  # 不抛异常即为通过（超深被截断）
