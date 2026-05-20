#!/usr/bin/env python3
"""
持仓风险检查脚本（HTTP 客户端版）

通过调用 Flask API 检查持仓风险。
前置条件: Flask API 服务运行在 localhost:5001

使用方法：
python scripts/risk_check.py
python scripts/risk_check.py --symbols 000425,600036
"""

import sys
import json
import argparse
import requests

API_BASE = "http://localhost:5001"


def main():
    parser = argparse.ArgumentParser(description='持仓风险检查')
    parser.add_argument('--symbols', type=str, help='股票代码（逗号分隔），不传则检查全部')
    parser.add_argument('--account-value', type=float, help='账户总资金（元）')
    args = parser.parse_args()

    print("=" * 60)
    print("持仓风险检查 (API 模式)")
    print("=" * 60)

    # 检查 API 健康
    try:
        health = requests.get(f"{API_BASE}/api/health", timeout=5)
        if health.status_code != 200:
            print("❌ API 不可用")
            return
    except requests.ConnectionError:
        print(f"❌ 无法连接到 API 服务 ({API_BASE})")
        print("   请先启动: python3 quant/api/server.py")
        return

    # 构建请求
    payload = {}
    if args.symbols:
        payload['symbols'] = [s.strip() for s in args.symbols.split(',')]
    if args.account_value:
        payload['account_value'] = args.account_value

    try:
        resp = requests.post(f"{API_BASE}/api/risk/check", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"❌ API 请求失败: {e}")
        return

    # 风险等级颜色
    level_colors = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}
    risk_level = data.get('risk_level', 'unknown')
    risk_score = data.get('risk_score', 0)

    print(f"\n整体风险评分: {risk_score}/100 {level_colors.get(risk_level, '⚪')}")
    print(f"风险等级: {risk_level.upper()}")
    print(f"持仓数量: {data.get('holdings_count', 0)}")
    print()

    for check in data.get('checks', []):
        symbol = check['symbol']
        name = check.get('name', '')
        pnl_pct = check.get('pnl_pct')
        score = check.get('score', 100)

        status = level_colors['low'] if score >= 80 else level_colors['medium'] if score >= 50 else level_colors['high']
        print(f"{status} {symbol} {name}")
        print(f"   评分: {score}/100 | 成本: ¥{check.get('avg_cost', 0):.2f} | 现价: ¥{check.get('current_price', 0) or 'N/A'}")
        if pnl_pct is not None:
            print(f"   盈亏: {pnl_pct:+.2f}%")

        for c in check.get('checks', []):
            icon = '🔴' if c['level'] == 'high' else '🟡' if c['level'] == 'medium' else 'ℹ️'
            print(f"   {icon} {c['message']}")
            if c.get('suggestion'):
                print(f"      💡 {c['suggestion']}")
        print()


if __name__ == '__main__':
    main()
