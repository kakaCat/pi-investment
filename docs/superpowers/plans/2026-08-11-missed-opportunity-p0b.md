# P0b 踏空捕获（Missed Opportunity Scoring）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"信号已发但 agent 未行动"的买入信号补登为 `missed_opportunity` 决策并纳入 T+20 打分——信号后涨=负分（踏空）、跌=正分（正确观望），封住"少交易刷分"的奖励投机漏洞。

**Architecture:** 复用 P0a 全链路：score_calculator 加 `miss` 动作（方向同 sell）→ MissedOpportunityService 每日捕获补登 `agent_decisions`（decision_id=`MISS-{signal_id}` 天然幂等）→ DecisionScoreService 的 SCORABLE_TYPES 扩展后自动打分 → 新调度 handler。

**Tech Stack:** 同 P0a（Python 3.13 / SQLAlchemy / polars / pytest 连 quant_test）

**上位设计:** `docs/superpowers/specs/2026-08-07-text-param-evolution-design.md` §3.1（踏空类）、§7（奖励投机防线）

**工作区规则:** worktree 隔离开发；相对路径相对 `quantsys-v2/`；测试用主工作区 venv：`/Users/yunpeng/pi-investment/quantsys-v2/venv/bin/python -m pytest`（cwd=worktree 的 quantsys-v2）。

**已核实的生产事实（实现依据）:**
- `quant.signals`：17662 行（2025-12-12 起），字段 id/signal_date/symbol/action('buy'/'sell')/status('pending'/'approved'/'rejected')/strategy_id/price(可空)/confidence
- 捕获对象：`action='buy'` 且 `status IN ('pending','rejected')`（approved=已行动）
- `SignalORMRepository.get_signals_by_date_range(start, end)`（signal_repository.py L212）
- `AgentIntelligenceORMRepository`：`create_decision`（decision_id 传入即 honored）、`get_decision(decision_id)`、`get_decisions_by_entity(entity_type, entity_id, limit)`
- **create_decision 不一定 honor created_at**——Task 2 含小改动：支持可选 created_at 覆盖（回填成熟度的需要）
- 打分口径：miss 方向同 sell——excess × (-1)；信号后涨 → 负分

**限量与幂等纪律:**
- 宽限期：信号日后满 5 个交易日（K 线根数）才判定"未行动"
- 宽限期内同 symbol 出现 trade_buy 决策 → skipped_acted（agent 行动了不算踏空）
- 每日每 symbol 只留 confidence 最高的 1 条候选；每天最多捕获 5 条（confidence 降序）
- decision_id = `MISS-{signal_id}`，重复捕获靠 get_decision 预检跳过
- 只滚动处理最近 10 天信号，不做全量历史回填

---

### Task 1: score_calculator 加 miss 动作

**Files:**
- Modify: `application/services/evolution/score_calculator.py`
- Test: `tests/services/evolution/test_score_calculator.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
def test_miss_rally_is_negative():
    # 踏空：信号后大涨，未行动 → 满分负分
    r = compute_trade_score('miss', trade_price=10.0, ref_price=11.0, bench_return=0.0)
    assert r['score'] == -1.0
    assert r['band'] == 'big_loss'


def test_miss_drop_is_positive():
    # 正确观望：信号后大跌，未行动 → 正分
    r = compute_trade_score('miss', trade_price=10.0, ref_price=9.0, bench_return=-0.02)
    # 股票 -10%，基准 -2%，观望决策超额 +8% → 0.8
    assert r['score'] == 0.8
    assert r['band'] == 'big_win'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Users/yunpeng/pi-investment/quantsys-v2/venv/bin/python -m pytest tests/services/evolution/test_score_calculator.py -v`
Expected: FAIL，ValueError: unknown action: miss

- [ ] **Step 3: 重构为方向映射表**

