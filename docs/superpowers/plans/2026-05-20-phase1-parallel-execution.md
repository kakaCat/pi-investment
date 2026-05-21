# Phase 1 并行执行计划

> 复制每个 Agent 区块的完整内容，作为独立 prompt 发给一个 agent。
> 所有 agent 在同一时间开始工作，互不阻塞。

**前置条件**: Agent 0 必须先完成（项目初始化），后续 Agent 才能工作。
如果 Agent 0 还没执行，先跑 Agent 0。

---

## 执行顺序

```
Agent 0 (项目初始化, 5分钟)
    │
    └─► 并行启动 Agent 1 + 2 + 3 + 4
            │
            └─► 并行启动 Agent 5 + 6
                    │
                    └─► Agent 7 (集成测试, 等 1-6 全部完成)
                            │
                            └─► Agent 8 (文档)
```

---

# Agent 0: 项目初始化（先跑这个）

```
Task: 初始化 quantsys-v2 项目骨架

在当前仓库根目录 /Users/mac/Documents/ai/pi-investment/ 下创建 quantsys-v2/ 新项目目录，包含以下文件：

1. 创建目录结构:
   - quantsys-v2/core/
   - quantsys-v2/repositories/
   - quantsys-v2/services/
   - quantsys-v2/quant/stages/
   - quantsys-v2/tests/

2. 创建 quantsys-v2/requirements.txt:
   pandas>=2.0.0
   numpy>=1.24.0
   python-dateutil>=2.8.0
   psycopg2-binary>=2.9.0
   sqlalchemy>=2.0.0
   pytest>=7.4.0
   pytest-cov>=4.1.0
   pytest-mock>=3.11.0
   xgboost>=1.7.0
   scikit-learn>=1.3.0
   pydantic>=2.0.0

3. 创建 quantsys-v2/pytest.ini:
   [pytest]
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   addopts = 
       -v
       --tb=short
       --strict-markers

4. 创建 quantsys-v2/.gitignore:
   __pycache__/
   *.py[cod]
   .pytest_cache/
   .coverage
   htmlcov/
   .DS_Store

5. 创建所有 __init__.py（空文件）:
   - quantsys-v2/core/__init__.py
   - quantsys-v2/repositories/__init__.py
   - quantsys-v2/services/__init__.py
   - quantsys-v2/quant/__init__.py
   - quantsys-v2/quant/stages/__init__.py
   - quantsys-v2/tests/__init__.py

6. 运行: pip install -e quantsys-v2/ 下的包（如果 setup.py 不存在可跳过，但确认 pytest 可用）

执行完后报告: 目录结构是否创建完整，pytest --version 是否正常。
```

---

# Agent 1: 价格逻辑 + 盈亏计算测试（纯测试，可立即并行）

```
Task: 编写核心价格逻辑和盈亏计算的测试文件

严格只写测试代码，不写实现代码。创建以下两个文件：

## 文件 1: /Users/mac/Documents/ai/pi-investment/quantsys-v2/tests/test_price_logic.py

包含以下测试类，每个方法都是一组断言:

1. TestPriceChangeDirection - 涨跌方向判断（3个测试）
   - test_price_increase: 旧价100→新价110，change>0，涨幅=0.1
   - test_price_decrease: 旧价100→新价90，change<0，跌幅=-0.1
   - test_price_unchanged: 旧价100→新价100，change=0，涨跌幅=0

2. TestLimitUpDown - 涨跌停判断（4个测试）
   - test_limit_up_detection: 涨10%应判断为涨停
   - test_limit_down_detection: 跌10%应判断为跌停
   - test_not_limit_up: 涨5%不应判断为涨停
   - test_not_limit_down: 跌5%不应判断为跌停

3. TestPriceComparison - 价格比较（3个测试）
   - test_price_higher_than
   - test_price_lower_than
   - test_price_equal

## 文件 2: /Users/mac/Documents/ai/pi-investment/quantsys-v2/tests/test_pnl_calculation.py

1. TestUnrealizedPnL - 浮动盈亏（3个测试）
   - test_unrealized_profit: 入场100，当前110，数量100，浮动盈亏=+1000
   - test_unrealized_loss: 入场100，当前90，数量100，浮动盈亏=-1000
   - test_unrealized_breakeven: 入场100，当前100，浮动盈亏=0

2. TestRealizedPnL - 已实现盈亏（4个测试）
   - test_realized_profit_no_commission: 不计手续费，买入100卖出110，盈利+1000
   - test_realized_loss_no_commission: 不计手续费，买入100卖出90，亏损-1000
   - test_realized_profit_with_commission: 含佣金0.03%+印花税0.1%，验证扣除后仍盈利
   - test_realized_loss_with_commission: 含手续费后亏损

3. TestSlippage - 滑点（2个测试）
   - test_buy_slippage: 买入价上浮0.1%
   - test_sell_slippage: 卖出价下浮0.1%

写完两个文件后，运行: cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/test_price_logic.py tests/test_pnl_calculation.py -v

预期: 全部通过。

完成后不要写任何实现代码。
```

