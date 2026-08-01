# 股票热力图（Stock Heatmap）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 web-frontend 新增「市场热力图」页：行业→个股两级 treemap，颜色=验证窗实际涨跌，叠加 agent 信号/池调整/行业判断痕迹，用于人工校验 agent 判断对错。

**Architecture:** quantsys-v2 新增只读聚合端点 `GET /api/market/heatmap?date=D&window=N`（HeatmapService 纯 SQL 聚合 daily_klines/stocks/signals/pool_change_log/stock_pools/portfolio_holdings，无外部行情调用），**仅 FastAPI 路由**（Flask 已废弃仅用于回滚，见 quantsys-v2/CLAUDE.md「Flask (已废弃，仅用于回滚)」）；web-frontend 新增 StockHeatmap 视图（ECharts 6 内置 treemap，无新依赖），纯函数 option 构建器 + 对错判定器可单测。

**Tech Stack:** Python 3.13 / SQLAlchemy / Flask / FastAPI / pytest（真实 quant_test DB）；Vue 3 / Element Plus / ECharts 6 / Vitest。

**Spec:** `docs/superpowers/specs/2026-07-31-stock-heatmap-design.md`

**Worktree:** 实现必须在隔离 worktree 中进行（superpowers:using-git-worktrees，分支 `feat/stock-heatmap`）。本计划所有 git 命令假设 cwd 为 worktree 根目录。

**关键契约（跨任务一致）：**
- 后端 service 返回 snake_case dict；路由层 `api_response()` 会把所有 key 转 **camelCase**，所以前端拿到的字段是：`changePct / marketCap / inScope / poolEvents / agentStance / actualEndDate / scopeDegraded / excludedCount`
- `market_cap` 单位与 `quant.stocks` 表存储一致，**不做换算**（treemap 面积只用相对值）
- 响应结构见 spec §4.2，冻结后由 FastAPI 契约测试守护

---

## 文件结构

**后端（quantsys-v2/）：**
- 新建 `adapters/outbound/repositories/heatmap_repository.py` — 只读跨表查询（唯一 SQL 出口）
- 新建 `application/services/heatmap_service.py` — 聚合逻辑 + stance 推导 + in_scope 口径
- 修改 `adapters/inbound/fastapi_app/routes/market_data_async.py` — FastAPI 路由（唯一对外路由；不写 Flask 路由）
- 新建 `tests/services/test_heatmap_service.py`、`tests/api/test_market_heatmap_route.py`（FastAPI TestClient 契约测试）

**前端（web-frontend/）：**
- 修改 `src/types/api.ts` — Heatmap* 类型
- 修改 `src/services/api/adapters.ts` — `adaptHeatmap`
- 修改 `src/services/api/stock.ts` — `stockApi.getHeatmap`
- 新建 `src/views/StockHeatmap/verdict.ts` — 对错判定纯函数
- 新建 `src/views/StockHeatmap/chart-options.ts` — treemap option 构建纯函数
- 新建 `src/views/StockHeatmap/index.vue` — 页面
- 修改 `src/router/index.ts`、`src/components/layout/MainLayout.vue`
- 新建 `tests/unit/stock-heatmap.test.ts`

---

## Task 1: HeatmapRepository — 交易日与窗口收盘价查询

**Files:**
- Create: `quantsys-v2/adapters/outbound/repositories/heatmap_repository.py`
- Test: `quantsys-v2/tests/repositories/test_heatmap_repository.py`

- [ ] **Step 1: 写失败测试**

```python
# quantsys-v2/tests/repositories/test_heatmap_repository.py
"""HeatmapRepository 交易日/窗口收盘价查询测试（真实 quant_test DB）"""
from datetime import date

import pytest

from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
from infrastructure.persistence.orm.models.stock import DailyKline, Stock

# 用 2009 年的日期避免与 quant_test 中其他测试数据冲突
D0 = date(2009, 1, 5)   # 周一
D1 = date(2009, 1, 6)
D2 = date(2009, 1, 7)


@pytest.fixture
def seeded():
    repo = HeatmapRepository()
    s = repo.session
    s.add_all([
        Stock(symbol='TST001', name='测试一', industry='测试半导体', market='A', market_cap=100.0),
        Stock(symbol='TST002', name='测试二', industry='测试半导体', market='A', market_cap=50.0),
    ])
    for sym, c0, c1 in [('TST001', 10.0, 11.0), ('TST002', 20.0, 18.0)]:
        s.add_all([
            DailyKline(symbol=sym, trade_date=D0, open=c0, high=c0, low=c0, close=c0, volume=1, amount=1),
            DailyKline(symbol=sym, trade_date=D1, open=c1, high=c1, low=c1, close=c1, volume=1, amount=1),
        ])
    s.commit()
    yield repo
    for sym in ('TST001', 'TST002'):
        s.query(DailyKline).filter(DailyKline.symbol == sym).delete()
        s.query(Stock).filter(Stock.symbol == sym).delete()
    s.commit()


class TestTradeDates:
    def test_last_trade_date_on_or_before(self, seeded):
        assert seeded.get_last_trade_date_on_or_before(date(2009, 1, 6)) >= D1

    def test_trade_dates_from(self, seeded):
        dates = seeded.get_trade_dates_from(D0, 2)
        assert dates[0] == D0
        assert dates[1] == D1
        assert len(dates) == 2

    def test_trade_dates_partial_when_not_enough(self, seeded):
        # 只要 4 个交易日，但只播了 2 天（且更晚的日期若存在也属于其他数据，
        # 本用例只断言返回列表不为空且首日正确——partial 判定在 service 层）
        dates = seeded.get_trade_dates_from(D0, 4)
        assert dates[0] == D0


class TestWindowCloses:
    def test_window_closes(self, seeded):
        closes = seeded.get_window_closes(['TST001', 'TST002'], D0, D1)
        assert closes['TST001'] == {'close_d0': 10.0, 'close_dn': 11.0}
        assert closes['TST002'] == {'close_d0': 20.0, 'close_dn': 18.0}

    def test_window_closes_empty_symbols(self, seeded):
        assert seeded.get_window_closes([], D0, D1) == {}
```

- [ ] **Step 2: 运行确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_heatmap_repository.py -v --no-cov
```
预期：ImportError / 全部 FAIL（模块不存在）

- [ ] **Step 3: 实现 HeatmapRepository（第一批方法）**

```python
# quantsys-v2/adapters/outbound/repositories/heatmap_repository.py
"""热力图聚合查询 — 跨表只读查询的唯一出口（Task 1: 交易日与收盘价；Task 2 补充信号/池/持仓）"""
from datetime import date
from typing import Optional

from sqlalchemy import func

from infrastructure.persistence.orm.base_repository import BaseORMRepository
from infrastructure.persistence.orm.models.stock import DailyKline, Stock


class HeatmapRepository(BaseORMRepository[DailyKline]):
    model = DailyKline

    def get_last_trade_date_on_or_before(self, d: date) -> Optional[date]:
        """d（含）之前最近的交易日；无数据返回 None"""
        return (
            self.session.query(func.max(DailyKline.trade_date))
            .filter(DailyKline.trade_date <= d)
            .scalar()
        )

    def get_trade_dates_from(self, d: date, count: int) -> list[date]:
        """从 d（含）起最多 count 个不重复交易日，升序"""
        rows = (
            self.session.query(DailyKline.trade_date)
            .filter(DailyKline.trade_date >= d)
            .distinct()
            .order_by(DailyKline.trade_date.asc())
            .limit(count)
            .all()
        )
        return [r[0] for r in rows]

    def get_window_closes(self, symbols: list[str], d0: date, dn: date) -> dict[str, dict]:
        """每只股票在 d0 / dn 两日的收盘价：{symbol: {'close_d0': x, 'close_dn': y}}（缺日期的 key 不出现）"""
        if not symbols:
            return {}
        rows = (
            self.session.query(DailyKline.symbol, DailyKline.trade_date, DailyKline.close)
            .filter(DailyKline.symbol.in_(symbols), DailyKline.trade_date.in_([d0, dn]))
            .all()
        )
        result: dict[str, dict] = {}
        for symbol, trade_date, close in rows:
            entry = result.setdefault(symbol, {})
            if trade_date == d0:
                entry['close_d0'] = close
            else:
                entry['close_dn'] = close
        return result

    def get_stocks_meta(self, symbols: list[str]) -> dict[str, dict]:
        """{symbol: {'name','industry','market_cap'}}（market_cap 单位与 stocks 表一致，不换算）"""
        if not symbols:
            return {}
        rows = (
            self.session.query(Stock.symbol, Stock.name, Stock.industry, Stock.market_cap)
            .filter(Stock.symbol.in_(symbols))
            .all()
        )
        return {
            r.symbol: {'name': r.name, 'industry': r.industry, 'market_cap': r.market_cap}
            for r in rows
        }

    def get_stocks_meta_by_industries(self, industries: list[str]) -> dict[str, dict]:
        """同行业全部股票的 meta（含池外股票，供灰色背景块）"""
        if not industries:
            return {}
        rows = (
            self.session.query(Stock.symbol, Stock.name, Stock.industry, Stock.market_cap)
            .filter(Stock.industry.in_(industries))
            .all()
        )
        return {
            r.symbol: {'name': r.name, 'industry': r.industry, 'market_cap': r.market_cap}
            for r in rows
        }
