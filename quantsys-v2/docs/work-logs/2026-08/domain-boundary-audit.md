# 领域分界审计报告

**审计时间**: 2026-08-23  
**审计范围**: quantsys-v2/domain/  
**审计目标**: 检查领域边界清晰度、架构分层合规性

---

## 执行摘要

### 总体评分：⭐⭐⭐ (3/5)

**发现问题**:
- ❌ 3 处架构违规（domain → application）
- ❌ 10 处架构违规（domain → adapters）
- ⚠️ 50 处跨域依赖（部分合理）

**健康度**:
- 9/12 领域无架构违规 ✓ (75%)
- 6/12 领域完全隔离 ✓ (50%)

---

## 1. 架构违规详情

### 1.1 违规类型 I：domain → application（严重）

**影响**: 破坏依赖倒置原则，domain 层不应依赖 application 层

#### backtest (2 处) ❌

```python
# 文件: domain/backtest/engine/backtest_report.py
from application.services.risk_metrics_service import RiskMetricsService

# 文件: domain/backtest/engine/mixins/ml_mixin.py
from application.services.ml_pipeline.predictor import MLPredictor
```

**影响**:
- 回测报告依赖应用层服务
- ML 混入依赖应用层预测器

**建议修复**:
```python
# 方案 1: 依赖注入
class BacktestReport:
    def __init__(self, risk_metrics_service=None):
        self.risk_service = risk_metrics_service

# 方案 2: 下沉到 domain 层
# 将 RiskMetricsService 核心逻辑下沉为 domain 服务
```

#### benchmarks (1 处) ❌

```python
# 文件: domain/benchmarks/run_all_benchmarks.py
from application.services.benchmark_service import BenchmarkService
```

**影响**: 基准测试依赖应用服务

**建议修复**:
```python
# 方案: 通过依赖注入
def run_benchmarks(benchmark_service=None):
    service = benchmark_service or get_default_service()
    # ...
```

---

### 1.2 违规类型 II：domain → adapters（中等严重）

**影响**: domain 层不应直接导入 adapters 实现，应通过端口（接口）

#### backtest (2 处) ⚠️

```python
# 文件: domain/backtest/stages/data_pipeline/storage_stage.py
# 注释中提及 adapters 路径（非实际导入）
"(e.g. KlineORMRepository from adapters.outbound.repositories, "

# 文件: domain/backtest/engine/strategy_runner.py  
"(e.g. StrategyORMRepository from adapters.outbound.repositories, "
```

**影响**: 较小（仅在注释/文档中）

**建议**: 修改注释，只引用端口接口名

#### brokers (6 处) ❌

```python
# 文件: domain/brokers/broker_registry.py
from adapters.outbound.brokers.akshare_broker import AkshareBroker
from adapters.outbound.brokers.ibkr_broker import IBKRBroker
from adapters.outbound.brokers.alpaca_broker import AlpacaBroker

# 文件: domain/brokers/adapters/__init__.py
from adapters.outbound.brokers.akshare_broker import AkshareBroker
from adapters.outbound.brokers.ibkr_broker import IBKRBroker
```

**影响**: 严重 - 直接导入具体适配器实现

**建议修复**:
```python
# 方案 1: 通过配置 + 工厂模式
class BrokerRegistry:
    def __init__(self):
        self._brokers = {}
    
    def register(self, name, broker_class):
        """由 infrastructure 层注入具体实现"""
        self._brokers[name] = broker_class

# 方案 2: 移除 domain/brokers/adapters/
# 这个目录本身就违反了架构（domain 不应有 adapters 子目录）
```

#### memory (2 处) ❌

```python
# 文件: domain/memory/distiller.py
from adapters.outbound.repositories.memory_repository import MemoryRepository
from adapters.outbound.repositories.agent_intelligence_repository import AgentDecision
```

**影响**: 严重 - 直接导入 repository 实现

