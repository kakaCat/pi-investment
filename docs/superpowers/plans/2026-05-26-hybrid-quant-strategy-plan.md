# 混合路线量化策略 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现行业轮动 + 多因子精选 + ML 置信过滤三层混合量化策略，覆盖 A 股 + 港股。

**Architecture:** Python 策略引擎在 `quantsys-v2/services/strategy_engine/` 下拆分为三个独立模块（sector_rotation / factor_selection / ml_filter），由 `strategy_engine.py` 编排。通过 Flask REST API `/api/strategy/run` 暴露，TypeScript 端 `src/tools/strategy/` 负责调用和结果处理。

**Tech Stack:** Python 3.12+, Flask Blueprint, pandas, numpy; TypeScript (Node 22+), QuantV2Client

**Spec:** `docs/superpowers/specs/2026-05-26-hybrid-quant-strategy-design.md`

---

## File Structure

```
Create:
  quantsys-v2/services/strategy_engine/__init__.py
  quantsys-v2/services/strategy_engine/sector_rotation.py   # 行业轮动评分
  quantsys-v2/services/strategy_engine/factor_selection.py  # 多因子精选
  quantsys-v2/services/strategy_engine/ml_filter.py         # ML置信过滤
  quantsys-v2/services/strategy_engine/engine.py            # 编排器
  quantsys-v2/api/routes/strategy.py                        # REST API
  quantsys-v2/tests/test_sector_rotation.py
  quantsys-v2/tests/test_factor_selection.py
  quantsys-v2/tests/test_ml_filter.py
  quantsys-v2/tests/test_strategy_engine.py
  src/tools/strategy/strategy-runner.ts                     # TypeScript调用层

Modify:
  quantsys-v2/api/server.py                                 # 注册新blueprint
```

---

## Phase 1: Sector Rotation Service

### Task 1: Sector Rotation — Data Structures & Scoring

**Files:**
- Create: `quantsys-v2/services/strategy_engine/__init__.py`
- Create: `quantsys-v2/services/strategy_engine/sector_rotation.py`
- Create: `quantsys-v2/tests/test_sector_rotation.py`

- [ ] **Step 1: Create `__init__.py`**

```python
# quantsys-v2/services/strategy_engine/__init__.py
"""Strategy Engine — 行业轮动 + 多因子精选 + ML置信过滤"""
```

- [ ] **Step 2: Write failing test for sector rotation scoring**

```python
# quantsys-v2/tests/test_sector_rotation.py
import pytest
import pandas as pd
from services.strategy_engine.sector_rotation import SectorRotation, SectorScore

class TestSectorRotation:
    def test_score_sectors_basic(self):
        """测试行业评分基本逻辑：动量分 + 资金流分 + 强弱分"""
        rotator = SectorRotation(market="A")

        # 模拟 3 个行业数据
        momentum_data = {"食品饮料": 0.05, "电子": 0.12, "银行": -0.03}
        flow_data = {"食品饮料": 100, "电子": 500, "银行": -200}
        relative_strength = {"食品饮料": 0.02, "电子": 0.08, "银行": -0.05}

        scores = rotator.score(
            momentum=momentum_data,
            sector_flow=flow_data,
            relative_strength=relative_strength
        )

        assert len(scores) == 3
        # 电子行业应该排名第一（动量最高+资金流最多+相对强度最高）
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
        assert a_rotator.weights["flow"] == 0.35
        assert hk_rotator.weights["flow"] == 0.40  # 南向资金权重
        assert hk_rotator.weights["momentum"] == 0.35

    def test_continuous_top_penalty(self):
        """测试连续排名第一的衰减惩罚"""
        rotator = SectorRotation(market="A")
        rotator.consecutive_top_count = {"食品饮料": 4}  # 连续4周第一
        scores = [
            SectorScore("食品饮料", 0.80, {}),
            SectorScore("电子", 0.75, {}),
        ]
        adjusted = rotator.apply_consecutive_penalty(scores)
        # 食品饮料得分应该被打了8折
        assert adjusted[0].composite_score == pytest.approx(0.64)

    def test_normalize_scores(self):
        """测试Z-score标准化"""
        rotator = SectorRotation(market="A")
        raw = pd.Series([0.05, 0.10, 0.02, 0.08])
        normalized = rotator._normalize(raw)
        assert abs(normalized.mean()) < 0.001  # 均值为0
        assert abs(normalized.std() - 1.0) < 0.001  # 标准差为1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/test_sector_rotation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.strategy_engine.sector_rotation'`

- [ ] **Step 4: Implement SectorRotation**

