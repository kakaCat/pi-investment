"""判据 metric 契约（REQ-c9f899 t2，2026-09-18）

为什么需要：EvalResult.value 的语义此前没有类型，消费方各自假设——EscalationChecker
的量能路径把 price_break 的现价（388.5 元）当量比，产出「量能异常 388.5x」；同时把
真放量（volume_ratio=1.6）判成"未达阈值"。本模块是「读 value 前先声明期望 metric」的唯一入口：

  · require_metric —— 消费方承诺要看某类 metric 时使用；不符即抛
    WatchMetricContractViolation（响亮失败，不静默兜底）。
  · metric_matches —— 可选路径使用；不符返回 False，由调用方跳过该路径。

分层：只依赖 domain/watch/models 的 MetricKind，不反向依赖应用层。
"""
from typing import Iterable

from domain.watch.models import MetricKind, WatchMetricContractViolation


def metric_of(result) -> MetricKind:
    """取结果的 metric；缺失或非枚举一律视为 UNKNOWN（不猜测语义）"""
    metric = getattr(result, 'metric', None)
    if isinstance(metric, MetricKind):
        return metric
    return MetricKind.UNKNOWN


def metric_matches(result, allowed: Iterable[MetricKind]) -> bool:
    """宽松判定：结果 metric 是否属于 allowed（可选路径用）"""
    return metric_of(result) in set(allowed)


def require_metric(result, allowed: Iterable[MetricKind], where: str):
    """严格契约：消费方声明只看 allowed，否则响亮抛错。

    用法：读 result.value 当涨跌幅之前先 require_metric(result, {MetricKind.PCT_CHANGE}, '_check_anomaly')
    """
    allowed_set = set(allowed)
    actual = metric_of(result)
    if actual not in allowed_set:
        raise WatchMetricContractViolation(
            '%s 期望 metric ∈ %s，实际 %s（value=%r）——读 value 前必须先声明语义'
            % (where, sorted(m.value for m in allowed_set), actual.value,
               getattr(result, 'value', None)))
    return result
