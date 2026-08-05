# Agent 行为进化 Phase 1：双侧捕获适应度与排行榜 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec `docs/superpowers/specs/2026-08-05-agent-behavior-evolution-design.md` 的 Phase 1：每日滚动 20 日双侧捕获适应度计算（up_capture − down_capture）+ 排行榜 API + agent 工具 + 注入 daily_ai_review 复盘 prompt。

**Architecture:** quantsys-v2 侧新建 `evolution_fitness` 表 + 纯函数计算核心（可单测）+ ORM 仓储 + scheduler 日任务 + FastAPI 路由；基准数据复用 `benchmark_comparison.py` 的 `fetch_benchmark_klines`/`_benchmark_daily_returns`；agent-ts 侧薄封装工具走 runQuantV2 命令映射。

**Tech Stack:** Python 3.13 / SQLAlchemy ORM / FastAPI / APScheduler 自定义 SchedulerService；TypeScript / typebox / runQuantV2。

**关键契约（先读）:**
- 收益率一律小数比率（0.0123 = 1.23%），与 `simulation_equity_snapshot.daily_return` 一致
- 大盘日分类：沪深300 日收益 ≥ +0.3% 涨日，≤ −0.3% 跌日，其余横盘剔除
- down_capture 分母为负值：账户亏得少 → 比值趋 0 或转负 → 越小越好；fitness = up_capture − down_capture 越大越好
- runQuantV2 返回 `{ok, command, data}`，工具需手动取 `.data`（见 chan-analyze-tool.ts 注释）
- agent-ts 测试必须 `npm test`（--experimental-vm-modules），禁止裸 `npx jest`
- quantsys-v2 测试用 `venv/bin/python -m pytest`

---

### Task 1: evolution_fitness 表 migration + ORM model + 仓储

**Files:**
- Create: `quantsys-v2/infrastructure/persistence/migrations/add_evolution_fitness_table.sql`
- Create: `quantsys-v2/adapters/outbound/repositories/evolution_fitness_repository.py`
- Test: `quantsys-v2/tests/repositories/test_evolution_fitness_repository.py`

- [ ] **Step 1: 写失败测试**

```python
"""EvolutionFitness ORM Repository 测试"""
import pytest
from datetime import date
from adapters.outbound.repositories.evolution_fitness_repository import (
    EvolutionFitnessORMRepository,
)


class TestEvolutionFitnessRepository:
    def test_upsert_and_leaderboard(self, pg_session):
        repo = EvolutionFitnessORMRepository(pg_session)
        repo.upsert_fitness(
            account_name='agent_virtual', window_end=date(2026, 8, 5),
            up_capture=1.2, down_capture=0.5, fitness=0.7,
            up_days=10, down_days=7, status='ok',
        )
        repo.upsert_fitness(
            account_name='v14_simulation', window_end=date(2026, 8, 5),
            up_capture=0.8, down_capture=1.5, fitness=-0.7,
            up_days=10, down_days=7, status='ok',
        )
        board = repo.get_leaderboard(window_end=date(2026, 8, 5))
        assert [r['account_name'] for r in board] == ['agent_virtual', 'v14_simulation']
        assert board[0]['fitness'] == pytest.approx(0.7)

    def test_upsert_idempotent(self, pg_session):
        repo = EvolutionFitnessORMRepository(pg_session)
        for fitness in (0.7, 0.9):
            repo.upsert_fitness(
                account_name='agent_virtual', window_end=date(2026, 8, 5),
                up_capture=1.2, down_capture=0.3, fitness=fitness,
                up_days=10, down_days=7, status='ok',
            )
        board = repo.get_leaderboard(window_end=date(2026, 8, 5))
        assert len(board) == 1
        assert board[0]['fitness'] == pytest.approx(0.9)

    def test_leaderboard_skips_non_ok_status(self, pg_session):
        repo = EvolutionFitnessORMRepository(pg_session)
        repo.upsert_fitness(
            account_name='idle_acct', window_end=date(2026, 8, 5),
            up_capture=None, down_capture=None, fitness=None,
            up_days=0, down_days=0, status='no_trades',
        )
        board = repo.get_leaderboard(window_end=date(2026, 8, 5))
        assert board == []
        # 含非 ok 状态的全量查询（API 展示用）
        all_rows = repo.get_leaderboard(window_end=date(2026, 8, 5), include_non_ok=True)
        assert all_rows[0]['status'] == 'no_trades'
```

