# 分层架构编码规范

**版本**: 1.0  
**生效日期**: 2026-08-15  
**适用范围**: quantsys-v2 项目

---

## 目录

1. [架构原则](#架构原则)
2. [分层结构](#分层结构)
3. [依赖规则](#依赖规则)
4. [导入规范](#导入规范)
5. [接口定义规范](#接口定义规范)
6. [实现类规范](#实现类规范)
7. [常见场景示例](#常见场景示例)
8. [违规检测与修复](#违规检测与修复)
9. [Code Review 检查点](#code-review-检查点)

---

## 架构原则

### 1. 六边形架构（Hexagonal Architecture）

```
┌─────────────────────────────────────────┐
│      Adapters (Inbound - API)          │  ← 入站适配器
│  • Flask Routes                         │
│  • CLI Commands                         │
└─────────────────────────────────────────┘
              ↓ 调用
┌─────────────────────────────────────────┐
│      Application Services               │  ← 应用层
│  • 业务流程编排                         │
│  • 依赖领域端口（接口）                 │
└─────────────────────────────────────────┘
         ↓ 依赖接口
┌─────────────────────────────────────────┐
│      Domain (Ports + Models)            │  ← 领域层
│  • 接口定义（Ports）                    │
│  • 领域模型（Models）                   │
│  • 领域逻辑（Services）                 │
└─────────────────────────────────────────┘
         ↑ 实现接口
┌─────────────────────────────────────────┐
│      Adapters (Outbound)                │  ← 出站适配器
│  • Repository 实现                      │
│  • DataSource 实现                      │
│  • 外部服务适配器                       │
└─────────────────────────────────────────┘
```

### 2. 依赖倒置原则（DIP）

**核心**: 高层模块不依赖低层模块，都依赖抽象（接口）

- ✅ 应用层 → 领域端口（接口）
- ✅ 适配器 → 领域端口（实现接口）
- ❌ 应用层 → 适配器（直接依赖）

---

## 分层结构

```
quantsys-v2/
├── domain/                    # 领域层（核心）
│   ├── models/               # 领域模型
│   │   └── market_data.py    # QuoteData, KlineData, etc.
│   ├── ports/                # 端口（接口定义）
│   │   ├── repository_ports_extended.py    # Repository 接口
│   │   └── datasource_ports.py             # DataSource 接口
│   └── services/             # 领域服务（业务逻辑）
│
├── application/              # 应用层
│   └── services/             # 应用服务（流程编排）
│       ├── stock_data_service.py
│       └── market_data_service.py
│
├── adapters/                 # 适配器层
│   ├── inbound/              # 入站适配器
│   │   └── api/              # REST API
│   └── outbound/             # 出站适配器
│       ├── repositories/     # 数据仓储实现
│       └── datasources/      # 数据源实现
│
└── infrastructure/           # 基础设施
    ├── persistence/          # 持久化
    └── config/               # 配置
```

---

## 依赖规则

### ✅ 允许的依赖

| 层级 | 可以依赖 |
|-----|---------|
| **应用层** | `domain.models.*`<br>`domain.ports.*`<br>`domain.services.*` |
| **适配器层** | `domain.models.*`<br>`domain.ports.*`（实现接口）<br>`infrastructure.*` |
| **领域层** | 只能依赖标准库和领域内部模块 |
| **基础设施** | 可以依赖所有层（提供通用工具） |

### ❌ 禁止的依赖

1. **应用层 → 适配器层**
   ```python
   # ❌ 错误
   from adapters.outbound.repositories.stock_repository import StockORMRepository
   from adapters.outbound.datasources.manager import DataProviderManager
   
   # ✅ 正确
   from domain.ports.repository_ports_extended import IStockRepository
   from domain.ports.datasource_ports import IDataProviderManager
   ```

2. **领域层 → 应用层/适配器层**
   ```python
   # ❌ 错误 - 领域层不能依赖应用层
   from application.services.stock_data_service import StockDataService
   
   # ❌ 错误 - 领域层不能依赖适配器
   from adapters.outbound.repositories import KlineRepository
   ```

3. **循环依赖**
   ```python
   # ❌ 错误 - A 依赖 B，B 又依赖 A
   # service_a.py
   from application.services.service_b import ServiceB
   
   # service_b.py
   from application.services.service_a import ServiceA
   ```

---

## 导入规范

### 1. 应用层服务导入

**规则**: 只导入领域接口，不导入适配器实现

#### ✅ 正确示例

```python
# application/services/stock_data_service.py
import structlog
from typing import Dict, Any, List
from datetime import datetime

# ✅ 导入领域端口（接口）
from domain.ports.datasource_ports import IDataProviderManager
from domain.models.market_data import QuoteData, KlineData

logger = structlog.get_logger(__name__)


class StockDataService:
    """股票数据服务"""
    
    def __init__(self):
        self.logger = logger
        # ✅ 局部导入具体实现（避免顶层依赖）
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager: IDataProviderManager = get_data_provider_manager()
    
    def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情"""
        result = self.provider_manager.get_quote(symbol)
        if result.get('success'):
            return result.get('data')
        return None
```

#### ❌ 错误示例

```python
# ❌ 错误：顶层导入适配器实现
from adapters.outbound.datasources.manager import DataProviderManager, get_data_provider_manager

class StockDataService:
    def __init__(self):
        # ❌ 错误：直接使用具体实现类
        self.provider_manager = DataProviderManager()
```

### 2. Repository 访问

#### ✅ 正确示例

```python
# application/services/signal_service.py
from domain.ports.repository_ports_extended import ISignalRepository


class SignalService:
    def __init__(self, signal_repo: ISignalRepository):
        """依赖注入接口"""
        self.signal_repo = signal_repo
    
    def create_signal(self, signal_data: Dict) -> int:
        """创建信号"""
        return self.signal_repo.create_signal(signal_data)


# 或者使用局部导入（工厂模式）
class SignalService2:
    def __init__(self):
        # ✅ 局部导入，延迟依赖
        from adapters.outbound.repositories.signal_repository import SignalORMRepository
        self.signal_repo: ISignalRepository = SignalORMRepository()
```

#### ❌ 错误示例

```python
# ❌ 错误：顶层导入具体实现
from adapters.outbound.repositories.signal_repository import SignalORMRepository

class SignalService:
    def __init__(self):
        self.signal_repo = SignalORMRepository()
```

### 3. DataSource 访问

#### ✅ 正确示例

```python
# application/services/market_data_service.py
from domain.ports.datasource_ports import IDataProviderManager, ILhbDataSource


class MarketDataService:
    def __init__(self):
        # ✅ 通过工厂函数获取
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider: IDataProviderManager = get_data_provider_manager()
    
    def get_lhb_data(self, date: str):
        """获取龙虎榜数据"""
        # ✅ 局部导入特定数据源
        from adapters.outbound.datasources.lhb import LhbDataSource
        lhb_source: ILhbDataSource = LhbDataSource()
        return lhb_source.get_lhb(date)
```

### 4. 领域模型导入

#### ✅ 正确示例

```python
# application/services/realtime_quote_service.py
from domain.models.market_data import QuoteData
from domain.ports.datasource_ports import IQuoteProvider


class RealtimeQuoteService:
    def get_quote(self, symbol: str) -> QuoteData:
        """返回领域模型"""
        # ...
        return QuoteData(
            symbol=symbol,
            price=price,
            volume=volume,
            # ...
        )
```

#### ❌ 错误示例

```python
# ❌ 错误：从适配器层导入模型
from adapters.outbound.datasources.models import QuoteData
```

---

## 接口定义规范

### 1. Repository 接口

**位置**: `domain/ports/repository_ports_extended.py`

**命名规范**: `I{Entity}Repository`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class IStockRepository(ABC):
    """股票仓储接口
    
    定义股票数据访问的抽象方法
    """
    
    @abstractmethod
    def get_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """根据代码获取股票
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典或 None
        """
        pass
    
    @abstractmethod
    def get_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有股票
        
        Args:
            limit: 限制返回数量
            
        Returns:
            股票信息列表
        """
        pass
    
    @abstractmethod
    def create(self, stock_data: Dict[str, Any]) -> int:
        """创建股票记录
        
        Args:
            stock_data: 股票数据
            
        Returns:
            创建的记录ID
        """
        pass
```

### 2. DataSource 接口

**位置**: `domain/ports/datasource_ports.py`

**命名规范**: `I{Data}Provider` 或 `I{Source}DataSource`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from domain.models.market_data import QuoteData


class IQuoteProvider(ABC):
    """行情数据提供者接口"""
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情
        
        Args:
            symbol: 股票代码
            
        Returns:
            {'success': bool, 'data': QuoteData, 'source': str}
        """
        pass


class IDataProviderManager(ABC):
    """数据提供者管理器接口
    
    统一管理多个数据源，提供自动降级和健康监控
    """
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """获取行情数据（自动降级）"""
        pass
    
    @abstractmethod
    def get_klines(self, symbol: str, period: str, 
                   start_date: str, end_date: str) -> Dict[str, Any]:
        """获取K线数据（自动降级）"""
        pass
```

---

## 实现类规范

### 1. Repository 实现

**位置**: `adapters/outbound/repositories/`

**命名规范**: `{Entity}ORMRepository` 或 `{Entity}Repository`

```python
# adapters/outbound/repositories/stock_repository.py
from domain.ports.repository_ports_extended import IStockRepository
from infrastructure.persistence.orm import BaseORMRepository


class StockORMRepository(BaseORMRepository, IStockRepository):
    """股票仓储 ORM 实现
    
    实现 IStockRepository 接口
    """
    
    def get_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """实现接口方法"""
        row = self.session.query(Stock).filter_by(symbol=symbol).first()
        if row:
            return self._to_dict(row)
        return None
    
    def get_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """实现接口方法"""
        query = self.session.query(Stock)
        if limit:
            query = query.limit(limit)
        return [self._to_dict(row) for row in query.all()]
    
    def create(self, stock_data: Dict[str, Any]) -> int:
        """实现接口方法"""
        stock = Stock(**stock_data)
        self.session.add(stock)
        self.session.commit()
        return stock.id
```

### 2. DataSource 实现

**位置**: `adapters/outbound/datasources/`

```python
# adapters/outbound/datasources/providers/akshare_provider.py
from domain.ports.datasource_ports import IQuoteProvider
from domain.models.market_data import QuoteData


class AkshareQuoteProvider(IQuoteProvider):
    """Akshare 行情数据提供者
    
    实现 IQuoteProvider 接口
    """
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """实现接口方法"""
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            row = df[df['代码'] == symbol].iloc[0]
            
            quote = QuoteData(
                symbol=symbol,
                price=float(row['最新价']),
                volume=int(row['成交量']),
                # ...
            )
            
            return {
                'success': True,
                'data': quote,
                'source': 'akshare'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'source': 'akshare'
            }
```

---

## 常见场景示例

### 场景 1: 新建应用服务

```python
# application/services/new_service.py
import structlog
from typing import Dict, Any
from domain.ports.repository_ports_extended import IKlineRepository
from domain.ports.datasource_ports import IDataProviderManager

logger = structlog.get_logger(__name__)


class NewService:
    """新服务示例"""
    
    def __init__(self):
        """初始化服务
        
        使用局部导入避免顶层依赖违规
        """
        self.logger = logger
        
        # 延迟导入 Repository
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        self.kline_repo: IKlineRepository = KlineORMRepository()
        
        # 延迟导入 DataSource
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider: IDataProviderManager = get_data_provider_manager()
    
    def process_data(self, symbol: str) -> Dict[str, Any]:
        """业务方法"""
        # 1. 从数据库获取历史数据
        klines = self.kline_repo.get_kline_data(symbol)
        
        # 2. 从数据源获取最新数据
        latest = self.provider.get_quote(symbol)
        
        # 3. 业务逻辑处理
        result = self._analyze(klines, latest)
        
        return result
    
    def _analyze(self, klines, latest):
        """私有方法：业务逻辑"""
        # ...
        pass
```

### 场景 2: 依赖注入（推荐）

```python
# application/services/signal_service.py
from domain.ports.repository_ports_extended import ISignalRepository, IKlineRepository


class SignalService:
    """信号服务（依赖注入版本）"""
    
    def __init__(
        self, 
        signal_repo: ISignalRepository,
        kline_repo: IKlineRepository
    ):
        """通过构造函数注入依赖
        
        优点：
        - 便于测试（可以注入 mock）
        - 依赖清晰（显式声明）
        - 解耦彻底（完全不依赖具体实现）
        """
        self.signal_repo = signal_repo
        self.kline_repo = kline_repo
    
    def create_signal(self, symbol: str) -> int:
        """创建信号"""
        # 获取K线数据
        klines = self.kline_repo.get_kline_data(symbol)
        
        # 生成信号
        signal_data = self._generate_signal(klines)
        
        # 保存信号
        signal_id = self.signal_repo.create_signal(signal_data)
        return signal_id


# 使用示例（在 API 层或工厂中组装）
def create_signal_service() -> SignalService:
    """工厂函数：组装服务"""
    from adapters.outbound.repositories.signal_repository import SignalORMRepository
    from adapters.outbound.repositories.kline_repository import KlineORMRepository
    
    return SignalService(
        signal_repo=SignalORMRepository(),
        kline_repo=KlineORMRepository()
    )
```

### 场景 3: 工厂函数使用

```python
# application/services/market_service.py
from domain.ports.datasource_ports import IDataProviderManager


class MarketService:
    """市场服务"""
    
    def __init__(self):
        # ✅ 局部导入工厂函数
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider: IDataProviderManager = get_data_provider_manager()
    
    def get_market_overview(self) -> Dict:
        """获取市场概览"""
        # 使用接口方法
        result = self.provider.get_quote('000001.SH')
        return result
```

### 场景 4: 特定数据源访问

```python
# application/services/lhb_service.py
from domain.ports.datasource_ports import ILhbDataSource


class LhbService:
    """龙虎榜服务"""
    
    def __init__(self):
        # ✅ 局部导入特定数据源
        from adapters.outbound.datasources.lhb import LhbDataSource
        self.lhb_source: ILhbDataSource = LhbDataSource()
    
    def get_daily_lhb(self, date: str):
        """获取每日龙虎榜"""
        return self.lhb_source.get_lhb(date)
```

---

## 违规检测与修复

### 1. 运行检测工具

```bash
# 检测分层违规
cd quantsys-v2
python tools/analyze_layer_violations.py

# 检测循环依赖
python tools/detect_circular_deps.py
```

### 2. 常见违规及修复

#### 违规 1: 顶层导入适配器

**检测输出**:
```
application/services/stock_service.py
  L 10: from adapters.outbound.repositories.stock_repository
```

**修复前**:
```python
# ❌ 顶层导入
from adapters.outbound.repositories.stock_repository import StockORMRepository

class StockService:
    def __init__(self):
        self.repo = StockORMRepository()
```

**修复后**:
```python
# ✅ 局部导入 + 接口声明
from domain.ports.repository_ports_extended import IStockRepository

class StockService:
    def __init__(self):
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        self.repo: IStockRepository = StockORMRepository()
```

#### 违规 2: 直接导入具体实现

**修复前**:
```python
from adapters.outbound.datasources.manager import DataProviderManager

class Service:
    def __init__(self):
        self.manager = DataProviderManager()
```

**修复后**:
```python
from domain.ports.datasource_ports import IDataProviderManager

class Service:
    def __init__(self):
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.manager: IDataProviderManager = get_data_provider_manager()
```

#### 违规 3: 从适配器导入模型

**修复前**:
```python
from adapters.outbound.datasources.models import QuoteData
```

**修复后**:
```python
from domain.models.market_data import QuoteData
```

### 3. 自动修复工具

项目提供了自动修复工具：

```bash
# Repository 导入迁移
python quantsys-v2/tools/migrate_repository_imports.py

# DataSource 导入迁移
python quantsys-v2/tools/migrate_datasource_imports.py

# 工厂函数导入修复
python quantsys-v2/tools/fix_factory_imports.py
```

---

## Code Review 检查点

### 必查项

- [ ] **导入检查**: 应用层是否只导入 `domain.ports.*` 和 `domain.models.*`
- [ ] **接口使用**: 是否使用接口类型注解而非具体实现类
- [ ] **局部导入**: 具体实现是否使用局部导入（在 `__init__` 中）
- [ ] **循环依赖**: 是否引入新的循环依赖
- [ ] **领域模型**: 数据模型是否从 `domain.models.*` 导入

### 检查清单

#### 新增服务文件

```python
# ✅ 导入部分
from domain.ports.xxx import IXxxRepository      # 接口
from domain.models.xxx import XxxModel           # 模型

# ✅ 类定义
class NewService:
    def __init__(self):
        # ✅ 局部导入
        from adapters.outbound.repositories.xxx import XxxRepository
        self.repo: IXxxRepository = XxxRepository()  # ✅ 接口类型注解
```

#### 修改现有服务

- [ ] 是否新增了对 `adapters.*` 的顶层导入？
- [ ] 是否可以改用接口？
- [ ] 是否可以改为局部导入？

#### 新增 Repository/DataSource

- [ ] 是否定义了对应接口？
- [ ] 实现类是否声明了接口实现（`class XxxRepo(IXxxRepo)`）？
- [ ] 接口方法是否都已实现？

---

## 例外情况

### 允许的例外

1. **Infrastructure 层**
   - 可以导入任何层的代码（提供通用工具）
   - 例如：日志、配置、数据库连接

2. **测试代码**
   - 测试可以直接导入具体实现
   - 但建议使用接口 + mock

3. **Migration 脚本**
   - 数据迁移脚本可以直接访问 ORM 模型

4. **局部导入的工厂调用**
   - 在 `__init__` 中局部导入具体实现是允许的
   - 但必须有接口类型注解

### 特殊模块

**adapters.shared.*** - 共享工具模块
- 当前状态：部分代码导入（7 处）
- 处理方式：待评估是否抽象为接口或移至 infrastructure

---

## 持续改进

### CI 集成（TODO）

```yaml
# .github/workflows/architecture-check.yml
name: Architecture Check

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check Layer Violations
        run: |
          cd quantsys-v2
          python tools/analyze_layer_violations.py
          violations=$(python tools/analyze_layer_violations.py | grep "违规导入总数" | awk '{print $3}')
          if [ "$violations" -gt 10 ]; then
            echo "Too many violations: $violations"
            exit 1
          fi
```

### 定期审计

- **频率**: 每月
- **负责人**: 架构师
- **工具**: `analyze_layer_violations.py` + `detect_circular_deps.py`
- **报告**: 记录违规趋势，评估架构健康度

---

## 参考资料

### 内部文档
- [架构审计进度](../architecture-audit-progress.md)
- [Phase 1 完成报告](./2026-08-15-phase1-repository-migration-report.md)
- [Phase 2 完成报告](./2026-08-15-phase2-datasource-migration-report.md)
- [Phase 3 完成报告](./2026-08-15-phase3-remaining-violations-report.md)

### 外部资料
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

**维护者**: Architecture Team  
**最后更新**: 2026-08-15  
**版本历史**: 
- v1.0 (2026-08-15): 初始版本，基于 Phase 1-3 整改经验
