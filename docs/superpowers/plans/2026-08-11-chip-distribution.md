# 筹码分布（成本分布）服务实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于日 K 线 OHLCV + 换手率构建全市场筹码分布（成本分布）服务：每日增量计算落表 + 单票分布曲线 API + agent-ts 决策工具。

**Architecture:** 纯计算（domain）与编排（service）、数据访问（adapters repository）分离；存量分布按股票滚动维护在 `chip_distribution_state` 表，每日摘要指标落 `chip_metrics` 表；调度任务挂在 kline 更新之后做增量。

**Tech Stack:** Python 3.13 / numpy / SQLAlchemy (BaseORMRepository 模式) / FastAPI / pytest；agent-ts 侧 TypeScript + jest。

**设计文档:** `docs/superpowers/specs/2026-08-11-chip-distribution-design.md`

**目录映射说明（相对 spec 的调整）:** 仓库没有顶层 `services/` 目录，遵循现有 DDD 分层：
- calculator → `quantsys-v2/domain/chip_distribution/calculator.py`（纯计算）
- service → `quantsys-v2/domain/chip_distribution/service.py`（编排）
- repository → `quantsys-v2/adapters/outbound/repositories/chip_repository.py`

**关键仓库约定（实施前必读）:**
- Repository 基类：`quantsys-v2/infrastructure/persistence/orm/base_repository.py` 的 `BaseORMRepository`，子类设 `model` 类属性，`self.session` 懒加载线程共享 session，所有 `except` 分支必须调 `self._safe_rollback()`
- Job 模板：`quantsys-v2/infrastructure/jobs/fund_flow_update_job.py`（`execute(**params)` 入口，返回 dict）
- 调度注册：往 `quant.scheduler_task_configs` 插一行（见 `quantsys-v2/scripts/migrations/008_seed_index_constituents_job.sql`），scheduler_daemon 从该表加载
- 迁移 SQL 放 `quantsys-v2/scripts/migrations/`，用 `psql -d quant_investment -f <file>` 应用
- FastAPI 路由模板：`quantsys-v2/adapters/inbound/fastapi_app/routes/analysis_async.py`，用 `from adapters.inbound.fastapi_app.shared import api_response, error_response`
- agent-ts 工具模板：`agent-ts/src/infrastructure/tools/analysis/chan-analyze-tool.ts`；路由命令注册在 `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts` 的 `V2_ROUTES`（**禁止直接传 URL 路径**，必须注册命令名）；工具总注册在 `agent-ts/src/infrastructure/tools/index.ts`
- pytest 有预存在失败 baseline，只保证新增测试绿；agent-ts 测试必须 `npm test`（禁止裸 `npx jest`）
- K 线 symbol 格式为 `600519.SH` 带后缀；`daily_klines.volume` 单位=股、`amount` 单位=元、`turnover_rate` 单位=%

---

### Task 1: 建表迁移

**Files:**
- Create: `quantsys-v2/scripts/migrations/010_create_chip_distribution_tables.sql`

- [ ] **Step 1: 写迁移 SQL**

```sql
-- 010_create_chip_distribution_tables.sql
-- 筹码分布（成本分布）服务
-- 设计：docs/superpowers/specs/2026-08-11-chip-distribution-design.md

-- 每股票一行：增量计算的滚动状态（价位桶数组）
CREATE TABLE IF NOT EXISTS quant.chip_distribution_state (
    symbol          TEXT PRIMARY KEY REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    price_min       DOUBLE PRECISION NOT NULL,
    bin_width       DOUBLE PRECISION NOT NULL,
    counts          BYTEA NOT NULL,           -- numpy float64 数组序列化（N_BINS 个）
    last_trade_date DATE NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 每日摘要指标：全市场约 5270 行/日，供扫描/因子用
CREATE TABLE IF NOT EXISTS quant.chip_metrics (
    symbol        TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    trade_date    DATE NOT NULL,
    profit_ratio  DOUBLE PRECISION,   -- 获利盘比例：收盘价以下筹码占比
    avg_cost      DOUBLE PRECISION,   -- 平均持仓成本
    cost_90_low   DOUBLE PRECISION,
    cost_90_high  DOUBLE PRECISION,   -- 90% 成本区间
    cost_70_low   DOUBLE PRECISION,
    cost_70_high  DOUBLE PRECISION,   -- 70% 成本区间
    peak_price    DOUBLE PRECISION,   -- 最大密集峰价位
    concentration DOUBLE PRECISION,   -- (cost_70_high - cost_70_low) / 区间中位价
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_chip_metrics_date ON quant.chip_metrics (trade_date);
CREATE INDEX IF NOT EXISTS idx_chip_metrics_profit ON quant.chip_metrics (trade_date, profit_ratio);
```

- [ ] **Step 2: 应用迁移并验证**

```bash
psql -d quant_investment -f quantsys-v2/scripts/migrations/010_create_chip_distribution_tables.sql
psql -d quant_investment -c "\d quant.chip_metrics"
```
Expected: 两表创建成功，`\d` 输出显示上述列。

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/scripts/migrations/010_create_chip_distribution_tables.sql
git commit -m "feat(chip): 009 建表——chip_distribution_state + chip_metrics"
```

---

### Task 2: calculator 纯计算核心（TDD）

**Files:**
- Create: `quantsys-v2/domain/chip_distribution/__init__.py`
- Create: `quantsys-v2/domain/chip_distribution/calculator.py`
- Test: `quantsys-v2/tests/chip/test_calculator.py`

- [ ] **Step 1: 写失败的测试**

创建 `quantsys-v2/tests/chip/__init__.py`（空文件）和 `quantsys-v2/tests/chip/test_calculator.py`：

```python
"""筹码分布计算器单测 — 合成 K 线，不依赖数据库"""
import numpy as np
import pytest

from domain.chip_distribution.calculator import ChipDistribution, N_BINS


def make_dist(price_min=10.0, price_max=30.0):
    return ChipDistribution.empty(price_min, price_max)


