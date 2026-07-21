"""
测试 core.response_utils 模块
"""
import pytest
import pandas as pd
from flask import Flask
from adapters.inbound.api.utils.response import normalize_indicator_fields
from adapters.inbound.api.routes import indicators as indicators_routes
from application.services.strategy_code_service import StrategyCodeService
from domain.quantlib.engine.indicator_strategy_executor import IndicatorStrategyResult


class TestNormalizeIndicatorFields:
    """测试 normalize_indicator_fields 函数"""

    def test_empty_list(self):
        """测试空列表"""
        result = normalize_indicator_fields([])
        assert result == []

    def test_already_has_name_field(self):
        """测试已有 name 字段的情况"""
        indicators = [
            {'id': 1, 'name': 'Test Indicator', 'strategy_name': 'Old Name'}
        ]
        result = normalize_indicator_fields(indicators)

        # name 字段应该保持不变
        assert result[0]['name'] == 'Test Indicator'
        assert result[0]['strategy_name'] == 'Old Name'

    def test_only_strategy_name_field(self):
        """测试只有 strategy_name 字段的情况"""
        indicators = [
            {'id': 1, 'strategy_name': 'My Strategy', 'description': 'Test'}
        ]
        result = normalize_indicator_fields(indicators)

        # 应该添加 name 字段
        assert result[0]['name'] == 'My Strategy'
        assert result[0]['strategy_name'] == 'My Strategy'

    def test_missing_both_fields(self):
        """测试两个字段都缺失的情况"""
        indicators = [
            {'id': 1, 'description': 'Test'}
        ]
        result = normalize_indicator_fields(indicators)

        # 不应该添加 name 字段
        assert 'name' not in result[0]
        assert 'strategy_name' not in result[0]

    def test_multiple_indicators(self):
        """测试多个指标的情况"""
        indicators = [
            {'id': 1, 'strategy_name': 'Strategy 1'},
            {'id': 2, 'name': 'Strategy 2', 'strategy_name': 'Old 2'},
            {'id': 3, 'strategy_name': 'Strategy 3'},
            {'id': 4, 'description': 'No name'}
        ]
        result = normalize_indicator_fields(indicators)

        assert len(result) == 4
        assert result[0]['name'] == 'Strategy 1'
        assert result[1]['name'] == 'Strategy 2'
        assert result[2]['name'] == 'Strategy 3'
        assert 'name' not in result[3]

    def test_preserves_other_fields(self):
        """测试保留其他字段"""
        indicators = [
            {
                'id': 1,
                'strategy_name': 'Test',
                'description': 'Description',
                'category': 'trend',
                'author': 'user1',
                'code_type': 'indicator'
            }
        ]
        result = normalize_indicator_fields(indicators)

        assert result[0]['id'] == 1
        assert result[0]['name'] == 'Test'
        assert result[0]['description'] == 'Description'
        assert result[0]['category'] == 'trend'
        assert result[0]['author'] == 'user1'
        assert result[0]['code_type'] == 'indicator'

    def test_maps_metadata_notebook_to_notebook_field(self):
        """metadata.notebook 应该作为独立字段返回给前端"""
        indicators = [
            {
                'id': 1,
                'strategy_name': 'Notebook Strategy',
                'metadata': {
                    'notebook': {
                        'pros': '趋势明确',
                        'cons': '震荡亏损',
                        'observations': '青岛啤酒有效',
                        'nextSteps': '加入成交量过滤',
                    },
                    'source': 'validator'
                }
            }
        ]

        result = normalize_indicator_fields(indicators)

        assert result[0]['notebook'] == {
            'pros': '趋势明确',
            'cons': '震荡亏损',
            'observations': '青岛啤酒有效',
            'nextSteps': '加入成交量过滤',
        }
        assert result[0]['metadata']['source'] == 'validator'

    def test_none_input(self):
        """测试 None 输入"""
        with pytest.raises(TypeError):
            normalize_indicator_fields(None)

    def test_non_list_input(self):
        """测试非列表输入"""
        try:
            result = normalize_indicator_fields({'id': 1, 'name': 'Test'})
            assert result is not None
        except (TypeError, Exception):
            pass

    def test_empty_strategy_name(self):
        """测试空字符串 strategy_name"""
        indicators = [
            {'id': 1, 'strategy_name': ''}
        ]
        result = normalize_indicator_fields(indicators)

        # 空字符串也应该被映射
        assert result[0]['name'] == ''

    def test_special_characters_in_name(self):
        """测试名称中的特殊字符"""
        indicators = [
            {'id': 1, 'strategy_name': 'MA(5,20) 双均线策略'},
            {'id': 2, 'strategy_name': 'RSI<30 超卖信号'}
        ]
        result = normalize_indicator_fields(indicators)

        assert result[0]['name'] == 'MA(5,20) 双均线策略'
        assert result[1]['name'] == 'RSI<30 超卖信号'

    def test_immutability(self):
        """测试不修改原始列表"""
        original = [
            {'id': 1, 'strategy_name': 'Test'}
        ]
        original_copy = [dict(item) for item in original]

        result = normalize_indicator_fields(original)

        # 原始列表应该被修改（函数设计为就地修改）
        assert original[0]['name'] == 'Test'
        assert result is original  # 返回的是同一个列表对象


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


