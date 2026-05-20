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
from typing import List, Dict
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database
from quantsys.utils.confidence_calibration import (
    calibrate_rsi_confidence,
    calibrate_ma_confidence,
    calibrate_macd_confidence,
    calibrate_bollinger_confidence,
    calibrate_kdj_confidence
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

        if rsi < 30:
            confidence = calibrate_rsi_confidence(rsi, 30, 'buy')
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

    # ========== 策略2: 均线突破策略 ==========

    def strategy_ma_crossover(self, symbol: str, factors: Dict, price: Dict) -> Dict:
        """
        均线突破策略
        买入: MA5 上穿 MA20
        卖出: MA5 下穿 MA20
        """
        ma5 = factors.get('MA5')
        ma20 = factors.get('MA20')
        close = price['close']

        if ma5 is None or ma20 is None:
            return None

        # 计算穿越强度
        ma_diff_pct = abs(ma5 - ma20) / ma20
        confidence = calibrate_ma_confidence(ma_diff_pct)

        if ma5 > ma20 and close > ma5:
            return {
                'symbol': symbol,
                'strategy': '均线突破',
                'signal': 'BUY',
                'reason': f'MA5({ma5:.2f}) > MA20({ma20:.2f})',
                'price': close,
                'confidence': confidence
            }
        elif ma5 < ma20 and close < ma5:
            return {
                'symbol': symbol,
                'strategy': '均线突破',
                'signal': 'SELL',
                'reason': f'MA5({ma5:.2f}) < MA20({ma20:.2f})',
                'price': close,
                'confidence': confidence
            }

        return None

    # ========== 策略3: MACD金叉死叉 ==========

    def strategy_macd(self, symbol: str, factors: Dict, price: Dict) -> Dict:
        """
        MACD策略
        买入: MACD金叉 (DIF上穿DEA)
        卖出: MACD死叉 (DIF下穿DEA)
        """
        dif = factors.get('MACD_DIF')
        dea = factors.get('MACD_DEA')
        macd = factors.get('MACD_MACD')

        if dif is None or dea is None:
            return None

        dif_dea_diff = abs(dif - dea)
        confidence = calibrate_macd_confidence(dif_dea_diff)

        if dif > dea and macd > 0:
            return {
                'symbol': symbol,
                'strategy': 'MACD',
                'signal': 'BUY',
                'reason': f'MACD金叉 (DIF={dif:.3f}, DEA={dea:.3f})',
                'price': price['close'],
                'confidence': confidence
            }
        elif dif < dea and macd < 0:
            return {
                'symbol': symbol,
                'strategy': 'MACD',
                'signal': 'SELL',
                'reason': f'MACD死叉 (DIF={dif:.3f}, DEA={dea:.3f})',
                'price': price['close'],
                'confidence': confidence
            }

        return None

    # ========== 策略4: 布林带突破 ==========

    def strategy_bollinger(self, symbol: str, factors: Dict, price: Dict) -> Dict:
        """
        布林带策略
        买入: 价格触及下轨
        卖出: 价格触及上轨
        """
        upper = factors.get('BOLL_UPPER')
        middle = factors.get('BOLL_MIDDLE')
        lower = factors.get('BOLL_LOWER')
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
        k = factors.get('KDJ_K')
        d = factors.get('KDJ_D')

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

    # ========== 综合信号生成 ==========

    def generate_signals(self, symbols: List[str], date: str) -> List[Dict]:
        """为所有股票生成信号"""
        all_signals = []

        for symbol in symbols:
            # 获取因子和价格
            factors = self.get_stock_factors(symbol, date)
            price = self.get_stock_price(symbol, date)

            if not factors or not price:
                continue

            # 运行所有策略
            strategies = [
                self.strategy_rsi_reversal,
                self.strategy_ma_crossover,
                self.strategy_macd,
                self.strategy_bollinger,
                self.strategy_kdj,
            ]

            for strategy_func in strategies:
                try:
                    signal = strategy_func(symbol, factors, price)
                    if signal:
                        signal['date'] = date
                        signal['timestamp'] = datetime.now().isoformat()
                        all_signals.append(signal)
                except Exception as e:
                    logger.warning(f"  ⚠️  {symbol} 策略 {strategy_func.__name__} 失败: {e}")
                    continue

        return all_signals


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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='交易信号生成脚本')
    parser.add_argument('--symbols', type=str, help='股票代码列表，逗号分隔；不传则生成全部A股信号')
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

    # 数据库路径
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest', 'stock-db', 'stocks.db'
    )

    db = Database(db_path)
    generator = SignalGenerator(db)

    # 获取最新日期
    latest_date = generator.get_latest_date()
    logger.info(f"最新数据日期: {latest_date}")

    # 获取股票范围
    symbols = parse_symbols(args.symbols) or db.get_all_symbols(market='A')
    logger.info(f"共 {len(symbols)} 只股票需要生成信号")
    logger.info("")

    # 生成信号
    signals = generator.generate_signals(symbols, latest_date)

    logger.info("")
    logger.info("=" * 60)
    logger.info("信号生成完成")
    logger.info(f"总信号数: {len(signals)}")
    logger.info(f"买入信号: {len([s for s in signals if s['signal'] == 'BUY'])}")
    logger.info(f"卖出信号: {len([s for s in signals if s['signal'] == 'SELL'])}")
    logger.info("=" * 60)

    # 保存信号
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