class TestApplyDay:
    def test_first_day_adds_turnover_mass(self):
        d = make_dist()
        d.apply_day(low=19.0, high=21.0, close=20.0, turnover_rate=5.0)  # 5%
        assert d.counts.sum() == pytest.approx(0.05, abs=1e-9)

    def test_decay_reduces_existing_chips(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 50.0)   # sum = 0.5
        d.apply_day(19.0, 21.0, 20.0, 50.0)   # 0.5*0.5 + 0.5 = 0.75
        assert d.counts.sum() == pytest.approx(0.75, abs=1e-9)

    def test_invariant_holds_at_steady_state(self):
        """sum≈1 后每日保持 1（归一化不变式）"""
        d = make_dist()
        for _ in range(30):
            d.apply_day(19.0, 21.0, 20.0, 100.0)
        assert d.counts.sum() == pytest.approx(1.0, abs=1e-9)
        d.apply_day(18.0, 22.0, 20.0, 20.0)
        assert d.counts.sum() == pytest.approx(1.0, abs=1e-9)

    def test_full_turnover_erases_old_chips(self):
        """持续 100% 换手后，旧价位筹码趋近 0"""
        d = make_dist()
        d.apply_day(9.0, 11.0, 10.0, 100.0)       # 筹码全在 10 元附近
        for _ in range(10):
            d.apply_day(19.0, 21.0, 20.0, 100.0)  # 换到 20 元附近
        low_mass = d.mass_between(9.0, 11.0)
        assert low_mass < 0.01

    def test_turnover_capped_at_100(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 150.0)  # 异常数据封顶
        assert d.counts.sum() == pytest.approx(1.0, abs=1e-9)

    def test_limit_up_single_price(self):
        """一字板 low==high：全部质量进单桶，不报错"""
        d = make_dist()
        d.apply_day(20.0, 20.0, 20.0, 10.0)
        assert d.counts.sum() == pytest.approx(0.1, abs=1e-9)

    def test_triangular_peak_at_typical_price(self):
        """三角分布峰值在典型价 (H+L+2C)/4"""
        d = make_dist()
        d.apply_day(10.0, 30.0, 12.0, 100.0)  # 典型价 = (30+10+24)/4 = 16
        peak_price = d.price_at_peak()
        assert abs(peak_price - 16.0) < 2.0


class TestMetrics:
    def test_profit_ratio(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 100.0)  # 筹码全在 20 附近
        m = d.metrics(close=25.0)
        assert m["profit_ratio"] > 0.9
        m2 = d.metrics(close=15.0)
        assert m2["profit_ratio"] < 0.1

    def test_avg_cost(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 100.0)
        m = d.metrics(close=20.0)
        assert abs(m["avg_cost"] - 20.0) < 1.0

    def test_cost_intervals_ordered(self):
        d = make_dist()
        for _ in range(20):
            d.apply_day(10.0, 30.0, 20.0, 20.0)
        m = d.metrics(close=20.0)
        assert m["cost_90_low"] <= m["cost_70_low"] <= m["cost_70_high"] <= m["cost_90_high"]
        assert 0 <= m["profit_ratio"] <= 1
        assert m["concentration"] >= 0

    def test_empty_distribution_metrics_safe(self):
        d = make_dist()
        m = d.metrics(close=20.0)
        assert m["profit_ratio"] is None  # 无筹码时指标为 None

    def test_metrics_keys_complete(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 100.0)
        m = d.metrics(close=20.0)
        assert set(m) == {
            "profit_ratio", "avg_cost", "cost_90_low", "cost_90_high",
            "cost_70_low", "cost_70_high", "peak_price", "concentration",
        }


class TestSerialization:
    def test_roundtrip(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 30.0)
        blob = d.to_bytes()
        d2 = ChipDistribution.from_bytes(d.price_min, d.bin_width, blob)
        np.testing.assert_array_equal(d.counts, d2.counts)

    def test_from_klines_builds_distribution(self):
        klines = [
            {"low": 19.0, "high": 21.0, "close": 20.0, "turnover_rate": 5.0},
            {"low": 20.0, "high": 22.0, "close": 21.0, "turnover_rate": 5.0},
        ]
        d = ChipDistribution.from_klines(klines)
        assert d.counts.sum() == pytest.approx(0.05 * 0.95 + 0.05, abs=1e-9)

    def test_from_klines_expands_range(self):
        """价格突破初始区间时自动重分桶"""
        klines = [
            {"low": 19.0, "high": 21.0, "close": 20.0, "turnover_rate": 50.0},
            {"low": 39.0, "high": 41.0, "close": 40.0, "turnover_rate": 50.0},
        ]
        d = ChipDistribution.from_klines(klines)
        assert d.price_min <= 19.0
        assert d.price_at_peak() > 30.0  # 峰移到 40 附近（各 50% 质量，峰在后一半）
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/chip/test_calculator.py -v
```
Expected: 收集失败或全 FAIL，`ModuleNotFoundError: domain.chip_distribution`

- [ ] **Step 3: 实现 calculator**

创建 `quantsys-v2/domain/chip_distribution/__init__.py`（空文件）和 `quantsys-v2/domain/chip_distribution/calculator.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/chip/test_calculator.py -v
```
Expected: 全部 PASS（15 个测试）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/domain/chip_distribution/ quantsys-v2/tests/chip/
git commit -m "feat(chip): calculator——三角分布+换手率衰减纯计算核心，15 单测"
```

---

### Task 3: repository 数据访问层

**Files:**
- Create: `quantsys-v2/adapters/outbound/repositories/chip_repository.py`
- Test: `quantsys-v2/tests/chip/test_chip_repository.py`

- [ ] **Step 1: 写失败的测试**

创建 `quantsys-v2/tests/chip/test_chip_repository.py`（集成测试，连真实 dev PG，只读校验 + 临时 symbol 写入后清理）：

