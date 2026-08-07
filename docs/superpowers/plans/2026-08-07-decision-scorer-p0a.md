# P0a 决策打分核心（DecisionScorer）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 `agent_decisions` 中满 20 个交易日的 trade_buy/trade_sell 决策自动打分（基准调整后 [-1,1] + 分档）并回写，每日调度运行——激活现有 pending→evaluated 断头管道，为裁判 agent 产出待解读原料。

**Architecture:** 纯函数计算器（score_calculator）+ 可注入依赖的服务（DecisionScoreService，模式同 EvolutionFitnessService）+ 仓储两个新方法（update_score / list_scored_decisions）+ 调度 handler（scheduler_tasks._TASK_HANDLERS）+ 只读 API（evolution_async）。v2 只做计算，不做判断（总设计 §1.2 无判断权原则）。

**Tech Stack:** Python 3.13 / SQLAlchemy ORM / polars / psycopg2 调度器 / FastAPI / pytest（连 quant_test 真实 PG）

**上位设计:** `docs/superpowers/specs/2026-08-07-text-param-evolution-design.md` §3.1

**工作区规则（必须遵守）:** 在独立 worktree 中实施（`git worktree add .claude/worktrees/decision-scorer -b feat/decision-scorer`），完成合并后再删。测试必须连 `quant_test`（conftest 强制 `_test` 后缀）。以下所有相对路径相对 `quantsys-v2/`。

**打分口径（全计划统一）:**
- 超额收益 = 股票区间收益 − 同期沪深300 收益；卖出方向取反（躲过下跌为正，割肉为负）
- score = clamp(超额 / 0.10, -1, 1)（±10% 超额 = 满分），保留 4 位小数
- 分档：≥0.5 big_win / ≥0.1 small_win / ≤-0.5 big_loss / ≤-0.1 small_loss / 其余 neutral
- 成熟判据：决策日之后（严格大于）的 K 线 ≥ 20 根；参考价 = 第 20 根收盘价
- 基准缺失：降级 bench_return=0.0，明细标 `benchmark_missing: true`（沿袭 fetch_benchmark_klines 降级语义）

---

### Task 1: 迁移 + ORM 列

**Files:**
- Create: `infrastructure/persistence/migrations/add_agent_decision_score.sql`
- Modify: `adapters/outbound/repositories/agent_intelligence_repository.py:22-42`（AgentDecision ORM 类）

- [ ] **Step 1: 写迁移文件**

```sql
-- 决策打分列（文本参数进化 P0a，2026-08-07）
-- score: 基准调整后归一化分数 [-1,1]；score_band: big_win/small_win/neutral/small_loss/big_loss
ALTER TABLE quant.agent_decisions ADD COLUMN IF NOT EXISTS score REAL;
ALTER TABLE quant.agent_decisions ADD COLUMN IF NOT EXISTS score_band TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_decisions_score ON quant.agent_decisions(score) WHERE score IS NOT NULL;
```

- [ ] **Step 2: 对两个库执行迁移**

```bash
cd quantsys-v2
psql -d quant_investment -f infrastructure/persistence/migrations/add_agent_decision_score.sql
psql -d quant_test -f infrastructure/persistence/migrations/add_agent_decision_score.sql
```

Expected: 各输出 2 行 `ALTER TABLE` + 1 行 `CREATE INDEX`（重复执行报已存在也算通过，幂等）。

- [ ] **Step 3: ORM 加列**

`adapters/outbound/repositories/agent_intelligence_repository.py` 的 `AgentDecision` 类中（`session_key` 字段之后）追加：

```python
    score = Column(Float)               # 决策打分 [-1,1]（P0a，2026-08-07）
    score_band = Column(String(20))     # big_win/small_win/neutral/small_loss/big_loss
```

检查文件头部 sqlalchemy import，若无 `Float` 则加入 import 列表。

- [ ] **Step 4: 验证 ORM 与库一致**

Run: `cd quantsys-v2 && python -c "from adapters.outbound.repositories.agent_intelligence_repository import AgentDecision; print(AgentDecision.__table__.columns.keys())"`
Expected: 输出中包含 `'score'` 和 `'score_band'`。

- [ ] **Step 5: Commit**

