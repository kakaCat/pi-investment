#!/usr/bin/env python3
"""
P1-5.1 收缩协方差测试脚本
测试三级降级：2-4只/5-9只/10+只
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from domain.factors.models.barra import BarraRiskModelCalculator
import pandas as pd
import numpy as np

def generate_mock_returns(symbols, n_periods=60):
    """生成模拟收益率数据"""
    np.random.seed(42)
    returns = {}
    for symbol in symbols:
        returns[symbol] = np.random.randn(n_periods) * 0.02
    return pd.DataFrame(returns).T

def generate_mock_factors(symbols, n_factors=5):
    """生成模拟因子暴露"""
    np.random.seed(42)
    factor_names = ['size', 'value', 'momentum', 'volatility', 'liquidity'][:n_factors]
    factors = {}
    for factor in factor_names:
        factors[factor] = np.random.randn(len(symbols))
    return pd.DataFrame(factors, index=symbols)

def test_tier1_very_small(n_stocks=3):
    """测试 Tier 1: 2-4 只股票 -> 单因子模式"""
    print("\n" + "="*60)
    print(f"测试 Tier 1: {n_stocks} 只股票（单因子模式）")
    print("="*60)
    
    symbols = ['600519', '000858', '601318'][:n_stocks]
    returns = generate_mock_returns(symbols)
    factors = generate_mock_factors(symbols, n_factors=5)
    
    calc = BarraRiskModelCalculator()
    
    try:
        result = calc.calculate(
            returns=returns,
            factor_exposures=factors
        )
        
        value = result.get('value', {})
        print(f"✓ 自动降级成功")
        print(f"  - 股票数: {value.get('n_stocks')}")
        print(f"  - 因子数: {value.get('n_factors')}")
        print(f"  - 方法: {value.get('method')}")
        print(f"  - 降级标记: {value.get('degraded')}")
        print(f"  - 总风险: {value.get('total_risk', 0):.4f}")
        
        assert value.get('method') == 'single_factor_size', f"应该是单因子模式，实际: {value.get('method')}"
        assert value.get('n_factors') == 1, f"因子数应该为 1，实际: {value.get('n_factors')}"
        assert value.get('degraded') == True, "应该标记为降级"
        
        print("✓ 所有断言通过")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tier2_medium(n_stocks=6):
    """测试 Tier 2: 5-9 只股票 -> 收缩协方差模式"""
    print("\n" + "="*60)
    print(f"测试 Tier 2: {n_stocks} 只股票（收缩协方差模式）")
    print("="*60)
    
    symbols = ['600519', '000858', '601318', '000001', '600036', '601398'][:n_stocks]
    returns = generate_mock_returns(symbols)
    factors = generate_mock_factors(symbols, n_factors=5)
    
    calc = BarraRiskModelCalculator()
    
    try:
        result = calc.calculate(
            returns=returns,
            factor_exposures=factors
        )
        
        value = result.get('value', {})
        print(f"✓ 自动降级成功")
        print(f"  - 股票数: {value.get('n_stocks')}")
        print(f"  - 因子数: {value.get('n_factors')}")
        print(f"  - 方法: {value.get('method')}")
        print(f"  - 降级标记: {value.get('degraded')}")
        print(f"  - 总风险: {value.get('total_risk', 0):.4f}")
        print(f"  - 收缩强度: {value.get('shrinkage_intensity', 0):.3f}")
        print(f"  - 因子风险占比: {value.get('factor_contribution_pct', 0):.2f}%")
        
        assert value.get('method') == 'shrinkage_covariance', f"应该是收缩协方差模式，实际: {value.get('method')}"
        assert value.get('n_factors') == 5, f"因子数应该为 5，实际: {value.get('n_factors')}"
        assert value.get('degraded') == True, "应该标记为降级"
        assert 'shrinkage_intensity' in value, "应该包含收缩强度"
        
        print("✓ 所有断言通过")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tier3_full(n_stocks=10):
    """测试 Tier 3: ≥10 只股票 -> 完整多因子模式"""
    print("\n" + "="*60)
    print(f"测试 Tier 3: {n_stocks} 只股票（完整多因子模式）")
    print("="*60)
    
    symbols = ['600519', '000858', '601318', '000001', '600036', 
               '601398', '600028', '601288', '600900', '000333']
    returns = generate_mock_returns(symbols)
    factors = generate_mock_factors(symbols, n_factors=5)
    
    calc = BarraRiskModelCalculator()
    
    try:
        result = calc.calculate(
            returns=returns,
            factor_exposures=factors
        )
        
        value = result.get('value', {})
        print(f"✓ 计算成功")
        print(f"  - 股票数: {value.get('n_stocks')}")
        print(f"  - 因子数: {value.get('n_factors')}")
        print(f"  - 方法: {value.get('method', 'full')}")
        print(f"  - 降级标记: {value.get('degraded', False)}")
        print(f"  - 总风险: {value.get('total_risk', 0):.4f}")
        
        assert value.get('degraded') != True, "不应该降级"
        assert value.get('n_factors') == 5, f"因子数应该为 5，实际: {value.get('n_factors')}"
        
        print("✓ 所有断言通过")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_comparison_5stocks():
    """对比测试：5只股票，收缩协方差 vs 单因子"""
    print("\n" + "="*60)
    print("对比测试: 5 只股票（收缩协方差 vs 单因子）")
    print("="*60)
    
    symbols = ['600519', '000858', '601318', '000001', '600036']
    returns = generate_mock_returns(symbols)
    factors = generate_mock_factors(symbols, n_factors=5)
    
    calc = BarraRiskModelCalculator()
    
    try:
        # 收缩协方差模式（自动降级）
        result_shrink = calc.calculate(
            returns=returns,
            factor_exposures=factors
        )
        
        # 单因子模式（强制调用）
        market_caps = pd.Series([2000, 500, 3000, 400, 2500], index=symbols)
        result_single = calc.calculate_small_sample(
            returns=returns,
            market_caps=market_caps
        )
        
        v_shrink = result_shrink.get('value', {})
        v_single = result_single.get('value', {})
        
        print(f"\n收缩协方差模式:")
        print(f"  - 因子数: {v_shrink.get('n_factors')}")
        print(f"  - 总风险: {v_shrink.get('total_risk', 0):.4f}")
        print(f"  - 因子风险占比: {v_shrink.get('factor_contribution_pct', 0):.2f}%")
        print(f"  - 收缩强度: {v_shrink.get('shrinkage_intensity', 0):.3f}")
        
        print(f"\n单因子模式:")
        print(f"  - 因子数: {v_single.get('n_factors')}")
        print(f"  - 总风险: {v_single.get('total_risk', 0):.4f}")
        print(f"  - 因子风险占比: {v_single.get('factor_contribution_pct', 0):.2f}%")
        
        print(f"\n✓ 收缩协方差保留了 {v_shrink.get('n_factors')} 个因子信息")
        print(f"  （单因子只有 {v_single.get('n_factors')} 个）")
        
        assert v_shrink.get('n_factors') > v_single.get('n_factors'), "收缩协方差应该有更多因子"
        
        print("\n✓ 所有断言通过")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("P1-5.1 收缩协方差三级降级测试")
    print("="*60)
    
    results = {
        'tier1_3stocks': test_tier1_very_small(3),
        'tier2_6stocks': test_tier2_medium(6),
        'tier3_10stocks': test_tier3_full(10),
        'comparison': test_comparison_5stocks(),
    }
    
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有测试通过！")
        print("\n三级降级策略:")
        print("  Tier 1 (2-4只)  → 单因子市值")
        print("  Tier 2 (5-9只)  → 收缩协方差（多因子+Ledoit-Wolf）")
        print("  Tier 3 (≥10只)  → 完整多因子模型")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())
