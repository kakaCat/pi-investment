# 盈利闭环统一实施计划（Profit Loop Closure）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通"找股票 → 信号 → agent 模拟买卖 → 日复盘 → 每周进化"的自动闭环：v2 降级为确定性骨架（刷池/信号/推送），agent 是唯一交易者（账本 agent_virtual），统一 supervisor 保证 4 进程常驻。

**Architecture:** 方案 A（日程骨架 + 事件驱动）。v2 orchestrator 不再下单，MARKET_OPEN 改为推送 `signals_ready` 事件到 agent wake channel；agent 通过 portfolio_trade 操作 agent_virtual 账户；服务端风控硬护栏兜底；loop_supervisor.py 管理全部进程。

**Tech Stack:** Python 3.13（quantsys-v2，pytest）、TypeScript/tsx（agent-ts，Jest ESM）、Flask API :5001、wake channel :3100、PostgreSQL。

**设计文档:** `docs/superpowers/specs/2026-07-24-profit-loop-closure-design.md`

**关键事实（实施前必读）：**
- 5001 端口当前由 Flask `quantsys-v2/adapters/inbound/api/server.py` 提供服务，健康检查端点是 `GET /api/health`（不是 `/health`）
- wake channel 端口 **3100**（`WAKE_CHANNEL_PORT` 默认 3100；v2 侧 `AGENT_API_URL=http://127.0.0.1:3100`），健康检查 `GET /wake/health`
- v2 Python 解释器必须用 `quantsys-v2/.venv-py313/bin/python`（scheduler_daemon 用错解释器会静默丢任务）
- quantsys-v2 跑 pytest 时自动切到 `quant_test` 数据库（测试安全）
- agent-ts 测试：Jest ESM（`npm test -- <file>`），测试文件与源码同目录 `*.test.ts`
- `SimulationTrade.action` 字段值为 `'buy'/'sell'`，`trade_date` 是 Date 列

---

## Phase 1 — v2：orchestrator 降级为信号准备（断点 2）

### Task 1: SignalExecutionScheduler 懒加载 PaperTradingEngine

**目的：** orchestrator 改造后只需 `_collect_signals()`，但 `SignalExecutionScheduler.__init__` 会无条件创建绑定 `rotation_main` 的 PaperTradingEngine。改为懒加载，只有真正下单的路径才创建。

**Files:**
- Modify: `quantsys-v2/application/services/signal_execution_scheduler.py:35-45`
- Test: `quantsys-v2/tests/test_signal_execution_lazy_engine.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/test_signal_execution_lazy_engine.py`：

```python
"""SignalExecutionScheduler 懒加载 PaperTradingEngine 测试"""
from unittest.mock import patch
from application.services.signal_execution_scheduler import SignalExecutionScheduler


def test_engine_not_created_on_init():
    """构造时不应创建 PaperTradingEngine（避免无关路径绑定 rotation_main）"""
    with patch('application.services.signal_execution_scheduler.DataService'), \
         patch('application.services.signal_execution_scheduler.StrategyCodeService'), \
         patch('application.services.signal_execution_scheduler.RiskCheckService'), \
         patch('application.services.signal_execution_scheduler.SignalORMRepository'), \
         patch('application.services.signal_execution_scheduler.SignalExecutionLogORMRepository'), \
         patch('application.services.signal_execution_scheduler.StrategyORMRepository'), \
         patch('application.services.signal_execution_scheduler.PaperTradingEngine') as MockEngine:
        scheduler = SignalExecutionScheduler()
        MockEngine.assert_not_called()
        assert scheduler._paper_engine is None


def test_engine_created_lazily_on_access():
    """首次访问 paper_engine 属性时才创建，且复用同一实例"""
    with patch('application.services.signal_execution_scheduler.DataService'), \
         patch('application.services.signal_execution_scheduler.StrategyCodeService'), \
         patch('application.services.signal_execution_scheduler.RiskCheckService'), \
         patch('application.services.signal_execution_scheduler.SignalORMRepository'), \
         patch('application.services.signal_execution_scheduler.SignalExecutionLogORMRepository'), \
         patch('application.services.signal_execution_scheduler.StrategyORMRepository'), \
         patch('application.services.signal_execution_scheduler.PaperTradingEngine') as MockEngine:
        scheduler = SignalExecutionScheduler()
        engine1 = scheduler.paper_engine
        engine2 = scheduler.paper_engine
        MockEngine.assert_called_once_with(
            account_name='rotation_main', initial_capital=1_000_000)
        assert engine1 is engine2
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_signal_execution_lazy_engine.py -v
```
预期：FAIL（`scheduler._paper_engine` 属性不存在 / 构造时已调用 PaperTradingEngine）

- [ ] **Step 3: 实现**

修改 `quantsys-v2/application/services/signal_execution_scheduler.py` 的 `__init__`（35-45 行）：

```python
    def __init__(self):
        self.ds = DataService()
        self.strategy_service = StrategyCodeService()
        self.risk_service = RiskCheckService(self.ds)
        self.signal_repo = SignalORMRepository()
        self.log_repo = SignalExecutionLogORMRepository()
        self.strategy_repo = StrategyORMRepository()
        # 懒加载：只有真正下单的路径（_batch_create_orders）才创建引擎。
        # 2026-07-24 盈利闭环改造：orchestrator 只收集信号不下单，
        # 不应因构造 scheduler 就绑定 rotation_main 账户。
        self._paper_engine = None

    @property
    def paper_engine(self):
        if self._paper_engine is None:
            self._paper_engine = PaperTradingEngine(
                account_name='rotation_main',
                initial_capital=1_000_000,
            )
        return self._paper_engine
```

检查文件内所有 `self.paper_engine` 引用点（`_batch_create_orders` 等处）——属性方式访问无需修改，但确认没有 `self.paper_engine = ...` 的赋值语句（有则改为 `self._paper_engine = ...`）。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_signal_execution_lazy_engine.py -v
```
预期：2 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/signal_execution_scheduler.py quantsys-v2/tests/test_signal_execution_lazy_engine.py
git commit -m "refactor: SignalExecutionScheduler 懒加载 PaperTradingEngine（闭环改造前置）"
```

---

### Task 2: orchestrator MARKET_OPEN 改为推送 signals_ready

**目的：** v2 不再自动下单；开盘阶段收集当日 pending 信号并推送 agent 决策。

**Files:**
- Modify: `quantsys-v2/application/services/daily_orchestrator.py:247-261`
- Test: `quantsys-v2/tests/test_orchestrator_signals_ready.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/test_orchestrator_signals_ready.py`：

```python
"""orchestrator MARKET_OPEN 阶段改造测试：推送 signals_ready，不下单"""
from datetime import date
from unittest.mock import patch, MagicMock

from application.services.daily_orchestrator import DailyOrchestrator


def _make_orchestrator():
    orch = DailyOrchestrator.__new__(DailyOrchestrator)
    orch.name = 'test'
    orch.session = MagicMock()
    return orch


def _make_state():
    state = MagicMock()
    state.trade_date = date(2026, 7, 24)
    state.context = {}
    return state


def test_market_open_pushes_signals_ready_without_executing():
    orch = _make_orchestrator()
    state = _make_state()
    fake_signals = [
        {'id': 1, 'symbol': '600519.SH', 'signal_type': '买入', 'strength': 85},
        {'id': 2, 'symbol': '000858.SZ', 'signal_type': '买入', 'strength': 78},
    ]

    with patch('application.services.signal_execution_scheduler.SignalExecutionScheduler') as MockSched, \
         patch('application.services.daily_orchestrator.agent_service') as mock_agent:
        MockSched.return_value._collect_signals.return_value = fake_signals

        result = orch._phase_market_open(state)

    # 不再自动下单
    MockSched.return_value.execute_daily_signals.assert_not_called()
    # 推送 signals_ready
    mock_agent.notify_agent.assert_called_once()
    event, data = mock_agent.notify_agent.call_args[0]
    assert event == 'signals_ready'
    assert data['account'] == 'agent_virtual'
    assert data['signal_count'] == 2
    assert data['signals'] == fake_signals
    assert 'trade_date' in data
    assert result['status'] == 'signals_pushed'
    assert result['signal_count'] == 2


def test_market_open_with_zero_signals_still_notifies():
    """0 信号也推送（agent 需要知道"今日无信号"而不是静默）"""
    orch = _make_orchestrator()
    state = _make_state()

    with patch('application.services.signal_execution_scheduler.SignalExecutionScheduler') as MockSched, \
         patch('application.services.daily_orchestrator.agent_service') as mock_agent:
        MockSched.return_value._collect_signals.return_value = []

        result = orch._phase_market_open(state)

    mock_agent.notify_agent.assert_called_once()
    event, data = mock_agent.notify_agent.call_args[0]
    assert event == 'signals_ready'
    assert data['signal_count'] == 0
    assert result['signal_count'] == 0
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_orchestrator_signals_ready.py -v
```
预期：FAIL（当前 `_phase_market_open` 调用 `execute_daily_signals` 且不推送 signals_ready）

