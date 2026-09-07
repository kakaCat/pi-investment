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

VALID_TYPES = {'price_break', 'pct_change', 'pnl_pct', 'velocity', 'volume_surge', 'combined'}

DEFAULT_COOLDOWN_SEC = 300
MAX_NESTING_DEPTH = 3


@dataclass
class EvalResult:
    triggered: bool
    value: Optional[float]
    distance_ratio: Optional[float]
    message: str
    # 数据缺失无法评估（区别于正常未触发）。子条件 degraded 时不作为 False 阻断
    # 组合（fail-open），但组合触发会继承 degraded 标注，供下游知悉该触发未经完整验证。
    degraded: bool = False


@dataclass
class EvalContext:
    cost_price: Optional[float] = None
    price_history: Tuple[Tuple[datetime, float], ...] = ()  # tuple[(datetime, price), ...]，按时间升序
    avg_volume_20d: Optional[float] = None
    elapsed_fraction: float = 1.0        # 当日已过交易时间比例 0~1


def validate_condition(cond: dict, depth: int = 0) -> None:
    """校验条件结构，非法时抛 ValueError。支持递归校验 combined 类型。
    
    Args:
        cond: 条件字典
        depth: 当前嵌套深度（防止无限递归）
    """
    if depth > MAX_NESTING_DEPTH:
        raise ValueError(f'条件嵌套深度超过限制（最大 {MAX_NESTING_DEPTH} 层）')
    
    ctype = cond.get('type')
    if ctype not in VALID_TYPES:
        raise ValueError(f'未知条件类型: {ctype}，支持: {sorted(VALID_TYPES)}')
    
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


def evaluate(cond: dict, quote, ctx: EvalContext, now: Optional[datetime] = None) -> EvalResult:
    """评估单个条件（支持递归评估 combined）。quote 需有 .price，可选 .prev_close / .change_pct / .volume"""
    ctype = cond['type']
    if ctype not in _HANDLERS:
        raise ValueError(f'未知条件类型: {ctype}')
    params = cond.get('params') or {}
    handler = _HANDLERS[ctype]
    return handler(params, quote, ctx, now or datetime.now())


def _threshold_result(triggered: bool, value: float, threshold: float,
                      direction: str, message: str) -> EvalResult:
    """统一构造 above/below 结果和距离"""
    if triggered:
        distance = 0.0
    elif threshold == 0:
        distance = None
    elif direction == 'above':
        distance = max(0.0, (threshold - value) / abs(threshold))
    else:
        distance = max(0.0, (value - threshold) / abs(threshold))
    return EvalResult(triggered=triggered, value=value, distance_ratio=distance, message=message)


def _eval_price_break(params, quote, ctx, now) -> EvalResult:
    price = float(quote.price)
    threshold = float(params['price'])
    direction = params['direction']
    triggered = price >= threshold if direction == 'above' else price <= threshold
    word = '上破' if direction == 'above' else '下破'
    return _threshold_result(triggered, price, threshold, direction,
                             f'现价 {price} {"≥" if direction == "above" else "≤"} 阈值 {threshold}（{word}）' if triggered
                             else f'现价 {price} 未{word} {threshold}')


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
                             f'涨跌幅 {pct:.2f}%（阈值 {direction} {threshold}%）')


def _eval_pnl_pct(params, quote, ctx, now) -> EvalResult:
    if not ctx.cost_price:
        return EvalResult(False, None, None, '无成本价，无法计算盈亏')
    pnl = (float(quote.price) - ctx.cost_price) / ctx.cost_price * 100
    threshold = float(params['pct'])
    direction = params['direction']
    triggered = pnl >= threshold if direction == 'above' else pnl <= threshold
    return _threshold_result(triggered, pnl, threshold, direction,
                             f'盈亏 {pnl:.2f}%（成本 {ctx.cost_price}，阈值 {direction} {threshold}%）')


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
                      f'{window_min}min 内波动 {change:.2f}%（阈值 {threshold}%）')


def _eval_volume_surge(params, quote, ctx, now) -> EvalResult:
    if not ctx.avg_volume_20d or getattr(quote, 'volume', None) is None:
        # 数据缺失：不是"未放量"，而是"无法评估" → degraded，供组合 fail-open
        return EvalResult(False, None, None, '无均量或成交量数据，放量维度未评估', degraded=True)
    baseline = ctx.avg_volume_20d * min(1.0, max(ctx.elapsed_fraction, 0.01))
    ratio = float(quote.volume) / baseline
    multiple = float(params['multiple'])
    triggered = ratio >= multiple
    distance = 0.0 if triggered else max(0.0, (multiple - ratio) / multiple)
    return EvalResult(triggered, ratio, distance,
                      f'成交量为同期均量 {ratio:.2f}x（阈值 {multiple}x）')


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
                      message=message, degraded=degraded)


_HANDLERS = {
    'price_break': _eval_price_break,
    'pct_change': _eval_pct_change,
    'pnl_pct': _eval_pnl_pct,
    'velocity': _eval_velocity,
    'volume_surge': _eval_volume_surge,
    'combined': _eval_combined,
}