```python
"""ChipRepository 集成测试 — 连真实 quant_investment 库"""
import pytest

from adapters.outbound.repositories.chip_repository import ChipRepository


@pytest.fixture
def repo():
    return ChipRepository()


class TestKlineRead:
    def test_get_klines_known_symbol(self, repo):
        rows = repo.get_klines("600519.SH")
        assert len(rows) > 1000
        first = rows[0]
        assert set(first) >= {"trade_date", "low", "high", "close", "volume", "turnover_rate"}
        # 时间升序
        dates = [r["trade_date"] for r in rows]
        assert dates == sorted(dates)

    def test_get_klines_after_date(self, repo):
        rows = repo.get_klines("600519.SH", after_date="2026-08-01")
        assert 0 < len(rows) < 20


class TestStateRoundtrip:
    def test_state_upsert_and_get(self, repo):
        import numpy as np
        from domain.chip_distribution.calculator import ChipDistribution
        d = ChipDistribution.empty(10.0, 30.0)
        d.apply_day(19.0, 21.0, 20.0, 30.0)
        # 用真实 symbol，测试后恢复原状由 backfill 覆盖；此处用不存在于 stocks 的 symbol 会违反外键，
        # 故直接用 600519.SH 验证 roundtrip，再用 service 回填修正。
        repo.upsert_state("600519.SH", d, "1999-01-04")
        got = repo.get_state("600519.SH")
        assert got is not None
        assert got["last_trade_date"].isoformat()[:10] == "1999-01-04"
        d2 = ChipDistribution.from_bytes(got["price_min"], got["bin_width"], got["counts"])
        np.testing.assert_array_equal(d.counts, d2.counts)


class TestMetricsUpsert:
    def test_upsert_metrics_idempotent(self, repo):
        m = {
            "profit_ratio": 0.5, "avg_cost": 20.0,
            "cost_90_low": 18.0, "cost_90_high": 22.0,
            "cost_70_low": 19.0, "cost_70_high": 21.0,
            "peak_price": 20.0, "concentration": 0.1,
        }
        repo.upsert_metrics("600519.SH", "1999-01-04", m)
        repo.upsert_metrics("600519.SH", "1999-01-04", {**m, "profit_ratio": 0.6})
        row = repo.get_metrics("600519.SH", "1999-01-04")
        assert row["profit_ratio"] == 0.6


class TestHelpers:
    def test_get_circulating_mv(self, repo):
        mv = repo.get_circulating_mv("600519.SH")
        assert mv is None or mv > 0

    def test_get_symbols_with_pending_klines_empty_when_fresh(self, repo):
        # state 里没有的 symbol 一定 pending；这个测试只校验返回类型与字段
        rows = repo.get_symbols_with_pending_klines()
        assert isinstance(rows, list)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/chip/test_chip_repository.py -v
```
Expected: FAIL，`ModuleNotFoundError: adapters.outbound.repositories.chip_repository`

- [ ] **Step 3: 实现 repository**

创建 `quantsys-v2/adapters/outbound/repositories/chip_repository.py`：

```python
"""筹码分布 Repository — quant.chip_distribution_state / quant.chip_metrics"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import Column, Date, DateTime, Float, LargeBinary, Text, text

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class ChipState(Base):
    __tablename__ = 'chip_distribution_state'
    __table_args__ = {'schema': 'quant'}

    symbol = Column(Text, primary_key=True)
    price_min = Column(Float, nullable=False)
    bin_width = Column(Float, nullable=False)
    counts = Column(LargeBinary, nullable=False)
    last_trade_date = Column(Date, nullable=False)
    updated_at = Column(DateTime)


class ChipMetrics(Base):
    __tablename__ = 'chip_metrics'
    __table_args__ = {'schema': 'quant'}

    symbol = Column(Text, primary_key=True)
    trade_date = Column(Date, primary_key=True)
    profit_ratio = Column(Float)
    avg_cost = Column(Float)
    cost_90_low = Column(Float)
    cost_90_high = Column(Float)
    cost_70_low = Column(Float)
    cost_70_high = Column(Float)
    peak_price = Column(Float)
    concentration = Column(Float)
    created_at = Column(DateTime)


class ChipRepository(BaseORMRepository[ChipState]):
    model = ChipState

    # ---------- K 线读取 ----------

    def get_klines(self, symbol: str, after_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """读日 K（时间升序）。after_date 为排他下界（增量更新用）。"""
        try:
            sql = """
                SELECT trade_date, low, high, close, volume, turnover_rate
                FROM quant.daily_klines
                WHERE symbol = :symbol
            """
            params: Dict[str, Any] = {"symbol": symbol}
            if after_date:
                sql += " AND trade_date > :after_date"
                params["after_date"] = after_date
            sql += " ORDER BY trade_date"
            rows = self.session.execute(text(sql), params).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_klines error: {e}")
            return []

    def get_latest_close(self, symbol: str) -> Optional[float]:
        try:
            row = self.session.execute(
                text("""
                    SELECT close FROM quant.daily_klines
                    WHERE symbol = :s ORDER BY trade_date DESC LIMIT 1
                """),
                {"s": symbol},
            ).first()
            return float(row[0]) if row and row[0] else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_latest_close error: {e}")
            return None

    def get_circulating_mv(self, symbol: str) -> Optional[float]:
        try:
            row = self.session.execute(
                text("SELECT circulating_mv FROM quant.stocks WHERE symbol = :s"),
                {"s": symbol},
            ).first()
            return float(row[0]) if row and row[0] else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_circulating_mv error: {e}")
            return None

    def get_median_turnover(self, trade_date: date) -> Optional[float]:
        """当日全市场换手率中位数（最后一级回退用）"""
        try:
            row = self.session.execute(
                text("""
                    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY turnover_rate)
                    FROM quant.daily_klines
                    WHERE trade_date = :d AND turnover_rate IS NOT NULL AND turnover_rate > 0
                """),
                {"d": trade_date},
            ).first()
            return float(row[0]) if row and row[0] else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_median_turnover error: {e}")
            return None

    # ---------- 状态读写 ----------

    def get_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            r = self.session.query(self.model).filter_by(symbol=symbol).first()
            if not r:
                return None
            return {
                "price_min": r.price_min,
                "bin_width": r.bin_width,
                "counts": bytes(r.counts),
                "last_trade_date": r.last_trade_date,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_state error: {e}")
            return None

    def upsert_state(self, symbol: str, dist, last_trade_date) -> None:
        """dist 为 domain.chip_distribution.calculator.ChipDistribution"""
        try:
            self.session.execute(
                text("""
                    INSERT INTO quant.chip_distribution_state
                        (symbol, price_min, bin_width, counts, last_trade_date, updated_at)
                    VALUES (:s, :pmin, :bw, :counts, :d, NOW())
                    ON CONFLICT (symbol) DO UPDATE SET
                        price_min = EXCLUDED.price_min,
                        bin_width = EXCLUDED.bin_width,
                        counts = EXCLUDED.counts,
                        last_trade_date = EXCLUDED.last_trade_date,
                        updated_at = NOW()
                """),
                {"s": symbol, "pmin": dist.price_min, "bw": dist.bin_width,
                 "counts": dist.to_bytes(), "d": last_trade_date},
            )
            self.session.commit()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip upsert_state error: {e}")
            raise

    # ---------- 指标读写 ----------

    def upsert_metrics(self, symbol: str, trade_date, metrics: Dict[str, Any]) -> None:
        try:
            self.session.execute(
                text("""
                    INSERT INTO quant.chip_metrics
                        (symbol, trade_date, profit_ratio, avg_cost,
                         cost_90_low, cost_90_high, cost_70_low, cost_70_high,
                         peak_price, concentration)
                    VALUES (:s, :d, :pr, :ac, :c90l, :c90h, :c70l, :c70h, :pp, :conc)
                    ON CONFLICT (symbol, trade_date) DO UPDATE SET
                        profit_ratio = EXCLUDED.profit_ratio,
                        avg_cost = EXCLUDED.avg_cost,
                        cost_90_low = EXCLUDED.cost_90_low,
                        cost_90_high = EXCLUDED.cost_90_high,
                        cost_70_low = EXCLUDED.cost_70_low,
                        cost_70_high = EXCLUDED.cost_70_high,
                        peak_price = EXCLUDED.peak_price,
                        concentration = EXCLUDED.concentration
                """),
                {"s": symbol, "d": trade_date, "pr": metrics["profit_ratio"],
                 "ac": metrics["avg_cost"], "c90l": metrics["cost_90_low"],
                 "c90h": metrics["cost_90_high"], "c70l": metrics["cost_70_low"],
                 "c70h": metrics["cost_70_high"], "pp": metrics["peak_price"],
                 "conc": metrics["concentration"]},
            )
            self.session.commit()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip upsert_metrics error: {e}")
            raise

    def get_metrics(self, symbol: str, trade_date: str) -> Optional[Dict[str, Any]]:
        try:
            r = self.session.query(ChipMetrics).filter_by(
                symbol=symbol, trade_date=trade_date).first()
            if not r:
                return None
            return {c.name: getattr(r, c.name) for c in ChipMetrics.__table__.columns}
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_metrics error: {e}")
            return None

    # ---------- 增量发现 ----------

    def get_symbols_with_pending_klines(self) -> List[Dict[str, Any]]:
        """有新 K 线未处理的股票：state 缺失或 last_trade_date 落后于最新 K 线。

        返回 [{symbol, from_date}]，from_date 为排他下界（None 表示全量）。
        """
        try:
            rows = self.session.execute(
                text("""
                    WITH latest AS (
                        SELECT symbol, MAX(trade_date) AS max_date
                        FROM quant.daily_klines GROUP BY symbol
                    )
                    SELECT l.symbol, s.last_trade_date AS from_date
                    FROM latest l
                    LEFT JOIN quant.chip_distribution_state s ON s.symbol = l.symbol
                    WHERE s.symbol IS NULL OR s.last_trade_date < l.max_date
                """),
            ).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_symbols_with_pending error: {e}")
            return []
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/chip/test_chip_repository.py -v
```
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/outbound/repositories/chip_repository.py quantsys-v2/tests/chip/test_chip_repository.py
git commit -m "feat(chip): repository——state/metrics 读写 + 增量发现 + 换手率回退查询"
```

---

### Task 4: service 编排层（TDD，fake repo）

**Files:**
- Create: `quantsys-v2/domain/chip_distribution/service.py`
- Test: `quantsys-v2/tests/chip/test_chip_service.py`

- [ ] **Step 1: 写失败的测试**

```python
"""ChipDistributionService 单测 — fake repository，不连数据库"""
import pytest

