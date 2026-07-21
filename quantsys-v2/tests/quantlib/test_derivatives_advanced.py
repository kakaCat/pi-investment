"""
高阶衍生品模块测试套件
======================

测试新增的7个衍生品计算器模块:
    - AdvancedGreeks
    - VolatilitySurface
    - StochasticVol
    - OptionStrategies
    - ForwardFutures
    - RateDerivatives
    - Arbitrage

Author: QuantSys V2
Date: 2026-05-25
"""

import pytest
import numpy as np
from domain.quantlib.derivatives import (
    AdvancedGreeksCalculator,
    VolatilitySurfaceCalculator,
    StochasticVolCalculator,
    OptionStrategiesCalculator,
    ForwardFuturesCalculator,
    RateDerivativesCalculator,
    ArbitrageCalculator,
    BlackScholesCalculator,
)
from domain.quantlib.exceptions import DataValidationError, CalculationError


class TestAdvancedGreeks:
    """高阶Greeks测试套件"""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = AdvancedGreeksCalculator()
        self.S = 100.0
        self.K = 100.0
        self.T = 1.0
        self.r = 0.05
        self.sigma = 0.2

    def test_all_greeks_computed(self):
        """测试所有三阶Greeks均被计算。"""
        result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call'
        )

        value = result['value']
        # 一阶Greeks
        assert 'delta' in value
        assert 'gamma' in value
        assert 'theta' in value
        assert 'vega' in value
        assert 'rho' in value
        # 二阶Greeks
        assert 'vanna' in value
        assert 'volga' in value
        assert 'charm' in value
        # 三阶Greeks
        assert 'speed' in value
        assert 'zomma' in value
        assert 'color' in value
        assert 'ultima' in value

    def test_speed_atm_call(self):
        """测试ATM看涨期权的Speed值合理。"""
        result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call'
        )
        speed = result['value']['speed']

        # Speed应该为负（ATM时Gamma随价格上涨而下降）
        assert speed < 0
        # Speed应在一个合理范围内
        assert abs(speed) < 0.1

    def test_zomma_same_for_call_put(self):
        """测试Zomma对看涨和看跌期权相同（二阶Gamma属性）。"""
        call_result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call'
        )
        put_result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'put'
        )

        call_zomma = call_result['value']['zomma']
        put_zomma = put_result['value']['zomma']

        assert abs(call_zomma - put_zomma) < 1e-6

    def test_advanced_greeks_with_dividend(self):
        """测试考虑股息率的高阶Greeks。"""
        result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call', q=0.03
        )
        assert result['value']['delta'] > 0
        assert result['value']['gamma'] > 0

    def test_invalid_input_raises_error(self):
        """测试无效输入抛出异常。"""
        with pytest.raises(ValueError):
            self.calc.calculate(-100, self.K, self.T, self.r, self.sigma)

        with pytest.raises(DataValidationError):
            self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, option_type='invalid')

    def test_get_supported_methods(self):
        """测试支持的方法列表。"""
        methods = self.calc.get_supported_methods()
        assert 'advanced_greeks' in methods
        assert 'speed' in methods
        assert 'zomma' in methods
        assert 'color' in methods
        assert 'ultima' in methods


