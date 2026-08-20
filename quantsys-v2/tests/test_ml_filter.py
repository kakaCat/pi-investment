import pytest
import sys
import os
from application.services.strategy_engine.ml_filter import MLFilter, MLVote


class TestMLFilter:
    def test_fusion_both_buy(self):
        """双模型都预测 buy → buy"""
        result = MLFilter.fuse_signals("buy", "buy", 0.75, 0.80)
        assert result.verdict == "buy"
        assert result.confidence == pytest.approx(0.775)  # 均值

    def test_fusion_buy_hold(self):
        """一个buy一个hold → buy但仓位打折"""
        result = MLFilter.fuse_signals("buy", "hold", 0.70, 0.50)
        assert result.verdict == "buy"
        assert result.position_adjustment == 0.8

    def test_fusion_conflict(self):
        """buy vs sell → hold (剔除)"""
        result = MLFilter.fuse_signals("buy", "sell", 0.75, 0.70)
        assert result.verdict == "hold"

    def test_fusion_both_hold(self):
        """双hold → hold"""
        result = MLFilter.fuse_signals("hold", "hold", 0.50, 0.50)
        assert result.verdict == "hold"

    def test_confidence_threshold(self):
        """置信度低于阈值 → 不通过"""
        fil = MLFilter(confidence_threshold=0.65)
        vote = MLVote("hold", 0.55, 1.0)
        assert not fil.passes(vote)

        vote2 = MLVote("buy", 0.70, 1.0)
        assert fil.passes(vote2)

    def test_hk_single_model(self):
        """港股只用 XGBoost"""
        fil = MLFilter(market="HK")
        vote = fil.process_single_model("buy", 0.72)
        assert vote.verdict == "buy"
        assert vote.confidence == 0.72

    def test_pass_rate_check(self):
        """大面积否决时应标记"""
        fil = MLFilter()
        results = [MLVote("hold", 0.5, 1.0)] * 8 + [MLVote("buy", 0.8, 1.0)] * 2
        pass_rate = fil.check_pass_rate(results)
        assert pass_rate == 0.2
        assert pass_rate < 0.4

    def test_filter_pipeline(self):
        """完整过滤流水线"""
        fil = MLFilter(market="A")
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

        passed = fil.filter(candidates, predictions)
        # 000001: buy+buy(0.775) → pass
        # 000002: buy+hold(0.625) < 0.65 → fail
        # 000003: hold+hold → fail
        # 000004: buy+sell → hold(fail)
        # 000005: hold+buy(0.635) < 0.65 → fail
        assert passed == ["000001"]