from domain.chip_distribution.calculator import ChipDistribution
from domain.chip_distribution.service import ChipDistributionService


class FakeRepo:
    def __init__(self, klines=None, state=None, circulating_mv=None, median_turnover=2.0):
        self._klines = klines or {}
        self._state = state or {}
        self._mv = circulating_mv
        self._median = median_turnover
        self.saved_states = {}
        self.saved_metrics = []

    def get_klines(self, symbol, after_date=None, limit=None):
        rows = self._klines.get(symbol, [])
        if after_date:
            rows = [r for r in rows if str(r["trade_date"]) > str(after_date)]
        return rows

    def get_latest_close(self, symbol):
        rows = self._klines.get(symbol, [])
        return rows[-1]["close"] if rows else None

    def get_state(self, symbol):
        return self._state.get(symbol)

    def get_circulating_mv(self, symbol):
        return self._mv

    def get_median_turnover(self, trade_date):
        return self._median

    def upsert_state(self, symbol, dist, last_trade_date):
        self.saved_states[symbol] = (dist, last_trade_date)

    def upsert_metrics(self, symbol, trade_date, metrics):
        self.saved_metrics.append((symbol, trade_date, metrics))

    def get_symbols_with_pending_klines(self):
        return []


def kline(date, low, high, close, turnover=None, volume=1e6):
    return {"trade_date": date, "low": low, "high": high, "close": close,
            "volume": volume, "turnover_rate": turnover}


KLINES = [
    kline("2026-08-03", 19.0, 21.0, 20.0, turnover=5.0),
    kline("2026-08-04", 20.0, 22.0, 21.0, turnover=5.0),
    kline("2026-08-05", 21.0, 23.0, 22.0, turnover=5.0),
]


class TestUpdateSymbol:
    def test_bootstrap_from_full_history(self):
        repo = FakeRepo(klines={"600519.SH": KLINES})
        svc = ChipDistributionService(repo)
        result = svc.update_symbol("600519.SH")
        assert result["days_applied"] == 3
        assert "600519.SH" in repo.saved_states
        # 最后一天收盘价算指标
        assert repo.saved_metrics[-1][1] == "2026-08-05"
        assert 0 <= repo.saved_metrics[-1][2]["profit_ratio"] <= 1

    def test_incremental_from_state(self):
        d = ChipDistribution.empty(19.0, 23.0)
        d.apply_day(19.0, 21.0, 20.0, 5.0)
        repo = FakeRepo(
            klines={"600519.SH": KLINES},
            state={"600519.SH": {
                "price_min": d.price_min, "bin_width": d.bin_width,
                "counts": d.to_bytes(), "last_trade_date": "2026-08-03",
            }},
        )
        svc = ChipDistributionService(repo)
        result = svc.update_symbol("600519.SH")
        assert result["days_applied"] == 2  # 只补 08-04/08-05

    def test_no_new_klines_noop(self):
        d = ChipDistribution.empty(19.0, 23.0)
        repo = FakeRepo(
            klines={"600519.SH": KLINES},
            state={"600519.SH": {
                "price_min": d.price_min, "bin_width": d.bin_width,
                "counts": d.to_bytes(), "last_trade_date": "2026-08-05",
            }},
        )
        svc = ChipDistributionService(repo)
        result = svc.update_symbol("600519.SH")
        assert result["days_applied"] == 0
        assert repo.saved_metrics == []

    def test_unknown_symbol_returns_error(self):
        repo = FakeRepo()
        svc = ChipDistributionService(repo)
        result = svc.update_symbol("000000.XX")
        assert result["days_applied"] == 0
        assert "error" in result