class TestStrategyNotebookUpdate:
    """测试策略记事本后端保存逻辑"""

    def test_update_strategy_saves_notebook_in_metadata(self, mocker):
        service = StrategyCodeService()
        service.strategy_repo = mocker.Mock()
        service.strategy_repo.get_by_id.return_value = {
            'id': 7,
            'code_type': 'indicator',
            'metadata': {'source': 'validator'}
        }
        service.strategy_repo.update.return_value = {
            'id': 7,
            'metadata': {
                'source': 'validator',
                'notebook': {
                    'pros': '趋势明确',
                    'cons': '震荡亏损',
                    'observations': '青岛啤酒有效',
                    'nextSteps': '加入成交量过滤',
                }
            }
        }

        notebook = {
            'pros': '趋势明确',
            'cons': '震荡亏损',
            'observations': '青岛啤酒有效',
            'nextSteps': '加入成交量过滤',
        }

        service.update_strategy(strategy_id=7, notebook=notebook)

        service.strategy_repo.update.assert_called_once_with(
            7,
            {
                'metadata': {
                    'source': 'validator',
                    'notebook': notebook,
                }
            }
        )

    def test_update_strategy_normalizes_snake_case_notebook_fields(self, mocker):
        service = StrategyCodeService()
        service.strategy_repo = mocker.Mock()
        service.strategy_repo.get_by_id.return_value = {
            'id': 7,
            'code_type': 'indicator',
            'metadata': {}
        }
        service.strategy_repo.update.return_value = {'id': 7}

        service.update_strategy(
            strategy_id=7,
            notebook={
                'pros': '趋势明确',
                'cons': '震荡亏损',
                'observations': '青岛啤酒有效',
                'next_steps': '加入成交量过滤',
            }
        )

        service.strategy_repo.update.assert_called_once_with(
            7,
            {
                'metadata': {
                    'notebook': {
                        'pros': '趋势明确',
                        'cons': '震荡亏损',
                        'observations': '青岛啤酒有效',
                        'nextSteps': '加入成交量过滤',
                    }
                }
            }
        )

    def test_update_strategy_preserves_notebook_when_code_changes(self, mocker):
        service = StrategyCodeService()
        service.strategy_repo = mocker.Mock()
        service.strategy_repo.get_by_id.return_value = {
            'id': 7,
            'code_type': 'indicator',
            'metadata': {
                'notebook': {
                    'pros': '趋势明确',
                    'cons': '震荡亏损',
                    'observations': '青岛啤酒有效',
                    'nextSteps': '加入成交量过滤',
                },
                'source': 'manual'
            }
        }
        service.strategy_repo.update.return_value = {'id': 7}
        mocker.patch.object(service, 'validate_code', return_value={
            'valid': True,
            'params': [],
            'risk_config': {},
            'metadata': {'description': 'updated from code'}
        })

        service.update_strategy(strategy_id=7, code="df['buy'] = False")

        update_data = service.strategy_repo.update.call_args.args[1]
        assert update_data['metadata'] == {
            'notebook': {
                'pros': '趋势明确',
                'cons': '震荡亏损',
                'observations': '青岛啤酒有效',
                'nextSteps': '加入成交量过滤',
            },
            'source': 'manual',
            'description': 'updated from code',
        }


