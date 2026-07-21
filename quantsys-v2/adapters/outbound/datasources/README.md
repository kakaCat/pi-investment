# Data Sources Module

增强的数据源架构，借鉴 FinceptTerminal 的设计模式，提供统一、可靠、高性能的数据访问层。

## 🎯 核心特性

### 1. **统一的响应格式**
所有数据源返回标准化的 `DataSourceResponse` 对象：
```python
{
    "success": True/False,
    "data": [...],
    "count": 10,
    "error": None,
    "metadata": {...}
}
```

### 2. **连接池优化**
- HTTP 连接复用，减少握手开销
- 自动重试机制（指数退避）
- 并发连接池管理

### 3. **统一错误处理**
- 自动重试（可配置次数和延迟）
- DataFrame 自动转换（NaN/Infinity 处理）
- 详细的错误上下文

### 4. **环境变量配置**
- API Key 通过环境变量管理
- 安全性更好，便于 CI/CD
- 支持多环境配置

## 📦 已实现的数据源

### AkShareSource (A股/港股市场数据)
```python
from data_sources.sources import AkShareSource

source = AkShareSource()

# 获取股票信息
result = source.get_stock_info("000001.SZ")

# 获取K线数据
result = source.get_klines("000001.SZ", period="daily", 
                          start_date="20240101", end_date="20240131")

# 获取实时行情
result = source.get_realtime_quote(["000001.SZ", "600000.SH"])

# 获取指数数据
result = source.get_index_data("000001", start_date="20240101")

# 获取板块列表
result = source.get_sector_list()

# 获取北向资金
result = source.get_north_flow(start_date="20240101")

# 获取市场新闻
result = source.get_market_news(symbol="000001.SZ", limit=20)

# 获取财务数据
result = source.get_financial_data("000001.SZ")
```

### FREDSource (美联储经济数据)
```python
from data_sources.sources import FREDSource

source = FREDSource()

# 获取经济指标序列
result = source.get_series("GDP", start_date="2020-01-01", end_date="2024-01-01")

# 搜索序列
result = source.search_series("unemployment", limit=10)

# 获取分类
result = source.get_categories(category_id=None)

# 获取发布序列
result = source.get_release_series(release_id=53)
```

**常用指标 ID**:
- `GDP` - 国内生产总值
- `UNRATE` - 失业率
- `CPIAUCSL` - 消费者价格指数
- `DFF` - 联邦基金利率
- `DGS10` - 10年期国债收益率

**配置**: 需要设置 `FRED_API_KEY` 环境变量
- 免费申请: https://fred.stlouisfed.org/docs/api/api_key.html

### WorldBankSource (世界银行商品价格)
```python
from data_sources.sources import WorldBankSource

source = WorldBankSource()

# 列出所有商品
result = source.list_commodities()

# 获取石油价格
result = source.get_oil_prices(start_year=2020, end_year=2024)

# 获取特定商品价格
result = source.get_commodity_price("gold", start_year=2020, end_year=2024)

# 获取商品指数
result = source.get_commodity_index("energy_index", start_year=2020)

# 搜索商品
result = source.search_series("copper", limit=5)
```

**支持的商品类别**:
- **能源**: crude_oil_brent, crude_oil_wti, natural_gas_us, coal
- **农产品**: wheat, corn, rice, soybean, sugar, coffee, cocoa
- **金属**: gold, silver, copper, aluminum, iron_ore, nickel
- **化肥**: urea, dap, potassium_chloride, phosphate_rock

**无需 API Key**

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install requests pandas akshare
```

### 2. 配置环境变量（可选）
```bash
# .env 文件
FRED_API_KEY=your_fred_api_key_here
```

### 3. 使用示例
```python
from data_sources.sources import AkShareSource, FREDSource, WorldBankSource
from data_sources.config import DataSourceConfig

# 检查配置状态
status = DataSourceConfig.validate_all()
for source, message in status.items():
    print(f"{source}: {message}")

# 使用 AkShare
akshare = AkShareSource()
result = akshare.get_stock_info("000001.SZ")
if result.success:
    print(result.data)
else:
    print(f"Error: {result.error}")

# 使用 FRED (需要 API key)
fred = FREDSource()
result = fred.get_series("GDP")
if result.success:
    print(f"Got {result.count} observations")

# 使用 World Bank
wb = WorldBankSource()
result = wb.get_oil_prices(start_year=2023, end_year=2024)
if result.success:
    print(result.data)