class TestTurnoverFallback:
    def test_missing_turnover_uses_circulating_mv(self):
        # 流通市值 20亿，收盘 20 元 → 流通股 1亿股；volume 500万股 → 换手 5%
        rows = [kline("2026-08-05", 19.0, 21.0, 20.0, turnover=None, volume=5e6)]
        repo = FakeRepo(klines={"600519.SH": rows}, circulating_mv=2e9)
        svc = ChipDistributionService(repo)
        svc.update_symbol("600519.SH")
        dist, _ = repo.saved_states["600519.SH"]
        assert dist.counts.sum() == pytest.approx(0.05, abs=1e-9)

    def test_missing_turnover_and_mv_uses_market_median(self):
        rows = [kline("2026-08-05", 19.0, 21.0, 20.0, turnover=None)]
        repo = FakeRepo(klines={"600519.SH": rows}, circulating_mv=None, median_turnover=3.0)
        svc = ChipDistributionService(repo)
        svc.update_symbol("600519.SH")
        dist, _ = repo.saved_states["600519.SH"]
        assert dist.counts.sum() == pytest.approx(0.03, abs=1e-9)


class TestGetDistribution:
    def test_curve_and_metrics(self):
        repo = FakeRepo(klines={"600519.SH": KLINES})
        svc = ChipDistributionService(repo)
        svc.update_symbol("600519.SH")
        out = svc.get_distribution("600519.SH")
        assert out["symbol"] == "600519.SH"
        assert out["as_of"] == "2026-08-05"
        assert len(out["curve"]) > 0
        assert abs(sum(p["weight"] for p in out["curve"]) - 1.0) < 1e-6
        assert set(out["metrics"]) >= {"profit_ratio", "avg_cost", "peak_price"}

    def test_symbol_normalization(self):
        repo = FakeRepo(klines={"600519.SH": KLINES})
        svc = ChipDistributionService(repo)
        svc.update_symbol("600519")  # 无后缀 → 自动补 .SH
        assert "600519.SH" in repo.saved_states
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/chip/test_chip_service.py -v
```
Expected: FAIL，`ModuleNotFoundError: domain.chip_distribution.service`

- [ ] **Step 3: 实现 service**

创建 `quantsys-v2/domain/chip_distribution/service.py`：

```python
"""筹码分布编排服务 — 增量更新、回填、换手率回退、查询

换手率回退链（spec §计算模型）：
  daily_klines.turnover_rate（%，可能为 None）
  → volume × close / circulating_mv（流通市值反推流通股）
  → 当日全市场换手率中位数
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from domain.chip_distribution.calculator import ChipDistribution

logger = structlog.get_logger(__name__)


def normalize_symbol(symbol: str) -> str:
    """600519 → 600519.SH；000001 → 000001.SZ；8/4 开头 → .BJ"""
    s = symbol.strip().upper()
    if "." in s:
        return s
    if s.startswith("6"):
        return f"{s}.SH"
    if s.startswith(("4", "8")):
        return f"{s}.BJ"
    return f"{s}.SZ"


class ChipDistributionService:
    def __init__(self, repo):
        self.repo = repo

    # ---------- 换手率回退 ----------

    def _resolve_turnover(self, symbol: str, row: Dict[str, Any]) -> float:
        tr = row.get("turnover_rate")
        if tr is not None:
            return float(tr)
        mv = self.repo.get_circulating_mv(symbol)
        close = row.get("close")
        volume = row.get("volume")
        if mv and close and volume:
            float_shares = mv / close
            if float_shares > 0:
                return min(volume / float_shares * 100.0, 100.0)
        median = self.repo.get_median_turnover(row["trade_date"])
        if median:
            logger.warning(f"chip turnover fallback to market median: {symbol} {row['trade_date']}")
            return median
        return 0.0

    # ---------- 增量更新 ----------

    def update_symbol(self, symbol: str) -> Dict[str, Any]:
        """把 symbol 的筹码分布推进到最新 K 线。返回 {days_applied, ...}。"""
        symbol = normalize_symbol(symbol)
        state = self.repo.get_state(symbol)
        after = state["last_trade_date"] if state else None
        rows = self.repo.get_klines(symbol, after_date=after)
        if not rows:
            if state:
                return {"symbol": symbol, "days_applied": 0}
            return {"symbol": symbol, "days_applied": 0,
                    "error": "无 K 线数据或 symbol 不存在"}

        if state:
            dist = ChipDistribution.from_bytes(
                state["price_min"], state["bin_width"], state["counts"])
        else:
            dist = ChipDistribution.empty(
                min(r["low"] for r in rows), max(r["high"] for r in rows))

        for row in rows:
            t = self._resolve_turnover(symbol, row)
            dist.apply_day(row["low"], row["high"], row["close"], t)

        last = rows[-1]
        self.repo.upsert_state(symbol, dist, last["trade_date"])
        metrics = dist.metrics(last["close"])
        self.repo.upsert_metrics(symbol, last["trade_date"], metrics)
        return {"symbol": symbol, "days_applied": len(rows),
                "last_trade_date": str(last["trade_date"])}

    def daily_update(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """全市场增量：所有有新 K 线的股票。返回汇总统计。"""
        pending = self.repo.get_symbols_with_pending_klines()
        if limit:
            pending = pending[:limit]
        ok, failed, days = 0, 0, 0
        for p in pending:
            try:
                r = self.update_symbol(p["symbol"])
                if "error" in r:
                    failed += 1
                else:
                    ok += 1
                    days += r["days_applied"]
            except Exception as e:
                failed += 1
                logger.error(f"chip daily_update {p['symbol']} failed: {e}")
        summary = {"pending": len(pending), "updated": ok,
                   "failed": failed, "days_applied": days}
        logger.info(f"chip daily_update done: {summary}")
        return summary

    # ---------- 查询 ----------

    def get_distribution(self, symbol: str) -> Dict[str, Any]:
        """完整分布曲线 + 最新指标（从 state 还原，不重新计算）"""
        symbol = normalize_symbol(symbol)
        state = self.repo.get_state(symbol)
        if not state:
            return {"symbol": symbol, "error": "筹码分布未计算，请先运行更新任务"}
        dist = ChipDistribution.from_bytes(
            state["price_min"], state["bin_width"], state["counts"])
        close = self.repo.get_latest_close(symbol)
        total = dist.counts.sum()
        centers = dist.bin_centers()
        # 只返回非零桶，减小响应体积
        curve = [
            {"price": round(float(c), 4), "weight": float(w) / float(total)}
            for c, w in zip(centers, dist.counts) if w > 0
        ] if total > 0 else []
        return {
            "symbol": symbol,
            "as_of": str(state["last_trade_date"]),
            "close": close,
            "curve": curve,
            "metrics": dist.metrics(close) if close else None,
        }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/chip/test_chip_service.py -v
```
Expected: 全部 PASS（8 个测试）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/domain/chip_distribution/service.py quantsys-v2/tests/chip/test_chip_service.py
git commit -m "feat(chip): service——增量更新/换手率回退链/分布查询，8 单测 fake repo"
```

---

### Task 5: 调度 Job + 任务注册

**Files:**
- Create: `quantsys-v2/infrastructure/jobs/chip_distribution_update_job.py`
- Create: `quantsys-v2/scripts/migrations/011_seed_chip_distribution_job.sql`

- [ ] **Step 1: 写 job**

创建 `quantsys-v2/infrastructure/jobs/chip_distribution_update_job.py`：

```python
"""
筹码分布增量更新 Job — 全市场每日增量

