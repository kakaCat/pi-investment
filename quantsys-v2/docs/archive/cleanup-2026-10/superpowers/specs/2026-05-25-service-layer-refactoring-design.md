# QuantSys V2 服务层重构设计

**日期**: 2026-05-25  
**作者**: Claude (Kiro)  
**状态**: 设计阶段

## 1. 背景与问题

### 1.1 当前问题

QuantSys V2 项目的 `services/` 目录存在以下问题：

1. **文件过大**：多个服务文件超过 500 行，最大达到 1196 行
   - `risk_service.py`: 1196 行
   - `strategy_code_service.py`: 812 行
   - `data_service.py`: 690 行
   - `execution_service.py`: 671 行

2. **职责混杂**：单个文件包含多个不相关的职责
   - `risk_service.py` 包含事前风控、实盘风控、融资融券、合规检查等多个领域
   - `strategy_code_service.py` 混合了策略管理、执行、验证、回测等逻辑

3. **代码重复**：多处存在重复的模式
   - 数据获取逻辑重复
   - 验证逻辑重复
   - 结果格式化重复
   - 错误处理重复

4. **难以维护**：大文件导致
   - 难以快速定位代码
   - 修改影响范围不明确
   - 测试覆盖困难
   - 新人上手成本高

### 1.2 重构目标

1. **拆分大文件**：将 4 个大文件拆分为职责单一的小模块（< 500 行）
2. **建立分层架构**：明确编排层、执行层、工具层的职责边界
3. **消除重复代码**：抽象共享工具和基类
4. **统一代码规范**：建立长期可维护的组织规范
5. **同步更新调用方**：API、CLI、测试文件同步调整

### 1.3 设计原则

- **职责单一原则**：每个文件只做一件事
- **500 行软上限**：超过 500 行视为代码异味信号
- **按业务域分组**：使用子目录组织相关模块
- **调用层级分离**：编排逻辑与执行逻辑分离
- **直接迁移策略**：删除旧文件，全局更新导入，不保留兼容层
- **DRY 原则**：识别重复模式，抽象为共享工具

## 2. 架构设计

### 2.1 整体架构

```
services/
├── common/                        # 共享工具层（新增）
│   ├── __init__.py
│   ├── base_checker.py           # 检查器基类
│   ├── base_aggregator.py        # 聚合器基类
│   ├── base_algo.py              # 算法基类
│   ├── result_types.py           # 标准化结果类型
│   ├── decorators.py             # 通用装饰器
│   ├── validators.py             # 通用验证器
│   └── exceptions.py             # 业务异常定义
├── risk/                          # 风险管理域（重构）
│   ├── __init__.py
│   ├── orchestrator.py           # RiskOrchestrator 编排类
│   ├── checkers/                 # 检查器执行层
│   │   ├── __init__.py
│   │   ├── position_checker.py
│   │   ├── portfolio_checker.py
│   │   ├── market_checker.py
│   │   ├── trading_checker.py
│   │   ├── margin_checker.py
│   │   └── compliance_checker.py
│   └── utils.py                  # 域内工具函数
├── strategy/                      # 策略管理域（重构）
│   ├── __init__.py
│   ├── manager.py                # StrategyManager
│   ├── executor.py               # StrategyExecutor
│   ├── validator.py              # CodeValidator 封装
│   ├── backtest_runner.py        # 回测执行
│   └── utils.py                  # 域内工具函数
├── data/                          # 数据服务域（重构）
│   ├── __init__.py
│   ├── service.py                # DataService Facade
│   ├── aggregators/              # 跨表查询执行层
│   │   ├── __init__.py
│   │   ├── stock_aggregator.py
│   │   ├── portfolio_aggregator.py
│   │   ├── backtest_aggregator.py
│   │   └── signal_aggregator.py
│   └── cache_helper.py           # 缓存辅助
├── execution/                     # 订单执行域（重构）
│   ├── __init__.py
│   ├── orchestrator.py           # OrderExecutor
│   ├── algos/                    # 算法执行层
│   │   ├── __init__.py
│   │   ├── base_algo.py
│   │   ├── twap.py
│   │   ├── vwap.py
│   │   └── iceberg.py
│   ├── broker_adapter.py         # Broker 适配器
│   └── utils.py                  # 域内工具函数
├── order_service.py               # 保持（652行，职责单一）
├── position_service.py            # 保持（562行）
└── trade_service.py               # 保持（277行）
```

