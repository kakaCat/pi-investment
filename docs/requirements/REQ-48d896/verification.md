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

$ python -m pytest tests/test_eastmoney_market_provider.py tests/test_sentiment_real_data.py \
    tests/test_orm_db_drift.py tests/integration/test_provider_failover.py \
    tests/adapters/outbound/datasources -q
355 passed, 3 failed
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

---

## 五、t9 追加交付：东财直连第二源（含"修好被阻塞的端点"）

### 5.1 关键成果：`/api/sentiment/top-fund-stocks` 从 502 恢复为 200

**根因**：akshare 对该接口用**位置式列名**（N 个名字按顺序硬套到东财返回的数组上），
东财字段一变就整体错位 —— 实测映射错位表：

| akshare 列名 | akshare 给的值 | 东财真实字段 |
|---|---|---|
| 股票简称 | `'300308'`（其实是代码） | SECURITY_CODE |
| 持有基金家数 | `'01'`（其实是机构类型） | ORG_TYPE |
| 持股总数 | `3578`（其实是家数） | HOULD_NUM |
| 股票代码 | `141398625194.02`（其实是持股市值） | — |

**修复**：东财直连按**字段名**取值，结构上不可能错位。线上复验：

```
GET /api/sentiment/top-fund-stocks?limit=2 → 200
{"success":true,"data":{"fundType":"基金持仓","reportDate":"2026-06-30","stocks":[
  {"序号":1,"股票代码":"300308","股票简称":"中际旭创","持有基金家数":3578,
   "持股总数":214732617,"持股市值":272710423590,"持股变化":"减仓",
   "持股变动数值":-15877661,"持股变动比例":-6.89},
  {"序号":2,"股票代码":"603293","股票简称":"埃泰克","持有基金家数":31...}]}}
```

### 5.2 failover 实测（kacceptance：拔掉 akshare 自动切换）

```
akshare get_top_fund_stocks: 上游 基金持仓 列错位（股票代码 列非 6 位代码，
  实测样例 [141398625194.02, 14600642.8800004, -34423004720.08]）——拒绝返回不可信数据
get_top_fund_stocks  success=True  source=eastmoney  attempted=['akshare','eastmoney']
```
`attempted_sources` 如实含**两个源**，成功由第二个源提供。

### 5.3 覆盖与不覆盖（诚实声明）

| 方法 | akshare | eastmoney | 源数 |
|---|---|---|---|
| get_top_holders | ✅ | ✅ | 2 |
| get_holder_changes | ✅ | ✅ | 2 |
| get_top_fund_stocks | ⚠️（错位，拒收） | ✅ | 2 |
| get_stock_comment | ✅ | ✅ | 2 |
| get_fund_holdings | ✅（**新浪**上游） | ✖（东财报表混装机构且 ORG_TYPE_NAME 为 None，筛不可靠） | 1 |

→ 除 `get_fund_holdings`（其上游本就是新浪，与东财不同通道）外，**不再有"单源无兜底"的数据类型**。

### 5.4 t9 测试

```
tests/test_eastmoney_market_provider.py  10 passed
```
覆盖：字段映射语义正确（重点 top_fund_stocks 的代码/简称归位）、多报告期取最新、
`last_error` 必设（框架据此判真故障）、**异常绝不出抛**（`_try_providers` 只捕获超时，
其它异常会穿透 failover 循环）、健康空、拔掉 akshare 自动切换、上游错位场景兜底为正确数据。

### 5.5 顺带修正的分类缺陷

框架只在 provider **自报 `last_error`** 时才判真故障；否则 `None` 会被归为
「非空但无效」且**错误原因丢失**。上一轮的完整性拒收未设 `last_error`，
线上显示成 `"数据校验未通过（非空但无效，不计入健康分）"` —— 分类错误。
本次给 akshare 源补齐 `last_error` 纪律（14 处，含每次调用开头重置）。

### 5.6 变更后的遗留（相较 §三 前提）

- ~~`/api/sentiment/top-fund-stocks` 不可用~~ → **已修复**（东财直连兜底）；
- `get_fund_holdings` 单源（见 §5.3，上游独立，非缺口）；
- `public.audit_log`、`quant.async_factors` 两个悬空模型仍在门禁豁免名单（需产品决策）；
- 门禁以测试库为口径，"测试库有、生产没有"仍看不见。