```python
"""决策打分纯函数（文本参数进化 P0a/P0b）。

口径：超额收益（股票区间收益 − 同期基准收益）归一化到 [-1, 1]，±10% 超额 = 满分。
方向：buy 正向；sell/miss 反向（躲过下跌/正确观望为正，割肉/踏空为负）。
纯函数不碰 DB——判断权在裁判 agent，这里只算数。
"""

FULL_SCORE_EXCESS = 0.10  # ±10% 超额收益对应 ±1 分

DIRECTION = {'buy': 1, 'sell': -1, 'miss': -1}


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
    """决策统一打分。action='buy'|'sell'|'miss'；ref_price 为窗口参考收盘价。

    返回 {'score', 'band', 'excess_return'}，excess_return 为方向调整后的超额。
    非法 action 抛 ValueError（防静默错向打分）。
    """
    if action not in DIRECTION:
        raise ValueError(f'unknown action: {action}')
    stock_return = ref_price / trade_price - 1.0
    excess = (stock_return - bench_return) * DIRECTION[action]
    score = max(-1.0, min(1.0, excess / FULL_SCORE_EXCESS))
    return {
        'score': round(score, 4),
        'band': score_band(score),
        'excess_return': round(excess, 6),
    }
```

- [ ] **Step 4: 跑测试确认通过** — Expected: 9 passed（既有 7 个不受影响）

- [ ] **Step 5: Commit**

```bash
git add application/services/evolution/score_calculator.py tests/services/evolution/test_score_calculator.py
git commit -m "feat(evolution): 打分器加 miss 动作——踏空/观望方向化评分"
```

---

### Task 2: create_decision 支持 created_at 覆盖

**Files:**
- Modify: `adapters/outbound/repositories/agent_intelligence_repository.py`（`create_decision`，约 L55-82）
- Test: `tests/services/test_decision_score_repo.py`（追加）

- [ ] **Step 1: Read 现有 create_decision 实现**，确认字段赋值模式

- [ ] **Step 2: 追加失败测试**

```python
def test_create_decision_with_created_at_override():
    """P0b：补登历史/信号决策需要把 created_at 设为事件日（成熟度从事件日起算）"""
    from datetime import datetime as _dt
    repo = AgentIntelligenceORMRepository()
    created = repo.create_decision({
        'decision_id': 'TEST-CREATED-AT-001',
        'decision_type': 'missed_opportunity',
        'parameters': {'symbol': '600519', 'price': 10.0},
        'reasoning': 'created_at 覆盖测试',
        'created_at': _dt(2026, 6, 15, 10, 30),
    })
    try:
        assert created['created_at'] is not None
        assert str(created['created_at'])[:10] == '2026-06-15'
    finally:
        session = repo.session
        session.query(repo.model).filter_by(decision_id='TEST-CREATED-AT-001').delete()
        session.commit()
```

- [ ] **Step 3: 跑测试确认失败**（created_at 被写成今天）

- [ ] **Step 4: 实现** — 在 create_decision 的字段赋值处加（遵循该方法的既有赋值模式）：

```python
            if decision_data.get('created_at'):
                row.created_at = decision_data['created_at']
```

（若实现是 `self.model(**fields)` 构造式，则在构造后、commit 前赋值。）

- [ ] **Step 5: 跑测试确认通过**（该文件 2 passed）

- [ ] **Step 6: Commit**

```bash
git add adapters/outbound/repositories/agent_intelligence_repository.py tests/services/test_decision_score_repo.py
git commit -m "feat(evolution): create_decision 支持 created_at 覆盖——P0b 补登成熟度起算"
```

---

### Task 3: MissedOpportunityService

**Files:**
- Create: `application/services/evolution/missed_opportunity_service.py`
- Test: `tests/services/evolution/test_missed_opportunity_service.py`

- [ ] **Step 1: 写失败测试**

