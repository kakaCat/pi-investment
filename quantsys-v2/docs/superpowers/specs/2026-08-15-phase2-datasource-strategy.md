# Phase 2: 数据源接口抽象策略

**日期**: 2026-08-15  
**状态**: 规划中

## 问题分析

### 当前违规情况
- **违规总数**: 20 处 datasource 导入
- **违规文件**: 16 个服务文件
- **违规类型**: 应用层直接依赖 adapters.outbound.datasources

### 导入模式分析

#### 1. Manager/Factory 导入 (最常见，~12处)
```python
from adapters.outbound.datasources import get_data_provider_manager
from adapters.outbound.datasources.manager import get_data_provider_manager
from adapters.outbound.datasources.manager import get_data_source_manager
```

**使用场景**:
- market_data_service.py (3处)
- opportunity_scoring_service.py
- strategy_code_service.py
- 等...

#### 2. 基础设施组件导入 (~4处)
```python
from adapters.outbound.datasources.cache import DataSourceCache
from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
```

**使用场景**:
- enhanced_financial_data_service.py (2处)

#### 3. 特定数据源导入 (~4处)
```python
from adapters.outbound.datasources.lhb_source import LhbDataSource
from adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
from adapters.outbound.datasources.north_flow_ccass import NorthHoldingsCCASSSource
```

**使用场景**:
- lhb_service.py
- 其他专用服务

## 核心挑战

### 1. 架构现状
datasource 层已经有较好的抽象：
- `BaseDataProvider` - 抽象基类
- `QuoteProvider`, `FinancialProvider` 等专用接口
- `DataProviderManager` - 统一管理器

**问题**: 这些接口定义在 `adapters.outbound.datasources.*`，不在 `domain.ports.*`

### 2. 与 Repository 迁移的差异

| 维度 | Repository 迁移 | DataSource 迁移 |
|-----|----------------|----------------|
| 接口位置 | ✅ domain.ports 已有 | ❌ adapters 层 |
| 依赖方向 | 清晰（应用→领域） | 混乱（应用→适配器） |
| 复杂度 | 低（1对1映射） | 高（管理器模式） |
| 影响范围 | 64 个文件 | 16 个文件 |

## 策略选择

### 方案 A: 完全迁移到 domain.ports ✅ 推荐

**步骤**:
1. 在 `domain/ports/` 创建 `datasource_ports.py`
2. 定义接口：
   - `IDataProviderManager` - 管理器接口
   - `IQuoteProvider` - 行情接口
   - `IKlineProvider` - K线接口
   - `IFinancialProvider` - 财务接口
   - `IMarketProvider` - 市场接口
3. 提取基础设施接口：
   - `ICacheService` - 缓存接口
   - `ICircuitBreaker` - 熔断器接口
4. 应用层使用 domain.ports 接口
5. adapters 层实现这些接口

**优点**:
- 完全符合六边形架构
- 依赖方向清晰
- 易于测试和替换

**缺点**:
- 需要定义较多接口
- 实施时间较长（2-3天）

### 方案 B: 保留 datasource 基类，仅修正导入路径 ❌ 不推荐

保持 `adapters.outbound.datasources.base` 的接口定义，但将其视为"伪端口层"。

**优点**:
- 工作量小
- 不破坏现有结构

**缺点**:
- 不符合六边形架构
- 依赖方向仍然错误
- 技术债务未消除

### 方案 C: 混合方案 - 分阶段迁移 🟡 可选

**Phase 2a**: 先处理 Manager 和基础设施组件（高频使用）
**Phase 2b**: 再处理特定数据源（低频使用）

**优点**:
- 快速见效
- 渐进式改进

**缺点**:
- 两阶段工作
- 中间状态不一致

## 推荐方案：方案 A

### 实施计划

#### Step 1: 定义领域端口接口 (2h)

**文件**: `domain/ports/datasource_ports.py`

