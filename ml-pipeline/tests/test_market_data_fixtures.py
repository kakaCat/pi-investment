import unittest
from pathlib import Path

import pandas as pd


FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures' / 'market_data'
EXPECTED_COLUMNS = [
    'symbol',
    'date',
    'open',
    'high',
    'low',
    'close',
    'volume',
    'amount',
    'turnover_rate',
]


class TestMarketDataFixtures(unittest.TestCase):
    def test_market_data_fixtures_exist_and_match_expected_shape(self):
        for file_name in ['uptrend.csv', 'downtrend.csv', 'sideways.csv']:
            fixture_path = FIXTURE_DIR / file_name
            self.assertTrue(fixture_path.exists(), f'missing fixture: {file_name}')

            df = pd.read_csv(fixture_path)

            self.assertEqual(df.columns.tolist(), EXPECTED_COLUMNS)
            self.assertEqual(len(df), 100)
            self.assertEqual(df['symbol'].nunique(), 1)
            self.assertTrue((pd.to_datetime(df['date']).sort_values().tolist() == pd.to_datetime(df['date']).tolist()))
            self.assertTrue((df['high'] >= df[['open', 'close']].max(axis=1)).all())
            self.assertTrue((df['low'] <= df[['open', 'close']].min(axis=1)).all())
            self.assertTrue((df['volume'] > 0).all())
            self.assertTrue((df['amount'] > 0).all())
            self.assertTrue((df['turnover_rate'] > 0).all())

    def test_market_data_fixtures_follow_named_trends(self):
        uptrend = pd.read_csv(FIXTURE_DIR / 'uptrend.csv')
        downtrend = pd.read_csv(FIXTURE_DIR / 'downtrend.csv')
        sideways = pd.read_csv(FIXTURE_DIR / 'sideways.csv')

        self.assertGreater(uptrend['close'].iloc[-1], uptrend['close'].iloc[0])
        self.assertLess(downtrend['close'].iloc[-1], downtrend['close'].iloc[0])
        self.assertLess(abs(sideways['close'].iloc[-1] / sideways['close'].iloc[0] - 1), 0.05)


if __name__ == '__main__':
    unittest.main()
