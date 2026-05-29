# 基本面因子模块实施计划 - 阶段2: 计算层

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现FundamentalFactorCalculator基类和三个因子计算器(ValueFactors, QualityFactors, GrowthFactors)

**Architecture:** 基类提供通用计算方法(分位数、增速、CAGR),三个子类实现具体因子计算逻辑

**Tech Stack:** Python 3.13, NumPy, BaseCalculator框架

---

## 文件结构

**新建文件:**
- `quantsys-v2/quantlib/factors/fundamental_base.py` - 基本面因子计算器基类
- `quantsys-v2/quantlib/factors/value.py` - 估值因子
- `quantsys-v2/quantlib/factors/quality.py` - 质量因子
- `quantsys-v2/quantlib/factors/growth.py` - 成长因子
- `quantsys-v2/tests/test_fundamental_factors.py` - 因子计算器测试

**修改文件:**
- `quantsys-v2/quantlib/factors/__init__.py` - 导出新的因子类
- `quantsys-v2/quantlib/core/exceptions.py` - 添加财务数据异常类

---

## Task 1: 添加财务数据异常类

**Files:**
- Modify: `quantsys-v2/quantlib/core/exceptions.py`

- [ ] **Step 1: 编写异常类测试**

```python
# tests/test_fundamental_factors.py
import pytest
from quantlib.core.exceptions import (
    InsufficientFinancialDataError,
    FinancialDataSyncError,
    InvalidFinancialDataError
)


class TestFinancialDataExceptions:
    """财务数据异常测试"""
    
    def test_insufficient_financial_data_error(self):
        """测试数据不足异常"""
        error = InsufficientFinancialDataError(
            symbol='600519.SH',
            required_periods=5,
            actual_periods=3
        )
        
        assert error.symbol == '600519.SH'
        assert error.required_periods == 5
        assert error.actual_periods == 3
        assert '600519.SH' in str(error)
        assert '需要至少5期数据' in str(error)
        assert '实际只有3期' in str(error)
    
    def test_financial_data_sync_error(self):
        """测试数据同步异常"""
        error = FinancialDataSyncError(
            symbol='600519.SH',
            table_type='income_statements',
            reason='网络超时'
        )
        
        assert error.symbol == '600519.SH'
        assert error.table_type == 'income_statements'
        assert error.reason == '网络超时'
        assert 'income_statements同步失败' in str(error)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd quantsys-v2 && pytest tests/test_fundamental_factors.py::TestFinancialDataExceptions -v`

Expected: FAIL with "ImportError: cannot import name 'InsufficientFinancialDataError'"

- [ ] **Step 3: 实现异常类**

```python
# quantlib/core/exceptions.py (追加)

class FinancialDataError(Exception):
    """财务数据相关错误基类"""
    pass


class InsufficientFinancialDataError(FinancialDataError):
    """财务数据不足错误"""
    
    def __init__(self, symbol: str, required_periods: int, actual_periods: int):
        self.symbol = symbol
        self.required_periods = required_periods
        self.actual_periods = actual_periods
        super().__init__(
            f"{symbol}: 需要至少{required_periods}期数据,实际只有{actual_periods}期"
        )


class FinancialDataSyncError(FinancialDataError):
    """财务数据同步错误"""
    
    def __init__(self, symbol: str, table_type: str, reason: str):
        self.symbol = symbol
        self.table_type = table_type
        self.reason = reason
        super().__init__(
            f"{symbol}: {table_type}同步失败 - {reason}"
        )


class InvalidFinancialDataError(FinancialDataError):
    """无效的财务数据"""
    
    def __init__(self, symbol: str, field: str, value, reason: str):
        self.symbol = symbol
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(
            f"{symbol}: 字段{field}的值{value}无效 - {reason}"
        )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd quantsys-v2 && pytest tests/test_fundamental_factors.py::TestFinancialDataExceptions -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add quantlib/core/exceptions.py tests/test_fundamental_factors.py
git commit -m "feat: add financial data exception classes

- InsufficientFinancialDataError: 数据不足异常
- FinancialDataSyncError: 数据同步异常
- InvalidFinancialDataError: 无效数据异常"
```

---

## Task 2: 实现FundamentalFactorCalculator基类 - 数据验证

**Files:**
- Create: `quantsys-v2/quantlib/factors/fundamental_base.py`
- Modify: `quantsys-v2/tests/test_fundamental_factors.py`

- [ ] **Step 1: 编写数据验证测试**