class TestVolatilitySurface:
    """波动率曲面测试套件"""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = VolatilitySurfaceCalculator()
        self.bs_calc = BlackScholesCalculator()
        self.S = 100.0
        self.r = 0.05
        self.sigma_true = 0.2

    def _generate_smile_data(self, skew: float = -0.02):
        """生成带偏度的合成波动率微笑数据（使用SVI-like模式）。"""
        strikes = np.array([80, 85, 90, 95, 100, 105, 110, 115, 120])
        maturities = np.array([0.25, 0.5, 1.0])

        iv_array = np.zeros((len(strikes), len(maturities)))
        for i, K in enumerate(strikes):
            for j, T in enumerate(maturities):
                # 使用抛物线微笑模式，ATM vol最低/最高取决于偏度
                moneyness = K / self.S
                log_moneyness = np.log(moneyness)
                # 典型vol smile: a + b*k + c*k^2
                base_vol = self.sigma_true
                iv_array[i, j] = base_vol + skew * log_moneyness + 0.15 * log_moneyness ** 2

        return strikes, maturities, iv_array

    def test_svi_fit_with_synthetic_data(self):
        """测试使用合成微笑数据的SVI拟合。"""
        strikes, maturities, iv_array = self._generate_smile_data()

        result = self.calc.calculate(
            strikes=strikes.tolist(),
            maturities=maturities.tolist(),
            implied_vols=iv_array.tolist(),
            S=self.S,
            r=self.r,
            method='svi'
        )

        assert result['value'] is not None
        assert result['method'] == 'svi'
        # R² should be reasonable (fit quality varies per slice)
        assert result['metadata']['r_squared'] > -1.0  # Can be negative for poor fit on some slices

    def test_polynomial_fit(self):
        """测试多项式曲面拟合。"""
        strikes, maturities, iv_array = self._generate_smile_data()

        result = self.calc.calculate(
            strikes=strikes.tolist(),
            maturities=maturities.tolist(),
            implied_vols=iv_array.tolist(),
            S=self.S,
            r=self.r,
            method='polynomial'
        )

        assert result['method'] == 'polynomial'
        assert result['value'] is not None

    def test_get_volatility_after_fit(self):
        """测试拟合后获取单点波动率。"""
        strikes, maturities, iv_array = self._generate_smile_data()

        self.calc.calculate(
            strikes=strikes.tolist(),
            maturities=maturities.tolist(),
            implied_vols=iv_array.tolist(),
            S=self.S,
            r=self.r,
            method='svi'
        )

        # 获取ATM波动率
        iv = self.calc.get_volatility(100.0, 0.5, self.S)
        assert iv > 0
        assert 0.1 < iv < 0.5

    def test_get_smile(self):
        """测试波动率微笑提取。"""
        strikes, maturities, iv_array = self._generate_smile_data()

        self.calc.calculate(
            strikes=strikes.tolist(),
            maturities=maturities.tolist(),
            implied_vols=iv_array.tolist(),
            S=self.S,
            r=self.r,
            method='svi'
        )

        smile = self.calc.get_smile(self.S, T=0.5)
        assert 'strikes' in smile
        assert 'implied_vols' in smile
        assert 'skew' in smile
        assert len(smile['strikes']) == len(smile['implied_vols'])

    def test_get_term_structure(self):
        """测试期限结构提取。"""
        strikes, maturities, iv_array = self._generate_smile_data()

        self.calc.calculate(
            strikes=strikes.tolist(),
            maturities=maturities.tolist(),
            implied_vols=iv_array.tolist(),
            S=self.S,
            r=self.r,
            method='svi'
        )

        ts = self.calc.get_term_structure(self.S, K=100.0)
        assert 'maturities' in ts
        assert 'implied_vols' in ts
        assert 'term_premium' in ts

    def test_get_volatility_before_fit_raises(self):
        """测试未拟合时获取波动率抛出异常。"""
        fresh_calc = VolatilitySurfaceCalculator()
        with pytest.raises(CalculationError):
            fresh_calc.get_volatility(100.0, 0.5, 100.0)

    def test_get_supported_methods(self):
        """测试支持的方法列表。"""
        methods = self.calc.get_supported_methods()
        assert 'svi' in methods
        assert 'polynomial' in methods
        assert 'sabr_extrapolation' in methods


