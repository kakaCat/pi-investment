# 多数据源架构

## 概述

本系统支持多个第三方数据源，并提供自动降级功能。当主数据源失败时，系统会自动切换到备用数据源，确保数据获取的稳定性。

## 支持的数据源

### 1. Tushare（优先级1 - 最高）
- **类型**: 官方API
- **稳定性**: ⭐⭐⭐⭐⭐
- **速度**: ⭐⭐⭐⭐
- **费用**: 免费版 + 付费版
- **限制**: 免费版每分钟200次请求
- **注册**: https://tushare.pro/register
- **优点**: 数据质量高、稳定可靠
- **缺点**: 需要注册获取token、有限流

### 2. AkShare（优先级2）
- **类型**: 网页爬虫
- **稳定性**: ⭐⭐⭐
- **速度**: ⭐⭐⭐⭐⭐
- **费用**: 完全免费
- **限制**: 无官方限制
- **优点**: 免费、接口丰富、更新及时
- **缺点**: 依赖网页爬虫，可能不稳定

### 3. BaoStock（未实现，可扩展）
- **类型**: 官方API
- **稳定性**: ⭐⭐⭐⭐
- **速度**: ⭐⭐⭐
- **费用**: 完全免费
- **优点**: 稳定、免费
- **缺点**: 数据更新较慢

## 快速开始

### 1. 安装依赖

```bash
pip install tushare akshare pandas
```

### 2. 配置 Tushare Token（可选）

如果要使用 Tushare，需要设置环境变量：

```bash
export TUSHARE_TOKEN="your_token_here"
```

获取 token：https://tushare.pro/register

### 3. 基本使用

```python
from quantsys.data.data.data_service import DataService

# 初始化服务（自动配置所有可用数据源）
service = DataService()

# 获取日线数据（自动尝试 Tushare → AkShare）
df = service.get_daily_klines("000001", days=365)

# 获取股票列表
stocks = service.get_stock_list(market="A")
```

## 核心功能

### 1. 自动降级

当主数据源失败时，自动切换到备用数据源：

```python
service = DataService()

# 会按优先级尝试：Tushare → AkShare
df = service.get_daily_klines("000001", days=30)
```

### 2. 健康检查

系统会自动监控数据源的健康状态：

```python
# 查看健康状态
health = service.get_health_status()

for source, status in health.items():
    print(f"{source}: {status['available']}")
    print(f"  成功: {status['success_count']}")
    print(f"  失败: {status['failure_count']}")
```

**自动禁用规则**：
- 连续失败3次后，数据源会被自动禁用
- 可以手动重置健康状态：`service.reset_health_status()`

### 3. 缓存机制

减少API调用，提高响应速度：

```python
service = DataService(cache_enabled=True)

# 第一次请求：从数据源获取
df1 = service.get_daily_klines("000001", days=30)

# 第二次请求：从缓存返回（瞬间完成）
df2 = service.get_daily_klines("000001", days=30)

# 查看缓存统计
stats = service.get_cache_stats()
```

### 4. 数据验证

自动验证数据完整性和质量：

```python
service = DataService(validate_data=True)

# 自动检查：缺失值、异常值、数据完整性
df = service.get_daily_klines("000001", days=365)
```

## 架构设计

```
DataService (统一接口)
    ↓
DataSourceManager (多源管理)
    ↓
├── TushareAdapter (优先级1)
├── AkShareAdapter (优先级2)
└── [可扩展更多适配器]
    ↓
CacheManager (缓存层)
    ↓
DataValidator (数据验证)
```

## API 参考

### DataService

#### `get_daily_klines(symbol, start_date=None, end_date=None, days=None, adjust="qfq")`

获取日线K线数据。

**参数**：
- `symbol`: 股票代码（如 "000001"）
- `start_date`: 开始日期（YYYYMMDD格式）
- `end_date`: 结束日期（YYYYMMDD格式）
- `days`: 获取天数（与 start_date 二选一）
- `adjust`: 复权类型 - "qfq"（前复权）、"hfq"（后复权）、""（不复权）

**返回**：
- DataFrame，包含列：date, open, high, low, close, volume, amount