### 2.2 架构分层

**三层架构**：

1. **编排层（Orchestrator）**
   - 职责：协调多个执行层模块，实现完整业务流程
   - 示例：`RiskOrchestrator.pre_trade_check()` 协调多个 checker
   - 特点：轻量级，主要是流程控制和结果聚合

2. **执行层（Executor/Checker/Aggregator）**
   - 职责：具体的业务逻辑实现
   - 示例：`PositionChecker.check()` 实现仓位检查逻辑
   - 特点：独立、可测试、可复用

3. **工具层（Utils/Common）**
   - 职责：可复用的辅助函数和基类
   - 示例：`BaseChecker` 基类、`@cached` 装饰器
   - 特点：无状态、纯函数、高复用

**依赖规则**：
- 编排层 → 执行层 + 工具层
- 执行层 → 工具层
- 工具层 → 无依赖
- 禁止反向依赖和循环依赖

### 2.3 命名规范

- **编排类**：`{Domain}Orchestrator`（如 `RiskOrchestrator`）
- **管理类**：`{Domain}Manager`（如 `StrategyManager`）
- **执行类**：`{Domain}Executor`（如 `OrderExecutor`）
- **检查器**：`{Feature}Checker`（如 `PositionChecker`）
- **聚合器**：`{Feature}Aggregator`（如 `StockAggregator`）
- **算法类**：`{Algo}Algorithm` 或简写（如 `TWAPAlgo`）

## 3. 详细设计

### 3.1 共享工具层（services/common/）

#### 3.1.1 base_checker.py - 检查器基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class CheckResult:
    """统一的检查结果"""
    passed: bool
    rule_name: str
    severity: str  # 'error' | 'warning'
    message: str
    metadata: Dict[str, Any] = None

class BaseChecker(ABC):
    """所有检查器的基类"""
    
    @abstractmethod
    def check(self, ds, context: Dict[str, Any]) -> CheckResult:
        """执行检查逻辑
        
        Args:
            ds: DataService 实例
            context: 检查上下文（symbol, action, quantity, price 等）
        
        Returns:
            CheckResult: 检查结果
        """
        pass
    
    def _build_result(self, passed: bool, message: str, 
                     severity: str = 'error', **kwargs) -> CheckResult:
        """构建标准化结果"""
        return CheckResult(
            passed=passed,
            rule_name=self.__class__.__name__,
            severity=severity,
            message=message,
            metadata=kwargs
        )
```

**设计要点**：
- 统一接口：所有 checker 实现 `check()` 方法
- 标准化结果：使用 `CheckResult` 数据类
- 辅助方法：`_build_result()` 简化结果构建

#### 3.1.2 decorators.py - 通用装饰器

```python
from functools import wraps
import logging
import time

def cached(namespace: str, key_fn, ttl: int = 300):
    """缓存装饰器
    
    Args:
        namespace: 缓存命名空间
        key_fn: 生成缓存 key 的函数
        ttl: 过期时间（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self, '_cache') and self._cache:
                key = key_fn(*args, **kwargs)
                cached_value = self._cache.get(namespace, key)
                if cached_value:
                    return cached_value
                result = func(self, *args, **kwargs)
                self._cache.set(namespace, key, result, ttl=ttl)
                return result
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

def handle_broker_errors(func):
    """Broker 错误处理装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BrokerConnectionError as e:
            return ExecutionResult(success=False, error=f"Broker连接失败: {e}")
        except BrokerAPIError as e:
            return ExecutionResult(success=False, error=f"Broker API错误: {e}")
        except Exception as e:
            return ExecutionResult(success=False, error=f"未知错误: {e}")
    return wrapper

def validate_params(*param_validators):
    """参数验证装饰器
    
    Usage:
        @validate_params(validate_symbol, validate_quantity)
        def buy_stock(symbol, quantity):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for validator in param_validators:
                validator(*args, **kwargs)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def timing_decorator(func):
    """性能计时装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logging.debug(f"{func.__name__} 执行时间: {elapsed:.3f}s")
        return result
    return wrapper
