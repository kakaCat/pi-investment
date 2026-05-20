#!/usr/bin/env python3
"""
分析模型中哪些因子最重要（HTTP 客户端版）

通过调用 Flask API 获取因子重要性排名。
前置条件: Flask API 服务运行在 localhost:5001

使用方法：
python scripts/analyze_feature_importance.py
"""

import sys
import json
import requests

API_BASE = "http://localhost:5001"


def main():
    print("=" * 60)
    print("特征重要性分析 (API 模式)")
    print("=" * 60)

    # 检查 API 健康
    try:
        health = requests.get(f"{API_BASE}/api/health", timeout=5)
        if health.status_code != 200 or not health.json().get('model_loaded'):
            print("❌ API 不可用或模型未加载")
            print("   请先启动: python3 quant/api/server.py")
            return
    except requests.ConnectionError:
        print(f"❌ 无法连接到 API 服务 ({API_BASE})")
        print("   请先启动: python3 quant/api/server.py")
        return

    # 获取因子重要性
    print("\n获取因子重要性...")
    try:
        resp = requests.get(f"{API_BASE}/api/feature-importance", timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"❌ API 请求失败: {e}")
        return

    features = data.get('features', [])
    if not features:
        print("❌ 无因子重要性数据")
        return

    # 显示 Top 15
    print("\n" + "=" * 60)
    print("🏆 Top 15 最重要的因子")
    print("=" * 60)
    for i, f in enumerate(features[:15], 1):
        bar = "█" * int(f['percentage'] / 2)
        print(f"{i:2d}. {f['feature']:25s} | {f['importance']:.4f} | {f['percentage']:5.1f}% {bar}")

    # 80/20 法则
    top_20 = data.get('top_20_percent_count', 0)
    total = data.get('total_features', 0)
    if top_20 and total:
        print(f"\n💡 80/20法则: 前 {top_20}/{total} 个因子贡献了 80% 的预测能力")
        print(f"   占比: {top_20/total*100:.1f}%")

    # 保存
    try:
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / '.pi-invest'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'feature_importance.json'
        with open(output_path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n📄 详细数据已保存: {output_path}")
    except Exception as e:
        print(f"\n⚠️  保存失败: {e}")


if __name__ == '__main__':
    main()
