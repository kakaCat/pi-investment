# Phase 2: 数据层重构实施计划

## 📋 概述

**目标**: 扩展Repository层，覆盖所有14张数据库表，建立统一的数据访问接口

**工作量**: 3-4天

**优先级**: P1

**依赖**: Phase 1核心抽象层

---

## 🎯 目标

1. ✅ **完整的Repository层** - 为所有14张表创建Repository
2. ✅ **统一的数据访问** - 通过DataService统一数据访问接口
3. ✅ **缓存集成** - 在Repository层集成缓存逻辑
4. ✅ **完整的测试覆盖** - 单元测试 + 集成测试
5. ✅ **性能优化** - 批量查询、连接池、索引优化

---

## 📊 当前状态

### Phase 1已完成
- ✅ `core/base_repository.py` - Repository基类
- ✅ `repositories/stock_repository.py` - 股票信息Repository
- ✅ `core/pipeline.py` - Pipeline基础框架
- ✅ `quant/stages/factor_stage.py` - 因子计算Stage
- ✅ 60个测试用例，100%通过，93%代码覆盖率

### 数据库表结构（14张表）
**核心数据层（6张）**
- ✅ `stocks` - 股票基础信息（已有Repository）
- ⏳ `daily_klines` - 日K线数据
- ⏳ `minute_klines` - 分钟K线数据
- ⏳ `factor_values` - 因子值
- ⏳ `trading_signals` - 交易信号
- ⏳ `signal_factors` - 信号因子详情

**交易执行层（3张）**
- ⏳ `portfolio_holdings` - 持仓表
- ⏳ `trades` - 交易记录表
- ⏳ `orders` - 订单表

**策略回测层（2张）**
- ⏳ `backtest_results` - 回测结果表
- ⏳ `strategy_configs` - 策略配置表

**风险管理层（2张）**
- ⏳ `account_balance` - 账户资金表
- ⏳ `risk_metrics` - 风险指标表

**执行记录层（1张）**
- ⏳ `signal_executions` - 信号执行记录表

---

## 📝 任务清单

### Task 1: KlineRepository（日K线和分钟K线）

**文件**: `repositories/kline_repository.py`

**功能需求**:
```python
class KlineRepository(BaseRepository):
    """K线数据Repository，支持日K线和分钟K线"""
    
    # 查询方法
    def get_daily_klines(self, symbol: str, start_date: str, end_date: str) -> List[Dict]
    def get_minute_klines(self, symbol: str, start_time: str, end_time: str) -> List[Dict]
    def get_latest_kline(self, symbol: str, kline_type: str = 'daily') -> Optional[Dict]
    def get_klines_batch(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, List[Dict]]
    
    # 写入方法
    def save_daily_klines(self, klines: List[Dict]) -> int
    def save_minute_klines(self, klines: List[Dict]) -> int
    def upsert_klines(self, klines: List[Dict], kline_type: str = 'daily') -> int
    
    # 统计方法
    def get_kline_count(self, symbol: str, start_date: str, end_date: str) -> int
    def get_available_date_range(self, symbol: str) -> Tuple[str, str]
```

**测试用例**:
- 测试日K线查询（单股票、多股票、日期范围）
- 测试分钟K线查询（时间范围、最新K线）
- 测试批量查询性能
- 测试数据写入和更新
- 测试参数校验（无效股票代码、日期格式）
- 测试边界条件（空数据、大数据量）

**验收标准**:
- ✅ 所有查询方法正常工作
- ✅ 支持批量操作
- ✅ 测试覆盖率 > 90%
- ✅ 查询性能 < 100ms（单股票1年数据）

---

### Task 2: FactorRepository（因子值管理）

**文件**: `repositories/factor_repository.py`

**功能需求**:
```python
class FactorRepository(BaseRepository):
    """因子值Repository"""
    
    # 查询方法
    def get_factors(self, symbol: str, date: str) -> Optional[Dict]
    def get_factors_batch(self, symbols: List[str], date: str) -> Dict[str, Dict]
    def get_factor_history(self, symbol: str, factor_name: str, start_date: str, end_date: str) -> List[Dict]
    def get_latest_factors(self, symbol: str) -> Optional[Dict]
    
    # 写入方法
    def save_factors(self, symbol: str, date: str, factors: Dict[str, float]) -> bool
    def save_factors_batch(self, factor_data: List[Dict]) -> int
    def update_factor(self, symbol: str, date: str, factor_name: str, value: float) -> bool
    
    # 统计方法
    def get_factor_stats(self, factor_name: str, start_date: str, end_date: str) -> Dict
    def get_available_factors(self, symbol: str) -> List[str]
```

