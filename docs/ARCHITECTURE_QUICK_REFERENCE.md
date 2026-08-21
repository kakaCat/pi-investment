# 分层架构快速参考

> **TL;DR**: 应用层只导入领域接口，具体实现用局部导入

---

## 🚦 导入规则速查

### ✅ 允许

```python
# 应用层服务
from domain.ports.repository_ports_extended import IStockRepository
from domain.ports.datasource_ports import IDataProviderManager
from domain.models.market_data import QuoteData

class MyService:
    def __init__(self):
        # ✅ 局部导入具体实现
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        self.repo: IStockRepository = StockORMRepository()
```

### ❌ 禁止

```python
# ❌ 顶层导入适配器
from adapters.outbound.repositories.stock_repository import StockORMRepository
from adapters.outbound.datasources.manager import DataProviderManager

class MyService:
    def __init__(self):
        # ❌ 直接使用具体类
        self.repo = StockORMRepository()
```

---

## 📋 常用模式

### Pattern 1: Repository 访问

```python
from domain.ports.repository_ports_extended import IKlineRepository

class MyService:
    def __init__(self):
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        self.kline_repo: IKlineRepository = KlineORMRepository()
```

### Pattern 2: DataSource 访问

```python
from domain.ports.datasource_ports import IDataProviderManager

class MyService:
    def __init__(self):
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider: IDataProviderManager = get_data_provider_manager()
```

### Pattern 3: 依赖注入（推荐）

```python
from domain.ports.repository_ports_extended import ISignalRepository

class SignalService:
    def __init__(self, signal_repo: ISignalRepository):
        """接口注入，便于测试"""
        self.signal_repo = signal_repo

# 工厂函数组装
def create_signal_service() -> SignalService:
    from adapters.outbound.repositories.signal_repository import SignalORMRepository
    return SignalService(signal_repo=SignalORMRepository())
```

---

## 🔍 违规检测

```bash
# 运行检测工具
cd quantsys-v2
python tools/analyze_layer_violations.py

# 查看违规详情
python tools/analyze_layer_violations.py | less
```

---

## 🛠️ 常见违规修复

### 修复 1: Repository 顶层导入

```python
# Before ❌
from adapters.outbound.repositories.stock_repository import StockORMRepository

class Service:
    def __init__(self):
        self.repo = StockORMRepository()

# After ✅
from domain.ports.repository_ports_extended import IStockRepository

class Service:
    def __init__(self):
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        self.repo: IStockRepository = StockORMRepository()
```

### 修复 2: DataSource 顶层导入

```python
# Before ❌
from adapters.outbound.datasources.manager import DataProviderManager

class Service:
    def __init__(self):
        self.manager = DataProviderManager()

# After ✅
from domain.ports.datasource_ports import IDataProviderManager

class Service:
    def __init__(self):
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.manager: IDataProviderManager = get_data_provider_manager()
```

### 修复 3: 模型导入

```python
# Before ❌
from adapters.outbound.datasources.models import QuoteData

# After ✅
from domain.models.market_data import QuoteData
```

---

## 📍 接口位置速查

| 接口类型 | 文件位置 | 命名规范 |
|---------|---------|---------|
| Repository | `domain/ports/repository_ports_extended.py` | `I{Entity}Repository` |
| DataSource | `domain/ports/datasource_ports.py` | `I{Data}Provider` |
| 领域模型 | `domain/models/` | `{Entity}Data`, `{Entity}` |

---

## 🎯 Code Review 检查点

提交代码前，确认：

- [ ] 应用层只导入 `domain.ports.*` 和 `domain.models.*`
- [ ] 具体实现使用局部导入（在 `__init__` 中）
- [ ] 所有 Repository/DataSource 使用接口类型注解
- [ ] 运行过 `analyze_layer_violations.py` 且无新增违规
- [ ] 测试通过

---

## 📚 详细文档

完整规范请参考: [CODING_STANDARDS.md](../CODING_STANDARDS.md)

---

**快速帮助**: 遇到问题？先运行检测工具，90% 的问题都能发现
