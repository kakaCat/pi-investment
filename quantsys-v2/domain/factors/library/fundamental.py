"""
Fundamental Factor Calculators
==============================

Piotroski FSCORE (0-9) and Earnings Quality (0-400) factor calculations.

FSCORE evaluates financial health across 9 Piotroski criteria.
Earnings Quality decomposes profit quality into 4 sub-scores.

All calculators inherit from BaseCalculator for standardized interface.
"""

from __future__ import annotations

from typing import Any, Optional

from domain.quantlib.core.base_calculator import BaseCalculator


# ──────────────────────────────────────────────────────────────────────
# FSCORE Calculator — Piotroski 9-criteria scoring
# ──────────────────────────────────────────────────────────────────────

class FScoreCalculator(BaseCalculator):
    """
    Piotroski FSCORE (0-9).

    Scores a company on 9 binary signals of financial health, comparing
    the current quarter against the same quarter one year ago.

    Signals (1 point each):
        1. ROA > 0
        2. Operating Cash Flow > 0
        3. ROA increased YoY
        4. Operating CF > Net Income  (accrual quality)
        5. Long-term Debt / Total Assets decreased YoY
        6. Current Ratio increased YoY
        7. No new equity issuance (total shares decreased or unchanged)
        8. Gross Margin increased YoY
        9. Asset Turnover (Revenue / Total Assets) increased YoY

    Adapter interface:
        calculate(financial_data: dict) where financial_data has keys
        'current' and 'previous', each a dict with keys:
            roa, operating_cf, net_income, long_term_debt,
            total_assets, current_ratio, total_shares, gross_margin, revenue

    Also supports direct call:
        calculate(current: dict, previous: dict)  # positional args
    """

    def __init__(self, precision: int = 4):
        super().__init__(precision)

    def get_supported_methods(self) -> list[str]:
        return ["fscore"]

    def calculate(self, *args) -> Optional[int]:
        """
        Calculate FSCORE.

        Supports two calling conventions:
            1. calculate(financial_data: dict) — adapter-friendly
               where financial_data = {'current': {...}, 'previous': {...}}
            2. calculate(current: dict, previous: dict) — direct call

        Returns None if critical data fields are missing.
        """
        if len(args) == 1 and isinstance(args[0], dict) and 'current' in args[0]:
            # Adapter calling convention
            fd = args[0]
            current = fd.get('current', {})
            previous = fd.get('previous', {})
        elif len(args) == 2:
            current, previous = args[0], args[1]
        else:
            self.logger.error(f"Invalid arguments for FSCORE: {len(args)} args")
            return None

        def _get(d: dict, key: str) -> Optional[float]:
            v = d.get(key)
            return float(v) if v is not None else None

        # ── extract values ──
        roa = _get(current, "roa")
        cfo = _get(current, "operating_cf")
        ni  = _get(current, "net_income")
        ltd = _get(current, "long_term_debt")
        ta  = _get(current, "total_assets")
        cr  = _get(current, "current_ratio")
        shares = _get(current, "total_shares")
        gm  = _get(current, "gross_margin")
        rev = _get(current, "revenue")

        prev_roa = _get(previous, "roa")
        prev_ltd = _get(previous, "long_term_debt")
        prev_ta  = _get(previous, "total_assets")
        prev_cr  = _get(previous, "current_ratio")
        prev_shares = _get(previous, "total_shares")
        prev_gm  = _get(previous, "gross_margin")
        prev_rev = _get(previous, "revenue")

        # ── guard: need minima ──
        if any(v is None for v in [roa, cfo, ni, ltd, ta, cr, shares, gm, rev]):
            return None
        if any(v is None for v in [prev_roa, prev_ltd, prev_ta, prev_cr,
                                     prev_shares, prev_gm, prev_rev]):
            return None

        score = 0

        # 1. ROA > 0
        if roa > 0:
            score += 1

        # 2. Operating CF > 0
        if cfo > 0:
            score += 1

        # 3. ROA increased YoY
        if roa > prev_roa:
            score += 1

        # 4. Accrual quality: CFO > Net Income
        if cfo > ni:
            score += 1

        # 5. Leverage decreased: LT Debt / Total Assets ↓
        cur_lev = ltd / ta if ta != 0 else None
        prev_lev = prev_ltd / prev_ta if prev_ta != 0 else None
        if cur_lev is not None and prev_lev is not None and cur_lev < prev_lev:
            score += 1

        # 6. Current Ratio increased
        if cr > prev_cr:
            score += 1

        # 7. No new equity issuance (shares ≤ previous)
        if shares <= prev_shares:
            score += 1

        # 8. Gross Margin increased
        if gm > prev_gm:
            score += 1

        # 9. Asset Turnover increased: Revenue / Total Assets ↑
        cur_turn = rev / ta if ta != 0 else None
        prev_turn = prev_rev / prev_ta if prev_ta != 0 else None
        if cur_turn is not None and prev_turn is not None and cur_turn > prev_turn:
            score += 1

        return score


# ──────────────────────────────────────────────────────────────────────
# Earnings Quality Calculator — 4-factor composite (0-400)
# ──────────────────────────────────────────────────────────────────────

