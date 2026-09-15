#!/usr/bin/env python3
"""
P1-5 Barra 小样本路径测试脚本
测试 2/3/10 只股票的 Barra 风险分解
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

def generate_mock_market_caps(symbols):
    """生成模拟市值数据"""
    np.random.seed(42)
    market_caps = {}
    base_caps = {
        '600519': 2000,  # 贵州茅台 - 大
        '000858': 500,   # 五粮液 - 中
        '601318': 3000,  # 中国平安 - 大
        '000001': 400,   # 平安银行 - 中
        '600036': 2500,  # 招商银行 - 大
    }
    for symbol in symbols:
        market_caps[symbol] = base_caps.get(symbol, 1000) * (1 + np.random.randn() * 0.1)
    return pd.Series(market_caps)

def test_small_sample_2_stocks():
    """测试 2 只股票（最小样本）"""
    print("\n" + "="*60)
    print("测试 1: 2 只股票（小样本模式）")
    print("="*60)
    
    symbols = ['600519', '000858']
    returns = generate_mock_returns(symbols)
    market_caps = generate_mock_market_caps(symbols)
    
    calc = BarraRiskModelCalculator()
    
    try:
        result = calc.calculate_small_sample(
            returns=returns,
            market_caps=market_caps
        )
        
        value = result.get('value', {})
        print(f"✓ 计算成功")
        print(f"  - 股票数: {value.get('n_stocks')}")
        print(f"  - 因子数: {value.get('n_factors')}")
        print(f"  - 总风险: {value.get('total_risk', 0):.4f}")
        print(f"  - 因子风险: {value.get('factor_risk', 0):.4f}")
        print(f"  - 特异风险: {value.get('specific_risk', 0):.4f}")
        print(f"  - 降级标记: {value.get('degraded')}")
        print(f"  - 方法: {value.get('method')}")
        print(f"  - 警告: {value.get('warning')}")
        
        # 验证降级标记
        assert value.get('degraded') == True, "应该标记为降级模式"
        assert value.get('method') == 'single_factor_size', "应该使用单因子模式"
        assert value.get('n_factors') == 1, "因子数应该为 1"
        
        print("✓ 所有断言通过")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_small_sample_3_stocks():
    """测试 3 只股票"""
    print("\n" + "="*60)
    print("测试 2: 3 只股票（小样本模式）")
    print("="*60)
    
    symbols = ['600519', '000858', '601318']
    returns = generate_mock_returns(symbols)
    market_caps = generate_mock_market_caps(symbols)
    
    calc = BarraRiskModelCalculator()
    
    try:
        result = calc.calculate_small_sample(
            returns=returns,
            market_caps=market_caps
        )
        
        value = result.get('value', {})
        print(f"✓ 计算成功")
        print(f"  - 股票数: {value.get('n_stocks')}")
        print(f"  - 总风险: {value.get('total_risk', 0):.4f}")
        print(f"  - 因子风险占比: {value.get('factor_contribution_pct', 0):.2f}%")
        print(f"  - 特异风险占比: {value.get('specific_contribution_pct', 0):.2f}%")
        
        assert value.get('degraded') == True, "应该标记为降级模式"
        print("✓ 所有断言通过")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_auto_degrade_from_calculate():
    """测试从 calculate 方法自动降级"""
    print("\n" + "="*60)
    print("测试 3: calculate 方法自动降级（3 只股票）")
    print("="*60)
    
    symbols = ['600519', '000858', '601318']
    returns = generate_mock_returns(symbols)
    
    # 生成因子暴露（5 个风格因子，需要 10 只股票才能完整回归）
    n = len(symbols)
    factors_df = pd.DataFrame({
        'size': np.random.randn(n),
        'value': np.random.randn(n),
        'momentum': np.random.randn(n),
        'volatility': np.random.randn(n),
        'liquidity': np.random.randn(n),
    }, index=symbols)
    
    calc = BarraRiskModelCalculator()
    
    try:
        # 应该自动降级到小样本模式
        result = calc.calculate(
            returns=returns,
            factor_exposures=factors_df
        )
        
        value = result.get('value', {})
        print(f"✓ 自动降级成功")
        print(f"  - 股票数: {value.get('n_stocks')}")
        print(f"  - 因子数: {value.get('n_factors')}")
        print(f"  - 降级标记: {value.get('degraded')}")
        print(f"  - 方法: {value.get('method')}")
        
        assert value.get('degraded') == True, "应该自动降级"
        assert value.get('n_stocks') == 3, "股票数应该为 3"
        print("✓ 所有断言通过")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_full_mode_10_stocks():
    """测试 10 只股票（完整模式）"""
    print("\n" + "="*60)
    print("测试 4: 10 只股票（完整多因子模式）")
    print("="*60)
    
    symbols = ['600519', '000858', '601318', '000001', '600036', 
               '601398', '600028', '601288', '600900', '000333']
    returns = generate_mock_returns(symbols)
    
    # 生成因子暴露
    n = len(symbols)
    factors_df = pd.DataFrame({
        'size': np.random.randn(n),
        'value': np.random.randn(n),
        'momentum': np.random.randn(n),
        'volatility': np.random.randn(n),
        'liquidity': np.random.randn(n),
    }, index=symbols)
    
    calc = BarraRiskModelCalculator()
    
    try:
        result = calc.calculate(
            returns=returns,
            factor_exposures=factors_df
        )
        
        value = result.get('value', {})
        print(f"✓ 计算成功")
        print(f"  - 股票数: {value.get('n_stocks')}")
        print(f"  - 因子数: {value.get('n_factors')}")
        print(f"  - 总风险: {value.get('total_risk', 0):.4f}")
        print(f"  - 降级标记: {value.get('degraded', False)}")
        
        assert value.get('degraded') != True, "不应该降级"
        assert value.get('n_factors') == 5, "应该使用完整 5 因子"
        print("✓ 所有断言通过")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("P1-5 Barra 小样本路径测试")
    print("="*60)
    
    results = {
        'test_2_stocks': test_small_sample_2_stocks(),
        'test_3_stocks': test_small_sample_3_stocks(),
        'test_auto_degrade': test_auto_degrade_from_calculate(),
        'test_10_stocks': test_full_mode_10_stocks(),
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
        return 0
    else:
        print("✗ 部分测试失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())
