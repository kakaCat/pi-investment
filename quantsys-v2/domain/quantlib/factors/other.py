"""
Other Technical Indicators Module
==================================

Miscellaneous technical factors including WR, BIAS, PSY, AR, BR, DMA, TRIX, VR,
EMV, WVAD, AD Line, and CCI variants.
Migrated from legacy factor system to BaseCalculator framework.
"""

import numpy as np
from typing import Dict, Any, List

from domain.quantlib.factors.base import TechnicalFactorCalculator
from infrastructure.quantlib.core.base_calculator import validate_inputs, timing_decorator
from infrastructure.quantlib.core.exceptions import InsufficientDataError


class OtherFactors(TechnicalFactorCalculator):
    """
    Other technical indicator calculator.

    Provides miscellaneous technical indicators not categorized elsewhere.
    """

    def get_supported_methods(self) -> List[str]:
        """Return list of supported other indicators."""
        return [
            'wr', 'wr10', 'wr6',
            'bias', 'bias6', 'bias12', 'bias24',
            'psy', 'psy12',
            'ar', 'br',
            'dma', 'dma10_50',
            'trix', 'trix12',
            'vr', 'vr26',
            'emv', 'emv14',
            'wvad',
            'ad_line',
            'cci20'
        ]

    # =========================================================================
    # Williams %R
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def wr(self, klines: List[Dict[str, Any]], period: int = 14) -> Dict[str, Any]:
        """
        Calculate Williams %R indicator.

        WR = (Highest High - Close) / (Highest High - Lowest Low) × -100

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            period: Lookback period (default: 14)

        Returns:
            Result dictionary with WR value (-100 to 0)
        """
        n = len(klines)

        if n < period:
            raise InsufficientDataError(
                required=period,
                actual=n,
                message=f"Williams %R requires at least {period} data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Get highest high and lowest low in period
        highest_high = float(np.max(highs[-period:]))
        lowest_low = float(np.min(lows[-period:]))
        latest_close = closes[-1]

        # Calculate WR
        if highest_high == lowest_low:
            wr_value = -50.0  # Neutral when no range
        else:
            wr_value = -100.0 * (highest_high - latest_close) / (highest_high - lowest_low)

        return self._create_result_dict(
            value=float(wr_value),
            method='wr',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'highest_high': highest_high,
                'lowest_low': lowest_low,
                'latest_close': latest_close,
                'oversold': wr_value < -80,
                'overbought': wr_value > -20
            }
        )

    @validate_inputs
    @timing_decorator
    def wr10(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 10-day Williams %R."""
        return self.wr(klines, period=10)

    @validate_inputs
    @timing_decorator
    def wr6(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 6-day Williams %R."""
        return self.wr(klines, period=6)

    # =========================================================================
    # BIAS (Bias Ratio)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def bias(self, klines: List[Dict[str, Any]], period: int = 6) -> Dict[str, Any]:
        """
        Calculate BIAS (Bias Ratio) indicator.

        BIAS = (Close - MA) / MA × 100

        Args:
            klines: K-line data with 'close' field
            period: MA period (default: 6)

        Returns:
            Result dictionary with BIAS value (percentage)
        """
        n = len(klines)

        if n < period:
            raise InsufficientDataError(
                required=period,
                actual=n,
                message=f"BIAS requires at least {period} data points"
            )

        closes = self._extract_closes(klines)

        # Calculate MA
        ma_value = float(np.mean(closes[-period:]))
        latest_close = closes[-1]

        # Calculate BIAS
        if ma_value == 0:
            raise ValueError("MA is zero, cannot calculate BIAS")

        bias_value = (latest_close - ma_value) / ma_value * 100.0

        return self._create_result_dict(
            value=float(bias_value),
            method='bias',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'ma_value': ma_value,
                'latest_close': latest_close,
                'positive_bias': bias_value > 0,
                'extreme': abs(bias_value) > 10
            }
        )

    @validate_inputs
    @timing_decorator
    def bias6(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 6-day BIAS."""
        return self.bias(klines, period=6)

    @validate_inputs
    @timing_decorator
    def bias12(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 12-day BIAS."""
        return self.bias(klines, period=12)

    @validate_inputs
    @timing_decorator
    def bias24(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 24-day BIAS."""
        return self.bias(klines, period=24)

    # =========================================================================
    # PSY (Psychological Line)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def psy(self, klines: List[Dict[str, Any]], period: int = 12) -> Dict[str, Any]:
        """
        Calculate PSY (Psychological Line) indicator.

        PSY = Count of up days / period × 100

        Args:
            klines: K-line data with 'close' field
            period: Lookback period (default: 12)

        Returns:
            Result dictionary with PSY value (0-100)
        """
        n = len(klines)

        if n < period + 1:
            raise InsufficientDataError(
                required=period + 1,
                actual=n,
                message=f"PSY requires at least {period + 1} data points"
            )

        closes = self._extract_closes(klines)

        # Count up days in the period
        up_days = 0
        for i in range(-period, 0):
            if closes[i] > closes[i - 1]:
                up_days += 1

        psy_value = (up_days / period) * 100.0

        return self._create_result_dict(
            value=float(psy_value),
            method='psy',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'up_days': up_days,
                'down_days': period - up_days,
                'oversold': psy_value < 25,
                'overbought': psy_value > 75
            }
        )

    @validate_inputs
    @timing_decorator
    def psy12(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 12-day PSY."""
        return self.psy(klines, period=12)

    # =========================================================================
    # AR (AR Indicator)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def ar(self, klines: List[Dict[str, Any]], period: int = 26) -> Dict[str, Any]:
        """
        Calculate AR (Buying/Selling Momentum) indicator.

        AR = sum(High - Open) / sum(Open - Low) × 100

        Args:
            klines: K-line data with 'open', 'high', 'low' fields
            period: Lookback period (default: 26)

        Returns:
            Result dictionary with AR value
        """
        n = len(klines)

        if n < period:
            raise InsufficientDataError(
                required=period,
                actual=n,
                message=f"AR requires at least {period} data points"
            )

        opens = self._extract_opens(klines)
        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)

        # Calculate AR components
        sum_ho = float(np.sum(highs[-period:] - opens[-period:]))
        sum_ol = float(np.sum(opens[-period:] - lows[-period:]))

        if sum_ol == 0:
            ar_value = 100.0  # Neutral when denominator is zero
        else:
            ar_value = (sum_ho / sum_ol) * 100.0

        return self._create_result_dict(
            value=float(ar_value),
            method='ar',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'sum_ho': sum_ho,
                'sum_ol': sum_ol,
                'weak': ar_value < 70,
                'strong': ar_value > 150
            }
        )

    # =========================================================================
    # BR (BR Indicator)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def br(self, klines: List[Dict[str, Any]], period: int = 26) -> Dict[str, Any]:
        """
        Calculate BR (Buying/Selling Willingness) indicator.

        BR = sum(High - Previous Close) / sum(Previous Close - Low) × 100

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            period: Lookback period (default: 26)

        Returns:
            Result dictionary with BR value
        """
        n = len(klines)

        if n < period + 1:
            raise InsufficientDataError(
                required=period + 1,
                actual=n,
                message=f"BR requires at least {period + 1} data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Calculate BR components
        sum_hc = 0.0
        sum_cl = 0.0

        for i in range(-period, 0):
            prev_close = closes[i - 1]
            sum_hc += max(0, highs[i] - prev_close)
            sum_cl += max(0, prev_close - lows[i])

        if sum_cl == 0:
            br_value = 100.0  # Neutral when denominator is zero
        else:
            br_value = (sum_hc / sum_cl) * 100.0

        return self._create_result_dict(
            value=float(br_value),
            method='br',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'sum_hc': sum_hc,
                'sum_cl': sum_cl,
                'weak': br_value < 70,
                'strong': br_value > 200
            }
        )

    # =========================================================================
    # DMA (Different Moving Average)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def dma(
        self,
        klines: List[Dict[str, Any]],
        short_period: int = 10,
        long_period: int = 50
    ) -> Dict[str, Any]:
        """
        Calculate DMA (Different Moving Average) indicator.

        DMA = Short MA - Long MA

        Args:
            klines: K-line data with 'close' field
            short_period: Short MA period (default: 10)
            long_period: Long MA period (default: 50)

        Returns:
            Result dictionary with DMA value
        """
        n = len(klines)

        if n < long_period:
            raise InsufficientDataError(
                required=long_period,
                actual=n,
                message=f"DMA requires at least {long_period} data points"
            )

        closes = self._extract_closes(klines)

        # Calculate short and long MAs
        short_ma = float(np.mean(closes[-short_period:]))
        long_ma = float(np.mean(closes[-long_period:]))

        dma_value = short_ma - long_ma

        return self._create_result_dict(
            value=float(dma_value),
            method='dma',
            parameters={'short_period': short_period, 'long_period': long_period},
            metadata={
                'data_points': n,
                'short_ma': short_ma,
                'long_ma': long_ma,
                'bullish': dma_value > 0,
                'bearish': dma_value < 0
            }
        )

    @validate_inputs
    @timing_decorator
    def dma10_50(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate DMA with 10/50 periods."""
        return self.dma(klines, short_period=10, long_period=50)

    # =========================================================================
    # TRIX (Triple Exponential Average)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def trix(self, klines: List[Dict[str, Any]], period: int = 12) -> Dict[str, Any]:
        """
        Calculate TRIX (Triple Exponential Average) indicator.

        TRIX = (EMA3 - Previous EMA3) / Previous EMA3 × 100
        where EMA3 = EMA(EMA(EMA(Close)))

        Args:
            klines: K-line data with 'close' field
            period: EMA period (default: 12)

        Returns:
            Result dictionary with TRIX value (percentage)
        """
        n = len(klines)

        if n < period * 3:
            raise InsufficientDataError(
                required=period * 3,
                actual=n,
                message=f"TRIX requires at least {period * 3} data points"
            )

        closes = self._extract_closes(klines)

        # Calculate triple EMA
        ema1 = self._ema_series(closes, period)
        ema2 = self._ema_series(ema1[~np.isnan(ema1)], period)
        ema3 = self._ema_series(ema2[~np.isnan(ema2)], period)

        # Remove NaN values
        ema3_clean = ema3[~np.isnan(ema3)]

        if len(ema3_clean) < 2:
            raise InsufficientDataError(
                required=period * 3,
                actual=n,
                message="Insufficient data for TRIX calculation"
            )

        # Calculate rate of change
        prev_ema3 = ema3_clean[-2]
        curr_ema3 = ema3_clean[-1]

        if prev_ema3 == 0:
            trix_value = 0.0
        else:
            trix_value = ((curr_ema3 - prev_ema3) / prev_ema3) * 100.0

        return self._create_result_dict(
            value=float(trix_value),
            method='trix',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'ema3_current': curr_ema3,
                'ema3_previous': prev_ema3,
                'bullish': trix_value > 0,
                'bearish': trix_value < 0
            }
        )

    @validate_inputs
    @timing_decorator
    def trix12(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 12-day TRIX."""
        return self.trix(klines, period=12)

    # =========================================================================
    # VR (Volume Ratio)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def vr(self, klines: List[Dict[str, Any]], period: int = 26) -> Dict[str, Any]:
        """
        Calculate VR (Volume Ratio) indicator.

        VR = (AVS + 1/2 CVS) / (BVS + 1/2 CVS) × 100
        AVS = sum of volume on up days
        BVS = sum of volume on down days
        CVS = sum of volume on unchanged days

        Args:
            klines: K-line data with 'close', 'volume' fields
            period: Lookback period (default: 26)

        Returns:
            Result dictionary with VR value
        """
        n = len(klines)

        if n < period + 1:
            raise InsufficientDataError(
                required=period + 1,
                actual=n,
                message=f"VR requires at least {period + 1} data points"
            )

        closes = self._extract_closes(klines)
        volumes = self._extract_volumes(klines)

        # Calculate volume sums
        avs = 0.0  # Up volume
        bvs = 0.0  # Down volume
        cvs = 0.0  # Unchanged volume

        for i in range(-period, 0):
            if closes[i] > closes[i - 1]:
                avs += volumes[i]
            elif closes[i] < closes[i - 1]:
                bvs += volumes[i]
            else:
                cvs += volumes[i]

        # Calculate VR
        denominator = bvs + 0.5 * cvs
        if denominator == 0:
            vr_value = 100.0
        else:
            vr_value = ((avs + 0.5 * cvs) / denominator) * 100.0

        return self._create_result_dict(
            value=float(vr_value),
            method='vr',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'up_volume': avs,
                'down_volume': bvs,
                'unchanged_volume': cvs,
                'oversold': vr_value < 70,
                'overbought': vr_value > 180
            }
        )

    @validate_inputs
    @timing_decorator
    def vr26(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 26-day VR."""
        return self.vr(klines, period=26)

    # =========================================================================
    # EMV (Ease of Movement)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def emv(self, klines: List[Dict[str, Any]], period: int = 14) -> Dict[str, Any]:
        """
        Calculate EMV (Ease of Movement) indicator.

        EMV = MA(Distance Moved / (Volume / (High - Low)))
        Distance Moved = (High + Low) / 2 - Previous (High + Low) / 2

        Args:
            klines: K-line data with 'high', 'low', 'volume' fields
            period: MA period (default: 14)

        Returns:
            Result dictionary with EMV value
        """
        n = len(klines)

        if n < period + 1:
            raise InsufficientDataError(
                required=period + 1,
                actual=n,
                message=f"EMV requires at least {period + 1} data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        volumes = self._extract_volumes(klines)

        # Calculate EMV raw values
        emv_raw = np.zeros(n)

        for i in range(1, n):
            mid_point = (highs[i] + lows[i]) / 2.0
            prev_mid = (highs[i - 1] + lows[i - 1]) / 2.0
            distance = mid_point - prev_mid

            high_low_range = highs[i] - lows[i]
            if high_low_range == 0 or volumes[i] == 0:
                emv_raw[i] = 0.0
            else:
                box_ratio = (volumes[i] / 1000000.0) / high_low_range
                emv_raw[i] = distance / box_ratio

        # Calculate MA of EMV
        emv_value = float(np.mean(emv_raw[-period:]))

        return self._create_result_dict(
            value=float(emv_value),
            method='emv',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'latest_raw_emv': emv_raw[-1],
                'bullish': emv_value > 0,
                'bearish': emv_value < 0
            }
        )

    @validate_inputs
    @timing_decorator
    def emv14(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 14-day EMV."""
        return self.emv(klines, period=14)

    # =========================================================================
    # WVAD (Weighted Volume Accumulation/Distribution)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def wvad(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate WVAD (Weighted Volume Accumulation/Distribution) indicator.

        WVAD = sum((Close - Open) / (High - Low) × Volume)

        Args:
            klines: K-line data with 'open', 'high', 'low', 'close', 'volume' fields

        Returns:
            Result dictionary with WVAD value
        """
        n = len(klines)

        if n < 1:
            raise InsufficientDataError(
                required=1,
                actual=n,
                message="WVAD requires at least 1 data point"
            )

        opens = self._extract_opens(klines)
        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)
        volumes = self._extract_volumes(klines)

        # Calculate WVAD
        wvad_value = 0.0

        for i in range(n):
            high_low_range = highs[i] - lows[i]
            if high_low_range == 0:
                continue
            wvad_value += ((closes[i] - opens[i]) / high_low_range) * volumes[i]

        return self._create_result_dict(
            value=float(wvad_value),
            method='wvad',
            parameters={},
            metadata={
                'data_points': n,
                'latest_volume': volumes[-1],
                'accumulation': wvad_value > 0,
                'distribution': wvad_value < 0
            }
        )

    # =========================================================================
    # AD Line (Accumulation/Distribution Line)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def ad_line(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate A/D Line (Accumulation/Distribution Line) indicator.

        CLV = ((Close - Low) - (High - Close)) / (High - Low)
        A/D Line = cumulative sum of (CLV × Volume)

        Args:
            klines: K-line data with 'high', 'low', 'close', 'volume' fields

        Returns:
            Result dictionary with A/D Line value
        """
        n = len(klines)

        if n < 1:
            raise InsufficientDataError(
                required=1,
                actual=n,
                message="A/D Line requires at least 1 data point"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)
        volumes = self._extract_volumes(klines)

        # Calculate A/D Line
        ad_value = 0.0

        for i in range(n):
            high_low_range = highs[i] - lows[i]
            if high_low_range == 0:
                clv = 0.0
            else:
                clv = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / high_low_range

            ad_value += clv * volumes[i]

        return self._create_result_dict(
            value=float(ad_value),
            method='ad_line',
            parameters={},
            metadata={
                'data_points': n,
                'latest_volume': volumes[-1],
                'accumulation': ad_value > 0,
                'distribution': ad_value < 0
            }
        )

    # =========================================================================
    # CCI20 (20-day CCI variant)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def cci20(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate 20-day CCI (Commodity Channel Index) indicator.

        CCI = (Typical Price - MA) / (0.015 × Mean Deviation)
        Typical Price = (High + Low + Close) / 3

        Args:
            klines: K-line data with 'high', 'low', 'close' fields

        Returns:
            Result dictionary with CCI value
        """
        period = 20
        n = len(klines)

        if n < period:
            raise InsufficientDataError(
                required=period,
                actual=n,
                message=f"CCI20 requires at least {period} data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Calculate typical price
        tp = (highs + lows + closes) / 3.0

        # Calculate MA of typical price
        tp_ma = float(np.mean(tp[-period:]))

        # Calculate mean deviation
        deviations = np.abs(tp[-period:] - tp_ma)
        mean_deviation = float(np.mean(deviations))

        # Calculate CCI
        if mean_deviation == 0:
            cci_value = 0.0
        else:
            cci_value = (tp[-1] - tp_ma) / (0.015 * mean_deviation)

        return self._create_result_dict(
            value=float(cci_value),
            method='cci20',
            parameters={'period': 20},
            metadata={
                'data_points': n,
                'typical_price': tp[-1],
                'tp_ma': tp_ma,
                'mean_deviation': mean_deviation,
                'oversold': cci_value < -100,
                'overbought': cci_value > 100
            }
        )
