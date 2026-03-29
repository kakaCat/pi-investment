import unittest
from io import StringIO
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
from ml_pipeline import main


class TestCLI(unittest.TestCase):
    @patch('ml_pipeline.SignalTrainer', create=True)
    @patch('ml_pipeline.TechnicalFeatures', create=True)
    @patch('ml_pipeline.Database', create=True)
    def test_train_command(self, mock_database_cls, mock_features_cls, mock_trainer_cls):
        stock_symbols = [f'{i:06d}' for i in range(10)]
        raw_df = pd.DataFrame(
            {
                'close': [10, 11, 12],
                'volume': [100, 110, 120],
            }
        )
        feature_df = pd.DataFrame(
            {
                'ma5': [10.5, 11.5],
                'rsi': [55.0, 60.0],
                'label': [0, 1],
            }
        )

        mock_db = MagicMock()
        mock_db.get_all_symbols.return_value = stock_symbols
        mock_db.get_klines.return_value = raw_df
        mock_database_cls.return_value = mock_db

        mock_features_cls.calculate_all.return_value = feature_df

        mock_trainer = MagicMock()
        mock_trainer.train.return_value = {
            'train_score': 0.9,
            'test_score': 0.8,
            'n_samples': 20,
        }
        mock_trainer.save.return_value = 'ml-pipeline/models/signal_model.pkl'
        mock_trainer_cls.return_value = mock_trainer

        stdout = StringIO()
        with patch('sys.stdout', stdout):
            result = main(['train', '--model', 'signal'])

        self.assertEqual(result, 0)
        mock_db.get_all_symbols.assert_called_once_with()
        self.assertEqual(mock_db.get_klines.call_count, 10)
        mock_db.get_klines.assert_any_call(stock_symbols[0], 500)
        mock_features_cls.calculate_all.assert_called()
        train_args, _ = mock_trainer.train.call_args
        X, y = train_args
        self.assertEqual(list(X.columns), ['ma5', 'rsi'])
        self.assertEqual(len(X), 20)
        self.assertEqual(y.tolist(), [0, 1] * 10)
        mock_trainer.save.assert_called_once_with('signal_model.pkl')
        self.assertIn('train_score', stdout.getvalue())

    @patch('ml_pipeline.SignalTrainer', create=True)
    @patch('ml_pipeline.TechnicalFeatures', create=True)
    @patch('ml_pipeline.Database', create=True)
    def test_train_command_returns_1_when_no_data(self, mock_database_cls, mock_features_cls, mock_trainer_cls):
        mock_db = MagicMock()
        mock_db.get_all_symbols.return_value = []
        mock_database_cls.return_value = mock_db

        stderr = StringIO()
        with patch('sys.stderr', stderr):
            result = main(['train'])

        self.assertEqual(result, 1)
        mock_db.get_klines.assert_not_called()
        mock_features_cls.calculate_all.assert_not_called()
        mock_trainer_cls.assert_not_called()
        self.assertIn('没有可用于训练的数据', stderr.getvalue())

    @patch('ml_pipeline.SignalPredictor', create=True)
    @patch('ml_pipeline.TechnicalFeatures', create=True)
    @patch('ml_pipeline.Database', create=True)
    def test_predict_command(self, mock_database_cls, mock_features_cls, mock_predictor_cls):
        raw_df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
                'close': [10, 11, 12],
                'volume': [100, 110, 120],
            }
        )
        feature_df = pd.DataFrame(
            {
                'date': ['2024-01-03'],
                'symbol': ['600519'],
                'close': [12.0],
                'ma5': [11.0],
                'rsi': [65.0],
                'label': [1],
            }
        )

        mock_db = MagicMock()
        mock_db.get_klines.return_value = raw_df
        mock_database_cls.return_value = mock_db
        mock_features_cls.calculate_all.return_value = feature_df

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = np.array([0.75])
        mock_predictor_cls.return_value = mock_predictor

        stdout = StringIO()
        with patch('sys.stdout', stdout):
            result = main(['predict', '--symbol', '600519'])

        self.assertEqual(result, 0)
        mock_db.get_klines.assert_called_once_with('600519', 500)
        predict_args, _ = mock_predictor.predict.call_args
        X = predict_args[0]
        self.assertEqual(list(X.columns), ['close', 'ma5', 'rsi'])
        self.assertEqual(len(X), 1)
        self.assertIn('上涨概率: 75.00%', stdout.getvalue())
        self.assertIn('信号: 买入', stdout.getvalue())

    @patch('ml_pipeline.Path.exists', autospec=True, return_value=True)
    @patch('ml_pipeline.SignalPredictor', create=True)
    @patch('ml_pipeline.SignalTrainer', create=True)
    @patch('ml_pipeline.TechnicalFeatures', create=True)
    @patch('ml_pipeline.Database', create=True)
    def test_evaluate_command(
        self,
        mock_database_cls,
        mock_features_cls,
        mock_trainer_cls,
        mock_predictor_cls,
        mock_path_exists,
    ):
        stock_symbols = [f'{i:06d}' for i in range(20)]
        raw_df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
                'close': [10, 11, 12],
                'volume': [100, 110, 120],
            }
        )
        feature_df = pd.DataFrame(
            {
                'date': ['2024-01-02', '2024-01-03'],
                'symbol': ['000010', '000010'],
                'close': [11.0, 12.0],
                'ma5': [10.5, 11.0],
                'rsi': [55.0, 45.0],
                'label': [1, 0],
            }
        )

        mock_db = MagicMock()
        mock_db.get_all_symbols.return_value = stock_symbols
        mock_db.get_klines.return_value = raw_df
        mock_database_cls.return_value = mock_db
        mock_features_cls.calculate_all.return_value = feature_df

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = np.array([0.8, 0.3] * 5)
        mock_predictor_cls.return_value = mock_predictor

        stdout = StringIO()
        with patch('sys.stdout', stdout):
            result = main(['evaluate'])

        self.assertEqual(result, 0)
        mock_db.get_all_symbols.assert_called_once_with()
        self.assertEqual(
            [call.args[0] for call in mock_db.get_klines.call_args_list],
            stock_symbols[10:15],
        )
        predict_args, _ = mock_predictor.predict.call_args
        X = predict_args[0]
        self.assertEqual(list(X.columns), ['close', 'ma5', 'rsi'])
        self.assertEqual(len(X), 10)
        self.assertIn('准确率 (Accuracy): 100.00%', stdout.getvalue())
        self.assertIn('精确率 (Precision): 100.00%', stdout.getvalue())
        self.assertIn('召回率 (Recall): 100.00%', stdout.getvalue())
        self.assertIn('F1分数: 100.00%', stdout.getvalue())
        self.assertIn('测试样本数: 10', stdout.getvalue())

    def test_list_models_command(self):
        result = main(['list-models'])
        self.assertEqual(result, 0)

    @patch('ml_pipeline.BacktestEngine', create=True)
    @patch('ml_pipeline.SignalPredictor', create=True)
    @patch('ml_pipeline.TechnicalFeatures', create=True)
    @patch('ml_pipeline.Database', create=True)
    def test_backtest_command(self, mock_database_cls, mock_features_cls, mock_predictor_cls, mock_engine_cls):
        stock_symbols = [f'{i:06d}' for i in range(10)]
        feature_df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02'],
                'close': [10.0, 11.0],
                'symbol': ['000001', '000001'],
                'ma5': [9.5, 10.5],
                'rsi': [55.0, 65.0],
                'label': [0, 1],
            }
        )

        mock_db = MagicMock()
        mock_db.get_all_symbols.return_value = stock_symbols
        mock_db.get_klines.return_value = feature_df[['date', 'close']].assign(volume=[100, 110])
        mock_database_cls.return_value = mock_db
        mock_features_cls.calculate_all.return_value = feature_df

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = np.array([0.4, 0.8])
        mock_predictor_cls.return_value = mock_predictor

        mock_engine = MagicMock()
        mock_engine.run.return_value = {
            'initial_capital': 100000,
            'final_value': 105000,
            'return': 5.0,
            'trades': 2,
            'win_rate': 50.0,
            'max_drawdown': 10.0,
            'sharpe_ratio': 1.2,
        }
        mock_engine_cls.return_value = mock_engine

        stdout = StringIO()
        with patch('sys.stdout', stdout):
            result = main(['backtest'])

        self.assertEqual(result, 0)
        mock_db.get_all_symbols.assert_called_once_with()
        self.assertEqual(mock_db.get_klines.call_count, 5)
        self.assertEqual(mock_predictor.predict.call_count, 5)
        self.assertEqual(mock_engine.run.call_count, 5)
        self.assertIn('[Backtest] 回测结果', stdout.getvalue())
        self.assertIn(
            '000000: 收益率 5.00%, 交易次数 2, 胜率 50.00%, 最大回撤 10.00%, 夏普比率 1.20',
            stdout.getvalue(),
        )
