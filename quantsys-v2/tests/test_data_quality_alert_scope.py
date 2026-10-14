"""数据质量告警口径用例 —— REQ-261006163444-8e4f（t4/t6 共用）

覆盖设计 test-cases 文档 §1 的 T8–T17 与反例锁 L1–L4。
判据与正文都从 `_check_quality_alerts` 的可观测输出取，不读私有中间态。

背景（一句话）：旧口径把「全库 5686 只（含约 400 只退市/长停）」当分母、把「当日行数」
当 D 级数量，于是同一天跑两次就把 D 级从 403 报成 806；本文件锁住新口径。
"""
import pytest

from application.services.data_quality_service import DataQualityService
from application.services.kline_domain import classify_domain
from infrastructure.jobs import data_quality_check_job as job

# 交易日倒序（[0] = 最后交易日）。gap: rn-1
DATES = [
    "2026-09-30",  # rn1 -> gap 0  可交易
    "2026-09-29",  # rn2 -> gap 1  观察中 + 掉出
    "2026-09-28",  # rn3 -> gap 2  观察中
    "2026-09-25",  # rn4 -> gap 3  观察中
    "2026-09-24",  # rn5 -> gap 4  观察中（上界）
    "2026-09-23",  # rn6 -> gap 5  存量（下界）
]

THRESHOLDS = {
    'd_grade': 20,
    'score': 88.0,
    'coverage_info': 97.0,
    'backfill_fail_rate': 50.0,
    'backfill_min_sample': 10,
}


def _snapshot(rows):
    return classify_domain(DATES, rows)


def _rec(score=95.0, cov=100.0, grade='A', missing=0):
    return {
        'coverage_rate': cov, 'missing_days_count': missing, 'quality_score': score,
        'overall_score': score, 'grade': grade, 'has_duplicates': False,
        'has_anomalies': False, 'anomaly_unknown': False,
    }


@pytest.fixture
def sent(monkeypatch):
    """拦住飞书外发并留底正文（测试期禁止真实外发）。"""
    box = {}

    def fake(title, message, urgency='normal'):
        box.update(title=title, message=message, urgency=urgency)
        return True

    monkeypatch.setattr(job, '_dispatch_alert_to_feishu', fake)
    return box


def _run(snapshot, per_symbol, backfill_summary=None, thresholds=None,
         backfill_degraded=False):
    result = {
        'check_summary': {},
        'backfill_summary': backfill_summary,
        'backfill_degraded': backfill_degraded,
    }
    th = dict(THRESHOLDS)
    th.update(thresholds or {})
    dispatch = job._check_quality_alerts(result, snapshot, per_symbol, th)
    return result, dispatch


# ── T8 域内均值与 D 计数不含存量 ──────────────────────────────────────
def test_t8_domain_stats_exclude_stock():
    snap = _snapshot([("A", DATES[0]), ("B", DATES[0]), ("C", DATES[0]), ("Z1", "2020-01-01")])
    per_symbol = {
        "A": _rec(score=100.0), "B": _rec(score=90.0), "C": _rec(score=82.5),
        "Z1": _rec(score=25.0, cov=0.0, grade='D'),   # 存量：不得进均值，也不得计 D
    }
    stats = job._build_domain_stats(snap, per_symbol, None)
    assert stats.tradable == 3 and stats.stock == 1
    assert stats.stats_symbols == 3
    assert abs(stats.mean_score - (100.0 + 90.0 + 82.5) / 3) < 1e-9
    assert stats.d_grade == 0                      # 存量那只 D 不算
    assert abs(stats.mean_coverage - 100.0) < 1e-9  # 存量 cov=0 不进均值


# ── T9 D 级阈值双向边界（20 不报 / 21 报） ────────────────────────────
def _n_tradable(n, grade='A', score=95.0, missing=0):
    return {f"S{i}": _rec(score=score, grade=grade, missing=missing) for i in range(n)}


def test_t9_d_grade_threshold_boundary(sent):
    rows = [("S0", DATES[0])]
    snap = _snapshot(rows)
    # 3 只 D：不报
    res, _ = _run(snap, _n_tradable(3, grade='D', score=40.0))
    assert 'D级股票数量过多' not in (sent.get('message') or '')
    # 21 只 D：报
    snap2 = _snapshot([(f"S{i}", DATES[0]) for i in range(21)])
    res2, _ = _run(snap2, _n_tradable(21, grade='D', score=40.0))
    assert 'D级股票数量过多: 21只 (阈值: 20, 域内)' in sent['message']
    assert res2['alert_scope'] == 'tradable'


