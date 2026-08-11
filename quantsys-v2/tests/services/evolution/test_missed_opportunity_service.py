"""MissedOpportunityService 测试（P0b）——信号/决策/K线仓储全部 mock。"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import polars as pl

from application.services.evolution.missed_opportunity_service import MissedOpportunityService

TODAY = date(2026, 8, 11)
SIGNAL_DATE = date(2026, 8, 3)  # 距 TODAY 6 个交易日（造 8 根 K 线，含信号日）


def _kline_df(start, days, close=10.0):
    return pl.DataFrame({
        'symbol': ['300255'] * days,
        'trade_date': [start + timedelta(days=i) for i in range(days)],
        'open': [close] * days, 'high': [close] * days,
        'low': [close] * days, 'close': [close] * days,
        'volume': [1000] * days, 'amount': [10000.0] * days,
    })


def _signal(**kw):
    s = {'id': 101, 'signal_date': SIGNAL_DATE, 'symbol': '300255',
         'action': 'buy', 'status': 'pending', 'strategy_id': 'cci_reversal',
         'price': 24.43, 'confidence': 0.8}
    s.update(kw)
    return s


def _service(signals, kline_df, existing_decisions=None):
    signal_repo = MagicMock()
    signal_repo.get_signals_by_date_range.return_value = signals
    decision_repo = MagicMock()
    decision_repo.get_decision.return_value = None
    decision_repo.get_decisions_by_entity.return_value = existing_decisions or []
    kline_repo = MagicMock()
    kline_repo.get_daily_klines.return_value = kline_df
    return MissedOpportunityService(
        signal_repo=signal_repo, decision_repo=decision_repo, kline_repo=kline_repo,
    ), decision_repo


def test_pending_buy_signal_captured():
    svc, repo = _service([_signal()], _kline_df(SIGNAL_DATE, 8))
    result = svc.capture(today=TODAY)
    assert result['captured'] == 1
    args = repo.create_decision.call_args[0][0]
    assert args['decision_id'] == 'MISS-101'
    assert args['decision_type'] == 'missed_opportunity'
    assert args['parameters']['symbol'] == '300255'
    assert args['parameters']['price'] == 24.43
    assert args['created_at'].date() == SIGNAL_DATE


def test_approved_signal_not_captured():
    svc, repo = _service([_signal(status='approved')], _kline_df(SIGNAL_DATE, 8))
    result = svc.capture(today=TODAY)
    assert result['captured'] == 0
    assert result['scanned'] == 0  # approved 不进候选
    repo.create_decision.assert_not_called()


def test_sell_signal_not_captured():
    svc, repo = _service([_signal(action='sell')], _kline_df(SIGNAL_DATE, 8))
    result = svc.capture(today=TODAY)
    assert result['captured'] == 0
    repo.create_decision.assert_not_called()


def test_signal_in_grace_period_skipped():
    # 信号日后仅 3 根 K 线 < 5 天宽限期
    svc, repo = _service([_signal(signal_date=date(2026, 8, 7))],
                         _kline_df(date(2026, 8, 7), 4))
    result = svc.capture(today=TODAY)
    assert result['skipped_in_grace'] == 1
    repo.create_decision.assert_not_called()


def test_duplicate_skipped():
    svc, repo = _service([_signal()], _kline_df(SIGNAL_DATE, 8))
    repo.get_decision.return_value = {'decision_id': 'MISS-101'}  # 已捕获过
    result = svc.capture(today=TODAY)
    assert result['skipped_duplicate'] == 1
    repo.create_decision.assert_not_called()


def test_acted_within_grace_skipped():
    acted = [{'decision_type': 'trade_buy',
              'created_at': datetime(2026, 8, 5, 10, 0)}]  # 信号日后第 2 天买入
    svc, repo = _service([_signal()], _kline_df(SIGNAL_DATE, 8), acted)
    result = svc.capture(today=TODAY)
    assert result['skipped_acted'] == 1
    repo.create_decision.assert_not_called()


def test_daily_cap_and_confidence_dedup():
    # 同日同 symbol 两条信号留 confidence 高的；同日 6 个 symbol 只捕 5 条
    signals = [_signal(id=101, confidence=0.5), _signal(id=102, confidence=0.9)]
    signals += [_signal(id=200 + i, symbol=f'30000{i}', confidence=0.1 * i)
                for i in range(6)]
    # 每个 symbol 的 K 线查询都要返回成熟数据
    kline_repo_df = _kline_df(SIGNAL_DATE, 8)
    signal_repo = MagicMock()
    signal_repo.get_signals_by_date_range.return_value = signals
    decision_repo = MagicMock()
    decision_repo.get_decision.return_value = None
    decision_repo.get_decisions_by_entity.return_value = []
    kline_repo = MagicMock()
    kline_repo.get_daily_klines.return_value = kline_repo_df
    svc = MissedOpportunityService(
        signal_repo=signal_repo, decision_repo=decision_repo, kline_repo=kline_repo)
    result = svc.capture(today=TODAY)
    assert result['captured'] == 5  # cap=5
    captured_ids = [c[0][0]['decision_id'] for c in decision_repo.create_decision.call_args_list]
    assert 'MISS-102' in captured_ids      # 同 symbol 留高 confidence
    assert 'MISS-101' not in captured_ids
    assert 'MISS-200' not in captured_ids  # confidence=0 最低被 cap 掉


def test_missing_price_falls_back_to_signal_day_close():
    svc, repo = _service([_signal(price=None)], _kline_df(SIGNAL_DATE, 8, close=24.43))
    result = svc.capture(today=TODAY)
    assert result['captured'] == 1
    assert repo.create_decision.call_args[0][0]['parameters']['price'] == 24.43
