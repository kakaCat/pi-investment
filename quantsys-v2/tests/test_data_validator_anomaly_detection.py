"""REQ-261006133733-1fdf · 异常检测三态与回归锁（T1–T15）

回归背景：`DataValidator.detect_anomalies` 的成交量段迭代了 **polars DataFrame**（应为 `to_dicts()`
的 list[dict]），每次抛 `TypeError: cannot select elements using Sequence with elements of type 'str'`，
又被 `except` 吞成 `has_anomalies=False` —— 于是「异常检测」恒报「无异常」（100% 假阴性），
质量分的异常率分量（20 分）恒得满分，且每只股票留一条 error（今日 4 分钟 7995 条）。

本文件是**锁**：它必须在改前红、改后绿（反例锁见 test-cases.md L1–L4）。
"""
from __future__ import annotations

import re
from pathlib import Path

import polars as pl
import pytest

from application.services.data_quality_service import DataQualityService, _anomaly_state
from application.services.data_validator import DataValidator

REPO_ROOT = Path(__file__).resolve().parents[1]

TWO_STATES = ("ok", "has_anomalies", "unknown_reason")
ALL_KEYS = {
    'ok', 'has_anomalies', 'unknown_reason', 'price_anomalies',
    'volume_anomalies', 'total_anomalies', 'message', 'error',
}


# ============================================================
# 工具
# ============================================================

def _df(rows: int = 40, *, price_spike: bool = False, volume_spike: bool = False) -> pl.DataFrame:
    """构造真 polars DataFrame（价格/量平稳，末行可选尖峰）。"""
    close = [10.0 + (i % 3) * 0.1 for i in range(rows)]
    volume = [1000.0 + (i % 5) for i in range(rows)]
    if price_spike:
        close[-1] = 999.0
    if volume_spike:
        volume[-1] = 9_999_999.0
    return pl.DataFrame({
        'trade_date': [f'2026-01-{i % 28 + 1:02d}' for i in range(rows)],
        'close': close,
        'volume': volume,
    })


class _Repo:
    """按 symbol 路由的假仓储：A 正常 / B 数据不足 / C 抛错。"""

    def __init__(self, df: pl.DataFrame | None = None):
        self._df = df

    def get_daily_klines(self, symbol: str, *args, **kwargs):
        if symbol == 'C.SH':
            raise RuntimeError('boom-provider')
        if self._df is not None:
            return self._df
        return _df(10 if symbol == 'B.SH' else 40)

    def find_duplicate_trade_dates(self, *args, **kwargs):
        return []


def _validator(df: pl.DataFrame | None = None) -> DataValidator:
    return DataValidator(kline_repo=_Repo(df))


class _GapDetector:
    def detect_gaps_batch(self, **kwargs):
        return {s: {'coverage_rate': 100.0, 'missing_days_count': 0} for s in ('A.SH', 'B.SH', 'C.SH')}

    def get_gap_summary(self, gaps):
        return {'total_missing_days': 0, 'avg_coverage_rate': 100.0}


def _service() -> DataQualityService:
    svc = DataQualityService(
        kline_repo=_Repo(), calendar=object(), gap_detector=_GapDetector(), backfiller=object())
    svc._persist_quality_audit = lambda **kwargs: None
    return svc


def _code_lines(path: Path) -> list[str]:
    """粗略剔除注释与模块/函数 docstring，只留可执行行（T15 用）。"""
    out, in_doc = [], False
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0]
        if line.count('"""') % 2 == 1:
            in_doc = not in_doc
            continue
        if in_doc:
            continue
        out.append(line)
    return out


# ============================================================
# T1–T6：三态契约
# ============================================================

def test_three_state_normal_no_anomaly():
    """T1：平稳序列 → ok=True / has_anomalies is False / 无 error。"""
    r = _validator(_df(40)).detect_anomalies('A.SH', '2026-01-01', '2026-03-01')
    assert r['ok'] is True
    assert r['has_anomalies'] is False
    assert r['unknown_reason'] is None
    assert r['total_anomalies'] == 0
    assert r['error'] is None


def test_price_anomaly_is_reported():
    """T2：价格 5σ 尖峰 → price_anomalies 命中且 z_score > 3。"""
    r = _validator(_df(40, price_spike=True)).detect_anomalies('A.SH', '2026-01-01', '2026-03-01')
    assert r['ok'] is True
    assert r['has_anomalies'] is True
    assert r['price_anomalies'], r
    assert r['price_anomalies'][0]['z_score'] > 3


