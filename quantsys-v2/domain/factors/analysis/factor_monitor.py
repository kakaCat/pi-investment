"""
因子监控系统 - Team A
IC/IR监控、因子衰减检测、自动告警
"""
import sys
import os

import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FactorMonitor:
    """
    因子监控系统

    功能:
    1. IC/IR实时计算
    2. 因子衰减检测
    3. 因子有效性评级
    4. 自动告警
    """

    def __init__(self,
                 ic_threshold: float = 0.03,
                 ir_threshold: float = 0.5,
                 decay_threshold: float = -0.001):
        """
        Args:
            ic_threshold: IC告警阈值
            ir_threshold: IR告警阈值
            decay_threshold: 衰减告警阈值（斜率）
        """
        self.ic_threshold = ic_threshold
        self.ir_threshold = ir_threshold
        self.decay_threshold = decay_threshold
        self.history = {}  # {factor_name: {'ic': [], 'dates': []}}
        self.alerts = []

        logger.info(f"FactorMonitor initialized: IC>{ic_threshold}, IR>{ir_threshold}")

    def calculate_ic(self,
                    factor_values: pd.Series,
                    forward_returns: pd.Series) -> float:
        """
        计算信息系数 (Information Coefficient)

        IC = Corr(因子值, 未来收益)

        Args:
            factor_values: 因子值序列
            forward_returns: 未来收益序列

        Returns:
            IC值
        """
        # 对齐数据
        common_index = factor_values.index.intersection(forward_returns.index)

        if len(common_index) < 10:
            logger.warning("Insufficient data for IC calculation")
            return 0.0

        factor = factor_values.loc[common_index]
        returns = forward_returns.loc[common_index]

        # 计算相关系数
        ic = factor.corr(returns)

        return float(ic)

    def calculate_ic_ir(self,
                       factor_values: pd.DataFrame,
                       forward_returns: pd.DataFrame,
                       factor_name: str = None) -> Dict:
        """
        计算IC和IR (Information Ratio)

        IR = mean(IC) / std(IC)

        Args:
            factor_values: 因子值矩阵 (日期 × 股票)
            forward_returns: 未来收益矩阵 (日期 × 股票)
            factor_name: 因子名称

        Returns:
            {
                'ic_series': List[float],
                'mean_ic': float,
                'std_ic': float,
                'ir': float,
                'ic_positive_rate': float
            }
        """
        ic_series = []
        dates = []

        # 逐日计算IC
        for date in factor_values.index:
            if date not in forward_returns.index:
                continue

            factor_day = factor_values.loc[date].dropna()
            returns_day = forward_returns.loc[date].dropna()

            # 对齐股票
            common_stocks = factor_day.index.intersection(returns_day.index)

            if len(common_stocks) < 10:
                continue

            ic = factor_day.loc[common_stocks].corr(returns_day.loc[common_stocks])

            if not np.isnan(ic):
                ic_series.append(ic)
                dates.append(date)

        if len(ic_series) == 0:
            return self._empty_ic_ir()

        ic_series = np.array(ic_series)

        mean_ic = float(np.mean(ic_series))
        std_ic = float(np.std(ic_series))
        ir = mean_ic / std_ic if std_ic > 0 else 0.0
        ic_positive_rate = float(np.sum(ic_series > 0) / len(ic_series))

        # 保存历史
        if factor_name:
            self.history[factor_name] = {
                'ic': ic_series.tolist(),
                'dates': dates
            }

        result = {
            'ic_series': ic_series.tolist(),
            'dates': dates,
            'mean_ic': mean_ic,
            'std_ic': std_ic,
            'ir': ir,
            'ic_positive_rate': ic_positive_rate,
            'n_periods': len(ic_series)
        }

        logger.info(
            f"Factor {factor_name}: IC={mean_ic:.4f}, IR={ir:.2f}, "
            f"positive_rate={ic_positive_rate:.2%}"
        )

        return result

    def detect_decay(self,
                    factor_name: str,
                    lookback_periods: int = 60) -> Dict:
        """
        检测因子衰减

        使用线性回归检测IC趋势

        Args:
            factor_name: 因子名称
            lookback_periods: 回看期数

        Returns:
            {
                'is_decaying': bool,
                'slope': float,
                'r_squared': float,
                'p_value': float
            }
        """
        if factor_name not in self.history:
            logger.warning(f"No history for factor {factor_name}")
            return {'is_decaying': False, 'slope': 0, 'r_squared': 0, 'p_value': 1}

        ic_series = self.history[factor_name]['ic']

        if len(ic_series) < lookback_periods:
            lookback_periods = len(ic_series)

        if lookback_periods < 20:
            return {'is_decaying': False, 'slope': 0, 'r_squared': 0, 'p_value': 1}

        # 取最近的IC
        recent_ic = ic_series[-lookback_periods:]

        # 线性回归
        from scipy.stats import linregress

        x = np.arange(len(recent_ic))
        slope, intercept, r_value, p_value, std_err = linregress(x, recent_ic)

        is_decaying = slope < self.decay_threshold and p_value < 0.05

        result = {
            'is_decaying': bool(is_decaying),
            'slope': float(slope),
            'r_squared': float(r_value**2),
            'p_value': float(p_value),
            'recent_ic_mean': float(np.mean(recent_ic))
        }

        if is_decaying:
            logger.warning(
                f"Factor {factor_name} is decaying: slope={slope:.6f}, p={p_value:.4f}"
            )

        return result

    def rate_factor(self, ic_ir_result: Dict) -> str:
        """
        因子有效性评级

        评级标准:
        - A: IR > 1.0, IC > 0.05
        - B: IR > 0.5, IC > 0.03
        - C: IR > 0.3, IC > 0.02
        - D: 其他

        Args:
            ic_ir_result: calculate_ic_ir的返回结果

        Returns:
            评级 ('A', 'B', 'C', 'D')
        """
        mean_ic = abs(ic_ir_result['mean_ic'])
        ir = abs(ic_ir_result['ir'])

        if ir > 1.0 and mean_ic > 0.05:
            rating = 'A'
        elif ir > 0.5 and mean_ic > 0.03:
            rating = 'B'
        elif ir > 0.3 and mean_ic > 0.02:
            rating = 'C'
        else:
            rating = 'D'

        return rating

    def check_alerts(self, factor_name: str, ic_ir_result: Dict, decay_result: Dict):
        """
        检查并生成告警

        Args:
            factor_name: 因子名称
            ic_ir_result: IC/IR结果
            decay_result: 衰减检测结果
        """
        # IC过低告警
        if abs(ic_ir_result['mean_ic']) < self.ic_threshold:
            self._add_alert('low_ic', factor_name, {
                'mean_ic': ic_ir_result['mean_ic'],
                'threshold': self.ic_threshold
            })

        # IR过低告警
        if abs(ic_ir_result['ir']) < self.ir_threshold:
            self._add_alert('low_ir', factor_name, {
                'ir': ic_ir_result['ir'],
                'threshold': self.ir_threshold
            })

        # 因子衰减告警
        if decay_result['is_decaying']:
            self._add_alert('decay', factor_name, {
                'slope': decay_result['slope'],
                'p_value': decay_result['p_value']
            })

    def _add_alert(self, alert_type: str, factor_name: str, details: Dict):
        """添加告警"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'factor': factor_name,
            'details': details
        }
        self.alerts.append(alert)

        logger.warning(f"Alert: {alert_type} for {factor_name}, details={details}")

    def get_alerts(self, last_n: int = 10) -> List[Dict]:
        """获取最近的告警"""
        return self.alerts[-last_n:]

    def generate_report(self, factor_name: str) -> Dict:
        """
        生成因子监控报告

        Returns:
            {
                'factor_name': str,
                'ic_ir': Dict,
                'decay': Dict,
                'rating': str,
                'alerts': List
            }
        """
        if factor_name not in self.history:
            return {'error': f'No data for factor {factor_name}'}

        # 从历史重新计算IC/IR
        ic_series = self.history[factor_name]['ic']
        dates = self.history[factor_name]['dates']

        ic_ir = {
            'ic_series': ic_series,
            'dates': dates,
            'mean_ic': float(np.mean(ic_series)),
            'std_ic': float(np.std(ic_series)),
            'ir': float(np.mean(ic_series) / np.std(ic_series)),
            'ic_positive_rate': float(np.sum(np.array(ic_series) > 0) / len(ic_series))
        }

        decay = self.detect_decay(factor_name)
        rating = self.rate_factor(ic_ir)

        # 获取该因子的告警
        factor_alerts = [a for a in self.alerts if a['factor'] == factor_name]

        return {
            'factor_name': factor_name,
            'ic_ir': ic_ir,
            'decay': decay,
            'rating': rating,
            'alerts': factor_alerts[-5:]  # 最近5条告警
        }

    def _empty_ic_ir(self) -> Dict:
        """空IC/IR结果"""
        return {
            'ic_series': [],
            'dates': [],
            'mean_ic': 0.0,
            'std_ic': 0.0,
            'ir': 0.0,
            'ic_positive_rate': 0.0,
            'n_periods': 0
        }
