# 统一 v13/v14 策略每日检查实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 修复并启用 StrategyService 统一架构，让 v13/v14 的止损/调仓真正按各自配置运行，新策略纯配置化接入。

**Architecture:** 调度任务 → `strategy_trading_job.py`（薄壳）→ `StrategyService.daily_check(strategy_name)` → 配置驱动的 `SimulationTrader`（正确账户/模型/因子计算器/风控）。设计文档：`quantsys-v2/docs/superpowers/specs/2026-07-28-unified-strategy-daily-check-design.md`

**Tech Stack:** Python 3.13, pytest（mock 风格，参照 `tests/test_orchestrator_account_unify.py`）, SQLAlchemy ORM, XGBoost, APScheduler

**工作目录：** 所有路径相对 `quantsys-v2/`。运行 pytest 用 `venv/bin/python -m pytest`（测试自动切 quant_test 库）。

---

### Task 1: SimulationTrader 构造函数参数化（account_name + factor_calculator）

**Files:**
- Modify: `live_trading/simulation_trader.py:58-95`（`__init__`）
- Test: `tests/test_strategy_service_unified.py`（新建）

- [x] **Step 1: 写失败测试**

创建 `tests/test_strategy_service_unified.py`：

```python
"""统一策略每日检查架构测试（StrategyService + SimulationTrader 参数化）"""
from unittest.mock import patch, MagicMock

import pytest


def _make_trader(**kwargs):
    """在 mock 重依赖的前提下构造 SimulationTrader"""
    with patch('live_trading.simulation_trader.DataService'), \
         patch('live_trading.simulation_trader.get_engine', return_value=MagicMock()), \
         patch('live_trading.simulation_trader.SimulationORMRepository') as MockRepo, \
         patch('live_trading.simulation_trader.create_notifier_from_config', return_value=None):
        MockRepo.return_value.get_account.return_value = None
        from live_trading.simulation_trader import SimulationTrader
        trader = SimulationTrader(**kwargs)
    return trader, MockRepo


def test_account_name_injected_before_load():
    """account_name 必须在账户加载前生效（回归：此前硬编码 default 导致止损跳过）"""
    trader, MockRepo = _make_trader(account_name='v14_simulation')
    assert trader.account_name == 'v14_simulation'
    MockRepo.return_value.get_account.assert_called_once_with('v14_simulation')


def test_account_name_default_compatible():
    """不传 account_name 时保持 default（向后兼容）"""
    trader, MockRepo = _make_trader()
    assert trader.account_name == 'default'
    MockRepo.return_value.get_account.assert_called_once_with('default')


def test_factor_calculator_v14():
    """factor_calculator='v14' 时使用 V14FactorCalculator"""
    from live_trading.v14_factor_calculator import V14FactorCalculator
    trader, _ = _make_trader(factor_calculator='v14')
    assert isinstance(trader.factor_calc, V14FactorCalculator)


def test_factor_calculator_default_v13():
    """默认使用 V13FactorCalculator（保持现状）"""
    from live_trading.factor_calculator import V13FactorCalculator
    trader, _ = _make_trader()
    assert isinstance(trader.factor_calc, V13FactorCalculator)


def test_factor_calculator_unknown_raises():
    """未知的因子计算器键名应报错"""
    with pytest.raises(ValueError, match='factor_calculator'):
        _make_trader(factor_calculator='v99')
```

- [x] **Step 2: 运行测试确认失败**

Run: `cd quantsys-v2 && venv/bin/python -m pytest tests/test_strategy_service_unified.py -v`
Expected: FAIL — `TypeError: SimulationTrader.__init__() got an unexpected keyword argument 'account_name'`

- [x] **Step 3: 实现**

修改 `live_trading/simulation_trader.py`：

a) 在文件头部 import 区（第 36 行附近）后加注册表：

```python
from live_trading.factor_calculator import V13FactorCalculator
from live_trading.v14_factor_calculator import V14FactorCalculator

# 因子计算器注册表：新策略引入全新因子体系时在此注册一行
FACTOR_CALCULATORS = {
    'v13': V13FactorCalculator,
    'v14': V14FactorCalculator,
}
```

b) 修改 `__init__` 签名与账户/因子计算器赋值（约 58-95 行）：