#### `get_stock_list(market="A")`

获取股票列表。

**参数**：
- `market`: 市场类型 - "A"（A股）、"HK"（港股）

**返回**：
- DataFrame，包含列：symbol, name, market, industry, list_date

#### `get_health_status()`

获取所有数据源的健康状态。

**返回**：
- Dict，映射数据源名称到健康状态

#### `clear_cache()`

清除所有缓存数据。

## 扩展新数据源

### 1. 创建适配器

```python
from quantsys.data.data.sources.base_adapter import BaseDataAdapter

class MyDataAdapter(BaseDataAdapter):
    def fetch_daily_klines(self, symbol, start_date, end_date, adjust="qfq"):
        # 实现数据获取逻辑
        pass
    
    def fetch_stock_list(self, market="A"):
        # 实现股票列表获取
        pass
```

### 2. 注册到 DataService

```python
from quantsys.data.data.data_service import DataService

service = DataService()

# 添加自定义数据源
my_adapter = MyDataAdapter()
service.manager.add_source(
    name="my_source",
    adapter=my_adapter,
    priority=3,  # 优先级（数字越小越高）
    enabled=True
)
```

## 配置文件

编辑 `quantsys/data/data/config.py` 来配置数据源：

```python
# 数据源优先级
DATA_SOURCE_PRIORITIES = {
    "tushare": 1,   # 最高优先级
    "akshare": 2,   # 次优先级
    "my_source": 3, # 自定义数据源
}

# 缓存配置
CACHE_MAX_SIZE = 1000  # 最大缓存项数
CACHE_DEFAULT_TTL = 300  # 默认TTL（秒）
```

## 最佳实践

### 1. 生产环境配置

```python
# 启用所有功能
service = DataService(
    cache_enabled=True,      # 启用缓存
    validate_data=True,      # 启用数据验证
)
```

### 2. 批量下载

```python
symbols = ["000001", "000002", "600000", "600519"]

for symbol in symbols:
    try:
        df = service.get_daily_klines(symbol, days=365)
        # 处理数据
    except Exception as exc:
        print(f"Failed to fetch {symbol}: {exc}")
```

### 3. 监控健康状态

```python
# 定期检查数据源健康状态
health = service.get_health_status()

for source, status in health.items():
    if not status['available']:
        print(f"⚠️ {source} is unavailable!")
        # 发送告警
```

### 4. 手动降级

```python
# 临时禁用某个数据源
service.manager.disable_source("tushare")

# 重新启用
service.manager.enable_source("tushare")
```

## 故障排查

### 问题1：Tushare 连接失败

**原因**：Token 未设置或无效

**解决**：
```bash
export TUSHARE_TOKEN="your_valid_token"
```

### 问题2：所有数据源都失败

**原因**：网络问题或数据源维护

**解决**：
1. 检查网络连接
2. 查看健康状态：`service.get_health_status()`
3. 重置健康状态：`service.reset_health_status()`

### 问题3：数据不一致

**原因**：不同数据源的数据可能略有差异

**解决**：
- 优先使用 Tushare（数据质量最高）
- 启用数据验证：`DataService(validate_data=True)`

## 示例代码

查看完整示例：
```bash
python -m quantsys.data.data.examples.multi_source_example
```

## 性能优化

### 1. 使用缓存

```python
# 启用缓存可以减少90%的API调用
service = DataService(cache_enabled=True)
```

### 2. 批量请求

```python
# 批量下载时使用较小的 days 参数
for symbol in symbols:
    df = service.get_daily_klines(symbol, days=30)  # 而不是 days=3650
```

### 3. 限流控制

```python
import time

for symbol in symbols:
    df = service.get_daily_klines(symbol, days=30)
    time.sleep(0.1)  # 避免触发限流
```

## 未来计划

- [ ] 添加 BaoStock 适配器
- [ ] 添加 efinance 适配器
- [ ] 支持分钟级K线数据
- [ ] 支持实时行情数据
- [ ] 添加数据质量评分
- [ ] 支持异步并行请求
- [ ] 添加数据源性能监控
