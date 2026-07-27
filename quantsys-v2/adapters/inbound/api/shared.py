"""
API 共享工具模块 - 新版本

使用ServiceFactory替代全局单例，提供向后兼容的接口

迁移状态：✅ 已完成重构
"""
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import jsonify, request
from infrastructure.services.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

# ── 服务实例（使用工厂模式） ──

# 向后兼容：保持原有的变量名，但使用工厂获取实例
@property
def ds():
    """DataService实例（延迟初始化）"""
    return ServiceFactory.get_data_service()


@property
def strategy_service():
    """StrategyCodeService实例（延迟初始化）"""
    return ServiceFactory.get_strategy_code_service()


@property
def stock_pool_service():
    """StockPoolService实例（延迟初始化）"""
    return ServiceFactory.get_stock_pool_service()


@property
def scoring_service():
    """OpportunityScoringService实例（延迟初始化）"""
    return ServiceFactory.get_scoring_service()


@property
def stock_scoring_service():
    """StockScoringService实例（延迟初始化）"""
    return ServiceFactory.get_stock_scoring_service()


@property
def sector_rotation_service():
    """SectorRotationService实例（延迟初始化）"""
    return ServiceFactory.get_sector_rotation_service()


@property
def pool_validation_service():
    """PoolValidationService实例（延迟初始化）"""
    return ServiceFactory.get_pool_validation_service()


# 直接实例化（向后兼容）
ds = ServiceFactory.get_data_service()
strategy_service = ServiceFactory.get_strategy_code_service()
stock_pool_service = ServiceFactory.get_stock_pool_service()
scoring_service = ServiceFactory.get_scoring_service()
stock_scoring_service = ServiceFactory.get_stock_scoring_service()
sector_rotation_service = ServiceFactory.get_sector_rotation_service()
pool_validation_service = ServiceFactory.get_pool_validation_service()

# Repository实例
from adapters.outbound.repositories import StockPoolORMRepository, StrategyORMRepository
pool_repo = StockPoolORMRepository()
strategy_repository = StrategyORMRepository()

# 因子适配器
from domain.quantlib.adapters import get_factor_adapter
factor_adapter = get_factor_adapter()


# 导出服务供 routes 使用
__all__ = [
    'ds',
    'strategy_service',
    'stock_pool_service',
    'pool_repo',
    'pool_validation_service',
    'factor_adapter',
    'scoring_service',
    'stock_scoring_service',
    'sector_rotation_service',
    'strategy_repository',
    'ServiceFactory',
]

# ── 后台任务并发控制（已解耦到中立层，向后兼容再导出，保证跨框架共享同一任务锁） ──

from adapters.shared.tasks import (
    _running_tasks,
    _task_lock,
    acquire_task,
    release_task,
    get_running_tasks,
)


# ── 通用工具函数 ──

def _safe_float(value, default=0.0, decimals=None):
    """安全转换为浮点数"""
    if value is None:
        return default
    try:
        result = float(value)
        return round(result, decimals) if decimals is not None else result
    except (ValueError, TypeError):
        return default


def success_response(data: Any = None, message: str = "Success") -> Dict:
    """成功响应"""
    return {
        'success': True,
        'message': message,
        'data': data
    }


def error_response(message: str, code: int = 500, data: Any = None) -> tuple:
    """错误响应"""
    return jsonify({
        'success': False,
        'message': message,
        'data': data
    }), code


def validate_required_params(params: List[str]) -> Optional[tuple]:
    """验证必需参数

    Args:
        params: 必需参数列表

    Returns:
        如果缺少参数，返回错误响应；否则返回None
    """
    data = request.get_json() or {}
    missing = [p for p in params if p not in data]
    if missing:
        return error_response(f"Missing required parameters: {', '.join(missing)}", 400)
    return None


def parse_date_param(param_name: str, default: Optional[str] = None) -> Optional[str]:
    """解析日期参数

    Args:
        param_name: 参数名
        default: 默认值

    Returns:
        日期字符串
    """
    value = request.args.get(param_name, default)
    if value:
        try:
            # 验证日期格式
            datetime.strptime(value, '%Y-%m-%d')
            return value
        except ValueError:
            logger.warning(f"Invalid date format for {param_name}: {value}")
            return default
    return default