```python
    def __init__(self, config_path='live_trading/config_simulation.yaml',
                 account_name='default', factor_calculator='v13'):
        """初始化

        Args:
            config_path: 交易参数配置文件路径
            account_name: 数据库账户名（必须在 _load_account_from_db 之前确定）
            factor_calculator: 因子计算器，FACTOR_CALCULATORS 注册表键名或实例
        """
        self.config = self._load_config(config_path)
        self.ds = DataService()

        # 因子计算器：注册表键名或直接传实例
        if isinstance(factor_calculator, str):
            if factor_calculator not in FACTOR_CALCULATORS:
                raise ValueError(
                    f"未知 factor_calculator: {factor_calculator}，"
                    f"可用: {sorted(FACTOR_CALCULATORS)}"
                )
            self.factor_calc = FACTOR_CALCULATORS[factor_calculator]()
        else:
            self.factor_calc = factor_calculator

        self.broker = SimulationBroker(
            commission_rate=self.config['trading']['commission_rate'],
            slippage_rate=self.config['trading']['slippage_rate']
        )

        # 初始化 SQLAlchemy Engine(如果未初始化)
        try:
            get_engine()
        except RuntimeError:
            init_engine(pool_size=5, max_overflow=10)

        # 让 Repository 自己从 Engine 池获取连接
        self.repo = SimulationORMRepository()

        self.model = None
        self.valid_factors = None

        # 模型文件路径（load_model 读取，可在构造后由调用方覆盖）
        base_dir = Path(__file__).parent
        self.model_path = str(base_dir / 'models' / 'v13_model.json')
        self.factors_path = str(base_dir / 'models' / 'valid_factors.json')

        # 账户名称（必须在 _load_account_from_db 之前赋值）
        self.account_name = account_name

        # 初始化风险控制
        self.risk_controller = RiskController(self.config['risk_control'])
        # ... 其余保持不变（feishu、_setup_logging、_load_account_from_db）
```

注意：删除原来的 `self.factor_calc = V13FactorCalculator()`（62 行）和 `self.account_name = 'default'`（81 行）两处旧赋值。

- [x] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/test_strategy_service_unified.py -v`
Expected: 5 个测试全 PASS

- [x] **Step 5: Commit**

```bash
git add quantsys-v2/live_trading/simulation_trader.py quantsys-v2/tests/test_strategy_service_unified.py
git commit -m "feat(quantsys-v2): SimulationTrader 构造函数参数化 account_name 与 factor_calculator

修复账户注入时机 bug：此前硬编码 default 导致 v13/v14 每日检查
操作空仓 default 账户，止损被整体跳过。"
```

---

### Task 2: load_model 改用实例属性

**Files:**
- Modify: `live_trading/simulation_trader.py:637-655`（`load_model`）
- Test: `tests/test_strategy_service_unified.py`（追加）

- [x] **Step 1: 写失败测试**

追加到 `tests/test_strategy_service_unified.py`：

```python
def test_load_model_uses_instance_paths(tmp_path):
    """load_model 必须读 self.model_path/self.factors_path（回归：此前硬编码 v13 模型）"""
    import json
    import xgboost as xgb
    from live_trading.simulation_trader import SimulationTrader

    # 构造一个可加载的临时模型与因子文件
    model_file = tmp_path / 'test_model.json'
    factors_file = tmp_path / 'test_factors.json'
    xgb.XGBRegressor(n_jobs=1).save_model(str(model_file))
    factors_file.write_text(json.dumps(['__test_factor_a__', '__test_factor_b__']))

    trader = object.__new__(SimulationTrader)
    trader.model = None
    trader.valid_factors = None
    trader.model_path = str(model_file)
    trader.factors_path = str(factors_file)
    trader.load_model()

    assert trader.valid_factors == ['__test_factor_a__', '__test_factor_b__']
    assert trader.model is not None
```

- [x] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/test_strategy_service_unified.py::test_load_model_uses_instance_paths -v`
Expected: FAIL — 断言不成立（旧代码加载仓库默认的 75 因子文件而非临时文件）

- [x] **Step 3: 实现**

修改 `live_trading/simulation_trader.py` 的 `load_model`：

