"""每日任务通知判据（REQ-261006165125-23a9 · FR-1/FR-2/FR-4/FR-6/FR-7）

为什么单独一个模块：通知决策原先散在 `runtime._run_job` 的三处（开始 / 完成 / 失败）里，
各自判断"这条要不要发"；要立一条**通用**规则（"本次没有事情发生 → 开始与完成两条都不发"），
就必须有一个**唯一判据入口**——否则以后新增一种"无事"取值，得在三个分支里各改一遍，
且很容易改漏（2026-10-06 用户实证：`event_calendar_check` 连续 4 天 `no_event`，每天照发 2 条）。

本模块是**纯函数**：不碰 DB、不起线程、不发消息。判断"发不发"的只有这里。
真正的"怎么发"在 `alerting`（文案）与 `runtime`（时机）。

设计依据：docs/requirements/REQ-261006165125-23a9/design/interfaces.md §1。
"""

from __future__ import annotations

import os
from typing import Any

#: 环境变量：置真 = 恢复旧行为（无事也发两条），用于一键回滚（FR-7）
ENV_NOTIFY_NOOP = 'DAILY_JOBS_NOTIFY_NOOP'
#: 环境变量：任务超过该秒数仍未结束 → 发一条「⏳ 仍在运行」（FR-3）；<=0 = 关闭该提示
ENV_RUNNING_NOTICE_SECONDS = 'DAILY_JOBS_RUNNING_NOTICE_SECONDS'

#: 「本次没有事情发生」的 status 白名单（FR-1）。
#: 只放**明确的空结果**；新增取值必须回 design 阶段登记，不许就地加字符串——
#: 判宽了会静默掉真产出（设计 R4）。
NO_OP_STATUSES: frozenset[str] = frozenset({'no_event', 'no_op'})

#: 超阈值提示的默认阈值（秒）
RUNNING_NOTICE_DEFAULT_SECONDS: float = 60.0


def is_no_op(result: Any) -> bool:
    """本次运行是否"没有事情发生"（FR-1）。

    命中二者之一即为真：
      ① `result['no_output'] is True`（**严格** is True：`1` / `'true'` 都不算，见反向锁 T-1）；
      ② `result['status']` 是字符串且去空白小写后落在 `NO_OP_STATUSES`。

    其余**一律 False**：非 dict（含字符串/列表）、未知 status、缺键、`status` 非字符串。
    取向是"宁多一条、不漏一条"——默认外发。
    """
    if not isinstance(result, dict):
        return False
    if result.get('no_output') is True:
        return True
    status = result.get('status')
    if isinstance(status, str) and status.strip().lower() in NO_OP_STATUSES:
        return True
    return False


def notify_noop_enabled() -> bool:
    """旧行为开关（FR-7 回滚口）：真 = 恢复"开始必发 + 完成必发（零产出 ⚠️ 语气）"。

    语义与同包 `interval._env_flag` 一致（`1/true/yes/on`，忽略大小写与首尾空白）；
    未设或其它值 → False（新行为）。坏值不得抛异常。
    """
    from adapters.inbound.fastapi_app.daily_jobs.interval import _env_flag
    return _env_flag(ENV_NOTIFY_NOOP, False)


def running_notice_seconds() -> float:
    """「⏳ 仍在运行」提示的阈值（秒）（FR-3/FR-7）。

    未设 / 空白 / 非数 → 默认 60 秒；`<= 0` → 0.0，表示**显式关闭**该提示
    （0 不是"立刻发"：`runtime._arm_running_notice` 对 `<= 0` 直接不 arm timer）。
    坏值不得抛异常。
    """
    raw = os.getenv(ENV_RUNNING_NOTICE_SECONDS)
    if raw is None or not str(raw).strip():
        return RUNNING_NOTICE_DEFAULT_SECONDS
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return RUNNING_NOTICE_DEFAULT_SECONDS
    if value <= 0:
        return 0.0
    return value


def should_send_start() -> bool:
    """是否在任务开始时就发「▶️ 每日任务开始」（FR-7 回滚口）。

    只有回滚态（`DAILY_JOBS_NOTIFY_NOOP=true`）才为真；默认 False——
    默认路径下"开始消息"由 `runtime._arm_running_notice` 的**超阈值提示**承担（FR-3）。
    人工触发也不发开始消息（只在结束时回一条带「（人工触发）」的完成消息，见 FR-6）。
    """
    return notify_noop_enabled()


def should_send_completion(*, result: Any, manual: bool = False) -> bool:
    """是否发「每日任务完成」消息（FR-2 / FR-6 / FR-7）。

    优先级（从上到下）：
      ① `manual=True` → True（人工触发的运行必须有回执，否则"点了没反应"）；
      ② 回滚态开关打开 → True（旧行为：完成必发）；
      ③ `is_no_op(result)` → **False**（本次核心：无事不发）；
      ④ 否则 → True（有产出照发）。

    **失败不经过本函数**：调用方在调它之前已用 `find_result_failure` + `try/except` 分流
    （失败一律照发，FR-4）——这里不做失败判定，避免出现第二套失败口径。
    """
    if manual:
        return True
    if notify_noop_enabled():
        return True
    return not is_no_op(result)