def test_volume_anomaly_is_reported():
    """T3（本缺陷直击点）：成交量尖峰 → volume_anomalies 非空。

    改前：成交量段迭代 polars DataFrame → TypeError 被吞 → has_anomalies=False、
    volume_anomalies=[] ⇒ 本用例红（反例锁 L1）。
    """
    r = _validator(_df(40, volume_spike=True)).detect_anomalies('A.SH', '2026-01-01', '2026-03-01')
    assert r['ok'] is True
    assert r['volume_anomalies'], r
    assert r['total_anomalies'] >= 1


def test_insufficient_data_is_unknown_not_clean():
    """T4：K 线 <30 行 → B 态（has_anomalies is None），既有 message 文案逐字保留。"""
    r = _validator(_df(20)).detect_anomalies('A.SH', '2026-01-01', '2026-03-01')
    assert r['ok'] is True
    assert r['has_anomalies'] is None
    assert r['unknown_reason'] == 'insufficient_data'
    assert r['message'] == 'Insufficient data for anomaly detection'
    assert r['error'] is None


def test_detection_failure_is_not_clean_and_does_not_raise():
    """T5：仓储抛错 → C 态（ok=False、has_anomalies is None、reason 含原因），且方法不抛。"""
    r = _validator().detect_anomalies('C.SH', '2026-01-01', '2026-03-01')
    assert r['ok'] is False
    assert r['has_anomalies'] is None
    assert 'boom-provider' in r['unknown_reason']
    assert r['error'] == r['unknown_reason']
    assert r['total_anomalies'] == 0


def test_key_set_is_backward_compatible():
    """T6：三态返回的键集齐备（只增不改）。"""
    v = _validator(_df(40))
    for r in (
        v.detect_anomalies('A.SH', '2026-01-01', '2026-03-01'),                       # A
        _validator(_df(20)).detect_anomalies('A.SH', '2026-01-01', '2026-03-01'),      # B
        _validator().detect_anomalies('C.SH', '2026-01-01', '2026-03-01'),             # C
    ):
        assert ALL_KEYS <= set(r), set(r)
        assert set(TWO_STATES) <= set(r)


# ============================================================
# T7–T10：质量分四态
# ============================================================

def _score(info: dict, coverage_rate: float = 90.0) -> float:
    """注意：coverage_rate 取 90（**不是 100**）——覆盖率满分时「剔除归一」与「确无异常」
    都得 100，分辨不出两条分支，用例会假绿（本卡复核发现并修正）。"""
    v = _validator(_df(40))
    v.detect_anomalies = lambda *a, **k: info  # 实例属性替换（本仓既有打桩手法）
    return v.get_data_quality_score('A.SH', '2026-01-01', '2026-03-01', coverage_rate)


def test_score_clean_gets_full_component():
    """T7：确无异常 → 异常率分量 20 分（54 + 20 + 20 = 94）。"""
    assert _score({'ok': True, 'has_anomalies': False, 'unknown_reason': None,
                   'total_anomalies': 0}) == 94.0


def test_score_with_anomaly_deducts():
    """T8：2/40 = 5% 异常率 → 分量 0（54 + 20 + 0 = 74）。"""
    assert _score({'ok': True, 'has_anomalies': True, 'unknown_reason': None,
                   'total_anomalies': 2}) == 74.0


def test_score_insufficient_data_renormalizes():
    """T9：数据不足 → 剔除该分量并重新归一 → (54+20)/80*100 = 92.5（**不是** 94）。"""
    assert _score({'ok': True, 'has_anomalies': None, 'unknown_reason': 'insufficient_data',
                   'total_anomalies': 0}) == 92.5


def test_score_detection_failure_gets_zero_component(monkeypatch):
    """T10：检测失败 → 分量 0（54 + 20 + 0 = 74），且必须留一条 error（与 T8 的区分点）。"""
    import application.services.data_validator as dv
    errors = []
    monkeypatch.setattr(dv.logger, 'error', lambda *a, **k: errors.append((a, k)))
    score = _score({'ok': False, 'has_anomalies': None, 'unknown_reason': 'TypeError: x',
                    'total_anomalies': 0})
    assert score == 74.0
    assert errors, '失败路径必须留痕'


# ============================================================
# T11–T13：消费点与汇总计数
# ============================================================

def _run_three_state_check() -> dict:
    return _service().check_data_quality(
        symbols=['A.SH', 'B.SH', 'C.SH'], start_date='2026-01-01', end_date='2026-03-01')


