#!/usr/bin/env python3
"""
分析单只股票的因子贡献（HTTP 客户端版）

通过调用 Flask API 获取因子分析和ML预测结果。
前置条件: Flask API 服务运行在 localhost:5001

使用方法：
python scripts/analyze_stock_factors.py 000001
python scripts/analyze_stock_factors.py 600036 2026-05-18
"""

import sys
import json
import requests

API_BASE = "http://localhost:5001"


def main():
    if len(sys.argv) < 2:
        print("使用方法: python analyze_stock_factors.py <股票代码> [日期]")
        print("示例: python analyze_stock_factors.py 000001")
        print("示例: python analyze_stock_factors.py 600036 2026-05-18")
        print("\n⚠️  请确保 Flask API 已启动: python3 quant/api/server.py")
        return

    symbol = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else None

    print("=" * 60)
    print(f"分析股票: {symbol}")
    print("=" * 60)

    # 检查 API 健康状态
    try:
        health = requests.get(f"{API_BASE}/api/health", timeout=5)
        if health.status_code != 200:
            print(f"❌ API 服务异常: {health.status_code}")
            return
    except requests.ConnectionError:
        print(f"❌ 无法连接到 API 服务 ({API_BASE})")
        print("   请先启动: python3 quant/api/server.py")
        return

    # 调用因子分析端点
    url = f"{API_BASE}/api/stock/{symbol}/factors"
    params = {}
    if date:
        params['date'] = date

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 404:
            print(f"❌ 未找到股票 {symbol} 的数据")
            return
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"❌ API 请求失败: {e}")
        return

    # 显示结果
    print(f"分析日期: {data['date']}")
    print(f"当前价格: ¥{data['price']:.2f}")
    print(f"预测方向: {'📈 看涨' if data['prediction']['direction'] == 'UP' else '📉 看跌'}")
    print(f"上涨概率: {data['prediction']['up_probability']:.2%}")
    print(f"置信度:   {data['prediction']['confidence']:.2%}")
    print()
    print("=" * 60)
    print("因子贡献分析 (Top 10)")
    print("=" * 60)

    if not data.get('key_factors'):
        print("⚠️  因子贡献数据不可用（模型可能不支持 feature_importances_）")
        return

    for i, factor in enumerate(data['key_factors'][:10], 1):
        direction = "📈" if factor['contribution'] > 0 else "📉"
        print(f"{i:2d}. {direction} {factor['name']:25s} | "
              f"值: {factor['value']:10.4f} | "
              f"重要性: {factor['importance']:.4f} | "
              f"贡献: {factor['contribution']:+10.4f}")

    # 保存结果
    output_dir = sys.path[0]
    try:
        import os
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / '.pi-invest'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f'factor_analysis_{symbol}_{data["date"]}.json'
        with open(output_path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n📄 详细分析已保存: {output_path}")
    except Exception as e:
        print(f"\n⚠️  保存失败: {e}")


if __name__ == '__main__':
    main()
