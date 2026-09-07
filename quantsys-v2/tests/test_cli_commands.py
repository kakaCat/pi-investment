"""
CLI Commands Tests

测试CLI命令的执行和HTTP调用
"""

import pytest
from unittest.mock import Mock, MagicMock
from adapters.inbound.cli.command_base import CommandResult
from adapters.inbound.cli.commands.stock_commands import (
    StockSearchCommand,
    StockInfoCommand,
    StockListCommand,
    StockAnalysisCommand
)
from adapters.inbound.cli.commands.market_commands import (
    MarketOverviewCommand,
    MarketIndexCommand,
    MarketSectorCommand,
    MarketStatusCommand
)
from adapters.inbound.cli.commands.kline_commands import (
    KlineQueryCommand,
    KlineLatestCommand,
    KlineStatsCommand
)
from adapters.inbound.cli.commands.factor_commands import (
    FactorLatestCommand,
    FactorHistoryCommand,
    FactorListCommand,
    FactorCalculateCommand
)
from adapters.inbound.cli.commands.signal_commands import (
    SignalQueryCommand,
    SignalLatestCommand,
    SignalStatsCommand
)


class TestStockCommands:
    """测试股票命令"""

    def setup_method(self):
        """设置测试"""
        self.mock_client = Mock()

    def test_stock_search_success(self):
        """测试股票搜索成功"""
        # Mock响应
        self.mock_client.request.return_value = {
            'query': '平安',
            'total': 2,
            'stocks': [
                {'symbol': '000001.SZ', 'name': '平安银行'},
                {'symbol': '601318.SH', 'name': '中国平安'}
            ]
        }

        cmd = StockSearchCommand(self.mock_client)
        result = cmd.execute(q='平安', limit=10)

        assert result.success
        assert result.data['total'] == 2
        assert len(result.data['stocks']) == 2

    def test_stock_search_missing_param(self):
        """测试股票搜索缺少参数"""
        cmd = StockSearchCommand(self.mock_client)
        result = cmd.execute()

        assert not result.success
        assert '搜索关键词不能为空' in result.error

    def test_stock_info_success(self):
        """测试股票信息成功"""
        self.mock_client.request.return_value = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'market': 'A',
            'industry': '银行'
        }

        cmd = StockInfoCommand(self.mock_client)
        result = cmd.execute(symbol='000001.SZ')

        assert result.success
        assert result.data['symbol'] == '000001.SZ'

    def test_stock_list_success(self):
        """测试股票列表成功"""
        self.mock_client.request.return_value = {
            'count': 2,
            'stocks': [
                {'symbol': '000001.SZ', 'name': '平安银行'},
                {'symbol': '000002.SZ', 'name': '万科A'}
            ]
        }

        cmd = StockListCommand(self.mock_client)
        result = cmd.execute(market='A', limit=50)

        assert result.success
        assert result.data['count'] == 2


class TestMarketCommands:
    """测试市场命令"""

    def setup_method(self):
        """设置测试"""
        self.mock_client = Mock()

    def test_market_overview_success(self):
        """测试市场概览成功"""
        self.mock_client.request.return_value = {
            'indices': {
                '上证指数': {'price': 3000.0, 'change_pct': 1.5},
                '深证成指': {'price': 10000.0, 'change_pct': 2.0}
            }
        }

        cmd = MarketOverviewCommand(self.mock_client)
        result = cmd.execute()

        assert result.success
        assert '上证指数' in result.data['indices']

    def test_market_index_success(self):
        """测试指数行情成功"""
        self.mock_client.request.return_value = {
            'symbol': 'sh000001',
            'name': '上证指数',
            'price': 3000.0
        }

        cmd = MarketIndexCommand(self.mock_client)
        result = cmd.execute(symbol='sh000001')

        assert result.success
        assert result.data['symbol'] == 'sh000001'


class TestKlineCommands:
    """测试K线命令"""

    def setup_method(self):
        """设置测试"""
        self.mock_client = Mock()

    def test_kline_query_success(self):
        """测试K线查询成功"""
        self.mock_client.request.return_value = {
            'symbol': '000001.SZ',
            'count': 10,
            'klines': [
                {'date': '2024-01-01', 'close': 10.0},
                {'date': '2024-01-02', 'close': 10.5}
            ]
        }

        cmd = KlineQueryCommand(self.mock_client)
        result = cmd.execute(symbol='000001.SZ', limit=10)

        assert result.success
        assert result.data['count'] == 10

    def test_kline_query_missing_symbol(self):
        """测试K线查询缺少股票代码"""
        cmd = KlineQueryCommand(self.mock_client)
        result = cmd.execute(limit=10)

        assert not result.success
        assert '股票代码不能为空' in result.error


