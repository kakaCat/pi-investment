# Domain 层依赖注入指南

## 修复前后对比

### 修复前（违规）

```python
# domain/quantlib/core/portfolio_calculator.py
from adapters.outbound.repositories import PortfolioORMRepository

class PortfolioCalculator:
    def __init__(self, initial_cash: float = None):
        self.portfolio_repo = PortfolioORMRepository()  # ❌ 直接依赖具体实现
```

### 修复后（正确）

```python
# domain/quantlib/core/portfolio_calculator.py
from domain.ports import IPortfolioRepository

class PortfolioCalculator:
    def __init__(
        self,
        portfolio_repo: IPortfolioRepository,  # ✅ 依赖接口
        kline_repo: IKlineRepository,
        risk_repo: IRiskRepository,
        initial_cash: float = None
    ):
        self.portfolio_repo = portfolio_repo
        self.kline_repo = kline_repo
        self.risk_repo = risk_repo
```

## Application 层依赖注入

### 修复前

```python
# application/services/portfolio_service.py
from domain.quantlib.core.portfolio_calculator import PortfolioCalculator

class PortfolioService:
    def calculate_portfolio(self):
        calculator = PortfolioCalculator()  # Domain 自己创建依赖
        return calculator.calculate()
```

### 修复后

```python
# application/services/portfolio_service.py
from domain.quantlib.core.portfolio_calculator import PortfolioCalculator
from adapters.outbound.repositories import (
    PortfolioORMRepository,
    KlineORMRepository,
    RiskORMRepository,
)

class PortfolioService:
    def __init__(self):
        # Application 层创建具体实现
        self.portfolio_repo = PortfolioORMRepository()
        self.kline_repo = KlineORMRepository()
        self.risk_repo = RiskORMRepository()

    def calculate_portfolio(self):
        # 注入到 Domain 对象
        calculator = PortfolioCalculator(
            portfolio_repo=self.portfolio_repo,
            kline_repo=self.kline_repo,
            risk_repo=self.risk_repo,
        )
        return calculator.calculate()
```

## 测试中的 Mock

```python
# tests/test_portfolio_calculator.py
from unittest.mock import Mock
from domain.ports import IPortfolioRepository, IKlineRepository, IRiskRepository
from domain.quantlib.core.portfolio_calculator import PortfolioCalculator

def test_calculate_portfolio():
    # 创建 Mock 对象
    mock_portfolio_repo = Mock(spec=IPortfolioRepository)
    mock_kline_repo = Mock(spec=IKlineRepository)
    mock_risk_repo = Mock(spec=IRiskRepository)

    # 设置 Mock 行为
    mock_portfolio_repo.get_trades_by_date.return_value = []

    # 注入 Mock
    calculator = PortfolioCalculator(
        portfolio_repo=mock_portfolio_repo,
        kline_repo=mock_kline_repo,
        risk_repo=mock_risk_repo,
    )

    # 测试
    result = calculator.calculate_cash_balance(date.today())
    assert result == 1000000.0
```

## 需要修改的文件清单

### Domain 层（需要接受依赖注入）

1. ✅ `domain/quantlib/engine/strategy_runner.py`
2. ✅ `domain/quantlib/core/portfolio_calculator.py`
3. ✅ `domain/quantlib/tools/strategy_stock_matcher.py`
4. ✅ `domain/quantlib/engine/strategy_factory.py`
5. ✅ `domain/quantlib/stages/data_pipeline/factor_compute_stage.py`
6. ✅ `domain/quantlib/stages/data_pipeline/storage_stage.py`
7. ⚠️  `domain/quantlib/stages/data_pipeline/time_alignment_stage.py` (需要手动审查)
8. ⏳ `domain/quantlib/engine/backtest_report.py`
9. ⏳ `domain/quantlib/engine/mixins/ml_mixin.py`
10. ⏳ `domain/benchmarks/benchmark_cache.py`
11. ⏳ `domain/benchmarks/run_all_benchmarks.py`
12. ⏳ `domain/quantlib/pipeline/monitor.py`
13. ⏳ `domain/quantlib/pipeline/__init__.py`

### Application 层（需要实现依赖注入）

1. ⏳ `application/services/strategy_execution_service.py`
2. ⏳ `application/services/data_service.py`
3. ⏳ `application/services/backtest_service.py`
4. ⏳ `application/services/portfolio_service.py`
5. ⏳ 其他使用 Domain 对象的 Service

## 重构检查清单

- [ ] Domain 层所有类通过构造函数接收依赖（接口类型）
- [ ] Domain 层不再直接创建 Repository 实例
- [ ] Application 层负责创建具体 Repository 并注入
- [ ] 测试使用 Mock 对象替代真实 Repository
- [ ] 运行架构检查: `python scripts/check_ddd_violations.py`
- [ ] 所有测试通过

## 注意事项

1. **向后兼容**: 在构造函数中提供默认值 `None`，临时保持兼容性
2. **渐进式迁移**: 一次修复一个类，立即测试
3. **文档更新**: 更新类的文档字符串说明新的使用方式
4. **CLI 工具**: 需要在入口点创建并注入依赖

## 示例完整修复

见 [portfolio_calculator.py](../domain/quantlib/core/portfolio_calculator.py)