- [ ] **Step 3: 实现**

替换 `quantsys-v2/application/services/daily_orchestrator.py` 的 `_phase_market_open`（247-261 行）：

```python
    def _phase_market_open(self, state: DailyOrchestratorState) -> Dict[str, Any]:
        """开盘阶段：汇总当日待处理信号并推送 Agent 决策。

        2026-07-24 盈利闭环改造：v2 不再自动下单。
        买卖决策唯一执行者是 Agent（LLM），账本为 agent_virtual。
        本阶段只负责"信号准备 + 事件推送"。
        """
        signals = self._collect_pending_signals()

        self._update_context(state, {
            'signals_ready_count': len(signals),
        })

        self._notify_agent('signals_ready', {
            'trade_date': str(state.trade_date),
            'signal_count': len(signals),
            'signals': signals[:20],
            'account': 'agent_virtual',
            'instructions': (
                '请使用工具链处理今日信号：\n'
                '1. decision_history → 检查今日是否已处理过这些信号（按信号ID判重）\n'
                '2. portfolio_status → 查看 agent_virtual 持仓与可用资金\n'
                '3. 逐信号评估后决定买入：portfolio_trade(account=agent_virtual)\n'
                '4. 放弃的信号也要 decision_record 记录理由\n'
                '5. 全部处理完：knowledge_record 摘要 + feishu_notify 简报'
            ),
        })

        return {'status': 'signals_pushed', 'signal_count': len(signals)}

    def _collect_pending_signals(self) -> List[Dict[str, Any]]:
        """收集当日 pending 信号（复用 SignalExecutionScheduler 的收集逻辑，不下单）"""
        from application.services.signal_execution_scheduler import SignalExecutionScheduler
        scheduler = SignalExecutionScheduler()
        return scheduler._collect_signals(date.today().strftime('%Y-%m-%d'))
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_orchestrator_signals_ready.py -v
```
预期：2 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/daily_orchestrator.py quantsys-v2/tests/test_orchestrator_signals_ready.py
git commit -m "feat: orchestrator MARKET_OPEN 改为推送 signals_ready，v2 不再自动下单"
```

---

### Task 3: orchestrator 账户引用 rotation_main → agent_virtual

**目的：** market_close（T+1 结转）、post_market（净值快照/绩效）、review（当日成交查询）三本账统一到 agent_virtual。

**Files:**
- Modify: `quantsys-v2/application/services/daily_orchestrator.py:273-302`（market_close）、`304-340`（post_market）、`342-385`（review）
- Test: `quantsys-v2/tests/test_orchestrator_account_unify.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/test_orchestrator_account_unify.py`：

```python
"""orchestrator 各阶段账户统一为 agent_virtual 测试"""
from datetime import date
from unittest.mock import patch, MagicMock

from application.services.daily_orchestrator import DailyOrchestrator


def _make_orchestrator():
    orch = DailyOrchestrator.__new__(DailyOrchestrator)
    orch.name = 'test'
    orch.session = MagicMock()
    return orch


def _make_state():
    state = MagicMock()
    state.trade_date = date(2026, 7, 24)
    state.context = {}
    return state


def test_market_close_settles_agent_virtual():
    orch = _make_orchestrator()
    state = _make_state()

    with patch('adapters.outbound.repositories.SimulationORMRepository') as MockRepo, \
         patch('live_trading.paper_trading_engine.PaperTradingEngine') as MockEngine:
        MockEngine.return_value.get_current_positions.return_value = []
        orch._phase_market_close(state)

    MockRepo.return_value.settle_t1.assert_called_once_with('agent_virtual')
    MockEngine.assert_called_once_with(account_name='agent_virtual')


def test_post_market_snapshot_uses_agent_virtual():
    orch = _make_orchestrator()
    state = _make_state()

    with patch('live_trading.paper_trading_engine.PaperTradingEngine') as MockEngine, \
         patch('application.services.scheduler_tasks.handle_factor_compute', return_value={'status': 'ok'}):
        MockEngine.return_value.take_daily_snapshot.return_value = {}
        MockEngine.return_value.get_performance_report.return_value = {}
        orch._phase_post_market(state)

    MockEngine.assert_called_once_with(account_name='agent_virtual')


def test_review_queries_agent_virtual_trades():
    orch = _make_orchestrator()
    state = _make_state()

    with patch('adapters.outbound.repositories.simulation_repository.SimulationORMRepository') as MockRepo, \
         patch('application.services.daily_orchestrator.agent_service') as mock_agent:
        MockRepo.return_value.get_trades_by_account.return_value = []
        orch._phase_review(state)

    MockRepo.return_value.get_trades_by_account.assert_called_once()
    assert MockRepo.return_value.get_trades_by_account.call_args[0][0] == 'agent_virtual'
    mock_agent.notify_agent.assert_called_once()
```

注意：`_phase_market_close` 里的 import 是 `from adapters.outbound.repositories import SimulationORMRepository`，patch 目标用 `adapters.outbound.repositories.SimulationORMRepository`；若实际 import 路径不同，以文件内实际 import 语句为准调整 patch 目标。

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_orchestrator_account_unify.py -v
```
预期：FAIL（当前全部使用 'rotation_main'）

- [ ] **Step 3: 实现**

在 `daily_orchestrator.py` 文件顶部（Phase 常量区之后）加模块级常量：

```python
# 唯一交易账本（2026-07-24 盈利闭环改造）
TRADING_ACCOUNT = 'agent_virtual'
```

然后替换三处 `'rotation_main'` 为 `TRADING_ACCOUNT`：
- `_phase_market_close`：`repo.settle_t1(TRADING_ACCOUNT)` 和 `PaperTradingEngine(account_name=TRADING_ACCOUNT)`
- `_phase_post_market`：`PaperTradingEngine(account_name=TRADING_ACCOUNT)`
- `_phase_review`：`sim_repo.get_trades_by_account(TRADING_ACCOUNT, ...)`

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_orchestrator_account_unify.py -v
```
预期：3 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/daily_orchestrator.py quantsys-v2/tests/test_orchestrator_account_unify.py
git commit -m "feat: orchestrator 各阶段账户统一为 agent_virtual"
```

---

## Phase 2 — v2：动态池自动刷新（断点 1）

### Task 4: handle_pool_refresh_daily 处理器 + 注册 + 种子

**目的：** 每天 02:00 自动刷新到期动态池，成员变更推送 agent（pool_changed 事件）。

**Files:**
- Modify: `quantsys-v2/application/services/scheduler_tasks.py`（新增 handler + `_TASK_HANDLERS` 注册，约 1000-1029 行）
- Modify: `quantsys-v2/scripts/init_scheduler_tasks.py:29-93`（DEFAULT_TASKS 种子）
- Test: `quantsys-v2/tests/test_pool_refresh_daily.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/test_pool_refresh_daily.py`：