**测试用例**:
- 测试因子查询（单股票、批量、历史数据）
- 测试因子写入和更新
- 测试因子统计（均值、标准差、分位数）
- 测试参数校验
- 测试JSON序列化（处理NaN、Infinity）

**验收标准**:
- ✅ 支持42个因子的存储和查询
- ✅ 批量操作性能优化
- ✅ 测试覆盖率 > 90%
- ✅ 正确处理特殊值（NaN、Infinity）

---

### Task 3: SignalRepository（交易信号管理）

**文件**: `repositories/signal_repository.py`

**功能需求**:
```python
class SignalRepository(BaseRepository):
    """交易信号Repository"""
    
    # 查询方法
    def get_signal(self, signal_id: int) -> Optional[Dict]
    def get_signals_by_date(self, date: str, signal_type: str = None) -> List[Dict]
    def get_signals_by_symbol(self, symbol: str, start_date: str, end_date: str) -> List[Dict]
    def get_active_signals(self) -> List[Dict]
    def get_signal_with_factors(self, signal_id: int) -> Dict
    
    # 写入方法
    def create_signal(self, signal_data: Dict) -> int
    def update_signal_status(self, signal_id: int, status: str) -> bool
    def save_signal_factors(self, signal_id: int, factors: Dict[str, float]) -> bool
    
    # 统计方法
    def get_signal_stats(self, start_date: str, end_date: str) -> Dict
    def get_signal_performance(self, signal_id: int) -> Dict
```

**测试用例**:
- 测试信号查询（按日期、按股票、按状态）
- 测试信号创建和状态更新
- 测试信号因子关联查询
- 测试信号统计和绩效分析
- 测试参数校验

**验收标准**:
- ✅ 支持信号全生命周期管理
- ✅ 支持信号因子关联查询
- ✅ 测试覆盖率 > 90%
- ✅ 查询性能优化

---

### Task 4: PortfolioRepository（持仓和交易记录）

**文件**: `repositories/portfolio_repository.py`

**功能需求**:
```python
class PortfolioRepository(BaseRepository):
    """持仓和交易记录Repository"""
    
    # 持仓查询
    def get_holdings(self, account_id: str = 'default') -> List[Dict]
    def get_holding(self, account_id: str, symbol: str) -> Optional[Dict]
    def get_holding_history(self, account_id: str, symbol: str, start_date: str, end_date: str) -> List[Dict]
    
    # 持仓更新
    def update_holding(self, account_id: str, symbol: str, quantity: int, cost_price: float) -> bool
    def close_holding(self, account_id: str, symbol: str) -> bool
    
    # 交易记录查询
    def get_trades(self, account_id: str, start_date: str, end_date: str) -> List[Dict]
    def get_trade(self, trade_id: int) -> Optional[Dict]
    def get_trades_by_symbol(self, symbol: str, start_date: str, end_date: str) -> List[Dict]
    
    # 交易记录写入
    def create_trade(self, trade_data: Dict) -> int
    def update_trade_status(self, trade_id: int, status: str) -> bool
    
    # 订单管理
    def create_order(self, order_data: Dict) -> int
    def get_order(self, order_id: int) -> Optional[Dict]
    def get_pending_orders(self, account_id: str) -> List[Dict]
    def update_order_status(self, order_id: int, status: str, filled_quantity: int = None) -> bool
    
    # 统计方法
    def get_portfolio_value(self, account_id: str) -> float
    def get_trade_stats(self, account_id: str, start_date: str, end_date: str) -> Dict
```

**测试用例**:
- 测试持仓查询和更新
- 测试交易记录创建和查询
- 测试订单管理（创建、查询、状态更新）
- 测试持仓历史查询
- 测试统计方法（持仓价值、交易统计）
- 测试并发更新（乐观锁）

**验收标准**:
- ✅ 支持多账户管理
- ✅ 支持持仓、交易、订单完整生命周期
- ✅ 测试覆盖率 > 90%
- ✅ 并发安全

---

### Task 5: BacktestRepository（回测结果）

**文件**: `repositories/backtest_repository.py`

