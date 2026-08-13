"""ChanScanService 测试——池内股票缠论买卖点扫描落 signals 表"""
from unittest.mock import patch, MagicMock
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
    @patch('application.services.chan_scan_service.SignalORMRepository')
    @patch('application.services.chan_scan_service.StockPoolORMRepository')
    @patch('application.services.chan_scan_service.ChanService')
    def test_writes_only_latest_day_buypoints(self, mock_chan, mock_pool, mock_sig):
        """只落最近交易日的买卖点；旧日期的买卖点跳过"""
        mock_pool.return_value.get_all.return_value = _pools()
        mock_chan.return_value.analyze.side_effect = [
            _analyze_result(bp_date='2026-08-04'),   # 600519: 当日信号 → 落库
            _analyze_result(bp_date='2026-07-20'),   # 000858: 旧信号 → 跳过
        ]
        mock_sig.return_value.create_signal.return_value = 101

        result = ChanScanService().scan()

        assert result['scanned'] == 2
        assert result['signals_written'] == 1
        call = mock_sig.return_value.create_signal.call_args[0][0]
        assert call['symbol'] == '600519'  # 归一为无后缀（signals.symbol FK 契约）
        assert call['action'] == 'buy'
        assert call['strategy_id'] == 'chan_1买'
        assert call['confidence'] == 90.0          # 0.9 → 0-100 映射
        assert call['status'] == 'pending'
        assert call['signal_date'] == '2026-08-04'

    @patch('application.services.chan_scan_service.SignalORMRepository')
    @patch('application.services.chan_scan_service.StockPoolORMRepository')
    @patch('application.services.chan_scan_service.ChanService')
    def test_empty_klines_counted_skipped_and_error_isolated(self, mock_chan, mock_pool, mock_sig):
        """无K线→skipped；单股异常→errors 且不中断"""
        mock_pool.return_value.get_all.return_value = _pools()
        mock_chan.return_value.analyze.side_effect = [
            {'symbol': '600519.SH', 'trend_type': '无数据', 'bis': [], 'segments': [],
             'zhongshus': [], 'buypoints': [], 'klines': []},
            RuntimeError('boom'),
        ]
        result = ChanScanService().scan()
        assert result['skipped'] == 1
        assert result['errors'] == 1
        assert result['signals_written'] == 0

    @patch('application.services.chan_scan_service.SignalORMRepository')
    @patch('application.services.chan_scan_service.StockPoolORMRepository')
    @patch('application.services.chan_scan_service.ChanService')
    def test_dedup_via_create_signal_conflict(self, mock_chan, mock_pool, mock_sig):
        """create_signal 返回 0（唯一键冲突）→ 计入 duplicates 而非 written"""
        pools = _pools()[:1]
        pools[0]['members'] = [{'symbol': '600519.SH', 'name': '贵州茅台'}]
        mock_pool.return_value.get_all.return_value = pools
        mock_chan.return_value.analyze.return_value = _analyze_result()
        mock_sig.return_value.create_signal.return_value = 0

        result = ChanScanService().scan()
        assert result['signals_written'] == 0
        assert result['duplicates'] == 1


class TestPoolSymbols:
    @patch('application.services.chan_scan_service.SignalORMRepository')
    @patch('application.services.chan_scan_service.StockPoolORMRepository')
    @patch('application.services.chan_scan_service.ChanService')
    def test_symbol_suffix_normalized_and_deduped(self, mock_chan, mock_pool, mock_sig):
        """统一归一为无后缀形式（stocks/signals 表全部无后缀，signals.symbol
        有 FK 到 stocks.symbol——带后缀写入会 FK 冲突被吞成"duplicates"），
        且 002475 与 002475.SZ 两种池内写法去重"""
        mock_pool.return_value.get_all.return_value = [{
            'id': 1, 'name': 'p', 'scan_enabled': True,
            'members': [{'symbol': '002475', 'name': 'a'},
                        {'symbol': '002475.SZ', 'name': 'a'},
                        {'symbol': '600519.SH', 'name': 'b'},
                        {'symbol': '300059.SZ', 'name': 'c'}],
        }]
        symbols = ChanScanService()._pool_symbols()
        codes = [s['symbol'] for s in symbols]
        assert codes == ['002475', '600519', '300059']

    @patch('application.services.chan_scan_service.SignalORMRepository')
    @patch('application.services.chan_scan_service.StockPoolORMRepository')
    @patch('application.services.chan_scan_service.ChanService')
    def test_sell_buypoint_written_as_sell(self, mock_chan, mock_pool, mock_sig):
        """卖点落库：action='sell'，strategy_id='chan_1卖'"""
        pools = _pools()[:1]
        pools[0]['members'] = [{'symbol': '600519.SH', 'name': '贵州茅台'}]
        mock_pool.return_value.get_all.return_value = pools
        mock_chan.return_value.analyze.return_value = _analyze_result(bp_type='1卖')
        mock_sig.return_value.create_signal.return_value = 102

        result = ChanScanService().scan()
        assert result['signals_written'] == 1
        call = mock_sig.return_value.create_signal.call_args[0][0]
        assert call['action'] == 'sell'
        assert call['strategy_id'] == 'chan_1卖'