```python
"""动态池每日刷新任务测试"""
from datetime import date
from unittest.mock import patch, MagicMock

from application.services.scheduler_tasks import (
    handle_pool_refresh_daily,
    _is_pool_refresh_due,
)


def _pool(pid, ptype='dynamic', interval='daily', last=None):
    return {
        'id': pid, 'name': f'pool{pid}', 'pool_type': ptype,
        'refresh_interval': interval, 'last_refreshed_at': last,
    }


def _make_service(pools, before_after):
    """before_after: [(before_symbols, after_symbols), ...] 按刷新顺序"""
    svc = MagicMock()
    svc.list_pools.return_value = pools
    gets = []
    for before, after in before_after:
        gets.append({'symbols': before})
        gets.append({'symbols': after})
    svc.get_pool.side_effect = gets
    return svc


def test_is_refresh_due_daily_always():
    assert _is_pool_refresh_due(_pool(1, interval='daily'), date(2026, 7, 24)) is True
    assert _is_pool_refresh_due(_pool(1, interval=None), date(2026, 7, 24)) is True


def test_is_refresh_due_weekly():
    assert _is_pool_refresh_due(
        _pool(1, interval='weekly', last='2026-07-20'), date(2026, 7, 24)) is False
    assert _is_pool_refresh_due(
        _pool(1, interval='weekly', last='2026-07-16'), date(2026, 7, 24)) is True
    # 从未刷新过的 weekly 池：该刷
    assert _is_pool_refresh_due(
        _pool(1, interval='weekly', last=None), date(2026, 7, 24)) is True


@patch('application.services.agent_notification_service.agent_service')
def test_refresh_due_dynamic_pools_and_notify(mock_agent):
    svc = _make_service(
        pools=[_pool(1), _pool(2, ptype='static')],
        before_after=[(['A', 'B'], ['B', 'C'])],
    )

    result = handle_pool_refresh_daily(service=svc)

    svc.refresh_pool.assert_called_once_with(1)
    assert result['status'] == 'success'
    assert result['refreshed'] == 1
    assert result['changed'] == 1
    mock_agent.notify_agent.assert_called_once()
    event, data = mock_agent.notify_agent.call_args[0]
    assert event == 'pool_changed'
    assert data['pools_changed'][0]['added'] == ['C']
    assert data['pools_changed'][0]['removed'] == ['A']


@patch('application.services.agent_notification_service.agent_service')
def test_no_change_no_notify(mock_agent):
    svc = _make_service(
        pools=[_pool(1)],
        before_after=[(['A', 'B'], ['A', 'B'])],
    )

    result = handle_pool_refresh_daily(service=svc)

    assert result['changed'] == 0
    mock_agent.notify_agent.assert_not_called()


@patch('application.services.agent_notification_service.agent_service')
def test_refresh_failure_isolated(mock_agent):
    """单个池刷新失败不影响其他池"""
    svc = _make_service(
        pools=[_pool(1), _pool(2)],
        before_after=[],
    )
    # 第一个池 refresh 抛异常，第二个正常。
    # handler 对每个池先调 get_pool(before) 再 refresh，失败池的 after 不会查，
    # 所以 get_pool 调用序：pool1-before → pool2-before → pool2-after
    svc.refresh_pool.side_effect = [RuntimeError('scoring down'), None]
    svc.get_pool.side_effect = [
        {'symbols': ['X']},        # pool1 before
        {'symbols': ['A']},        # pool2 before
        {'symbols': ['A', 'B']},   # pool2 after
    ]

    result = handle_pool_refresh_daily(service=svc)

    assert result['status'] == 'partial'
    assert result['refreshed'] == 1
    assert len(result['failed']) == 1
    assert result['failed'][0]['pool_id'] == 1
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_pool_refresh_daily.py -v
```
预期：FAIL（`handle_pool_refresh_daily` / `_is_pool_refresh_due` 不存在）

- [ ] **Step 3: 实现**

在 `quantsys-v2/application/services/scheduler_tasks.py` 中（放在 `handle_signal_generate` 之后）新增：

```python
def _is_pool_refresh_due(pool: Dict[str, Any], today: date) -> bool:
    """判断动态池是否到期该刷新。

    refresh_interval 约定：'daily' 每个交易日刷；'weekly' 距上次 ≥7 天；
    其他/缺失值按 daily 处理（宁多刷不漏刷）。
    """
    interval = (pool.get('refresh_interval') or 'daily').lower()
    if interval == 'weekly':
        last = pool.get('last_refreshed_at')
        if not last:
            return True
        try:
            last_date = datetime.fromisoformat(str(last).split(' ')[0]).date()
            return (today - last_date).days >= 7
        except ValueError:
            return True
    return True


def handle_pool_refresh_daily(
    params: Dict[str, Any] = None,
    service=None,
) -> Dict[str, Any]:
    """每日动态池刷新任务（02:00）

    刷新所有到期动态池，记录成员变更；有变更时通知 Agent（pool_changed）。
    service 参数用于测试注入；默认使用 API 共享单例。
    """
    params = params or {}
    logger.info("Starting pool_refresh_daily task")

    if service is None:
        from adapters.inbound.api.shared import stock_pool_service
        service = stock_pool_service

    today = date.today()
    refreshed, skipped, failed = [], [], []

    for pool in service.list_pools():
        if pool.get('pool_type') != 'dynamic':
            continue
        if not _is_pool_refresh_due(pool, today):
            skipped.append({'pool_id': pool['id'], 'name': pool['name']})
            continue
        try:
            before_symbols = set(service.get_pool(pool['id']).get('symbols', []))
            service.refresh_pool(pool['id'])
            after_symbols = set(service.get_pool(pool['id']).get('symbols', []))
            refreshed.append({
                'pool_id': pool['id'],
                'name': pool['name'],
                'added': sorted(after_symbols - before_symbols),
                'removed': sorted(before_symbols - after_symbols),
            })
        except Exception as e:
            logger.error(f"Failed to refresh pool {pool['id']}: {e}")
            failed.append({'pool_id': pool['id'], 'name': pool['name'], 'error': str(e)})

    changed = [r for r in refreshed if r['added'] or r['removed']]
    if changed and not params.get('skip_notify'):
        try:
            from application.services.agent_notification_service import agent_service
            agent_service.notify_agent('pool_changed', {
                'trade_date': today.isoformat(),
                'pools_changed': changed,
                'account': 'agent_virtual',
            })
        except Exception as e:
            logger.warning(f"pool_changed notify failed: {e}")

    return {
        "action": "pool_refresh_daily",
        "status": "success" if not failed else "partial",
        "refreshed": len(refreshed),
        "changed": len(changed),
        "skipped": len(skipped),
        "failed": failed,
        "timestamp": datetime.now().isoformat(),
    }
```

在 `_TASK_HANDLERS` 字典（约 1005 行 `"signal_generate"` 之后）注册：

```python
    "pool_refresh_daily": handle_pool_refresh_daily,
```

确认文件顶部已 import `date`（`from datetime import datetime, date`），没有则补上。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_pool_refresh_daily.py -v
```
预期：5 passed

- [ ] **Step 5: 种子注册**

修改 `quantsys-v2/scripts/init_scheduler_tasks.py` 的 `DEFAULT_TASKS`，在列表末尾追加：

```python
    {
        'name': 'daily-pool-refresh',
        'cron_expression': '0 2 * * 1-5',  # 工作日 02:00
        'command': 'pool_refresh_daily',
        'params': {},
        'description': '每日刷新到期动态股票池（盈利闭环：找股票环节）'
    },
```

验证（种子脚本是幂等的，已存在则跳过）：

```bash
cd quantsys-v2 && .venv-py313/bin/python scripts/init_scheduler_tasks.py 2>&1 | grep -E "pool-refresh|创建|跳过"
```
预期输出包含 `daily-pool-refresh`（首次运行为"已创建"，重复运行为"已存在，跳过"）

- [ ] **Step 6: Commit**

```bash
git add quantsys-v2/application/services/scheduler_tasks.py quantsys-v2/scripts/init_scheduler_tasks.py quantsys-v2/tests/test_pool_refresh_daily.py
git commit -m "feat: 动态池每日自动刷新任务（pool_refresh_daily，02:00）+ pool_changed 事件"
```

---

## Phase 3 — v2：信号兜底推送（断点 4）

### Task 5: handle_signal_execution_daily 改造为兜底重推 + 种子

**目的：** 该处理器当前会调用 `execute_daily_signals()` 下单。改造为：只收集 pending 信号并重推 signals_ready（agent 侧判重，重复推送无副作用），作为 orchestrator 推送的兜底。同时补入调度种子。

**Files:**
- Modify: `quantsys-v2/application/services/scheduler_tasks.py:229-253`
- Modify: `quantsys-v2/scripts/init_scheduler_tasks.py`（DEFAULT_TASKS）
- Test: `quantsys-v2/tests/test_signal_execution_fallback.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/test_signal_execution_fallback.py`：

```python
"""signal_execution_daily 兜底推送改造测试"""
from unittest.mock import patch