```bash
git add infrastructure/persistence/migrations/add_agent_decision_score.sql adapters/outbound/repositories/agent_intelligence_repository.py
git commit -m "feat(evolution): agent_decisions 增 score/score_band 列——P0a 打分落库地基"
```

---

### Task 2: 打分纯函数 score_calculator

**Files:**
- Create: `application/services/evolution/score_calculator.py`
- Test: `tests/services/evolution/test_score_calculator.py`

- [ ] **Step 1: 写失败测试**

```python
"""打分纯函数测试（P0a）——口径见计划头部。"""
from application.services.evolution.score_calculator import compute_trade_score, score_band


def test_buy_beats_benchmark_scores_positive():
    r = compute_trade_score('buy', trade_price=10.0, ref_price=11.0, bench_return=0.02)
    # 股票 +10%，基准 +2%，超额 +8% → 0.8
    assert r['score'] == 0.8
    assert r['band'] == 'big_win'
    assert r['excess_return'] == 0.08


def test_sell_avoids_drop_scores_positive():
    r = compute_trade_score('sell', trade_price=10.0, ref_price=9.0, bench_return=-0.02)
    # 股票 -10%，基准 -2%，卖出决策超额 +8% → 0.8
    assert r['score'] == 0.8
    assert r['band'] == 'big_win'


def test_panic_sell_rebound_scores_negative():
    # 割肉：卖完反弹，卖出决策为负分
    r = compute_trade_score('sell', trade_price=10.0, ref_price=11.0, bench_return=0.0)
    assert r['score'] == -1.0
    assert r['band'] == 'big_loss'


def test_score_clamped_to_one():
    r = compute_trade_score('buy', trade_price=10.0, ref_price=12.5, bench_return=0.0)
    assert r['score'] == 1.0


def test_hold_is_buy_direction():
    # 持有不动 = 买入方向的延续打分（未平仓按最新价打分与 buy 同向）
    r = compute_trade_score('buy', trade_price=10.0, ref_price=10.3, bench_return=0.0)
    assert r['score'] == 0.3
    assert r['band'] == 'small_win'


def test_score_band_boundaries():
    assert score_band(0.5) == 'big_win'
    assert score_band(0.1) == 'small_win'
    assert score_band(0.05) == 'neutral'
    assert score_band(-0.1) == 'small_loss'
    assert score_band(-0.5) == 'big_loss'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/services/evolution/test_score_calculator.py -v`
Expected: FAIL，ModuleNotFoundError: score_calculator

- [ ] **Step 3: 实现**

```python
"""决策打分纯函数（文本参数进化 P0a，2026-08-07）。

口径：超额收益（股票区间收益 − 同期基准收益）归一化到 [-1, 1]，±10% 超额 = 满分。
卖出方向取反：躲过下跌为正，割肉（卖完反弹）为负。
纯函数不碰 DB——判断权在裁判 agent，这里只算数。
"""

FULL_SCORE_EXCESS = 0.10  # ±10% 超额收益对应 ±1 分


def score_band(score: float) -> str:
    if score >= 0.5:
        return 'big_win'
    if score >= 0.1:
        return 'small_win'
    if score <= -0.5:
        return 'big_loss'
    if score <= -0.1:
        return 'small_loss'
    return 'neutral'


def compute_trade_score(action: str, trade_price: float, ref_price: float,
                        bench_return: float) -> dict:
    """买/卖统一打分。action='buy'|'sell'；ref_price 为窗口参考收盘价。

    返回 {'score', 'band', 'excess_return'}，excess_return 为方向调整后的超额。
    """
    stock_return = ref_price / trade_price - 1.0
    excess = stock_return - bench_return
    if action == 'sell':
        excess = -excess
    score = max(-1.0, min(1.0, excess / FULL_SCORE_EXCESS))
    return {
        'score': round(score, 4),
        'band': score_band(score),
        'excess_return': round(excess, 6),
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/services/evolution/test_score_calculator.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add application/services/evolution/score_calculator.py tests/services/evolution/test_score_calculator.py
git commit -m "feat(evolution): 决策打分纯函数——买卖方向超额收益归一化+分档"
```

---