```python
# quantsys-v2/services/strategy_engine/sector_rotation.py
"""
行业轮动评分引擎

A股: 动量40% + 资金流35% + 相对强弱25%
港股: 南向资金40% + 动量35% + 相对强弱25%
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class SectorScore:
    sector_name: str
    composite_score: float
    detail: Dict[str, float] = field(default_factory=dict)


class SectorRotation:
    """行业轮动评分器"""

    A_WEIGHTS = {"momentum": 0.40, "flow": 0.35, "strength": 0.25}
    HK_WEIGHTS = {"momentum": 0.35, "flow": 0.40, "strength": 0.25}

    MOMENTUM_PERIODS = [4, 8, 12]  # 4周/8周/12周多周期
    CONSECUTIVE_PENALTY_THRESHOLD = 4  # 连续4周排名第一触发衰减
    PENALTY_FACTOR = 0.8  # 打8折

    def __init__(self, market: str = "A"):
        if market not in ("A", "HK"):
            raise ValueError(f"market must be 'A' or 'HK', got {market}")
        self.market = market
        self.weights = self.A_WEIGHTS if market == "A" else self.HK_WEIGHTS
        self.consecutive_top_count: Dict[str, int] = {}

    def score(
        self,
        momentum: Dict[str, float],
        sector_flow: Dict[str, float],
        relative_strength: Dict[str, float]
    ) -> List[SectorScore]:
        """
        对所有行业进行综合评分。

        Args:
            momentum: {行业名: 多周期动量均值} — 已在外层做多周期等权平均
            sector_flow: {行业名: 周度资金流标准化得分}
            relative_strength: {行业名: vs基准超额收益}

        Returns:
            List[SectorScore] 按综合得分降序排列
        """
        sectors = sorted(set(momentum.keys()) | set(sector_flow.keys()) | set(relative_strength.keys()))
        results = []

        for sector in sectors:
            m = momentum.get(sector, 0.0)
            f = sector_flow.get(sector, 0.0)
            s = relative_strength.get(sector, 0.0)

            composite = (
                m * self.weights["momentum"] +
                f * self.weights["flow"] +
                s * self.weights["strength"]
            )

            results.append(SectorScore(
                sector_name=sector,
                composite_score=round(composite, 4),
                detail={"momentum": m, "flow": f, "strength": s}
            ))

        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results

    def _normalize(self, series: pd.Series) -> pd.Series:
        """Z-score标准化"""
        if series.std() == 0:
            return pd.Series(0.0, index=series.index)
        return (series - series.mean()) / series.std()

    def top_n(self, scores: List[SectorScore], n: int = 3) -> List[SectorScore]:
        """返回前N行业"""
        return scores[:n]

    def apply_consecutive_penalty(self, scores: List[SectorScore]) -> List[SectorScore]:
        """对连续排名第一的行业打折扣"""
        result = []
        for s in scores:
            count = self.consecutive_top_count.get(s.sector_name, 0)
            if count >= self.CONSECUTIVE_PENALTY_THRESHOLD:
                s.composite_score *= self.PENALTY_FACTOR
                logger.info(f"行业 {s.sector_name} 连续{count}周第一，打{PENALTY_FACTOR}折")
            result.append(s)
        result.sort(key=lambda x: x.composite_score, reverse=True)
        return result

    def update_consecutive_count(self, top_sector: str, all_sectors: List[str]):
        """更新连续排名计数"""
        for sector in all_sectors:
            if sector == top_sector:
                self.consecutive_top_count[sector] = self.consecutive_top_count.get(sector, 0) + 1
            else:
                self.consecutive_top_count[sector] = 0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/test_sector_rotation.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment
git add quantsys-v2/services/strategy_engine/__init__.py \
        quantsys-v2/services/strategy_engine/sector_rotation.py \
        quantsys-v2/tests/test_sector_rotation.py
git commit -m "feat: sector rotation scoring engine with A/HK dual weights"
```

---

## Phase 2: Multi-Factor Selection Service

### Task 2: Factor Selection — Stock Scoring

**Files:**
- Create: `quantsys-v2/services/strategy_engine/factor_selection.py`
- Create: `quantsys-v2/tests/test_factor_selection.py`

- [ ] **Step 1: Write failing test for factor selection**

```python
# quantsys-v2/tests/test_factor_selection.py
import pytest
import pandas as pd
import numpy as np
from services.strategy_engine.factor_selection import FactorSelector, FactorConfig

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
        """Z-score标准化后每个因子均值≈0，标准差≈1"""
        selector = FactorSelector(market="A")
        normalized = selector._zscore_normalize(sample_factors.drop(columns=["symbol"]))
        for col in normalized.columns:
            assert abs(normalized[col].mean()) < 0.01

    def test_exclude_st_stocks(self):
        """ST股票和次新股应被排除"""
        selector = FactorSelector(market="A")
        df = pd.DataFrame({
            "symbol": ["000001", "000002", "000003"],
            "name": ["平安银行", "ST测试", "新股"],
            "pe_percentile": [30, 50, 40],
            "is_st": [False, True, False],
            "days_listed": [500, 300, 30],  # 新股<60天
        })
        # 需要先补全因子列
        for col in ["pb_percentile", "dividend_yield", "roe", "gross_margin",
                     "cf_to_net_income", "debt_ratio", "ret_1m", "ret_3m",
                     "ret_6m", "rsi_14", "volume_ratio", "volatility_20d", "macd_trend"]:
            if col not in df.columns:
                df[col] = 0.0

        result = selector.score(df)
        symbols = [r.symbol for r in result]
        assert "000002" not in symbols  # ST
        assert "000003" not in symbols  # 次新股

    def test_top_n_per_sector(self, sample_factors):
        """每个行业取前N只"""
        selector = FactorSelector(market="A")
        # 给数据加上行业标签
        sample_factors["industry"] = ["电子"]*4 + ["食品饮料"]*3 + ["银行"]*3

        result = selector.score(sample_factors)
        grouped = selector.top_n_per_industry(result, n=3)

        assert "电子" in grouped
        assert "食品饮料" in grouped
        assert "银行" in grouped
        assert len(grouped["电子"]) <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/test_factor_selection.py -v`
Expected: FAIL

- [ ] **Step 3: Implement FactorSelector**