class EarningsQualityCalculator(BaseCalculator):
    """
    Earnings Quality 4-Factor Score (0-400).

    Four dimensions, each scored 0-100 (higher = better quality):

        1. Accrual Score:  |Net Income - Operating CF| / Total Assets
           → lower is better (less accrual manipulation)

        2. CF/A Score:     Operating CF / Total Assets
           → higher is better (strong cash generation)

        3. D/A Score:      Total Liabilities / Total Assets
           → lower is better (less leverage)

        4. ROE Score:      Return on Equity
           → higher is better (profitability)

    Adapter interface:
        calculate(financial_data: dict) where financial_data has a 'current' key
        containing: net_income, operating_cf, total_assets, total_liabilities, roe

    Percentile scoring uses DEFAULT_PERCENTILES as fallback when no
    reference distribution is available.
    """

    # ── default percentile thresholds (if no reference provided) ──
    DEFAULT_PERCENTILES = {
        "accrual":      [0.00, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.20, 0.35, 0.60],
        "cf_to_assets": [-0.05, 0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30],
        "debt_to_assets":[0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95],
        "roe":          [-0.10, 0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30],
    }

    def __init__(self, precision: int = 4):
        super().__init__(precision)

    def get_supported_methods(self) -> list[str]:
        return ["earnings_quality"]

    def calculate(self, *args) -> Optional[dict[str, Any]]:
        """
        Calculate earnings quality scores.

        Supports two calling conventions:
            1. calculate(financial_data: dict) — adapter-friendly
               where financial_data = {'current': {...}}
            2. calculate(data: dict) — direct call with metrics directly

        Returns dict with: accrual_score, cf_score, da_score, roe_score, total_score.
        Returns None if critical data is missing.
        """
        if len(args) == 1 and isinstance(args[0], dict):
            raw = args[0]
            # Unwrap 'current' if present (adapter format)
            data = raw.get('current', raw) if 'current' in raw else raw
        else:
            self.logger.error(f"Invalid arguments for EarningsQuality: {len(args)} args")
            return None

        def _get(key: str) -> Optional[float]:
            v = data.get(key)
            return float(v) if v is not None else None

        ni = _get("net_income")
        cf = _get("operating_cf")
        ta = _get("total_assets")
        tl = _get("total_liabilities")
        roe_raw = _get("roe")

        if any(v is None for v in [ni, cf, ta, tl, roe_raw]):
            return None
        if ta == 0:
            return None

        ref = self.DEFAULT_PERCENTILES

        # 1. Accrual Score — lower accrual = better
        accrual = abs(ni - cf) / abs(ta)  # type: ignore[operator]
        accrual_score = self._percentile_score_inverted(accrual, ref["accrual"])

        # 2. CF/A Score — higher = better
        cf_ratio = cf / abs(ta)  # type: ignore[operator]
        cf_score = self._percentile_score(cf_ratio, ref["cf_to_assets"])

        # 3. D/A Score — lower leverage = better
        da_ratio = tl / abs(ta)  # type: ignore[operator]
        da_score = self._percentile_score_inverted(da_ratio, ref["debt_to_assets"])

        # 4. ROE Score — higher = better
        roe_score = self._percentile_score(roe_raw / 100.0 if abs(roe_raw) > 1 else roe_raw,  # type: ignore[operator]
                                           ref["roe"])

        total = accrual_score + cf_score + da_score + roe_score

        return {
            "accrual_score":   round(accrual_score, self.precision),
            "cf_score":        round(cf_score, self.precision),
            "da_score":        round(da_score, self.precision),
            "roe_score":       round(roe_score, self.precision),
            "total_score":     round(total, self.precision),
            "accrual_raw":     round(accrual, 6),
            "cf_ratio_raw":    round(cf_ratio, 6),
            "da_ratio_raw":    round(da_ratio, 6),
            "roe_raw":         round(roe_raw, 4),
        }

    # ── scoring helpers ──

    @staticmethod
    def _percentile_score(value: float, thresholds: list[float]) -> float:
        """
        Map *value* to 0-100 score using *thresholds* (ascending).
        Each threshold represents the 10th, 20th, …, 100th percentile.
        Higher value → higher score.
        """
        if not thresholds:
            return 50.0
        for i, t in enumerate(reversed(thresholds), 1):
            if value >= t:
                return 100.0 - (i - 1) * 10.0 + (10.0 * min(1.0, (value - t) / (t + 0.001)))
        return 0.0

    @staticmethod
    def _percentile_score_inverted(value: float, thresholds: list[float]) -> float:
        """
        Map *value* to 0-100 score using *thresholds* (ascending).
        Lower value → higher score (inverted).
        """
        if not thresholds:
            return 50.0
        for i, t in enumerate(thresholds):
            if value <= t:
                return 100.0 - (i) * 10.0 + (10.0 * min(1.0, (t - value) / (t + 0.001)))
        return 0.0


# ──────────────────────────────────────────────────────────────────────
# Convenience: compute both in one call
# ──────────────────────────────────────────────────────────────────────

def compute_fundamental_factors(
    financial_data: dict[str, Optional[float]],
    previous_data: Optional[dict[str, Optional[float]]] = None,
) -> dict[str, Any]:
    """
    Compute FSCORE and Earnings Quality from financial data.
    Convenience wrapper that returns both in one call.

    Args:
        financial_data: Current-period financial metrics dict
        previous_data: Prior-period financial metrics (for FSCORE YoY).
                       If None, FSCORE returns None.

    Returns:
        Dict with keys: fscore, earnings_quality
    """
    fscore_calc = FScoreCalculator()
    eq_calc = EarningsQualityCalculator()

    result: dict[str, Any] = {}

    if previous_data is not None:
        # Package into adapter format
        result["fscore"] = fscore_calc.calculate({
            "current": financial_data,
            "previous": previous_data
        })
    else:
        result["fscore"] = None

    result["earnings_quality"] = eq_calc.calculate({
        "current": financial_data
    })

    return result