from application.services.scheduler_tasks import handle_signal_execution_daily


@patch('application.services.agent_notification_service.agent_service')
@patch('application.services.signal_execution_scheduler.SignalExecutionScheduler')
def test_repushes_signals_without_executing(MockSched, mock_agent):
    MockSched.return_value._collect_signals.return_value = [
        {'id': 1, 'symbol': '600519.SH', 'signal_type': '买入', 'strength': 85},
    ]
    mock_agent.notify_agent_detailed.return_value = 'ok'

    result = handle_signal_execution_daily()

    MockSched.return_value.execute_daily_signals.assert_not_called()
    mock_agent.notify_agent_detailed.assert_called_once()
    event, data = mock_agent.notify_agent_detailed.call_args[0]
    assert event == 'signals_ready'
    assert data['account'] == 'agent_virtual'
    assert data['source'] == 'signal_execution_daily_fallback'
    assert result['signals_pending'] == 1
    assert result['pushed'] is True


@patch('application.services.agent_notification_service.agent_service')
@patch('application.services.signal_execution_scheduler.SignalExecutionScheduler')
def test_no_signals_no_push(MockSched, mock_agent):
    MockSched.return_value._collect_signals.return_value = []

    result = handle_signal_execution_daily()

    mock_agent.notify_agent_detailed.assert_not_called()
    assert result['signals_pending'] == 0
    assert result['pushed'] is False
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_signal_execution_fallback.py -v
```
预期：FAIL（当前实现调用 `execute_daily_signals`）

- [ ] **Step 3: 实现**

替换 `quantsys-v2/application/services/scheduler_tasks.py` 的 `handle_signal_execution_daily`（229-253 行）：

```python
def handle_signal_execution_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每日信号汇总推送（兜底重推）

    2026-07-24 盈利闭环改造：v2 不再自动下单。本任务只把当日 pending
    信号再次推送给 Agent（orchestrator MARKET_OPEN 推送的兜底），
    Agent 侧按信号 ID 判重，重复推送不会重复交易。
    """
    params = params or {}

    from application.services.signal_execution_scheduler import SignalExecutionScheduler

    logger.info("Starting daily signal summary push (fallback)")

    try:
        scheduler = SignalExecutionScheduler()
        signals = scheduler._collect_signals(date.today().strftime('%Y-%m-%d'))

        pushed = False
        if signals and not params.get('skip_notify'):
            from application.services.agent_notification_service import agent_service
            result = agent_service.notify_agent_detailed('signals_ready', {
                'trade_date': date.today().isoformat(),
                'signal_count': len(signals),
                'signals': signals[:20],
                'account': 'agent_virtual',
                'source': 'signal_execution_daily_fallback',
            })
            # timeout 视为已送达（agent 正在处理），不重推
            pushed = result in ('ok', 'timeout')

        return {
            "action": "signal_execution_daily",
            "status": "success",
            "signals_pending": len(signals),
            "pushed": pushed,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Signal summary push failed: {e}")
        return {
            "action": "signal_execution_daily",
            "status": "failed",
            "error": str(e)
        }
```

确认文件顶部已 import `date`。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_signal_execution_fallback.py -v
```
预期：2 passed

- [ ] **Step 5: 种子注册**

修改 `quantsys-v2/scripts/init_scheduler_tasks.py` 的 `DEFAULT_TASKS`，追加：

```python
    {
        'name': 'daily-signal-push-fallback',
        'cron_expression': '40 9 * * 1-5',  # 工作日 09:40（MARKET_OPEN 窗口结束后兜底重推）
        'command': 'signal_execution_daily',
        'params': {},
        'description': '信号兜底推送（orchestrator signals_ready 的重推，agent 判重）'
    },
```

验证：

```bash
cd quantsys-v2 && .venv-py313/bin/python scripts/init_scheduler_tasks.py 2>&1 | grep -E "signal-push|创建|跳过"
```

- [ ] **Step 6: Commit**

```bash
git add quantsys-v2/application/services/scheduler_tasks.py quantsys-v2/scripts/init_scheduler_tasks.py quantsys-v2/tests/test_signal_execution_fallback.py
git commit -m "feat: signal_execution_daily 改造为信号兜底推送（不再下单）+ 种子注册"
```

---

## Phase 4 — v2：风控护栏与账户冻结（断点 2 收尾）

### Task 6: AccountTradingService 账户级日限额

**目的：** 服务端硬护栏——单日买入 ≤5 笔、单日买入金额 ≤总资产 50%。防止 LLM 失控满仓/高频交易。

**Files:**
- Modify: `quantsys-v2/application/services/account_trading_service.py:19-26`（常量）、`97-110`（buy 分支）
- Test: `quantsys-v2/tests/test_account_daily_limits.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/test_account_daily_limits.py`：

```python
"""账户级日买入限额测试（服务端硬护栏）"""
import pytest
from unittest.mock import MagicMock

from application.services.account_trading_service import (
    AccountTradingService,
    TradingError,
)


class FakeTrade:
    def __init__(self, action, amount):
        self.action = action
        self.amount = amount


def _svc_with_trades(trades):
    repo = MagicMock()
    repo.get_trades_by_account.return_value = trades
    return AccountTradingService(repo=repo)


def test_daily_buy_count_limit_reached():
    svc = _svc_with_trades([FakeTrade('buy', 1000)] * 5)
    with pytest.raises(TradingError, match='单日买入笔数超限'):
        svc._check_daily_buy_limits('agent_virtual', 1000, 100000)


def test_daily_buy_count_under_limit_passes():
    svc = _svc_with_trades([FakeTrade('buy', 1000)] * 4)
    svc._check_daily_buy_limits('agent_virtual', 1000, 100000)  # 不抛异常


def test_daily_buy_amount_limit():
    """今日已买 4.5 万，再买 1 万 → 5.5 万 > 总资产 10 万的 50%"""
    svc = _svc_with_trades([FakeTrade('buy', 45000)])
    with pytest.raises(TradingError, match='单日买入金额超限'):
        svc._check_daily_buy_limits('agent_virtual', 10000, 100000)


def test_daily_buy_amount_at_boundary_passes():
    """已买 4 万 + 本次 1 万 = 5 万 = 50%，不超限"""
    svc = _svc_with_trades([FakeTrade('buy', 40000)])
    svc._check_daily_buy_limits('agent_virtual', 10000, 100000)  # 不抛异常


def test_sell_trades_not_counted():
    """卖出不计入买入限额"""
    svc = _svc_with_trades([FakeTrade('sell', 90000)] * 10)
    svc._check_daily_buy_limits('agent_virtual', 10000, 100000)  # 不抛异常
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_account_daily_limits.py -v
```
预期：FAIL（`_check_daily_buy_limits` 不存在）

- [ ] **Step 3: 实现**

修改 `quantsys-v2/application/services/account_trading_service.py`：

常量区（24-25 行之后）追加：

```python
    MAX_DAILY_BUY_COUNT = 5              # 单日买入笔数上限
    MAX_DAILY_BUY_AMOUNT_RATIO = 0.50    # 单日买入金额占总资产上限
```

文件顶部 import 区确认有 `from datetime import date`，没有则补上。

新增方法（放在 `_get_price` 之后）：

```python
    def _check_daily_buy_limits(
        self, account_name: str, trade_amount: float, total_value: float
    ) -> None:
        """账户级日买入限额（服务端硬护栏，防 LLM 失控）。

        超限抛 TradingError，拒绝原因会返回给调用方（agent 记录后不再重试）。
        """
        today = date.today().isoformat()
        trades = self.repo.get_trades_by_account(
            account_name, start_date=today, end_date=today)
        buys = [t for t in trades if t.action == 'buy']
        if len(buys) >= self.MAX_DAILY_BUY_COUNT:
            raise TradingError(
                f'单日买入笔数超限: 今日已买 {len(buys)} 笔，'
                f'上限 {self.MAX_DAILY_BUY_COUNT} 笔', 422)
        bought_amount = sum(float(t.amount or 0) for t in buys)
        if (bought_amount + trade_amount) / total_value > self.MAX_DAILY_BUY_AMOUNT_RATIO:
            raise TradingError(
                f'单日买入金额超限: 今日已买 ¥{bought_amount:,.0f}，'
                f'本次 ¥{trade_amount:,.0f}，'
                f'超过总资产 {self.MAX_DAILY_BUY_AMOUNT_RATIO:.0%}', 422)
```

在 buy 分支（`if action == 'buy':` 内，资金检查之前，约 98 行处）插入调用：

```python
        if action == 'buy':
            self._check_daily_buy_limits(account_name, trade_amount, total_value)
            total_cost = trade_amount + commission + transfer_fee
            ...
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_account_daily_limits.py -v
```
预期：5 passed

- [ ] **Step 5: 回归——确认现有交易相关测试不破**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/ -k "trading or simulation" -x -q 2>&1 | tail -5
```
预期：全绿（若有用多笔当日买入的存量测试，给对应 repo mock 补 `get_trades_by_account` 返回值）

- [ ] **Step 6: Commit**

```bash
git add quantsys-v2/application/services/account_trading_service.py quantsys-v2/tests/test_account_daily_limits.py
git commit -m "feat: 模拟交易账户级日限额护栏（≤5笔/日、≤总资产50%/日）"
```

---

### Task 7: 账户状态管理 + 冻结旧账户

**目的：** 新增 `set_account_status` 仓储方法；冻结 `rotation_main` 和 `default`（`execute_trade` 已有 `status != 'active'` 拒绝逻辑，冻结后任何自动/手动路径都写不进这两本账）。

**Files:**
- Modify: `quantsys-v2/adapters/outbound/repositories/simulation_repository.py`（`archive_account` 之后，约 197 行）
- Create: `quantsys-v2/scripts/freeze_legacy_accounts.py`
- Test: `quantsys-v2/tests/test_simulation_repo_status.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/test_simulation_repo_status.py`（pytest 自动使用 quant_test 库）：

```python
"""账户状态管理测试"""
import uuid

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository


def test_set_account_status_roundtrip():
    repo = SimulationORMRepository()
    name = f'test_status_{uuid.uuid4().hex[:8]}'
    repo.create_account(account_name=name, initial_capital=10000)

    assert repo.set_account_status(name, 'frozen') is True
    assert repo.get_account(name).status == 'frozen'

    assert repo.set_account_status(name, 'active') is True
    assert repo.get_account(name).status == 'active'


def test_set_account_status_nonexistent():
    repo = SimulationORMRepository()
    assert repo.set_account_status('no_such_account_xyz', 'frozen') is False
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_simulation_repo_status.py -v
```
预期：FAIL（`set_account_status` 不存在）

- [ ] **Step 3: 实现**

在 `quantsys-v2/adapters/outbound/repositories/simulation_repository.py` 的 `archive_account` 方法之后新增：

```python
    def set_account_status(self, account_name: str, status: str) -> bool:
        """设置账户状态（active/frozen/archived）。

        frozen 账户被 execute_trade 拒绝写操作（status != 'active' 检查），
        用于退役旧账本但保留历史数据。
        """
        try:
            account = self.get_account(account_name)
            if not account:
                logger.warning(f"Account {account_name} not found")
                return False
            account.status = status
            self.session.commit()
            logger.info(f"账户状态变更: {account_name} → {status}")
            return True
        except Exception as e:
            logger.error(f"Error setting status for {account_name}: {e}")
            self.session.rollback()
            return False
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/test_simulation_repo_status.py -v
```
预期：2 passed

- [ ] **Step 5: 冻结脚本**

创建 `quantsys-v2/scripts/freeze_legacy_accounts.py`：

```python
#!/usr/bin/env python
"""冻结旧模拟账户（盈利闭环改造，2026-07-24）

