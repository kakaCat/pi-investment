"""SignalGenerateJob 重写测试（2026-10-23 迁移）

背景：`SchedulerService._handle_signal_generate` 已于 2026-10-20 **委托**
`qs_ops.application.jobs.signal_jobs.SignalGenerateJob`（唯一实现，含宇宙并入
rotation_main 持仓、SELL 只对有持仓标的落库的降噪）。原测试 patch 的是旧内联
实现的模块级导入，委托后全部失效（打到真实 DB）。

本文件改为直接测试 SignalGenerateJob.execute()，断言口径不变：
宇宙=非空池成员∪持仓，逐策略 PoolSignalScanner，buy/sell 经
SignalORMRepository.create_signal 落库（幂等去重），带后缀的标的归一为裸代码。
"""
import asyncio
from unittest.mock import patch

import pytest

from qs_ops.application.jobs.signal_jobs import SignalGenerateJob


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


def _run(universe=('600000', '300750'), names=None, scan_side_effect=None,
         create_returns=None, scan_result=None):
    """执行一次 SignalGenerateJob，返回 (result_dict, scanner_mock, sig_repo_mock)。"""
    names = names or {'600000': '浦发银行', '300750': '宁德时代'}
    with patch('adapters.outbound.repositories.heatmap_repository.HeatmapRepository') as MockHM, \
         patch('adapters.outbound.repositories.kline_repository.KlineORMRepository'), \
         patch('adapters.outbound.repositories.strategy_repository.StrategyORMRepository'), \
         patch('qs_sourcing.adapters.outbound.repositories.signal_repository.SignalORMRepository') as MockSigRepo, \
         patch('qs_sourcing.application.services.pool_signal_scanner.PoolSignalScanner') as MockScanner, \
         patch('adapters.outbound.repositories.SimulationORMRepository') as MockSimRepo:
        hm = MockHM.return_value
        hm.get_pool_members_now.return_value = set(universe[:1])
        hm.get_current_holding_symbols.return_value = set(universe[1:])
        hm.get_stocks_meta.return_value = {s: {'name': n} for s, n in names.items()}

        # 模拟账户无持仓：宇宙不额外扩张（降噪分支仍按 held 集合工作）
        MockSimRepo.return_value.list_accounts.return_value = []

        scanner = MockScanner.return_value
        if scan_side_effect:
            scanner.scan_pool_signals.side_effect = scan_side_effect
        else:
            scanner.scan_pool_signals.return_value = scan_result or _scan_result(
                buys=('600000',), sells=('300750',))

        sig_repo = MockSigRepo.return_value
        sig_repo.create_signal.side_effect = create_returns or [101, 0]

        job_result = asyncio.run(SignalGenerateJob().execute({'strategy_ids': [162]}))
        details = (job_result.details or {}).get('details', job_result.details or {})
        result = {'status': 'success' if job_result.success else 'failed', **details}
    return result, scanner, sig_repo


class TestSignalGenerateJob:
    def test_scans_universe_and_persists_buy_sell(self):
        result, scanner, sig_repo = _run()
        assert result['status'] == 'success'
        assert result['signals_saved'] == 1
        assert result['duplicates'] == 1
        # 扫描器拿到的是并集宇宙
        scanned_symbols = scanner.scan_pool_signals.call_args.kwargs.get('symbols') \
            or scanner.scan_pool_signals.call_args[0][0]
        assert set(scanned_symbols) == {'600000', '300750'}
        # 落库字段：name 取自 stocks meta，action 大写
        first_call = sig_repo.create_signal.call_args_list[0][0][0]
        assert first_call['symbol'] == '600000'
        assert first_call['name'] == '浦发银行'
        assert first_call['action'] == 'BUY'
        assert first_call['price'] == 10.0
        assert first_call['reason'] == 'RSI超卖反弹'
        assert first_call['indicators'] == {'rsi': 28.0}
        assert first_call['signal_date'] is not None

    def test_buy_sell_both_called(self):
        """buy + sell 都会尝试落库（各 1 次）"""
        result, scanner, sig_repo = _run(create_returns=[101, 102])
        assert sig_repo.create_signal.call_count == 2

    def test_strategy_failure_marks_failed_when_nothing_saved(self):
        result, _, _ = _run(scan_side_effect=RuntimeError('strategy boom'))
        assert result['status'] == 'failed'
        assert result['signals_saved'] == 0
        assert 'strategy boom' in str(result['strategy_errors'])

    def test_empty_universe_returns_success_with_zero(self):
        with patch('adapters.outbound.repositories.heatmap_repository.HeatmapRepository') as MockHM, \
             patch('adapters.outbound.repositories.SimulationORMRepository') as MockSimRepo:
            hm = MockHM.return_value
            hm.get_pool_members_now.return_value = set()
            hm.get_current_holding_symbols.return_value = set()
            MockSimRepo.return_value.list_accounts.return_value = []
            job_result = asyncio.run(SignalGenerateJob().execute({'strategy_ids': [162]}))
            details = (job_result.details or {}).get('details', job_result.details or {})
        assert job_result.success is True
        assert details.get('universe_size') == 0
        assert details.get('signals_saved') == 0

    def test_suffixed_symbols_normalized_to_bare(self):
        """池成员带交易所后缀（688012.SH）必须归一为裸代码——
        signals.symbol 有 FK 到 stocks.symbol，带后缀会 ForeignKeyViolation"""
        result, scanner, sig_repo = _run(
            universe=('688012.SH',),
            names={'688012': '某科创股'},
            scan_result=_scan_result(buys=('688012',)),
            create_returns=[201],
        )
        assert result['signals_saved'] == 1
        call = sig_repo.create_signal.call_args[0][0]
        assert call['symbol'] == '688012'      # 裸代码入库
        assert call['name'] == '某科创股'
        # 扫描器拿到的也是归一后的宇宙
        scanned = scanner.scan_pool_signals.call_args.kwargs.get('symbols') \
            or scanner.scan_pool_signals.call_args[0][0]
        assert scanned == ['688012']
