#!/usr/bin/env python3
"""
动态因子权重智能选股系统 - 演示脚本

展示固定权重 vs 动态权重的差异
"""
import requests
import json
from typing import Dict, List

API_BASE = "http://127.0.0.1:5001"

def scan_with_weights(stocks: List[str], weights: Dict = None) -> List[Dict]:
    """使用指定权重扫描股票"""
    payload = {
        "stocks": stocks,
        "min_score": 0
    }
    if weights:
        payload["weights"] = weights

    response = requests.post(f"{API_BASE}/api/signals/scan", json=payload)
    data = response.json()
    return data.get("opportunities", [])

def print_results(title: str, opportunities: List[Dict]):
    """打印结果"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")

    for opp in opportunities:
        print(f"\n{opp['name']} ({opp['symbol']})")
        print(f"  综合评分: {opp['score']}")
        print(f"  技术: {opp['technical_score']} | 基本面: {opp['fundamental_score']} | 资金: {opp['capital_score']}")
        print(f"  风险等级: {opp['risk_level']}")

def main():
    print("🚀 动态因子权重智能选股系统 - 演示")
    print("="*60)

    # 测试股票
    stocks = ["600519", "000858", "601318"]

    # 场景1: 默认固定权重（技术50% + 基本面30% + 资金20%）
    print("\n📊 场景1: 默认固定权重")
    print("权重配置: 技术50% + 基本面30% + 资金20%")
    results_default = scan_with_weights(stocks)
    print_results("默认固定权重结果", results_default)

    # 场景2: 技术面主导（适合趋势行情）
    print("\n\n📈 场景2: 技术面主导（趋势行情）")
    print("权重配置: 技术70% + 基本面20% + 资金10%")
    print("适用: 牛市、强趋势、短期交易")
    results_technical = scan_with_weights(stocks, {
        "technical": 0.7,
        "fundamental": 0.2,
        "capital": 0.1
    })
    print_results("技术面主导结果", results_technical)

    # 场景3: 基本面主导（适合价值投资）
    print("\n\n💰 场景3: 基本面主导（价值投资）")
    print("权重配置: 技术20% + 基本面60% + 资金20%")
    print("适用: 熊市、震荡市、长期投资")
    results_fundamental = scan_with_weights(stocks, {
        "technical": 0.2,
        "fundamental": 0.6,
        "capital": 0.2
    })
    print_results("基本面主导结果", results_fundamental)

    # 场景4: 资金面主导（适合短线）
    print("\n\n🔥 场景4: 资金面主导（短线交易）")
    print("权重配置: 技术30% + 基本面20% + 资金50%")
    print("适用: 热点炒作、资金驱动行情")
    results_capital = scan_with_weights(stocks, {
        "technical": 0.3,
        "fundamental": 0.2,
        "capital": 0.5
    })
    print_results("资金面主导结果", results_capital)

    # 对比分析
    print("\n\n" + "="*60)
    print("📊 对比分析")
    print("="*60)

    for stock in stocks:
        opp_default = next((o for o in results_default if o['symbol'] == stock), None)
        opp_tech = next((o for o in results_technical if o['symbol'] == stock), None)
        opp_fund = next((o for o in results_fundamental if o['symbol'] == stock), None)
        opp_cap = next((o for o in results_capital if o['symbol'] == stock), None)

        if all([opp_default, opp_tech, opp_fund, opp_cap]):
            print(f"\n{opp_default['name']} ({stock})")
            print(f"  默认权重:   {opp_default['score']}")
            print(f"  技术主导:   {opp_tech['score']} ({opp_tech['score'] - opp_default['score']:+d})")
            print(f"  基本面主导: {opp_fund['score']} ({opp_fund['score'] - opp_default['score']:+d})")
            print(f"  资金主导:   {opp_cap['score']} ({opp_cap['score'] - opp_default['score']:+d})")

            # 推荐场景
            scores = {
                "技术主导": opp_tech['score'],
                "基本面主导": opp_fund['score'],
                "资金主导": opp_cap['score']
            }
            best_scenario = max(scores, key=scores.get)
            print(f"  ✨ 最优场景: {best_scenario} (评分: {scores[best_scenario]})")

    print("\n\n" + "="*60)
    print("✅ 演示完成")
    print("="*60)
    print("\n💡 关键洞察:")
    print("  • 不同权重配置对评分影响显著")
    print("  • 技术面强的股票在技术主导场景下评分更高")
    print("  • 基本面好的股票在价值投资场景下更优")
    print("  • 动态权重能根据市场环境自动优化配置")
    print("\n📚 详细文档:")
    print("  • 设计: docs/features/dynamic-factor-weight-stock-screener.md")
    print("  • 实现: docs/features/dynamic-factor-weight-implementation-summary.md")
    print("  • 测试: docs/testing/smart-stock-screener-test.md")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("❌ 错误: 无法连接到 quantsys-v2 服务")
        print("请先启动服务: cd quantsys-v2 && python start_all.py")
    except Exception as e:
        print(f"❌ 错误: {e}")
