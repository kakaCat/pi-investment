"""
期权Greeks计算完整示例

演示如何使用GreeksCalculator进行期权定价和Greeks计算：
1. 基础期权定价
2. Greeks计算和解读
3. 隐含波动率计算
4. Greeks敏感性分析
5. 期权策略Greeks
"""

import sys
import os

import numpy as np
import pandas as pd
from domain.quantlib.options.greeks_calculator import GreeksCalculator


def basic_option_pricing():
    """基础期权定价"""
    print("=" * 60)
    print("步骤1: 基础期权定价")
    print("=" * 60)

    calculator = GreeksCalculator()

    # 期权参数
    S = 100      # 标的价格
    K = 100      # 行权价
    T = 0.25     # 到期时间（3个月）
    r = 0.03     # 无风险利率（3%）
    sigma = 0.2  # 波动率（20%）

    print(f"\n期权参数:")
    print(f"  标的价格 (S): {S}")
    print(f"  行权价 (K): {K}")
    print(f"  到期时间 (T): {T}年 ({T*365:.0f}天)")
    print(f"  无风险利率 (r): {r:.1%}")
    print(f"  波动率 (σ): {sigma:.1%}")

    # 计算看涨期权
    call_price = calculator.black_scholes_price(S, K, T, r, sigma, 'call')
    print(f"\n看涨期权价格: {call_price:.4f}")

    # 计算看跌期权
    put_price = calculator.black_scholes_price(S, K, T, r, sigma, 'put')
    print(f"看跌期权价格: {put_price:.4f}")

    # 验证Put-Call Parity
    # C - P = S - K * e^(-rT)
    parity_left = call_price - put_price
    parity_right = S - K * np.exp(-r * T)
    print(f"\nPut-Call Parity验证:")
    print(f"  C - P = {parity_left:.4f}")
    print(f"  S - K*e^(-rT) = {parity_right:.4f}")
    print(f"  差异: {abs(parity_left - parity_right):.6f} (应接近0)")


def greeks_calculation_and_interpretation():
    """Greeks计算和解读"""
    print("\n" + "=" * 60)
    print("步骤2: Greeks计算和解读")
    print("=" * 60)

    calculator = GreeksCalculator()

    S = 100
    K = 100
    T = 0.25
    r = 0.03
    sigma = 0.2

    # 计算看涨期权Greeks
    call_greeks = calculator.calculate_greeks(S, K, T, r, sigma, 'call')

    print("\n看涨期权Greeks:")
    print(f"  价格 (Price): {call_greeks['price']:.4f}")
    print(f"  Delta: {call_greeks['delta']:.4f}")
    print(f"  Gamma: {call_greeks['gamma']:.4f}")
    print(f"  Theta: {call_greeks['theta']:.4f}")
    print(f"  Vega: {call_greeks['vega']:.4f}")
    print(f"  Rho: {call_greeks['rho']:.4f}")

    print("\nGreeks解读:")
    print(f"  Delta = {call_greeks['delta']:.4f}")
    print(f"    → 标的价格上涨1元，期权价格上涨约{call_greeks['delta']:.4f}元")
    print(f"    → 对冲需要卖出{call_greeks['delta']:.4f}份标的")

    print(f"\n  Gamma = {call_greeks['gamma']:.4f}")
    print(f"    → 标的价格上涨1元，Delta增加约{call_greeks['gamma']:.4f}")
    print(f"    → Gamma越大，Delta变化越快，对冲频率越高")

    print(f"\n  Theta = {call_greeks['theta']:.4f}")
    print(f"    → 每过1天，期权价格下降约{abs(call_greeks['theta']):.4f}元")
    print(f"    → 时间价值衰减速度")

    print(f"\n  Vega = {call_greeks['vega']:.4f}")
    print(f"    → 波动率上升1%，期权价格上涨约{call_greeks['vega']:.4f}元")
    print(f"    → 对波动率的敏感度")

    print(f"\n  Rho = {call_greeks['rho']:.4f}")
    print(f"    → 利率上升1%，期权价格上涨约{call_greeks['rho']:.4f}元")

    # 计算看跌期权Greeks
    put_greeks = calculator.calculate_greeks(S, K, T, r, sigma, 'put')

    print("\n\n看跌期权Greeks:")
    print(f"  价格 (Price): {put_greeks['price']:.4f}")
    print(f"  Delta: {put_greeks['delta']:.4f}")
    print(f"  Gamma: {put_greeks['gamma']:.4f}")
    print(f"  Theta: {put_greeks['theta']:.4f}")
    print(f"  Vega: {put_greeks['vega']:.4f}")
    print(f"  Rho: {put_greeks['rho']:.4f}")

    print("\n看涨vs看跌对比:")
    print(f"  Delta: Call={call_greeks['delta']:.4f}, Put={put_greeks['delta']:.4f}")
    print(f"    → 差值约为1 (Put-Call Parity)")
    print(f"  Gamma: 相同 = {call_greeks['gamma']:.4f}")
    print(f"  Vega: 相同 = {call_greeks['vega']:.4f}")


