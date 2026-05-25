#!/usr/bin/env python3
"""
交易信号生成脚本

功能：
1. 读取最新因子值
2. 运行策略生成交易信号
3. 保存信号到 JSON 文件
"""

import os
import sys
import json
import logging
import argparse
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database
from quantsys.utils.confidence_calibration import (
    calibrate_rsi_confidence,
    calibrate_ma_confidence,
    calibrate_macd_confidence,
    calibrate_bollinger_confidence,
    calibrate_kdj_confidence,
    bayesian_calibrate
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_symbol(symbol: str) -> str:
    """Normalize common exchange prefixes/suffixes."""
    value = str(symbol).strip()
    value = re.sub(r'^(sh|sz|bj)', '', value, flags=re.IGNORECASE)
    value = re.sub(r'\.(SH|SZ|BJ|HK)$', '', value, flags=re.IGNORECASE)
    return value


def parse_symbols(raw_symbols: str = None):
    """Parse comma/whitespace separated symbols."""
    if not raw_symbols:
        return None
    symbols = [
        normalize_symbol(symbol)
        for symbol in re.split(r'[\s,，]+', raw_symbols)
        if symbol.strip()
    ]
    return list(dict.fromkeys(symbols))


class SignalGenerator:
    """信号生成器"""

    def __init__(self, db: Database):
        self.db = db

    def get_latest_date(self) -> str:
        """获取最新数据日期"""
        return self.db.get_latest_kline_date()

    def get_prev_trading_date(self, date: str) -> Optional[str]:
        """获取给定日期之前最近的一个交易日（通过 Database 统一接口）"""
        try:
            prev = self.db.get_prev_trading_date(date)
            return prev
        except AttributeError:
            # db 对象没有此方法（旧版本），回退到直接 SQLite 查询
            import sqlite3
            db_path = str(self.db.db_path) if getattr(self.db, 'db_path', None) else None
            if not db_path:
                return None
            date_compact = date.replace('-', '')
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT date FROM daily_klines WHERE date < ? ORDER BY date DESC LIMIT 1",
                    (date_compact,)
                ).fetchone()
                if row:
                    raw = row["date"]
                    if len(raw) == 8:
                        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
                    return raw
                return None
            finally:
                conn.close()

    def get_stock_factors(self, symbol: str, date: str) -> Dict:
        """获取股票的因子值"""
        return self.db.get_factor_values(symbol, date)

    def get_stock_price(self, symbol: str, date: str) -> Dict:
        """获取股票价格"""
        return self.db.get_price_on_date(symbol, date)

    # ========== 策略1: RSI反转策略 ==========

    def strategy_rsi_reversal(self, symbol: str, factors: Dict, price: Dict) -> Dict:
        """
        RSI反转策略
        买入: RSI < 30 (超卖)
        卖出: RSI > 70 (超买)
        """
        rsi = factors.get('RSI12')

        if rsi is None:
            return None

        if rsi < 35:
            confidence = calibrate_rsi_confidence(rsi, 35, 'buy')
            return {
                'symbol': symbol,
                'strategy': 'RSI反转',
                'signal': 'BUY',
                'reason': f'RSI超卖 ({rsi:.2f} < 30)',
                'price': price['close'],
                'confidence': confidence
            }
        elif rsi > 70:
            confidence = calibrate_rsi_confidence(rsi, 70, 'sell')
            return {
                'symbol': symbol,
                'strategy': 'RSI反转',
                'signal': 'SELL',
                'reason': f'RSI超买 ({rsi:.2f} > 70)',
                'price': price['close'],
                'confidence': confidence
            }

        return None

    # ========== 策略2: 均线突破策略（事件检测：真实金叉/死叉） ==========

    def strategy_ma_crossover(self, symbol: str, factors: Dict, price: Dict,
                              prev_factors: Optional[Dict] = None) -> Optional[Dict]:
        """
        均线突破策略（事件检测版）
        买入: MA5 上穿 MA20（前一天 MA5 < MA20，今天 MA5 > MA20）
        卖出: MA5 下穿 MA20（前一天 MA5 > MA20，今天 MA5 < MA20）
        """
        ma5 = factors.get('MA5')
        ma20 = factors.get('MA20')
        close = price['close']

        if ma5 is None or ma20 is None:
            return None

        # 如果没有前一天数据，降级为状态判断（但降低信心度）
        if prev_factors is None:
            prev_ma5 = prev_ma20 = None
        else:
            prev_ma5 = prev_factors.get('MA5')
            prev_ma20 = prev_factors.get('MA20')

        has_prev = prev_ma5 is not None and prev_ma20 is not None

        # 计算穿越强度
        ma_diff_pct = abs(ma5 - ma20) / ma20
        confidence = calibrate_ma_confidence(ma_diff_pct)

        # 金叉：前一天 MA5 ≤ MA20，今天 MA5 > MA20
        if ma5 > ma20:
            if has_prev and prev_ma5 <= prev_ma20:
                # 真实金叉事件
                return {
                    'symbol': symbol,
                    'strategy': '均线突破',
                    'signal': 'BUY',
                    'reason': f'MA5({ma5:.2f}) 上穿 MA20({ma20:.2f})',
                    'price': close,
                    'confidence': confidence
                }
            elif not has_prev:
                # 无前一天数据，降级为状态信号（降低信心度）
                return {
                    'symbol': symbol,
                    'strategy': '均线突破',
                    'signal': 'BUY',
                    'reason': f'MA5({ma5:.2f}) > MA20({ma20:.2f}) [⚠无前日数据]',
                    'price': close,
                    'confidence': confidence * 0.6
                }
            # 否则：已经金叉状态，不重复发信号
            return None

        # 死叉：前一天 MA5 ≥ MA20，今天 MA5 < MA20
        elif ma5 < ma20:
            if has_prev and prev_ma5 >= prev_ma20:
                # 真实死叉事件
                return {
                    'symbol': symbol,
                    'strategy': '均线突破',
                    'signal': 'SELL',
                    'reason': f'MA5({ma5:.2f}) 下穿 MA20({ma20:.2f})',
                    'price': close,
                    'confidence': confidence
                }
            elif not has_prev:
                return {
                    'symbol': symbol,
                    'strategy': '均线突破',
                    'signal': 'SELL',
                    'reason': f'MA5({ma5:.2f}) < MA20({ma20:.2f}) [⚠无前日数据]',
                    'price': close,
                    'confidence': confidence * 0.6
                }
            return None

        return None

    # ========== 策略3: MACD金叉死叉（事件检测版） ==========

    def strategy_macd(self, symbol: str, factors: Dict, price: Dict,
                      prev_factors: Optional[Dict] = None) -> Optional[Dict]:
        """
        MACD策略（事件检测版）
        买入: MACD金叉 (DIF上穿DEA) — 前一天 DIF ≤ DEA，今天 DIF > DEA
        卖出: MACD死叉 (DIF下穿DEA) — 前一天 DIF ≥ DEA，今天 DIF < DEA
        """
        dif = factors.get('MACD_macd_dif')
        dea = factors.get('MACD_macd_dea')
        macd = factors.get('MACD_macd_histogram')
        # fallback for old-style factor names
        if dif is None:
            dif = factors.get('MACD_DIF')
        if dea is None:
            dea = factors.get('MACD_DEA')
        if macd is None:
            macd = factors.get('MACD_MACD')

        if dif is None or dea is None:
            return None

        # 前一天 MACD 数据
        if prev_factors is None:
            prev_dif = prev_dea = None
        else:
            prev_dif = prev_factors.get('MACD_macd_dif') or prev_factors.get('MACD_DIF')
            prev_dea = prev_factors.get('MACD_macd_dea') or prev_factors.get('MACD_DEA')

        has_prev = prev_dif is not None and prev_dea is not None
        dif_dea_diff = abs(dif - dea)
        confidence = calibrate_macd_confidence(dif_dea_diff)

        # 金叉：前一天 DIF ≤ DEA，今天 DIF > DEA
        if dif > dea:
            if has_prev and prev_dif <= prev_dea:
                return {
                    'symbol': symbol,
                    'strategy': 'MACD',
                    'signal': 'BUY',
                    'reason': f'MACD金叉 (DIF={dif:.3f}, DEA={dea:.3f})',
                    'price': price['close'],
                    'confidence': confidence
                }
            elif not has_prev:
                return {
                    'symbol': symbol,
                    'strategy': 'MACD',
                    'signal': 'BUY',
                    'reason': f'MACD金叉状态 (DIF={dif:.3f}, DEA={dea:.3f}) [⚠无前日数据]',
                    'price': price['close'],
                    'confidence': confidence * 0.6
                }
            return None

        # 死叉：前一天 DIF ≥ DEA，今天 DIF < DEA
        elif dif < dea:
            if has_prev and prev_dif >= prev_dea:
                return {
                    'symbol': symbol,
                    'strategy': 'MACD',
                    'signal': 'SELL',
                    'reason': f'MACD死叉 (DIF={dif:.3f}, DEA={dea:.3f})',
                    'price': price['close'],
                    'confidence': confidence
                }
            elif not has_prev:
                return {
                    'symbol': symbol,
                    'strategy': 'MACD',
                    'signal': 'SELL',
                    'reason': f'MACD死叉状态 (DIF={dif:.3f}, DEA={dea:.3f}) [⚠无前日数据]',
                    'price': price['close'],
                    'confidence': confidence * 0.6
                }
            return None

        return None

    # ========== 策略4: 布林带突破 ==========

    def strategy_bollinger(self, symbol: str, factors: Dict, price: Dict) -> Dict:
        """
        布林带策略
        买入: 价格触及下轨
        卖出: 价格触及上轨
        """
        upper = factors.get('BOLL_bb_upper') or factors.get('BOLL_UPPER')
        middle = factors.get('BOLL_bb_middle') or factors.get('BOLL_MIDDLE')
        lower = factors.get('BOLL_bb_lower') or factors.get('BOLL_LOWER')
        close = price['close']

        if upper is None or lower is None:
            return None

        if close <= lower:
            distance_pct = abs((lower - close) / lower)
            confidence = calibrate_bollinger_confidence(distance_pct)
            return {
                'symbol': symbol,
                'strategy': '布林带',
                'signal': 'BUY',
                'reason': f'价格触及下轨 ({close:.2f} <= {lower:.2f})',
                'price': close,
                'confidence': confidence
            }
        elif close >= upper:
            distance_pct = abs((close - upper) / upper)
            confidence = calibrate_bollinger_confidence(distance_pct)
            return {
                'symbol': symbol,
                'strategy': '布林带',
                'signal': 'SELL',
                'reason': f'价格触及上轨 ({close:.2f} >= {upper:.2f})',
                'price': close,
                'confidence': confidence
            }

        return None

    # ========== 策略5: KDJ超买超卖 ==========

    def strategy_kdj(self, symbol: str, factors: Dict, price: Dict) -> Dict:
        """
        KDJ策略
        买入: K < 20 且 D < 20 (超卖)
        卖出: K > 80 且 D > 80 (超买)
        """
        k = factors.get('KDJ_k') or factors.get('KDJ_K')
        d = factors.get('KDJ_d') or factors.get('KDJ_D')

        if k is None or d is None:
            return None

        if k < 20 and d < 20:
            confidence = calibrate_kdj_confidence(k, 20, 'buy')
            return {
                'symbol': symbol,
                'strategy': 'KDJ',
                'signal': 'BUY',
                'reason': f'KDJ超卖 (K={k:.2f}, D={d:.2f})',
                'price': price['close'],
                'confidence': confidence
            }
        elif k > 80 and d > 80:
            confidence = calibrate_kdj_confidence(k, 80, 'sell')
            return {
                'symbol': symbol,
                'strategy': 'KDJ',
                'signal': 'SELL',
                'reason': f'KDJ超买 (K={k:.2f}, D={d:.2f})',
                'price': price['close'],
                'confidence': confidence
            }

        return None

    # ========== 策略6: 放量突破（严格阈值版） ==========

    def strategy_volume_breakout(self, symbol: str, factors: Dict, price: Dict) -> Dict:
        """
        放量突破策略
        买入: 价格刚突破MA20（涨幅 2%~10%）+ 成交量放大 (VR > 1.5)
              涨幅超过10%视为追高，不触发
        卖出: 价格跌破MA20（跌幅 2%~10%）+ 成交量放大
        """
        ma20 = factors.get('MA20')
        vr = factors.get('VR')
        close = price['close']
        volume = price.get('volume', 0)

        if ma20 is None or close is None:
            return None

        breakout_pct = (close - ma20) / ma20
        volume_amplified = vr and vr > 1.5

        # 买入：突破MA20 2%-10%（太远=追高）
        if 0.02 <= breakout_pct <= 0.10 and volume_amplified:
            raw_conf = min(0.85, 0.5 + breakout_pct * 5)
            confidence = bayesian_calibrate(raw_conf)

            return {
                'symbol': symbol,
                'strategy': '放量突破',
                'signal': 'BUY',
                'reason': f'放量突破MA20 (VR={vr:.2f}, 涨幅 {breakout_pct*100:.1f}%)',
                'price': close,
                'confidence': confidence
            }

        # 卖出：跌破MA20 2%-10%（确认性下跌）
        breakdown_pct = (ma20 - close) / ma20
        if 0.02 <= breakdown_pct <= 0.10 and volume_amplified:
            raw_conf = min(0.85, 0.5 + breakdown_pct * 5)
            confidence = bayesian_calibrate(raw_conf)

            return {
                'symbol': symbol,
                'strategy': '放量突破',
                'signal': 'SELL',
                'reason': f'放量跌破MA20 (VR={vr:.2f}, 跌幅 {breakdown_pct*100:.1f}%)',
                'price': close,
                'confidence': confidence
            }

        return None

    # ========== 策略7: 均线多头排列（事件检测版） ==========

    def strategy_ma_alignment(self, symbol: str, factors: Dict, price: Dict,
                              prev_factors: Optional[Dict] = None) -> Optional[Dict]:
        """
        均线多头排列策略（事件检测版）
        买入: 新形成多头排列 MA5>MA10>MA20>MA60（前一天非多头 → 今天多头）
        卖出: 多头排列被破坏，形成空头排列 MA5<MA10<MA20（前一天非空头 → 今天空头）
        """
        ma5 = factors.get('MA5')
        ma10 = factors.get('MA10')
        ma20 = factors.get('MA20')
        ma60 = factors.get('MA60')
        close = price['close']

        if any(v is None for v in [ma5, ma10, ma20, ma60]):
            return None

        # 当天状态
        is_bullish = ma5 > ma10 > ma20 > ma60
        is_bearish = ma5 < ma10 < ma20

        # 前一天状态
        if prev_factors is None:
            prev_bullish = prev_bearish = None
        else:
            prev_ma5 = prev_factors.get('MA5')
            prev_ma10 = prev_factors.get('MA10')
            prev_ma20 = prev_factors.get('MA20')
            prev_ma60 = prev_factors.get('MA60')
            if all(v is not None for v in [prev_ma5, prev_ma10, prev_ma20, prev_ma60]):
                prev_bullish = prev_ma5 > prev_ma10 > prev_ma20 > prev_ma60
                prev_bearish = prev_ma5 < prev_ma10 < prev_ma20
            else:
                prev_bullish = prev_bearish = None
        has_prev = prev_bullish is not None

        if is_bullish and close > ma5:
            if has_prev and not prev_bullish:
                # 刚形成多头排列
                alignment_strength = (
                    (ma5 - ma10) / ma10 +
                    (ma10 - ma20) / ma20 +
                    (ma20 - ma60) / ma60
                )
                raw_conf = min(0.85, 0.45 + alignment_strength * 10)
                confidence = bayesian_calibrate(raw_conf)
                return {
                    'symbol': symbol,
                    'strategy': '均线多头排列',
                    'signal': 'BUY',
                    'reason': f'新形成多头排列 MA5({ma5:.2f})>MA10({ma10:.2f})>MA20({ma20:.2f})>MA60({ma60:.2f})',
                    'price': close,
                    'confidence': confidence
                }
            elif not has_prev:
                return {
                    'symbol': symbol,
                    'strategy': '均线多头排列',
                    'signal': 'BUY',
                    'reason': f'多头排列状态 MA5>MA10>MA20>MA60 [⚠无前日数据]',
                    'price': close,
                    'confidence': 0.5
                }
            return None

        if is_bearish:
            if has_prev and not prev_bearish:
                # 刚形成空头排列
                alignment_strength = (
                    (ma10 - ma5) / ma10 +
                    (ma20 - ma10) / ma20
                )
                raw_conf = min(0.85, 0.4 + alignment_strength * 8)
                confidence = bayesian_calibrate(raw_conf)
                return {
                    'symbol': symbol,
                    'strategy': '均线多头排列',
                    'signal': 'SELL',
                    'reason': f'空头排列形成 MA5({ma5:.2f})<MA10({ma10:.2f})<MA20({ma20:.2f})',
                    'price': close,
                    'confidence': confidence
                }
            elif not has_prev:
                return {
                    'symbol': symbol,
                    'strategy': '均线多头排列',
                    'signal': 'SELL',
                    'reason': f'空头排列状态 MA5<MA10<MA20 [⚠无前日数据]',
                    'price': close,
                    'confidence': 0.5
                }
            return None

        return None

    # ========== 策略8: ML预测 ==========

    def _init_ml_model(self) -> bool:
        """Initialize ML model (lazy load). Returns True if model is available."""
        if hasattr(self, '_ml_model'):
            return self._ml_model is not None

        try:
            import joblib
        except ImportError:
            logger.warning("⚠️  ML策略跳过: joblib未安装")
            self._ml_model = None
            return False

        quant_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_paths = [
            os.path.join(quant_root, "quantsys", "ml", "models", "xgboost_latest.pkl"),
            os.path.join(quant_root, "quantsys", "ml", "models", "xgboost_model.pkl"),
        ]
        report_paths = [
            os.path.join(quant_root, "quantsys", "ml", "models", "training_report_latest.json"),
            os.path.join(quant_root, "quantsys", "ml", "models", "training_report.json"),
        ]

        model_path = next((p for p in model_paths if os.path.exists(p)), None)
        report_path = next((p for p in report_paths if os.path.exists(p)), None)

        if model_path is None or report_path is None:
            logger.warning("⚠️  ML策略跳过: 模型或训练报告未找到")
            self._ml_model = None
            return False

        try:
            self._ml_model = joblib.load(model_path)
            report = json.loads(open(report_path, encoding='utf-8').read())
            self._ml_feature_names = report.get("feature_names", [])
            logger.info(f"✅ ML模型已加载: {model_path} (特征数: {len(self._ml_feature_names)})")
            return True
        except Exception as e:
            logger.warning(f"⚠️  ML模型加载失败: {e}")
            self._ml_model = None
            return False

    def strategy_ml_prediction(self, symbol: str, factors: Dict, price: Dict) -> Optional[Dict]:
        """ML预测策略: 使用XGBoost模型预测涨跌方向生成买卖信号。"""
        if not self._init_ml_model():
            return None

        try:
            # Build feature vector matching training order
            feature_dict = {
                "open": price.get("open", 0),
                "high": price.get("high", 0),
                "low": price.get("low", 0),
                "close": price.get("close", 0),
                "volume": price.get("volume", 0),
                **factors,  # factor values override OHLCV if names conflict
            }
            features = [float(feature_dict.get(name) or 0.0) for name in self._ml_feature_names]
            x = np.array(features, dtype=np.float64).reshape(1, -1)

            if hasattr(self._ml_model, 'predict_proba'):
                up_prob = float(self._ml_model.predict_proba(x)[0][1])
            else:
                up_prob = float(self._ml_model.predict(x)[0])

            ml_confidence = abs(up_prob - 0.5) * 2  # 0.0-1.0

            # Only emit signal if confidence > 0.3 (threshold for meaningful prediction)
            if ml_confidence < 0.3:
                return None

            if up_prob > 0.5:
                return {
                    'symbol': symbol,
                    'strategy': 'ML预测',
                    'signal': 'BUY',
                    'reason': f'ML预测上涨 (概率: {up_prob:.1%})',
                    'price': price['close'],
                    'confidence': ml_confidence,
                }
            else:
                return {
                    'symbol': symbol,
                    'strategy': 'ML预测',
                    'signal': 'SELL',
                    'reason': f'ML预测下跌 (概率: {up_prob:.1%})',
                    'price': price['close'],
                    'confidence': ml_confidence,
                }

        except Exception as e:
            logger.debug(f"ML预测 {symbol} 失败: {e}")
            return None

    # ========== 综合信号生成 ==========

    def generate_signals(self, symbols: List[str], date: str) -> Tuple[List[Dict], Dict[str, Dict]]:
        """为所有股票生成信号，返回信号列表和因子字典"""
        all_signals = []
        all_factors_map = {}  # 存储每个股票的因子数据

        # 获取前一个交易日，用于穿越检测
        prev_date = self.get_prev_trading_date(date)
        if prev_date:
            logger.info(f"前一个交易日: {prev_date}（用于金叉/死叉检测）")
        else:
            logger.warning("⚠️ 未找到前一个交易日，均线/MACD/多头排列将降级为状态判断")

        for symbol in symbols:
            try:
                # 获取因子和价格
                factors = self.get_stock_factors(symbol, date)
                price = self.get_stock_price(symbol, date)

                if not factors or not price:
                    continue
            except Exception as e:
                logger.warning(f"  ⚠️  跳过 {symbol}（数据获取失败: {e}）")
                continue

            # 获取前一天因子（用于穿越检测）
            prev_factors = None
            if prev_date:
                try:
                    prev_factors = self.get_stock_factors(symbol, prev_date)
                    if not prev_factors:
                        prev_factors = None  # 确保为 None 而非空 dict
                except Exception:
                    prev_factors = None

            # 保存当前因子数据供后续持久化使用
            all_factors_map[symbol] = factors

            # 运行所有策略
            # 需要前一天数据的策略通过 prev_factors 参数传递
            crossover_strategies = {
                self.strategy_ma_crossover,
                self.strategy_macd,
                self.strategy_ma_alignment,
            }

            strategies = [
                self.strategy_rsi_reversal,
                self.strategy_ma_crossover,
                self.strategy_macd,
                self.strategy_bollinger,
                self.strategy_kdj,
                self.strategy_volume_breakout,
                self.strategy_ma_alignment,
                self.strategy_ml_prediction,
            ]

            for strategy_func in strategies:
                try:
                    if strategy_func in crossover_strategies:
                        signal = strategy_func(symbol, factors, price, prev_factors)
                    else:
                        signal = strategy_func(symbol, factors, price)
                    if signal:
                        signal['date'] = date
                        signal['timestamp'] = datetime.now().isoformat()
                        all_signals.append(signal)
                except Exception as e:
                    logger.warning(f"  ⚠️  {symbol} 策略 {strategy_func.__name__} 失败: {e}")
                    continue

        return all_signals, all_factors_map