唯一交易账本为 agent_virtual；rotation_main/default 冻结防误写。
历史数据保留，可随时解冻（status 改回 active）。

用法: .venv-py313/bin/python scripts/freeze_legacy_accounts.py
"""
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

LEGACY_ACCOUNTS = ['rotation_main', 'default']


def main():
    repo = SimulationORMRepository()
    for name in LEGACY_ACCOUNTS:
        if not repo.get_account(name):
            print(f'⊙ 账户不存在，跳过: {name}')
            continue
        repo.set_account_status(name, 'frozen')
        print(f'✓ 已冻结: {name}')


if __name__ == '__main__':
    main()
```

对生产库执行（手动确认后）：

```bash
cd quantsys-v2 && .venv-py313/bin/python scripts/freeze_legacy_accounts.py
```
预期输出：`✓ 已冻结: rotation_main` 和 `✓ 已冻结: default`

验证：

```bash
curl -s http://127.0.0.1:5001/api/simulation/accounts | python3 -c "import json,sys; [print(a['account_name'], a['status']) for a in json.load(sys.stdin)['data']['accounts']]"
```
预期：rotation_main 和 default 不出现在列表（`list_accounts(status='active')` 只返回 active）

- [ ] **Step 6: Commit**

```bash
git add quantsys-v2/adapters/outbound/repositories/simulation_repository.py quantsys-v2/scripts/freeze_legacy_accounts.py quantsys-v2/tests/test_simulation_repo_status.py
git commit -m "feat: 账户状态管理 set_account_status + 冻结 rotation_main/default 旧账本"
```

---

## Phase 5 — agent：事件链与每周进化（断点 5）

### Task 8: wake-channel 新增 signals_ready 决策链

**目的：** agent 收到 signals_ready 事件后走完整决策链：判重 → 查持仓(agent_virtual) → 逐信号评估 → portfolio_trade / decision_record → 摘要通知。

**Files:**
- Modify: `agent-ts/src/api/wake-channel.ts:227`（导出 `buildPromptFromEvent`）、`328-329` 附近（新增 case）
- Test: `agent-ts/src/api/wake-channel-signals.test.ts`

- [ ] **Step 1: 写失败测试**

创建 `agent-ts/src/api/wake-channel-signals.test.ts`：

```typescript
import { buildPromptFromEvent } from "./wake-channel.js";

describe("signals_ready 事件 prompt", () => {
  const data = {
    trade_date: "2026-07-24",
    signal_count: 2,
    signals: [
      { id: 1, symbol: "600519.SH", signal_type: "买入", strength: 85, strategy: "v13" },
      { id: 2, symbol: "000858.SZ", signal_type: "买入", strength: 78, strategy: "v13" },
    ],
    account: "agent_virtual",
  };

  it("包含信号列表和 ID（判重依据）", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, data);
    expect(prompt).toContain("600519.SH");
    expect(prompt).toContain("ID:1");
    expect(prompt).toContain("ID:2");
  });

  it("固定唯一账本 agent_virtual", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, data);
    expect(prompt).toContain("agent_virtual");
  });

  it("包含判重指引（兜底重推不会重复交易）", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, data);
    expect(prompt).toContain("判重");
    expect(prompt).toContain("decision_history");
  });

  it("包含服务端硬护栏说明", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, data);
    expect(prompt).toContain("单日");
  });

  it("0 信号也能生成 prompt", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, {
      trade_date: "2026-07-24",
      signal_count: 0,
      signals: [],
      account: "agent_virtual",
    });
    expect(prompt).toContain("0");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd agent-ts && npm test -- wake-channel-signals 2>&1 | tail -10
```
预期：FAIL（`buildPromptFromEvent` 未导出 / 无 signals_ready case）

- [ ] **Step 3: 实现**

修改 `agent-ts/src/api/wake-channel.ts`：

1. 227 行处把 `function buildPromptFromEvent(` 改为 `export function buildPromptFromEvent(`

2. 在 `case 'signal_generated':` 之前新增 case：

```typescript
    case 'signals_ready': {
      const signalList: any[] = data?.signals || [];
      const signalLines = signalList.length > 0
        ? signalList.map((s: any, i: number) =>
            `${i + 1}. [ID:${s.id ?? 'N/A'}] ${s.symbol || 'N/A'} ${s.signal_type || ''} 强度:${s.strength ?? 'N/A'} 策略:${s.strategy_name || s.strategy || 'N/A'}`
          ).join('\n')
        : '（今日无信号）';
      return `【今日信号就绪】${data?.trade_date || '今日'} V2 已生成 ${data?.signal_count ?? signalList.length} 个待处理信号。

信号列表:
${signalLines}

你操作的唯一账本是 agent_virtual。请按以下决策链操作（每步都要看返回结果再决定下一步）：

1. 调用 decision_history 检查今日是否已处理过这些信号
   → 按信号 ID 判重：已决策过的信号直接跳过（本事件可能因兜底机制重推）
2. 调用 portfolio_status({ action: 'get', account: 'agent_virtual' }) 查看持仓与可用资金
3. 逐信号评估：是否已持仓？与现有持仓是否同板块重复？信号强度是否 ≥70？
4. 决定买入的信号：调用 portfolio_trade({ account: 'agent_virtual', action: 'buy', symbol, amount, reason })
   → reason 必须 ≥10 字，引用信号 ID 和理由
   → 服务端硬护栏：单股≤30%、最多3只、总仓≤80%、单日买入≤5笔、单日买入≤总资产50%
   → 被护栏拒绝时：decision_record 记录原因，降仓位最多重试一次，不要反复重试
5. 放弃的信号：调用 decision_record 记录放弃理由（这也是学习数据）
6. 全部处理完：调用 knowledge_record 写今日信号处理摘要，feishu_notify 通知用户（处理了几条、买了什么、放弃了什么）

注意：不要因为信号多就全买。没有把握就全部放弃并记录理由——空仓也是合法决策。`;
    }
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd agent-ts && npm test -- wake-channel-signals 2>&1 | tail -10
```
预期：5 passed

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/wake-channel.ts agent-ts/src/api/wake-channel-signals.test.ts
git commit -m "feat: wake-channel 新增 signals_ready 专用决策链（判重+agent_virtual+护栏说明）"
```

---

### Task 9: agent 定时任务更新（早盘兜底 + 固定账户 + 每周进化）

**目的：**（a）早盘任务固定 agent_virtual 账户并增加"补处理昨日未处理信号"兜底；（b）日复盘增加信号覆盖率统计；（c）注册 weekly_evolution 定时任务（周日 20:00，执行器已支持该 kind）。

**Files:**
- Modify: `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts`
- Modify: `agent-ts/src/services/scheduler/init-agent-tasks.ts:52`（摘要过滤列表）
- Test: `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.test.ts`

- [ ] **Step 1: 写失败测试**

创建 `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.test.ts`：

```typescript
import { createAgentDecisionTasks } from "./agent-decision-tasks.js";

describe("createAgentDecisionTasks", () => {
  const tasks = createAgentDecisionTasks();
  const byName = (n: string) => tasks.find(t => t.name === n);

  it("包含每周进化任务（周日 20:00）", () => {
    const weekly = byName("weekly_evolution");
    expect(weekly).toBeDefined();
    expect(weekly!.scheduleKind).toBe("cron");
    expect(weekly!.scheduleExpr).toBe("0 20 * * 0");
    expect((weekly!.payload as any).kind).toBe("weekly_evolution");
    expect(weekly!.enabled).toBe(true);
  });

  it("早盘任务固定唯一账本 agent_virtual", () => {
    const morning = byName("morning_ai_analysis");
    const msg = (morning!.payload as any).message as string;
    expect(msg).toContain("agent_virtual");
  });

  it("早盘任务包含昨日信号兜底检查", () => {
    const morning = byName("morning_ai_analysis");
    const msg = (morning!.payload as any).message as string;
    expect(msg).toContain("兜底");
    expect(msg).toContain("signals_ready");
  });

  it("日复盘包含信号处理覆盖率统计", () => {
    const review = byName("daily_ai_review");
    const msg = (review!.payload as any).message as string;
    expect(msg).toContain("覆盖率");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd agent-ts && npm test -- agent-decision-tasks 2>&1 | tail -10
```
预期：FAIL（无 weekly_evolution 任务；早盘 prompt 无 agent_virtual/兜底；复盘无覆盖率）

- [ ] **Step 3: 实现**

修改 `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts`：

1. **早盘任务 message 改造**——把"第一步：检查虚拟仓持仓"整节（第 23-36 行）替换为：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：检查持仓（唯一账本 agent_virtual）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 你操作的唯一账本是 agent_virtual（不要操作其他任何账户）。
   使用 portfolio_status({ action: 'get', account: 'agent_virtual' }) 查看
   - 有持仓吗？持仓几只？可用资金多少？当前总盈亏如何？

2. 【兜底】检查是否有昨日生成但未处理的信号：
   - 用 decision_history 回顾昨日决策
   - 如果昨日有 signals_ready 事件但没有对应的处理记录
     （说明事件推送时你不在线），先按信号决策链补处理这些信号，
     再继续后续步骤

3. 如果有持仓，使用 portfolio_analyze({ account: 'agent_virtual' }) 分析
   - 哪些需要止盈？（盈利≥10%）
   - 哪些需要止损？（亏损≥5%）
   - 哪些继续持有？
   - 注意T+1：今日买入的明天才能卖
```

message 中后续所有 `portfolio_status({ action: 'list' })`、`portfolio_status({ action: 'get', account: '<账户名>' })`、`portfolio_analyze({ account: '<账户名>' })` 引用统一改为 `account: 'agent_virtual'`，删除"先确认要操作哪个账户"的表述。

2. **日复盘 message 改造**——在"第二步：回顾今日交易"开头（第 178-189 行区域）插入覆盖率统计：

```
1. 统计今日信号处理覆盖率：
   - 今日收到几条 signals_ready 信号？处理了几条？成交了几笔？
   - 用 decision_history 核对，把"收到N/处理N/成交N"写入 knowledge_record

2. 使用 trade_monitor 查看今日交易记录
   ...（原有内容）
```

（原有序号顺延。）

3. **新增每周进化任务**——在 `daily_ai_review` 任务对象之后追加：

```typescript
    // 4. 每周进化 - 绩效归因 + 经验评审 + 策略调整建议
    {
      name: 'weekly_evolution',
      enabled: true,
      scheduleKind: 'cron',
      scheduleExpr: '0 20 * * 0',  // 每周日 20:00
      payload: {
        kind: 'weekly_evolution',
      },
      compensationEnabled: false,
      compensationCheckAfter: undefined,
      compensationMaxAttempts: 0,
      deleteAfterRun: false
    }
```

4. **init-agent-tasks.ts 摘要列表**——52 行的过滤数组改为：

```typescript
      ['morning_ai_analysis', 'realtime_quick_check', 'daily_ai_review', 'weekly_evolution'].includes(s.name)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd agent-ts && npm test -- agent-decision-tasks 2>&1 | tail -10
```
预期：4 passed

- [ ] **Step 5: 类型检查**

```bash
cd agent-ts && npx tsc -p tsconfig.build.json --noEmit 2>&1 | grep -E "agent-decision-tasks|wake-channel" | head -5
```
预期：无输出（这两个文件无类型错误；`payload.kind: 'weekly_evolution'` 需匹配 SchedulerTask 的 payload 类型，若不匹配按现有类型定义补充字段）

- [ ] **Step 6: Commit**

```bash
git add agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts agent-ts/src/services/scheduler/tasks/agent-decision-tasks.test.ts agent-ts/src/services/scheduler/init-agent-tasks.ts
git commit -m "feat: agent 定时任务闭环——早盘兜底+固定 agent_virtual+复盘覆盖率+每周进化任务"
```

---

## Phase 6 — supervisor 与端到端冒烟（断点 3）

### Task 10: 统一进程 supervisor

**目的：** 一个命令拉起并守护闭环全部 4 进程，健康检查 + 崩溃重启（指数退避）+ 飞书告警 + 状态文件。

**Files:**
- Create: `scripts/loop_supervisor.py`
- Test: `scripts/test_loop_supervisor.py`

- [ ] **Step 1: 写失败测试**

创建 `scripts/test_loop_supervisor.py`（纯单元测试，不依赖 DB/网络）：

```python
"""loop_supervisor 核心逻辑测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loop_supervisor import next_backoff, should_restart, PROCESSES