def test_consumer_counts_failure_as_issue():
    """T11：检测失败（C）计入 has_issues，且条目带 anomaly_unknown 三态留痕。"""
    res = _run_three_state_check()
    entry = [e for e in res['stocks_with_issues'] if e['symbol'] == 'C.SH']
    assert entry, res['stocks_with_issues']
    assert entry[0]['anomaly_unknown'] is True
    assert entry[0]['has_anomalies'] is None
    assert 'boom-provider' in entry[0]['anomaly_unknown_reason']


def test_consumer_insufficient_data_not_an_issue():
    """T12：数据不足（B）**不**计入 has_issues（新股不是质量问题），但单独计数。"""
    res = _run_three_state_check()
    assert all(e['symbol'] != 'B.SH' for e in res['stocks_with_issues'])
    assert res['summary']['insufficient_history_count'] == 1


def test_summary_counts_three_states():
    """T13：三态计数各归各位（失败 1 / 数据不足 1），问题清单只含失败那只。"""
    res = _run_three_state_check()
    assert res['summary']['anomaly_unknown_count'] == 1
    assert res['summary']['insufficient_history_count'] == 1
    assert [e['symbol'] for e in res['stocks_with_issues']] == ['C.SH']


def test_anomaly_state_helper_is_backward_compatible():
    """旧形字典（无 ok 键）必须仍被判为 A 态——既有替身/stub 不被误伤。"""
    assert _anomaly_state({'has_anomalies': True, 'total_anomalies': 1}) == (False, False, None)
    assert _anomaly_state({'has_anomalies': False}) == (False, False, None)


# ============================================================
# T14：审计留痕（改前恒为空转）
# ============================================================

def test_audit_records_anomaly_and_unknown(monkeypatch):
    """T14：有异常写 type=anomaly（改前读的 anomalies 键从不存在 → 恒为空）；失败写 unknown。"""
    import adapters.outbound.repositories.kline_quality_repository as kqr

    captured = []

    class _FakeRepo:
        def record_check_result(self, **kwargs):
            captured.append(kwargs)

    monkeypatch.setattr(kqr, 'KlineQualityRepository', _FakeRepo)  # 桩打在被调函数所在模块

    svc = DataQualityService(kline_repo=object(), calendar=object(),
                             gap_detector=object(), backfiller=object())
    gap = {'coverage_rate': 98.0}
    dup = {'has_duplicates': False, 'duplicate_count': 0}
    svc._persist_quality_audit(
        symbol='A.SH', start_date='2026-01-01', end_date='2026-03-01', gap_info=gap,
        dup_info=dup, quality_score=90.0, duration_ms=1,
        anomaly_info={'ok': True, 'has_anomalies': True, 'unknown_reason': None, 'total_anomalies': 2,
                      'price_anomalies': [{'date': '2026-02-01', 'close': 1.0, 'z_score': 4.2}],
                      'volume_anomalies': [{'date': '2026-02-02', 'volume': 9e9, 'z_score': 5.1}]})
    svc._persist_quality_audit(
        symbol='C.SH', start_date='2026-01-01', end_date='2026-03-01', gap_info=gap,
        dup_info=dup, quality_score=70.0, duration_ms=1,
        anomaly_info={'ok': False, 'has_anomalies': None, 'unknown_reason': 'RuntimeError: boom',
                      'total_anomalies': 0, 'price_anomalies': [], 'volume_anomalies': []})

    types_a = [w['type'] for w in captured[0]['warnings_json']]
    assert types_a.count('anomaly') == 2, captured[0]['warnings_json']
    assert captured[1]['warnings_json'][0]['type'] == 'anomaly_detection_unknown'
    assert 'boom' in captured[1]['warnings_json'][0]['reason']


# ============================================================
# T15：静态红线（禁止用真值判断 has_anomalies）
# ============================================================

_BOOL_CTX = re.compile(r'(if|while|and|or|not)\b[^\n]*has_anomalies')
_ALLOWED = ('is True', 'is False', 'is None')


def test_static_no_truthiness_on_has_anomalies():
    """T15：全仓代码里 `has_anomalies` 不得出现在真值语境（`None` 也是假值 → 又会吞成"干净"）。"""
    offenders = []
    for base in ('application', 'adapters', 'infrastructure'):
        for path in (REPO_ROOT / base).rglob('*.py'):
            if 'venv' in path.parts:
                continue
            for i, line in enumerate(_code_lines(path), 1):
                if 'has_anomalies' not in line:
                    continue
                if _BOOL_CTX.search(line) and not any(tok in line for tok in _ALLOWED):
                    offenders.append(f'{path.relative_to(REPO_ROOT)}:{i}: {line.strip()}')
    assert not offenders, offenders