def parse_int_param(param_name: str, default: int = 0, min_value: Optional[int] = None) -> int:
    """解析整数参数

    Args:
        param_name: 参数名
        default: 默认值
        min_value: 最小值限制

    Returns:
        整数值
    """
    try:
        value = int(request.args.get(param_name, default))
        if min_value is not None and value < min_value:
            return min_value
        return value
    except (ValueError, TypeError):
        return default


def parse_bool_param(param_name: str, default: bool = False) -> bool:
    """解析布尔参数

    Args:
        param_name: 参数名
        default: 默认值

    Returns:
        布尔值
    """
    value = request.args.get(param_name, '').lower()
    if value in ('true', '1', 'yes'):
        return True
    elif value in ('false', '0', 'no'):
        return False
    return default


# ── 装饰器 ──

def async_task(func):
    """异步任务装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        task_type = func.__name__
        run_id = str(uuid.uuid4())

        if not acquire_task(task_type, run_id):
            return error_response(f"Task {task_type} is already running", 409)

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            release_task(task_type, run_id)

    return wrapper


def require_params(*param_names):
    """必需参数装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            error = validate_required_params(list(param_names))
            if error:
                return error
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ── JSON序列化工具 ──

def sanitize_for_json(obj):
    """递归清理对象，使其可以被JSON序列化"""
    import pandas as pd
    import numpy as np
    import math

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    if isinstance(obj, (np.integer, np.floating)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj.item()

    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {
            sanitize_for_json(k) if not isinstance(k, str) else k: sanitize_for_json(v)
            for k, v in obj.items()
        }

    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]

    if hasattr(obj, 'isoformat'):
        return obj.isoformat()

    return obj


# ── 命名转换工具 ──

def to_camel_case(snake_str: str) -> str:
    """将蛇形命名转换为驼峰命名"""
    if not isinstance(snake_str, str):
        return snake_str
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def to_snake_case(camel_str: str) -> str:
    """将驼峰命名转换为蛇形命名"""
    import re
    if not isinstance(camel_str, str):
        return camel_str
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()


def convert_keys_to_camel(obj: Any) -> Any:
    """递归将字典的key转换为驼峰命名"""
    import pandas as pd

    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str):
                new_key = to_camel_case(k)
            elif isinstance(k, pd.Timestamp):
                new_key = k.isoformat()
            elif hasattr(k, 'isoformat'):
                new_key = k.isoformat()
            else:
                new_key = str(k)
            result[new_key] = convert_keys_to_camel(v)
        return result
    elif isinstance(obj, list):
        return [convert_keys_to_camel(item) for item in obj]
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


def convert_keys_to_snake(obj: Any) -> Any:
    """递归将字典的key转换为蛇形命名"""
    import pandas as pd

    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str):
                new_key = to_snake_case(k)
            elif isinstance(k, pd.Timestamp):
                new_key = k.isoformat()
            elif hasattr(k, 'isoformat'):
                new_key = k.isoformat()
            else:
                new_key = str(k)
            result[new_key] = convert_keys_to_snake(v)
        return result
    elif isinstance(obj, list):
        return [convert_keys_to_snake(item) for item in obj]
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


def api_response(data: Any, success: bool = True, message: str = None) -> Dict:
    """标准API响应格式"""
    response = {
        'success': success,
        'data': convert_keys_to_camel(sanitize_for_json(data))
    }
    if message:
        response['message'] = message
    return jsonify(response)


def handle_api_error(f):
    """API错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except KeyError as e:
            return jsonify({'success': False, 'error': f'缺少参数: {e}'}), 400
        except Exception as e:
            import traceback
            import sys
            print("="*80, file=sys.stderr)
            print("API ERROR TRACEBACK:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("="*80, file=sys.stderr)
            sys.stderr.flush()
            logger.error(f"API错误: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'服务器内部错误: {e}'}), 500
    return decorated_function


# ── 向后兼容的路径和工具函数 ──

from pathlib import Path

# 路径常量
_V2_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_PROJECT_ROOT_PATH = _V2_ROOT.parent
_LEGACY_QUANT_ROOT = _PROJECT_ROOT_PATH / 'quant'


def _safe_float(value, default=0.0):
    """安全转换为浮点数"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def get_running_tasks_snapshot():
    """获取运行中任务快照（向后兼容）"""
    return get_running_tasks()