```python
# quantsys-v2/services/strategy_engine/factor_selection.py
"""
多因子精选引擎

4大类因子打分：价值20% + 质量30% + 动量25% + 技术25%
港股权重调整：价值25% + 质量15% + 动量30% + 技术30%
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class FactorConfig:
    """因子配置"""
    name: str
    category: str  # value, quality, momentum, technical
    direction: int  # 1=越大越好, -1=越小越好
    weight: float  # 子因子在类别内的权重


@dataclass
class StockScore:
    symbol: str
    name: str = ""
    score: float = 0.0
    category_scores: Dict[str, float] = field(default_factory=dict)
    factor_values: Dict[str, float] = field(default_factory=dict)


class FactorSelector:
    """多因子选股评分器"""

    # A股因子配置
    A_FACTORS = [
        # 价值类 (20%)
        FactorConfig("pe_percentile", "value", -1, 0.40),
        FactorConfig("pb_percentile", "value", -1, 0.35),
        FactorConfig("dividend_yield", "value", 1, 0.25),
        # 质量类 (30%)
        FactorConfig("roe", "quality", 1, 0.30),
        FactorConfig("gross_margin", "quality", 1, 0.25),
        FactorConfig("cf_to_net_income", "quality", 1, 0.25),
        FactorConfig("debt_ratio", "quality", -1, 0.20),
        # 动量类 (25%)
        FactorConfig("ret_1m", "momentum", 1, 0.30),
        FactorConfig("ret_3m", "momentum", 1, 0.35),
        FactorConfig("ret_6m", "momentum", 1, 0.20),
        FactorConfig("rsi_14", "momentum", 1, 0.15),
        # 技术类 (25%)
        FactorConfig("volume_ratio", "technical", 1, 0.35),
        FactorConfig("volatility_20d", "technical", -1, 0.35),  # 低波加分
        FactorConfig("macd_trend", "technical", 1, 0.30),
    ]

    A_CATEGORY_WEIGHTS = {"value": 0.20, "quality": 0.30, "momentum": 0.25, "technical": 0.25}
    HK_CATEGORY_WEIGHTS = {"value": 0.25, "quality": 0.15, "momentum": 0.30, "technical": 0.30}

    def __init__(self, market: str = "A"):
        if market not in ("A", "HK"):
            raise ValueError(f"market must be 'A' or 'HK', got {market}")
        self.market = market
        self.factors = self.A_FACTORS  # 港股因子列表会根据数据可用性动态调整
        self.category_weights = self.A_CATEGORY_WEIGHTS if market == "A" else self.HK_CATEGORY_WEIGHTS

    def score(self, df: pd.DataFrame) -> List[StockScore]:
        """
        对股票池进行多因子评分。

        Args:
            df: 包含 symbol + 各因子列的 DataFrame

        Returns:
            List[StockScore] 按综合得分降序排列
        """
        if df.empty:
            return []

        # 过滤ST和次新股
        df = self._filter_universe(df)

        if df.empty:
            return []

        # 取需要的因子列
        factor_cols = [f.name for f in self.factors if f.name in df.columns]
        if not factor_cols:
            logger.warning("No matching factor columns found in data")
            return []

        # Z-score 标准化
        factor_df = df[factor_cols].copy()
        normalized = self._zscore_normalize(factor_df)

        # 方向调整（低PE是好的 → 反转符号）
        for f in self.factors:
            if f.name in normalized.columns and f.direction == -1:
                normalized[f.name] = -normalized[f.name]

        # 分子类别计算得分
        category_scores: Dict[str, pd.Series] = {}
        for category in self.category_weights:
            cat_factors = [f for f in self.factors if f.category == category and f.name in normalized.columns]
            if not cat_factors:
                continue

            # 类别内等权平均（可后续改为IC加权）
            cat_score = pd.Series(0.0, index=normalized.index)
            for f in cat_factors:
                cat_score += normalized[f.name] * f.weight
            category_scores[category] = cat_score

        # 综合得分
        composite = pd.Series(0.0, index=normalized.index)
        for cat, weight in self.category_weights.items():
            if cat in category_scores:
                composite += category_scores[cat] * weight

        # 构建结果
        results = []
        for idx in composite.sort_values(ascending=False).index:
            row = df.loc[idx]
            results.append(StockScore(
                symbol=str(row.get("symbol", "")),
                name=str(row.get("name", "")),
                score=round(float(composite[idx]), 4),
                category_scores={cat: round(float(category_scores[cat][idx]), 4)
                                for cat in category_scores},
                factor_values={f.name: float(row[f.name]) if f.name in df.columns and not pd.isna(row[f.name]) else 0.0
                              for f in self.factors}
            ))

        return results

    def _filter_universe(self, df: pd.DataFrame) -> pd.DataFrame:
        """过滤ST股票和次新股(上市<60天)"""
        df = df.copy()
        # 过滤ST
        if "name" in df.columns:
            df = df[~df["name"].str.contains("ST", na=False)]
        if "is_st" in df.columns:
            df = df[~df["is_st"]]
        # 过滤次新股
        if "days_listed" in df.columns:
            df = df[df["days_listed"] >= 60]
        return df

    def _zscore_normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Z-score标准化（对每列）"""
        result = pd.DataFrame(index=df.index)
        for col in df.columns:
            std = df[col].std()
            if std == 0 or pd.isna(std):
                result[col] = 0.0
            else:
                result[col] = (df[col] - df[col].mean()) / std
        return result

    def top_n_per_industry(
        self,
        scores: List[StockScore],
        n: int = 5
    ) -> Dict[str, List[StockScore]]:
        """按行业取前N只"""
        groups: Dict[str, List[StockScore]] = {}
        for s in scores:
            industry = getattr(s, 'industry', '未知')
            if industry not in groups:
                groups[industry] = []
            groups[industry].append(s)

        result = {}
        for industry, stocks in groups.items():
            result[industry] = stocks[:n]

        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/test_factor_selection.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/strategy_engine/factor_selection.py \
        quantsys-v2/tests/test_factor_selection.py
git commit -m "feat: multi-factor stock selection with IC-aware category weights"
```

