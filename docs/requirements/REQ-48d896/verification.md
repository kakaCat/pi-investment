# REQ-48d896 验收材料：sentiment 端点去 mock

**交付结论**：7 个端点的"伪造/空壳"数据已改为真实数据源实现 —— 其中 5 项新增 provider 方法、
1 项复用已有实现（内部人交易）、1 项只读已有真实表（市场情绪）；
另 1 项（基金重仓股）因**上游数据错位**而诚实失败，拒绝返回不可信数据。

## 一、可复核证据

### 1) 线上端点实测（重启后，2026-09-14 23:2x）

```
GET /api/stock/600519/top-holders    → 200
  {"holderType":"top10","reportDate":"2026-06-30","holders":[{"名次":1,
   "股东名称":"中国贵州茅台酒厂(集团)有限责任公司","持股数":681282935,
   "占总股本持股比例":54.5,...}]}

GET /api/stock/600519/holder-changes → 200
  {"periods":[{"股东户数统计截止日":"2026-06-30","股东户数-本次":296404,
   "股东户数-增减":53245,"股东户数-增减比例":21.9,...}]}

GET /api/stock/600519/fund-holdings  → 200
  {"holdings":[{"基金名称":"招商中证白酒指数C","基金代码":"012414",
   "持仓数量":4562459,"占流通股比例":0.365,"截止日期":"2026-06-30"},...]}

GET /api/stock/600519/insider-trades → 200
  {"records":[],"total":0,"empty":true,"source":"akshare",
   "attemptedSources":["akshare"],"degraded":false}   ← 该股确实无记录（诚实空）

GET /api/sentiment/market            → 200
  {"tradeDate":"2026-09-14","upCount":2278,"downCount":1714,"adRatio":1.33,
   "fearGreedIndex":60.0,"coverage":4155,...}

GET /api/sentiment/stock/600519      → 200
  {"comment":{"名称":"贵州茅台","机构参与度":0.4675,"综合得分":75.2,
   "市盈率":17.94,"主力成本":1277.27},"sourceNote":"东财千股千评..."}

GET /api/sentiment/top-fund-stocks   → 502（诚实失败，见下）
  {"success":false,"error":"All data providers failed",
   "attempted_sources":["akshare"],
   "provider_errors":{"akshare":"数据校验未通过（非空但无效，不计入健康分）"}}
```

### 2) 两次调用一致性（改造前是随机的）

```
✅ 一致  /api/stock/600519/top-holders
✅ 一致  /api/stock/600519/holder-changes
✅ 一致  /api/sentiment/stock/600519
✅ 一致  /api/sentiment/market
```
（改造前证据：同端点两次调用 `shares 13132.08 → 31545.16`、`"李四" → "张三"`）

### 3) 测试

```
$ python -m pytest tests/test_sentiment_real_data.py -q
27 passed

$ python -m pytest tests/test_orm_db_drift.py -q
6 passed

$ python -m pytest tests/test_sentiment_real_data.py tests/test_orm_db_drift.py \
    tests/integration/test_provider_failover.py tests/adapters/outbound/datasources -q
343 passed, 3 failed
```
3 个失败为**既有**：在 `main`（不含本改动，`grep get_top_holders manager.py = 0`）上同样失败
（`TestCircuitBreaker` 3 例，熔断状态跨测试泄漏）。

### 4) 关键测试覆盖

- `test_top_fund_stocks_rejects_misaligned_upstream` —— 上游错位表**必须拒绝**；
- `test_top_holders_all_periods_missing_is_healthy_empty` —— 数据缺失≠故障；
- `test_top_holders_transport_error_is_hard_failure` —— 传输故障→None（进熔断）；
- `test_insider_trades_reuses_cached_market_df` —— 2.5 万行接口 TTL 缓存命中；
- `test_sentiment_route_returns_502_on_provider_failure` —— 降级不假成功；
- `test_no_mock_generators_anywhere_in_adapters` / `test_mock_datasource_is_deleted` —— 防回归护栏。

## 二、改动清单

| 文件 | 改动 |
|---|---|
| `adapters/outbound/datasources/providers/market/akshare.py` | +5 方法、TTL 缓存、JSON 安全转换、健康空/硬失败分流、上游完整性校验 |
| `adapters/outbound/datasources/manager.py` | +5 转发方法（走 `_try_providers`） |
| `adapters/inbound/fastapi_app/routes/sentiment_async.py` | 4 端点改调框架 + 502 降级 |
| `adapters/inbound/fastapi_app/routes/stock_async.py` | insider 端点改指向已有方法（+days 过滤） |
| `adapters/inbound/fastapi_app/routes/p1_batch_async.py` | 2 端点接真实数据源 |
| `adapters/inbound/fastapi_app/shared.py` | + `provider_payload()`（诚实标记统一出口） |
| `adapters/outbound/datasources/sentiment_data_source.py` | **删除**（random 伪造实现） |
| `adapters/outbound/repositories/sentiment_async_repository.py` | **删除**（绑定幻觉表） |
| `tests/test_sentiment_real_data.py` | 新增 27 例 |
| `tests/test_orm_db_drift.py` | 悬空基线收敛 `quant.sentiment_data` |

## 三、遗留与风险

1. **`/api/sentiment/top-fund-stocks` 不可用**：上游 `stock_report_fund_hold` 列错位，
   三种替代源均不可用（详见工作日志 §五）。需产品决策（等上游 / 换子集语义+定时任务）。
2. 契约变更（记录键改为原生列、market 改真实指标）**仓内零消费者**，但对任何外部调用方是破坏性变更。
3. 兄弟源 `fund_flow_source`/`margin_data_source` 未迁入框架。
4. 门禁以测试库为口径，"测试库有、生产没有"仍看不见。

## 四、文档

- 工作日志：`docs/work-logs/2026-09/v2-sentiment-real-data-source.md`
- 实施计划：`docs/requirements/REQ-48d896/plan.md`
- 项目说明书更新：`docs/architecture/project-manual.md`（新增 provider 框架术语 + 本需求更新点）
