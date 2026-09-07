"""Unit tests for EastMoneyAdapter quote parsing (价格单位).

eastmoney `qt/stock/get` 在未传 fltt=2 时返回「分」单位整数价格
(f43/f44/f45/f46/f60/f152/f170 均 ×100)。_parse_quote_data 必须换算为元。
"""
from domain.quantlib.adapters.eastmoney_adapter import EastMoneyAdapter


def _raw_quote():
    """模拟 eastmoney 原始响应（分单位，茅台 1253.00 元）"""
    return {
        'f58': '贵州茅台',
        'f43': 125300,        # 现价 1253.00
        'f46': 124000,        # 今开 1240.00
        'f44': 126000,        # 最高 1260.00
        'f45': 123500,        # 最低 1235.00
        'f60': 124100,        # 昨收 1241.00
        'f47': 25000,         # 成交量（手，不缩放）
        'f48': 3100000000.0,  # 成交额（元，不缩放）
        'f170': 97,           # 涨跌幅 0.97%
    }


class TestParseQuoteData:
    def setup_method(self):
        self.adapter = EastMoneyAdapter()

    def test_prices_converted_from_cents_to_yuan(self):
        q = self.adapter._parse_quote_data(_raw_quote(), '600519.SH')
        assert q is not None
        assert q['price'] == 1253.0
        assert q['open'] == 1240.0
        assert q['high'] == 1260.0
        assert q['low'] == 1235.0
        assert q['pre_close'] == 1241.0

    def test_change_computed_in_yuan(self):
        q = self.adapter._parse_quote_data(_raw_quote(), '600519.SH')
        assert q['change'] == round(1253.0 - 1241.0, 2)

    def test_change_pct_converted(self):
        q = self.adapter._parse_quote_data(_raw_quote(), '600519.SH')
        assert q['change_pct'] == 0.97

    def test_volume_and_amount_not_scaled(self):
        q = self.adapter._parse_quote_data(_raw_quote(), '600519.SH')
        assert q['volume'] == 25000.0          # 手
        assert q['amount'] == 3100000000.0     # 元

    def test_zero_price_returns_none(self):
        raw = _raw_quote()
        raw['f43'] = 0
        assert self.adapter._parse_quote_data(raw, '600519.SH') is None
