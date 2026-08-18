# 后端 API 问题诊断报告

## 概述

对 agent-dh 审计中发现的 5 个后端 API 问题进行根因分析。

---

## 问题 1: getSectorAnalysis → 503

**端点**: `GET /api/market/sectors`
**路由文件**: `market_data_async.py:32-39`

### 根因
`market_data_service.get_sectors()` 内部调用 `ak.stock_board_industry_name_em()` 获取东方财富行业板块数据。该调用失败（网络/数据源问题），返回 `success=false`，路由层将其转为 503。

### 代码路径
```python
# market_data_async.py:32-39
@router.get('/api/market/sectors')
def get_sectors_v2():
    result = market_data_service.get_sectors()
    if not result.get('success', False):
        return error_response(result, 503)  # <-- 这里返回 503
```

### 判断
**非代码 bug**。这是数据源（akshare → 东方财富）的临时网络问题。`get_sectors()` 已有 try-catch 和降级处理，返回了有意义的错误信息。

### 建议
- 考虑增加本地缓存，避免每次实时拉取
- 或增加备用数据源

---

## 问题 2: verifyTrades → 503

**端点**: `POST /api/risk/trade-verify`
**路由文件**: `analysis_async.py:731-743`

### 根因
该端点尝试从已删除的 `quantsys-v2/quant/` 目录导入旧 CLI 模块：

```python
sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
from quantsys.cli.trade_portfolio_analytics import verify_trades  # ImportError!
```

`quantsys-v2/quant/` 目录已不存在（2026-07-21 起 quantsys-v2 不再是独立 git 仓库，旧代码归档）。

### 影响范围
所有使用 `sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))` 模式的端点都会 503：

| 端点 | 行号 | 状态 |
|------|------|------|
| `/api/risk/price-alert` | 719-726 | ❌ 503 |
| `/api/risk/trade-verify` | 731-743 | ❌ 503 |
| `/api/portfolio/benchmark` | 797-804 | ❌ 503 |
| `/api/portfolio/optimize` | 814-821 | ❌ 503 |
| `/api/portfolio/correlation` | 831-838 | ❌ 503 |
| `/api/portfolio/factor-decay` | 892-899 | ❌ 503 |
| `/api/portfolio/performance-analyze` | 1021-1028 | ❌ 503 |
| `/api/portfolio/signal-arbitrate` | 1038-1045 | ❌ 503 |

### 判断
**架构性遗留问题**。这些端点是 Flask → FastAPI 迁移期间的占位实现，依赖的旧 `quant/` CLI 模块已被删除。

### 修复方案
这些端点需要重新实现为 v2 原生服务调用，或标记为已弃用。短期可返回 410 Gone 明确告知客户端。

---

## 问题 3: getRiskMetrics → 400

**端点**: `POST /api/risk/metrics`
**路由文件**: `analysis_async.py:748-787`

### 根因
**参数契约不匹配**。

后端期望的参数：
```json
{
  "returns": [0.01, -0.02, 0.015, ...],
  "benchmark_returns": [0.005, 0.01, ...],
  "risk_free_rate": 0.02
}
```

但 agent-dh 的 `risk_metrics` 工具传的是：
```json
{
  "account_name": "default"
}
```

### 代码
```python
# analysis_async.py:757-763
returns = data.get('returns')
if not returns:
    return error_response({
        'success': False,
        'error': 'returns 参数不能为空'
    }, 400)
```

### 判断
**client 调用参数错误**，但后端可以做得更好——支持按账户名自动获取收益率数据。

### 修复方案
两个选择：
1. **修改 client**：让 `getRiskMetrics` 先获取账户历史收益数据，再传 `returns` 数组
2. **增强后端**：支持 `account_name` 参数，后端自动查询账户历史收益并计算指标

推荐方案 2（后端增强），这样更贴合工具的使用方式。

---

## 问题 4: calculateFactors → 500

**端点**: `GET /api/stock/{symbol}/factors`
**路由文件**: `analysis_async.py:206-224`

### 根因
需要查看具体错误日志。该端点调用 `ds.factor.get_latest_factors(symbol)` 和 `ds.stock.get_by_symbol(symbol)`，可能的问题：
- 股票代码格式问题
- 数据库中无该股票的因子数据
- `get_by_symbol` 返回 ORM 对象而非字典，第 217 行 `stock_info['name']` 可能失败

### 代码
```python
# analysis_async.py:211-218
stock_info = ds.stock.get_by_symbol(symbol)
kline = ds.kline.get_latest_daily_kline(symbol)
latest_signals = ds.signal.get_signals_by_symbol(symbol, '2024-01-01', date or '2026-12-31')
return sanitize_for_json({
    'symbol': symbol,
    'stock_name': stock_info['name'] if stock_info else '',  # 如果 stock_info 是 ORM 对象，这里会失败
    ...
})
```

### 判断
**疑似 ORM 对象访问问题**。`get_by_symbol` 可能返回 ORM 对象而非字典，`stock_info['name']` 会抛 TypeError。

### 修复方案
修复第 217-218 行，兼容 ORM 对象和字典：
```python
stock_name = stock_info.name if hasattr(stock_info, 'name') else (stock_info or {}).get('name', '')
market = stock_info.market if hasattr(stock_info, 'market') else (stock_info or {}).get('market', '')
```

---

## 问题 5: manageWatchRule → 已修复 ✅

**修复**: client 层将 `POST /api/watch/rules/{id}/enable` 改为 `PATCH /api/watch/rules/{id}`

---

## 修复优先级

| 优先级 | 问题 | 工作量 | 影响 |
|--------|------|--------|------|
| P0 | verifyTrades 等 8 个端点 503 | 中 | 高 |
| P0 | calculateFactors 500 | 小 | 中 |
| P1 | getRiskMetrics 400 | 小 | 中 |
| P1 | getSectorAnalysis 503 | 小 | 低（数据源问题） |
