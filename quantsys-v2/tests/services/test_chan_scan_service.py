"""ChanScanService 测试——池内股票缠论买卖点扫描落 signals 表"""
from unittest.mock import MagicMock
import pytest

from application.services.chan_scan_service import ChanScanService


def _pools():
    return [{
        'id': 1, 'name': '高质量池', 'scan_enabled': True,
        'members': [{'symbol': '600519.SH', 'name': '贵州茅台'},
                    {'symbol': '000858.SZ', 'name': '五粮液'}],
    }]


def _analyze_result(bp_date='2026-08-04', kline_date='2026-08-04', bp_type='1买'):
    return {
        'symbol': '600519.SH', 'trend_type': '上涨',
        'bis': [], 'segments': [], 'zhongshus': [],
        'buypoints': [{'type': bp_type, 'price': 1620.5, 'index': 100,
                       'date': bp_date, 'confidence': 0.9,
                       'position_ratio': 1.0, 'reason': '下跌背驰'}],
        'klines': [{'date': kline_date, 'close': 1621.0}],
    }


class TestChanScan:
    def test_writes_only_latest_day_buypoints(self):
        mock_pool = MagicMock()
        mock_pool.get_all.return_value = _pools()
        mock_chan = MagicMock()
        mock_chan.analyze.side_effect = [
            _analyze_result(bp_date='2026-08-04'),
            _analyze_result(bp_date='2026-07-20'),
        ]
        mock_sig = MagicMock()
        mock_sig.create_signal.return_value = 101

        result = ChanScanService(chan_service=mock_chan, pool_repo=mock_pool, signal_repo=mock_sig).scan()

        assert result['scanned'] == 2
        assert result['signals_written'] == 1
        call = mock_sig.create_signal.call_args[0][0]
        assert call['symbol'] == '600519'
        assert call['action'] == 'BUY'
        assert call['strategy_id'] == 'chan_1买'
        assert call['confidence'] == 90.0
        assert call['status'] == 'pending'
        assert call['signal_date'] == '2026-08-04'

    def test_empty_klines_counted_skipped_and_error_isolated(self):
        mock_pool = MagicMock()
        mock_pool.get_all.return_value = _pools()
        mock_chan = MagicMock()
        mock_chan.analyze.side_effect = [
            {'symbol': '600519.SH', 'trend_type': '无数据', 'bis': [], 'segments': [],
             'zhongshus': [], 'buypoints': [], 'klines': []},
            RuntimeError('boom'),
        ]
        mock_sig = MagicMock()
        result = ChanScanService(chan_service=mock_chan, pool_repo=mock_pool, signal_repo=mock_sig).scan()
        assert result['skipped'] == 1
        assert result['errors'] == 1
        assert result['signals_written'] == 0

    def test_dedup_via_create_signal_conflict(self):
        pools = _pools()[:1]
        pools[0]['members'] = [{'symbol': '600519.SH', 'name': '贵州茅台'}]
        mock_pool = MagicMock()
        mock_pool.get_all.return_value = pools
        mock_chan = MagicMock()
        mock_chan.analyze.return_value = _analyze_result()
        mock_sig = MagicMock()
        mock_sig.create_signal.return_value = 0

        result = ChanScanService(chan_service=mock_chan, pool_repo=mock_pool, signal_repo=mock_sig).scan()
        assert result['signals_written'] == 0
        assert result['duplicates'] == 1


class TestPoolSymbols:
    def test_symbol_suffix_normalized_and_deduped(self):
        mock_pool = MagicMock()
        mock_pool.get_all.return_value = [{
            'id': 1, 'name': 'p', 'scan_enabled': True,
            'members': [{'symbol': '002475', 'name': 'a'},
                        {'symbol': '002475.SZ', 'name': 'a'},
                        {'symbol': '600519.SH', 'name': 'b'},
                        {'symbol': '300059.SZ', 'name': 'c'}],
        }]
        symbols = ChanScanService(pool_repo=mock_pool)._pool_symbols()
        codes = [s['symbol'] for s in symbols]
        assert codes == ['002475', '600519', '300059']

    def test_sell_buypoint_written_as_sell(self):
        pools = _pools()[:1]
        pools[0]['members'] = [{'symbol': '600519.SH', 'name': '贵州茅台'}]
        mock_pool = MagicMock()
        mock_pool.get_all.return_value = pools
        mock_chan = MagicMock()
        mock_chan.analyze.return_value = _analyze_result(bp_type='1卖')
        mock_sig = MagicMock()
        mock_sig.create_signal.return_value = 102

        result = ChanScanService(chan_service=mock_chan, pool_repo=mock_pool, signal_repo=mock_sig).scan()
        assert result['signals_written'] == 1
        call = mock_sig.create_signal.call_args[0][0]
        assert call['action'] == 'SELL'
        assert call['strategy_id'] == 'chan_1卖'
