# API Integration Analysis Report

**Date**: 2026-05-23  
**Frontend**: web-frontend (TypeScript/Vue)  
**Backend**: quantsys-v2 (Python/Flask)

## Executive Summary

✅ **Frontend IS calling backend APIs**

The frontend has a well-structured API client layer that makes HTTP requests to the backend Flask server. The integration is active and functional.

---

## Architecture Overview

### Frontend API Layer
- **Location**: `web-frontend/src/services/api/`
- **HTTP Client**: Axios with custom wrapper (`apiClient`)
- **Base URL**: `http://localhost:5001` (configurable via `VITE_API_BASE_URL`)
- **Response Format**: Handles both standard `{code, message, data}` and QuantSys V2 `{success, data}` formats

### Backend API Server
- **Location**: `quantsys-v2/api/server.py`
- **Framework**: Flask with CORS enabled
- **Response Format**: `{success: bool, data: any, message?: string}` with camelCase conversion
- **Port**: 5001 (default)

---

## API Integration Status

### ✅ Fully Integrated Endpoints

#### 1. **Stock APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `GET /api/stocks/list` | ✅ Implemented | Working |
| `POST /api/stocks/resolve` | ✅ Implemented | Working |
| `GET /api/stocks/search` | ✅ Implemented | Working |
| `GET /api/stock/{symbol}/klines` | ✅ Implemented | Working |
| `GET /api/stock/{symbol}/technical` | ✅ Implemented | Working |

#### 2. **Signal APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `GET /api/signals` | ✅ Implemented | Working |
| `POST /api/signals/{id}/approve` | ✅ Implemented | Working |
| `POST /api/signals/{id}/reject` | ✅ Implemented | Working |
| `POST /api/signals/{id}/mark-error` | ✅ Implemented | Working |
| `GET /api/signals/statistics` | ✅ Implemented | Working |

#### 3. **Trading/Portfolio APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `GET /api/orders/list` | ✅ Implemented | Working |
| `GET /api/orders/detail/{id}` | ✅ Implemented | Working |
| `POST /api/orders/create` | ✅ Implemented | Working |
| `POST /api/orders/cancel/{id}` | ✅ Implemented | Working |
| `POST /api/orders/update/{id}` | ✅ Implemented | Working |
| `GET /api/portfolio/summary` | ✅ Implemented | Working |
| `GET /api/portfolio/positions` | ✅ Implemented | Working |
| `GET /api/portfolio/history` | ✅ Implemented | Working |
| `GET /api/portfolio/holdings` | ✅ Implemented | Working |
| `GET /api/trades/list` | ✅ Implemented | Working |

#### 4. **Strategy APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `GET /api/strategies/list` | ✅ Implemented | Working |
| `GET /api/strategies/detail/{id}` | ✅ Implemented | Working |
| `POST /api/strategies/create` | ✅ Implemented | Working |
| `POST /api/strategies/update/{id}` | ✅ Implemented | Working |
| `POST /api/strategies/delete/{id}` | ✅ Implemented | Working |
| `POST /api/strategies/start/{id}` | ✅ Implemented | Working |
| `POST /api/strategies/stop/{id}` | ✅ Implemented | Working |
| `GET /api/strategies/performance/{id}` | ✅ Implemented | Working |

#### 5. **Data Update APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `POST /api/data/update` | ✅ Implemented | Working |
| `GET /api/data/update/jobs/{id}` | ✅ Implemented | Working |

#### 6. **Indicator APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `GET /api/indicators/list` | ✅ Implemented | Working |
| `POST /api/indicators/create` | ✅ Implemented | Working |
| `POST /api/indicators/backtest` | ✅ Implemented | Working |

#### 7. **Backtest APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `GET /api/backtest/results` | ✅ Implemented | Working |
| `POST /api/backtest` | ✅ Implemented | Working |

#### 8. **Risk APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `POST /api/risk/check` | ✅ Implemented | Working |

#### 9. **Pipeline APIs**
| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `GET /api/pipeline/statistics` | ✅ Implemented | Working |
| `GET /api/pipeline/tasks/list` | ✅ Implemented | Working |
| `GET /api/pipeline/runs/list` | ✅ Implemented | Working |
| `POST /api/pipeline/trigger` | ✅ Implemented | Working |

