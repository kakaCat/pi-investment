"""
FinRL Configuration Validation Module - Refactored
降低复杂度：从49降至<15
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


def _validate_numeric_param(value: Any, name: str, min_val: float = None,
                            max_val: float = None, positive_only: bool = False,
                            integer_only: bool = False) -> str:
    """验证数值参数"""
    if integer_only:
        if not isinstance(value, int) or value <= 0:
            return f"Invalid {name}: {value}. Must be a positive integer."
    else:
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
    # 浮点数参数
    float_params = {
        'learning_rate': (None, None, True),
        'gamma': (0, 1, False),
        'tau': (None, None, True),
    }

    for param, (min_val, max_val, positive) in float_params.items():
        if param in config:
            error = _validate_numeric_param(config[param], param, min_val, max_val, positive)
            if error:
                errors.append(error)

    # 整数参数
    int_params = ['n_steps', 'batch_size', 'buffer_size', 'n_epochs']
    for param in int_params:
        if param in config:
            error = _validate_numeric_param(config[param], param, integer_only=True)
            if error:
                errors.append(error)


def _validate_env_config(env: Dict[str, Any], errors: List[str]) -> None:
    """验证环境配置"""
    if 'initial_balance' in env:
        error = _validate_numeric_param(env['initial_balance'], 'initial_balance',
                                       positive_only=True)
        if error:
            errors.append(error)

    if 'transaction_cost' in env:
        error = _validate_numeric_param(env['transaction_cost'], 'transaction_cost',
                                       min_val=0, max_val=1)
        if error:
            errors.append(error)

    if 'reward_scaling' in env:
        error = _validate_numeric_param(env['reward_scaling'], 'reward_scaling',
                                       positive_only=True)
        if error:
            errors.append(error)


def _validate_training_config(training: Dict[str, Any], errors: List[str]) -> None:
    """验证训练配置"""
    int_params = ['total_timesteps', 'eval_freq', 'save_freq', 'log_interval', 'n_eval_episodes']

    for param in int_params:
        if param in training:
            error = _validate_numeric_param(training[param], param, integer_only=True)
            if error:
                errors.append(error)


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate FinRL configuration.

    重构后：复杂度从49降至8
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
