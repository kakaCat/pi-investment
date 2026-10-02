"""模型训练门控与资源释放辅助

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_common import logger  # noqa: F401

RETRAIN_MIN_AGE_DAYS = 6.5

RETRAIN_MIN_ACCURACY = 0.55

def _release_thread_session() -> None:
    """释放当前线程的 ORM 会话（归还连接池）；失败不抛。

    2026-09-11（w-f4aa1f6a）：get_session() 取的是线程本地 scoped session，
    任务线程若无 close_session()，该会话会一直占用连接。session_guard 实测
    model_train_auto 任务路径上会话被持有 311 秒（age_seconds=311，事件 a6780ec3），
    是 v2 DB 连接池健康度被打满（utilization 100%，事件 ed7d2f6a）的来源之一。
    """
    try:
        from infrastructure.persistence.orm.config import close_session
        close_session()
    except Exception as e:  # 释放失败不应影响任务本身
        logger.debug(f"release thread session failed: {e}")


def _model_age_days(train_date_str):
    """模型年龄（天）；train_date 缺失或无法解析 → None（调用方按“需重训”处理）

    train_date 来自 timestamptz 列（psycopg 返回 tz-aware +08:00），与 naive
    datetime.now() 直接相减会抛 TypeError（2026-09-05 实证）→ 统一为本地 aware 再算。
    """
    if not train_date_str:
        return None
    try:
        import pandas as pd

        train_date = pd.to_datetime(train_date_str)
        now_local = datetime.now().astimezone()
        if train_date.tzinfo is None:
            train_date = train_date.tz_localize(now_local.tzinfo)  # naive 视为本地墙钟
        train_date = train_date.to_pydatetime().astimezone()  # 统一为本地 aware
        return (now_local - train_date).total_seconds() / 86400.0
    except Exception as e:
        logger.warning(f"模型 train_date 解析失败（按需重训处理）: {train_date_str!r}: {e}")
        return None


def _age_needs_retrain(age_days) -> bool:
    """年龄是否已达重训阈值（纯函数：便于按时间轴推演节律、便于测试）

    age_days=None（缺 train_date / 无法解析）按“需重训”处理。
    """
    return age_days is None or age_days >= RETRAIN_MIN_AGE_DAYS


def _check_train_needed(model_type: str) -> tuple:
    """检查是否需要训练

    判定顺序（REQ-a458a6 t1）：
      · 无模型 / 无元数据 / train_date 缺失或不可解析 → 训练
      · 实际年龄 ≥ RETRAIN_MIN_AGE_DAYS 天 → 训练
      · test_accuracy < RETRAIN_MIN_ACCURACY → 训练
      · 否则跳过（reason 带实际年龄、阈值与准确率，便于复核）
    """
    from adapters.shared.ml_helpers import _get_model_repo, _resolve_latest_version
    
    latest_version = _resolve_latest_version(model_type)
    if not latest_version:
        return (True, "无可用模型")
    
    repo = _get_model_repo()
    model = repo.get_by_type_version(model_type, latest_version)
    # 2026-09-11（w-f4aa1f6a）：本函数是 model_train_auto 的最早步骤（此前无待写事务），
    # get_by_type_version 返回 plain dict（无惰性加载），读完即可安全归还会话，
    # 避免训练全程占住连接（详见 _release_thread_session 注释）
    _release_thread_session()
    if not model:
        return (True, "模型元数据缺失")
    
    train_date_str = model.get('train_date')
    age_days = _model_age_days(train_date_str)
    if age_days is None:
        # 2026-09-14（REQ-a458a6 t1）：原实现把整段年龄判断放在 `if train_date_str:` 内，
        # train_date 为空时 days_old 从未赋值却在函数末尾 f-string 中被引用 →
        # UnboundLocalError（任务以异常结束，连 reason 都拿不到）。改为显式判定。
        return (True, f"模型{latest_version}缺 train_date 元数据，按需重训")

    if _age_needs_retrain(age_days):
        return (True, f"模型已{age_days:.1f}天未更新（阈值{RETRAIN_MIN_AGE_DAYS}天）")

    test_acc = model.get('test_accuracy')
    if test_acc and test_acc < RETRAIN_MIN_ACCURACY:
        return (True, f"模型性能低 (test_acc={test_acc:.4f} < {RETRAIN_MIN_ACCURACY})")

    acc_txt = f"{test_acc:.4f}" if test_acc is not None else "N/A"
    return (False, f"模型{latest_version}仍有效 (age={age_days:.1f}d < {RETRAIN_MIN_AGE_DAYS}d, acc={acc_txt})")