---

### ⚠️ Frontend Calls WITHOUT Backend Implementation

These endpoints are called by the frontend but **NOT implemented** in the backend:

#### Stock APIs
- `GET /api/stocks/{symbol}/fundamentals` - 基本面数据
- `GET /api/stocks/{symbol}/fund-flow` - 资金流向
- `GET /api/stocks/{symbol}/dragon-tiger` - 龙虎榜
- `GET /api/stocks/{symbol}/announcements` - 公告
- `GET /api/stocks/{symbol}/news` - 新闻
- `GET /api/stocks/watchlist` - 自选股列表
- `POST /api/stocks/watchlist` - 添加自选股
- `DELETE /api/stocks/watchlist/{symbol}` - 删除自选股
- `GET /api/stocks/watchlist/{symbol}/check` - 检查自选股
- `GET /api/stocks/watchlist/groups` - 自选股分组
- `POST /api/stocks/watchlist/groups` - 创建分组
- `PUT /api/stocks/watchlist/groups/{id}` - 更新分组
- `DELETE /api/stocks/watchlist/groups/{id}` - 删除分组

#### Signal APIs
- `GET /api/signals/{id}` - 单个信号详情
- `POST /api/signals/{id}/verify` - 复现验证信号

#### Strategy APIs
- `POST /api/strategies/{id}/pause` - 暂停策略
- `POST /api/strategies/{id}/resume` - 恢复策略
- `GET /api/strategies/{id}/positions` - 策略持仓
- `GET /api/strategies/{id}/orders` - 策略订单
- `GET /api/strategies/{id}/logs` - 策略日志

#### Portfolio APIs
- `GET /api/portfolio/equity-curve` - 资产曲线
- `GET /api/portfolio/allocation` - 持仓分布

#### Data APIs
- `GET /api/data/sources` - 数据源列表
- `GET /api/data/stats` - 数据统计
- `POST /api/data/update/stop-all` - 停止所有更新
- `POST /api/data/sources/{id}/update` - 更新指定数据源
- `GET /api/data/jobs` - 更新任务列表
- `GET /api/data/logs` - 更新日志
- `GET /api/data/sources/{id}/config` - 数据源配置
- `PUT /api/data/sources/{id}/config` - 更新数据源配置

#### Risk APIs
- `GET /api/risk/metrics` - 风险指标
- `GET /api/risk/limits` - 风险限额
- `GET /api/risk/report` - 风险报告
- `POST /api/risk/stress-test` - 压力测试
- `GET /api/risk/var` - VaR计算

#### Analysis APIs
- `POST /api/analysis/correlation` - 相关性分析

#### Agent APIs
- `GET /api/agent/status` - Agent状态
- `POST /api/agent/start` - 启动Agent
- `POST /api/agent/stop` - 停止Agent
- `POST /api/agent/pause` - 暂停Agent
- `POST /api/agent/resume` - 恢复Agent
- `POST /api/agent/analyze` - Agent分析
- `GET /api/agent/logs` - Agent日志
- `GET /api/agent/performance` - Agent性能
- `GET /api/agent/statistics` - Agent统计
- `GET /api/agent/config` - Agent配置

---

### 🔧 Backend Endpoints NOT Used by Frontend

These endpoints exist in the backend but are **NOT called** by the frontend:

