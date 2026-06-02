# 财务数据多数据源实现文档

## 概述

实现了财务数据的多数据源支持，类似于实时行情数据的多源 fallback 机制。当主数据源失败时，自动切换到备用数据源。

**实现日期**: 2026-06-02

## 架构设计

### 1. Provider 模式

采用统一的 Provider 接口，每个数据源实现相同的接口：

```
services/financial_providers/
├── __init__.py              # 模块导出
├── base.py                  # 基类和数据结构
├── sina_provider.py         # 新浪财经提供者
└── eastmoney_provider.py    # 东方财富提供者
```

### 2. 核心组件

#### FinancialData (数据结构)
```python
@dataclass
class FinancialData:
    symbol: str                          # 股票代码（带后缀）
    name: str                            # 股票名称
    statement_type: str                  # 报表类型
    periods: int                         # 期数
    income_statement: List[Dict]         # 利润表
    balance_sheet: List[Dict]            # 资产负债表
    cash_flow: List[Dict]                # 现金流量表
    source: str                          # 数据源名称
    timestamp: datetime                  # 时间戳
```

#### FinancialProvider (基类)
```python
class FinancialProvider(ABC):
    @abstractmethod
    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4
    ) -> FinancialData:
        pass
```

#### FinancialDataService (协调器)
多数据源协调器，实现 fallback 逻辑：
- 按优先级依次尝试各数据源
- 验证数据完整性
- 收集统计信息
- 返回第一个成功的结果

### 3. 数据源优先级

**默认顺序**:
1. **新浪财经** (sina) - 通过 `akshare.stock_financial_report_sina`
2. **东方财富** (eastmoney) - 通过 `akshare.stock_financial_analysis_indicator`

### 4. 集成到 DataService

修改 `services/data_service.py`:
- 在 `__init__` 中初始化 `FinancialDataService`
- 重构 `get_financial_statements` 使用多数据源服务
- 保持缓存机制（季度数据，TTL 1天）
- 返回格式包含 `source` 字段标识数据源

## 功能特性

### 1. 自动 Fallback
当主数据源失败时，自动切换到下一个数据源，无需人工干预。

### 2. 数据验证
验证返回数据的完整性：
- 至少包含一个报表
- 报表数据非空
- 期数符合要求

### 3. 统计信息
跟踪服务使用情况：
- 总请求数
- 成功/失败次数
- 成功率
- 各数据源的成功/失败统计

### 4. 错误处理
- 标准化错误消息
- 详细的日志记录
- 友好的错误提示

## API 使用

### HTTP API
```bash
# 获取所有财务报表
GET /api/stock/{symbol}/financials?type=all&periods=4

# 获取单个报表
GET /api/stock/{symbol}/financials?type=income&periods=4

# 响应格式
{
  "success": true,
  "data": {
    "symbol": "600519.SH",
    "name": "贵州茅台",
    "statementType": "all",
    "periods": 4,
    "source": "sina",          # 数据源标识
    "incomeStatement": [...],
    "balanceSheet": [...],
    "cashFlow": [...]
  }
}
```

### Python API
```python
from services.financial_data_service import FinancialDataService

service = FinancialDataService()

# 获取财务数据
data = service.get_financial_data(
    symbol='600519',
    statement_type='all',
    periods=4
)

# 查看统计
stats = service.get_stats()
print(f"成功率: {stats['success_rate']}")
```

## 测试结果

运行测试脚本 `test_multi_source_financial.py`:

```
测试 1: 基本数据获取
✓ 600519 - 成功 (sina)
✓ 000001 - 成功 (sina)
✓ 000708 - 成功 (sina)

成功率: 100.00%

测试 2: 单个报表获取
✓ 所有报表类型均正常

测试 3: 错误处理
✓ 无效代码正确捕获错误
✓ Fallback 机制正常工作
```

## 性能优化

1. **缓存机制**: 季度数据缓存 1 天，减少重复请求
2. **快速失败**: 单个数据源失败立即切换，不等待超时
3. **并行查询**: 未来可支持多数据源并行查询，取最快响应

## 扩展性

### 添加新数据源

1. 创建新的 Provider 类：
```python
# services/financial_providers/new_provider.py
from .base import FinancialProvider, FinancialData

class NewProvider(FinancialProvider):
    def __init__(self):
        super().__init__(name="new_source")
    
    def get_financial_data(self, symbol, statement_type, periods):
        # 实现数据获取逻辑
        ...
```

2. 注册到服务：
```python
# services/financial_data_service.py
from services.financial_providers import NewProvider

self.providers = [
    SinaFinancialProvider(),
    EastmoneyFinancialProvider(),
    NewProvider(),  # 添加新数据源
]
```

### 自定义优先级

```python
# 自定义数据源顺序
custom_providers = [
    EastmoneyFinancialProvider(),  # 优先使用东方财富
    SinaFinancialProvider(),
]

service = FinancialDataService(providers=custom_providers)
```

## 已知问题

### 1. 数据格式差异
不同数据源返回的字段名称可能不同：
- 新浪财经：使用中文字段名（如 "报告日"）
- 东方财富：使用中文字段名（如 "日期"）

**解决方案**: 未来可添加字段映射层统一格式。

### 2. 数据完整性
某些股票在部分数据源可能没有完整的财务数据：
- 新上市股票
- 已退市股票
- ST 股票

**解决方案**: 多数据源 fallback 提高数据覆盖率。

## 相关文件

### 核心实现
- `quantsys-v2/services/financial_providers/base.py`
- `quantsys-v2/services/financial_providers/sina_provider.py`
- `quantsys-v2/services/financial_providers/eastmoney_provider.py`
- `quantsys-v2/services/financial_data_service.py`

### 集成层
- `quantsys-v2/services/data_service.py` - get_financial_statements 方法

### 测试
- `quantsys-v2/test_multi_source_financial.py`

### TypeScript 工具
- `src/infrastructure/tools/data/fetch-financial-tool.ts` - 无需修改，通过 API 自动使用多数据源

## 后续改进

1. **并行查询**: 同时查询多个数据源，取最快响应
2. **数据融合**: 合并多个数据源的数据，提高准确性
3. **智能选择**: 根据历史成功率动态调整数据源优先级
4. **监控告警**: 数据源失败率过高时自动告警
5. **数据对比**: 定期对比不同数据源的数据一致性

## 总结

✅ **已完成**:
- 多数据源架构实现
- 自动 fallback 机制
- 数据验证和错误处理
- 统计信息收集
- 集成到现有系统
- 完整测试验证

✅ **优势**:
- 提高数据可用性（单一数据源失败不影响整体服务）
- 可扩展（轻松添加新数据源）
- 可观测（统计信息追踪）
- 向后兼容（API 接口不变）

🎯 **效果**:
- 解决了原始问题（000708 财务数据获取失败）
- 系统鲁棒性提升
- 为未来扩展奠定基础