测试用 PG 真实连接（项目 pytest 惯例连本地 quant_investment 库，schema quant）。`pg_session` fixture 参考 `tests/repositories/test_heatmap_repository.py` 现有 fixture 写法；若没有共享 fixture，在测试文件内用 `infrastructure.persistence.orm` 的 session 工厂建一个并在 teardown 删测试行（`DELETE FROM quant.evolution_fitness WHERE account_name LIKE 'agent_virtual' OR ...` 用本测试专用账户名即可）。

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_evolution_fitness_repository.py -v`
Expected: ImportError（模块不存在）

- [ ] **Step 3: migration SQL + ORM model + 仓储实现**

`add_evolution_fitness_table.sql`：

```sql
-- 双侧捕获适应度表（agent 行为进化 Phase 1，2026-08-05）
CREATE TABLE IF NOT EXISTS quant.evolution_fitness (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(50) NOT NULL,
    window_end DATE NOT NULL,
    window_days INTEGER NOT NULL DEFAULT 20,
    up_capture NUMERIC(10, 4),
    down_capture NUMERIC(10, 4),
    fitness NUMERIC(10, 4),
    up_days INTEGER NOT NULL DEFAULT 0,
    down_days INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'ok',  -- ok / insufficient_sample / no_trades / data_gap
    computed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT evolution_fitness_account_date_key UNIQUE (account_name, window_end, window_days)
);
CREATE INDEX IF NOT EXISTS idx_evolution_fitness_window_end ON quant.evolution_fitness (window_end);
```

`evolution_fitness_repository.py`（模式照抄 `agent_knowledge_repository.py`：独立 Base model + BaseORMRepository）：

```python
"""Evolution Fitness ORM Repository - evolution_fitness 表访问

表 DDL 见 infrastructure/persistence/migrations/add_evolution_fitness_table.sql。
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class EvolutionFitness(Base):
    __tablename__ = 'evolution_fitness'
    __table_args__ = (
        UniqueConstraint('account_name', 'window_end', 'window_days',
                         name='evolution_fitness_account_date_key'),
        {'schema': 'quant'},
    )

    id = Column(Integer, primary_key=True)
    account_name = Column(String(50), nullable=False)
    window_end = Column(Date, nullable=False)
    window_days = Column(Integer, nullable=False, default=20)
    up_capture = Column(Numeric(10, 4))
    down_capture = Column(Numeric(10, 4))
    fitness = Column(Numeric(10, 4))
    up_days = Column(Integer, nullable=False, default=0)
    down_days = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default='ok')
    computed_at = Column(DateTime, nullable=False, default=datetime.now)


class EvolutionFitnessORMRepository(BaseORMRepository[EvolutionFitness]):
    model = EvolutionFitness

    def upsert_fitness(
        self,
        account_name: str,
        window_end: date,
        up_capture: Optional[float],
        down_capture: Optional[float],
        fitness: Optional[float],
        up_days: int,
        down_days: int,
        status: str,
        window_days: int = 20,
    ) -> None:
        row = (
            self.session.query(EvolutionFitness)
            .filter_by(account_name=account_name, window_end=window_end, window_days=window_days)
            .first()
        )
        if row is None:
            row = EvolutionFitness(account_name=account_name, window_end=window_end,
                                   window_days=window_days)
            self.session.add(row)
        row.up_capture = up_capture
        row.down_capture = down_capture
        row.fitness = fitness
        row.up_days = up_days
        row.down_days = down_days
        row.status = status
        row.computed_at = datetime.now()
        self.session.commit()

    def get_leaderboard(
        self, window_end: date, window_days: int = 20, include_non_ok: bool = False
    ) -> List[Dict[str, Any]]:
        q = self.session.query(EvolutionFitness).filter_by(
            window_end=window_end, window_days=window_days)
        if not include_non_ok:
            q = q.filter_by(status='ok')
        rows = q.order_by(EvolutionFitness.fitness.desc().nullslast()).all()
        return [
            {
                'account_name': r.account_name,
                'window_end': r.window_end.isoformat(),
                'up_capture': float(r.up_capture) if r.up_capture is not None else None,
                'down_capture': float(r.down_capture) if r.down_capture is not None else None,
                'fitness': float(r.fitness) if r.fitness is not None else None,
                'up_days': r.up_days,
                'down_days': r.down_days,
                'status': r.status,
            }
            for r in rows
        ]

    def get_latest_window_end(self, window_days: int = 20) -> Optional[date]:
        row = (
            self.session.query(EvolutionFitness.window_end)
            .filter_by(window_days=window_days)
            .order_by(EvolutionFitness.window_end.desc())
            .first()
        )
        return row[0] if row else None
```

- [ ] **Step 4: 建表并跑测试**

Run: `cd quantsys-v2 && venv/bin/python -c "import psycopg2, os; from dotenv import load_dotenv; load_dotenv(); c=psycopg2.connect(host=os.getenv('PGHOST','127.0.0.1'), port=int(os.getenv('PGPORT','5432')), dbname=os.getenv('PGDATABASE','quant_investment'), user=os.getenv('PGUSER','postgres'), password=os.getenv('PGPASSWORD','')); c.autocommit=True; c.cursor().execute(open('infrastructure/persistence/migrations/add_evolution_fitness_table.sql').read()); print('table created')"`
（若项目用 psycopg3/SQLAlchemy 直连，改用 `infrastructure/persistence/orm` 的 engine 执行同样 SQL。）
Run: `venv/bin/python -m pytest tests/repositories/test_evolution_fitness_repository.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/infrastructure/persistence/migrations/add_evolution_fitness_table.sql quantsys-v2/adapters/outbound/repositories/evolution_fitness_repository.py quantsys-v2/tests/repositories/test_evolution_fitness_repository.py
git commit -m "feat(evolution): evolution_fitness 表 + ORM 仓储（upsert/leaderboard 幂等）"
```

---

### Task 2: 捕获率纯函数计算核心（TDD 重心）

**Files:**
- Create: `quantsys-v2/application/services/evolution/fitness_calculator.py`
- Test: `quantsys-v2/tests/services/evolution/test_fitness_calculator.py`

纯函数、零 DB 依赖，合成行情驱动全部边界。`application/services/evolution/` 新包（需 `__init__.py`，scoring/ 同款结构）。

- [ ] **Step 1: 写失败测试**

```python
"""双侧捕获适应度纯函数测试——合成行情，不碰 DB"""
import pytest
from application.services.evolution.fitness_calculator import (
    compute_capture, SIDEWAYS_THRESHOLD, MIN_SAMPLE_DAYS,
)


def _bench(days):
    """{date: bench_return}"""
    return {f'2026-07-{d:02d}': r for d, r in days}


class TestDayClassification:
    def test_up_down_sideways_split(self):
        # 10 涨日(+1%)、7 跌日(-1%)、3 横盘(±0.1%)
        days = [(i, 0.01) for i in range(1, 11)] + \
               [(i, -0.01) for i in range(11, 18)] + \
               [(i, 0.001) for i in range(18, 21)]
        bench = _bench(days)
        acct = {d: 0.012 for d in bench}  # 每天都挣 1.2%
        result = compute_capture(acct, bench, has_trades=True)
        assert result['status'] == 'ok'
        assert result['up_days'] == 10
        assert result['down_days'] == 7
        assert result['up_capture'] == pytest.approx(1.2)
        # 跌日账户也挣 1.2%（分母为负）→ down_capture = 0.012 / -0.01 = -1.2
        assert result['down_capture'] == pytest.approx(-1.2)
        assert result['fitness'] == pytest.approx(2.4)


class TestCaptureSemantics:
    def test_good_defense_beats_bad_offense(self):
        # 账户A：涨日跟上(1.0x)，跌日只亏一半(0.5x) → fitness = 1.0-0.5 = 0.5
        # 账户B：涨日冲 1.3x，跌日亏 1.6x → fitness = 1.3-1.6 = -0.3
        days = [(i, 0.01) for i in range(1, 11)] + [(i, -0.01) for i in range(11, 18)]
        bench = _bench(days)
        a = compute_capture({d: (0.01 if r > 0 else -0.005) for d, r in bench.items()},
                            bench, has_trades=True)
        b = compute_capture({d: (0.013 if r > 0 else -0.016) for d, r in bench.items()},
                            bench, has_trades=True)
        assert a['fitness'] > b['fitness']

    def test_missing_account_days_skipped(self):
        # 账户缺 2 天 snapshot：只在交集上计算，样本计数随之减少
        days = [(i, 0.01) for i in range(1, 11)] + [(i, -0.01) for i in range(11, 18)]
        bench = _bench(days)
        acct = {d: 0.01 for d, r in bench.items() if d not in ('2026-07-01', '2026-07-11')}
        result = compute_capture(acct, bench, has_trades=True)
        assert result['up_days'] == 9
        assert result['down_days'] == 6


class TestBoundaryStatus:
    def test_insufficient_sample_when_few_down_days(self):
        # 单边市：15 涨日 + 3 跌日（< MIN_SAMPLE_DAYS=5）
        days = [(i, 0.01) for i in range(1, 16)] + [(i, -0.01) for i in range(16, 19)]
        result = compute_capture(_bench(days), _bench(days), has_trades=True)
        assert result['status'] == 'insufficient_sample'
        assert result['fitness'] is None
        assert result['down_days'] == 3

    def test_no_trades_account_excluded(self):
        days = [(i, 0.01) for i in range(1, 11)] + [(i, -0.01) for i in range(11, 18)]
        bench = _bench(days)
        acct = {d: 0.0 for d in bench}  # 空仓收益恒 0
        result = compute_capture(acct, bench, has_trades=False)
        assert result['status'] == 'no_trades'
        assert result['fitness'] is None

    def test_sideways_threshold_boundary(self):
        assert abs(SIDEWAYS_THRESHOLD - 0.003) < 1e-9
        # +0.3% 恰为涨日，+0.29% 为横盘
        days = [(i, 0.003) for i in range(1, 11)] + [(i, -0.01) for i in range(11, 18)] + \
               [(18, 0.0029)]
        bench = _bench(days)
        acct = {d: 0.003 for d in bench}
        result = compute_capture(acct, bench, has_trades=True)
        assert result['up_days'] == 10

    def test_min_sample_days_constant(self):
        assert MIN_SAMPLE_DAYS == 5
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && venv/bin/python -m pytest tests/services/evolution/test_fitness_calculator.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: 实现纯函数**

```python
"""双侧捕获适应度纯计算（agent 行为进化 Phase 1 核心）