def test_backoff_sequence():
    """指数退避：1min → 5min → 15min 封顶"""
    assert next_backoff(1) == 60
    assert next_backoff(2) == 300
    assert next_backoff(3) == 900
    assert next_backoff(10) == 900  # 封顶


def test_should_restart_after_three_health_failures():
    assert should_restart(consecutive_health_failures=2, process_alive=True) is False
    assert should_restart(consecutive_health_failures=3, process_alive=True) is True
    assert should_restart(consecutive_health_failures=0, process_alive=False) is True


def test_process_config_integrity():
    """4 个进程配置完整：启动顺序、命令、健康检查"""
    assert [p['name'] for p in PROCESSES] == [
        'v2-api', 'v2-daemon', 'agent-dev', 'agent-wake']
    for p in PROCESSES:
        assert p['cmd'], f"{p['name']} 缺少启动命令"
        assert p['cwd'], f"{p['name']} 缺少工作目录"
        assert p['health']['type'] in ('http', 'process'), f"{p['name']} 健康检查类型非法"
    # v2-api 必须先于依赖它的进程
    assert PROCESSES[0]['name'] == 'v2-api'
    # daemon 必须用 venv python（monotonic/misfire 坑）
    assert '.venv-py313' in PROCESSES[1]['cmd'][0] or 'venv' in PROCESSES[1]['cmd'][0]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python3 -m pytest scripts/test_loop_supervisor.py -v