**功能需求**:
```python
class BacktestRepository(BaseRepository):
    """回测结果Repository"""
    
    # 回测结果查询
    def get_backtest(self, backtest_id: int) -> Optional[Dict]
    def get_backtests_by_strategy(self, strategy_name: str) -> List[Dict]
    def get_latest_backtest(self, strategy_name: str) -> Optional[Dict]
    def get_backtest_trades(self, backtest_id: int) -> List[Dict]
    
    # 回测结果写入
    def create_backtest(self, backtest_data: Dict) -> int
    def save_backtest_trades(self, backtest_id: int, trades: List[Dict]) -> int
    def update_backtest_metrics(self, backtest_id: int, metrics: Dict) -> bool
    
    # 策略配置管理
    def get_strategy_config(self, strategy_name: str) -> Optional[Dict]
    def save_strategy_config(self, config_data: Dict) -> int
    def update_strategy_config(self, strategy_name: str, config: Dict) -> bool
    def get_all_strategies(self) -> List[Dict]
    
    # 统计方法
    def get_strategy_performance_comparison(self, strategy_names: List[str]) -> Dict
    def get_best_backtest(self, metric: str = 'sharpe_ratio') -> Optional[Dict]
```

**测试用例**:
- 测试回测结果创建和查询
- 测试回测交易记录保存
- 测试策略配置管理
- 测试策略性能比较
- 测试参数校验

**验收标准**:
- ✅ 支持完整的回测结果存储
- ✅ 支持策略配置管理
- ✅ 测试覆盖率 > 90%
- ✅ 支持策略性能比较

---

### Task 6: RiskRepository（风险指标和账户资金）

**文件**: `repositories/risk_repository.py`

**功能需求**:
```python
class RiskRepository(BaseRepository):
    """风险指标和账户资金Repository"""
    
    # 账户资金查询
    def get_account_balance(self, account_id: str) -> Optional[Dict]
    def get_balance_history(self, account_id: str, start_date: str, end_date: str) -> List[Dict]
    def get_latest_balance(self, account_id: str) -> Optional[Dict]
    
    # 账户资金更新
    def update_balance(self, account_id: str, balance_data: Dict) -> bool
    def record_balance_snapshot(self, account_id: str) -> int
    
    # 风险指标查询
    def get_risk_metrics(self, account_id: str, date: str) -> Optional[Dict]
    def get_risk_metrics_history(self, account_id: str, start_date: str, end_date: str) -> List[Dict]
    def get_latest_risk_metrics(self, account_id: str) -> Optional[Dict]
    
    # 风险指标写入
    def save_risk_metrics(self, account_id: str, date: str, metrics: Dict) -> bool
    def update_risk_metrics(self, account_id: str, date: str, metrics: Dict) -> bool
    
    # 统计方法
    def get_max_drawdown(self, account_id: str, start_date: str, end_date: str) -> float
    def get_sharpe_ratio(self, account_id: str, start_date: str, end_date: str) -> float
    def check_risk_limits(self, account_id: str) -> Dict[str, bool]
```

**测试用例**:
- 测试账户资金查询和更新
- 测试资金历史查询
- 测试风险指标查询和保存
- 测试风险统计（最大回撤、夏普比率）
- 测试风险限制检查
- 测试参数校验

**验收标准**:
- ✅ 支持账户资金管理
- ✅ 支持风险指标计算和存储
- ✅ 测试覆盖率 > 90%
- ✅ 支持风险限制检查

---

### Task 7: DataService（统一数据访问接口）

**文件**: `services/data_service.py`

**功能需求**:
```python
class DataService:
    """统一数据访问服务，聚合所有Repository"""
    
    def __init__(self):
        self.stock_repo = StockRepository()
        self.kline_repo = KlineRepository()
        self.factor_repo = FactorRepository()
        self.signal_repo = SignalRepository()
        self.portfolio_repo = PortfolioRepository()
        self.backtest_repo = BacktestRepository()
        self.risk_repo = RiskRepository()
    
    # 高级查询方法
    def get_stock_with_latest_data(self, symbol: str) -> Dict
    def get_market_snapshot(self, date: str) -> Dict
    def get_portfolio_summary(self, account_id: str) -> Dict
    def get_strategy_dashboard(self, strategy_name: str) -> Dict
    
    # 批量操作
    def refresh_market_data(self, symbols: List[str], date: str) -> Dict
    def calculate_and_save_factors(self, symbols: List[str], date: str) -> int
    
    # 缓存管理
    def clear_cache(self, cache_type: str = 'all') -> bool
    def get_cache_stats(self) -> Dict
```