```python
    def load_model(self):
        """加载已训练的模型（路径来自 self.model_path / self.factors_path）"""
        model_file = Path(self.model_path)
        factors_file = Path(self.factors_path)

        if not model_file.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_file}")
        if not factors_file.exists():
            raise FileNotFoundError(f"因子文件不存在: {factors_file}")

        self.model = xgb.XGBRegressor(n_jobs=1)  # 使用单线程避免段错误
        self.model.load_model(str(model_file))

        with open(factors_file, 'r') as f:
            self.valid_factors = json.load(f)

        logging.info(f"模型加载完成: {len(self.valid_factors)}个因子 ({model_file.name})")
```

- [x] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/test_strategy_service_unified.py -v`
Expected: 全 PASS

- [x] **Step 5: Commit**

```bash
git add quantsys-v2/live_trading/simulation_trader.py quantsys-v2/tests/test_strategy_service_unified.py
git commit -m "fix(quantsys-v2): load_model 改用实例属性，v14 不再错载 v13 模型"
```

---

### Task 3: StrategyService._create_trader 修复 + 策略 yaml 补 factor_calculator

**Files:**
- Modify: `application/services/strategy_service.py:185-309`（`manual_rebalance`、`_create_trader`）
- Modify: `live_trading/configs/strategies/v13.yaml`、`live_trading/configs/strategies/v14.yaml`（model 节加一行）
- Test: `tests/test_strategy_service_unified.py`（追加）

- [x] **Step 1: 写失败测试**

追加：

```python
def test_create_trader_uses_strategy_config():
    """_create_trader 必须把账户/因子计算器注入构造函数，且风控/调仓参数真正生效"""
    from types import SimpleNamespace
    from application.services.strategy_service import StrategyService

    service = StrategyService.__new__(StrategyService)
    service._configs_cache = {}
    from pathlib import Path
    service.config_dir = Path('live_trading/configs/strategies')

    mock_trader = MagicMock()
    mock_trader.config = {'strategy': {'rebalance_days': 5}}
    mock_trader.risk_controller = SimpleNamespace(single_stop_loss=-0.10)

    with patch('application.services.strategy_service.SimulationTrader',
               return_value=mock_trader) as MockTrader:
        config = service.get_config('v14')
        trader = service._create_trader(config)

    # 账户与因子计算器通过构造函数注入（不是事后赋值）
    _, kwargs = MockTrader.call_args
    assert kwargs.get('account_name') == 'v14_simulation'
    assert kwargs.get('factor_calculator') == 'v14'

    # 调仓周期与止损阈值写入 trader 真正读取的位置
    assert trader.config['strategy']['rebalance_days'] == 7
    assert trader.risk_controller.single_stop_loss == -0.12

    # 模型路径按策略配置覆盖
    assert trader.model_path == 'live_trading/models/v14_p0_model.json'
    assert trader.factors_path == 'live_trading/models/v14_p0_valid_factors.json'
    trader.load_model.assert_called_once()


def test_manual_rebalance_passes_current_date():
    """manual_rebalance 必须传 current_date（回归：此前调用必 TypeError）"""
    from application.services.strategy_service import StrategyService

    service = StrategyService.__new__(StrategyService)
    service._configs_cache = {}
    from pathlib import Path
    service.config_dir = Path('live_trading/configs/strategies')

    mock_trader = MagicMock()
    mock_trader.account_name = 'v13_simulation'
    mock_trader.rebalance.return_value = {'success': True}

    with patch.object(service, '_create_trader', return_value=mock_trader), \
         patch.object(service, 'get_config', return_value={'strategy': {'account_name': 'v13_simulation'}}):
        result = service.manual_rebalance('v13')

    args, kwargs = mock_trader.rebalance.call_args
    current_date = kwargs.get('current_date') or (args[0] if args else None)
    assert current_date is not None  # 形如 '2026-07-28'
    assert result['status'] == 'success'
```

- [x] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/test_strategy_service_unified.py -k "create_trader or manual_rebalance" -v`
Expected: FAIL（构造调用无 kwargs；rebalance 缺 current_date）

- [x] **Step 3: 实现**

a) 修改 `application/services/strategy_service.py` 的 `_create_trader`：