```python
"""MissedOpportunityService 测试（P0b）——信号/决策/K线仓储全部 mock。"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import polars as pl

from application.services.evolution.missed_opportunity_service import MissedOpportunityService

TODAY = date(2026, 8, 11)
SIGNAL_DATE = date(2026, 8, 3)  # 距 TODAY 6 个交易日（造 8 根 K 线，含信号日）


def _kline_df(start, days, close=10.0):
    return pl.DataFrame({
        'symbol': ['300255'] * days,
        'trade_date': [start + timedelta(days=i) for i in range(days)],
        'open': [close] * days, 'high': [close] * days,
        'low': [close] * days, 'close': [close] * days,
        'volume': [1000] * days, 'amount': [10000.0] * days,
    })


def _signal(**kw):
    s = {'id': 101, 'signal_date': SIGNAL_DATE, 'symbol': '300255',
         'action': 'buy', 'status': 'pending', 'strategy_id': 'cci_reversal',
         'price': 24.43, 'confidence': 0.8}
    s.update(kw)
    return s


def _service(signals, kline_df, existing_decisions=None):
    signal_repo = MagicMock()
    signal_repo.get_signals_by_date_range.return_value = signals
    decision_repo = MagicMock()
    decision_repo.get_decision.return_value = None
    decision_repo.get_decisions_by_entity.return_value = existing_decisions or []
    kline_repo = MagicMock()
    kline_repo.get_daily_klines.return_value = kline_df
    return MissedOpportunityService(
        signal_repo=signal_repo, decision_repo=decision_repo, kline_repo=kline_repo,
    ), decision_repo


def test_pending_buy_signal_captured():
    svc, repo = _service([_signal()], _kline_df(SIGNAL_DATE, 8))
    result = svc.capture(today=TODAY)
    assert result['captured'] == 1
    args = repo.create_decision.call_args[0][0]
    assert args['decision_id'] == 'MISS-101'
    assert args['decision_type'] == 'missed_opportunity'
    assert args['parameters']['symbol'] == '300255'
    assert args['parameters']['price'] == 24.43
    assert args['created_at'].date() == SIGNAL_DATE


def test_approved_signal_not_captured():
    svc, repo = _service([_signal(status='approved')], _kline_df(SIGNAL_DATE, 8))
    result = svc.capture(today=TODAY)
    assert result['captured'] == 0
    assert result['scanned'] == 0  # approved 不进候选
    repo.create_decision.assert_not_called()


def test_sell_signal_not_captured():
    svc, repo = _service([_signal(action='sell')], _kline_df(SIGNAL_DATE, 8))
    result = svc.capture(today=TODAY)
    assert result['captured'] == 0
    repo.create_decision.assert_not_called()


def test_signal_in_grace_period_skipped():
    # 信号日后仅 3 根 K 线 < 5 天宽限期
    svc, repo = _service([_signal(signal_date=date(2026, 8, 7))],
                         _kline_df(date(2026, 8, 7), 4))
    result = svc.capture(today=TODAY)
    assert result['skipped_in_grace'] == 1
    repo.create_decision.assert_not_called()


def test_duplicate_skipped():
    svc, repo = _service([_signal()], _kline_df(SIGNAL_DATE, 8))
    repo.get_decision.return_value = {'decision_id': 'MISS-101'}  # 已捕获过
    result = svc.capture(today=TODAY)
    assert result['skipped_duplicate'] == 1
    repo.create_decision.assert_not_called()


def test_acted_within_grace_skipped():
    acted = [{'decision_type': 'trade_buy',
              'created_at': datetime(2026, 8, 5, 10, 0)}]  # 信号日后第 2 天买入
    svc, repo = _service([_signal()], _kline_df(SIGNAL_DATE, 8), acted)
    result = svc.capture(today=TODAY)
    assert result['skipped_acted'] == 1
    repo.create_decision.assert_not_called()


def test_daily_cap_and_confidence_dedup():
    # 同日同 symbol 两条信号留 confidence 高的；同日 6 个 symbol 只捕 5 条
    signals = [_signal(id=101, confidence=0.5), _signal(id=102, confidence=0.9)]
    signals += [_signal(id=200 + i, symbol=f'30000{i}', confidence=0.1 * i)
                for i in range(6)]
    # 每个 symbol 的 K 线查询都要返回成熟数据
    kline_repo_df = _kline_df(SIGNAL_DATE, 8)
    signal_repo = MagicMock()
    signal_repo.get_signals_by_date_range.return_value = signals
    decision_repo = MagicMock()
    decision_repo.get_decision.return_value = None
    decision_repo.get_decisions_by_entity.return_value = []
    kline_repo = MagicMock()
    kline_repo.get_daily_klines.return_value = kline_repo_df
    svc = MissedOpportunityService(
        signal_repo=signal_repo, decision_repo=decision_repo, kline_repo=kline_repo)
    result = svc.capture(today=TODAY)
    assert result['captured'] == 5  # cap=5
    captured_ids = [c[0][0]['decision_id'] for c in decision_repo.create_decision.call_args_list]
    assert 'MISS-102' in captured_ids      # 同 symbol 留高 confidence
    assert 'MISS-101' not in captured_ids
    assert 'MISS-200' not in captured_ids  # confidence=0 最低被 cap 掉


def test_missing_price_falls_back_to_signal_day_close():
    svc, repo = _service([_signal(price=None)], _kline_df(SIGNAL_DATE, 8, close=24.43))
    result = svc.capture(today=TODAY)
    assert result['captured'] == 1
    assert repo.create_decision.call_args[0][0]['parameters']['price'] == 24.43
```