### Task 3: 仓储 update_score / list_scored_decisions

**Files:**
- Modify: `adapters/outbound/repositories/agent_intelligence_repository.py`（追加两个方法，模式复刻 `update_evaluation` L119-149）
- Test: `tests/services/test_decision_score_repo.py`

- [ ] **Step 1: 写失败测试（真实 quant_test 落库，模式同 test_decision_session_key.py）**

```python
"""update_score / list_scored_decisions 落库测试（P0a），连 quant_test。"""
from adapters.outbound.repositories.agent_intelligence_repository import (
    AgentIntelligenceORMRepository,
)


def test_update_score_roundtrip():
    repo = AgentIntelligenceORMRepository()
    created = repo.create_decision({
        'decision_type': 'trade_buy',
        'parameters': {'symbol': '600519', 'price': 10.0, 'shares': 100},
        'reasoning': 'P0a 打分落库测试',
    })
    decision_id = created['decision_id']
    try:
        detail = {'scorer': 'decision_score_p0a', 'score': 0.8, 'band': 'big_win',
                  'excess_return': 0.08, 'benchmark': 'sh000300'}
        updated = repo.update_score(decision_id, 0.8, 'big_win', detail)
        assert updated is not None
        assert updated['evaluation_status'] == 'evaluated'
        assert updated['success'] is True

        rows = repo.list_scored_decisions(limit=10, band='big_win')
        hit = [r for r in rows if r['decision_id'] == decision_id]
        assert len(hit) == 1
        assert abs(hit[0]['score'] - 0.8) < 1e-6
        assert hit[0]['score_band'] == 'big_win'
        assert hit[0]['evaluation_result']['scorer'] == 'decision_score_p0a'

        # 负分 → success=False；band 过滤生效
        repo.update_score(decision_id, -0.6, 'big_loss', {'scorer': 'decision_score_p0a'})
        rows = repo.list_scored_decisions(limit=10, band='big_win')
        assert all(r['decision_id'] != decision_id for r in rows)
        row = repo.get_decision(decision_id)
        assert row['success'] is False
    finally:
        session = repo.session
        session.query(repo.model).filter_by(decision_id=decision_id).delete()
        session.commit()
```