```
预期：FAIL（`loop_supervisor` 模块不存在）

- [ ] **Step 3: 实现**

创建 `scripts/loop_supervisor.py`：

```python
#!/usr/bin/env python3
"""盈利闭环统一进程 supervisor（2026-07-24）

管理闭环全部 4 进程的生命周期：
  1. v2-api      Flask REST API (:5001)
  2. v2-daemon   scheduler_daemon（orchestrator + WatchEngine 只在这里启动）
  3. agent-dev   agent 主进程（定时决策任务）
  4. agent-wake  agent wake channel (:3100，接收 v2 推送)

用法:
  python3 scripts/loop_supervisor.py start    # 拉起全部并进入监控循环（前台）
  python3 scripts/loop_supervisor.py stop     # 优雅停止全部
  python3 scripts/loop_supervisor.py status   # 查看状态

边界说明：supervisor 解决"进程活着"，不解决笔记本合盖休眠（物理约束）。
唤醒后由 APScheduler misfire 修复 + agent 早盘兜底检查恢复。
"""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / 'logs' / 'supervisor'
STATUS_FILE = LOG_DIR / 'status.json'

VENV_PY = ROOT / 'quantsys-v2' / '.venv-py313' / 'bin' / 'python'
if not VENV_PY.exists():
    print(f'⚠️  未找到 {VENV_PY}，回退到当前解释器 {sys.executable}')
    VENV_PY = Path(sys.executable)

PROCESSES = [
    {
        'name': 'v2-api',
        'cwd': str(ROOT / 'quantsys-v2'),
        'cmd': [str(VENV_PY), 'adapters/inbound/api/server.py'],
        'health': {'type': 'http', 'url': 'http://127.0.0.1:5001/api/health'},
    },
    {
        'name': 'v2-daemon',
        'cwd': str(ROOT / 'quantsys-v2'),
        'cmd': [str(VENV_PY), 'scheduler_daemon.py'],
        'health': {'type': 'process'},
    },
    {
        'name': 'agent-dev',
        'cwd': str(ROOT / 'agent-ts'),
        'cmd': ['npm', 'run', 'dev'],
        'health': {'type': 'process'},
    },
    {
        'name': 'agent-wake',
        'cwd': str(ROOT / 'agent-ts'),
        'cmd': ['npm', 'run', 'wake'],
        'health': {'type': 'http', 'url': 'http://127.0.0.1:3100/wake/health'},
    },
]

HEALTH_INTERVAL = 30          # 健康检查间隔（秒）
HEALTH_FAIL_THRESHOLD = 3     # 连续失败 N 次才重启
BACKOFF_STEPS = [60, 300, 900]  # 重启退避（秒），封顶 15min
MAX_CONSECUTIVE_RESTARTS = 3  # 连续重启 N 次仍失败 → 告警并放弃该进程


def next_backoff(restart_count: int) -> int:
    """指数退避：1min → 5min → 15min 封顶"""
    idx = min(restart_count - 1, len(BACKOFF_STEPS) - 1)
    return BACKOFF_STEPS[max(idx, 0)]


def should_restart(consecutive_health_failures: int, process_alive: bool) -> bool:
    """进程死了立即重启；健康检查连续失败达阈值才重启"""
    if not process_alive:
        return True
    return consecutive_health_failures >= HEALTH_FAIL_THRESHOLD


def check_http_health(url: str, timeout: int = 5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def alert(message: str):
    """飞书告警（webhook 未配置则只记日志，绝不静默）"""
    line = f'[loop_supervisor] {message}'
    print(f'🚨 {line}', flush=True)
    webhook = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook:
        return
    try:
        import urllib.request as req
        payload = json.dumps({'msg_type': 'text', 'content': {'text': line}}).encode()
        request = req.Request(webhook, data=payload,
                              headers={'Content-Type': 'application/json'})
        req.urlopen(request, timeout=10)
    except Exception as e:
        print(f'⚠️  飞书告警发送失败: {e}', flush=True)


class ProcessGuard:
    """单进程守护：启动、日志重定向、健康检查、重启退避"""

    def __init__(self, config: dict):
        self.cfg = config
        self.name = config['name']
        self.proc: subprocess.Popen | None = None
        self.restart_count = 0
        self.consecutive_restarts = 0
        self.health_failures = 0
        self.gave_up = False
        self.last_restart_at: float = 0
        self.log_path = LOG_DIR / f'{self.name}.log'

    def start(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = open(self.log_path, 'a')
        log_file.write(f'\n===== {datetime.now().isoformat()} start =====\n')
        log_file.flush()
        self.proc = subprocess.Popen(
            self.cfg['cmd'],
            cwd=self.cfg['cwd'],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 独立进程组，stop 时整组终止
        )
        self.health_failures = 0
        print(f'✅ [{self.name}] 已启动 pid={self.proc.pid}', flush=True)

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def check_health(self) -> bool:
        if not self.is_alive():
            return False
        health = self.cfg['health']
        if health['type'] == 'http':
            return check_http_health(health['url'])
        return True  # type == 'process'：活着即健康

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=10)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        self.proc = None

    def maintain(self):
        """每轮监控调用：按需重启（带退避和放弃机制）"""
        if self.gave_up:
            return

        alive = self.is_alive()
        if alive and self.check_health():
            self.health_failures = 0
            self.consecutive_restarts = 0
            return
        self.health_failures = 0 if not alive else self.health_failures + 1

        if not should_restart(self.health_failures, alive):
            return

        # 退避：距上次重启不足 backoff 时间则等待
        backoff = next_backoff(self.consecutive_restarts + 1)
        if time.time() - self.last_restart_at < backoff:
            return

        self.restart_count += 1
        self.consecutive_restarts += 1
        self.last_restart_at = time.time()
        alert(f'{self.name} 异常（存活={alive}, 健康失败={self.health_failures}），'
              f'第 {self.consecutive_restarts} 次重启')
        self.stop()
        self.start()

        if self.consecutive_restarts >= MAX_CONSECUTIVE_RESTARTS:
            self.gave_up = True
            alert(f'{self.name} 连续 {MAX_CONSECUTIVE_RESTARTS} 次重启仍异常，'
                  f'已放弃自动重启，需要人工介入！日志: {self.log_path}')

    def status_dict(self) -> dict:
        return {
            'pid': self.proc.pid if self.is_alive() else None,
            'alive': self.is_alive(),
            'restart_count': self.restart_count,
            'health_failures': self.health_failures,
            'gave_up': self.gave_up,
            'log': str(self.log_path),
        }


def write_status(guards: list):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        'updated_at': datetime.now().isoformat(),
        'processes': {g.name: g.status_dict() for g in guards},
    }
    STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_start():
    guards = [ProcessGuard(cfg) for cfg in PROCESSES]

    # 按依赖序拉起，等待前一个健康再拉下一个
    for g in guards:
        g.start()
        if g.cfg['health']['type'] == 'http':
            for _ in range(30):  # 最多等 30s
                if g.check_health():
                    break
                time.sleep(1)

    print('\n🔄 进入监控循环（Ctrl-C 停止全部进程）\n', flush=True)
    try:
        while True:
            for g in guards:
                g.maintain()
            write_status(guards)
            time.sleep(HEALTH_INTERVAL)
    except KeyboardInterrupt:
        print('\n🛑 收到中断，停止全部进程...', flush=True)
        for g in reversed(guards):
            g.stop()


