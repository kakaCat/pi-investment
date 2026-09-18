"""反复触发（噪音）判定与规则修复动作 —— domain 纯函数（REQ-c9f899 R6 / t8，2026-09-18）

为什么独立成模块（architecture.md §2）：级别判定 / 账户路由 / 终态校验 / **反复触发判定**
全部是 domain 纯函数，应用层只做编排与持久化——避免出现第二份真相。本模块只有数学与
白名单，**不读库、不读时钟**：时间（now / 交易日）与触发次数（来自 watch_triggers 的聚合）
一律由调用方注入。这样阈值边界可以用真值表单测，也不会出现"第二份时钟"（同一份统计在
不同进程/时区下给出不同结论）。

阈值（R6 要求「必须先于实施给出可证伪默认值」，默认值来自 design/test-cases.md §1）：

    ｜ 单日触发 ≥ 8 次（DEFAULT_MAX_TRIGGERS_PER_DAY）
    ｜ 或 连续 ≥ 3 日触发且日均 ≥ 4 次（DEFAULT_MIN_CONSECUTIVE_DAYS / DEFAULT_MIN_AVG_PER_DAY）

**阈值是模块常量且可被参数覆写**（每个判定函数的入参都带同名 keyword-only 覆盖项），
配置若要调整只改常量，不改判定逻辑。

判定口径（避免歧义，逐条可证伪）：
  · 单日条件只看今日计数，**不看**连续天数（一天爆量同样要抑噪）；
  · 连续条件要求「截至今日的连续触发段」长度 ≥ min_consecutive_days
    且该段内的日均 ≥ min_avg_per_day——**今天必须仍在触发**（连续段必须以今日结尾），
    否则视为"正在收敛"，不抑噪；
  · None / 非法输入按 0 处理（缺数据 ≠ 触发，绝不臆造触发）。

修复动作（REPAIR_ACTIONS，受账户授权约束；与 architecture.md §5 的修复枚举一一对应）：
延长冷却 / 调整阈值或方向 / 拆分规则 / 合并规则 / 退役。
另有 suppress / unsuppress 两个**抑噪态**动作（interfaces.md §1.2 的 change_kind 全集），
它们不是"修复"，只是临时改投递级别，故不在 REPAIR_ACTIONS 内。
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Mapping, Optional

# ── 默认阈值（模块常量，可被判定函数的 keyword-only 参数覆写）────────────────
#: 单日触发次数上限：≥ 此值即抑噪
DEFAULT_MAX_TRIGGERS_PER_DAY = 8
#: 连续触发天数门槛
DEFAULT_MIN_CONSECUTIVE_DAYS = 3
#: 连续触发段内的日均触发次数门槛
DEFAULT_MIN_AVG_PER_DAY = 4.0
#: 统计窗口（日）——连续天数的最大可观测长度，也是"连续"判定的回溯边界
DEFAULT_WINDOW_DAYS = 7
#: 自动抑噪时长（小时）：临时延长冷却（architecture §5-②，写 runtime 状态，不改静态配置）
DEFAULT_SUPPRESS_HOURS = 24

# ── 修复动作枚举（R6 / architecture §5）────────────────────────────────────
#: 可执行的规则修复动作全集（顺序 = 破坏性由轻到重）
REPAIR_ACTIONS = ('cooldown', 'threshold', 'split', 'merge', 'retire')

#: 每个修复动作的适用场景说明（写进服务 docstring / 审计 reason 的可读口径）
REPAIR_ACTION_SCENARIOS: Dict[str, str] = {
    'cooldown': '阈值合理但冷却太短：同一条件反复穿越，延长冷却即可压到可接受频率',
    'threshold': '阈值贴着市价：价格在阈值附近抖动导致反复触发，把阈值/方向调出噪音带',
    'split': '一条规则混杂多个条件/时段：拆分后各自独立冷却与分级，避免互相放大',
    'merge': '多条规则监控同一标的同一方向：合并为一条，避免同事件重复通知',
    'retire': '规则已失效（基本面/持仓/意图已不成立）：退役停用，保留审计可回溯',
}

#: 允许写入 quant.watch_rule_changes.change_kind 的全集
#: （data-model.md §4 列出的 7 个值 = REPAIR_ACTIONS + 抑噪态两动作）
CHANGE_KINDS = REPAIR_ACTIONS + ('suppress', 'unsuppress')


def _num(value: Any) -> float:
    """None / 非数值一律按 0（缺数据不是触发；绝不猜）"""
    if value is None or isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def should_suppress(trigger_today, consecutive_days, avg_per_day, *,
                    max_triggers_per_day: int = DEFAULT_MAX_TRIGGERS_PER_DAY,
                    min_consecutive_days: int = DEFAULT_MIN_CONSECUTIVE_DAYS,
                    min_avg_per_day: float = DEFAULT_MIN_AVG_PER_DAY) -> bool:
    """反复触发判定（纯函数）：是否应进入抑噪态。

    命中任一条件即为 True（先判单日，再判连续）：
      · 今日触发次数 >= max_triggers_per_day                       （默认 8）
      · 连续触发天数 >= min_consecutive_days 且 日均 >= min_avg_per_day（默认 3 日 / 4 次）

    边界（test-cases.md §1「自愈阈值」）：7 次不命中、8 次命中；连续 2 日不命中、
    连续 3 日且日均 ≥4 命中。None / 非法输入按 0 处理。
    """
    today = _num(trigger_today)
    if today >= _num(max_triggers_per_day):
        return True
    return (_num(consecutive_days) >= _num(min_consecutive_days)
            and _num(avg_per_day) >= _num(min_avg_per_day))


def noise_reason(trigger_today, consecutive_days, avg_per_day, *,
                 max_triggers_per_day: int = DEFAULT_MAX_TRIGGERS_PER_DAY,
                 min_consecutive_days: int = DEFAULT_MIN_CONSECUTIVE_DAYS,
                 min_avg_per_day: float = DEFAULT_MIN_AVG_PER_DAY) -> str:
    """抑噪理由（人读、可核验）：写清命中的是哪条判据与具体数值。

    审计（watch_rule_changes.reason）与待办说明共用同一份措辞，避免两处口径漂移。
    """
    today = _num(trigger_today)
    days = _num(consecutive_days)
    avg = _num(avg_per_day)
    if today >= _num(max_triggers_per_day):
        return (f'单日触发 {int(today)} 次 ≥ 阈值 {int(max_triggers_per_day)} 次，'
                f'触发规则自愈抑噪（R6）')
    return (f'连续 {int(days)} 日触发（日均 {avg:.1f} 次）≥ 阈值 '
            f'{int(min_consecutive_days)} 日 / 日均 {_num(min_avg_per_day):.1f} 次，'
            f'触发规则自愈抑噪（R6）')


def suppress_until(now: datetime, hours: float = DEFAULT_SUPPRESS_HOURS) -> datetime:
    """抑噪截止时刻（纯函数：**now 由调用方注入**，本模块不读时钟）。

    抑噪只改投递级别（architecture §5「不做的事」），不判定、不改规则静态配置；
    到期后规则自动恢复原级别。
    """
    return now + timedelta(hours=float(hours))


# ── 抑噪态判定（供触发摄入路径用：抑噪期内只进 P3 聚合、不建 todo）────────────
#: watch_rules.noise_state 的抑噪取值
NOISE_STATE_SUPPRESSED = 'suppressed'


def _wall_clock(value):
    """aware datetime → 去 tzinfo 的墙钟值（本仓 watch_rules 时间列是朴素本地时间）

    守卫只做"是否仍在抑噪期"的两值比较，不做时区换算；混入 aware 输入时按墙钟比较，
    **绝不抛 TypeError**（抑噪守卫抛错会连带阻断触发摄入，比误判更糟）。
    """
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def is_suppressed(noise_state, suppress_until, now: datetime) -> bool:
    """该规则此刻是否处于抑噪态（纯函数，now 由调用方注入）。

    语义（architecture.md §4/§5）：抑噪期内该规则产生的触发**不逐条投递、不建 todo**，
    只落 P3 聚合；抑噪只改投递级别，不改判定结果（真信号仍在聚合摘要里可见）。
    suppress_until 为空视为"一直抑噪"（保守）；到期即自动恢复原级别。
    """
    if str(noise_state or '').strip().lower() != NOISE_STATE_SUPPRESSED:
        return False
    if suppress_until is None:
        return True
    return _wall_clock(now) < _wall_clock(suppress_until)


# ── change_kind 白名单（服务用它做 400 校验；这里只给事实，不抛领域异常）─────

def is_repair_action(change_kind) -> bool:
    """是否属于「修复」动作（REPAIR_ACTIONS 五选一）"""
    return str(change_kind or '').strip().lower() in REPAIR_ACTIONS


def is_change_kind(change_kind) -> bool:
    """是否属于允许写入审计的 change_kind 全集（含 suppress/unsuppress）"""
    return str(change_kind or '').strip().lower() in CHANGE_KINDS


# ── 日聚合的纯计算（输入来自 watch_triggers 的按日计数，输出喂给 should_suppress）──

def _as_date(value: Any) -> Optional[date]:
    """date / datetime / 'YYYY-MM-DD' → date；无法解析返回 None（跳过而非猜）"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _normalized(daily_counts: Mapping[Any, Any]) -> Dict[date, int]:
    """把 {date|str: count} 归一为 {date: int}（非法键/值跳过）"""
    out: Dict[date, int] = {}
    for key, value in (daily_counts or {}).items():
        day = _as_date(key)
        if day is None:
            continue
        out[day] = int(_num(value))
    return out


