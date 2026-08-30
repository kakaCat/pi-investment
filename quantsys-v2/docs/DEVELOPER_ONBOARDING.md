# 开发者快速入门

> 新加入团队？5 分钟快速上手 quantsys-v2 开发规范

---

## 📋 必读清单

在开始写代码前，请确保你已经：

- [ ] 阅读 [CODING_STANDARDS.md](../../docs/coding-standards.md)（完整规范）
- [ ] 收藏 [ARCHITECTURE_QUICK_REFERENCE.md](ARCHITECTURE_QUICK_REFERENCE.md)（日常速查）
- [ ] 安装 pre-commit hook（自动检查）
- [ ] 运行一次架构检测工具（验证环境）

---

## 🚀 环境配置

### 1. 克隆项目

```bash
git clone <repository-url>
cd pi-investment/quantsys-v2
```

### 2. 安装 Python 环境

```bash
# 使用 Python 3.13
/opt/homebrew/bin/python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 安装 Git Hooks

```bash
# 配置 git 使用项目的 hooks 目录
git config core.hooksPath .git-hooks

# 或者手动复制
cp .git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 4. 验证环境

```bash
# 运行架构检测工具
python tools/analyze_layer_violations.py

# 应该看到类似输出：
# ✅ 违规导入总数: 7
```

---

## 🏗️ 架构概览

### 三层架构

```
应用层 (Application)
    ↓ 依赖
领域层 (Domain - Ports & Models)
    ↑ 实现
适配器层 (Adapters)
```

### 核心原则

1. **依赖倒置**: 应用层依赖接口（Ports），不依赖实现（Adapters）
2. **局部导入**: 具体实现在 `__init__` 方法中局部导入
3. **接口注解**: 所有 Repository/DataSource 使用接口类型注解

---

## 📝 日常开发模式

### 创建新服务

```python
# application/services/my_new_service.py
import structlog
from domain.ports.repository_ports_extended import IStockRepository
from domain.models.market_data import QuoteData

logger = structlog.get_logger(__name__)


class MyNewService:
    """我的新服务"""
    
    def __init__(self):
        """初始化 - 局部导入具体实现"""
        self.logger = logger
        
        # ✅ 局部导入 + 接口注解
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        self.stock_repo: IStockRepository = StockORMRepository()
    
    def my_business_logic(self, symbol: str) -> QuoteData:
        """业务方法"""
        stock_data = self.stock_repo.get_by_symbol(symbol)
        # 处理业务逻辑...
        return result
```

### 使用已有 Repository

```python
from domain.ports.repository_ports_extended import IKlineRepository

class MyService:
    def __init__(self):
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        self.kline_repo: IKlineRepository = KlineORMRepository()
```

### 使用 DataSource

```python
from domain.ports.datasource_ports import IDataProviderManager

class MyService:
    def __init__(self):
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider: IDataProviderManager = get_data_provider_manager()
```

---

## ⚠️ 常见错误

### ❌ 错误 1: 顶层导入适配器

```python
# ❌ 不要这样写
from adapters.outbound.repositories.stock_repository import StockORMRepository

class Service:
    def __init__(self):
        self.repo = StockORMRepository()
```

**为什么错？** 违反了依赖倒置原则，应用层直接依赖了适配器层。

**正确写法：**

```python
# ✅ 应该这样写
from domain.ports.repository_ports_extended import IStockRepository

class Service:
    def __init__(self):
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        self.repo: IStockRepository = StockORMRepository()
```

### ❌ 错误 2: 缺少接口类型注解

```python
# ❌ 不要这样写
class Service:
    def __init__(self):
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        self.kline_repo = KlineORMRepository()  # 缺少类型注解
```

**为什么错？** 失去了接口的抽象，测试和维护困难。

**正确写法：**

```python
# ✅ 应该这样写
from domain.ports.repository_ports_extended import IKlineRepository

class Service:
    def __init__(self):
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        self.kline_repo: IKlineRepository = KlineORMRepository()  # ✅ 接口类型
```

