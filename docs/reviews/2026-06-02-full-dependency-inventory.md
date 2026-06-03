# quantsys v1 模块依赖全面清单

**日期**: 2026-06-02
**扫描范围**: 整个项目（包括 scripts 和 quantsys-v2）
**总依赖数**: 55 处（分布在 14 个文件中）

## 分类统计

### API 路由层 (45处) - 运行时关键

| 文件 | 依赖数 | 优先级 | 状态 |
|------|--------|--------|------|
| `api/routes/analysis.py` | 19 | 🔴 高 | ⏳ 待处理 |
| `api/routes/risk.py` | 13 | 🔴 高 | ⏳ 待处理 |
| `api/routes/stock.py` | 5 | 🔴 高 | ⏳ 待处理 |
| `api/routes/health.py` | 3 | 🟡 中 | ⏳ 待处理 |
| `api/routes/pipeline.py` | 2 | 🟡 中 | ⏳ 待处理 |
| `api/routes/charts.py` | 1 | 🟢 低 | ⏳ 待处理 |
| `api/routes/jobs.py` | 1 | 🟢 低 | ⏳ 待处理 |
| `api/routes/signal_test.py` | 1 | 🟢 低 | ⏳ 待处理 |

### 服务层 (1处) - 运行时关键

| 文件 | 依赖数 | 优先级 | 状态 |
|------|--------|--------|------|
| `services/strategy_code_service.py` | 1 | 🟡 中 | ⏳ 待处理 |

### 脚本工具 (9处) - 非运行时

| 文件 | 依赖数 | 优先级 | 状态 |
|------|--------|--------|------|
| `scripts/migrate_stop_loss_to_db.py` | 2 | 🟢 低 | ⏳ 待处理 |
| `quantsys-v2/scripts/diagnostics/diagnose_system_indicators.py` | 1 | 🟢 低 | ⏳ 待处理 |
| `quantsys-v2/scripts/maintenance/backfill_null_volume_all.py` | 2 | 🟢 低 | ⏳ 待处理 |
| `quantsys-v2/scripts/maintenance/backfill_null_volume_active.py` | 2 | 🟢 低 | ⏳ 待处理 |
| `quantsys-v2/scripts/maintenance/backfill_zero_volume_active.py` | 2 | 🟢 低 | ⏳ 待处理 |

## 详细分析

### 🔴 高优先级 (37处) - 影响核心功能

#### 1. api/routes/analysis.py (19处)

**依赖内容**:
```python
from quantsys.cli.analysis_query import analyze_price_action
from quantsys.cli.analysis_query import calculate_buy_range
from quantsys.cli.analysis_query import get_exit_plan
from quantsys.cli.analysis_query import analyze_candlestick
from quantsys.cli.financial_query import get_financial_indicators
from quantsys.cli.financial_query import get_stock_valuation
from quantsys.cli.screening_query import screen_stocks_quality
from quantsys.cli.financial_query import get_cash_flow
from quantsys.cli.financial_query import get_income_statement
from quantsys.cli.risk_watch_analytics import stress_test
from quantsys.cli.risk_watch_analytics import price_alert
from quantsys.cli.trade_portfolio_analytics import verify_trades
from quantsys.cli.portfolio_analytics import compare_benchmark
from quantsys.cli.portfolio_analytics import optimize_portfolio
from quantsys.cli.trade_portfolio_analytics import correlate_portfolio
from quantsys.cli.factor_decay import analyze_factor_decay
from quantsys.cli.factor_sector_analytics import aggregate_sectors
from quantsys.cli.strategy_analytics import analyze_performance
from quantsys.cli.strategy_analytics import arbitrate_signals
```

**影响功能**: 技术分析、财务分析、风险分析、组合分析、因子分析、策略分析

**修复建议**: 创建 6 个服务类
- `TechnicalAnalysisService` (4个方法)
- `FinancialAnalysisService` (4个方法)
- `RiskAnalysisService` (2个方法)
- `PortfolioAnalysisService` (4个方法)
- `FactorAnalysisService` (2个方法)
- `StrategyAnalysisService` (2个方法)

#### 2. api/routes/risk.py (13处)

**依赖内容**:
```python
from quantsys.cli.risk_query import check_trade_risk
from quantsys.cli.risk_query import calculate_position_size
from quantsys.cli.risk_query import calculate_stop_loss
from quantsys.db.dao import StopLossRuleDAO
from quantsys.data.db import Database
# ... 其他风控相关
```

**影响功能**: 交易风控、仓位计算、止损计算

**修复建议**: 创建 `RiskService`，替换 DAO 和 Database

#### 3. api/routes/stock.py (5处)