class TestFactorCommands:
    """测试因子命令"""

    def setup_method(self):
        """设置测试"""
        self.mock_client = Mock()

    def test_factor_latest_success(self):
        """测试最新因子成功"""
        self.mock_client.request.return_value = {
            'symbol': '000001.SZ',
            'factors': {
                'pe': 10.5,
                'pb': 1.2,
                'roe': 0.15
            }
        }

        cmd = FactorLatestCommand(self.mock_client)
        result = cmd.execute(symbol='000001.SZ')

        assert result.success
        assert 'pe' in result.data['factors']

    def test_factor_calculate_success(self):
        """测试因子计算成功"""
        self.mock_client.request.return_value = {
            'symbol': '000001.SZ',
            'factors': ['pe', 'pb'],
            'results': {
                'pe': 10.5,
                'pb': 1.2
            }
        }

        cmd = FactorCalculateCommand(self.mock_client)
        result = cmd.execute(symbol='000001.SZ', factors=['pe', 'pb'])

        assert result.success
        assert len(result.data['factors']) == 2


class TestSignalCommands:
    """测试信号命令"""

    def setup_method(self):
        """设置测试"""
        self.mock_client = Mock()

    def test_signal_latest_success(self):
        """测试最新信号成功"""
        self.mock_client.request.return_value = {
            'count': 5,
            'signals': [
                {'symbol': '000001.SZ', 'type': 'buy', 'score': 0.8},
                {'symbol': '000002.SZ', 'type': 'sell', 'score': 0.7}
            ]
        }

        cmd = SignalLatestCommand(self.mock_client)
        result = cmd.execute(limit=10)

        assert result.success
        assert result.data['count'] == 5

    def test_signal_stats_success(self):
        """测试信号统计成功"""
        self.mock_client.request.return_value = {
            'total': 100,
            'buy_count': 60,
            'sell_count': 40,
            'avg_score': 0.75
        }

        cmd = SignalStatsCommand(self.mock_client)
        result = cmd.execute(start='2024-01-01', end='2024-01-31')

        assert result.success
        assert result.data['total'] == 100


class TestHTTPClient:
    """测试HTTP客户端"""

    def test_http_client_retry(self):
        """测试HTTP客户端重试机制"""
        from adapters.inbound.cli.http_client import HTTPClient
        import requests

        client = HTTPClient(max_retries=2, retry_delay=0.1)

        # Mock session
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'error': 'Server Error'}

        client.session.request = Mock(return_value=mock_response)

        result = client.get('/api/test')

        # 应该重试2次
        assert client.session.request.call_count == 2
        assert 'error' in result


class TestCommandRegistry:
    """测试命令注册表"""

    def test_registry_register_and_get(self):
        """测试注册和获取命令"""
        from adapters.inbound.cli.command_registry import CommandRegistry

        registry = CommandRegistry()
        mock_client = Mock()

        cmd = StockSearchCommand(mock_client)
        registry.register(cmd)

        retrieved = registry.get('stock.search')
        assert retrieved is not None
        assert retrieved.name == 'stock.search'

    def test_registry_list_by_domain(self):
        """测试按域列出命令"""
        from adapters.inbound.cli.command_registry import CommandRegistry

        registry = CommandRegistry()
        mock_client = Mock()

        registry.register(StockSearchCommand(mock_client))
        registry.register(StockInfoCommand(mock_client))
        registry.register(MarketOverviewCommand(mock_client))

        stock_commands = registry.list_by_domain('stock')
        assert len(stock_commands) == 2

        market_commands = registry.list_by_domain('market')
        assert len(market_commands) == 1

    def test_registry_count(self):
        """测试命令计数"""
        from adapters.inbound.cli.command_registry import CommandRegistry

        registry = CommandRegistry()
        mock_client = Mock()

        assert registry.count() == 0

        registry.register(StockSearchCommand(mock_client))
        registry.register(StockInfoCommand(mock_client))

        assert registry.count() == 2

    def test_indicator_commands_registered(self):
        """测试指标命令已注册"""
        from adapters.inbound.cli.command_registry import auto_discover_commands

        mock_client = Mock()
        registry = auto_discover_commands(mock_client)

        # 验证5个指标命令已注册
        assert registry.exists('indicators.list')
        assert registry.exists('indicators.create')
        assert registry.exists('indicators.update')
        assert registry.exists('indicators.run')
        assert registry.exists('indicators.backtest')

        # 验证indicators域有5个命令
        indicator_commands = registry.list_by_domain('indicators')
        assert len(indicator_commands) == 5


class TestFormatters:
    """测试格式化器"""

    def test_json_formatter(self):
        """测试JSON格式化器"""
        from adapters.inbound.cli.formatters import JSONFormatter

        formatter = JSONFormatter(pretty=True)
        data = {'name': '平安银行', 'price': 10.5}

        output = formatter.format(data)
        assert '平安银行' in output
        assert '10.5' in output

    def test_table_formatter(self):
        """测试表格格式化器"""
        from adapters.inbound.cli.formatters import TableFormatter

        formatter = TableFormatter()
        data = [
            {'symbol': '000001.SZ', 'name': '平安银行', 'price': 10.5},
            {'symbol': '000002.SZ', 'name': '万科A', 'price': 8.3}
        ]

        output = formatter.format(data)
        assert 'symbol' in output
        assert '平安银行' in output
        assert '10.5' in output

    def test_compact_formatter(self):
        """测试简洁格式化器"""
        from adapters.inbound.cli.formatters import CompactFormatter

        formatter = CompactFormatter()
        data = {'name': '平安银行', 'price': 10.5, 'change': 0.5}

        output = formatter.format(data)
        assert 'name: 平安银行' in output
        assert 'price: 10.5' in output
