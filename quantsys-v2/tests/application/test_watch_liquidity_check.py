"""流动性核验服务单测（Taskmaster liquidity-check）。

覆盖两条验收判据：
  0. 正常 / 枯竭 / 诱骗 三类判定（含边界与判定优先级）；
  1. 阈值缺失/非法、数据缺失/非法时如实 skipped，ok 绝不为 True（不误判为通过）。
"""
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.liquidity_check_service import (
    VERDICT_DRAINED,
    VERDICT_NORMAL,
    VERDICT_SKIPPED,
    VERDICT_TRAP,
    LiquidityCheckService,
    LiquidityThresholds,
    check_liquidity,
)

THRESHOLDS = {
    'min_amount': 5_000_000,      # 成交额下限 500 万
    'min_volume_ratio': 1.0,      # 量比下限 1.0
    'trap_big_order_ratio': 0.4,  # 大单占比 ≥ 40% 视为诱骗候选
}


def _quote(amount=2.0e8, volume_ratio=1.5, big_order_ratio=0.2, symbol='600150', **extra):
    quote = {
        'symbol': symbol,
        'amount': amount,
        'volume_ratio': volume_ratio,
        'big_order_ratio': big_order_ratio,
    }
    quote.update(extra)
    return quote


@pytest.fixture
def svc():
    return LiquidityCheckService(THRESHOLDS)


# ── 判据 0：正常 / 枯竭 / 诱骗 三类判定 ──────────────────────────────────

def test_normal_when_amount_and_volume_ratio_healthy(svc):
    result = svc.check(_quote())

    assert result.verdict == VERDICT_NORMAL
    assert result.ok is True
    assert result.skipped is False
    assert result.label == '正常'
    assert '盘口正常' in result.reason


def test_drained_when_amount_below_floor(svc):
    result = svc.check(_quote(amount=1_000_000))

    assert result.verdict == VERDICT_DRAINED
    assert result.ok is False
    assert result.label == '流动性枯竭'
    assert '枯竭' in result.reason
    assert '成交额' in result.reason


def test_drained_when_volume_ratio_below_floor(svc):
    result = svc.check(_quote(volume_ratio=0.42))

    assert result.verdict == VERDICT_DRAINED
    assert result.ok is False
    assert '量比' in result.reason


def test_drained_reason_lists_every_weak_dimension(svc):
    result = svc.check(_quote(amount=1_000_000, volume_ratio=0.3))

    assert result.verdict == VERDICT_DRAINED
    assert '成交额' in result.reason and '量比' in result.reason


def test_trap_when_big_orders_concentrated_without_turnover(svc):
    result = svc.check(_quote(amount=800_000, volume_ratio=0.35, big_order_ratio=0.62))

    assert result.verdict == VERDICT_TRAP
    assert result.ok is False
    assert result.label == '大单诱骗'
    assert '诱骗' in result.reason
    assert '62.0%' in result.reason


def test_trap_beats_drained_when_liquidity_weak(svc):
    """大单集中且量能不足 → 诱骗，而不是笼统归为枯竭。"""
    result = svc.check(_quote(volume_ratio=0.3, big_order_ratio=0.5))

    assert result.verdict == VERDICT_TRAP
    assert '诱骗' in result.reason


def test_high_big_order_ratio_with_real_volume_is_normal(svc):
    """大单占比高但有成交额/量能配合 → 真实大单，不冤判诱骗。"""
    result = svc.check(_quote(amount=3e8, volume_ratio=2.0, big_order_ratio=0.7))

    assert result.verdict == VERDICT_NORMAL
    assert result.ok is True
    assert '真实大单' in result.reason


def test_thresholds_are_inclusive(svc):
    """恰在阈值上算达标（≥ 达标、< 不达标）。"""
    result = svc.check(_quote(amount=5_000_000, volume_ratio=1.0, big_order_ratio=0.4))

    assert result.verdict == VERDICT_NORMAL
    assert result.ok is True