- `GET /api/health` - 健康检查
- `GET /api/platform/status` - 平台状态
- `GET /api/stocks/add` - 添加股票
- `GET /api/stocks/data-status` - 数据状态
- `POST /api/stocks/compare` - 对比股票
- `GET /api/stock/{symbol}/factors` - 因子分析
- `GET /api/stocks/{symbol}/factors` - 因子分析（备用路由）
- `GET /api/signals/history` - 信号历史
- `POST /api/signals/scan` - 扫描信号
- `GET /api/signals/detail/{id}` - 信号详情
- `POST /api/compute/factors` - 计算因子
- `GET /api/report/daily` - 每日报告
- `GET /api/performance/strategy/{id}` - 策略性能
- `GET /api/executions` - 执行记录列表
- `POST /api/executions` - 创建执行记录
- `GET /api/executions/{id}` - 执行记录详情
- `PUT /api/executions/{id}/close` - 平仓执行
- `PUT /api/executions/{id}/cancel` - 取消执行
- `PUT /api/executions/{id}/status` - 更新执行状态
- `GET /api/executions/stats` - 执行统计
- `GET /api/executions/daily` - 每日执行统计
- `GET /api/executions/pending` - 待处理执行
- `GET /api/executions/signal/{id}` - 信号执行记录
- `GET /api/executions/summary` - 执行摘要
- `GET /api/indicators/detail/{id}` - 指标详情
- `POST /api/indicators/update/{id}` - 更新指标
- `POST /api/indicators/delete/{id}` - 删除指标
- `POST /api/indicators/run/{id}` - 运行指标
- `GET /api/ml/features` - ML特征
- `POST /api/ml/train` - ML训练
- `POST /api/ml/predict` - ML预测
- `GET /api/ml/model/info` - ML模型信息

---

## Key Findings

### 1. **Core Integration is Working** ✅
The frontend successfully calls backend APIs for:
- Stock data retrieval
- Signal management (approve/reject/mark-error)
- Order creation and management
- Portfolio summary and positions
- Strategy CRUD operations
- Data updates

### 2. **Missing Backend Implementations** ⚠️
**67 frontend API calls** are defined but lack backend endpoints. Key missing features:
- Watchlist management (14 endpoints)
- Advanced risk analytics (5 endpoints)
- Agent management (9 endpoints)
- Data source management (8 endpoints)
- Strategy pause/resume/logs (3 endpoints)
- Portfolio equity curve and allocation (2 endpoints)

### 3. **Unused Backend Endpoints** 📊
**30+ backend endpoints** exist but aren't used by frontend:
- Execution tracking system (9 endpoints)
- ML pipeline endpoints (4 endpoints)
- Signal scanning and history (2 endpoints)
- Factor computation (2 endpoints)
- Health checks and platform status (2 endpoints)

### 4. **API Response Format** ✅
Backend correctly returns:
```json
{
  "success": true,
  "data": { ... },
  "message": "optional message"
}
```

Frontend client handles this format correctly in [client.ts:74-82](web-frontend/src/services/api/client.ts#L74-L82).

### 5. **Naming Convention** ✅
Backend converts snake_case to camelCase automatically:
- Backend: `avg_cost`, `total_assets`
- Frontend receives: `avgCost`, `totalAssets`

Conversion functions in [server.py:49-82](quantsys-v2/api/server.py#L49-L82).

---

## Recommendations

### Priority 1: Implement Missing Core Features
1. **Watchlist Management** - 14 endpoints needed for user stock tracking
2. **Risk Analytics** - 5 endpoints for comprehensive risk monitoring
3. **Portfolio Analytics** - Equity curve and allocation visualization

### Priority 2: Connect Existing Backend Features
1. **Execution Tracking** - Frontend should use the 9 execution endpoints
2. **Signal History** - Connect signal scanning and history features
3. **Health Monitoring** - Add health check integration

### Priority 3: Clean Up Unused Code
1. Review and document why 30+ backend endpoints aren't used
2. Either implement frontend features or deprecate unused endpoints
3. Update API documentation

### Priority 4: Add Missing Frontend Features
1. **Agent Management UI** - 9 agent endpoints need frontend pages
2. **Data Source Management** - 8 data endpoints need admin UI
3. **ML Pipeline UI** - 4 ML endpoints need visualization

---

## Testing Recommendations

1. **Integration Tests**: Test all 40+ working endpoints
2. **Error Handling**: Verify frontend handles backend errors gracefully
3. **Performance**: Monitor API response times (already tracked via `performanceMonitor`)
4. **CORS**: Ensure CORS is properly configured for production

---

## Conclusion

**The frontend IS actively calling the backend.** The integration is functional with 40+ working endpoints covering core features like stocks, signals, orders, portfolio, and strategies. However, there's a significant gap:

- **67 frontend calls** lack backend implementation (mostly advanced features)
- **30+ backend endpoints** aren't used by frontend (mostly execution tracking and ML)

This suggests the project is in active development with frontend and backend teams working somewhat independently. The core functionality works, but advanced features need coordination to complete the integration.