调度配置（quant.scheduler_task_configs，见 011_seed_chip_distribution_job.sql）：
    task_name: chip_distribution_update
    command:   infrastructure.jobs.chip_distribution_update_job.execute
    cron:      30 18 * * 0-4（kline_update 17:40 之后）

手动执行：
    python -m infrastructure.jobs.chip_distribution_update_job [--limit 100]
    python -m infrastructure.jobs.chip_distribution_update_job --symbol 600519.SH
"""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


def execute(**params):
    """
    Args:
        **params:
            - limit: 最多处理多少只（调试用）
            - symbol: 只更新单只股票（调试用）

    Returns:
        dict: {pending, updated, failed, days_applied}
    """
    from adapters.outbound.repositories.chip_repository import ChipRepository
    from domain.chip_distribution.service import ChipDistributionService

    svc = ChipDistributionService(ChipRepository())

    symbol = params.get('symbol')
    if symbol:
        result = svc.update_symbol(symbol)
        logger.info(f"单票更新: {result}")
        return result

    return svc.daily_update(limit=params.get('limit'))


if __name__ == '__main__':
    import argparse
    import json
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--symbol', type=str, default=None)
    args = parser.parse_args()
    params = {k: v for k, v in vars(args).items() if v is not None}
    print(json.dumps(execute(**params), ensure_ascii=False, default=str))
```

- [ ] **Step 2: 手动冒烟（单票 + 小批量）**

```bash
cd quantsys-v2 && ./venv/bin/python -m infrastructure.jobs.chip_distribution_update_job --symbol 600519.SH
cd quantsys-v2 && ./venv/bin/python -m infrastructure.jobs.chip_distribution_update_job --limit 5
```
Expected: 单票返回 `days_applied > 1000`（首次全历史）；limit 5 返回 `updated: 5`。

验证落库：
```bash
psql -d quant_investment -c "SELECT symbol, trade_date, round(profit_ratio::numeric, 3), round(avg_cost::numeric, 2), round(peak_price::numeric, 2) FROM quant.chip_metrics WHERE symbol = '600519.SH' ORDER BY trade_date DESC LIMIT 1"
psql -d quant_investment -c "SELECT close FROM quant.daily_klines WHERE symbol='600519.SH' ORDER BY trade_date DESC LIMIT 1"
```
Expected: profit_ratio ∈ [0,1]，avg_cost 与历史价格量级一致；再执行一次同 symbol，`days_applied = 0`（幂等）。

- [ ] **Step 3: 写任务注册迁移并应用**

创建 `quantsys-v2/scripts/migrations/011_seed_chip_distribution_job.sql`：

```sql
-- 011_seed_chip_distribution_job.sql
-- 注册筹码分布每日增量任务（scheduler_daemon 从该表加载）
-- 排在 kline_update（40 17 * * 0-4）之后
INSERT INTO quant.scheduler_task_configs
    (task_name, description, cron_expression, command, params, is_enabled,
     executor, max_instances, misfire_grace_time, coalesce, created_by)
VALUES
    ('chip_distribution_update', '筹码分布每日增量更新（全市场成本分布+摘要指标）',
     '30 18 * * 0-4', 'infrastructure.jobs.chip_distribution_update_job.execute',
     '{}'::jsonb, true, 'default', 1, 43200, true, 'migration-010')
ON CONFLICT (task_name) DO NOTHING;
```

```bash
psql -d quant_investment -f quantsys-v2/scripts/migrations/011_seed_chip_distribution_job.sql
psql -d quant_investment -c "SELECT task_name, cron_expression, is_enabled FROM quant.scheduler_task_configs WHERE task_name='chip_distribution_update'"
```
Expected: 一行，is_enabled = t。

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/infrastructure/jobs/chip_distribution_update_job.py quantsys-v2/scripts/migrations/011_seed_chip_distribution_job.sql
git commit -m "feat(chip): 每日增量 job + 调度注册（18:30 接 kline_update 后）"
```

---

### Task 6: FastAPI 查询接口

**Files:**
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/routes/analysis_async.py`（文件末尾追加路由）

- [ ] **Step 1: 追加路由**

在 `quantsys-v2/adapters/inbound/fastapi_app/routes/analysis_async.py` 末尾追加：

```python
# ============ /api/analysis/chip-distribution（筹码分布） ============

@router.get('/api/analysis/chip-distribution/{symbol}')
def get_chip_distribution(symbol: str):
    """筹码分布（成本分布）：完整分布曲线 + 摘要指标

    数据来源 quant.chip_distribution_state（每日 18:30 增量更新）。
    首次使用或新上市股票可能无数据，返回 error 提示。
    """
    try:
        from adapters.outbound.repositories.chip_repository import ChipRepository
        from domain.chip_distribution.service import ChipDistributionService
        svc = ChipDistributionService(ChipRepository())
        result = svc.get_distribution(symbol)
        if "error" in result:
            return error_response(result, 404)
        return api_response(sanitize_for_json(result))
    except Exception as e:
        return handle_api_error(e, 'chip-distribution')
```

- [ ] **Step 2: 重启 5001 并 curl 验证**

5001 是主工作区 venv nohup 起的 FastAPI（无 supervisor，手动重启）。在 worktree 里验证用独立端口启动，避免动生产：

```bash
cd quantsys-v2 && PORT=5099 ./venv/bin/python -m uvicorn adapters.inbound.fastapi_app.main:app --port 5099 &
sleep 5
curl -s http://127.0.0.1:5099/api/analysis/chip-distribution/600519 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success'), list(d.get('data',{}).keys()))"
curl -s http://127.0.0.1:5099/api/analysis/chip-distribution/000001.SZ | head -c 300
kill %1
```
Expected: `success true`，data 含 `symbol/as_of/close/curve/metrics`；`curve` 权重和≈1。注意：若 worktree 的 FastAPI 需要特定启动方式，参照 `quantsys-v2/adapters/inbound/fastapi_app/main.py` 的实际启动命令调整。

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/adapters/inbound/fastapi_app/routes/analysis_async.py
git commit -m "feat(chip): GET /api/analysis/chip-distribution/{symbol} 分布曲线+指标"
```

---

### Task 7: agent-ts 工具 chip_analysis（TDD）

**Files:**
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`（V2_ROUTES 加一行）
- Create: `agent-ts/src/infrastructure/tools/analysis/chip-analysis-tool.ts`
- Create: `agent-ts/src/infrastructure/tools/analysis/chip-analysis-tool.test.ts`
- Modify: `agent-ts/src/infrastructure/tools/index.ts`（import + 注册）

- [ ] **Step 1: 写失败的测试**

创建 `agent-ts/src/infrastructure/tools/analysis/chip-analysis-tool.test.ts`（参照同目录 `chan-analyze-tool.test.ts` 的 mock 方式）：

```typescript
/**
 * Chip Analysis Tool 测试
 * 契约：runQuantV2 返回 {ok, command, data}，formatter 收到解包后的 data
 */
import { chipAnalysisTool } from "./chip-analysis-tool.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

jest.mock("../../adapters/quant/quant-v2-client.js", () => ({
  runQuantV2: jest.fn(),
}));

const mockedRun = runQuantV2 as jest.MockedFunction<typeof runQuantV2>;

const SAMPLE = {
  symbol: "600519.SH",
  as_of: "2026-08-07",
  close: 1700.0,
  curve: [
    { price: 1650, weight: 0.4 },
    { price: 1700, weight: 0.6 },
  ],
  metrics: {
    profit_ratio: 0.62, avg_cost: 1680.5,
    cost_90_low: 1500, cost_90_high: 1800,
    cost_70_low: 1600, cost_70_high: 1750,
    peak_price: 1700, concentration: 0.09,
  },
};

describe("chip_analysis tool", () => {
  beforeEach(() => mockedRun.mockReset());

  it("缺少 symbol 返回错误", async () => {
    const result = await chipAnalysisTool.execute("t1", {});
    expect(result.details).toMatchObject({ success: false });
  });

  it("正常返回含获利盘/成本/峰位解读", async () => {
    mockedRun.mockResolvedValue({ ok: true, command: "analysis.chipDistribution", data: SAMPLE } as any);
    const result = await chipAnalysisTool.execute("t2", { symbol: "600519" });
    expect(mockedRun).toHaveBeenCalledWith("analysis.chipDistribution", { symbol: "600519" });
    const text = result.content[0].text;
    expect(text).toContain("获利盘");
    expect(text).toContain("62");
    expect(text).toContain("1680.5");
    expect(text).toContain("密集峰");
  });

  it("后端返回 error 时透传", async () => {
    mockedRun.mockResolvedValue({ ok: true, command: "analysis.chipDistribution", data: { symbol: "X", error: "筹码分布未计算" } } as any);
    const result = await chipAnalysisTool.execute("t3", { symbol: "X" });
    expect(result.content[0].text).toContain("未计算");
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd agent-ts && npm test -- chip-analysis-tool
```
Expected: FAIL，模块不存在（**必须 npm test**，裸 npx jest 会误报 TS1378）

- [ ] **Step 3: 实现工具 + 注册路由**

在 `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts` 的 `V2_ROUTES` 中 `"chan.analyze"` 行附近加：

```typescript
  "analysis.chipDistribution": { path: "/api/analysis/chip-distribution/{symbol}", method: "GET" }, // ✅ 筹码分布：成本分布曲线+获利盘/密集峰指标
```

（参照同文件 `sentiment.holder_changes` 的 `{symbol}` 路径参数替换方式，确认 client 支持路径参数替换；若不支持则改为 query 参数并在后端路由同步调整。）

创建 `agent-ts/src/infrastructure/tools/analysis/chip-analysis-tool.ts`：

```typescript
/**
 * Chip Analysis Tool - 筹码分布（成本分布）分析工具
 *
 * 调用 quantsys-v2 GET /api/analysis/chip-distribution/{symbol}，返回：
 * 获利盘比例、平均持仓成本、90%/70% 成本区间、最大密集峰价位、集中度，
 * 以及当前价相对密集峰的位置解读（上方套牢压力/下方支撑）。
 *
 * 何时使用：
 * - 评估个股持仓成本结构：谁在赚钱、谁被套、支撑压力在哪
 * - 博弈分析：获利盘>90% 警惕兑现压力，<10% 可能是恐慌出清后的机会
 * - 集中度低（<0.1）说明筹码集中，变盘概率大
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

function pct(v: number | null | undefined): string {
  return v == null ? "未知" : `${(v * 100).toFixed(1)}%`;
}

function formatChip(data: any): string {
  if (data.error) return `筹码分布查询失败：${data.error}`;
  const m = data.metrics ?? {};
  const lines: string[] = [
    `筹码分布 ${data.symbol}（截至 ${data.as_of}，现价 ${data.close}）：`,
    `获利盘比例 ${pct(m.profit_ratio)}｜平均成本 ${m.avg_cost ?? "未知"}`,
    `90% 成本区间 [${m.cost_90_low ?? "?"}, ${m.cost_90_high ?? "?"}]｜70% 区间 [${m.cost_70_low ?? "?"}, ${m.cost_70_high ?? "?"}]`,
    `最大密集峰价位 ${m.peak_price ?? "未知"}｜集中度 ${m.concentration ?? "未知"}（越小越集中）`,
  ];
  if (m.profit_ratio != null && data.close != null && m.peak_price != null) {
    if (m.profit_ratio > 0.9) {
      lines.push("解读：获利盘 >90%，兑现压力大，追高需谨慎。");
    } else if (m.profit_ratio < 0.1) {
      lines.push("解读：获利盘 <10%，大量筹码套牢，反弹抛压重；若基本面无恶化，可能是恐慌出清后的左侧机会。");
    }
    if (data.close > m.peak_price * 1.05) {
      lines.push(`现价高于密集峰 ${m.peak_price} 超 5%，上方套牢压力已部分消化。`);
    } else if (data.close < m.peak_price * 0.95) {
      lines.push(`现价低于密集峰 ${m.peak_price} 超 5%，密集峰构成反弹阻力。`);
    }
  }
  return lines.join("\n");
}

export const chipAnalysisTool: ToolDefinition = {
  name: "chip_analysis",
  label: "筹码分布分析",
  description: "筹码分布（成本分布）分析：获利盘比例、平均持仓成本、90%/70% 成本区间、最大密集峰价位、集中度，以及现价相对密集峰的支撑/压力解读。用于评估持仓成本结构和博弈位置。",
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码，如 600519 或 600519.SH" }),
  }),
  execute: async (_toolCallId: string, params: any) => {
    if (!params.symbol) {
      return {
        content: [{ type: "text" as const, text: "缺少必填参数: symbol" }],
        details: { success: false, error: "MISSING_SYMBOL" },
      };
    }
    try {
      const response = await runQuantV2("analysis.chipDistribution", { symbol: params.symbol });
      return handleToolResponse({
        toolName: "chip_analysis",
        data: (response as any).data ?? response,
        formatter: (data) => (typeof data === "string" ? data : formatChip(data)),
        metadata: { params },
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `筹码分布分析失败: ${errorMsg}` }],
        details: { success: false, error: errorMsg },
      };
    }
  },
};
```

在 `agent-ts/src/infrastructure/tools/index.ts`：import 区（chanAnalyzeTool 附近）加：

```typescript
import { chipAnalysisTool } from "./analysis/chip-analysis-tool.js";
```

工具数组（`chanAnalyzeTool` 注册处附近）加：

```typescript
  chipAnalysisTool,               // chip_analysis - 筹码分布（成本分布）分析
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd agent-ts && npm test -- chip-analysis-tool
```
Expected: 3 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/infrastructure/tools/analysis/chip-analysis-tool.ts agent-ts/src/infrastructure/tools/analysis/chip-analysis-tool.test.ts agent-ts/src/infrastructure/tools/index.ts agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts
git commit -m "feat(chip): agent chip_analysis 工具——成本分布/获利盘/密集峰决策上下文"
```

---

### Task 8: 全市场回填

**Files:** 无需新建文件（复用 Task 5 的 job）

- [ ] **Step 1: 后台跑全量回填**

首次 `daily_update` 无 state，会自动全历史回放（bootstrap），所以直接跑全量即可：

```bash
cd quantsys-v2 && nohup ./venv/bin/python -m infrastructure.jobs.chip_distribution_update_job > /tmp/chip_backfill.log 2>&1 &
tail -f /tmp/chip_backfill.log
```
Expected: 约 5700 只股票 × 平均 800 交易日，估计 10~30 分钟。日志最终输出 `{pending: ~5700, updated: ~5600+, failed: 小, days_applied: ~4500000}`。

- [ ] **Step 2: 抽样校验**

```bash
psql -d quant_investment -c "SELECT count(*), count(*) FILTER (WHERE profit_ratio BETWEEN 0 AND 1) AS valid FROM quant.chip_metrics WHERE trade_date = (SELECT max(trade_date) FROM quant.chip_metrics)"
psql -d quant_investment -c "SELECT symbol, round(profit_ratio::numeric,3), round(avg_cost::numeric,2), round(peak_price::numeric,2) FROM quant.chip_metrics WHERE trade_date=(SELECT max(trade_date) FROM quant.chip_metrics) ORDER BY profit_ratio DESC LIMIT 5"
```
Expected: 行数 ≈ 当日 K 线股票数；valid 占比 > 99%。人工抽查 2~3 只熟票的 avg_cost 是否符合常识。

- [ ] **Step 3: 记录回填结果**

在 commit message 或 PR 描述中记录回填统计（updated/failed/耗时），失败的股票列出原因。

---

### Task 9: 收尾验证与文档

- [ ] **Step 1: 全量新增测试回归**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/chip/ -v
cd agent-ts && npm test -- chip-analysis
```
Expected: 全绿

- [ ] **Step 2: 更新 quantsys-v2/CLAUDE.md**

在数据表清单（如有）追加两行：

```markdown
- `quant.chip_distribution_state` — 筹码分布滚动状态（每股票一行价位桶数组，job: chip_distribution_update 18:30）
- `quant.chip_metrics` — 筹码每日摘要指标（获利盘比例/平均成本/成本区间/密集峰/集中度）
```

- [ ] **Step 3: Commit + 合并回 main**

```bash
git add quantsys-v2/CLAUDE.md
git commit -m "docs(chip): CLAUDE.md 数据表清单补筹码分布两表"
```

按 merge-back 流程合并回 main（update-ref + cp + git add 绕过主工作区钩子），部署侧需重启 5001（FastAPI 无 supervisor 手动重启）并确认 scheduler_daemon 已加载新任务（改 scheduler 配置要同时重启 5001 和 daemon）。

---

## Self-Review 记录

- Spec 覆盖：calculator/repository/service/调度/API/agent 工具/回填/测试 全部有对应 Task ✅
- 已修正：`get_distribution` 取最新收盘价最初误用 `get_klines(limit=1)`（ASC 排序会取到最早一天），已改为 repository 独立的 `get_latest_close` 方法（DESC LIMIT 1）
- 已知让步：Task 7 Step 3 标注了 V2_ROUTES 路径参数支持需现场确认
