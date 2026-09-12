"""generate_lesson 纯函数单测（REQ-9bcd0a WP1）。不连库。"""
from application.services.evolution.lesson_generator import generate_lesson


def _mk(**over):
    base = dict(action='buy', decision_type='trade_buy', symbol='600519',
                trade_price=1850.0, trade_date='2026-07-14', ref_date='2026-08-11',
                excess_return=-0.444, band='big_loss', score=-1.0,
                window_trading_days=20, benchmark='sh000300',
                benchmark_missing=False, context=None)
    base.update(over)
    return generate_lesson(**base)


def test_contains_four_required_elements():
    s = _mk()
    assert '600519' in s           # 标的
    assert '2026-07-14' in s and '2026-08-11' in s  # 日期区间
    assert '-44.4%' in s           # 超额数值
    assert 'big_loss' in s         # band


def test_conclusion_differs_by_action_and_band():
    buy_loss = _mk(action='buy', band='big_loss')
    buy_win = _mk(action='buy', band='big_win', excess_return=0.39, score=1.0)
    miss_win = _mk(action='miss', decision_type='missed_opportunity', band='big_win',
                   excess_return=0.27, score=1.0)
    sell_win = _mk(action='sell', decision_type='trade_sell', band='big_win',
                   excess_return=0.12, score=1.0)
    conclusions = {
        buy_loss.split('→ ')[1], buy_win.split('→ ')[1],
        miss_win.split('→ ')[1], sell_win.split('→ ')[1],
    }
    assert len(conclusions) == 4, '不同 action/band 必须给出不同结论（禁模板化）'


def test_direction_semantics_not_inverted():
    """方向铁律（score_calculator）：excess 已按方向调整。

    miss 为反向 → 超额为【正】= 标的跑输基准 = 观望有效；
    超额为【负】= 标的跑赢基准 = 踏空。写反会把学习回路带偏。
    """
    wait_ok = _mk(action='miss', decision_type='missed_opportunity', band='big_win',
                  excess_return=0.20, score=1.0)
    missed = _mk(action='miss', decision_type='missed_opportunity', band='big_loss',
                 excess_return=-0.14, score=-1.0)
    assert '躲过下跌' in wait_ok or '有效' in wait_ok
    assert '踏空' in missed
    assert '躲过下跌' not in missed and '正确' not in missed

    # buy 为正向：超额为负 = 跑输基准 = 买错
    buy_bad = _mk(action='buy', band='big_loss', excess_return=-0.44, score=-1.0)
    assert '跑输基准' in buy_bad


def test_context_appended_and_missing_marked():
    s = _mk(context={'regime': 'risk_off', 'signal_source': 'opportunity_scan'})
    assert 'regime=risk_off' in s and '来源=opportunity_scan' in s
    s2 = _mk(benchmark_missing=True)
    assert '基准缺失' in s2


def test_no_context_no_parens_noise():
    s = _mk(context=None)
    assert '（）' not in s
