"""
Tests for financial indicators injection in strategy code service
"""
import pytest
from unittest.mock import Mock, patch
import pandas as pd
from application.services.strategy_code_service import StrategyCodeService


class TestFinancialInjection:
    """Test financial indicators injection"""

    def test_fetch_from_sina_success(self):
        """Test successful fetch from Sina Finance"""
        service = StrategyCodeService()

        # Mock akshare response
        mock_income_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '营业收入': 100000000,
                '营业成本': 60000000,
                '净利润': 20000000,
                '营业利润': 25000000,
                '公告日期': '20260425'
            }
        ])

        mock_balance_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '资产总计': 500000000,
                '负债合计': 200000000,
                '股东权益合计': 300000000,
                '流动资产合计': 150000000,
                '流动负债合计': 100000000,
                '公告日期': '20260425'
            }
        ])

        mock_cashflow_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '经营活动现金流量净额': 18000000,
                '公告日期': '20260425'
            }
        ])

        with patch('akshare.stock_financial_report_sina') as mock_ak:
            mock_ak.side_effect = [mock_income_df, mock_balance_df, mock_cashflow_df]

            result = service._fetch_from_sina('000001')

            assert result is not None
            assert 'income' in result
            assert 'balance' in result
            assert 'cashflow' in result
            assert len(result['income']) == 1
            assert result['income'][0]['营业收入'] == 100000000

    def test_fetch_from_eastmoney_success(self):
        """Test successful fetch from East Money"""
        service = StrategyCodeService()

        # Mock akshare East Money response
        mock_df = pd.DataFrame([
            {
                '报告期': '2026-03-31',
                '净资产收益率': 15.5,
                '销售毛利率': 38.2,
                '销售净利率': 25.1,
                '资产负债率': 45.3,
                '营业总收入同比增长': 12.5,
                '流动比率': 1.8,
                '总资产净利率': 8.2,
                '营业利润率': 28.3,
                '公告日期': '2026-04-25'
            }
        ])

        with patch('akshare.stock_financial_analysis_indicator') as mock_ak:
            mock_ak.return_value = mock_df

            result = service._fetch_from_eastmoney('000001')

            assert result is not None
            assert len(result) == 1
            assert result[0]['净资产收益率'] == 15.5

    def test_calculate_indicators(self):
        """Test financial indicators calculation"""
        service = StrategyCodeService()

        # Prepare test data
        income = {
            '营业收入': 100000000,
            '营业成本': 60000000,
            '净利润': 20000000,
            '营业利润': 25000000
        }

        balance = {
            '资产总计': 500000000,
            '负债合计': 200000000,
            '股东权益合计': 300000000,
            '流动资产合计': 150000000,
            '流动负债合计': 100000000
        }

        cashflow = {
            '经营活动现金流量净额': 18000000
        }

        prev_income = {
            '营业收入': 90000000
        }

        result = service._calculate_indicators(income, balance, cashflow, prev_income)

        # Verify calculations
        assert abs(result['roe'] - 6.67) < 0.1  # 20M / 300M * 100
        assert abs(result['gross_margin'] - 40.0) < 0.1  # (100M - 60M) / 100M * 100
        assert abs(result['net_profit_margin'] - 20.0) < 0.1  # 20M / 100M * 100
        assert abs(result['debt_ratio'] - 40.0) < 0.1  # 200M / 500M * 100
        assert abs(result['revenue_growth'] - 11.11) < 0.1  # (100M - 90M) / 90M * 100
        assert abs(result['ocf_to_profit'] - 0.9) < 0.1  # 18M / 20M
        assert abs(result['current_ratio'] - 1.5) < 0.1  # 150M / 100M
        assert abs(result['roa'] - 4.0) < 0.1  # 20M / 500M * 100
        assert abs(result['operating_margin'] - 25.0) < 0.1  # 25M / 100M * 100

    def test_forward_fill_to_klines(self):
        """Test forward-fill temporal alignment"""
        service = StrategyCodeService()

        # Prepare K-lines
        klines = [
            {'trade_date': '2026-04-20'},  # Before announcement
            {'trade_date': '2026-04-25'},  # Announcement day
            {'trade_date': '2026-04-26'},  # After announcement
            {'trade_date': '2026-05-15'},  # Much later
        ]

        # Prepare financial timeline (quarterly)
        financial_timeline_q = [
            {
                'announce_date': '2026-04-25',
                'roe': 15.5,
                'gross_margin': 38.2,
                'net_profit_margin': 25.1,
                'debt_ratio': 45.3,
                'revenue_growth': 12.5,
                'ocf_to_profit': 0.9,
                'current_ratio': 1.8,
                'roa': 8.2,
                'operating_margin': 28.3
            }
        ]

        # Prepare financial timeline (annual) - empty for this test
        financial_timeline_y = []

        result = service._forward_fill_to_klines(klines, financial_timeline_q, financial_timeline_y)

        # Verify forward-fill logic
        import math
        assert math.isnan(result[0]['roe_q'])  # Before announcement - NaN
        assert result[1]['roe_q'] == 15.5  # Announcement day - has data
        assert result[2]['roe_q'] == 15.5  # After announcement - forward-filled
        assert result[3]['roe_q'] == 15.5  # Much later - still forward-filled

        # Verify annual indicators are NaN (no annual data)
        assert math.isnan(result[1]['roe_y'])

    def test_inject_financial_integration(self):
        """Test full financial injection integration"""
        service = StrategyCodeService()

        # Prepare K-lines
        klines = [
            {'trade_date': '2026-04-20', 'close': 100},
            {'trade_date': '2026-04-25', 'close': 102},
            {'trade_date': '2026-05-15', 'close': 105},
        ]

        # Mock Sina data source
        mock_income_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '营业收入': 100000000,
                '营业成本': 60000000,
                '净利润': 20000000,
                '营业利润': 25000000,
                '公告日期': '20260425'
            },
            {
                '报告日': '20251231',
                '营业收入': 90000000,
                '营业成本': 55000000,
                '净利润': 18000000,
                '营业利润': 22000000,
                '公告日期': '20260330'
            }
        ])

        mock_balance_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '资产总计': 500000000,
                '负债合计': 200000000,
                '股东权益合计': 300000000,
                '流动资产合计': 150000000,
                '流动负债合计': 100000000,
                '公告日期': '20260425'
            }
        ])

        mock_cashflow_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '经营活动现金流量净额': 18000000,
                '公告日期': '20260425'
            }
        ])

        with patch('akshare.stock_financial_report_sina') as mock_ak:
            mock_ak.side_effect = [mock_income_df, mock_balance_df, mock_cashflow_df]

            result = service._inject_financial(klines, '000001')

            # Verify columns exist
            assert 'roe_q' in result[0]
            assert 'gross_margin_q' in result[0]
            assert 'roe_y' in result[0]

            # Verify forward-fill logic
            import math
            assert math.isnan(result[0]['roe_q'])  # Before announcement
            assert result[1]['roe_q'] > 0  # Announcement day
            assert result[2]['roe_q'] == result[1]['roe_q']  # Forward-filled

    def test_strategy_with_financial_indicators(self):
        """Test strategy execution with financial indicators"""
        service = StrategyCodeService()

        # Create a test strategy that uses financial indicators
        strategy_code = """
# 基本面 + 技术面共振策略
df['quality_stock'] = (
    (df['roe_y'] >= 10) &
    (df['debt_ratio_y'] < 70) &
    (df['gross_margin_q'] > 20)
)

df['buy'] = (df['rsi'] < 35) & df['quality_stock']
df['sell'] = df['rsi'] > 65
"""

        # Mock K-lines with RSI
        klines = [
            {'trade_date': '2026-04-20', 'close': 100, 'rsi': 30},
            {'trade_date': '2026-04-25', 'close': 102, 'rsi': 32},
            {'trade_date': '2026-05-15', 'close': 105, 'rsi': 70},
        ]

        # Mock financial data
        mock_income_df = pd.DataFrame([
            {
                '报告日': '20251231',
                '营业收入': 100000000,
                '营业成本': 60000000,
                '净利润': 20000000,
                '营业利润': 25000000,
                '公告日期': '20260330'
            }
        ])

        mock_balance_df = pd.DataFrame([
            {
                '报告日': '20251231',
                '资产总计': 500000000,
                '负债合计': 200000000,
                '股东权益合计': 300000000,
                '流动资产合计': 150000000,
                '流动负债合计': 100000000,
                '公告日期': '20260330'
            }
        ])

        mock_cashflow_df = pd.DataFrame([
            {
                '报告日': '20251231',
                '经营活动现金流量净额': 18000000,
                '公告日期': '20260330'
            }
        ])

        with patch('akshare.stock_financial_report_sina') as mock_ak:
            mock_ak.side_effect = [mock_income_df, mock_balance_df, mock_cashflow_df]

            # Inject financial indicators
            result_klines = service._inject_financial(klines, '000001')

            # Verify financial columns exist
            assert 'roe_y' in result_klines[0]
            assert 'gross_margin_q' in result_klines[0]
            assert 'debt_ratio_y' in result_klines[0]

            # Verify strategy can access these columns (would be tested in actual execution)
            # Here we just verify the columns have valid values after announcement date
            import math
            assert not math.isnan(result_klines[1]['roe_y'])  # After announcement
            assert result_klines[1]['roe_y'] > 0
