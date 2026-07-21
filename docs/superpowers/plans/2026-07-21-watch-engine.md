# WatchEngine 实时盯盘系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 quantsys-v2 中新建 WatchEngine 服务（Agent 动态注册监视规则 → v2 自适应频率轮询实时行情 → 条件触发 → 唤醒 Agent 决策），agent-ts 增加 `watch_manage` 工具管理规则。

**Architecture:** 规则存 PostgreSQL（`quant.watch_rules` / `quant.watch_triggers`）；引擎为常驻线程（挂在 `scheduler_daemon.py`），复用 `RealtimeQuoteServiceV2` 取价（5 源 failover + 熔断 + 缓存），条件判定器为纯函数；触发经 `AgentNotificationService.notify_agent('watch_triggered', ...)` 唤醒 Agent，同时 WS broadcast 到 `market_data` 频道。API 双实现：Flask（生产 5001）+ FastAPI parity。

**Tech Stack:** Python 3.13 / SQLAlchemy ORM（`BaseORMRepository`）/ Flask Blueprint + FastAPI APIRouter / pytest；TypeScript / Jest（agent-ts）。

**Spec:** `docs/superpowers/specs/2026-07-21-watch-engine-design.md`

**关键约定（来自代码库现状，务必遵守）：**
- quantsys-v2 表都在 `quant` schema 下；迁移 SQL 放 `quantsys-v2/migrations/`
- pytest 运行时自动切 `quant_test` 库（库名须 `_test` 结尾）
- Flask 蓝图为生产路径（5001 由 `adapters/inbound/api/server.py` 提供），FastAPI 路由须保持响应契约一致
- agent-ts 工具命令名必须与 `quant-v2-client.ts` 的 `V2_ROUTES` 键**完全一致**（已有 `watch.price-alert` vs `watch.price_alert` 不匹配 bug，Task 8 顺带修复）
- `V2_ROUTES` method 仅支持 GET/POST/PUT/DELETE；URL 路径参数用 `{param}` 占位符，由 `buildRequest` 自动替换
- 涨跌幅单位统一为**百分数**（3.0 表示 3%）
- 所有条件 direction 语义统一：`above` → value >= threshold 触发；`below` → value <= threshold 触发（`velocity` 无方向，取绝对值）

---

### Task 1: 数据库迁移 + ORM 模型 + 仓储

**Files:**
- Create: `quantsys-v2/migrations/create_watch_tables.sql`
- Create: `quantsys-v2/adapters/outbound/repositories/watch_rule_repository.py`
- Test: `quantsys-v2/tests/repositories/test_watch_rule_repository.py`

- [ ] **Step 1: 写迁移 SQL**

```sql
-- quantsys-v2/migrations/create_watch_tables.sql
-- WatchEngine 实时盯盘表
-- 创建时间: 2026-07-21

CREATE TABLE IF NOT EXISTS quant.watch_rules (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    conditions JSONB NOT NULL,          -- [{"type": "...", "params": {...}, "cooldown_sec": 300}]
    context TEXT,                        -- Agent 创建时填的监视理由，触发时回传
    cost_price NUMERIC(12,4),            -- pnl_pct 条件的成本基准
    active_window JSONB,                 -- ["09:30-10:30","14:30-15:00"]，NULL = 全交易时段
    expires_at TIMESTAMP,                -- 过期自动停用，NULL = 永不过期
    created_by VARCHAR(50) DEFAULT 'agent',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watch_rules_enabled ON quant.watch_rules(enabled) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_watch_rules_symbol ON quant.watch_rules(symbol);

COMMENT ON TABLE quant.watch_rules IS 'WatchEngine 盯盘监视规则（Agent 动态注册）';
COMMENT ON COLUMN quant.watch_rules.conditions IS '条件数组，type: price_break/pct_change/pnl_pct/velocity/volume_surge';

CREATE TABLE IF NOT EXISTS quant.watch_triggers (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES quant.watch_rules(id) ON DELETE SET NULL,
    symbol VARCHAR(20) NOT NULL,
    condition JSONB NOT NULL,            -- 触发时命中的条件快照
    trigger_price NUMERIC(12,4),
    detail JSONB,                        -- 评估详情（value、message、涨跌幅等）
    agent_response JSONB,                -- Agent 决策回填（后续）
    notified BOOLEAN DEFAULT false,      -- 是否成功唤醒 Agent
    triggered_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watch_triggers_symbol_time ON quant.watch_triggers(symbol, triggered_at DESC);

COMMENT ON TABLE quant.watch_triggers IS 'WatchEngine 触发审计记录（供 Agent 学习）';
```

- [ ] **Step 2: 应用迁移到开发和测试库**

```bash
cd quantsys-v2 && source activate-py313.sh
psql -d quant_investment -f migrations/create_watch_tables.sql
psql -d quant_test -f migrations/create_watch_tables.sql
```

预期输出：两个 `CREATE TABLE` + `CREATE INDEX` + `COMMENT`，无 ERROR。

- [ ] **Step 3: 写仓储测试（先失败）**

创建 `quantsys-v2/tests/repositories/test_watch_rule_repository.py`：

```python
"""WatchRuleRepository 集成测试（使用 quant_test 库）"""
import pytest
from datetime import datetime, timedelta

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository,
)


@pytest.mark.integration
class TestWatchRuleRepository:
    def setup_method(self):
        self.repo = WatchRuleRepository()
        self.trigger_repo = WatchTriggerRepository()
        self._created_ids = []

    def teardown_method(self):
        for rid in self._created_ids:
            self.repo.delete_by_id(rid)

    def _make_rule(self, symbol='600519.SH'):
        rule = self.repo.create_rule(
            symbol=symbol,
            conditions=[{'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}}],
            context='测试规则',
            cost_price=1700.0,
            created_by='test',
        )
        self._created_ids.append(rule.id)
        return rule

    def test_create_and_get(self):
        rule = self._make_rule()
        fetched = self.repo.get_by_id(rule.id)
        assert fetched is not None
        assert fetched.symbol == '600519.SH'
        assert fetched.enabled is True
        assert fetched.conditions[0]['type'] == 'price_break'
        assert float(fetched.cost_price) == 1700.0

    def test_list_enabled_excludes_disabled_and_expired(self):
        active = self._make_rule('000001.SZ')
        disabled = self._make_rule('000002.SZ')
        self.repo.update_fields(disabled.id, enabled=False)
        expired = self._make_rule('000003.SZ')
        self.repo.update_fields(expired.id, expires_at=datetime.now() - timedelta(days=1))

        enabled_ids = {r.id for r in self.repo.list_enabled()}
        assert active.id in enabled_ids
        assert disabled.id not in enabled_ids
        assert expired.id not in enabled_ids

    def test_update_fields(self):
        rule = self._make_rule()
        updated = self.repo.update_fields(rule.id, context='新理由', enabled=False)
        assert updated.context == '新理由'
        assert updated.enabled is False

    def test_record_trigger(self):
        rule = self._make_rule()
        trigger = self.trigger_repo.record(
            rule_id=rule.id, symbol=rule.symbol,
            condition={'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}},
            trigger_price=1801.5,
            detail={'value': 1801.5, 'message': '上破 1800.0'},
            notified=True,
        )
        assert trigger.id is not None
        rows = self.trigger_repo.list_by_symbol(rule.symbol, limit=10)
        assert any(t.id == trigger.id for t in rows)
```

- [ ] **Step 4: 运行测试确认失败**

```bash
cd quantsys-v2 && source activate-py313.sh
pytest tests/repositories/test_watch_rule_repository.py -v --no-cov
```

预期：ModuleNotFoundError: No module named 'adapters.outbound.repositories.watch_rule_repository'

- [ ] **Step 5: 实现 ORM 模型 + 仓储**

创建 `quantsys-v2/adapters/outbound/repositories/watch_rule_repository.py`：

```python
"""WatchEngine 盯盘规则/触发记录 ORM Repository"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base


class WatchRule(Base):
    __tablename__ = 'watch_rules'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    enabled = Column(Boolean, default=True)
    conditions = Column(JSONB, nullable=False)
    context = Column(Text)
    cost_price = Column(Numeric(12, 4))
    active_window = Column(JSONB)
    expires_at = Column(DateTime)
    created_by = Column(String(50), default='agent')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class WatchTrigger(Base):
    __tablename__ = 'watch_triggers'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('quant.watch_rules.id', ondelete='SET NULL'))
    symbol = Column(String(20), nullable=False)
    condition = Column(JSONB, nullable=False)
    trigger_price = Column(Numeric(12, 4))
    detail = Column(JSONB)
    agent_response = Column(JSONB)
    notified = Column(Boolean, default=False)
    triggered_at = Column(DateTime, default=datetime.now)


def rule_to_dict(rule: WatchRule) -> dict:
    """序列化为 API 响应 dict（snake_case，与现有契约风格一致）"""
    return {
        'id': rule.id,
        'symbol': rule.symbol,
        'enabled': rule.enabled,
        'conditions': rule.conditions,
        'context': rule.context,
        'cost_price': float(rule.cost_price) if rule.cost_price is not None else None,
        'active_window': rule.active_window,
        'expires_at': rule.expires_at.isoformat() if rule.expires_at else None,
        'created_by': rule.created_by,
        'created_at': rule.created_at.isoformat() if rule.created_at else None,
        'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
    }


def trigger_to_dict(t: WatchTrigger) -> dict:
    return {
        'id': t.id,
        'rule_id': t.rule_id,
        'symbol': t.symbol,
        'condition': t.condition,
        'trigger_price': float(t.trigger_price) if t.trigger_price is not None else None,
        'detail': t.detail,
        'agent_response': t.agent_response,
        'notified': t.notified,
        'triggered_at': t.triggered_at.isoformat() if t.triggered_at else None,
    }


class WatchRuleRepository(BaseORMRepository[WatchRule]):
    model = WatchRule

    def create_rule(self, symbol, conditions, context=None, cost_price=None,
                    active_window=None, expires_at=None, created_by='agent') -> WatchRule:
        rule = WatchRule(
            symbol=symbol, conditions=conditions, context=context,
            cost_price=cost_price, active_window=active_window,
            expires_at=expires_at, created_by=created_by, enabled=True,
        )
        return self.create(rule)

    def list_enabled(self) -> List[WatchRule]:
        """启用的规则（排除已过期）"""
        with self.session() as s:
            return (
                s.query(WatchRule)
                .filter(WatchRule.enabled.is_(True))
                .filter((WatchRule.expires_at.is_(None)) | (WatchRule.expires_at > datetime.now()))
                .all()
            )

    def list_rules(self, symbol: Optional[str] = None,
                   enabled: Optional[bool] = None) -> List[WatchRule]:
        with self.session() as s:
            q = s.query(WatchRule)
            if symbol:
                q = q.filter(WatchRule.symbol == symbol)
            if enabled is not None:
                q = q.filter(WatchRule.enabled.is_(enabled))
            return q.order_by(WatchRule.id.desc()).all()

    def update_fields(self, rule_id: int, **fields) -> Optional[WatchRule]:
        rule = self.get_by_id(rule_id)
        if rule is None:
            return None
        allowed = {'symbol', 'enabled', 'conditions', 'context',
                   'cost_price', 'active_window', 'expires_at'}
        for key, value in fields.items():
            if key in allowed:
                setattr(rule, key, value)
        rule.updated_at = datetime.now()
        return self.update(rule)


class WatchTriggerRepository(BaseORMRepository[WatchTrigger]):
    model = WatchTrigger

    def record(self, rule_id, symbol, condition, trigger_price,
               detail=None, notified=False) -> WatchTrigger:
        trigger = WatchTrigger(
            rule_id=rule_id, symbol=symbol, condition=condition,
            trigger_price=trigger_price, detail=detail, notified=notified,
        )
        return self.create(trigger)

    def list_by_symbol(self, symbol: Optional[str] = None, limit: int = 50) -> List[WatchTrigger]:
        with self.session() as s:
            q = s.query(WatchTrigger)
            if symbol:
                q = q.filter(WatchTrigger.symbol == symbol)
            return q.order_by(WatchTrigger.triggered_at.desc()).limit(limit).all()
```

