# Redis缓存集成指南

## 概述

quantsys-v2已集成Redis分布式缓存，用于缓存热数据以减少数据库压力。系统支持自动降级：Redis不可用时自动切换到内存缓存。

## 架构

```
┌─────────────────┐
│  DataService    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  CacheService   │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ Memory │ │ Redis  │
│ Cache  │ │ Cache  │
└────────┘ └────────┘
```

## 安装依赖

```bash
cd quantsys-v2
pip install -r requirements.txt
```

新增依赖：
- `redis>=5.0.0` - Redis Python客户端
- `hiredis>=2.2.0` - C扩展，提升性能

## Redis安装

### macOS
```bash
brew install redis
brew services start redis
```

### Ubuntu/Debian
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

### Docker
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

## 配置

### 环境变量

创建 `.env` 文件：

```bash
# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # 可选
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
```

### 缓存TTL配置

在 `config/redis_config.py` 中配置：

```python
CACHE_TTL = {
    'kline_latest': 60,          # 最新K线: 1分钟
    'kline_daily': 300,          # 日K线数据: 5分钟
    'factor_latest': 300,        # 最新因子: 5分钟
    'factor_history': 600,       # 因子历史: 10分钟
    'stock_info': 3600,          # 股票信息: 1小时
    'market_overview': 300,      # 市场概览: 5分钟
    'portfolio': 60,             # 投资组合: 1分钟
    'signal': 180,               # 信号数据: 3分钟
    'risk_metrics': 300,         # 风险指标: 5分钟
}
```

## 使用方法

### 1. 初始化缓存服务

```python
from config.cache_factory import create_cache_service

# 创建Redis缓存（自动降级）
cache = create_cache_service(use_redis=True)

# 或强制使用内存缓存
cache = create_cache_service(use_redis=False)
```

### 2. 在DataService中使用

```python
from services.data_service import DataService
from config.cache_factory import create_cache_service

# 创建带缓存的DataService
cache = create_cache_service(use_redis=True)
ds = DataService(cache_manager=cache)

# 获取数据（自动缓存）
kline = ds._get_latest_kline_cached('000001.SZ')
factors = ds._get_latest_factors_cached('000001.SZ')

# 清除缓存
ds.invalidate_stock_cache('000001.SZ')

# 查看缓存统计
stats = ds.get_cache_stats()
print(stats)
```

### 3. 直接使用CacheService

```python
from services.cache_service import CacheService
from config.cache_factory import create_cache_service

cache = create_cache_service(use_redis=True)

# 设置缓存
cache.set('klines', 'AAPL:2024-01-01', {'close': 100.0}, ttl=300)

# 获取缓存
data = cache.get('klines', 'AAPL:2024-01-01')

# 删除缓存
cache.delete('klines', 'AAPL:2024-01-01')

# 模式匹配删除
cache.invalidate_by_pattern('klines', 'AAPL:*')

# 清空命名空间
cache.clear_namespace('klines')
```

## 命令行工具

### 测试Redis连接

```bash
python scripts/init_redis.py test
```

### 查看配置

```bash
python scripts/init_redis.py config
```

### 查看缓存统计

```bash
python scripts/init_redis.py stats
```

### 清除缓存

```bash
# 清除所有缓存
python scripts/init_redis.py clear

# 清除指定命名空间
python scripts/init_redis.py clear --namespace klines
```

### 预热缓存

```bash
python scripts/init_redis.py warmup
```

## 测试

### 运行所有缓存测试

```bash
cd quantsys-v2
pytest tests/test_cache_service.py -v
pytest tests/test_redis_cache.py -v
```

### 运行特定测试

```bash
# 测试Redis后端
pytest tests/test_redis_cache.py::TestRedisCacheBackend -v

# 测试性能
pytest tests/test_redis_cache.py::TestCachePerformance -v -s

# 测试DataService集成
pytest tests/test_redis_cache.py::TestDataServiceWithRedis -v
```

## 缓存策略

### Look-Aside模式