```python
    def _create_trader(self, config: Dict, **kwargs) -> SimulationTrader:
        """
        创建配置驱动的交易器

        Args:
            config: 策略配置
            **kwargs: 可选覆盖参数（rebalance_days / stop_loss_pct 等）

        Returns:
            SimulationTrader: 配置好的交易器实例
        """
        # 账户与因子计算器必须在构造时注入（账户状态在 __init__ 内加载）
        trader = SimulationTrader(
            account_name=config['strategy']['account_name'],
            factor_calculator=config['model'].get('factor_calculator', 'v13'),
        )

        # 模型文件路径（load_model 读取实例属性）
        trader.model_path = config['model']['model_path']
        trader.factors_path = config['model']['factors_path']

        # 调仓周期：should_rebalance 读 config['strategy']['rebalance_days']
        trader.config['strategy']['rebalance_days'] = kwargs.get(
            'rebalance_days', config['trading']['rebalance_days'])

        # 止损阈值：check_single_stock_stop_loss 读 risk_controller.single_stop_loss
        if 'risk' in config:
            trader.risk_controller.single_stop_loss = kwargs.get(
                'stop_loss_pct', config['risk']['single_stock_stop_loss'])

        # 加载模型
        trader.load_model()

        logger.info(f"交易器已配置:")
        logger.info(f"  账户: {trader.account_name}")
        logger.info(f"  模型: {trader.model_path}")
        logger.info(f"  调仓周期: {trader.config['strategy']['rebalance_days']}天")
        logger.info(f"  单股止损: {trader.risk_controller.single_stop_loss:.0%}")

        return trader
```

b) 修改 `manual_rebalance` 中的调仓调用：

```python
        # 执行调仓
        result = trader.rebalance(current_date=datetime.now().strftime('%Y-%m-%d'))
```

c) `live_trading/configs/strategies/v13.yaml` 的 `model:` 节加一行：

```yaml
model:
  model_path: "live_trading/models/v13_model.json"
  factors_path: "live_trading/models/valid_factors.json"   # 修正：实际文件名是 valid_factors.json
  factor_calculator: v13
```

注意：v13.yaml 原 `factors_path` 写的是 `live_trading/models/v13_valid_factors.json`，该文件**不存在**，真实文件是 `valid_factors.json`，一并修正。

d) `live_trading/configs/strategies/v14.yaml` 的 `model:` 节加一行：

```yaml
  factor_calculator: v14
```

- [x] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/test_strategy_service_unified.py -v`
Expected: 全 PASS

- [x] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/strategy_service.py \
        quantsys-v2/live_trading/configs/strategies/v13.yaml \
        quantsys-v2/live_trading/configs/strategies/v14.yaml \
        quantsys-v2/tests/test_strategy_service_unified.py
git commit -m "fix(quantsys-v2): StrategyService 配置真正生效（账户/模型/因子/风控注入）"
```

---

### Task 4: 止损触发链路测试

**Files:**
- Test: `tests/test_strategy_service_unified.py`（追加）

- [x] **Step 1: 写测试（此任务为纯测试加固，应直接通过）**

追加：

```python
def _make_bare_trader(portfolio, stop_loss=-0.12):
    """绕过 __init__ 构造最小可用 trader 用于止损链路测试"""
    from live_trading.simulation_trader import SimulationTrader
    from live_trading.risk_control import RiskController

    trader = object.__new__(SimulationTrader)
    trader.model = MagicMock()
    trader.portfolio = portfolio
    trader.risk_controller = RiskController({'single_stock_stop_loss': stop_loss})
    trader.config = {'strategy': {'rebalance_days': 7}}
    trader.last_rebalance_date = '2026-07-20'
    trader._get_current_prices = MagicMock(
        return_value={s: p['current'] for s, p in portfolio.items()})
    trader._execute_stop_loss = MagicMock()
    trader._save_account_to_db = MagicMock()
    trader.should_rebalance = MagicMock(return_value=False)
    return trader


def test_stop_loss_triggers_below_threshold():
    """浮亏超过阈值 → 触发止损卖出（v14 场景：300162 成本13.12 现价6.88 = -47.6%）"""
    trader = _make_bare_trader({
        '300162': {'shares': 900, 'avg_price': 13.12, 'current': 6.88},
    })
    trader.run_daily_check()
    trader._execute_stop_loss.assert_called_once()
    symbols = trader._execute_stop_loss.call_args[0][0]
    assert symbols == ['300162']
    trader._save_account_to_db.assert_called_once()


def test_stop_loss_not_triggered_above_threshold():
    """浮亏未达阈值 → 不止损"""
    trader = _make_bare_trader({
        '300432': {'shares': 500, 'avg_price': 19.75, 'current': 18.50},  # -6.3%
    })
    trader.run_daily_check()
    trader._execute_stop_loss.assert_not_called()


def test_stop_loss_skipped_when_portfolio_empty():
    """空仓 → 不查价不止损（回归保护：default 空仓场景应静默跳过而非误操作）"""
    trader = _make_bare_trader({})
    trader.run_daily_check()
    trader._get_current_prices.assert_not_called()
    trader._execute_stop_loss.assert_not_called()
```