注意：若 `BaseORMRepository` 子类化方式与 `AutomationTaskRepository` 不同（例如用 `__init__` 传 model），先打开 `adapters/outbound/repositories/automation_repository.py` 对齐其写法（该类是本仓库的仓储范式）。

- [ ] **Step 6: 运行测试确认通过**

```bash
pytest tests/repositories/test_watch_rule_repository.py -v --no-cov
```

预期：4 passed

- [ ] **Step 7: Commit**

```bash
git add migrations/create_watch_tables.sql adapters/outbound/repositories/watch_rule_repository.py tests/repositories/test_watch_rule_repository.py
git commit -m "feat: WatchEngine 盯盘表迁移 + ORM 仓储"
```

---

### Task 2: 条件判定器（纯函数）

**Files:**
- Create: `quantsys-v2/application/services/watch_engine/__init__.py`（空文件）
- Create: `quantsys-v2/application/services/watch_engine/conditions.py`
- Test: `quantsys-v2/tests/services/test_watch_conditions.py`

**语义约定：**
- `above` → value >= threshold 触发；`below` → value <= threshold 触发
- `distance_ratio`：距触发的归一化距离，0 = 已触达，越大越远，None = 无法评估。用于引擎自适应升档（<= buffer_ratio 升 10s 档）
- 百分数单位：3.0 表示 3%
- `velocity` / `volume_surge` 数据不足时返回 `triggered=False, distance_ratio=None`，不报错（冷启动降级）

- [ ] **Step 1: 写测试（先失败）**

创建 `quantsys-v2/tests/services/test_watch_conditions.py`：

```python
"""盯盘条件判定器单测（纯函数）"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from application.services.watch_engine.conditions import (
    EvalContext, evaluate, validate_condition,
)


def make_quote(price=100.0, prev_close=98.0, volume=5_000_000, change_pct=None):
    return SimpleNamespace(price=price, prev_close=prev_close,
                           volume=volume, change_pct=change_pct)


NOW = datetime(2026, 7, 21, 10, 30)


class TestValidate:
    @pytest.mark.parametrize('cond', [
        {'type': 'price_break', 'params': {'direction': 'above', 'price': 1.0}},
        {'type': 'pct_change', 'params': {'direction': 'above', 'pct': 3.0}},
        {'type': 'pnl_pct', 'params': {'direction': 'below', 'pct': -8.0}},
        {'type': 'velocity', 'params': {'pct': 2.0, 'window_min': 5}},
        {'type': 'volume_surge', 'params': {'multiple': 2.0}},
    ])
    def test_valid_types(self, cond):
        validate_condition(cond)  # 不抛异常

    def test_unknown_type_rejected(self):
        with pytest.raises(ValueError, match='未知条件类型'):
            validate_condition({'type': 'magic', 'params': {}})

    def test_price_break_requires_price(self):
        with pytest.raises(ValueError):
            validate_condition({'type': 'price_break', 'params': {'direction': 'above'}})


class TestPriceBreak:
    def test_above_triggered(self):
        r = evaluate({'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}},
                     make_quote(price=100.0), EvalContext())
        assert r.triggered is True
        assert r.distance_ratio == 0.0

    def test_above_not_triggered_with_distance(self):
        r = evaluate({'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}},
                     make_quote(price=95.0), EvalContext())
        assert r.triggered is False
        assert r.distance_ratio == pytest.approx(0.05)

    def test_below_triggered(self):
        r = evaluate({'type': 'price_break', 'params': {'direction': 'below', 'price': 90.0}},
                     make_quote(price=89.5), EvalContext())
        assert r.triggered is True


class TestPctChange:
    def test_uses_prev_close(self):
        # (100-98)/98*100 ≈ 2.04%
        r = evaluate({'type': 'pct_change', 'params': {'direction': 'above', 'pct': 2.0}},
                     make_quote(), EvalContext())
        assert r.triggered is True
        assert r.value == pytest.approx(2.0408, abs=0.001)

    def test_below_direction(self):
        r = evaluate({'type': 'pct_change', 'params': {'direction': 'below', 'pct': -3.0}},
                     make_quote(price=94.0, prev_close=98.0), EvalContext())
        assert r.triggered is True  # -4.08% <= -3%

    def test_fallback_to_quote_change_pct(self):
        q = make_quote(prev_close=None, change_pct=3.5)
        r = evaluate({'type': 'pct_change', 'params': {'direction': 'above', 'pct': 3.0}},
                     q, EvalContext())
        assert r.triggered is True
        assert r.value == 3.5

    def test_no_data_returns_unavailable(self):
        q = make_quote(prev_close=None, change_pct=None)
        r = evaluate({'type': 'pct_change', 'params': {'direction': 'above', 'pct': 3.0}},
                     q, EvalContext())
        assert r.triggered is False
        assert r.distance_ratio is None


class TestPnlPct:
    def test_profit_trigger(self):
        ctx = EvalContext(cost_price=90.0)
        r = evaluate({'type': 'pnl_pct', 'params': {'direction': 'above', 'pct': 10.0}},
                     make_quote(price=100.0), ctx)
        assert r.triggered is True  # +11.1% >= 10%

    def test_loss_trigger(self):
        ctx = EvalContext(cost_price=110.0)
        r = evaluate({'type': 'pnl_pct', 'params': {'direction': 'below', 'pct': -8.0}},
                     make_quote(price=100.0), ctx)
        assert r.triggered is True  # -9.09% <= -8%

    def test_no_cost_price_unavailable(self):
        r = evaluate({'type': 'pnl_pct', 'params': {'direction': 'above', 'pct': 10.0}},
                     make_quote(), EvalContext(cost_price=None))
        assert r.triggered is False
        assert r.distance_ratio is None


class TestVelocity:
    def test_trigger_within_window(self):
        history = (
            (NOW - timedelta(minutes=4), 100.0),
            (NOW, 103.0),
        )
        ctx = EvalContext(price_history=history)
        r = evaluate({'type': 'velocity', 'params': {'pct': 2.5, 'window_min': 5}},
                     make_quote(price=103.0), ctx, now=NOW)
        assert r.triggered is True
        assert r.value == pytest.approx(3.0)

    def test_ignores_points_outside_window(self):
        history = (
            (NOW - timedelta(minutes=20), 80.0),   # 窗口外
            (NOW - timedelta(minutes=2), 100.0),
            (NOW, 101.0),
        )
        ctx = EvalContext(price_history=history)
        r = evaluate({'type': 'velocity', 'params': {'pct': 2.5, 'window_min': 5}},
                     make_quote(price=101.0), ctx, now=NOW)
        assert r.triggered is False
        assert r.value == pytest.approx(1.0)

    def test_insufficient_history(self):
        ctx = EvalContext(price_history=())
        r = evaluate({'type': 'velocity', 'params': {'pct': 2.5, 'window_min': 5}},
                     make_quote(), ctx, now=NOW)
        assert r.triggered is False
        assert r.distance_ratio is None


class TestVolumeSurge:
    def test_trigger(self):
        ctx = EvalContext(avg_volume_20d=10_000_000, elapsed_fraction=0.25)
        # 基准 = 1000万 * 0.25 = 250万；实际 500万 → 2.0x
        r = evaluate({'type': 'volume_surge', 'params': {'multiple': 2.0}},
                     make_quote(volume=5_000_000), ctx)
        assert r.triggered is True
        assert r.value == pytest.approx(2.0)

    def test_no_avg_volume_unavailable(self):
        ctx = EvalContext(avg_volume_20d=None)
        r = evaluate({'type': 'volume_surge', 'params': {'multiple': 2.0}},
                     make_quote(), ctx)
        assert r.triggered is False
        assert r.distance_ratio is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/services/test_watch_conditions.py -v --no-cov
```

预期：ModuleNotFoundError: No module named 'application.services.watch_engine'

- [ ] **Step 3: 实现 conditions.py**