```

**设计要点**：
- 横切关注点：缓存、错误处理、验证、计时
- 可组合：多个装饰器可以叠加使用
- 保持函数签名：使用 `@wraps` 保留元数据

#### 3.1.3 result_types.py - 标准化结果类型

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class CheckResult:
    """风控检查结果"""
    passed: bool
    rule_name: str
    severity: str  # 'error' | 'warning'
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionResult:
    """订单执行结果"""
    success: bool
    order_id: str = ""
    algo: str = "market"
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    slippage_bps: float = 0.0
    execution_time_seconds: float = 0.0
    error: Optional[str] = None
    slices: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StrategyResult:
    """策略执行结果"""
    success: bool
    strategy_id: int
    signals: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AggregationResult:
    """数据聚合结果"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    cache_hit: bool = False
    query_time_seconds: float = 0.0
```

**设计要点**：
- 使用 dataclass 减少样板代码
- 统一的成功/失败标志
- 可选的错误信息
- 扩展性：metadata 字段用于附加信息

#### 3.1.4 validators.py - 通用验证器

```python
from datetime import datetime

def validate_symbol(symbol: str):
    """验证股票代码格式"""
    if not symbol or not isinstance(symbol, str):
        raise ValueError("股票代码不能为空")
    if not symbol.endswith(('.SH', '.SZ', '.BJ')):
        raise ValueError(f"无效的股票代码格式: {symbol}")

def validate_quantity(quantity: int):
    """验证数量"""
    if quantity <= 0:
        raise ValueError("数量必须大于0")
    if quantity % 100 != 0:
        raise ValueError("A股数量必须是100的整数倍")

def validate_action(action: str):
    """验证交易方向"""
    if action not in ('buy', 'sell'):
        raise ValueError(f"无效的交易方向: {action}，必须是 'buy' 或 'sell'")

def validate_date_range(start_date: str, end_date: str):
    """验证日期范围"""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"日期格式错误: {e}")
    
    if start > end:
        raise ValueError("开始日期不能晚于结束日期")

def validate_price(price: float):
    """验证价格"""
    if price <= 0:
        raise ValueError("价格必须大于0")

def validate_broker_id(broker_id: str):
    """验证券商ID"""
    if not broker_id or not isinstance(broker_id, str):
        raise ValueError("券商ID不能为空")
```

**设计要点**：
- 纯函数：无副作用，只做验证
- 失败即抛异常：使用 `raise ValueError`
- 清晰的错误信息：便于调试


### 3.2 风险管理域（services/risk/）

**原文件**: risk_service.py (1196行)  
**拆分后**: 7个文件，每个 < 200行

### 3.3 策略管理域（services/strategy/）

**原文件**: strategy_code_service.py (812行)  
**拆分后**: 5个文件，每个 < 300行

### 3.4 数据服务域（services/data/）

**原文件**: data_service.py (690行)  
**拆分后**: 6个文件，每个 < 200行

### 3.5 订单执行域（services/execution/）

**原文件**: execution_service.py (671行)  
**拆分后**: 7个文件，每个 < 200行

## 4. 迁移策略

### 4.1 迁移步骤（5天计划）

**Day 1**: 准备工作 + 补充测试  
**Day 2**: 共享工具层 + data 服务  
**Day 3**: execution + strategy 服务  
**Day 4**: risk 服务 + 调用方更新  
**Day 5**: 测试与合并

### 4.2 成功标准

- 所有现有测试通过
- 新增测试覆盖率 > 80%
- 所有文件 < 500 行
- API/CLI 功能无变化

## 5. 代码组织规范（写入 CLAUDE.md）

### 5.1 文件大小与职责

- 单个文件不超过 500 行（软上限）
- 每个文件只承担一个明确的职责

### 5.2 架构分层原则

**三层架构**:
1. 编排层（Orchestrator）：协调多个模块
2. 执行层（Executor/Checker/Aggregator）：具体业务逻辑
3. 工具层（Utils/Common）：可复用辅助函数

### 5.3 重复代码处理

**抽象位置**:
- 跨域共享 → services/common/
- 域内共享 → services/{domain}/utils.py
- 单文件内共享 → 私有函数

### 5.4 重构检查清单

- 是否识别并消除了重复代码？
- 是否遵循了单一职责原则？
- 是否所有文件 < 500 行？
- 是否有清晰的架构分层？

## 6. 总结

**重构收益**: 文件大小降至 < 500 行，代码职责清晰，消除重复代码

**关键设计决策**: 按业务域分组、调用层级分离、直接迁移策略、共享工具层、同步重构

---

**设计完成日期**: 2026-05-25  
**预计实施时间**: 5 天  
**风险等级**: 中等

