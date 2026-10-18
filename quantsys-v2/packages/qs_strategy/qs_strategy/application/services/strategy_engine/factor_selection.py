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
    industry: str = ""
    score: float = 0.0
    category_scores: Dict[str, float] = field(default_factory=dict)
    factor_values: Dict[str, float] = field(default_factory=dict)


class FactorSelector:
    """多因子选股评分器"""

    A_FACTORS = [
        FactorConfig("pe_percentile", "value", -1, 0.40),
        FactorConfig("pb_percentile", "value", -1, 0.35),
        FactorConfig("dividend_yield", "value", 1, 0.25),
        FactorConfig("roe", "quality", 1, 0.30),
        FactorConfig("gross_margin", "quality", 1, 0.25),
        FactorConfig("cf_to_net_income", "quality", 1, 0.25),
        FactorConfig("debt_ratio", "quality", -1, 0.20),
        FactorConfig("ret_1m", "momentum", 1, 0.30),
        FactorConfig("ret_3m", "momentum", 1, 0.35),
        FactorConfig("ret_6m", "momentum", 1, 0.20),
        FactorConfig("rsi_14", "momentum", 1, 0.15),
        FactorConfig("volume_ratio", "technical", 1, 0.35),
        FactorConfig("volatility_20d", "technical", -1, 0.35),
        FactorConfig("macd_trend", "technical", 1, 0.30),
    ]

    A_CATEGORY_WEIGHTS = {"value": 0.20, "quality": 0.30, "momentum": 0.25, "technical": 0.25}
    HK_CATEGORY_WEIGHTS = {"value": 0.25, "quality": 0.15, "momentum": 0.30, "technical": 0.30}

    def __init__(self, market: str = "A"):
        if market not in ("A", "HK"):
            raise ValueError(f"market must be 'A' or 'HK', got {market}")
        self.market = market
        self.factors = self.A_FACTORS
        self.category_weights = self.A_CATEGORY_WEIGHTS if market == "A" else self.HK_CATEGORY_WEIGHTS

    def score(self, df: pd.DataFrame) -> List[StockScore]:
        """对股票池进行多因子评分。"""
        if df.empty:
            return []

        df = self._filter_universe(df)

        if df.empty:
            return []

        factor_cols = [f.name for f in self.factors if f.name in df.columns]
        if not factor_cols:
            logger.warning("No matching factor columns found in data")
            return []

        factor_df = df[factor_cols].copy()
        normalized = self._zscore_normalize(factor_df)

        for f in self.factors:
            if f.name in normalized.columns and f.direction == -1:
                normalized[f.name] = -normalized[f.name]

        category_scores: Dict[str, pd.Series] = {}
        for category in self.category_weights:
            cat_factors = [f for f in self.factors if f.category == category and f.name in normalized.columns]
            if not cat_factors:
                continue

            cat_score = pd.Series(0.0, index=normalized.index)
            for f in cat_factors:
                cat_score += normalized[f.name] * f.weight
            category_scores[category] = cat_score

        composite = pd.Series(0.0, index=normalized.index)
        for cat, weight in self.category_weights.items():
            if cat in category_scores:
                composite += category_scores[cat] * weight

        results = []
        for idx in composite.sort_values(ascending=False).index:
            row = df.loc[idx]
            results.append(StockScore(
                symbol=str(row.get("symbol", "")),
                name=str(row.get("name", "")),
                industry=str(row.get("industry", "")),
                score=round(float(composite[idx]), 4),
                category_scores={cat: round(float(category_scores[cat][idx]), 4)
                               for cat in category_scores},
                factor_values={f.name: float(row[f.name])
                             if f.name in df.columns and not pd.isna(row[f.name]) else 0.0
                             for f in self.factors}
            ))

        return results

    def _filter_universe(self, df: pd.DataFrame) -> pd.DataFrame:
        """过滤ST股票和次新股(上市<60天)"""
        df = df.copy()
        if "name" in df.columns:
            df = df[~df["name"].str.contains("ST", na=False)]
        if "is_st" in df.columns:
            df = df[df["is_st"] == 0]
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
