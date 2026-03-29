"""技术特征计算"""
import pandas as pd


class TechnicalFeatures:
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # MA
        for p in [5, 10, 20, 60]:
            df[f'ma{p}'] = df['close'].rolling(p).mean()

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / loss))

        # MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # 布林带
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        # ATR
        df['tr'] = df[['high', 'low', 'close']].apply(
            lambda x: max(x['high'] - x['low'], abs(x['high'] - x['close']), abs(x['low'] - x['close'])), axis=1
        )
        df['atr'] = df['tr'].rolling(14).mean()

        # 变化率
        df['price_change'] = df['close'].pct_change()
        df['volume_change'] = df['volume'].pct_change()

        # 标签（降低阈值到 2%）
        df['label'] = (df['close'].shift(-5) / df['close'] - 1 > 0.02).astype(int)

        return df.dropna()
