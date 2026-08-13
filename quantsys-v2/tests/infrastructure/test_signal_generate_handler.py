"""_handle_signal_generate 重写测试（2026-08-04）

桩任务 → 真实扫描落库：宇宙=非空池成员∪持仓，逐策略 PoolSignalScanner，
buy/sell 经 SignalORMRepository.create_signal 落库（幂等去重）。
"""
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.scheduler.scheduler import SchedulerService


def _scan_result(buys=(), sells=()):
    return {
        'buy_signals': [
            {'symbol': s, 'signal': 'buy', 'current_price': 10.0,
             'reasons': ['RSI超卖反弹'], 'indicators': {'rsi': 28.0},
             'trade_params': {}, 'trade_date': '2026-08-04', 'error': None}
            for s in buys
        ],
        'sell_signals': [
            {'symbol': s, 'signal': 'sell', 'current_price': 20.0,
             'reasons': ['MACD死叉'], 'indicators': {'macd': -0.5},
             'trade_params': {}, 'trade_date': '2026-08-04', 'error': None}
            for s in sells
        ],
        'hold_signals': [], 'errors': [],
    }


@pytest.fixture
def svc():
    return SchedulerService()


def _run(svc, universe=('600000', '300750'), names=None, scan_side_effect=None, create_returns=None):
    names = names or {'600000': '浦发银行', '300750': '宁德时代'}
    with patch('infrastructure.scheduler.scheduler.HeatmapRepository') as MockHM, \
         patch('infrastructure.scheduler.scheduler.PoolSignalScanner') as MockScanner, \
         patch('infrastructure.scheduler.scheduler.SignalORMRepository') as MockSigRepo:
        hm = MockHM.return_value
        hm.get_pool_members_now.return_value = set(universe[:1])
        hm.get_current_holding_symbols.return_value = set(universe[1:])
        hm.get_stocks_meta.return_value = {s: {'name': n} for s, n in names.items()}

        scanner = MockScanner.return_value
        if scan_side_effect:
            scanner.scan_pool_signals.side_effect = scan_side_effect
        else:
            scanner.scan_pool_signals.return_value = _scan_result(buys=('600000',), sells=('300750',))

        sig_repo = MockSigRepo.return_value
        sig_repo.create_signal.side_effect = create_returns or [101, 0]

        result = svc._handle_signal_generate({'strategy_ids': [162]})
    return result, scanner, sig_repo


class TestSignalGenerateHandler:
    def test_scans_universe_and_persists_buy_sell(self, svc):
        result, scanner, sig_repo = _run(svc)
        assert result['status'] == 'success'
        assert result['signals_saved'] == 1
        assert result['duplicates'] == 1
        # 扫描器拿到的是并集宇宙
        scanned_symbols = scanner.scan_pool_signals.call_args.kwargs.get('symbols') \
            or scanner.scan_pool_signals.call_args[1].get('symbols') \
            or scanner.scan_pool_signals.call_args[0][0]
        assert set(scanned_symbols) == {'600000', '300750'}
        # 落库字段：name 取自 stocks meta，action_type 由 repo 推导
        first_call = sig_repo.create_signal.call_args_list[0][0][0]
        assert first_call['symbol'] == '600000'
        assert first_call['name'] == '浦发银行'
        assert first_call['action'] == 'BUY'  # signals 大写契约（08-13，落库点 .upper()）
        assert first_call['price'] == 10.0
        assert first_call['reason'] == 'RSI超卖反弹'
        assert first_call['indicators'] == {'rsi': 28.0}
        assert first_call['signal_date'] is not None

    def test_hold_signals_not_persisted(self, svc):
        result, scanner, sig_repo = _run(svc, scan_side_effect=None)
        # 只有 buy/sell 落库（fixture 中 hold_signals 为空，验证 create 只被调 buy+sell 次）
        assert sig_repo.create_signal.call_count == 2

    def test_strategy_failure_marks_failed_when_nothing_saved(self, svc):
        result, _, _ = _run(svc, scan_side_effect=RuntimeError('strategy boom'))
        assert result['status'] == 'failed'
        assert result['signals_saved'] == 0
        assert 'strategy boom' in str(result['strategy_errors'])

    def test_empty_universe_returns_success_with_zero(self, svc):
        with patch('infrastructure.scheduler.scheduler.HeatmapRepository') as MockHM:
            hm = MockHM.return_value
            hm.get_pool_members_now.return_value = set()
            hm.get_current_holding_symbols.return_value = set()
            result = svc._handle_signal_generate({'strategy_ids': [162]})
        assert result['status'] == 'success'
        assert result['universe_size'] == 0
        assert result['signals_saved'] == 0

    def test_suffixed_symbols_normalized_to_bare(self, svc):
        """池成员带交易所后缀（688012.SH）必须归一为裸代码——
        signals.symbol 有 FK 到 stocks.symbol，带后缀会 ForeignKeyViolation"""
        with patch('infrastructure.scheduler.scheduler.HeatmapRepository') as MockHM, \
             patch('infrastructure.scheduler.scheduler.PoolSignalScanner') as MockScanner, \
             patch('infrastructure.scheduler.scheduler.SignalORMRepository') as MockSigRepo:
            hm = MockHM.return_value
            hm.get_pool_members_now.return_value = {'688012.SH'}
            hm.get_current_holding_symbols.return_value = set()
            hm.get_stocks_meta.return_value = {'688012': {'name': '某科创股'}}
            MockScanner.return_value.scan_pool_signals.return_value = _scan_result(buys=('688012',))
            sig_repo = MockSigRepo.return_value
            sig_repo.create_signal.return_value = 201

            result = svc._handle_signal_generate({'strategy_ids': [162]})

        assert result['signals_saved'] == 1
        call = sig_repo.create_signal.call_args[0][0]
        assert call['symbol'] == '688012'      # 裸代码入库
        assert call['name'] == '某科创股'
        # 扫描器拿到的也是归一后的宇宙
        scanned = MockScanner.return_value.scan_pool_signals.call_args.kwargs.get('symbols') \
            or MockScanner.return_value.scan_pool_signals.call_args[0][0]
        assert scanned == ['688012']