- [ ] **Step 2: 跑测试确认失败** — ModuleNotFoundError: missed_opportunity_service

- [ ] **Step 3: 实现**

```python
"""踏空捕获服务（文本参数进化 P0b，2026-08-11）。

每日调度：捕获"信号已发但 agent 未行动"的买入信号，补登为 missed_opportunity
决策（不行动也是决策），满20交易日后由 DecisionScoreService 打分：
信号后涨=负分（踏空），跌=正分（正确观望）。
防奖励投机：agent 无法靠"少交易"逃避评分（总设计 §7）。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from application.services.evolution.decision_score_service import _as_date

logger = logging.getLogger(__name__)

BUY_ACTION = 'buy'
CAPTURABLE_STATUS = ('pending', 'rejected')


class MissedOpportunityService:
    """依赖注入同 DecisionScoreService：repo 可替换，便于 mock 测试。"""

    def __init__(self, signal_repo=None, decision_repo=None, kline_repo=None,
                 grace_trading_days: int = 5, daily_cap: int = 5):
        if signal_repo is None:
            from adapters.outbound.repositories.signal_repository import SignalORMRepository
            signal_repo = SignalORMRepository()
        if decision_repo is None:
            from adapters.outbound.repositories.agent_intelligence_repository import (
                AgentIntelligenceORMRepository,
            )
            decision_repo = AgentIntelligenceORMRepository()
        if kline_repo is None:
            from adapters.outbound.repositories.kline_repository import KlineORMRepository
            kline_repo = KlineORMRepository()
        self.signal_repo = signal_repo
        self.decision_repo = decision_repo
        self.kline_repo = kline_repo
        self.grace_trading_days = grace_trading_days
        self.daily_cap = daily_cap

    def capture(self, lookback_days: int = 10, today: Optional[date] = None) -> Dict[str, Any]:
        """滚动捕获最近 lookback_days 内未被行动的买入信号，返回计数汇总。"""
        today = today or date.today()
        start = today - timedelta(days=lookback_days)
        signals = self.signal_repo.get_signals_by_date_range(
            start.isoformat(), today.isoformat())
        result = {'scanned': 0, 'captured': 0, 'skipped_acted': 0,
                  'skipped_duplicate': 0, 'skipped_in_grace': 0,
                  'skipped_invalid': 0, 'errors': 0}

        # 候选：同日同 symbol 只留 confidence 最高的一条
        candidates: Dict[tuple, dict] = {}
        for s in signals or []:
            if str(s.get('action') or '').lower() != BUY_ACTION:
                continue
            if s.get('status') not in CAPTURABLE_STATUS:
                continue
            key = (str(s.get('signal_date'))[:10], s.get('symbol'))
            cur = candidates.get(key)
            if cur is None or (s.get('confidence') or 0) > (cur.get('confidence') or 0):
                candidates[key] = s

        # 每日限量：confidence 降序取前 daily_cap
        by_date: Dict[str, List[dict]] = {}
        for (d, _symbol), s in candidates.items():
            by_date.setdefault(d, []).append(s)
        selected: List[dict] = []
        for d, items in by_date.items():
            items.sort(key=lambda x: x.get('confidence') or 0, reverse=True)
            selected.extend(items[: self.daily_cap])

        for s in selected:
            result['scanned'] += 1
            try:
                outcome = self._capture_one(s, today)
            except Exception as e:
                logger.error(f"踏空捕获失败 signal {s.get('id')}: {e}")
                result['errors'] += 1
                continue
            result[outcome] += 1
        logger.info(f"踏空捕获完成: {result}")
        return result

    def _capture_one(self, signal: Dict[str, Any], today: date) -> str:
        decision_id = f"MISS-{signal.get('id')}"
        if self.decision_repo.get_decision(decision_id):
            return 'skipped_duplicate'
        symbol = signal.get('symbol')
        signal_date = _as_date(signal.get('signal_date'))
        if not symbol or signal_date is None:
            return 'skipped_invalid'

        df = self.kline_repo.get_daily_klines(
            symbol, start_date=signal_date.isoformat(), end_date=today.isoformat())
        if df is None or df.height == 0:
            return 'skipped_invalid'
        rows = list(df.iter_rows(named=True))
        later = [r for r in rows
                 if _as_date(r['trade_date']) is not None
                 and _as_date(r['trade_date']) > signal_date]
        if len(later) < self.grace_trading_days:
            return 'skipped_in_grace'

        if self._acted(symbol, signal_date, later):
            return 'skipped_acted'

        price = signal.get('price')
        if price is None:
            price = float(rows[0]['close'])  # 信号日收盘兜底
        self.decision_repo.create_decision({
            'decision_id': decision_id,
            'decision_type': 'missed_opportunity',
            'context': {
                'source': 'missed_signal_capture',
                'strategy_id': signal.get('strategy_id'),
                'signal_status': signal.get('status'),
                'signal_date': signal_date.isoformat(),
            },
            'parameters': {'symbol': symbol, 'price': float(price),
                           'signal_id': signal.get('id')},
            'reasoning': f"信号未行动捕获（{signal.get('strategy_id')} @ {signal_date.isoformat()}）",
            'created_at': datetime.combine(signal_date, datetime.min.time()),
        })
        return 'captured'

    def _acted(self, symbol: str, signal_date: date, later_rows: List[dict]) -> bool:
        """宽限期内同 symbol 出现 trade_buy 决策 = 已行动。"""
        window_end = _as_date(later_rows[self.grace_trading_days - 1]['trade_date'])
        decisions = self.decision_repo.get_decisions_by_entity('stock', symbol, limit=100)
        for d in decisions:
            if d.get('decision_type') != 'trade_buy':
                continue
            dd = _as_date(d.get('created_at'))
            if dd is not None and signal_date < dd <= window_end:
                return True
        return False
```

