"""
Factor Mining Calculator
=========================

Automated factor discovery and evaluation for quantitative strategies.

Features:
    - Genetic algorithm for factor evolution
    - Random Forest feature importance for factor selection
    - LASSO regression for sparse factor selection
    - Factor evaluation: IC, IR, monotonicity, stability
    - Automatic formula generation

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, List, Tuple, Callable
from itertools import combinations
import warnings

from domain.quantlib import BaseCalculator, validate_inputs, timing_decorator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    CalculationError,
    ConfigurationError
)


# ---------- Operator Library ----------

OPERATOR_REGISTRY = {
    'add': lambda x, y: x + y,
    'sub': lambda x, y: x - y,
    'mul': lambda x, y: x * y,
    'div': lambda x, y: x / (y + 1e-10),
    'abs': lambda x: np.abs(x),
    'log': lambda x: np.log(np.maximum(x, 1e-10)),
    'sqrt': lambda x: np.sqrt(np.maximum(x, 0)),
    'square': lambda x: x ** 2,
    'inv': lambda x: 1.0 / (x + 1e-10),
    'rank': lambda x: pd.Series(x).rank(pct=True).values if isinstance(x, np.ndarray) else x.rank(pct=True).values,
    'pct_change': lambda x: pd.Series(x).pct_change().fillna(0).values if isinstance(x, np.ndarray) else x.pct_change().fillna(0).values,
    'zscore': lambda x: (x - np.nanmean(x)) / (np.nanstd(x) + 1e-10),
    'ts_mean': lambda x, w=5: pd.Series(x).rolling(window=w).mean().bfill().values,
    'ts_std': lambda x, w=5: pd.Series(x).rolling(window=w).std().bfill().values,
    'ts_max': lambda x, w=5: pd.Series(x).rolling(window=w).max().bfill().values,
    'ts_min': lambda x, w=5: pd.Series(x).rolling(window=w).min().bfill().values,
    'ts_corr': lambda x, y, w=5: pd.Series(x).rolling(window=w).corr(pd.Series(y)).fillna(0).values,
}


class FactorMiningCalculator(BaseCalculator):
    """
    Automated factor mining for quantitative strategy development.

    Discovers, evaluates, and ranks alpha factors using genetic algorithms,
    random forest importance, and LASSO selection.

    Example:
        calc = FactorMiningCalculator()
        result = calc.calculate(
            data=factor_candidates_df,
            target=forward_returns,
            method='genetic',
            n_factors=20
        )
        print(f"Top factors: {result['value']['factors'][:5]}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0,
                 random_state: int = 42):
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)
        self.random_state = random_state
        np.random.seed(random_state)

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        return self.mine_factors(*args, **kwargs)

    def get_supported_methods(self) -> List[str]:
        return ['genetic', 'random_forest', 'lasso', 'correlation', 'combined']

    @validate_inputs
    @timing_decorator
    def mine_factors(self,
                     data: pd.DataFrame,
                     target: Union[np.ndarray, pd.Series],
                     method: str = 'combined',
                     n_factors: int = 20,
                     operators: Optional[List[str]] = None,
                     population_size: int = 100,
                     generations: int = 10,
                     mutation_rate: float = 0.1,
                     crossover_rate: float = 0.7) -> Dict[str, Any]:
        """
        Mine factors from candidate data.

        Args:
            data: DataFrame of candidate factor columns
            target: Target variable (forward returns) for factor evaluation
            method: Mining method - 'genetic', 'random_forest', 'lasso', 'correlation', 'combined'
            n_factors: Number of top factors to return
            operators: List of operator names for genetic algorithm
            population_size: Population size for genetic algorithm
            generations: Number of generations for genetic algorithm
            mutation_rate: Mutation rate for genetic algorithm
            crossover_rate: Crossover rate for genetic algorithm

        Returns:
            Dictionary with:
                - factors: List of top factor names/expressions
                - importance: Dict mapping factor to importance score
                - ic: Information Coefficient for each factor
                - formulas: Generated factor formulas (for genetic method)
        """
        if data is None or (isinstance(data, pd.DataFrame) and data.empty):
            raise DataValidationError("Input data is empty", field_name="data")

        if not isinstance(data, pd.DataFrame):
            raise DataValidationError("data must be a pandas DataFrame", field_name="data")

        target = self._validate_numeric_input(target, 'target')
        if isinstance(target, np.ndarray) and len(target.shape) > 1:
            target = target.flatten()

        if len(data) < 20:
            raise InsufficientDataError(required=20, provided=len(data))

        if operators is None:
            operators = ['add', 'sub', 'mul', 'div', 'zscore', 'pct_change', 'rank']

        self.validate_method(method)
        n_factors = min(n_factors, data.shape[1] if method != 'genetic' else 50)

        # Align target length
        if len(target) != len(data):
            target = target[-len(data):]

        all_factors = {}
        all_ic = {}
        all_formulas = {}
        factor_details = {}

        if method in ('random_forest', 'combined'):
            rf_factors, rf_importance = self._random_forest_selection(data, target, n_factors)
            all_factors['random_forest'] = rf_factors
            for k, v in rf_importance.items():
                all_ic[k] = float(v)
                factor_details[k] = {'method': 'random_forest', 'importance': float(v)}

        if method in ('lasso', 'combined'):
            lasso_factors, lasso_coefs = self._lasso_selection(data, target, n_factors)
            all_factors['lasso'] = lasso_factors
            for k, v in lasso_coefs.items():
                if k in all_ic:
                    all_ic[k] = max(all_ic[k], abs(float(v)))
                else:
                    all_ic[k] = abs(float(v))
                factor_details[k] = {'method': 'lasso', 'coefficient': float(v)}

        if method in ('correlation', 'combined'):
            corr_factors, corr_vals = self._correlation_selection(data, target, n_factors)
            all_factors['correlation'] = corr_factors
            for k, v in corr_vals.items():
                if k in all_ic:
                    all_ic[k] = max(all_ic[k], abs(float(v)))
                else:
                    all_ic[k] = abs(float(v))
                factor_details[k] = {'method': 'correlation', 'correlation': float(v)}

        if method in ('genetic', 'combined'):
            genetic_result = self._genetic_algorithm(
                data, target, operators, population_size,
                generations, mutation_rate, crossover_rate, n_factors
            )
            all_factors['genetic'] = genetic_result['factors']
            all_formulas = genetic_result['formulas']
            for f in genetic_result['factors']:
                if f not in all_ic:
                    all_ic[f] = genetic_result.get('base_ic', 0.0)
                factor_details[f] = {
                    'method': 'genetic',
                    'formula': all_formulas.get(f, ''),
                    'fitness': genetic_result.get('fitness', {}).get(f, 0.0)
                }

        # Combine and deduplicate factors
        unique_factors = []
        seen = set()
        for method_key in all_factors:
            for f in all_factors[method_key]:
                if f not in seen:
                    unique_factors.append(f)
                    seen.add(f)

        # Evaluate all unique factors for IC and stability
        final_ic, final_stability, final_monotonicity = self._evaluate_factors(
            data, target, unique_factors
        )

        # Sort by IC and select top n_factors
        scored_factors = [(f, final_ic.get(f, 0)) for f in unique_factors]
        scored_factors.sort(key=lambda x: abs(x[1]), reverse=True)
        top_factors = [f for f, _ in scored_factors[:n_factors]]

        # Build importance
        importance = {}
        for f in top_factors:
            importance[f] = abs(final_ic.get(f, 0))

        if importance:
            max_imp = max(importance.values())
            if max_imp > 0:
                importance = {k: v / max_imp for k, v in importance.items()}

        return self._create_result_dict(
            value={
                'factors': top_factors,
                'n_factors': len(top_factors),
                'method': method
            },
            method=f'factor_mining_{method}',
            parameters={
                'method': method,
                'n_factors': n_factors,
                'operators': operators,
            },
            metadata={
                'importance': importance,
                'ic': {f: final_ic.get(f, 0) for f in top_factors},
                'stability': {f: final_stability.get(f, 0) for f in top_factors},
                'monotonicity': {f: final_monotonicity.get(f, 0) for f in top_factors},
                'formulas': all_formulas,
                'factor_details': factor_details,
                'cross_sectional_ic': final_ic,
            }
        )

    def _random_forest_selection(self,
                                 data: pd.DataFrame,
                                 target: np.ndarray,
                                 n_factors: int) -> Tuple[List[str], Dict[str, float]]:
        """Select factors using Random Forest importance."""
        try:
            from sklearn.ensemble import RandomForestRegressor
        except ImportError:
            raise DependencyError("scikit-learn", message="Install with: pip install scikit-learn")

        # Prepare data
        valid_data = data.dropna()
        if valid_data.empty:
            return [], {}

        common_idx = min(len(valid_data), len(target))
        X = valid_data.iloc[:common_idx].values
        y = target[:common_idx]

        # Remove rows with NaN in target
        mask = ~np.isnan(y)
        X, y = X[mask], y[mask]

        if len(y) < 10:
            return [], {}

        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=5,
            random_state=self.random_state,
            n_jobs=-1
        )
        rf.fit(X, y)

        importances = dict(zip(valid_data.columns, rf.feature_importances_))
        sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)

        top_factors = [f for f, _ in sorted_features[:n_factors] if _ > 0]
        top_importance = dict(sorted_features[:n_factors])

        return top_factors, top_importance

    def _lasso_selection(self,
                         data: pd.DataFrame,
                         target: np.ndarray,
                         n_factors: int) -> Tuple[List[str], Dict[str, float]]:
        """Select factors using LASSO regression."""
        try:
            from sklearn.linear_model import LassoCV
        except ImportError:
            raise DependencyError("scikit-learn", message="Install with: pip install scikit-learn")

        valid_data = data.dropna()
        if valid_data.empty:
            return [], {}

        common_idx = min(len(valid_data), len(target))
        X = valid_data.iloc[:common_idx].values
        y = target[:common_idx]

        mask = ~np.isnan(y)
        X, y = X[mask], y[mask]

        if len(y) < 10:
            return [], {}

        lasso = LassoCV(cv=3, random_state=self.random_state, max_iter=5000)
        lasso.fit(X, y)

        coefs = dict(zip(valid_data.columns, lasso.coef_))
        nonzero = {k: v for k, v in coefs.items() if abs(v) > 1e-8}
        sorted_coefs = sorted(nonzero.items(), key=lambda x: abs(x[1]), reverse=True)

        top_factors = [f for f, _ in sorted_coefs[:n_factors]]
        top_coefs = dict(sorted_coefs[:n_factors])

        return top_factors, top_coefs

    def _correlation_selection(self,
                               data: pd.DataFrame,
                               target: np.ndarray,
                               n_factors: int) -> Tuple[List[str], Dict[str, float]]:
        """Select factors using correlation with target."""
        correlations = {}
        common_len = min(len(data), len(target))

        for col in data.columns:
            col_vals = data[col].values[:common_len]
            tgt_vals = target[:common_len]

            mask = ~(np.isnan(col_vals) | np.isnan(tgt_vals))
            if mask.sum() < 10:
                continue

            corr = np.corrcoef(col_vals[mask], tgt_vals[mask])[0, 1]
            if not np.isnan(corr):
                correlations[col] = corr

        sorted_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
        top_factors = [f for f, _ in sorted_corr[:n_factors]]
        top_corr = dict(sorted_corr[:n_factors])

        return top_factors, top_corr

    def _genetic_algorithm(self,
                           data: pd.DataFrame,
                           target: np.ndarray,
                           operators: List[str],
                           population_size: int,
                           generations: int,
                           mutation_rate: float,
                           crossover_rate: float,
                           n_factors: int) -> Dict[str, Any]:
        """
        Genetic algorithm for factor evolution.

        Evolves factor expressions using genetic operators to maximize
        IC with the target.
        """
        columns = list(data.columns)
        if len(columns) < 2:
            return {'factors': columns, 'formulas': {}, 'base_ic': 0.0, 'fitness': {}}

        common_len = min(len(data), len(target))
        X = data.iloc[:common_len].values
        y = target[:common_len]

        # Initialize population with simple expressions
        population = self._initialize_population(columns, population_size, operators)

        best_factors = {}
        best_fitness = {}

        for generation in range(generations):
            # Evaluate fitness
            fitness_scores = {}
            for i, (expr, formula) in enumerate(population):
                try:
                    factor_values = self._evaluate_expression(expr, data)
                    if factor_values is not None and len(factor_values) > 10:
                        ic = self._compute_ic(factor_values, y)
                        fitness_scores[i] = abs(ic)
                        factor_name = f"genetic_factor_{generation}_{i}"
                        best_factors[factor_name] = factor_values
                        best_fitness[factor_name] = abs(ic)
                except Exception:
                    fitness_scores[i] = 0.0

            if not fitness_scores:
                break

            # Selection
            sorted_idx = sorted(fitness_scores.keys(), key=lambda i: fitness_scores[i], reverse=True)
            if not sorted_idx:
                break

            # Crossover and mutation
            new_population = []
            elite_count = max(2, population_size // 10)

            # Keep elite
            for idx in sorted_idx[:elite_count]:
                new_population.append(population[idx])

            # Generate offspring
            while len(new_population) < population_size:
                if len(sorted_idx) >= 2 and np.random.random() < crossover_rate:
                    p1_idx = np.random.choice(sorted_idx[:max(2, len(sorted_idx)//2)])
                    p2_idx = np.random.choice(sorted_idx[:max(2, len(sorted_idx)//2)])
                    child_expr, child_formula = self._crossover(
                        population[p1_idx], population[p2_idx]
                    )
                    new_population.append((child_expr, child_formula))
                else:
                    if sorted_idx:
                        parent = population[np.random.choice(sorted_idx[:max(2, len(sorted_idx)//2)])]
                        child_expr, child_formula = self._mutate(parent, operators, columns, mutation_rate)
                        new_population.append((child_expr, child_formula))

            population = new_population[:population_size]

        # Select best factors
        sorted_best = sorted(best_fitness.items(), key=lambda x: x[1], reverse=True)
        top_factors = [f for f, _ in sorted_best[:n_factors]]

        # Generate formulas
        formulas = {}
        for f in top_factors:
            formulas[f] = f"genetic_factor({f})"

        return {
            'factors': top_factors,
            'formulas': formulas,
            'base_ic': best_fitness.get(top_factors[0], 0) if top_factors else 0,
            'fitness': best_fitness,
        }

    def _initialize_population(self,
                               columns: List[str],
                               population_size: int,
                               operators: List[str]) -> List[Tuple[Any, str]]:
        """Initialize population with simple factor expressions."""
        population = []

        # Simple column references
        for col in columns[:min(len(columns), population_size)]:
            population.append((('col', col), col))

        # Simple transformations
        for col in columns:
            if len(population) >= population_size:
                break
            for op in ['zscore', 'rank', 'pct_change']:
                if op in operators and len(population) < population_size:
                    population.append((('unary', op, ('col', col)), f"{op}({col})"))

        # Binary operations between columns
        for col1, col2 in combinations(columns[:5], 2):
            if len(population) >= population_size:
                break
            for op in ['add', 'sub', 'mul', 'div']:
                if op in operators and len(population) < population_size:
                    expr = (('binary', op, ('col', col1), ('col', col2)),
                            f"({col1} {op} {col2})")
                    population.append(expr)

        # Pad with random expressions
        while len(population) < population_size:
            col = np.random.choice(columns)
            op = np.random.choice([o for o in operators if o in OPERATOR_REGISTRY])
            if op in ['add', 'sub', 'mul', 'div']:
                col2 = np.random.choice(columns)
                population.append((('binary', op, ('col', col), ('col', col2)),
                                   f"({col} {op} {col2})"))
            else:
                population.append((('unary', op, ('col', col)),
                                   f"{op}({col})"))

        return population

    def _evaluate_expression(self, expr: Tuple, data: pd.DataFrame) -> Optional[np.ndarray]:
        """Evaluate a factor expression tree on data."""
        expr_type = expr[0]

        if expr_type == 'col':
            col_name = expr[1]
            if col_name in data.columns:
                return data[col_name].values.astype(float)
            return None

        elif expr_type == 'unary':
            _, op, child = expr
            child_vals = self._evaluate_expression(child, data)
            if child_vals is None:
                return None
            if op in OPERATOR_REGISTRY:
                result = OPERATOR_REGISTRY[op](child_vals)
                return result if isinstance(result, np.ndarray) else np.array(result)
            return None

        elif expr_type == 'binary':
            _, op, left, right = expr
            left_vals = self._evaluate_expression(left, data)
            right_vals = self._evaluate_expression(right, data)
            if left_vals is None or right_vals is None:
                return None
            if op in OPERATOR_REGISTRY:
                result = OPERATOR_REGISTRY[op](left_vals, right_vals)
                return result if isinstance(result, np.ndarray) else np.array(result)
            return None

        return None

    def _crossover(self,
                   parent1: Tuple,
                   parent2: Tuple) -> Tuple[Tuple, str]:
        """Crossover two parent expressions."""
        # Simple crossover: swap subtrees
        if np.random.random() < 0.5:
            return parent1
        return parent2

    def _mutate(self,
                parent: Tuple,
                operators: List[str],
                columns: List[str],
                mutation_rate: float) -> Tuple[Tuple, str]:
        """Mutate an expression."""
        if np.random.random() > mutation_rate:
            return parent

        expr, _ = parent
        expr_type = expr[0]

        if expr_type == 'col':
            new_col = np.random.choice(columns)
            return (('col', new_col), new_col)

        elif expr_type == 'unary':
            op = np.random.choice([o for o in operators if o in OPERATOR_REGISTRY
                                   and o not in ['add', 'sub', 'mul', 'div']])
            return (('unary', op, expr[2]), f"{op}(_)")

        elif expr_type == 'binary':
            op = np.random.choice([o for o in operators
                                   if o in ['add', 'sub', 'mul', 'div']])
            return (('binary', op, expr[2], expr[3]), f"(_ {op} _)")

        return parent

    def _compute_ic(self, factor_values: np.ndarray, target: np.ndarray) -> float:
        """Compute Information Coefficient (rank correlation)."""
        common_len = min(len(factor_values), len(target))
        fv = factor_values[:common_len]
        tv = target[:common_len]

        mask = ~(np.isnan(fv) | np.isnan(tv))
        if mask.sum() < 10:
            return 0.0

        try:
            from scipy import stats
            ic, _ = stats.spearmanr(fv[mask], tv[mask])
            return ic if not np.isnan(ic) else 0.0
        except Exception:
            return 0.0

    def _evaluate_factors(self,
                          data: pd.DataFrame,
                          target: np.ndarray,
                          factors: List[str]) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Evaluate factors on IC, stability, and monotonicity.
        """
        ic = {}
        stability = {}
        monotonicity = {}

        common_len = min(len(data), len(target))

        for f in factors:
            if f in data.columns:
                fv = data[f].values[:common_len]
            else:
                continue

            tv = target[:common_len]
            mask = ~(np.isnan(fv) | np.isnan(tv))
            if mask.sum() < 10:
                continue

            # IC
            try:
                from scipy import stats
                ic_val, _ = stats.spearmanr(fv[mask], tv[mask])
                ic[f] = float(ic_val) if not np.isnan(ic_val) else 0.0
            except Exception:
                ic[f] = 0.0

            # Stability: correlation of factor with its lagged value
            try:
                stability_corr = np.corrcoef(fv[mask][:-1], fv[mask][1:])[0, 1]
                stability[f] = float(stability_corr) if not np.isnan(stability_corr) else 0.0
            except Exception:
                stability[f] = 0.0

            # Monotonicity: how well factor values predict target direction
            try:
                f_direction = np.sign(np.diff(fv[mask])) if len(fv[mask]) > 1 else np.array([0])
                t_direction = np.sign(np.diff(tv[mask])) if len(tv[mask]) > 1 else np.array([0])
                if len(f_direction) > 1:
                    mono = np.mean(f_direction == t_direction)
                    monotonicity[f] = float(mono)
                else:
                    monotonicity[f] = 0.0
            except Exception:
                monotonicity[f] = 0.0

        return ic, stability, monotonicity
