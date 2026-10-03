> ⚠️ **归档说明（2026-10-02 · REQ-261001145152-3982 审查）**：本指南是 **2026-09-06 的一次性扫描报告**，
> 已从仓根归入 。文中引用的 
> **已于本次审查删除**（零外部引用、从未接线 —— 见提交 3dbe034c 同批的删除记录），
> 故文中与之相关的条目只作**历史快照**看待，不代表当前代码结构。

# 高复杂度函数重构指南

**扫描时间**: 2026-09-06
**发现问题**: 219 个函数复杂度 > 15

## 优先级分布

- 🔴 P0 (>30): 28 个
- 🟡 P1 (20-30): 73 个
- 🟢 P2 (15-20): 118 个

## Top 20 最高复杂度函数

| 函数 | 复杂度 | 文件 | 行 |
|------|--------|------|----|
| `generate` | 91 | `application/services/core_plan_service.py` | 513 |
| `register_routes` | 85 | `adapters/inbound/fastapi_app/main.py` | 628 |
| `main` | 72 | `scripts/compare_strategies.py` | 32 |
| `validate_config` | 55 | `domain/quantlib/qlib/config.py` | 197 |
| `upsert_chain` | 50 | `adapters/outbound/repositories/industry_chain_repository.py` | 235 |
| `validate_config` | 49 | `domain/quantlib/finrl/config.py` | 170 |
| `execute_trade` | 49 | `application/services/account_trading_service.py` | 151 |
| `ml_predict` | 43 | `adapters/inbound/fastapi_app/routes/ml_async.py` | 210 |
| `run_pe_mean_reversion_backtest` | 40 | `adapters/shared/backtest_helpers.py` | 232 |
| `risk_check` | 40 | `adapters/inbound/fastapi_app/routes/risk_async.py` | 43 |
| `migrate_file` | 38 | `tools/migrate_datasource_imports.py` | 108 |
| `run_pb_mean_reversion_backtest` | 38 | `adapters/shared/backtest_helpers.py` | 545 |
| `_calculate_indicators` | 37 | `application/services/strategy_code_service.py` | 1729 |
| `scan_signals` | 37 | `adapters/inbound/fastapi_app/routes/signals_async.py` | 74 |
| `run_backtest` | 37 | `adapters/inbound/fastapi_app/routes/analysis_async.py` | 29 |
| `ml_train` | 37 | `adapters/inbound/fastapi_app/routes/ml_async.py` | 32 |
| `sanitize_for_json` | 34 | `adapters/shared/json_helpers.py` | 17 |
| `_job_watch_rule_health` | 34 | `adapters/inbound/fastapi_app/daily_jobs/health.py` | 28 |
| `screen_stocks` | 33 | `application/services/stock_screening_service.py` | 39 |
| `validate_custom_prices` | 33 | `application/services/strategy_code_validator.py` | 196 |

## 重构建议详情

### 1. generate (复杂度 91)

**文件**: `application/services/core_plan_service.py:513`

**建议**:

1. 提取验证逻辑: 发现 24 个 if 语句，可以提取为 Validator 类
2. 提取循环逻辑: 发现 17 个 for 循环，可以提取为独立方法
3. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
4. 严重过高 (复杂度 91): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: generate

原复杂度: 91
目标复杂度: < 15

重构建议:
1. 提取验证逻辑: 发现 24 个 if 语句，可以提取为 Validator 类
2. 提取循环逻辑: 发现 17 个 for 循环，可以提取为独立方法
3. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
4. 严重过高 (复杂度 91): 必须拆分为多个小方法，目标每个 < 15

"""

class GenerateProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def generate_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 91
    """
    processor = GenerateProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 2. register_routes (复杂度 85)

**文件**: `adapters/inbound/fastapi_app/main.py:628`

**建议**:

1. 严重过高 (复杂度 85): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: register_routes

原复杂度: 85
目标复杂度: < 15

重构建议:
1. 严重过高 (复杂度 85): 必须拆分为多个小方法，目标每个 < 15

"""

class RegisterRoutesProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def register_routes_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 85
    """
    processor = RegisterRoutesProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 3. main (复杂度 72)

**文件**: `scripts/compare_strategies.py:32`

**建议**:

1. 提取循环逻辑: 发现 9 个 for 循环，可以提取为独立方法
2. 严重过高 (复杂度 72): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: main

原复杂度: 72
目标复杂度: < 15

重构建议:
1. 提取循环逻辑: 发现 9 个 for 循环，可以提取为独立方法
2. 严重过高 (复杂度 72): 必须拆分为多个小方法，目标每个 < 15

"""

class MainProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def main_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 72
    """
    processor = MainProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 4. validate_config (复杂度 55)

**文件**: `domain/quantlib/qlib/config.py:197`

**建议**:

1. 提取验证逻辑: 发现 37 个 if 语句，可以提取为 Validator 类
2. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
3. 严重过高 (复杂度 55): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: validate_config

原复杂度: 55
目标复杂度: < 15

