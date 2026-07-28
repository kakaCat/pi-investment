# 统一 v13/v14 策略每日检查架构设计

日期：2026-07-28
状态：已确认
范围：quantsys-v2

## 背景

v13/v14 模拟策略的止损从未执行，根因调查（2026-07-27）发现：

1. **v14 止损是桩代码**：`infrastructure/jobs/v14_trading_job.py` 止损块为 `# TODO: 实现V14止损逻辑`，永远输出"暂无触发"。证据：v14_simulation 持有 300162（-47.6%）、300432（-22.2%），远超 -12% 阈值，历史上 zero SELL。
2. **v13 job 加载错误账户**：`v13_trading_job.py` 创建 `SimulationTrader` 时不设 `account_name`，构造函数硬编码 `'default'` 并在 `__init__` 内完成账户加载。default 账户 07-23 重建后 0 持仓、已冻结，`if self.portfolio:` 为 False，止损整体跳过。
3. **`load_model()` 硬编码 v13 模型**：无视 `self.model_path`/`self.factors_path`，v14 实际一直在用 v13 的模型和因子文件，`v14_p0_model.json` 从未被加载。
4. **因子计算器硬编码**：`SimulationTrader.__init__` 写死 `V13FactorCalculator()`，v14 应使用 `V14FactorCalculator`。
5. **统一架构已存在但未接线**：`application/services/strategy_service.py`（StrategyService）+ `infrastructure/jobs/strategy_trading_job.py` + `live_trading/configs/strategies/{v13,v14,v15}.yaml` 已就绪，但调度表仍指向旧 job，且 StrategyService 自身有三个 bug（见下）。

用户决策（2026-07-27）：
- 目标形态：**统一每日检查流水线**（共享领域服务 + 每策略一份配置），不做完整领域层重构，v13/v14 不退役。
- v14 深套持仓：**修复后首次运行立即按 -12% 规则止损卖出**（策略设计行为）。
- 新策略必须**可配置化接入**（一个 yaml + 两条 SQL + 模型文件，免改代码）。

## 总体设计

修复并启用已有的统一架构，不新造轮子：

```
quant.scheduler_task_configs (DB)
  v13_daily_trading  14:25 ─┐
  v14_daily_trading  15:30 ─┤
                            ▼
        infrastructure/jobs/strategy_trading_job.py
          v13_daily_check() / v14_daily_check()  （薄兼容壳）
                            ▼
        application/services/strategy_service.py
          StrategyService.daily_check(strategy_name)
            ├─ get_config(strategy_name)      → configs/strategies/<name>.yaml
            ├─ _create_trader(config)          → SimulationTrader（正确账户/模型/因子/风控）
            └─ trader.run_daily_check()        → 止损检查 → 调仓判断 → 调仓
```

新策略接入路径（如 v16）：
1. 新建 `live_trading/configs/strategies/v16.yaml`
2. `simulation_account` 表插入 `v16_simulation` 账户（一条 SQL）
3. `scheduler_task_configs` 表插入定时任务（一条 SQL，command 指统一 job）
4. 模型文件放入 `live_trading/models/`

仅当新策略引入**全新因子体系**时，才需在因子计算器注册表加一行代码。

## 修复清单

### 1. `SimulationTrader.__init__` 增加 `account_name` 参数

文件：`live_trading/simulation_trader.py:58`

```python
def __init__(self, config_path='live_trading/config_simulation.yaml',
             account_name='default', factor_calculator=None):
```

- `self.account_name = account_name` 在 `_load_account_from_db()` **之前**赋值
- 默认 `'default'` 保持向后兼容

### 2. `load_model()` 改用实例属性

文件：`live_trading/simulation_trader.py:637`

- `__init__` 设默认值：`self.model_path = <base>/models/v13_model.json`、`self.factors_path = <base>/models/valid_factors.json`（保持现状行为）
- `load_model()` 读 `self.model_path`/`self.factors_path`，不再硬编码
- v14 从此真正加载 `v14_p0_model.json` + `v14_p0_valid_factors.json`

### 3. 因子计算器配置化

- `live_trading/simulation_trader.py`（或新的小模块）增加注册表：

