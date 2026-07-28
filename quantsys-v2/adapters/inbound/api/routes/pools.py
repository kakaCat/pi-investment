"""Stock pool management API routes."""
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

pools_bp = Blueprint('pools', __name__)

# Lazy imports to avoid circular dependencies at module level.
_stock_pool_service = None
_pool_validation_service = None

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


def _get_services():
    global _stock_pool_service, _pool_validation_service
    if _stock_pool_service is None:
        from adapters.inbound.api.shared import stock_pool_service, pool_validation_service
        _stock_pool_service = stock_pool_service
        _pool_validation_service = pool_validation_service
    return _stock_pool_service, _pool_validation_service


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
def create_pool():
    svc, _ = _get_services()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400

    name = data.get('name')
    pool_type = data.get('poolType') or data.get('pool_type')
    if not name or not pool_type:
        return jsonify({'success': False, 'error': 'name and poolType are required'}), 400

    # 新增：校验筛选条件（在转换之前）
    filter_template_raw = data.get('filterTemplate') or data.get('filter_template')
    if filter_template_raw and filter_template_raw.get('conditions'):
        try:
            validate_filter(filter_template_raw)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    try:
        pool = svc.create_pool(
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
def list_pools():
    svc, _ = _get_services()
    try:
        pools = svc.list_pools()
        return jsonify({'success': True, 'data': pools})
    except Exception as e:
        logger.error(f"List pools failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>', methods=['GET'])
def get_pool(pool_id):
    svc, _ = _get_services()
    try:
        pool = svc.get_pool(pool_id)
        return jsonify({'success': True, 'data': pool})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Get pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>', methods=['PUT'])
def update_pool(pool_id):
    svc, _ = _get_services()
    data = request.get_json() or {}
    try:
        pool = svc.update_pool(
            pool_id,
            name=data.get('name'),
            symbols=data.get('symbols'),
            description=data.get('description'),
        )
        return jsonify({'success': True, 'data': pool})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Update pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>', methods=['DELETE'])
def delete_pool(pool_id):
    svc, _ = _get_services()
    try:
        svc.delete_pool(pool_id)
        return jsonify({'success': True, 'message': f'Pool {pool_id} deleted'})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Delete pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/refresh', methods=['POST'])
def refresh_pool(pool_id):
    svc, _ = _get_services()
    try:
        pool = svc.refresh_pool(pool_id)
        return jsonify({'success': True, 'data': pool})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Refresh pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/sync-stock-names', methods=['POST'])
def sync_stock_names(pool_id):
    svc, _ = _get_services()
    try:
        pool = svc.sync_stock_names(pool_id)
        return jsonify({'success': True, 'data': pool})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Sync stock names failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/members/<symbol>', methods=['PUT'])
def update_member(pool_id, symbol):
    """更新池子中单个成员的详细信息"""
    svc, _ = _get_services()
    data = request.get_json() or {}
    try:
        pool = svc.update_member(
            pool_id=pool_id,
            symbol=symbol,
            member_data={
                'description': data.get('description'),
                'buy_point': data.get('buyPoint') or data.get('buy_point'),
                'sell_point': data.get('sellPoint') or data.get('sell_point'),
                'tags': data.get('tags', [])
            }
        )
        return jsonify({'success': True, 'data': pool})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Update member failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/members', methods=['POST'])
def add_members(pool_id):
    """批量添加池子成员（幂等：已在池中的跳过）"""
    svc, _ = _get_services()
    data = request.get_json() or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return jsonify({'success': False, 'error': 'symbols must be a non-empty array'}), 400
    try:
        result = svc.add_members(
            pool_id=pool_id,
            symbols=symbols,
            member_data={
                'description': data.get('description'),
                'buy_point': data.get('buyPoint') or data.get('buy_point'),
                'sell_point': data.get('sellPoint') or data.get('sell_point'),
                'tags': data.get('tags', [])
            }
        )
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Add members failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/members', methods=['DELETE'])
def remove_members(pool_id):
    """批量移除池子成员（幂等：不在池中的跳过）"""
    svc, _ = _get_services()
    data = request.get_json() or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return jsonify({'success': False, 'error': 'symbols must be a non-empty array'}), 400
    try:
        result = svc.remove_members(pool_id=pool_id, symbols=symbols)
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Remove members failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/validate', methods=['POST'])
def validate_pool(pool_id):
    _, val_svc = _get_services()
    data = request.get_json() or {}
    try:
        result = val_svc.validate_pool(
            pool_id=pool_id,
            strategy_ids=data.get('strategyIds') or data.get('strategy_ids'),
            start_date=data.get('startDate') or data.get('start_date'),
            end_date=data.get('endDate') or data.get('end_date'),
        )
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Validate pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/scan-and-create', methods=['POST'])
def scan_and_create():
    svc, _ = _get_services()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400

    name = data.get('name')
    pool_type = data.get('poolType') or data.get('pool_type')
    filter_params = data.get('filter') or data.get('filterTemplate') or data.get('filter_template')

    if not name or not pool_type or not filter_params:
        return jsonify({'success': False, 'error': 'name, poolType, and filter are required'}), 400

    # 新增：校验筛选条件
    logger.info(f"filter_params: {filter_params}")
    if filter_params and filter_params.get('conditions'):
        logger.info(f"Validating conditions: {filter_params.get('conditions')}")
        try:
            validate_filter(filter_params)
        except ValueError as e:
            logger.error(f"Validation failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
    else:
        logger.info("No conditions to validate")

    try:
        pool = svc.create_from_scan(
            name=name,
            pool_type=pool_type,
            scan_params=_convert_filter_keys(filter_params),
            refresh_interval=data.get('refreshInterval') or data.get('refresh_interval'),
            description=data.get('description'),
        )
        return jsonify({'success': True, 'data': pool}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Scan and create failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/scan-signals', methods=['POST'])
def scan_pool_signals(pool_id):
    """扫描股票池的实时买卖信号"""
    from adapters.inbound.api.shared import stock_pool_service
    from application.services.pool_signal_scanner import PoolSignalScanner
    from adapters.outbound.repositories import KlineORMRepository
    from adapters.outbound.repositories import StrategyORMRepository
    
    data = request.get_json() or {}
    strategy_id = data.get('strategy_id') or data.get('strategyId')
    lookback_days = data.get('lookback_days') or data.get('lookbackDays') or 60
    
    if not strategy_id:
        return jsonify({'success': False, 'error': 'strategy_id is required'}), 400

    try:
        # 使用stock_pool_service获取股票池
        pool = stock_pool_service._pool_repo.get_pool(pool_id)
        if not pool:
            return jsonify({'success': False, 'error': f'Pool {pool_id} not found'}), 404

        symbols = pool.get('symbols', [])
        if not symbols:
            return jsonify({'success': False, 'error': 'Pool is empty'}), 400

        # 创建扫描器（repositories自动连接数据库）
        kline_repo = KlineORMRepository()
        strategy_repo = StrategyORMRepository()
        scanner = PoolSignalScanner(kline_repo, strategy_repo)

        # 执行扫描
        result = scanner.scan_pool_signals(
            symbols=symbols,
            strategy_id=strategy_id,
            lookback_days=lookback_days
        )

        # 保存扫描结果
        stock_pool_service._pool_repo.update_signal_scan(pool_id, result)

        return jsonify({'success': True, 'data': result})
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Scan pool signals failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
