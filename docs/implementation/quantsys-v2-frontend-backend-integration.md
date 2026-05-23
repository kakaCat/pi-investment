# QuantSys V2 前后端对接指导文档

## 目标

把 `web-frontend/` Vue 前端接到 `quantsys-v2/` Flask 量化后端。本文只说明应该改哪里、怎么改、接口如何映射，不直接修改业务代码。

## 当前结论

- 前端页面、路由、菜单已经覆盖原型 20 个页面，`npm run build` 可通过。
- 后端主 REST API 在 `quantsys-v2/api/server.py`，默认端口是 `5000`。
- 后端 WebSocket 在 `quantsys-v2/api/server_websocket.py`，当前也是硬编码 `5000`，不能和 REST 服务同时占用同一端口。
- 前端 API 封装已经存在于 `web-frontend/src/services/api/`，但很多路径和后端真实路径不一致。
- 后端响应格式不统一，有的返回 `{count, stocks}`，有的返回 `{success, ...}`，有的直接返回业务对象；前端 `client.ts` 已经可以处理非 `{code,message,data}` 格式，但各 API 模块仍需要做字段适配。

## 推荐对接策略

优先采用“前端适配现有后端 + 后端只补缺失接口”的方式。

不要一开始重写后端所有响应格式，否则会影响 CLI、测试和已有后端调用方。更稳妥的做法是：

1. 前端 API 模块改成调用后端已有路径。
2. 前端在 API 层把后端字段转换成页面需要的字段。
3. 后端只补确实不存在的接口，例如订单、交易流水、策略配置、调度器、指标 IDE、Pipeline 管理等。
4. WebSocket 后续合并或分端口运行，第一阶段先完成 REST 对接。

## 启动配置

### 后端

文件：`quantsys-v2/api/server.py`

当前入口：

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
pip install -r requirements.txt
python api/server.py
```

默认服务地址：

```text
http://localhost:5000
```

基础验证：

```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/stocks/list
```

### 前端

文件：`web-frontend/.env.development`

建议先直接连后端，因为后端已启用 CORS：

```env
VITE_API_BASE_URL=http://localhost:5000
VITE_WS_URL=http://localhost:5000
VITE_USE_MOCK=false
```

启动：

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm install
npm run dev
```

注意：如果改成走 Vite proxy，不要使用当前 `vite.config.ts` 里的 `rewrite: path.replace(/^\/api/, '')`，因为后端路由本身包含 `/api`。否则 `/api/health` 会被代理成 `/health`，后端会 404。

## 前端需要修改的文件

### 1. `web-frontend/src/services/api/client.ts`

职责：统一 axios 请求、错误处理、响应拆包。

需要调整：

- 保持 `VITE_API_BASE_URL=http://localhost:5000`。
- 错误拦截器识别后端 `{error: "..."}`。
- 不要假设所有成功响应都有 `code`。

建议规则：

```ts
// 后端返回 { code, message, data } 时，继续拆 data。
// 后端返回 { error } 时，抛错。
// 后端返回普通对象时，直接返回普通对象。
```

### 2. `web-frontend/src/services/api/stock.ts`

当前前端路径和后端路径不匹配，需要改：

| 前端方法 | 当前路径 | 后端真实路径 | 修改建议 |
| --- | --- | --- | --- |
| `getStocks` | `GET /api/stocks` | `GET /api/stocks/list` | 改路径，并把 `{stocks,count}` 转成前端分页结构 |
| `searchStocks` | `GET /api/stocks/search?keyword=` | `GET /api/stocks/search?q=` | 参数名 `keyword` 改为 `q` |
| `getKLineData` | `GET /api/market/kline` | `GET /api/stock/<symbol>/klines` | 用 `params.symbol` 拼路径；参数改成 `start_date/end_date/limit` |
| `getTechnicalIndicators` | `GET /api/stocks/<symbol>/indicators` | `GET /api/stock/<symbol>/technical` | 改路径 |
| `getStockDetail` | `GET /api/stocks/<symbol>` | 后端无同名接口 | 用 `/api/stocks/resolve` 或新增后端接口 |
| 自选股相关 | `/api/stocks/watchlist...` | 后端无接口 | 后端新增或前端保留 mock |

