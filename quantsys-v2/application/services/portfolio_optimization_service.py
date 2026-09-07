"""
组合优化服务 - 基于 cvxpy
提供科学的组合构建和权重优化
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)

# 尝试导入 cvxpy
try:
    import cvxpy as cp
    CVXPY_AVAILABLE = True
    logger.info("cvxpy is available")
except ImportError:
    CVXPY_AVAILABLE = False
    logger.warning("cvxpy not available. Install with: pip install cvxpy")


class PortfolioOptimizationService:
    """
    组合优化服务

    基于 cvxpy 库，提供业界标准的组合优化算法。
    支持的优化方法包括：
    - 均值-方差优化（马科维茨模型）
    - 最小方差组合
    - 最大夏普比率组合
    - 风险平价组合
    - 均值-CVaR优化

    支持的约束条件：
    - 多头/多空约束
    - 权重上下限
    - 行业中性
    - 换手率限制
    - 杠杆限制
    """

    def __init__(self):
        """初始化组合优化服务"""
        if not CVXPY_AVAILABLE:
            logger.warning(
                "cvxpy not available. Install with: pip install cvxpy"
            )

    def mean_variance_optimization(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        risk_aversion: float = 1.0,
        constraints: Optional[Dict] = None
    ) -> Dict:
        """
        均值-方差优化（马科维茨模型）

        目标函数: maximize (expected_return - risk_aversion * variance)

        Args:
            expected_returns: 预期收益率向量 (n,)
            cov_matrix: 协方差矩阵 (n, n)
            risk_aversion: 风险厌恶系数（越大越保守），默认1.0
            constraints: 约束条件字典

        Returns:
            {
                'weights': 最优权重,
                'expected_return': 预期收益率,
                'risk': 组合标准差,
                'sharpe': 夏普比率
            }
        """
        if not CVXPY_AVAILABLE:
            return self._fallback_equal_weight(len(expected_returns))

        try:
            n = len(expected_returns)
            w = cp.Variable(n)

            # 目标函数
            ret = expected_returns @ w
            risk = cp.quad_form(w, cov_matrix)
            objective = cp.Maximize(ret - risk_aversion * risk)

            # 构建约束
            constraints_list = self._build_constraints(w, n, constraints)

            # 求解（自动选择可用求解器）
            prob = cp.Problem(objective, constraints_list)

            # 尝试多个求解器
            solvers_to_try = [cp.ECOS, cp.SCS, cp.OSQP, cp.CVXOPT]
            solved = False

            for solver in solvers_to_try:
                try:
                    prob.solve(solver=solver)
                    if prob.status in ['optimal', 'optimal_inaccurate']:
                        solved = True
                        break
                except Exception as e:
                    logger.debug(f"Solver {solver} failed: {e}")
                    continue

            if not solved:
                logger.error(f"All solvers failed. Last status: {prob.status}")
                return self._fallback_equal_weight(n)

            weights = w.value
            portfolio_return = float(expected_returns @ weights)
            portfolio_risk = float(np.sqrt(weights @ cov_matrix @ weights))
            sharpe = portfolio_return / portfolio_risk if portfolio_risk > 0 else 0

            return {
                'weights': weights,
                'expected_return': portfolio_return,
                'risk': portfolio_risk,
                'sharpe': sharpe,
                'status': prob.status
            }

        except Exception as e:
            logger.error(f"Mean-variance optimization failed: {e}", exc_info=True)
            return self._fallback_equal_weight(len(expected_returns))

    def minimum_variance(
        self,
        cov_matrix: np.ndarray,
        constraints: Optional[Dict] = None
    ) -> Dict:
        """
        最小方差组合

        目标函数: minimize variance

        Args:
            cov_matrix: 协方差矩阵 (n, n)
            constraints: 约束条件字典

        Returns:
            {
                'weights': 最优权重,
                'risk': 组合标准差
            }
        """
        if not CVXPY_AVAILABLE:
            return self._fallback_equal_weight(cov_matrix.shape[0])

        try:
            n = cov_matrix.shape[0]
            w = cp.Variable(n)

            # 目标函数
            objective = cp.Minimize(cp.quad_form(w, cov_matrix))

            # 构建约束
            constraints_list = self._build_constraints(w, n, constraints)

            # 求解（自动选择可用求解器）
            prob = cp.Problem(objective, constraints_list)

            # 尝试多个求解器
            solvers_to_try = [cp.ECOS, cp.SCS, cp.OSQP, cp.CVXOPT]
            solved = False

            for solver in solvers_to_try:
                try:
                    prob.solve(solver=solver)
                    if prob.status in ['optimal', 'optimal_inaccurate']:
                        solved = True
                        break
                except Exception as e:
                    logger.debug(f"Solver {solver} failed: {e}")
                    continue

            if not solved:
                logger.error(f"All solvers failed. Last status: {prob.status}")
                return self._fallback_equal_weight(n)

            weights = w.value
            portfolio_risk = float(np.sqrt(weights @ cov_matrix @ weights))

            return {
                'weights': weights,
                'risk': portfolio_risk,
                'status': prob.status
            }

        except Exception as e:
            logger.error(f"Minimum variance optimization failed: {e}", exc_info=True)
            return self._fallback_equal_weight(cov_matrix.shape[0])

    def maximum_sharpe(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        risk_free_rate: float = 0.02,
        constraints: Optional[Dict] = None
    ) -> Dict:
        """
        最大夏普比率组合

        目标函数: maximize (return - risk_free_rate) / std

        使用技巧：转换为二次规划问题

        Args:
            expected_returns: 预期收益率向量
            cov_matrix: 协方差矩阵
            risk_free_rate: 无风险利率（年化）
            constraints: 约束条件字典

        Returns:
            {
                'weights': 最优权重,
                'expected_return': 预期收益率,
                'risk': 组合标准差,
                'sharpe': 夏普比率
            }
        """
        if not CVXPY_AVAILABLE:
            return self._fallback_equal_weight(len(expected_returns))

        try:
            n = len(expected_returns)
            w = cp.Variable(n)
            kappa = cp.Variable()

            # 目标函数：最小化方差
            # 约束：超额收益 = 1（归一化）
            objective = cp.Minimize(cp.quad_form(w, cov_matrix))

            constraints_list = [
                (expected_returns - risk_free_rate) @ w == 1,
                cp.sum(w) == kappa
            ]

            # 添加其他约束
            if constraints and constraints.get('long_only', True):
                constraints_list.append(w >= 0)

            if constraints and 'max_weight' in constraints:
                constraints_list.append(w <= constraints['max_weight'] * kappa)

            # 求解（自动选择可用求解器）
            prob = cp.Problem(objective, constraints_list)

            # 尝试多个求解器
            solvers_to_try = [cp.ECOS, cp.SCS, cp.OSQP, cp.CVXOPT]
            solved = False

            for solver in solvers_to_try:
                try:
                    prob.solve(solver=solver)
                    if prob.status in ['optimal', 'optimal_inaccurate']:
                        solved = True
                        break
                except Exception as e:
                    logger.debug(f"Solver {solver} failed: {e}")
                    continue

            if not solved:
                logger.error(f"All solvers failed. Last status: {prob.status}")
                return self._fallback_equal_weight(n)

            # 归一化权重
            weights = w.value / kappa.value
            portfolio_return = float(expected_returns @ weights)
            portfolio_risk = float(np.sqrt(weights @ cov_matrix @ weights))
            sharpe = (portfolio_return - risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0

            return {
                'weights': weights,
                'expected_return': portfolio_return,
                'risk': portfolio_risk,
                'sharpe': sharpe,
                'status': prob.status
            }

        except Exception as e:
            logger.error(f"Maximum Sharpe optimization failed: {e}", exc_info=True)
            return self._fallback_equal_weight(len(expected_returns))

    def risk_parity(
        self,
        cov_matrix: np.ndarray,
        constraints: Optional[Dict] = None
    ) -> Dict:
        """
        风险平价组合

        目标：每个资产贡献相同的风险
        Risk Contribution_i = w_i * (Sigma @ w)_i

        使用迭代算法（风险平价是非凸优化）

        Args:
            cov_matrix: 协方差矩阵
            constraints: 约束条件字典

        Returns:
            {
                'weights': 最优权重,
                'risk': 组合标准差,
                'risk_contributions': 各资产风险贡献
            }
        """
        try:
            n = cov_matrix.shape[0]

            # 初始等权
            w = np.ones(n) / n

            # 迭代优化
            max_iter = 100
            tol = 1e-6

            for iteration in range(max_iter):
                # 计算风险贡献
                portfolio_var = w @ cov_matrix @ w
                marginal_contrib = cov_matrix @ w
                risk_contrib = w * marginal_contrib

                # 目标：每个资产贡献相同风险
                target_risk = portfolio_var / n

                # 调整权重
                w_new = w * np.sqrt(target_risk / (risk_contrib + 1e-10))
                w_new = w_new / w_new.sum()

                # 检查收敛
                if np.allclose(w, w_new, atol=tol):
                    logger.debug(f"Risk parity converged after {iteration + 1} iterations")
                    break

                w = w_new

            portfolio_risk = float(np.sqrt(w @ cov_matrix @ w))
            risk_contributions = w * (cov_matrix @ w)

            return {
                'weights': w,
                'risk': portfolio_risk,
                'risk_contributions': risk_contributions,
                'iterations': iteration + 1
            }

        except Exception as e:
            logger.error(f"Risk parity optimization failed: {e}", exc_info=True)
            return self._fallback_equal_weight(cov_matrix.shape[0])

    def _build_constraints(
        self,
        w: 'cp.Variable',
        n: int,
        constraints: Optional[Dict]
    ) -> List:
        """
        构建约束条件列表

        Args:
            w: cvxpy变量（权重）
            n: 资产数量
            constraints: 约束字典

        Returns:
            约束列表
        """
        constraints_list = [cp.sum(w) == 1]  # 全仓约束

        if constraints is None:
            constraints = {}

        # 多头约束
        if constraints.get('long_only', True):
            constraints_list.append(w >= 0)

        # 权重上限
        if 'max_weight' in constraints:
            constraints_list.append(w <= constraints['max_weight'])

        # 权重下限
        if 'min_weight' in constraints:
            constraints_list.append(w >= constraints['min_weight'])

        # 行业约束
        if 'sector_mapping' in constraints and 'sector_limits' in constraints:
            sector_constraints = self._apply_sector_constraints(
                w, n,
                constraints['sector_mapping'],
                constraints['sector_limits']
            )
            constraints_list.extend(sector_constraints)

        # 换手率约束
        if 'current_weights' in constraints and 'max_turnover' in constraints:
            turnover_constraints = self._apply_turnover_constraint(
                w,
                constraints['current_weights'],
                constraints['max_turnover']
            )
            constraints_list.extend(turnover_constraints)

        return constraints_list

    def _fallback_equal_weight(self, n: int) -> Dict:
        """
        降级方案：等权重

        Args:
            n: 资产数量

        Returns:
            等权重结果
        """
        logger.warning("Using equal-weight fallback")
        weights = np.ones(n) / n
        return {
            'weights': weights,
            'method': 'equal_weight_fallback'
        }

    def mean_cvar_optimization(
        self,
        returns_scenarios: np.ndarray,
        confidence_level: float = 0.95,
        constraints: Optional[Dict] = None
    ) -> Dict:
        """
        均值-CVaR优化

        目标函数: minimize CVaR (条件风险价值)

        Args:
            returns_scenarios: 收益率情景矩阵 (n_scenarios, n_assets)
            confidence_level: 置信水平（默认95%）
            constraints: 约束条件字典

        Returns:
            {
                'weights': 最优权重,
                'cvar': CVaR值,
                'var': VaR值
            }
        """
        if not CVXPY_AVAILABLE:
            return self._fallback_equal_weight(returns_scenarios.shape[1])

        try:
            n_scenarios, n_assets = returns_scenarios.shape
            alpha = 1 - confidence_level

            # 变量
            w = cp.Variable(n_assets)
            var = cp.Variable()  # VaR
            z = cp.Variable(n_scenarios)  # 超过VaR的部分

            # 计算每个情景的组合收益
            portfolio_returns = returns_scenarios @ w

            # CVaR目标函数（最小化损失的CVaR）
            # CVaR = VaR + (1/alpha) * E[max(-return - VaR, 0)]
            cvar = var + (1 / (alpha * n_scenarios)) * cp.sum(z)
            objective = cp.Minimize(cvar)

            # 约束条件
            constraints_list = [
                cp.sum(w) == 1,
                z >= 0,
                z >= -portfolio_returns - var  # z_i >= max(0, -r_i - VaR)
            ]

            # 添加其他约束
            if constraints and constraints.get('long_only', True):
                constraints_list.append(w >= 0)

            if constraints and 'max_weight' in constraints:
                constraints_list.append(w <= constraints['max_weight'])

            # 求解
            prob = cp.Problem(objective, constraints_list)

            # 尝试多个求解器
            solvers_to_try = [cp.ECOS, cp.SCS, cp.OSQP, cp.CVXOPT]
            solved = False

            for solver in solvers_to_try:
                try:
                    prob.solve(solver=solver)
                    if prob.status in ['optimal', 'optimal_inaccurate']:
                        solved = True
                        break
                except Exception as e:
                    logger.debug(f"Solver {solver} failed: {e}")
                    continue

            if not solved:
                logger.error(f"All solvers failed. Last status: {prob.status}")
                return self._fallback_equal_weight(n_assets)

            weights = w.value
            var_value = float(var.value)
            cvar_value = float(var_value + (1 / (alpha * n_scenarios)) * np.sum(z.value))

            return {
                'weights': weights,
                'var': var_value,
                'cvar': cvar_value,
                'status': prob.status
            }

        except Exception as e:
            logger.error(f"Mean-CVaR optimization failed: {e}", exc_info=True)
            return self._fallback_equal_weight(returns_scenarios.shape[1])

    def _apply_sector_constraints(
        self,
        w: 'cp.Variable',
        n: int,
        sector_mapping: Dict[int, str],
        sector_limits: Dict[str, tuple]
    ) -> List:
        """
        应用行业约束

        Args:
            w: cvxpy权重变量
            n: 资产数量
            sector_mapping: 资产索引 -> 行业映射 {0: 'finance', 1: 'tech', ...}
            sector_limits: 行业限制 {'finance': (0.1, 0.3), 'tech': (0.2, 0.4)}

        Returns:
            约束列表
        """
        constraints_list = []

        # 按行业分组
        sectors = {}
        for idx, sector in sector_mapping.items():
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(idx)

        # 为每个行业添加权重限制
        for sector, indices in sectors.items():
            if sector in sector_limits:
                min_weight, max_weight = sector_limits[sector]
                sector_weight = cp.sum([w[i] for i in indices])
                constraints_list.append(sector_weight >= min_weight)
                constraints_list.append(sector_weight <= max_weight)

        return constraints_list

    def _apply_turnover_constraint(
        self,
        w: 'cp.Variable',
        current_weights: np.ndarray,
        max_turnover: float
    ) -> List:
        """
        应用换手率约束

        Args:
            w: cvxpy权重变量
            current_weights: 当前持仓权重
            max_turnover: 最大换手率（0-1之间）

        Returns:
            约束列表
        """
        # 换手率 = sum(|w_new - w_old|) / 2
        # 使用辅助变量来处理绝对值
        n = len(current_weights)
        t = cp.Variable(n)  # 辅助变量

        constraints_list = [
            t >= w - current_weights,
            t >= current_weights - w,
            cp.sum(t) <= 2 * max_turnover
        ]

        return constraints_list