```

### 4. 运行示例
```bash
python data_sources/examples.py
```

### 5. 运行测试
```bash
pytest tests/test_data_sources.py -v
```

## 🏗️ 架构设计

### 目录结构
```
data_sources/
├── __init__.py              # 包入口
├── base.py                  # 基础抽象类
├── session_manager.py       # HTTP 连接池管理
├── error_handler.py         # 错误处理和重试
├── config.py                # 配置管理
├── examples.py              # 使用示例
├── sources/                 # 数据源实现
│   ├── __init__.py
│   ├── akshare_source.py    # AkShare 封装
│   ├── fred_source.py       # FRED 封装
│   └── world_bank_source.py # World Bank 封装
└── README.md                # 本文档
```

### 核心组件

#### BaseDataSource
所有数据源的抽象基类，定义标准接口：
- `validate_config()` - 验证配置
- `test_connection()` - 测试连接
- 统一的日志记录
- 统一的错误处理

#### SessionManager
HTTP 连接池管理器：
- 连接复用（避免重复握手）
- 自动重试（指数退避）
- 多数据源隔离（独立 session）

#### ErrorHandler
错误处理工具集：
- `safe_call()` - 带重试的安全调用
- `handle_dataframe()` - DataFrame 转换
- 日期格式化、类型转换等工具函数

## 📊 性能优化

### 连接池效果
- **无连接池**: 每次请求 ~200ms（TCP 握手 + TLS 握手）
- **有连接池**: 首次 ~200ms，后续 ~50ms（复用连接）
- **提升**: 高频调用场景下 **4x 性能提升**

### 重试机制
- 默认重试 2 次
- 指数退避（0.3s → 0.6s → 1.2s）
- 自动识别临时性错误

### 数据转换
- DataFrame → JSON 自动转换
- NaN/Infinity 自动处理为 None
- Datetime 自动转换为字符串

## 🔧 扩展新数据源

### 1. 创建数据源类
```python
from data_sources.base import EconomicDataSource, DataSourceResponse
from data_sources.session_manager import SessionManager

class MyDataSource(EconomicDataSource):
    def __init__(self):
        super().__init__(name="MySource", requires_api_key=True)
        self.session = SessionManager.get_session("my_source")
    
    def validate_config(self) -> bool:
        # 验证配置
        return True
    
    def test_connection(self) -> DataSourceResponse:
        # 测试连接
        pass
    
    def get_series(self, series_id: str, ...) -> DataSourceResponse:
        # 实现数据获取
        pass
```

### 2. 注册到 sources/__init__.py
```python
from data_sources.sources.my_source import MyDataSource

__all__ = [
    "AkShareSource",
    "FREDSource",
    "WorldBankSource",
    "MyDataSource",  # 新增
]
```

### 3. 添加配置（如需要）
在 `config.py` 中添加 API key 配置：
```python
ENV_VARS = {
    # ...
    "my_source": "MY_SOURCE_API_KEY",
}
```

## 🧪 测试

### 运行所有测试
```bash
pytest tests/test_data_sources.py -v
```

### 运行特定测试
```bash
pytest tests/test_data_sources.py::TestAkShareSource -v
```

### 测试覆盖率
```bash
pytest tests/test_data_sources.py --cov=data_sources --cov-report=html
```

## 📝 最佳实践

### 1. 错误处理
```python
result = source.get_data(...)
if result.success:
    # 处理数据
    data = result.data
else:
    # 处理错误
    logger.error(f"Failed to fetch data: {result.error}")
```

### 2. 使用连接池
```python
# 为不同数据源使用不同的 session
session = SessionManager.get_session("my_source")
response = session.get(url, params=params, timeout=30)
```

### 3. 配置验证
```python
from data_sources.config import DataSourceConfig

# 检查配置
if not DataSourceConfig.is_configured("fred"):
    print("Please set FRED_API_KEY environment variable")
    return

# 获取 API key
api_key = DataSourceConfig.get_api_key("fred")
```

### 4. 日志记录
```python
# 数据源自动记录请求和响应
source.get_data(...)  # 自动记录到日志
```

## 🔗 相关资源

- **FinceptTerminal**: https://github.com/Fincept-Corporation/FinceptTerminal
- **AkShare 文档**: https://akshare.akfamily.xyz/
- **FRED API 文档**: https://fred.stlouisfed.org/docs/api/
- **World Bank API**: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392

## 📄 许可证

本模块遵循 quantsys-v2 项目的许可证。

## 🤝 贡献

欢迎贡献新的数据源实现！请遵循现有的架构模式：
1. 继承 `BaseDataSource` 或其子类
2. 实现必需的抽象方法
3. 使用 `SessionManager` 管理连接
4. 使用 `safe_call` 处理错误
5. 返回 `DataSourceResponse` 对象
6. 编写单元测试