```python
FACTOR_CALCULATORS = {
    'v13': V13FactorCalculator,
    'v14': V14FactorCalculator,
}
```

- `__init__` 的 `factor_calculator` 参数接受注册表键名或实例；默认 `'v13'`（保持现状）
- yaml 增加 `model.factor_calculator: v13|v14` 键；v14.yaml 配 `v14`，v13.yaml 配 `v13`

### 4. 修 `StrategyService._create_trader`

文件：`application/services/strategy_service.py:272`

- `account_name`、`factor_calculator` 通过构造函数传入（修注入时机）
- 配置真正生效，消除 dead write：
  - `trader.config['strategy']['rebalance_days'] = config['trading']['rebalance_days']`（`should_rebalance` 读此处）
  - `trader.risk_controller.single_stop_loss = config['risk']['single_stock_stop_loss']`
  - 删除 `trader.stop_loss_pct`、`trader.rebalance_days`、`trader.max_positions` 等无人读取的属性赋值
- `manual_rebalance` 补传 `current_date=datetime.now().strftime('%Y-%m-%d')`（当前调用必 TypeError，因为 `rebalance(self, current_date)` 无默认值）

### 5. 止损行为（统一后 v13/v14 一致）

`run_daily_check()` 已有完整链路：`check_single_stock_stop_loss` → `_execute_stop_loss` → `_save_account_to_db`，阈值来自各自 yaml：v13=-15%、v14=-12%。

**预期首跑行为**：v14 首次运行将立即止损卖出 300162、300432（已与用户确认）。

### 6. 调度切换与清理

- `quant.scheduler_task_configs` 更新两行（时间不变）：
  - `v13_daily_trading` command → `infrastructure.jobs.strategy_trading_job.v13_daily_check`
  - `v14_daily_trading` command → `infrastructure.jobs.strategy_trading_job.v14_daily_check`
  - params 保留 `enable_stop_loss`/`enable_rebalance`
  - 切换后重启 scheduler_daemon（用 venv/bin/python）
- 删除废弃文件：`infrastructure/jobs/v13_trading_job.py`、`infrastructure/jobs/v14_trading_job.py`（先确认无残留引用）
- 删除 `public.scheduler_tasks` 死任务 `v13-daily-trading`（payload 指向不存在的 `/api/simulation/run`，零执行记录）
- 顺带修 `infrastructure/jobs/weekly_report_job.py` 的 `get_account_total_value` AttributeError（同类账户硬编码 bug，每周一 09:00 报错）：账户改为从策略配置解析，repo 方法缺失则改用现有 `get_account` 的 `total_value` 字段

### 7. 测试（pytest，quant_test 库）

新增 `tests/test_strategy_service_unified.py`：

1. `_create_trader('v14')`：`account_name` 在持仓加载前生效（portfolio 来自 v14_simulation 而非 default）
2. `load_model` 按 `self.model_path`/`self.factors_path` 加载对应文件
3. 止损阈值从策略 yaml 进入 `risk_controller.single_stop_loss`；调仓周期进入 `config['strategy']['rebalance_days']`
4. 止损触发链路：构造 -13% 持仓（v14 阈值 -12%）→ `run_daily_check` 产生 SELL 交易并落库
5. `manual_rebalance` 不再 TypeError

## 明确不做（YAGNI）

- 移动止损（trailing_stop）、止盈档位：yaml 有配置项但代码从未实现，本次不新增
- IntradayMonitor 覆盖范围（rotation_main / agent_virtual）：独立体系，不动
- v15.yaml：已存在，统一架构下自动获益，无需处理
- 完整领域层重构（domain/strategies 抽象）：用户已明确不做

## 验收标准

1. `pytest tests/test_strategy_service_unified.py` 全绿，且不回归现有测试
2. daemon 日志显示 v13/v14 任务从统一 job 入口执行，账户为 v13_simulation / v14_simulation
3. v14 首跑日志出现"触发单股止损： ['300162', '300432']"并产生 SELL 交易记录
4. v14 首跑日志显示加载 78 个因子且来自 `v14_p0_valid_factors.json`（当前误加载的默认文件为 75 个）
5. `git grep` 无 `v13_trading_job` / `v14_trading_job` 残留引用
