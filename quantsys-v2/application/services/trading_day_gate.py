"""交易日门（判据唯一真源）——REQ-261006093620-a315 · FR-1/FR-2/FR-5

## 为什么有本模块

交易日门原先只住在 `adapters/inbound/fastapi_app/daily_jobs/gate.py`，只服务 ③ DailyJobs 宿主；
② 库表调度（`infrastructure/scheduler/`，读 `quant.scheduler_tasks`）**没有任何门**——
2026-10-06（国庆休市·周二）09:25 实测 `pre-market-scan` 照常开火并记 `success`
（`task_id=250`、`run_id=3379`、129ms）。

若让 `infrastructure/` 直接 import 入站适配器，依赖方向就反了；故判据**上移到 application 层**
（本仓既有合法方向：`infrastructure/scheduler/scheduler.py` 早已 import `application.services.*`），
由两条调度路径共用**同一份**判据。`daily_jobs/gate.py` 退化为薄转发。

**判据只有一条，调用方不许各写一份**（那正是本仓反复踩的形态）。

## 策略（三值，来自需求 D-4/D-6）

| policy | 语义 |
|---|---|
| `always`（缺省） | 不判门，照跑——**行为与装门之前完全一致** |
| `trading-days` | 非交易日一律跳过（休市日 / 周末 / 未来） |
| `holidays` | **只跳法定节假日**（`source='trading-calendar-holiday'`），周末照跑 |

为什么不是布尔：`#232`（每日 00:00 数据质量检查）排班**含周末**，按 D-6 只跳法定节假日；
布尔无法同时表达"非交易日一律跳"与"只跳节假日"两档。

## fail-open（与钱路任务的 fail-closed 刻意相反）

`TradingDayGuard` 是 **fail-closed**（数据源异常 → 保守判非交易日），那是「钱路」任务要的语义。
本模块的收益只是「省一次无信息量的重算」，**绝不能换成一次静默停摆**，故取守：

    只有"日历明确答该跳过"才跳过；任何降级与自身异常 → **一律照跑**，并把 source/degraded 带出去。

未知 policy 同样 fail-open（按 `always` 照跑）并记 warning——**不静默、不跳过**。

## 判据口径（验收时最容易写反的一处）

本模块判的是**当天**（`now` 缺省 = `datetime.now()`），永不把"未来日期"喂给守卫。
`TradingDayGuard.check('2026-10-08')` 在 10-06 当天会返回 `source='future'` / `is_trading_day=False`
（写入型路径刻意保守）；**"复市首日不得跳过"的验收要用 `resolve_trading_day(d).date == d`**，
不要拿 `check(未来日)` 当判据——那会把好代码判成 bug。

## 用法

    from application.services.trading_day_gate import should_skip
    skip, info = should_skip('trading-days')     # ② 库表调度在执行期判定
    if skip:
        ...                                       # 写 skipped 留痕、不发通知

    ③ DailyJobs 继续用 skip_non_trading_day() / is_non_trading_day() / verdict_info()（签名未变）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import structlog

from application.services.trading_day_guard import (
    SOURCE_CALENDAR_HOLIDAY,
    TradingDayGuard,
)

logger = structlog.get_logger(__name__)

#: 门自身异常时的来源标注（与 TradingDayGuard 的 source 取值并列，便于排查）
SOURCE_GATE_ERROR = 'gate-error'

#: 策略取值（与 `quant.scheduler_tasks.trading_day_policy` 的 CHECK 约束同值域）
POLICY_ALWAYS = 'always'
POLICY_TRADING_DAYS = 'trading-days'
POLICY_HOLIDAYS = 'holidays'
KNOWN_POLICIES = frozenset({POLICY_ALWAYS, POLICY_TRADING_DAYS, POLICY_HOLIDAYS})


def _day_str(now: Optional[datetime]) -> str:
    """判定对象日的字符串形式（只用于留痕；取不到就退回今天）。"""
    try:
        return (now or datetime.now()).date().isoformat()
    except Exception:  # noqa: BLE001 - 留痕字段不许成为故障源
        return datetime.now().date().isoformat()


def _gate_error_info(now: Optional[datetime], error: BaseException) -> Dict[str, Any]:
    """门自身异常时的注解：**判「照跑」**（degraded=True ⇒ skip 恒为 False）。

    刻意与 `TradingDayGuard` 的 `unavailable` / `compute-error` 同形
    （`is_trading_day=False` + `degraded=True`），而不是谎报"今天是交易日"。
    """
    return {
        'day': _day_str(now),
        'is_trading_day': False,
        'source': SOURCE_GATE_ERROR,
        'degraded': True,
        'reason': f'交易日门自身异常（{type(error).__name__}: {error}）→ 按降级照跑'[:200],
    }


def verdict_info(now: Optional[datetime] = None) -> Dict[str, Any]:
    """取判定注解（五键：day / is_trading_day / source / degraded / reason）。**永不抛**。

    照跑路径也要用它——降级事实必须随任务 result 带出去。
    """
    try:
        verdict = TradingDayGuard.check(now)
        return {
            'day': verdict.day.isoformat(),
            'is_trading_day': bool(verdict.is_trading_day),
            'source': str(verdict.source),
            'degraded': bool(verdict.degraded),
            'reason': str(verdict.reason),
        }
    except Exception as e:  # noqa: BLE001 - 门的契约是"绝不抛"
        logger.warning('trading_day_gate_error', error=f'{type(e).__name__}: {e}')
        return _gate_error_info(now, e)


def should_skip(policy: Optional[str], now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]:
    """按策略判定"本次自动执行是否跳过"。返回 `(是否跳过, 判定注解)`。**永不抛**。

    - `always`（及缺省/未知值）→ `(False, info)`——未知值另带 `policy_unknown=True` + warning；
    - `trading-days` → 跳过 ⇔ `is_trading_day=False` **且** `degraded=False`；
    - `holidays` → 跳过 ⇔ `source == 'trading-calendar-holiday'` **且** `degraded=False`
      （降级时不跳：fail-open 优先于"只跳节假日"）。
    """
    try:
        info = verdict_info(now)
        effective = policy if policy in KNOWN_POLICIES else POLICY_ALWAYS
        if policy not in KNOWN_POLICIES:
            # 写库侧有 CHECK 约束；能读到未知值只剩"人工直改库/回滚到旧代码"，
            # 此时照跑（最坏 = 多跑一次）比跳过（静默停摆）安全。必须响亮留痕。
            logger.warning('trading_day_gate_policy_unknown', policy=str(policy))
            info = {
                **info,
                'policy_unknown': True,
                'reason': (
                    f'{info.get("reason", "")}；未知策略 {policy!r} → 按 always 照跑'
                )[:200],
            }

        if effective == POLICY_ALWAYS:
            return False, info

        not_trading = (not info['is_trading_day']) and (not info['degraded'])
        if effective == POLICY_TRADING_DAYS:
            return not_trading, info

        # POLICY_HOLIDAYS：只跳法定节假日，周末照跑
        is_holiday = str(info.get('source')) == SOURCE_CALENDAR_HOLIDAY
        return (is_holiday and (not info['degraded'])), info
    except Exception as e:  # noqa: BLE001 - 最后一道兜底：门不许成为可用性故障源
        logger.warning('trading_day_gate_error', error=f'{type(e).__name__}: {e}')
        return False, _gate_error_info(now, e)


def skip_non_trading_day(now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]:
    """③ 兼容入口：等价 `should_skip(POLICY_TRADING_DAYS, now)`。**永不抛**。"""
    return should_skip(POLICY_TRADING_DAYS, now)


def is_non_trading_day(now: Optional[datetime] = None) -> bool:
    """③ 兼容入口：局部跳过用（`_job_evening_pipeline` 的因子段）。永不抛。"""
    return should_skip(POLICY_TRADING_DAYS, now)[0]
