"""流动性核验服务：基于 quote 判定盘口正常 / 枯竭 / 大单诱骗（纯函数，无 I/O）。

为什么要有它：「放量突破」「大单进场」两类信号都可能被单方面伪造——成交额/量比
不足时挂着的大单是诱多话术；流动性枯竭的票即使触发价格线，真实成交也常被滑点
吃掉。本服务只回答一个问题：**这张盘口现在能不能承接**，输出 ``ok + reason``
供下游决定「这张卡值不值得发、这笔动作能不能做」。

判定口径（阈值全部可配；缺失/非法一律 skipped，绝不猜默认值）：

    阈值：min_amount            成交额下限（元）
          min_volume_ratio      量比下限
          trap_big_order_ratio  大单占比诱骗阈值（0<r≤1 为比例，1<r≤100 视为百分数）
    数据：amount / volume_ratio / big_order_ratio
          （支持常见别名，见 AMOUNT_KEYS / VOLUME_RATIO_KEYS / BIG_ORDER_RATIO_KEYS；
          接受 Mapping 或带同名属性的对象，如 QuoteData）

    skipped  ok=None   阈值未配置/非法，或 quote 缺字段/字段非法 —— 既非通过也非失败
    drained  ok=False  成交额或量比低于下限（盘口偏薄 / 缩量）→ 流动性枯竭
    trap     ok=False  大单占比达阈值，且成交额或量比同时偏弱 → 疑似大单诱骗
    normal   ok=True   成交额与量比均达标，且大单占比未达诱骗阈值（大单有量能配合也算正常）

判定顺序：trap 先于 drained —— 大单集中却量能不足，是「诱骗」而非单纯「枯竭」。
边界：一律「≥ 达标、< 不达标」，恰在阈值上算达标。
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    'BIG_ORDER_RATIO_KEYS',
    'AMOUNT_KEYS',
    'LiquidityCheckResult',
    'LiquidityCheckService',
    'LiquidityThresholds',
    'VERDICT_DRAINED',
    'VERDICT_LABELS',
    'VERDICT_NORMAL',
    'VERDICT_SKIPPED',
    'VERDICT_TRAP',
    'VOLUME_RATIO_KEYS',
    'check_liquidity',
]

# ── 判定结论 ──────────────────────────────────────────────────────────────
VERDICT_NORMAL = 'normal'
VERDICT_DRAINED = 'drained'
VERDICT_TRAP = 'trap'
VERDICT_SKIPPED = 'skipped'

VERDICT_LABELS = {
    VERDICT_NORMAL: '正常',
    VERDICT_DRAINED: '流动性枯竭',
    VERDICT_TRAP: '大单诱骗',
    VERDICT_SKIPPED: '数据不足',
}

# ── 行情字段别名（按优先级取第一个存在的字段）──────────────────────────────
AMOUNT_KEYS = ('amount', 'turnover', '成交额')
VOLUME_RATIO_KEYS = ('volume_ratio', 'vol_ratio', '量比')
BIG_ORDER_RATIO_KEYS = ('big_order_ratio', 'large_order_ratio', 'big_order_pct', '大单占比')

# ── 阈值配置别名 ───────────────────────────────────────────────────────────
_AMOUNT_FLOOR_KEYS = ('min_amount', 'amount_floor', '成交额下限')
_VOLUME_RATIO_FLOOR_KEYS = ('min_volume_ratio', 'volume_ratio_floor', '量比下限')
_TRAP_KEYS = ('trap_big_order_ratio', 'big_order_ratio_threshold', '大单占比阈值')


def _to_float(value: Any) -> Optional[float]:
    """尽力把数值/数值字符串转成 float；其它（含 bool、NaN、inf）一律 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _get(source: Any, keys: Iterable[str]) -> Any:
    """从 Mapping 或对象属性里按 keys 优先级取值；都没有返回 None。"""
    for key in keys:
        if isinstance(source, Mapping):
            if key in source:
                return source[key]
        elif hasattr(source, key):
            return getattr(source, key)
    return None


