# REQ-48d896 实施计划（v3 · 含「已实现」审计，避免重复实现）

> v1：`SentimentDataSource` 直连 akshare（单源、绕框架）→ 废弃。
> v2：改走 provider 多源框架。
> **v3（本版）**：新增第 2 节「已实现审计」—— 用户要求"已经实现的不要重复实现"，
> 逐项核对后确认 **7 项需求里 2 项已存在**（1 项代码已就绪、1 项数据已在库），只对 **5 项**新增实现。

## 一、问题（证据已固定）

### A. 5 个端点返回**伪造数据**
`sentiment_data_source.py`（388 行）：`import random`、无 akshare/requests、5/5 public 方法调
`_generate_mock_*`，注释自认「实际应该从akshare或其他数据源获取」。
铁证（同端点连续两次）：top-holders `shares 13132.08 → 31545.16`；insider-trades `"李四"→"张三"`。
响应恒 `success:true`，无 mock/degraded 标记。

**mock 端点精确清单（已验证，只是 5 个）：**
| 端点 | 位置 |
|---|---|
| `/api/stock/{symbol}/fund-holdings` | `routes/sentiment_async.py:85` |
| `/api/stock/{symbol}/top-holders` | `routes/sentiment_async.py:97` |
| `/api/stock/{symbol}/holder-changes` | `routes/sentiment_async.py:109` |
| `/api/sentiment/top-fund-stocks` | `routes/sentiment_async.py:121` |
| `/api/stock/{symbol}/insider-trades` | `routes/stock_async.py:174` |

同文件另 3 个端点**已是真实实现**，不在改造范围：`/fund-flow`(`FundFlowDataSource`)、
`/margin`(`MarginDataSource`)、`/lhb`(`lhb_service`)—— 实测分别返回真实数据/honest error。

### B. 2 个端点**空壳**
`/api/sentiment/market`、`/api/sentiment/stock/{symbol}` → `quant.sentiment_data`：
无迁移建表、写方 `save_sentiment` 零调用 → 恒 `data:{}`/`data:null` + `success:true`。

## 二、已实现审计（**复用清单，不重复实现**）

审计方法：①全仓搜 akshare 真源函数名；②`DataProviderManager` 55 个方法逐一比对；
③DB 表名扫描；④全部路由扫描；⑤兄弟数据源（`*_source.py`）排查。

| # | 需求 | 是否已有实现 | 证据 | 本需求要做的事 |
|---|---|---|---|---|
| 1 | 内部人交易 | ✅ **代码已就绪** | `providers/market/akshare.py:448`（`stock_inner_trade_xq`）+ `manager.py:950` + 端点 `/api/provider/stock/{symbol}/insider-trades` | **不新增代码**，仅把 mock 路由改指向已有 manager 方法 |
| 2 | 十大股东 | ❌ 无 | `stock_gdfx_top_10_em`/`stock_gdfx_free_top_10_em` 全仓未被使用；DB 无表；manager 无方法 | 新增 provider 方法 |
| 3 | 股东户数变化 | ❌ 无 | `stock_zh_a_gdhs_detail_em` 未被使用 | 新增 provider 方法 |
| 4 | 基金持股 | ❌ 无 | `stock_fund_stock_holder` 仅出现在 `tests/test_stock_data_fix.py`（测试，非生产） | 新增 provider 方法 |
| 5 | 基金重仓股 | ❌ 无 | `stock_report_fund_hold` 未被使用 | 新增 provider 方法 |
| 6 | 千股千评（个股情绪） | ❌ 无 | `stock_comment_em` 未被使用 | 新增 provider 方法 |
| 7 | 市场情绪 | ✅ **数据已在库** | `quant.market_sentiment_daily` 有真实数据（09-14 涨2278/跌1714/ad1.33/恐贪60） | **不建取数链**，仅读表 |

→ **结论：7 项里只有 5 项需要新增实现（#2–#6）；#1 复用已有代码，#7 读已有表。**

## 三、架构决策：走 provider 多源框架

框架 = `DataProviderManager._try_providers(providers, method, ...)`：

| 能力 | 证据（manager.py） |
|---|---|
| 故障转移：跳过未实现该方法的源 | L339 `if not hasattr(provider, method_name): continue` |
| 熔断 / 健康排序 | L333 / L326 |
| 诚实标记 | `source / attempted_sources / empty_sources / provider_errors / empty` |
| 「空结果≠故障」契约 | L318 |

market 域现有 3 源（`akshare` 12 方法 / `sina` 3 / `ths` 4）。

**为什么不仿照兄弟源 `fund_flow_source.py`/`margin_data_source.py`（顶层 standalone 单上游包装）？**
因为 #1 的真实实现已在框架内，同一族数据放两处会重演「平行实现」老问题（本仓已因平行实现出过 3 次线上静默故障）；
且新数据需要故障转移/熔断。**代价已登记**：与那两个兄弟源风格不一致，把它们迁入框架**不在本需求范围**。