fitness = up_capture − down_capture：
- up_capture  = 大盘涨日账户平均日收益 / 大盘涨日平均收益（跟上/超越 → ≥1）
- down_capture = 大盘跌日账户平均日收益 / 大盘跌日平均收益
  （分母为负：亏得少 → 比值趋 0 或转负 → 越小越好）

单位契约：收益率均为小数比率。纯函数，不碰 DB/网络，便于合成行情测试。
"""
from typing import Any, Dict, Mapping

SIDEWAYS_THRESHOLD = 0.003  # 沪深300 日收益 |r| < 0.3% 为横盘日，剔除
MIN_SAMPLE_DAYS = 5         # 涨/跌样本任一侧不足则 insufficient_sample


def compute_capture(
    account_returns: Mapping[str, float],
    bench_returns: Mapping[str, float],
    has_trades: bool,
) -> Dict[str, Any]:
    """
    Args:
        account_returns: {date_str: 账户日收益}（窗口内，可缺日）
        bench_returns:   {date_str: 基准日收益}（窗口内）
        has_trades:      窗口内账户是否有交易（False → no_trades，防空仓虚高分）

    Returns:
        {up_capture, down_capture, fitness, up_days, down_days, status}
        status: ok / insufficient_sample / no_trades；
        非 ok 时 fitness/up_capture/down_capture 均为 None。
    """
    up_acct, up_bench, down_acct, down_bench = [], [], [], []
    for date_str, bench_r in bench_returns.items():
        if date_str not in account_returns:
            continue  # snapshot 缺日：跳过（样本计数随之减少）
        if bench_r >= SIDEWAYS_THRESHOLD:
            up_bench.append(bench_r)
            up_acct.append(float(account_returns[date_str] or 0))
        elif bench_r <= -SIDEWAYS_THRESHOLD:
            down_bench.append(bench_r)
            down_acct.append(float(account_returns[date_str] or 0))

    up_days, down_days = len(up_bench), len(down_bench)

    if not has_trades:
        return {'up_capture': None, 'down_capture': None, 'fitness': None,
                'up_days': up_days, 'down_days': down_days, 'status': 'no_trades'}
    if up_days < MIN_SAMPLE_DAYS or down_days < MIN_SAMPLE_DAYS:
        return {'up_capture': None, 'down_capture': None, 'fitness': None,
                'up_days': up_days, 'down_days': down_days,
                'status': 'insufficient_sample'}

    up_capture = (sum(up_acct) / up_days) / (sum(up_bench) / up_days)
    down_capture = (sum(down_acct) / down_days) / (sum(down_bench) / down_days)
    return {
        'up_capture': round(up_capture, 4),
        'down_capture': round(down_capture, 4),
        'fitness': round(up_capture - down_capture, 4),
        'up_days': up_days,
        'down_days': down_days,
        'status': 'ok',
    }
```

- [ ] **Step 4: 运行确认通过**

Run: `venv/bin/python -m pytest tests/services/evolution/test_fitness_calculator.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/evolution/ quantsys-v2/tests/services/evolution/
git commit -m "feat(evolution): 双侧捕获适应度纯函数（涨/跌/横盘分类+样本门槛+空仓排除）"
```

---

### Task 3: EvolutionFitnessService——装配快照+基准，逐账户计算

**Files:**
- Create: `quantsys-v2/application/services/evolution/evolution_fitness_service.py`
- Test: `quantsys-v2/tests/services/evolution/test_evolution_fitness_service.py`

- [ ] **Step 1: 写失败测试（mock 仓储与基准）**

```python
"""EvolutionFitnessService 装配层测试——mock 仓储/基准源，验证编排逻辑"""
from datetime import date, timedelta
from unittest.mock import MagicMock
from application.services.evolution.evolution_fitness_service import EvolutionFitnessService


def _make_service(snaps_by_acct, bench_returns, trades_by_acct):
    sim_repo = MagicMock()
    sim_repo.list_account_names.return_value = list(snaps_by_acct.keys())
    sim_repo.get_equity_snapshots.side_effect = (
        lambda account_name, limit=90, end_date=None: snaps_by_acct[account_name]
    )
    fitness_repo = MagicMock()
    svc = EvolutionFitnessService(
        sim_repo=sim_repo,
        fitness_repo=fitness_repo,
        bench_returns_provider=lambda start, end: bench_returns,
        trade_counter=lambda account_name, start, end: trades_by_acct[account_name],
    )
    return svc, fitness_repo


class TestComputeAllAccounts:
    def test_upserts_per_account_with_status(self):
        # 构造 20 天窗口：10 涨 7 跌 3 横盘
        end = date(2026, 8, 5)
        bench = {}
        acct_snaps = []
        day = end - timedelta(days=27)  # 窗口外多给几天，服务应只取窗口内
        i = 0
        while len(bench) < 20:
            day += timedelta(days=1)
            if day.weekday() >= 5:
                continue
            i += 1
            r = 0.01 if i <= 10 else (-0.01 if i <= 17 else 0.001)
            bench[day.isoformat()] = r
        for acct in ('agent_virtual',):
            snaps = [MagicMock(snapshot_date=date.fromisoformat(d), daily_return=r * 1.2,
                               total_value=100000)
                     for d, r in bench.items()]
            acct_snaps = snaps
        svc, fitness_repo = _make_service(
            {'agent_virtual': acct_snaps}, bench, {'agent_virtual': 3})
        result = svc.compute_all_accounts(window_end=end, window_days=20)
        assert result['computed'] == 1
        upsert = fitness_repo.upsert_fitness.call_args.kwargs
        assert upsert['account_name'] == 'agent_virtual'
        assert upsert['status'] == 'ok'
        assert upsert['up_capture'] == 1.2

    def test_no_trades_account_marked(self):
        svc, fitness_repo = _make_service({'v15': []}, {}, {'v15': 0})
        svc.compute_all_accounts(window_end=date(2026, 8, 5), window_days=20)
        upsert = fitness_repo.upsert_fitness.call_args.kwargs
        assert upsert['status'] == 'no_trades'

    def test_bench_missing_degrades_to_data_gap(self):
        snaps = [MagicMock(snapshot_date=date(2026, 8, 5), daily_return=0.01,
                           total_value=100000)]
        svc, fitness_repo = _make_service({'agent_virtual': snaps}, {}, {'agent_virtual': 2})
        svc.compute_all_accounts(window_end=date(2026, 8, 5), window_days=20)
        upsert = fitness_repo.upsert_fitness.call_args.kwargs
        assert upsert['status'] == 'data_gap'
```

- [ ] **Step 2: 运行确认失败**

Run: `venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py -v`
Expected: ModuleNotFoundError / TypeError（签名不存在）

- [ ] **Step 3: 实现服务**

先确认两个依赖的真实签名（实现时读代码对齐）：
- `adapters/outbound/repositories/simulation_repository.py` 的 `get_equity_snapshots(account_name, limit)`（:522，按 date desc，limit 默认 90）；账户清单查 `SimulationAccount`（同文件 model，补一个 `list_account_names()` 方法若不存在）
- `application/services/benchmark_comparison.py` 的 `fetch_benchmark_klines(symbol='sh000300', start_date, end_date)` + `_benchmark_daily_returns(klines)`
- 交易计数：`SimulationTrade`（`simulation.py` model）按 account_name + trade_date 区间 count；仓储无现成方法则在服务内直接 query

```python
"""双侧捕获适应度装配服务：快照 + 基准 → 纯函数 → 落库（每日调度调用）"""
from datetime import date, timedelta
from typing import Any, Callable, Dict, Mapping, Optional

import structlog

from application.services.benchmark_comparison import (
    _benchmark_daily_returns, fetch_benchmark_klines,
)
from application.services.evolution.fitness_calculator import compute_capture

logger = structlog.get_logger(__name__)

BENCHMARK_SYMBOL = 'sh000300'
LOOKBACK_BUFFER_DAYS = 45  # 20 交易日窗口的自然日上界（含周末/长假缓冲）


class EvolutionFitnessService:
    def __init__(
        self,
        sim_repo=None,
        fitness_repo=None,
        bench_returns_provider: Optional[Callable[[date, date], Mapping[str, float]]] = None,
        trade_counter: Optional[Callable[[str, date, date], int]] = None,
    ):
        if sim_repo is None:
            from adapters.outbound.repositories.simulation_repository import SimulationRepository
            sim_repo = SimulationRepository()
        if fitness_repo is None:
            from adapters.outbound.repositories.evolution_fitness_repository import (
                EvolutionFitnessORMRepository,
            )
            fitness_repo = EvolutionFitnessORMRepository()
        self.sim_repo = sim_repo
        self.fitness_repo = fitness_repo
        self._bench_provider = bench_returns_provider or self._default_bench_provider
        self._trade_counter = trade_counter or self._default_trade_counter

    @staticmethod
    def _default_bench_provider(start: date, end: date) -> Mapping[str, float]:
        klines = fetch_benchmark_klines(
            symbol=BENCHMARK_SYMBOL, start_date=start.isoformat(), end_date=end.isoformat())
        return _benchmark_daily_returns(klines)

    def _default_trade_counter(self, account_name: str, start: date, end: date) -> int:
        from infrastructure.persistence.orm.models.simulation import SimulationTrade
        return (
            self.sim_repo.session.query(SimulationTrade)
            .filter(SimulationTrade.account_name == account_name,
                    SimulationTrade.trade_date >= start,
                    SimulationTrade.trade_date <= end)
            .count()
        )

    def compute_all_accounts(self, window_end: Optional[date] = None,
                             window_days: int = 20) -> Dict[str, Any]:
        window_end = window_end or date.today()
        start = window_end - timedelta(days=LOOKBACK_BUFFER_DAYS)
        bench_all = dict(self._bench_provider(start, window_end))
        computed = skipped = 0
        for account_name in self.sim_repo.list_account_names():
            snaps = self.sim_repo.get_equity_snapshots(
                account_name, limit=LOOKBACK_BUFFER_DAYS)
            acct_returns = {
                s.snapshot_date.isoformat(): float(s.daily_return or 0)
                for s in snaps if start <= s.snapshot_date <= window_end
            }
            # 窗口内对齐日 = 账户 ∩ 基准；基准本身按交易日给，取最近 window_days 个
            aligned_dates = sorted(d for d in bench_all if d in acct_returns)[-window_days:]
            bench_window = {d: bench_all[d] for d in aligned_dates}
            acct_window = {d: acct_returns[d] for d in aligned_dates}
            if not bench_window:
                result = {'up_capture': None, 'down_capture': None, 'fitness': None,
                          'up_days': 0, 'down_days': 0, 'status': 'data_gap'}
            else:
                win_start = date.fromisoformat(min(aligned_dates))
                trades = self._trade_counter(account_name, win_start, window_end)
                result = compute_capture(acct_window, bench_window, has_trades=trades > 0)
            self.fitness_repo.upsert_fitness(
                account_name=account_name, window_end=window_end,
                window_days=window_days, **result)
            computed += 1
        logger.info('evolution_fitness computed', window_end=str(window_end),
                    computed=computed)
        return {'computed': computed, 'skipped': skipped, 'window_end': str(window_end)}
```

注意：服务依赖 `sim_repo.list_account_names()`——若 `SimulationRepository` 没有此方法，在 Task 内给它补上（查 `SimulationAccount.account_name` distinct，照该文件现有 query 风格），并为其加一行测试断言。

- [ ] **Step 4: 运行确认通过**

Run: `venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/evolution/evolution_fitness_service.py quantsys-v2/tests/services/evolution/test_evolution_fitness_service.py quantsys-v2/adapters/outbound/repositories/simulation_repository.py
git commit -m "feat(evolution): EvolutionFitnessService 装配层（快照∩基准对齐+交易计数+降级）"
```

---

### Task 4: scheduler 日任务接线

**Files:**
- Modify: `quantsys-v2/infrastructure/scheduler/scheduler.py`（`_execute_command` handlers map :1064 附近 + 新增 handler 方法）
- Modify: `quantsys-v2/scripts/init_scheduler_tasks.py`（DEFAULT_TASKS 加一条）
- Test: `quantsys-v2/tests/test_evolution_fitness_task.py`（参照 `tests/test_chan_scan_task.py` 模式）

- [ ] **Step 1: 写失败测试**

```python
"""evolution_fitness_daily 调度命令测试"""
from unittest.mock import patch, MagicMock
from infrastructure.scheduler.scheduler import SchedulerService


class TestEvolutionFitnessCommand:
    def test_command_dispatches_and_returns_summary(self):
        svc = SchedulerService()
        with patch(
            'application.services.evolution.evolution_fitness_service.EvolutionFitnessService'
        ) as MockSvc:
            MockSvc.return_value.compute_all_accounts.return_value = {
                'computed': 5, 'skipped': 0, 'window_end': '2026-08-05'}
            result = svc._execute_command('evolution_fitness_daily', {})
        assert result['status'] == 'success'
        assert result['computed'] == 5
```

- [ ] **Step 2: 运行确认失败**

Run: `venv/bin/python -m pytest tests/test_evolution_fitness_task.py -v`
Expected: ValueError: Unknown scheduler command: 'evolution_fitness_daily'

- [ ] **Step 3: 接线**

`scheduler.py` handlers map 加一行（`"kline_update"` 那行之后）：

```python
            "evolution_fitness_daily": self._handle_evolution_fitness_daily,  # 双侧捕获适应度日算（2026-08-05 行为进化 P1）
```

新增方法（放 `_handle_signal_generate` 后，照其结构）：

```python
    def _handle_evolution_fitness_daily(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """每日收盘后计算全账户滚动 20 日双侧捕获适应度。"""
        from application.services.evolution.evolution_fitness_service import EvolutionFitnessService
        window_days = int(params.get('window_days', 20))
        result = EvolutionFitnessService().compute_all_accounts(window_days=window_days)
        return {'status': 'success', **result}
```

`init_scheduler_tasks.py` DEFAULT_TASKS 加（equity snapshot 在收盘对账后产出，18:30 稳态）：

```python
    {
        'name': 'evolution-fitness-daily',
        'cron_expression': '30 18 * * 1-5',  # 工作日下午 6:30（收盘对账后）
        'command': 'evolution_fitness_daily',
        'params': {'window_days': 20},
        'description': '双侧捕获适应度每日计算（行为进化 Phase 1）'
    },
```

- [ ] **Step 4: 运行测试 + 生产注册任务**

Run: `venv/bin/python -m pytest tests/test_evolution_fitness_task.py -v`
Expected: 1 passed
Run: `venv/bin/python scripts/init_scheduler_tasks.py`（幂等注册；随后查 PG `SELECT name, is_enabled, next_run_at FROM quant.scheduler_tasks WHERE name='evolution-fitness-daily';` 确认注册——缠论 cron 的教训：注册必须眼见为实）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/infrastructure/scheduler/scheduler.py quantsys-v2/scripts/init_scheduler_tasks.py quantsys-v2/tests/test_evolution_fitness_task.py
git commit -m "feat(evolution): evolution_fitness_daily 调度命令接线（18:30 工作日）"
```

---

### Task 5: 排行榜 API（FastAPI）

**Files:**
- Create: `quantsys-v2/adapters/inbound/fastapi_app/routes/evolution_async.py`
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/main.py`（:487 chan_router 注册处同款）
- Test: `quantsys-v2/tests/api/test_evolution_api.py`（参照现有 FastAPI 路由测试模式；无 API 测试目录则放 `tests/test_evolution_api.py` 用 fastapi.testclient）

- [ ] **Step 1: 写失败测试**

```python
"""GET /api/evolution/leaderboard 契约测试"""
from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient


class TestLeaderboardApi:
    def test_returns_ranked_rows(self, api_client: TestClient):
        rows = [
            {'account_name': 'agent_virtual', 'window_end': '2026-08-05',
             'up_capture': 1.2, 'down_capture': 0.5, 'fitness': 0.7,
             'up_days': 10, 'down_days': 7, 'status': 'ok'},
        ]
        with patch(
            'adapters.outbound.repositories.evolution_fitness_repository.EvolutionFitnessORMRepository'
        ) as MockRepo:
            inst = MockRepo.return_value
            inst.get_latest_window_end.return_value = date(2026, 8, 5)
            inst.get_leaderboard.return_value = rows
            resp = api_client.get('/api/evolution/leaderboard?window=20')
        assert resp.status_code == 200
        data = resp.json()
        assert data['window_end'] == '2026-08-05'
        assert data['ranking'][0]['account_name'] == 'agent_virtual'
        assert data['ranking'][0]['rank'] == 1
```

`api_client` fixture：用项目 FastAPI app 的 TestClient（参照现有任一 FastAPI 路由测试的 app 构造方式）。

- [ ] **Step 2: 运行确认失败**

Run: `venv/bin/python -m pytest tests/api/test_evolution_api.py -v`
Expected: 404

- [ ] **Step 3: 实现路由并注册**

```python
"""进化适应度排行榜 API（行为进化 Phase 1）"""
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Evolution - 行为进化"])


@router.get('/api/evolution/leaderboard')
def get_leaderboard(
    window: int = Query(20, ge=5, le=60),
    window_end: Optional[str] = Query(None, description='YYYY-MM-DD，默认最新已计算日'),
    include_non_ok: bool = Query(False),
):
    """全账户双侧捕获适应度排行（fitness 降序，rank 从 1 起）"""
    try:
        from datetime import date as _date
        from adapters.outbound.repositories.evolution_fitness_repository import (
            EvolutionFitnessORMRepository,
        )
        repo = EvolutionFitnessORMRepository()
        end = _date.fromisoformat(window_end) if window_end else repo.get_latest_window_end(window)
        if end is None:
            return {'window_end': None, 'ranking': [], 'message': '尚无适应度数据'}
        rows = repo.get_leaderboard(end, window_days=window, include_non_ok=include_non_ok)
        for i, row in enumerate(rows, 1):
            row['rank'] = i
        return {'window_end': end.isoformat(), 'window_days': window, 'ranking': rows}
    except Exception as e:
        logger.error('leaderboard failed', error=str(e))
        return JSONResponse(status_code=500, content={'error': f'排行榜查询失败: {e}'})
```

`main.py` :487 处照 chan_router 模式加：

```python
        from adapters.inbound.fastapi_app.routes.evolution_async import router as evolution_router
        app.include_router(evolution_router)
```
（包进同款 try/except ImportError 块，logger.warning 同款文案。）

- [ ] **Step 4: 运行确认通过 + 冒烟**

Run: `venv/bin/python -m pytest tests/api/test_evolution_api.py -v`
Expected: 1 passed
冒烟（5001 是 FastAPI，手动重启后）：`curl -s http://127.0.0.1:5001/api/evolution/leaderboard | head -c 400`（此时表空 → `ranking: []` 属正常）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/inbound/fastapi_app/routes/evolution_async.py quantsys-v2/adapters/inbound/fastapi_app/main.py quantsys-v2/tests/api/test_evolution_api.py
git commit -m "feat(evolution): GET /api/evolution/leaderboard 排行榜 API"
```

---

### Task 6: agent-ts 工具 evolution_leaderboard

**Files:**
- Create: `agent-ts/src/infrastructure/tools/performance/evolution-leaderboard-tool.ts`
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`（V2_ROUTES :93 附近加映射）
- Modify: `agent-ts/src/infrastructure/tools/index.ts`（import + 注册，:301 chanAnalyzeTool 附近）
- Test: `agent-ts/src/infrastructure/tools/performance/evolution-leaderboard-tool.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { evolutionLeaderboardTool } from "./evolution-leaderboard-tool.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

jest.mock("../../adapters/quant/quant-v2-client.js", () => ({
  runQuantV2: jest.fn(),
}));
const mockRun = runQuantV2 as jest.MockedFunction<typeof runQuantV2>;

describe("evolution_leaderboard", () => {
  it("格式化排行榜含排名/适应度/捕获明细", async () => {
    mockRun.mockResolvedValue({
      ok: true, command: "evolution.leaderboard",
      data: {
        window_end: "2026-08-05", window_days: 20,
        ranking: [
          { rank: 1, account_name: "agent_virtual", fitness: 0.7,
            up_capture: 1.2, down_capture: 0.5, up_days: 10, down_days: 7, status: "ok" },
          { rank: 2, account_name: "v14_simulation", fitness: -0.7,
            up_capture: 0.8, down_capture: 1.5, up_days: 10, down_days: 7, status: "ok" },
        ],
      },
    } as any);
    const result = await evolutionLeaderboardTool.execute("t1", {});
    const text = result.content[0].text;
    expect(mockRun).toHaveBeenCalledWith("evolution.leaderboard", { window: 20 });
    expect(text).toContain("agent_virtual");
    expect(text).toContain("0.70");
    expect(text).toContain("上涨捕获 1.20");
    expect(text).toContain("下跌捕获 0.50");
  });

  it("空排行返回引导文案", async () => {
    mockRun.mockResolvedValue({
      ok: true, command: "evolution.leaderboard",
      data: { window_end: null, ranking: [], message: "尚无适应度数据" },
    } as any);
    const result = await evolutionLeaderboardTool.execute("t2", {});
    expect(result.content[0].text).toContain("尚无适应度数据");
  });

  it("v2 错误返回 success=false", async () => {
    mockRun.mockRejectedValue(new Error("connect ECONNREFUSED"));
    const result = await evolutionLeaderboardTool.execute("t3", {});
    expect((result.details as any).success).toBe(false);
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npm test -- evolution-leaderboard`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现工具 + 注册**

V2_ROUTES 加（:93 chan.analyze 行后）：

```typescript
  "evolution.leaderboard":  { path: "/api/evolution/leaderboard",           method: "GET"  }, // ✅ 双侧捕获适应度排行（行为进化 P1）
```

`evolution-leaderboard-tool.ts`（结构照 chan-analyze-tool.ts）：

```typescript
/**
 * Evolution Leaderboard Tool - 行为进化适应度排行榜
 *
 * 调用 quantsys-v2 GET /api/evolution/leaderboard，返回全账户滚动 20 日
 * 双侧捕获适应度排名：fitness = 上涨捕获 − 下跌捕获。
 * 上涨捕获 ≥1 = 大盘涨时跟得上；下跌捕获越小 = 大盘跌时亏得越少。
 *
 * 何时使用：每日复盘评估自己在全账户中的相对表现；判断当前行为模式
 * 是「涨跟不上」还是「跌守不住」。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

interface FitnessRow {
  rank: number; account_name: string; fitness: number | null;
  up_capture: number | null; down_capture: number | null;
  up_days: number; down_days: number; status: string;
}

function formatBoard(data: any): string {
  if (!data.ranking || data.ranking.length === 0) {
    return `尚无适应度数据（${data.message ?? '等待每日计算任务产出'}）。`;
  }
  const lines: string[] = [
    `行为进化适应度排行（窗口 ${data.window_end} 止 ${data.window_days} 交易日）：`,
  ];
  for (const r of data.ranking as FitnessRow[]) {
    if (r.status !== 'ok' || r.fitness == null) {
      lines.push(`#${r.rank} ${r.account_name}：${r.status}（样本不足或无交易，不参与排名）`);
      continue;
    }
    lines.push(
      `#${r.rank} ${r.account_name}：适应度 ${r.fitness.toFixed(2)}` +
      `｜上涨捕获 ${r.up_capture!.toFixed(2)}（${r.up_days} 个涨日）` +
      `｜下跌捕获 ${r.down_capture!.toFixed(2)}（${r.down_days} 个跌日）`
    );
  }
  lines.push('解读：上涨捕获≥1 为跟上大盘；下跌捕获<1 为跌时少亏；适应度越高越好。');
  return lines.join('\n');
}

export const evolutionLeaderboardTool: ToolDefinition = {
  name: "evolution_leaderboard",
  label: "进化适应度排行",
  description: "查看全账户滚动20日双侧捕获适应度排名（fitness=上涨捕获−下跌捕获）。用于每日复盘评估相对表现：涨时是否跟上、跌时是否守住。",
  parameters: Type.Object({
    window: Type.Optional(Type.Number({ description: "窗口交易日数，默认 20", default: 20 })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const response = await runQuantV2("evolution.leaderboard", { window: params.window ?? 20 });
      return handleToolResponse({
        toolName: 'evolution_leaderboard',
        data: (response as any).data ?? response,
        formatter: (data) => typeof data === 'string' ? data : formatBoard(data),
        metadata: { params },
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `适应度排行查询失败: ${errorMsg}` }],
        details: { success: false, error: errorMsg, params },
      };
    }
  },
};
```

`tools/index.ts`：import 并在 :301 chanAnalyzeTool 行后加 `evolutionLeaderboardTool, // evolution_leaderboard - 双侧捕获适应度排行`。

注意 GET 命令的 query 传递：读 `quant-v2-client.ts` 确认 GET 方法如何把 params 拼成 query string（照已有 GET 命令的工具用法，如 decision_history）；若客户端不支持 GET 带参，改为不传 window 参数（服务端默认 20）并在测试中去掉该断言。

- [ ] **Step 4: 运行确认通过**

Run: `cd agent-ts && npm test -- evolution-leaderboard`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/infrastructure/tools/performance/ agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts agent-ts/src/infrastructure/tools/index.ts
git commit -m "feat(evolution): evolution_leaderboard 工具（v2 排行榜薄封装）"
```

---

### Task 7: 注入 daily_ai_review 复盘 prompt

**Files:**
- Modify: `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts`（daily_ai_review 第四步 :184-260 区域）
- Test: `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.test.ts`

- [ ] **Step 1: 先看现有测试断言**

Run: `cd agent-ts && grep -n "daily_ai_review\|第四步" src/services/scheduler/tasks/agent-decision-tasks.test.ts | head`
若有 prompt 内容断言，新步骤不能破坏；若无，补一条断言。

- [ ] **Step 2: 写/改失败测试**

在测试文件加（或改）：

```typescript
it("daily_ai_review prompt 包含进化适应度排行步骤", () => {
  const tasks = buildAgentDecisionTasks(); // 照该测试文件现有获取任务列表的方式
  const review = tasks.find((t) => t.name === "daily_ai_review");
  expect((review?.payload as any).message).toContain("evolution_leaderboard");
  expect((review?.payload as any).message).toContain("上涨捕获");
});
```

- [ ] **Step 3: 修改 prompt**

`agent-decision-tasks.ts` daily_ai_review message 的「第四步：计算绩效指标」末尾追加一段（插在第五步分隔线之前）：

```
2. 使用 evolution_leaderboard 查看全账户适应度排行：
   - 我排第几？fitness 多少？
   - 差距在哪一侧：上涨捕获 <1（涨时没跟上）还是下跌捕获 >1（跌时亏更多）？
   - 把这个判断写进今日经验沉淀（第五步）
```

- [ ] **Step 4: 运行测试**

Run: `cd agent-ts && npm test -- agent-decision-tasks`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts agent-ts/src/services/scheduler/tasks/agent-decision-tasks.test.ts
git commit -m "feat(evolution): daily_ai_review 注入适应度排行自评步骤"
```

---

### Task 8: 历史回填 + Phase 1 验收

**Files:** 无新文件（运维操作 + 记录）

- [ ] **Step 1: 回填历史 20 日适应度**

写一个一次性回填（直接 python 内联，不落文件）：

Run: `cd quantsys-v2 && venv/bin/python -c "
from datetime import date, timedelta
from application.services.evolution.evolution_fitness_service import EvolutionFitnessService
svc = EvolutionFitnessService()
end = date.today()
for i in range(30, -1, -1):
    d = end - timedelta(days=i)
    if d.weekday() < 5:
        print(svc.compute_all_accounts(window_end=d))
"`

- [ ] **Step 2: 查排行验证已知好坏分离**

Run: `psql quant_investment -c "SELECT account_name, window_end, fitness, up_capture, down_capture, status FROM quant.evolution_fitness ORDER BY window_end DESC, fitness DESC NULLS LAST LIMIT 20;"`

验收判定（spec §3.4）：v14_simulation 应显著垫底（fitness 大负值），agent_virtual 应相对靠前。若分不出，记录现象回 spec 讨论改公式，**不进 Phase 2**。

- [ ] **Step 3: 确认调度任务下次运行**

Run: `psql quant_investment -c "SELECT name, is_enabled, next_run_at FROM quant.scheduler_tasks WHERE name='evolution-fitness-daily';"`
确认 next_run_at 为下一个工作日 18:30（缠论 cron 教训：注册必须眼见为实）。

- [ ] **Step 4: 重启 5001 FastAPI 与 scheduler daemon**

生产 5001 是主工作区 venv nohup 手动重启（见 prod-5001 部署记忆）。重启后 `curl -s http://127.0.0.1:5001/api/evolution/leaderboard | head -c 400` 冒烟。**改 scheduler 代码要同时重启 5001 和 daemon**（scheduler-zombie-run-reaper 记忆）。

- [ ] **Step 5: 更新记忆 + 最终 commit**

更新 `docs/superpowers/specs/2026-08-05-agent-behavior-evolution-design.md` 顶部状态为「Phase 1 已上线，观察期至 20 个交易日后验收」并 commit。

---

## Self-Review 记录

- Spec 覆盖：§3.1 公式/边界 → Task 2；§3.2 存储 → Task 1；§3.3 API/工具/prompt → Task 5/6/7；每日增量计算 → Task 4；§3.4 验收 → Task 8。web 前端页面 spec 明确不做 ✓
- 类型一致性：`compute_capture` 返回 dict 键（up_capture/down_capture/fitness/up_days/down_days/status）在 Task 3 upsert kwargs、Task 1 仓储签名、Task 5 API 响应中一致 ✓；`evolution.leaderboard` 命令名在 Task 5/6 一致 ✓
- 已知风险：GET 带参（Task 6 Step 3 已留确认步骤）；`list_account_names` 可能需新增（Task 3 Step 3 已注明）；pg_session fixture 名以现有 heatmap 测试为准（Task 1 Step 1 已注明）