创建 `quantsys-v2/application/services/watch_engine/__init__.py`（空）和 `quantsys-v2/application/services/watch_engine/conditions.py`：

```python
"""WatchEngine 条件判定器 —— 纯函数，无 I/O，无外部依赖

语义约定：
- direction 'above' → value >= threshold 触发；'below' → value <= threshold 触发
- velocity 无方向，取窗口内涨跌幅绝对值
- 百分数单位：3.0 表示 3%
- distance_ratio: 距触发的归一化距离（0=已触达），供引擎自适应频率升档；None=无法评估
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Tuple

VALID_TYPES = {'price_break', 'pct_change', 'pnl_pct', 'velocity', 'volume_surge'}

DEFAULT_COOLDOWN_SEC = 300


@dataclass
class EvalResult:
    triggered: bool
    value: Optional[float]
    distance_ratio: Optional[float]
    message: str


@dataclass
class EvalContext:
    cost_price: Optional[float] = None
    price_history: Tuple = ()            # tuple[(datetime, price), ...]，按时间升序
    avg_volume_20d: Optional[float] = None
    elapsed_fraction: float = 1.0        # 当日已过交易时间比例 0~1


def validate_condition(cond: dict) -> None:
    """校验条件结构，非法时抛 ValueError"""
    ctype = cond.get('type')
    if ctype not in VALID_TYPES:
        raise ValueError(f'未知条件类型: {ctype}，支持: {sorted(VALID_TYPES)}')
    params = cond.get('params') or {}
    if ctype == 'price_break':
        if 'price' not in params:
            raise ValueError('price_break 需要 params.price')
        if params.get('direction') not in ('above', 'below'):
            raise ValueError('price_break 需要 params.direction: above|below')
    elif ctype in ('pct_change', 'pnl_pct'):
        if 'pct' not in params:
            raise ValueError(f'{ctype} 需要 params.pct')
        if params.get('direction') not in ('above', 'below'):
            raise ValueError(f'{ctype} 需要 params.direction: above|below')
    elif ctype == 'velocity':
        if 'pct' not in params or 'window_min' not in params:
            raise ValueError('velocity 需要 params.pct 和 params.window_min')
    elif ctype == 'volume_surge':
        if 'multiple' not in params:
            raise ValueError('volume_surge 需要 params.multiple')


def evaluate(cond: dict, quote, ctx: EvalContext, now: Optional[datetime] = None) -> EvalResult:
    """评估单个条件。quote 需有 .price，可选 .prev_close / .change_pct / .volume"""
    ctype = cond['type']
    params = cond.get('params') or {}
    handler = _HANDLERS[ctype]
    return handler(params, quote, ctx, now or datetime.now())


def _threshold_result(triggered: bool, value: float, threshold: float,
                      direction: str, message: str) -> EvalResult:
    """统一构造 above/below 结果和距离"""
    if triggered:
        distance = 0.0
    elif threshold == 0:
        distance = None
    elif direction == 'above':
        distance = max(0.0, (threshold - value) / abs(threshold))
    else:
        distance = max(0.0, (value - threshold) / abs(threshold))
    return EvalResult(triggered=triggered, value=value, distance_ratio=distance, message=message)


def _eval_price_break(params, quote, ctx, now) -> EvalResult:
    price = float(quote.price)
    threshold = float(params['price'])
    direction = params['direction']
    triggered = price >= threshold if direction == 'above' else price <= threshold
    word = '上破' if direction == 'above' else '下破'
    return _threshold_result(triggered, price, threshold, direction,
                             f'现价 {price} {"≥" if direction == "above" else "≤"} 阈值 {threshold}（{word}）' if triggered
                             else f'现价 {price} 未{word} {threshold}')


def _eval_pct_change(params, quote, ctx, now) -> EvalResult:
    pct = None
    if getattr(quote, 'prev_close', None):
        pct = (float(quote.price) - float(quote.prev_close)) / float(quote.prev_close) * 100
    elif getattr(quote, 'change_pct', None) is not None:
        pct = float(quote.change_pct)
    if pct is None:
        return EvalResult(False, None, None, '无昨收数据，无法计算涨跌幅')
    threshold = float(params['pct'])
    direction = params['direction']
    triggered = pct >= threshold if direction == 'above' else pct <= threshold
    return _threshold_result(triggered, pct, threshold, direction,
                             f'涨跌幅 {pct:.2f}%（阈值 {direction} {threshold}%）')


def _eval_pnl_pct(params, quote, ctx, now) -> EvalResult:
    if not ctx.cost_price:
        return EvalResult(False, None, None, '无成本价，无法计算盈亏')
    pnl = (float(quote.price) - ctx.cost_price) / ctx.cost_price * 100
    threshold = float(params['pct'])
    direction = params['direction']
    triggered = pnl >= threshold if direction == 'above' else pnl <= threshold
    return _threshold_result(triggered, pnl, threshold, direction,
                             f'盈亏 {pnl:.2f}%（成本 {ctx.cost_price}，阈值 {direction} {threshold}%）')


def _eval_velocity(params, quote, ctx, now) -> EvalResult:
    window_min = float(params['window_min'])
    cutoff = now - timedelta(minutes=window_min)
    points = [(ts, p) for ts, p in ctx.price_history if ts >= cutoff]
    if not points:
        return EvalResult(False, None, None, f'窗口 {window_min}min 内无历史价格（冷启动）')
    base_price = float(points[0][1])
    if base_price <= 0:
        return EvalResult(False, None, None, '历史价格无效')
    change = abs((float(quote.price) - base_price) / base_price * 100)
    threshold = float(params['pct'])
    triggered = change >= threshold
    distance = 0.0 if triggered else max(0.0, (threshold - change) / threshold)
    return EvalResult(triggered, change, distance,
                      f'{window_min}min 内波动 {change:.2f}%（阈值 {threshold}%）')


def _eval_volume_surge(params, quote, ctx, now) -> EvalResult:
    if not ctx.avg_volume_20d or getattr(quote, 'volume', None) is None:
        return EvalResult(False, None, None, '无均量或成交量数据')
    baseline = ctx.avg_volume_20d * max(ctx.elapsed_fraction, 0.01)
    ratio = float(quote.volume) / baseline
    multiple = float(params['multiple'])
    triggered = ratio >= multiple
    distance = 0.0 if triggered else max(0.0, (multiple - ratio) / multiple)
    return EvalResult(triggered, ratio, distance,
                      f'成交量为同期均量 {ratio:.2f}x（阈值 {multiple}x）')


_HANDLERS = {
    'price_break': _eval_price_break,
    'pct_change': _eval_pct_change,
    'pnl_pct': _eval_pnl_pct,
    'velocity': _eval_velocity,
    'volume_surge': _eval_volume_surge,
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/services/test_watch_conditions.py -v --no-cov
```

预期：全部 passed

- [ ] **Step 5: Commit**

```bash
git add application/services/watch_engine/ tests/services/test_watch_conditions.py
git commit -m "feat: WatchEngine 条件判定器（5种条件类型，纯函数）"
```

---

### Task 3: WatchEngine 核心（tick + 冷却 + 自适应频率）

**Files:**
- Create: `quantsys-v2/application/services/watch_engine/engine.py`
- Test: `quantsys-v2/tests/services/test_watch_engine.py`

**设计要点：**
- `tick()` 为一次完整判定（同步，可单测）；`run_forever()` 是常驻循环
- ring buffer 存每股最近 `history_minutes` 分钟 (ts, price)，供 velocity 用
- 冷却：`(rule_id, cond_index)` → 上次触发时间，cond 级独立 `cooldown_sec`（默认 300）
- 自适应：任一条件 `distance_ratio <= buffer_ratio` → `_fast_mode=True`，`run_forever` 用 `fast_interval`
- 交易时段：工作日 9:30–11:30 / 13:00–15:00；`active_window` 进一步收窄；过期规则仓储层已过滤
- 取价失败（五源全挂返回 None）→ 跳过该股，不告警

- [ ] **Step 1: 写测试（先失败）**

创建 `quantsys-v2/tests/services/test_watch_engine.py`：