def implied_volatility_calculation():
    """隐含波动率计算"""
    print("\n" + "=" * 60)
    print("步骤3: 隐含波动率计算")
    print("=" * 60)

    calculator = GreeksCalculator()

    S = 100
    K = 100
    T = 0.25
    r = 0.03
    true_sigma = 0.25  # 真实波动率

    # 计算期权市场价格
    market_price = calculator.black_scholes_price(S, K, T, r, true_sigma, 'call')
    print(f"\n期权市场价格: {market_price:.4f}")
    print(f"真实波动率: {true_sigma:.1%}")

    # 反推隐含波动率
    implied_vol = calculator.implied_volatility(market_price, S, K, T, r, 'call')
    print(f"计算的隐含波动率: {implied_vol:.1%}")
    print(f"误差: {abs(implied_vol - true_sigma):.6f}")

    # 不同行权价的隐含波动率（波动率微笑）
    print("\n\n波动率微笑示例:")
    print("行权价    市场价格    隐含波动率")
    print("-" * 40)

    strikes = [90, 95, 100, 105, 110]
    for K in strikes:
        # 模拟波动率微笑：实值和虚值期权波动率更高
        smile_sigma = true_sigma + 0.05 * ((K - S) / S) ** 2
        market_price = calculator.black_scholes_price(S, K, T, r, smile_sigma, 'call')
        implied_vol = calculator.implied_volatility(market_price, S, K, T, r, 'call')
        print(f"{K:>6}    {market_price:>8.4f}    {implied_vol:>10.1%}")


def greeks_sensitivity_analysis():
    """Greeks敏感性分析"""
    print("\n" + "=" * 60)
    print("步骤4: Greeks敏感性分析")
    print("=" * 60)

    calculator = GreeksCalculator()

    base_params = {
        'S': 100,
        'K': 100,
        'T': 0.25,
        'r': 0.03,
        'sigma': 0.2
    }

    # 1. Delta随标的价格变化
    print("\n1. Delta随标的价格变化:")
    print("标的价格    Call Delta    Put Delta")
    print("-" * 45)

    spot_prices = [90, 95, 100, 105, 110]
    for S in spot_prices:
        call_greeks = calculator.calculate_greeks(S, base_params['K'], base_params['T'],
                                                   base_params['r'], base_params['sigma'], 'call')
        put_greeks = calculator.calculate_greeks(S, base_params['K'], base_params['T'],
                                                  base_params['r'], base_params['sigma'], 'put')
        print(f"{S:>8}    {call_greeks['delta']:>10.4f}    {put_greeks['delta']:>10.4f}")

    # 2. Gamma随标的价格变化
    print("\n2. Gamma随标的价格变化:")
    print("标的价格    Gamma")
    print("-" * 25)

    for S in spot_prices:
        greeks = calculator.calculate_greeks(S, base_params['K'], base_params['T'],
                                             base_params['r'], base_params['sigma'], 'call')
        print(f"{S:>8}    {greeks['gamma']:>10.4f}")

    print("\n  → Gamma在平值期权处最大")

    # 3. Theta随到期时间变化
    print("\n3. Theta随到期时间变化:")
    print("剩余天数    Theta")
    print("-" * 25)

    time_to_expiry = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0]  # 年
    for T in time_to_expiry:
        greeks = calculator.calculate_greeks(base_params['S'], base_params['K'], T,
                                             base_params['r'], base_params['sigma'], 'call')
        print(f"{T*365:>8.0f}    {greeks['theta']:>10.4f}")

    print("\n  → 临近到期时，Theta加速衰减")

    # 4. Vega随波动率变化
    print("\n4. Vega随波动率变化:")
    print("波动率    Vega")
    print("-" * 25)

    volatilities = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4]
    for sigma in volatilities:
        greeks = calculator.calculate_greeks(base_params['S'], base_params['K'], base_params['T'],
                                             base_params['r'], sigma, 'call')
        print(f"{sigma:>6.1%}    {greeks['vega']:>10.4f}")


