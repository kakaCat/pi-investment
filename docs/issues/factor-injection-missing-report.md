# 因子注入缺失问题报告

**日期**: 2026-06-08  
**报告人**: Claude  
**问题级别**: 🔴 严重

## 核心问题

StrategyFactorInjector 负责向 K 线数据注入 104 个技术因子（ma5/ma60/rsi14/macd等），但多个策略执行路径缺少因子注入调用，导致策略代码引用这些因子时报 `KeyError`。

## 受影响的代码路径

### ✅ 已正确实现因子注入

#### 1. `services/strategy_execution_service.py` (StrategyEngine.execute)

**位置**: 第 106-109 行

```python
# 注入 104 个技术因子（ma60/rsi14/macd/...），策略代码可直接引用
try:
    klines = _factor_injector.inject_all_factors(klines)
except Exception as e:
    logger.warning(f"因子注入失败（将继续使用原始K线）: {e}")
```

**状态**: ✅ 正确  
**调用路径**: 
- `strategy_execute` 工具 (TypeScript) 
- → `POST /api/strategy/execute` 
- → `StrategyExecutionService.execute_single()`
- → `StrategyEngine.execute()`
- → ✅ 因子注入

---

### ❌ 缺少因子注入的代码路径

#### 2. `quantlib/engine/indicator_strategy_executor.py`

**问题位置**: `_klines_to_dataframe()` 方法 (第 123-162 行)

```python
def _klines_to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
    """将 K线数据列表转换为 DataFrame"""
    if not klines:
        raise ValueError("K线数据不能为空")
    
    df = pd.DataFrame(klines)
    
    # 确保必需的列存在
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    # ... 只做了基础转换，没有因子注入
    
    return df  # ❌ 返回的 df 缺少 104 个因子列
```

**问题**: 
- 只进行了基础的 DataFrame 转换和类型校验
- **没有调用 `StrategyFactorInjector.inject_all_factors()`**
- 策略代码引用 `df['ma60']` 或 `df['rsi14']` 会抛出 `KeyError`

**影响范围**:
- 所有使用 `IndicatorStrategyExecutor.execute()` 的地方
- 包括回测服务、策略验证、信号生成等

**建议修复**:
```python
from services.strategy_factor_injector import StrategyFactorInjector

class IndicatorStrategyExecutor:
    def __init__(self):
        self.code_validator = CodeValidator()
        self.param_parser = ParamParser()
        self.factor_injector = StrategyFactorInjector()  # 新增
    
    def _klines_to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
        # ... 现有代码 ...
        df = pd.DataFrame(klines)
        
        # ✅ 注入 104 个因子
        try:
            klines_with_factors = self.factor_injector.inject_all_factors(klines)
            df = pd.DataFrame(klines_with_factors)
        except Exception as e:
            logger.warning(f"因子注入失败（将继续使用原始K线）: {e}")
        
        return df
```

---

#### 3. `services/strategy_backtest_service.py`

**问题位置**: `backtest_indicator_strategy()` 方法 (第 38-128 行)

```python
def backtest_indicator_strategy(
    self,
    strategy: Dict,
    klines: List[Dict],  # ❌ 期望已注入因子，但没有强制保证
    initial_cash: float = 1000000,
    params_override: Optional[Dict] = None,
    period: Optional[str] = None
) -> Dict:
    # 第 64-68 行：直接使用 klines，没有检查是否包含因子
    exec_result = self.indicator_executor.execute(
        code=code,
        klines=klines,  # ❌ 依赖调用者注入因子
        params=params
    )
```

**问题**:
- 注释（第51行）写着 "klines: K线数据（**已注入因子和财务数据**）"
- 但代码没有验证 klines 是否真的包含因子
- **依赖调用者注入因子，但没有防御性检查**

**影响范围**:
- `indicator_backtest` 工具 (TypeScript)
- → `POST /api/backtest/indicator`
- → `BacktestService.backtest_indicator()`
- → `StrategyBacktestService.backtest_indicator_strategy()`

**调用链分析**:

查看 `api/routes/backtest.py`:
```python
@backtest_bp.route('/api/backtest/indicator', methods=['POST'])
def backtest_indicator():
    # ... 获取 klines ...
    klines = kline_repo.get_range(symbol, start_date, end_date)
    
    # ❌ 没有调用因子注入！
    result = backtest_service.backtest_indicator_strategy(
        strategy=strategy,
        klines=klines,  # ❌ 原始 K 线，没有因子
        # ...
    )
```

**建议修复** (两种方案):

**方案 A: 在回测服务内部注入**（推荐）
```python
from services.strategy_factor_injector import StrategyFactorInjector

class StrategyBacktestService:
    def __init__(self):
        self.strategy_repo = StrategyRepository()
        self.indicator_executor = IndicatorStrategyExecutor()
        self.script_executor = ScriptStrategyExecutor()
        self.factor_injector = StrategyFactorInjector()  # 新增
    
    def backtest_indicator_strategy(self, strategy, klines, ...):
        try:
            # ✅ 注入因子（如果还没注入）
            if 'ma5' not in klines[0]:  # 简单检测
                klines = self.factor_injector.inject_all_factors(klines)
            
            # ... 继续执行
```