```python
# tests/test_fundamental_factors.py (追加)

from quantlib.factors.fundamental_base import FundamentalFactorCalculator
from quantlib.core.exceptions import DataValidationError, InsufficientDataError


class TestFundamentalFactorCalculator:
    """基本面因子计算器基类测试"""
    
    @pytest.fixture
    def calculator(self):
        return FundamentalFactorCalculator()
    
    def test_validate_financial_data_success(self, calculator):
        """测试财务数据验证 - 成功"""
        data = [
            {'symbol': '600519.SH', 'revenue': 100000000000.0},
            {'symbol': '600519.SH', 'revenue': 110000000000.0}
        ]
        
        # 不应抛出异常
        calculator._validate_financial_data(
            data,
            min_length=2,
            required_fields=['symbol', 'revenue']
        )
    
    def test_validate_financial_data_insufficient(self, calculator):
        """测试财务数据验证 - 数据不足"""
        data = [{'symbol': '600519.SH', 'revenue': 100000000000.0}]
        
        with pytest.raises(InsufficientDataError):
            calculator._validate_financial_data(data, min_length=2)
    
    def test_validate_financial_data_missing_field(self, calculator):
        """测试财务数据验证 - 缺少字段"""
        data = [{'symbol': '600519.SH'}]
        
        with pytest.raises(DataValidationError):
            calculator._validate_financial_data(
                data,
                required_fields=['symbol', 'revenue']
            )
    
    def test_validate_period_type_success(self, calculator):
        """测试期间类型验证 - 成功"""
        calculator._validate_period_type('Q')
        calculator._validate_period_type('Y')
    
    def test_validate_period_type_invalid(self, calculator):
        """测试期间类型验证 - 无效"""
        with pytest.raises(DataValidationError):
            calculator._validate_period_type('M')
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd quantsys-v2 && pytest tests/test_fundamental_factors.py::TestFundamentalFactorCalculator -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'quantlib.factors.fundamental_base'"

- [ ] **Step 3: 实现基类 - 数据验证部分**

```python
# quantlib/factors/fundamental_base.py
"""
基本面因子计算器基类

提供:
- 财务数据验证
- 分位数计算
- 同比增速计算
- 统一结果格式化
"""
from typing import Optional, List, Dict, Any
import numpy as np
from quantlib.core.base_calculator import BaseCalculator
from quantlib.core.exceptions import DataValidationError, InsufficientDataError


class FundamentalFactorCalculator(BaseCalculator):
    """
    基本面因子计算器基类
    
    所有基本面因子应继承此类
    """
    
    def __init__(self, precision: int = 4):
        super().__init__(precision)
    
    # ========== 数据验证 ==========
    
    def _validate_financial_data(
        self,
        data: List[Dict[str, Any]],
        min_length: Optional[int] = None,
        required_fields: Optional[List[str]] = None
    ) -> None:
        """
        验证财务数据格式和内容
        
        Args:
            data: 财务数据列表
            min_length: 最小数据长度
            required_fields: 必需字段列表
        
        Raises:
            DataValidationError: 数据格式无效
            InsufficientDataError: 数据长度不足
        """
        if not data:
            raise DataValidationError("财务数据不能为空", "data")
        
        if not isinstance(data, list):
            raise DataValidationError("财务数据必须是列表", "data")
        
        # 检查最小长度
        if min_length is not None and len(data) < min_length:
            raise InsufficientDataError(
                required=min_length,
                actual=len(data),
                message=f"需要至少{min_length}条数据,实际只有{len(data)}条"
            )
        
        # 检查必需字段
        if required_fields:
            first_item = data[0]
            if not isinstance(first_item, dict):
                raise DataValidationError("财务数据项必须是字典", "data")
            
            missing_fields = [f for f in required_fields if f not in first_item]
            if missing_fields:
                raise DataValidationError(
                    f"缺少必需字段: {', '.join(missing_fields)}",
                    "data"
                )
    
    def _validate_period_type(self, period_type: str) -> None:
        """
        验证期间类型
        
        Args:
            period_type: 'Q' (季度) 或 'Y' (年度)
        
        Raises:
            DataValidationError: 期间类型无效
        """
        if period_type not in ['Q', 'Y']:
            raise DataValidationError(
                f"期间类型必须是'Q'或'Y',实际为'{period_type}'",
                "period_type"
            )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd quantsys-v2 && pytest tests/test_fundamental_factors.py::TestFundamentalFactorCalculator -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add quantlib/factors/fundamental_base.py tests/test_fundamental_factors.py
git commit -m "feat: implement FundamentalFactorCalculator base class - validation

- _validate_financial_data: 验证财务数据格式和内容
- _validate_period_type: 验证期间类型"
```

---

## 阶段2待续

由于计划内容较长,阶段2的剩余任务包括:
- Task 3: 实现分位数计算方法
- Task 4: 实现增速计算方法(YoY, QoQ, CAGR)
- Task 5: 实现数据提取方法
- Task 6-8: 实现ValueFactors, QualityFactors, GrowthFactors

完整的阶段2计划将在下一个文件中继续。

**下一步:** 创建阶段2完整计划或开始执行当前任务?
