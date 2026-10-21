# quantsys-v2 API 使用手册

**版本**: 2.0.0  
**更新日期**: 2026-09-06  
**基础 URL**: http://127.0.0.1:5001

---

## 快速开始

### 认证

当前版本无需认证（内网部署）。生产环境建议添加 JWT 认证。

### 基础请求

```bash
# 检查服务状态
curl http://127.0.0.1:5001/health

# 查看 API 文档
open http://127.0.0.1:5001/docs
```

---

## 核心 API

### 1. 股票池管理

#### 1.1 获取所有股票池

```bash
GET /api/pools
```

**响应示例**:
```json
{
  "pools": [
    {
      "id": 1,
      "name": "高质量成长股",
      "type": "dynamic",
      "member_count": 25,
      "created_at": "2026-06-01T10:00:00Z"
    }
  ]
}
```

#### 1.2 刷新股票池

```bash
POST /api/pools/{pool_id}/refresh
```

**业务场景**: 每日 02:00 自动刷新，或手动触发

**请求示例**:
```bash
curl -X POST http://127.0.0.1:5001/api/pools/1/refresh
```

**响应**:
```json
{
  "pool_id": 1,
  "changes": {
    "added": ["600519.SH", "000858.SZ"],
    "removed": ["600036.SH"],
    "unchanged": 23
  },
  "total_members": 24,
  "refresh_time": "2026-09-06T02:00:15Z"
}
```

#### 1.3 创建股票池

```bash
POST /api/pools
```

**请求体**:
```json
{
  "name": "高股息红利",
  "type": "dynamic",
  "criteria": {
    "dividend_yield_min": 0.04,
    "roe_min": 0.10,
    "market": "A"
  },
  "description": "股息率 > 4%，ROE > 10%"
}
```

---

### 2. K 线数据

#### 2.1 获取日线数据

```bash
GET /api/klines/{symbol}/daily?start_date={date}&end_date={date}
```

**参数**:
- `symbol`: 股票代码（如 600519.SH）
- `start_date`: 开始日期（YYYY-MM-DD）
- `end_date`: 结束日期（YYYY-MM-DD）

**示例**:
```bash
curl "http://127.0.0.1:5001/api/klines/600519.SH/daily?start_date=2026-01-01&end_date=2026-09-06"
```

**响应**:
```json
{
  "symbol": "600519.SH",
  "period": "daily",
  "data": [
    {
      "date": "2026-01-02",
      "open": 1650.50,
      "high": 1680.00,
      "low": 1645.00,
      "close": 1675.30,
      "volume": 1250000,
      "amount": 2087625000.00
    }
  ],
  "count": 180
}
```

---

### 3. 策略回测

#### 3.1 执行回测

```bash
POST /api/strategies/{strategy_id}/backtest
```

**请求体**:
```json
{
  "symbol": "600519.SH",
  "start_date": "2025-01-01",
  "end_date": "2026-08-31",
  "initial_capital": 100000,
  "params": {
    "fast_period": 5,
    "slow_period": 20
  }
}
```

**响应**:
```json
{
  "strategy_id": 179,
  "symbol": "600519.SH",
  "summary": {
    "total_return": 0.4523,
    "annualized_return": 0.3845,
    "max_drawdown": -0.0856,
    "sharpe_ratio": 2.34,
    "win_rate": 0.62,
    "total_trades": 24
  },
  "equity_curve": [...],
  "trades": [...]
}
```

---

### 4. 信号生成

#### 4.1 扫描买入信号

```bash
POST /api/signals/scan
```

**请求体**:
```json
{
  "scan_type": "buy",
  "strategy_ids": [179, 178, 163, 193],
  "pool_id": 1,
  "date": "2026-09-06"
}
```

**响应**:
```json
{
  "scan_date": "2026-09-06",
  "signals": [
    {
      "symbol": "600519.SH",
      "strategy_id": 179,
      "signal_type": "buy",
      "price": 1680.50,
      "score": 0.85,
      "reason": "均线金叉 + RSI 超卖"
    }
  ],
  "total_signals": 12
}
```

---

### 5. 持仓管理

#### 5.1 获取当前持仓

```bash
GET /api/positions?account_name={account}
```

**示例**:
```bash
curl "http://127.0.0.1:5001/api/positions?account_name=agent_virtual"
```

**响应**:
```json
{
  "account_name": "agent_virtual",
  "positions": [
    {
      "symbol": "600519.SH",
      "shares": 100,
      "available_shares": 100,
      "cost_price": 1650.00,
      "current_price": 1680.50,
      "market_value": 168050.00,
      "profit_loss": 3050.00,
      "profit_loss_pct": 0.0185
    }
  ],
  "total_market_value": 450000.00,
  "total_profit_loss": 12500.00
}
```

---

### 6. 交易执行

#### 6.1 下单

```bash
POST /api/trades/order
```

**请求体**:
```json
{
  "account_name": "agent_virtual",
  "symbol": "600519.SH",
  "action": "buy",
  "shares": 100,
  "price": 1680.50,
  "order_type": "limit",
  "notes": "策略 179 买入信号"
}
```

**响应**:
```json
{
  "order_id": "ORD20260906001",
  "status": "filled",
  "filled_shares": 100,
  "filled_price": 1680.50,
  "commission": 50.42,
  "filled_at": "2026-09-06T09:35:12Z"
}
```

---

### 7. 因子计算

#### 7.1 计算单只股票因子

```bash
POST /api/factors/calculate
```

**请求体**:
```json
{
  "symbol": "600519.SH",
  "date": "2026-09-06",
  "factors": ["momentum_5d", "volatility_20d", "rsi_14"]
}
```