```python
"""WatchEngine 核心单测（fake 仓储 + fake 行情源）"""
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

from application.services.watch_engine.engine import WatchEngine, elapsed_trading_fraction


def make_rule(id=1, symbol='600519.SH', conditions=None, cost_price=None,
              active_window=None):
    return SimpleNamespace(
        id=id, symbol=symbol,
        conditions=conditions or [{'type': 'price_break',
                                   'params': {'direction': 'above', 'price': 100.0}}],
        cost_price=cost_price, active_window=active_window,
    )


class FakeRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return list(self._rules)


class FakeQuoteService:
    def __init__(self, prices: dict):
        self.prices = prices
        self.calls = []

    def get_realtime_quote(self, symbol):
        self.calls.append(symbol)
        price = self.prices.get(symbol)
        if price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=price, prev_close=98.0,
                               volume=1_000_000, change_pct=None)


class FakeNotifier:
    def __init__(self):
        self.notifications = []

    def notify(self, rule, condition, quote, result):
        self.notifications.append((rule.id, condition['type'], quote.price))
        return True


NOW = datetime(2026, 7, 21, 10, 30)  # 周二，交易时段内


def make_engine(rules, prices, notifier=None, **kw):
    return WatchEngine(
        rule_repo=FakeRepo(rules),
        quote_service=FakeQuoteService(prices),
        notifier=notifier or FakeNotifier(),
        now_fn=lambda: NOW,
        **kw,
    )


class TestTick:
    def test_trigger_fires_notification(self):
        notifier = FakeNotifier()
        engine = make_engine([make_rule()], {'600519.SH': 101.0}, notifier)
        events = engine.tick()
        assert len(events) == 1
        assert notifier.notifications == [(1, 'price_break', 101.0)]

    def test_no_trigger_below_threshold(self):
        notifier = FakeNotifier()
        engine = make_engine([make_rule()], {'600519.SH': 99.0}, notifier)
        events = engine.tick()
        assert events == []
        assert notifier.notifications == []

    def test_cooldown_suppresses_repeat(self):
        notifier = FakeNotifier()
        engine = make_engine([make_rule()], {'600519.SH': 101.0}, notifier)
        engine.tick()
        events2 = engine.tick()  # 立即再次 tick，同一条件冷却中
        assert events2 == []
        assert len(notifier.notifications) == 1

    def test_cooldown_expires(self):
        notifier = FakeNotifier()
        clock = {'now': NOW}
        engine = WatchEngine(
            rule_repo=FakeRepo([make_rule()]),
            quote_service=FakeQuoteService({'600519.SH': 101.0}),
            notifier=notifier,
            now_fn=lambda: clock['now'],
        )
        engine.tick()
        clock['now'] = NOW + timedelta(seconds=301)  # 默认冷却 300s 已过
        events = engine.tick()
        assert len(events) == 1

    def test_custom_cooldown(self):
        rule = make_rule(conditions=[{'type': 'price_break',
                                      'params': {'direction': 'above', 'price': 100.0},
                                      'cooldown_sec': 3600}])
        clock = {'now': NOW}
        notifier = FakeNotifier()
        engine = WatchEngine(FakeRepo([rule]), FakeQuoteService({'600519.SH': 101.0}),
                             notifier, now_fn=lambda: clock['now'])
        engine.tick()
        clock['now'] = NOW + timedelta(seconds=301)
        assert engine.tick() == []  # 自定义冷却 3600s 未过

    def test_quote_failure_skips_silently(self):
        notifier = FakeNotifier()
        engine = make_engine([make_rule()], {}, notifier)  # 无价格 → 五源全挂
        assert engine.tick() == []
        assert notifier.notifications == []

    def test_active_window_excludes(self):
        rule = make_rule(active_window=['14:30-15:00'])  # 当前 10:30 不在窗口
        engine = make_engine([rule], {'600519.SH': 101.0})
        assert engine.tick() == []

    def test_active_window_includes(self):
        rule = make_rule(active_window=['09:30-10:30', '14:30-15:00'])
        engine = make_engine([rule], {'600519.SH': 101.0})
        assert len(engine.tick()) == 1


class TestAdaptiveFrequency:
    def test_fast_mode_when_near_threshold(self):
        # 阈值 100，现价 99.5 → distance_ratio = 0.005 <= 0.2 → 高频档
        engine = make_engine([make_rule()], {'600519.SH': 99.5})
        engine.tick()
        assert engine.fast_mode is True

    def test_normal_mode_when_far(self):
        engine = make_engine([make_rule()], {'600519.SH': 50.0})
        engine.tick()
        assert engine.fast_mode is False

    def test_fast_mode_on_trigger(self):
        engine = make_engine([make_rule()], {'600519.SH': 101.0})
        engine.tick()
        assert engine.fast_mode is True  # distance_ratio 0 → 保持高频


class TestPriceHistory:
    def test_velocity_uses_ring_buffer(self):
        rule = make_rule(conditions=[{'type': 'velocity',
                                      'params': {'pct': 2.0, 'window_min': 5}}])
        clock = {'now': NOW}
        notifier = FakeNotifier()
        quotes = FakeQuoteService({'600519.SH': 100.0})
        engine = WatchEngine(FakeRepo([rule]), quotes, notifier, now_fn=lambda: clock['now'])
        engine.tick()  # 积累第一点 100.0
        clock['now'] = NOW + timedelta(minutes=3)
        quotes.prices['600519.SH'] = 103.0  # 3分钟涨3%
        events = engine.tick()
        assert len(events) == 1
        assert notifier.notifications[0][1] == 'velocity'


class TestTradingTime:
    @pytest.mark.parametrize('t,expected', [
        (time(9, 29), False), (time(9, 30), True), (time(11, 30), True),
        (time(12, 0), False), (time(13, 0), True), (time(15, 0), True),
        (time(15, 1), False),
    ])
    def test_is_trading_time(self, t, expected):
        assert WatchEngine.is_trading_time(t) is expected


class TestElapsedFraction:
    def test_open(self):
        assert elapsed_trading_fraction(datetime(2026, 7, 21, 9, 30)) == pytest.approx(0.0)

    def test_lunch_boundary(self):
        # 11:30 已交易 120/240 分钟
        assert elapsed_trading_fraction(datetime(2026, 7, 21, 11, 30)) == pytest.approx(0.5)

    def test_afternoon(self):
        # 14:00 = 上午120 + 下午60 = 180/240
        assert elapsed_trading_fraction(datetime(2026, 7, 21, 14, 0)) == pytest.approx(0.75)

    def test_close(self):
        assert elapsed_trading_fraction(datetime(2026, 7, 21, 15, 0)) == pytest.approx(1.0)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/services/test_watch_engine.py -v --no-cov
```

预期：ImportError: cannot import name 'WatchEngine'

- [ ] **Step 3: 实现 engine.py**

创建 `quantsys-v2/application/services/watch_engine/engine.py`：

```python
"""WatchEngine 盯盘引擎核心

tick() 为一次完整判定（同步、可单测）；run_forever() 为常驻循环。
仅交易日（周一至周五）9:30-11:30 / 13:00-15:00 运行。
"""
import time as time_module
from datetime import datetime, time, timedelta
from typing import Callable, Dict, List, Optional, Tuple

import structlog

from application.services.watch_engine.conditions import (
    DEFAULT_COOLDOWN_SEC, EvalContext, evaluate,
)

logger = structlog.get_logger(__name__)

TOTAL_TRADING_MINUTES = 240  # 上午120 + 下午120


def elapsed_trading_fraction(now: datetime) -> float:
    """当日已过交易时间比例（0~1），供 volume_surge 折算同期均量"""
    t = now.time()
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    if t <= time(9, 30):
        return 0.0
    if t <= morning_end:
        minutes = (now - now.replace(hour=9, minute=30, second=0)).seconds / 60
    elif t < afternoon_start:
        minutes = 120
    elif t <= time(15, 0):
        minutes = 120 + (now - now.replace(hour=13, minute=0, second=0)).seconds / 60
    else:
        minutes = TOTAL_TRADING_MINUTES
    return min(1.0, max(0.0, minutes / TOTAL_TRADING_MINUTES))


class WatchEngine:
    def __init__(self, rule_repo, quote_service, notifier,
                 avg_volume_provider: Optional[Callable[[str], Optional[float]]] = None,
                 base_interval: int = 60, fast_interval: int = 10,
                 buffer_ratio: float = 0.2, history_minutes: int = 30,
                 now_fn: Callable[[], datetime] = datetime.now):
        self.rule_repo = rule_repo
        self.quote_service = quote_service
        self.notifier = notifier
        self.avg_volume_provider = avg_volume_provider
        self.base_interval = base_interval
        self.fast_interval = fast_interval
        self.buffer_ratio = buffer_ratio
        self.history_minutes = history_minutes
        self.now_fn = now_fn

        self._history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._last_triggered: Dict[Tuple[int, int], datetime] = {}
        self._avg_volume_cache: Dict[str, float] = {}
        self.fast_mode = False
        self._stopped = False

    @staticmethod
    def is_trading_time(t: time) -> bool:
        return (time(9, 30) <= t <= time(11, 30)) or (time(13, 0) <= t <= time(15, 0))

    def stop(self):
        self._stopped = True

    # ── 主循环 ──────────────────────────────────────────────

    def run_forever(self):
        logger.info('WatchEngine 启动', base_interval=self.base_interval,
                    fast_interval=self.fast_interval)
        while not self._stopped:
            now = self.now_fn()
            if now.weekday() < 5 and self.is_trading_time(now.time()):
                try:
                    self.tick()
                except Exception as e:
                    logger.error('WatchEngine tick 异常', error=str(e))
                interval = self.fast_interval if self.fast_mode else self.base_interval
            else:
                interval = 60  # 非交易时段低频心跳
            time_module.sleep(interval)
        logger.info('WatchEngine 已停止')

    # ── 单次判定 ────────────────────────────────────────────

    def tick(self) -> List[dict]:
        now = self.now_fn()
        rules = self.rule_repo.list_enabled()
        events = []
        fast = False

        for rule in rules:
            if not self._in_active_window(rule, now):
                continue
            quote = self.quote_service.get_realtime_quote(rule.symbol)
            if quote is None:
                logger.warning('取价失败跳过', symbol=rule.symbol)
                continue
            self._push_history(rule.symbol, now, float(quote.price))
            ctx = self._build_ctx(rule, now)

            for idx, cond in enumerate(rule.conditions):
                try:
                    result = evaluate(cond, quote, ctx, now=now)
                except Exception as e:
                    logger.error('条件评估异常', rule_id=rule.id, cond=cond, error=str(e))
                    continue
                if result.distance_ratio is not None and result.distance_ratio <= self.buffer_ratio:
                    fast = True
                if not result.triggered:
                    continue
                if self._in_cooldown(rule.id, idx, cond, now):
                    continue
                self.notifier.notify(rule, cond, quote, result)
                self._last_triggered[(rule.id, idx)] = now
                events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                               'condition': cond, 'price': float(quote.price),
                               'message': result.message})

        self.fast_mode = fast
        return events

    # ── 内部 ────────────────────────────────────────────────

    def _in_active_window(self, rule, now: datetime) -> bool:
        windows = getattr(rule, 'active_window', None)
        if not windows:
            return True
        current = now.strftime('%H:%M')
        return any(start <= current <= end for w in windows
                   for start, end in [w.split('-')])

    def _build_ctx(self, rule, now: datetime) -> EvalContext:
        cost = getattr(rule, 'cost_price', None)
        return EvalContext(
            cost_price=float(cost) if cost is not None else None,
            price_history=tuple(self._history.get(rule.symbol, ())),
            avg_volume_20d=self._get_avg_volume(rule.symbol),
            elapsed_fraction=elapsed_trading_fraction(now),
        )

    def _push_history(self, symbol: str, ts: datetime, price: float):
        buf = self._history.setdefault(symbol, [])
        buf.append((ts, price))
        cutoff = ts - timedelta(minutes=self.history_minutes)
        self._history[symbol] = [(t, p) for t, p in buf if t >= cutoff]

    def _get_avg_volume(self, symbol: str) -> Optional[float]:
        if self.avg_volume_provider is None:
            return None
        if symbol not in self._avg_volume_cache:
            try:
                value = self.avg_volume_provider(symbol)
                if value:
                    self._avg_volume_cache[symbol] = value
            except Exception as e:
                logger.warning('均量获取失败', symbol=symbol, error=str(e))
                return None
        return self._avg_volume_cache.get(symbol)

    def _in_cooldown(self, rule_id: int, cond_idx: int, cond: dict, now: datetime) -> bool:
        last = self._last_triggered.get((rule_id, cond_idx))
        if last is None:
            return False
        cooldown = cond.get('cooldown_sec', DEFAULT_COOLDOWN_SEC)
        return (now - last).total_seconds() < cooldown
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/services/test_watch_engine.py -v --no-cov
```