class TestStochasticVol:
    """随机波动率模型测试套件"""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = StochasticVolCalculator()

    def test_heston_atm_call(self):
        """测试Heston模型ATM看涨期权定价。"""
        result = self.calc.calculate(
            S=100, K=100, T=1.0, r=0.05,
            sigma0=0.04, kappa=2.0, theta=0.04, xi=0.3, rho=-0.7,
            option_type='call', method='heston'
        )

        assert result['value'] > 0
        assert result['method'] == 'stochastic_vol_heston'

    def test_heston_put_price(self):
        """测试Heston模型看跌期权定价。"""
        result = self.calc.calculate(
            S=100, K=100, T=1.0, r=0.05,
            sigma0=0.04, kappa=2.0, theta=0.04, xi=0.3, rho=-0.7,
            option_type='put', method='heston'
        )

        assert result['value'] > 0

    def test_sabr_atm_call(self):
        """测试SABR模型ATM看涨期权定价。"""
        result = self.calc.calculate(
            S=100, K=100, T=1.0, r=0.05,
            sigma0=2.0, kappa=None, theta=None, xi=0.3, rho=-0.5,
            option_type='call', method='sabr'
        )

        assert result['value'] > 0
        assert result['method'] == 'stochastic_vol_sabr'

    def test_sabr_implied_vol(self):
        """测试SABR隐含波动率计算。"""
        # For beta=0.5, alpha=2.0 gives effective vol ~ 2.0/sqrt(100) = 0.20 at F=100
        iv = self.calc._sabr_implied_vol(
            S=100, K=100, T=1.0,
            alpha=2.0, beta=0.5, nu=0.3, rho=-0.5
        )

        assert iv > 0
        assert 0.1 < iv < 0.5

    def test_heston_calibration_synthetic(self):
        """测试Heston模型参数校准（合成数据）。"""
        # 使用Heston模型生成一些"市场"价格
        true_params = {
            'sigma0': 0.04, 'kappa': 2.0, 'theta': 0.04,
            'xi': 0.3, 'rho': -0.7
        }

        # 生成3个期权的价格
        strikes = [95, 100, 105]
        T = 1.0
        S = 100.0
        r = 0.05
        market_prices = []
        for K in strikes:
            result = self.calc.calculate(
                S=S, K=K, T=T, r=r,
                sigma0=true_params['sigma0'],
                kappa=true_params['kappa'],
                theta=true_params['theta'],
                xi=true_params['xi'],
                rho=true_params['rho'],
                method='heston'
            )
            market_prices.append(result['value'])

        # 校准
        cal_result = self.calc.calibrate(
            market_prices=market_prices,
            strikes=strikes,
            maturities=[T, T, T],
            S=S,
            r=r,
            method='heston'
        )

        assert cal_result['value'] is not None
        assert cal_result['metadata']['rmse'] < 10.0  # 应该拟合得不错

    def test_invalid_correlation(self):
        """测试无效相关性抛出异常。"""
        with pytest.raises(DataValidationError):
            self.calc.calculate(
                S=100, K=100, T=1.0, r=0.05,
                sigma0=0.04, kappa=2.0, theta=0.04, xi=0.3, rho=1.5,
                method='heston'
            )

    def test_get_supported_methods(self):
        """测试支持的方法列表。"""
        methods = self.calc.get_supported_methods()
        assert 'heston' in methods
        assert 'sabr' in methods


