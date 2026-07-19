# 多账户域方案 · 计划 1：quantsys-v2 后端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 quantsys-v2 落地 6 表账户域模型（账户/委托/成交/资金流水/持仓/净值快照），提供账户注册/发现/手工交易 API，取消所有 `default` 兜底，并完成历史数据迁移。

**Architecture:** 以 `simulation_*` 体系为唯一账户体系；`add_trade` 自动写资金流水维持不变式 `Σ流水 == cash_available + cash_frozen`；手工交易走新的 `AccountTradingService` 单事务流程；服务层对外 JSON key 保持兼容（`cash`、`shares` 等），ORM 列名全面换新。

**Tech Stack:** Python 3.13 / Flask (5001) / SQLAlchemy ORM / PostgreSQL（生产 `quant_investment`，测试 `quant_test`，pytest 自动切换）。

**Spec:** `docs/superpowers/specs/2026-07-19-multi-account-domain-design.md`

**范围说明（与 spec 的三处工程取舍）：**
1. 历史净值曲线由 `/performance` 的 fallback 重放逻辑提供（保留现有代码），快照表自迁移日起累积 —— 避免用当前价格伪造历史净值。
2. FastAPI parity 单独一个 Task（Task 10），Flask 先行（生产 5001 当前是 Flask）。
3. `orders.py` 的 `/api/portfolio/*` 本次只切源 `positions` 与 `summary` 两个端点（Task 8）；`history`/`holdings`/`allocation`/`equity-curve`/`positions/<symbol>` 维持旧体系只读，避免在未知消费方响应契约的情况下盲改，统一放到后续迭代。

**新发现（已纳入 Task 7）：** `SimulationTrader._save_daily_snapshot` 写入全局表 `quant.account_balance`（只有 `balance_date`，**无 account_name**）——v13/v14 的每日快照互相覆盖，这是又一处隔离漏洞，本次改为写新的按账户隔离的快照表。

---

### Task 1: ORM 模型扩充（3 表改造 + 3 表新增）

**Files:**
- Modify: `quantsys-v2/infrastructure/persistence/orm/models/simulation.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/test_multi_account_domain.py`：

```python
"""多账户域模型测试"""
import pytest
from datetime import date


class TestORMModels:
    """Task 1: 模型结构"""

    def test_account_has_new_columns(self):
        from infrastructure.persistence.orm.models.simulation import SimulationAccount
        cols = {c.name for c in SimulationAccount.__table__.columns}
        assert 'cash_available' in cols
        assert 'cash_frozen' in cols
        assert 'position_value' in cols
        assert 'initial_capital' in cols
        assert 'display_name' in cols
        assert 'strategy_name' in cols
        assert 'status' in cols
        assert 'cash' not in cols  # 旧列已改名

    def test_position_has_t1_columns(self):
        from infrastructure.persistence.orm.models.simulation import SimulationPosition
        cols = {c.name for c in SimulationPosition.__table__.columns}
        assert 'shares_total' in cols
        assert 'shares_available' in cols
        assert 'avg_cost' in cols
        assert 'profit_total' in cols
        assert 'profit_total_rate' in cols
        assert 'profit_today' in cols
        assert 'shares' not in cols

    def test_trade_has_realized_pnl_columns(self):
        from infrastructure.persistence.orm.models.simulation import SimulationTrade
        cols = {c.name for c in SimulationTrade.__table__.columns}
        for col in ('order_id', 'transfer_fee', 'realized_pnl', 'realized_pnl_rate', 'reason'):
            assert col in cols, f"missing {col}"

    def test_new_models_exist(self):
        from infrastructure.persistence.orm.models.simulation import (
            SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
        )
        order_cols = {c.name for c in SimulationOrder.__table__.columns}
        assert {'account_name', 'action', 'order_type', 'symbol', 'shares',
                'status', 'filled_shares', 'avg_filled_price', 'reason'} <= order_cols
        flow_cols = {c.name for c in SimulationCashFlow.__table__.columns}
        assert {'account_name', 'flow_type', 'amount', 'balance_after'} <= flow_cols
        snap = SimulationEquitySnapshot.__table__
        snap_cols = {c.name for c in snap.columns}
        assert {'account_name', 'snapshot_date', 'cash', 'position_value',
                'total_value', 'daily_return', 'cumulative_return', 'drawdown'} <= snap_cols
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: FAIL（`cash_available` 不存在等）

- [ ] **Step 3: 修改模型**

`infrastructure/persistence/orm/models/simulation.py`：

1. `SimulationAccount`：将 `cash = Column(...)` 改名为 `cash_available`；在其后新增：

```python
    cash_frozen = Column(Numeric(15, 2), nullable=False, default=0, comment='冻结资金')
    position_value = Column(Numeric(15, 2), nullable=False, default=0, comment='持仓市值')
    initial_capital = Column(Numeric(15, 2), nullable=False, default=0, comment='初始资金')
    display_name = Column(String(100), comment='显示名')
    strategy_name = Column(String(50), comment='绑定策略名')
    status = Column(String(20), nullable=False, default='active', comment='active/archived')
```

`to_dict()` 中 `'cash': ...` 改为 `'cash_available': float(self.cash_available) if self.cash_available else 0`，并增加 `cash_frozen`、`position_value`、`initial_capital`、`display_name`、`strategy_name`、`status` 六个 key。

2. `SimulationPosition`：`shares` → `shares_total`；`avg_price` → `avg_cost`；`profit` → `profit_total`；`profit_rate` → `profit_total_rate`；新增：

```python
    shares_available = Column(Integer, nullable=False, default=0, comment='可用数量(T+1)')
    profit_today = Column(Numeric(15, 2), comment='当日盈亏')
```

`to_dict()` 同步改名并补 `shares_available`、`profit_today`。

3. `SimulationTrade`：新增列：

```python
    order_id = Column(Integer, comment='关联委托单ID')
    transfer_fee = Column(Numeric(10, 2), default=0, comment='过户费')
    realized_pnl = Column(Numeric(15, 2), comment='已实现盈亏(卖出)')
    realized_pnl_rate = Column(Numeric(10, 4), comment='已实现盈亏率')
    reason = Column(String(500), comment='交易理由')