---

# Agent 2: Pipeline 模式（TDD）

```
Task: 用 TDD 方式实现 Pipeline 模式

## 步骤 1: 先写测试
创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/tests/test_pipeline.py

```python
import pytest
from core.pipeline import QuantPipeline, PipelineStage

class TestPipelineBasics:
    def test_create_empty_pipeline(self):
        pipeline = QuantPipeline(name="test_pipeline")
        assert pipeline.name == "test_pipeline"
        assert len(pipeline.stages) == 0

    def test_add_stage(self):
        class MockStage(PipelineStage):
            def process(self, data):
                return {"result": "mock"}
        stage = MockStage(name="mock_stage")
        pipeline = QuantPipeline(name="test")
        pipeline.add_stage(stage)
        assert len(pipeline.stages) == 1
        assert pipeline.stages[0].name == "mock_stage"

    def test_pipeline_execution_order(self):
        pipeline = QuantPipeline(name="test")
        execution_order = []
        class Stage1(PipelineStage):
            def process(self, data):
                execution_order.append("stage1")
                return {"stage1": "done"}
        class Stage2(PipelineStage):
            def process(self, data):
                execution_order.append("stage2")
                return {"stage2": "done"}
        pipeline.add_stage(Stage1(name="stage1"))
        pipeline.add_stage(Stage2(name="stage2"))
        pipeline.run({"input": "data"})
        assert execution_order == ["stage1", "stage2"]

class TestPipelineDataFlow:
    def test_data_passing_between_stages(self):
        pipeline = QuantPipeline(name="test")
        class AddStage(PipelineStage):
            def process(self, data):
                return {"value": data.get("value", 0) + 10}
        class MultiplyStage(PipelineStage):
            def process(self, data):
                return {"value": data.get("value", 0) * 2}
        pipeline.add_stage(AddStage(name="add"))
        pipeline.add_stage(MultiplyStage(name="multiply"))
        result = pipeline.run({"value": 5})
        assert result["value"] == 30  # (5+10)*2

class TestPipelinePartialExecution:
    def test_run_until_specific_stage(self):
        pipeline = QuantPipeline(name="test")
        class Stage1(PipelineStage):
            def process(self, data):
                return {"stage": "1"}
        class Stage2(PipelineStage):
            def process(self, data):
                return {"stage": "2"}
        class Stage3(PipelineStage):
            def process(self, data):
                return {"stage": "3"}
        pipeline.add_stage(Stage1(name="stage1"))
        pipeline.add_stage(Stage2(name="stage2"))
        pipeline.add_stage(Stage3(name="stage3"))
        result = pipeline.run_until("stage2", {"input": "data"})
        assert result["stage"] == "2"
```

运行测试确认失败: 
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/test_pipeline.py -v
```

## 步骤 2: 实现 pipeline.py 使测试通过

创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/core/pipeline.py

需要实现:
- PipelineStage(ABC): 抽象类，构造函数接收 name: str，抽象方法 process(data: Dict) -> Dict，可选方法 validate_input(data) -> bool
- QuantPipeline: __init__(name)，add_stage(stage) 返回 self（链式调用），run(input_data) -> Dict，run_until(stage_name, input_data) -> Dict

关键逻辑:
- run() 遍历所有 stage，将上一个 stage 的返回值传给下一个
- run_until() 在指定 stage 处停止并返回数据
- 每个 stage 执行前调用 validate_input()

