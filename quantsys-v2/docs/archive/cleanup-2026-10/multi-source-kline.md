# K线数据多数据源支持

## 概述

K线数据现在支持多数据源自动降级，参考报价和财务数据的模式实现。

## 数据源优先级

1. **Database (主数据源)** - 本地PostgreSQL数据库
   - 速度快，数据稳定
   - 支持：daily, weekly, monthly
   - 适用于历史数据查询

2. **AkShare (备用数据源)** - 在线API
   - 数据库无数据时自动降级
   - 支持：daily, weekly, monthly, 1m, 5m, 15m, 30m, 60m
   - 适用于分钟级数据和实时数据

## API 使用

### 端点
```
GET /api/stock/<symbol>/history
```

### 参数
- `period`: 周期 (daily|weekly|monthly|1m|5m|15m|30m|60m)，默认 daily
- `start_date`: 开始日期 (YYYY-MM-DD)
- `end_date`: 结束日期 (YYYY-MM-DD)
- `limit`: 返回数据点数，默认60，最大200
- `source`: 数据源选择 (auto|db|akshare)，默认 auto

### 响应格式
```json
{
  "symbol": "600519",
  "period": "daily",
  "count": 30,
  "source": "database",  // 标识实际使用的数据源
  "data": [
    {
      "date": "2024-01-01",
      "open": 100.0,
      "high": 105.0,
      "low": 99.0,
      "close": 103.0,
      "volume": 1000000,
      "change_pct": 3.0
    }
  ]
}
```

## 架构设计

### 1. Provider 层
- `KlineProvider` (base.py) - 抽象基类
- `DatabaseKlineProvider` (database.py) - 数据库数据源
- `AkshareKlineProvider` (akshare.py) - AkShare数据源

### 2. Manager 层
- `DataProviderManager` (manager.py) - 统一管理多个数据源
- `get_klines()` 方法 - 自动降级逻辑

### 3. API 层
- `/api/stock/<symbol>/history` - 使用 DataProviderManager

## 降级逻辑

```python
# 1. 尝试数据库
database_result = DatabaseKlineProvider.get_klines(...)
if database_result:
    return database_result

# 2. 数据库失败，尝试 AkShare
akshare_result = AkshareKlineProvider.get_klines(...)
if akshare_result:
    return akshare_result

# 3. 所有数据源都失败
return error with attempted_sources list
```

## TypeScript 端集成

TypeScript Agent 端无需修改，直接调用后端 API：

```typescript
// agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts
export async function getKlineHistory(
  symbol: string,
  period: 'daily' | 'weekly' | 'monthly' = 'daily',
  startDate?: string,
  endDate?: string,
  limit: number = 60
): Promise<KlineData> {
  // 直接调用后端 API，后端自动处理多数据源降级
  const url = `${V2_API_BASE}/api/stock/${symbol}/history?period=${period}&limit=${limit}`;
  const response = await fetchV2<any>(url);
  return response;
}
```

## 健康监控

DataProviderManager 会追踪每个数据源的成功/失败次数：

```python
provider_manager = get_data_provider_manager()
health = provider_manager.get_provider_health()

# 输出示例:
# {
#   "database": {"success": 100, "failure": 5},
#   "akshare": {"success": 20, "failure": 2}
# }
```

## 测试

```bash
# 运行单元测试
cd quantsys-v2
python -m pytest adapters/outbound/datasources/providers/kline/test_providers.py -v

# 测试 API 端点
curl "http://127.0.0.1:5001/api/stock/600519/history?period=daily&limit=10"
```

## 扩展新数据源

要添加新的 K 线数据源（如 Tushare、Wind 等）：

1. 创建新的 Provider 类：
```python
# adapters/outbound/datasources/providers/kline/tushare.py
from adapters.outbound.datasources.providers.kline.base import KlineProvider, KlineData

class TushareKlineProvider(KlineProvider):
    @property
    def name(self) -> str:
        return "tushare"
    
    def get_klines(self, symbol, period, start_date, end_date):
        # 实现 Tushare 数据获取逻辑
        pass
```

2. 在 DataProviderManager 中注册：
```python
# adapters/outbound/datasources/manager.py
from adapters.outbound.datasources.providers.kline.tushare import TushareKlineProvider

class DataProviderManager:
    def __init__(self, ds=None):
        # ...
        self.kline_providers = []
        if ds and hasattr(ds, 'kline'):
            self.kline_providers.append(DatabaseKlineProvider(ds.kline))
        self.kline_providers.append(TushareKlineProvider())  # 新增
        self.kline_providers.append(AkshareKlineProvider())
```

## 注意事项

1. **数据一致性**: 不同数据源可能有细微差异（复权方式、精度等）
2. **速率限制**: AkShare 有速率限制，频繁调用可能失败
3. **数据延迟**: 实时数据可能有几秒到几分钟的延迟
4. **周期支持**: 分钟级数据仅 AkShare 支持，数据库暂不支持

## 相关文件

- `quantsys-v2/adapters/outbound/datasources/providers/kline/` - Provider 实现
- `quantsys-v2/adapters/outbound/datasources/manager.py` - Manager 管理器
- `quantsys-v2/adapters/inbound/api/routes/quote_market.py` - API 路由
- `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts` - TS 客户端
- `agent-ts/src/infrastructure/tools/data/fetch-kline-tool.ts` - Agent 工具
