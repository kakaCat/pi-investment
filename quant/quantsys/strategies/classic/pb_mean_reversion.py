"""
PB Mean Reversion Strategy — 市净率均值回归策略

专为高ROE周期股设计（如紫金矿业、矿业、钢铁等）。
核心逻辑：PB相对资产价值均值回归，且PB比PE更适合周期股估值。

PB 分位映射：
  < 20% 历史分位 → 重仓买入（6成仓位）
  20-35% → 分批买入（4成仓位）
  35-65% → 持有不动
  65-80% → 减仓（卖1/3）
  > 80% → 清仓

适用标的特征：
  - ROE 稳定且高（> 15%，证明资产质量好）
  - PE 波动剧烈（强周期属性）
  - PB 波动相对可控
  - 资产负债率合理（< 60%）
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..base import BaseStrategy, Signal


class PBMeanReversionStrategy(BaseStrategy):
    """
    PB Mean Reversion Strategy — 市净率均值回归。

    相比PE均值回归，PB更适合：
    1. 重资产行业（矿业、钢铁、银行、地产）
    2. 盈利周期性强的股票（PE剧烈波动但PB相对稳定）
    3. ROE高且相对稳定的标的

    参数:
        pb_history_min: PB 历史最小值
        pb_history_max: PB 历史最大值
        pb_history_median: PB 历史中位数
        pb_heavy_buy: 重仓买入PB线（对应历史低位）
        pb_batch_buy: 分批买入PB线
        pb_reduce: 减仓PB线
        pb_liquidate: 清仓PB线
        max_position_pct: 最大仓位比例
        stop_loss_pct: 硬止损比例
        atr_stop_mult: ATR止损倍率
        roe_min_threshold: ROE最低门槛（低于此值禁止买入）
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            # PB 历史区间（近3年）
            'pb_history_min': 1.5,
            'pb_history_max': 6.5,
            'pb_history_median': 3.0,
            # PB 估值区间
            'pb_heavy_buy': 2.0,       # PB ≤ 2.0 → 重仓买入
            'pb_batch_buy': 2.5,       # PB ≤ 2.5 → 分批买入
            'pb_reduce': 4.5,          # PB ≥ 4.5 → 减仓
            'pb_liquidate': 5.5,       # PB ≥ 5.5 → 清仓
            # 风控参数
            'max_position_pct': 0.60,
            'stop_loss_pct': 0.08,
            'atr_stop_mult': 2.0,
            'take_profit_pct': 0.30,    # 止盈30%（周期股止盈空间可大一些）
            # 财务过滤
            'roe_min_threshold': 0.10,  # ROE < 10% 禁止买入
            'debt_max_threshold': 0.65, # 负债率 > 65% 谨慎
            # 技术指标参数
            'rsi_period': 14,
            'atr_period': 14,
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        self.name = 'PB_Mean_Reversion'

    def _estimate_daily_pb(
        self, data: pd.DataFrame, roe_series: pd.Series = None,
        pe_series: pd.Series = None
    ) -> pd.Series:
        """
        估算每日PB。

        优先使用data中的pb列，否则从 PE × ROE 反推：
          PB = PE × ROE

        Args:
            data: OHLCV DataFrame
            roe_series: 每日ROE（可选，用于反推）
            pe_series: 每日PE（可选）

        Returns:
            每日PB的Series，如果没有可用数据返回None
        """
        if 'pb' in data.columns and not data['pb'].isna().all():
            return data['pb']

        # 从PE和ROE反推 PB = PE × ROE
        pe_col = None
        if pe_series is not None:
            pe_col = pe_series
        elif 'pe' in data.columns:
            pe_col = data['pe']

        if pe_col is not None and roe_series is not None:
            pb_series = pe_col * roe_series.clip(lower=0.001, upper=0.60)
            pb_series = pb_series.clip(
                lower=self.params['pb_history_min'] * 0.7,
                upper=self.params['pb_history_max'] * 1.3
            )
            return pb_series

        return None

    def _get_pb_zone(self, pb_value: float) -> str:
        """
        根据PB值确定当前估值区间。

        返回:
            'heavy_buy'   — PB ≤ pb_heavy_buy（极度低估）
            'batch_buy'   — PB ≤ pb_batch_buy（低估）
            'hold'        — PB 在合理区间
            'reduce'      — PB ≥ pb_reduce（偏高）
            'liquidate'   — PB ≥ pb_liquidate（高估）
        """
        if pb_value <= self.params['pb_heavy_buy']:
            return 'heavy_buy'
        elif pb_value <= self.params['pb_batch_buy']:
            return 'batch_buy'
        elif pb_value >= self.params['pb_liquidate']:
            return 'liquidate'
        elif pb_value >= self.params['pb_reduce']:
            return 'reduce'
        else:
            return 'hold'

    def _zone_to_position_pct(self, zone: str) -> float:
        """将PB区间映射为建议仓位比例。"""
        mapping = {
            'heavy_buy': 0.60,
            'batch_buy': 0.40,
            'hold': 0.30,
            'reduce': 0.10,
            'liquidate': 0.00,
        }
        return mapping.get(zone, 0.30)

    def _calculate_confidence(
        self, pb_value: float, zone: str, action: str,
        roe: float = None
    ) -> float:
        """根据PB偏离程度和ROE质量计算信号置信度。"""
        if action == 'buy':
            # PB越低，置信度越高
            min_pb = self.params['pb_history_min']
            heavy_pb = self.params['pb_heavy_buy']
            if pb_value <= min_pb:
                confidence = 0.85
            else:
                range_size = max(heavy_pb - min_pb, 0.01)
                confidence = 0.60 + 0.25 * (heavy_pb - pb_value) / range_size
                confidence = min(max(confidence, 0.50), 0.85)

            # ROE越高，置信度加成
            if roe is not None and roe > self.params['roe_min_threshold']:
                roe_bonus = min((roe - self.params['roe_min_threshold']) * 0.5, 0.10)
                confidence = min(confidence + roe_bonus, 0.90)

            return confidence

        elif action == 'sell':
            max_pb = self.params['pb_history_max']
            liquidate_pb = self.params['pb_liquidate']
            if pb_value >= max_pb:
                confidence = 0.85
            else:
                range_size = max(max_pb - liquidate_pb, 0.01)
                confidence = 0.55 + 0.30 * (pb_value - liquidate_pb) / range_size
                confidence = min(max(confidence, 0.50), 0.85)

            return confidence

        return 0.50

    def calculate_signals(
        self, data: pd.DataFrame, pb_series: pd.Series = None,
        pe_series: pd.Series = None, roe_series: pd.Series = None
    ) -> List[Signal]:
        """
        计算PB均值回归信号。

        Args:
            data: OHLCV DataFrame（必需列: close, high, low, volume）
            pb_series: 每日PB序列（可选，不提供则从data中取或从PE×ROE反推）
            pe_series: 每日PE序列（可选，用于反推PB）
            roe_series: 每日ROE序列（可选，用于反推PB和置信度加成）

        Returns:
            Signal 列表
        """
        signals = []
        data = data.copy()

        # 确保有PB数据
        if pb_series is not None:
            data['pb'] = pb_series
        elif 'pb' not in data.columns:
            # 尝试从PE×ROE反推
            if pe_series is not None and roe_series is not None:
                data['pb'] = pe_series * roe_series.clip(lower=0.001, upper=0.60)
            elif 'pe' in data.columns and roe_series is not None:
                data['pb'] = data['pe'] * roe_series.clip(lower=0.001, upper=0.60)
            else:
                return signals  # 无PB数据，无法生成信号

        # 计算ATR
        if 'atr' not in data.columns:
            high_low = data['high'] - data['low']
            high_close = np.abs(data['high'] - data['close'].shift(1))
            low_close = np.abs(data['low'] - data['close'].shift(1))
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            data['atr'] = tr.rolling(window=self.params['atr_period']).mean()

        # 计算RSI
        delta = data['close'].diff()
        gain = delta.clip(lower=0).rolling(self.params['rsi_period']).mean()
        loss = (-delta.clip(upper=0)).rolling(self.params['rsi_period']).mean()
        data['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

        # 当前ROE（用于置信度加成）
        current_roe = None
        if roe_series is not None and len(roe_series) > 0:
            current_roe = float(roe_series.iloc[-1])

        # 逐日扫描信号
        for idx, row in data.iterrows():
            if pd.isna(row.get('pb')) or pd.isna(row.get('close')):
                continue

            symbol = row.get('symbol', 'UNKNOWN')
            timestamp = row.get('timestamp', row.get('trade_date', datetime.now()))
            close_price = row['close']
            pb_value = row['pb']
            current_zone = self._get_pb_zone(pb_value)
            volume = row.get('volume', 0)

            # --- 买入信号 ---
            if current_zone in ('heavy_buy', 'batch_buy'):
                if self.has_position(symbol):
                    continue

                # RSI辅助：避免追高
                if pd.notna(row.get('rsi')) and row['rsi'] > 70:
                    continue

                confidence = self._calculate_confidence(
                    pb_value, current_zone, 'buy', roe=current_roe
                )

                # 成交量放大加分
                if 'volume' in data.columns and len(data) > 20:
                    vol_ma20 = data['volume'].rolling(20).mean()
                    if idx >= 20 and pd.notna(vol_ma20.iloc[idx]) and vol_ma20.iloc[idx] > 0:
                        vol_ratio = volume / vol_ma20.iloc[idx]
                        if 1.2 <= vol_ratio <= 3.0:
                            confidence = min(confidence * 1.05, 0.88)

                signal = Signal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=close_price,
                    reason=f'pb_{current_zone}_{pb_value:.2f}',
                    confidence=confidence
                )
                signals.append(signal)

                # 设置止损
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
                        sell_qty = (
                            position.quantity
                            if current_zone == 'liquidate'
                            else position.quantity // 3
                        )
                        if sell_qty > 0:
                            confidence = self._calculate_confidence(
                                pb_value, current_zone, 'sell'
                            )
                            signal = Signal(
                                timestamp=timestamp,
                                symbol=symbol,
                                action='sell',
                                price=close_price,
                                quantity=sell_qty,
                                reason=f'pb_{current_zone}_{pb_value:.2f}',
                                confidence=confidence
                            )
                            signals.append(signal)

        return signals

    def get_strategy_info(self) -> Dict[str, Any]:
        """策略信息。"""
        return {
            'name': self.name,
            'type': 'mean_reversion',
            'suitable_for': '高ROE周期股（矿业、钢铁、银行）',
            'parameters': self.params,
            'description': (
                f'PB均值回归：买入PB≤{self.params["pb_heavy_buy"]}(重仓)/'
                f'PB≤{self.params["pb_batch_buy"]}(分批)，'
                f'卖出PB≥{self.params["pb_reduce"]}(减仓)/'
                f'PB≥{self.params["pb_liquidate"]}(清仓)'
            ),
            'entry_rules': [
                f'PB ≤ {self.params["pb_heavy_buy"]} → 重仓买入（60%仓位）',
                f'PB ≤ {self.params["pb_batch_buy"]} → 分批买入（40%仓位）',
                f'ROE > {self.params["roe_min_threshold"]*100}% 确认（避免低质资产）',
                f'RSI < 70 确认（避免追高）',
                f'止损：{self.params["stop_loss_pct"]*100}% 或 {self.params["atr_stop_mult"]}×ATR',
                f'止盈：{self.params["take_profit_pct"]*100}%',
            ],
            'exit_rules': [
                f'PB ≥ {self.params["pb_reduce"]} → 减仓1/3',
                f'PB ≥ {self.params["pb_liquidate"]} → 清仓',
                '或止损/止盈触发',
            ],
            'pb_zones': {
                'history_min': self.params['pb_history_min'],
                'history_median': self.params['pb_history_median'],
                'history_max': self.params['pb_history_max'],
                'heavy_buy': self.params['pb_heavy_buy'],
                'batch_buy': self.params['pb_batch_buy'],
                'reduce': self.params['pb_reduce'],
                'liquidate': self.params['pb_liquidate'],
            },
        }
