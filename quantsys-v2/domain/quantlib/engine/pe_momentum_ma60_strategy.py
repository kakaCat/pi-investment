"""
PE价值+动量+MA60止损策略 (PE + Momentum + MA60 Stop Strategy)

结合价值因子（PE）和动量因子（60日涨幅）的混合策略，MA60 作为趋势止损线。

评分逻辑（回测用多股排名）:
  Score = rank(1/PE) × 50% + rank(60日涨幅) × 50%
  筛选: 负债率 < 70%
  选股: Top 20 等权，月度调仓
  风控: 收盘价 < MA60 → 止损

单股信号逻辑（strategy_execute 用）:
  买入: PE < 30 AND 60日动量 > 0 AND 收盘价 > MA60 AND 负债率 < 70%
  卖出: 收盘价 < MA60（止损触发）OR (PE > 60 AND 动量 < -5%)
  持有: 其余情况

因子说明:
  - PE 价值: 低 PE = 估值合理/便宜，使用 PE < 30 作为价值阈值
  - 60日动量: 近60个交易日价格涨跌幅，> 0 表示中期趋势向上
  - MA60 止损: 收盘价跌破 60 日均线 → 趋势可能转向，触发止损
  - 负债率过滤: 负债率 ≥ 70% → 财务风险偏高，不放买入信号

Author: QuantSys V2
Date: 2026-05-29
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import logging

from domain.quantlib.engine.strategy_base import StrategyBase

logger = logging.getLogger(__name__)


class PEMomentumMA60Strategy(StrategyBase):
    """
    PE价值+动量+MA60止损策略

    默认参数:
        pe_threshold: 30           — PE 低于此值视为价值区间
        pe_danger: 60              — PE 高于此值视为高估危险区
        momentum_period: 60        — 动量计算周期（交易日）
        ma_period: 60              — 均线周期（止损用）
        debt_threshold: 70.0       — 负债率上限（%）
        buy_momentum_min: 0.0      — 买入最低动量要求（%）
        sell_momentum_max: -5.0    — 卖出动量阈值（%），动量低于此且高PE触发卖出
    """

    DEFAULT_PARAMS = {
        'pe_threshold': 30,
        'pe_danger': 60,
        'momentum_period': 60,
        'ma_period': 60,
        'debt_threshold': 70.0,
        'buy_momentum_min': 0.0,
        'sell_momentum_max': -5.0,
    }

    PARAM_SCHEMA = {
        'pe_threshold': {
            'type': 'number', 'min': 5, 'max': 100, 'default': 30,
            'description': 'PE 低于此值视为价值区间'
        },
        'pe_danger': {
            'type': 'number', 'min': 20, 'max': 200, 'default': 60,
            'description': 'PE 高于此值视为高估危险区'
        },
        'momentum_period': {
            'type': 'integer', 'min': 10, 'max': 250, 'default': 60,
            'description': '动量计算周期（交易日）'
        },
        'ma_period': {
            'type': 'integer', 'min': 10, 'max': 250, 'default': 60,
            'description': '均线周期（止损用）'
        },
        'debt_threshold': {
            'type': 'number', 'min': 0, 'max': 100, 'default': 70.0,
            'description': '负债率上限（%）'
        },
        'buy_momentum_min': {
            'type': 'number', 'min': -50, 'max': 50, 'default': 0.0,
            'description': '买入最低动量要求（%）'
        },
        'sell_momentum_max': {
            'type': 'number', 'min': -50, 'max': 50, 'default': -5.0,
            'description': '卖出动量阈值（%）'
        },
    }

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据 PE + 动量 + MA60 生成交易信号

        Args:
            klines: K线数据列表，每个元素含 trade_date, open, high, low, close, volume
            params: 策略参数，可包含:
                - pe: 当前 PE(TTM)，不传则只依赖技术面
                - debt_ratio: 当前负债率(%)，不传则跳过负债率过滤
                - 以及 DEFAULT_PARAMS 中的所有参数

        Returns:
            信号字典:
            {
                'action': 'buy' | 'sell' | 'hold',
                'confidence': 0.0 ~ 1.0,
                'reason': str,
                'risk_management': {...},   # buy/sell 时包含
                'indicators': {...}         # 技术指标值
            }
        """
        if params is None:
            params = {}

        # --- 解析参数 ---
        pe = params.get('pe')  # 可选: 当前 PE(TTM)
        debt_ratio = params.get('debt_ratio')  # 可选: 当前负债率(%)
        pe_threshold = float(params.get('pe_threshold', self.DEFAULT_PARAMS['pe_threshold']))
        pe_danger = float(params.get('pe_danger', self.DEFAULT_PARAMS['pe_danger']))
        momentum_period = int(params.get('momentum_period', self.DEFAULT_PARAMS['momentum_period']))
        ma_period = int(params.get('ma_period', self.DEFAULT_PARAMS['ma_period']))
        debt_threshold = float(params.get('debt_threshold', self.DEFAULT_PARAMS['debt_threshold']))
        buy_momentum_min = float(params.get('buy_momentum_min', self.DEFAULT_PARAMS['buy_momentum_min']))
        sell_momentum_max = float(params.get('sell_momentum_max', self.DEFAULT_PARAMS['sell_momentum_max']))

        # --- 数据校验 ---
        min_required = max(momentum_period, ma_period) + 1
        self._validate_klines(klines, min_length=min_required)
        closes = self._extract_closes(klines)
        current_close = closes[-1]

        # --- 计算技术指标 ---
        # 60日动量: (当前价 - N日前价) / N日前价 × 100
        momentum = self._calc_momentum(closes, momentum_period)

        # MA60
        ma_values = self._calculate_ma(closes, ma_period)
        ma = ma_values[-1]

        # --- 风控：MA60 止损（最高优先级） ---
        if current_close < ma:
            # 止损触发
            stop_loss = self._build_stop_loss_percent(
                entry_price=current_close,
                percent=0.08,
                direction='long'
            )
            return {
                'action': 'sell',
                'confidence': min(0.95, 0.75 + abs(momentum) / 20),
                'reason': (
                    f'收盘价 {current_close:.2f} < MA{ma_period}({ma:.2f})，'
                    f'跌破 {((ma - current_close) / ma * 100):.1f}%，趋势止损触发。'
                    f'动量 {momentum:.1f}%'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                },
                'indicators': {
                    'close': round(current_close, 2),
                    f'ma{ma_period}': round(ma, 2),
                    f'momentum_{momentum_period}d': round(momentum, 2),
                    'pe': pe,
                    'debt_ratio': debt_ratio,
                }
            }

        # --- 卖出：高PE + 弱动量 ---
        if pe is not None and pe > pe_danger and momentum < sell_momentum_max:
            return {
                'action': 'sell',
                'confidence': 0.65,
                'reason': (
                    f'PE({pe:.1f}) > {pe_danger} (高估) 且 '
                    f'{momentum_period}日动量({momentum:.1f}%) < {sell_momentum_max}% (弱势)，'
                    f'建议减仓。当前价 {current_close:.2f}'
                ),
                'indicators': {
                    'close': round(current_close, 2),
                    f'ma{ma_period}': round(ma, 2),
                    f'momentum_{momentum_period}d': round(momentum, 2),
                    'pe': pe,
                    'debt_ratio': debt_ratio,
                }
            }

        # --- 负债率过滤 ---
        if debt_ratio is not None and debt_ratio >= debt_threshold:
            return {
                'action': 'hold',
                'confidence': 0.3,
                'reason': (
                    f'负债率 {debt_ratio:.1f}% ≥ {debt_threshold}%，'
                    f'财务风险偏高，暂不买入。'
                    f'PE={pe or "未知"}, 动量 {momentum:.1f}%'
                ),
                'indicators': {
                    'close': round(current_close, 2),
                    f'ma{ma_period}': round(ma, 2),
                    f'momentum_{momentum_period}d': round(momentum, 2),
                    'pe': pe,
                    'debt_ratio': debt_ratio,
                }
            }

        # --- 买入：低PE + 正动量 + MA60上方 ---
        buy_conditions = []
        buy_score = 0.0

        # 条件1: PE 价值区间
        if pe is not None:
            if pe < pe_threshold:
                buy_conditions.append(f'PE({pe:.1f}) < {pe_threshold}')
                buy_score += 0.40
            elif pe < pe_threshold * 1.5:
                # PE 略高于阈值，部分得分
                pe_score = 0.40 * (1 - (pe - pe_threshold) / pe_threshold)
                buy_score += max(0.10, pe_score)
                buy_conditions.append(f'PE({pe:.1f}) ≈ {pe_threshold}')
        else:
            # 无 PE 数据，动量权重提高
            buy_score += 0.20  # 中性对待

        # 条件2: 动量 > 阈值
        if momentum > buy_momentum_min:
            buy_conditions.append(f'动量({momentum:.1f}%) > {buy_momentum_min}%')
            # 动量越强，得分越高
            momentum_boost = min(0.30, momentum / 20 * 0.10)
            buy_score += 0.30 + momentum_boost
        elif momentum > buy_momentum_min - 5:
            # 动量略低于阈值，部分得分
            buy_score += 0.15
            buy_conditions.append(f'动量({momentum:.1f}%) ≈ {buy_momentum_min}%')

        # 条件3: MA60 上方（已在上面通过止损检查）
        buy_conditions.append(f'收盘价({current_close:.2f}) > MA{ma_period}({ma:.2f})')
        buy_score += 0.15

        # 判断买入
        if buy_score >= 0.60:
            trailing_percent = 0.05 if momentum > 10 else 0.08

            stop_loss = self._build_stop_loss_trailing(
                entry_price=current_close,
                trailing_percent=trailing_percent,
                direction='long'
            )

            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.55,
                profit_loss_ratio=2.0,
                kelly_fraction=0.25
            )

            confidence = min(0.90, buy_score)

            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'PE价值+动量策略买入: ' + ' | '.join(buy_conditions) +
                    f' | 综合评分 {buy_score:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing,
                },
                'indicators': {
                    'close': round(current_close, 2),
                    f'ma{ma_period}': round(ma, 2),
                    f'momentum_{momentum_period}d': round(momentum, 2),
                    'pe': pe,
                    'debt_ratio': debt_ratio,
                    'buy_score': round(buy_score, 2),
                }
            }

        # --- 持有 ---
        return {
            'action': 'hold',
            'confidence': round(max(0.35, buy_score), 4),
            'reason': (
                f'PE价值+动量策略持有。'
                f'PE={pe or "未知"}, 动量={momentum:.1f}%, '
                f'MA{ma_period}={ma:.2f}, 评分={buy_score:.2f}'
            ),
            'indicators': {
                'close': round(current_close, 2),
                f'ma{ma_period}': round(ma, 2),
                f'momentum_{momentum_period}d': round(momentum, 2),
                'pe': pe,
                'debt_ratio': debt_ratio,
                'buy_score': round(buy_score, 2),
            }
        }

    def _calc_momentum(self, closes: List[float], period: int) -> float:
        """计算动量: (当前价 - N日前价) / N日前价 × 100"""
        if len(closes) <= period:
            return 0.0
        return (closes[-1] - closes[-period - 1]) / closes[-period - 1] * 100
