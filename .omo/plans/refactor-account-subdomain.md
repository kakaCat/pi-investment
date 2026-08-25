# 重构计划：账户子域（account）— 首个子域切片

> 状态：待执行（规划产物，不实现代码）
> 执行方式：独立 worktree 分支 `refactor/account`，验证通过后合并回 `main`
> 所属程序：quantsys-v2 重构程序（阶段 2 的首个切片，验证"逐包重构"模式）

## 0. 目标与原则

- 把"投资账户"相关逻辑从扁平的 `application/services/` 抽成**独立限界上下文包** `application/services/account/`。
- **纯机械搬移 + 接线 + 端口提取**，不改业务行为；行为保持与现状一致。
- 遵守两条铁律：
  1. `account` 包只依赖 `domain/ports` 与自身端口，**不**直接依赖其他应用服务、不直接 import ORM 模型。
  2. `account/__init__.py` 不做急切重导入（沿用 `application/services/__init__.py` 的 segfault 纪律：调用方显式 `from application.services.account.trading_service import AccountTradingService`）。

## 1. 现状（已核实）

- `application/services/account_trading_service.py`（427 行）：`AccountTradingService`、`TradingError`。
  - 依赖：`domain.ports.ISimulationRepository`（端口，OK）。
  - 反模式：懒导入 `application.services.trading_calendar_service`、`application.services.realtime_quote_service`（跨服务耦合）；被 `docs/domain-boundary-audit-2026-08.md` 点名"直接 import ORM 模型"。
- `application/services/performance_tracker.py`：`PerformanceTracker`（`_account_summary`/`_position_summary`/`_performance_metrics`/`_calculate_max_drawdown`/`_strategy_attribution`），`get_performance_tracker(account_name='rotation_main')`。
- `simulation_service.py` 含账户方法（`get_account_status`/`_position_to_dict`/`_trade_to_dict`），但同文件又有 `run_strategy`（属 strategy 域）→ **本期不搬 simulation_service**，仅记录后续路由。
- 引用点（需改写 import 路径，共 33 处 / 15 文件）：
  - 生产：`application/services/evolution/daily_snapshot_service.py`、`application/services/daily_orchestrator.py`、`infrastructure/services/service_factory.py`（`get_account_trading_service`）、`adapters/shared/services.py`（`get_account_trading_service` + property）、`adapters/inbound/fastapi_app/routes/simulation_async.py`
  - 测试：`tests/services/test_trade_auto_record.py`、`tests/services/test_pending_orders.py`、`tests/test_trade_cash_race.py`、`tests/test_account_daily_limits.py`、`tests/test_trading_window_guard.py`、`tests/test_multi_account_domain.py`、`tests/test_simulation_trade_route.py`、`tests/api/test_simulation_trade_route.py`

## 2. 范围（本切片搬哪些）

| 源文件 | 目标位置 | 说明 |
|--------|---------|------|
| `account_trading_service.py` | `application/services/account/trading_service.py` | 交易执行/限额/交易时段护栏 |
| `performance_tracker.py` | `application/services/account/performance_service.py` | 账户业绩/回撤/归因 |

**不搬（本期）**：`simulation_service.py`（`run_strategy` 属 strategy 域，需后续切片路由其账户方法）、`position_repository`/`portfolio_repository`/`simulation_repository`（属 outbound 适配层，不动）、`live_trading/*`（顶层脚本，不在 application/services）。

## 3. 实现内容（要落地的代码）

1. **新建包** `application/services/account/`：
   - `__init__.py`：仅放 `__all__` 与惰性访问说明，**不**急切 import 重型 service（segfault 纪律）。
   - `trading_service.py`：原 `account_trading_service.py` 内容；类改名保持 `AccountTradingService`/`TradingError`（公开名不变，避免外部破坏）。
   - `performance_service.py`：原 `performance_tracker.py` 内容；`PerformanceTracker`/`get_performance_tracker` 公开名不变。
   - `ports.py`：定义账户域对外端口（见下）。
2. **端口提取（本切片关键实现，体现 BC 价值）**：
   - 行情：**复用已有 `IQuoteProvider`**（`domain/ports/datasource_ports.py:21`，`get_quote(symbol)`）替代对 `realtime_quote_service` 的懒导入——**不另造 `IRealtimeQuotePort`**（核实后已有端口可直接复用）。
   - **新增 `ITradingCalendarPort`**（替代对 `trading_calendar_service` 的懒导入）：`is_trading_day(date)->bool`——该端口目前不存在，需新增。
   - 端口定义放 `application/services/account/ports.py`；`ITradingCalendarPort` 实现由 `infrastructure` 提供（包装现有 `TradingCalendarService`）。`AccountTradingService.__init__` 改为接收这两个端口（保留 `now_fn`/`calendar=None` 兜底以兼容现有测试）。