注意：`run_daily_check` 内 `if self.portfolio:` 为 False 时不会调用 `_get_current_prices`。

- [x] **Step 2: 运行测试**

Run: `venv/bin/python -m pytest tests/test_strategy_service_unified.py -v`
Expected: 全 PASS（若有 FAIL 说明 Task 1-3 改动破坏了 run_daily_check 链路，回查而非改测试）

- [x] **Step 3: Commit**

```bash
git add quantsys-v2/tests/test_strategy_service_unified.py
git commit -m "test(quantsys-v2): 止损触发链路回归测试（触发/未触发/空仓三态）"
```

---

### Task 5: 引用迁移到统一 job + 删除旧 job 文件

**Files:**
- Modify: `adapters/inbound/web/v14_api.py:10`
- Modify: `adapters/inbound/fastapi_app/routes/v14_trading.py:10`
- Modify: `adapters/inbound/api/routes/v14_trading.py:10`
- Modify: `infrastructure/scheduler/scheduler.py:1511`
- Modify: `register_v14_to_v2.py:44`
- Modify: `tests/test_v13_scheduler.py:29`、`tests/test_unified_scheduler_misfire.py:79-80`
- Modify: `domain/strategies/v14_strategy.py:88`（注释）
- Delete: `infrastructure/jobs/v13_trading_job.py`、`infrastructure/jobs/v14_trading_job.py`

- [x] **Step 1: 迁移所有 import/引用**

a) 三个 v14 路由文件（`adapters/inbound/web/v14_api.py`、`adapters/inbound/fastapi_app/routes/v14_trading.py`、`adapters/inbound/api/routes/v14_trading.py`）第 10 行统一改为：

```python
from infrastructure.jobs.strategy_trading_job import v14_daily_check, v14_manual_rebalance
```

b) `infrastructure/scheduler/scheduler.py` 约 1511 行，把：

```python
        from infrastructure.jobs.v13_trading_job import execute

        logger.info("Executing v13_daily_check command")
        return execute(**params)
```

改为：

```python
        from infrastructure.jobs.strategy_trading_job import v13_daily_check

        logger.info("Executing v13_daily_check command")
        return v13_daily_check(**params)
```

c) `register_v14_to_v2.py:44` 的 command 字符串改为 `'infrastructure.jobs.strategy_trading_job.v14_daily_check'`。

d) `tests/test_v13_scheduler.py:29` 改为：

```python
        from infrastructure.jobs.strategy_trading_job import v13_daily_check as execute
```

e) `tests/test_unified_scheduler_misfire.py:79-80` 两个 command 字符串改为：

```python
        'infrastructure.jobs.strategy_trading_job.v13_daily_check',
        'infrastructure.jobs.strategy_trading_job.v14_daily_check',
```

f) `domain/strategies/v14_strategy.py:88` 注释改为 `# 实际交易通过 strategy_trading_job（统一入口）执行`。

- [x] **Step 2: 删除旧 job 文件并确认零残留**

```bash
rm quantsys-v2/infrastructure/jobs/v13_trading_job.py quantsys-v2/infrastructure/jobs/v14_trading_job.py
grep -rn "v13_trading_job\|v14_trading_job" quantsys-v2 --include="*.py" | grep -v __pycache__
```

Expected: 无输出（scheduler_daemon.py:62 docstring 中的示例字符串除外——把它也改成 `infrastructure.jobs.strategy_trading_job.v13_daily_check` 后即应无输出）

- [x] **Step 3: 运行受影响测试**

Run: `venv/bin/python -m pytest tests/test_v13_scheduler.py tests/test_unified_scheduler_misfire.py tests/test_strategy_service_unified.py -v`
Expected: 全 PASS

- [x] **Step 4: Commit**

```bash
git add -A quantsys-v2
git commit -m "refactor(quantsys-v2): 全部引用迁移到统一 strategy_trading_job，删除旧 v13/v14 job"
```