```

- [ ] **Step 4: 运行确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_heatmap_repository.py -v --no-cov
```
预期：5 个测试全 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/outbound/repositories/heatmap_repository.py quantsys-v2/tests/repositories/test_heatmap_repository.py
git commit -m "feat(heatmap): HeatmapRepository 交易日/窗口收盘价/stock meta 查询"
```

---

## Task 2: HeatmapRepository — 信号 / 池事件 / 持仓查询

**Files:**
- Modify: `quantsys-v2/adapters/outbound/repositories/heatmap_repository.py`
- Test: `quantsys-v2/tests/repositories/test_heatmap_repository_events.py`

- [ ] **Step 1: 写失败测试**

```python
# quantsys-v2/tests/repositories/test_heatmap_repository_events.py
"""HeatmapRepository 信号/池事件/持仓查询测试（真实 quant_test DB）"""
from datetime import date, datetime

import pytest

from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
from adapters.outbound.repositories.pool_change_log_repository import PoolChangeLog
from adapters.outbound.repositories.stock_pool_repository import StockPool
from infrastructure.persistence.orm.models.portfolio import PortfolioHolding
from infrastructure.persistence.orm.models.signal import Signal
from infrastructure.persistence.orm.models.stock import Stock

D = date(2009, 1, 20)


@pytest.fixture
def seeded():
    repo = HeatmapRepository()
    s = repo.session
    s.add(Stock(symbol='TST010', name='信号股', industry='测试医药', market='A', market_cap=10.0))
    s.add(Stock(symbol='TST011', name='持仓股', industry='测试医药', market='A', market_cap=20.0))
    s.add_all([
        Signal(symbol='TST010', name='信号股', signal_date=date(2009, 1, 15),
               action='buy', strategy_id='v13', price=1.0, confidence=0.8),
        Signal(symbol='TST010', name='信号股', signal_date=date(2009, 1, 18),
               action='sell', strategy_id='v13', price=1.0, confidence=0.7),
        # 窗口外信号（2009-01-05 前）不应返回
        Signal(symbol='TST010', name='信号股', signal_date=date(2008, 12, 1),
               action='buy', strategy_id='v13', price=1.0, confidence=0.6),
    ])
    pool = StockPool(name='测试池', pool_type='dynamic', members=['TST011'])
    s.add(pool)
    s.flush()
    s.add_all([
        PoolChangeLog(pool_id=pool.id, changed_at=datetime(2009, 1, 19, 10, 0),
                      action='add', symbol='TST010', reason='测试调入'),
        PoolChangeLog(pool_id=pool.id, changed_at=datetime(2009, 1, 21, 10, 0),
                      action='remove', symbol='TST011', reason='D 之后的事件（回放用）'),
    ])
    s.add(PortfolioHolding(symbol='TST011', name='持仓股', quantity=100, avg_cost=5.0, market='A'))
    s.commit()
    yield {'repo': repo, 'pool_id': pool.id}
    s.query(Signal).filter(Signal.symbol.in_(['TST010', 'TST011'])).delete()
    s.query(PoolChangeLog).filter(PoolChangeLog.pool_id == pool.id).delete()
    s.query(StockPool).filter(StockPool.id == pool.id).delete()
    s.query(PortfolioHolding).filter(PortfolioHolding.symbol == 'TST011').delete()
    s.query(Stock).filter(Stock.symbol.in_(['TST010', 'TST011'])).delete()
    s.commit()


class TestSignals:
    def test_signals_in_window(self, seeded):
        sigs = seeded['repo'].get_signals_between(date(2009, 1, 1), D)
        ours = [x for x in sigs if x['symbol'] == 'TST010']
        assert len(ours) == 2
        assert {x['action'] for x in ours} == {'buy', 'sell'}
        assert ours[0]['strategy_id'] == 'v13'


class TestPoolEvents:
    def test_pool_events_between(self, seeded):
        evts = seeded['repo'].get_pool_events_between(datetime(2009, 1, 1), datetime(2009, 1, 20, 23, 59))
        ours = [e for e in evts if e['symbol'] == 'TST010']
        assert len(ours) == 1
        assert ours[0]['action'] == 'add'

    def test_pool_events_after_for_replay(self, seeded):
        evts = seeded['repo'].get_pool_events_after(datetime(2009, 1, 20, 23, 59))
        ours = [e for e in evts if e['pool_id'] == seeded['pool_id']]
        assert len(ours) == 1 and ours[0]['action'] == 'remove'

    def test_pool_names(self, seeded):
        names = seeded['repo'].get_pool_names()
        assert names[seeded['pool_id']] == '测试池'

    def test_pool_members_now(self, seeded):
        members = seeded['repo'].get_pool_members_now()
        assert 'TST011' in members

    def test_has_pool_log_before(self, seeded):
        repo = seeded['repo']
        # 池内有 2009-01-19 的日志 → 2009-01-20 之前有记录
        assert repo.has_pool_log_before(datetime(2009, 1, 20, 23, 59)) is True
        # 2009-01-01 之前没有任何日志
        assert repo.has_pool_log_before(datetime(2009, 1, 1)) is False


class TestHoldings:
    def test_current_holding_symbols(self, seeded):
        assert 'TST011' in seeded['repo'].get_current_holding_symbols()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_heatmap_repository_events.py -v --no-cov
```
预期：AttributeError（方法不存在）全 FAIL

- [ ] **Step 3: 实现（追加到 heatmap_repository.py）**

在文件头部 import 区追加：

```python
from datetime import datetime

from adapters.outbound.repositories.pool_change_log_repository import PoolChangeLog
from adapters.outbound.repositories.stock_pool_repository import StockPool
from infrastructure.persistence.orm.models.portfolio import PortfolioHolding
from infrastructure.persistence.orm.models.signal import Signal
```

在 `HeatmapRepository` 类内追加：

```python
    def get_signals_between(self, start: date, end: date) -> list[dict]:
        """[start, end] 内的买/卖信号，按日期升序"""
        rows = (
            self.session.query(Signal.symbol, Signal.action, Signal.signal_date, Signal.strategy_id)
            .filter(
                Signal.signal_date >= start,
                Signal.signal_date <= end,
                Signal.action.in_(['buy', 'sell']),
            )
            .order_by(Signal.signal_date.asc())
            .all()
        )
        return [
            {'symbol': r.symbol, 'action': r.action, 'signal_date': r.signal_date, 'strategy_id': r.strategy_id}
            for r in rows
        ]

    def get_pool_events_between(self, start: datetime, end: datetime) -> list[dict]:
        """[start, end] 内的池调入/调出事件，按时间升序"""
        rows = (
            self.session.query(PoolChangeLog.pool_id, PoolChangeLog.action,
                               PoolChangeLog.symbol, PoolChangeLog.changed_at)
            .filter(
                PoolChangeLog.changed_at >= start,
                PoolChangeLog.changed_at <= end,
                PoolChangeLog.action.in_(['add', 'remove']),
            )
            .order_by(PoolChangeLog.changed_at.asc())
            .all()
        )
        return [
            {'pool_id': r.pool_id, 'action': r.action, 'symbol': r.symbol, 'changed_at': r.changed_at}
            for r in rows
        ]

    def get_pool_events_after(self, d: datetime) -> list[dict]:
        """d 之后的池事件，按时间倒序（用于从当前成员回放到 D 时点）"""
        rows = (
            self.session.query(PoolChangeLog.pool_id, PoolChangeLog.action,
                               PoolChangeLog.symbol, PoolChangeLog.changed_at)
            .filter(PoolChangeLog.changed_at > d, PoolChangeLog.action.in_(['add', 'remove']))
            .order_by(PoolChangeLog.changed_at.desc())
            .all()
        )
        return [
            {'pool_id': r.pool_id, 'action': r.action, 'symbol': r.symbol, 'changed_at': r.changed_at}
            for r in rows
        ]

    def get_pool_names(self) -> dict[int, str]:
        return {p.id: p.name for p in self.session.query(StockPool.id, StockPool.name).all()}

    def get_pool_members_now(self) -> set[str]:
        """当前全部动态池成员（members JSON 兼容 list[str] / list[dict] / dict 三种形态）"""
        members: set[str] = set()
        for pool in self.session.query(StockPool).all():
            raw = pool.members or []
            if isinstance(raw, dict):
                raw = raw.get('symbols', [])
            for item in raw:
                if isinstance(item, str):
                    members.add(item)
                elif isinstance(item, dict) and item.get('symbol'):
                    members.add(item['symbol'])
        return members

    def has_pool_log_before(self, d: datetime) -> bool:
        """d（含）之前是否存在任何池变更日志（spec §4.3：无则 D 时点池成员不可知 → scope 退化）"""
        return (
            self.session.query(PoolChangeLog.id)
            .filter(PoolChangeLog.changed_at <= d)
            .first()
            is not None
        )

    def get_current_holding_symbols(self) -> set[str]:
        """当前持仓（quantity > 0）股票代码"""
        rows = (
            self.session.query(PortfolioHolding.symbol)
            .filter(PortfolioHolding.quantity > 0)
            .all()
        )
        return {r[0] for r in rows}