def consecutive_active_days(daily_counts: Mapping[Any, Any], today: date) -> int:
    """截至 today 的连续触发天数（必须包含 today；today 无触发则为 0）

    "连续"以**自然日**递减计数，任何一天为 0（含缺失）即断：今天火但昨天断，
    连续天数是 1 —— 说明规则正在重新开始响，还不到"连续多日骚扰"。
    """
    counts = _normalized(daily_counts)
    if counts.get(today, 0) <= 0:
        return 0
    days = 0
    cursor = today
    while counts.get(cursor, 0) > 0:
        days += 1
        cursor = cursor - timedelta(days=1)
    return days


def average_per_active_day(daily_counts: Mapping[Any, Any], today: date,
                           consecutive_days: Optional[int] = None) -> float:
    """连续触发段内的日均触发次数（段长为 0 → 0.0）

    口径：**只用连续段内的天数做分母**（不含断档日、不含窗口内更早的孤立触发）。
    """
    counts = _normalized(daily_counts)
    days = (consecutive_active_days(counts, today)
            if consecutive_days is None else int(consecutive_days))
    if days <= 0:
        return 0.0
    total = 0
    cursor = today
    for _ in range(days):
        total += counts.get(cursor, 0)
        cursor = cursor - timedelta(days=1)
    return total / float(days)


def summarize(daily_counts: Mapping[Any, Any], today: date) -> Dict[str, Any]:
    """把按日计数汇总成判定输入 + 展示字段（纯函数）。

    返回：
      trigger_today    今日触发次数
      consecutive_days 截至今日的连续触发天数（>0 时必含今日）
      avg_per_day      连续段内日均
      active_days      窗口内**有触发**的天数（不等于连续天数，供排查"老是断档"）
      trigger_days     按日明细 [{date, count}]（升序），供 GET /noise 展示
    """
    counts = _normalized(daily_counts)
    consecutive = consecutive_active_days(counts, today)
    return {
        'trigger_today': int(counts.get(today, 0)),
        'consecutive_days': consecutive,
        'avg_per_day': round(average_per_active_day(counts, today, consecutive), 4),
        'active_days': sum(1 for value in counts.values() if value > 0),
        'trigger_days': [{'date': day.isoformat(), 'count': counts[day]}
                         for day in sorted(counts)],
    }