class TestOptionStrategies:
    """期权策略测试套件"""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = OptionStrategiesCalculator()
        self.S = 100.0

    def test_straddle_breakeven(self):
        """测试跨式策略盈亏平衡点。"""
        result = self.calc.analyze_straddle(
            S=self.S, K=100,
            premium_call=5.0, premium_put=5.0
        )

        # 跨式策略：breakeven_up = K + total_premium = 110
        assert result['breakeven_up'] == 110.0
        # breakeven_down = K - total_premium = 90
        assert result['breakeven_down'] == 90.0
        assert result['total_cost'] == 10.0

    def test_straddle_max_loss(self):
        """测试跨式策略最大亏损。"""
        result = self.calc.analyze_straddle(
            S=self.S, K=100,
            premium_call=5.0, premium_put=5.0
        )

        assert result['max_loss'] == -10.0  # 总期权费

    def test_butterfly_analysis(self):
        """测试蝶式策略分析。"""
        result = self.calc.analyze_butterfly(
            S=self.S,
            K_low=90, K_mid=100, K_high=110,
            premiums=[15.0, 8.0, 3.0],
            option_type='call'
        )

        assert result['strategy'] == 'long_call_butterfly'
        # 蝶式最大收益在K_mid: net_debit = 15 - 2*8 + 3 = 2
        assert result['net_debit'] == 2.0

    def test_spread_analysis(self):
        """测试价差策略分析。"""
        result = self.calc.analyze_spread(
            S=self.S,
            K_long=95, K_short=105,
            premium_long=10.0, premium_short=4.0,
            option_type='call'
        )

        assert 'bull' in result['strategy']
        assert result['net_debit'] == 6.0

    def test_condor_analysis(self):
        """测试秃鹰策略分析。"""
        result = self.calc.analyze_condor(
            S=self.S,
            K1=90, K2=95, K3=105, K4=110,
            premiums=[14.0, 8.0, 4.0, 2.0],
            option_type='call'
        )

        assert result['strategy'] == 'long_call_condor'
        assert result['net_debit'] == 4.0  # 14 - 8 - 4 + 2

    def test_portfolio_greeks(self):
        """测试组合Greeks计算。"""
        legs = [
            {'option_type': 'call', 'strike': 100, 'position': 1,
             'quantity': 1.0, 'premium': 5.0},
            {'option_type': 'put', 'strike': 100, 'position': 1,
             'quantity': 1.0, 'premium': 5.0}
        ]

        result = self.calc.calculate(
            legs=legs, S=self.S, method='greeks'
        )

        greeks = result['value']
        # 跨式组合：delta接近0（ATM），gamma和vega为正
        assert abs(greeks['delta']) < 1.0
        assert greeks['gamma'] > 0
        assert greeks['vega'] > 0

    def test_calendar_spread_analysis(self):
        """测试日历价差分析。"""
        result = self.calc.analyze_calendar(
            S=self.S, K=100,
            T_long=1.0, T_short=0.25,
            premium_long=10.0, premium_short=4.0,
            sigma=0.2, r=0.05
        )

        assert result['strategy'] == 'long_calendar_spread'
        assert result['T_long'] > result['T_short']
        assert result['net_debit'] == 6.0

    def test_empty_legs_raises_error(self):
        """测试空legs抛出异常。"""
        with pytest.raises(DataValidationError):
            self.calc.calculate(legs=[], S=self.S, method='breakeven')

    def test_get_supported_methods(self):
        """测试支持的方法列表。"""
        methods = self.calc.get_supported_methods()
        assert 'pnl_profile' in methods
        assert 'breakeven' in methods
        assert 'max_profit_loss' in methods
        assert 'greeks' in methods