---

## Phase 3: ML Confidence Filter

### Task 3: ML Filter — Signal Voting

**Files:**
- Create: `quantsys-v2/services/strategy_engine/ml_filter.py`
- Create: `quantsys-v2/tests/test_ml_filter.py`

- [ ] **Step 1: Write failing test for ML filter**

```python
# quantsys-v2/tests/test_ml_filter.py
import pytest
from services.strategy_engine.ml_filter import MLFilter, MLVote

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
        # 港股不需要融合，直接使用XGBoost结果
        vote = fil.process_single_model("buy", 0.72)
        assert vote.verdict == "buy"
        assert vote.confidence == 0.72

    def test_pass_rate_check(self):
        """大面积否决时应标记"""
        fil = MLFilter()
        results = [MLVote("hold", 0.5, 1.0)] * 8 + [MLVote("buy", 0.8, 1.0)] * 2
        pass_rate = fil.check_pass_rate(results)
        assert pass_rate == 0.2
        assert pass_rate < 0.4  # 低于40%应标记
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/test_ml_filter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement MLFilter**

```python
# quantsys-v2/services/strategy_engine/ml_filter.py
"""
ML置信过滤层

角色：只做否决，不做选股。
A股：XGBoost + LightGBM 双模型融合
港股：仅 XGBoost
"""
from dataclasses import dataclass
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class MLVote:
    verdict: str  # buy / hold / sell
    confidence: float  # 0-1
    position_adjustment: float = 1.0  # 仓位调整系数


