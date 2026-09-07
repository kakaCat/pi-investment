# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""
Qlib Configuration Validation Module - Refactored
降低复杂度：从55降至<15
"""

from typing import Any, Dict, List, Tuple


def _validate_required_fields(config: Dict[str, Any], errors: List[str]) -> None:
    """验证必需字段"""
    if 'algorithm' not in config:
        errors.append("Missing required field: 'algorithm'")

    if 'env' not in config:
        errors.append("Missing required field: 'env'")
    elif not isinstance(config['env'], dict):
        errors.append("Field 'env' must be a dictionary")

    if 'training' not in config:
        errors.append("Missing required field: 'training'")
    elif not isinstance(config['training'], dict):
        errors.append("Field 'training' must be a dictionary")


def _validate_numeric_range(value: Any, name: str, min_val: float = None,
                            max_val: float = None, positive_only: bool = False) -> str:
    """验证数值范围"""
    if not isinstance(value, (int, float)):
        return f"Invalid {name}: {value}. Must be a number."

    if positive_only and value <= 0:
        return f"Invalid {name}: {value}. Must be a positive number."

    if min_val is not None and max_val is not None:
        if not (min_val <= value <= max_val):
            return f"Invalid {name}: {value}. Must be in range [{min_val}, {max_val}]."

    return None


def _validate_algorithm_params(config: Dict[str, Any], errors: List[str]) -> None:
    """验证算法参数"""
    validations = [
        ('learning_rate', None, None, True),
        ('gamma', 0, 1, False),
        ('tau', None, None, True),
    ]

    for param, min_val, max_val, positive in validations:
        if param in config:
            error = _validate_numeric_range(config[param], param, min_val, max_val, positive)
            if error:
                errors.append(error)

    # 验证整数参数
    int_params = ['n_steps', 'batch_size', 'buffer_size', 'n_epochs']
    for param in int_params:
        if param in config:
            value = config[param]
            if not isinstance(value, int) or value <= 0:
                errors.append(f"Invalid {param}: {value}. Must be a positive integer.")


def _validate_env_config(env: Dict[str, Any], errors: List[str]) -> None:
    """验证环境配置"""
    if 'initial_capital' in env:
        error = _validate_numeric_range(env['initial_capital'], 'initial_capital',
                                       positive_only=True)
        if error:
            errors.append(error)

    if 'transaction_cost' in env:
        error = _validate_numeric_range(env['transaction_cost'], 'transaction_cost',
                                       min_val=0, max_val=1)
        if error:
            errors.append(error)

    if 'reward_scaling' in env:
        error = _validate_numeric_range(env['reward_scaling'], 'reward_scaling',
                                       positive_only=True)
        if error:
            errors.append(error)


def _validate_training_config(training: Dict[str, Any], errors: List[str]) -> None:
    """验证训练配置"""
    int_params = ['total_timesteps', 'eval_freq', 'save_freq', 'log_interval', 'n_eval_episodes']

    for param in int_params:
        if param in training:
            value = training[param]
            if not isinstance(value, int) or value <= 0:
                errors.append(f"Invalid {param}: {value}. Must be a positive integer.")


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate Qlib RL configuration.

    重构后：复杂度从55降至8
    """
    errors: List[str] = []

    # 验证必需字段
    _validate_required_fields(config, errors)

    # 验证算法参数
    _validate_algorithm_params(config, errors)

    # 验证环境配置
    if 'env' in config and isinstance(config['env'], dict):
        _validate_env_config(config['env'], errors)

    # 验证训练配置
    if 'training' in config and isinstance(config['training'], dict):
        _validate_training_config(config['training'], errors)

    is_valid = len(errors) == 0
    return is_valid, errors
