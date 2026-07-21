"""
Risk Assessment Stage

Calculates risk metrics from price/returns data.
Supports single-stock and portfolio-level analysis.
"""
import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from domain.quantlib.core.pipeline import PipelineStage

logger = logging.getLogger(__name__)


class RiskAssessmentStage(PipelineStage):
    """
    Risk assessment stage.

    Input:
    - symbol: stock code (or "portfolio" for portfolio-level)
    - klines: K-line data (list of dict with close prices)
    - positions: (optional) current positions for portfolio risk
    - confidence_level: VaR confidence level (default 0.95)

    Output:
    - risk_assessment: {var, cvar, max_drawdown, volatility, sharpe, ...}
    """

    def __init__(
        self,
        name: str = "risk",
        confidence_level: float = 0.95,
        risk_free_rate: float = 0.02,
    ):
        super().__init__(name)
        self.confidence_level = confidence_level
        self.risk_free_rate = risk_free_rate

    def validate_input(self, data: Dict[str, Any]) -> bool:
        if "symbol" not in data:
            raise ValueError("Missing required field: symbol")
        if "klines" not in data:
            raise ValueError("Missing required field: klines")
        if not isinstance(data["klines"], list) or len(data["klines"]) < 5:
            raise ValueError("klines must be a list with at least 5 entries")
        return True

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = data["symbol"]
        klines = data["klines"]
        positions = data.get("positions", [])
        confidence = data.get("confidence_level", self.confidence_level)
        rf_rate = data.get("risk_free_rate", self.risk_free_rate)

        logger.info(f"Calculating risk metrics for {symbol}, {len(klines)} klines")

        assessment = self._calculate_risk(
            symbol, klines, positions,
            confidence_level=confidence,
            risk_free_rate=rf_rate,
        )

        result = data.copy()
        result["risk_assessment"] = assessment

        logger.info(
            f"Risk for {symbol}: VaR={assessment.get('var_95', 0):.4f}, "
            f"volatility={assessment.get('volatility', 0):.4f}"
        )
        return result

    def _calculate_risk(
        self,
        symbol: str,
        klines: List[Dict],
        positions: List[Dict],
        confidence_level: float,
        risk_free_rate: float,
    ) -> Dict:
        df = pd.DataFrame(klines)
        if "close" not in df.columns:
            return {"error": "No close price data"}

        closes = pd.to_numeric(df["close"], errors="coerce").dropna()
        if len(closes) < 5:
            return {"error": "Insufficient price data"}

        returns = closes.pct_change().dropna()

        result = {
            "symbol": symbol,
            "data_points": len(returns),
            "latest_price": float(closes.iloc[-1]),
            "mean_return": round(float(returns.mean()), 6),
            "volatility": round(float(returns.std()), 6),
        }

        # VaR & CVaR
        var_95 = self._historical_var(returns, confidence_level)
        result["var_95"] = round(float(var_95), 6)
        result["var_99"] = round(float(self._historical_var(returns, 0.99)), 6)
        result["cvar_95"] = round(float(self._historical_cvar(returns, confidence_level)), 6)
        result["cvar_99"] = round(float(self._historical_cvar(returns, 0.99)), 6)

        # Parametric VaR
        result["parametric_var_95"] = round(float(self._parametric_var(returns, confidence_level)), 6)

        # Max drawdown
        max_dd, dd_period = self._max_drawdown(closes)
        result["max_drawdown"] = round(float(max_dd), 6)
        result["max_drawdown_days"] = dd_period

        # Sharpe ratio
        excess = returns - (risk_free_rate / 252)
        if returns.std() > 0:
            result["sharpe_ratio"] = round(float(excess.mean() / returns.std() * np.sqrt(252)), 4)
        else:
            result["sharpe_ratio"] = 0.0

        # Sortino ratio (downside deviation only)
        downside = returns[returns < 0]
        if len(downside) > 1 and downside.std() > 0:
            result["sortino_ratio"] = round(float(excess.mean() / downside.std() * np.sqrt(252)), 4)
        else:
            result["sortino_ratio"] = 0.0

        # Calmar ratio
        if abs(max_dd) > 1e-10:
            annual_return = float(returns.mean() * 252)
            result["calmar_ratio"] = round(float(annual_return / abs(max_dd)), 4)
        else:
            result["calmar_ratio"] = 0.0

        # Win/loss stats
        win_days = (returns > 0).sum()
        loss_days = (returns < 0).sum()
        total_days = len(returns)
        result["win_rate_daily"] = round(float(win_days / total_days), 4) if total_days > 0 else 0.0
        result["avg_win"] = round(float(returns[returns > 0].mean()), 6) if win_days > 0 else 0.0
        result["avg_loss"] = round(float(returns[returns < 0].mean()), 6) if loss_days > 0 else 0.0

        # Skewness & Kurtosis
        if len(returns) > 3:
            result["skewness"] = round(float(returns.skew()), 4)
            result["kurtosis"] = round(float(returns.kurtosis()), 4)

        # Portfolio-level metrics (if positions provided)
        if positions:
            result["position_risk"] = self._position_risk(positions, closes)

        return result

    @staticmethod
    def _historical_var(returns: pd.Series, confidence: float) -> float:
        alpha = 1 - confidence
        return returns.quantile(alpha)

    @staticmethod
    def _historical_cvar(returns: pd.Series, confidence: float) -> float:
        alpha = 1 - confidence
        var = returns.quantile(alpha)
        tail = returns[returns <= var]
        if len(tail) == 0:
            return var
        return tail.mean()

    @staticmethod
    def _parametric_var(returns: pd.Series, confidence: float) -> float:
        from scipy.stats import norm
        mu = returns.mean()
        sigma = returns.std()
        z_score = norm.ppf(1 - confidence)
        return mu + z_score * sigma

    @staticmethod
    def _max_drawdown(prices: pd.Series):
        peak = prices.expanding().max()
        drawdown = (prices - peak) / peak
        max_dd = drawdown.min()

        if max_dd >= 0:
            return 0.0, 0

        dd_start = None
        max_dd_days = 0
        in_dd = False

        for i in range(len(drawdown)):
            if drawdown.iloc[i] < 0 and not in_dd:
                dd_start = i
                in_dd = True
            elif drawdown.iloc[i] >= 0 and in_dd:
                dd_days = i - dd_start
                if dd_days > max_dd_days:
                    max_dd_days = dd_days
                in_dd = False

        if in_dd:
            dd_days = len(drawdown) - dd_start
            if dd_days > max_dd_days:
                max_dd_days = dd_days

        return max_dd, max_dd_days

    @staticmethod
    def _position_risk(positions: List[Dict], prices: pd.Series) -> Dict:
        total_value = 0.0
        position_risks = []

        latest_price = float(prices.iloc[-1])

        for pos in positions:
            shares = pos.get("shares", 0)
            entry_price = pos.get("entry_price", 0) or pos.get("avg_cost", 0)

            market_value = shares * latest_price
            cost_basis = shares * entry_price

            pnl = market_value - cost_basis if cost_basis > 0 else 0.0
            pnl_pct = pnl / cost_basis if cost_basis > 0 else 0.0

            position_risks.append({
                "symbol": pos.get("symbol", ""),
                "shares": shares,
                "entry_price": entry_price,
                "current_price": latest_price,
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 4),
            })
            total_value += market_value

        # Concentration risk
        for pr in position_risks:
            pr["weight"] = round(pr["market_value"] / total_value, 4) if total_value > 0 else 0.0

        return {
            "total_value": round(total_value, 2),
            "position_count": len(positions),
            "positions": position_risks,
            "max_concentration": round(
                max((p["weight"] for p in position_risks), default=0.0), 4
            ),
        }
