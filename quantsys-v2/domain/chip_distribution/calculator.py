"""筹码分布计算器 — 纯计算，无 IO

模型：每只股票一个价位桶数组 counts[N_BINS]，覆盖 [price_min, price_min + N*bin_width]。
每个交易日两步：
  1. 衰减：counts *= (1 - t)，t = 换手率（0~1，封顶 1.0）
  2. 新增：质量 t 按三角分布摊到 [low, high]，峰值在典型价 (H+L+2C)/4

总量不变式：steady state 下 sum(counts) == 1（sum' = (1-t)*sum + t）。
初期 sum < 1 是物理含义（历史筹码未完全建模），metrics 计算时归一化。

价位近似：三角分布在桶中心采样后归一化，N=200 桶下误差可忽略。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

N_BINS = 200


class ChipDistribution:
    def __init__(self, price_min: float, bin_width: float, counts: np.ndarray):
        self.price_min = float(price_min)
        self.bin_width = float(bin_width)
        self.counts = counts  # shape (N_BINS,), float64

    # ---------- 构造 ----------

    @classmethod
    def empty(cls, price_min: float, price_max: float, n_bins: int = N_BINS) -> "ChipDistribution":
        price_min = float(price_min)
        price_max = float(price_max)
        if price_max <= price_min:
            price_max = price_min * 1.01 + 0.01
        # 上下各留 10% 余量，减少重分桶频率
        span = price_max - price_min
        lo = price_min - span * 0.1
        hi = price_max + span * 0.1
        return cls(lo, (hi - lo) / n_bins, np.zeros(n_bins, dtype=np.float64))

    @classmethod
    def from_klines(cls, klines: List[Dict[str, Any]]) -> "ChipDistribution":
        """从 K 线序列（时间升序）构建分布。klines 元素需含 low/high/close/turnover_rate。

        turnover_rate 单位为 %，缺失（None）按 0 处理（调用方负责回退估算）。
        """
        if not klines:
            raise ValueError("klines 不能为空")
        lows = [k["low"] for k in klines]
        highs = [k["high"] for k in klines]
        d = cls.empty(min(lows), max(highs))
        for k in klines:
            d.apply_day(k["low"], k["high"], k["close"], k.get("turnover_rate") or 0.0)
        return d

    # ---------- 序列化 ----------

    def to_bytes(self) -> bytes:
        return self.counts.astype(np.float64).tobytes()

    @classmethod
    def from_bytes(cls, price_min: float, bin_width: float, blob: bytes) -> "ChipDistribution":
        counts = np.frombuffer(blob, dtype=np.float64).copy()
        return cls(price_min, bin_width, counts)

    # ---------- 核心更新 ----------

    def _price_max(self) -> float:
        return self.price_min + self.bin_width * len(self.counts)

    def bin_centers(self) -> np.ndarray:
        return self.price_min + (np.arange(len(self.counts)) + 0.5) * self.bin_width

    def _ensure_range(self, low: float, high: float) -> None:
        """价格超出覆盖范围时重分桶（旧分布按桶中心线性重采样）"""
        if low >= self.price_min and high <= self._price_max():
            return
        span = self._price_max() - self.price_min
        new_min = min(self.price_min, low - span * 0.1)
        new_max = max(self._price_max(), high + span * 0.1)
        new_width = (new_max - new_min) / len(self.counts)
        old_centers = self.bin_centers()
        new_centers = new_min + (np.arange(len(self.counts)) + 0.5) * new_width
        self.counts = np.interp(new_centers, old_centers, self.counts, left=0.0, right=0.0)
        self.price_min = new_min
        self.bin_width = new_width

    def apply_day(self, low: float, high: float, close: float, turnover_rate: float) -> None:
        """应用一个交易日。turnover_rate 单位 %，封顶 100。low==high（一字板）安全。"""
        t = min(max(float(turnover_rate), 0.0), 100.0) / 100.0
        if t == 0.0:
            return
        self._ensure_range(low, high)
        self.counts *= (1.0 - t)

        centers = self.bin_centers()
        if high <= low:
            idx = int(np.argmin(np.abs(centers - close)))
            self.counts[idx] += t
            return
        typical = (high + low + 2.0 * close) / 4.0
        # 三角分布：low→typical 上升，typical→high 下降
        weights = np.zeros(len(centers), dtype=np.float64)
        left = (centers >= low) & (centers <= typical)
        right = (centers > typical) & (centers <= high)
        if typical > low:
            weights[left] = (centers[left] - low) / (typical - low)
        if high > typical:
            weights[right] = (high - centers[right]) / (high - typical)
        total = weights.sum()
        if total <= 0:
            idx = int(np.argmin(np.abs(centers - typical)))
            weights[idx] = 1.0
            total = 1.0
        self.counts += t * weights / total

    # ---------- 查询 ----------

    def mass_between(self, low: float, high: float) -> float:
        centers = self.bin_centers()
        return float(self.counts[(centers >= low) & (centers <= high)].sum())

    def price_at_peak(self) -> float:
        return float(self.bin_centers()[int(np.argmax(self.counts))])

    def _percentile(self, p: np.ndarray, q: float) -> float:
        """p 为归一化后的质量数组，返回 q 分位（0~1）对应价格"""
        cdf = np.cumsum(p)
        centers = self.bin_centers()
        idx = int(np.searchsorted(cdf, q))
        idx = min(idx, len(centers) - 1)
        return float(centers[idx])

    def metrics(self, close: float) -> Dict[str, Optional[float]]:
        total = self.counts.sum()
        if total <= 0:
            return {
                "profit_ratio": None, "avg_cost": None,
                "cost_90_low": None, "cost_90_high": None,
                "cost_70_low": None, "cost_70_high": None,
                "peak_price": None, "concentration": None,
            }
        p = self.counts / total
        centers = self.bin_centers()
        profit_ratio = float(p[centers < close].sum())
        avg_cost = float((p * centers).sum())
        c90l, c90h = self._percentile(p, 0.05), self._percentile(p, 0.95)
        c70l, c70h = self._percentile(p, 0.15), self._percentile(p, 0.85)
        mid = (c70l + c70h) / 2.0
        concentration = float((c70h - c70l) / mid) if mid > 0 else None
        return {
            "profit_ratio": profit_ratio,
            "avg_cost": avg_cost,
            "cost_90_low": c90l,
            "cost_90_high": c90h,
            "cost_70_low": c70l,
            "cost_70_high": c70h,
            "peak_price": self.price_at_peak(),
            "concentration": concentration,
        }