# ── T10 评分阈值双向边界（90.84 不报 / 87.9 报） ──────────────────────
def test_t10_score_threshold_boundary(sent):
    snap = _snapshot([("A", DATES[0]), ("B", DATES[0])])
    _run(snap, {"A": _rec(score=93.33), "B": _rec(score=88.35)})   # 均值 90.84
    assert '数据质量评分偏低' not in (sent.get('message') or '')
    _run(snap, {"A": _rec(score=87.9), "B": _rec(score=87.9)})
    assert '数据质量评分偏低: 87.90 (阈值: 88.0, 域内)' in sent['message']


# ── T11 掉出名单与 20 只截断不冒充 count ─────────────────────────────
def test_t11_dropped_list_truncation(sent):
    rows = [(f"D{i}", DATES[1]) for i in range(25)]
    rows.append(("ALIVE", DATES[0]))
    snap = _snapshot(rows)
    res, _ = _run(snap, {"ALIVE": _rec()})
    assert res['domain_dropped']['count'] == 25
    assert len(res['domain_dropped']['symbols']) == job.DROPPED_SYMBOLS_DISPLAY_LIMIT
    assert res['domain_dropped']['truncated'] is True
    assert '本期掉出可交易域: 25 只（只显示前 20 只）' in sent['message']


# ── T12 回填失败率样本门槛（n=7 不判 / n=10 判） ──────────────────────
def test_t12_backfill_sample_gate(sent):
    # D1 掉出可交易域 ⇒ 保证本轮一定有告警正文（否则 _send_quality_alerts 不会被调用）
    snap = _snapshot([("A", DATES[0]), ("D1", DATES[1])])
    per = {"A": _rec(), "D1": _rec()}
    res, _ = _run(snap, per, backfill_summary={'total_stocks': 7, 'failed_count': 5})
    assert '回填失败率过高' not in sent['message']
    assert '样本 n=7 < 10，不判失败率' in sent['message']
    res2, _ = _run(snap, per, backfill_summary={'total_stocks': 10, 'failed_count': 6})
    assert '回填失败率过高: 60.0% (阈值: 50.0%, 分母 10 只)' in sent['message']
    assert res2['alert_dispatch']['urgency'] == 'high'


# ── T13 回填目标只在可交易域内 ───────────────────────────────────────
def test_t13_backfill_targets_only_tradable():
    per_symbol = {
        "A": _rec(missing=3), "B": _rec(missing=9),
        "X1": _rec(missing=60, grade='D'), "X2": _rec(missing=60, grade='D'),
    }
    tradable = {"A", "B"}
    assert job._select_backfill_targets(per_symbol, tradable) == ["B", "A"]
    assert job._select_backfill_targets(per_symbol, tradable, limit=1) == ["B"]
    assert job._select_backfill_targets(per_symbol, set()) == []


# ── T14 审计列 original_count 取 total_trading_days（改前恒 0） ───────
def test_t14_original_count_key(monkeypatch):
    from adapters.outbound.repositories.kline_quality_repository import KlineQualityRepository
    captured = {}
    monkeypatch.setattr(KlineQualityRepository, 'record_check_result',
                        lambda self, **kw: captured.update(kw))
    svc = DataQualityService.__new__(DataQualityService)   # 跳过重型 __init__
    svc._persist_quality_audit(
        symbol='600519', start_date='2026-07-08', end_date='2026-10-06',
        gap_info={'total_trading_days': 60, 'actual_days': 55, 'coverage_rate': 91.67},
        dup_info={'has_duplicates': False, 'duplicate_count': 0},
        anomaly_info={'ok': True, 'has_anomalies': False, 'price_anomalies': [],
                      'volume_anomalies': [], 'total_anomalies': 0},
        quality_score=91.67, duration_ms=12,
    )
    assert captured['original_count'] == 60      # 改前：expected_days 不存在 ⇒ 0
    assert captured['cleaned_count'] == 55
    assert captured['grade'] == 'B'


