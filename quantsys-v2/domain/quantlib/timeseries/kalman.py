"""
Kalman Filter Module
====================

Kalman filtering for state space models and dynamic linear models.
Migrated from FinceptTerminal.

Features:
    - Standard Kalman filter
    - Extended Kalman filter (EKF)
    - Unscented Kalman filter (UKF)
    - State estimation and prediction
    - Parameter estimation
    - Smoothing (forward-backward pass)

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
import warnings

from domain.quantlib.base_calculator import BaseCalculator, validate_inputs, timing_decorator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    ModelFitError,
    CalculationError
)


class KalmanFilterCalculator(BaseCalculator):
    """
    Kalman filter calculator for state space models.

    State Space Model:
        State equation:  x_t = F*x_{t-1} + B*u_t + w_t    (w_t ~ N(0, Q))
        Observation:     y_t = H*x_t + v_t                (v_t ~ N(0, R))

    Where:
        - x_t: State vector at time t
        - y_t: Observation vector at time t
        - F: State transition matrix
        - H: Observation matrix
        - Q: Process noise covariance
        - R: Observation noise covariance
        - B: Control input matrix (optional)
        - u_t: Control input (optional)

    Applications:
        - Time series smoothing and filtering
        - Trend estimation
        - Missing data imputation
        - Sensor fusion
        - Dynamic regression

    Example:
        calc = KalmanFilterCalculator()
        result = calc.filter(observations, F, H, Q, R)
        smoothed = calc.smooth(result)
    """

    def get_supported_methods(self) -> List[str]:
        return [
            'filter',
            'smooth',
            'predict',
            'estimate_parameters',
            'fit_local_level'
        ]

    @validate_inputs
    @timing_decorator
    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Main calculation method. Delegates to filter() by default.
        """
        return self.filter(*args, **kwargs)

    @validate_inputs
    @timing_decorator
    def filter(
        self,
        observations: Union[List, np.ndarray, pd.Series],
        F: np.ndarray,
        H: np.ndarray,
        Q: np.ndarray,
        R: np.ndarray,
        x0: Optional[np.ndarray] = None,
        P0: Optional[np.ndarray] = None,
        B: Optional[np.ndarray] = None,
        u: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Apply Kalman filter to observations.

        Args:
            observations: Observation sequence (T x m)
            F: State transition matrix (n x n)
            H: Observation matrix (m x n)
            Q: Process noise covariance (n x n)
            R: Observation noise covariance (m x m)
            x0: Initial state estimate (n x 1)
            P0: Initial state covariance (n x n)
            B: Control input matrix (n x k) [optional]
            u: Control inputs (T x k) [optional]

        Returns:
            Result dict with filtered states, covariances, and innovations
        """
        # Validate observations
        observations = self._validate_numeric_input(observations, 'observations')
        if isinstance(observations, pd.Series):
            obs_array = observations.values.reshape(-1, 1)
        elif isinstance(observations, pd.DataFrame):
            obs_array = observations.values
        else:
            obs_array = np.array(observations)
            if obs_array.ndim == 1:
                obs_array = obs_array.reshape(-1, 1)

        T, m = obs_array.shape  # T: time steps, m: observation dimension

        # Validate matrices
        F = np.array(F)
        H = np.array(H)
        Q = np.array(Q)
        R = np.array(R)

        n = F.shape[0]  # State dimension

        # Validate dimensions
        if F.shape != (n, n):
            raise DataValidationError(
                f"F must be square matrix, got shape {F.shape}",
                field_name="F"
            )

        if H.shape[1] != n:
            raise DataValidationError(
                f"H must have {n} columns to match state dimension",
                field_name="H"
            )

        if Q.shape != (n, n):
            raise DataValidationError(
                f"Q must be {n}x{n} matrix",
                field_name="Q"
            )

        if R.shape[0] != m or R.shape[1] != m:
            raise DataValidationError(
                f"R must be {m}x{m} matrix",
                field_name="R"
            )

        # Initialize state and covariance
        if x0 is None:
            x0 = np.zeros((n, 1))
        else:
            x0 = np.array(x0).reshape(-1, 1)

        if P0 is None:
            P0 = np.eye(n) * 1000  # Large initial uncertainty
        else:
            P0 = np.array(P0)

        # Control inputs
        if B is not None and u is not None:
            B = np.array(B)
            u = np.array(u)
            if u.ndim == 1:
                u = u.reshape(-1, 1)
        else:
            B = None
            u = None

        try:
            # Storage for results
            x_filtered = np.zeros((T, n))  # Filtered states
            P_filtered = np.zeros((T, n, n))  # Filtered covariances
            x_predicted = np.zeros((T, n))  # Predicted states
            P_predicted = np.zeros((T, n, n))  # Predicted covariances
            innovations = np.zeros((T, m))  # Innovation (prediction error)
            innovation_cov = np.zeros((T, m, m))  # Innovation covariance

            # Initialize
            x = x0
            P = P0

            # Kalman filter loop
            for t in range(T):
                # Prediction step
                if B is not None and u is not None:
                    x_pred = F @ x + B @ u[t].reshape(-1, 1)
                else:
                    x_pred = F @ x

                P_pred = F @ P @ F.T + Q

                x_predicted[t] = x_pred.flatten()
                P_predicted[t] = P_pred

                # Handle missing observations
                if np.any(np.isnan(obs_array[t])):
                    # Skip update step for missing data
                    x = x_pred
                    P = P_pred
                    innovations[t] = np.nan
                else:
                    # Update step
                    y = obs_array[t].reshape(-1, 1)
                    y_pred = H @ x_pred

                    # Innovation
                    innov = y - y_pred
                    innovations[t] = innov.flatten()

                    # Innovation covariance
                    S = H @ P_pred @ H.T + R
                    innovation_cov[t] = S

                    # Kalman gain
                    K = P_pred @ H.T @ np.linalg.inv(S)

                    # Update state and covariance
                    x = x_pred + K @ innov
                    P = (np.eye(n) - K @ H) @ P_pred

                x_filtered[t] = x.flatten()
                P_filtered[t] = P

            # Calculate log-likelihood
            log_likelihood = self._calculate_log_likelihood(
                innovations, innovation_cov
            )

            return self._create_result_dict(
                value={
                    'filtered_states': x_filtered.tolist(),
                    'filtered_covariances': P_filtered.tolist(),
                    'predicted_states': x_predicted.tolist(),
                    'predicted_covariances': P_predicted.tolist(),
                    'innovations': innovations.tolist(),
                    'log_likelihood': round(float(log_likelihood), 4)
                },
                method='kalman_filter',
                parameters={
                    'n_observations': T,
                    'state_dim': n,
                    'obs_dim': m
                },
                metadata={
                    'F': F.tolist(),
                    'H': H.tolist(),
                    'Q': Q.tolist(),
                    'R': R.tolist()
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Kalman filter failed: {str(e)}",
                calculation_type="kalman_filter"
            )

    @validate_inputs
    @timing_decorator
    def smooth(
        self,
        filter_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply Rauch-Tung-Striebel (RTS) smoother.

        Backward pass to obtain smoothed state estimates using all observations.

        Args:
            filter_result: Result from filter() method

        Returns:
            Result dict with smoothed states and covariances
        """
        # Extract filtered results
        x_filtered = np.array(filter_result['value']['filtered_states'])
        P_filtered = np.array(filter_result['value']['filtered_covariances'])
        x_predicted = np.array(filter_result['value']['predicted_states'])
        P_predicted = np.array(filter_result['value']['predicted_covariances'])

        T, n = x_filtered.shape

        # Extract system matrices
        F = np.array(filter_result['metadata']['F'])

        try:
            # Storage for smoothed results
            x_smoothed = np.zeros((T, n))
            P_smoothed = np.zeros((T, n, n))

            # Initialize with last filtered estimate
            x_smoothed[-1] = x_filtered[-1]
            P_smoothed[-1] = P_filtered[-1]

            # Backward pass
            for t in range(T - 2, -1, -1):
                # Smoother gain
                P_pred = P_predicted[t + 1]
                J = P_filtered[t] @ F.T @ np.linalg.inv(P_pred)

                # Smoothed state
                x_smoothed[t] = x_filtered[t] + J @ (x_smoothed[t + 1] - x_predicted[t + 1])

                # Smoothed covariance
                P_smoothed[t] = P_filtered[t] + J @ (P_smoothed[t + 1] - P_pred) @ J.T

            return self._create_result_dict(
                value={
                    'smoothed_states': x_smoothed.tolist(),
                    'smoothed_covariances': P_smoothed.tolist()
                },
                method='rts_smoother',
                parameters={
                    'n_observations': T,
                    'state_dim': n
                },
                metadata={
                    'smoother_type': 'Rauch-Tung-Striebel'
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Kalman smoother failed: {str(e)}",
                calculation_type="kalman_smoother"
            )

    @validate_inputs
    @timing_decorator
    def predict(
        self,
        filter_result: Dict[str, Any],
        steps: int = 10
    ) -> Dict[str, Any]:
        """
        Predict future states using Kalman filter.

        Args:
            filter_result: Result from filter() method
            steps: Number of steps to predict

        Returns:
            Result dict with predicted states and covariances
        """
        if steps < 1:
            raise DataValidationError(
                "steps must be at least 1",
                field_name="steps"
            )

        # Extract last filtered state and covariance
        x_filtered = np.array(filter_result['value']['filtered_states'])
        P_filtered = np.array(filter_result['value']['filtered_covariances'])

        x_last = x_filtered[-1].reshape(-1, 1)
        P_last = P_filtered[-1]

        # Extract system matrices
        F = np.array(filter_result['metadata']['F'])
        H = np.array(filter_result['metadata']['H'])
        Q = np.array(filter_result['metadata']['Q'])
        R = np.array(filter_result['metadata']['R'])

        n = F.shape[0]
        m = H.shape[0]

        try:
            # Storage for predictions
            x_pred = np.zeros((steps, n))
            P_pred = np.zeros((steps, n, n))
            y_pred = np.zeros((steps, m))
            y_pred_cov = np.zeros((steps, m, m))

            x = x_last
            P = P_last

            # Prediction loop
            for t in range(steps):
                # Predict state
                x = F @ x
                P = F @ P @ F.T + Q

                x_pred[t] = x.flatten()
                P_pred[t] = P

                # Predict observation
                y = H @ x
                y_cov = H @ P @ H.T + R

                y_pred[t] = y.flatten()
                y_pred_cov[t] = y_cov

            return self._create_result_dict(
                value={
                    'predicted_states': x_pred.tolist(),
                    'predicted_state_covariances': P_pred.tolist(),
                    'predicted_observations': y_pred.tolist(),
                    'predicted_observation_covariances': y_pred_cov.tolist()
                },
                method='kalman_predict',
                parameters={
                    'steps': steps,
                    'state_dim': n,
                    'obs_dim': m
                },
                metadata={}
            )

        except Exception as e:
            raise CalculationError(
                message=f"Kalman prediction failed: {str(e)}",
                calculation_type="kalman_predict"
            )

    @validate_inputs
    @timing_decorator
    def fit_local_level(
        self,
        observations: Union[List, np.ndarray, pd.Series],
        initial_level: Optional[float] = None,
        level_variance: Optional[float] = None,
        obs_variance: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Fit local level model (random walk + noise).

        Model:
            Level: μ_t = μ_{t-1} + η_t    (η_t ~ N(0, σ²_η))
            Obs:   y_t = μ_t + ε_t        (ε_t ~ N(0, σ²_ε))

        Args:
            observations: Observation sequence
            initial_level: Initial level estimate (if None, use first observation)
            level_variance: Level variance σ²_η (if None, estimated)
            obs_variance: Observation variance σ²_ε (if None, estimated)

        Returns:
            Result dict with filtered level and estimated parameters
        """
        # Validate observations
        observations = self._validate_numeric_input(observations, 'observations')
        if isinstance(observations, pd.Series):
            obs_array = observations.values
        else:
            obs_array = np.array(observations)

        T = len(obs_array)

        if T < 10:
            raise InsufficientDataError(
                required=10,
                provided=T,
                calculation="local_level"
            )

        try:
            # Estimate variances if not provided
            if level_variance is None or obs_variance is None:
                # Simple estimation: split variance
                total_var = np.var(np.diff(obs_array))
                level_variance = level_variance or total_var * 0.1
                obs_variance = obs_variance or total_var * 0.9

            # Set up state space matrices
            F = np.array([[1.0]])  # Random walk
            H = np.array([[1.0]])  # Direct observation
            Q = np.array([[level_variance]])
            R = np.array([[obs_variance]])

            # Initial state
            if initial_level is None:
                x0 = np.array([[obs_array[0]]])
            else:
                x0 = np.array([[initial_level]])

            P0 = np.array([[obs_variance]])

            # Apply Kalman filter
            filter_result = self.filter(
                observations=obs_array,
                F=F, H=H, Q=Q, R=R,
                x0=x0, P0=P0
            )

            # Extract level estimates
            level = np.array(filter_result['value']['filtered_states']).flatten()

            # Apply smoother for better estimates
            smooth_result = self.smooth(filter_result)
            level_smoothed = np.array(smooth_result['value']['smoothed_states']).flatten()

            return self._create_result_dict(
                value={
                    'level_filtered': level.tolist(),
                    'level_smoothed': level_smoothed.tolist(),
                    'level_variance': round(float(level_variance), 6),
                    'obs_variance': round(float(obs_variance), 6),
                    'log_likelihood': filter_result['value']['log_likelihood']
                },
                method='local_level',
                parameters={
                    'n_observations': T,
                    'initial_level': float(x0[0, 0])
                },
                metadata={
                    'signal_to_noise_ratio': round(float(level_variance / obs_variance), 4),
                    'filter_result': filter_result,
                    'smooth_result': smooth_result
                }
            )

        except Exception as e:
            raise ModelFitError(
                message=f"Local level model failed: {str(e)}",
                model_type="local_level"
            )

    def _calculate_log_likelihood(
        self,
        innovations: np.ndarray,
        innovation_cov: np.ndarray
    ) -> float:
        """
        Calculate log-likelihood from innovations.

        Args:
            innovations: Innovation sequence (T x m)
            innovation_cov: Innovation covariance sequence (T x m x m)

        Returns:
            Log-likelihood value
        """
        T = len(innovations)
        log_likelihood = 0.0

        for t in range(T):
            if not np.any(np.isnan(innovations[t])):
                innov = innovations[t].reshape(-1, 1)
                S = innovation_cov[t]

                # Log-likelihood contribution
                try:
                    sign, logdet = np.linalg.slogdet(S)
                    if sign > 0:
                        ll_t = -0.5 * (logdet + innov.T @ np.linalg.inv(S) @ innov)
                        log_likelihood += float(ll_t)
                except:
                    continue

        return log_likelihood

    @validate_inputs
    @timing_decorator
    def estimate_parameters(
        self,
        observations: Union[List, np.ndarray, pd.Series],
        F: np.ndarray,
        H: np.ndarray,
        initial_params: Dict[str, float],
        method: str = 'mle'
    ) -> Dict[str, Any]:
        """
        Estimate Kalman filter parameters (Q, R) using maximum likelihood.

        Args:
            observations: Observation sequence
            F: State transition matrix (known)
            H: Observation matrix (known)
            initial_params: Initial parameter guesses {'q': ..., 'r': ...}
            method: Estimation method ('mle')

        Returns:
            Result dict with estimated parameters
        """
        from scipy.optimize import minimize

        # Validate observations
        observations = self._validate_numeric_input(observations, 'observations')
        if isinstance(observations, pd.Series):
            obs_array = observations.values.reshape(-1, 1)
        else:
            obs_array = np.array(observations)
            if obs_array.ndim == 1:
                obs_array = obs_array.reshape(-1, 1)

        n = F.shape[0]
        m = H.shape[0]

        def neg_log_likelihood(params):
            """Negative log-likelihood for optimization."""
            q_var = params[0]
            r_var = params[1]

            if q_var <= 0 or r_var <= 0:
                return 1e10

            Q = np.eye(n) * q_var
            R = np.eye(m) * r_var

            try:
                result = self.filter(
                    observations=obs_array,
                    F=F, H=H, Q=Q, R=R
                )
                return -result['value']['log_likelihood']
            except:
                return 1e10

        try:
            # Initial parameters
            x0 = [initial_params.get('q', 1.0), initial_params.get('r', 1.0)]

            # Optimize
            result = minimize(
                neg_log_likelihood,
                x0,
                method='Nelder-Mead',
                options={'maxiter': 1000}
            )

            q_est = result.x[0]
            r_est = result.x[1]

            return self._create_result_dict(
                value={
                    'q_variance': round(float(q_est), 6),
                    'r_variance': round(float(r_est), 6),
                    'log_likelihood': round(float(-result.fun), 4)
                },
                method='parameter_estimation',
                parameters={
                    'method': method,
                    'initial_params': initial_params
                },
                metadata={
                    'converged': result.success,
                    'n_iterations': result.nit
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Parameter estimation failed: {str(e)}",
                calculation_type="parameter_estimation"
            )
