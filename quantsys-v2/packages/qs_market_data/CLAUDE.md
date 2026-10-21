# qs_market_data — 数据供给包

> 抽离记录：quantsys-v2 单体 S3（2026-10-18）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S3。

## 本包是什么

**AI 工作区 L2**：本目录=「数据供给」项目。上下文只要本文件，不要去根工作区。

- **定位**：AI agent 派生系统里所有股票/行情数据的**唯一取数出口**（根仓库 CLAUDE.md「⚠️ Data Access Rules」的对齐物）
- 对外核心符号：`DataProviderManager` / `get_data_provider_manager()`（多源故障转移 + 熔断 + 健康排序）、`QuoteData/FinancialData/DividendData...`

## 目录结构

```
qs_market_data/
├── application/services/          数据供给服务层
│   ├── data_service.py            DataService（K线业务包装，DataService.kline.*）
│   ├── stock_data_service.py / market_data_service.py / hk_market_data_service.py
│   ├── realtime_quote_service.py  (+ _v2)  实时行情（v2 走 quote_providers）
│   ├── dividend_service.py / dividend_data_source.py  分红
│   ├── valuation_data_service.py  估值
│   ├── financial_data_service_adapter.py / financial_analysis_service.py  财务
│   ├── trading_calendar_service.py 交易日历
│   ├── stock_code_validator.py    股票代码校验
│   ├── data_backfiller.py / data_gap_detector.py  数据回补/缺失检测
│   ├── financial_providers/       财务源适配（eastmoney_direct / sina_web）
│   └── quote_providers/           实时行情源适配（akshare / tencent / sina / netease / eastmoney）
└── adapters/outbound/datasources/ Provider 框架（16,786 行）
    ├── manager.py                 统一入口（2110 行，熔断/缓存/回退）
    ├── base.py / models.py / circuit_breaker*.py / cache.py / monitoring.py
    └── providers/                 13 子包：kline quote dividend financial events
        industry_chain minute_kline index hk market sector stock quantlib
```

## 依赖边界（方案卡 §11.3 白名单）

- ✅ **本包不依赖任何业务项目**（sourcing/trading/watch/...）；允许 import kernel 层
- 暂留 L1 引用（S11 kernel 成型后收口）：`domain.models.market_data`、`domain.events.{ports,model}`、`domain.ports.datasource_ports`、`domain.exceptions`、`domain.factors.library.*`（一个 provider 内）、`domain.industry_chain.ports`、`application.services.base_service`（dividend_service）、`domain.trading.ports.ITradingCalendar`
- 旧路径兼容 shim 在 L1：`adapters/outbound/datasources/`、`application/services/<15 模块名>.py`、`financial_providers/`、`quote_providers/`（`__path__` 转发，30 天观察期后删除）

## 已知技术债（随包带来，别在域内任务里装看不到）

1. `providers/quote/akshare.py` 与 `quote_providers/akshare_provider.py` **直接 import akshare** —— 违反根 CLAUDE.md 数据取数规则，历史债务；统一收口到 manager 网格是后续重构项
2. `providers/quote/tests/` 是历史误植的内嵌测试树（镜像路径 import，仅 1 个文件）
3. 旧路径 `qs_market_data` 场外代码若仍 import `adapters.outbound.datasources`，shim 存续期内可用，请尽快改为 `qs_market_data.adapters.outbound.datasources`

## 常见任务路径

- **换数据源/降级策略** → `adapters/outbound/datasources/manager.py`（`get_data_provider_manager`，熔断态机 `circuit_breaker*.py`）
- **加一个 K 线源** → `providers/kline/`（照 `akshare.py` 模式 + 在 manager/providers 注册表登记）
- **加财务/估值字段** → `providers/financial/` + `financial_providers/`（两套：日频抓取 vs 直连网页）
- **修日历口径** → `trading_calendar_service.py`
- **数据缺失/回补** → `data_gap_detector.py`（比对交易日历）→ `data_backfiller.py`