---

### Task 6: weekly_report_job 修复（同类账户硬编码 bug）

**Files:**
- Modify: `infrastructure/jobs/weekly_report_job.py`
- Test: `tests/test_weekly_report_job.py`（新建）

背景：`run()` 调用了 4 个不存在/不匹配的 repo 接口：`get_account_total_value`、`get_trades_between`、`list_positions`（2 处）、`count_rebalances`，且 `trade.direction`、`account.cash` 字段名错误，账户硬编码 `'default'`。repo 真实接口：`get_account`（返回 ORM，含 `total_value`/`cash_available`/`initial_capital`/`last_rebalance_date`(date)/`created_at`）、`get_trades_by_account(account, start_date, end_date)`（trade.action 为 'BUY'/'SELL'）、`get_all_positions(account)`。

- [x] **Step 1: 写失败测试**

创建 `tests/test_weekly_report_job.py`：

```python
"""weekly_report_job 修复回归测试：run() 用现有 repo 接口跑通"""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from infrastructure.jobs.weekly_report_job import WeeklyReportJob


def _make_job():
    job = WeeklyReportJob.__new__(WeeklyReportJob)
    job.config = {
        'strategy': {'rebalance_days': 7},
        'feishu': {'observation_period': {'cycles': 3}},
    }
    job.feishu_notifier = None

    repo = MagicMock()
    repo.get_account.return_value = SimpleNamespace(
        total_value=86644.52,
        cash_available=49068.52,
        initial_capital=99993.81,
        last_rebalance_date=date(2026, 7, 17),
        created_at=datetime(2026, 6, 22),
    )
    repo.get_trades_by_account.return_value = []
    repo.get_all_positions.return_value = []
    job.repo = repo

    job._calculate_position_returns = MagicMock(return_value=[])
    job._get_index_return = MagicMock(return_value=0.01)
    return job


def test_run_completes_with_existing_repo_methods():
    job = _make_job()
    job.run()  # 不抛 AttributeError 即通过

    # 账户查询使用 v13_simulation 而非 default
    assert job.repo.get_account.call_args_list[0][1]['account_name'] == 'v13_simulation'
    # 交易查询走现有接口
    job.repo.get_trades_by_account.assert_called()
```

- [x] **Step 2: 运行测试确认失败**

Run: `venv/bin/python -m pytest tests/test_weekly_report_job.py -v`
Expected: FAIL — `AttributeError: ... get_account_total_value`（或 account_name 断言失败）

- [x] **Step 3: 实现**

修改 `infrastructure/jobs/weekly_report_job.py`：

a) 类常量与 `run()` 数据获取段：

```python
class WeeklyReportJob:
    """周报任务"""

    ACCOUNT_NAME = 'v13_simulation'  # V13 策略账户（此前误用已冻结的 default）
```

b) `run()` 中：

```python
        # 获取账户信息
        account = self.repo.get_account(account_name=self.ACCOUNT_NAME)
        if not account:
            logger.warning("账户不存在，跳过周报生成")
            return

        # 计算周初和周末账户价值
        initial_value = self._get_account_value_at_date(start_date)
        final_value = float(account.total_value)

        # 计算本周收益
        weekly_return = (final_value - initial_value) / initial_value

        # 获取本周交易数据
        trades = self.repo.get_trades_by_account(
            account_name=self.ACCOUNT_NAME,
            start_date=start_date,
            end_date=end_date
        )

        # 统计调仓次数（买入交易日期去重）
        rebalance_dates = set()
        for trade in trades:
            if trade.action == 'BUY':
                rebalance_dates.add(trade.trade_date)
```

c) 持仓与现金段：

```python
        # 获取当前仓位水平
        positions = self.repo.get_all_positions(account_name=self.ACCOUNT_NAME)
        cash = float(account.cash_available)
        position_level = (final_value - cash) / final_value if final_value > 0 else 0
```

d) 观察期进度（`count_rebalances` 不存在，用全部买入交易日去重代替）：

```python
        # 观察期进度
        all_trades = self.repo.get_trades_by_account(account_name=self.ACCOUNT_NAME)
        total_rebalances = len({t.trade_date for t in all_trades if t.action == 'BUY'})
        observation_cycles = self.config['feishu']['observation_period']['cycles']
        observation_progress = f"{total_rebalances}/{observation_cycles}"
```

