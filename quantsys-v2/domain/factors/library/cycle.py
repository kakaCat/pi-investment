"""
Cycle Indicators Module
=======================

Hilbert Transform cycle indicators using TA-Lib HT_* functions.
🆕 5 cycle analysis indicators for market regime detection.

These indicators help identify:
- Market cycles and periodicity
- Trend vs oscillation regimes
- Phase relationships
"""

import numpy as np
try:
    import talib
except ImportError:
    talib = None
from typing import Dict, Any, List

from domain.factors.library.base import TechnicalFactorCalculator
from infrastructure.quantlib.core.base_calculator import validate_inputs, timing_decorator
from infrastructure.quantlib.core.exceptions import InsufficientDataError


class CycleFactors(TechnicalFactorCalculator):
    """
    Cycle indicator calculator using Hilbert Transform.
    
    Provides 5 cycle analysis indicators:
    - Dominant Cycle Period
    - Dominant Cycle Phase
    - Phasor Components
    - SineWave
    - Trend Mode
    """

    def get_supported_methods(self) -> List[str]:
        """Return list of supported cycle indicators."""
        return [
            'ht_dcperiod',
            'ht_dcphase',
            'ht_phasor',
            'ht_sine',
            'ht_trendmode'
        ]

    # =========================================================================
    # Dominant Cycle Period
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def ht_dcperiod(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Hilbert Transform - Dominant Cycle Period.
        
        Identifies the dominant cycle period in the price data.
        Useful for adaptive indicators and cycle-based strategies.
        
        Args:
            klines: K-line data
        
        Returns:
            Cycle period in days (typically 10-40)
        """
        min_length = 32  # HT functions require at least 32 data points
        if len(klines) < min_length:
            raise InsufficientDataError(
                required=min_length,
                actual=len(klines),
                message=f"HT_DCPERIOD requires at least {min_length} data points"
            )
        
        closes = self._extract_closes(klines)
        
        # Calculate dominant cycle period
        period_values = talib.HT_DCPERIOD(closes)
        period = float(period_values[-1]) if not np.isnan(period_values[-1]) else 0.0
        
        return self._create_result_dict(
            value=period,
            method='ht_dcperiod',
            parameters={},
            metadata={
                'data_points': len(klines),
                'latest_close': float(closes[-1]),
                'interpretation': self._interpret_period(period)
            }
        )

    def _interpret_period(self, period: float) -> str:
        """Interpret cycle period."""
        if period < 15:
            return 'Short cycle (< 15 days) - High frequency'
        elif period < 25:
            return 'Medium cycle (15-25 days) - Normal frequency'
        else:
            return 'Long cycle (> 25 days) - Low frequency'

    # =========================================================================
    # Dominant Cycle Phase
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def ht_dcphase(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Hilbert Transform - Dominant Cycle Phase.
        
        Identifies the current phase within the dominant cycle.
        Phase ranges from 0 to 360 degrees.
        
        Args:
            klines: K-line data
        
        Returns:
            Phase angle in degrees (0-360)
        """
        min_length = 32
        if len(klines) < min_length:
            raise InsufficientDataError(
                required=min_length,
                actual=len(klines),
                message=f"HT_DCPHASE requires at least {min_length} data points"
            )
        
        closes = self._extract_closes(klines)
        
        # Calculate dominant cycle phase
        phase_values = talib.HT_DCPHASE(closes)
        phase = float(phase_values[-1]) if not np.isnan(phase_values[-1]) else 0.0
        
        return self._create_result_dict(
            value=phase,
            method='ht_dcphase',
            parameters={},
            metadata={
                'data_points': len(klines),
                'latest_close': float(closes[-1]),
                'phase_quadrant': self._get_phase_quadrant(phase)
            }
        )

    def _get_phase_quadrant(self, phase: float) -> str:
        """Determine phase quadrant."""
        if 0 <= phase < 90:
            return 'Q1: Rising (0-90°)'
        elif 90 <= phase < 180:
            return 'Q2: Topping (90-180°)'
        elif 180 <= phase < 270:
            return 'Q3: Falling (180-270°)'
        else:
            return 'Q4: Bottoming (270-360°)'

    # =========================================================================
    # Phasor Components
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def ht_phasor(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Hilbert Transform - Phasor Components.
        
        Returns in-phase and quadrature components.
        Useful for advanced cycle analysis.
        
        Args:
            klines: K-line data
        
        Returns:
            Dictionary with in_phase and quadrature values
        """
        min_length = 32
        if len(klines) < min_length:
            raise InsufficientDataError(
                required=min_length,
                actual=len(klines),
                message=f"HT_PHASOR requires at least {min_length} data points"
            )
        
        closes = self._extract_closes(klines)
        
        # Calculate phasor components
        in_phase, quadrature = talib.HT_PHASOR(closes)
        
        in_phase_val = float(in_phase[-1]) if not np.isnan(in_phase[-1]) else 0.0
        quadrature_val = float(quadrature[-1]) if not np.isnan(quadrature[-1]) else 0.0
        
        return self._create_result_dict(
            value=in_phase_val,
            method='ht_phasor',
            parameters={},
            metadata={
                'data_points': len(klines),
                'in_phase': in_phase_val,
                'quadrature': quadrature_val,
                'magnitude': float(np.sqrt(in_phase_val**2 + quadrature_val**2))
            }
        )

    # =========================================================================
    # SineWave
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def ht_sine(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Hilbert Transform - SineWave.
        
        Returns sine and lead sine values for cycle prediction.
        Lead sine leads the sine by 45 degrees.
        
        Args:
            klines: K-line data
        
        Returns:
            Dictionary with sine and lead_sine values
        """
        min_length = 32
        if len(klines) < min_length:
            raise InsufficientDataError(
                required=min_length,
                actual=len(klines),
                message=f"HT_SINE requires at least {min_length} data points"
            )
        
        closes = self._extract_closes(klines)
        
        # Calculate sine wave
        sine, lead_sine = talib.HT_SINE(closes)
        
        sine_val = float(sine[-1]) if not np.isnan(sine[-1]) else 0.0
        lead_sine_val = float(lead_sine[-1]) if not np.isnan(lead_sine[-1]) else 0.0
        
        # Detect crossovers for signals
        signal = 'neutral'
        if len(sine) >= 2:
            if sine[-1] > lead_sine[-1] and sine[-2] <= lead_sine[-2]:
                signal = 'bullish_cross'
            elif sine[-1] < lead_sine[-1] and sine[-2] >= lead_sine[-2]:
                signal = 'bearish_cross'
        
        return self._create_result_dict(
            value=sine_val,
            method='ht_sine',
            parameters={},
            metadata={
                'data_points': len(klines),
                'sine': sine_val,
                'lead_sine': lead_sine_val,
                'signal': signal
            }
        )

    # =========================================================================
    # Trend Mode
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def ht_trendmode(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Hilbert Transform - Trend vs Cycle Mode.
        
        Identifies whether the market is in trend or cycle mode.
        Returns:
        - 1: Trend mode (trending market)
        - 0: Cycle mode (oscillating market)
        
        Args:
            klines: K-line data
        
        Returns:
            Mode value (0 or 1)
        """
        min_length = 63  # HT_TRENDMODE requires more data
        if len(klines) < min_length:
            raise InsufficientDataError(
                required=min_length,
                actual=len(klines),
                message=f"HT_TRENDMODE requires at least {min_length} data points"
            )
        
        closes = self._extract_closes(klines)
        
        # Calculate trend mode
        mode_values = talib.HT_TRENDMODE(closes)
        mode = int(mode_values[-1]) if not np.isnan(mode_values[-1]) else 0
        
        return self._create_result_dict(
            value=mode,
            method='ht_trendmode',
            parameters={},
            metadata={
                'data_points': len(klines),
                'latest_close': float(closes[-1]),
                'mode': 'trend' if mode == 1 else 'cycle',
                'interpretation': self._interpret_mode(mode)
            }
        )

    def _interpret_mode(self, mode: int) -> str:
        """Interpret trend mode."""
        if mode == 1:
            return 'Trending market - Use trend-following strategies'
        else:
            return 'Oscillating market - Use mean-reversion strategies'
