#!/usr/bin/env python3
"""
增强版报告 - 因子分析（HTTP 客户端版）

通过 Flask API 获取因子数据，生成本地增强报告。
前置条件: Flask API 服务运行在 localhost:5001
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import requests

API_BASE = "http://localhost:5001"


def interpret_factor(name: str, value: float) -> str:
    """解释因子含义"""
    interpretations = {
        'RSI': '超买' if value > 70 else '超卖' if value < 30 else '中性',
        'MACD_DIF': '多头' if value > 0 else '空头',
        'KDJ_K': '超买' if value > 80 else '超卖' if value < 20 else '中性',
        'CCI': '超买' if value > 100 else '超卖' if value < -100 else '中性',
        'BB_Position': '上轨' if value > 0.8 else '下轨' if value < 0.2 else '中轨',
    }
    for key, pattern in interpretations.items():
        if key in name:
            return pattern
    return '-'


def analyze_stock(symbol: str) -> dict:
    """通过 API 分析单只股票"""
    try:
        resp = requests.get(f"{API_BASE}/api/stock/{symbol}/factors", timeout=30)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def main():
    print("=" * 60)
    print("增强版因子分析报告 (API 模式)")
    print("=" * 60)

    # 参数
    symbols_arg = sys.argv[1] if len(sys.argv) > 1 else None

    # 检查 API
    try:
        requests.get(f"{API_BASE}/api/health", timeout=5)
    except requests.ConnectionError:
        print(f"❌ 无法连接到 API ({API_BASE})")
        return

    # 获取股票列表
    if symbols_arg:
        symbols = [s.strip() for s in symbols_arg.split(',')]
    else:
        # 从 signals 获取热门股票
        resp = requests.get(f"{API_BASE}/api/signals", timeout=30)
        signals = resp.json().get('signals', [])
        symbols = list(set(s.get('symbol', '') for s in signals[:20]))[:10]
        if not symbols:
            # fallback: 获取前10只有数据的股票
            resp = requests.get(f"{API_BASE}/api/stocks/data-status", timeout=30)
            stocks = resp.json().get('stocks', [])
            symbols = [s['symbol'] for s in stocks[:10]]

    if not symbols:
        print("❌ 无待分析股票")
        return

    print(f"分析 {len(symbols)} 只股票: {', '.join(symbols[:10])}")
    print()

    results = []
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] 分析 {symbol}...")
        data = analyze_stock(symbol)
        if data:
            results.append(data)

    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 因子分析摘要")
    print("=" * 60)

    for r in sorted(results, key=lambda x: x['prediction']['up_probability'], reverse=True):
        symbol = r['symbol']
        pred = r['prediction']
        direction = '📈' if pred['direction'] == 'UP' else '📉'
        print(f"\n{direction} {symbol} | 价格: ¥{r['price']:.2f} | "
              f"上涨概率: {pred['up_probability']:.2%} | 置信度: {pred['confidence']:.2%}")

        # Top 3 关键因子
        for factor in r.get('key_factors', [])[:3]:
            contrib = factor['contribution']
            arrow = '↑' if contrib > 0 else '↓'
            interp = interpret_factor(factor['name'], factor['value'])
            print(f"    {arrow} {factor['name']:20s} = {factor['value']:8.4f} "
                  f"(贡献: {contrib:+.4f}, {interp})")

    # 保存
    output_dir = Path(__file__).parent.parent / '.pi-invest'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'enhanced_report_{datetime.now().strftime("%Y%m%d")}.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📄 报告已保存: {output_path}")


if __name__ == '__main__':
    main()
