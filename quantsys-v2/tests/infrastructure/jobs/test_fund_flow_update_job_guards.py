"""fund_flow_update_job 两道闸门回归锁（2026-09-11，w-f436d4ea）

背景事故：本 job 的 trade_date 来自**墙钟**（params['date'] 或 datetime.now()），
而快照来自「发请求那一刻」，两者可能不是同一天。已实测两种污染进入 quant.stock_fund_flow：
  1) 手动回补 --date 2026-09-10 在 09-11 **盘中**运行（updated_at 12:52:33）→ 抓到
     盘中价 41.82/−3.77% 记成 09-10 收盘，而 09-10 真值 43.46/+1.85%（差 3.9%）；
  2) **非交易日**运行 → 上游返回上一交易日陈旧快照被记成当天（09-05 周六整行复制 09-04）。
下游若按「资金流 vs 涨跌」对齐分析，会得出错误结论。

闸门：① 非交易日不落库；② 抽样比对权威 K 线收盘，不一致则拒绝落库。

全程不触网、不写库：数据源与仓储均被替换为桩。
"""
import pytest

from infrastructure.jobs import fund_flow_update_job as job
from infrastructure.jobs.fund_flow_update_job import _snapshot_matches_reference


def _recs(pairs):
    return [{'symbol': s, 'close_price': p} for s, p in pairs]


# ── 闸门②：快照与权威 K 线一致性 ──────────────────────────────

def test_收盘价一致时通过():
    recs = _recs([('600176', 43.46), ('600150', 39.75)])
    ok, reason, detail = _snapshot_matches_reference(
        recs, '2026-09-10', close_lookup=lambda s, d: {'600176': 43.46, '600150': 39.75})
    assert ok and reason == ''
    assert detail['checked'] == 2 and detail['mismatch'] == 0


def test_真实事故_盘中快照被记成前一日收盘_必须拦截():
    """实测样本：600176 的 2026-09-10 行存 41.82（09-11 盘中价），真值 43.46。"""
    recs = _recs([('600176', 41.82), ('600150', 37.0), ('600887', 25.0)])
    ok, reason, detail = _snapshot_matches_reference(
        recs, '2026-09-10',
        close_lookup=lambda s, d: {'600176': 43.46, '600150': 39.75, '600887': 26.66})
    assert not ok, '盘中快照被记成历史交易日收盘必须拦截'
    assert '不属于' in reason or '拒绝落库' in reason
    assert detail['mismatch'] == 3 and detail['ratio'] == 1.0
    assert detail['examples'][0]['symbol'] == '600176'


def test_容差内不误拦():
    recs = _recs([('600176', 43.46 * 1.004)])          # +0.4%，在 0.5% 容差内
    ok, _, _ = _snapshot_matches_reference(
        recs, '2026-09-10', close_lookup=lambda s, d: {'600176': 43.46})
    assert ok, '复权/四舍五入级别的小偏差不得触发拦截'


def test_取不到参照K线时不拦但如实说明():
    ok, _, detail = _snapshot_matches_reference(
        _recs([('600176', 41.82)]), '2026-09-10', close_lookup=lambda s, d: {})
    assert ok, '无法证伪 != 有问题（同「空结果不是故障」口径）'
    assert detail['checked'] == 0
    assert '未做一致性校验' in detail['note']


def test_无可用收盘价时跳过校验():
    ok, _, detail = _snapshot_matches_reference(
        [{'symbol': '600176', 'close_price': None}], '2026-09-10',
        close_lookup=lambda s, d: {'600176': 43.46})
    assert ok and detail['checked'] == 0


# ── 闸门①：非交易日 / 落库接线 ──────────────────────────────

class _StubSource:
    def __init__(self, name, records):
        self.name = name
        self._records = records

    def fetch_market_wide_flow(self):
        return [dict(r) for r in self._records]


def _patch(monkeypatch, records, sink):
    import adapters.outbound.datasources.fund_flow_source as ffs
    import adapters.outbound.repositories as repos

    monkeypatch.setattr(ffs, 'EastMoneyFundFlowSource', lambda: _StubSource('eastmoney', records))
    monkeypatch.setattr(ffs, 'SinaFundFlowSource', lambda: _StubSource('sina', []))

    class _Repo:
        def batch_upsert(self, recs):
            sink.extend(recs)
            return len(recs)

    monkeypatch.setattr(repos, 'FundFlowORMRepository', _Repo)


def test_非交易日不落库(monkeypatch):
    """2026-09-05 是周六：实测当天 23:01 跑过一次并写出与 09-04 完全相同的行。"""
    sink = []
    _patch(monkeypatch, [{'symbol': '600176', 'close_price': 40.18}], sink)

    out = job.execute(date='2026-09-05')

    assert out['success'] is False
    assert out.get('skipped') is True and out['reason'] == 'non_trading_day'
    assert sink == [], '非交易日绝不允许写库'


def test_快照不属于该交易日时不落库(monkeypatch):
    sink = []
    _patch(monkeypatch, [{'symbol': '600176', 'close_price': 41.82}], sink)
    monkeypatch.setattr(job, '_snapshot_matches_reference',
                        lambda recs, d: (False, '快照不属于 2026-09-10', {'checked': 1}))

    out = job.execute(date='2026-09-10')

    assert out['reason'] == 'snapshot_mismatch' and sink == []


def test_闸门通过后正常落库并回传sanity(monkeypatch):
    sink = []
    _patch(monkeypatch, [{'symbol': '600176', 'close_price': 43.46}], sink)
    monkeypatch.setattr(job, '_snapshot_matches_reference',
                        lambda recs, d: (True, '', {'checked': 1, 'mismatch': 0}))

    out = job.execute(date='2026-09-10')

    assert out['success'] is True and out['records'] == 1
    assert sink[0]['trade_date'] == '2026-09-10', '必须按闸门校验过的交易日打标'
    assert out['sanity'] == {'checked': 1, 'mismatch': 0}