```

- [ ] **Step 4: 运行确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_heatmap_repository_events.py -v --no-cov
```
预期：7 个测试全 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/outbound/repositories/heatmap_repository.py quantsys-v2/tests/repositories/test_heatmap_repository_events.py
git commit -m "feat(heatmap): HeatmapRepository 信号/池事件/持仓/日志存在性查询"
```

---

## Task 3: HeatmapService — 聚合逻辑与 stance 推导

**Files:**
- Create: `quantsys-v2/application/services/heatmap_service.py`
- Test: `quantsys-v2/tests/services/test_heatmap_service.py`

**核心逻辑（供 Step 3 实现参考的完整算法）：**

1. `window` 校验 ∈ (1, 5, 20)，否则 `{'success': False, 'error': ...}`
2. anchor：`date` 参数（`YYYY-MM-DD`）或今天 → `get_last_trade_date_on_or_before` 对齐；返回 None → 空数据响应
3. `dates = get_trade_dates_from(anchor, window+1)`；`d0=dates[0]`，`dn=dates[min(window, len-1)]`，`partial = len(dates) < window+1`
4. lookback_start = d0 − 30 天（日历日，spec §4.3）
5. in_scope = 信号符号 ∪ 持仓 ∪ pool_members_at_D（回放：从 members_now 出发，倒序遍历 d0 之后的事件：add→discard、remove→add；**d0 之前无任何池日志 → 成员置空并 `scope_degraded=True`**）
6. scope 股票 meta → 行业集合（跳过空 industry）→ `get_stocks_meta_by_industries` 得全宇宙 → `get_window_closes`
7. 每股 `change_pct = (close_dn - close_d0) / close_d0 * 100`；缺任一端点或 close_d0==0 → excluded_count+1，不入图
8. 行业 `change_pct` = 成员 change_pct 的 market_cap 加权（权重缺失/≤0 时按 1 计）
9. stance：行业内 in_scope 股票的 (buy 信号数 + add 事件数) vs (sell 信号数 + remove 事件数)：净正 bullish、净负 bearish、否则 neutral
10. 行业按总市值降序、行业内股票按 market_cap 降序

- [ ] **Step 1: 写失败测试**

```python
# quantsys-v2/tests/services/test_heatmap_service.py
"""HeatmapService 聚合逻辑测试（真实 quant_test DB，日期取 2009 年避免冲突）"""
from datetime import date, datetime

import pytest

from application.services.heatmap_service import HeatmapService
from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
from adapters.outbound.repositories.pool_change_log_repository import PoolChangeLog
from adapters.outbound.repositories.stock_pool_repository import StockPool
from infrastructure.persistence.orm.models.portfolio import PortfolioHolding
from infrastructure.persistence.orm.models.signal import Signal
from infrastructure.persistence.orm.models.stock import DailyKline, Stock

D0, D1 = date(2009, 2, 2), date(2009, 2, 3)   # 周一/周二，window=1


@pytest.fixture
def seeded():
    repo = HeatmapRepository()
    s = repo.session
    stocks = [
        Stock(symbol='TST100', name='买信号股', industry='测试半导体', market='A', market_cap=100.0),
        Stock(symbol='TST101', name='池外参照股', industry='测试半导体', market='A', market_cap=50.0),
        Stock(symbol='TST102', name='停牌股', industry='测试半导体', market='A', market_cap=10.0),
        Stock(symbol='TST103', name='持仓股', industry='测试白酒', market='A', market_cap=200.0),
    ]
    s.add_all(stocks)
    klines = []
    for sym, c0, c1 in [('TST100', 10.0, 11.0), ('TST101', 20.0, 19.0), ('TST103', 5.0, 5.5)]:
        klines += [
            DailyKline(symbol=sym, trade_date=D0, open=c0, high=c0, low=c0, close=c0, volume=1, amount=1),
            DailyKline(symbol=sym, trade_date=D1, open=c1, high=c1, low=c1, close=c1, volume=1, amount=1),
        ]
    # TST102 只有 d0 没有 dn → 应被剔除
    klines.append(DailyKline(symbol='TST102', trade_date=D0, open=1, high=1, low=1, close=8.0, volume=1, amount=1))
    s.add_all(klines)
    s.add(Signal(symbol='TST100', name='买信号股', signal_date=date(2009, 1, 30),
                 action='buy', strategy_id='v13', price=1.0, confidence=0.8))
    pool = StockPool(name='回放池', pool_type='dynamic', members=['TST100'])
    s.add(pool)
    s.flush()
    # D0 之前的日志：保证 has_pool_log_before 为 True（否则 scope 退化）
    s.add(PoolChangeLog(pool_id=pool.id, changed_at=datetime(2009, 1, 28, 10, 0),
                        action='add', symbol='TST100', reason='D前调入'))
    # D 之后调入 TST100 → 回放后 D 时点不在池内（但信号仍使其 in_scope）
    s.add(PoolChangeLog(pool_id=pool.id, changed_at=datetime(2009, 2, 10, 10, 0),
                        action='add', symbol='TST100', reason='D后调入'))
    s.add(PortfolioHolding(symbol='TST103', name='持仓股', quantity=100, avg_cost=5.0, market='A'))
    s.commit()
    svc = HeatmapService()
    yield svc
    syms = ['TST100', 'TST101', 'TST102', 'TST103']
    s.query(DailyKline).filter(DailyKline.symbol.in_(syms)).delete()
    s.query(Signal).filter(Signal.symbol.in_(syms)).delete()
    s.query(PoolChangeLog).filter(PoolChangeLog.pool_id == pool.id).delete()
    s.query(StockPool).filter(StockPool.id == pool.id).delete()
    s.query(PortfolioHolding).filter(PortfolioHolding.symbol.in_(syms)).delete()
    s.query(Stock).filter(Stock.symbol.in_(syms)).delete()
    s.commit()


def _industry(data, name):
    return next((i for i in data['industries'] if i['name'] == name), None)


class TestGetHeatmap:
    def test_window_validation(self, seeded):
        r = seeded.get_heatmap(date='2009-02-02', window=7)
        assert r['success'] is False

    def test_basic_aggregation(self, seeded):
        r = seeded.get_heatmap(date='2009-02-02', window=1)
        assert r['success'] is True
        d = r['data']
        assert d['date'] == '2009-02-02'
        assert d['actual_end_date'] == '2009-02-03'
        semi = _industry(d, '测试半导体')
        assert semi is not None
        by_symbol = {s['symbol']: s for s in semi['stocks']}
        # 涨跌幅
        assert by_symbol['TST100']['change_pct'] == pytest.approx(10.0)
        assert by_symbol['TST101']['change_pct'] == pytest.approx(-5.0)
        # in_scope 口径：信号股 in_scope，池外参照股不 in_scope
        assert by_symbol['TST100']['in_scope'] is True
        assert by_symbol['TST101']['in_scope'] is False
        # 停牌剔除
        assert 'TST102' not in by_symbol
        assert d['excluded_count'] >= 1
        # 信号透传
        assert by_symbol['TST100']['signals'][0]['type'] == 'buy'
        assert by_symbol['TST100']['signals'][0]['strategy'] == 'v13'
        # D 前有池日志 → 未退化
        assert d['scope_degraded'] is False

    def test_holding_makes_in_scope_and_industry_present(self, seeded):
        r = seeded.get_heatmap(date='2009-02-02', window=1)
        liquor = _industry(r['data'], '测试白酒')
        assert liquor is not None
        assert liquor['stocks'][0]['symbol'] == 'TST103'
        assert liquor['stocks'][0]['in_scope'] is True

    def test_stance_derivation(self, seeded):
        r = seeded.get_heatmap(date='2009-02-02', window=1)
        semi = _industry(r['data'], '测试半导体')
        # 1 个 buy 信号、无 sell/remove → bullish
        assert semi['agent_stance'] == 'bullish'
        liquor = _industry(r['data'], '测试白酒')
        assert liquor['agent_stance'] == 'neutral'

    def test_partial_window(self, seeded):
        # window=20 但 2009-02-03 之后（对测试符号）无数据；
        # 若全表更晚日期存在则 dn 会更晚——断言结构而非具体日期
        r = seeded.get_heatmap(date='2009-02-02', window=20)
        assert r['success'] is True
        assert r['data']['window'] == 20
        assert 'partial' in r['data'] and 'actual_end_date' in r['data']

    def test_date_alignment_non_trade_day(self, seeded):
        # 2009-02-01 是周日 → 对齐到之前最近交易日（未必是 D0，取决于全表数据，只断言成功且结构齐）
        r = seeded.get_heatmap(date='2009-02-01', window=1)
        assert r['success'] is True
        assert r['data']['date'] <= '2009-02-01'

    def test_empty_when_no_klines(self, seeded):
        r = seeded.get_heatmap(date='1990-01-01', window=1)
        assert r['success'] is True
        assert r['data']['industries'] == []