def get_query_params_snake_case():
    """获取请求参数并转换为蛇形命名"""
    params = request.args.to_dict()
    return convert_keys_to_snake(params)


# ── Pipeline 运行管理（向后兼容） ──

_PIPELINE_RUNS_FILE = _V2_ROOT / 'data' / 'pipeline_runs.json'


def _load_pipeline_runs():
    """加载 pipeline 运行记录"""
    if not _PIPELINE_RUNS_FILE.exists():
        return []
    try:
        with open(_PIPELINE_RUNS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载 pipeline 运行记录失败: {e}")
        return []


def _save_pipeline_runs(runs):
    """保存 pipeline 运行记录"""
    try:
        _PIPELINE_RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_PIPELINE_RUNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(runs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存 pipeline 运行记录失败: {e}")


def _get_pipeline_run(run_id):
    """获取指定的 pipeline 运行记录"""
    runs = _load_pipeline_runs()
    for run in runs:
        if run.get('run_id') == run_id:
            return run
    return None


def _update_pipeline_run(run_id, updates):
    """更新 pipeline 运行记录"""
    runs = _load_pipeline_runs()
    for run in runs:
        if run.get('run_id') == run_id:
            run.update(updates)
            _save_pipeline_runs(runs)
            return True
    return False


# ── Watchlist 管理（向后兼容） ──

_WATCHLIST_FILE = _V2_ROOT / '.pi-invest' / 'watchlist.json'


def _read_watchlist():
    """读取自选股列表"""
    if not _WATCHLIST_FILE.exists():
        return {'items': []}
    try:
        with open(_WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 兼容旧格式：如果是列表，转换为字典格式
            if isinstance(data, list):
                return {'items': data}
            return data
    except Exception as e:
        logger.error(f"读取自选股列表失败: {e}")
        return {'items': []}


def _write_watchlist(watchlist):
    """写入自选股列表"""
    try:
        _WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写入自选股列表失败: {e}")


def _read_groups():
    """读取分组配置"""
    groups_file = _V2_ROOT / 'data' / 'groups.json'
    if not groups_file.exists():
        return {}
    try:
        with open(groups_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取分组配置失败: {e}")
        return {}


def _write_groups(groups):
    """写入分组配置"""
    groups_file = _V2_ROOT / 'data' / 'groups.json'
    try:
        groups_file.parent.mkdir(parents=True, exist_ok=True)
        with open(groups_file, 'w', encoding='utf-8') as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写入分组配置失败: {e}")


# ── 行情解析（向后兼容） ──

def _parse_sina_a_quote(data):
    """解析新浪 A 股行情数据"""
    return {
        'symbol': data.get('symbol', ''),
        'name': data.get('name', ''),
        'price': _safe_float(data.get('price')),
        'change': _safe_float(data.get('change')),
        'change_pct': _safe_float(data.get('change_pct')),
        'volume': _safe_float(data.get('volume')),
        'amount': _safe_float(data.get('amount')),
    }


def _parse_sina_hk_quote(data):
    """解析新浪港股行情数据"""
    return {
        'symbol': data.get('symbol', ''),
        'name': data.get('name', ''),
        'price': _safe_float(data.get('price')),
        'change': _safe_float(data.get('change')),
        'change_pct': _safe_float(data.get('change_pct')),
        'volume': _safe_float(data.get('volume')),
        'amount': _safe_float(data.get('amount')),
    }


def enrich_stock_data(stock_data):
    """丰富股票数据（向后兼容）"""
    return stock_data


def signal_to_opportunity(signal):
    """将信号转换为机会（向后兼容）"""
    return signal


# ── K线聚合函数（向后兼容） ──

def _aggregate_weekly(klines):
    """将日K线聚合为周K线"""
    import pandas as pd
    if not klines:
        return []
    
    df = pd.DataFrame(klines)
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
    
    weekly = df.resample('W').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'amount': 'sum',
    }).dropna()
    
    weekly.reset_index(inplace=True)
    return weekly.to_dict('records')


def _aggregate_monthly(klines):
    """将日K线聚合为月K线"""
    import pandas as pd
    if not klines:
        return []
    
    df = pd.DataFrame(klines)
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
    
    monthly = df.resample('M').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'amount': 'sum',
    }).dropna()
    
    monthly.reset_index(inplace=True)
    return monthly.to_dict('records')