系统采用Look-Aside（旁路）缓存模式：

1. **读取流程**：
   - 先查缓存
   - 缓存命中 → 返回数据
   - 缓存未命中 → 查数据库 → 写入缓存 → 返回数据

2. **写入流程**：
   - 更新数据库
   - 清除相关缓存（或更新缓存）

### 缓存键设计

```
命名空间:业务键

示例：
klines:latest:000001.SZ          # 最新K线
klines:000001.SZ:2024-01-01:2024-12-31  # 历史K线
factors:latest:000001.SZ         # 最新因子
stocks:info:000001.SZ            # 股票信息
```

### 缓存失效策略

1. **TTL自动过期**：根据数据更新频率设置合理的TTL
2. **主动失效**：数据更新时主动清除相关缓存
3. **模式匹配清除**：批量清除相关缓存

## 性能优化

### 1. 使用hiredis加速

```bash
pip install hiredis
```

hiredis是C扩展，可提升Redis性能2-3倍。

### 2. 批量操作

```python
# 批量获取
symbols = ['000001.SZ', '000002.SZ', '000003.SZ']
for symbol in symbols:
    cache.set('klines', f'latest:{symbol}', data, ttl=60)
```

### 3. 连接池

Redis客户端默认使用连接池，无需额外配置。

### 4. 管道操作（高级）

```python
import redis
from config.redis_config import get_redis_config

config = get_redis_config()
client = redis.Redis(**config)

# 使用管道批量操作
pipe = client.pipeline()
for i in range(100):
    pipe.set(f'key{i}', f'value{i}')
pipe.execute()
```

## 监控

### 查看Redis状态

```bash
redis-cli info stats
redis-cli info memory
```

### 查看缓存命中率

```python
stats = cache.get_stats()
print(f"命中率: {stats['hit_rate']*100:.1f}%")
print(f"命中次数: {stats['hits']}")
print(f"未命中次数: {stats['misses']}")
```

### 查看Redis键

```bash
redis-cli keys "klines:*"
redis-cli keys "factors:*"
```

## 故障处理

### Redis连接失败

系统会自动降级到内存缓存，不影响主流程：

```
WARNING - Redis连接失败，降级到内存缓存: Connection refused
INFO - 使用内存缓存后端
```

### 缓存数据不一致

手动清除缓存：

```python
# 清除特定股票缓存
ds.invalidate_stock_cache('000001.SZ')

# 清除所有K线缓存
cache.clear_namespace('klines')

# 清除所有缓存
cache.clear_all()
```

### Redis内存不足

配置Redis最大内存和淘汰策略：

```bash
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

## 最佳实践

1. **合理设置TTL**：根据数据更新频率设置，避免过长或过短
2. **避免缓存大对象**：单个缓存值建议不超过1MB
3. **使用命名空间隔离**：不同业务使用不同命名空间
4. **监控缓存命中率**：定期检查，优化缓存策略
5. **异常处理**：所有缓存操作都有异常处理，不影响主流程
6. **不缓存敏感数据**：密码、密钥等不应缓存

## 示例：完整工作流

```python
from config.cache_factory import create_cache_service
from services.data_service import DataService

# 1. 初始化
cache = create_cache_service(use_redis=True)
ds = DataService(cache_manager=cache)

# 2. 获取数据（自动缓存）
symbol = '000001.SZ'
kline = ds._get_latest_kline_cached(symbol)
factors = ds._get_latest_factors_cached(symbol)

# 3. 查看统计
stats = ds.get_cache_stats()
print(f"缓存后端: {stats['backend']}")
print(f"命中率: {stats.get('hit_rate', 0)*100:.1f}%")

# 4. 数据更新后清除缓存
ds.invalidate_stock_cache(symbol)

# 5. 关闭连接
ds.close()
```

## 参考资料

- [Redis官方文档](https://redis.io/documentation)
- [redis-py文档](https://redis-py.readthedocs.io/)
- [缓存设计模式](https://docs.microsoft.com/en-us/azure/architecture/patterns/cache-aside)