预期：全部 passed

- [ ] **Step 5: Commit**

```bash
git add application/services/watch_engine/engine.py tests/services/test_watch_engine.py
git commit -m "feat: WatchEngine 核心（tick/冷却/ring buffer/自适应频率）"
```

---

### Task 4: Notifier（唤醒 Agent + WS 广播 + 审计落库）

**Files:**
- Create: `quantsys-v2/application/services/watch_engine/notifier.py`
- Test: `quantsys-v2/tests/services/test_watch_notifier.py`

**设计要点：**
- payload 含 symbol、当前价、涨跌幅、命中条件、盈亏（如有成本价）、`context`（Agent 当初填的监视理由）
- `agent_service.notify_agent('watch_triggered', payload)` 失败重试 3 次；最终失败仍落库（`notified=false`）待补发
- WS broadcast 走 `POST http://127.0.0.1:5003/broadcast/market_data`，fire-and-forget（WS 服务没起不阻塞）

- [ ] **Step 1: 写测试（先失败）**

创建 `quantsys-v2/tests/services/test_watch_notifier.py`：

```python
"""WatchNotifier 单测"""
from types import SimpleNamespace
from unittest.mock import patch

from application.services.watch_engine.conditions import EvalResult
from application.services.watch_engine.notifier import WatchNotifier


def make_rule():
    return SimpleNamespace(id=7, symbol='600519.SH', context='突破平台考虑加仓',
                           cost_price=1700.0)


def make_quote(price=1801.5):
    return SimpleNamespace(symbol='600519.SH', name='贵州茅台', price=price,
                           prev_close=1780.0, change_pct=None, volume=1_000_000)


COND = {'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}}
RESULT = EvalResult(triggered=True, value=1801.5, distance_ratio=0.0,
                    message='现价 1801.5 ≥ 阈值 1800.0（上破）')


class FakeAgentService:
    def __init__(self, results):
        self.results = list(results)  # 每次调用的返回值
        self.calls = []

    def notify_agent(self, event, data):
        self.calls.append((event, data))
        return self.results.pop(0) if self.results else False


class FakeTriggerRepo:
    def __init__(self):
        self.records = []

    def record(self, **kw):
        self.records.append(kw)
        return SimpleNamespace(id=1)


class TestNotify:
    def test_payload_contains_context_and_pnl(self):
        agent = FakeAgentService([True])
        repo = FakeTriggerRepo()
        notifier = WatchNotifier(agent, repo, ws_url=None)
        ok = notifier.notify(make_rule(), COND, make_quote(), RESULT)
        assert ok is True
        event, data = agent.calls[0]
        assert event == 'watch_triggered'
        assert data['symbol'] == '600519.SH'
        assert data['price'] == 1801.5
        assert data['context'] == '突破平台考虑加仓'
        assert data['pnl_pct'] == round((1801.5 - 1700.0) / 1700.0 * 100, 2)
        assert data['condition']['type'] == 'price_break'
        assert data['message'] == RESULT.message
        # 审计落库
        assert repo.records[0]['notified'] is True
        assert repo.records[0]['trigger_price'] == 1801.5

    def test_retry_on_failure_then_success(self):
        agent = FakeAgentService([False, False, True])
        repo = FakeTriggerRepo()
        notifier = WatchNotifier(agent, repo, ws_url=None, max_retries=3, retry_interval=0)
        assert notifier.notify(make_rule(), COND, make_quote(), RESULT) is True
        assert len(agent.calls) == 3

    def test_all_retries_fail_still_records(self):
        agent = FakeAgentService([False, False, False])
        repo = FakeTriggerRepo()
        notifier = WatchNotifier(agent, repo, ws_url=None, max_retries=3, retry_interval=0)
        assert notifier.notify(make_rule(), COND, make_quote(), RESULT) is False
        assert repo.records[0]['notified'] is False  # 落库待补发

    def test_ws_broadcast_fire_and_forget(self):
        agent = FakeAgentService([True])
        notifier = WatchNotifier(agent, FakeTriggerRepo(),
                                 ws_url='http://127.0.0.1:5003/broadcast/market_data')
        with patch('application.services.watch_engine.notifier.requests.post') as mock_post:
            notifier.notify(make_rule(), COND, make_quote(), RESULT)
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == 'http://127.0.0.1:5003/broadcast/market_data'
            assert kwargs['json']['type'] == 'watch_triggered'

    def test_ws_failure_does_not_break_notify(self):
        agent = FakeAgentService([True])
        notifier = WatchNotifier(agent, FakeTriggerRepo(),
                                 ws_url='http://127.0.0.1:5003/broadcast/market_data')
        with patch('application.services.watch_engine.notifier.requests.post',
                   side_effect=ConnectionError('ws down')):
            assert notifier.notify(make_rule(), COND, make_quote(), RESULT) is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/services/test_watch_notifier.py -v --no-cov
```

预期：ImportError: cannot import name 'WatchNotifier'

- [ ] **Step 3: 实现 notifier.py**

创建 `quantsys-v2/application/services/watch_engine/notifier.py`：

```python
"""WatchEngine 触发通知器：唤醒 Agent + WS 广播 + 审计落库"""
import time
from typing import Optional

import requests
import structlog

logger = structlog.get_logger(__name__)


class WatchNotifier:
    def __init__(self, agent_service, trigger_repo=None,
                 ws_url: Optional[str] = 'http://127.0.0.1:5003/broadcast/market_data',
                 max_retries: int = 3, retry_interval: float = 1.0):
        self.agent_service = agent_service
        self.trigger_repo = trigger_repo
        self.ws_url = ws_url
        self.max_retries = max_retries
        self.retry_interval = retry_interval

    def notify(self, rule, condition: dict, quote, result) -> bool:
        """触发通知。返回是否成功唤醒 Agent（失败也落库待补发）"""
        payload = self._build_payload(rule, condition, quote, result)
        notified = self._notify_agent_with_retry(payload)
        self._broadcast_ws(payload)
        self._record(rule, condition, quote, result, notified)
        return notified

    def _build_payload(self, rule, condition, quote, result) -> dict:
        price = float(quote.price)
        change_pct = None
        if getattr(quote, 'prev_close', None):
            change_pct = round((price - float(quote.prev_close)) / float(quote.prev_close) * 100, 2)
        elif getattr(quote, 'change_pct', None) is not None:
            change_pct = float(quote.change_pct)
        pnl_pct = None
        cost = getattr(rule, 'cost_price', None)
        if cost:
            pnl_pct = round((price - float(cost)) / float(cost) * 100, 2)
        return {
            'rule_id': rule.id,
            'symbol': rule.symbol,
            'name': getattr(quote, 'name', None),
            'price': price,
            'change_pct': change_pct,
            'pnl_pct': pnl_pct,
            'condition': condition,
            'message': result.message,
            'context': getattr(rule, 'context', None),
        }

    def _notify_agent_with_retry(self, payload) -> bool:
        for attempt in range(1, self.max_retries + 1):
            if self.agent_service.notify_agent('watch_triggered', payload):
                return True
            logger.warning('唤醒 Agent 失败，重试', attempt=attempt,
                           symbol=payload['symbol'])
            if attempt < self.max_retries:
                time.sleep(self.retry_interval)
        logger.error('唤醒 Agent 最终失败（已落库待补发）', symbol=payload['symbol'])
        return False

    def _broadcast_ws(self, payload):
        if not self.ws_url:
            return
        try:
            requests.post(self.ws_url, json={'type': 'watch_triggered', 'data': payload},
                          timeout=3)
        except Exception as e:
            logger.debug('WS 广播失败（忽略）', error=str(e))

    def _record(self, rule, condition, quote, result, notified):
        if self.trigger_repo is None:
            return
        try:
            self.trigger_repo.record(
                rule_id=rule.id, symbol=rule.symbol, condition=condition,
                trigger_price=float(quote.price),
                detail={'value': result.value, 'message': result.message},
                notified=notified,
            )
        except Exception as e:
            logger.error('触发记录落库失败', error=str(e))
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/services/test_watch_notifier.py -v --no-cov
```

预期：5 passed

- [ ] **Step 5: Commit**

```bash
git add application/services/watch_engine/notifier.py tests/services/test_watch_notifier.py
git commit -m "feat: WatchNotifier 唤醒 Agent + WS 广播 + 触发审计"
```

---

### Task 5: 引擎装配 + 注册到 scheduler_daemon

**Files:**
- Create: `quantsys-v2/application/services/watch_engine/factory.py`
- Modify: `quantsys-v2/scheduler_daemon.py`（在 `_register_orchestrator` 后追加 `_register_watch_engine`，并在 `start()` 中调用）

**设计要点：**
- `run_forever` 是阻塞循环且用 `time.sleep`（同步），放 daemon 线程跑，随 scheduler_daemon 进程退出
- `avg_volume_provider` 用 `DataProviderManager.get_klines` 取近 20 日日均成交量；失败返回 None（volume_surge 自动降级）
- 引擎注册失败不影响 daemon 其他任务（try/except，与现有注册风格一致）

- [ ] **Step 1: 写 factory.py**

创建 `quantsys-v2/application/services/watch_engine/factory.py`：