def test_trap_fires_exactly_at_threshold_when_liquidity_weak(svc):
    result = svc.check(_quote(amount=4_999_999, big_order_ratio=0.4))

    assert result.verdict == VERDICT_TRAP


def test_big_order_ratio_accepts_percentage_input(svc):
    """大单占比给百分数（62）时按百分数归一，仍能判出诱骗。"""
    result = svc.check(_quote(amount=800_000, big_order_ratio=62))

    assert result.verdict == VERDICT_TRAP
    assert '62.0%' in result.reason


def test_normal_reads_quote_object_attributes(svc):
    quote = SimpleNamespace(symbol='600519', amount=9e8, volume_ratio=1.8,
                            big_order_ratio=0.15)

    result = svc.check(quote)

    assert result.verdict == VERDICT_NORMAL
    assert result.symbol == '600519'


def test_normal_reads_field_aliases(svc):
    quote = {'symbol': '000001', 'turnover': 2e8, 'vol_ratio': 1.4,
             'large_order_ratio': 0.2}

    result = svc.check(quote)

    assert result.verdict == VERDICT_NORMAL


def test_numeric_strings_are_accepted(svc):
    quote = {'symbol': '600150', 'amount': '2e8', 'volume_ratio': '1.5',
             'big_order_ratio': '0.2'}

    result = svc.check(quote)

    assert result.verdict == VERDICT_NORMAL


# ── 判据 1：阈值缺失/非法、数据不足 → 如实 skipped ──────────────────────

def test_skipped_when_all_thresholds_missing():
    result = LiquidityCheckService().check(_quote())

    assert result.verdict == VERDICT_SKIPPED
    assert result.ok is None
    assert result.ok is not True
    assert result.skipped is True
    assert result.label == '数据不足'
    assert 'skipped' in result.reason
    assert '不判为通过' in result.reason
    assert set(result.missing) == {'min_amount', 'min_volume_ratio', 'trap_big_order_ratio'}


def test_skipped_when_only_some_thresholds_configured():
    svc = LiquidityCheckService({'min_amount': 5_000_000})

    result = svc.check(_quote())

    assert result.verdict == VERDICT_SKIPPED
    assert result.ok is None
    assert 'min_volume_ratio' in result.reason
    assert 'trap_big_order_ratio' in result.reason


def test_skipped_when_thresholds_invalid():
    svc = LiquidityCheckService({
        'min_amount': 0,
        'min_volume_ratio': -1,
        'trap_big_order_ratio': 150,
    })

    result = svc.check(_quote())

    assert result.verdict == VERDICT_SKIPPED
    assert result.ok is None
    assert '非法' in result.reason


def test_skipped_when_quote_missing_all_market_fields():
    result = LiquidityCheckService(THRESHOLDS).check({'symbol': '600150'})

    assert result.verdict == VERDICT_SKIPPED
    assert result.ok is None
    assert '行情' in result.reason
    assert {'amount', 'volume_ratio', 'big_order_ratio'} <= set(result.missing)
    assert result.symbol == '600150'


@pytest.mark.parametrize('missing_field', ['amount', 'volume_ratio', 'big_order_ratio'])
def test_skipped_when_any_single_market_field_missing(svc, missing_field):
    """三个行情字段缺一即数据不足——不许拿剩余字段猜一个「正常」。"""
    quote = _quote()
    quote.pop(missing_field)

    result = svc.check(quote)

    assert result.verdict == VERDICT_SKIPPED
    assert result.ok is None
    assert result.ok is not True
    assert missing_field in result.missing


def test_weak_liquidity_without_big_order_ratio_is_skipped_not_drained(svc):
    """量能偏弱但缺大单占比：无法区分枯竭与诱骗，如实 skipped（不误判为通过）。"""
    result = svc.check({'symbol': '600150', 'amount': 800_000, 'volume_ratio': 0.3})

    assert result.verdict == VERDICT_SKIPPED
    assert result.ok is None
    assert 'big_order_ratio' in result.missing