推荐新增前端适配函数：

```ts
function adaptStock(raw: any): StockInfo {
  return {
    symbol: raw.symbol,
    name: raw.name,
    industry: raw.industry || '',
    sector: raw.market || '',
    marketCap: raw.market_cap || 0,
    pe: raw.pe || 0,
    pb: raw.pb || 0,
    roe: raw.roe || 0,
    currentPrice: raw.current_price || raw.close || 0,
    change: raw.change || 0,
    changePercent: raw.change_percent || 0
  }
}
```

### 3. `web-frontend/src/services/api/analysis.ts`

需要改成后端现有接口：

| 前端方法 | 当前路径 | 后端真实路径 | 修改建议 |
| --- | --- | --- | --- |
| `runBacktest` | `POST /api/backtest` | `POST /api/backtest` | 路径对，payload 字段要改 |
| `getBacktestResult` | `GET /api/backtest/:id` | 后端无单个回测接口 | 用 `/api/backtest/results` 或后端新增 |
| `getBacktestHistory` | `GET /api/backtest/history` | `GET /api/backtest/results` | 改路径 |
| `getFactorAnalysis` | `POST /api/analysis/factors` | `POST /api/stocks/compare` | 改路径和响应字段 |
| `getStockFactorAnalysis` | `GET /api/analysis/factors/:symbol` | `GET /api/stock/<symbol>/factors` | 改路径 |
| `scanOpportunities` | `POST /api/analysis/opportunities/scan` | `POST /api/signals/scan` | 临时接信号扫描，或后端新增机会接口 |
| `getTechnicalAnalysis` | `GET /api/analysis/technical/:symbol` | `GET /api/stock/<symbol>/technical` | 改路径 |

`runBacktest` payload 需要映射：

```ts
{
  strategy_name: form.strategy,
  symbol: form.symbol,
  start_date: formatDate(form.startDate),
  end_date: formatDate(form.endDate),
  initial_capital: form.initialCapital
}
```

### 4. `web-frontend/src/services/api/signal.ts`

后端已有：

```text
GET  /api/signals
GET  /api/signals/history
POST /api/signals/scan
```

前端目前还有这些后端没有的接口：

```text
GET  /api/signals/:id
POST /api/signals/:id/approve
POST /api/signals/:id/reject
POST /api/signals/:id/mark-error
GET  /api/signals/statistics
POST /api/signals/:id/verify
```

处理方式：

- 第一阶段：列表页只接 `GET /api/signals`。
- 审批、拒绝、验证按钮先禁用或保留前端 mock。
- 第二阶段：在后端新增审批相关路由，落到 `repositories/signal_repository.py`。

### 5. `web-frontend/src/services/api/risk.ts`

后端当前只有核心检查：

```text
POST /api/risk/check
```

前端还调用：

```text
GET /api/risk/metrics
GET /api/risk/limits
PUT /api/risk/limits
GET /api/risk/report
GET /api/risk/var
GET /api/risk/stress-test
POST /api/risk/stress-test
```

建议：

- 风控页先接 `checkRisk`。
- `getRiskMetrics/getRiskReport/getVaR` 后端可以基于 `ds.risk` 新增。
- 限额、压力测试、止损规则属于新功能，后端需要新增表或复用现有风险配置存储。

### 6. `web-frontend/src/services/api/data.ts`

后端已有：

```text
POST /api/data/update
GET  /api/data/update/jobs/<job_id>
```

前端需要改：

| 前端方法 | 当前路径 | 后端真实路径 | 修改建议 |
| --- | --- | --- | --- |
| `startUpdate` | `POST /api/data/update/start` | `POST /api/data/update` | 改路径 |
| `getJobs` | `GET /api/data/jobs` | 只有 `GET /api/data/update/jobs/<job_id>` | 后端新增列表接口，或前端只查单任务 |
| `getDataSources` | `GET /api/data/sources` | 无 | 后端新增静态数据源接口 |
| `getStats` | `GET /api/data/stats` | 无 | 后端新增统计接口 |

`startUpdate` payload 映射：

```ts
{
  source: request.scope,
  days: request.days,
  force: request.forceUpdate ?? false,
  async: true
}
```