**建议修复**:
```python
# 方案: 通过端口注入
from domain.ports import IMemoryRepository

class Distiller:
    def __init__(self, memory_repo: IMemoryRepository):
        self.memory_repo = memory_repo
```

---

## 2. 跨域依赖分析

### 2.1 合理的跨域依赖

#### ✅ backtest → ports (3 处)

```python
from domain.ports import IKlineRepository, IFactorRepository, IStrategyRepository
```

**评价**: ✅ 合理 - 通过端口接口依赖，符合依赖倒置原则

#### ✅ backtest → quantlib (1 处)

```python
from domain.quantlib.data_validator import DataValidator
```

**评价**: ✅ 合理 - quantlib 是纯技术工具库，可被其他域使用

#### ✅ factors → quantlib (8 处)

```python
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError
```

**评价**: ✅ 合理 - 继承技术基类和使用共享异常

#### ✅ risk → quantlib (34 处)

```python
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError, DataValidationError
)
```

**评价**: ✅ 合理 - 风险计算继承 quantlib 基类

#### ✅ ports → models (1 处)

```python
from domain.models.market_data import MarketData
```

**评价**: ✅ 合理 - 端口定义引用共享领域模型

---

### 2.2 需要审查的跨域依赖

#### ⚠️ quantlib → backtest/risk/factors (3 处)

```python
# 文件: domain/quantlib/__init__.py（文档字符串中）
from domain.risk import RiskAttributionCalculator
from domain.backtest.engine import BacktestEngine
from domain.factors.library import FactorLibrary
```

**问题**: quantlib 作为技术库，不应依赖业务域

**当前状态**: 仅在文档字符串示例代码中，非实际导入

**建议**: ✅ 可接受（示例代码）

#### ⚠️ benchmarks → quantlib.gpu_acceleration (2 处)

```python
from domain.quantlib.gpu_acceleration.gpu_factors import GPUFactorCalculator
from domain.quantlib.gpu_acceleration.gpu_ml import GPUMLTrainer
```

**问题**: 基准测试应该测试接口，不应硬编码依赖具体实现

**建议**: 通过参数化测试，支持多种实现

---

## 3. 领域隔离度评分

### 完全隔离（无任何依赖）✅

| 领域 | 文件数 | 评分 |
|------|--------|------|
| brokers* | 9 | ⭐⭐⭐ (有 adapters 违规) |
| chan | 14 | ⭐⭐⭐⭐⭐ |
| chip_distribution | 3 | ⭐⭐⭐⭐⭐ |
| memory* | 6 | ⭐⭐⭐ (有 adapters 违规) |
| models | 2 | ⭐⭐⭐⭐⭐ |
| strategies | 9 | ⭐⭐⭐⭐⭐ |

**总计**: 6/12 领域完全隔离

---

### 有合理依赖（ports/quantlib）✅

| 领域 | 依赖 | 评分 |
|------|------|------|
| backtest | quantlib, ports | ⭐⭐⭐⭐ (有 app 违规) |
| factors | quantlib | ⭐⭐⭐⭐⭐ |
| risk | quantlib | ⭐⭐⭐⭐⭐ |
| ports | models | ⭐⭐⭐⭐⭐ |

**总计**: 4/12 领域有合理依赖

---

### 有架构违规 ❌

| 领域 | 违规类型 | 严重性 | 评分 |
|------|----------|--------|------|
| backtest | app (2) + adapters (2) | 严重 | ⭐⭐ |
| benchmarks | app (1) | 中等 | ⭐⭐⭐ |
| brokers | adapters (6) | 严重 | ⭐⭐ |
| memory | adapters (2) | 严重 | ⭐⭐ |

**总计**: 4/12 领域有违规（但 backtest 注释违规影响小）

---

## 4. 依赖方向图