def _normalize_ratio(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """把大单占比归一到 0..1；≤1 视为比例，1<r≤100 视为百分数。

    返回 (归一值, 错误标记)。value 为 None → (None, None)（缺失，交由调用方报）。
    """
    number = _to_float(value)
    if number is None:
        return None, ('invalid' if value is not None else None)
    if 0.0 <= number <= 1.0:
        return number, None
    if 1.0 < number <= 100.0:
        return number / 100.0, None
    return None, 'invalid'


def _fmt_amount(value: float) -> str:
    if abs(value) >= 1e8:
        return '%.2f亿' % (value / 1e8)
    if abs(value) >= 1e4:
        return '%.0f万' % (value / 1e4)
    return '%.0f元' % value


def _fmt_pct(value: float) -> str:
    return '%.1f%%' % (value * 100.0)


@dataclass(frozen=True)
class LiquidityThresholds:
    """可配阈值。字段为 None = 未配置 → 核验如实 skipped（不猜默认值）。"""

    min_amount: Optional[float] = None
    min_volume_ratio: Optional[float] = None
    trap_big_order_ratio: Optional[float] = None

    @classmethod
    def from_mapping(cls, config: Optional[Mapping[str, Any]] = None) -> 'LiquidityThresholds':
        """从配置字典构造（支持中文键名别名）。"""
        if config is None:
            return cls()
        if not isinstance(config, Mapping):
            raise TypeError(
                'LiquidityThresholds.from_mapping 需要 Mapping，实际 %r'
                % (type(config).__name__,)
            )
        return cls(
            min_amount=_get(config, _AMOUNT_FLOOR_KEYS),
            min_volume_ratio=_get(config, _VOLUME_RATIO_FLOOR_KEYS),
            trap_big_order_ratio=_get(config, _TRAP_KEYS),
        )

    def validated(
        self,
    ) -> Tuple[Optional[Dict[str, float]], Tuple[Tuple[str, str], ...]]:
        """校验并归一阈值。

        返回 ``(可用的归一阈值, 问题清单)``：有问题时第一项为 None，
        问题清单形如 ``(('min_amount', '未配置'), ...)``，直接进 skipped 原因。
        """
        problems: List[Tuple[str, str]] = []

        amount = _to_float(self.min_amount)
        if self.min_amount is None:
            problems.append(('min_amount', '未配置'))
        elif amount is None or amount <= 0:
            problems.append(('min_amount', '非法（需为 > 0 的数值）'))

        volume_ratio = _to_float(self.min_volume_ratio)
        if self.min_volume_ratio is None:
            problems.append(('min_volume_ratio', '未配置'))
        elif volume_ratio is None or volume_ratio <= 0:
            problems.append(('min_volume_ratio', '非法（需为 > 0 的数值）'))

        trap_ratio, error = _normalize_ratio(self.trap_big_order_ratio)
        if self.trap_big_order_ratio is None:
            problems.append(('trap_big_order_ratio', '未配置'))
        elif error is not None or trap_ratio is None or trap_ratio <= 0:
            problems.append(
                ('trap_big_order_ratio', '非法（需为 0<r≤1 比例或 0<r≤100 百分数）')
            )

        if problems:
            return None, tuple(problems)
        return {
            'min_amount': amount,                    # type: ignore[dict-item]
            'min_volume_ratio': volume_ratio,        # type: ignore[dict-item]
            'trap_big_order_ratio': trap_ratio,      # type: ignore[dict-item]
        }, ()


@dataclass(frozen=True)
class _QuoteView:
    """从 quote 里抽出的核验所需字段（缺失项进 problems）。"""

    symbol: str = ''
    amount: Optional[float] = None
    volume_ratio: Optional[float] = None
    big_order_ratio: Optional[float] = None
    problems: Tuple[Tuple[str, str], ...] = ()


def _read_quote(quote: Any) -> _QuoteView:
    symbol_raw = _get(quote, ('symbol', 'code', 'ts_code'))
    symbol = str(symbol_raw).strip() if symbol_raw is not None else ''

    problems: List[Tuple[str, str]] = []

    amount = _to_float(_get(quote, AMOUNT_KEYS))
    if amount is None:
        problems.append(('amount', '缺失或非数值'))
    elif amount < 0:
        problems.append(('amount', '为负值'))

    volume_ratio = _to_float(_get(quote, VOLUME_RATIO_KEYS))
    if volume_ratio is None:
        problems.append(('volume_ratio', '缺失或非数值'))
    elif volume_ratio < 0:
        problems.append(('volume_ratio', '为负值'))

    raw_big = _get(quote, BIG_ORDER_RATIO_KEYS)
    big_order_ratio, error = _normalize_ratio(raw_big)
    if raw_big is None:
        problems.append(('big_order_ratio', '缺失或非数值'))
    elif error is not None:
        problems.append(('big_order_ratio', '非法（应为 0..1 比例或 0..100 百分数）'))

    return _QuoteView(
        symbol=symbol,
        amount=amount,
        volume_ratio=volume_ratio,
        big_order_ratio=big_order_ratio,
        problems=tuple(problems),
    )


@dataclass(frozen=True)
class LiquidityCheckResult:
    """核验结论。

    ``ok`` 是三态：True=正常通过，False=枯竭/诱骗，None=skipped（无法判定，
    绝不等于通过）。消费方直接 ``if result.ok`` 时 skipped 为假，不会被误当成放行。
    """

    symbol: str
    verdict: str
    ok: Optional[bool]
    reason: str
    amount: Optional[float] = None
    volume_ratio: Optional[float] = None
    big_order_ratio: Optional[float] = None
    missing: Tuple[str, ...] = ()

    @property
    def skipped(self) -> bool:
        return self.verdict == VERDICT_SKIPPED

    @property
    def label(self) -> str:
        return VERDICT_LABELS.get(self.verdict, self.verdict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'verdict': self.verdict,
            'label': self.label,
            'ok': self.ok,
            'skipped': self.skipped,
            'reason': self.reason,
            'amount': self.amount,
            'volume_ratio': self.volume_ratio,
            'big_order_ratio': self.big_order_ratio,
            'missing': list(self.missing),
        }


def _coerce_thresholds(value: Any) -> LiquidityThresholds:
    if isinstance(value, LiquidityThresholds):
        return value
    if value is None:
        return LiquidityThresholds()
    if isinstance(value, Mapping):
        return LiquidityThresholds.from_mapping(value)
    raise TypeError(
        '阈值需为 LiquidityThresholds / Mapping / None，实际 %r'
        % (type(value).__name__,)
    )


class LiquidityCheckService:
    """盘口流动性核验（无状态；阈值可构造时给，也可逐次覆盖）。"""

    def __init__(self, thresholds: Any = None) -> None:
        self._thresholds = _coerce_thresholds(thresholds)

    @classmethod
    def from_config(cls, config: Optional[Mapping[str, Any]] = None) -> 'LiquidityCheckService':
        """从配置字典构造（键名同 LiquidityThresholds.from_mapping）。"""
        return cls(config)

    @property
    def thresholds(self) -> LiquidityThresholds:
        return self._thresholds

    def check(self, quote: Any, thresholds: Any = None) -> LiquidityCheckResult:
        """核验单条 quote，返回 ok+reason（skipped 时 ok=None）。"""
        active = self._thresholds if thresholds is None else _coerce_thresholds(thresholds)
        values, threshold_problems = active.validated()
        view = _read_quote(quote)

        problems = list(threshold_problems) + list(view.problems)
        if problems:
            return self._skipped(view, threshold_problems, view.problems)

        min_amount = values['min_amount']
        min_volume_ratio = values['min_volume_ratio']
        trap_ratio = values['trap_big_order_ratio']

        weak: List[str] = []
        if view.amount < min_amount:
            weak.append(
                '成交额 %s < 下限 %s'
                % (_fmt_amount(view.amount), _fmt_amount(min_amount))
            )
        if view.volume_ratio < min_volume_ratio:
            weak.append(
                '量比 %.2f < 下限 %.2f' % (view.volume_ratio, min_volume_ratio)
            )

        big_order_hot = view.big_order_ratio >= trap_ratio

        if weak and big_order_hot:
            reason = (
                '疑似大单诱骗：大单占比 %s ≥ 阈值 %s，但%s（大单无真实承接，勿追）'
                % (
                    _fmt_pct(view.big_order_ratio),
                    _fmt_pct(trap_ratio),
                    '、'.join(weak),
                )
            )
            verdict = VERDICT_TRAP
        elif weak:
            reason = '流动性枯竭：%s（盘口偏薄或缩量，难以按预期价承接）' % '；'.join(weak)
            verdict = VERDICT_DRAINED
        else:
            healthy = '成交额 %s ≥ 下限 %s，量比 %.2f ≥ 下限 %.2f' % (
                _fmt_amount(view.amount),
                _fmt_amount(min_amount),
                view.volume_ratio,
                min_volume_ratio,
            )
            if big_order_hot:
                reason = (
                    '盘口正常：%s；大单占比 %s ≥ 诱骗阈值 %s，但有成交额/量能配合，'
                    '判为真实大单'
                    % (healthy, _fmt_pct(view.big_order_ratio), _fmt_pct(trap_ratio))
                )
            else:
                reason = (
                    '盘口正常：%s，大单占比 %s < 诱骗阈值 %s'
                    % (healthy, _fmt_pct(view.big_order_ratio), _fmt_pct(trap_ratio))
                )
            verdict = VERDICT_NORMAL

        return LiquidityCheckResult(
            symbol=view.symbol,
            verdict=verdict,
            ok=verdict == VERDICT_NORMAL,
            reason=reason,
            amount=view.amount,
            volume_ratio=view.volume_ratio,
            big_order_ratio=view.big_order_ratio,
        )

    def check_many(
        self, quotes: Iterable[Any], thresholds: Any = None
    ) -> List[LiquidityCheckResult]:
        """批量核验（逐条独立，不因一条 skipped 影响其它）。"""
        return [self.check(quote, thresholds=thresholds) for quote in quotes]

    @staticmethod
    def _skipped(
        view: _QuoteView,
        threshold_problems: Tuple[Tuple[str, str], ...],
        quote_problems: Tuple[Tuple[str, str], ...],
    ) -> LiquidityCheckResult:
        clauses: List[str] = []
        if threshold_problems:
            clauses.append(
                '阈值：' + '；'.join('%s %s' % p for p in threshold_problems)
            )
        if quote_problems:
            clauses.append('行情：' + '；'.join('%s %s' % p for p in quote_problems))
        reason = (
            '未判定（skipped）：%s —— 缺阈值/缺数据时不猜默认值、不判为通过'
            % '；'.join(clauses)
        )
        missing = tuple(name for name, _ in threshold_problems + quote_problems)
        return LiquidityCheckResult(
            symbol=view.symbol,
            verdict=VERDICT_SKIPPED,
            ok=None,
            reason=reason,
            amount=view.amount,
            volume_ratio=view.volume_ratio,
            big_order_ratio=view.big_order_ratio,
            missing=missing,
        )


def check_liquidity(quote: Any, thresholds: Any = None) -> LiquidityCheckResult:
    """便捷入口：一次性核验（无需复用服务实例时用）。"""
    return LiquidityCheckService(thresholds).check(quote)
