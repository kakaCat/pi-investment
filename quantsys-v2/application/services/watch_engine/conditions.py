"""WatchEngine 条件判定器 —— 纯函数，无 I/O，无外部依赖

语义约定：
- direction 'above' → value >= threshold 触发；'below' → value <= threshold 触发
- velocity 无方向，取窗口内涨跌幅绝对值
- 百分数单位：3.0 表示 3%
- distance_ratio: 距触发的归一化距离（0=已触达），供引擎自适应频率升档；None=无法评估
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

VALID_TYPES = {'price_break', 'pct_change', 'pnl_pct', 'velocity', 'volume_surge'}

DEFAULT_COOLDOWN_SEC = 300


@dataclass
class EvalResult:
    triggered: bool
    value: Optional[float]
    distance_ratio: Optional[float]
    message: str


@dataclass
class EvalContext:
    cost_price: Optional[float] = None
    price_history: Tuple[Tuple[datetime, float], ...] = ()  # tuple[(datetime, price), ...]，按时间升序
    avg_volume_20d: Optional[float] = None
    elapsed_fraction: float = 1.0        # 当日已过交易时间比例 0~1


def validate_condition(cond: dict) -> None:
    """校验条件结构，非法时抛 ValueError"""
    ctype = cond.get('type')
    if ctype not in VALID_TYPES:
        raise ValueError(f'未知条件类型: {ctype}，支持: {sorted(VALID_TYPES)}')
    params = cond.get('params') or {}
    if ctype == 'price_break':
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
    """评估单个条件。quote 需有 .price，可选 .prev_close / .change_pct / .volume"""
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
        return EvalResult(False, None, None, '无均量或成交量数据')
    baseline = ctx.avg_volume_20d * min(1.0, max(ctx.elapsed_fraction, 0.01))
    ratio = float(quote.volume) / baseline
    multiple = float(params['multiple'])
    triggered = ratio >= multiple
    distance = 0.0 if triggered else max(0.0, (multiple - ratio) / multiple)
    return EvalResult(triggered, ratio, distance,
                      f'成交量为同期均量 {ratio:.2f}x（阈值 {multiple}x）')


_HANDLERS = {
    'price_break': _eval_price_break,
    'pct_change': _eval_pct_change,
    'pnl_pct': _eval_pnl_pct,
    'velocity': _eval_velocity,
    'volume_surge': _eval_volume_surge,
}
