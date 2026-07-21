import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from application.services.strategy_engine.sector_rotation import SectorRotation, SectorScore


class TestSectorRotation:
    def test_score_sectors_basic(self):
        """测试行业评分基本逻辑：动量分 + 资金流分 + 强弱分"""
        rotator = SectorRotation(market="A")

        momentum_data = {"食品饮料": 0.05, "电子": 0.12, "银行": -0.03}
        flow_data = {"食品饮料": 100, "电子": 500, "银行": -200}
        relative_strength = {"食品饮料": 0.02, "电子": 0.08, "银行": -0.05}

        scores = rotator.score(
            momentum=momentum_data,
            sector_flow=flow_data,
            relative_strength=relative_strength
        )

        assert len(scores) == 3
        assert scores[0].sector_name == "电子"
        assert scores[0].composite_score > scores[2].composite_score

    def test_top_n_selection(self):
        """测试取前N行业"""
        rotator = SectorRotation(market="A")
        scores = [
            SectorScore("食品饮料", 0.75, {"momentum": 0.3, "flow": 0.25, "strength": 0.2}),
            SectorScore("电子", 0.85, {"momentum": 0.35, "flow": 0.3, "strength": 0.2}),
            SectorScore("银行", 0.45, {"momentum": 0.15, "flow": 0.15, "strength": 0.15}),
            SectorScore("医药", 0.65, {"momentum": 0.25, "flow": 0.2, "strength": 0.2}),
        ]
        top = rotator.top_n(scores, n=3)
        assert len(top) == 3
        assert top[0].sector_name == "电子"

    def test_hk_weights_differ_from_a(self):
        """港股权重应与A股不同（南向资金权重更高）"""
        a_rotator = SectorRotation(market="A")
        hk_rotator = SectorRotation(market="HK")

        assert a_rotator.weights["momentum"] == 0.40
        assert hk_rotator.weights["flow"] == 0.40
        assert hk_rotator.weights["momentum"] == 0.35

    def test_continuous_top_penalty(self):
        """测试连续排名第一的衰减惩罚"""
        rotator = SectorRotation(market="A")
        rotator.consecutive_top_count = {"食品饮料": 4}
        scores = [
            SectorScore("食品饮料", 0.80, {}),
            SectorScore("电子", 0.75, {}),
        ]
        adjusted = rotator.apply_consecutive_penalty(scores)
        # 食品饮料被打折后(0.64)排名第二，电子(0.75)排第一
        assert adjusted[1].composite_score == pytest.approx(0.64, 0.001)
        assert adjusted[0].composite_score == pytest.approx(0.75, 0.001)

    def test_normalize_scores(self):
        """测试Z-score标准化"""
        rotator = SectorRotation(market="A")
        raw = pd.Series([0.05, 0.10, 0.02, 0.08])
        normalized = rotator._normalize(raw)
        assert abs(normalized.mean()) < 0.001
        assert abs(normalized.std() - 1.0) < 0.001