def cmd_stop():
    if not STATUS_FILE.exists():
        print('无状态文件，supervisor 未在运行')
        return
    data = json.loads(STATUS_FILE.read_text())
    for name, info in data.get('processes', {}).items():
        pid = info.get('pid')
        if pid:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                print(f'✅ 已停止 {name} (pid={pid})')
            except ProcessLookupError:
                print(f'⊙ {name} (pid={pid}) 已不存在')
            except Exception as e:
                print(f'⚠️  停止 {name} 失败: {e}')
    STATUS_FILE.unlink()


def cmd_status():
    if not STATUS_FILE.exists():
        print('supervisor 未在运行（无状态文件）')
        return
    data = json.loads(STATUS_FILE.read_text())
    print(f"更新时间: {data['updated_at']}\n")
    for name, info in data.get('processes', {}).items():
        state = '💀 已放弃' if info['gave_up'] else ('✅ 运行中' if info['alive'] else '❌ 停止')
        print(f"  {name}: {state} pid={info['pid']} 重启{info['restart_count']}次")
        print(f"    日志: {info['log']}")


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if command == 'start':
        cmd_start()
    elif command == 'stop':
        cmd_stop()
    elif command == 'status':
        cmd_status()
    else:
        print(__doc__)
        sys.exit(1)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python3 -m pytest scripts/test_loop_supervisor.py -v
```
预期：3 passed

- [ ] **Step 5: 手动验证（不进入监控循环，只验证启动序列）**

先停掉现有手工启动的 5001 进程，然后：

```bash
python3 scripts/loop_supervisor.py status   # 预期：未在运行
```

（完整 start 验证放到 Task 11 冒烟里做，避免重复拉起进程。）

- [ ] **Step 6: Commit**

```bash
git add scripts/loop_supervisor.py scripts/test_loop_supervisor.py
git commit -m "feat: 盈利闭环统一进程 supervisor（4进程守护+健康检查+退避重启+飞书告警）"
```

---

### Task 11: 端到端冒烟脚本 + 验收

**目的：** 半自动验收脚本，按设计文档验收标准逐项检查。

**Files:**
- Create: `scripts/smoke_loop.sh`

- [ ] **Step 1: 编写冒烟脚本**

创建 `scripts/smoke_loop.sh`：

```bash
#!/usr/bin/env bash
# 盈利闭环端到端冒烟（2026-07-24）
#
# 前提：loop_supervisor 已拉起全部进程（python3 scripts/loop_supervisor.py start）
# 注意：第 5 步会真实触发 signals_ready 推送，agent 会真实决策并下模拟单
#       （agent_virtual 账户），请在你准备好接受模拟交易时运行。
set -uo pipefail

PASS=0; FAIL=0
check() {  # check <描述> <命令...>
  local desc="$1"; shift
  if "$@" > /dev/null 2>&1; then
    echo "✅ $desc"; PASS=$((PASS+1))
  else
    echo "❌ $desc"; FAIL=$((FAIL+1))
  fi
}

echo "━━━━ 1. 进程健康 ━━━━"
check "v2 API :5001 健康"        curl -sf http://127.0.0.1:5001/api/health
check "agent wake :3100 健康"    curl -sf http://127.0.0.1:3100/wake/health
check "agent 主进程存活"          pgrep -f "tsx src/index.ts"
check "scheduler_daemon 存活"     pgrep -f "scheduler_daemon.py"

echo "━━━━ 2. 账户状态 ━━━━"
ACCOUNTS=$(curl -s http://127.0.0.1:5001/api/simulation/accounts)
echo "$ACCOUNTS" | grep -q "agent_virtual" \
  && echo "✅ agent_virtual 存在" && PASS=$((PASS+1)) \
  || { echo "❌ agent_virtual 不存在"; FAIL=$((FAIL+1)); }
echo "$ACCOUNTS" | grep -q "rotation_main" \
  && { echo "❌ rotation_main 仍在 active 列表（应已冻结）"; FAIL=$((FAIL+1)); } \
  || { echo "✅ rotation_main 已冻结（不在 active 列表）"; PASS=$((PASS+1)); }

echo "━━━━ 3. 调度任务 ━━━━"
TASKS=$(curl -s http://127.0.0.1:5001/api/scheduler/tasks)
for t in daily-pool-refresh daily-signal-push-fallback; do
  echo "$TASKS" | grep -q "$t" \
    && echo "✅ 调度任务已注册: $t" && PASS=$((PASS+1)) \
    || { echo "❌ 调度任务缺失: $t（运行 scripts/init_scheduler_tasks.py）"; FAIL=$((FAIL+1)); }
done

echo "━━━━ 4. orchestrator 状态 ━━━━"
curl -s http://127.0.0.1:5001/api/orchestrator/status | head -c 300; echo

echo "━━━━ 5. 手动触发 signals_ready（真实推送，agent 将决策）━━━━"
echo "即将触发 MARKET_OPEN 阶段，agent 会对今日信号做真实模拟交易决策。"
read -r -p "确认继续？[y/N] " ans
if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
  (cd quantsys-v2 && .venv-py313/bin/python -c "
from application.services.daily_orchestrator import get_daily_orchestrator
print(get_daily_orchestrator().run_phase('MARKET_OPEN'))
")
  echo "→ 已触发。观察 agent 输出和 agent_virtual 账户变化："
  echo "  curl -s http://127.0.0.1:5001/api/simulation/accounts/agent_virtual | python3 -m json.tool"
else
  echo "⊙ 跳过"
fi

echo ""
echo "━━━━ 结果: $PASS 通过, $FAIL 失败 ━━━━"
[[ $FAIL -eq 0 ]]
```

- [ ] **Step 2: 赋可执行权限并运行（进程健康部分）**

```bash
chmod +x scripts/smoke_loop.sh
./scripts/smoke_loop.sh
```
预期：1-4 节全绿；第 5 节按提示选择是否触发真实决策

- [ ] **Step 3: 按设计文档验收标准逐项核对**

对照 `docs/superpowers/specs/2026-07-24-profit-loop-closure-design.md` 验收标准：
1. ✅ 一条命令拉起 4 进程（Task 10 + 冒烟第 1 节）
2. ✅ signals_ready 推送 → agent 决策 → 成交落在 agent_virtual（冒烟第 5 节，需交易时段或 mock 价格注入）
3. 日复盘产出（agent 侧 18:00 任务，prompt 已含覆盖率统计）——观察一次实际运行
4. 周日 20:00 每周进化自动运行——观察一次实际运行或手动触发验证
5. 杀掉任一进程 supervisor 自动重启并告警——手动 `kill <pid>` 验证
6. rotation_main/default 冻结（冒烟第 2 节）

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke_loop.sh
git commit -m "feat: 盈利闭环端到端冒烟脚本"
```

---

## 全局回归检查（所有 Task 完成后）

- [ ] v2 全量测试：`cd quantsys-v2 && .venv-py313/bin/python -m pytest tests/ -x -q 2>&1 | tail -5` —— 全绿（尤其 misfire 修复相关的 scheduler 测试）
- [ ] agent 全量测试：`cd agent-ts && npm test 2>&1 | tail -5` —— 全绿
- [ ] agent 类型检查：`cd agent-ts && npx tsc -p tsconfig.build.json --noEmit 2>&1 | head -10` —— 无新增错误
- [ ] 冒烟：`./scripts/smoke_loop.sh`