## 步骤 3: 运行测试确认通过
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/test_pipeline.py -v
```

预期: 全部通过。
```

---

# Agent 3: BaseRepository（TDD）

```
Task: 用 TDD 方式实现 BaseRepository 基类

## 步骤 1: 先写测试
创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/tests/test_base_repository.py

```python
import pytest
from core.base_repository import BaseRepository

class TestBaseRepository:
    def test_validate_symbol_valid(self):
        repo = BaseRepository()
        assert repo._validate_symbol("600519") == True
        assert repo._validate_symbol("000001") == True

    def test_validate_symbol_empty(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_symbol("")

    def test_validate_symbol_wrong_length(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_symbol("12345")

    def test_validate_symbol_none(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_symbol(None)

    def test_validate_date_valid(self):
        repo = BaseRepository()
        assert repo._validate_date("2026-05-20") == True

    def test_validate_date_invalid_month(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_date("2026-13-01")

    def test_validate_date_invalid_format(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_date("invalid")

    def test_validate_positive_number_valid(self):
        repo = BaseRepository()
        assert repo._validate_positive_number(100.0, "price") == True

    def test_validate_positive_number_zero(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_positive_number(0, "price")

    def test_validate_positive_number_negative(self):
        repo = BaseRepository()
        with pytest.raises(ValueError):
            repo._validate_positive_number(-10, "price")

    def test_to_domain_object_identity(self):
        repo = BaseRepository()
        row = {"symbol": "600519", "name": "贵州茅台"}
        assert repo._to_domain_object(row) == row

    def test_to_db_row_identity(self):
        repo = BaseRepository()
        obj = {"symbol": "600519", "name": "贵州茅台"}
        assert repo._to_db_row(obj) == obj
```

运行测试确认失败:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/test_base_repository.py -v
```

## 步骤 2: 实现 base_repository.py

创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/core/base_repository.py

```python
from abc import ABC
from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BaseRepository(ABC):
    def __init__(self, db_connection=None):
        self.db = db_connection

    def _validate_symbol(self, symbol: str) -> bool:
        if not symbol:
            raise ValueError("Symbol cannot be empty")
        if not isinstance(symbol, str):
            raise ValueError("Symbol must be string")
        if len(symbol) != 6:
            raise ValueError(f"Symbol must be 6 digits, got {len(symbol)}")
        if not symbol.isdigit():
            raise ValueError("Symbol must contain only digits")
        return True

    def _validate_date(self, date_str: str) -> bool:
        if not date_str:
            raise ValueError("Date cannot be empty")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")

    def _validate_positive_number(self, value: float, name: str) -> bool:
        if value is None:
            raise ValueError(f"{name} cannot be None")
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")
        return True

    def _to_domain_object(self, db_row: Dict[str, Any]) -> Dict[str, Any]:
        return db_row

    def _to_db_row(self, domain_object: Dict[str, Any]) -> Dict[str, Any]:
        return domain_object

    def _log_query(self, operation: str, params: Dict[str, Any]):
        logger.debug(f"Repository operation: {operation}, params: {params}")
```

## 步骤 3: 运行测试确认通过
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/test_base_repository.py -v
```
```

---

# Agent 4: BaseService + Validators

```
Task: 实现 ServiceBase 基类和通用 Validators

这两个组件独立于 Pipeline 和 Repository，可以独立编写。

## 文件 1: /Users/mac/Documents/ai/pi-investment/quantsys-v2/core/validators.py

```python
"""通用参数验证器 - 供装饰器和Service共同使用"""
from typing import Any
from datetime import datetime

def validate_symbol(symbol: str) -> bool:
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Symbol cannot be empty")
    if len(symbol) != 6 or not symbol.isdigit():
        raise ValueError(f"Invalid symbol: {symbol}")
    return True

def validate_date(date_str: str) -> bool:
    if not date_str:
        raise ValueError("Date cannot be empty")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")

def validate_required(value: Any, name: str) -> bool:
    if value is None or (isinstance(value, str) and value == ""):
        raise ValueError(f"{name} is required")
    return True

def validate_positive(value: float, name: str) -> bool:
    if value is None:
        raise ValueError(f"{name} cannot be None")
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return True
```

## 文件 2: /Users/mac/Documents/ai/pi-investment/quantsys-v2/core/base_service.py

```python
"""Service基类 - 统一错误处理和日志"""
from abc import ABC
from typing import Any
import logging

class ServiceBase(ABC):
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def _validate_required(self, value: Any, name: str):
        if value is None or (isinstance(value, str) and value == ""):
            raise ValueError(f"{name} is required")

    def _validate_symbol(self, symbol: str):
        self._validate_required(symbol, "symbol")
        if not symbol.isdigit() or len(symbol) != 6:
            raise ValueError(f"Invalid symbol: {symbol}")

    def _log_operation(self, operation: str, **kwargs):
        self.logger.info(f"{operation}: {kwargs}")

    def _handle_error(self, exc: Exception, operation: str):
        self.logger.error(f"{operation} failed: {exc}")
        raise RuntimeError(f"{operation} failed") from exc
```

## 文件 3: /Users/mac/Documents/ai/pi-investment/quantsys-v2/tests/test_validators.py

```python
import pytest
from core.validators import validate_symbol, validate_date, validate_required, validate_positive

class TestValidateSymbol:
    def test_valid(self):
        assert validate_symbol("600519") == True

    def test_empty(self):
        with pytest.raises(ValueError):
            validate_symbol("")

    def test_wrong_length(self):
        with pytest.raises(ValueError):
            validate_symbol("12345")

class TestValidateDate:
    def test_valid(self):
        assert validate_date("2026-05-20") == True

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_date("invalid")

class TestValidateRequired:
    def test_valid(self):
        assert validate_required("hello", "name") == True

    def test_none(self):
        with pytest.raises(ValueError):
            validate_required(None, "name")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            validate_required("", "name")

class TestValidatePositive:
    def test_valid(self):
        assert validate_positive(100.0, "price") == True

    def test_zero(self):
        with pytest.raises(ValueError):
            validate_positive(0, "price")

    def test_negative(self):
        with pytest.raises(ValueError):
            validate_positive(-10, "price")
```

运行测试:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/test_validators.py -v
```

预期: 全部通过。
```

---

# Agent 5: StockRepository（依赖 Agent 3 的 BaseRepository）

```
Task: 实现 StockRepository

前置: 确保 /Users/mac/Documents/ai/pi-investment/quantsys-v2/core/base_repository.py 已存在。

## 步骤 1: 先写测试
创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/tests/test_stock_repository.py

```python
import pytest
from repositories.stock_repository import StockRepository

class TestStockRepository:
    def test_get_by_symbol_validation_empty(self):
        repo = StockRepository()
        with pytest.raises(ValueError):
            repo.get_by_symbol("")

    def test_get_by_symbol_validation_wrong_length(self):
        repo = StockRepository()
        with pytest.raises(ValueError):
            repo.get_by_symbol("12345")

    def test_get_by_symbol_no_db(self):
        repo = StockRepository()
        with pytest.raises(RuntimeError, match="Database"):
            repo.get_by_symbol("600519")

    def test_search_empty_keyword(self):
        repo = StockRepository()
        with pytest.raises(ValueError):
            repo.search("")

    def test_save_empty_symbol(self):
        repo = StockRepository()
        with pytest.raises(ValueError):
            repo.save({"symbol": "", "name": "test"})

    def test_save_empty_name(self):
        repo = StockRepository()
        with pytest.raises(ValueError):
            repo.save({"symbol": "600519", "name": ""})
```

运行测试确认失败:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/test_stock_repository.py -v
```

## 步骤 2: 实现

创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/repositories/stock_repository.py

核心类 StockRepository(BaseRepository)，方法:
- get_by_symbol(symbol, fields=None) -> Optional[Dict] — 先 _validate_symbol，再构建 SELECT 查询
- get_all(market=None, industry=None, is_st=None, limit=None, offset=None) -> List[Dict] — 动态拼接 WHERE 条件
- search(keyword, limit=10) -> List[Dict] — LIKE 模糊匹配 symbol 和 name
- save(stock) -> None — 校验后调用 self.db.upsert

每个方法在没有 self.db 时抛出 RuntimeError("Database connection not initialized")。

## 步骤 3: 运行测试确认通过
```

---

# Agent 6: FactorStage（依赖 Agent 2 的 Pipeline）

```
Task: 实现 FactorStage

前置: 确保 /Users/mac/Documents/ai/pi-investment/quantsys-v2/core/pipeline.py 已存在。

## 步骤 1: 先写测试
创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/tests/test_quant_stages.py

```python
import pytest
from quant.stages.factor_stage import FactorStage

class TestFactorStage:
    def test_factor_stage_requires_symbol(self):
        stage = FactorStage(name="factors")
        with pytest.raises(ValueError):
            stage.validate_input({"klines": []})

    def test_factor_stage_requires_klines(self):
        stage = FactorStage(name="factors")
        with pytest.raises(ValueError):
            stage.validate_input({"symbol": "600519"})

    def test_factor_stage_valid_input(self):
        stage = FactorStage(name="factors")
        assert stage.validate_input({"symbol": "600519", "klines": []}) == True

    def test_factor_stage_process(self):
        stage = FactorStage(name="factors")
        result = stage.process({
            "symbol": "600519",
            "klines": [
                {"date": "2026-05-20", "close": 100.0},
                {"date": "2026-05-21", "close": 110.0},
            ]
        })
        assert "factors" in result
        assert result["symbol"] == "600519"
        assert len(result["klines"]) == 2
```

运行确认失败:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/test_quant_stages.py -v
```

## 步骤 2: 实现

创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/quant/stages/factor_stage.py

```python
from typing import Dict, Any
from core.pipeline import PipelineStage
import logging

logger = logging.getLogger(__name__)

class FactorStage(PipelineStage):
    def __init__(self, name: str = "factors"):
        super().__init__(name)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        if "symbol" not in data:
            raise ValueError("Missing required field: symbol")
        if "klines" not in data:
            raise ValueError("Missing required field: klines")
        return True

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = data["symbol"]
        klines = data["klines"]
        logger.info(f"Calculating factors for {symbol}")
        # TODO: 从旧项目迁移因子计算逻辑
        factors = {"ma5": 105.0, "ma20": 100.0, "rsi": 65.0, "macd": 2.5}
        result = data.copy()
        result["factors"] = factors
        return result
```

## 步骤 3: 运行测试确认通过
```

---

# Agent 7: 集成测试（等 Agent 1-6 全部完成后再跑）

```
Task: 编写端到端集成测试

前置: 确保以下文件全部存在:
- core/pipeline.py (QuantPipeline)
- core/base_repository.py (BaseRepository)
- repositories/stock_repository.py (StockRepository)
- quant/stages/factor_stage.py (FactorStage)

创建 /Users/mac/Documents/ai/pi-investment/quantsys-v2/tests/test_integration.py

```python
import pytest
from core.pipeline import QuantPipeline
from quant.stages.factor_stage import FactorStage
from repositories.stock_repository import StockRepository

class TestEndToEndFlow:
    def test_repository_to_pipeline_flow(self):
        class MockDB:
            def query_one(self, query, *params):
                return {"symbol": "600519", "name": "贵州茅台", "market": "A"}
        repo = StockRepository(db_connection=MockDB())
        stock = repo.get_by_symbol("600519")
        assert stock is not None
        assert stock["name"] == "贵州茅台"
        pipeline = QuantPipeline(name="test_flow")
        pipeline.add_stage(FactorStage(name="factors"))
        result = pipeline.run({
            "symbol": stock["symbol"],
            "klines": [{"date": "2026-05-20", "close": 100.0}]
        })
        assert "factors" in result
        assert result["symbol"] == "600519"

    def test_full_pipeline_chaining(self):
        pipeline = QuantPipeline(name="full_test")
        pipeline.add_stage(FactorStage(name="factors"))
        result = pipeline.run({
            "symbol": "000001",
            "klines": [{"date": "2026-05-20", "close": 50.0}]
        })
        assert result["factors"]["ma5"] == 105.0
```

然后运行全部测试:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/ -v
```

预期: 所有测试通过。
```

---

# Agent 8: 文档（最后跑）

```
Task: 更新 README 和架构文档

确认所有测试通过后:
1. 更新 quantsys-v2/README.md，描述项目结构和运行方式
2. 创建 quantsys-v2/ARCHITECTURE.md，描述 Pipeline + Repository 架构

内容简洁，不超过 30 行每个文件。
```