后端返回 `job_id`，前端需要适配成 `jobId`。

### 7. `web-frontend/src/services/api/trading.ts`

后端 `api/server.py` 目前没有 REST 订单、交易、持仓接口，但已有服务：

- `quantsys-v2/services/order_service.py`
- `quantsys-v2/services/trade_service.py`
- `ds.portfolio` 相关 repository 方法

前端需要的接口：

```text
GET  /api/orders
GET  /api/orders/:id
POST /api/orders
POST /api/orders/:id/cancel
PUT  /api/orders/:id
GET  /api/portfolio/positions
GET  /api/portfolio/summary
GET  /api/trades
GET  /api/portfolio/equity-curve
GET  /api/portfolio/allocation
```

建议后端新增这些路由到 `quantsys-v2/api/server.py`，调用现有 `order_service` / `trade_service`。

### 8. `web-frontend/src/services/api/strategy.ts`

前端策略中心/策略配置需要：

```text
GET    /api/strategies
GET    /api/strategies/:id
POST   /api/strategies
PUT    /api/strategies/:id
DELETE /api/strategies/:id
POST   /api/strategies/:id/start
POST   /api/strategies/:id/stop
GET    /api/strategies/:id/performance
```

后端可用能力：

- `quantsys-v2/services/strategy_code_service.py`
- `quantsys-v2/repositories/strategy_repository.py`
- 已有 `GET /api/performance/strategy/<strategy_id>`

建议后端新增 `/api/strategies...` 路由，优先支持列表、详情、创建、更新、启停。

### 9. `web-frontend/src/services/api/indicator.ts`

前端指标 IDE 当前需要完整 CRUD：

```text
GET    /api/indicators
POST   /api/indicators
PUT    /api/indicators/:id
DELETE /api/indicators/:id
POST   /api/indicators/:id/run
POST   /api/indicators/backtest
```

后端没有同名路由，但 `StrategyCodeService` 已支持 `code_type='indicator'`。

建议：

- 后端把 indicator 当作 `strategy_code_service` 的一种 code type。
- 新增 `/api/indicators` 路由，内部调用 `StrategyCodeService.create_strategy(..., code_type='indicator')`。
- `run/backtest` 调用 `run_strategy` / `backtest_strategy`。

### 10. `web-frontend/src/services/api/pipeline.ts`

前端量化流水线页面需要：

```text
GET  /api/pipeline/statistics
GET  /api/pipeline/tasks
GET  /api/pipeline/runs
POST /api/pipeline/trigger
```

后端已有 `core/pipeline.py` 和数据更新、因子、ML、回测能力，但没有管理型 REST 路由。

建议：

- 后端新增轻量路由，先用已有服务组合执行。
- `POST /api/pipeline/trigger` 可接受 `{symbols, stages}`，按 `data_update -> factors -> signals -> risk` 顺序执行。
- 运行历史可先落内存或复用 `.pi-invest/pipeline-runs`。

### 11. 调度器页面

前端页面存在 `Scheduler`，后端已有：

- `quantsys-v2/services/scheduler.py`

但缺 REST 路由。建议新增：

```text
GET    /api/scheduler/tasks
POST   /api/scheduler/tasks
GET    /api/scheduler/tasks/:id
PUT    /api/scheduler/tasks/:id
DELETE /api/scheduler/tasks/:id
POST   /api/scheduler/tasks/:id/run
GET    /api/scheduler/runs
```

## 后端需要修改的文件

### 1. `quantsys-v2/api/server.py`

短期最小改法：继续在这个文件里添加缺失路由。

建议新增分区：

```python
# ==================== 订单 / 持仓 / 交易流水 ====================
# ==================== 策略 / 指标 ====================
# ==================== Pipeline 管理 ====================
# ==================== Scheduler 管理 ====================
```

长期更好做法：拆成 `api/routes/*.py`，但这会扩大改动范围，不建议第一阶段做。

### 2. `quantsys-v2/api/response_builder.py`

可选改动。不要强制一次性改完所有旧接口。

如果要统一新接口响应，建议新接口使用：

