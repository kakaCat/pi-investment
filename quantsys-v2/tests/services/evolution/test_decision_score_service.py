"""DecisionScoreService 测试（P0a）——仓储/K线/基准全部 mock。"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import polars as pl

from application.services.evolution.decision_score_service import DecisionScoreService

TRADE_DATE = date(2026, 7, 1)


def _kline_df(closes, start=TRADE_DATE):
    """从 start 起连续自然日造 K 线（服务不校验交易日历，只数行数）。"""
    n = len(closes)
    return pl.DataFrame({
        'symbol': ['600519'] * n,
        'trade_date': [start + timedelta(days=i) for i in range(n)],
        'open': closes, 'high': closes, 'low': closes, 'close': closes,
        'volume': [1000] * n, 'amount': [10000.0] * n,
    })


def _bench(closes, start=TRADE_DATE):
    return [{'date': (start + timedelta(days=i)).isoformat(), 'close': c}
            for i, c in enumerate(closes)]


def _decision(**kw):
    d = {'decision_id': 'DEC-T1', 'decision_type': 'trade_buy',
         'parameters': {'symbol': '600519', 'price': 10.0, 'shares': 100},
         'created_at': datetime(2026, 7, 1, 10, 30)}
    d.update(kw)
    return d


def _service(pending, kline_df, bench):
    decision_repo = MagicMock()
    decision_repo.list_pending_evaluations.return_value = pending
    kline_repo = MagicMock()
    kline_repo.get_daily_klines.return_value = kline_df
    return DecisionScoreService(
        decision_repo=decision_repo, kline_repo=kline_repo,
        bench_klines_provider=lambda symbol, start_date, end_date: bench,
    ), decision_repo


def test_mature_buy_scored():
    # 交易日后 20 根 K 线，第 20 根（索引 19）收盘 11.0；基准平稳
    df = _kline_df([10.0] + [10.5] * 19 + [11.0])
    svc, repo = _service([_decision()], df, _bench([100.0] * 30))
    result = svc.score_mature_decisions()
    assert result['scanned'] == 1
    assert result['scored'] == 1
    args = repo.update_score.call_args
    assert args[0][0] == 'DEC-T1'
    # 第 20 根（索引 19）收盘 11.0：股票 +10%，基准 0% → score 1.0
    assert args[0][1] == 1.0
    assert args[0][2] == 'big_win'
    detail = args[0][3]
    assert detail['window_trading_days'] == 20
    assert detail['benchmark_missing'] is False


def test_unmature_skipped():
    df = _kline_df([10.0] * 5)  # 交易日后仅 4 根 < 20
    svc, repo = _service([_decision()], df, _bench([100.0] * 5))
    result = svc.score_mature_decisions()
    assert result['skipped_unmature'] == 1
    repo.update_score.assert_not_called()


def test_non_trade_type_skipped():
    svc, repo = _service([_decision(decision_type='daily_review')],
                         _kline_df([10.0] * 30), _bench([100.0] * 30))
    result = svc.score_mature_decisions()
    assert result['scanned'] == 0
    repo.update_score.assert_not_called()


def test_missing_params_skipped():
    svc, repo = _service([_decision(parameters={'shares': 100})],
                         _kline_df([10.0] * 30), _bench([100.0] * 30))
    result = svc.score_mature_decisions()
    assert result['skipped_invalid'] == 1
    repo.update_score.assert_not_called()


def test_sell_direction_and_bench_missing_degradation():
    df = _kline_df([10.0] + [9.0] * 20 + [9.0])
    svc, repo = _service(
        [_decision(decision_type='trade_sell',
                   parameters={'symbol': '600519', 'price': 10.0})],
        df, [])  # 基准缺失 → 降级 0.0 并标记
    result = svc.score_mature_decisions()
    assert result['scored'] == 1
    args = repo.update_score.call_args
    # 卖后跌 10%，躲过下跌 → score 1.0
    assert args[0][1] == 1.0
    assert args[0][3]['benchmark_missing'] is True


def test_single_error_does_not_abort_batch():
    good_df = _kline_df([10.0] + [10.5] * 19 + [11.0])
    kline_repo = MagicMock()
    kline_repo.get_daily_klines.side_effect = [RuntimeError('kline db error'), good_df]
    decision_repo = MagicMock()
    decision_repo.list_pending_evaluations.return_value = [
        _decision(decision_id='DEC-BAD'),
        _decision(decision_id='DEC-GOOD'),
    ]
    svc = DecisionScoreService(
        decision_repo=decision_repo, kline_repo=kline_repo,
        bench_klines_provider=lambda symbol, start_date, end_date: _bench([100.0] * 30),
    )
    result = svc.score_mature_decisions()
    assert result['errors'] == 1
    assert result['scored'] == 1
    assert decision_repo.update_score.call_count == 1
    assert decision_repo.update_score.call_args[0][0] == 'DEC-GOOD'


def test_write_failure_counted_as_error():
    df = _kline_df([10.0] + [10.5] * 19 + [11.0])
    svc, repo = _service([_decision()], df, _bench([100.0] * 30))
    repo.update_score.return_value = None
    result = svc.score_mature_decisions()
    assert result['errors'] == 1
    assert result['scored'] == 0


def test_missed_opportunity_scored():
    # P0b：missed_opportunity 决策成熟后按 miss 方向打分（信号后涨=负分）
    df = _kline_df([10.0] + [11.0] * 19 + [11.0])  # 信号后第20根收盘 11.0（+10%）
    svc, repo = _service(
        [_decision(decision_id='MISS-101', decision_type='missed_opportunity')],
        df, _bench([100.0] * 30))
    result = svc.score_mature_decisions()
    assert result['scored'] == 1
    args = repo.update_score.call_args
    assert args[0][0] == 'MISS-101'
    assert args[0][1] == -1.0          # 踏空：+10% 超额 × miss 方向 -1 → -1.0
    assert args[0][2] == 'big_loss'