```
application/
    ↑
    ❌ (违规)
    |
domain/
├── backtest ────→ quantlib (✓)
│   ├────────────→ ports (✓)
│   └──❌──────→ application (违规)
│
├── factors ─────→ quantlib (✓)
│
├── risk ────────→ quantlib (✓)
│
├── brokers ──❌→ adapters (违规)
│
├── memory ───❌→ adapters (违规)
│
├── benchmarks ─→ quantlib (✓)
│   └──❌──────→ application (违规)
│
├── ports ───────→ models (✓)
│
└── quantlib (无依赖) ✓
    ↓
infrastructure/
```

**理想依赖方向**:
```
application → domain → infrastructure
```

**当前违规**:
```
domain/backtest ──❌→ application
domain/brokers  ──❌→ adapters (infrastructure)
domain/memory   ──❌→ adapters (infrastructure)
```

---

## 5. 修复优先级

### P0 - 必须修复（破坏架构原则）

1. **backtest → application (2 处)**
   - backtest_report.py → RiskMetricsService
   - ml_mixin.py → MLPredictor
   - **工作量**: 2-3 小时
   - **方案**: 依赖注入

2. **brokers → adapters (6 处)**
   - broker_registry.py 直接导入具体实现
   - domain/brokers/adapters/ 目录违反分层
   - **工作量**: 4-6 小时
   - **方案**: 移除 adapters/ 目录，改用工厂模式 + 配置

3. **memory → adapters (2 处)**
   - distiller.py 直接导入 repository 实现
   - **工作量**: 1-2 小时
   - **方案**: 通过 IMemoryRepository 端口注入

### P1 - 建议修复（代码质量）

4. **benchmarks → application (1 处)**
   - run_all_benchmarks.py → BenchmarkService
   - **工作量**: 1 小时
   - **方案**: 依赖注入

5. **benchmarks → quantlib GPU (2 处)**
   - 硬编码依赖 GPU 实现
   - **工作量**: 2 小时
   - **方案**: 参数化测试

### P2 - 文档清理

6. **backtest 注释中的 adapters 引用 (2 处)**
   - 仅在注释中提及，非实际导入
   - **工作量**: 5 分钟
   - **方案**: 修改注释措辞

---

## 6. 修复方案详解

### 方案 A: 依赖注入（推荐）

**适用**: backtest → application 违规

```python
# 修复前
class BacktestReport:
    def generate_risk_metrics(self):
        from application.services.risk_metrics_service import RiskMetricsService
        service = RiskMetricsService()
        return service.calculate_metrics(self.returns)

# 修复后
class BacktestReport:
    def __init__(self, risk_calculator=None):
        """
        Args:
            risk_calculator: 风险计算器（可选注入）
        """
        self.risk_calculator = risk_calculator
    
    def generate_risk_metrics(self):
        if self.risk_calculator:
            return self.risk_calculator.calculate_metrics(self.returns)
        else:
            # 使用默认的 domain 层计算
            return self._calculate_basic_metrics()
```

---

### 方案 B: 工厂模式 + 配置（推荐）

**适用**: brokers → adapters 违规

```python
# 修复前（domain/brokers/broker_registry.py）
from adapters.outbound.brokers.akshare_broker import AkshareBroker

class BrokerRegistry:
    def get_broker(self, name):
        if name == 'akshare':
            return AkshareBroker()  # 直接实例化

# 修复后
# domain/brokers/broker_registry.py
class BrokerRegistry:
    def __init__(self):
        self._factories = {}
    
    def register_broker_factory(self, name, factory):
        """由 infrastructure 层调用注册"""
        self._factories[name] = factory
    
    def get_broker(self, name):
        if name not in self._factories:
            raise ValueError(f"Unknown broker: {name}")
        return self._factories[name]()

# infrastructure/brokers/setup.py
from adapters.outbound.brokers.akshare_broker import AkshareBroker
from domain.brokers.broker_registry import BrokerRegistry

def setup_brokers(registry: BrokerRegistry):
    """在 infrastructure 层注册具体实现"""
    registry.register_broker_factory('akshare', AkshareBroker)
    registry.register_broker_factory('ibkr', IBKRBroker)
```

---

### 方案 C: 端口接口（推荐）

**适用**: memory → adapters 违规

