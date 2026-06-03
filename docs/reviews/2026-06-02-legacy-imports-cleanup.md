# quantsys-v2 旧模块依赖清理报告

**日期**: 2026-06-02
**问题**: quantsys-v2 后端中存在 54 处对旧 v1 `quantsys` 模块的依赖，导致 503 错误

## 已修复 ✅

### 1. api/routes/market.py - 概念板块功能
**问题**: `market.concepts` 和 `market.concept_stocks` 依赖旧 v1 `quantsys.cli.market_query`

**修复**:
- 在 `MarketDataService` 中新增 `get_concepts(keyword)` 和 `get_concept_stocks(concept)` 方法
- 更新路由使用 `market_data_service` 替代旧模块导入
- 移除 `sys.path.insert` 和 `from quantsys.cli.market_query import ...`

**修改文件**:
- `quantsys-v2/services/market_data_service.py` - 新增 2 个方法
- `quantsys-v2/api/routes/market.py` - 更新 2 个路由函数

**影响**: ✅ `market_cli({ command: "market.concepts" })` 现在可以正常工作（网络问题除外）

## 待修复问题 (按优先级排序)

### 高优先级 🔴 (影响常用功能)

#### 1. api/routes/market.py (5处剩余)
- `get_macro_data()` - 宏观数据
- `get_market_news()` - 市场新闻
- `get_index_history()` - 指数历史
- `get_hk_market_overview()` - 港股概览
- `get_hk_south_flow()` - 南向资金

**建议**: 扩展 `MarketDataService`，添加这些方法的 v2 实现

#### 2. api/routes/stock.py (5处)
- `get_stock_announcements()` - 股票公告
- `get_stock_news()` - 个股新闻
- `get_batch_stock_quotes()` - 批量行情
- `get_insider_trades()` - 内幕交易
- `compare_peers()` - 同业对比

**建议**: 创建 `StockDataService`，迁移这些功能

#### 3. api/routes/analysis.py (20+处)
- 技术分析: `analyze_price_action`, `calculate_buy_range`, `get_exit_plan`, `analyze_candlestick`
- 财务分析: `get_financial_indicators`, `get_stock_valuation`, `get_cash_flow`, `get_income_statement`
- 风险分析: `stress_test`, `price_alert`
- 组合分析: `verify_trades`, `compare_benchmark`, `optimize_portfolio`, `correlate_portfolio`
- 因子分析: `analyze_factor_decay`, `aggregate_sectors`
- 策略分析: `analyze_performance`, `arbitrate_signals`

**建议**: 这是最大的依赖集群，需要分阶段迁移：
1. 技术分析 → `TechnicalAnalysisService`
2. 财务分析 → `FinancialAnalysisService`
3. 风险分析 → `RiskAnalysisService`
4. 组合分析 → `PortfolioAnalysisService`

### 中优先级 🟡 (影响特定功能)

#### 4. api/routes/risk.py (5处)
- `check_trade_risk()` - 交易风控
- `calculate_position_size()` - 仓位计算
- `calculate_stop_loss()` - 止损计算
- `StopLossRuleDAO` - 数据库访问

**建议**: 创建 `RiskService`，整合风控逻辑

#### 5. api/routes/health.py (3处)
- `Database` - 数据库连接
- `KlineFetcher` - K线获取

**建议**: 用 v2 的 `repositories` 替代

#### 6. api/routes/pipeline.py (2处)
- `Database` - 数据库连接
- `run_calibration()` - 置信度校准

**建议**: 保留 ML 管道，但更新数据访问层

### 低优先级 🟢 (非关键功能)

#### 7. api/routes/charts.py (1处)
- `from quantsys.ml import visualizer` - 可视化

**建议**: 如果功能未使用，可以注释掉路由；否则重新实现

#### 8. api/routes/jobs.py (1处)
- `get_stock_fund_flow()` - 资金流向

**建议**: 迁移到 `MarketSentimentService`

#### 9. services/strategy_code_service.py (1处)
- `get_stock_fund_flow()` - 策略代码中使用

**建议**: 更新策略模板使用 v2 API

## 修复策略建议

### Phase 1: 核心数据服务 (1-2天)
1. 扩展 `MarketDataService` (市场数据)
2. 创建 `StockDataService` (个股数据)
3. 更新对应路由

### Phase 2: 分析服务 (3-5天)
1. 创建 `TechnicalAnalysisService`
2. 创建 `FinancialAnalysisService`
3. 创建 `RiskService`
4. 更新 `analysis.py` 和 `risk.py` 路由

### Phase 3: 清理收尾 (1天)
1. 处理剩余低优先级依赖
2. 移除所有 `sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))` 代码
3. 添加单元测试验证迁移完整性

## 预期收益

✅ **稳定性**: 消除 ImportError 和 503 错误
✅ **维护性**: v2 代码自包含，不依赖旧系统
✅ **性能**: 避免动态模块加载开销
✅ **测试**: 更容易编写单元测试

## 当前状态

- **总计**: 54 处旧依赖
- **已修复**: 2 处 (market.concepts, market.concept_stocks)
- **待修复**: 52 处
- **完成度**: 3.7%

## 相关文件

**受影响文件** (9个):
1. `api/routes/analysis.py` - 20+ 处依赖
2. `api/routes/market.py` - 7 处依赖 (2 处已修复)
3. `api/routes/stock.py` - 5 处依赖
4. `api/routes/risk.py` - 5 处依赖
5. `api/routes/health.py` - 3 处依赖
6. `api/routes/pipeline.py` - 2 处依赖
7. `api/routes/charts.py` - 1 处依赖
8. `api/routes/jobs.py` - 1 处依赖
9. `services/strategy_code_service.py` - 1 处依赖

**修改文件**:
- `quantsys-v2/services/market_data_service.py` - 新增概念板块方法
- `quantsys-v2/api/routes/market.py` - 更新概念板块路由

## 测试验证

```bash
# 启动后端服务
cd quantsys-v2 && python start_all.py

# 测试概念板块 API
curl "http://127.0.0.1:5001/api/market/concepts"
curl "http://127.0.0.1:5001/api/market/concept/国产替代/stocks"
```

**预期结果**: 返回概念板块数据（JSON 格式），不再报 503 错误

## 后续行动

1. **立即**: 继续清理高优先级依赖 (market.py, stock.py)
2. **本周**: 完成 Phase 1 核心数据服务迁移
3. **下周**: 启动 Phase 2 分析服务重构
4. **本月**: 完成全部 54 处依赖清理
