"""WatchEngine 条件判定器 —— 纯函数，无 I/O，无外部依赖

语义约定：
- direction 'above' → value >= threshold 触发；'below' → value <= threshold 触发
- velocity 无方向，取窗口内涨跌幅绝对值
- 百分数单位：3.0 表示 3%
- distance_ratio: 距触发的归一化距离（0=已触达），供引擎自适应频率升档；None=无法评估
- combined: 复合条件，支持 AND/OR 组合，最大嵌套深度 3 层
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

from qs_watch.domain.watch.models import MetricKind
from qs_watch.domain.watch.services.market_rule_evaluator import (
    MARKET_CONDITION_TYPES, validate_market_condition,
)
from qs_watch.domain.watch.services.metric_contract import (  # noqa: F401 - 供消费侧复用同一契约
    metric_matches, metric_of, require_metric,
)

VALID_TYPES = {'price_break', 'pct_change', 'pnl_pct', 'velocity', 'volume_surge', 'combined',
               'staged_break'}

DEFAULT_COOLDOWN_SEC = 300
MAX_NESTING_DEPTH = 3

# ── 两段式伏击（staged_break，2026-10-19 P1）────────────────────────────
#: 触及后等待确认的默认观察窗（分钟）
DEFAULT_STAGED_WINDOW_MIN = 120
#: hold 确认的默认持续分钟数
DEFAULT_STAGED_HOLD_MIN = 30
STAGED_CONFIRM_KINDS = ('hold', 'reclaim', 'volume')

# ── 迟滞闩锁 + 每条件日上限（REQ-261016155500-4f2a wt:engine:1，2026-10-16）────────
#: price_break 触发后重新武装的迟滞带：h = max(0.5% × 阈值, 最小报价单位×5)。
#: 阈值附近的小幅反复穿越不再重新武装——治「跌穿后每 30 分钟复读一张卡」。
HYSTERESIS_PCT = 0.5          # 0.5%
MIN_HYSTERESIS_ABS = 0.05     # A 股最小报价单位 0.01 × 5
#: 每规则每条件每交易日的通知上限（超限只落库不通知）。
DEFAULT_DAILY_EMIT_CAP = 2


def _price_line_of(cond: dict) -> Tuple[Optional[float], Optional[str]]:
    """条件的「价格线」语义：(阈值, 方向)。price_break 取 params，staged_break 取 params.touch。

    两段式的触及线就是它的价格线——陈旧驻留判定与迟滞带对两者同口径。
    其它类型返回 (None, None)。
    """
    if not isinstance(cond, dict):
        return None, None
    ctype = cond.get('type')
    params = cond.get('params') or {}
    if ctype == 'price_break':
        src = params
    elif ctype == 'staged_break':
        src = params.get('touch') or {}
    else:
        return None, None
    threshold, direction = src.get('price'), src.get('direction')
    if threshold is None or direction not in ('above', 'below'):
        return None, None
    try:
        threshold = float(threshold)
    except (TypeError, ValueError):
        return None, None
    if threshold <= 0:
        return None, None
    return threshold, direction


def freshness_of(cond: dict, prev_close):
    """price_break/staged_break 触发是否「今日新鲜穿越」（2026-10-19 用户裁定：穿越 vs 驻留）。

    定义：昨收时条件尚不成立（未触及价格线）→ True（今日新穿越，有信息增量）；
    昨收已在触发侧 → False（陈旧驻留，零增量——它是规则失真信号不是市场事件）。
    无法判定返回 None（prev_close 缺失 / 无价格线类型）——调用方按既有行为处理。
    """
    threshold, direction = _price_line_of(cond)
    if threshold is None or prev_close is None:
        return None
    try:
        prev = float(prev_close)
    except (TypeError, ValueError):
        return None
    prev_triggered = prev >= threshold if direction == 'above' else prev <= threshold
    return not prev_triggered


def hysteresis_rearm_price(cond: dict):
    """price_break/staged_break 的重新武装边界（纯函数）。

    下破触发（price ≤ T）后：需回升到 T+h 以上才重新武装；上破触发（price ≥ T）
    后：需回落到 T-h 以下。无价格线类型 → None（维持「未触发即重新武装」的原语义）。
    staged_break 以其 touch 线为价格线。
    """
    threshold, direction = _price_line_of(cond)
    if threshold is None:
        return None
    h = max(threshold * HYSTERESIS_PCT / 100.0, MIN_HYSTERESIS_ABS)
    return threshold + h if direction == 'below' else threshold - h


def within_hysteresis_band(cond: dict, value) -> bool:
    """闩锁保持期间，value 是否仍在迟滞带内（带内 → 不重新武装，继续等）。

    仅在 hysteresis_rearm_price 有定义（price_break / staged_break）且 value 可解析时生效。
    """
    if value is None:
        return False
    rearm = hysteresis_rearm_price(cond)
    if rearm is None:
        return False
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    _t, direction = _price_line_of(cond)
    return value <= rearm if direction == 'below' else value >= rearm



@dataclass
class EvalResult:
    triggered: bool
    value: Optional[float]
    distance_ratio: Optional[float]
    message: str
    # 数据缺失无法评估（区别于正常未触发）。子条件 degraded 时不作为 False 阻断
    # 组合（fail-open），但组合触发会继承 degraded 标注，供下游知悉该触发未经完整验证。
    degraded: bool = False
    # 判据 metric（2026-09-18，REQ-c9f899 t2）：value 的语义由 metric 唯一确定。
    # 消费方读 value 前必须声明期望 metric（require_metric / metric_matches），
    # 否则「现价当量比」这类误读会再次发生（线上 19 条假「量能异常」）。
    metric: MetricKind = MetricKind.UNKNOWN
    unit: Optional[str] = None


@dataclass
class EvalContext:
    cost_price: Optional[float] = None
    price_history: Tuple[Tuple[datetime, float], ...] = ()  # tuple[(datetime, price), ...]，按时间升序
    avg_volume_20d: Optional[float] = None
    elapsed_fraction: float = 1.0        # 当日已过交易时间比例 0~1


def validate_condition(cond: dict, depth: int = 0) -> None:
    """校验条件结构，非法时抛 ValueError。支持递归校验 combined 类型。

    市场级类型（index_break/sector_pct/held_sector_pct 等）委托领域服务
    validate_market_condition——它们不进个股 DSL 的 VALID_TYPES，但 REST
    出入库校验不能缺位（2026-10-19 P2 前市场级规则无法经 API 创建）。

    Args:
        cond: 条件字典
        depth: 当前嵌套深度（防止无限递归）
    """
    if depth > MAX_NESTING_DEPTH:
        raise ValueError(f'条件嵌套深度超过限制（最大 {MAX_NESTING_DEPTH} 层）')

    ctype = cond.get('type')
    if ctype in MARKET_CONDITION_TYPES:
        validate_market_condition(cond)
        return
    if ctype not in VALID_TYPES:
        raise ValueError(f'未知条件类型: {ctype}，支持: {sorted(VALID_TYPES)}'
                         f'（市场级: {list(MARKET_CONDITION_TYPES)}）')
    
    params = cond.get('params') or {}
    
    if ctype == 'combined':
        # 复合条件校验
        operator = params.get('operator')
        if operator not in ('AND', 'OR'):
            raise ValueError('combined 需要 params.operator: AND|OR')
        
        conditions = params.get('conditions')
        if not isinstance(conditions, list):
            raise ValueError('combined 需要 params.conditions 为数组')
        if len(conditions) < 2:
            raise ValueError('combined 的 conditions 数组至少需要 2 个条件（单条件无需 combined）')
        
        # 递归校验每个子条件
        for i, subcond in enumerate(conditions):
            try:
                validate_condition(subcond, depth + 1)
            except ValueError as e:
                raise ValueError(f'combined 的第 {i+1} 个子条件无效: {e}')
    
    elif ctype == 'price_break':
        if 'price' not in params:
            raise ValueError('price_break 需要 params.price')
        if params['price'] <= 0:
            raise ValueError('price_break 的 price 必须为正数')
        if params.get('direction') not in ('above', 'below'):
            raise ValueError('price_break 需要 params.direction: above|below')
    elif ctype in ('pct_change', 'pnl_pct'):
        if 'pct' not in params:
            raise ValueError(f'{ctype} 需要 params.pct')
        if params.get('direction') not in ('above', 'below'):
            raise ValueError(f'{ctype} 需要 params.direction: above|below')
    elif ctype == 'velocity':
        if 'pct' not in params or 'window_min' not in params:
            raise ValueError('velocity 需要 params.pct 和 params.window_min')
        if params['pct'] <= 0:
            raise ValueError('velocity 的 pct 必须为正数')
        if params['window_min'] <= 0:
            raise ValueError('velocity 的 window_min 必须为正数')
    elif ctype == 'volume_surge':
        if 'multiple' not in params:
            raise ValueError('volume_surge 需要 params.multiple')
        if params['multiple'] <= 0:
            raise ValueError('volume_surge 的 multiple 必须为正数')
    elif ctype == 'staged_break':
        touch = params.get('touch') or {}
        if 'price' not in touch:
            raise ValueError('staged_break 需要 params.touch.price')
        if touch['price'] <= 0:
            raise ValueError('staged_break 的 touch.price 必须为正数')
        if touch.get('direction') not in ('above', 'below'):
            raise ValueError('staged_break 需要 params.touch.direction: above|below')
        confirm = params.get('confirm') or {}
        kind = confirm.get('kind')
        if kind not in STAGED_CONFIRM_KINDS:
            raise ValueError(f'staged_break 需要 params.confirm.kind: {STAGED_CONFIRM_KINDS}')
        if kind == 'hold':
            minutes = confirm.get('minutes', DEFAULT_STAGED_HOLD_MIN)
            if minutes <= 0:
                raise ValueError('staged_break hold 确认需要 confirm.minutes > 0')
        if kind == 'volume':
            if 'multiple' not in confirm or confirm['multiple'] <= 0:
                raise ValueError('staged_break volume 确认需要 confirm.multiple > 0')
        window_min = params.get('window_min', DEFAULT_STAGED_WINDOW_MIN)
        if window_min <= 0:
            raise ValueError('staged_break 的 window_min 必须为正数')


def evaluate(cond: dict, quote, ctx: EvalContext, now: Optional[datetime] = None) -> EvalResult:
    """评估单个条件（支持递归评估 combined）。quote 需有 .price，可选 .prev_close / .change_pct / .volume

    staged_break 不在此评估：它是有状态的两段式（触及→观察→确认），由引擎经
    StagedBreakManager 处理；直接 evaluate 会丢状态语义，故响亮拒绝。
    """
    ctype = cond['type']
    if ctype == 'staged_break':
        raise ValueError('staged_break 是有状态条件，需经 StagedBreakManager 评估（引擎 tick 内拦截）')
    if ctype not in _HANDLERS:
        raise ValueError(f'未知条件类型: {ctype}')
    params = cond.get('params') or {}
    handler = _HANDLERS[ctype]
    return handler(params, quote, ctx, now or datetime.now())


def _threshold_result(triggered: bool, value: float, threshold: float,
                      direction: str, message: str,
                      metric: MetricKind = MetricKind.UNKNOWN,
                      unit: Optional[str] = None) -> EvalResult:
    """统一构造 above/below 结果和距离（metric 显式声明 value 的语义）"""
    if triggered:
        distance = 0.0
    elif threshold == 0:
        distance = None
    elif direction == 'above':
        distance = max(0.0, (threshold - value) / abs(threshold))
    else:
        distance = max(0.0, (value - threshold) / abs(threshold))
    return EvalResult(triggered=triggered, value=value, distance_ratio=distance,
                      message=message, metric=metric, unit=unit)


def _eval_price_break(params, quote, ctx, now) -> EvalResult:
    price = float(quote.price)
    threshold = float(params['price'])
    direction = params['direction']
    triggered = price >= threshold if direction == 'above' else price <= threshold
    word = '上破' if direction == 'above' else '下破'
    return _threshold_result(triggered, price, threshold, direction,
                             f'现价 {price} {"≥" if direction == "above" else "≤"} 阈值 {threshold}（{word}）' if triggered
                             else f'现价 {price} 未{word} {threshold}',
                             metric=MetricKind.PRICE, unit='元')


def _eval_pct_change(params, quote, ctx, now) -> EvalResult:
    pct = None
    if getattr(quote, 'prev_close', None):
        pct = (float(quote.price) - float(quote.prev_close)) / float(quote.prev_close) * 100
    elif getattr(quote, 'change_pct', None) is not None:
        pct = float(quote.change_pct)
    if pct is None:
        return EvalResult(False, None, None, '无昨收数据，无法计算涨跌幅')
    threshold = float(params['pct'])
    direction = params['direction']
    triggered = pct >= threshold if direction == 'above' else pct <= threshold
    return _threshold_result(triggered, pct, threshold, direction,
                             f'涨跌幅 {pct:.2f}%（阈值 {direction} {threshold}%）',
                             metric=MetricKind.PCT_CHANGE, unit='%')


def _eval_pnl_pct(params, quote, ctx, now) -> EvalResult:
    if not ctx.cost_price:
        return EvalResult(False, None, None, '无成本价，无法计算盈亏')
    pnl = (float(quote.price) - ctx.cost_price) / ctx.cost_price * 100
    threshold = float(params['pct'])
    direction = params['direction']
    triggered = pnl >= threshold if direction == 'above' else pnl <= threshold
    return _threshold_result(triggered, pnl, threshold, direction,
                             f'盈亏 {pnl:.2f}%（成本 {ctx.cost_price}，阈值 {direction} {threshold}%）',
                             metric=MetricKind.PNL_PCT, unit='%')


def _eval_velocity(params, quote, ctx, now) -> EvalResult:
    window_min = float(params['window_min'])
    cutoff = now - timedelta(minutes=window_min)
    points = [(ts, p) for ts, p in ctx.price_history if ts >= cutoff]
    if not points:
        return EvalResult(False, None, None, f'窗口 {window_min}min 内无历史价格（冷启动）')
    base_price = float(points[0][1])
    if base_price <= 0:
        return EvalResult(False, None, None, '历史价格无效')
    change = abs((float(quote.price) - base_price) / base_price * 100)
    threshold = float(params['pct'])
    triggered = change >= threshold
    distance = 0.0 if triggered else max(0.0, (threshold - change) / threshold)
    return EvalResult(triggered, change, distance,
                      f'{window_min}min 内波动 {change:.2f}%（阈值 {threshold}%）',
                      metric=MetricKind.VELOCITY_PCT, unit='%')


def _eval_volume_surge(params, quote, ctx, now) -> EvalResult:
    if not ctx.avg_volume_20d or getattr(quote, 'volume', None) is None:
        # 数据缺失：不是"未放量"，而是"无法评估" → degraded，供组合 fail-open
        return EvalResult(False, None, None, '无均量或成交量数据，放量维度未评估',
                          degraded=True, metric=MetricKind.VOLUME_RATIO, unit='x')
    baseline = ctx.avg_volume_20d * min(1.0, max(ctx.elapsed_fraction, 0.01))
    ratio = float(quote.volume) / baseline
    multiple = float(params['multiple'])
    triggered = ratio >= multiple
    distance = 0.0 if triggered else max(0.0, (multiple - ratio) / multiple)
    return EvalResult(triggered, ratio, distance,
                      f'成交量为同期均量 {ratio:.2f}x（阈值 {multiple}x）',
                      metric=MetricKind.VOLUME_RATIO, unit='x')


def _eval_combined(params, quote, ctx, now) -> EvalResult:
    """复合条件评估器：递归评估子条件，按 operator 聚合结果。

    degraded 语义（数据缺失 ≠ 未触发）：
    - 子条件因数据缺失而 degraded（如 volume_surge 无均量）时，不以 False 阻断组合；
    - AND：至少 1 个可评估子条件且全部可评估子条件触发 → 组合触发；若存在 degraded
      子条件则组合继承 degraded 标注（⚠️ 部分维度未验证，供下游人工核验）；
      全部子条件都无法评估 → 不触发（不凭空报），仅标 degraded。
    - OR：任一可评估子条件真实触发 → 组合触发（真实触发不标 degraded）；
      无真实触发但存在 degraded 子条件 → 标 degraded（提示可能有漏判）。
    """
    operator = params['operator']  # AND / OR
    conditions = params['conditions']
    
    results = []
    for cond in conditions:
        result = evaluate(cond, quote, ctx, now)
        results.append(result)
    
    # 分离可评估与数据缺失（degraded）子条件
    evaluable = [r for r in results if not r.degraded]
    any_degraded = len(evaluable) < len(results)
    valid_distances = [r.distance_ratio for r in results if r.distance_ratio is not None]
    
    if operator == 'AND':
        if not evaluable:
            # 全部子条件数据缺失：不触发，标注 degraded（防凭空误报）
            distance = None
            triggered = False
            degraded = True
        else:
            triggered = all(r.triggered for r in evaluable)
            # AND: distance = 最远的子条件距离（瓶颈）；degraded 子条件无距离不参与
            distance = max(valid_distances) if valid_distances else None
            degraded = any_degraded and triggered
    else:  # OR
        triggered = any(r.triggered for r in evaluable)
        # OR: distance = 最近的子条件距离（最容易达到的）
        distance = min(valid_distances) if valid_distances else None
        degraded = any_degraded and not triggered
    
    # 组合消息：标注 degraded 子条件
    sep = ' 且 ' if operator == 'AND' else ' 或 '
    parts = []
    for r in results:
        parts.append(r.message + ('（数据缺失，未评估）' if r.degraded else ''))
    message = f'{operator} 组合：{sep.join(parts)}'
    if degraded and triggered:
        message += ' ⚠️ 部分维度数据缺失，本次触发未经完整验证，需人工核验'
    
    return EvalResult(triggered=triggered, value=None, distance_ratio=distance,
                      message=message, degraded=degraded, metric=MetricKind.COMPOSITE)


_HANDLERS = {
    'price_break': _eval_price_break,
    'pct_change': _eval_pct_change,
    'pnl_pct': _eval_pnl_pct,
    'velocity': _eval_velocity,
    'volume_surge': _eval_volume_surge,
    'combined': _eval_combined,
}


# ── staged_break 两段式伏击：无状态评估件（状态机在 StagedBreakManager）────
#
# 语义（2026-10-19 P1，用户裁定：盯盘是「守伏击点」，触及 ≠ 信号）：
#   触及 touch 线 → 进观察态（静默，不发卡不占日配额）；
#   观察窗内 confirm 满足 → 才作为真实触发进入正常流水线；
#   窗口到期未确认 → 归档一条 suppressed 样本（复盘用），回到待命。
# 这两个函数保持纯函数：状态（是否已触及、窗口截止）由调用方传入/持有。


def eval_staged_touch(cond: dict, quote) -> EvalResult:
    """触及判定：与 price_break 同语义，阈值/方向取自 params.touch。"""
    params = cond.get('params') or {}
    touch = params.get('touch') or {}
    return _eval_price_break({'price': touch['price'], 'direction': touch['direction']},
                             quote, None, None)


def eval_staged_confirm(cond: dict, quote, ctx: EvalContext, now: datetime,
                        touch_at: datetime) -> EvalResult:
    """确认判定（观察窗内每个 tick 调用一次）。

    kind:
      hold    —— 触及后价格在触发侧持续 confirm.minutes 分钟不回落（企稳）；
                 判定依据 ctx.price_history：窗内所有价格点都在触发侧且时长达标。
      reclaim —— 触及后价格收复阈值回到非触发侧（假摔收回）。
      volume  —— 观察窗内放量（复用 volume_surge 口径；数据缺失 degraded，不判死）。
    """
    params = cond.get('params') or {}
    touch = params.get('touch') or {}
    confirm = params.get('confirm') or {}
    kind = confirm['kind']
    threshold = float(touch['price'])
    direction = touch['direction']
    price = float(quote.price)

    if kind == 'reclaim':
        # 下破触及（≤T）后收复 = price > T；上破触及（≥T）后回落 = price < T
        reclaimed = price > threshold if direction == 'below' else price < threshold
        word = '收复' if direction == 'below' else '回落破'
        return _threshold_result(
            reclaimed, price, threshold,
            'above' if direction == 'below' else 'below',
            f'现价 {price} 已{word}触及线 {threshold}（reclaim 确认）' if reclaimed
            else f'现价 {price} 未{word}触及线 {threshold}',
            metric=MetricKind.PRICE, unit='元')

    if kind == 'volume':
        res = _eval_volume_surge({'multiple': confirm['multiple']}, quote, ctx, now)
        if res.triggered:
            res.message = f'观察窗内放量确认：{res.message}'
        return res

    # hold：持续 minutes 分钟不回落
    minutes = float(confirm.get('minutes', DEFAULT_STAGED_HOLD_MIN))
    points = [(ts, float(p)) for ts, p in (ctx.price_history or ()) if ts >= touch_at]
    on_side = (lambda v: v <= threshold) if direction == 'below' else (lambda v: v >= threshold)
    if points and not all(on_side(p) for _ts, p in points):
        # 窗内曾回落到非触发侧：企稳被破坏，确认不成立（状态机负责是否作废）
        return EvalResult(False, price, None,
                          f'观察窗内价格曾离开触发侧（阈值 {threshold}），企稳未成立',
                          metric=MetricKind.PRICE, unit='元')
    held_sec = (now - touch_at).total_seconds()
    triggered = held_sec >= minutes * 60 and on_side(price)
    return EvalResult(
        triggered, price,
        0.0 if triggered else max(0.0, 1.0 - held_sec / (minutes * 60)),
        f'触及侧已持续 {held_sec / 60:.1f}min（hold 确认需 {minutes:.0f}min）'
        + ('，企稳成立' if triggered else ''),
        metric=MetricKind.PRICE, unit='元')
