"""标准 cron(0=周日) → APScheduler(0=周一) 的星期字段转换。

背景（2026-09-12 实证，w-c8cae280）
------------------------------------
APScheduler 的 CronTrigger.from_crontab 按 0=周一 … 6=周日 解释 DOW，
而本仓其余全部消费方都是标准 cron（0=周日 … 6=周六）：

  - infrastructure/scheduler/scheduler.py 的 parse_cron（0/7=周日，用于校验与 next_run_at）
  - scripts/scheduler_watchdog.py（croniter，tz=CST）
  - Agent OS 侧 robfig/cron（Go，0=周日）
  - 智能执行页检查点期望（expectDays/expectTime）
  - 人工书写习惯（* * 1-5 = 工作日）

实测后果（近三周 scheduler_runs）：cron '30 22 * * 1-5' 的「每日数据更新」实际跑在
周二~周六，周一一整天没有 v2 日线流水；'0 1 * * 0' 的「v13-weekly-report」实跑周一。
全部 23 个带 DOW 的 enabled 任务均错位一天，且被看门狗的「已排期豁免」静默掩盖。

结论：表达式以标准 cron 为准（库里存什么就该是什么意思），只在交给 APScheduler 的
那一步翻译 DOW。本模块是唯一翻译点。

注意：不转换的后果不是"早一天/晚一天"这么简单 —— 1-5 会从 {周一..周五} 变成
{周二..周六}，即周一整体缺失、周六反而执行。
"""
from __future__ import annotations

import logging
from typing import List

from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 标准 cron 星期编号：0/7=周日, 1=周一 … 6=周六
_STD_TO_NAME = {0: 'sun', 1: 'mon', 2: 'tue', 3: 'wed', 4: 'thu', 5: 'fri', 6: 'sat', 7: 'sun'}
_NAME_TO_STD = {'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6}
# APScheduler day_of_week 的规范顺序（0=mon）：输出用名字，避免两套数字再撞车
_APS_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


def _std_value(token: str) -> int:
    """把标准 cron 的单个星期记号转成 0..6（0=周日）。支持数字与英文缩写。"""
    t = token.strip().lower()
    if t in _NAME_TO_STD:
        return _NAME_TO_STD[t]
    v = int(t)
    if v == 7:
        return 0
    if not 0 <= v <= 6:
        raise ValueError(f"星期字段取值非法: {token!r}")
    return v


def _expand_dow(field: str) -> List[int]:
    """展开标准 cron 的 DOW 字段为 0..6（0=周日）升序列表。

    支持 * / a / a-b / a-b/n / */n / 逗号列表 / 英文缩写。
    区间跨周回绕（如 5-1）按 a..6 + 0..b 处理。
    """
    days = set()
    for raw in str(field).split(','):
        part = raw.strip()
        if not part:
            continue
        step = 1
        if '/' in part:
            part, _, step_s = part.partition('/')
            step = int(step_s)
            if step <= 0:
                raise ValueError(f"星期字段步长非法: {raw!r}")
            part = part.strip()
        if part in ('*', '?'):
            lo, hi = 0, 6
        elif '-' in part:
            a, _, b = part.partition('-')
            lo, hi = _std_value(a), _std_value(b)
        else:
            days.add(_std_value(part))
            continue
        rng = list(range(lo, hi + 1)) if lo <= hi else list(range(lo, 7)) + list(range(0, hi + 1))
        for v in rng:
            if (v - lo) % step == 0:
                days.add(v)
    if not days:
        raise ValueError(f"星期字段为空或无法解析: {field!r}")
    return sorted(days)


def convert_standard_dow(field: str) -> str:
    """标准 cron 的 DOW 字段 → APScheduler day_of_week 取值（英文名逗号串或 *）。"""
    if str(field).strip() in ('*', '?'):
        return '*'
    days = _expand_dow(field)
    names = {_STD_TO_NAME[d] for d in days}
    if len(names) == 7:
        return '*'
    return ','.join(n for n in _APS_ORDER if n in names)


def validate_cron(cron_expr: str) -> None:
    """校验 cron 表达式为标准的 **5 段**（分 时 日 月 周）。

    2026-09-13（w-32314d00，看板事件 435f0c0a / 26737737 / c488fdad）：
    任务行被写成 **6 段**（Agent OS / robfig-cron 风格，首位是秒）时，写入与任务注册都成功，
    直到 APScheduler 加载才抛 ValueError: Wrong number of fields; got 6, expected 5 ——
    表现是「任务根本没进调度器」：scheduler_runs 里查不到任何失败，只有一行加载日志。
    故把校验提前到写入点，并给出直指修法的错误信息。

    Raises:
        ValueError: 段数不为 5（Agent OS 托管伪任务 managed_by_agent_* 除外）。
    """
    expr = str(cron_expr or '').strip()
    if not expr:
        raise ValueError('cron 表达式为空')
    if expr.startswith('managed_by_agent_'):
        return  # Agent OS 托管伪任务：不参与 APScheduler 排期，加载阶段按托管跳过
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(
            f'cron 只接受 5 段（分 时 日 月 周），收到 {len(fields)} 段: {expr!r}'
            '；若来自 Agent OS（6 段、首位是秒），请去掉秒位后再写入')


def build_cron_trigger(cron_expr: str, tz: str = 'Asia/Shanghai') -> CronTrigger:
    """按标准 cron 语义构造 CronTrigger（仅翻译 DOW，其余字段原样透传）。

    非 5 段表达式不再「原样透传」（旧行为把 croniter 的短错误抛进加载日志，
    极易被当成无关警告略过），改为在这里显式拒绝。
    """
    validate_cron(cron_expr)
    if str(cron_expr).strip().startswith('managed_by_agent_'):
        raise ValueError(f'Agent OS 托管伪任务不应构造 APScheduler 触发器: {cron_expr!r}')
    minute, hour, dom, month, dow = str(cron_expr).split()
    return CronTrigger(
        minute=minute, hour=hour, day=dom, month=month,
        day_of_week=convert_standard_dow(dow), timezone=tz,
    )