@pytest.fixture
def seeded_no_pool_log():
    """只有池成员、无任何池变更日志 → 无法回放 → scope_degraded + 空结果"""
    repo = HeatmapRepository()
    s = repo.session
    s.add(Stock(symbol='TST200', name='无日志股', industry='测试无日志', market='A', market_cap=10.0))
    s.add_all([
        DailyKline(symbol='TST200', trade_date=D0, open=1, high=1, low=1, close=10.0, volume=1, amount=1),
        DailyKline(symbol='TST200', trade_date=D1, open=1, high=1, low=1, close=11.0, volume=1, amount=1),
    ])
    pool = StockPool(name='无日志池', pool_type='dynamic', members=['TST200'])
    s.add(pool)
    s.commit()
    yield HeatmapService()
    s.query(DailyKline).filter(DailyKline.symbol == 'TST200').delete()
    s.query(StockPool).filter(StockPool.id == pool.id).delete()
    s.query(Stock).filter(Stock.symbol == 'TST200').delete()
    s.commit()


class TestScopeDegraded:
    def test_no_pool_log_degrades_scope(self, seeded_no_pool_log):
        r = seeded_no_pool_log.get_heatmap(date='2009-02-02', window=1)
        assert r['success'] is True
        d = r['data']
        # 退化后 in_scope 为空（无信号/持仓）→ 行业为空，且标记 degraded
        assert d['scope_degraded'] is True
        assert d['industries'] == []
```

- [ ] **Step 2: 运行确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/test_heatmap_service.py -v --no-cov
```
预期：ImportError 全 FAIL

- [ ] **Step 3: 实现 HeatmapService**

```python
# quantsys-v2/application/services/heatmap_service.py
"""热力图聚合服务 — agent 判断 × 市场实际走势的可视化校验数据源（纯本地 DB，无外部行情调用）"""
from datetime import date, datetime, time, timedelta
from typing import Optional

import structlog

VALID_WINDOWS = (1, 5, 20)
LOOKBACK_DAYS = 30  # spec §4.3：信号/池事件回看窗口（日历日）


class HeatmapService:
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self._repo = None

    @property
    def repo(self):
        """延迟初始化避免循环 import（与 MarketDataService 同模式）"""
        if self._repo is None:
            from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
            self._repo = HeatmapRepository()
        return self._repo

    def get_heatmap(self, date: Optional[str] = None, window: int = 5) -> dict:
        try:
            if window not in VALID_WINDOWS:
                return {'success': False, 'error': f'window 必须是 {VALID_WINDOWS} 之一'}
            anchor = self._resolve_anchor(date)
            if anchor is None:
                return {'success': True, 'data': self._empty_data(date, window)}

            dates = self.repo.get_trade_dates_from(anchor, window + 1)
            d0 = dates[0]
            dn = dates[min(window, len(dates) - 1)]
            partial = len(dates) < window + 1

            lookback_start = d0 - timedelta(days=LOOKBACK_DAYS)
            signals = self.repo.get_signals_between(lookback_start, d0)
            pool_events = self.repo.get_pool_events_between(
                datetime.combine(lookback_start, time.min),
                datetime.combine(d0, time.max),
            )
            pool_names = self.repo.get_pool_names()
            holdings = self.repo.get_current_holding_symbols()
            members_at_d, scope_degraded = self._replay_pool_members(d0)

            in_scope = {s['symbol'] for s in signals} | holdings | members_at_d

            scope_meta = self.repo.get_stocks_meta(sorted(in_scope))
            industries = sorted({m['industry'] for m in scope_meta.values() if m['industry']})
            if not industries:
                return {'success': True, 'data': self._empty_data(d0.isoformat(), window, scope_degraded)}
            universe_meta = self.repo.get_stocks_meta_by_industries(industries)
            closes = self.repo.get_window_closes(sorted(universe_meta), d0, dn)

            signals_by_symbol = self._group_signals(signals)
            events_by_symbol = self._group_pool_events(pool_events, pool_names)

            data = self._build_data(
                d0=d0, dn=dn, window=window, partial=partial,
                scope_degraded=scope_degraded,
                universe_meta=universe_meta, in_scope=in_scope,
                closes=closes,
                signals_by_symbol=signals_by_symbol,
                events_by_symbol=events_by_symbol,
                pool_events=pool_events,
                signals=signals,
            )
            return {'success': True, 'data': data}
        except Exception as e:
            self.logger.error("heatmap_aggregation_failed", error=str(e))
            return {'success': False, 'error': f'热力图聚合失败: {e}'}

    # ---- 内部方法 ----

    def _resolve_anchor(self, date_arg: Optional[str]) -> Optional[date]:
        target = date.fromisoformat(date_arg) if date_arg else date.today()
        return self.repo.get_last_trade_date_on_or_before(target)

    def _replay_pool_members(self, d0: date) -> tuple[set[str], bool]:
        """回放 d0 时点池成员：从当前成员倒序撤销 d0 之后的事件（add→剔除，remove→加回）。
        spec §4.3：d0 之前无任何池日志 → 池历史不可知 → 返回空集合并标记 degraded
        （in_scope 退化为「信号+持仓」口径）。"""
        cutoff = datetime.combine(d0, time.max)
        if not self.repo.has_pool_log_before(cutoff):
            return set(), True
        members = self.repo.get_pool_members_now()
        for evt in self.repo.get_pool_events_after(cutoff):
            if evt['action'] == 'add':
                members.discard(evt['symbol'])
            elif evt['action'] == 'remove':
                members.add(evt['symbol'])
        return members, False

    @staticmethod
    def _group_signals(signals: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for s in signals:
            grouped.setdefault(s['symbol'], []).append({
                'type': s['action'],
                'date': s['signal_date'].isoformat(),
                'strategy': s['strategy_id'],
            })
        return grouped

    @staticmethod
    def _group_pool_events(events: list[dict], pool_names: dict[int, str]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for e in events:
            grouped.setdefault(e['symbol'], []).append({
                'action': e['action'],
                'pool': pool_names.get(e['pool_id'], str(e['pool_id'])),
                'date': e['changed_at'].date().isoformat(),
            })
        return grouped

    def _build_data(self, *, d0, dn, window, partial, scope_degraded,
                    universe_meta, in_scope, closes,
                    signals_by_symbol, events_by_symbol, pool_events, signals) -> dict:
        excluded = 0
        industries_map: dict[str, list[dict]] = {}
        for symbol, meta in universe_meta.items():
            c = closes.get(symbol, {})
            c0, cn = c.get('close_d0'), c.get('close_dn')
            if not c0 or cn is None:
                excluded += 1
                continue
            stock = {
                'symbol': symbol,
                'name': meta['name'],
                'change_pct': round((cn - c0) / c0 * 100, 2),
                'market_cap': meta['market_cap'] or 0,
                'in_scope': symbol in in_scope,
            }
            if symbol in signals_by_symbol:
                stock['signals'] = signals_by_symbol[symbol]
            if symbol in events_by_symbol:
                stock['pool_events'] = events_by_symbol[symbol]
            industries_map.setdefault(meta['industry'], []).append(stock)

        industries = []
        for name, stocks in industries_map.items():
            total_w = sum(max(s['market_cap'], 0) or 1 for s in stocks)
            weighted = sum(
                s['change_pct'] * (max(s['market_cap'], 0) or 1) for s in stocks
            ) / total_w if total_w else 0.0
            industries.append({
                'name': name,
                'change_pct': round(weighted, 2),
                'agent_stance': self._derive_stance(name, universe_meta, in_scope, signals, pool_events),
                'stocks': sorted(stocks, key=lambda s: s['market_cap'], reverse=True),
            })
        industries.sort(key=lambda i: sum(s['market_cap'] for s in i['stocks']), reverse=True)

        return {
            'date': d0.isoformat(),
            'window': window,
            'actual_end_date': dn.isoformat(),
            'partial': partial,
            'scope_degraded': scope_degraded,
            'excluded_count': excluded,
            'industries': industries,
        }

    @staticmethod
    def _derive_stance(industry: str, universe_meta, in_scope, signals, pool_events) -> str:
        """spec §4.4：行业内 in_scope 股票的 (buy + add) vs (sell + remove) 净方向"""
        industry_symbols = {
            sym for sym, m in universe_meta.items()
            if m['industry'] == industry and sym in in_scope
        }
        pos = sum(1 for s in signals if s['symbol'] in industry_symbols and s['action'] == 'buy')
        pos += sum(1 for e in pool_events if e['symbol'] in industry_symbols and e['action'] == 'add')
        neg = sum(1 for s in signals if s['symbol'] in industry_symbols and s['action'] == 'sell')
        neg += sum(1 for e in pool_events if e['symbol'] in industry_symbols and e['action'] == 'remove')
        if pos > neg:
            return 'bullish'
        if neg > pos:
            return 'bearish'
        return 'neutral'

    @staticmethod
    def _empty_data(date_str: Optional[str], window: int, scope_degraded: bool = False) -> dict:
        return {
            'date': date_str,
            'window': window,
            'actual_end_date': None,
            'partial': False,
            'scope_degraded': scope_degraded,
            'excluded_count': 0,
            'industries': [],
            'message': '该日期无可用 K 线数据或 agent 相关行业为空',
        }


heatmap_service = HeatmapService()
```