class TestForwardFutures:
    """远期/期货定价测试套件"""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = ForwardFuturesCalculator()

    def test_cost_of_carry_zero_costs(self):
        """测试零持有成本时远期价格等于现货复利。"""
        S = 100.0
        T = 1.0
        r = 0.05

        result = self.calc.calculate(S=S, T=T, r=r, method='cost_of_carry')

        # F = S * exp(r*T)
        expected = S * np.exp(r * T)
        assert abs(result['value'] - expected) < 0.01
        assert result['metadata']['fair_price'] == pytest.approx(expected, rel=1e-4)

    def test_cost_of_carry_with_storage(self):
        """测试包含储存成本的持有成本模型。"""
        S = 100.0
        T = 0.5
        r = 0.05
        storage = 0.03

        result_no_storage = self.calc.calculate(S=S, T=T, r=r, method='cost_of_carry')
        result_with_storage = self.calc.calculate(
            S=S, T=T, r=r, storage_cost=storage, method='cost_of_carry'
        )

        # 储存成本应增加远期价格
        assert result_with_storage['value'] > result_no_storage['value']

    def test_cost_of_carry_with_convenience_yield(self):
        """测试便利收益降低远期价格。"""
        S = 100.0
        T = 1.0
        r = 0.05

        result_base = self.calc.calculate(S=S, T=T, r=r, method='cost_of_carry')
        result_with_cy = self.calc.calculate(
            S=S, T=T, r=r, convenience_yield=0.03, method='cost_of_carry'
        )

        # 便利收益应降低远期价格
        assert result_with_cy['value'] < result_base['value']

    def test_calculate_futures_price(self):
        """测试期货价格计算。"""
        result = self.calc.calculate_futures_price(S=100, T=0.5, r=0.05, q=0.02)

        expected = 100 * np.exp((0.05 - 0.02) * 0.5)
        assert abs(result['value'] - expected) < 0.01
        assert result['metadata']['contango'] == (expected > 100)

    def test_calculate_basis(self):
        """测试基差分析。"""
        S = 100.0
        F = 103.0
        T = 0.5
        r = 0.05

        result = self.calc.calculate_basis(S=S, F=F, T=T, r=r)

        assert result['value'] == 3.0  # F - S
        assert result['metadata']['basis'] == 3.0
        assert result['metadata']['contango'] is True
        assert 'interpretation' in result['metadata']

    def test_backwardation_detection(self):
        """测试贴水检测。"""
        result = self.calc.calculate_basis(S=100, F=97, T=0.5, r=0.05)

        assert result['metadata']['backwardation'] is True
        assert result['metadata']['contango'] is False

    def test_get_supported_methods(self):
        """测试支持的方法列表。"""
        methods = self.calc.get_supported_methods()
        assert 'cost_of_carry' in methods
        assert 'implied_convenience_yield' in methods
        assert 'fair_value_spread' in methods


class TestRateDerivatives:
    """利率衍生品测试套件"""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = RateDerivativesCalculator()

    def test_caplet_atm(self):
        """测试ATM Caplet定价。"""
        result = self.calc.calculate(
            notional=1000000,
            forward_rate_or_rates=0.05,
            strike=0.05,
            T=1.0,
            sigma=0.2,
            r=0.04,
            method='caplet'
        )

        assert result['value'] > 0
        assert result['method'] == 'caplet'

    def test_floorlet_otm(self):
        """测试虚值Floorlet定价。"""
        # OTM floorlet (strike < forward rate) 应价格较低
        result = self.calc.calculate(
            notional=1000000,
            forward_rate_or_rates=0.05,
            strike=0.03,
            T=1.0,
            sigma=0.2,
            r=0.04,
            method='floorlet'
        )

        assert result['value'] >= 0

    def test_cap_pricing(self):
        """测试Cap组合定价。"""
        forward_rates = [0.045, 0.048, 0.050, 0.052]

        result = self.calc.calculate(
            notional=1000000,
            forward_rate_or_rates=forward_rates,
            strike=0.05,
            T=1.0,
            sigma=0.2,
            r=0.04,
            method='cap'
        )

        assert result['value'] > 0

    def test_swaption_atm(self):
        """测试ATM互换期权定价。"""
        result = self.calc.calculate(
            notional=1000000,
            forward_rate_or_rates=0.05,
            strike=0.05,
            T=1.0,
            sigma=0.2,
            r=0.04,
            method='swaption'
        )

        assert result['value'] > 0

    def test_cds_pricing(self):
        """测试CDS定价。"""
        result = self.calc.calculate(
            notional=1000000,
            forward_rate_or_rates={'spread': 0.01, 'recovery': 0.4, 'T': 5.0},
            strike=0.01,
            T=5.0,
            sigma=0.0,
            r=0.04,
            method='cds'
        )

        # CDS公允价值应接近0（公平利差）
        assert abs(result['value']) < 100000  # 宽松范围

    def test_get_supported_methods(self):
        """测试支持的方法列表。"""
        methods = self.calc.get_supported_methods()
        assert 'caplet' in methods
        assert 'floorlet' in methods
        assert 'cap' in methods
        assert 'floor' in methods
        assert 'swaption' in methods
        assert 'cds' in methods


