import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from application.services.strategy_engine.factor_selection import FactorSelector, FactorConfig


class TestFactorSelector:
    @pytest.fixture
    def sample_factors(self):
        """模拟10只股票的因子数据"""
        symbols = [f"00000{i}" for i in range(1, 11)]
        np.random.seed(42)
        return pd.DataFrame({
            "symbol": symbols,
            "pe_percentile": np.random.uniform(0, 100, 10),
            "pb_percentile": np.random.uniform(0, 100, 10),
            "dividend_yield": np.random.uniform(0, 5, 10),
            "roe": np.random.uniform(2, 30, 10),
            "gross_margin": np.random.uniform(10, 80, 10),
            "cf_to_net_income": np.random.uniform(0.3, 2.0, 10),
            "debt_ratio": np.random.uniform(10, 80, 10),
            "ret_1m": np.random.uniform(-15, 20, 10),
            "ret_3m": np.random.uniform(-25, 40, 10),
            "ret_6m": np.random.uniform(-30, 60, 10),
            "rsi_14": np.random.uniform(20, 80, 10),
            "volume_ratio": np.random.uniform(0.5, 3.0, 10),
            "volatility_20d": np.random.uniform(0.01, 0.08, 10),
            "macd_trend": np.random.choice([-1, 0, 1], 10),
        })

    def test_score_stocks_returns_sorted(self, sample_factors):
        """因子打分返回按得分降序排列的结果"""
        selector = FactorSelector(market="A")
        result = selector.score(sample_factors)

        assert len(result) == 10
        assert result[0].score >= result[-1].score
        assert all(hasattr(r, 'symbol') for r in result)
        assert all(hasattr(r, 'category_scores') for r in result)

    def test_a_hk_weights_differ(self):
        """A股和港股使用不同的因子权重"""
        a_selector = FactorSelector(market="A")
        hk_selector = FactorSelector(market="HK")

        assert a_selector.category_weights["quality"] == 0.30
        assert hk_selector.category_weights["quality"] == 0.15
        assert hk_selector.category_weights["momentum"] == 0.30

    def test_zscore_normalization(self, sample_factors):
        """Z-score标准化后每个因子均值≈0"""
        selector = FactorSelector(market="A")
        factor_df = sample_factors.drop(columns=["symbol"])
        normalized = selector._zscore_normalize(factor_df)
        for col in normalized.columns:
            assert abs(normalized[col].mean()) < 0.01

    def test_exclude_st_stocks(self):
        """ST股票和次新股应被排除"""
        selector = FactorSelector(market="A")
        df = pd.DataFrame({
            "symbol": ["000001", "000002", "000003"],
            "name": ["平安银行", "ST测试", "新股"],
            "pe_percentile": [30.0, 50.0, 40.0],
            "is_st": [False, True, False],
            "days_listed": [500, 300, 30],
        })
        for col in ["pb_percentile", "dividend_yield", "roe", "gross_margin",
                     "cf_to_net_income", "debt_ratio", "ret_1m", "ret_3m",
                     "ret_6m", "rsi_14", "volume_ratio", "volatility_20d", "macd_trend"]:
            if col not in df.columns:
                df[col] = 0.0

        result = selector.score(df)
        symbols = [r.symbol for r in result]
        assert "000002" not in symbols  # ST
        assert "000003" not in symbols  # 次新股 < 60天

    def test_top_n_per_sector(self, sample_factors):
        """每个行业取前N只"""
        selector = FactorSelector(market="A")
        sample_factors["industry"] = ["电子"]*4 + ["食品饮料"]*3 + ["银行"]*3

        result = selector.score(sample_factors)
        # 把 industry 信息带到 StockScore 上
        industry_map = dict(zip(sample_factors["symbol"], sample_factors["industry"]))
        for r in result:
            r.industry = industry_map.get(r.symbol, "未知")

        grouped = selector.top_n_per_industry(result, n=3)

        assert "电子" in grouped
        assert len(grouped["电子"]) <= 3
