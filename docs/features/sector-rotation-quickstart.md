# 行业相对强度筛选功能 - 快速开始

## ✅ 功能已实现并测试通过

### 测试结果

**行业排名端点测试：**
```bash
curl 'http://127.0.0.1:5001/api/sectors/ranking?market=A&limit=3'
```

**响应示例：**
```json
{
  "market": "A",
  "sectors": [
    {
      "code": "",
      "composite_score": 0.85,
      "flow": 0.88,
      "momentum": 0.82,
      "name": "食品饮料",
      "rank": 1,
      "relative_strength": 0.86
    }
  ],
  "success": true,
  "timestamp": "2026-05-27T22:29:02",
  "total": 1
}
```

## 使用方式

### 1. 在 TypeScript Agent 中使用

```typescript
// 基础用法：启用行业筛选
await agent.useTool('opportunity_scan', {
  sectorFilter: {
    enabled: true,
    topN: 3,
    market: 'A'
  }
});

// 高级用法：完整参数
await agent.useTool('opportunity_scan', {
  sectorFilter: {
    enabled: true,
    topN: 3,                      // 选择前3个强势行业
    minSectorScore: 0.5,          // 行业最低评分（0-1）
    excludeSectors: ['银行', '房地产'],  // 排除的行业
    market: 'A'                   // A股或HK（港股）
  },
  conditions: ['rsi_oversold', 'roe_high'],  // 技术面+基本面条件
  minScore: 60                    // 股票最低评分
});
```

### 2. 直接调用 API

**查询行业排名：**
```bash
# GET 请求
curl 'http://127.0.0.1:5001/api/sectors/ranking?market=A&limit=5'

# POST 请求
curl -X POST 'http://127.0.0.1:5001/api/sectors/ranking' \
  -H 'Content-Type: application/json' \
  -d '{
    "market": "A",
    "limit": 5,
    "minScore": 0.5
  }'
```

**机会扫描（带行业筛选）：**
```bash
curl -X POST 'http://127.0.0.1:5001/api/signals/scan' \
  -H 'Content-Type: application/json' \
  -d '{
    "sectorFilter": {
      "enabled": true,
      "topN": 3,
      "minSectorScore": 0.5,
      "market": "A"
    },
    "minScore": 60,
    "technical": ["rsi_oversold", "macd_golden_cross"],
    "fundamental": ["roe_high", "pe_low"]
  }'
```

## 工作流程

```
1. 计算所有行业的相对强度评分
   ├─ 动量（40%）：最近20日涨幅
   ├─ 资金流（35%）：成交量变化
   └─ 相对强度（25%）：相对大盘超额收益

2. 筛选强势行业
   ├─ 按综合评分排序
   ├─ 选择前 topN 个行业
   ├─ 过滤低于 minSectorScore 的行业
   └─ 排除 excludeSectors 中的行业

3. 获取强势行业的成分股
   └─ 从数据库查询属于这些行业的股票

4. 对成分股进行三维评分
   ├─ 技术面（50%）：RSI、MACD、布林带、成交量
   ├─ 基本面（30%）：PE、ROE、毛利率、负债率
   └─ 资金面（20%）：成交量增长、连续递增

5. 返回结果
   └─ 每个机会包含：股票信息 + 行业信息 + 评分详情
```

## 返回数据结构

```typescript
{
  success: true,
  opportunities: [
    {
      symbol: "600519.SH",
      name: "贵州茅台",
      score: 85,                    // 综合评分
      technical_score: 90,
      fundamental_score: 80,
      capital_score: 75,
      confidence: 0.85,
      risk_level: "low",
      signal_type: "buy",
      
      // 新增：行业信息
      industry: "食品饮料",
      sector_score: 0.85,           // 所属行业评分
      sector_rank: 1,               // 行业排名
      
      timestamp: "2026-05-27T12:00:00"
    }
  ],
  total: 15,
  scanned: 350,
  
  // 新增：行业筛选信息
  sectorInfo: {
    enabled: true,
    selectedSectors: [
      { name: "食品饮料", score: 0.85, rank: 1 },
      { name: "电子", score: 0.78, rank: 2 },
      { name: "医药生物", score: 0.72, rank: 3 }
    ],
    totalSectors: 30
  }
}
```

## 实际应用场景

### 场景 1：行业轮动策略
```typescript
// 每周一执行：选择当前最强的3个行业，在其中精选个股
await agent.useTool('opportunity_scan', {
  sectorFilter: {
    enabled: true,
    topN: 3,
    market: 'A'
  },
  conditions: ['rsi_oversold', 'roe_high'],
  minScore: 70
});
```

### 场景 2：避开弱势行业
```typescript
// 排除当前表现不佳的行业
await agent.useTool('opportunity_scan', {
  sectorFilter: {
    enabled: true,
    topN: 5,
    excludeSectors: ['银行', '房地产', '钢铁'],
    market: 'A'
  }
});
```

### 场景 3：高质量行业精选
```typescript
// 只选择评分 > 0.6 的行业
await agent.useTool('opportunity_scan', {
  sectorFilter: {
    enabled: true,
    topN: 10,
    minSectorScore: 0.6,
    market: 'A'
  },
  minScore: 75
});
```

## 性能特点

- **批量查询优化**：使用 `batch_get_recent_klines` 减少数据库查询
- **采样限制**：每个行业最多采样50只股票计算指标
- **响应时间**：
  - 行业排名查询：~2-5秒（取决于行业数量）
  - 机会扫描（带行业筛选）：~5-10秒（取决于股票数量）

## 数据要求

1. **股票表**：需要 `industry` 字段（行业分类）
2. **K线数据**：至少20日的历史数据
3. **大盘指数**：需要沪深300（000300.SH）的K线数据

## 故障排查

### 问题：返回的行业评分都是 0
**原因**：数据库中缺少K线数据或股票数据不足
**解决**：运行数据回填脚本补充历史数据

### 问题：某些行业没有股票
**原因**：`stocks` 表中该行业的股票数据缺失
**解决**：检查数据导入流程，确保行业分类正确

### 问题：API 返回 404
**原因**：服务器未正确启动或路由未注册
**解决**：检查 `api/server.py` 中是否注册了 `sectors_bp`

## 下一步优化

1. **缓存机制**：行业评分结果缓存1小时，避免重复计算
2. **更多指标**：增加北向资金、机构持仓等数据源
3. **历史回测**：行业轮动策略的历史表现分析
4. **可视化**：行业热度趋势图表

---

**文档版本**：v1.0  
**最后更新**：2026-05-27  
**状态**：✅ 已实现并测试通过