def test_skipped_when_quote_is_none_or_not_a_quote():
    svc = LiquidityCheckService(THRESHOLDS)

    for whatever in (None, 'not-a-quote', 42):
        result = svc.check(whatever)
        assert result.verdict == VERDICT_SKIPPED
        assert result.ok is None
        assert result.symbol == ''


def test_skipped_when_quote_values_invalid():
    svc = LiquidityCheckService(THRESHOLDS)

    negative_amount = svc.check(_quote(amount=-1))
    assert negative_amount.verdict == VERDICT_SKIPPED
    assert negative_amount.ok is None
    assert 'amount' in negative_amount.reason

    non_numeric = svc.check(_quote(volume_ratio='high'))
    assert non_numeric.verdict == VERDICT_SKIPPED
    assert 'volume_ratio' in non_numeric.reason

    out_of_range_ratio = svc.check(_quote(big_order_ratio=150))
    assert out_of_range_ratio.verdict == VERDICT_SKIPPED
    assert 'big_order_ratio' in out_of_range_ratio.reason


def test_skipped_reason_when_both_thresholds_and_data_missing():
    result = LiquidityCheckService().check({'symbol': '600150'})

    assert result.verdict == VERDICT_SKIPPED
    assert result.ok is None
    assert '阈值' in result.reason and '行情' in result.reason


def test_skipped_result_to_dict_never_reports_pass():
    payload = LiquidityCheckService().check(_quote()).to_dict()

    assert payload['verdict'] == 'skipped'
    assert payload['ok'] is None
    assert payload['skipped'] is True
    assert payload['label'] == '数据不足'


# ── 配置与批量入口 ────────────────────────────────────────────────────────

def test_from_config_accepts_chinese_and_alias_keys():
    svc = LiquidityCheckService.from_config({
        '成交额下限': 5_000_000,
        'volume_ratio_floor': 1.0,
        '大单占比阈值': 40,          # 百分数 → 0.4
    })

    assert isinstance(svc.thresholds, LiquidityThresholds)
    assert svc.check(_quote(big_order_ratio=0.62, amount=1_000_000)).verdict == VERDICT_TRAP


def test_per_call_thresholds_override_service_defaults(svc):
    strict = dict(THRESHOLDS, min_amount=1e10)

    result = svc.check(_quote(), thresholds=strict)

    assert result.verdict == VERDICT_DRAINED
    # 覆盖只作用于本次调用，服务默认值不变
    assert svc.check(_quote()).verdict == VERDICT_NORMAL


def test_per_call_thresholds_work_on_default_service():
    """服务未预置阈值时，逐次传入同样能完成判定（阈值可配）。"""
    result = LiquidityCheckService().check(_quote(), thresholds=THRESHOLDS)

    assert result.verdict == VERDICT_NORMAL
    assert result.ok is True


def test_check_many_returns_one_result_per_quote(svc):
    results = svc.check_many([
        _quote(symbol='600150'),
        _quote(symbol='600151', amount=1_000_000),
        _quote(symbol='600152', amount=800_000, big_order_ratio=0.62),
    ])

    assert [r.verdict for r in results] == [VERDICT_NORMAL, VERDICT_DRAINED, VERDICT_TRAP]
    assert [r.symbol for r in results] == ['600150', '600151', '600152']


def test_normal_result_to_dict(svc):
    payload = svc.check(_quote()).to_dict()

    assert payload['verdict'] == 'normal'
    assert payload['ok'] is True
    assert payload['skipped'] is False
    assert payload['amount'] == 2.0e8
    assert payload['missing'] == []


def test_bad_threshold_type_raises_type_error():
    with pytest.raises(TypeError):
        LiquidityCheckService('not-thresholds')

    with pytest.raises(TypeError):
        LiquidityCheckService(THRESHOLDS).check(_quote(), thresholds='not-thresholds')


def test_module_level_check_liquidity():
    result = check_liquidity(_quote(), THRESHOLDS)

    assert result.verdict == VERDICT_NORMAL
    assert result.ok is True