注意：若仓储无 `get_decision(decision_id)` 方法，改用 `repo.session.query(repo.model).filter_by(decision_id=decision_id).first()` 取行后断言字段。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_decision_score_repo.py -v`
Expected: FAIL，AttributeError: update_score

- [ ] **Step 3: 实现两个方法**

在 `agent_intelligence_repository.py` 的 `update_evaluation` 方法（L119-149）之后追加：

```python
    def update_score(self, decision_id: str, score: float, band: str,
                     detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """写回决策打分（文本参数进化 P0a）。

        score/score_band 落列，明细进 evaluation_result，状态置 evaluated；
        success = 分数为正（供 decision_service 报表统计）。
        """
        try:
            row = (self.session.query(self.model)
                   .filter_by(decision_id=decision_id).first())
            if row is None:
                logger.warning(f"Decision not found for scoring: {decision_id}")
                return None
            row.score = score
            row.score_band = band
            row.evaluation_status = 'evaluated'
            row.evaluation_result = detail
            row.evaluation_date = datetime.now()
            row.success = score > 0
            self.session.commit()
            return self._to_dict(row)
        except SQLAlchemyError as e:
            logger.error(f"Error updating score for {decision_id}: {e}")
            self.session.rollback()
            return None

    def list_scored_decisions(self, limit: int = 50,
                              band: Optional[str] = None) -> List[Dict[str, Any]]:
        """查询已打分决策（score 非空），按评估时间倒序"""
        try:
            q = (self.session.query(self.model)
                 .filter(self.model.score.isnot(None)))
            if band:
                q = q.filter(self.model.score_band == band)
            rows = (q.order_by(self.model.evaluation_date.desc())
                    .limit(limit).all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error listing scored decisions: {e}")
            return []
```

再检查 `_to_dict`：若它显式枚举字段而非反射列，把 `'score'`、`'score_band'` 加入枚举。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_decision_score_repo.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add adapters/outbound/repositories/agent_intelligence_repository.py tests/services/test_decision_score_repo.py
git commit -m "feat(evolution): 决策仓储 update_score/list_scored_decisions——打分回写与查询"
```

---

### Task 4: DecisionScoreService

**Files:**
- Create: `application/services/evolution/decision_score_service.py`
- Test: `tests/services/evolution/test_decision_score_service.py`

- [ ] **Step 1: 写失败测试（mock 注入，模式同 test_evolution_fitness_service.py）**

```python
"""DecisionScoreService 测试（P0a）——仓储/K线/基准全部 mock。"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import polars as pl

from application.services.evolution.decision_score_service import DecisionScoreService

TRADE_DATE = date(2026, 7, 1)


def _kline_df(closes, start=TRADE_DATE):
    """从 start 起连续自然日造 K 线（服务不校验交易日历，只数行数）。"""
    n = len(closes)
    return pl.DataFrame({
        'symbol': ['600519'] * n,
        'trade_date': [start + timedelta(days=i) for i in range(n)],
        'open': closes, 'high': closes, 'low': closes, 'close': closes,
        'volume': [1000] * n, 'amount': [10000.0] * n,
    })


def _bench(closes, start=TRADE_DATE):
    return [{'date': (start + timedelta(days=i)).isoformat(), 'close': c}
            for i, c in enumerate(closes)]


def _decision(**kw):
    d = {'decision_id': 'DEC-T1', 'decision_type': 'trade_buy',
         'parameters': {'symbol': '600519', 'price': 10.0, 'shares': 100},
         'created_at': datetime(2026, 7, 1, 10, 30)}
    d.update(kw)
    return d


def _service(pending, kline_df, bench):
    decision_repo = MagicMock()
    decision_repo.list_pending_evaluations.return_value = pending
    kline_repo = MagicMock()
    kline_repo.get_daily_klines.return_value = kline_df
    return DecisionScoreService(
        decision_repo=decision_repo, kline_repo=kline_repo,
        bench_klines_provider=lambda symbol, start_date, end_date: bench,
    ), decision_repo


def test_mature_buy_scored():
    # 交易日后 21 根 K 线（首根=交易日），第 20 根收盘 11.0；基准平稳
    df = _kline_df([10.0] + [10.5] * 20 + [11.0])
    svc, repo = _service([_decision()], df, _bench([100.0] * 30))
    result = svc.score_mature_decisions()
    assert result['scanned'] == 1
    assert result['scored'] == 1
    args = repo.update_score.call_args
    assert args[0][0] == 'DEC-T1'
    # 第 20 根（索引 20）收盘 11.0：股票 +10%，基准 0% → score 1.0
    assert args[0][1] == 1.0
    assert args[0][2] == 'big_win'
    detail = args[0][3]
    assert detail['window_trading_days'] == 20
    assert detail['benchmark_missing'] is False


def test_unmature_skipped():
    df = _kline_df([10.0] * 5)  # 交易日后仅 4 根 < 20
    svc, repo = _service([_decision()], df, _bench([100.0] * 5))
    result = svc.score_mature_decisions()
    assert result['skipped_unmature'] == 1
    repo.update_score.assert_not_called()


def test_non_trade_type_skipped():
    svc, repo = _service([_decision(decision_type='daily_review')],
                         _kline_df([10.0] * 30), _bench([100.0] * 30))
    result = svc.score_mature_decisions()
    assert result['scanned'] == 0
    repo.update_score.assert_not_called()


def test_missing_params_skipped():
    svc, repo = _service([_decision(parameters={'shares': 100})],
                         _kline_df([10.0] * 30), _bench([100.0] * 30))
    result = svc.score_mature_decisions()
    assert result['skipped_invalid'] == 1
    repo.update_score.assert_not_called()


def test_sell_direction_and_bench_missing_degradation():
    df = _kline_df([10.0] + [9.0] * 20 + [9.0])
    svc, repo = _service(
        [_decision(decision_type='trade_sell',
                   parameters={'symbol': '600519', 'price': 10.0})],
        df, [])  # 基准缺失 → 降级 0.0 并标记
    result = svc.score_mature_decisions()
    assert result['scored'] == 1
    args = repo.update_score.call_args
    # 卖后跌 10%，躲过下跌 → score 1.0
    assert args[0][1] == 1.0
    assert args[0][3]['benchmark_missing'] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/services/evolution/test_decision_score_service.py -v`
Expected: FAIL，ModuleNotFoundError: decision_score_service

- [ ] **Step 3: 实现**

```python
"""决策打分服务（文本参数进化 P0a，2026-08-07）。

每日调度：对 evaluation_status='pending' 的 trade_buy/trade_sell 决策，
满 mature_window 个交易日后用 daily_klines 收盘价 + 沪深300 基准打分回写。
纯计算无判断——分数是裁判 agent 的待解读原料（总设计 §1.2/§3.1）。
依赖注入模式同 EvolutionFitnessService：repo 与 provider 可替换，便于 mock 测试。
"""
import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional

from application.services.evolution.score_calculator import compute_trade_score

logger = logging.getLogger(__name__)

BENCHMARK_SYMBOL = 'sh000300'
SCORABLE_TYPES = {'trade_buy': 'buy', 'trade_sell': 'sell'}


def _as_date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:19]).date()
        except ValueError:
            return None
    return None


class DecisionScoreService:
    def __init__(self, decision_repo=None, kline_repo=None,
                 bench_klines_provider: Optional[Callable] = None,
                 mature_window: int = 20):
        if decision_repo is None:
            from adapters.outbound.repositories.agent_intelligence_repository import (
                AgentIntelligenceORMRepository,
            )
            decision_repo = AgentIntelligenceORMRepository()
        if kline_repo is None:
            from adapters.outbound.repositories.kline_repository import KlineORMRepository
            kline_repo = KlineORMRepository()
        if bench_klines_provider is None:
            from application.services.benchmark_comparison import fetch_benchmark_klines
            bench_klines_provider = fetch_benchmark_klines
        self.decision_repo = decision_repo
        self.kline_repo = kline_repo
        self.bench_klines_provider = bench_klines_provider
        self.mature_window = mature_window

    def score_mature_decisions(self, pending_days: int = 1) -> Dict[str, Any]:
        """扫描 pending 决策并打分回写，返回计数汇总（供调度 run 记录）。"""
        pending = self.decision_repo.list_pending_evaluations(days=pending_days)
        result = {'scanned': 0, 'scored': 0, 'skipped_unmature': 0,
                  'skipped_invalid': 0, 'errors': 0}
        for decision in pending:
            action = SCORABLE_TYPES.get(decision.get('decision_type'))
            if action is None:
                continue
            result['scanned'] += 1
            try:
                outcome = self._score_one(decision, action)
            except Exception as e:
                logger.error(f"打分失败 {decision.get('decision_id')}: {e}")
                result['errors'] += 1
                continue
            if outcome == 'scored':
                result['scored'] += 1
            elif outcome == 'unmature':
                result['skipped_unmature'] += 1
            else:
                result['skipped_invalid'] += 1
        logger.info(f"决策打分完成: {result}")
        return result

    def _score_one(self, decision: Dict[str, Any], action: str) -> str:
        """单条决策打分。返回 'scored' | 'unmature' | 'invalid'。"""
        params = decision.get('parameters') or {}
        symbol = params.get('symbol')
        trade_price = params.get('price')
        trade_date = _as_date(decision.get('created_at'))
        if not symbol or not trade_price or trade_date is None:
            return 'invalid'

        today = date.today()
        df = self.kline_repo.get_daily_klines(
            symbol, start_date=trade_date.isoformat(), end_date=today.isoformat())
        if df is None or df.height == 0:
            return 'invalid'
        future = [r for r in df.iter_rows(named=True)
                  if _as_date(r['trade_date']) is not None
                  and _as_date(r['trade_date']) > trade_date]
        if len(future) < self.mature_window:
            return 'unmature'
        ref = future[self.mature_window - 1]
        ref_price = float(ref['close'])
        ref_date = _as_date(ref['trade_date'])

        bench_return, bench_missing = self._bench_return(trade_date, ref_date)
        scored = compute_trade_score(action, float(trade_price), ref_price, bench_return)

        detail = {
            'scorer': 'decision_score_p0a',
            'window_trading_days': self.mature_window,
            'trade_date': trade_date.isoformat(),
            'ref_date': ref_date.isoformat(),
            'trade_price': float(trade_price),
            'ref_price': ref_price,
            'benchmark': BENCHMARK_SYMBOL,
            'benchmark_missing': bench_missing,
            **scored,
        }
        self.decision_repo.update_score(
            decision['decision_id'], scored['score'], scored['band'], detail)
        return 'scored'

    def _bench_return(self, start: date, end: date):
        """基准区间收益。klines 为 akshare 风格 [{'date','close'}]；缺失降级 (0.0, True)。"""
        klines = self.bench_klines_provider(
            symbol=BENCHMARK_SYMBOL, start_date=start.isoformat(), end_date=end.isoformat())
        window = [k for k in klines
                  if _as_date(k.get('date')) is not None
                  and start <= _as_date(k.get('date')) <= end]
        if len(window) < 2:
            return 0.0, True
        return float(window[-1]['close']) / float(window[0]['close']) - 1.0, False
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/services/evolution/test_decision_score_service.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add application/services/evolution/decision_score_service.py tests/services/evolution/test_decision_score_service.py
git commit -m "feat(evolution): DecisionScoreService——满20交易日买卖决策基准调整打分"
```

---

### Task 5: 调度 handler + 任务注册

**Files:**
- Modify: `application/services/scheduler_tasks.py`（追加 handler + `_TASK_HANDLERS` 条目，L1272-1306 区域）
- Test: `tests/services/test_decision_score_task.py`
- 注册: 生产库 `quant.scheduler_tasks` 插一行（SQL 见 Step 4）

- [ ] **Step 1: 写失败测试（patch 定义模块路径，模式同 test_evolution_fitness_task.py）**

```python
"""decision_score_daily 调度 handler 测试（P0a）。"""
from unittest.mock import patch

from application.services.scheduler_tasks import (
    get_task_handler, handle_decision_score_daily,
)


@patch('application.services.evolution.decision_score_service.DecisionScoreService')
def test_handler_success(mock_cls):
    mock_cls.return_value.score_mature_decisions.return_value = {
        'scanned': 3, 'scored': 2, 'skipped_unmature': 1,
        'skipped_invalid': 0, 'errors': 0,
    }
    r = handle_decision_score_daily()
    assert r['action'] == 'decision_score_daily'
    assert r['status'] == 'success'
    assert r['scored'] == 2


@patch('application.services.evolution.decision_score_service.DecisionScoreService')
def test_handler_failure_swallowed(mock_cls):
    mock_cls.return_value.score_mature_decisions.side_effect = RuntimeError('db down')
    r = handle_decision_score_daily()
    assert r['status'] == 'failed'
    assert 'db down' in r['error']


def test_handler_registered():
    assert get_task_handler('decision_score_daily') is handle_decision_score_daily
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_decision_score_task.py -v`
Expected: FAIL，ImportError: handle_decision_score_daily

- [ ] **Step 3: 实现 handler 并注册**

在 `scheduler_tasks.py` 的 `handle_evolution_fitness_daily`（L1245-1268）之后追加：

```python
def handle_decision_score_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """决策打分每日任务（文本参数进化 P0a）：满20交易日的买卖决策打分回写"""
    try:
        from application.services.evolution.decision_score_service import DecisionScoreService
        result = DecisionScoreService().score_mature_decisions()
        return {"action": "decision_score_daily", "status": "success",
                **result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"决策打分任务失败: {e}")
        return {"action": "decision_score_daily", "status": "failed",
                "error": str(e), "timestamp": datetime.now().isoformat()}
```

在 `_TASK_HANDLERS` dict 中 `"evolution_fitness_daily"` 条目后加一行：

```python
    "decision_score_daily": handle_decision_score_daily,
```

- [ ] **Step 4: 注册生产调度任务行**

```bash
psql -d quant_investment -c "
INSERT INTO quant.scheduler_tasks (name, cron_expression, command, params, is_enabled, description)
VALUES ('decision-score-daily', '45 18 * * 1-5', 'decision_score_daily', '{}', true,
        '决策打分（P0a）：满20交易日的买卖决策基准调整打分回写')
ON CONFLICT (name) DO NOTHING;"
```

（cron 排在 evolution-fitness-daily 18:30 之后，避免争用；工作日运行。）

- [ ] **Step 5: 跑测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_decision_score_task.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add application/services/scheduler_tasks.py tests/services/test_decision_score_task.py
git commit -m "feat(evolution): decision_score_daily 调度任务——工作日18:45自动打分"
```

---

### Task 6: 只读 API GET /api/evolution/decision-scores

**Files:**
- Modify: `adapters/inbound/fastapi_app/routes/evolution_async.py`（追加路由；evolution_router 已在 main.py 注册，无需改 main.py）

- [ ] **Step 1: 追加路由**

在 `evolution_async.py` 末尾追加：

```python
@router.get('/api/evolution/decision-scores')
@handle_api_error
def get_decision_scores(
    limit: int = Query(50, ge=1, le=200),
    band: Optional[str] = Query(None, description='big_win/small_win/neutral/small_loss/big_loss'),
):
    """最近已打分决策（P0a）——裁判 agent 与仪表盘的打分读取入口"""
    from adapters.outbound.repositories.agent_intelligence_repository import (
        AgentIntelligenceORMRepository,
    )
    repo = AgentIntelligenceORMRepository()
    rows = repo.list_scored_decisions(limit=limit, band=band)
    return api_response({'total': len(rows), 'items': rows})
```

- [ ] **Step 2: 验证路由注册与响应**

```bash
cd quantsys-v2 && python -c "
from adapters.inbound.fastapi_app.main import app
paths = [r.path for r in app.routes]
assert '/api/evolution/decision-scores' in paths, paths
print('route ok')"
```

Expected: 输出 `route ok`（若 import main 过重可在 worktree 内起服务后 `curl 'http://127.0.0.1:5001/api/evolution/decision-scores'` 验证 `{"success":true,...}`）。

- [ ] **Step 3: Commit**

```bash
git add adapters/inbound/fastapi_app/routes/evolution_async.py
git commit -m "feat(evolution): GET /api/evolution/decision-scores——打分结果只读入口"
```

---

### Task 7: 收尾验证

- [ ] **Step 1: 全量测试（对照基线失败清单，只接受预存在失败）**

Run: `cd quantsys-v2 && python -m pytest tests/services/evolution/ tests/services/test_decision_score_repo.py tests/services/test_decision_score_task.py -v`
Expected: 本计划新增 15 个测试全过；仓库其他预存在失败不新增。

- [ ] **Step 2: 生产库手动跑一次打分（dry 验证）**

```bash
cd quantsys-v2 && python -c "
from application.services.evolution.decision_score_service import DecisionScoreService
print(DecisionScoreService().score_mature_decisions())"
```

Expected: 输出计数 dict（生产 60 条 pending 决策中 trade_* 类按成熟度被 scored/skipped_unmature；akshare 基准失败时 benchmark_missing=true 降级，不报错）。

- [ ] **Step 3: 确认 scheduler_runs 落记录（心跳等价物）**

下次调度运行后：`psql -d quant_investment -c "SELECT name,last_run_at,last_status FROM quant.scheduler_tasks WHERE name='decision-score-daily';"` 可见最近运行时间与状态（现有 scheduler_runs 机制即心跳载体，僵尸 run 6h 判死已内置）。

- [ ] **Step 4: 合并回 main 并删 worktree**（遵循仓库 merge-back 流程；5001 为手动重启部署，合并后需重启 FastAPI 使 API 生效）

---

## Self-Review 记录

- **Spec 覆盖**：总设计 §3.1 四类决策中买/卖/持有由本计划覆盖（持有=买入方向延续打分，test_hold_is_buy_direction）；踏空类按敏捷切分留给 P0b；调度+运行可见性由 Task 5/7（scheduler_runs 即心跳，与现状一致）覆盖。
- **占位符**：无 TBD/TODO；所有代码步骤含完整代码。
- **类型一致**：`update_score(decision_id, score, band, detail)`、`list_scored_decisions(limit, band)`、`compute_trade_score(action, trade_price, ref_price, bench_return)`、`score_mature_decisions(pending_days)` 在 Task 3/4/5/6 间签名一致。
