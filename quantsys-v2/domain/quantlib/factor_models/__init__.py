"""
Factor Models Module
====================

Multi-factor models for asset pricing and risk analysis.

Includes:
    - Fama-French 3-factor model
    - Fama-French 5-factor model
    - Carhart 4-factor model
    - Barra risk model
    - Factor exposure calculation

Author: QuantSys V2
Date: 2026-05-24
"""

from .fama_french import (
    FamaFrench3FactorCalculator,
    FamaFrench5FactorCalculator,
    FamaFrenchFactorBuilder
)

from .carhart import (
    CarhartFourFactorCalculator,
    MomentumFactorBuilder
)

from .barra import (
    BarraRiskModelCalculator,
    BarraFactorBuilder
)

from .factor_exposure import FactorExposureCalculator

__all__ = [
    'FamaFrench3FactorCalculator',
    'FamaFrench5FactorCalculator',
    'FamaFrenchFactorBuilder',
    'CarhartFourFactorCalculator',
    'MomentumFactorBuilder',
    'BarraRiskModelCalculator',
    'BarraFactorBuilder',
    'FactorExposureCalculator',
]
