"""打分纯函数测试（P0a）——口径见计划头部。"""
import pytest

from application.services.evolution.score_calculator import compute_trade_score, score_band


def test_buy_beats_benchmark_scores_positive():
    r = compute_trade_score('buy', trade_price=10.0, ref_price=11.0, bench_return=0.02)
    # 股票 +10%，基准 +2%，超额 +8% → 0.8
    assert r['score'] == 0.8
    assert r['band'] == 'big_win'
    assert r['excess_return'] == 0.08


def test_sell_avoids_drop_scores_positive():
    r = compute_trade_score('sell', trade_price=10.0, ref_price=9.0, bench_return=-0.02)
    # 股票 -10%，基准 -2%，卖出决策超额 +8% → 0.8
    assert r['score'] == 0.8
    assert r['band'] == 'big_win'


def test_panic_sell_rebound_scores_negative():
    # 割肉：卖完反弹，卖出决策为负分
    r = compute_trade_score('sell', trade_price=10.0, ref_price=11.0, bench_return=0.0)
    assert r['score'] == -1.0
    assert r['band'] == 'big_loss'


def test_score_clamped_to_one():
    r = compute_trade_score('buy', trade_price=10.0, ref_price=12.5, bench_return=0.0)
    assert r['score'] == 1.0


def test_hold_is_buy_direction():
    # 持有不动 = 买入方向的延续打分（未平仓按最新价打分与 buy 同向）
    r = compute_trade_score('buy', trade_price=10.0, ref_price=10.3, bench_return=0.0)
    assert r['score'] == 0.3
    assert r['band'] == 'small_win'


def test_invalid_action_raises():
    with pytest.raises(ValueError, match='unknown action'):
        compute_trade_score('hold', trade_price=10.0, ref_price=11.0, bench_return=0.0)


def test_score_band_boundaries():
    assert score_band(0.5) == 'big_win'
    assert score_band(0.1) == 'small_win'
    assert score_band(0.05) == 'neutral'
    assert score_band(-0.1) == 'small_loss'
    assert score_band(-0.5) == 'big_loss'


def test_miss_rally_is_negative():
    # 踏空：信号后大涨，未行动 → 满分负分
    r = compute_trade_score('miss', trade_price=10.0, ref_price=11.0, bench_return=0.0)
    assert r['score'] == -1.0
    assert r['band'] == 'big_loss'


def test_miss_drop_is_positive():
    # 正确观望：信号后大跌，未行动 → 正分
    r = compute_trade_score('miss', trade_price=10.0, ref_price=9.0, bench_return=-0.02)
    # 股票 -10%，基准 -2%，观望决策超额 +8% → 0.8
    assert r['score'] == 0.8
    assert r['band'] == 'big_win'