def option_strategy_greeks():
    """期权策略Greeks"""
    print("\n" + "=" * 60)
    print("步骤5: 期权策略Greeks")
    print("=" * 60)

    calculator = GreeksCalculator()

    S = 100
    T = 0.25
    r = 0.03
    sigma = 0.2

    # 策略1: 跨式组合 (Straddle)
    print("\n策略1: 跨式组合 (Long Straddle)")
    print("  买入1份ATM看涨期权 + 买入1份ATM看跌期权")

    K = 100
    call_greeks = calculator.calculate_greeks(S, K, T, r, sigma, 'call')
    put_greeks = calculator.calculate_greeks(S, K, T, r, sigma, 'put')

    straddle_greeks = {
        'price': call_greeks['price'] + put_greeks['price'],
        'delta': call_greeks['delta'] + put_greeks['delta'],
        'gamma': call_greeks['gamma'] + put_greeks['gamma'],
        'theta': call_greeks['theta'] + put_greeks['theta'],
        'vega': call_greeks['vega'] + put_greeks['vega'],
        'rho': call_greeks['rho'] + put_greeks['rho']
    }

    print(f"\n组合Greeks:")
    for key, value in straddle_greeks.items():
        print(f"  {key}: {value:.4f}")

    print(f"\n策略特点:")
    print(f"  Delta ≈ 0: 方向中性")
    print(f"  Gamma > 0: 做多波动")
    print(f"  Vega > 0: 做多波动率")
    print(f"  Theta < 0: 时间价值衰减")

    # 策略2: 牛市价差 (Bull Spread)
    print("\n\n策略2: 牛市价差 (Bull Call Spread)")
    print("  买入1份ATM看涨期权 + 卖出1份OTM看涨期权")

    K1 = 100  # 买入
    K2 = 110  # 卖出

    long_call = calculator.calculate_greeks(S, K1, T, r, sigma, 'call')
    short_call = calculator.calculate_greeks(S, K2, T, r, sigma, 'call')

    bull_spread_greeks = {
        'price': long_call['price'] - short_call['price'],
        'delta': long_call['delta'] - short_call['delta'],
        'gamma': long_call['gamma'] - short_call['gamma'],
        'theta': long_call['theta'] - short_call['theta'],
        'vega': long_call['vega'] - short_call['vega'],
        'rho': long_call['rho'] - short_call['rho']
    }

    print(f"\n组合Greeks:")
    for key, value in bull_spread_greeks.items():
        print(f"  {key}: {value:.4f}")

    print(f"\n策略特点:")
    print(f"  Delta > 0: 看涨")
    print(f"  成本较低: {bull_spread_greeks['price']:.4f} vs {long_call['price']:.4f}")
    print(f"  最大收益有限: {K2 - K1 - bull_spread_greeks['price']:.4f}")

    # 策略3: 铁鹰式 (Iron Condor)
    print("\n\n策略3: 铁鹰式 (Iron Condor)")
    print("  卖出OTM看跌 + 买入更OTM看跌 + 卖出OTM看涨 + 买入更OTM看涨")

    K_put_sell = 95
    K_put_buy = 90
    K_call_sell = 105
    K_call_buy = 110

    put_sell = calculator.calculate_greeks(S, K_put_sell, T, r, sigma, 'put')
    put_buy = calculator.calculate_greeks(S, K_put_buy, T, r, sigma, 'put')
    call_sell = calculator.calculate_greeks(S, K_call_sell, T, r, sigma, 'call')
    call_buy = calculator.calculate_greeks(S, K_call_buy, T, r, sigma, 'call')

    iron_condor_greeks = {
        'price': -put_sell['price'] + put_buy['price'] - call_sell['price'] + call_buy['price'],
        'delta': -put_sell['delta'] + put_buy['delta'] - call_sell['delta'] + call_buy['delta'],
        'gamma': -put_sell['gamma'] + put_buy['gamma'] - call_sell['gamma'] + call_buy['gamma'],
        'theta': -put_sell['theta'] + put_buy['theta'] - call_sell['theta'] + call_buy['theta'],
        'vega': -put_sell['vega'] + put_buy['vega'] - call_sell['vega'] + call_buy['vega'],
        'rho': -put_sell['rho'] + put_buy['rho'] - call_sell['rho'] + call_buy['rho']
    }

    print(f"\n组合Greeks:")
    for key, value in iron_condor_greeks.items():
        print(f"  {key}: {value:.4f}")

    print(f"\n策略特点:")
    print(f"  Delta ≈ 0: 方向中性")
    print(f"  Gamma < 0: 做空波动")
    print(f"  Theta > 0: 赚取时间价值")
    print(f"  Vega < 0: 做空波动率")
    print(f"  收取权利金: {-iron_condor_greeks['price']:.4f}")


def main():
    """主函数"""
    print("期权Greeks计算完整示例")
    print("=" * 60)

    # 1. 基础期权定价
    basic_option_pricing()

    # 2. Greeks计算和解读
    greeks_calculation_and_interpretation()

    # 3. 隐含波动率计算
    implied_volatility_calculation()

    # 4. Greeks敏感性分析
    greeks_sensitivity_analysis()

    # 5. 期权策略Greeks
    option_strategy_greeks()

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)
    print("\n关键要点:")
    print("1. Delta: 方向风险，对冲比率")
    print("2. Gamma: Delta的变化率，对冲频率")
    print("3. Theta: 时间价值衰减")
    print("4. Vega: 波动率风险")
    print("5. 组合策略可以构造不同的风险收益特征")
    print("6. Greeks是动态的，需要持续监控和调整")


if __name__ == "__main__":
    main()