```python
"""WatchEngine 装配：构建引擎 + 后台线程启动"""
import threading
from datetime import datetime, timedelta
from typing import Optional

import structlog

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository,
)
from application.services.agent_notification_service import AgentNotificationService
from application.services.realtime_quote_service_v2 import RealtimeQuoteServiceV2
from application.services.watch_engine.engine import WatchEngine
from application.services.watch_engine.notifier import WatchNotifier

logger = structlog.get_logger(__name__)


def make_avg_volume_provider():
    """近 20 日日均成交量 provider。失败返回 None（volume_surge 降级不判定）"""
    def provider(symbol: str) -> Optional[float]:
        from adapters.outbound.datasources.manager import get_data_provider_manager
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
        result = get_data_provider_manager().get_klines(symbol, 'daily', start, end)
        if not result.get('success'):
            return None
        volumes = [k['volume'] for k in result['data'][-20:] if k.get('volume')]
        return sum(volumes) / len(volumes) if volumes else None
    return provider


def create_watch_engine() -> WatchEngine:
    notifier = WatchNotifier(
        agent_service=AgentNotificationService(),
        trigger_repo=WatchTriggerRepository(),
    )
    return WatchEngine(
        rule_repo=WatchRuleRepository(),
        quote_service=RealtimeQuoteServiceV2(),
        notifier=notifier,
        avg_volume_provider=make_avg_volume_provider(),
    )


def start_watch_engine_in_thread() -> threading.Thread:
    """daemon 线程启动引擎，随主进程退出"""
    engine = create_watch_engine()
    thread = threading.Thread(target=engine.run_forever, name='watch-engine', daemon=True)
    thread.start()
    logger.info('✓ WatchEngine 已在后台线程启动')
    return thread
```

- [ ] **Step 2: 注册到 scheduler_daemon.py**

在 `scheduler_daemon.py` 的 `_register_orchestrator` 方法**之后**新增方法（对齐现有注册风格）：

```python
    def _register_watch_engine(self):
        """注册 WatchEngine 实时盯盘引擎（后台线程）"""
        try:
            from application.services.watch_engine.factory import start_watch_engine_in_thread
            start_watch_engine_in_thread()
        except Exception as e:
            logger.error(f"Failed to register WatchEngine: {e}")
```

并在 `start()` 方法中调用 `self._register_orchestrator()` 的下一行加：

```python
        self._register_watch_engine()
```

- [ ] **Step 3: 冒烟验证（不起真实引擎，验证装配可导入可构建）**

```bash
cd quantsys-v2 && source activate-py313.sh
python -c "
from application.services.watch_engine.factory import create_watch_engine
engine = create_watch_engine()
print('engine ok:', type(engine).__name__, 'fast_mode =', engine.fast_mode)
"
```

预期输出：`engine ok: WatchEngine fast_mode = False`

- [ ] **Step 4: Commit**

```bash
git add application/services/watch_engine/factory.py scheduler_daemon.py
git commit -m "feat: WatchEngine 装配并注册到 scheduler_daemon（后台线程）"
```

---

### Task 6: Flask API 路由（生产路径）

**Files:**
- Create: `quantsys-v2/adapters/inbound/api/routes/watch.py`
- Modify: `quantsys-v2/adapters/inbound/api/server.py`（import + register_blueprint，对齐现有蓝图注册段）
- Test: `quantsys-v2/tests/api/test_watch_routes.py`

**端点契约（响应 snake_case，`{success, ...}`）：**

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/watch/rules?symbol=&enabled=` | 规则列表 |
| POST | `/api/watch/rules` | 创建 `{symbol, conditions, context?, cost_price?, active_window?, expires_at?, created_by?}` |
| PUT | `/api/watch/rules/{id}` | 部分更新（enabled/conditions/context/cost_price/active_window/expires_at/symbol） |
| DELETE | `/api/watch/rules/{id}` | 删除 |
| GET | `/api/watch/triggers?symbol=&limit=` | 触发记录 |

- [ ] **Step 1: 写测试（先失败）**

创建 `quantsys-v2/tests/api/test_watch_routes.py`：

```python
"""watch Flask 路由测试（蓝图级 test_client，不经 server.py）"""
import pytest
from flask import Flask

from adapters.inbound.api.routes.watch import watch_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(watch_bp)
    return app.test_client()


VALID_CONDITIONS = [
    {'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}},
    {'type': 'pnl_pct', 'params': {'direction': 'below', 'pct': -8.0}},
]


@pytest.fixture
def created_rule(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '600519.SH',
        'conditions': VALID_CONDITIONS,
        'context': '测试盯盘',
        'cost_price': 1700.0,
    })
    assert resp.status_code == 200, resp.get_json()
    rule_id = resp.get_json()['rule']['id']
    yield rule_id
    client.delete(f'/api/watch/rules/{rule_id}')


class TestCreate:
    def test_create_success(self, created_rule):
        assert isinstance(created_rule, int)

    def test_missing_symbol_400(self, client):
        resp = client.post('/api/watch/rules', json={'conditions': VALID_CONDITIONS})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_invalid_condition_400(self, client):
        resp = client.post('/api/watch/rules', json={
            'symbol': '600519.SH',
            'conditions': [{'type': 'magic', 'params': {}}],
        })
        assert resp.status_code == 400

    def test_empty_conditions_400(self, client):
        resp = client.post('/api/watch/rules', json={'symbol': '600519.SH', 'conditions': []})
        assert resp.status_code == 400


class TestList:
    def test_list_contains_created(self, client, created_rule):
        resp = client.get('/api/watch/rules')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.get_json()['rules']]
        assert created_rule in ids

    def test_filter_by_symbol(self, client, created_rule):
        resp = client.get('/api/watch/rules?symbol=600519.SH')
        rules = resp.get_json()['rules']
        assert all(r['symbol'] == '600519.SH' for r in rules)


class TestUpdate:
    def test_disable_rule(self, client, created_rule):
        resp = client.put(f'/api/watch/rules/{created_rule}', json={'enabled': False})
        assert resp.status_code == 200
        assert resp.get_json()['rule']['enabled'] is False

    def test_update_nonexistent_404(self, client):
        resp = client.put('/api/watch/rules/99999999', json={'enabled': False})
        assert resp.status_code == 404

    def test_update_invalid_conditions_400(self, client, created_rule):
        resp = client.put(f'/api/watch/rules/{created_rule}',
                          json={'conditions': [{'type': 'magic'}]})
        assert resp.status_code == 400


class TestDelete:
    def test_delete(self, client, created_rule):
        resp = client.delete(f'/api/watch/rules/{created_rule}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_delete_nonexistent_404(self, client):
        assert client.delete('/api/watch/rules/99999999').status_code == 404


class TestTriggers:
    def test_list_triggers(self, client):
        resp = client.get('/api/watch/triggers?limit=5')
        assert resp.status_code == 200
        assert 'triggers' in resp.get_json()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/api/test_watch_routes.py -v --no-cov
```

预期：ModuleNotFoundError

- [ ] **Step 3: 实现 watch.py**

创建 `quantsys-v2/adapters/inbound/api/routes/watch.py`：

```python
"""WatchEngine 盯盘规则 API（Flask，生产路径）"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository, rule_to_dict, trigger_to_dict,
)
from application.services.watch_engine.conditions import validate_condition

watch_bp = Blueprint('watch', __name__)

_rule_repo = WatchRuleRepository()
_trigger_repo = WatchTriggerRepository()


def _parse_expires_at(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


@watch_bp.route('/api/watch/rules', methods=['GET'])
def list_rules():
    symbol = request.args.get('symbol')
    enabled_arg = request.args.get('enabled')
    enabled = None if enabled_arg is None else enabled_arg.lower() == 'true'
    rules = _rule_repo.list_rules(symbol=symbol, enabled=enabled)
    return jsonify({'success': True, 'rules': [rule_to_dict(r) for r in rules]})


@watch_bp.route('/api/watch/rules', methods=['POST'])
def create_rule():
    data = request.get_json() or {}
    symbol = (data.get('symbol') or '').strip()
    conditions = data.get('conditions')
    if not symbol:
        return jsonify({'success': False, 'error': '缺少必填参数: symbol'}), 400
    if not conditions:
        return jsonify({'success': False, 'error': '缺少必填参数: conditions（非空数组）'}), 400
    try:
        for cond in conditions:
            validate_condition(cond)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    try:
        rule = _rule_repo.create_rule(
            symbol=symbol,
            conditions=conditions,
            context=data.get('context'),
            cost_price=data.get('cost_price'),
            active_window=data.get('active_window'),
            expires_at=_parse_expires_at(data.get('expires_at')),
            created_by=data.get('created_by', 'agent'),
        )
    except Exception as e:
        return jsonify({'success': False, 'error': f'创建失败: {e}'}), 500
    return jsonify({'success': True, 'rule': rule_to_dict(rule)})


@watch_bp.route('/api/watch/rules/<int:rule_id>', methods=['PUT', 'PATCH'])
def update_rule(rule_id):
    data = request.get_json() or {}
    if 'conditions' in data:
        try:
            for cond in data['conditions']:
                validate_condition(cond)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    if 'expires_at' in data:
        data['expires_at'] = _parse_expires_at(data['expires_at'])
    rule = _rule_repo.update_fields(rule_id, **data)
    if rule is None:
        return jsonify({'success': False, 'error': '规则不存在'}), 404
    return jsonify({'success': True, 'rule': rule_to_dict(rule)})


@watch_bp.route('/api/watch/rules/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    if _rule_repo.get_by_id(rule_id) is None:
        return jsonify({'success': False, 'error': '规则不存在'}), 404
    _rule_repo.delete_by_id(rule_id)
    return jsonify({'success': True})


@watch_bp.route('/api/watch/triggers', methods=['GET'])
def list_triggers():
    symbol = request.args.get('symbol')
    limit = min(int(request.args.get('limit', 50)), 200)
    triggers = _trigger_repo.list_by_symbol(symbol=symbol, limit=limit)
    return jsonify({'success': True, 'triggers': [trigger_to_dict(t) for t in triggers]})
```

- [ ] **Step 4: 注册蓝图**

修改 `quantsys-v2/adapters/inbound/api/server.py`：

在 watchlist 蓝图 import 附近加：

```python
from adapters.inbound.api.routes.watch import watch_bp
```

在 `app.register_blueprint(...)` 序列中加（按现有字母序大致位置）：

```python
    app.register_blueprint(watch_bp)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/api/test_watch_routes.py -v --no-cov
```

预期：全部 passed

- [ ] **Step 6: Commit**

```bash
git add adapters/inbound/api/routes/watch.py adapters/inbound/api/server.py tests/api/test_watch_routes.py
git commit -m "feat: /api/watch/rules + /api/watch/triggers Flask 路由"
```

---

### Task 7: FastAPI parity 路由

**Files:**
- Create: `quantsys-v2/adapters/inbound/fastapi_app/routes/watch_async.py`
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/main.py`（import + include_router，对齐现有注册段，加 try/except 包裹风格与其他 router 一致）

**契约必须与 Task 6 Flask 版完全一致**（路径、字段名、状态码、`{success, ...}` 结构）。

- [ ] **Step 1: 写测试（先失败）**

创建 `quantsys-v2/tests/api/test_watch_routes_async.py`：

```python
"""watch FastAPI 路由 parity 测试"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.watch_async import router

VALID_CONDITIONS = [
    {'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}},
]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def created_rule(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '000001.SZ', 'conditions': VALID_CONDITIONS, 'context': 'parity 测试',
    })
    assert resp.status_code == 200, resp.json()
    rule_id = resp.json()['rule']['id']
    yield rule_id
    client.delete(f'/api/watch/rules/{rule_id}')


def test_create_and_list(client, created_rule):
    resp = client.get('/api/watch/rules?symbol=000001.SZ')
    assert resp.status_code == 200
    ids = [r['id'] for r in resp.json()['rules']]
    assert created_rule in ids


def test_create_invalid_condition_400(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '600519.SH', 'conditions': [{'type': 'magic', 'params': {}}],
    })
    assert resp.status_code == 400
    assert resp.json()['success'] is False