**测试用例**:
- 测试高级查询方法
- 测试批量操作
- 测试缓存集成
- 测试错误处理
- 测试性能

**验收标准**:
- ✅ 统一的数据访问接口
- ✅ 缓存集成
- ✅ 测试覆盖率 > 90%
- ✅ 性能优化

---

### Task 8: 集成测试

**文件**: `tests/test_data_layer_integration.py`

**测试场景**:
1. **完整数据流测试**
   - 股票数据 → K线数据 → 因子计算 → 信号生成 → 交易执行 → 持仓更新

2. **回测流程测试**
   - 策略配置 → 历史数据加载 → 回测执行 → 结果保存 → 绩效分析

3. **风险管理测试**
   - 持仓查询 → 风险指标计算 → 风险限制检查 → 预警触发

4. **性能测试**
   - 批量查询性能（1000只股票）
   - 并发写入性能（100个并发请求）
   - 缓存命中率测试

5. **错误处理测试**
   - 数据库连接失败
   - 数据不一致
   - 并发冲突

**验收标准**:
- ✅ 所有集成测试通过
- ✅ 端到端流程验证
- ✅ 性能达标
- ✅ 错误处理完善

---

### Task 9: 文档和总结

**文件**:
- `docs/phase2-summary.md` - Phase 2完成总结
- `README.md` - 更新项目文档
- `docs/api-reference.md` - Repository API参考文档

**内容**:
1. Phase 2完成情况总结
2. Repository层架构说明
3. 使用示例和最佳实践
4. 性能优化建议
5. 下一步计划（Phase 3）

**验收标准**:
- ✅ 文档完整清晰
- ✅ 包含使用示例
- ✅ 包含性能数据
- ✅ Git提交记录完整

---

## 🎯 验收标准

### 功能完整性
- ✅ 所有14张表都有对应的Repository
- ✅ 所有Repository继承自BaseRepository
- ✅ 统一的数据访问接口（DataService）
- ✅ 支持批量操作
- ✅ 支持缓存集成

### 测试覆盖率
- ✅ 单元测试覆盖率 > 90%
- ✅ 集成测试覆盖核心流程
- ✅ 所有测试通过
- ✅ 性能测试达标

### 代码质量
- ✅ 遵循Python PEP 8规范
- ✅ 类型注解完整
- ✅ 文档字符串完整
- ✅ 无重复代码

### 性能指标
- ✅ 单股票查询 < 50ms
- ✅ 批量查询（100只股票）< 500ms
- ✅ 因子计算 < 200ms/股票
- ✅ 缓存命中率 > 80%

---

## 📈 进度跟踪

| Task | 状态 | 完成时间 | 测试通过 | 代码覆盖率 |
|------|------|----------|----------|------------|
| Task 1: KlineRepository | ⏳ 待开始 | - | - | - |
| Task 2: FactorRepository | ⏳ 待开始 | - | - | - |
| Task 3: SignalRepository | ⏳ 待开始 | - | - | - |
| Task 4: PortfolioRepository | ⏳ 待开始 | - | - | - |
| Task 5: BacktestRepository | ⏳ 待开始 | - | - | - |
| Task 6: RiskRepository | ⏳ 待开始 | - | - | - |
| Task 7: DataService | ⏳ 待开始 | - | - | - |
| Task 8: 集成测试 | ⏳ 待开始 | - | - | - |
| Task 9: 文档和总结 | ⏳ 待开始 | - | - | - |

---

## 🚀 下一步

完成Phase 2后，将进入：
- **Phase 3**: ML层整合（合并多个训练器和预测器）
- **Phase 4**: CLI层简化（298个函数 → 命令模式）
- **Phase 5**: API层优化（统一参数验证、错误处理）

---

## 📚 参考资料

- [Phase 1完成总结](./phase1-summary.md)
- [数据库表结构文档](./database-schema.md)
- [架构设计文档](../../docs/superpowers/specs/2026-05-20-quant-system-architecture-design.md)
- [BaseRepository实现](../core/base_repository.py)
- [StockRepository示例](../repositories/stock_repository.py)