def save_signals(signals: List[Dict], output_path: str):
    """保存信号到 JSON 文件"""
    # 按信心度排序
    signals.sort(key=lambda x: x['confidence'], reverse=True)

    # 统计信息
    buy_signals = [s for s in signals if s['signal'] == 'BUY']
    sell_signals = [s for s in signals if s['signal'] == 'SELL']

    output = {
        'generated_at': datetime.now().isoformat(),
        'date': signals[0]['date'] if signals else None,
        'summary': {
            'total': len(signals),
            'buy': len(buy_signals),
            'sell': len(sell_signals)
        },
        'signals': signals
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 信号已保存到: {output_path}")


def extract_factors_from_signal(signal: Dict, all_factors: Dict) -> List[Dict[str, Any]]:
    """从信号中提取因子信息，用于持久化到 signal_factors 表"""
    symbol = signal['symbol']
    date = signal['date']
    strategy = signal['strategy']

    factors_list = []

    # 策略到因子的映射
    strategy_factor_map = {
        'RSI反转': ['RSI12'],
        '均线突破': ['MA5', 'MA20'],
        'MACD': ['MACD_macd_dif', 'MACD_macd_dea', 'MACD_macd_histogram'],
        '布林带': ['BOLL_bb_upper', 'BOLL_bb_middle', 'BOLL_bb_lower'],
        'KDJ': ['KDJ_k', 'KDJ_d', 'KDJ_j'],
        '放量突破': ['MA20', 'VR'],
        '均线多头排列': ['MA5', 'MA10', 'MA20', 'MA60'],
        'ML预测': [],  # ML uses all features, no single factor mapping
    }

    factor_names = strategy_factor_map.get(strategy, [])

    for idx, factor_name in enumerate(factor_names):
        factor_value = all_factors.get(factor_name)
        if factor_value is not None:
            factors_list.append({
                'symbol': symbol,
                'signal_date': date,
                'strategy_name': strategy,
                'factor_name': factor_name,
                'factor_value': float(factor_value),
                'factor_weight': None,  # 可以后续优化添加权重
                'trigger_condition': None,  # 可以后续添加触发条件描述
                'is_primary': (idx == 0)  # 第一个因子标记为主因子
            })

    return factors_list


def persist_signals_to_database(db: Database, signals: List[Dict], signal_date: str, all_factors_map: Dict[str, Dict]):
    """将信号和因子持久化到数据库"""
    if not signals:
        logger.info("没有信号需要持久化")
        return

    try:
        # 准备信号数据
        signal_rows = []
        for signal in signals:
            signal_rows.append({
                'symbol': normalize_symbol(signal['symbol']),
                'signal_date': signal['date'],
                'signal_type': signal['signal'],
                'strategy_name': signal['strategy'],
                'confidence': float(signal.get('confidence', 0.0)),
                'price': float(signal.get('price', 0.0)),
                'reason': signal.get('reason', ''),
                'metadata': json.dumps({
                    'timestamp': signal.get('timestamp'),
                    'generated_by': 'generate_signals.py'
                })
            })

        # 准备因子数据
        factor_rows = []
        for signal in signals:
            symbol = signal['symbol']
            factors = all_factors_map.get(symbol, {})
            if factors:
                signal_factors = extract_factors_from_signal(signal, factors)
                factor_rows.extend(signal_factors)

        # 持久化到数据库
        symbols = [normalize_symbol(s['symbol']) for s in signals]
        count = db.replace_trading_signals_for_date(
            signal_date=signal_date,
            signals=signal_rows,
            signal_factors=factor_rows,
            symbols=symbols
        )

        logger.info(f"✅ 已将 {count} 条信号持久化到数据库")
        logger.info(f"✅ 已将 {len(factor_rows)} 条因子详情持久化到数据库")

    except Exception as e:
        logger.error(f"❌ 数据库持久化失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # 不抛出异常，允许继续保存到 JSON


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='交易信号生成脚本')
    parser.add_argument('--symbols', type=str, help='股票代码列表，逗号分隔；不传则生成全部A股信号')
    parser.add_argument('--date', type=str, help='指定信号日期（YYYY-MM-DD），不传则使用最新K线日期')
    parser.add_argument('--job-id', type=str, help='后端异步任务ID，用于兼容API任务调度')
    return parser


def main():
    """主函数"""
    args = build_arg_parser().parse_args()

    logger.info("=" * 60)
    logger.info("交易信号生成任务开始")
    if args.job_id:
        logger.info(f"任务ID: {args.job_id}")
    logger.info(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 使用环境变量 QUANT_DB_PROVIDER 决定数据库（默认 postgres）
    os.environ.setdefault("QUANT_DB_PROVIDER", "postgres")
    db = Database()
    generator = SignalGenerator(db)

    # 获取日期：优先用参数，否则用最新K线日期
    if args.date:
        latest_date = args.date
        logger.info(f"使用指定日期: {latest_date}")
    else:
        latest_date = generator.get_latest_date()
        logger.info(f"最新数据日期: {latest_date}")

    # 获取股票范围
    symbols = parse_symbols(args.symbols) or db.get_all_symbols(
        market='A', exclude_st=True, exclude_suspended=True
    )
    logger.info(f"共 {len(symbols)} 只股票需要生成信号")
    logger.info("")

    # 生成信号
    signals, all_factors_map = generator.generate_signals(symbols, latest_date)

    logger.info("")
    logger.info("=" * 60)
    logger.info("信号生成完成")
    logger.info(f"总信号数: {len(signals)}")
    logger.info(f"买入信号: {len([s for s in signals if s['signal'] == 'BUY'])}")
    logger.info(f"卖出信号: {len([s for s in signals if s['signal'] == 'SELL'])}")
    logger.info("=" * 60)

    # 持久化到数据库（PostgreSQL）
    persist_signals_to_database(db, signals, latest_date, all_factors_map)

    # 保存信号到 JSON（向后兼容）
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest'
    )
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'signals.json')
    save_signals(signals, output_path)

    # 显示Top 10信号
    if signals:
        logger.info("\n📊 Top 10 买入信号:")
        buy_signals = [s for s in signals if s['signal'] == 'BUY'][:10]
        for i, sig in enumerate(buy_signals, 1):
            logger.info(f"  {i}. {sig['symbol']} | {sig['strategy']} | "
                       f"信心度: {sig['confidence']:.2f} | {sig['reason']}")

        logger.info("\n📊 Top 10 卖出信号:")
        sell_signals = [s for s in signals if s['signal'] == 'SELL'][:10]
        for i, sig in enumerate(sell_signals, 1):
            logger.info(f"  {i}. {sig['symbol']} | {sig['strategy']} | "
                       f"信心度: {sig['confidence']:.2f} | {sig['reason']}")


if __name__ == '__main__':
    main()
