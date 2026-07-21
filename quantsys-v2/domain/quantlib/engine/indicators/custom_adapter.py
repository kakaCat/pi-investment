"""
自定义技术指标适配器

实现标准技术指标的正确计算，避免第三方库的bug
"""

from typing import Any, Dict, List
import numpy as np
import pandas as pd


class CustomIndicatorAdapter:
    """自定义指标适配器，实现标准技术指标"""

    def is_available(self) -> bool:
        """自定义适配器始终可用"""
        return True

    def list_indicators(self) -> List[str]:
        """返回支持的指标列表"""
        return ['CCI', 'RSI', 'MACD', 'BBANDS', 'ATR', 'ADX', 'PLUS_DI', 'MINUS_DI']

    def calculate(
        self, klines: List[Dict], indicator: str, **params
    ) -> Any:
        """计算指标"""
        df = self._klines_to_dataframe(klines)

        if indicator == 'CCI':
            return self._calculate_cci(df, **params)
        elif indicator == 'RSI':
            return self._calculate_rsi(df, **params)
        elif indicator == 'MACD':
            return self._calculate_macd(df, **params)
        elif indicator == 'BBANDS':
            return self._calculate_bbands(df, **params)
        elif indicator == 'ATR':
            return self._calculate_atr(df, **params)
        elif indicator in ('ADX', 'PLUS_DI', 'MINUS_DI'):
            return self._calculate_adx(df, indicator, **params)

        return None

    def _klines_to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
        """将K线数据转换为DataFrame"""
        df = pd.DataFrame(klines)

        # 确保数值类型
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 处理volume（可能为NULL）
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)

        return df

    def _calculate_cci(self, df: pd.DataFrame, length: int = 20, **kwargs) -> pd.Series:
        """
        计算CCI (Commodity Channel Index)

        标准公式:
        TP = (High + Low + Close) / 3
        SMA = TP的简单移动平均
        MAD = TP与SMA的平均绝对偏差
        CCI = (TP - SMA) / (0.015 * MAD)

        Args:
            df: K线数据
            length: 周期，默认20

        Returns:
            CCI序列
        """
        # 计算典型价格
        typical_price = (df['high'] + df['low'] + df['close']) / 3.0

        # 计算SMA
        sma = typical_price.rolling(window=length).mean()

        # 计算MAD (Mean Absolute Deviation)
        mad = typical_price.rolling(window=length).apply(
            lambda x: np.abs(x - x.mean()).mean(),
            raw=False
        )

        # 计算CCI
        cci = (typical_price - sma) / (0.015 * mad)

        return cci

    def _calculate_rsi(self, df: pd.DataFrame, length: int = 14, **kwargs) -> pd.Series:
        """
        计算RSI (Relative Strength Index)

        Args:
            df: K线数据
            length: 周期，默认14

        Returns:
            RSI序列
        """
        close = df['close']
        delta = close.diff()

        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=length).mean()
        avg_loss = loss.rolling(window=length).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(
        self, df: pd.DataFrame,
        fast: int = 12, slow: int = 26, signal: int = 9,
        **kwargs
    ) -> Dict[str, pd.Series]:
        """
        计算MACD

        Args:
            df: K线数据
            fast: 快线周期，默认12
            slow: 慢线周期，默认26
            signal: 信号线周期，默认9

        Returns:
            包含macd, signal, histogram的字典
        """
        close = df['close']

        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }

    def _calculate_bbands(
        self, df: pd.DataFrame,
        length: int = 20, std: float = 2.0,
        **kwargs
    ) -> Dict[str, pd.Series]:
        """
        计算布林带

        Args:
            df: K线数据
            length: 周期，默认20
            std: 标准差倍数，默认2.0

        Returns:
            包含upper, middle, lower的字典
        """
        close = df['close']

        middle = close.rolling(window=length).mean()
        std_dev = close.rolling(window=length).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }

    def _calculate_atr(self, df: pd.DataFrame, length: int = 14, **kwargs) -> pd.Series:
        """
        计算ATR (Average True Range)

        Args:
            df: K线数据
            length: 周期，默认14

        Returns:
            ATR序列
        """
        high = df['high']
        low = df['low']
        close = df['close']

        # 计算True Range
        tr1 = high - low
        tr2 = np.abs(high - close.shift())
        tr3 = np.abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 计算ATR
        atr = tr.rolling(window=length).mean()

        return atr

    def _calculate_adx(
        self, df: pd.DataFrame, indicator: str, length: int = 14, **kwargs
    ) -> pd.Series:
        """
        计算 ADX / +DI / -DI（平均趋向指数）

        使用 Wilder's Smoothing 计算:
          1. True Range (TR)
          2. +DM / -DM (Directional Movement)
          3. Wilder 平滑 TR, +DM, -DM (α = 1/length)
          4. +DI = 100 × smoothed_+DM / smoothed_TR
          5. -DI = 100 × smoothed_-DM / smoothed_TR
          6. DX = 100 × |+DI - -DI| / (+DI + -DI)
          7. ADX = Wilder 平滑 DX

        Args:
            df: K 线数据（需包含 high, low, close）
            indicator: 返回哪个指标 — 'ADX' | 'PLUS_DI' | 'MINUS_DI'
            length: 周期，默认 14

        Returns:
            对应指标的 Series（前 length 根 K 线值为 NaN）
        """
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        n = len(df)

        # 1. True Range
        tr = np.empty(n, dtype=np.float64)
        tr[:] = np.nan
        for i in range(1, n):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i - 1])
            tr3 = abs(low[i] - close[i - 1])
            tr[i] = max(tr1, tr2, tr3)

        # 2. +DM / -DM
        plus_dm = np.empty(n, dtype=np.float64)
        minus_dm = np.empty(n, dtype=np.float64)
        plus_dm[:] = np.nan
        minus_dm[:] = np.nan
        for i in range(1, n):
            up_move = high[i] - high[i - 1]
            down_move = low[i - 1] - low[i]
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            else:
                plus_dm[i] = 0.0
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
            else:
                minus_dm[i] = 0.0

        # 3. Wilder's Smoothing（初始值 = 前 length 项的简单平均）
        tr_smooth = np.empty(n, dtype=np.float64)
        plus_dm_smooth = np.empty(n, dtype=np.float64)
        minus_dm_smooth = np.empty(n, dtype=np.float64)
        tr_smooth[:] = np.nan
        plus_dm_smooth[:] = np.nan
        minus_dm_smooth[:] = np.nan

        init_end = length + 1
        if init_end <= n:
            tr_valid = tr[1:init_end]
            tr_init = np.mean(tr_valid[~np.isnan(tr_valid)]) if np.any(~np.isnan(tr_valid)) else 0.0
            pdm_init = np.mean(plus_dm[1:init_end])
            mdm_init = np.mean(minus_dm[1:init_end])
        else:
            return pd.Series([np.nan] * n, index=df.index, name=indicator)

        prev_tr = tr_init
        prev_pdm = pdm_init
        prev_mdm = mdm_init

        for i in range(init_end, n):
            prev_tr = prev_tr + (tr[i] - prev_tr) / length
            prev_pdm = prev_pdm + (plus_dm[i] - prev_pdm) / length
            prev_mdm = prev_mdm + (minus_dm[i] - prev_mdm) / length
            tr_smooth[i] = prev_tr
            plus_dm_smooth[i] = prev_pdm
            minus_dm_smooth[i] = prev_mdm

        # 4 & 5. +DI / -DI
        plus_di = np.full(n, np.nan, dtype=np.float64)
        minus_di = np.full(n, np.nan, dtype=np.float64)
        for i in range(init_end, n):
            if tr_smooth[i] > 0:
                plus_di[i] = 100.0 * plus_dm_smooth[i] / tr_smooth[i]
                minus_di[i] = 100.0 * minus_dm_smooth[i] / tr_smooth[i]
            else:
                plus_di[i] = 0.0
                minus_di[i] = 0.0

        # 6 & 7. DX → ADX（再次 Wilder 平滑）
        adx = np.full(n, np.nan, dtype=np.float64)
        prev_adx = 0.0
        for i in range(init_end, n):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum == 0:
                continue
            dx = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum
            if i == init_end:
                prev_adx = dx
            else:
                prev_adx = prev_adx + (dx - prev_adx) / length
            adx[i] = prev_adx

        if indicator == 'ADX':
            return pd.Series(adx, index=df.index, name='ADX')
        elif indicator == 'PLUS_DI':
            return pd.Series(plus_di, index=df.index, name='PLUS_DI')
        elif indicator == 'MINUS_DI':
            return pd.Series(minus_di, index=df.index, name='MINUS_DI')
        return pd.Series(adx, index=df.index, name='ADX')
