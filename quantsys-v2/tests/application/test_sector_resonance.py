"""板块共振核验服务单测（2026-10-20，确认核验流水线 M2）

用户场景：候选池标的的异动要区分「板块共振」（有主线资金）与「孤立异动」（独立消息/噪声）。
证伪清单：
  1) 同步共振：同板块核心标的同向且幅度达标 → resonant / passed=True；
  2) 孤立异动：同向核心标的不足/幅度不够 → isolated / passed=False，且 reason 写清降级理由；
  3) 映射缺失（未构建/已过期/标的不在映射）→ skipped / verified=False / passed=None，
     reason 明确「不校验」，**不得**把缺数据当成「孤立异动」或「共振成立」；
  4) 核心标的口径：总市值前 N、剔除自身；无市值按成分顺序；支持显式名单；
  5) 行情缺失（标的/核心标的）同样不校验，不臆造结论；未达异动阈值不校验；
  6) 候选池口径映射：只映射候选池标的，首个命中板块为主板块，支持 candidate_source+pool_id。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.sector_resonance_service import (
    STATUS_ISOLATED,
    STATUS_RESONANT,
    STATUS_SKIPPED,
    SectorResonanceService,
    SectorResonanceResult,
)

T0 = datetime(2026, 10, 20, 10, 0, 0)


# ── 替身 ────────────────────────────────────────────────────

def _member(sym, name=None, cap=None):
    return {'symbol': sym, 'name': name or sym, 'market_cap': cap}


class _SectorSource:
    """板块端口替身：boards = {板块: [成员]}，fail_sectors 可模拟单板块失败。"""

    def __init__(self, boards, fail_list=False):
        self.boards = boards
        self.fail_list = fail_list
        self.list_calls = 0
        self.member_calls = []

    def list_sectors(self):
        self.list_calls += 1
        if self.fail_list:
            raise RuntimeError('sector list boom')
        return list(self.boards)

    def get_members(self, sector):
        self.member_calls.append(sector)
        return [dict(m) for m in self.boards.get(sector, [])]


class _QuoteSource:
    """批量行情端口替身：changes = {symbol: 涨跌幅%}。"""

    def __init__(self, changes):
        self.changes = changes
        self.calls = []

    def get_quotes(self, symbols):
        self.calls.append(list(symbols))
        data = {s: SimpleNamespace(symbol=s, change_pct=self.changes[s])
                for s in symbols if s in self.changes}
        return {'success': True, 'data': data}


class _CandidateSource:
    """候选池端口替身。"""

    def __init__(self, members, expected_pool_id=None):
        self.members = members
        self.expected_pool_id = expected_pool_id
        self.calls = []

    def get_members(self, pool_id):
        self.calls.append(pool_id)
        if self.expected_pool_id is not None:
            assert pool_id == self.expected_pool_id
        return list(self.members)


#: 白酒板块：subject 市值最大，其余按市值递减
BAIJIU = {
    '白酒': [
        _member('600519', '贵州茅台', 2.1e12),
        _member('000858', '五粮液', 5.0e11),
        _member('000568', '泸州老窖', 2.4e11),
        _member('600809', '山西汾酒', 2.2e11),
        _member('000799', '酒鬼酒', 3.0e10),
    ]
}
ALL_BAIJIU = ['600519', '000858', '000568', '600809', '000799']


class _Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def _make(boards=None, changes=None, candidates=ALL_BAIJIU, clock=None, **kwargs):
    sector = _SectorSource(boards or BAIJIU)
    quote = _QuoteSource(changes or {})
    svc = SectorResonanceService(sector_source=sector, quote_source=quote,
                                 now_fn=clock or _Clock(), **kwargs)
    if candidates is not None:
        out = svc.refresh(candidates=candidates)
        assert out['built'] is True
    return svc, sector, quote


# ── 1. 同步共振 ─────────────────────────────────────────────

def test_sync_resonance_passes():
    svc, _, _ = _make(changes={'600519': 6.0, '000858': 3.2, '000568': 2.4,
                               '600809': -0.8, '000799': 0.2})
    res = svc.check('600519')

    assert isinstance(res, SectorResonanceResult)
    assert res.status == STATUS_RESONANT
    assert res.verified is True and res.passed is True and res.ok is True
    assert res.sector == '白酒' and res.direction == 'up'
    assert res.subject_change_pct == pytest.approx(6.0)
    assert set(res.synced) == {'000858', '000568'}
    assert res.quoted_peers == 4                  # 剔除自身
    assert res.sync_ratio == pytest.approx(2 / 4)  # 恰好压线（min_sync_ratio=0.5）
    assert res.core_basis == 'market_cap'
    assert '共振成立' in res.reason
    assert '孤立异动' not in res.reason

    payload = res.to_dict()
    assert payload['label'] == '板块共振'
    assert payload['verdict'] == STATUS_RESONANT
    assert payload['passed'] is True and payload['skipped'] is False


def test_downside_resonance_also_passes():
    """同跌也算共振（方向跟着标的走），不能只认上涨。"""
    svc, _, _ = _make(changes={'600519': -4.2, '000858': -2.2, '000568': -1.6,
                               '600809': 0.5, '000799': -0.3})
    res = svc.check('600519')
    assert res.status == STATUS_RESONANT and res.passed is True
    assert res.direction == 'down'
    assert set(res.synced) == {'000858', '000568'}


def test_ratio_and_count_gates_are_both_enforced():
    """同步家数够但占比不够 / 占比够但家数不够，都必须是孤立异动。"""
    changes = {'600519': 5.0, '000858': 2.0, '000568': 0.3,
               '600809': -0.2, '000799': 0.1}
    svc, _, _ = _make(changes=changes, min_sync_ratio=0.75)
    res = svc.check('600519')
    assert res.status == STATUS_ISOLATED and res.passed is False
    assert res.synced == ('000858',)               # 1/4 = 25% < 75%

    svc2, _, _ = _make(changes=changes, min_synced=2)
    res2 = svc2.check('600519')
    assert res2.status == STATUS_ISOLATED and res2.passed is False
    assert '1/4' in res2.reason


# ── 2. 孤立异动（降级理由）──────────────────────────────────

def test_isolated_move_explains_downgrade_reason():
    svc, _, _ = _make(changes={'600519': 5.0, '000858': 0.4, '000568': -0.2,
                               '600809': 0.6, '000799': -0.1})
    res = svc.check('600519')

    assert res.status == STATUS_ISOLATED
    assert res.verified is True and res.passed is False
    assert res.downgraded is True and res.downgrade_reason == res.reason
    assert res.synced == ()
    assert res.sync_ratio == pytest.approx(0.0)
    assert '降级理由' in res.reason
    assert '0/4' in res.reason
    assert '同向最大 600809 +0.60%' in res.reason      # 说明差多少，不是一句话否定
    assert '不按板块共振加权' in res.reason


# ── 3. 映射缺失 = 不校验 ────────────────────────────────────

def test_mapping_missing_degrades_to_no_check():
    svc, _, _ = _make(candidates=None)             # 未 refresh
    res = svc.check('600519', 6.0)

    assert res.status == STATUS_SKIPPED
    assert res.verified is False and res.passed is None and res.resonance is None
    assert res.degraded is True and res.skip_code == 'mapping_not_built'
    assert '不校验' in res.reason and '板块映射缺失' in res.reason
    # 不臆造结论：既不能说共振成立，也不能说孤立异动
    assert '共振成立：' not in res.reason
    assert '判定为个股独立异动' not in res.reason
    assert res.sector is None and res.peers == () and res.core_peers == ()
    assert res.to_dict()['passed'] is None


def test_symbol_not_in_candidate_mapping_skips():
    svc, _, _ = _make(candidates=['600519'])        # 只有 600519 进映射
    assert svc.mapping() == {'600519': '白酒'}

    res = svc.check('000001', 5.0)
    assert res.status == STATUS_SKIPPED and res.passed is None
    assert res.skip_code == 'symbol_not_mapped' and res.degraded is True
    assert '不校验' in res.reason
    assert '不认定共振成立' in res.reason


def test_expired_mapping_degrades_to_no_check():
    clock = _Clock(T0)
    svc, _, _ = _make(clock=clock, ttl_sec=60)
    assert svc.mapping()

    clock.now = T0 + timedelta(seconds=61)
    assert svc.mapping() == {}
    res = svc.check('600519', 6.0)
    assert res.status == STATUS_SKIPPED and res.skip_code == 'mapping_expired'
    assert res.verified is False and res.passed is None
    assert '不校验' in res.reason


# ── 4. 核心标的口径 ─────────────────────────────────────────

def test_core_targets_are_top_market_cap_excluding_subject():
    boards = {'白酒': [
        _member('600519', '贵州茅台', 1.0e12),
        _member('000001', '甲', 9.0e11),
        _member('000002', '乙', 8.0e11),
        _member('000003', '丙', 7.0e11),
        _member('000004', '丁', 6.0e11),
        _member('000005', '戊', 5.0e11),
    ]}
    svc, _, _ = _make(boards=boards, candidates=['600519'],
                      changes={'600519': 5.0, '000001': 3.0, '000002': 2.0,
                               '000003': 9.0, '000004': 9.0, '000005': 9.0},
                      core_size=2)
    res = svc.check('600519')
    assert res.core_peers == ('000001', '000002')   # 市值前二，剔除自身
    assert res.core_basis == 'market_cap'
    assert res.status == STATUS_RESONANT
    assert '000003' not in res.core_peers


def test_core_falls_back_to_constituent_order_without_market_cap():
    boards = {'白酒': [_member('600519'), _member('000001'), _member('000002'),
                       _member('000003')]}
    svc, _, _ = _make(boards=boards, candidates=['600519'],
                      changes={'600519': 5.0, '000001': 3.0, '000002': 2.0,
                               '000003': 9.0},
                      core_size=2)
    res = svc.check('600519')
    assert res.core_peers == ('000001', '000002')   # 无市值 → 成分顺序
    assert res.core_basis == 'order'


def test_explicit_core_list_overrides_market_cap():
    svc, _, _ = _make(changes={'600519': 5.0, '000858': 2.0, '000568': 2.0,
                               '600809': 2.0, '000799': 2.0},
                      core_by_sector={'白酒': ['000799']})
    res = svc.check('600519')
    assert res.core_peers == ('000799',)
    assert res.core_basis == 'explicit'
    assert res.status == STATUS_RESONANT


# ── 5. 行情/异动缺失都不臆造结论 ────────────────────────────

def test_peer_quotes_missing_skips_not_isolated():
    svc, _, _ = _make(changes={'600519': 6.0})      # 核心标的全部无行情
    res = svc.check('600519')

    assert res.status == STATUS_SKIPPED and res.verified is False
    assert res.passed is None and res.skip_code == 'peer_quotes_missing'
    assert res.degraded is True and len(res.missing_peer_quotes) == 4
    assert '不校验' in res.reason
    assert res.status != STATUS_ISOLATED           # 缺行情 ≠ 孤立异动


def test_subject_quote_missing_skips():
    svc = SectorResonanceService(sector_source=_SectorSource(BAIJIU),
                                 quote_source=_QuoteSource({}),
                                 now_fn=_Clock())
    svc.refresh(candidates=ALL_BAIJIU)
    res = svc.check('600519')
    assert res.status == STATUS_SKIPPED and res.skip_code == 'subject_quote_missing'
    assert res.passed is None and res.degraded is True


def test_not_abnormal_skips_without_degradation():
    svc, _, _ = _make(changes={'600519': 0.8})
    res = svc.check('600519')
    assert res.status == STATUS_SKIPPED and res.skip_code == 'not_abnormal'
    assert res.degraded is False and res.passed is None
    assert '未达异动阈值' in res.reason


def test_no_core_peers_skips():
    boards = {'白酒': [_member('600519', cap=1.0e12)]}
    svc, _, _ = _make(boards=boards, candidates=['600519'],
                      changes={'600519': 5.0})
    res = svc.check('600519')
    assert res.status == STATUS_SKIPPED and res.skip_code == 'no_core_peers'
    assert res.passed is None and '不校验' in res.reason
    assert res.degraded is False                    # 数据完整，只是没有同板块核心标的


def test_sector_members_missing_skips_not_isolated():
    """映射命中但成分取不到：是缺数据 → 不校验，不能当成「没有核心标的」或「孤立」。"""
    svc = SectorResonanceService(sector_source=_SectorSource({}),
                                 quote_source=_QuoteSource({'600519': 5.0}),
                                 now_fn=_Clock())
    res = svc.check('600519', 5.0, sector='空板块')
    assert res.status == STATUS_SKIPPED
    assert res.skip_code == 'sector_members_missing'
    assert res.degraded is True and res.passed is None
    assert '不校验' in res.reason
    assert res.status != STATUS_ISOLATED


# ── 6. 行情形状归一 + 候选池口径映射 ────────────────────────

def test_quote_shapes_dict_and_prev_close_are_normalized():
    """调用方直传 quotes：裸数字 / {'change_pct'} / {'price','prev_close'} 都要认。"""
    svc, _, _ = _make(changes={})                  # 不外呼，全部走 quotes
    quotes = {
        '600519': {'change_pct': 5.0},
        '000858': {'price': 10.2, 'prev_close': 10.0},   # +2.00%
        '000568': 2.0,
        '600809': -0.5,
        '000799': 0.1,
    }
    res = svc.check('600519', quotes=quotes)
    assert res.status == STATUS_RESONANT
    assert '000858' in res.synced and '000568' in res.synced
    assert res.quoted_peers == 4


def test_candidate_source_and_pool_id_build_mapping():
    """候选池口径：refresh() 自己从 candidate_source 取池成员；只映射候选标的。"""
    sector = _SectorSource(BAIJIU)
    candidate = _CandidateSource([{'symbol': '600519.SH'}, {'symbol': '000858'}],
                                 expected_pool_id=35)
    svc = SectorResonanceService(sector_source=sector, quote_source=_QuoteSource({}),
                                 candidate_source=candidate, pool_id=35, now_fn=_Clock())
    out = svc.refresh()

    assert out['built'] is True and out['mapped'] == 2
    assert candidate.calls == [35]
    assert svc.mapping() == {'600519': '白酒', '000858': '白酒'}
    # 非候选标的不会被顺手映射
    assert '000568' not in svc.mapping()


def test_refresh_failure_keeps_old_mapping_and_marks_degraded():
    clock = _Clock(T0)
    sector = _SectorSource(BAIJIU)
    svc = SectorResonanceService(sector_source=sector, quote_source=_QuoteSource({}),
                                 now_fn=clock)
    assert svc.refresh(candidates=ALL_BAIJIU)['built'] is True
    before = svc.mapping()

    sector.fail_list = True
    out = svc.refresh(force=True, candidates=ALL_BAIJIU)
    assert out['built'] is False and out['degraded'] is True
    assert svc.mapping() == before                  # stale 比空好
    assert svc.refresh_status()['degraded'] is True