```

`to_dict()` 补充对应 key。

4. 文件末尾追加三个新模型（并加入 `__all__`）：

```python
class SimulationOrder(Base):
    """委托单表 quant.simulation_order"""
    __tablename__ = 'simulation_order'
    __table_args__ = (
        Index('idx_simulation_order_account', 'account_name'),
        Index('idx_simulation_order_symbol', 'symbol'),
        {'schema': 'quant'}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(String(50), nullable=False, comment='账户名称')
    action = Column(String(10), nullable=False, comment='buy/sell')
    order_type = Column(String(20), nullable=False, default='market', comment='market/limit')
    symbol = Column(String(20), nullable=False)
    shares = Column(Integer, nullable=False)
    price_limit = Column(Numeric(10, 2), comment='限价')
    status = Column(String(20), nullable=False, default='submitted',
                    comment='submitted/filled/partially_filled/cancelled/rejected')
    filled_shares = Column(Integer, default=0)
    avg_filled_price = Column(Numeric(10, 2))
    reason = Column(String(500), comment='决策理由')
    strategy_name = Column(String(50), comment='来源策略')
    signal_id = Column(String(64), comment='来源信号')
    reject_reason = Column(String(500))
    created_at = Column(DateTime(timezone=False), default=datetime.now)
    updated_at = Column(DateTime(timezone=False), default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id, 'account_name': self.account_name, 'action': self.action,
            'order_type': self.order_type, 'symbol': self.symbol, 'shares': self.shares,
            'price_limit': float(self.price_limit) if self.price_limit else None,
            'status': self.status, 'filled_shares': self.filled_shares,
            'avg_filled_price': float(self.avg_filled_price) if self.avg_filled_price else None,
            'reason': self.reason, 'strategy_name': self.strategy_name,
            'signal_id': self.signal_id, 'reject_reason': self.reject_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SimulationCashFlow(Base):
    """资金流水表 quant.simulation_cash_flow —— 所有资金变动必须经此表"""
    __tablename__ = 'simulation_cash_flow'
    __table_args__ = (
        Index('idx_simulation_cash_flow_account', 'account_name'),
        {'schema': 'quant'}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(String(50), nullable=False)
    flow_type = Column(String(20), nullable=False,
                       comment='deposit/buy_debit/sell_credit/fee/withdraw/dividend/adjustment')
    amount = Column(Numeric(15, 2), nullable=False, comment='有符号变动额')
    balance_after = Column(Numeric(15, 2), nullable=False, comment='变动后余额')
    ref_order_id = Column(Integer, comment='来源委托单')
    ref_trade_id = Column(Integer, comment='来源成交')
    created_at = Column(DateTime(timezone=False), default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id, 'account_name': self.account_name, 'flow_type': self.flow_type,
            'amount': float(self.amount), 'balance_after': float(self.balance_after),
            'ref_order_id': self.ref_order_id, 'ref_trade_id': self.ref_trade_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SimulationEquitySnapshot(Base):
    """净值快照表 quant.simulation_equity_snapshot，(account_name, snapshot_date) 唯一"""
    __tablename__ = 'simulation_equity_snapshot'
    __table_args__ = (
        Index('simulation_equity_snapshot_account_date_key',
              'account_name', 'snapshot_date', unique=True),
        {'schema': 'quant'}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(String(50), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    cash = Column(Numeric(15, 2), nullable=False, default=0)
    position_value = Column(Numeric(15, 2), nullable=False, default=0)
    total_value = Column(Numeric(15, 2), nullable=False, default=0)
    daily_return = Column(Numeric(10, 4), default=0)
    cumulative_return = Column(Numeric(10, 4), default=0)
    drawdown = Column(Numeric(10, 4), default=0)
    created_at = Column(DateTime(timezone=False), default=datetime.now)

    def to_dict(self):
        return {
            'account_name': self.account_name,
            'date': self.snapshot_date.isoformat() if self.snapshot_date else None,
            'cash': float(self.cash or 0),
            'position_value': float(self.position_value or 0),
            'total_value': float(self.total_value or 0),
            'daily_return': float(self.daily_return or 0),
            'cumulative_return': float(self.cumulative_return or 0),
            'drawdown': float(self.drawdown or 0),
        }
```

5. 更新 `__all__`：

```python
__all__ = [
    'SimulationAccount', 'SimulationPosition', 'SimulationTrade',
    'SimulationOrder', 'SimulationCashFlow', 'SimulationEquitySnapshot',
]
```

6. 检查 `infrastructure/persistence/orm/models/__init__.py`，将三个新模型加入导出列表。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS（4 个模型测试）

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add infrastructure/persistence/orm/models/simulation.py infrastructure/persistence/orm/models/__init__.py tests/test_multi_account_domain.py
git commit -m "feat: 账户域模型扩充（资金两态/T+1持仓/委托单/资金流水/净值快照）"
```

---

### Task 2: 数据迁移脚本

**Files:**
- Create: `quantsys-v2/scripts/migrate_20260720_multi_account.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（追加）

幂等设计：所有 DDL 用 `IF NOT EXISTS` / information_schema 探测；数据改写用 `WHERE account_name='default'`（天然幂等）。脚本同时用于生产库和测试库（pytest 环境自动连 `quant_test`）。

- [ ] **Step 1: 写失败测试（迁移幂等性）**

`tests/test_multi_account_domain.py` 追加：

```python
class TestMigration:
    """Task 2: 迁移脚本幂等 + 结果正确"""

    def test_migration_idempotent(self):
        from scripts.migrate_20260720_multi_account import run_migration
        run_migration()   # 第一次
        run_migration()   # 第二次不报错即幂等

        from sqlalchemy import inspect
        from infrastructure.persistence.database.engine import get_engine
        insp = inspect(get_engine())
        acc_cols = {c['name'] for c in insp.get_columns('simulation_account', schema='quant')}
        assert 'cash_available' in acc_cols and 'cash' not in acc_cols
        pos_cols = {c['name'] for c in insp.get_columns('simulation_positions', schema='quant')}
        assert 'shares_total' in pos_cols and 'shares' not in pos_cols
        for table in ('simulation_order', 'simulation_cash_flow', 'simulation_equity_snapshot'):
            assert insp.has_table(table, schema='quant'), f"missing table {table}"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py::TestMigration -x -q`
Expected: FAIL（`No module named 'scripts.migrate_20260720_multi_account'`）

- [ ] **Step 3: 实现迁移脚本**

创建 `scripts/migrate_20260720_multi_account.py`：

```python
#!/usr/bin/env python3
"""多账户域迁移（2026-07-20）—— 幂等

1. 列改名/加列（account/positions/trades）
2. 建 3 张新表
3. default → v13_simulation（三表）
4. 补建 v15_simulation 账户
5. 回填 initial_capital / 资金流水 / 当日快照
"""
from sqlalchemy import text
from infrastructure.persistence.database.engine import get_engine
from infrastructure.persistence.orm.models import Base  # 确保新表由 metadata 创建


def _column_exists(conn, table, column):
    row = conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='quant' AND table_name=:t AND column_name=:c"
    ), {'t': table, 'c': column}).fetchone()
    return row is not None


def _rename_column(conn, table, old, new):
    if _column_exists(conn, table, old) and not _column_exists(conn, table, new):
        conn.execute(text(f'ALTER TABLE quant.{table} RENAME COLUMN {old} TO {new}'))


def run_migration():
    engine = get_engine()
    # 1) 新表（ORM metadata）
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        # 2) 列改名
        _rename_column(conn, 'simulation_account', 'cash', 'cash_available')
        _rename_column(conn, 'simulation_positions', 'shares', 'shares_total')
        _rename_column(conn, 'simulation_positions', 'avg_price', 'avg_cost')
        _rename_column(conn, 'simulation_positions', 'profit', 'profit_total')
        _rename_column(conn, 'simulation_positions', 'profit_rate', 'profit_total_rate')

        # 3) 加列
        ddls = [
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS cash_frozen NUMERIC(15,2) NOT NULL DEFAULT 0",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS position_value NUMERIC(15,2) NOT NULL DEFAULT 0",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS initial_capital NUMERIC(15,2) NOT NULL DEFAULT 0",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS display_name VARCHAR(100)",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(50)",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active'",
            "ALTER TABLE quant.simulation_positions ADD COLUMN IF NOT EXISTS shares_available INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE quant.simulation_positions ADD COLUMN IF NOT EXISTS profit_today NUMERIC(15,2)",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS order_id INTEGER",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS transfer_fee NUMERIC(10,2) DEFAULT 0",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS realized_pnl NUMERIC(15,2)",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS realized_pnl_rate NUMERIC(10,4)",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS reason VARCHAR(500)",
        ]
        for ddl in ddls:
            conn.execute(text(ddl))

        # 历史持仓均已过 T+1：available = total
        conn.execute(text(
            "UPDATE quant.simulation_positions SET shares_available = shares_total "
            "WHERE shares_available = 0 AND shares_total > 0"
        ))

        # 4) default → v13_simulation（幂等：无 default 行时为零操作）
        for table in ('simulation_account', 'simulation_positions', 'simulation_trades'):
            conn.execute(text(
                f"UPDATE quant.{table} SET account_name='v13_simulation' "
                "WHERE account_name='default'"
            ))
        conn.execute(text(
            "UPDATE quant.simulation_account SET display_name='V13 多因子模拟仓', "
            "strategy_name='v13' WHERE account_name='v13_simulation'"
        ))
        conn.execute(text(
            "UPDATE quant.simulation_account SET display_name='V14 模拟仓', "
            "strategy_name='v14' WHERE account_name='v14_simulation'"
        ))

        # 5) 回填 initial_capital（用累计收益率反推，仅一次）
        conn.execute(text(
            "UPDATE quant.simulation_account SET initial_capital = "
            "CASE WHEN cumulative_return IS NOT NULL AND cumulative_return <> 0 "
            "THEN total_value / (1 + cumulative_return) ELSE total_value END "
            "WHERE initial_capital IS NULL OR initial_capital = 0"
        ))

        # 6) 补建 v15_simulation
        conn.execute(text(
            "INSERT INTO quant.simulation_account "
            "(account_name, display_name, strategy_name, initial_capital, "
            " cash_available, total_value, status) "
            "VALUES ('v15_simulation', 'V15 深度学习模拟仓', 'v15', 100000, 100000, 100000, 'active') "
            "ON CONFLICT (account_name) DO NOTHING"
        ))

        # 7) 回填资金流水（仅当流水表为空时，逐账户重放交易）
        flow_count = conn.execute(text("SELECT count(*) FROM quant.simulation_cash_flow")).scalar()
        if flow_count == 0:
            accounts = conn.execute(text(
                "SELECT account_name, initial_capital FROM quant.simulation_account"
            )).fetchall()
            for acc_name, init_cap in accounts:
                balance = float(init_cap or 0)
                conn.execute(text(
                    "INSERT INTO quant.simulation_cash_flow "
                    "(account_name, flow_type, amount, balance_after) "
                    "VALUES (:a, 'deposit', :amt, :bal)"
                ), {'a': acc_name, 'amt': balance, 'bal': balance})
                trades = conn.execute(text(
                    "SELECT id, action, amount, commission, stamp_duty "
                    "FROM quant.simulation_trades WHERE account_name=:a "
                    "ORDER BY trade_time, id"
                ), {'a': acc_name}).fetchall()
                for t_id, action, amount, commission, stamp_duty in trades:
                    amt = float(amount or 0)
                    fees = float(commission or 0) + float(stamp_duty or 0)
                    net = -(amt + fees) if action.lower() == 'buy' else (amt - fees)
                    ftype = 'buy_debit' if action.lower() == 'buy' else 'sell_credit'
                    balance += net
                    conn.execute(text(
                        "INSERT INTO quant.simulation_cash_flow "
                        "(account_name, flow_type, amount, balance_after, ref_trade_id) "
                        "VALUES (:a, :t, :amt, :bal, :tid)"
                    ), {'a': acc_name, 't': ftype, 'amt': net, 'bal': balance, 'tid': t_id})
                # 对账：流水终值 vs 账户余额，有差额写 adjustment 流水强制不变式成立
                cash_row = conn.execute(text(
                    "SELECT cash_available + cash_frozen FROM quant.simulation_account "
                    "WHERE account_name=:a"
                ), {'a': acc_name}).fetchone()
                if cash_row is not None:
                    drift = float(cash_row[0]) - balance
                    if abs(drift) > 0.01:
                        balance += drift
                        conn.execute(text(
                            "INSERT INTO quant.simulation_cash_flow "
                            "(account_name, flow_type, amount, balance_after) "
                            "VALUES (:a, 'adjustment', :amt, :bal)"
                        ), {'a': acc_name, 'amt': drift, 'bal': balance})
                        print(f"[迁移] {acc_name} 对账差额 ¥{drift:.2f}，已写 adjustment 流水")

        # 8) 当日快照（每账户一条，历史曲线由 /performance fallback 重放提供）
        conn.execute(text(
            "INSERT INTO quant.simulation_equity_snapshot "
            "(account_name, snapshot_date, cash, position_value, total_value, "
            " cumulative_return, drawdown) "
            "SELECT account_name, CURRENT_DATE, cash_available + cash_frozen, "
            "       position_value, total_value, cumulative_return, "
            "       CASE WHEN peak_value > 0 THEN total_value / peak_value - 1 ELSE 0 END "
            "FROM quant.simulation_account "
            "ON CONFLICT (account_name, snapshot_date) DO NOTHING"
        ))

    print("[迁移] 多账户域迁移完成")


if __name__ == '__main__':
    run_migration()
```

同时修改 `live_trading/configs/strategies/v13.yaml` 第 8 行：

```yaml
  account_name: "v13_simulation"  # 数据库账户名称
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS（含迁移幂等测试）

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add scripts/migrate_20260720_multi_account.py live_trading/configs/strategies/v13.yaml tests/test_multi_account_domain.py
git commit -m "feat: 多账户域迁移脚本（幂等）+ v13 账户改名 v13_simulation"
```

---

### Task 3: Repository 扩展

**Files:**
- Modify: `quantsys-v2/adapters/outbound/repositories/simulation_repository.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（追加）

- [ ] **Step 1: 写失败测试**

`tests/test_multi_account_domain.py` 追加（fixture 与清理辅助一并加入）：

```python
TEST_ACCOUNTS = ('test_acc_a', 'test_acc_b')


@pytest.fixture()
def repo():
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    from scripts.migrate_20260720_multi_account import run_migration
    run_migration()  # 幂等，确保测试库结构就位
    r = SimulationORMRepository()
    yield r
    # 清理测试账户数据
    from infrastructure.persistence.orm.models.simulation import (
        SimulationAccount, SimulationPosition, SimulationTrade,
        SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
    )
    for model in (SimulationCashFlow, SimulationOrder, SimulationTrade,
                  SimulationPosition, SimulationEquitySnapshot, SimulationAccount):
        r.session.query(model).filter(model.account_name.in_(TEST_ACCOUNTS)).delete(
            synchronize_session=False)
    r.session.commit()


class TestRepository:
    """Task 3: Repository 扩展"""

    def test_create_account_writes_deposit_flow(self, repo):
        acc = repo.create_account('test_acc_a', initial_capital=200000,
                                  display_name='测试账户A', strategy_name=None)
        assert acc is not None
        assert float(acc.cash_available) == 200000
        assert float(acc.initial_capital) == 200000
        assert acc.status == 'active'
        flows = repo.get_cash_flows('test_acc_a')
        assert len(flows) == 1
        assert flows[0].flow_type == 'deposit'
        assert float(flows[0].balance_after) == 200000

    def test_list_account_summaries(self, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.create_account('test_acc_b', initial_capital=50000)
        summaries = repo.list_account_summaries()
        names = {s['account_name'] for s in summaries}
        assert {'test_acc_a', 'test_acc_b'} <= names
        a = next(s for s in summaries if s['account_name'] == 'test_acc_a')
        assert a['positions_count'] == 0
        assert a['cash_available'] == 100000.0

    def test_add_trade_auto_writes_cash_flow(self, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.add_trade(account_name='test_acc_a', symbol='600519', action='buy',
                       shares=100, price=10.0, filled_price=10.0,
                       commission=5.0, stamp_duty=0.0)
        result = repo.verify_cash_flow_invariant('test_acc_a')
        # 100000 - (1000 + 5) = 98995
        assert result['flow_balance'] == pytest.approx(98995.0, abs=0.01)
        # 账户 cash 尚未同步（由调用方负责），此处只验流水链
        assert result['flow_count'] == 2

    def test_equity_snapshot_upsert(self, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.upsert_equity_snapshot('test_acc_a', cash=60000, position_value=40000,
                                    total_value=100000, daily_return=0.01,
                                    cumulative_return=0.0, drawdown=0.0)
        repo.upsert_equity_snapshot('test_acc_a', cash=60000, position_value=41000,
                                    total_value=101000, daily_return=0.01,
                                    cumulative_return=0.01, drawdown=0.0)
        snaps = repo.get_equity_snapshots('test_acc_a')
        assert len(snaps) == 1  # 同日 upsert 不产生第二条
        assert float(snaps[0].total_value) == 101000

    def test_settle_t1(self, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.upsert_position('test_acc_a', '600519', shares_total=100, avg_cost=10.0,
                             shares_available=0)
        n = repo.settle_t1('test_acc_a')
        assert n == 1
        pos = repo.get_position('test_acc_a', '600519')
        assert pos.shares_available == 100
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py::TestRepository -x -q`
Expected: FAIL（方法不存在）

- [ ] **Step 3: 实现 Repository 扩展**

`adapters/outbound/repositories/simulation_repository.py`：

1. 头部 import 追加：

```python
from infrastructure.persistence.orm.models import (
    SimulationAccount, SimulationPosition, SimulationTrade,
    SimulationOrder, SimulationCashFlow, SimulationEquitySnapshot,
)
```

2. `create_account` 整体替换为：

```python
    def create_account(
        self,
        account_name: str,
        initial_capital: float,
        display_name: Optional[str] = None,
        strategy_name: Optional[str] = None,
        commit: bool = True
    ) -> Optional[SimulationAccount]:
        """开户（写 deposit 资金流水，建立流水链起点）"""
        try:
            existing = self.get_account(account_name)
            if existing:
                logger.warning(f"Account {account_name} already exists")
                return existing
            account = SimulationAccount(
                account_name=account_name,
                display_name=display_name or account_name,
                strategy_name=strategy_name,
                initial_capital=initial_capital,
                cash_available=initial_capital,
                cash_frozen=0,
                total_value=initial_capital,
                peak_value=initial_capital,
                status='active',
            )
            self.session.add(account)
            flow = SimulationCashFlow(
                account_name=account_name, flow_type='deposit',
                amount=initial_capital, balance_after=initial_capital,
            )
            self.session.add(flow)
            if commit:
                self.session.commit()
                self.session.refresh(account)
            logger.info(f"开户成功: {account_name}, 初始资金 ¥{initial_capital:,.2f}")
            return account
        except Exception as e:
            logger.error(f"Error creating account {account_name}: {e}")
            self.session.rollback()
            return None
```

3. 新增方法（追加到类中）：

```python
    # ==================== 账户发现 ====================

    def list_accounts(self, status: str = 'active') -> List[SimulationAccount]:
        return self.session.query(SimulationAccount).filter_by(status=status).all()

    def list_account_summaries(self, status: str = 'active') -> List[Dict]:
        accounts = self.list_accounts(status)
        counts = dict(
            self.session.query(
                SimulationPosition.account_name, func.count()
            ).group_by(SimulationPosition.account_name).all()
        )
        return [{
            'account_name': a.account_name,
            'display_name': a.display_name,
            'strategy_name': a.strategy_name,
            'status': a.status,
            'cash_available': float(a.cash_available or 0),
            'cash_frozen': float(a.cash_frozen or 0),
            'position_value': float(a.position_value or 0),
            'total_value': float(a.total_value or 0),
            'cumulative_return': float(a.cumulative_return or 0),
            'positions_count': int(counts.get(a.account_name, 0)),
        } for a in accounts]

    def archive_account(self, account_name: str) -> bool:
        account = self.get_account(account_name)
        if not account:
            return False
        account.status = 'archived'
        self.session.commit()
        return True

    # ==================== 资金流水 ====================

    def add_cash_flow(
        self,
        account_name: str,
        flow_type: str,
        amount: float,
        balance_after: float,
        ref_order_id: Optional[int] = None,
        ref_trade_id: Optional[int] = None,
        commit: bool = True
    ) -> Optional[SimulationCashFlow]:
        flow = SimulationCashFlow(
            account_name=account_name, flow_type=flow_type, amount=amount,
            balance_after=balance_after, ref_order_id=ref_order_id,
            ref_trade_id=ref_trade_id,
        )
        self.session.add(flow)
        if commit:
            self.session.commit()
        return flow

    def get_cash_flows(self, account_name: str, limit: int = 500) -> List[SimulationCashFlow]:
        return self.session.query(SimulationCashFlow).filter_by(
            account_name=account_name
        ).order_by(SimulationCashFlow.id).limit(limit).all()

    def get_last_flow_balance(self, account_name: str) -> Optional[float]:
        flow = self.session.query(SimulationCashFlow).filter_by(
            account_name=account_name
        ).order_by(SimulationCashFlow.id.desc()).first()
        return float(flow.balance_after) if flow else None

    def verify_cash_flow_invariant(self, account_name: str) -> Dict:
        """校验不变式: 末条流水余额 == cash_available + cash_frozen"""
        account = self.get_account(account_name)
        flows = self.get_cash_flows(account_name, limit=100000)
        flow_balance = float(flows[-1].balance_after) if flows else 0.0
        cash = float(account.cash_available or 0) + float(account.cash_frozen or 0) if account else 0.0
        return {
            'account_name': account_name,
            'flow_balance': flow_balance,
            'account_cash': cash,
            'flow_count': len(flows),
            'invariant_ok': abs(flow_balance - cash) < 0.01,
        }

    # ==================== 委托单 ====================

    def create_order(
        self,
        account_name: str,
        action: str,
        symbol: str,
        shares: int,
        order_type: str = 'market',
        price_limit: Optional[float] = None,
        reason: Optional[str] = None,
        strategy_name: Optional[str] = None,
        signal_id: Optional[str] = None,
        commit: bool = True
    ) -> SimulationOrder:
        order = SimulationOrder(
            account_name=account_name, action=action, order_type=order_type,
            symbol=symbol, shares=shares, price_limit=price_limit,
            status='submitted', filled_shares=0, reason=reason,
            strategy_name=strategy_name, signal_id=signal_id,
        )
        self.session.add(order)
        if commit:
            self.session.commit()
            self.session.refresh(order)
        else:
            self.session.flush()  # 拿到 order.id
        return order

    # ==================== 净值快照 ====================

    def upsert_equity_snapshot(
        self,
        account_name: str,
        cash: float,
        position_value: float,
        total_value: float,
        daily_return: float = 0.0,
        cumulative_return: float = 0.0,
        drawdown: float = 0.0,
        snapshot_date: Optional[date] = None,
        commit: bool = True
    ) -> SimulationEquitySnapshot:
        day = snapshot_date or datetime.now().date()
        snap = self.session.query(SimulationEquitySnapshot).filter_by(
            account_name=account_name, snapshot_date=day
        ).first()
        if snap:
            snap.cash = cash
            snap.position_value = position_value
            snap.total_value = total_value
            snap.daily_return = daily_return
            snap.cumulative_return = cumulative_return
            snap.drawdown = drawdown
        else:
            snap = SimulationEquitySnapshot(
                account_name=account_name, snapshot_date=day, cash=cash,
                position_value=position_value, total_value=total_value,
                daily_return=daily_return, cumulative_return=cumulative_return,
                drawdown=drawdown,
            )
            self.session.add(snap)
        if commit:
            self.session.commit()
        return snap

    def get_equity_snapshots(self, account_name: str, limit: int = 90) -> List[SimulationEquitySnapshot]:
        return self.session.query(SimulationEquitySnapshot).filter_by(
            account_name=account_name
        ).order_by(SimulationEquitySnapshot.snapshot_date.desc()).limit(limit).all()

    # ==================== T+1 结转 ====================

    def settle_t1(self, account_name: str) -> int:
        """T+1 结转：将该账户全部持仓的可用数置为总数（次日全部可卖），返回更新行数"""
        n = self.session.query(SimulationPosition).filter_by(
            account_name=account_name
        ).update({'shares_available': SimulationPosition.shares_total},
                 synchronize_session=False)
        self.session.commit()
        return n
```

4. `update_account` 签名改 `cash: float` → `cash_available: float`，方法体内 `account.cash = cash` → `account.cash_available = cash_available`；新增可选参数 `position_value: Optional[float] = None`，为 None 时不更新，否则 `account.position_value = position_value`。

5. `upsert_position` 签名改为：

```python
    def upsert_position(
        self,
        account_name: str,
        symbol: str,
        shares_total: int,
        avg_cost: float,
        shares_available: Optional[int] = None,
        commit: bool = True
    ) -> bool:
```

方法体内 `get_position(account_name, symbol)` 存在则更新 `shares_total`/`avg_cost`/`shares_available`（None 时 = shares_total）；不存在则新建（`shares_available = shares_available if shares_available is not None else shares_total`）。

6. `add_trade` 扩展签名并自动写流水：

```python
    def add_trade(
        self,
        account_name: str,
        symbol: str,
        action: str,
        shares: int,
        price: float,
        filled_price: float,
        amount: Optional[float] = None,
        commission: float = 0,
        stamp_duty: float = 0,
        transfer_fee: float = 0,
        total_cost: Optional[float] = None,
        total_revenue: Optional[float] = None,
        trade_date: Optional[str] = None,
        order_type: str = 'market',
        order_id: Optional[int] = None,
        realized_pnl: Optional[float] = None,
        realized_pnl_rate: Optional[float] = None,
        reason: Optional[str] = None,
        write_flow: bool = True,
        commit: bool = True
    ) -> Optional[int]:
```

在原构造 `SimulationTrade(...)` 的参数中追加 `order_id=order_id, transfer_fee=transfer_fee, realized_pnl=realized_pnl, realized_pnl_rate=realized_pnl_rate, reason=reason`；原 `self.create(trade, commit=True)` 改为 `self.session.add(trade); self.session.flush()`，随后：

```python
            if write_flow:
                fees = float(commission or 0) + float(stamp_duty or 0) + float(transfer_fee or 0)
                if action.lower() == 'buy':
                    net = -(float(amount) + fees)
                    flow_type = 'buy_debit'
                else:
                    net = float(amount) - fees
                    flow_type = 'sell_credit'
                last = self.get_last_flow_balance(account_name)
                prev = last if last is not None else float(
                    self.get_account(account_name).cash_available or 0)
                self.add_cash_flow(
                    account_name=account_name, flow_type=flow_type, amount=net,
                    balance_after=prev + net, ref_order_id=order_id,
                    ref_trade_id=trade.id, commit=False)
            if commit:
                self.session.commit()
            return trade.id
```

7. `get_account` / `get_all_positions` / `get_trades` / `get_trades_by_account` 的 `account_name: str = 'default'` 默认值全部删除（改为必填位置参数）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add adapters/outbound/repositories/simulation_repository.py tests/test_multi_account_domain.py
git commit -m "feat: Repository 扩展（账户发现/资金流水/委托单/快照/T+1/自动流水）"
```

---

### Task 4: AccountTradingService（手工交易事务）

**Files:**
- Create: `quantsys-v2/application/services/account_trading_service.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
class TestAccountTradingService:
    """Task 4: 手工交易事务"""

    @pytest.fixture()
    def trading(self, repo):
        from application.services.account_trading_service import AccountTradingService
        return AccountTradingService(repo=repo)

    def test_buy_success_full_chain(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        result = trading.execute_trade(
            'test_acc_a', 'buy', '600519', shares=100,
            reason='测试买入：技术面突破+放量', price=10.0)
        assert result['order_status'] == 'filled'
        assert result['shares'] == 100
        acc = repo.get_account('test_acc_a')
        # 费用: 佣金 max(1000*0.00025,5)=5, 印花税0, 过户费 1000*0.00001=0.01
        assert float(acc.cash_available) == pytest.approx(100000 - 1000 - 5 - 0.01, abs=0.01)
        pos = repo.get_position('test_acc_a', '600519')
        assert pos.shares_total == 100
        assert pos.shares_available == 0  # T+1 当日不可卖
        inv = repo.verify_cash_flow_invariant('test_acc_a')
        assert inv['invariant_ok'], inv

    def test_sell_t1_blocked_same_day(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：技术面突破+放量', price=10.0)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'sell', '600519', shares=100,
                                  reason='测试卖出：当日卖出应被T+1拦截', price=11.0)
        assert exc.value.status_code == 422
        assert 'T+1' in str(exc.value) or '可卖' in str(exc.value)

    def test_sell_next_day_with_realized_pnl(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：技术面突破+放量', price=10.0)
        repo.settle_t1('test_acc_a')  # 模拟次日
        result = trading.execute_trade('test_acc_a', 'sell', '600519', shares=100,
                                       reason='测试卖出：止盈离场验证盈亏', price=11.0)
        # 收入1100, 费用: 佣金5, 印花税0.55, 过户费0.011
        # 成本(含费用摊薄): (1000+5+0.01)/100 = 10.0501/股
        assert result['realized_pnl'] is not None
        assert result['realized_pnl'] > 0  # 涨价卖出必盈利
        inv = repo.verify_cash_flow_invariant('test_acc_a')
        assert inv['invariant_ok'], inv

    def test_buy_insufficient_cash(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=1000)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=1000,
                                  reason='测试买入：资金不足应被拒绝', price=10.0)
        assert exc.value.status_code == 422

    def test_archived_account_rejected(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.archive_account('test_acc_a')
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                                  reason='测试买入：归档账户应被拒绝', price=10.0)
        assert exc.value.status_code == 409

    def test_reason_required(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                                  reason='太短', price=10.0)
        assert exc.value.status_code == 400

    def test_single_position_risk_limit(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            # 买入 5 万，超过总资产 30%
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=5000,
                                  reason='测试买入：单票超限应被拒绝', price=10.0)
        assert exc.value.status_code == 422
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py::TestAccountTradingService -x -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 AccountTradingService**

创建 `application/services/account_trading_service.py`：

```python
"""账户交易服务 —— 手工/代管交易的单事务执行

事务流: 校验 → 委托单 → 成交+费用 → 资金流水(add_trade自动) → 持仓 → 账户 → 快照
"""
import logging
from typing import Dict, Optional

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

logger = logging.getLogger(__name__)


class TradingError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


class AccountTradingService:
    COMMISSION_RATE = 0.00025      # 佣金万2.5
    COMMISSION_MIN = 5.0           # 最低5元
    STAMP_DUTY_RATE = 0.0005       # 印花税(卖出)
    TRANSFER_FEE_RATE = 0.00001    # 过户费
    MAX_SINGLE_POSITION_RATIO = 0.30
    MAX_TOTAL_POSITION_RATIO = 0.80

    def __init__(self, repo: Optional[SimulationORMRepository] = None):
        self.repo = repo or SimulationORMRepository()

    def _get_price(self, symbol: str) -> float:
        from application.services.realtime_quote_service import RealtimeQuoteService
        quote = RealtimeQuoteService().get_realtime_quote(symbol)
        if not quote or not quote.price or quote.price <= 0:
            raise TradingError(f'无法获取 {symbol} 实时价格', 502)
        return float(quote.price)

    def execute_trade(
        self,
        account_name: str,
        action: str,
        symbol: str,
        shares: Optional[int] = None,
        amount: Optional[float] = None,
        price_limit: Optional[float] = None,
        reason: Optional[str] = None,
        max_positions: int = 10,
        price: Optional[float] = None,
    ) -> Dict:
        # ---- 校验 ----
        if not reason or len(reason.strip()) < 10:
            raise TradingError('必须提供详细的交易理由（至少10字）', 400)
        action = (action or '').lower()
        if action not in ('buy', 'sell'):
            raise TradingError("action 必须是 'buy' 或 'sell'", 400)
        account = self.repo.get_account(account_name)
        if not account:
            raise TradingError(f'账户不存在: {account_name}', 404)
        if account.status != 'active':
            raise TradingError(f'账户已归档，拒绝写操作: {account_name}', 409)

        self.repo.settle_t1(account_name)  # 历史持仓全部可卖（T+1 次日结转）

        px = price if price is not None else self._get_price(symbol)
        if price_limit is not None:
            if action == 'buy' and px > price_limit:
                raise TradingError(f'现价 {px} 高于限价 {price_limit}，委托拒绝', 422)
            if action == 'sell' and px < price_limit:
                raise TradingError(f'现价 {px} 低于限价 {price_limit}，委托拒绝', 422)

        if shares is None:
            if not amount:
                raise TradingError('shares 与 amount 必须提供一个', 400)
            shares = int(amount // (px * 100)) * 100
            if shares <= 0:
                raise TradingError('金额不足一手（100股）', 422)
        if shares % 100 != 0:
            raise TradingError('股数必须为 100 的整数倍', 422)

        trade_amount = round(px * shares, 2)
        commission = max(round(trade_amount * self.COMMISSION_RATE, 2), self.COMMISSION_MIN)
        stamp_duty = round(trade_amount * self.STAMP_DUTY_RATE, 2) if action == 'sell' else 0.0
        transfer_fee = round(trade_amount * self.TRANSFER_FEE_RATE, 2)

        positions = self.repo.get_all_positions(account_name)
        pos = next((p for p in positions if p.symbol == symbol), None)
        position_value = sum(
            float(p.market_value or 0) or float(p.shares_total) * float(p.current_price or p.avg_cost)
            for p in positions
        )
        total_value = float(account.cash_available) + float(account.cash_frozen) + position_value
        if total_value <= 0:
            total_value = float(account.total_value or account.initial_capital or 1)

        realized_pnl = None
        realized_pnl_rate = None
        if action == 'buy':
            total_cost = trade_amount + commission + transfer_fee
            if total_cost > float(account.cash_available):
                raise TradingError(
                    f'可用资金不足: 需要 ¥{total_cost:,.2f}，可用 ¥{float(account.cash_available):,.2f}', 422)
            new_mv = trade_amount + (
                float(pos.market_value or 0) or float(pos.shares_total) * px if pos else 0)
            if new_mv / total_value > self.MAX_SINGLE_POSITION_RATIO:
                raise TradingError(
                    f'单票仓位超限: 买入后 {symbol} 市值占比 {new_mv / total_value:.1%} > 30%', 422)
            if pos is None and len(positions) >= max_positions:
                raise TradingError(f'持仓数量超限: 已持有 {len(positions)} 只，上限 {max_positions}', 422)
            if (position_value + trade_amount) / total_value > self.MAX_TOTAL_POSITION_RATIO:
                raise TradingError('总仓位超限: 买入后超过总资产 80%', 422)
        else:
            if pos is None or pos.shares_total <= 0:
                raise TradingError(f'无 {symbol} 持仓，无法卖出', 422)
            if shares > pos.shares_available:
                raise TradingError(
                    f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422)
            cost_basis = shares * float(pos.avg_cost)
            realized_pnl = round(trade_amount - cost_basis - commission - stamp_duty - transfer_fee, 2)
            realized_pnl_rate = round(realized_pnl / cost_basis, 4) if cost_basis else 0.0

        # ---- 单事务执行 ----
        try:
            order = self.repo.create_order(
                account_name=account_name, action=action, symbol=symbol,
                shares=shares, price_limit=price_limit, reason=reason,
                commit=False)
            order.status = 'filled'
            order.filled_shares = shares
            order.avg_filled_price = px

            trade_id = self.repo.add_trade(
                account_name=account_name, symbol=symbol, action=action,
                shares=shares, price=px, filled_price=px, amount=trade_amount,
                commission=commission, stamp_duty=stamp_duty, transfer_fee=transfer_fee,
                total_cost=trade_amount + commission + transfer_fee if action == 'buy' else None,
                total_revenue=trade_amount - commission - stamp_duty - transfer_fee if action == 'sell' else None,
                order_id=order.id, realized_pnl=realized_pnl,
                realized_pnl_rate=realized_pnl_rate, reason=reason, commit=False)

            if action == 'buy':
                old_total = pos.shares_total if pos else 0
                old_cost = float(pos.avg_cost) * old_total if pos else 0.0
                new_total = old_total + shares
                new_avg = round((old_cost + trade_amount + commission + transfer_fee) / new_total, 4)
                self.repo.upsert_position(
                    account_name, symbol, shares_total=new_total, avg_cost=new_avg,
                    shares_available=pos.shares_available if pos else 0,  # 当日买入不可卖
                    commit=False)
                account.cash_available = float(account.cash_available) - (
                    trade_amount + commission + transfer_fee)
            else:
                remaining = pos.shares_total - shares
                if remaining == 0:
                    self.repo.delete_position(account_name, symbol)
                else:
                    self.repo.upsert_position(
                        account_name, symbol, shares_total=remaining,
                        avg_cost=float(pos.avg_cost),
                        shares_available=pos.shares_available - shares, commit=False)
                account.cash_available = float(account.cash_available) + (
                    trade_amount - commission - stamp_duty - transfer_fee)

            account.position_value = position_value + (
                trade_amount if action == 'buy' else -trade_amount)
            account.total_value = (
                float(account.cash_available) + float(account.cash_frozen)
                + float(account.position_value))
            if account.initial_capital:
                account.cumulative_return = (
                    float(account.total_value) / float(account.initial_capital) - 1)
            if account.peak_value and float(account.total_value) > float(account.peak_value):
                account.peak_value = account.total_value

            self.repo.upsert_equity_snapshot(
                account_name,
                cash=float(account.cash_available) + float(account.cash_frozen),
                position_value=float(account.position_value),
                total_value=float(account.total_value),
                cumulative_return=float(account.cumulative_return or 0),
                drawdown=(float(account.total_value) / float(account.peak_value) - 1)
                if account.peak_value else 0.0,
                commit=False)

            self.repo.session.commit()
        except Exception as e:
            self.repo.session.rollback()
            logger.error(f'交易事务失败，已回滚: {e}', exc_info=True)
            raise TradingError(f'交易执行失败: {e}', 500)

        return {
            'order_id': order.id,
            'order_status': 'filled',
            'trade_id': trade_id,
            'symbol': symbol,
            'action': action,
            'shares': shares,
            'price': px,
            'amount': trade_amount,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'realized_pnl': realized_pnl,
            'realized_pnl_rate': realized_pnl_rate,
        }
```

注意：`repo.delete_position` 内部若自行 commit 需检查——该方法是独立 commit 的（现状如此），在事务中调用会破坏原子性。**实现时将 `delete_position` 增加 `commit: bool = True` 参数**，事务内传 `commit=False`（`self.session.delete(position)` 后不 commit）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add application/services/account_trading_service.py adapters/outbound/repositories/simulation_repository.py tests/test_multi_account_domain.py
git commit -m "feat: AccountTradingService 手工交易单事务（费用/T+1/风控/已实现盈亏/流水不变式）"
```

---

### Task 5: SimulationService + StrategyService 内部适配新模型

**Files:**
- Modify: `quantsys-v2/application/services/simulation_service.py`
- Modify: `quantsys-v2/application/services/strategy_service.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
class TestServiceLayer:
    """Task 5: 服务层适配"""

    def test_get_account_status_new_fields(self, repo):
        from application.services.simulation_service import SimulationService
        repo.create_account('test_acc_a', initial_capital=100000,
                            display_name='测试账户A', strategy_name='v13')
        svc = SimulationService()
        svc.repo = repo
        status = svc.get_account_status('test_acc_a')
        assert status['cash'] == 100000  # 兼容 key
        assert status['cash_available'] == 100000
        assert status['cash_frozen'] == 0
        assert status['initial_capital'] == 100000
        assert status['display_name'] == '测试账户A'
        assert status['strategy_name'] == 'v13'

    def test_list_accounts_via_service(self, repo):
        from application.services.simulation_service import SimulationService
        repo.create_account('test_acc_a', initial_capital=100000)
        svc = SimulationService()
        svc.repo = repo
        accounts = svc.list_accounts()
        names = {a['account_name'] for a in accounts}
        assert 'test_acc_a' in names

    def test_create_account_via_service_duplicate_rejected(self, repo):
        from application.services.simulation_service import SimulationService
        repo.create_account('test_acc_a', initial_capital=100000)
        svc = SimulationService()
        svc.repo = repo
        import pytest as _pt
        with _pt.raises(ValueError):
            svc.create_account('test_acc_a', 50000)

    def test_position_dict_t1_fields(self, repo):
        from application.services.simulation_service import SimulationService
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.upsert_position('test_acc_a', '600519', shares_total=100,
                             avg_cost=10.0, shares_available=0)
        svc = SimulationService()
        svc.repo = repo
        d = svc._position_to_dict(repo.get_position('test_acc_a', '600519'))
        assert d['shares'] == 100           # 兼容 key
        assert d['shares_available'] == 0
        assert d['avg_price'] == 10.0       # 兼容 key
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py::TestServiceLayer -x -q`
Expected: FAIL

- [ ] **Step 3: 实现**

`application/services/simulation_service.py`：

1. `get_account_status`：删除 `print(f"[DEBUG] ...")` 全部调试输出；返回 dict 改为：

```python
        return {
            'account_name': account_name,
            'display_name': getattr(account, 'display_name', None),
            'strategy_name': getattr(account, 'strategy_name', None),
            'status': getattr(account, 'status', 'active'),
            'cash': float(getattr(account, 'cash_available', 0) or 0),      # 兼容 key
            'cash_available': float(getattr(account, 'cash_available', 0) or 0),
            'cash_frozen': float(getattr(account, 'cash_frozen', 0) or 0),
            'position_value': float(getattr(account, 'position_value', 0) or 0),
            'initial_capital': float(getattr(account, 'initial_capital', 0) or 0),
            'total_value': float(getattr(account, 'total_value', 0) or 0),
            'cumulative_return': float(getattr(account, 'cumulative_return', 0) or 0),
            'last_rebalance_date': str(account.last_rebalance_date) if getattr(account, 'last_rebalance_date', None) else None,
            'positions_count': len(positions),
            'positions': [self._position_to_dict(p) for p in positions]
        }
```

2. `_position_to_dict` 改为：

```python
        return {
            'symbol': getattr(position, 'symbol', None),
            'shares': getattr(position, 'shares_total', None),          # 兼容 key
            'shares_total': getattr(position, 'shares_total', None),
            'shares_available': getattr(position, 'shares_available', None),
            'avg_price': float(getattr(position, 'avg_cost', 0) or 0),  # 兼容 key
            'avg_cost': float(getattr(position, 'avg_cost', 0) or 0),
            'current_price': float(getattr(position, 'current_price', 0) or 0) or None,
            'market_value': float(getattr(position, 'market_value', 0) or 0) or None,
            'profit': float(getattr(position, 'profit_total', 0) or 0) or None,  # 兼容 key
            'profit_total': float(getattr(position, 'profit_total', 0) or 0) or None,
            'profit_rate': float(getattr(position, 'profit_total_rate', 0) or 0) or None,
            'profit_today': float(getattr(position, 'profit_today', 0) or 0) or None,
        }
```

3. `_trade_to_dict` 返回 dict 追加：

```python
            'transfer_fee': float(getattr(trade, 'transfer_fee', 0) or 0),
            'realized_pnl': float(getattr(trade, 'realized_pnl', 0) or 0) if getattr(trade, 'realized_pnl', None) is not None else None,
            'realized_pnl_rate': float(getattr(trade, 'realized_pnl_rate', 0) or 0) if getattr(trade, 'realized_pnl_rate', None) is not None else None,
            'reason': getattr(trade, 'reason', None),
            'order_id': getattr(trade, 'order_id', None),
```

4. 新增方法：

```python
    def list_accounts(self) -> List[Dict]:
        """账户发现：所有 active 账户摘要"""
        return self.repo.list_account_summaries()

    def create_account(self, account_name: str, initial_capital: float,
                       display_name: Optional[str] = None,
                       strategy_name: Optional[str] = None) -> Dict:
        if not account_name or account_name == 'default':
            raise ValueError("账户名非法：禁止为空或 'default'")
        if self.repo.get_account(account_name):
            raise ValueError(f'账户已存在: {account_name}')
        account = self.repo.create_account(
            account_name, initial_capital=initial_capital,
            display_name=display_name, strategy_name=strategy_name)
        if not account:
            raise ValueError(f'开户失败: {account_name}')
        return account.to_dict()
```

5. `run_strategy` / `get_account_status` / `get_trades` 的 `account_name: str = 'default'` 默认值删除（必填）。

`application/services/strategy_service.py`：

- 第 131 行 `cash = float(account.cash)` → `cash = float(account.cash_available or 0)`
- 检查同文件其他 `account.cash` 引用一并改掉（返回 dict 的 `'cash'` key 保持不变）

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add application/services/simulation_service.py application/services/strategy_service.py tests/test_multi_account_domain.py
git commit -m "feat: 服务层适配新账户模型（兼容对外 key + 账户发现/开户服务）"
```

---

### Task 6: Simulation API 路由（新增端点 + 必填化）

**Files:**
- Modify: `quantsys-v2/adapters/inbound/api/routes/simulation.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
class TestSimulationAPI:
    """Task 6: 路由层"""

    @pytest.fixture()
    def client(self, repo):
        from flask import Flask
        from adapters.inbound.api.routes.simulation import simulation_bp, get_service
        app = Flask(__name__)
        app.register_blueprint(simulation_bp)
        svc = get_service()
        svc.repo = repo  # 复用测试库连接与清理
        return app.test_client()

    def test_list_accounts(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        resp = client.get('/api/simulation/accounts')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        names = {a['account_name'] for a in data['data']}
        assert 'test_acc_a' in names

    def test_create_account(self, client):
        resp = client.post('/api/simulation/accounts', json={
            'account_name': 'test_acc_b', 'display_name': '测试B',
            'initial_capital': 50000,
        })
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_create_account_rejects_default(self, client):
        resp = client.post('/api/simulation/accounts', json={
            'account_name': 'default', 'initial_capital': 50000,
        })
        assert resp.status_code == 400

    def test_manual_trade_buy(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        # 注入价格，避免依赖实时行情：走 amount/shares + price 参数
        resp = client.post('/api/simulation/accounts/test_acc_a/trade', json={
            'action': 'buy', 'symbol': '600519', 'shares': 100,
            'reason': '测试买入：API层验证完整链路', 'price': 10.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['order_status'] == 'filled'

    def test_trades_requires_account_name(self, client):
        resp = client.get('/api/simulation/trades')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'available_accounts' in data

    def test_performance_requires_account_name(self, client):
        resp = client.get('/api/simulation/performance')
        assert resp.status_code == 400

    def test_unknown_account_404_with_list(self, client):
        resp = client.get('/api/simulation/accounts/not_exist_acc')
        assert resp.status_code == 404
        data = resp.get_json()
        assert 'available_accounts' in data

    def test_trade_account_not_found(self, client):
        resp = client.post('/api/simulation/accounts/not_exist_acc/trade', json={
            'action': 'buy', 'symbol': '600519', 'shares': 100,
            'reason': '测试买入：账户不存在场景', 'price': 10.0,
        })
        assert resp.status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py::TestSimulationAPI -x -q`
Expected: FAIL（404 on /accounts 等）

- [ ] **Step 3: 实现路由**

`adapters/inbound/api/routes/simulation.py`，文件头部 import 后新增辅助函数与端点：

```python
def _available_accounts():
    try:
        return get_service().list_accounts()
    except Exception:
        return []


def _require_account_name(value):
    """校验 account_name，返回 (value, error_response_or_None)"""
    if not value:
        return None, (jsonify({
            'success': False,
            'error': 'account_name 为必填参数',
            'available_accounts': _available_accounts(),
        }), 400)
    return value, None


@simulation_bp.route('/accounts', methods=['GET'])
def list_accounts():
    """账户发现：所有 active 账户摘要"""
    try:
        return jsonify({'success': True, 'data': get_service().list_accounts()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@simulation_bp.route('/accounts', methods=['POST'])
def create_account():
    """开户: {account_name, display_name?, initial_capital, strategy_name?}"""
    try:
        data = request.get_json() or {}
        account_name = data.get('account_name')
        initial_capital = data.get('initial_capital')
        if not account_name:
            return jsonify({'success': False, 'error': 'account_name 为必填参数'}), 400
        if not initial_capital or float(initial_capital) <= 0:
            return jsonify({'success': False, 'error': 'initial_capital 必须为正数'}), 400
        account = get_service().create_account(
            account_name, float(initial_capital),
            display_name=data.get('display_name'),
            strategy_name=data.get('strategy_name'))
        return jsonify({'success': True, 'data': account})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@simulation_bp.route('/accounts/<account_name>/trade', methods=['POST'])
def manual_trade(account_name):
    """手工/代管交易: {action, symbol, shares|amount, price_limit?, reason, price?}"""
    from application.services.account_trading_service import (
        AccountTradingService, TradingError)
    try:
        data = request.get_json() or {}
        result = AccountTradingService().execute_trade(
            account_name=account_name,
            action=data.get('action'),
            symbol=data.get('symbol'),
            shares=data.get('shares'),
            amount=data.get('amount'),
            price_limit=data.get('price_limit'),
            reason=data.get('reason'),
            price=data.get('price'),  # 测试/回放场景可显式注入价格
        )
        return jsonify({'success': True, 'data': result})
    except TradingError as e:
        payload = {'success': False, 'error': str(e)}
        if e.status_code == 404:
            payload['available_accounts'] = _available_accounts()
        return jsonify(payload), e.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

路由注册顺序注意：Flask 中 `/accounts` 与 `/accounts/<account_name>` 不冲突，直接并列即可。

改造既有端点：

1. `get_account(account_name)`：`except ValueError` 分支的 404 响应体追加 `'available_accounts': _available_accounts()`。
2. `/trades`（约 115 行）：`account_name = request.args.get('account_name', 'default')` 改为：

```python
        account_name, err = _require_account_name(request.args.get('account_name'))
        if err:
            return err
```

3. `/performance`（约 219 行）：同样 `_require_account_name` 处理；并将函数体开头的反推 initial_capital 逻辑替换为：优先读快照表，快照为空回退原重放逻辑：

```python
        from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
        repo = SimulationORMRepository()
        account = repo.get_account(account_name)
        if not account:
            return jsonify({
                'success': False,
                'error': f'账户不存在: {account_name}',
                'available_accounts': _available_accounts(),
            }), 404

        snapshots = repo.get_equity_snapshots(account_name, limit=90)
        if snapshots:
            curve = [{
                'date': s.snapshot_date.isoformat(),
                'total_value': float(s.total_value or 0),
                'cash': float(s.cash or 0),
                'return': float(s.cumulative_return or 0),
                'drawdown': float(s.drawdown or 0),
            } for s in reversed(snapshots)]
            return jsonify({'success': True, 'data': {
                'equity_curve': curve,
                'initial_capital': float(account.initial_capital or 0),
                'current_value': float(account.total_value or 0),
                'cumulative_return': float(account.cumulative_return or 0),
                'max_drawdown': float(account.max_drawdown or 0),
            }})
        # fallback: 原重放逻辑（保留其下既有代码不变）
```

同时把 fallback 分支里 `initial_capital` 的反推改为 `float(account.initial_capital or 100000)`，删除 `print(f"DEBUG: ...")` 调试输出。
4. `/run`（约 63 行）：`account_name = data.get('account_name', 'default')` 改为：

```python
        account_name, err = _require_account_name(data.get('account_name'))
        if err:
            return err
```

5. `/execution-history`（约 166 行）：同样 `_require_account_name` 处理；并删除 `'strategy_id': strategy_id or 'v13'` 兜底——`strategy_id` 缺失时返回 400。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add adapters/inbound/api/routes/simulation.py tests/test_multi_account_domain.py
git commit -m "feat: 账户发现/开户/手工交易 API + account_name 必填化 + performance 读快照"
```

---

### Task 7: SimulationTrader 适配（策略交易链路）

**Files:**
- Modify: `quantsys-v2/live_trading/simulation_trader.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（追加）

背景：`SimulationTrader` 被 v13/v14/v15 策略链路使用。需适配列改名，并修复两处隔离缺陷：`_load_account_from_db` 中 `get_all_positions()` 未传账户名（实际查了 default 账户）；`_save_daily_snapshot` 写全局表 `quant.account_balance`（无 account_name，多账户互相覆盖）。

- [ ] **Step 1: 写失败测试**

```python
class TestTraderAdaptation:
    """Task 7: SimulationTrader 适配"""

    def test_snapshot_written_per_account(self, repo):
        """_save_daily_snapshot 必须写按账户隔离的新快照表"""
        from live_trading.simulation_trader import SimulationTrader
        trader = SimulationTrader.__new__(SimulationTrader)  # 跳过 __init__ 重活
        trader.repo = repo
        trader.cash = 80000.0
        trader.peak_value = 100000.0
        trader.portfolio = {}
        repo.create_account('test_acc_a', initial_capital=100000)
        trader._save_daily_snapshot(90000.0, -0.1, account_name='test_acc_a')
        snaps = repo.get_equity_snapshots('test_acc_a')
        assert len(snaps) == 1
        assert float(snaps[0].total_value) == 90000.0
        assert float(snaps[0].cash) == 80000.0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py::TestTraderAdaptation -x -q`
Expected: FAIL（`_save_daily_snapshot() got an unexpected keyword argument 'account_name'` 或断言失败）

- [ ] **Step 3: 修改 simulation_trader.py**

1. `_load_account_from_db`（约 128 行）：
   - `self.cash = float(account.cash)` → `self.cash = float(account.cash_available)`
   - dict 分支 `account['cash']` → `account['cash_available']`
   - `db_positions = self.repo.get_all_positions()` → `db_positions = self.repo.get_all_positions(self.account_name)`

2. `_save_account_to_db`（约 259 行）：
   - `self.repo.update_account(account_name=..., cash=self.cash, ...)` → `cash_available=self.cash`
   - `self.repo.upsert_position(account_name=..., symbol=..., shares=pos['shares'], avg_price=pos['avg_price'])` → `shares_total=pos['shares'], avg_cost=pos['avg_price'], shares_available=pos['shares']`
   - 末尾 `self._save_daily_snapshot(total_value, cumulative_return)` → `self._save_daily_snapshot(total_value, cumulative_return, account_name=self.account_name)`

3. `_save_daily_snapshot`（约 307 行）整体替换为：

```python
    def _save_daily_snapshot(self, total_value: float, cumulative_return: float,
                             account_name: str = None):
        """保存每日账户快照（按账户隔离，写 simulation_equity_snapshot）"""
        name = account_name or self.account_name
        position_value = max(total_value - self.cash, 0.0)
        drawdown = (total_value / self.peak_value - 1) if self.peak_value > 0 else 0.0
        self.repo.upsert_equity_snapshot(
            name,
            cash=self.cash,
            position_value=position_value,
            total_value=total_value,
            cumulative_return=cumulative_return,
            drawdown=drawdown,
        )
        logging.info(f"保存每日快照: {name}, 总资产=¥{total_value:,.2f}")
```

4. 全文检查其余 `account.cash`、`shares=`、`avg_price=` 残留调用并同步适配（`grep -n "\.cash\b\|avg_price=\|shares=" live_trading/simulation_trader.py`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add live_trading/simulation_trader.py tests/test_multi_account_domain.py
git commit -m "fix: SimulationTrader 适配新账户模型 + 快照按账户隔离（修复跨账户覆盖）"
```

---

### Task 8: orders.py `/api/portfolio/*` 切源到 simulation 体系

**Files:**
- Modify: `quantsys-v2/adapters/inbound/api/routes/orders.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（追加）

改造 `/api/portfolio/positions` 与 `/api/portfolio/summary` 两个端点：`account_name` 必填，数据源切到 `SimulationORMRepository`，响应 key 保持兼容。其余 portfolio 端点（history/holdings/allocation/equity-curve/positions/<symbol>）本次不改，保持现状（旧 `quant.accounts` 体系只读保留）。

- [ ] **Step 1: 写失败测试**

```python
class TestPortfolioEndpoints:
    """Task 8: /api/portfolio/* 切源"""

    @pytest.fixture()
    def client(self, repo):
        from flask import Flask
        from adapters.inbound.api.routes.orders import orders_bp
        app = Flask(__name__)
        app.register_blueprint(orders_bp)
        return app.test_client()

    def test_positions_requires_account_name(self, client):
        resp = client.get('/api/portfolio/positions')
        assert resp.status_code == 400
        assert 'available_accounts' in resp.get_json()

    def test_positions_from_simulation(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        repo.upsert_position('test_acc_a', '600519', shares_total=100,
                             avg_cost=10.0, shares_available=100)
        resp = client.get('/api/portfolio/positions?account_name=test_acc_a')
        assert resp.status_code == 200
        data = resp.get_json()
        positions = data['data']['positions'] if 'data' in data else data['positions']
        assert len(positions) == 1
        assert positions[0]['symbol'] == '600519'
        assert positions[0]['quantity'] == 100
        assert positions[0]['avg_cost'] == 10.0

    def test_summary_from_simulation(self, client, repo):
        repo.create_account('test_acc_a', initial_capital=100000)
        resp = client.get('/api/portfolio/summary?account_name=test_acc_a')
        assert resp.status_code == 200
        data = resp.get_json()
        summary = data['data'] if 'data' in data else data
        assert summary['cash'] == 100000.0
        assert summary['positions'] == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py::TestPortfolioEndpoints -x -q`
Expected: FAIL（当前实现不读 account_name / 查旧表）

- [ ] **Step 3: 实现**

`adapters/inbound/api/routes/orders.py` 顶部附近新增：

```python
def _portfolio_account_or_error():
    """从 query string 取必填 account_name 并校验存在性"""
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    account_name = request.args.get('account_name')
    repo = SimulationORMRepository()
    if not account_name:
        return None, None, (jsonify({
            'success': False,
            'error': 'account_name 为必填参数',
            'available_accounts': repo.list_account_summaries(),
        }), 400)
    account = repo.get_account(account_name)
    if not account:
        return None, None, (jsonify({
            'success': False,
            'error': f'账户不存在: {account_name}',
            'available_accounts': repo.list_account_summaries(),
        }), 404)
    return account_name, repo, None
```

`get_portfolio_positions`（276 行起）整体替换为：

```python
@orders_bp.route('/api/portfolio/positions', methods=['GET'])
@handle_api_error
def get_portfolio_positions():
    """获取持仓列表（simulation 体系，account_name 必填）"""
    account_name, repo, err = _portfolio_account_or_error()
    if err:
        return err

    positions = []
    for p in repo.get_all_positions(account_name):
        cost_basis = float(p.avg_cost or 0)
        quantity = int(p.shares_total or 0)
        current_price = float(p.current_price or 0) or cost_basis
        total_invested = cost_basis * quantity
        current_value = float(p.market_value or 0) or quantity * current_price
        profit_loss = current_value - total_invested
        positions.append({
            'symbol': p.symbol,
            'name': '',
            'quantity': quantity,
            'avg_cost': cost_basis,
            'current_price': current_price,
            'total_cost': total_invested,
            'current_value': current_value,
            'profit_loss': profit_loss,
            'profit_loss_pct': (profit_loss / total_invested * 100) if total_invested > 0 else 0,
            'market': '',
            'sector': '',
            'updated_at': p.updated_at.isoformat() if p.updated_at else None,
        })

    return api_response({'positions': positions, 'count': len(positions)})
```

`get_portfolio_summary`（353 行起）整体替换为：

```python
@orders_bp.route('/api/portfolio/summary', methods=['GET'])
@handle_api_error
def get_portfolio_summary():
    """组合汇总（simulation 体系，account_name 必填）"""
    account_name, repo, err = _portfolio_account_or_error()
    if err:
        return err

    account = repo.get_account(account_name)
    positions = repo.get_all_positions(account_name)
    total_cost = sum(float(p.avg_cost or 0) * int(p.shares_total or 0) for p in positions)
    market_value = sum(
        float(p.market_value or 0) or int(p.shares_total or 0) * float(p.current_price or p.avg_cost or 0)
        for p in positions)
    profit_count = sum(1 for p in positions if float(p.profit_total or 0) > 0)
    loss_count = sum(1 for p in positions if float(p.profit_total or 0) < 0)
    available_cash = float(account.cash_available or 0)
    unrealized_pnl = market_value - total_cost
    total_assets = available_cash + float(account.cash_frozen or 0) + market_value

    return api_response({
        'totalValue': total_assets,
        'totalCost': total_cost,
        'totalMarketValue': market_value,
        'totalPnl': unrealized_pnl,
        'totalPnlPct': round(unrealized_pnl / total_cost * 100, 2) if total_cost > 0 else 0.0,
        'dailyChange': 0.0,
        'positions': len(positions),
        'cash': available_cash,
        'liquidAssets': available_cash,
        'profitCount': profit_count,
        'lossCount': loss_count,
        'lastUpdated': account.updated_at.isoformat() if account.updated_at else None,
    })
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add adapters/inbound/api/routes/orders.py tests/test_multi_account_domain.py
git commit -m "feat: /api/portfolio/positions+summary 切源 simulation 体系（account_name 必填）"
```

---

### Task 9: 策略账户启动校验

**Files:**
- Modify: `quantsys-v2/application/services/strategy_service.py`
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
class TestStrategyAccountValidation:
    """Task 9: 策略配置账户存在性校验"""

    def test_validate_strategy_accounts(self, repo):
        from application.services.strategy_service import StrategyService
        svc = StrategyService.__new__(StrategyService)
        svc.repo = repo
        repo.create_account('test_acc_a', initial_capital=100000)
        warnings = svc.validate_strategy_accounts({
            'v13': {'strategy': {'account_name': 'test_acc_a'}},
            'vX': {'strategy': {'account_name': 'not_exist_acc'}},
        })
        assert warnings == ['vX']  # 只有账户缺失的策略被告警
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py::TestStrategyAccountValidation -x -q`
Expected: FAIL（方法不存在）

- [ ] **Step 3: 实现**

`application/services/strategy_service.py` 的 `StrategyService` 新增：

```python
    def validate_strategy_accounts(self, configs: Dict[str, Dict]) -> List[str]:
        """校验策略配置的 account_name 是否存在于注册表

        Returns:
            List[str]: 账户缺失的策略名列表（调用方据此禁用并告警）
        """
        missing = []
        for name, config in configs.items():
            account_name = (config or {}).get('strategy', {}).get('account_name')
            if account_name and not self.repo.get_account(account_name):
                logger.error(f"策略 {name} 配置的账户不存在: {account_name}，该策略禁用")
                missing.append(name)
        return missing
```

并在 `__init__` 末尾调用（configs 来源为该服务现有的策略配置加载逻辑）：

```python
        missing = self.validate_strategy_accounts(self._load_all_strategy_configs())
        self._disabled_strategies = missing
```

若 `StrategyService` 当前没有集中加载全部配置的方法，则只在 `get_account_info` / `manual_rebalance` 入口已有的 `ValueError(f"账户不存在...")` 之上保留运行时校验即可，`__init__` 调用可省略——以实现时代码现状为准，但必须保留 `validate_strategy_accounts` 方法供启动任务调用。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && python -m pytest tests/test_multi_account_domain.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add application/services/strategy_service.py tests/test_multi_account_domain.py
git commit -m "feat: 策略账户启动校验（账户缺失则告警禁用）"
```

---

### Task 10: FastAPI parity

**Files:**
- Create: `quantsys-v2/adapters/inbound/fastapi_app/routes/simulation_async.py`
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/main.py`

- [ ] **Step 1: 实现 FastAPI 路由**

创建 `adapters/inbound/fastapi_app/routes/simulation_async.py`：

```python
"""模拟交易账户 API（FastAPI 版，与 Flask simulation.py 契约一致）"""
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from application.services.simulation_service import SimulationService
from application.services.account_trading_service import (
    AccountTradingService, TradingError,
)

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])
_service = SimulationService()


def _err(message: str, status_code: int, with_accounts: bool = False):
    payload = {"success": False, "error": message}
    if with_accounts:
        try:
            payload["available_accounts"] = _service.list_accounts()
        except Exception:
            payload["available_accounts"] = []
    return JSONResponse(payload, status_code=status_code)


@router.get("/accounts")
async def list_accounts():
    return {"success": True, "data": _service.list_accounts()}


@router.post("/accounts")
async def create_account(data: dict = Body(...)):
    account_name = data.get("account_name")
    initial_capital = data.get("initial_capital")
    if not account_name:
        return _err("account_name 为必填参数", 400)
    if not initial_capital or float(initial_capital) <= 0:
        return _err("initial_capital 必须为正数", 400)
    try:
        account = _service.create_account(
            account_name, float(initial_capital),
            display_name=data.get("display_name"),
            strategy_name=data.get("strategy_name"))
        return {"success": True, "data": account}
    except ValueError as e:
        return _err(str(e), 400)


@router.get("/accounts/{account_name}")
async def get_account(account_name: str):
    try:
        return {"success": True, "data": _service.get_account_status(account_name)}
    except ValueError as e:
        return _err(str(e), 404, with_accounts=True)


@router.post("/accounts/{account_name}/trade")
async def manual_trade(account_name: str, data: dict = Body(...)):
    try:
        result = AccountTradingService().execute_trade(
            account_name=account_name,
            action=data.get("action"),
            symbol=data.get("symbol"),
            shares=data.get("shares"),
            amount=data.get("amount"),
            price_limit=data.get("price_limit"),
            reason=data.get("reason"),
            price=data.get("price"),
        )
        return {"success": True, "data": result}
    except TradingError as e:
        return _err(str(e), e.status_code, with_accounts=(e.status_code == 404))


@router.get("/trades")
async def get_trades(account_name: str = Query(None), limit: int = Query(100)):
    if not account_name:
        return _err("account_name 为必填参数", 400, with_accounts=True)
    return {"success": True, "data": _service.get_trades(account_name, limit=limit)}


@router.get("/performance")
async def get_performance(account_name: str = Query(None)):
    if not account_name:
        return _err("account_name 为必填参数", 400, with_accounts=True)
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    repo = SimulationORMRepository()
    account = repo.get_account(account_name)
    if not account:
        return _err(f"账户不存在: {account_name}", 404, with_accounts=True)
    snapshots = repo.get_equity_snapshots(account_name, limit=90)
    curve = [{
        "date": s.snapshot_date.isoformat(),
        "total_value": float(s.total_value or 0),
        "cash": float(s.cash or 0),
        "return": float(s.cumulative_return or 0),
        "drawdown": float(s.drawdown or 0),
    } for s in reversed(snapshots)]
    return {"success": True, "data": {
        "equity_curve": curve,
        "initial_capital": float(account.initial_capital or 0),
        "current_value": float(account.total_value or 0),
        "cumulative_return": float(account.cumulative_return or 0),
        "max_drawdown": float(account.max_drawdown or 0),
    }}
```

在 `adapters/inbound/fastapi_app/main.py` 中注册（仿照现有 router 注册方式）：

```python
from adapters.inbound.fastapi_app.routes.simulation_async import router as simulation_async_router
app.include_router(simulation_async_router)
```

- [ ] **Step 2: 启动 FastAPI 手动验证**

```bash
cd quantsys-v2 && python adapters/inbound/fastapi_app/main.py &
sleep 3
curl -s http://127.0.0.1:5001/api/simulation/accounts | python -m json.tool | head -20
curl -s "http://127.0.0.1:5001/api/simulation/trades" | python -m json.tool  # 期望 400 + available_accounts
kill %1
```

注意：验证时若 5001 被 Flask 占用，先停 Flask 或改端口验证。

- [ ] **Step 3: Commit**

```bash
cd quantsys-v2
git add adapters/inbound/fastapi_app/routes/simulation_async.py adapters/inbound/fastapi_app/main.py
git commit -m "feat: FastAPI 模拟账户路由 parity"
```

---

### Task 11: 生产迁移 + 端到端验证

**Files:**
- Create: `quantsys-v2/scripts/verify_multi_account_e2e.py`

- [ ] **Step 1: 写 e2e 验证脚本**

创建 `scripts/verify_multi_account_e2e.py`：

```python
#!/usr/bin/env python3
"""多账户域端到端验证（对运行中的 Flask 5001）"""
import sys
import requests

BASE = "http://127.0.0.1:5001/api/simulation"
ACC = "e2e_verify_acc"
failures = []


def check(name, cond, detail=""):
    status = "✅" if cond else "❌"
    print(f"{status} {name} {detail}")
    if not cond:
        failures.append(name)


# 1. 账户发现
r = requests.get(f"{BASE}/accounts").json()
check("账户发现", r.get("success") is True)
names = {a["account_name"] for a in r.get("data", [])}
check("v13_simulation 存在", "v13_simulation" in names, str(names))
check("v14_simulation 存在", "v14_simulation" in names)
check("v15_simulation 存在", "v15_simulation" in names)
check("default 已消除", "default" not in names)

# 2. 开户
requests.post(f"{BASE}/accounts", json={
    "account_name": ACC, "display_name": "E2E验证", "initial_capital": 100000})
r = requests.get(f"{BASE}/accounts/{ACC}").json()
check("开户", r.get("success") is True and r["data"]["cash_available"] == 100000)

# 3. 买入（注入价格，离线可跑）
r = requests.post(f"{BASE}/accounts/{ACC}/trade", json={
    "action": "buy", "symbol": "600519", "shares": 100,
    "reason": "E2E验证买入：完整链路检查", "price": 10.0}).json()
check("买入成交", r.get("success") is True, str(r.get("error", "")))

# 4. T+1 拦截
r = requests.post(f"{BASE}/accounts/{ACC}/trade", json={
    "action": "sell", "symbol": "600519", "shares": 100,
    "reason": "E2E验证卖出：T+1应拦截", "price": 11.0})
check("T+1 拦截", r.status_code == 422, f"got {r.status_code}")

# 5. 缺 account_name 400 + 账户列表
r = requests.get(f"{BASE}/trades")
check("缺 account_name 400", r.status_code == 400 and "available_accounts" in r.json())

# 6. 绩效（快照）
r = requests.get(f"{BASE}/performance?account_name={ACC}").json()
check("绩效快照", r.get("success") is True and len(r["data"]["equity_curve"]) >= 1)

# 7. 隔离：v14 数据不受 e2e 账户影响
r13 = requests.get(f"{BASE}/accounts/v13_simulation").json()
r14 = requests.get(f"{BASE}/accounts/v14_simulation").json()
check("账户隔离", r13["data"]["cash"] != r14["data"]["cash"] or
      r13["data"]["account_name"] != r14["data"]["account_name"])

print()
if failures:
    print(f"❌ {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("✅ 全部通过")
```

- [ ] **Step 2: 生产库执行迁移**

```bash
cd quantsys-v2
PGDATABASE=quant_investment python scripts/migrate_20260720_multi_account.py
# 再跑一次验证幂等
PGDATABASE=quant_investment python scripts/migrate_20260720_multi_account.py
```

Expected: 两次均输出 `[迁移] 多账户域迁移完成`，第二次无报错。

- [ ] **Step 3: 启动 Flask 并跑 e2e**

```bash
cd quantsys-v2 && python adapters/inbound/api/server.py &
sleep 5
python scripts/verify_multi_account_e2e.py
kill %1
```

Expected: `✅ 全部通过`

- [ ] **Step 4: 全量回归**

```bash
cd quantsys-v2 && python -m pytest tests/ -q
```

Expected: 无新增失败（既有失败若存在需逐个确认与本改动无关）

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add scripts/verify_multi_account_e2e.py
git commit -m "test: 多账户域端到端验证脚本"
```

---

## 后续计划（不在本文件范围）

- **计划 2：agent-ts** —— QuantV2Client 扩展（listAccounts/getAccount/executeTrade 等）、portfolio_trade 修复断链改走 `/api/simulation/accounts/<name>/trade`、portfolio_status/analyze 增加 account 参数、新增 portfolio_account 工具
- **计划 3：web-frontend** —— SimulationTrading 改统一账户页 + 切换器 + 开户对话框、V14Trading 页下线重定向