**依赖内容**:
```python
from quantsys.cli.stock_query import get_stock_announcements
from quantsys.cli.stock_query import get_stock_news
from quantsys.cli.stock_query import get_batch_stock_quotes
from quantsys.cli.sentiment_query import get_insider_trades
from quantsys.cli.analysis_query import compare_peers
```

**影响功能**: 股票公告、个股新闻、批量行情、内幕交易、同业对比

**修复建议**: 创建 `StockDataService`

### 🟡 中优先级 (6处) - 影响特定功能

#### 4. api/routes/health.py (3处)

**依赖内容**:
```python
from quantsys.data.db import Database
from quantsys.data.fetchers.klines import KlineFetcher
```

**影响功能**: 健康检查、系统诊断

**修复建议**: 用 v2 repositories 替代

#### 5. api/routes/pipeline.py (2处)

**依赖内容**:
```python
from quantsys.data.db import Database
from quantsys.ml.confidence_calibrator import run_calibration
```

**影响功能**: ML 管道、置信度校准

**修复建议**: 更新数据访问层，保留 ML 逻辑

#### 6. services/strategy_code_service.py (1处)

**依赖内容**:
```python
from quantsys.cli.sentiment_query import get_stock_fund_flow
```

**影响功能**: 策略代码生成模板

**修复建议**: 更新模板使用 v2 API

### 🟢 低优先级 (12处) - 非核心功能或工具脚本

#### 7. api/routes/charts.py (1处)

**依赖内容**:
```python
from quantsys.ml import visualizer
```

**影响功能**: 图表可视化

**修复建议**: 如未使用可注释；否则重新实现

#### 8. api/routes/jobs.py (1处)

**依赖内容**:
```python
from quantsys.cli.sentiment_query import get_stock_fund_flow
```

**影响功能**: 后台任务

**修复建议**: 迁移到 `MarketSentimentService`

#### 9. api/routes/signal_test.py (1处)

**影响功能**: 信号测试

**修复建议**: 待确认具体依赖后处理

#### 10. 维护脚本 (9处)

**文件列表**:
- `scripts/migrate_stop_loss_to_db.py` (2处)
- `quantsys-v2/scripts/diagnostics/diagnose_system_indicators.py` (1处)
- `quantsys-v2/scripts/maintenance/backfill_*.py` (6处)

**影响范围**: 一次性迁移脚本、数据回填脚本

**修复建议**: 
- 迁移脚本可保持现状（已完成使命）
- 维护脚本可逐步更新或标记为 legacy

## 修复优先级排序

### Phase 2: 个股数据服务 (1-2天)
**目标**: `stock.py` 5处
- 创建 `StockDataService`
- 实现 5 个方法
- 更新路由

**预期完成度**: 29.1%

### Phase 3: 分析服务重构 (3-5天)
**目标**: `analysis.py` 19处
- 创建 6 个服务类
- 分阶段迁移
- 全面测试

**预期完成度**: 63.6%

### Phase 4: 风控服务 (1天)
**目标**: `risk.py` 13处
- 创建 `RiskService`
- 替换 DAO 和 Database
- 更新路由

**预期完成度**: 87.3%

### Phase 5: 清理收尾 (1天)
**目标**: 剩余 7 处（health, pipeline, charts, jobs, signal_test, services）
- 逐个处理
- 全局验证
- 集成测试

**预期完成度**: 100%

### Phase 6: 脚本更新 (可选)
**目标**: 维护脚本 9 处
- 标记为 legacy
- 或逐步更新
- 非必需

## 总结

### 当前状态
- **已修复**: 11 处（api/routes/market.py）
- **待修复**: 55 处
- **总计**: 66 处
- **完成度**: 16.7%

### 修正后统计
| 类别 | 数量 | 占比 |
|------|------|------|
| API 路由 | 45 | 81.8% |
| 服务层 | 1 | 1.8% |
| 工具脚本 | 9 | 16.4% |
| **运行时关键** | **46** | **83.6%** |

### 关键发现
1. ✅ **market.py 已完全清理**（11处 → 0处）
2. ⚠️ **analysis.py 是最大依赖源**（19处，占总数 34.5%）
3. ⚠️ **risk.py 是第二大依赖源**（13处，占总数 23.6%）
4. 💡 **工具脚本可延后处理**（非运行时关键）

### 推荐行动
1. **立即**: 继续 Phase 2（stock.py 5处）
2. **本周**: 完成 Phase 3（analysis.py 19处）
3. **下周**: 完成 Phase 4（risk.py 13处）
4. **本月**: 完成 Phase 5（剩余 7处）
5. **未来**: 按需更新工具脚本

---

**报告生成时间**: 2026-06-02 23:55:00
**下一步**: 开始 Phase 2 - 个股数据服务清理