- [ ] **Step 4: 跑测试确认通过** — Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add application/services/evolution/missed_opportunity_service.py tests/services/evolution/test_missed_opportunity_service.py
git commit -m "feat(evolution): MissedOpportunityService——未行动买入信号捕获补登"
```

---

### Task 4: DecisionScoreService 扩展 + 调度 handler

**Files:**
- Modify: `application/services/evolution/decision_score_service.py`（SCORABLE_TYPES）
- Modify: `application/services/scheduler_tasks.py`（追加 handler + _TASK_HANDLERS 条目）
- Test: `tests/services/evolution/test_decision_score_service.py`（追加）、`tests/services/test_missed_opportunity_task.py`（新建）

- [ ] **Step 1: 追加失败测试**

`test_decision_score_service.py` 追加：

```python
def test_missed_opportunity_scored():
    # P0b：missed_opportunity 决策成熟后按 miss 方向打分（信号后涨=负分）
    df = _kline_df([10.0] + [11.0] * 19 + [11.0])  # 信号后第20根收盘 11.0（+10%）
    svc, repo = _service(
        [_decision(decision_id='MISS-101', decision_type='missed_opportunity')],
        df, _bench([100.0] * 30))
    result = svc.score_mature_decisions()
    assert result['scored'] == 1
    args = repo.update_score.call_args
    assert args[0][0] == 'MISS-101'
    assert args[0][1] == -1.0          # 踏空：+10% 超额 × miss 方向 -1 → -1.0
    assert args[0][2] == 'big_loss'
```

新建 `tests/services/test_missed_opportunity_task.py`：

```python
"""missed_opportunity_daily 调度 handler 测试（P0b）。"""
from unittest.mock import patch

from application.services.scheduler_tasks import (
    get_task_handler, handle_missed_opportunity_daily,
)


@patch('application.services.evolution.missed_opportunity_service.MissedOpportunityService')
def test_handler_success(mock_cls):
    mock_cls.return_value.capture.return_value = {
        'scanned': 5, 'captured': 3, 'skipped_acted': 1, 'skipped_duplicate': 1,
        'skipped_in_grace': 0, 'skipped_invalid': 0, 'errors': 0,
    }
    r = handle_missed_opportunity_daily()
    assert r['action'] == 'missed_opportunity_daily'
    assert r['status'] == 'success'
    assert r['captured'] == 3


@patch('application.services.evolution.missed_opportunity_service.MissedOpportunityService')
def test_handler_failure_swallowed(mock_cls):
    mock_cls.return_value.capture.side_effect = RuntimeError('db down')
    r = handle_missed_opportunity_daily()
    assert r['status'] == 'failed'
    assert 'db down' in r['error']