重构建议:
1. 提取验证逻辑: 发现 37 个 if 语句，可以提取为 Validator 类
2. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
3. 严重过高 (复杂度 55): 必须拆分为多个小方法，目标每个 < 15

"""

class ValidateConfigProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def validate_config_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 55
    """
    processor = ValidateConfigProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 5. upsert_chain (复杂度 50)

**文件**: `adapters/outbound/repositories/industry_chain_repository.py:235`

**建议**:

1. 提取验证逻辑: 发现 9 个 if 语句，可以提取为 Validator 类
2. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
3. 严重过高 (复杂度 50): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: upsert_chain

原复杂度: 50
目标复杂度: < 15

重构建议:
1. 提取验证逻辑: 发现 9 个 if 语句，可以提取为 Validator 类
2. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
3. 严重过高 (复杂度 50): 必须拆分为多个小方法，目标每个 < 15

"""

class UpsertChainProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def upsert_chain_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 50
    """
    processor = UpsertChainProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 6. validate_config (复杂度 49)

**文件**: `domain/quantlib/finrl/config.py:170`

**建议**:

1. 提取验证逻辑: 发现 33 个 if 语句，可以提取为 Validator 类
2. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
3. 严重过高 (复杂度 49): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: validate_config

原复杂度: 49
目标复杂度: < 15

重构建议:
1. 提取验证逻辑: 发现 33 个 if 语句，可以提取为 Validator 类
2. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
3. 严重过高 (复杂度 49): 必须拆分为多个小方法，目标每个 < 15

"""

class ValidateConfigProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def validate_config_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 49
    """
    processor = ValidateConfigProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 7. execute_trade (复杂度 49)

**文件**: `application/services/account_trading_service.py:151`

**建议**:

1. 提取验证逻辑: 发现 28 个 if 语句，可以提取为 Validator 类
2. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
3. 严重过高 (复杂度 49): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: execute_trade

原复杂度: 49
目标复杂度: < 15

重构建议:
1. 提取验证逻辑: 发现 28 个 if 语句，可以提取为 Validator 类
2. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
3. 严重过高 (复杂度 49): 必须拆分为多个小方法，目标每个 < 15

"""

class ExecuteTradeProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def execute_trade_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 49
    """
    processor = ExecuteTradeProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 8. ml_predict (复杂度 43)

**文件**: `adapters/inbound/fastapi_app/routes/ml_async.py:210`

**建议**:

1. 提取验证逻辑: 发现 19 个 if 语句，可以提取为 Validator 类
2. 提取循环逻辑: 发现 6 个 for 循环，可以提取为独立方法
3. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
4. 严重过高 (复杂度 43): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: ml_predict

原复杂度: 43
目标复杂度: < 15

重构建议:
1. 提取验证逻辑: 发现 19 个 if 语句，可以提取为 Validator 类
2. 提取循环逻辑: 发现 6 个 for 循环，可以提取为独立方法
3. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
4. 严重过高 (复杂度 43): 必须拆分为多个小方法，目标每个 < 15

"""

class MlPredictProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def ml_predict_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 43
    """
    processor = MlPredictProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 9. run_pe_mean_reversion_backtest (复杂度 40)

**文件**: `adapters/shared/backtest_helpers.py:232`

**建议**:

1. 提取验证逻辑: 发现 25 个 if 语句，可以提取为 Validator 类
2. 提取循环逻辑: 发现 7 个 for 循环，可以提取为独立方法
3. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
4. 严重过高 (复杂度 40): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: run_pe_mean_reversion_backtest

原复杂度: 40
目标复杂度: < 15

重构建议:
1. 提取验证逻辑: 发现 25 个 if 语句，可以提取为 Validator 类
2. 提取循环逻辑: 发现 7 个 for 循环，可以提取为独立方法
3. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
4. 严重过高 (复杂度 40): 必须拆分为多个小方法，目标每个 < 15

"""

class RunPeMeanReversionBacktestProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def run_pe_mean_reversion_backtest_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 40
    """
    processor = RunPeMeanReversionBacktestProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

### 10. risk_check (复杂度 40)

**文件**: `adapters/inbound/fastapi_app/routes/risk_async.py:43`

**建议**:

1. 提取验证逻辑: 发现 10 个 if 语句，可以提取为 Validator 类
2. 提取循环逻辑: 发现 3 个 for 循环，可以提取为独立方法
3. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
4. 严重过高 (复杂度 40): 必须拆分为多个小方法，目标每个 < 15

**重构模板**:

```python
"""
重构: risk_check

原复杂度: 40
目标复杂度: < 15

重构建议:
1. 提取验证逻辑: 发现 10 个 if 语句，可以提取为 Validator 类
2. 提取循环逻辑: 发现 3 个 for 循环，可以提取为独立方法
3. 使用策略模式: 大量 if-elif-else 分支可以用策略模式替代
4. 严重过高 (复杂度 40): 必须拆分为多个小方法，目标每个 < 15

"""

class RiskCheckProcessor:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def risk_check_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: 40
    """
    processor = RiskCheckProcessor(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({'error': error}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({'error': str(e)}, 500)

```

---