e) `_get_account_value_at_date`、`_get_next_rebalance_date`、`_calculate_position_returns` 三处 `'default'` 全部改为 `self.ACCOUNT_NAME`；`_get_next_rebalance_date` 中 `last_rebalance_date` 是 date 对象，改为：

```python
        last_rebalance = datetime.strptime(str(account.last_rebalance_date), '%Y-%m-%d')
```

- [x] **Step 4: 运行测试确认通过**

Run: `venv/bin/python -m pytest tests/test_weekly_report_job.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add quantsys-v2/infrastructure/jobs/weekly_report_job.py quantsys-v2/tests/test_weekly_report_job.py
git commit -m "fix(quantsys-v2): 周报任务改用现有 repo 接口与 v13_simulation 账户"
```

---

### Task 7: 调度切换 + 死任务清理 + 全量验证

**Files:**
- DB: `quant.scheduler_task_configs`（2 行 UPDATE）、`public.scheduler_tasks`（1 行 DELETE）

- [x] **Step 1: 切换调度命令到统一 job**

```bash
cd quantsys-v2 && set -a && source .env && set +a && psql "$PGDATABASE" <<'SQL'
UPDATE quant.scheduler_task_configs
SET command = 'infrastructure.jobs.strategy_trading_job.v13_daily_check'
WHERE task_name = 'v13_daily_trading';

UPDATE quant.scheduler_task_configs
SET command = 'infrastructure.jobs.strategy_trading_job.v14_daily_check'
WHERE task_name = 'v14_daily_trading';

-- 清理死任务：payload 指向不存在的 /api/simulation/run，零执行记录
DELETE FROM public.scheduler_tasks WHERE id = 'v13-daily-trading';
SQL
```

验证：

```bash
psql "$PGDATABASE" -c "SELECT task_name, command, cron_expression FROM quant.scheduler_task_configs WHERE task_name LIKE 'v1%';"
```

Expected: 两行 command 均为 `infrastructure.jobs.strategy_trading_job.*`，cron 不变（14:25 / 15:30）

- [x] **Step 2: 全量测试**

Run: `venv/bin/python -m pytest tests/ -q`
Expected: 全 PASS（若有与本次无关的历史失败，记录并在交付说明中列出，不在本计划内修）

- [x] **Step 3: 重启 scheduler_daemon（必须用 venv python）**

当前 daemon 进程用的是 homebrew Python（PID 35470），重启为：

```bash
kill 35470   # 先确认仍是 scheduler_daemon 进程
cd quantsys-v2 && nohup venv/bin/python scheduler_daemon.py >> logs/scheduler_daemon.log 2>&1 &
```

验证：新进程启动日志中出现 `✓ Task loaded: v13_daily_trading` / `v14_daily_trading`，且 14:25/15:30 触发时日志显示统一 job 的 "使用旧接口 v13_daily_check()，建议迁移到 strategy_daily_check('v13')" 字样（兼容壳输出，证明走的是统一入口）。

- [x] **Step 4: 首跑人工验证（可选，交易日 14:25 后）**

⚠️ v14 首跑将按设计立即止损卖出 300162/300432（已与用户确认）。验证点：
1. daemon 日志 v14 任务出现 `触发单股止损: ['300162', '300432']`
2. `psql "$PGDATABASE" -c "SELECT symbol, action, shares, price, trade_date FROM quant.simulation_trades WHERE account_name='v14_simulation' ORDER BY id DESC LIMIT 5;"` 出现 SELL 记录
3. v14 日志显示 `模型加载完成: 78个因子 (v14_p0_model.json)`（此前误载 v13 的 75 因子）

- [x] **Step 5: Commit（如有文档/脚本变更）**

无代码变更则跳过 commit；在交付说明中汇报 DB 变更与 daemon 重启结果。

---

## Self-Review 记录

- Spec 覆盖：修复清单 1→Task1，2→Task2，3→Task1+3，4→Task3，5→Task4+Task7-Step4，6→Task5+Task7，7→分散各 Task 的测试步骤 + Task4。weekly_report 修复→Task6。✅
- 类型一致性：`factor_calculator` 参数接受注册表键名（str）或实例，Task1/3 一致；`single_stop_loss` 属性名与 RiskController 定义一致；`rebalance(current_date=...)` 与签名一致。✅
- 占位符：无 TBD/TODO。✅