def test_update_disable(client, created_rule):
    resp = client.put(f'/api/watch/rules/{created_rule}', json={'enabled': False})
    assert resp.status_code == 200
    assert resp.json()['rule']['enabled'] is False


def test_update_nonexistent_404(client):
    assert client.put('/api/watch/rules/99999999', json={'enabled': False}).status_code == 404


def test_delete(client, created_rule):
    assert client.delete(f'/api/watch/rules/{created_rule}').json()['success'] is True


def test_delete_nonexistent_404(client):
    assert client.delete('/api/watch/rules/99999999').status_code == 404


def test_list_triggers(client):
    resp = client.get('/api/watch/triggers?limit=5')
    assert resp.status_code == 200
    assert 'triggers' in resp.json()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/api/test_watch_routes_async.py -v --no-cov
```

预期：ModuleNotFoundError

- [ ] **Step 3: 实现 watch_async.py**

创建 `quantsys-v2/adapters/inbound/fastapi_app/routes/watch_async.py`：

```python
"""WatchEngine 盯盘规则 API - FastAPI 版（与 Flask watch.py 响应契约一致）"""
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository, rule_to_dict, trigger_to_dict,
)
from application.services.watch_engine.conditions import validate_condition

router = APIRouter(tags=['Watch - 实时盯盘'])

_rule_repo = WatchRuleRepository()
_trigger_repo = WatchTriggerRepository()


def _err(message: str, status: int) -> JSONResponse:
    return JSONResponse({'success': False, 'error': message}, status_code=status)