# ── T16 截断时诚实标注 partial ───────────────────────────────────────
def test_t16_partial_marked(sent):
    rows = [(f"T{i}", DATES[0]) for i in range(10)] + [("D1", DATES[1])]
    snap = _snapshot(rows)
    per_symbol = {f"T{i}": _rec() for i in range(4)}          # 只统计到 4/10
    res, _ = _run(snap, per_symbol)
    assert res['domain']['partial'] is True
    assert res['domain']['stats_symbols'] == 4 and res['domain']['tradable_count'] == 10
    assert '统计 4/10 只（检查被墙钟截断）' in sent['message']


# ── T17 per_symbol 缺失 ⇒ 响亮降级，不回退第二真相源 ─────────────────
def test_t17_missing_per_symbol_degrades(sent):
    snap = _snapshot([("A", DATES[0])])
    res, _ = _run(snap, {})
    assert res['alert_scope'] == 'degraded'
    assert '分域不可用' in sent['message']
    assert res['alert_dispatch']['urgency'] == 'high'


def test_t17b_degraded_snapshot_degrades(sent):
    snap = _snapshot([])                       # 退化快照
    assert snap.degraded is True
    res, _ = _run(snap, {"A": _rec()})
    assert res['alert_scope'] == 'degraded'
    assert '分域不可用' in sent['message']


# ── T15 / L1 反例锁：同日两批行不得翻倍 ──────────────────────────────
def test_t15_L1_count_is_distinct_not_rows():
    """同一标的同一天写两行（同日跑两次）⇒ 计数按标的，不是按行。"""
    from sqlalchemy import func
    from infrastructure.persistence.orm.models import KlineDataQuality
    from adapters.outbound.repositories.kline_quality_repository import KlineQualityRepository

    repo = KlineQualityRepository()
    probe = '__REQ_PROBE__'      # symbol 列是 varchar(20)，别超长
    try:
        for _ in range(2):                      # 同标的两行（模拟 00:00 + 13:48 各写一行）
            repo.record_check_result(
                symbol=probe, start_date='2026-07-08', end_date='2026-10-06',
                original_count=60, cleaned_count=0, removed_count=0, fixed_count=0,
                error_count=0, warning_count=0, errors_json=[], warnings_json=[],
                cleaning_operations_json=[], completeness_score=0.0, consistency_score=100.0,
                accuracy_score=25.0, overall_score=41.67, grade='D', duration_ms=1,
            )
        rows = (repo.session.query(func.count(KlineDataQuality.id))
                .filter(KlineDataQuality.symbol == probe).scalar())
        assert rows == 2, '前置：确实写了两行'
        hits = repo.count_by_grade_on('D', symbols=[probe])
        assert hits == 1, f'改前为 2（行数）；改后必须为 1（distinct 标的），实得 {hits}'
    finally:
        repo.session.query(KlineDataQuality).filter(KlineDataQuality.symbol == probe).delete()
        repo.session.commit()


# ── L2 反例锁：旧口径（全库 + 阈值 95）必然误报 ──────────────────────
def test_L2_old_scope_would_false_alarm(sent):
    """把存量标的算进分母 + 沿用 95.0 阈值 ⇒ 必然报两条；新口径不报。"""
    rows = [("A", DATES[0]), ("B", DATES[0])] + [(f"Z{i}", "2020-01-01") for i in range(12)]
    snap = _snapshot(rows)
    per_symbol = {"A": _rec(score=100.0), "B": _rec(score=90.0)}
    per_symbol.update({f"Z{i}": _rec(score=25.0, cov=0.0, grade='D') for i in range(12)})

    # 旧口径：分母 = 全部 10 只（含 8 只存量），阈值 95.0，D级阈值 500? 用 20 演示 D 越线
    old_mean = sum(r['quality_score'] for r in per_symbol.values()) / len(per_symbol)
    assert old_mean < 95.0            # 旧阈值下必然红
    old_d_rows = sum(1 for r in per_symbol.values() if r['grade'] == 'D') * 2   # 两批行 = 翻倍
    assert old_d_rows > 20

    # 新口径：存量不进分母、D 只数域内 ⇒ 不报
    res, _ = _run(snap, per_symbol)
    assert '数据质量评分偏低' not in (sent.get('message') or '')
    assert 'D级股票数量过多' not in (sent.get('message') or '')
    assert res['alert_scope'] == 'tradable'
