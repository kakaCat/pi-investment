"""
集成测试：验证完整流水线在模拟数据上的表现
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from application.services.strategy_engine.engine import StrategyEngine
from application.services.strategy_engine.ml_filter import MLFilter


class TestStrategyIntegration:
    def test_full_pipeline_a_with_data(self):
        """A股完整流水线端到端测试"""
        engine = StrategyEngine()

        sector_data = {
            "momentum": {"电子": 0.12, "食品饮料": 0.05, "银行": -0.03, "医药": 0.08, "地产": -0.10},
            "flow": {"电子": 500, "食品饮料": 200, "银行": -300, "医药": 150, "地产": -100},
            "strength": {"电子": 0.08, "食品饮料": 0.02, "银行": -0.05, "医药": 0.04, "地产": -0.08},
        }

        result = engine.run(market="A", sector_data=sector_data)

        assert result.market == "A"
        assert len(result.sectors) <= 3
        assert len(result.sector_scores) == len(result.sectors)
        assert result.sector_scores[0]["sector_name"] == result.sectors[0]
        assert "composite_score" in result.sector_scores[0]
        # 没有股票数据时 candidates 为空，final_portfolio 为空
        assert result.candidates == {}
        assert result.final_portfolio == []

    def test_ml_filter_integration(self):
        """ML过滤与因子层集成测试"""
        ml_filter = MLFilter(market="A")
        candidates = ["000001", "000002", "000003", "000004", "000005"]

        predictions = {
            "000001": {"xgb_signal": "buy", "xgb_confidence": 0.75,
                       "lgb_signal": "buy", "lgb_confidence": 0.80},
            "000002": {"xgb_signal": "buy", "xgb_confidence": 0.70,
                       "lgb_signal": "hold", "lgb_confidence": 0.55},
            "000003": {"xgb_signal": "hold", "xgb_confidence": 0.50,
                       "lgb_signal": "hold", "lgb_confidence": 0.50},
            "000004": {"xgb_signal": "buy", "xgb_confidence": 0.68,
                       "lgb_signal": "sell", "lgb_confidence": 0.60},
            "000005": {"xgb_signal": "hold", "xgb_confidence": 0.55,
                       "lgb_signal": "buy", "lgb_confidence": 0.72},
        }

        passed = ml_filter.filter(candidates, predictions)
        # 000001: buy+buy(0.775≥0.65) → pass
        # 000002: buy+hold(0.625<0.65) → fail
        # 000003: hold+hold → fail
        # 000004: buy+sell → hold(fail)
        # 000005: hold+buy(0.635<0.65) → fail
        assert "000001" in passed
        assert "000002" not in passed
        assert "000003" not in passed
        assert "000004" not in passed
        assert "000005" not in passed

    def test_pipeline_with_ml_fallback(self):
        """ML通过率太低时自动fallback到因子层"""
        engine = StrategyEngine()

        import pandas as pd
        import numpy as np
        np.random.seed(42)
        symbols = [f"00000{i}" for i in range(1, 11)]
        stock_data = pd.DataFrame({
            "symbol": symbols,
            "industry": ["电子"] * 3 + ["食品饮料"] * 3 + ["医药"] * 4,
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

        result = engine.run(market="A", stock_data=stock_data)
        # 没有ML预测 → 所有候选通过
        assert len(result.candidates) > 0
        assert len(result.final_portfolio) > 0

    def test_hk_pipeline(self):
        """港股流水线正确使用港股参数"""
        engine = StrategyEngine()
        assert engine.hk_rotation.market == "HK"
        assert engine.hk_selector.market == "HK"
        assert not engine.hk_ml_filter.use_dual_model
        assert engine.hk_ml_filter.market == "HK"