- [ ] **Step 4: 运行确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/test_heatmap_service.py -v --no-cov
```
预期：8 个测试全 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/heatmap_service.py quantsys-v2/tests/services/test_heatmap_service.py
git commit -m "feat(heatmap): HeatmapService 窗口聚合+in_scope口径+stance推导"
```

---

## Task 4: FastAPI 路由 + 契约测试

**Files:**
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/routes/market_data_async.py`
- Test: `quantsys-v2/tests/api/test_market_heatmap_route.py`

- [ ] **Step 1: 写失败测试**

```python
# quantsys-v2/tests/api/test_market_heatmap_route.py
"""GET /api/market/heatmap FastAPI 路由契约测试（TestClient + mock service 层）"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _ok_payload():
    return {
        'success': True,
        'data': {
            'date': '2026-07-24', 'window': 5, 'actual_end_date': '2026-07-31',
            'partial': False, 'scope_degraded': False, 'excluded_count': 0,
            'industries': [{
                'name': '半导体', 'change_pct': 4.2, 'agent_stance': 'bullish',
                'stocks': [{'symbol': '688981', 'name': '中芯国际', 'change_pct': 8.2,
                            'market_cap': 4.5e11, 'in_scope': True,
                            'signals': [{'type': 'buy', 'date': '2026-07-23', 'strategy': 'v13'}]}],
            }],
        },
    }


class TestMarketHeatmapRoute:
    def test_success_camelcase_contract(self, client):
        with patch('application.services.heatmap_service.heatmap_service') as mock_svc:
            mock_svc.get_heatmap.return_value = _ok_payload()
            resp = client.get('/api/market/heatmap', params={'date': '2026-07-24', 'window': 5})
        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        data = body['data']
        # api_response 转 camelCase 的契约冻结
        assert data['actualEndDate'] == '2026-07-31'
        assert data['scopeDegraded'] is False
        assert data['excludedCount'] == 0
        stock = data['industries'][0]['stocks'][0]
        assert stock['changePct'] == 8.2
        assert stock['marketCap'] == 4.5e11
        assert stock['inScope'] is True
        assert data['industries'][0]['agentStance'] == 'bullish'

    def test_default_params(self, client):
        with patch('application.services.heatmap_service.heatmap_service') as mock_svc:
            mock_svc.get_heatmap.return_value = _ok_payload()
            resp = client.get('/api/market/heatmap')
        assert resp.status_code == 200
        mock_svc.get_heatmap.assert_called_once_with(date=None, window=5)

    def test_service_error_returns_400(self, client):
        with patch('application.services.heatmap_service.heatmap_service') as mock_svc:
            mock_svc.get_heatmap.return_value = {'success': False, 'error': 'window 必须是 (1, 5, 20) 之一'}
            resp = client.get('/api/market/heatmap', params={'window': 7})
        assert resp.status_code == 400
        assert resp.json()['success'] is False
```

注意：mock 打在 `application.services.heatmap_service.heatmap_service`（模块级单例），路由必须以 `from application.services.heatmap_service import heatmap_service` 在**函数体内**延迟 import（与 market_data_async.py 现有路由同模式），patch 才生效。

- [ ] **Step 2: 运行确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/api/test_market_heatmap_route.py -v --no-cov
```
预期：404 全 FAIL

- [ ] **Step 3: 实现路由**

在 `quantsys-v2/adapters/inbound/fastapi_app/routes/market_data_async.py` 中，紧跟 `get_sectors_v2` 之后添加：

```python
@router.get('/api/market/heatmap')
@handle_api_error
def get_market_heatmap(date: Optional[str] = Query(None), window: int = Query(5)):
    """市场热力图 - 行业×个股验证窗涨跌 + agent 判断痕迹叠加（本地 DB 聚合）"""
    from application.services.heatmap_service import heatmap_service
    result = heatmap_service.get_heatmap(date=date, window=window)
    if not result.get('success', False):
        return error_response(result, 400)
    return api_response(result.get('data', {}))
```

确认文件顶部已有 `Optional`、`Query`、`api_response`、`error_response`、`handle_api_error` 的 import（该文件现有，无需新增）。router 已在 `main.py` 注册，无需改注册代码。**不要**在 `adapters/inbound/api/routes/`（Flask，已废弃）添加任何路由。

- [ ] **Step 4: 运行确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/api/test_market_heatmap_route.py -v --no-cov
```
预期：3 个测试全 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/inbound/fastapi_app/routes/market_data_async.py quantsys-v2/tests/api/test_market_heatmap_route.py
git commit -m "feat(heatmap): FastAPI 路由 GET /api/market/heatmap + camelCase 契约测试"
```

---

## Task 5: 前端类型 + adapter + API 方法

**Files:**
- Modify: `web-frontend/src/types/api.ts`
- Modify: `web-frontend/src/services/api/adapters.ts`
- Modify: `web-frontend/src/services/api/stock.ts`
- Test: `web-frontend/tests/unit/stock-heatmap.test.ts`（本任务先建 API 部分，Task 6 继续追加 verdict 测试）

- [ ] **Step 1: 写失败测试（API 契约部分）**

```ts
// web-frontend/tests/unit/stock-heatmap.test.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }
}))

const { apiClient } = await import('@/services/api/client')
const { stockApi } = await import('@/services/api/stock')
const mockedClient = vi.mocked(apiClient)

describe('stockApi.getHeatmap', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls heatmap endpoint with params', async () => {
    mockedClient.get.mockResolvedValueOnce({ industries: [] })
    await stockApi.getHeatmap({ date: '2026-07-24', window: 5 })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/market/heatmap', {
      params: { date: '2026-07-24', window: 5 }
    })
  })

  it('adapts backend camelCase payload and tolerates snake_case', async () => {
    mockedClient.get.mockResolvedValueOnce({
      date: '2026-07-24', window: 5, actualEndDate: '2026-07-31',
      partial: false, scopeDegraded: false, excludedCount: 1,
      industries: [{
        name: '半导体', changePct: 4.2, agentStance: 'bullish',
        stocks: [{
          symbol: '688981', name: '中芯国际', change_pct: 8.2,
          market_cap: 4.5e11, in_scope: true,
          signals: [{ type: 'buy', date: '2026-07-23', strategy: 'v13' }]
        }]
      }]
    })
    const result = await stockApi.getHeatmap()
    expect(result.actualEndDate).toBe('2026-07-31')
    expect(result.excludedCount).toBe(1)
    const ind = result.industries[0]
    expect(ind.agentStance).toBe('bullish')
    const st = ind.stocks[0]
    expect(st.changePct).toBe(8.2)
    expect(st.marketCap).toBe(4.5e11)
    expect(st.inScope).toBe(true)
    expect(st.signals?.[0].type).toBe('buy')
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
cd web-frontend && npx vitest run tests/unit/stock-heatmap.test.ts
```
预期：FAIL（getHeatmap 不存在）

- [ ] **Step 3: 实现类型 + adapter + API 方法**

`web-frontend/src/types/api.ts` 末尾追加：

```ts
// ---- 市场热力图（/api/market/heatmap）----
export interface HeatmapSignal {
  type: 'buy' | 'sell'
  date: string
  strategy?: string
}

export interface HeatmapPoolEvent {
  action: 'add' | 'remove'
  pool: string
  date: string
}

export interface HeatmapStock {
  symbol: string
  name: string
  changePct: number
  marketCap: number
  inScope: boolean
  signals?: HeatmapSignal[]
  poolEvents?: HeatmapPoolEvent[]
}

export interface HeatmapIndustry {
  name: string
  changePct: number
  agentStance: 'bullish' | 'bearish' | 'neutral'
  stocks: HeatmapStock[]
}

export interface HeatmapResponse {
  date: string
  window: number
  actualEndDate: string | null
  partial: boolean
  scopeDegraded: boolean
  excludedCount: number
  industries: HeatmapIndustry[]
  message?: string
}

export interface HeatmapRequest {
  date?: string
  window?: number
}
```

`web-frontend/src/services/api/adapters.ts` 末尾追加：

```ts
import type { HeatmapResponse } from '@/types'

export function adaptHeatmap(response: any): HeatmapResponse {
  const raw = asData<any>(response) ?? {}
  const industries = Array.isArray(raw.industries) ? raw.industries : []
  return {
    date: raw.date ?? '',
    window: Number(raw.window ?? 5),
    actualEndDate: raw.actualEndDate ?? raw.actual_end_date ?? null,
    partial: Boolean(raw.partial),
    scopeDegraded: Boolean(raw.scopeDegraded ?? raw.scope_degraded),
    excludedCount: Number(raw.excludedCount ?? raw.excluded_count ?? 0),
    message: raw.message,
    industries: industries.map((ind: any) => ({
      name: ind.name ?? '',
      changePct: Number(ind.changePct ?? ind.change_pct ?? 0),
      agentStance: ind.agentStance ?? ind.agent_stance ?? 'neutral',
      stocks: (Array.isArray(ind.stocks) ? ind.stocks : []).map((s: any) => ({
        symbol: s.symbol ?? '',
        name: s.name ?? '',
        changePct: Number(s.changePct ?? s.change_pct ?? 0),
        marketCap: Number(s.marketCap ?? s.market_cap ?? 0),
        inScope: Boolean(s.inScope ?? s.in_scope),
        signals: s.signals,
        poolEvents: s.poolEvents ?? s.pool_events,
      })),
    })),
  }
}
```

`web-frontend/src/services/api/stock.ts`：在 `stockApi` 对象内（`getStocks` 之后）添加，并在文件顶部 import 处把 `adaptHeatmap` 加入 `./adapters` 的 import 列表、把 `HeatmapRequest, HeatmapResponse` 加入 `@/types` import：

```ts
  async getHeatmap(params?: HeatmapRequest): Promise<HeatmapResponse> {
    const response = await apiClient.get('/api/market/heatmap', {
      params: compactParams({ date: params?.date, window: params?.window })
    })
    return adaptHeatmap(response)
  },
```

- [ ] **Step 4: 运行确认通过**

```bash
cd web-frontend && npx vitest run tests/unit/stock-heatmap.test.ts
```
预期：2 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/types/api.ts web-frontend/src/services/api/adapters.ts web-frontend/src/services/api/stock.ts web-frontend/tests/unit/stock-heatmap.test.ts
git commit -m "feat(heatmap-web): Heatmap 类型 + adaptHeatmap + stockApi.getHeatmap"
```

---

## Task 6: 对错判定纯函数 verdict.ts

**Files:**
- Create: `web-frontend/src/views/StockHeatmap/verdict.ts`
- Test: `web-frontend/tests/unit/stock-heatmap.test.ts`（追加 describe）

- [ ] **Step 1: 追加失败测试**

在 `tests/unit/stock-heatmap.test.ts` 末尾追加：

```ts
const { judgeSignal, judgePoolEvent, judgeStance } = await import('@/views/StockHeatmap/verdict')

describe('verdict 对错判定', () => {
  it('买入信号涨=对，跌=错', () => {
    expect(judgeSignal('buy', 8.2)).toBe('right')
    expect(judgeSignal('buy', -4.4)).toBe('wrong')
  })

  it('卖出信号跌=对，涨=错', () => {
    expect(judgeSignal('sell', -3.1)).toBe('right')
    expect(judgeSignal('sell', 2.0)).toBe('wrong')
  })

  it('涨跌为 0 时不判', () => {
    expect(judgeSignal('buy', 0)).toBe('none')
  })

  it('池调入涨=对，池调出跌=对', () => {
    expect(judgePoolEvent('add', 1.5)).toBe('right')
    expect(judgePoolEvent('add', -1.5)).toBe('wrong')
    expect(judgePoolEvent('remove', -2.0)).toBe('right')
    expect(judgePoolEvent('remove', 2.0)).toBe('wrong')
  })

  it('行业 stance：看好且行业涨=对，回避且行业跌=对，neutral 不判', () => {
    expect(judgeStance('bullish', 4.2)).toBe('right')
    expect(judgeStance('bullish', -1.0)).toBe('wrong')
    expect(judgeStance('bearish', -5.0)).toBe('right')
    expect(judgeStance('bearish', 3.0)).toBe('wrong')
    expect(judgeStance('neutral', 9.9)).toBe('none')
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
cd web-frontend && npx vitest run tests/unit/stock-heatmap.test.ts
```
预期：FAIL（verdict 模块不存在）

- [ ] **Step 3: 实现 verdict.ts**

```ts
// web-frontend/src/views/StockHeatmap/verdict.ts
/** agent 判断对错判定（spec §5.3）：判断方向与验证窗实际涨跌是否同向 */

export type Verdict = 'right' | 'wrong' | 'none'

/** 买信号后涨=对；卖信号后跌=对；涨跌幅为 0 不判 */
export function judgeSignal(type: 'buy' | 'sell', changePct: number): Verdict {
  if (changePct === 0) return 'none'
  const up = changePct > 0
  return (type === 'buy') === up ? 'right' : 'wrong'
}

/** 调入后涨=对；调出后跌=对 */
export function judgePoolEvent(action: 'add' | 'remove', changePct: number): Verdict {
  if (changePct === 0) return 'none'
  const up = changePct > 0
  return (action === 'add') === up ? 'right' : 'wrong'
}

/** 看好且行业涨=对；回避且行业跌=对；neutral 不判 */
export function judgeStance(
  stance: 'bullish' | 'bearish' | 'neutral',
  industryChangePct: number
): Verdict {
  if (stance === 'neutral' || industryChangePct === 0) return 'none'
  const up = industryChangePct > 0
  return (stance === 'bullish') === up ? 'right' : 'wrong'
}
```

- [ ] **Step 4: 运行确认通过**

```bash
cd web-frontend && npx vitest run tests/unit/stock-heatmap.test.ts
```
预期：全部 PASS（2 个 API + 5 个 verdict）

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/views/StockHeatmap/verdict.ts web-frontend/tests/unit/stock-heatmap.test.ts
git commit -m "feat(heatmap-web): verdict 对错判定纯函数（信号/池事件/行业stance）"
```

---

## Task 7: treemap option 构建器 chart-options.ts

**Files:**
- Create: `web-frontend/src/views/StockHeatmap/chart-options.ts`
- Test: `web-frontend/tests/unit/stock-heatmap-options.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
// web-frontend/tests/unit/stock-heatmap-options.test.ts
import { describe, expect, it } from 'vitest'
import type { HeatmapResponse } from '@/types'
import { buildHeatmapOption, changeColor } from '@/views/StockHeatmap/chart-options'

function fixture(): HeatmapResponse {
  return {
    date: '2026-07-24', window: 5, actualEndDate: '2026-07-31',
    partial: false, scopeDegraded: false, excludedCount: 0,
    industries: [{
      name: '半导体', changePct: 4.2, agentStance: 'bullish',
      stocks: [
        { symbol: '688981', name: '中芯国际', changePct: 8.2, marketCap: 4.5e11, inScope: true,
          signals: [{ type: 'buy', date: '2026-07-23', strategy: 'v13' }] },
        { symbol: '300999', name: '池外股', changePct: 1.1, marketCap: 2e10, inScope: false },
      ],
    }],
  }
}

describe('changeColor', () => {
  it('红涨绿跌', () => {
    const up = changeColor(5)
    const down = changeColor(-5)
    expect(up).not.toBe(down)
    // 涨为红色系（R 通道高），跌为绿色系（G 通道高）
    expect(up).toMatch(/192|#c0|rgb\(19/)
    expect(down).toMatch(/39, 174|#27|rgb\(39/)
  })

  it('池外股票低饱和灰化', () => {
    expect(changeColor(5, false)).not.toBe(changeColor(5, true))
  })
})

describe('buildHeatmapOption', () => {
  it('行业→个股两级 treemap 数据', () => {
    const option = buildHeatmapOption({ data: fixture(), overlays: { signals: true, pool: true, industry: true } })
    const series = (option.series as any[])[0]
    expect(series.type).toBe('treemap')
    const industryNode = series.data[0]
    expect(industryNode.name).toContain('半导体')
    expect(industryNode.children).toHaveLength(2)
    const stock = industryNode.children[0]
    expect(stock.name).toContain('中芯国际')
    expect(stock.value).toBe(4.5e11)
  })

  it('信号叠加开启时 in_scope 股票 label 带角标，关闭时不带', () => {
    const on = buildHeatmapOption({ data: fixture(), overlays: { signals: true, pool: true, industry: true } })
    const off = buildHeatmapOption({ data: fixture(), overlays: { signals: false, pool: false, industry: false } })
    const stockOn = (on.series as any[])[0].data[0].children[0]
    const stockOff = (off.series as any[])[0].data[0].children[0]
    expect(stockOn.name).toContain('▲')
    expect(stockOff.name).not.toContain('▲')
  })

  it('行业 stance 叠加开启时 bullish 行业节点带金色边框', () => {
    const option = buildHeatmapOption({ data: fixture(), overlays: { signals: false, pool: false, industry: true } })
    const industryNode = (option.series as any[])[0].data[0]
    expect(industryNode.itemStyle.borderColor).toBe('#d4a017')
  })

  it('空数据返回空 series', () => {
    const empty = { ...fixture(), industries: [] }
    const option = buildHeatmapOption({ data: empty, overlays: { signals: true, pool: true, industry: true } })
    expect((option.series as any[])[0].data).toHaveLength(0)
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
cd web-frontend && npx vitest run tests/unit/stock-heatmap-options.test.ts
```
预期：FAIL（模块不存在）

- [ ] **Step 3: 实现 chart-options.ts**

```ts
// web-frontend/src/views/StockHeatmap/chart-options.ts
/** 热力图 treemap option 构建（纯函数，spec §5.2 视觉编码） */
import type { EChartsOption } from 'echarts'
import type { HeatmapIndustry, HeatmapResponse, HeatmapStock } from '@/types'
import { judgePoolEvent, judgeSignal } from './verdict'

export interface HeatmapOverlays {
  signals: boolean
  pool: boolean
  industry: boolean
}

export interface BuildHeatmapOptionParams {
  data: HeatmapResponse
  overlays: HeatmapOverlays
}

const STANCE_BORDER: Record<string, string> = {
  bullish: '#d4a017',   // 金框 = 看好
  bearish: '#888888',   // 灰框 = 回避
  neutral: '#555555',
}

/** 红涨绿跌发散色（±10% 封顶取深浅）；池外股票低饱和灰化 */
export function changeColor(pct: number, inScope = true): string {
  const t = Math.min(Math.abs(pct), 10) / 10
  if (!inScope) {
    return pct >= 0 ? 'rgba(192, 57, 43, 0.18)' : 'rgba(39, 174, 96, 0.18)'
  }
  const alpha = 0.3 + 0.7 * t
  return pct >= 0 ? `rgba(192, 57, 43, ${alpha})` : `rgba(39, 174, 96, ${alpha})`
}

function latestSignal(stock: HeatmapStock) {
  return stock.signals?.length ? stock.signals[stock.signals.length - 1] : undefined
}

function stockLabel(stock: HeatmapStock, overlays: HeatmapOverlays): string {
  let label = `${stock.name}\n${stock.changePct > 0 ? '+' : ''}${stock.changePct}%`
  if (!stock.inScope) return label
  if (overlays.signals) {
    const sig = latestSignal(stock)
    if (sig) label += sig.type === 'buy' ? ' ▲' : ' ▼'
  }
  if (overlays.pool && stock.poolEvents?.length) {
    label += stock.poolEvents[stock.poolEvents.length - 1].action === 'add' ? ' ●' : ' ○'
  }
  return label
}

function buildStockNode(stock: HeatmapStock, overlays: HeatmapOverlays) {
  const sig = overlays.signals && stock.inScope ? latestSignal(stock) : undefined
  const sigVerdict = sig ? judgeSignal(sig.type, stock.changePct) : 'none'
  const poolVerdict = overlays.pool && stock.poolEvents?.length
    ? judgePoolEvent(stock.poolEvents[stock.poolEvents.length - 1].action, stock.changePct)
    : 'none'
  return {
    name: stockLabel(stock, overlays),
    value: Math.max(stock.marketCap, 1),
    symbol: stock.symbol,
    raw: stock,
    verdicts: { signal: sigVerdict, pool: poolVerdict },
    itemStyle: {
      color: changeColor(stock.changePct, stock.inScope),
      borderColor: sigVerdict === 'right' || poolVerdict === 'right'
        ? '#ffffff'
        : sigVerdict === 'wrong' || poolVerdict === 'wrong'
          ? '#111111'
          : 'rgba(255,255,255,0.4)',
      borderWidth: stock.inScope && (sig || stock.poolEvents?.length) ? 3 : 1,
    },
  }
}

function buildIndustryNode(ind: HeatmapIndustry, overlays: HeatmapOverlays) {
  return {
    name: `${ind.name} ${ind.changePct > 0 ? '+' : ''}${ind.changePct}%`,
    value: ind.stocks.reduce((sum, s) => sum + Math.max(s.marketCap, 1), 0),
    itemStyle: {
      borderColor: overlays.industry ? STANCE_BORDER[ind.agentStance] : '#555555',
      borderWidth: overlays.industry && ind.agentStance !== 'neutral' ? 3 : 1,
      gapWidth: 2,
    },
    children: ind.stocks.map((s) => buildStockNode(s, overlays)),
  }
}

export function buildHeatmapOption({ data, overlays }: BuildHeatmapOptionParams): EChartsOption {
  return {
    animation: false,
    tooltip: {
      formatter: (info: any) => {
        const stock = info?.data?.raw as HeatmapStock | undefined
        if (!stock) return String(info?.name ?? '')
        const lines = [
          `<b>${stock.name} (${stock.symbol})</b>`,
          `验证窗涨跌: ${stock.changePct > 0 ? '+' : ''}${stock.changePct}%`,
          `市值: ${(stock.marketCap / 1e8).toFixed(1)} 亿`,
        ]
        if (stock.inScope) {
          stock.signals?.forEach((s) =>
            lines.push(`信号: ${s.type === 'buy' ? '买入' : '卖出'} @ ${s.date} (${s.strategy ?? '-'}) → ${judgeSignal(s.type, stock.changePct) === 'right' ? '✅对' : judgeSignal(s.type, stock.changePct) === 'wrong' ? '❌错' : '—'}`))
          stock.poolEvents?.forEach((e) =>
            lines.push(`池事件: ${e.action === 'add' ? '调入' : '调出'}「${e.pool}」@ ${e.date} → ${judgePoolEvent(e.action, stock.changePct) === 'right' ? '✅对' : judgePoolEvent(e.action, stock.changePct) === 'wrong' ? '❌错' : '—'}`))
        } else {
          lines.push('<i>池外参照</i>')
        }
        return lines.join('<br/>')
      },
    },
    series: [{
      type: 'treemap',
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      width: '100%',
      height: '100%',
      label: { show: true, fontSize: 11, color: '#fff' },
      upperLabel: { show: true, height: 22, color: '#333', fontWeight: 'bold' },
      data: data.industries.map((ind) => buildIndustryNode(ind, overlays)),
    }],
  }
}
```

注意：测试断言 `changeColor(5)` 匹配 `/192|#c0|rgb\(19/` — 实现返回 `rgba(192, 57, 43, ...)` 含 "192" ✓；`changeColor(-5)` 返回含 "39, 174" ✓。

- [ ] **Step 4: 运行确认通过**

```bash
cd web-frontend && npx vitest run tests/unit/stock-heatmap-options.test.ts
```
预期：6 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/views/StockHeatmap/chart-options.ts web-frontend/tests/unit/stock-heatmap-options.test.ts
git commit -m "feat(heatmap-web): treemap option 构建器（红涨绿跌/池外灰化/叠加标记）"
```

---

## Task 8: StockHeatmap 视图 + 路由 + 菜单

**Files:**
- Create: `web-frontend/src/views/StockHeatmap/index.vue`
- Modify: `web-frontend/src/router/index.ts`（OpportunityRadar 路由之后插入）
- Modify: `web-frontend/src/components/layout/MainLayout.vue`（研究分析组内）

- [ ] **Step 1: 创建视图**

```vue
<!-- web-frontend/src/views/StockHeatmap/index.vue -->
<template>
  <div class="stock-heatmap" v-loading="pageLoading">
    <div class="page-header">
      <h2 class="page-title">市场热力图</h2>
      <p class="page-subtitle">agent 判断 × 验证窗实际涨跌 — 白框红=判断对，白框绿=判断错</p>
      <div class="header-actions">
        <el-date-picker
          v-model="queryDate"
          type="date"
          value-format="YYYY-MM-DD"
          :clearable="false"
          placeholder="判断日"
          @change="loadData"
        />
        <el-radio-group v-model="windowDays" @change="loadData">
          <el-radio-button :value="1">1日</el-radio-button>
          <el-radio-button :value="5">5日</el-radio-button>
          <el-radio-button :value="20">20日</el-radio-button>
        </el-radio-group>
        <el-checkbox-group v-model="overlayList" @change="renderChart">
          <el-checkbox value="signals">信号</el-checkbox>
          <el-checkbox value="pool">池调整</el-checkbox>
          <el-checkbox value="industry">行业判断</el-checkbox>
        </el-checkbox-group>
      </div>
    </div>

    <el-alert
      v-if="heatmap?.partial"
      type="warning"
      :closable="false"
      :title="`验证窗未满：实际数据到 ${heatmap.actualEndDate}，统计计入「待定」`"
    />
    <el-alert
      v-if="heatmap && queryDate && heatmap.date !== queryDate"
      type="info"
      :closable="false"
      :title="`所选日期非交易日，已对齐到 ${heatmap.date}`"
    />
    <el-alert
      v-if="heatmap?.scopeDegraded"
      type="info"
      :closable="false"
      title="池成员历史无法完整回放，in_scope 口径已退化为「信号+持仓」"
    />
    <el-alert
      v-if="heatmap && heatmap.excludedCount > 0"
      type="info"
      :closable="false"
      :title="`${heatmap.excludedCount} 只股票停牌/缺数据未显示`"
    />

    <div v-if="heatmap && heatmap.industries.length > 0" ref="chartWrapRef" class="chart-wrap">
      <div ref="chartRef" class="chart"></div>
    </div>
    <el-empty v-else-if="!pageLoading" description="该日期无热力图数据" />

    <div v-if="heatmap && heatmap.industries.length > 0" class="verdict-stats">
      <el-tag type="danger">判断对 {{ stats.right }}</el-tag>
      <el-tag type="success">判断错 {{ stats.wrong }}</el-tag>
      <el-tag type="info">待定 {{ stats.pending }}</el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useChart } from '@/composables/useChart'
import { stockApi } from '@/services/api'
import type { HeatmapResponse } from '@/types'
import { buildHeatmapOption } from './chart-options'
import { judgePoolEvent, judgeSignal, judgeStance } from './verdict'

const router = useRouter()
const { chartRef, chartInstance, setOption } = useChart()

const queryDate = ref<string>('')
const windowDays = ref<number>(5)
const overlayList = ref<string[]>(['signals', 'pool', 'industry'])
const heatmap = ref<HeatmapResponse | null>(null)
const pageLoading = ref(false)

const overlays = computed(() => ({
  signals: overlayList.value.includes('signals'),
  pool: overlayList.value.includes('pool'),
  industry: overlayList.value.includes('industry'),
}))

const stats = computed(() => {
  const acc = { right: 0, wrong: 0, pending: 0 }
  if (!heatmap.value) return acc
  const tally = (v: 'right' | 'wrong' | 'none') => {
    if (v === 'none') return
    if (heatmap.value?.partial) { acc.pending++; return }
    acc[v]++
  }
  for (const ind of heatmap.value.industries) {
    tally(judgeStance(ind.agentStance, ind.changePct))
    for (const s of ind.stocks) {
      if (!s.inScope) continue
      if (s.signals?.length) tally(judgeSignal(s.signals[s.signals.length - 1].type, s.changePct))
      if (s.poolEvents?.length) tally(judgePoolEvent(s.poolEvents[s.poolEvents.length - 1].action, s.changePct))
    }
  }
  return acc
})

async function loadData() {
  pageLoading.value = true
  try {
    heatmap.value = await stockApi.getHeatmap({
      date: queryDate.value || undefined,
      window: windowDays.value,
    })
    await nextTick()
    renderChart()
  } catch {
    ElMessage.error('获取热力图数据失败')
  } finally {
    pageLoading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !heatmap.value || heatmap.value.industries.length === 0) return
  setOption(buildHeatmapOption({ data: heatmap.value, overlays: overlays.value }), true)
  bindChartClick()
}

function bindChartClick() {
  const inst = chartInstance.value
  if (!inst) return
  inst.off('click')
  inst.on('click', (params: any) => {
    const symbol = params?.data?.raw?.symbol
    if (symbol) router.push(`/stocks/${symbol}`)
  })
}

loadData()
</script>

<style scoped>
.stock-heatmap { padding: 16px; display: flex; flex-direction: column; gap: 12px; height: 100%; }
.page-header { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.page-title { margin: 0; font-size: 20px; }
.page-subtitle { margin: 0; color: #888; font-size: 13px; flex-basis: 100%; }
.header-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.chart-wrap { flex: 1; min-height: 480px; }
.chart { width: 100%; height: 100%; min-height: 480px; }
.verdict-stats { display: flex; gap: 8px; }
</style>
```

注意：treemap option 里 `nodeClick: false` 只是禁用 ECharts 自带的下钻手势；点击跳 StockDetail 通过 `chartInstance.on('click')` 自定义实现（spec §5.4）。

- [ ] **Step 2: 加路由**

在 `web-frontend/src/router/index.ts` 中 OpportunityRadar 路由条目之后插入：

```ts
      {
        path: '/stock-heatmap',
        name: 'StockHeatmap',
        component: () => import(/* webpackChunkName: "stock-heatmap" */ '@/views/StockHeatmap/index.vue'),
        meta: { title: '市场热力图' }
      },
```

- [ ] **Step 3: 加菜单项**

在 `web-frontend/src/components/layout/MainLayout.vue` 的「研究分析」组（机会雷达菜单项之后）插入：

```html
        <el-menu-item index="/stock-heatmap">
          <el-icon><Grid /></el-icon>
          <span>市场热力图</span>
        </el-menu-item>
```

（`Grid` 图标在该文件已从 `@element-plus/icons-vue` import，无需新增 import；若构建报未使用/未定义则在 script 的 icons import 列表中补上 `Grid`。）

- [ ] **Step 4: 验证构建与既有测试**

```bash
cd web-frontend && npx vue-tsc --noEmit 2>&1 | tail -5
cd web-frontend && npx vitest run
cd web-frontend && npm run build 2>&1 | tail -5
```
预期：类型检查无新错误；既有测试保持基线（stock-heatmap 相关全 PASS，其余与基线一致）；build 成功。

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/views/StockHeatmap/index.vue web-frontend/src/router/index.ts web-frontend/src/components/layout/MainLayout.vue
git commit -m "feat(heatmap-web): StockHeatmap 视图 + 路由 + 研究分析菜单项"
```

---

## Task 9: 真实数据冒烟 + 全量回归

**Files:** 无新文件（验证任务）

- [ ] **Step 1: 后端真实 DB 冒烟（只读，不起服务）**

```bash
cd quantsys-v2 && PGDATABASE=quant_investment venv/bin/python -c "
from application.services.heatmap_service import heatmap_service
r = heatmap_service.get_heatmap(None, 5)
assert r['success'], r
d = r['data']
print('date:', d['date'], 'end:', d['actual_end_date'], 'partial:', d['partial'])
print('industries:', len(d['industries']), 'excluded:', d['excluded_count'], 'degraded:', d['scope_degraded'])
for ind in d['industries'][:3]:
    scoped = [s for s in ind['stocks'] if s['in_scope']]
    print(ind['name'], ind['change_pct'], ind['agent_stance'], f'stocks={len(ind[\"stocks\"])} scoped={len(scoped)}')
"
```
预期：成功返回；`date` 为最近已收盘交易日；若有 in_scope 股票则 industries 非空。
人工抽查：任选一只 in_scope 股票，用 `ds.kline.get_daily_klines(symbol, ...)` 或前端 StockDetail 页核对 change_pct。

边界预期：若当前 agent 无信号/持仓/池（新环境），industries 为空 + message — 这是合法空态，不算失败。

- [ ] **Step 2: 前端 dev server 人工冒烟**

```bash
cd web-frontend && npm run dev
```
浏览器打开 `http://localhost:3001/#/stock-heatmap`（端口以 vite 输出为准）：
- treemap 渲染、红涨绿跌正确（与当日行情方向一致）
- 切换验证窗 1/5/20 → 重新请求且颜色变化
- 关闭「信号」叠加 → ▲▼ 角标消失（不重新请求，Network 面板确认）
- hover in_scope 股票 → tooltip 含信号/池事件 + ✅/❌
- 底部统计条数字与 tooltip 抽查一致

- [ ] **Step 3: 全量回归**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_heatmap_repository.py tests/repositories/test_heatmap_repository_events.py tests/services/test_heatmap_service.py tests/api/test_market_heatmap_route.py -v --no-cov
cd web-frontend && npx vitest run
```
预期：后端热力图相关 23 个测试全 PASS；前端热力图相关 13 个测试全 PASS，其余与基线一致（基线失败清单见 memory，不由本计划引入）。

- [ ] **Step 4: 更新 spec 状态 + 收尾 commit**

把 `docs/superpowers/specs/2026-07-31-stock-heatmap-design.md` 顶部状态改为「已实现（YYYY-MM-DD）」并提交：

```bash
git add docs/superpowers/specs/2026-07-31-stock-heatmap-design.md
git commit -m "docs(spec): 股票热力图已实现——更新 spec 状态"
```