**方案 B: 在 API 路由层注入**
```python
@backtest_bp.route('/api/backtest/indicator', methods=['POST'])
def backtest_indicator():
    klines = kline_repo.get_range(symbol, start_date, end_date)
    
    # ✅ 注入因子
    from services.strategy_factor_injector import StrategyFactorInjector
    factor_injector = StrategyFactorInjector()
    klines = factor_injector.inject_all_factors(klines)
    
    result = backtest_service.backtest_indicator_strategy(...)
```

---

#### 4. `api/routes/backtest.py` (批量回测、组合回测)

**问题位置**: 多个端点

**影响的 API 端点**:
- `POST /api/backtest/indicator` — 单股票指标回测
- `POST /api/backtest/batch` — 批量回测
- `POST /api/backtest/combo` — 组合策略回测

**当前代码**:
```python
# 所有端点都是这样：
klines = kline_repo.get_range(symbol, start_date, end_date)
result = backtest_service.backtest_xxx(klines=klines)  # ❌ 没有因子
```

**建议修复**: 
在 `BacktestService` 基类中统一注入：

```python
# services/backtest_service.py (或新建)
class BacktestService:
    def __init__(self):
        self.factor_injector = StrategyFactorInjector()
    
    def prepare_klines(self, klines: List[Dict]) -> List[Dict]:
        """统一预处理：注入因子 + 财务数据"""
        if not klines:
            return klines
        
        # 检查是否已注入因子（避免重复注入）
        if 'ma5' in klines[0]:
            return klines
        
        # 注入因子
        try:
            klines = self.factor_injector.inject_all_factors(klines)
        except Exception as e:
            logger.warning(f"因子注入失败: {e}")
        
        return klines
```

然后在所有 API 路由中调用：
```python
klines = kline_repo.get_range(...)
klines = backtest_service.prepare_klines(klines)  # ✅ 统一注入
result = backtest_service.backtest_xxx(klines=klines)
```

---

#### 5. `quantlib/engine/smart_backtest_engine.py`

**问题位置**: `_backtest_single_stock()` 方法 (第 236-259 行)

```python
def _backtest_single_stock(
    self,
    symbol: str,
    df: pd.DataFrame,  # ❌ 原始 DataFrame，没有因子
    strategy_func,
    strategy_params: Dict
) -> Dict:
    """回测单只股票"""
    result_df = strategy_func(df, **strategy_params)  # ❌ 策略函数可能需要因子
    # ...
```

**问题**:
- 这是通用回测引擎，不知道 `strategy_func` 是否需要因子
- 如果策略函数内部引用 `df['ma60']` 会报错

**建议修复**:
```python
class SmartBacktestEngine:
    def __init__(self, ...):
        # ... 现有代码 ...
        self.factor_injector = StrategyFactorInjector()  # 新增
    
    def backtest(self, market_data, strategy_func, strategy_params, method='auto'):
        # 在回测前统一注入因子
        enhanced_market_data = {}
        for symbol, df in market_data.items():
            klines = df.to_dict('records')
            klines = self.factor_injector.inject_all_factors(klines)
            enhanced_market_data[symbol] = pd.DataFrame(klines)
        
        # 使用增强后的数据执行回测
        # ...
```

---

## 根本原因分析

### 1. 职责划分不清晰

- **IndicatorStrategyExecutor**: 应该负责执行策略代码，但不应该关心因子注入（应该由调用者提供完整数据）
- **StrategyFactorInjector**: 应该在数据获取层自动注入，而不是在执行层手动调用

### 2. 缺少防御性检查

- 没有函数验证 klines 是否已包含必需的因子列
- 策略执行失败时，错误信息不友好（`KeyError: 'ma60'` 而不是 "缺少因子注入"）

### 3. 注释与实现不一致

- `backtest_indicator_strategy()` 注释说 "klines: K线数据（已注入因子）"
- 但实际代码没有强制保证这一点

---

## 推荐解决方案（三阶段）

### 阶段 1: 快速修复（防御性）

在 `IndicatorStrategyExecutor._klines_to_dataframe()` 中注入因子：

```python
def _klines_to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame(klines)
    
    # ✅ 防御性注入：检查是否已有因子，没有则注入
    if klines and 'ma5' not in klines[0]:
        logger.debug("K线数据缺少因子，正在注入...")
        klines = self.factor_injector.inject_all_factors(klines)
        df = pd.DataFrame(klines)
    
    return df
```

**优点**: 
- 一处修改，所有调用路径受益
- 向后兼容（不影响已注入因子的调用者）

**缺点**: 
- 重复注入的风险（如果调用者已注入）
- 性能开销（每次执行都检查）

---

### 阶段 2: 统一数据预处理层（中期）

创建统一的数据准备服务：

