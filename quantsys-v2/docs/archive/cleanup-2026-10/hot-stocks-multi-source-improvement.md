# 热搜股票多数据源改进报告

**日期**: 2026-06-04  
**作者**: Kiro AI Agent

## 问题背景

原 `market.hot_stocks` 功能仅依赖东方财富单一数据源（akshare `stock_hot_rank_em`），在数据源不稳定时会返回错误：

```
HTTP 503: 暂时无法获取热搜股票数据: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
```

## 解决方案

实现了**多数据源 failover 机制**，参考实时行情数据的架构设计：

### 1. 数据源优先级

| 优先级 | 数据源 | API 函数 | 支持市场 | 数据量 | 状态 |
|--------|--------|----------|----------|--------|------|
| 1 | 雪球关注排行 | `stock_hot_follow_xq()` | A股 | 5604条 | ✅ 稳定 |
| 2 | 雪球交易排行 | `stock_hot_deal_xq()` | A股 | 5604条 | ✅ 稳定 |
| 3 | 东方财富热搜 | `stock_hot_rank_em()` | A股/港股/美股 | 100条 | ⚠️ 不稳定 |

### 2. 实现架构

```
market_cli (TypeScript)
    ↓
market_data_service.get_hot_stocks() (Python)
    ↓
HotStockSource.get_hot_stocks_with_fallback()
    ↓
├─ 1. 雪球关注排行 → 成功 ✓
├─ 2. 雪球交易排行 → 备用
└─ 3. 东方财富热搜 → 备用
```

### 3. 核心文件

- **数据源类**: `quantsys-v2/data_sources/hot_stock_source.py`
  - `get_hot_stocks_xueqiu_follow()` — 雪球关注排行
  - `get_hot_stocks_xueqiu_deal()` — 雪球交易排行
  - `get_hot_stocks_eastmoney()` — 东方财富热搜
  - `get_hot_stocks_with_fallback()` — 自动 failover

- **服务层**: `quantsys-v2/services/market_data_service.py`
  - `get_hot_stocks()` — 调用多数据源管理器

- **配置文件**: `quantsys-v2/data_sources/sources_config.yaml`
  - 新增 `get_hot_stocks` 配置项

## 测试结果

### 单数据源测试

```
1. 雪球关注排行: ✓ 成功（5604条）
2. 雪球交易排行: ✓ 成功（5604条）
3. 东方财富热搜: ✗ 失败（JSON解析错误）
```

### Failover 测试

```
✓ 成功！
  数据源: xueqiu_follow
  排行类型: 关注排行
  数据条数: 5604

  前10名热搜股票:
     1. 贵州茅台 (SH600519) - 热度: 3,643,347 | 价格: 1268.0
     2. 中国平安 (SH601318) - 热度: 3,088,284 | 价格: 53.23
     3. 招商银行 (SH600036) - 热度: 2,850,325 | 价格: 38.1
     4. 格力电器 (SZ000651) - 热度: 2,551,007 | 价格: 38.88
     5. 比亚迪 (SZ002594) - 热度: 2,353,981 | 价格: 93.44
```

### 完整调用链测试

```
TypeScript Agent → market_cli → Python API → 多数据源
✓ 成功（35秒，包含数据抓取时间）
```

## 改进效果

### 可靠性提升

- ✅ **容错能力**: 单一数据源失败时自动切换到备用源
- ✅ **数据量**: 从100条提升到5604条（56倍）
- ✅ **成功率**: 从不稳定提升到稳定可用

### 数据质量

- ✅ **数据新鲜度**: 实时关注度数据
- ✅ **数据完整性**: 包含股票代码、名称、热度、最新价
- ✅ **排行类型**: 支持关注排行和交易排行两种维度

## 使用方式

### 前端工具调用

```typescript
// 查询 A 股热搜股票
market_cli({ command: "market.hot_stocks" })
```

### Python 服务调用

```python
from services.market_data_service import market_data_service

result = market_data_service.get_hot_stocks("A股")
if result['success']:
    stocks = result['data']['stocks']
    print(f"数据源: {result.get('source')}")
    print(f"数据量: {len(stocks)}")
```

### 直接调用数据源

```python
from data_sources.hot_stock_source import get_hot_stock_source

source = get_hot_stock_source()
result = source.get_hot_stocks_with_fallback("A股")
```

## 注意事项

1. **性能**: 雪球数据抓取需要约35秒（分页抓取29页）
2. **市场支持**: 港股/美股暂时仅东方财富支持（但当前不稳定）
3. **缓存建议**: 建议在 API 层增加1分钟缓存，减少重复调用

## 后续优化方向

1. **性能优化**: 考虑并行抓取或缓存机制
2. **港股/美股**: 寻找雪球的港股/美股热搜API
3. **数据融合**: 考虑将多个数据源的数据进行综合排名
4. **监控告警**: 添加数据源健康监控和自动告警

## 相关文件

- `quantsys-v2/data_sources/hot_stock_source.py` — 数据源实现
- `quantsys-v2/services/market_data_service.py` — 服务层集成
- `quantsys-v2/data_sources/sources_config.yaml` — 数据源配置
- `quantsys-v2/data_sources/test_hot_stocks.py` — 测试脚本
- `src/infrastructure/tools/cli/market-cli-tool.ts` — TypeScript 前端工具