def _parse_expires_at(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


@router.get('/api/watch/rules')
def list_rules(symbol: Optional[str] = Query(None), enabled: Optional[bool] = Query(None)):
    rules = _rule_repo.list_rules(symbol=symbol, enabled=enabled)
    return {'success': True, 'rules': [rule_to_dict(r) for r in rules]}


@router.post('/api/watch/rules')
def create_rule(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = (payload.get('symbol') or '').strip()
    conditions = payload.get('conditions')
    if not symbol:
        return _err('缺少必填参数: symbol', 400)
    if not conditions:
        return _err('缺少必填参数: conditions（非空数组）', 400)
    try:
        for cond in conditions:
            validate_condition(cond)
    except ValueError as e:
        return _err(str(e), 400)
    try:
        rule = _rule_repo.create_rule(
            symbol=symbol,
            conditions=conditions,
            context=payload.get('context'),
            cost_price=payload.get('cost_price'),
            active_window=payload.get('active_window'),
            expires_at=_parse_expires_at(payload.get('expires_at')),
            created_by=payload.get('created_by', 'agent'),
        )
    except Exception as e:
        return _err(f'创建失败: {e}', 500)
    return {'success': True, 'rule': rule_to_dict(rule)}


@router.put('/api/watch/rules/{rule_id}')
def update_rule(rule_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    if 'conditions' in payload:
        try:
            for cond in payload['conditions']:
                validate_condition(cond)
        except ValueError as e:
            return _err(str(e), 400)
    if 'expires_at' in payload:
        payload['expires_at'] = _parse_expires_at(payload['expires_at'])
    rule = _rule_repo.update_fields(rule_id, **payload)
    if rule is None:
        return _err('规则不存在', 404)
    return {'success': True, 'rule': rule_to_dict(rule)}


@router.delete('/api/watch/rules/{rule_id}')
def delete_rule(rule_id: int):
    if _rule_repo.get_by_id(rule_id) is None:
        return _err('规则不存在', 404)
    _rule_repo.delete_by_id(rule_id)
    return {'success': True}


@router.get('/api/watch/triggers')
def list_triggers(symbol: Optional[str] = Query(None), limit: int = Query(50)):
    triggers = _trigger_repo.list_by_symbol(symbol=symbol, limit=min(limit, 200))
    return {'success': True, 'triggers': [trigger_to_dict(t) for t in triggers]}
```

- [ ] **Step 4: 注册 router**

修改 `quantsys-v2/adapters/inbound/fastapi_app/main.py`：

在 watchlist router import 附近加：

```python
from adapters.inbound.fastapi_app.routes.watch_async import router as watch_router
```

在 `app.include_router(watchlist_router)` 之后加（对齐现有 try/except 注册风格）：

```python
        app.include_router(watch_router)
```

（若 main.py 中各 router 注册包在独立 try/except 块内，按同样方式包裹。）

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/api/test_watch_routes_async.py -v --no-cov
```

预期：7 passed

- [ ] **Step 6: Commit**

```bash
git add adapters/inbound/fastapi_app/routes/watch_async.py adapters/inbound/fastapi_app/main.py tests/api/test_watch_routes_async.py
git commit -m "feat: /api/watch FastAPI parity 路由"
```

---

### Task 8: agent-ts `watch_manage` 工具 + 修复 watch.price-alert bug

**Files:**
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`（V2_ROUTES 增加 5 条）
- Create: `agent-ts/src/infrastructure/tools/monitor/watch-manage-tool.ts`
- Modify: `agent-ts/src/infrastructure/tools/index.ts`（import + 注册，在 watchAlertTool 附近）
- Modify: `agent-ts/src/infrastructure/tools/monitor/watch-alert-tool.ts:70`（`"watch.price-alert"` → `"watch.price_alert"`，修既有 bug）
- Test: `agent-ts/src/infrastructure/tools/monitor/watch-manage-tool.test.ts`

- [ ] **Step 1: V2_ROUTES 注册**

在 `quant-v2-client.ts` 的 watchlist 段附近加：

```typescript
  // ── watch (实时盯盘) ──
  "watch.rules.list":    { path: "/api/watch/rules",              method: "GET" },
  "watch.rules.create":  { path: "/api/watch/rules",              method: "POST" },
  "watch.rules.update":  { path: "/api/watch/rules/{id}",         method: "PUT" },
  "watch.rules.remove":  { path: "/api/watch/rules/{id}",         method: "DELETE" },
  "watch.triggers.list": { path: "/api/watch/triggers",           method: "GET" },
```

- [ ] **Step 2: 修复 watch-alert-tool 命令名 bug**

`watch-alert-tool.ts:70`：`runQuantV2("watch.price-alert", params)` → `runQuantV2("watch.price_alert", params)`（V2_ROUTES 里的键是 `watch.price_alert`，当前写法必然报"没有 v2 端点映射"）。

- [ ] **Step 3: 写工具测试（先失败）**

创建 `agent-ts/src/infrastructure/tools/monitor/watch-manage-tool.test.ts`：

```typescript
import { watchManageTool } from "./watch-manage-tool.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

jest.mock("../../adapters/quant/quant-v2-client.js", () => ({
  runQuantV2: jest.fn(),
}));

const mockRun = runQuantV2 as jest.MockedFunction<typeof runQuantV2>;

beforeEach(() => mockRun.mockReset());

const exec = (params: any) => watchManageTool.execute("test-id", params);

describe("watch_manage", () => {
  it("add 映射到 watch.rules.create", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.rules.create", data: { rule: { id: 1 } } } as any);
    await exec({
      action: "add", symbol: "600519.SH",
      conditions: [{ type: "price_break", params: { direction: "above", price: 1800 } }],
      context: "突破平台考虑加仓",
    });
    expect(mockRun).toHaveBeenCalledWith("watch.rules.create", expect.objectContaining({
      symbol: "600519.SH", context: "突破平台考虑加仓",
    }));
  });

  it("list 映射到 watch.rules.list 并传 symbol", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.rules.list", data: { rules: [] } } as any);
    await exec({ action: "list", symbol: "600519.SH" });
    expect(mockRun).toHaveBeenCalledWith("watch.rules.list", { symbol: "600519.SH" });
  });

  it("update 需要 rule_id", async () => {
    const result = await exec({ action: "update", enabled: false });
    expect(result.details).toMatchObject({ success: false, error: "MISSING_RULE_ID" });
    expect(mockRun).not.toHaveBeenCalled();
  });

  it("update 映射到 watch.rules.update", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.rules.update", data: { rule: { id: 3 } } } as any);
    await exec({ action: "update", rule_id: 3, enabled: false });
    expect(mockRun).toHaveBeenCalledWith("watch.rules.update", { id: 3, enabled: false });
  });

  it("remove 映射到 watch.rules.remove", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.rules.remove", data: {} } as any);
    await exec({ action: "remove", rule_id: 3 });
    expect(mockRun).toHaveBeenCalledWith("watch.rules.remove", { id: 3 });
  });

  it("triggers 映射到 watch.triggers.list", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.triggers.list", data: { triggers: [] } } as any);
    await exec({ action: "triggers", symbol: "600519.SH", limit: 10 });
    expect(mockRun).toHaveBeenCalledWith("watch.triggers.list", { symbol: "600519.SH", limit: 10 });
  });

  it("add 缺少 conditions 报错", async () => {
    const result = await exec({ action: "add", symbol: "600519.SH" });
    expect(result.details).toMatchObject({ success: false, error: "MISSING_CONDITIONS" });
  });

  it("未知 action 报错", async () => {
    const result = await exec({ action: "explode" });
    expect(result.details).toMatchObject({ success: false });
  });
});
```

- [ ] **Step 4: 运行测试确认失败**

```bash
cd agent-ts && npm test -- src/infrastructure/tools/monitor/watch-manage-tool.test.ts
```

预期：Cannot find module './watch-manage-tool.js'

- [ ] **Step 5: 实现 watch-manage-tool.ts**

创建 `agent-ts/src/infrastructure/tools/monitor/watch-manage-tool.ts`：

```typescript
/**
 * Watch Manage Tool - 实时盯盘规则管理
 *
 * 管理 quantsys-v2 WatchEngine 的盯盘规则：添加/查看/更新/删除监视规则，查询触发记录。
 * 触发后 v2 会通过 wake-channel 唤醒 Agent 决策。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

const ConditionSchema = Type.Object({
  type: Type.String({
    description: "条件类型: price_break(价格上下破) | pct_change(涨跌幅) | pnl_pct(盈亏%) | velocity(瞬时涨速) | volume_surge(量能异动)"
  }),
  params: Type.Record(Type.String(), Type.Any(), {
    description: "条件参数。price_break: {direction, price}; pct_change: {direction, pct}; pnl_pct: {direction, pct}; velocity: {pct, window_min}; volume_surge: {multiple}。direction: above|below；pct 为百分数(3.0=3%)"
  }),
  cooldown_sec: Type.Optional(Type.Number({ description: "触发冷却秒数，默认300" })),
});

function errorResult(error: string, text: string) {
  return {
    content: [{ type: "text" as const, text }],
    details: { success: false, error },
  };
}

export const watchManageTool: ToolDefinition = {
  name: "watch_manage",
  label: "盯盘管理",
  description:
    "实时盯盘规则管理：对股票设置盘中监视条件（价格上下破/涨跌幅/盈亏%/瞬时涨速/量能异动），" +
    "触发时后端会唤醒你决策。持仓股止损止盈、买入机会监控都应通过此工具注册规则。",
  parameters: Type.Object({
    action: Type.String({ description: "操作: add | list | update | remove | triggers" }),
    symbol: Type.Optional(Type.String({ description: "股票代码，如 600519.SH" })),
    rule_id: Type.Optional(Type.Number({ description: "规则ID（update/remove 必填）" })),
    conditions: Type.Optional(Type.Array(ConditionSchema, { description: "监视条件数组（add/update 用）" })),
    context: Type.Optional(Type.String({ description: "监视理由——触发时会原样回传给你作决策上下文，务必写清楚" })),
    cost_price: Type.Optional(Type.Number({ description: "成本价（pnl_pct 条件必填）" })),
    active_window: Type.Optional(Type.Array(Type.String(), {
      description: "盯盘时段，如 [\"09:30-10:30\",\"14:30-15:00\"]，默认全交易时段"
    })),
    expires_at: Type.Optional(Type.String({ description: "过期时间 ISO 格式，如 2026-07-25T15:00:00" })),
    enabled: Type.Optional(Type.Boolean({ description: "启用/停用（update 用）" })),
    limit: Type.Optional(Type.Number({ description: "triggers 返回条数，默认50" })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    const call = async (command: string, payload: Record<string, unknown>) => {
      const response = await runQuantV2(command, payload);
      return handleToolResponse({
        toolName: "watch_manage",
        data: response,
        formatter: (data) => (typeof data === "string" ? data : JSON.stringify(data, null, 2)),
        metadata: { params },
      });
    };

    try {
      switch (params.action) {
        case "add": {
          if (!params.symbol) return errorResult("MISSING_SYMBOL", "缺少必填参数: symbol");
          if (!params.conditions?.length) {
            return errorResult("MISSING_CONDITIONS", "add 需要非空 conditions 数组");
          }
          return call("watch.rules.create", {
            symbol: params.symbol,
            conditions: params.conditions,
            context: params.context,
            cost_price: params.cost_price,
            active_window: params.active_window,
            expires_at: params.expires_at,
          });
        }
        case "list":
          return call("watch.rules.list", {
            symbol: params.symbol,
            enabled: params.enabled,
          });
        case "update": {
          if (params.rule_id === undefined) return errorResult("MISSING_RULE_ID", "update 需要 rule_id");
          const { action, rule_id, ...fields } = params;
          return call("watch.rules.update", { id: rule_id, ...fields });
        }
        case "remove": {
          if (params.rule_id === undefined) return errorResult("MISSING_RULE_ID", "remove 需要 rule_id");
          return call("watch.rules.remove", { id: params.rule_id });
        }
        case "triggers":
          return call("watch.triggers.list", { symbol: params.symbol, limit: params.limit });
        default:
          return errorResult("UNKNOWN_ACTION", `未知 action: ${params.action}，支持: add | list | update | remove | triggers`);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `盯盘规则操作失败: ${errorMsg}` }],
        details: { success: false, error: errorMsg, params },
      };
    }
  },
};
```

- [ ] **Step 6: 注册工具**

修改 `agent-ts/src/infrastructure/tools/index.ts`：

在 `import { watchAlertTool } from "./monitor/watch-alert-tool.js";`（约 170 行）下方加：

```typescript
import { watchManageTool } from "./monitor/watch-manage-tool.js";
```

在工具数组中 `watchAlertTool,`（约 295 行）下方加：

```typescript
  watchManageTool,                // watch_manage - 实时盯盘规则管理
```

- [ ] **Step 7: 运行测试确认通过**

```bash
cd agent-ts && npm test -- src/infrastructure/tools/monitor/watch-manage-tool.test.ts
```

预期：8 passed

- [ ] **Step 8: TypeScript 编译检查**

```bash
cd agent-ts && npx tsc -p tsconfig.build.json --noEmit
```

预期：无 error

- [ ] **Step 9: Commit**

```bash
git add src/infrastructure/adapters/quant/quant-v2-client.ts src/infrastructure/tools/monitor/ src/infrastructure/tools/index.ts
git commit -m "feat: watch_manage 盯盘工具 + 修复 watch.price_alert 命令名 bug"
```

---

### Task 9: 端到端冒烟验证

**Files:** 无新增（手工验证）

- [ ] **Step 1: 启动后端 + 插入一条测试规则**

```bash
cd quantsys-v2 && source activate-py313.sh
python adapters/inbound/api/server.py &   # Flask 5001
curl -s -X POST http://127.0.0.1:5001/api/watch/rules \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"600519.SH","conditions":[{"type":"price_break","params":{"direction":"above","price":1.0}}],"context":"E2E冒烟：阈值极低必然触发"}'
```

预期：`{"success": true, "rule": {"id": ...}}`

- [ ] **Step 2: 单 tick 验证触发链路（不起常驻引擎，直接调 tick）**

```bash
python -c "
from application.services.watch_engine.factory import create_watch_engine
engine = create_watch_engine()
events = engine.tick()
print('events:', events)
"
```

预期：events 非空（价格 > 1.0 必然触发）；`quant.watch_triggers` 表有记录：

```bash
psql -d quant_investment -c "SELECT symbol, trigger_price, notified FROM quant.watch_triggers ORDER BY id DESC LIMIT 1;"
```

- [ ] **Step 3: 清理测试数据**

```bash
curl -s -X DELETE http://127.0.0.1:5001/api/watch/rules/<上一步的id>
psql -d quant_investment -c "DELETE FROM quant.watch_triggers WHERE detail->>'message' LIKE '%上破%';"
```

- [ ] **Step 4: 全量回归**

```bash
cd quantsys-v2 && pytest tests/services/test_watch_conditions.py tests/services/test_watch_engine.py tests/services/test_watch_notifier.py tests/api/test_watch_routes.py tests/api/test_watch_routes_async.py tests/repositories/test_watch_rule_repository.py --no-cov -q
cd ../agent-ts && npm test
```

预期：全部 passed

- [ ] **Step 5: Commit（如有清理改动）+ 更新 spec 状态**

将 spec 文件 `docs/superpowers/specs/2026-07-21-watch-engine-design.md` 的状态行改为 `**状态**: 已实现（2026-07-21）` 并提交。

---

## Self-Review 记录

- **Spec 覆盖**：建表（T1）✓ / 5 种条件（T2）✓ / 自适应频率+冷却+ring buffer+active_window+过期（T3，过期在 T1 仓储过滤）✓ / notify+WS+审计+重试（T4）✓ / 常驻引擎+守护（T5）✓ / Flask+FastAPI parity（T6/T7）✓ / watch_manage 工具+V2_ROUTES 一致性（T8）✓ / 五源全挂不告警（T3 `quote is None` 跳过）✓ / Agent response 回填字段已建表（回填逻辑留给 Agent 侧后续迭代，spec 中标注"后续回填"）✓
- **已知取舍**：`velocity`/`volume_surge` 冷启动降级（spec 已声明）；节假日不停引擎（周末已排除，节假日靠取价 stale 容错，可接受）；WS broadcast URL 硬编码 127.0.0.1:5003 符合固定 IP 约定。