class TestIndicatorNotebookRoute:
    """测试指标路由透传策略记事本字段"""

    def test_update_indicator_passes_notebook_to_strategy_service(self, mocker):
        app = Flask(__name__)
        app.register_blueprint(indicators_routes.indicators_bp)
        app.config['TESTING'] = True

        mock_service = mocker.Mock()
        mock_service.get_strategy.return_value = {
            'id': 7,
            'code_type': 'indicator',
        }
        mock_service.update_strategy.return_value = {
            'id': 7,
            'metadata': {
                'notebook': {
                    'pros': '趋势明确',
                    'cons': '震荡亏损',
                    'observations': '青岛啤酒有效',
                    'nextSteps': '加入成交量过滤',
                }
            }
        }
        mocker.patch.object(indicators_routes, 'strategy_service', mock_service)

        with app.test_client() as client:
            response = client.post('/api/indicators/update/7', json={
                'notebook': {
                    'pros': '趋势明确',
                    'cons': '震荡亏损',
                    'observations': '青岛啤酒有效',
                    'nextSteps': '加入成交量过滤',
                }
            })

        assert response.status_code == 200
        kwargs = mock_service.update_strategy.call_args.kwargs
        assert kwargs['strategy_id'] == 7
        assert kwargs['notebook'] == {
            'pros': '趋势明确',
            'cons': '震荡亏损',
            'observations': '青岛啤酒有效',
            'next_steps': '加入成交量过滤',
        }


class TestStrategyRunSignalSeries:
    """测试指标运行结果返回历史买卖信号序列"""

    def test_run_strategy_returns_signal_series_for_chart_markers(self, mocker):
        service = StrategyCodeService()
        service.strategy_repo = mocker.Mock()
        service.strategy_repo.get_by_id.return_value = {
            'id': 7,
            'code_type': 'indicator',
            'code_content': "df['buy'] = False\ndf['sell'] = False",
            'parsed_params': {}
        }
        mocker.patch.object(service, 'validate_code', return_value={'valid': True})
        mocker.patch.object(service, '_get_klines', return_value=[
            {'trade_date': '2026-05-20', 'open': 10, 'high': 11, 'low': 9, 'close': 10.5, 'volume': 1000},
            {'trade_date': '2026-05-21', 'open': 10.5, 'high': 12, 'low': 10, 'close': 11.5, 'volume': 1200},
            {'trade_date': '2026-05-22', 'open': 11.5, 'high': 13, 'low': 11, 'close': 12.5, 'volume': 1400},
        ])
        mocker.patch.object(service, '_inject_fund_flow', side_effect=lambda klines, _symbol: klines)
        mocker.patch.object(service, '_inject_financial', side_effect=lambda klines, _symbol: klines)
        mocker.patch.object(service, '_inject_technical_indicators', side_effect=lambda klines: klines)
        service.indicator_executor = mocker.Mock()
        service.indicator_executor.execute.return_value = IndicatorStrategyResult(
            signals=pd.DataFrame({
                'trade_date': ['2026-05-20', '2026-05-21', '2026-05-22'],
                'open': [10, 10.5, 11.5],
                'high': [11, 12, 13],
                'low': [9, 10, 11],
                'close': [10.5, 11.5, 12.5],
                'volume': [1000, 1200, 1400],
                'ma_short': [10.2, 11.2, 12.2],
                'buy': [True, False, False],
                'sell': [False, False, True],
            })
        )

        result = service.run_strategy(strategy_id=7, symbol='000001', limit=3, chart_limit=2)

        assert result['signal_series'] == {
            'buy': [False, False],
            'sell': [False, True],
        }