3. **修复越层**：`trading_service.py` 删除对 ORM 模型的任何直接 import，统一经 `ISimulationRepository` 端口读写账户/持仓/流水。
4. **DI 接线**：
   - `infrastructure/services/service_factory.py`：`get_account_trading_service` 改为 `from application.services.account.trading_service import ...`；新增 `get_performance_tracker`。
   - `adapters/shared/services.py`：`get_account_trading_service` 与 `account_trading_service` property 指向新路径；新增 `performance_tracker` 访问器。
   - 若 `config/services.yaml` 列出这两个 service，更新模块路径。
5. **引用改写**：上述 15 个文件的所有 `application.services.account_trading_service` / `application.services.performance_tracker` import 改为新路径；测试 import 同步改。

## 4. 验收（F 门 + 账户专项）

- **F1 导入解析**：`python -c "from application.services.account.trading_service import AccountTradingService; from application.services.account.performance_service import PerformanceTracker"` 成功，无 segfault。
- **F2 端口可实例化**：`AccountTradingService(repo=FakeRepo, calendar=FakeCal, now_fn=...)` 在测试中可构造（不触真实网络/模型加载）。
- **F3 引用清零**：`grep -rn "application.services.account_trading_service\|application.services.performance_tracker" quantsys-v2 --include=*.py` → **0 命中**（仅历史文档可保留，但代码 0）。
- **F4 DI 接通**：`ServiceFactory.get_account_trading_service()` 与 `adapters/shared/services.get_account_trading_service()` 返回实例；`get_performance_tracker('rotation_main')` 返回实例。
- **F5 测试全绿**：
  `pytest tests/test_account_daily_limits.py tests/test_trading_window_guard.py tests/test_trade_cash_race.py tests/test_trade_auto_record.py tests/test_pending_orders.py tests/test_multi_account_domain.py tests/test_simulation_trade_route.py tests/services/test_trade_auto_record.py tests/services/test_pending_orders.py tests/api/test_simulation_trade_route.py -q` → 全过。
- **F6 无新增越层**：`account` 包内 `grep -rn "import ORM\|from infrastructure.persistence.orm" application/services/account` → 0；`account` 不 import 其他 `application.services.*`（仅经 `ports`）。
- **F7 路由冒烟**：`python -c "import adapters.inbound.fastapi_app.routes.simulation_async"` 成功；`python start_all.py` 能起（或至少 API 模块 import 全解析）。

## 5. Worktree 执行步骤（worker 遵循）

```bash
# 在 quantsys-v2 仓库内
git worktree add .claude/worktrees/account -b refactor/account
cd .claude/worktrees/account
source ../../activate-py313.sh        # 或 venv/bin/activate
# 1. 建 application/services/account/ 包（__init__/ports/trading_service/performance_service）
# 2. 移文件、提取端口、去 ORM 直导
# 3. 改 DI（service_factory / shared/services / services.yaml）
# 4. 全量改写 15 处引用 + 测试 import
# 5. 跑 F1–F7
# 6. git status 只含本切片文件 → commit → 合并回 main → 推 GitHub
```

- 合并前 `git status` 必须**只**出现本切片相关文件；出现无关改动 = 停手。
- 禁止在脏工作区批量覆盖（`git checkout -- .` / `git restore --source=... .`）。

## 6. 风险与回滚

- 风险：引用改写漏改导致 import 失败 → F3 全量 grep 兜底。
- 风险：端口抽取改了 `AccountTradingService` 构造签名 → 保留 `calendar=None`/`now_fn=None` 兜底，F2 用 fake 验证。
- 回滚：worktree 未合并即丢弃 `git worktree remove .claude/worktrees/account --force`，主分支不受影响。

## 7. 对 18 子域分类的修正

- 原 18 子域漏了 `account`。本切片后，应用层子域数变 **19**：新增 `account`（与 `execution` 区分：`execution`=券商下单路由；`account`=系统内账户状态/限额/业绩）。
- 后续切片顺序建议：account（本切片）→ 其余低风险包（core/data/market）→ 高依赖包（execution/integration）。
