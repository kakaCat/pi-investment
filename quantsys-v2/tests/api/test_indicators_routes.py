"""
Tests for backtest summary calculation function.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
import sys
from pathlib import Path
from adapters.inbound.api.routes.indicators import calculate_backtest_summary

# Add quantsys-v2 to path
v2_root = Path(__file__).resolve().parents[2]
if str(v2_root) not in sys.path:
    sys.path.insert(0, str(v2_root))


@pytest.fixture
def client():
    """创建Flask测试客户端"""
    from adapters.inbound.api.server import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestCalculateBacktestSummary:
    """测试回测摘要计算函数"""

    def test_calculate_backtest_summary_empty(self):
        """测试空数据 - 规格要求的测试名称"""
        result = calculate_backtest_summary([], [], datetime.now(), datetime.now())
        assert result == {}

    def test_calculate_backtest_summary(self):
        """测试正常计算 - 规格要求的测试名称（综合测试）"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-03-01', 'equity': 1050000},
            {'date': '2024-06-01', 'equity': 1030000},
            {'date': '2024-09-01', 'equity': 1080000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        trades = [
            {'date': '2024-03-01', 'action': 'sell', 'pnl': 50000},
            {'date': '2024-06-01', 'action': 'sell', 'pnl': -20000},
            {'date': '2024-09-01', 'action': 'sell', 'pnl': 50000},
            {'date': '2024-12-31', 'action': 'sell', 'pnl': 20000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        # 验证所有 11 个指标都存在
        assert 'total_return' in result
        assert 'annual_return' in result
        assert 'max_drawdown' in result
        assert 'sharpe_ratio' in result
        assert 'win_rate' in result
        assert 'total_trades' in result
        assert 'winning_trades' in result
        assert 'losing_trades' in result
        assert 'avg_win' in result
        assert 'avg_loss' in result
        assert 'profit_factor' in result

        # 验证关键指标值
        assert result['total_return'] == 0.1
        assert result['total_trades'] == 4
        assert result['winning_trades'] == 3
        assert result['losing_trades'] == 1
        assert result['win_rate'] == 0.75
        assert result['avg_win'] == 40000
        assert result['avg_loss'] == -20000
        assert result['profit_factor'] == 6.0

    def test_single_trade_profit(self):
        """单笔盈利交易"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        trades = [
            {'date': '2024-06-01', 'action': 'sell', 'pnl': 100000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        assert result['total_return'] == 0.1
        assert result['total_trades'] == 1
        assert result['winning_trades'] == 1
        assert result['losing_trades'] == 0
        assert result['win_rate'] == 1.0
        assert result['avg_win'] == 100000
        assert result['avg_loss'] == 0

    def test_multiple_trades_mixed(self):
        """多笔交易混合盈亏"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-03-01', 'equity': 1050000},
            {'date': '2024-06-01', 'equity': 1030000},
            {'date': '2024-09-01', 'equity': 1080000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        trades = [
            {'date': '2024-03-01', 'action': 'sell', 'pnl': 50000},
            {'date': '2024-06-01', 'action': 'sell', 'pnl': -20000},
            {'date': '2024-09-01', 'action': 'sell', 'pnl': 50000},
            {'date': '2024-12-31', 'action': 'sell', 'pnl': 20000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        assert result['total_return'] == 0.1
        assert result['total_trades'] == 4
        assert result['winning_trades'] == 3
        assert result['losing_trades'] == 1
        assert result['win_rate'] == 0.75
        assert result['avg_win'] == 40000
        assert result['avg_loss'] == -20000
        assert result['profit_factor'] == 6.0

    def test_max_drawdown_calculation(self):
        """最大回撤计算"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-03-01', 'equity': 1200000},  # 峰值
            {'date': '2024-06-01', 'equity': 900000},   # 回撤 25%
            {'date': '2024-09-01', 'equity': 1100000},
            {'date': '2024-12-31', 'equity': 1150000}
        ]

        trades = [
            {'date': '2024-06-01', 'action': 'sell', 'pnl': -300000},
            {'date': '2024-09-01', 'action': 'sell', 'pnl': 200000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        assert result['max_drawdown'] == -0.25

    def test_sharpe_ratio_calculation(self):
        """夏普比率计算"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        # 稳定增长的权益曲线
        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-03-01', 'equity': 1025000},
            {'date': '2024-06-01', 'equity': 1050000},
            {'date': '2024-09-01', 'equity': 1075000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        trades = [
            {'date': '2024-03-01', 'action': 'sell', 'pnl': 25000},
            {'date': '2024-06-01', 'action': 'sell', 'pnl': 25000},
            {'date': '2024-09-01', 'action': 'sell', 'pnl': 25000},
            {'date': '2024-12-31', 'action': 'sell', 'pnl': 25000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        # 夏普比率应该为正数（收益率 > 无风险利率）
        assert result['sharpe_ratio'] > 0


    def test_indicators_list_excludes_inactive_indicators(self, client):
        """指标列表不返回已停用/删除的指标"""
        with patch('api.routes.indicators.strategy_service') as mock_strategy_service:
            mock_strategy_service.list_strategies.return_value = [
                {
                    'id': 1,
                    'strategy_name': 'active indicator',
                    'code_type': 'indicator',
                    'strategy_type': 'custom',
                    'is_active': True,
                },
                {
                    'id': 2,
                    'strategy_name': 'inactive indicator',
                    'code_type': 'indicator',
                    'strategy_type': 'custom',
                    'is_active': False,
                },
            ]

            response = client.get('/api/indicators/list?type=my')

        assert response.status_code == 200
        data = response.get_json()
        items = data['data']['items']
        assert [item['id'] for item in items] == [1]

    def test_annual_return_calculation(self):
        """年化收益率计算"""
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2024, 12, 31)  # 3年

        equity_curve = [
            {'date': '2022-01-01', 'equity': 1000000},
            {'date': '2024-12-31', 'equity': 1331000}  # 约 10% 年化
        ]

        trades = [
            {'date': '2024-12-31', 'action': 'sell', 'pnl': 331000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        # 总收益率 33.1%，3年，年化约 10%
        assert 0.09 < result['annual_return'] < 0.11

    def test_no_losing_trades(self):
        """没有亏损交易"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-12-31', 'equity': 1200000}
        ]

        trades = [
            {'date': '2024-06-01', 'action': 'sell', 'pnl': 100000},
            {'date': '2024-12-31', 'action': 'sell', 'pnl': 100000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        assert result['losing_trades'] == 0
        assert result['avg_loss'] == 0
        assert result['profit_factor'] == float('inf')

    def test_all_losing_trades(self):
        """全部亏损交易"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-12-31', 'equity': 800000}
        ]

        trades = [
            {'date': '2024-06-01', 'action': 'sell', 'pnl': -100000},
            {'date': '2024-12-31', 'action': 'sell', 'pnl': -100000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        assert result['winning_trades'] == 0
        assert result['avg_win'] == 0
        assert result['profit_factor'] == 0

    def test_no_trades_but_has_equity_curve(self):
        """修复问题3：没有交易但有权益曲线，应该返回权益相关指标"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-06-01', 'equity': 1050000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        result = calculate_backtest_summary(equity_curve, [], start_date, end_date)

        # 应该返回权益相关指标
        assert result != {}
        assert result['total_return'] == 0.1
        assert result['total_trades'] == 0
        assert result['winning_trades'] == 0
        assert result['losing_trades'] == 0
        assert result['win_rate'] == 0
        assert result['avg_win'] == 0
        assert result['avg_loss'] == 0
        assert result['profit_factor'] == 0

    def test_zero_initial_equity(self):
        """修复问题2：初始权益为0，应该返回空字典"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 0},
            {'date': '2024-12-31', 'equity': 100000}
        ]

        trades = [
            {'date': '2024-06-01', 'action': 'sell', 'pnl': 100000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)
        assert result == {}

    def test_negative_initial_equity(self):
        """修复问题2：初始权益为负数，应该返回空字典"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': -1000},
            {'date': '2024-12-31', 'equity': 100000}
        ]

        trades = []

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)
        assert result == {}


class TestBacktestIndicatorEndpoint:
    """测试回测指标端点"""

    def test_backtest_indicator_includes_summary(self, client, mocker):
        """测试回测端点返回包含摘要"""
        # Mock strategy service
        mock_strategy_service = mocker.patch('api.routes.indicators.strategy_service')
        mock_strategy_service.get_strategy.return_value = {
            'id': 1,
            'name': '测试指标',
            'code_type': 'indicator'
        }

        mock_strategy_service.backtest_strategy.return_value = {
            'equity_curve': [
                {'date': '2024-01-01', 'equity': 1000000},
                {'date': '2024-01-02', 'equity': 1020000},
            ],
            'trades': [
                {'date': '2024-01-02', 'action': 'buy', 'pnl': 2000}
            ]
        }

        response = client.post('/api/indicators/backtest', json={
            'indicatorId': 1,
            'symbol': '000001.SH',
            'startDate': '2024-01-01',
            'endDate': '2024-01-02'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success']
        assert 'summary' in data['data']
        # Keys are converted to camelCase by api_response
        assert 'totalReturn' in data['data']['summary']
        assert 'annualReturn' in data['data']['summary']
        assert 'maxDrawdown' in data['data']['summary']
        assert 'sharpeRatio' in data['data']['summary']
        assert 'winRate' in data['data']['summary']
        assert 'totalTrades' in data['data']['summary']


class TestRunIndicatorEndpoint:
    """测试运行指标端点"""

    def test_run_indicator_passes_period_and_chart_limit_to_strategy_service(self, client, mocker):
        """实时预览应该允许前端指定周期和图表返回数量"""
        mock_strategy_service = mocker.patch('api.routes.indicators.strategy_service')
        mock_strategy_service.get_strategy.return_value = {
            'id': 1,
            'name': '测试指标',
            'code_type': 'indicator'
        }
        mock_strategy_service.run_strategy.return_value = {
            'symbol': '000001.SH',
            'latest_signal': 'hold',
            'price': 100,
            'date': '2026-05-27',
            'kline_data': []
        }

        response = client.post('/api/indicators/run/1', json={
            'symbol': '000001.SH',
            'limit': 260,
            'chartLimit': 260,
            'period': '30min'
        })

        assert response.status_code == 200
        mock_strategy_service.run_strategy.assert_called_once_with(
            strategy_id=1,
            symbol='000001.SH',
            limit=260,
            chart_limit=260,
            period='30min'
        )

    def test_backtest_indicator_invalid_date_format(self, client, mocker):
        """测试无效日期格式返回 400 错误"""
        # Mock strategy service
        mock_strategy_service = mocker.patch('api.routes.indicators.strategy_service')
        mock_strategy_service.get_strategy.return_value = {
            'id': 1,
            'name': '测试指标',
            'code_type': 'indicator'
        }

        # Test invalid month
        response = client.post('/api/indicators/backtest', json={
            'indicatorId': 1,
            'symbol': '000001.SH',
            'startDate': '2024-13-01',  # Invalid month
            'endDate': '2024-01-02'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert not data['success']
        assert '日期格式无效' in data['error']

    def test_backtest_indicator_invalid_date_string(self, client, mocker):
        """测试完全无效的日期字符串返回 400 错误"""
        # Mock strategy service
        mock_strategy_service = mocker.patch('api.routes.indicators.strategy_service')
        mock_strategy_service.get_strategy.return_value = {
            'id': 1,
            'name': '测试指标',
            'code_type': 'indicator'
        }

        # Test completely invalid date string
        response = client.post('/api/indicators/backtest', json={
            'indicatorId': 1,
            'symbol': '000001.SH',
            'startDate': 'invalid-date',
            'endDate': '2024-01-02'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert not data['success']
        assert '日期格式无效' in data['error']


class TestCompareIndicatorsEndpoint:
    """测试对比指标端点"""

    def test_compare_indicators_missing_params(self, client):
        """测试对比指标缺少参数"""
        response = client.post('/api/indicators/compare', json={
            'indicatorIdA': 1
        })
        assert response.status_code == 400
        data = response.get_json()
        assert not data['success']

    def test_compare_indicators_success(self, client, mocker):
        """测试对比指标成功"""
        # Mock strategy service
        mock_strategy_service = mocker.patch('api.routes.indicators.strategy_service')
        mock_strategy_service.get_strategy.side_effect = [
            {'id': 1, 'name': 'RSI v5', 'code_type': 'indicator'},
            {'id': 2, 'name': 'RSI v6', 'code_type': 'indicator'}
        ]

        mock_strategy_service.backtest_strategy.side_effect = [
            {
                'equity_curve': [
                    {'date': '2024-01-01', 'equity': 1000000},
                    {'date': '2024-01-02', 'equity': 980000},
                ],
                'trades': [
                    {'date': '2024-01-02', 'action': 'buy', 'pnl': -2000},
                    {'date': '2024-01-03', 'action': 'buy', 'pnl': 1000},
                ]
            },
            {
                'equity_curve': [
                    {'date': '2024-01-01', 'equity': 1000000},
                    {'date': '2024-01-02', 'equity': 985000},
                ],
                'trades': [
                    {'date': '2024-01-03', 'action': 'buy', 'pnl': 1000},
                ]
            }
        ]

        response = client.post('/api/indicators/compare', json={
            'indicatorIdA': 1,
            'indicatorIdB': 2,
            'symbol': '000001.SH',
            'startDate': '2024-01-01',
            'endDate': '2024-12-31'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success']
        assert 'comparison' in data['data']
        assert 'filteredByBOnly' in data['data']['comparison']  # camelCase
        assert data['data']['comparison']['filteredByBOnly'] == 1

    def test_compare_indicators_empty_equity(self, client, mocker):
        """测试空权益曲线不会导致除零错误"""
        mock_strategy_service = mocker.patch('api.routes.indicators.strategy_service')
        mock_strategy_service.get_strategy.side_effect = [
            {'id': 1, 'name': 'RSI v5', 'code_type': 'indicator'},
            {'id': 2, 'name': 'RSI v6', 'code_type': 'indicator'}
        ]

        mock_strategy_service.backtest_strategy.side_effect = [
            {
                'equity_curve': [],
                'trades': []
            },
            {
                'equity_curve': [{'date': '2024-01-01', 'equity': 1000000}],  # 单元素
                'trades': []
            }
        ]

        response = client.post('/api/indicators/compare', json={
            'indicatorIdA': 1,
            'indicatorIdB': 2,
            'symbol': '000001.SH',
            'startDate': '2024-01-01',
            'endDate': '2024-12-31'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success']
        assert data['data']['strategyA']['totalReturn'] == 0.0
        assert data['data']['strategyB']['totalReturn'] == 0.0

    def test_compare_indicators_zero_initial_equity(self, client, mocker):
        """测试初始权益为0不会导致除零错误"""
        mock_strategy_service = mocker.patch('api.routes.indicators.strategy_service')
        mock_strategy_service.get_strategy.side_effect = [
            {'id': 1, 'name': 'RSI v5', 'code_type': 'indicator'},
            {'id': 2, 'name': 'RSI v6', 'code_type': 'indicator'}
        ]

        mock_strategy_service.backtest_strategy.side_effect = [
            {
                'equity_curve': [
                    {'date': '2024-01-01', 'equity': 0},
                    {'date': '2024-01-02', 'equity': 100000}
                ],
                'trades': []
            },
            {
                'equity_curve': [
                    {'date': '2024-01-01', 'equity': 1000000},
                    {'date': '2024-01-02', 'equity': 1100000}
                ],
                'trades': []
            }
        ]

        response = client.post('/api/indicators/compare', json={
            'indicatorIdA': 1,
            'indicatorIdB': 2,
            'symbol': '000001.SH',
            'startDate': '2024-01-01',
            'endDate': '2024-12-31'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success']
        assert data['data']['strategyA']['totalReturn'] == 0.0
        assert data['data']['strategyB']['totalReturn'] == 0.1

    def test_compare_indicators_invalid_id_type(self, client, mocker):
        """测试无效的指标ID类型返回400错误"""
        mock_strategy_service = mocker.patch('api.routes.indicators.strategy_service')

        response = client.post('/api/indicators/compare', json={
            'indicatorIdA': 'not-a-number',
            'indicatorIdB': 2,
            'symbol': '000001.SH',
            'startDate': '2024-01-01',
            'endDate': '2024-12-31'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert not data['success']
        assert '指标ID必须为整数' in data['error']


class TestSandboxColumnsEndpoint:
    """测试沙箱列探查端点"""

    def test_sandbox_columns_missing_symbol(self, client):
        """测试沙箱列探查缺少symbol参数"""
        response = client.get('/api/indicators/sandbox-columns')
        assert response.status_code == 400
        data = response.get_json()
        assert not data['success']
        assert 'symbol' in data['error']

    def test_sandbox_columns_success(self, client, mocker):
        """测试沙箱列探查成功"""
        # Mock kline repository - patch where it's used (not where it's defined)
        mock_kline_repo_class = mocker.patch('api.routes.indicators.KlineRepository')
        mock_kline_repo_instance = mock_kline_repo_class.return_value
        mock_kline_repo_instance.get_klines.return_value = [
            {
                'trade_date': '2024-01-01',
                'close': 10.0,
                'roe_q': 15.0,
                'debt_ratio_q': 50.0,
                'rsi': 65.0,
                'atr': 0.5
            },
            {
                'trade_date': '2024-01-02',
                'close': 10.2,
                'roe_q': 15.5,
                'debt_ratio_q': None,
                'rsi': 68.0,
                'atr': 0.52
            }
        ]

        response = client.get('/api/indicators/sandbox-columns?symbol=000001.SH')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success']
        assert 'columns' in data['data']
        assert 'roeQ' in data['data']['columns']  # camelCase
        assert data['data']['columns']['roeQ']['coverage'] == 1.0
        assert data['data']['columns']['debtRatioQ']['coverage'] == 0.5

    def test_sandbox_columns_no_data(self, client, mocker):
        """测试股票无数据返回 404"""
        mock_kline_repo_class = mocker.patch('api.routes.indicators.KlineRepository')
        mock_kline_repo_instance = mock_kline_repo_class.return_value
        mock_kline_repo_instance.get_klines.return_value = []

        response = client.get('/api/indicators/sandbox-columns?symbol=999999.SH')
        assert response.status_code == 404
        data = response.get_json()
        assert not data['success']
        assert '无数据' in data['error']

    def test_sandbox_columns_all_null(self, client, mocker):
        """测试列值全为 None 的覆盖率为 0"""
        mock_kline_repo_class = mocker.patch('api.routes.indicators.KlineRepository')
        mock_kline_repo_instance = mock_kline_repo_class.return_value
        mock_kline_repo_instance.get_klines.return_value = [
            {'trade_date': '2024-01-01', 'close': 10.0, 'roe_q': None},
            {'trade_date': '2024-01-02', 'close': 10.2, 'roe_q': None}
        ]

        response = client.get('/api/indicators/sandbox-columns?symbol=000001.SH')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success']
        if 'roeQ' in data['data']['columns']:
            assert data['data']['columns']['roeQ']['coverage'] == 0.0
            assert data['data']['columns']['roeQ']['latestValue'] is None