def test_handler_registered():
    assert get_task_handler('missed_opportunity_daily') is handle_missed_opportunity_daily
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**

`decision_score_service.py` 中：

```python
SCORABLE_TYPES = {'trade_buy': 'buy', 'trade_sell': 'sell',
                  'missed_opportunity': 'miss'}
```

`scheduler_tasks.py` 在 `handle_decision_score_daily` 之后追加，并在 `_TASK_HANDLERS` 的 `"decision_score_daily"` 条目后注册：

```python
def handle_missed_opportunity_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """踏空捕获每日任务（文本参数进化 P0b）：未行动买入信号补登为 missed_opportunity 决策"""
    try:
        from application.services.evolution.missed_opportunity_service import MissedOpportunityService
        result = MissedOpportunityService().capture()
        return {"action": "missed_opportunity_daily", "status": "success",
                **result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"踏空捕获任务失败: {e}")
        return {"action": "missed_opportunity_daily", "status": "failed",
                "error": str(e), "timestamp": datetime.now().isoformat()}
```

```python
    "missed_opportunity_daily": handle_missed_opportunity_daily,
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Users/yunpeng/pi-investment/quantsys-v2/venv/bin/python -m pytest tests/services/evolution/ tests/services/test_missed_opportunity_task.py tests/services/test_decision_score_repo.py tests/services/test_decision_score_task.py -v`
Expected: 全过（P0b 新增 12 个）

- [ ] **Step 5: Commit**

```bash
git add application/services/evolution/decision_score_service.py application/services/scheduler_tasks.py tests/services/evolution/test_decision_score_service.py tests/services/test_missed_opportunity_task.py
git commit -m "feat(evolution): missed_opportunity 纳入打分+每日捕获调度"
```

---

### Task 5: 收尾验证

- [ ] **Step 1: 全量测试**（同 Task 4 Step 4 命令 + `tests/services/evolution/` 全目录）

- [ ] **Step 2: 生产手动跑一次捕获**

```bash
cd quantsys-v2 && venv/bin/python -c "
from application.services.evolution.missed_opportunity_service import MissedOpportunityService
print(MissedOpportunityService().capture())"
```

Expected: 计数 dict（最近 10 天内的 pending/rejected 买入信号被捕获；重复跑第二次应全部 skipped_duplicate——幂等验证）。

- [ ] **Step 3: 验证补登结果**

```bash
psql -d quant_investment -c "SELECT decision_id, related_entity_id, created_at::date, evaluation_status FROM quant.agent_decisions WHERE decision_id LIKE 'MISS-%' ORDER BY created_at DESC LIMIT 10;"
```

- [ ] **Step 4: 合并回 main（merge-back 流程）→ 推送 → 生产注册 cron 行：**

```bash
psql -d quant_investment -c "INSERT INTO quant.scheduler_tasks (name, cron_expression, command, params, is_enabled, description)
VALUES ('missed-opportunity-daily', '40 18 * * 1-5', 'missed_opportunity_daily', '{}', true,
        '踏空捕获（P0b）：未行动买入信号补登（打分前 5 分钟跑）')
ON CONFLICT (name) DO NOTHING;"
```

→ 重启 5001（先 `mkdir -p logs`，nohup 带日志重定向）→ curl 验证服务正常。

---

## Self-Review 记录

- **Spec 覆盖**：总设计 §3.1 踏空类（信号后 20 日走势打分）= Task 1+3+4；§7 奖励投机防线 = 本计划整体动机；限量/幂等纪律在头部锁定。
- **占位符**：无；Task 2 的 create_decision 改动给了两种实现形态的指引（赋值式/构造式），因计划撰写时未读该函数体——实现者先 Read 再动手。
- **类型一致**：`capture(lookback_days, today)`、`compute_trade_score('miss', ...)`、计数键 captured/skipped_acted/skipped_duplicate/skipped_in_grace/skipped_invalid/errors 在 Task 3/4/5 间一致。
- **已知边界**：宽限期判定用信号 symbol 自身 K 线数交易日（个股停牌会影响计数，可接受）；_acted 只查 trade_buy（trade_swap 等复合类型不覆盖，P0c+ 再议）。