```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

前端 `client.ts` 和 API 适配层要同时支持旧格式和新格式。

### 3. `quantsys-v2/api/server_websocket.py`

当前和 REST 都占用 5000。

第一阶段建议：

- 先不接 WebSocket，前端实时数据走 REST/轮询。

第二阶段二选一：

1. 分端口运行：
   - REST: `5000`
   - WebSocket: `5001`
   - 修改 `server_websocket.py` 端口，前端 `VITE_WS_URL=http://localhost:5001`

2. 合并同一个 Flask app：
   - 把 REST app 和 SocketIO app 合并。
   - 保证 `SocketIO(app, cors_allowed_origins="*")` 和所有 REST route 使用同一个 `app`。

## 后端建议补的接口清单

第一批必须补：

```text
GET  /api/orders
GET  /api/orders/<order_id>
POST /api/orders
POST /api/orders/<order_id>/cancel
GET  /api/trades
GET  /api/portfolio/positions
GET  /api/portfolio/summary
```

第二批建议补：

```text
GET    /api/strategies
GET    /api/strategies/<strategy_id>
POST   /api/strategies
PUT    /api/strategies/<strategy_id>
POST   /api/strategies/<strategy_id>/start
POST   /api/strategies/<strategy_id>/stop
GET    /api/indicators
POST   /api/indicators
POST   /api/indicators/<indicator_id>/run
POST   /api/indicators/backtest
```

第三批增强：

```text
GET  /api/data/sources
GET  /api/data/stats
GET  /api/data/update/jobs
GET  /api/risk/metrics
GET  /api/risk/report
GET  /api/pipeline/statistics
GET  /api/pipeline/tasks
POST /api/pipeline/trigger
GET  /api/scheduler/tasks
POST /api/scheduler/tasks
```

## 推荐实施顺序

### 阶段 1：基础连通

1. 修改 `web-frontend/.env.development`，把端口改成 `5000`。
2. 启动 `python quantsys-v2/api/server.py`。
3. 验证 `curl http://localhost:5000/api/health`。
4. 前端启动 `npm run dev`。
5. 修 `stock.ts`，让股票列表、搜索、K线先可用。
6. 修 `analysis.ts`，让回测、因子、技术指标可用。
7. 跑 `npm run build`。

### 阶段 2：核心交易闭环

1. 后端补 `/api/orders`、`/api/trades`、`/api/portfolio/*`。
2. 前端修 `trading.ts` 字段适配。
3. 验证持仓、订单、交易流水页面。
4. 后端补信号审批接口，或前端隐藏审批动作。

### 阶段 3：高级功能

1. 后端补 `/api/strategies`。
2. 后端补 `/api/indicators`。
3. 前端修 `strategy.ts`、`indicator.ts`。
4. 接策略中心、策略配置、指标 IDE。

### 阶段 4：辅助与实时

1. 后端补数据源、数据更新任务列表、Pipeline、Scheduler 路由。
2. 前端修 `data.ts`、`pipeline.ts`，必要时新增 `scheduler.ts`。
3. WebSocket 分端口或合并服务。
4. 前端修 `useWebSocket.ts` 监听后端实际事件。

## 验收清单

后端：

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python -m py_compile api/server.py api/server_websocket.py
python api/server.py
curl http://localhost:5000/api/health
curl http://localhost:5000/api/stocks/list
```

前端：

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run build
npm run dev
```

浏览器验收：

- 股票列表能加载真实股票。
- 股票详情能加载 K 线、因子、技术指标。
- 交易信号能加载后端信号。
- 回测能提交并显示结果。
- 风控检查能提交并显示检查结果。
- 数据更新能创建 job，并能查看 job 状态。
- 无 404 API 请求。
- 控制台无运行时错误。

## 风险点

- 前端部分页面字段名偏 UI 模型，后端字段名偏数据库模型，需要 API 层做转换。
- 后端部分页面需要的管理接口尚不存在，不应只改前端。
- WebSocket 当前和 REST 服务端口冲突，必须先决定分端口还是合并。
- 如果使用 Vite proxy，必须保留 `/api` 前缀，不能 rewrite 掉。
- 订单、策略、指标、调度器属于写操作，接入前应先确认数据库表和迁移已执行。

