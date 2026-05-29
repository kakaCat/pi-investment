"""
PE Mean Reversion Strategy — 估值均值回归策略

专为稳定ROE蓝筹股设计（如长江电力）。
核心逻辑：PE在历史区间内规律波动，低估买入、高估卖出。

PE 分位映射：
  < 20% 分位 → 重仓买入（6成仓位）
  20-35% → 分批买入（4成仓位）
  35-65% → 持有不动
  65-80% → 减仓（卖1/3）
  > 80% → 清仓

适用标的特征：
  - ROE 稳定（12-18%）
  - 毛利率 > 40%
  - PE 在固定区间波动（14-22 典型）
  - 低波动（年化波动 < 25%）
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from ..base import BaseStrategy, Signal, Position


class PEMeanReversionStrategy(BaseStrategy):
    """
    PE Mean Reversion Strategy.

    参数:
        pe_history_min: PE 历史最小值
        pe_history_max: PE 历史最大值
        pe_history_median: PE 历史中位数
        pe_series: 每日PE序列（可选，如果不提供则从OHLCV推导）
        zone_20_pct: 20%分位PE值 — 重仓买入线
        zone_35_pct: 35%分位PE值 — 分批买入线
        zone_65_pct: 65%分位PE值 — 减仓线
        zone_80_pct: 80%分位PE值 — 清仓线
        max_position_pct: 最大仓位比例
        stop_loss_pct: 止损比例
        atr_stop_mult: ATR止损倍率（当价格跌破入场价 - N*ATR时触发）
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            # PE 历史区间（近3年）
            'pe_history_min': 14.26,
            'pe_history_max': 21.27,
            'pe_history_median': 18.52,
            # 估值区间分位点
            'pe_heavy_buy': 16.0,      # 20%分位 ≈ PE 16 → 重仓买入
            'pe_batch_buy': 17.0,      # 35%分位 ≈ PE 17 → 分批买入
            'pe_reduce': 19.5,         # 65%分位 ≈ PE 19.5 → 减仓
            'pe_liquidate': 20.5,      # 80%分位 ≈ PE 20.5 → 清仓
            # 风控参数
            'max_position_pct': 0.60,   # 单标的最高仓位 60%
            'stop_loss_pct': 0.08,      # 硬止损 8%
            'atr_stop_mult': 2.0,       # ATR 倍率止损
            'take_profit_pct': 0.25,    # 止盈 25%（PE均值回归策略止盈空间可大一些）
            'rsi_period': 14,
            'atr_period': 14,
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        self.name = 'PE_Mean_Reversion'
        self._prev_pe_zone = None  # 用于检测PE区间切换

    def _estimate_daily_pe(
        self, data: pd.DataFrame, quarterly_eps: float = None
    ) -> pd.Series:
        """
        估算每日PE。

        如果外部提供了PE序列，直接使用。
        否则根据最近一期EPS和每日收盘价推算：
          PE_daily = Close / EPS_TTM

        Args:
            data: OHLCV DataFrame
            quarterly_eps: 最近一季EPS_TTM（如果为None则用内置推算）

        Returns:
            每日PE的Series
        """
        if 'pe' in data.columns and not data['pe'].isna().all():
            return data['pe']

        # 从ROE和PB反推PE（如果数据可用）
        # PE = PB / ROE
        if 'pb' in data.columns and 'roe' in data.columns:
            pe_series = data['pb'] / data['roe'].clip(lower=0.001)
            pe_series = pe_series.clip(
                lower=self.params['pe_history_min'] * 0.8,
                upper=self.params['pe_history_max'] * 1.2
            )
            return pe_series

        return None

    def _get_pe_zone(self, pe_value: float) -> str:
        """
        根据PE值确定当前估值区间。

        返回:
            'heavy_buy'   — PE ≤ pe_heavy_buy（极度低估）
            'batch_buy'   — PE ≤ pe_batch_buy（低估）
            'hold'        — PE 在合理区间
            'reduce'      — PE ≥ pe_reduce（偏高）
            'liquidate'   — PE ≥ pe_liquidate（高估）
        """
        if pe_value <= self.params['pe_heavy_buy']:
            return 'heavy_buy'
        elif pe_value <= self.params['pe_batch_buy']:
            return 'batch_buy'
        elif pe_value >= self.params['pe_liquidate']:
            return 'liquidate'
        elif pe_value >= self.params['pe_reduce']:
            return 'reduce'
        else:
            return 'hold'

    def _zone_to_position_pct(self, zone: str) -> float:
        """将PE区间映射为建议仓位比例。"""
        mapping = {
            'heavy_buy': 0.60,
            'batch_buy': 0.40,
            'hold': 0.30,
            'reduce': 0.10,
            'liquidate': 0.00,
        }
        return mapping.get(zone, 0.30)

    def _calculate_confidence(
        self, pe_value: float, zone: str, action: str
    ) -> float:
        """根据PE偏离程度计算信号置信度。"""
        if action == 'buy':
            # PE越低，置信度越高
            min_pe = self.params['pe_history_min']
            heavy_pe = self.params['pe_heavy_buy']
            if pe_value <= min_pe:
                return 0.85
            # 线性映射：heavy_buy 线 → 0.80, 接近 min → 0.85
            range_size = max(heavy_pe - min_pe, 0.1)
            confidence = 0.65 + 0.20 * (heavy_pe - pe_value) / range_size
            return min(max(confidence, 0.55), 0.85)

        elif action == 'sell':
            # PE越高，置信度越高
            max_pe = self.params['pe_history_max']
            liquidate_pe = self.params['pe_liquidate']
            if pe_value >= max_pe:
                return 0.85
            range_size = max(max_pe - liquidate_pe, 0.1)
            confidence = 0.55 + 0.30 * (pe_value - liquidate_pe) / range_size
            return min(max(confidence, 0.50), 0.85)

        return 0.50

    def calculate_signals(
        self, data: pd.DataFrame, pe_series: pd.Series = None,
        pb_series: pd.Series = None, roe_series: pd.Series = None
    ) -> List[Signal]:
        """
        计算PE均值回归信号。

        Args:
            data: OHLCV DataFrame（必需列: close, 建议有: volume, pe, pb, roe）
            pe_series: 每日PE序列（可选，不提供则从data中取）
            pb_series: 每日PB序列（可选，用于辅助估值判断）
            roe_series: 每日ROE序列（可选）

        Returns:
            Signal 列表
        """
        signals = []
        data = data.copy()

        # 确保有PE数据
        if pe_series is not None:
            data['pe'] = pe_series
        elif 'pe' not in data.columns:
            if pb_series is not None and roe_series is not None:
                data['pe'] = pb_series / roe_series.clip(lower=0.001)
            else:
                return signals  # 无PE数据，无法生成信号

        # 计算ATR用于动态止损
        if 'atr' not in data.columns:
            high_low = data['high'] - data['low']
            high_close = np.abs(data['high'] - data['close'].shift(1))
            low_close = np.abs(data['low'] - data['close'].shift(1))
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            data['atr'] = tr.rolling(window=self.params['atr_period']).mean()

        # 计算RSI用于辅助确认
        delta = data['close'].diff()
        gain = delta.clip(lower=0).rolling(self.params['rsi_period']).mean()
        loss = (-delta.clip(upper=0)).rolling(self.params['rsi_period']).mean()
        data['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

        # 逐日扫描信号
        for idx, row in data.iterrows():
            if pd.isna(row.get('pe')) or pd.isna(row.get('close')):
                continue

            symbol = row.get('symbol', 'UNKNOWN')
            timestamp = row.get('timestamp', row.get('trade_date', datetime.now()))
            close_price = row['close']
            pe_value = row['pe']
            current_zone = self._get_pe_zone(pe_value)
            volume = row.get('volume', 0)

            # --- 买入信号 ---
            if current_zone in ('heavy_buy', 'batch_buy'):
                # 避免在已有足够仓位时重复买入
                if self.has_position(symbol):
                    position = self.get_position(symbol)
                    target_pct = self._zone_to_position_pct(current_zone)
                    # 当前仓位已达目标，跳过
                    if position.quantity > 0:
                        continue

                # RSI辅助：买入时RSI不要太高（避免追高）
                if pd.notna(row.get('rsi')) and row['rsi'] > 65:
                    continue

                confidence = self._calculate_confidence(pe_value, current_zone, 'buy')

                # 成交量放大加分
                if 'volume' in data.columns and len(data) > 20:
                    vol_ma20 = data['volume'].rolling(20).mean().iloc[idx]
                    if pd.notna(vol_ma20) and vol_ma20 > 0:
                        vol_ratio = volume / vol_ma20
                        if 1.2 <= vol_ratio <= 3.0:
                            confidence = min(confidence * 1.05, 0.85)

                signal = Signal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=close_price,
                    reason=f'pe_{current_zone}_{pe_value:.1f}',
                    confidence=confidence
                )
                signals.append(signal)

                # 设置止损：入场价 × (1 - 止损比例) 或 ATR动态止损，取高者
                stop_loss_price = close_price * (1 - self.params['stop_loss_pct'])
                if pd.notna(row.get('atr')):
                    atr_stop = close_price - self.params['atr_stop_mult'] * row['atr']
                    stop_loss_price = max(stop_loss_price, atr_stop)
                self.set_stop_loss(symbol, stop_loss_price)

                # 设置止盈
                take_profit_price = close_price * (1 + self.params['take_profit_pct'])
                self.set_take_profit(symbol, take_profit_price)

            # --- 卖出信号 ---
            elif current_zone in ('reduce', 'liquidate'):
                if self.has_position(symbol):
                    position = self.get_position(symbol)
                    if position.quantity > 0:
                        # 减仓：卖1/3；清仓：全卖
                        sell_qty = position.quantity if current_zone == 'liquidate' else position.quantity // 3

                        if sell_qty > 0:
                            confidence = self._calculate_confidence(pe_value, current_zone, 'sell')

                            signal = Signal(
                                timestamp=timestamp,
                                symbol=symbol,
                                action='sell',
                                price=close_price,
                                quantity=sell_qty,
                                reason=f'pe_{current_zone}_{pe_value:.1f}',
                                confidence=confidence
                            )
                            signals.append(signal)

        return signals

    def on_bar(self, bar: Dict[str, Any]) -> Optional[Signal]:
        """每根K线检查止损/止盈。"""
        return super().on_bar(bar)

    def get_strategy_info(self) -> Dict[str, Any]:
        """策略信息。"""
        return {
            'name': self.name,
            'type': 'mean_reversion',
            'suitable_for': '稳定ROE蓝筹（水电、消费龙头）',
            'parameters': self.params,
            'description': (
                f'PE均值回归：买入PE≤{self.params["pe_heavy_buy"]}(重仓)/'
                f'PE≤{self.params["pe_batch_buy"]}(分批)，'
                f'卖出PE≥{self.params["pe_reduce"]}(减仓)/'
                f'PE≥{self.params["pe_liquidate"]}(清仓)'
            ),
            'entry_rules': [
                f'PE ≤ {self.params["pe_heavy_buy"]} → 重仓买入（60%仓位）',
                f'PE ≤ {self.params["pe_batch_buy"]} → 分批买入（40%仓位）',
                f'RSI < 65 确认（避免追高）',
                f'止损：{self.params["stop_loss_pct"]*100}% 或 {self.params["atr_stop_mult"]}×ATR',
                f'止盈：{self.params["take_profit_pct"]*100}%',
            ],
            'exit_rules': [
                f'PE ≥ {self.params["pe_reduce"]} → 减仓1/3',
                f'PE ≥ {self.params["pe_liquidate"]} → 清仓',
                '或止损/止盈触发',
            ],
            'pe_zones': {
                'history_min': self.params['pe_history_min'],
                'history_median': self.params['pe_history_median'],
                'history_max': self.params['pe_history_max'],
                'heavy_buy': self.params['pe_heavy_buy'],
                'batch_buy': self.params['pe_batch_buy'],
                'reduce': self.params['pe_reduce'],
                'liquidate': self.params['pe_liquidate'],
            },
        }
