"""`domain.quantlib.core.base_calculator` —— 转发壳（2026-10-01 · REQ-261001145152-3982 t-3f2444）

## 为什么变成转发壳

本文件此前**自己定义了一个 `BaseCalculator` 类**（327 行），而
`domain/quantlib/base_calculator.py` 里还有**另一个同名但实现不同的** `BaseCalculator`
（501 行）。两者是**不同的类对象**，于是：

- 跨模块的 `isinstance(x, BaseCalculator)` 静默为 False（不报错、只是判断错）；
- `except SomeError` 的捕获面按导入路径而异（同一个计算走不同路径会得到不同结果）；
- 修 bug 时"改了一处、另一处照旧"——审计报告 §2 记录的复发源。

2026-10-01 用户裁决：**以 501 行版为唯一正本**（它是功能超集：多出
`calculate` / `validate_method` / `CalculationResult` / `cache_result` /
`_round_result` / `_sanitize_for_json` / `_handle_missing_data` 等，
其中 `.calculate(` 全仓 86 处、`validate_method` 22 处、`CalculationResult` 12 处在用），
本文件改为只做转发，**不再定义类**。

## 保留的对外符号（17 个消费方在用的全部名字）

`BaseCalculator` / `CalculatorFactory` / `CalculationResult` / `validate_inputs` /
`timing_decorator` / `cache_result` / `handle_calculation_error`

> `handle_calculation_error` 的**实现**已被逐字搬入正本（另有同名函数 2 份、实现不同：
> `core/exceptions.py` 相似度 0.53、`domain/quantlib/exceptions.py` 相似度 0.31）；
> 这里转发的是消费方原先真正调用的那一份，确保零行为变化。
>
> 原有、但**全仓无人调用**的 `_validate_positive_number` 方法随 327 行版一并移除
> （实测：仅有无关注释与无关模块的同名方法命中）。
"""
from domain.quantlib.base_calculator import (  # noqa: F401
    BaseCalculator,
    CalculatorFactory,
    CalculationResult,
    cache_result,
    handle_calculation_error,
    timing_decorator,
    validate_inputs,
)

__all__ = [
    "BaseCalculator",
    "CalculatorFactory",
    "CalculationResult",
    "validate_inputs",
    "timing_decorator",
    "cache_result",
    "handle_calculation_error",
]
