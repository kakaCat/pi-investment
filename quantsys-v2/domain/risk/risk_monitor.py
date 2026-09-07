"""
风险监控服务 - Team A
实时风险指标监控和告警
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime
import logging

from domain.risk.var import VaRCalculator

logger = logging.getLogger(__name__)


class RiskMonitorService:
    """
    风险监控服务

    功能:
    1. 实时风险指标计算
    2. 风险限额检查
    3. 风险告警
    """

    def __init__(self,
                 var_calculator: VaRCalculator = None,
                 risk_limits: Dict = None):
        """
        Args:
            var_calculator: VaR计算器
            risk_limits: 风险限额配置
        """
        self.var_calculator = var_calculator or VaRCalculator()
        self.risk_limits = risk_limits or self._default_risk_limits()
        self.portfolio_returns = []
        self.alerts = []

        logger.info("RiskMonitorService initialized")

    def get_realtime_metrics(self) -> Dict:
        """
        获取实时风险指标

        Returns:
            {
                'timestamp': str,
                'var_95': float,
                'cvar_95': float,
                'current_drawdown': float,
                'alerts': List[Dict]
            }
        """
        if len(self.portfolio_returns) < 20:
            logger.warning("Insufficient data for risk calculation")
            return self._empty_metrics()

        returns_series = pd.Series(self.portfolio_returns)

        # 计算风险指标
        metrics = self.var_calculator.calculate_risk_metrics(returns_series)

        # 检查告警
        self._check_alerts(metrics)

        result = {
            'timestamp': datetime.now().isoformat(),
            'var_95': metrics['var_95'],
            'var_99': metrics['var_99'],
            'cvar_95': metrics['cvar_95'],
            'cvar_99': metrics['cvar_99'],
            'current_drawdown': self._current_drawdown(returns_series),
            'max_drawdown': metrics['max_drawdown'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'volatility': metrics['volatility'],
            'alerts': self.alerts[-10:]  # 最近10条告警
        }

        logger.debug(f"Realtime metrics: VaR95={result['var_95']:.4f}")
        return result

    def check_risk_limits(self, position: Dict) -> Dict:
        """
        检查风险限额

        Args:
            position: {
                'symbol': str,
                'quantity': int,
                'price': float,
                'portfolio_value': float
            }

        Returns:
            {
                'passed': bool,
                'violations': List[str],
                'details': Dict
            }
        """
        violations = []
        details = {}

        # 计算仓位比例
        position_value = position['quantity'] * position['price']
        portfolio_value = position.get('portfolio_value', 1000000)
        position_ratio = position_value / portfolio_value

        details['position_value'] = position_value
        details['position_ratio'] = position_ratio

        # 检查单只股票仓位限制
        max_position_ratio = self.risk_limits['max_position_ratio']
        if position_ratio > max_position_ratio:
            violations.append(
                f"单只股票仓位{position_ratio:.2%}超过限额{max_position_ratio:.2%}"
            )

        # 检查VaR限额
        if len(self.portfolio_returns) >= 20:
            returns_series = pd.Series(self.portfolio_returns)
            var_95 = self.var_calculator.calculate(returns_series, confidence_level=0.95, method='historical')['value']
            max_var = self.risk_limits['max_var_95']

            details['var_95'] = var_95

            if var_95 > max_var:  # 正数，越大风险越高
                violations.append(
                    f"VaR95 {var_95:.4f}超过限额{max_var:.4f}"
                )

        passed = len(violations) == 0

        logger.info(f"Risk limit check: passed={passed}, violations={len(violations)}")

        return {
            'passed': passed,
            'violations': violations,
            'details': details
        }

    def add_return(self, daily_return: float):
        """添加日收益率"""
        self.portfolio_returns.append(daily_return)

        # 保持最近252个交易日的数据
        if len(self.portfolio_returns) > 252:
            self.portfolio_returns = self.portfolio_returns[-252:]

    def _check_alerts(self, metrics: Dict):
        """检查并生成告警"""
        # VaR告警 (now returns positive values)
        if metrics['var_95'] > self.risk_limits['alert_var_95']:
            self._add_alert('high', 'VaR95超过告警阈值', {
                'var_95': metrics['var_95'],
                'threshold': self.risk_limits['alert_var_95']
            })

        # 回撤告警 (now returns positive percentage)
        if metrics['max_drawdown'] > self.risk_limits['alert_drawdown']:
            self._add_alert('high', '最大回撤超过告警阈值', {
                'max_drawdown': metrics['max_drawdown'],
                'threshold': self.risk_limits['alert_drawdown']
            })

        # 波动率告警
        if metrics['volatility'] > self.risk_limits['alert_volatility']:
            self._add_alert('medium', '波动率超过告警阈值', {
                'volatility': metrics['volatility'],
                'threshold': self.risk_limits['alert_volatility']
            })

    def _add_alert(self, severity: str, message: str, details: Dict):
        """添加告警"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'severity': severity,
            'message': message,
            'details': details
        }
        self.alerts.append(alert)
        logger.warning(f"Risk alert: {severity} - {message}")

    def _current_drawdown(self, returns: pd.Series) -> float:
        """计算当前回撤"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        current_dd = (cumulative.iloc[-1] - running_max.iloc[-1]) / running_max.iloc[-1]
        return float(current_dd)

    def _default_risk_limits(self) -> Dict:
        """默认风险限额"""
        return {
            'max_position_ratio': 0.20,  # 单只股票最大20%
            'max_var_95': 0.03,          # VaR95最大3%
            'alert_var_95': 0.025,       # VaR95告警阈值2.5%
            'alert_drawdown': 0.10,      # 回撤告警阈值10%
            'alert_volatility': 0.03     # 波动率告警阈值3%
        }

    def _empty_metrics(self) -> Dict:
        """空指标（数据不足时）"""
        return {
            'timestamp': datetime.now().isoformat(),
            'var_95': None,
            'var_99': None,
            'cvar_95': None,
            'cvar_99': None,
            'current_drawdown': None,
            'max_drawdown': None,
            'sharpe_ratio': None,
            'volatility': None,
            'alerts': []
        }