**响应**:
```json
{
  "symbol": "600519.SH",
  "date": "2026-09-06",
  "factors": {
    "momentum_5d": 0.0234,
    "volatility_20d": 0.0156,
    "rsi_14": 58.32
  }
}
```

---

### 8. 筹码分布

#### 8.1 获取筹码分布

```bash
GET /api/analysis/chip-distribution/{symbol}
```

**示例**:
```bash
curl "http://127.0.0.1:5001/api/analysis/chip-distribution/600519.SH"
```

**响应**:
```json
{
  "symbol": "600519.SH",
  "date": "2026-09-06",
  "metrics": {
    "profit_ratio": 0.68,
    "avg_cost": 1520.50,
    "cost_range_90": [1450.00, 1650.00],
    "cost_range_70": [1500.00, 1600.00],
    "peak_price": 1550.00,
    "concentration": 0.45
  },
  "distribution": {
    "1400-1450": 0.08,
    "1450-1500": 0.15,
    "1500-1550": 0.32,
    "1550-1600": 0.28,
    "1600-1650": 0.12,
    "1650-1700": 0.05
  }
}
```

---

### 9. 调度任务

#### 9.1 手动触发任务

```bash
POST /api/scheduler/trigger
```

**请求体**:
```json
{
  "job_type": "kline_update",
  "params": {
    "symbols": ["600519.SH", "000858.SZ"]
  }
}
```

---

### 10. 市场感知（M1 模块）

#### 10.1 获取市场状态

```bash
GET /api/market/perception
```

**响应**:
```json
{
  "date": "2026-09-06",
  "regime": "bull_market",
  "sentiment": {
    "retail": 0.65,
    "institutional": 0.58,
    "overall": 0.62
  },
  "themes": [
    {
      "name": "AI芯片",
      "heat": 0.85,
      "stocks": ["600584.SH", "002371.SZ"]
    }
  ],
  "risk_level": "medium"
}
```

---

## WebSocket API

### 实时行情订阅

**连接**: `ws://127.0.0.1:5003`

**订阅消息**:
```json
{
  "action": "subscribe",
  "channel": "quotes",
  "symbols": ["600519.SH", "000858.SZ"]
}
```

**推送消息**:
```json
{
  "channel": "quotes",
  "symbol": "600519.SH",
  "price": 1680.50,
  "change": 0.0125,
  "volume": 1250000,
  "timestamp": "2026-09-06T10:30:05Z"
}
```

---

## 错误处理

### 标准错误响应

```json
{
  "error": {
    "code": "INVALID_SYMBOL",
    "message": "股票代码格式错误",
    "details": "symbol must match pattern: \\d{6}\\.(SH|SZ)"
  }
}
```

### 常见错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|------------|------|
| `INVALID_SYMBOL` | 400 | 股票代码格式错误 |
| `SYMBOL_NOT_FOUND` | 404 | 股票不存在 |
| `POOL_NOT_FOUND` | 404 | 股票池不存在 |
| `STRATEGY_NOT_FOUND` | 404 | 策略不存在 |
| `INSUFFICIENT_FUNDS` | 422 | 资金不足 |
| `INSUFFICIENT_SHARES` | 422 | 持仓不足 |
| `MARKET_CLOSED` | 422 | 非交易时段 |
| `INTERNAL_ERROR` | 500 | 内部错误 |

---

## 最佳实践

### 1. 批量请求优化

**不推荐**（串行请求）:
```python
for symbol in symbols:
    response = requests.get(f"/api/klines/{symbol}/daily")
```

**推荐**（批量请求）:
```python
response = requests.post("/api/klines/batch", json={"symbols": symbols})
```

### 2. 错误重试

```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
```

### 3. 超时设置

```python
response = requests.get(url, timeout=(3.0, 30.0))  # (connect, read)
```

---

## Python SDK 示例

```python
from quantsys_v2_client import QuantSysClient

# 初始化客户端
client = QuantSysClient(base_url="http://127.0.0.1:5001")

# 获取股票池
pools = client.pools.list()

# 刷新股票池
result = client.pools.refresh(pool_id=1)

# 获取 K 线数据
klines = client.klines.get_daily(
    symbol="600519.SH",
    start_date="2026-01-01",
    end_date="2026-09-06"
)

# 执行回测
backtest = client.strategies.backtest(
    strategy_id=179,
    symbol="600519.SH",
    start_date="2025-01-01",
    end_date="2026-08-31"
)

# 获取持仓
positions = client.positions.list(account_name="agent_virtual")

# 下单
order = client.trades.create_order(
    account_name="agent_virtual",
    symbol="600519.SH",
    action="buy",
    shares=100,
    price=1680.50
)
```

---

## 限流与配额

当前无限流限制（内网部署）。生产环境建议：

- 每个 IP：1000 req/min
- WebSocket 连接：每个 IP 最多 10 个
- 批量请求：最多 100 个 symbols

---

## 更新日志

### v2.0.0 (2026-08-02)
- ✅ Flask → FastAPI 完全迁移
- ✅ Agent OS Scheduler 集成
- ✅ 筹码分布模块上线
- ✅ 市场感知（M1）模块上线

### v1.x (Legacy)
- Flask API（已废弃）

---

## 技术支持

- **API 文档**: http://127.0.0.1:5001/docs
- **ReDoc**: http://127.0.0.1:5001/redoc
- **问题反馈**: 提交 GitHub Issue

---

**文档版本**: 1.0  
**最后更新**: 2026-09-06