```python
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime

# 数据模型（需要从 adapters 移到 domain）
class QuoteData:
    symbol: str
    price: float
    timestamp: datetime
    # ...

class IQuoteProvider(ABC):
    """行情数据提供者接口"""
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """获取实时行情"""
        pass
    
    @abstractmethod
    def get_batch_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """批量获取行情"""
        pass

class IKlineProvider(ABC):
    """K线数据提供者接口"""
    
    @abstractmethod
    def get_kline(self, symbol: str, start_date: str, end_date: str, period: str = 'daily') -> List[Dict]:
        """获取K线数据"""
        pass

class IDataProviderManager(ABC):
    """数据提供者管理器接口
    
    统一管理多个数据源，支持自动降级
    """
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """通过最优 provider 获取行情"""
        pass
    
    @abstractmethod
    def get_kline(self, symbol: str, **kwargs) -> List[Dict]:
        """通过最优 provider 获取K线"""
        pass
    
    @abstractmethod
    def get_provider_stats(self) -> Dict[str, Any]:
        """获取 provider 健康状态"""
        pass

class ICacheService(ABC):
    """缓存服务接口"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        pass

class ICircuitBreaker(ABC):
    """熔断器接口"""
    
    @abstractmethod
    def call(self, func, *args, **kwargs) -> Any:
        """执行受保护的调用"""
        pass
    
    @abstractmethod
    def is_open(self) -> bool:
        """熔断器是否打开"""
        pass
```

#### Step 2: 迁移数据模型到领域层 (1h)

**问题**: `QuoteData`, `FinancialData` 等模型定义在 `adapters.outbound.datasources.models`

**方案**: 移动到 `domain/models/market_data.py`

```python
# domain/models/market_data.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class QuoteData:
    """实时行情数据（领域模型）"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    source: str
    # ...

@dataclass
class KlineData:
    """K线数据（领域模型）"""
    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    # ...
```

#### Step 3: 适配器实现接口 (2h)

`adapters.outbound.datasources` 的类实现 `domain.ports` 的接口：

```python
# adapters/outbound/datasources/manager.py
from domain.ports.datasource_ports import IDataProviderManager, IQuoteProvider
from domain.models.market_data import QuoteData

class DataProviderManager(IDataProviderManager):
    """实现 IDataProviderManager 接口"""
    
    def __init__(self):
        self.quote_providers: List[IQuoteProvider] = [
            TencentQuoteProvider(),
            SinaQuoteProvider(),
            # ...
        ]
    
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        # 现有实现逻辑保持不变
        pass
```

#### Step 4: 更新应用层导入 (3h)

使用自动化工具批量替换：

**文件**: `tools/migrate_datasource_imports.py`

```python
DATASOURCE_MAPPING = {
    'get_data_provider_manager': ('domain.ports.datasource_ports', 'IDataProviderManager'),
    'DataSourceCache': ('domain.ports.datasource_ports', 'ICacheService'),
    'CircuitBreaker': ('domain.ports.datasource_ports', 'ICircuitBreaker'),
    'LhbDataSource': ('domain.ports.datasource_ports', 'ILhbDataSource'),
    # ...
}
```

**迁移模式**:
```python
# Before
from adapters.outbound.datasources import get_data_provider_manager
manager = get_data_provider_manager()

# After
from domain.ports.datasource_ports import IDataProviderManager
from adapters.outbound.datasources.manager import get_data_provider_manager

manager: IDataProviderManager = get_data_provider_manager()
```

#### Step 5: 验证和测试 (2h)

1. 运行 `tools/analyze_layer_violations.py` 验证违规降低
2. 运行单元测试确保功能不变
3. 手工验证关键服务（market_data_service, opportunity_scoring_service）

### 预期成果

- **违规降低**: 20 → 0 (-100%)
- **总违规**: 26 → 6 (-77%)
- **仅剩**: 6 处特殊 repository 违规（Phase 3 处理）

## 风险与挑战

### 风险 1: 数据模型迁移影响面大
**缓解**: 
- 保留 adapters 中的模型定义（标记为 deprecated）
- 逐步迁移，保持向后兼容

### 风险 2: Manager 模式复杂，接口难抽象
**缓解**:
- 接口只定义业务方法，不暴露内部降级逻辑
- Manager 实现类保持现有复杂逻辑

### 风险 3: 测试覆盖不足
**缓解**:
- 先跑现有测试建立 baseline
- 迁移后再次运行确保无回归

## 时间估算

| 任务 | 预计时间 |
|-----|---------|
| Step 1: 定义接口 | 2h |
| Step 2: 迁移模型 | 1h |
| Step 3: 适配器实现 | 2h |
| Step 4: 应用层迁移 | 3h |
| Step 5: 验证测试 | 2h |
| **总计** | **10h** (约 1.5 天) |

## 下一步

等待用户确认后开始 Step 1: 定义领域端口接口。

---

**制定者**: Claude (Kiro)  
**审核者**: 待用户确认
