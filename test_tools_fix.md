# 工具修复完成报告

## 问题诊断

三个工具执行失败：

1. **data_fetch_market_sentiment** - HTTP 404错误
2. **opportunity_scan** - HTTP 404错误  
3. **opponent_behavior** - 没有v2端点映射

## 根本原因

quantsys-v2 后端已从 Flask 迁移到 FastAPI，但存在端点映射不一致问题：

1. **opponent_behavior**: 工具直接调用 `/api/game/market/opponent-behavior`，但未在端点映射表注册
2. **market.sentiment**: 路径不匹配
   - agent-ts 映射: `/api/market/sentiment`
   - FastAPI 实际: `/api/sentiment/market`
3. **opportunity_scan**: 调用 `/api/signals/scan`，但 FastAPI 的 signals 路由中缺少该端点

## 修复内容

### 1. agent-ts 端点映射修复

**文件**: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`

✅ 修复 `market.sentiment` 路径映射:
```typescript
"market.sentiment": { path: "/api/sentiment/market", method: "GET" }
```

✅ 添加 `market.opponent_behavior` 端点映射（命名规范修正）:
```typescript
"market.opponent_behavior": { path: "/api/game/market/opponent-behavior", method: "GET" }
```

### 2. opponent_behavior 工具修复

**文件**: `agent-ts/src/infrastructure/tools/game/opponent-behavior-tool.ts`

✅ 改用命令格式调用，并使用正确的命名规范:
```typescript
// 修复前
const result = await runQuantV2('/api/game/market/opponent-behavior', 'GET');

// 修复后  
const result = await runQuantV2('market.opponent_behavior', {});
```

### 3. quantsys-v2 后端补充

**文件**: `quantsys-v2/adapters/inbound/fastapi_app/routes/signals_async.py`

✅ 添加 `/api/signals/scan` 端点:
```python
@router.post("/scan", response_model=ApiResponse, summary="扫描交易机会")
async def scan_opportunities(
    symbols: Optional[List[str]] = Body(None),
    technical: Optional[List[str]] = Body(None),
    fundamental: Optional[List[str]] = Body(None),
    limit: int = Body(20),
    weights: Optional[Dict[str, float]] = Body(None)
):
    # 临时返回示例数据（TODO: 接入实际服务）
    ...
```

## 端点映射一览

| 工具 | agent-ts 命令 | FastAPI 路径 | 状态 |
|-----|--------------|-------------|------|
| data_fetch_market_sentiment | `market.sentiment` | `/api/sentiment/market` | ✅ 已修复 |
| opportunity_scan | `scanOpportunities()` | `/api/signals/scan` | ✅ 已添加 |
| opponent_behavior | `market.opponent_behavior` | `/api/game/market/opponent-behavior` | ✅ 已修复 |

## 下一步操作

### 1. 重启后端服务

```bash
cd quantsys-v2
python adapters/inbound/fastapi_app/main.py
```

### 2. 重新构建 agent-ts

```bash
cd agent-ts
npm run build
```

### 3. 测试工具

```bash
# 测试 opponent_behavior
cd agent-ts
node -e "
const { runQuantV2 } = require('./dist/infrastructure/adapters/quant/quant-v2-client.js');
runQuantV2('market.opponent_behavior', {}).then(r => console.log(JSON.stringify(r, null, 2)));
"

# 测试 market.sentiment  
node -e "
const { runQuantV2 } = require('./dist/infrastructure/adapters/quant/quant-v2-client.js');
runQuantV2('market.sentiment', {}).then(r => console.log(JSON.stringify(r, null, 2)));
"

# 测试 opportunity_scan
node -e "
const { scanOpportunities } = require('./dist/infrastructure/adapters/quant/quant-v2-client.js');
scanOpportunities({limit: 5}).then(r => console.log(JSON.stringify(r, null, 2)));
"
```

## 注意事项

⚠️ **当前返回示例数据**

以下端点目前返回硬编码的示例数据，需要后续接入实际服务：

1. `/api/game/market/opponent-behavior` - 需要接入 OpponentBehaviorService
2. `/api/signals/scan` - 需要接入 OpportunityScannerService  
3. `/api/sentiment/market` - 需要接入 SentimentAsyncRepository

## 架构改进建议

### 短期（P0）

- [ ] 实现 OpportunityScannerService（复用旧 Flask 逻辑）
- [ ] 实现 SentimentAsyncRepository.get_market_sentiment_summary()
- [ ] 完善 opponent_behavior 的数据计算逻辑

### 中期（P1）

- [ ] 统一端点命名规范（建议：`/api/{domain}/{action}` 格式）
- [ ] 添加端点映射验证测试（防止映射表与实际路由不一致）
- [ ] 生成 OpenAPI 文档供 agent-ts 自动发现端点

### 长期（P2）  

- [ ] 考虑使用 tRPC 或 GraphQL 实现类型安全的 RPC 通信
- [ ] 端点映射自动生成（从 FastAPI 路由表导出到 TS）

## 相关文件清单

### agent-ts
- `src/infrastructure/adapters/quant/quant-v2-client.ts` - 端点映射表
- `src/infrastructure/tools/game/opponent-behavior-tool.ts` - 对手行为工具
- `src/infrastructure/tools/data/fetch-market-sentiment-tool.ts` - 市场情绪工具
- `src/infrastructure/tools/invest/opportunity-scan-tool.ts` - 机会扫描工具

### quantsys-v2  
- `adapters/inbound/fastapi_app/main.py` - FastAPI 应用入口
- `adapters/inbound/fastapi_app/routes/signals_async.py` - 信号路由
- `adapters/inbound/fastapi_app/routes/p1_batch_async.py` - 情绪分析路由
- `adapters/inbound/fastapi_app/routes/game/intelligence.py` - 博弈智能路由

---

**修复完成时间**: 2026-06-29
**修复人员**: Claude (Kiro AI Assistant)
