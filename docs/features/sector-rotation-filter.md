# 行业相对强度筛选功能

## 功能概述

扩展了 `invest_opportunity_scan` 工具，支持按行业相对强度筛选标的池。采用经典的 Top-Down 投资方法：先选择强势行业，再在强势行业中精选个股。

## 实现架构

### 新增组件

1. **SectorRotationService** (`services/sector_rotation_service.py`)
   - 计算行业评分（动量 + 资金流 + 相对强度）
   - 筛选强势行业
   - 提供行业排名查询

2. **API 端点**
   - `GET/POST /api/sectors/ranking` - 独立的行业排名查询
   - `POST /api/signals/scan` - 扩展支持 `sectorFilter` 参数

3. **Repository 扩展**
   - `StockRepository.get_all_industries()` - 获取所有行业列表
   - `StockRepository.get_stocks_by_industries()` - 根据行业获取股票

## 使用方式

### 1. TypeScript Agent 工具

```typescript
// 启用行业筛选
await agent.useTool('opportunity_scan', {
  sectorFilter: {
    enabled: true,
    topN: 3,                    // 选择前3个强势行业
    minSectorScore: 0.5,        // 行业最低评分（可选）
    excludeSectors: ['银行'],   // 排除的行业（可选）
    market: 'A'                 // A股或港股
  },
  conditions: ['rsi_oversold', 'roe_high']
});
```

### 2. 直接调用 API

**行业排名查询：**
```bash
curl -X GET "http://127.0.0.1:5001/api/sectors/ranking?market=A&limit=5"
```

**响应：**
```json
{
  "success": true,
  "sectors": [
    {
      "name": "食品饮料",
      "code": "BK0438",
      "composite_score": 0.85,
      "momentum": 0.82,
      "flow": 0.88,
      "relative_strength": 0.86,
      "rank": 1
    }
  ],
  "total": 5,
  "market": "A",
  "timestamp": "2026-05-27T12:00:00"
}
```

**机会扫描（带行业筛选）：**
```bash
curl -X POST "http://127.0.0.1:5001/api/signals/scan" \
  -H "Content-Type: application/json" \
  -d '{
    "sectorFilter": {
      "enabled": true,
      "topN": 3,
      "market": "A"
    },
    "minScore": 60,
    "technical": ["rsi_oversold"],
    "fundamental": ["roe_high"]
  }'
```

**响应：**
```json
{
  "success": true,
  "opportunities": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "score": 85,
      "industry": "食品饮料",
      "sector_score": 0.85,
      "sector_rank": 1,
      ...
    }
  ],
  "total": 15,
  "scanned": 350,
  "sectorInfo": {
    "enabled": true,
    "selectedSectors": [
      {"name": "食品饮料", "score": 0.85, "rank": 1},
      {"name": "电子", "score": 0.78, "rank": 2},
      {"name": "医药生物", "score": 0.72, "rank": 3}
    ],
    "totalSectors": 30
  }
}
```

## 行业评分算法

### A股权重
- 动量：40%
- 资金流：35%
- 相对强度：25%

### 港股权重
- 南向资金：40%
- 动量：35%
- 相对强度：25%

### 指标计算（简化版）

1. **动量**：最近20日行业平均涨幅
2. **资金流**：最近5日 vs 前5日成交量变化
3. **相对强度**：行业收益 - 大盘收益（沪深300）

## 性能优化

- 批量查询K线数据（`batch_get_recent_klines`）
- 行业采样限制（每个行业最多50只股票）
- 数据库查询优化（单次查询获取行业成分股）

## 文件清单

### Python 后端
- `quantsys-v2/services/sector_rotation_service.py` - 行业轮动服务
- `quantsys-v2/repositories/stock_repository.py` - 新增行业查询方法
- `quantsys-v2/api/routes/sectors.py` - 行业排名端点
- `quantsys-v2/api/routes/signals.py` - 扩展机会扫描端点
- `quantsys-v2/api/shared.py` - 注册服务实例
- `quantsys-v2/api/server.py` - 注册路由

### TypeScript 前端
- `src/infrastructure/quant/types.ts` - 扩展类型定义
- `src/infrastructure/tools/invest/opportunity-scan-tool.ts` - 扩展工具参数

## 测试

运行测试脚本：
```bash
cd quantsys-v2
python test_sector_filter.py
```

## 注意事项

1. **数据依赖**：需要数据库中有股票的行业分类数据（`stocks.industry` 字段）
2. **K线数据**：需要至少20日的K线数据才能计算行业指标
3. **性能**：首次计算行业排名可能需要几秒钟（取决于行业数量和股票数量）
4. **市场支持**：目前支持 A股 和 港股 两个市场

## 未来优化方向

1. 增加行业评分缓存（避免重复计算）
2. 支持更多行业指标（北向资金、机构持仓等）
3. 行业轮动策略回测
4. 行业热度趋势图表