```python
# 修复前（domain/memory/distiller.py）
from adapters.outbound.repositories.memory_repository import MemoryRepository

class Distiller:
    def __init__(self):
        self.repo = MemoryRepository()  # 直接实例化

# 修复后
# domain/ports/repository_ports.py
from abc import ABC, abstractmethod

class IMemoryRepository(ABC):
    @abstractmethod
    def save(self, memory): pass
    
    @abstractmethod
    def find_by_id(self, id): pass

# domain/memory/distiller.py
from domain.ports import IMemoryRepository

class Distiller:
    def __init__(self, memory_repo: IMemoryRepository):
        self.repo = memory_repo  # 通过构造函数注入

# infrastructure/di/container.py
from adapters.outbound.repositories.memory_repository import MemoryRepository
from domain.memory.distiller import Distiller

def create_distiller():
    repo = MemoryRepository()  # infrastructure 层创建具体实现
    return Distiller(memory_repo=repo)
```

---

## 7. 架构原则检查清单

### ✅ 遵循的原则

- ✅ **单一职责**: 每个领域职责明确
- ✅ **开放封闭**: 通过端口扩展，无需修改 domain
- ✅ **接口隔离**: ports/ 定义了清晰的接口
- ✅ **依赖倒置** (部分): factors/risk 依赖 quantlib 抽象

### ❌ 违反的原则

- ❌ **依赖倒置** (部分): backtest/benchmarks 依赖 application 具体服务
- ❌ **依赖倒置** (部分): brokers/memory 依赖 adapters 具体实现
- ❌ **分层架构**: domain 不应导入 application 或 adapters

---

## 8. 建议改进路线图

### Week 1: 紧急修复（P0）

**Day 1-2**: 修复 backtest → application (2 处)
- 重构 backtest_report.py
- 重构 ml_mixin.py
- 添加单元测试验证

**Day 3-4**: 修复 brokers → adapters (6 处)
- 实现工厂模式
- 移除 domain/brokers/adapters/
- 在 infrastructure 层注册实现

**Day 5**: 修复 memory → adapters (2 处)
- 通过 IMemoryRepository 注入
- 更新依赖注入配置

### Week 2: 质量提升（P1）

**Day 1**: 修复 benchmarks 违规 (3 处)
**Day 2**: 添加架构测试（自动检测违规）
**Day 3**: 更新文档和迁移指南
**Day 4-5**: 回归测试与性能验证

---

## 9. 自动化架构守护

### 建议添加 CI 检查

```python
# tests/architecture/test_domain_boundaries.py
import pytest
import os
import re

def test_domain_no_application_imports():
    """检查 domain 层不导入 application 层"""
    violations = []
    
    for root, dirs, files in os.walk('domain/'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path) as f:
                    content = f.read()
                    if 'from application.' in content:
                        violations.append(path)
    
    assert len(violations) == 0, f"Found {len(violations)} violations: {violations}"

def test_domain_no_adapters_imports():
    """检查 domain 层不导入 adapters 层"""
    # 类似实现
    pass
```

---

## 10. 总结

### 当前状态

**优势** ✅:
- 9/12 领域无架构违规
- quantlib 重构后职责清晰
- ports 端口定义完善
- 大部分跨域依赖合理

**问题** ❌:
- 13 处架构违规（3 严重 + 10 中等）
- brokers/memory 未使用端口注入
- benchmarks 测试耦合具体实现

### 建议优先级

1. **P0**: 修复 backtest/brokers/memory 的架构违规（必须）
2. **P1**: 修复 benchmarks 违规（建议）
3. **P2**: 添加自动化架构测试（长期）

### 预期收益

修复后：
- ✅ 架构合规率：75% → 100%
- ✅ 领域隔离度：50% → 75%
- ✅ 可测试性：显著提升
- ✅ 可维护性：显著提升

---

**审计人**: Claude (Kiro AI Assistant)  
**审计日期**: 2026-08-23  
**下次审计**: 建议 2 周后（修复完成后）
