"""
pools.py 依赖注入迁移版本

改造说明:
1. 删除 _get_services() 函数和全局变量
2. 使用 @inject 装饰器自动注入服务
3. 代码更简洁，依赖关系更清晰
"""
import logging
from flask import Blueprint, jsonify, request, current_app
from infrastructure.di.decorators import inject

logger = logging.getLogger(__name__)

pools_bp = Blueprint('pools', __name__)

# Screening filter validation
ALLOWED_FIELDS = {
    'roe', 'pe', 'pb', 'gross_margin', 'debt_ratio',
    'net_profit_growth', 'market_cap', 'circulating_mv',
    'avg_turnover_rate', 'rsi', 'macd', 'volume_ratio_5d'
}
ALLOWED_OPERATORS = {'>=', '<=', '>', '<', '==', '!='}


def validate_filter(filter_dict):
    """
    校验筛选条件合法性

    Args:
        filter_dict: 筛选条件字典

    Raises:
        ValueError: 条件不合法时抛出
    """
    conditions = filter_dict.get('conditions', [])

    for cond in conditions:
        field = cond.get('field')
        operator = cond.get('operator')
        value = cond.get('value')

        if field not in ALLOWED_FIELDS:
            raise ValueError(f"Invalid field: {field}. Allowed: {', '.join(sorted(ALLOWED_FIELDS))}")

        if operator not in ALLOWED_OPERATORS:
            raise ValueError(f"Invalid operator: {operator}. Allowed: {', '.join(sorted(ALLOWED_OPERATORS))}")

        if not isinstance(value, (int, float)):
            raise ValueError(f"Invalid value type for field '{field}': {type(value).__name__}. Must be number.")

    return True


def _convert_filter_keys(filter_dict):
    """Convert camelCase filter keys to snake_case."""
    if not filter_dict:
        return filter_dict
    mapping = {
        'minScore': 'min_score',
        'maxRiskLevel': 'max_risk_level',
        'topN': 'top_n',
    }
    result = {}
    for k, v in filter_dict.items():
        result[mapping.get(k, k)] = v
    return result


@pools_bp.route('/api/pools', methods=['POST'])
@inject
def create_pool(stock_pool_service):
    """创建股票池 - 使用依赖注入"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400

    name = data.get('name')
    pool_type = data.get('poolType') or data.get('pool_type')
    if not name or not pool_type:
        return jsonify({'success': False, 'error': 'name and poolType are required'}), 400

    # 校验筛选条件
    filter_template_raw = data.get('filterTemplate') or data.get('filter_template')
    if filter_template_raw and filter_template_raw.get('conditions'):
        try:
            validate_filter(filter_template_raw)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    try:
        pool = stock_pool_service.create_pool(
            name=name,
            pool_type=pool_type,
            symbols=data.get('symbols'),
            filter_template=_convert_filter_keys(filter_template_raw),
            refresh_interval=data.get('refreshInterval') or data.get('refresh_interval'),
            description=data.get('description'),
        )
        return jsonify({'success': True, 'data': pool}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Create pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools', methods=['GET'])
@inject
def list_pools(stock_pool_service):
    """列出所有股票池 - 使用依赖注入"""
    try:
        pools = stock_pool_service.list_pools()
        return jsonify({'success': True, 'data': pools})
    except Exception as e:
        logger.error(f"List pools failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>', methods=['GET'])
@inject
def get_pool(pool_id, stock_pool_service):
    """获取池子详情 - 使用依赖注入"""
    try:
        pool = stock_pool_service.get_pool(pool_id)
        if not pool:
            return jsonify({'success': False, 'error': 'Pool not found'}), 404
        return jsonify({'success': True, 'data': pool})
    except Exception as e:
        logger.error(f"Get pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# 注意：这是示例迁移代码，不要直接替换原文件
# 请逐步迁移每个路由函数，测试验证后再继续
