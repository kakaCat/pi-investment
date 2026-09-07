"""
Data Provider Monitoring Module

提供 Prometheus 指标用于监控多数据源健康状态
"""
import logging
from typing import Dict, Any
from prometheus_client import Gauge, Counter, Histogram

logger = logging.getLogger(__name__)

# Provider 健康评分 (0-1)
provider_health_score = Gauge(
    'provider_health_score',
    'Provider health score based on success rate and consecutive failures',
    ['provider_name', 'provider_type']
)

# Provider 熔断器状态 (0=closed, 1=open, 2=half_open)
provider_circuit_breaker_state = Gauge(
    'provider_circuit_breaker_state',
    'Circuit breaker state: 0=closed, 1=open, 2=half_open',
    ['provider_name', 'provider_type']
)

# Provider 请求总数（按结果分类）
provider_request_total = Counter(
    'provider_request_total',
    'Total number of requests to provider',
    ['provider_name', 'provider_type', 'result']  # result: success/failure/timeout/circuit_open
)

# Provider 请求耗时分布
provider_request_duration_seconds = Histogram(
    'provider_request_duration_seconds',
    'Request duration in seconds',
    ['provider_name', 'provider_type'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 90.0, float('inf'))
)

# Provider 降级次数
provider_failover_total = Counter(
    'provider_failover_total',
    'Total number of failovers (provider skipped due to failure)',
    ['provider_name', 'provider_type', 'reason']  # reason: circuit_open/consecutive_failures/timeout
)

# 缓存命中率
cache_hit_total = Counter(
    'cache_hit_total',
    'Total number of cache hits',
    ['method']  # method: get_quote/get_klines/etc
)

cache_miss_total = Counter(
    'cache_miss_total',
    'Total number of cache misses',
    ['method']
)

# 缓存大小
cache_size = Gauge(
    'cache_size',
    'Current number of items in cache'
)

cache_utilization = Gauge(
    'cache_utilization',
    'Cache utilization ratio (0-1)'
)

# K线回填统计
kline_backfill_total = Counter(
    'kline_backfill_total',
    'Total number of kline backfill operations',
    ['symbol', 'result']  # result: success/failure
)

kline_backfill_rows = Counter(
    'kline_backfill_rows',
    'Total number of kline rows backfilled',
    ['symbol']
)


def get_circuit_breaker_state_value(state_name: str) -> int:
    """Convert circuit breaker state name to numeric value

    Args:
        state_name: State name from pybreaker (e.g., 'closed', 'open', 'half_open')

    Returns:
        0 for closed, 1 for open, 2 for half_open
    """
    state_map = {
        'closed': 0,
        'open': 1,
        'half_open': 2,
        'half-open': 2,  # Alternative spelling
    }

    # Handle pybreaker state objects
    if hasattr(state_name, 'name'):
        state_name = state_name.name

    state_str = str(state_name).lower().replace('_', '-')
    return state_map.get(state_str, 1)  # Default to open (safe default)


def calculate_health_score(stats: Dict[str, int]) -> float:
    """Calculate provider health score from statistics

    Args:
        stats: Provider statistics dict with 'success', 'failure', 'consecutive_failures'

    Returns:
        Health score between 0.0 and 1.0
    """
    success = stats.get('success', 0)
    failure = stats.get('failure', 0)
    consecutive_failures = stats.get('consecutive_failures', 0)
    total = success + failure

    if total == 0:
        return 0.5  # Neutral score for untested providers

    # Base score: success rate
    success_rate = success / total

    # Penalty for consecutive failures (max -0.5)
    failure_penalty = min(consecutive_failures / 10.0, 0.5)

    # Bonus for proven reliability (max +0.1)
    reliability_bonus = min(success / 20.0, 0.1)

    score = success_rate - failure_penalty + reliability_bonus
    return max(0.0, min(1.0, score))  # Clamp to [0, 1]


def get_provider_type(provider_name: str) -> str:
    """Determine provider type from provider name

    Args:
        provider_name: Provider name (e.g., 'tencent', 'database', 'akshare')

    Returns:
        Provider type string (e.g., 'quote', 'kline', 'financial')
    """
    # Quote providers
    if provider_name in ('tencent', 'sina', 'netease', 'eastmoney'):
        return 'quote'

    # Kline providers
    if provider_name in ('database', 'baostock'):
        return 'kline'

    # Multi-purpose providers
    if provider_name == 'akshare':
        return 'multi'  # akshare provides multiple data types

    # Default
    return 'unknown'
