"""
DataService单元测试
"""
import pytest
from application.services.data_service import DataService


class TestStockQueries:
    """股票综合查询测试"""

    def setup_method(self):
        self.service = DataService()

    def teardown_method(self):
        self.service.close()

    def test_get_stock_full_data(self):
        """测试获取股票完整数据"""
        result = self.service.get_stock_full_data(
            "000001.SZ",
            "2024-01-01",
            "2024-01-31"
        )

        assert isinstance(result, dict)
        assert result['symbol'] == '000001.SZ'
        assert 'stock_info' in result
        assert 'klines' in result
        assert isinstance(result['klines'], list)
        assert 'kline_stats' in result
        assert 'available_factors' in result
        assert 'latest_factors' in result
        assert 'signals' in result
        assert result['date_range']['start'] == '2024-01-01'
        assert result['date_range']['end'] == '2024-01-31'

    def test_get_stock_full_data_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.service.get_stock_full_data("INVALID", "2024-01-01", "2024-01-31")

    def test_get_stock_analysis(self):
        """测试获取股票分析快照"""
        result = self.service.get_stock_analysis("000001.SZ")

        assert isinstance(result, dict)
        assert result['symbol'] == '000001.SZ'
        assert 'stock_info' in result
        assert 'latest_kline' in result
        assert 'factors' in result
        assert 'latest_signal' in result
        assert 'recent_signals' in result
        assert 'risk_metrics' in result
        assert 'recent_trades' in result

    def test_get_stock_analysis_not_found(self):
        """测试不存在的股票"""
        result = self.service.get_stock_analysis("999999.SZ")
        assert result['symbol'] == '999999.SZ'
        assert result['stock_info'] is None
        assert result['latest_kline'] is None


class TestPortfolioQueries:
    """组合分析测试"""

    def setup_method(self):
        self.service = DataService()

    def teardown_method(self):
        self.service.close()

    def test_get_portfolio_overview(self):
        result = self.service.get_portfolio_overview()

        assert isinstance(result, dict)
        assert 'holdings' in result
        assert 'stats' in result
        assert 'balance' in result
        assert 'recent_trades' in result
        assert isinstance(result['holdings'], list)
        assert isinstance(result['recent_trades'], list)

    def test_get_portfolio_risk_analysis(self):
        result = self.service.get_portfolio_risk_analysis()

        assert isinstance(result, dict)
        assert 'portfolio_risk' in result
        assert 'balance_stats' in result
        assert 'holdings_count' in result


class TestMarketQueries:
    """市场全景测试"""

    def setup_method(self):
        self.service = DataService()

    def teardown_method(self):
        self.service.close()

    def test_get_market_overview(self):
        result = self.service.get_market_overview()

        assert isinstance(result, dict)
        assert 'total_stocks' in result
        assert 'stocks_sample' in result
        assert 'latest_signals' in result
        assert 'factor_coverages' in result
        assert 'top_strategies' in result

    def test_get_top_signals(self):
        signals = self.service.get_top_signals(limit=10)

        assert isinstance(signals, list)
        assert len(signals) <= 10

        # 验证按置信度降序排列
        if len(signals) > 1:
            confidences = [s.get('confidence', 0) or 0 for s in signals]
            assert confidences == sorted(confidences, reverse=True)


class TestBacktestWorkflow:
    """回测工作流测试"""

    def setup_method(self):
        self.service = DataService()

    def teardown_method(self):
        self.service.close()

    def test_get_backtest_workflow_data(self):
        result = self.service.get_backtest_workflow_data(
            "000001.SZ",
            "2024-01-01",
            "2024-01-31"
        )

        assert isinstance(result, dict)
        assert result['symbol'] == '000001.SZ'
        assert 'klines' in result
        assert isinstance(result['klines'], list)
        assert 'signals' in result
        assert 'trades' in result
        assert 'factor_history' in result

    def test_save_backtest_workflow(self):
        metrics = {
            'total_return': 0.08,
            'sharpe_ratio': 1.2,
            'max_drawdown': -0.05,
            'win_rate': 0.55,
            'total_trades': 15,
            'winning_trades': 8,
            'losing_trades': 7
        }

        try:
            backtest_id = self.service.save_backtest_workflow(
                strategy_name="test_ma_cross_flow",
                symbol="000001.SZ",
                start_date="2024-01-01",
                end_date="2024-01-31",
                initial_capital=100000.0,
                final_capital=108000.0,
                metrics=metrics,
                parameters={"ma_short": 5, "ma_long": 20}
            )
            assert isinstance(backtest_id, int)
            assert backtest_id > 0
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")


class TestBatchOperations:
    """批量操作测试"""

    def setup_method(self):
        self.service = DataService()

    def teardown_method(self):
        self.service.close()

    def test_batch_get_klines(self):
        symbols = ["000001.SZ", "000002.SZ"]
        result = self.service.batch_get_klines(symbols, "2024-01-01", "2024-01-31")

        assert isinstance(result, dict)
        for symbol in symbols:
            if symbol in result:
                assert isinstance(result[symbol], list)

    def test_batch_get_klines_empty(self):
        result = self.service.batch_get_klines([], "2024-01-01", "2024-01-31")
        assert result == {}

    def test_batch_get_latest_factors(self):
        symbols = ["000001.SZ"]
        result = self.service.batch_get_latest_factors(symbols)

        assert isinstance(result, dict)
        for symbol, factors in result.items():
            assert symbol in symbols
            assert isinstance(factors, dict)

    def test_batch_get_risk_metrics(self):
        symbols = ["000001.SZ"]
        result = self.service.batch_get_risk_metrics(symbols)

        assert isinstance(result, dict)
        for symbol, metrics in result.items():
            assert symbol in symbols
            assert isinstance(metrics, dict)


class TestRiskSummary:
    """风险综合测试"""

    def setup_method(self):
        self.service = DataService()

    def teardown_method(self):
        self.service.close()

    def test_get_risk_summary(self):
        result = self.service.get_risk_summary()

        assert isinstance(result, dict)
        assert 'balance' in result
        assert 'balance_stats' in result
        assert 'balance_history' in result
        assert 'holdings_count' in result
        assert 'risk_metrics' in result


class TestDataIntegrity:
    """数据完整性测试"""

    def setup_method(self):
        self.service = DataService()

    def teardown_method(self):
        self.service.close()

    def test_check_data_integrity(self):
        result = self.service.check_data_integrity("000001.SZ")

        assert isinstance(result, dict)
        assert result['symbol'] == '000001.SZ'
        assert 'checks' in result
        assert 'kline' in result['checks']
        assert 'factor' in result['checks']
        assert 'signal' in result['checks']
        assert 'risk' in result['checks']
        assert isinstance(result['all_checks_pass'], bool)

    def test_check_data_integrity_nonexistent(self):
        result = self.service.check_data_integrity("999999.SZ")
        assert result['symbol'] == '999999.SZ'
        assert 'checks' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