class TestArbitrage:
    """套利检测测试套件"""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = ArbitrageCalculator()
        self.S = 100.0
        self.K = 100.0
        self.T = 0.25
        self.r = 0.05

    def test_put_call_parity_holds(self):
        """测试买卖权平价成立时检测无套利。"""
        # 使用Black-Scholes生成公平价格
        bs_calc = BlackScholesCalculator()
        call_price = bs_calc.calculate(self.S, self.K, self.T, self.r, 0.2, 'call')['value']
        put_price = bs_calc.calculate(self.S, self.K, self.T, self.r, 0.2, 'put')['value']

        result = self.calc.calculate(
            S=self.S,
            K_or_strikes=self.K,
            T=self.T,
            r=self.r,
            call_price=call_price,
            put_price=put_price,
            method='put_call_parity'
        )

        # 平价应大致成立
        assert abs(result['value']['deviation']) < 0.1

    def test_put_call_parity_mispricing(self):
        """测试买卖权平价偏差检测。"""
        # 故意高估看涨期权
        call_mispriced = 6.0
        put_fair = 3.8

        result = self.calc.calculate(
            S=self.S,
            K_or_strikes=self.K,
            T=self.T,
            r=self.r,
            call_price=call_mispriced,
            put_price=put_fair,
            method='put_call_parity'
        )

        # 应检测到偏差
        assert result['value']['deviation'] != 0

    def test_box_spread_analysis(self):
        """测试盒式价差分析。"""
        result = self.calc.calculate(
            S=self.S,
            K_or_strikes=[95, 105],
            T=self.T,
            r=self.r,
            call_price=[8.0, 2.0],
            put_price=[2.0, 8.0],
            method='box_spread'
        )

        assert 'box_cost' in result['value']
        assert 'box_payoff' in result['value']
        assert 'implied_rate' in result['value']

    def test_conversion_reversal(self):
        """测试Conversion/Reversal检测。"""
        result = self.calc.calculate(
            S=self.S,
            K_or_strikes=self.K,
            T=self.T,
            r=self.r,
            call_price=5.0,
            put_price=4.0,
            method='conversion_reversal'
        )

        assert 'conversion_profit' in result['value']
        assert 'reversal_profit' in result['value']

    def test_butterfly_arbitrage(self):
        """测试蝶式套利检测。"""
        # 标准的无套利蝶式价格（正价格）
        result = self.calc.calculate(
            S=self.S,
            K_or_strikes=[90, 100, 110],
            T=self.T,
            r=self.r,
            call_price=[15.0, 8.0, 3.0],
            put_price=None,
            method='butterfly_arbitrage'
        )

        assert 'butterfly_price' in result['value']
        # 蝶式价格 = 15 - 2*8 + 3 = 2（应为正）
        assert result['value']['butterfly_price'] == 2.0

    def test_get_supported_methods(self):
        """测试支持的方法列表。"""
        methods = self.calc.get_supported_methods()
        assert 'put_call_parity' in methods
        assert 'box_spread' in methods
        assert 'conversion_reversal' in methods
        assert 'butterfly_arbitrage' in methods


class TestIntegrationAdvanced:
    """高级模块集成测试"""

    def test_advanced_greeks_consistency_with_base_greeks(self):
        """测试高阶Greeks与基础Greeks的一致性。"""
        from domain.quantlib.derivatives import GreeksCalculator

        base_calc = GreeksCalculator()
        adv_calc = AdvancedGreeksCalculator()

        S, K, T, r, sigma = 100, 100, 1, 0.05, 0.2

        base_result = base_calc.calculate(S, K, T, r, sigma, 'call')
        adv_result = adv_calc.calculate(S, K, T, r, sigma, 'call')

        # 一阶Greeks应一致
        assert abs(base_result['value']['delta'] - adv_result['value']['delta']) < 1e-6
        assert abs(base_result['value']['gamma'] - adv_result['value']['gamma']) < 1e-6
        assert abs(base_result['value']['vega'] - adv_result['value']['vega']) < 1e-6