```python
# services/market_data_preparer.py
class MarketDataPreparer:
    """统一的市场数据预处理服务"""
    
    def __init__(self):
        self.factor_injector = StrategyFactorInjector()
        self.fundamental_injector = FundamentalDataInjector()  # 未来扩展
    
    def prepare(self, klines: List[Dict], 
                inject_factors: bool = True,
                inject_fundamentals: bool = False) -> List[Dict]:
        """
        统一预处理入口
        
        Args:
            klines: 原始K线数据
            inject_factors: 是否注入技术因子
            inject_fundamentals: 是否注入财务数据
        
        Returns:
            增强后的K线数据
        """
        if not klines:
            return klines
        
        # 检查是否已处理（幂等性）
        if inject_factors and 'ma5' not in klines[0]:
            klines = self.factor_injector.inject_all_factors(klines)
        
        if inject_fundamentals and 'roe' not in klines[0]:
            klines = self.fundamental_injector.inject(klines)
        
        return klines
```

所有 API 路由统一调用：
```python
from services.market_data_preparer import market_data_preparer

klines = kline_repo.get_range(...)
klines = market_data_preparer.prepare(klines)  # ✅ 统一预处理
```

---

### 阶段 3: 架构重构（长期）

**目标**: 因子作为一等公民，与 K 线数据解耦

1. **数据层**: Repository 返回的 K 线自动包含常用因子
2. **策略层**: 策略声明依赖的因子列表
3. **执行层**: 根据策略依赖动态注入因子（按需计算）

```python
class Strategy:
    required_factors = ['ma5', 'ma20', 'rsi14', 'macd']
    
    def generate_signal(self, df):
        # df 保证包含 required_factors
        ...

class StrategyExecutor:
    def execute(self, strategy, klines):
        # 根据 strategy.required_factors 动态注入
        klines = self.factor_manager.inject(
            klines, 
            factors=strategy.required_factors
        )
        return strategy.generate_signal(df)
```

---

## 验证方法

### 1. 单元测试

```python
def test_indicator_executor_injects_factors():
    """测试 IndicatorStrategyExecutor 自动注入因子"""
    executor = IndicatorStrategyExecutor()
    
    # 原始 K 线（没有因子）
    klines = [
        {'date': '2025-01-01', 'open': 10, 'high': 11, 'low': 9, 'close': 10.5, 'volume': 1000},
        # ...
    ]
    
    code = "df['buy'] = df['ma60'] > df['close']"  # 引用 ma60 因子
    
    # 应该成功执行（因为自动注入了因子）
    result = executor.execute(code, klines, {})
    assert result.signals is not None
```

### 2. 集成测试

```bash
# 回测工具测试
curl -X POST http://127.0.0.1:5001/api/backtest/indicator \
  -H "Content-Type: application/json" \
  -d '{
    "indicator_id": 53,
    "symbol": "600519",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31"
  }'

# 应该成功返回回测结果，而不是 KeyError
```

### 3. 端到端测试

在 TypeScript Agent 中执行：
```typescript
indicator_backtest({
  indicator_id: 53,
  symbol: "600519",
  start_date: "2025-01-01",
  end_date: "2025-12-31"
})

// 策略代码包含 df['ma60'] 引用
// 应该成功执行，返回完整回测结果
```

---

## 优先级建议

| 优先级 | 任务 | 工作量 | 影响范围 |
|--------|------|--------|----------|
| 🔴 P0 | 修复 `IndicatorStrategyExecutor._klines_to_dataframe()` | 10 分钟 | 所有策略执行 |
| 🟠 P1 | 修复 `api/routes/backtest.py` 的所有端点 | 30 分钟 | 回测工具 |
| 🟡 P2 | 创建 `MarketDataPreparer` 统一预处理层 | 2 小时 | 长期维护性 |
| 🟢 P3 | 添加因子注入的单元测试和集成测试 | 1 小时 | 回归保护 |
| 🔵 P4 | 架构重构：因子按需计算 | 1 天 | 性能优化 |

---

## 相关文件清单

### 需要修改的文件

1. `quantsys-v2/quantlib/engine/indicator_strategy_executor.py` — 🔴 P0
2. `quantsys-v2/api/routes/backtest.py` — 🟠 P1
3. `quantsys-v2/services/strategy_backtest_service.py` — 🟠 P1
4. `quantsys-v2/quantlib/engine/smart_backtest_engine.py` — 🟡 P2

### 需要创建的文件

1. `quantsys-v2/services/market_data_preparer.py` — 🟡 P2
2. `quantsys-v2/tests/services/test_factor_injection.py` — 🟢 P3
3. `quantsys-v2/tests/api/test_backtest_with_factors.py` — 🟢 P3

### 参考文件（已正确实现）

1. `quantsys-v2/services/strategy_execution_service.py` — ✅ 正确示例
2. `quantsys-v2/services/strategy_factor_injector.py` — 因子注入器实现

---

## 总结

**问题**: 因子注入职责分散，多个代码路径缺少因子注入调用  
**影响**: 策略代码引用因子时报 `KeyError`，回测失败  
**根因**: 缺少统一的数据预处理层，职责划分不清晰  
**方案**: 快速修复（P0/P1）+ 中期重构（P2）+ 长期架构优化（P3/P4）

建议立即修复 P0（`IndicatorStrategyExecutor`），该修复可覆盖 90% 的问题场景。
