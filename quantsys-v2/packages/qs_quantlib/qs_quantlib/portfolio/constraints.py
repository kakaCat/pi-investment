"""
Constraint Manager for Portfolio Optimization
==============================================

Manages various constraints for portfolio optimization including:
- Weight constraints (bounds, sum constraints)
- Sector/group constraints
- Risk constraints (volatility, VaR)
- Turnover constraints

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, List, Tuple, Callable
from scipy.optimize import LinearConstraint, NonlinearConstraint


class ConstraintManager:
    """
    Portfolio Optimization Constraint Manager

    Manages and converts various portfolio constraints to scipy-compatible format.

    Constraint types:
        - Weight constraints: lower/upper bounds, sum constraints
        - Sector constraints: sector exposure limits
        - Risk constraints: maximum volatility, VaR, CVaR
        - Turnover constraints: maximum portfolio turnover

    Example:
        manager = ConstraintManager(n_assets=5)

        # Add weight constraints
        manager.add_weight_constraint(lower_bound=0.0, upper_bound=0.3)

        # Add sector constraints
        sector_map = {0: 'Tech', 1: 'Tech', 2: 'Finance', 3: 'Finance', 4: 'Energy'}
        manager.add_sector_constraint(sector_map, sector_limits={'Tech': 0.4, 'Finance': 0.4})

        # Add risk constraint
        manager.add_volatility_constraint(cov_matrix=Sigma, max_volatility=0.15)

        # Convert to scipy format
        scipy_constraints = manager.to_scipy_constraints()
    """

    def __init__(self, n_assets: int):
        """
        Initialize constraint manager.

        Args:
            n_assets: Number of assets in the portfolio
        """
        if n_assets < 1:
            raise ValueError(f"n_assets must be positive, got {n_assets}")

        self.n_assets = n_assets
        self.constraints = []
        self.bounds = None

    def add_weight_constraint(self,
                             lower_bound: Union[float, np.ndarray] = 0.0,
                             upper_bound: Union[float, np.ndarray] = 1.0,
                             sum_to_one: bool = True) -> 'ConstraintManager':
        """
        Add weight constraints.

        Args:
            lower_bound: Lower bound for weights (scalar or array)
            upper_bound: Upper bound for weights (scalar or array)
            sum_to_one: Whether weights must sum to 1

        Returns:
            Self for method chaining
        """
        # Convert to arrays
        if isinstance(lower_bound, (int, float)):
            lb = np.full(self.n_assets, lower_bound, dtype=float)
        else:
            lb = np.asarray(lower_bound, dtype=float)

        if isinstance(upper_bound, (int, float)):
            ub = np.full(self.n_assets, upper_bound, dtype=float)
        else:
            ub = np.asarray(upper_bound, dtype=float)

        # Validate
        if lb.shape != (self.n_assets,):
            raise ValueError(f"lower_bound must have shape ({self.n_assets},), got {lb.shape}")

        if ub.shape != (self.n_assets,):
            raise ValueError(f"upper_bound must have shape ({self.n_assets},), got {ub.shape}")

        if np.any(lb > ub):
            raise ValueError("lower_bound must be <= upper_bound for all assets")

        # Store bounds
        self.bounds = [(lb[i], ub[i]) for i in range(self.n_assets)]

        # Add sum-to-one constraint
        if sum_to_one:
            self.constraints.append({
                'type': 'eq',
                'fun': lambda w: np.sum(w) - 1.0,
                'jac': lambda w: np.ones(self.n_assets),
                'description': 'weights_sum_to_one'
            })

        return self

    def add_sector_constraint(self,
                             sector_map: Dict[int, str],
                             sector_limits: Dict[str, Union[float, Tuple[float, float]]]) -> 'ConstraintManager':
        """
        Add sector exposure constraints.

        Args:
            sector_map: Mapping from asset index to sector name
            sector_limits: Dictionary of sector limits
                          - float: maximum exposure (e.g., {'Tech': 0.4})
                          - tuple: (min, max) exposure (e.g., {'Tech': (0.1, 0.4)})

        Returns:
            Self for method chaining

        Example:
            sector_map = {0: 'Tech', 1: 'Tech', 2: 'Finance', 3: 'Finance', 4: 'Energy'}
            sector_limits = {'Tech': 0.4, 'Finance': (0.2, 0.5), 'Energy': 0.3}
        """
        # Validate sector_map
        if not all(0 <= idx < self.n_assets for idx in sector_map.keys()):
            raise ValueError("sector_map contains invalid asset indices")

        # Group assets by sector
        sectors = {}
        for asset_idx, sector_name in sector_map.items():
            if sector_name not in sectors:
                sectors[sector_name] = []
            sectors[sector_name].append(asset_idx)

        # Add constraints for each sector
        for sector_name, limit in sector_limits.items():
            if sector_name not in sectors:
                raise ValueError(f"Sector '{sector_name}' not found in sector_map")

            asset_indices = sectors[sector_name]

            # Create constraint matrix (sum of weights in sector)
            def make_sector_constraint(indices, min_exp, max_exp):
                def constraint_fun(w):
                    return np.sum(w[indices])

                def constraint_jac(w):
                    jac = np.zeros(self.n_assets)
                    jac[indices] = 1.0
                    return jac

                return constraint_fun, constraint_jac, min_exp, max_exp

            # Parse limit
            if isinstance(limit, (int, float)):
                min_exposure = 0.0
                max_exposure = float(limit)
            elif isinstance(limit, (tuple, list)) and len(limit) == 2:
                min_exposure, max_exposure = limit
            else:
                raise ValueError(f"Invalid limit format for sector '{sector_name}'")

            constraint_fun, constraint_jac, min_exp, max_exp = make_sector_constraint(
                asset_indices, min_exposure, max_exposure
            )

            # Add inequality constraints
            if min_exp > 0:
                self.constraints.append({
                    'type': 'ineq',
                    'fun': lambda w, f=constraint_fun, m=min_exp: f(w) - m,
                    'jac': constraint_jac,
                    'description': f'sector_{sector_name}_min'
                })

            if max_exp < 1.0:
                self.constraints.append({
                    'type': 'ineq',
                    'fun': lambda w, f=constraint_fun, m=max_exp: m - f(w),
                    'jac': lambda w, j=constraint_jac: -j(w),
                    'description': f'sector_{sector_name}_max'
                })

        return self

    def add_volatility_constraint(self,
                                  cov_matrix: Union[np.ndarray, pd.DataFrame],
                                  max_volatility: float) -> 'ConstraintManager':
        """
        Add maximum portfolio volatility constraint.

        Args:
            cov_matrix: Covariance matrix of returns (n, n)
            max_volatility: Maximum allowed portfolio volatility

        Returns:
            Self for method chaining
        """
        if isinstance(cov_matrix, pd.DataFrame):
            cov_matrix = cov_matrix.values

        Sigma = np.asarray(cov_matrix, dtype=float)

        if Sigma.shape != (self.n_assets, self.n_assets):
            raise ValueError(f"cov_matrix must have shape ({self.n_assets}, {self.n_assets})")

        if max_volatility <= 0:
            raise ValueError("max_volatility must be positive")

        # Constraint: sqrt(w^T Σ w) <= max_volatility
        # Equivalent: w^T Σ w <= max_volatility^2
        max_variance = max_volatility ** 2

        def constraint_fun(w):
            variance = np.dot(w, np.dot(Sigma, w))
            return max_variance - variance

        def constraint_jac(w):
            return -2 * np.dot(Sigma, w)

        self.constraints.append({
            'type': 'ineq',
            'fun': constraint_fun,
            'jac': constraint_jac,
            'description': 'max_volatility'
        })

        return self

    def add_var_constraint(self,
                          returns_history: Union[np.ndarray, pd.DataFrame],
                          max_var: float,
                          confidence_level: float = 0.95) -> 'ConstraintManager':
        """
        Add maximum Value at Risk (VaR) constraint.

        Args:
            returns_history: Historical returns matrix (T x n)
            max_var: Maximum allowed VaR (positive number)
            confidence_level: Confidence level for VaR (e.g., 0.95)

        Returns:
            Self for method chaining
        """
        if isinstance(returns_history, pd.DataFrame):
            returns_history = returns_history.values

        R = np.asarray(returns_history, dtype=float)

        if R.shape[1] != self.n_assets:
            raise ValueError(f"returns_history must have {self.n_assets} columns")

        if max_var <= 0:
            raise ValueError("max_var must be positive")

        if not 0 < confidence_level < 1:
            raise ValueError("confidence_level must be in (0, 1)")

        # Calculate portfolio returns for each historical period
        def constraint_fun(w):
            portfolio_returns = np.dot(R, w)
            var = -np.percentile(portfolio_returns, (1 - confidence_level) * 100)
            return max_var - var

        self.constraints.append({
            'type': 'ineq',
            'fun': constraint_fun,
            'description': f'max_var_{confidence_level}'
        })

        return self

    def add_turnover_constraint(self,
                               current_weights: Union[np.ndarray, List],
                               max_turnover: float) -> 'ConstraintManager':
        """
        Add maximum turnover constraint.

        Turnover is defined as: sum(|w_new - w_old|)

        Args:
            current_weights: Current portfolio weights (n,)
            max_turnover: Maximum allowed turnover (e.g., 0.2 for 20%)

        Returns:
            Self for method chaining
        """
        w_old = np.asarray(current_weights, dtype=float)

        if w_old.shape != (self.n_assets,):
            raise ValueError(f"current_weights must have shape ({self.n_assets},)")

        if max_turnover < 0:
            raise ValueError("max_turnover must be non-negative")

        # Constraint: sum(|w_new - w_old|) <= max_turnover
        # This is non-smooth, so we approximate with a smooth constraint
        # or use auxiliary variables (not directly supported by scipy)

        # For now, we use a warning that this constraint is approximate
        def constraint_fun(w):
            turnover = np.sum(np.abs(w - w_old))
            return max_turnover - turnover

        self.constraints.append({
            'type': 'ineq',
            'fun': constraint_fun,
            'description': 'max_turnover'
        })

        return self

    def add_custom_constraint(self,
                             constraint_fun: Callable,
                             constraint_type: str = 'ineq',
                             jacobian: Optional[Callable] = None,
                             description: str = 'custom') -> 'ConstraintManager':
        """
        Add custom constraint function.

        Args:
            constraint_fun: Constraint function f(w)
                           - For 'eq': f(w) = 0
                           - For 'ineq': f(w) >= 0
            constraint_type: 'eq' for equality, 'ineq' for inequality
            jacobian: Optional Jacobian function (gradient of constraint)
            description: Description of the constraint

        Returns:
            Self for method chaining
        """
        if constraint_type not in ['eq', 'ineq']:
            raise ValueError("constraint_type must be 'eq' or 'ineq'")

        constraint = {
            'type': constraint_type,
            'fun': constraint_fun,
            'description': description
        }

        if jacobian is not None:
            constraint['jac'] = jacobian

        self.constraints.append(constraint)

        return self

    def to_scipy_constraints(self) -> List[Dict[str, Any]]:
        """
        Convert constraints to scipy-compatible format.

        Returns:
            List of constraint dictionaries for scipy.optimize.minimize
        """
        return self.constraints

    def get_bounds(self) -> Optional[List[Tuple[float, float]]]:
        """
        Get bounds for scipy optimization.

        Returns:
            List of (lower, upper) tuples for each asset, or None if not set
        """
        return self.bounds

    def validate_weights(self, weights: np.ndarray, tolerance: float = 1e-6) -> Dict[str, Any]:
        """
        Validate if weights satisfy all constraints.

        Args:
            weights: Portfolio weights to validate (n,)
            tolerance: Tolerance for constraint violations

        Returns:
            Dictionary with validation results:
                - satisfied: Boolean indicating if all constraints are satisfied
                - violations: List of violated constraints
        """
        if weights.shape != (self.n_assets,):
            raise ValueError(f"weights must have shape ({self.n_assets},)")

        violations = []

        # Check bounds
        if self.bounds is not None:
            for i, (lb, ub) in enumerate(self.bounds):
                if weights[i] < lb - tolerance:
                    violations.append({
                        'type': 'lower_bound',
                        'asset': i,
                        'value': weights[i],
                        'bound': lb,
                        'violation': lb - weights[i]
                    })
                if weights[i] > ub + tolerance:
                    violations.append({
                        'type': 'upper_bound',
                        'asset': i,
                        'value': weights[i],
                        'bound': ub,
                        'violation': weights[i] - ub
                    })

        # Check constraints
        for constraint in self.constraints:
            constraint_value = constraint['fun'](weights)

            if constraint['type'] == 'eq':
                if abs(constraint_value) > tolerance:
                    violations.append({
                        'type': 'equality',
                        'description': constraint.get('description', 'unknown'),
                        'value': constraint_value,
                        'violation': abs(constraint_value)
                    })
            elif constraint['type'] == 'ineq':
                if constraint_value < -tolerance:
                    violations.append({
                        'type': 'inequality',
                        'description': constraint.get('description', 'unknown'),
                        'value': constraint_value,
                        'violation': -constraint_value
                    })

        return {
            'satisfied': len(violations) == 0,
            'violations': violations,
            'n_violations': len(violations)
        }

    def clear_constraints(self) -> 'ConstraintManager':
        """Clear all constraints."""
        self.constraints = []
        self.bounds = None
        return self

    def get_constraint_summary(self) -> Dict[str, Any]:
        """
        Get summary of all constraints.

        Returns:
            Dictionary with constraint information
        """
        constraint_types = {}
        for constraint in self.constraints:
            ctype = constraint['type']
            desc = constraint.get('description', 'unknown')
            if ctype not in constraint_types:
                constraint_types[ctype] = []
            constraint_types[ctype].append(desc)

        return {
            'n_constraints': len(self.constraints),
            'has_bounds': self.bounds is not None,
            'constraint_types': constraint_types,
            'n_assets': self.n_assets
        }
