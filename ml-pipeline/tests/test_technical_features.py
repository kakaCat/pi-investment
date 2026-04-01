import unittest
from pathlib import Path

import pandas as pd

from features.technical import TechnicalFeatures, calculate_indicators, clean_data, generate_labels


FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures' / 'market_data'


class TestTechnicalFeatures(unittest.TestCase):
    def test_clean_data_sorts_rows_and_handles_nan_and_inf(self):
        raw = pd.DataFrame(
            {
                'symbol': ['600001', '600001', '600001'],
                'date': ['2024-01-03', '2024-01-01', '2024-01-02'],
                'open': [12.0, float('inf'), 11.0],
                'high': [12.5, 10.8, float('inf')],
                'low': [11.5, 9.8, 10.5],
                'close': [12.0, None, 11.0],
                'volume': [1200, 1000, None],
                'amount': [14400.0, float('inf'), 12100.0],
                'turnover_rate': [1.5, None, float('inf')],
            }
        )

        cleaned = clean_data(raw)
        numeric = cleaned.select_dtypes(include='number').replace([float('inf'), float('-inf')], pd.NA)

        self.assertEqual(cleaned['date'].dt.strftime('%Y-%m-%d').tolist(), ['2024-01-01', '2024-01-02', '2024-01-03'])
        self.assertFalse(numeric.isna().any().any())
        self.assertTrue((cleaned['high'] >= cleaned[['open', 'close']].max(axis=1)).all())
        self.assertTrue((cleaned['low'] <= cleaned[['open', 'close']].min(axis=1)).all())

    def test_calculate_indicators_adds_expected_columns(self):
        raw = pd.read_csv(FIXTURE_DIR / 'uptrend.csv')

        featured = calculate_indicators(clean_data(raw))

        for column in [
            'ma5',
            'ma10',
            'ma20',
            'ma60',
            'rsi',
            'macd',
            'macd_signal',
            'macd_hist',
            'bb_middle',
            'bb_upper',
            'bb_lower',
            'bb_width',
            'tr',
            'atr',
            'price_change',
            'volume_change',
        ]:
            self.assertIn(column, featured.columns)

    def test_generate_labels_uses_lookahead_window(self):
        df = pd.DataFrame(
            {
                'close': [100.0, 101.0, 102.0, 103.0, 104.0, 110.0, 111.0],
            }
        )

        labeled = generate_labels(df, lookahead_days=5, threshold=0.02)

        self.assertEqual(len(labeled), 2)
        self.assertEqual(labeled['label'].tolist(), [1, 1])

    def test_calculate_all_returns_finite_rows(self):
        raw = pd.read_csv(FIXTURE_DIR / 'sideways.csv')

        featured = TechnicalFeatures.calculate_all(raw)
        numeric = featured.select_dtypes(include='number').replace([float('inf'), float('-inf')], pd.NA)

        self.assertFalse(featured.empty)
        self.assertIn('label', featured.columns)
        self.assertFalse(numeric.isna().any().any())


if __name__ == '__main__':
    unittest.main()
