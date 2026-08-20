"""
V14模型因子重要性分析工具

分析V14模型中哪些因子贡献最大，用于：
1. 理解模型决策逻辑
2. 识别关键Alpha因子
3. 为V15优化提供方向
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
import xgboost as xgb

def analyze_factor_importance():
    """分析因子重要性"""

    print("\n" + "="*80)
    print(" V14模型因子重要性分析 ")
    print("="*80)

    # 加载模型
    model_path = Path('live_trading/models/v13_model.json')
    if not model_path.exists():
        print(f"\n❌ 模型文件不存在: {model_path}")
        print("   请先训练模型")
        return

    print(f"\n加载模型: {model_path}")
    model = xgb.XGBRegressor()
    model.load_model(str(model_path))

    # 加载因子列表
    factors_path = Path('live_trading/models/valid_factors.json')
    if not factors_path.exists():
        print(f"\n❌ 因子列表不存在: {factors_path}")
        return

    with open(factors_path) as f:
        factors = json.load(f)

    print(f"✓ 有效因子: {len(factors)}个")

    # 获取特征重要性
    importance_dict = model.get_booster().get_score(importance_type='gain')

    # 映射到因子名称
    feature_importance = {}
    for key, value in importance_dict.items():
        # XGBoost可能返回特征名称或f0, f1格式
        if key.startswith('f') and key[1:].isdigit():
            idx = int(key[1:])
            if idx < len(factors):
                feature_importance[factors[idx]] = value
        elif key in factors:
            feature_importance[key] = value

    # 排序
    sorted_factors = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)

    # 分类统计
    categories = {
        '动量因子': ['momentum', 'reversal'],
        '技术因子': ['ma_', 'rsi', 'macd', 'bollinger', 'cci', 'williams'],
        '资金流因子': ['inflow', 'fund_flow', 'order'],
        '相对强度因子': ['relative', 'excess', 'beta'],
        '波动率因子': ['volatility', 'atr'],
        '基本面因子': ['roe', 'margin', 'debt', 'revenue', 'ocf', 'roa'],
        '情绪因子': ['shock', 'sentiment', 'limit_up', 'amplitude'],
        '形态因子': ['shadow', 'candle', 'consecutive', 'gap', 'breakout']
    }

    category_importance = {cat: 0 for cat in categories}
    for factor, importance in sorted_factors:
        for cat, keywords in categories.items():
            if any(kw in factor for kw in keywords):
                category_importance[cat] += importance
                break

    # 输出结果
    print("\n" + "="*80)
    print("Top 20 重要因子")
    print("="*80)
    print(f"\n{'排名':<5} {'因子名称':<30} {'重要性':>15} {'累计占比':>15}")
    print("-"*80)

    total_importance = sum(importance_dict.values())
    cumulative = 0

    for i, (factor, importance) in enumerate(sorted_factors[:20], 1):
        cumulative += importance
        pct = (importance / total_importance) * 100
        cum_pct = (cumulative / total_importance) * 100
        print(f"{i:<5} {factor:<30} {importance:>15.2f} {cum_pct:>14.1f}%")

    print("\n" + "="*80)
    print("因子类别贡献度")
    print("="*80)

    sorted_categories = sorted(category_importance.items(), key=lambda x: x[1], reverse=True)
    print(f"\n{'类别':<20} {'重要性':>20} {'占比':>15}")
    print("-"*80)

    for cat, importance in sorted_categories:
        pct = (importance / total_importance) * 100
        print(f"{cat:<20} {importance:>20.2f} {pct:>14.1f}%")

    # 洞察分析
    print("\n" + "="*80)
    print("关键洞察")
    print("="*80)

    top_category = sorted_categories[0][0]
    top_factor = sorted_factors[0][0]

    print(f"\n1. 最重要因子: {top_factor}")
    print(f"   贡献度: {sorted_factors[0][1]:.2f}")

    print(f"\n2. 最重要类别: {top_category}")
    print(f"   贡献度: {sorted_categories[0][1]:.2f} ({(sorted_categories[0][1]/total_importance*100):.1f}%)")

    print(f"\n3. Top 5因子集中度:")
    top5_importance = sum(imp for _, imp in sorted_factors[:5])
    top5_pct = (top5_importance / total_importance) * 100
    print(f"   {top5_pct:.1f}%")

    print(f"\n4. Top 20因子集中度:")
    top20_importance = sum(imp for _, imp in sorted_factors[:20])
    top20_pct = (top20_importance / total_importance) * 100
    print(f"   {top20_pct:.1f}%")

    # 优化建议
    print("\n" + "="*80)
    print("V15优化建议")
    print("="*80)

    print("\n基于因子重要性分析，V15模型可以:")
    print(f"  1. 聚焦Top 30核心因子（当前{len(factors)}个）")
    print(f"  2. 强化{top_category}计算精度")
    print(f"  3. 剔除低贡献度因子（贡献<1%）")
    print(f"  4. 增加{top_factor}的衍生因子")

    # 保存分析结果
    analysis_result = {
        'top_20_factors': [
            {'rank': i+1, 'factor': f, 'importance': float(imp)}
            for i, (f, imp) in enumerate(sorted_factors[:20])
        ],
        'category_importance': {
            cat: float(imp) for cat, imp in sorted_categories
        },
        'insights': {
            'top_factor': top_factor,
            'top_category': top_category,
            'top5_concentration': f"{top5_pct:.1f}%",
            'top20_concentration': f"{top20_pct:.1f}%"
        }
    }

    result_path = Path('live_trading/v14_factor_importance.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_result, f, indent=2, ensure_ascii=False)

    print(f"\n📁 分析结果已保存: {result_path}")
    print("\n" + "="*80)

if __name__ == '__main__':
    analyze_factor_importance()