### ❌ 错误 3: 从适配器导入模型

```python
# ❌ 不要这样写
from adapters.outbound.datasources.models import QuoteData
```

**正确写法：**

```python
# ✅ 应该这样写
from domain.models.market_data import QuoteData
```

---

## 🔍 检查你的代码

### 提交前检查

```bash
# 方法 1: Git hook 自动检查（推荐）
git commit -m "your message"
# hook 会自动运行架构检查

# 方法 2: 手动运行检查
cd quantsys-v2
python tools/analyze_layer_violations.py

# 方法 3: 查看详细违规
python tools/analyze_layer_violations.py | less
```

### 查看你的文件是否有违规

```bash
# 检查特定文件
python tools/analyze_layer_violations.py | grep "my_service.py"
```

---

## 📚 快速参考

### 接口位置速查表

| 你需要... | 导入这个接口 | 文件位置 |
|----------|------------|---------|
| 操作数据库 | `IXxxRepository` | `domain/ports/repository_ports_extended.py` |
| 获取行情数据 | `IDataProviderManager` | `domain/ports/datasource_ports.py` |
| 使用领域模型 | `QuoteData`, `KlineData` | `domain/models/market_data.py` |

### 实现位置速查表

| 接口 | 实现类 | 导入路径 |
|-----|-------|---------|
| `IStockRepository` | `StockORMRepository` | `adapters.outbound.repositories.stock_repository` |
| `IKlineRepository` | `KlineORMRepository` | `adapters.outbound.repositories.kline_repository` |
| `IDataProviderManager` | `get_data_provider_manager()` | `adapters.outbound.datasources.manager` |

---

## 🆘 遇到问题？

### 问题 1: 检测工具报错

```bash
# 确保在正确的目录
cd quantsys-v2

# 确保 Python 环境激活
source venv/bin/activate

# 重新运行
python tools/analyze_layer_violations.py
```

### 问题 2: 不知道用哪个接口

1. 查看 `domain/ports/repository_ports_extended.py` - 所有 Repository 接口
2. 查看 `domain/ports/datasource_ports.py` - 所有 DataSource 接口
3. 搜索类似的服务文件，参考它们的写法

### 问题 3: 接口不存在

如果你需要的接口还不存在：

1. 先在 `domain/ports/` 中定义接口
2. 在 `adapters/outbound/` 中实现接口
3. 然后在应用层使用

**示例**:

```python
# 1. 定义接口 (domain/ports/repository_ports_extended.py)
class IMyNewRepository(ABC):
    @abstractmethod
    def my_method(self, param: str) -> Dict:
        pass

# 2. 实现接口 (adapters/outbound/repositories/my_new_repository.py)
class MyNewORMRepository(BaseORMRepository, IMyNewRepository):
    def my_method(self, param: str) -> Dict:
        # 实现...
        pass

# 3. 使用接口 (application/services/my_service.py)
from domain.ports.repository_ports_extended import IMyNewRepository

class MyService:
    def __init__(self):
        from adapters.outbound.repositories.my_new_repository import MyNewORMRepository
        self.repo: IMyNewRepository = MyNewORMRepository()
```

---

## 📖 进阶阅读

- [完整编码规范](../../docs/coding-standards.md) - 详细规则和示例
- [架构快速参考](ARCHITECTURE_QUICK_REFERENCE.md) - 模式速查卡
- [架构审计进度](architecture-audit-progress.md) - 重构历程

---

## ✅ 准备好了吗？

完成上述步骤后，你应该：

- ✅ 理解了三层架构和依赖倒置原则
- ✅ 知道如何正确导入接口和实现
- ✅ 配置好了自动检查工具
- ✅ 能够独立编写符合规范的服务代码

**开始编码吧！** 遇到问题随时查看 [Quick Reference](ARCHITECTURE_QUICK_REFERENCE.md) 📚

---

**维护者**: Architecture Team  
**最后更新**: 2026-08-15