### 多源现状（诚实声明，不夸大）
#2–#6 当前**只有 akshare 一个真源**（底层封装东财）→ 今天是「框架就绪的单源」，
`attempted_sources` 只会是 `["akshare"]`，**不是多源故障转移**；加第二源即自动参与。
第二源（东财直连，本仓已有 `providers/quote/eastmoney.py` 等可照抄）→ 可选任务 t9。

## 四、真实数据源可行性（已逐个实测，akshare 1.18.81）

| 数据 | 真源函数 | 实测 |
|---|---|---|
| 股东户数变化 | `stock_zh_a_gdhs_detail_em(symbol)` | ✅ 63 行×15 列 |
| 十大股东 | `stock_gdfx_top_10_em` / `stock_gdfx_free_top_10_em` | ✅ 10 行×7/8 列（需 `sh600519` 前缀 + 报告期） |
| 基金持股 | `stock_fund_stock_holder(symbol)` | ✅ 992 行×7 列 |
| 基金重仓股 | `stock_report_fund_hold(symbol,date)` | ✅ 5,225 行×9 列，**列名与现契约一一对应** |
| 千股千评 | `stock_comment_em()` | ✅ 5,196 行×14 列（机构参与度/综合得分） |
| 市场情绪 | `quant.market_sentiment_daily` | ✅ 库内真实（无需外部源） |

## 五、其余设计

1. **符号与报告期**：`600519 → sh600519`；十大股东需报告期 → 最近季度向前回退（≤4 期），
   实际报告期写入 `report_date`；回退全空 → `empty:true + report_date:null`，不伪造。
2. **TTL 缓存**（全市场拉取）：`stock_comment_em`(5196行) 10min、`stock_report_fund_hold`(5225行) 30min；
   单股接口（股东户数/十大股东/基金持股）5min。
3. **契约变更（2 个空壳端点）**：现契约是按个股情绪分类计数，真源是市场级指标 →
   改用真实键（`up_count/down_count/ad_ratio/fear_greed_index/volume_ratio`），旧键保留并标 `deprecated`；
   零消费者，风险可控但写入文档。
4. **个股端点语义**：返回**千股千评指标**（机构参与度/综合得分/换手率/市盈率），**不冒充**情绪分类；
   未覆盖标的 `empty:true`。
5. **防回归护栏**：源码级测试断言 `sentiment_data_source.py` 已删、`_generate_mock_*`/`import random` 在情绪链路不存在。

## 六、任务表

| key | 标题 | phase | side | 依赖 | 验收标准 |
|---|---|---|---|---|---|
| t1 | provider 框架内新增 **5** 个方法（十大股东/股东户数/基金持股/基金重仓股/千股千评）+ TTL 缓存 | implement | backend | — | 5 方法经 `_try_providers` 返回真实数据；异常/空结果带 `source/attempted_sources/empty_sources`；单测 mock akshare 全绿 |
| t2 | 4 个 mock 端点改调新 provider 方法；**insider-trades 端点改指向已有 `manager.get_insider_trades`（不新增实现）** | implement | backend | t1 | 5 端点实测真实值；连续两次调用**一致**（非随机）；insider 端点未新增 provider 代码 |
| t3 | /api/sentiment/market **只读** `quant.market_sentiment_daily` 并明确新契约 | implement | backend | t1 | 返回真实涨跌家数/恐贪指数；无数据显式 `degraded`；契约变更写入文档 |
| t4 | /api/sentiment/stock/{symbol} 接千股千评（复用 t1 的 provider 方法） | implement | backend | t1 | 返回该股机构参与度/综合得分；未覆盖标的 `empty:true` |
| t5 | 删除 `SentimentDataSource` 整体 + 退役 `quant.sentiment_data` 死模型 | implement | backend | t2,t3,t4 | 全仓零引用；漂移探针「内联缺表」减 1；门禁 allowlist 收敛 |
| t6 | 测试：契约 / 降级 / 防 mock 护栏 | test | backend | t5 | 7 端点契约 + 降级路径 + 源码护栏全覆盖；全绿 |
| t7 | 线上真实验证（重启后逐端点实测 + 两次一致性 + 拔源降级） | test | fullstack | t6 | 7 端点 curl 响应贴出；两次一致；降级路径人工验证 |
| t8 | 文档与门禁收敛 | doc | doc | t7 | 工作日志更新；REQ 目录齐备；项目说明书 manual_updates 写入 |
| t9 | **（可选）** 增设 eastmoney 直连第二源 | implement | backend | t1 | 至少 1 方法有 2 源；拔掉 akshare 自动切换且 `attempted_sources` 含两源 |

## 七、风险与不做的事

- **不做**：不改 `/api/provider/*`；不动 agent 工具契约；不新增数据表；
  **不重复实现 #1（已有）与 #7（数据已在库）**；不迁移兄弟源（`fund_flow_source`/`margin_data_source`）入框架。
- **风险 1**：akshare 限频 → TTL 缓存 + 显式降级；
- **风险 2**：报告期回退取不到 → 显式 `empty:true`；
- **风险 3**：契约变更遇未知外部调用方 → 文档明示 + 旧键标 `deprecated`。
