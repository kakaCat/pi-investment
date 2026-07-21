"""
市场环境识别器

功能：
1. 识别当前市场状态（牛市/熊市/震荡市）
2. 提供市场特征描述
3. 推荐适合的策略类型

方法：
- 趋势强度（ADX）
- 价格相对位置（52周高低点）
- 移动平均线排列
- 波动率水平
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)


class MarketRegimeDetector:
    """市场环境识别器"""

    # 市场环境特征定义
    REGIME_CHARACTERISTICS = {
        'bull': {
            'name': '牛市',
            'description': '上升趋势明确，适合趋势跟踪策略',
            'recommended_strategies': ['ma_cross', 'momentum', 'breakout'],
            'avoid_strategies': ['mean_reversion', 'contrarian'],
            'risk_level': 'medium',
            'typical_duration': '6-18个月',
            'trading_frequency': 'medium',  # 中频交易
            'position_sizing': '60-80%',    # 建议仓位
        },
        'bear': {
            'name': '熊市',
            'description': '下降趋势明确，防守为主，控制仓位',
            'recommended_strategies': ['defensive', 'short_selling'],
            'avoid_strategies': ['buy_dip', 'momentum_long'],
            'risk_level': 'high',
            'typical_duration': '3-12个月',
            'trading_frequency': 'low',     # 低频交易
            'position_sizing': '20-40%',    # 建议仓位
        },
        'sideways': {
            'name': '震荡市',
            'description': '无明确趋势，假信号多，高抛低吸',
            'recommended_strategies': ['rsi_reversal', 'bollinger_reversion', 'range_trading'],
            'avoid_strategies': ['trend_following', 'breakout', 'momentum'],
            'risk_level': 'high',           # 假信号多
            'typical_duration': '1-6个月',
            'trading_frequency': 'high',    # 高频交易（但胜率低）
            'position_sizing': '30-50%',    # 建议仓位
        }
    }

    def __init__(self, kline_repo=None):
        """
        初始化市场环境识别器

        Args:
            kline_repo: K线数据仓储（用于获取指数数据）
        """
        self.kline_repo = kline_repo

    def detect_current_regime(self, index_symbol: str = '000001') -> Dict[str, Any]:
        """
        识别当前市场环境

        Args:
            index_symbol: 指数代码（默认上证指数）

        Returns:
            {
                'regime': 'bull' | 'bear' | 'sideways',
                'confidence': 0.85,  # 置信度
                'signals': {...},     # 各项指标
                'characteristics': {...}  # 市场特征
            }
        """
        try:
            # 获取指数数据（至少需要120天）
            if self.kline_repo:
                klines = self.kline_repo.get_recent(index_symbol, limit=150)
                if len(klines) < 120:
                    logger.warning(f"指数数据不足（{len(klines)}条），使用默认判断")
                    return self._get_default_regime()

                df = pd.DataFrame([{
                    'date': k.date,
                    'open': float(k.open),
                    'high': float(k.high),
                    'low': float(k.low),
                    'close': float(k.close),
                    'volume': float(k.volume)
                } for k in klines])
                df = df.sort_values('date').reset_index(drop=True)
            else:
                logger.warning("未提供K线仓储，使用默认判断")
                return self._get_default_regime()

            # 计算各项指标
            signals = {}

            # 1. 趋势强度（ADX）
            signals['adx'] = self._calculate_adx(df)
            signals['trend_strength'] = 'strong' if signals['adx'] > 25 else 'weak'

            # 2. 价格相对位置（52周高低点）
            signals['price_position'] = self._calculate_price_position(df)

            # 3. 均线排列
            signals['ma_arrangement'] = self._analyze_ma_arrangement(df)

            # 4. 波动率水平
            signals['volatility'] = self._calculate_volatility(df)
            signals['volatility_level'] = self._classify_volatility(signals['volatility'])

            # 5. 价格动量
            signals['momentum_20'] = (df['close'].iloc[-1] / df['close'].iloc[-21] - 1) if len(df) >= 21 else 0
            signals['momentum_60'] = (df['close'].iloc[-1] / df['close'].iloc[-61] - 1) if len(df) >= 61 else 0

            # 综合判断
            regime, confidence = self._determine_regime(signals)

            return {
                'regime': regime,
                'confidence': round(confidence, 2),
                'signals': {k: round(v, 4) if isinstance(v, float) else v
                           for k, v in signals.items()},
                'characteristics': self.REGIME_CHARACTERISTICS[regime],
                'detected_at': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"市场环境识别失败: {e}")
            return self._get_default_regime()

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        计算ADX（平均趋向指数）

        ADX > 25: 趋势强
        ADX < 20: 趋势弱
        """
        try:
            high = df['high']
            low = df['low']
            close = df['close']

            # 计算+DM和-DM
            plus_dm = high.diff()
            minus_dm = -low.diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm < 0] = 0

            # 计算TR（真实波幅）
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # 计算ATR
            atr = tr.rolling(period).mean()

            # 计算+DI和-DI
            plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

            # 计算DX和ADX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(period).mean()

            return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 20.0

        except Exception as e:
            logger.error(f"ADX计算失败: {e}")
            return 20.0

    def _calculate_price_position(self, df: pd.DataFrame) -> float:
        """
        计算价格相对位置（0-1之间）

        1.0: 当前价格=52周最高价
        0.0: 当前价格=52周最低价
        """
        try:
            current_price = df['close'].iloc[-1]
            high_52w = df['high'].iloc[-min(252, len(df)):].max()
            low_52w = df['low'].iloc[-min(252, len(df)):].min()

            if high_52w == low_52w:
                return 0.5

            position = (current_price - low_52w) / (high_52w - low_52w)
            return float(position)

        except Exception as e:
            logger.error(f"价格位置计算失败: {e}")
            return 0.5

    def _analyze_ma_arrangement(self, df: pd.DataFrame) -> str:
        """
        分析均线排列

        Returns:
            'bullish': 多头排列（MA20 > MA60 > MA120）
            'bearish': 空头排列（MA20 < MA60 < MA120）
            'mixed': 混合排列
        """
        try:
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            ma60 = df['close'].rolling(60).mean().iloc[-1]
            ma120 = df['close'].rolling(120).mean().iloc[-1]

            if ma20 > ma60 > ma120:
                return 'bullish'
            elif ma20 < ma60 < ma120:
                return 'bearish'
            else:
                return 'mixed'

        except Exception as e:
            logger.error(f"均线排列分析失败: {e}")
            return 'mixed'

    def _calculate_volatility(self, df: pd.DataFrame, period: int = 20) -> float:
        """计算年化波动率"""
        try:
            returns = df['close'].pct_change()
            volatility = returns.rolling(period).std().iloc[-1] * np.sqrt(252)
            return float(volatility)
        except Exception as e:
            logger.error(f"波动率计算失败: {e}")
            return 0.20  # 默认20%

    def _classify_volatility(self, volatility: float) -> str:
        """分类波动率水平"""
        if volatility < 0.15:
            return 'low'
        elif volatility < 0.25:
            return 'medium'
        else:
            return 'high'

    def _determine_regime(self, signals: Dict[str, Any]) -> tuple:
        """
        综合判断市场环境

        Returns:
            (regime, confidence)
        """
        score_bull = 0
        score_bear = 0
        score_sideways = 0

        # 评分规则

        # 1. 趋势强度
        if signals['trend_strength'] == 'strong':
            if signals['momentum_20'] > 0.05:
                score_bull += 2
            elif signals['momentum_20'] < -0.05:
                score_bear += 2
        else:
            score_sideways += 2

        # 2. 价格位置
        price_pos = signals['price_position']
        if price_pos > 0.7:
            score_bull += 2
        elif price_pos < 0.3:
            score_bear += 2
        else:
            score_sideways += 1

        # 3. 均线排列
        ma_arr = signals['ma_arrangement']
        if ma_arr == 'bullish':
            score_bull += 2
        elif ma_arr == 'bearish':
            score_bear += 2
        else:
            score_sideways += 2

        # 4. 动量
        if signals['momentum_60'] > 0.10:
            score_bull += 1
        elif signals['momentum_60'] < -0.10:
            score_bear += 1

        # 5. 波动率
        if signals['volatility_level'] == 'high':
            # 高波动率在熊市和震荡市更常见
            score_bear += 0.5
            score_sideways += 0.5

        # 选择得分最高的
        scores = {
            'bull': score_bull,
            'bear': score_bear,
            'sideways': score_sideways
        }

        regime = max(scores, key=scores.get)
        max_score = scores[regime]
        total_score = sum(scores.values())

        # 计算置信度
        confidence = max_score / total_score if total_score > 0 else 0.33

        return regime, confidence

    def _get_default_regime(self) -> Dict[str, Any]:
        """获取默认市场环境（数据不足时）"""
        return {
            'regime': 'sideways',
            'confidence': 0.50,
            'signals': {},
            'characteristics': self.REGIME_CHARACTERISTICS['sideways'],
            'detected_at': datetime.now().isoformat(),
            'note': '数据不足，使用默认判断'
        }

    def get_strategy_suitability(self, strategy_type: str, current_regime: str) -> Dict[str, Any]:
        """
        评估策略在当前市场环境的适用性

        Args:
            strategy_type: 策略类型（如 'ma_cross', 'rsi_reversal'）
            current_regime: 当前市场环境

        Returns:
            {
                'suitability': 'high' | 'medium' | 'low',
                'reason': '...',
                'recommendation': 'use' | 'caution' | 'avoid'
            }
        """
        characteristics = self.REGIME_CHARACTERISTICS[current_regime]

        if strategy_type in characteristics['recommended_strategies']:
            return {
                'suitability': 'high',
                'reason': f'{characteristics["name"]}环境适合该策略',
                'recommendation': 'use'
            }
        elif strategy_type in characteristics['avoid_strategies']:
            return {
                'suitability': 'low',
                'reason': f'{characteristics["name"]}环境不适合该策略，容易产生假信号',
                'recommendation': 'avoid'
            }
        else:
            return {
                'suitability': 'medium',
                'reason': f'{characteristics["name"]}环境可谨慎使用该策略',
                'recommendation': 'caution'
            }


# 全局单例（可选）
_market_regime_detector = None

def get_market_regime_detector(kline_repo=None):
    """获取市场环境识别器单例"""
    global _market_regime_detector
    if _market_regime_detector is None:
        _market_regime_detector = MarketRegimeDetector(kline_repo)
    return _market_regime_detector