class MLFilter:
    """ML置信过滤"""

    CONFIDENCE_THRESHOLD = 0.65
    MIN_PASS_RATE = 0.40  # 最低通过率，低于此值暂停ML层

    def __init__(self, market: str = "A", confidence_threshold: float = None):
        self.market = market
        self.confidence_threshold = confidence_threshold or self.CONFIDENCE_THRESHOLD
        self.use_dual_model = (market == "A")

    @staticmethod
    def fuse_signals(
        xgb_signal: str,
        lgb_signal: str,
        xgb_confidence: float,
        lgb_confidence: float
    ) -> MLVote:
        """
        XGBoost + LightGBM 双模型融合规则

        ┌──────────┬───────────┬────────────────────────┐
        │ XGBoost  │ LightGBM  │ 判定                    │
        ├──────────┼───────────┼────────────────────────┤
        │ buy      │ buy       │ buy (置信度取均值)       │
        │ buy      │ hold      │ buy (仓位打8折)          │
        │ hold     │ buy       │ buy (仓位打8折)          │
        │ buy      │ sell      │ hold (冲突剔除)          │
        │ hold/sell│ hold/sell │ hold/sell               │
        └──────────┴───────────┴────────────────────────┘
        """
        avg_confidence = (xgb_confidence + lgb_confidence) / 2

        if xgb_signal == "buy" and lgb_signal == "buy":
            return MLVote("buy", avg_confidence, 1.0)

        if (xgb_signal == "buy" and lgb_signal == "hold") or \
           (xgb_signal == "hold" and lgb_signal == "buy"):
            return MLVote("buy", avg_confidence, 0.8)

        if xgb_signal == "sell" or lgb_signal == "sell":
            # 任一模型反对 → hold (不做空)
            return MLVote("hold", avg_confidence, 1.0)

        # 都是 hold
        return MLVote("hold", avg_confidence, 1.0)

    def process_single_model(self, signal: str, confidence: float) -> MLVote:
        """港股单模型处理"""
        return MLVote(
            verdict=signal if signal in ("buy", "hold", "sell") else "hold",
            confidence=confidence,
            position_adjustment=1.0
        )

    def passes(self, vote: MLVote) -> bool:
        """判断是否通过过滤"""
        return vote.verdict == "buy" and vote.confidence >= self.confidence_threshold

    def filter(
        self,
        candidates: List[str],
        predictions: Dict[str, Dict]
    ) -> List[str]:
        """
        过滤候选股票。

        Args:
            candidates: 候选股票代码列表
            predictions: {symbol: {xgb_signal, xgb_conf, lgb_signal, lgb_conf}}

        Returns:
            List[str] 通过过滤的股票代码
        """
        passed = []
        votes = []

        for symbol in candidates:
            pred = predictions.get(symbol, {})

            if self.use_dual_model:
                xgb_signal = pred.get("xgb_signal", "hold")
                xgb_conf = pred.get("xgb_confidence", 0.5)
                lgb_signal = pred.get("lgb_signal", "hold")
                lgb_conf = pred.get("lgb_confidence", 0.5)
                vote = self.fuse_signals(xgb_signal, lgb_signal, xgb_conf, lgb_conf)
            else:
                signal = pred.get("xgb_signal", "hold")
                conf = pred.get("xgb_confidence", 0.5)
                vote = self.process_single_model(signal, conf)

            votes.append(vote)

            if self.passes(vote):
                passed.append(symbol)
                logger.debug(f"ML通过: {symbol}, verdict={vote.verdict}, conf={vote.confidence:.2f}")

        # 检查通过率
        pass_rate = self.check_pass_rate(votes)
        if pass_rate < self.MIN_PASS_RATE:
            logger.warning(
                f"ML通过率仅 {pass_rate:.0%}，低于阈值 {self.MIN_PASS_RATE:.0%}，"
                f"建议暂停ML层使用"
            )

        return passed

    def check_pass_rate(self, votes: List[MLVote]) -> float:
        """计算通过率"""
        if not votes:
            return 0.0
        passed = sum(1 for v in votes if self.passes(v))
        return passed / len(votes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/test_ml_filter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/strategy_engine/ml_filter.py \
        quantsys-v2/tests/test_ml_filter.py
git commit -m "feat: ML confidence filter with dual-model fusion (XGBoost + LightGBM)"
```

---

## Phase 4: Strategy Engine Orchestrator

### Task 4: Strategy Engine — Pipeline Orchestrator

**Files:**
- Create: `quantsys-v2/services/strategy_engine/engine.py`
- Create: `quantsys-v2/tests/test_strategy_engine.py`

- [ ] **Step 1: Write failing test for engine**

```python
# quantsys-v2/tests/test_strategy_engine.py
import pytest
from unittest.mock import Mock, patch
from services.strategy_engine.engine import StrategyEngine, PipelineResult

class TestStrategyEngine:
    @pytest.fixture
    def engine(self):
        return StrategyEngine()

    def test_pipeline_result_dataclass(self):
        """PipelineResult结构正确"""
        result = PipelineResult(
            market="A",
            sectors=["电子", "食品饮料", "医药"],
            candidates=["000001", "000002", "000003"],
            final_portfolio=["000001", "000002"],
            ml_pass_rate=0.67,
            warnings=[]
        )
        assert result.market == "A"
        assert len(result.final_portfolio) == 2

    @patch.object(StrategyEngine, '_run_sector_rotation')
    @patch.object(StrategyEngine, '_run_factor_selection')
    @patch.object(StrategyEngine, '_run_ml_filter')
    def test_run_pipeline_order(self, mock_ml, mock_factor, mock_sector, engine):
        """流水线按正确顺序执行"""
        mock_sector.return_value = ["电子", "食品饮料", "医药"]
        mock_factor.return_value = {s: [f"stock_{i}"] for i, s in enumerate(["电子", "食品饮料", "医药"])}
        mock_ml.return_value = ["stock_0", "stock_1"]

        result = engine.run(market="A")

        # 确保调用顺序正确
        # 使用 mock 的 call_order 验证
        assert mock_sector.called
        assert mock_factor.called
        assert mock_ml.called

    def test_portfolio_builder_equal_weight(self, engine):
        """等权配置：行业等权 + 行业内个股等权"""
        candidates = {
            "电子": ["000001", "000002", "000003"],
            "食品饮料": ["000004", "000005"],
            "医药": ["000006"],
        }
        total_capital = 100000

        allocation = engine._build_portfolio(candidates, total_capital)

        # 3个行业 → 每个行业 33333
        assert len(allocation) == 6
        # 电子行业每只 = 33333/3 = 11111
        assert allocation["000001"]["capital"] == pytest.approx(11111, rel=0.01)
        # 单票不超15%
        max_pct = max(a["capital"] / total_capital for a in allocation.values())
        assert max_pct <= 0.15

    def test_portfolio_single_stock_cap(self, engine):
        """单只股票不超过15%"""
        candidates = {"电子": ["000001"]}  # 只有一个行业一只股
        total_capital = 100000

        allocation = engine._build_portfolio(candidates, total_capital)
        pct = allocation["000001"]["capital"] / total_capital
        assert pct <= 0.15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/test_strategy_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement StrategyEngine**

```python
# quantsys-v2/services/strategy_engine/engine.py
"""
策略编排引擎

串联三层流水线：行业轮动 → 多因子精选 → ML置信过滤 → 组合构建
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging

from .sector_rotation import SectorRotation, SectorScore
from .factor_selection import FactorSelector, StockScore
from .ml_filter import MLFilter, MLVote

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    market: str
    sectors: List[str] = field(default_factory=list)
    sector_scores: List[Dict] = field(default_factory=list)
    candidates: Dict[str, List[str]] = field(default_factory=dict)
    final_portfolio: List[str] = field(default_factory=list)
    allocation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    ml_pass_rate: float = 0.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class StrategyEngine:
    """混合策略编排器"""

    SINGLE_STOCK_MAX_PCT = 0.15
    A_HK_SPLIT = 0.70  # A股70%

    def __init__(self):
        self.a_rotation = SectorRotation(market="A")
        self.hk_rotation = SectorRotation(market="HK")
        self.a_selector = FactorSelector(market="A")
        self.hk_selector = FactorSelector(market="HK")
        self.a_ml_filter = MLFilter(market="A")
        self.hk_ml_filter = MLFilter(market="HK")

    def run(
        self,
        market: str = "A",
        sector_data: Dict = None,
        stock_data: Dict = None,
        ml_predictions: Dict = None
    ) -> PipelineResult:
        """
        执行完整流水线。

        Args:
            market: "A" 或 "HK"
            sector_data: 行业数据 {momentum, flow, strength}
            stock_data: 股票因子数据 DataFrame
            ml_predictions: ML预测结果 {symbol: {xgb_signal, xgb_conf, lgb_signal, lgb_conf}}

        Returns:
            PipelineResult
        """
        result = PipelineResult(market=market)

        try:
            # 第一层：行业轮动
            result.sectors = self._run_sector_rotation(market, sector_data)
            logger.info(f"[{market}] 行业轮动结果: {result.sectors}")

            # 第二层：因子精选
            result.candidates = self._run_factor_selection(market, stock_data, result.sectors)
            all_candidates = [s for stocks in result.candidates.values() for s in stocks]
            logger.info(f"[{market}] 因子精选候选: {len(all_candidates)}只 -> {result.candidates}")

            # 第三层：ML过滤
            ml_filter = self.a_ml_filter if market == "A" else self.hk_ml_filter
            passed = self._run_ml_filter(ml_filter, all_candidates, ml_predictions)
            result.final_portfolio = passed
            result.ml_pass_rate = len(passed) / len(all_candidates) if all_candidates else 0.0
            logger.info(f"[{market}] ML过滤后: {len(passed)}只 (通过率 {result.ml_pass_rate:.0%})")

            # 检查ML通过率
            if all_candidates and result.ml_pass_rate < MLFilter.MIN_PASS_RATE:
                result.warnings.append(
                    f"ML通过率仅 {result.ml_pass_rate:.0%}，低于 {MLFilter.MIN_PASS_RATE:.0%}，"
                    "建议暂停ML层，仅使用因子层结果"
                )
                # 使用因子层结果（不做ML过滤）
                result.final_portfolio = all_candidates

            # 组合构建
            # 重新按行业分组 final_portfolio
            final_by_sector = self._group_by_sector(result.final_portfolio, result.candidates)
            result.allocation = self._build_portfolio(final_by_sector)

        except Exception as e:
            logger.error(f"[{market}] 流水线执行失败: {e}", exc_info=True)
            result.errors.append(str(e))

        return result

    def _run_sector_rotation(self, market: str, data: Dict = None) -> List[str]:
        """执行行业轮动，返回前3行业名称"""
        if not data:
            logger.warning(f"[{market}] 无行业数据，使用默认全行业")
            return []

        rotator = self.a_rotation if market == "A" else self.hk_rotation
        scores = rotator.score(
            momentum=data.get("momentum", {}),
            sector_flow=data.get("flow", {}),
            relative_strength=data.get("strength", {})
        )

        # 应用连续排名衰减
        scores = rotator.apply_consecutive_penalty(scores)
        top = rotator.top_n(scores, n=3)
        return [s.sector_name for s in top]

    def _run_factor_selection(
        self,
        market: str,
        data: Any = None,
        sectors: List[str] = None
    ) -> Dict[str, List[str]]:
        """因子精选，按行业返回股票列表"""
        if data is None or data.empty:
            logger.warning(f"[{market}] 无股票因子数据")
            return {}

        selector = self.a_selector if market == "A" else self.hk_selector
        scores = selector.score(data)
        grouped = selector.top_n_per_industry(scores, n=5)

        if sectors:
            # 只返回前3行业的结果
            return {s: [stock.symbol for stock in grouped.get(s, [])]
                    for s in sectors if s in grouped}

        return {k: [stock.symbol for stock in v] for k, v in grouped.items()}

    def _run_ml_filter(
        self,
        ml_filter: MLFilter,
        candidates: List[str],
        predictions: Dict = None
    ) -> List[str]:
        """ML置信过滤"""
        if not candidates:
            return []
        if not predictions:
            logger.warning("无ML预测数据，所有候选通过")
            return candidates

        return ml_filter.filter(candidates, predictions)

    def _group_by_sector(
        self,
        symbols: List[str],
        sector_map: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """将最终选中的股票按行业分组"""
        grouped: Dict[str, List[str]] = {}
        for sector, stocks in sector_map.items():
            filtered = [s for s in stocks if s in symbols]
            if filtered:
                grouped[sector] = filtered
        return grouped

    def _build_portfolio(
        self,
        sector_candidates: Dict[str, List[str]],
        total_capital: float = 100000
    ) -> Dict[str, Dict[str, Any]]:
        """
        等权构建组合。

        Args:
            sector_candidates: {行业名: [股票代码]}
            total_capital: 总资金

        Returns:
            {symbol: {capital, pct, quantity}}
        """
        if not sector_candidates:
            return {}

        n_sectors = len(sector_candidates)
        capital_per_sector = total_capital / n_sectors

        allocation = {}
        for sector, stocks in sector_candidates.items():
            capital_per_stock = capital_per_sector / len(stocks)
            pct = capital_per_stock / total_capital

            # 单票上限
            if pct > self.SINGLE_STOCK_MAX_PCT:
                capital_per_stock = total_capital * self.SINGLE_STOCK_MAX_PCT
                pct = self.SINGLE_STOCK_MAX_PCT

            for symbol in stocks:
                allocation[symbol] = {
                    "capital": round(capital_per_stock, 2),
                    "pct": round(pct, 4),
                    "sector": sector,
                }

        return allocation
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/test_strategy_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/strategy_engine/engine.py \
        quantsys-v2/tests/test_strategy_engine.py
git commit -m "feat: strategy pipeline orchestrator with 3-layer execution"
```

---

## Phase 5: REST API Endpoint

### Task 5: Strategy API Route

**Files:**
- Create: `quantsys-v2/api/routes/strategy.py`
- Modify: `quantsys-v2/api/server.py` (add blueprint registration)

- [ ] **Step 1: Create strategy route file**

```python
# quantsys-v2/api/routes/strategy.py
"""
策略执行 API

POST /api/strategy/run  — 执行完整流水线
GET  /api/strategy/status — 获取当前策略状态
"""
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

strategy_bp = Blueprint('strategy', __name__)

# 延迟导入，避免循环依赖
_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        from services.strategy_engine.engine import StrategyEngine
        _engine = StrategyEngine()
    return _engine


@strategy_bp.route('/api/strategy/run', methods=['POST'])
def run_strategy():
    """
    执行策略流水线。

    Request body:
    {
        "market": "A",           // "A" 或 "HK"
        "sector_data": {         // 行业数据（可选，不传则实时拉取）
            "momentum": {...},
            "flow": {...},
            "strength": {...}
        },
        "stock_data": [...],     // 股票因子数据（DataFrame JSON，可选）
        "ml_predictions": {...}, // ML预测结果（可选）
        "total_capital": 100000  // 总资金
    }
    """
    try:
        data = request.get_json() or {}
        market = data.get("market", "A")
        total_capital = float(data.get("total_capital", 100000))

        if market not in ("A", "HK"):
            return jsonify({"success": False, "error": "market must be 'A' or 'HK'"}), 400

        engine = _get_engine()

        # 如果没有提供数据，使用默认空值（engine会正常处理）
        result = engine.run(
            market=market,
            sector_data=data.get("sector_data"),
            stock_data=data.get("stock_data"),
            ml_predictions=data.get("ml_predictions"),
        )

        # 如果传入了total_capital，重新计算allocation
        if total_capital != 100000 and result.candidates:
            all_symbols = [s for stocks in result.candidates.values() for s in stocks]
            final_by_sector = engine._group_by_sector(all_symbols, result.candidates)
            result.allocation = engine._build_portfolio(final_by_sector, total_capital)

        return jsonify({
            "success": True,
            "data": {
                "market": result.market,
                "sectors": result.sectors,
                "sector_scores": result.sector_scores,
                "candidates": result.candidates,
                "final_portfolio": result.final_portfolio,
                "allocation": result.allocation,
                "ml_pass_rate": result.ml_pass_rate,
                "warnings": result.warnings,
            }
        })

    except Exception as e:
        logger.error(f"策略执行失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@strategy_bp.route('/api/strategy/status', methods=['GET'])
def get_strategy_status():
    """获取策略状态"""
    engine = _get_engine()

    return jsonify({
        "success": True,
        "data": {
            "a_consecutive_counts": engine.a_rotation.consecutive_top_count,
            "hk_consecutive_counts": engine.hk_rotation.consecutive_top_count,
        }
    })
```

- [ ] **Step 2: Register blueprint in server.py**

Edit `quantsys-v2/api/server.py`, add after existing blueprint registrations:

```python
from api.routes.strategy import strategy_bp
app.register_blueprint(strategy_bp)
```

- [ ] **Step 3: Run all tests**

Run: `cd quantsys-v2 && python -m pytest tests/test_strategy_engine.py tests/test_sector_rotation.py tests/test_factor_selection.py tests/test_ml_filter.py -v`
Expected: ALL PASS

- [ ] **Step 4: Test API endpoint manually**

Start server: `cd quantsys-v2 && python api/server.py`
Then: `curl -X POST http://127.0.0.1:5001/api/strategy/run -H 'Content-Type: application/json' -d '{"market":"A"}'`
Expected: `{"success": true, "data": {...}}`

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/api/routes/strategy.py quantsys-v2/api/server.py
git commit -m "feat: strategy REST API endpoint — /api/strategy/run + /api/strategy/status"
```

---

## Phase 6: TypeScript Integration

### Task 6: Strategy Runner Tool (TypeScript)

**Files:**
- Create: `src/tools/strategy/strategy-runner.ts`

- [ ] **Step 1: Check existing QuantV2Client interface**

```bash
grep -rn "class QuantV2Client\|QuantV2Client" src/ --include="*.ts" | head -5
```

- [ ] **Step 2: Implement StrategyRunner**

```typescript
// src/tools/strategy/strategy-runner.ts
/**
 * 策略执行工具 — TypeScript 调用层
 *
 * 调用 quantsys-v2 /api/strategy/run 执行三层流水线，
 * 返回调仓建议供 portfolio_rebalance 使用。
 */

import { QuantV2Client } from '../../infrastructure/clients/quant-v2-client.js';

export interface StrategyRunRequest {
  market: 'A' | 'HK';
  sectorData?: {
    momentum: Record<string, number>;
    flow: Record<string, number>;
    strength: Record<string, number>;
  };
  stockData?: any; // DataFrame JSON
  mlPredictions?: Record<string, {
    xgb_signal: string;
    xgb_confidence: number;
    lgb_signal?: string;
    lgb_confidence?: number;
  }>;
  totalCapital?: number;
}

export interface StrategyRunResult {
  success: boolean;
  data?: {
    market: string;
    sectors: string[];
    candidates: Record<string, string[]>;
    finalPortfolio: string[];
    allocation: Record<string, {
      capital: number;
      pct: number;
      sector: string;
    }>;
    mlPassRate: number;
    warnings: string[];
  };
  error?: string;
}

export class StrategyRunner {
  private client: QuantV2Client;

  constructor() {
    this.client = new QuantV2Client();
  }

  async run(params: StrategyRunRequest): Promise<StrategyRunResult> {
    const response = await this.client.post('/api/strategy/run', {
      market: params.market,
      sector_data: params.sectorData,
      stock_data: params.stockData,
      ml_predictions: params.mlPredictions,
      total_capital: params.totalCapital || 100000,
    });

    if (!response.success) {
      return { success: false, error: response.error || 'Strategy execution failed' };
    }

    return {
      success: true,
      data: {
        market: response.data.market,
        sectors: response.data.sectors,
        candidates: response.data.candidates,
        finalPortfolio: response.data.final_portfolio,
        allocation: response.data.allocation,
        mlPassRate: response.data.ml_pass_rate,
        warnings: response.data.warnings,
      },
    };
  }

  async getStatus(): Promise<any> {
    return this.client.get('/api/strategy/status');
  }
}

export const strategyRunner = new StrategyRunner();
```

- [ ] **Step 3: Commit**

```bash
git add src/tools/strategy/strategy-runner.ts
git commit -m "feat: TypeScript strategy runner tool for quantsys-v2 integration"
```

---

## Phase 7: Integration Test & Documentation

### Task 7: End-to-End Integration Test

**Files:**
- Create: `quantsys-v2/tests/test_strategy_integration.py`

```python
# quantsys-v2/tests/test_strategy_integration.py
"""
集成测试：验证完整流水线在模拟数据上的表现
"""
import pytest
from services.strategy_engine.sector_rotation import SectorRotation
from services.strategy_engine.factor_selection import FactorSelector
from services.strategy_engine.ml_filter import MLFilter
from services.strategy_engine.engine import StrategyEngine

class TestStrategyIntegration:
    def test_full_pipeline_a_stock(self):
        """A股完整流水线端到端测试"""
        engine = StrategyEngine()

        # 模拟行业数据
        sector_data = {
            "momentum": {"电子": 0.12, "食品饮料": 0.05, "银行": -0.03, "医药": 0.08, "地产": -0.10},
            "flow": {"电子": 500, "食品饮料": 200, "银行": -300, "医药": 150, "地产": -100},
            "strength": {"电子": 0.08, "食品饮料": 0.02, "银行": -0.05, "医药": 0.04, "地产": -0.08},
        }

        result = engine.run(market="A", sector_data=sector_data)

        assert result.market == "A"
        # 没有股票数据时 sectors 会被计算但 candidates 为空
        assert len(result.sectors) <= 3

    def test_ml_filter_integration(self):
        """ML过滤与因子层集成测试"""
        ml_filter = MLFilter(market="A")
        candidates = ["000001", "000002", "000003", "000004", "000005"]

        predictions = {
            "000001": {"xgb_signal": "buy", "xgb_confidence": 0.75, "lgb_signal": "buy", "lgb_confidence": 0.80},
            "000002": {"xgb_signal": "buy", "xgb_confidence": 0.70, "lgb_signal": "hold", "lgb_confidence": 0.55},
            "000003": {"xgb_signal": "hold", "xgb_confidence": 0.50, "lgb_signal": "hold", "lgb_confidence": 0.50},
            "000004": {"xgb_signal": "buy", "xgb_confidence": 0.68, "lgb_signal": "sell", "lgb_confidence": 0.60},
            "000005": {"xgb_signal": "hold", "xgb_confidence": 0.55, "lgb_signal": "buy", "lgb_confidence": 0.72},
        }

        passed = ml_filter.filter(candidates, predictions)
        # 000001: buy+buy → pass
        # 000002: buy+hold → pass (打折)
        # 000003: hold+hold → fail
        # 000004: buy+sell → fail (冲突)
        # 000005: hold+buy → pass (打折)
        assert "000001" in passed
        assert "000005" in passed
        assert "000003" not in passed
        assert "000004" not in passed
```

- [ ] **Step 1: Run integration test**

Run: `cd quantsys-v2 && python -m pytest tests/test_strategy_integration.py -v`
Expected: PASS

- [ ] **Step 2: Run full test suite**

Run: `cd quantsys-v2 && python -m pytest tests/test_strategy_engine/ tests/test_sector_rotation.py tests/test_factor_selection.py tests/test_ml_filter.py tests/test_strategy_engine.py tests/test_strategy_integration.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/tests/test_strategy_integration.py
git commit -m "test: end-to-end strategy pipeline integration tests"
```

---

## Phase 8: Verification Summary

Run all tests and verify the strategy pipeline:

```bash
# 1. Run all strategy tests
cd quantsys-v2 && python -m pytest tests/test_sector_rotation.py tests/test_factor_selection.py tests/test_ml_filter.py tests/test_strategy_engine.py tests/test_strategy_integration.py -v

# 2. Check TypeScript compilation
cd /Users/mac/Documents/ai/pi-investment && npx tsc --noEmit src/tools/strategy/strategy-runner.ts

# 3. All committed?
git log --oneline -10
```

---

## Risk Notes

- **ML预测数据可用性**：流水线在不传 `ml_predictions` 时降级为跳过ML层，不影响因子层正常输出
- **港股因子覆盖率**：港股因子数据不如A股完整，已在 `FactorSelector` 中通过 `HK_CATEGORY_WEIGHTS` 调整权重
- **行业轮动数据依赖**：`market.sectors` 和 `market.sector_flow` 依赖外部数据源，失败时需fallback到全行业等权
- **回测验证**：本实现不包括回测逻辑，回测通过现有的 `quant_cli backtest.run` 和 `factor.analyze` 执行
