"""技术特征计算"""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ('date', 'open', 'high', 'low', 'close', 'volume')
OPTIONAL_NUMERIC_COLUMNS = ('amount', 'turnover_rate')
INDICATOR_COLUMNS = (
    'ma5',
    'ma10',
    'ma20',
    'ma60',
    'rsi',
    'macd',
    'macd_signal',
    'macd_hist',
    'bb_middle',
    'bb_std',
    'bb_upper',
    'bb_lower',
    'bb_width',
    'tr',
    'atr',
    'price_change',
    'volume_change',
)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        missing = ', '.join(missing_columns)
        raise ValueError(f'Market data missing required columns: {missing}')

    cleaned = df.copy()
    cleaned['date'] = pd.to_datetime(cleaned['date'], errors='coerce')

    numeric_columns = [column for column in (*REQUIRED_COLUMNS[1:], *OPTIONAL_NUMERIC_COLUMNS) if column in cleaned.columns]
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors='coerce')

    cleaned = cleaned.replace([np.inf, -np.inf], np.nan)
    cleaned = cleaned.sort_values('date').drop_duplicates(subset=['date'], keep='last').reset_index(drop=True)

    price_columns = ['open', 'high', 'low', 'close']
    cleaned[price_columns] = cleaned[price_columns].interpolate(limit_direction='both').ffill().bfill()

    for column in ['volume', 'amount', 'turnover_rate']:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].interpolate(limit_direction='both').ffill().bfill()

    if 'amount' not in cleaned.columns:
        cleaned['amount'] = cleaned['close'] * cleaned['volume']
    if 'turnover_rate' not in cleaned.columns:
        cleaned['turnover_rate'] = 0.0

    cleaned['high'] = cleaned[['high', 'open', 'close']].max(axis=1)
    cleaned['low'] = cleaned[['low', 'open', 'close']].min(axis=1)

    required_output_columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover_rate']
    if cleaned[required_output_columns].isna().any().any():
        raise ValueError('Market data contains invalid values after cleaning')

    return cleaned


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    featured = df.copy()

    for period in [5, 10, 20, 60]:
        featured[f'ma{period}'] = featured['close'].rolling(period).mean()

    delta = featured['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14, min_periods=14).mean()
    avg_loss = loss.rolling(14, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    featured['rsi'] = 100 - (100 / (1 + rs))
    featured.loc[avg_loss == 0, 'rsi'] = 100.0
    featured.loc[(avg_gain == 0) & (avg_loss == 0), 'rsi'] = 50.0

    ema12 = featured['close'].ewm(span=12, adjust=False).mean()
    ema26 = featured['close'].ewm(span=26, adjust=False).mean()
    featured['macd'] = ema12 - ema26
    featured['macd_signal'] = featured['macd'].ewm(span=9, adjust=False).mean()
    featured['macd_hist'] = featured['macd'] - featured['macd_signal']

    featured['bb_middle'] = featured['close'].rolling(20).mean()
    featured['bb_std'] = featured['close'].rolling(20).std()
    featured['bb_upper'] = featured['bb_middle'] + 2 * featured['bb_std']
    featured['bb_lower'] = featured['bb_middle'] - 2 * featured['bb_std']
    featured['bb_width'] = (featured['bb_upper'] - featured['bb_lower']) / featured['bb_middle'].replace(0, np.nan)

    previous_close = featured['close'].shift(1)
    true_range = pd.concat(
        [
            featured['high'] - featured['low'],
            (featured['high'] - previous_close).abs(),
            (featured['low'] - previous_close).abs(),
        ],
        axis=1,
    )
    featured['tr'] = true_range.max(axis=1)
    featured['atr'] = featured['tr'].rolling(14, min_periods=14).mean()

    featured['price_change'] = featured['close'].pct_change()
    featured['volume_change'] = featured['volume'].pct_change()
    featured = featured.replace([np.inf, -np.inf], np.nan)

    return featured


def generate_labels(df: pd.DataFrame, lookahead_days: int = 5, threshold: float = 0.02) -> pd.DataFrame:
    labeled = df.copy()
    future_return = labeled['close'].shift(-lookahead_days) / labeled['close'] - 1
    labeled['label'] = (future_return > threshold).astype(int)

    if lookahead_days > 0:
        labeled = labeled.iloc[:-lookahead_days].copy()

    return labeled


class TechnicalFeatures:
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        cleaned = clean_data(df)
        featured = calculate_indicators(cleaned)
        labeled = generate_labels(featured)
        labeled = labeled.replace([np.inf, -np.inf], np.nan)
        return labeled.dropna().reset_index(drop=True)
