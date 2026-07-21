# 数据访问指南 (Data Access Guide)

> **重要**: 本项目已有统一的数据访问层，禁止重复实现数据源逻辑！

## 📋 原则

**DO NOT**:
- ❌ 直接调用 akshare/tushare/sina 等第三方库
- ❌ 自己实现多数据源切换逻辑
- ❌ 写脚本绕过 DataService
- ❌ 在 routes 中直接访问数据库

**DO**:
- ✅ 使用 `DataProviderManager` (统一多数据源)
- ✅ 使用 `DataService` (业务逻辑层)
- ✅ 使用 Repository 层 (数据库访问)

---

## 🔧 数据访问的唯一入口

### 1. DataProviderManager (推荐)

**用途**: K线、行情、财务、分红等所有外部数据

**位置**: `adapters/outbound/datasources/manager.py`

**特性**:
- ✅ 自动多数据源切换 (database → akshare → sina → eastmoney)
- ✅ 健康检查和统计
- ✅ 统一错误处理
- ✅ 代理配置已优化

**示例**:
```python
from adapters.outbound.datasources.manager import get_data_provider_manager

manager = get_data_provider_manager()

# K线数据 (自动从database或akshare获取)
result = manager.get_klines('600519', 'daily', '2026-07-01', '2026-07-17')
if result['success']:
    klines = result['data']  # List[KlineData]
    source = result['source']  # 'database' or 'akshare'

# 实时行情
result = manager.get_quote('600519')

# 分红数据
result = manager.get_dividends('600519', years=5)
```

### 2. DataService (业务逻辑层)

**用途**: 需要业务逻辑处理的数据访问

**位置**: `application/services/data_service.py`

**示例**:
```python
from adapters.inbound.api.shared import ds

# K线数据 (返回 Polars DataFrame)
klines_df = ds.kline.get_daily_klines('600519', '2026-07-01', '2026-07-17')

# 因子数据
factors = ds.factor.compute_factors('600519')
```

### 3. Repository 层 (数据库访问)

**用途**: 仅用于直接操作数据库

**位置**: `infrastructure/repositories/`

**示例**:
```python
from infrastructure.repositories.kline_repository_orm import KlineORMRepository

repo = KlineORMRepository()
klines = repo.get_daily_klines('600519', '2026-07-01', '2026-07-17')
```

---

## 🚫 废弃的代码

以下代码**禁止使用**，应该重构或删除：

| 文件 | 问题 | 替代方案 |
|------|------|----------|
| `scripts/update_klines_multi_source.py` | 重复实现数据源逻辑 | 使用 `DataProviderManager.get_klines()` |
| `scripts/batch_update_klines.py` | 直接调用 Sina API | 使用 `DataProviderManager` |
| API routes 中的直接数据库查询 | 绕过业务逻辑层 | 使用 `DataService` |

---

## 📝 添加新数据源的正确方式

### 步骤 1: 实现 Provider

在 `adapters/outbound/datasources/providers/{domain}/{source}.py` 创建provider:

```python
from adapters.outbound.datasources.providers.kline.base import KlineProvider, KlineData

class NewSourceKlineProvider(KlineProvider):
    @property
    def name(self) -> str:
        return "new_source"
    
    def get_klines(self, symbol, period, start_date, end_date):
        # 实现数据获取逻辑
        pass
```

### 步骤 2: 注册到 Manager

在 `manager.py` 中添加到 providers 列表:

```python
from adapters.outbound.datasources.providers.kline.new_source import NewSourceKlineProvider

class DataProviderManager:
    def __init__(self, ds=None):
        self.kline_providers = [
            DatabaseKlineProvider(ds.kline),
            NewSourceKlineProvider(),  # 添加新provider
            AkshareKlineProvider(),
        ]
```

### 步骤 3: 完成

无需修改其他代码，所有使用 `DataProviderManager` 的地方自动生效！

---

## ⚡ 性能优化建议

1. **优先使用数据库** - `DatabaseKlineProvider` 最快
2. **批量查询** - 使用 batch API 而不是循环单个查询
3. **缓存结果** - 对于不变的历史数据，缓存在本地

---

## 🔍 Code Review Checklist

提交代码前检查：

- [ ] 没有直接 `import akshare`
- [ ] 没有直接 `import tushare`
- [ ] 没有自己实现数据源切换
- [ ] 使用了 `DataProviderManager` 或 `DataService`
- [ ] 阅读了本文档

---

## 📞 疑问？

如果你不确定应该使用哪个API，问自己：

1. **需要外部数据（行情/K线/财务）？** → `DataProviderManager`
2. **需要业务逻辑（因子计算/信号生成）？** → `DataService`
3. **只需要数据库CRUD？** → `Repository`

**仍然不确定？** 查看现有代码示例或询问团队成员。

---

**最后更新**: 2026-07-17
**维护者**: PI Investment Team
