# REQ-48d896 实施计划（v2 · 修订：改为走 provider 多源框架）

> v1 计划写的是「`SentimentDataSource` 直接接 akshare」—— **单源且绕过本仓已有的多源框架**，
> 且没发现 insider-trades 的真实实现早已在框架内。本版按框架约定重写。

## 一、问题（证据已固定）

### A. 5 个端点返回**伪造数据**
`adapters/outbound/datasources/sentiment_data_source.py`（388 行）：`import random`、无 akshare/requests、
5/5 public 方法调 `_generate_mock_*`，注释自认「实际应该从akshare或其他数据源获取」。

铁证（同端点连续两次）：top-holders `shares 13132.08 → 31545.16`；
insider-trades `"李四"/178.82 → "张三"/320.32`。响应恒 `success:true`，**无 mock/degraded 标记**。

### B. 2 个端点**空壳**
`/api/sentiment/market`、`/api/sentiment/stock/{symbol}` → `quant.sentiment_data`：
无迁移建表、写入方 `save_sentiment` 零调用、读方法无数据源 → 恒 `data:{}`/`data:null` + `success:true`。

### C. 暴露面（已核）
agent-ts 的 `sentiment_cli` 等「从未注册进 allCustomTools」（自证死代码）；agent-dh `stock_intel` 走
`/api/provider/...` 返回诚实空（**已核实 600519 在真源中确实 0 行，不是缺陷**）；前端零引用。

## 二、架构决策：为什么不直连 akshare

本仓已有 provider 多源框架 `DataProviderManager._try_providers(providers, method, ...)`：

| 能力 | 证据（manager.py） |
|---|---|
| 故障转移：跳过未实现该方法的源 | L339 `if not hasattr(provider, method_name): continue` |
| 熔断 | L333 `_is_circuit_broken` |
| 按健康度排序 | L326 `_sort_providers_by_health` |
| 诚实标记 | 返回 `source/attempted_sources/empty_sources/provider_errors/empty` |
| 「空结果≠故障」契约 | L318 注释 |

market 域现有 3 个源：`akshare.py`(12 方法) / `sina.py`(3) / `ths.py`(4)。

**关键**：`get_insider_trades` 的**真实实现早已在框架内**（`providers/market/akshare.py:448` +
`manager.py:950`）→ `SentimentDataSource` 那份 mock 是同一数据的**第三份平行实现**。

因此：
1. **不**在 `SentimentDataSource` 里直连 akshare（会绕过熔断/健康排序/诚实标记）；
2. 新增的 5 类数据**作为框架方法**实现（`manager` 转发 + `providers/market/akshare.py` 落地）；
3. insider-trades **不新增代码**，端点直接改调已有的 `manager.get_insider_trades`；
4. 最终**删除整个 `SentimentDataSource`**（含 `import random` 与 5 个 mock 方法）。

### 多源现状（诚实声明，不夸大）
这 5 类数据当前**只有 akshare 一个真源**（其底层封装东财数据）。所以：
- 今天 `attempted_sources` 只会有 `["akshare"]` —— **是「框架就绪的单源」，不是多源故障转移**；
- 框架收益仍然即时生效：熔断、健康排序、空≠故障、显式降级标记；
- 加第二源即自动参与故障转移。本仓已有东财直连适配器可照抄
  （`providers/quote/eastmoney.py`、`financial/eastmoney.py`、`sector/eastmoney.py`）→ 见可选任务 t9。

## 三、真实数据源可行性（已逐个实测，akshare 1.18.81）

| 数据 | 真源函数 | 实测 |
|---|---|---|
| 股东户数变化 | `stock_zh_a_gdhs_detail_em(symbol)` | ✅ 63 行×15 列 |
| 十大股东 | `stock_gdfx_top_10_em` / `stock_gdfx_free_top_10_em` | ✅ 10 行×7/8 列（需 `sh600519` 前缀 + 报告期） |
| 基金持股 | `stock_fund_stock_holder(symbol)` | ✅ 992 行×7 列 |
| 内部人交易 | `stock_inner_trade_xq()` | ✅ 25,758 行×9 列（覆盖 2127 只）**框架已有** |
| 基金重仓股 | `stock_report_fund_hold(symbol,date)` | ✅ 5,225 行×9 列，**列名与现契约一一对应** |
| 市场情绪 | `quant.market_sentiment_daily`（库内） | ✅ 真实（09-14 涨2278/跌1714/恐贪60） |
| 个股千股千评 | `stock_comment_em()` | ✅ 5,196 行×14 列（机构参与度/综合得分） |

## 四、其余设计

1. **符号与报告期**：`600519 → sh600519` 前缀映射；十大股东需报告期 → 从最近季度向前回退（≤4 期），
   把实际报告期写进响应 `report_date`；回退全空则 `empty:true + report_date:null`，不伪造。
2. **全市场拉取缓存**：`stock_inner_trade_xq`(2.5万行)、`stock_comment_em`(5196行)、
   `stock_report_fund_hold`(5225行) 加进程内 TTL（5/10/30 分钟），避免每请求打上游。
3. **契约变更（2 个空壳端点）**：现契约是按个股情绪分类计数（`bullish/bearish/neutral/total`），
   真源是市场级指标 → 改用真实键（`up_count/down_count/ad_ratio/fear_greed_index/volume_ratio`），
   并在响应注明口径与 `deprecated` 提示；因零消费者，风险可控但必须写文档。
4. **个股端点语义**：返回**千股千评指标**（机构参与度/综合得分/换手率/市盈率），
   **不冒充**「情绪分类」；未覆盖标的显式 `empty:true`。
5. **防回归护栏**：源码级测试断言 `sentiment_data_source.py` 已删除、`_generate_mock_*`/`import random`
   在全仓情绪链路中不存在；降级路径必带显式标记。

## 五、任务表

| key | 标题 | phase | side | 依赖 | 验收标准 |
|---|---|---|---|---|---|
| t1 | provider 框架内新增 5 个 sentiment 方法（manager 转发 + market/akshare 落地 + TTL 缓存） | implement | backend | — | 5 方法经 `_try_providers` 返回真实数据；异常/空结果带 `source/attempted_sources/empty_sources`；单测 mock akshare 全绿 |
| t2 | 5 个 mock 端点改调 provider 框架（insider-trades 复用已有方法，不新增代码） | implement | backend | t1 | 5 端点实测返回真实值；连续两次调用**一致**（非随机）；响应含 `source` |
| t3 | /api/sentiment/market 接 quant.market_sentiment_daily 并明确新契约 | implement | backend | t1 | 返回真实涨跌家数/恐贪指数；无数据显式 `degraded`；契约变更写入文档 |
| t4 | /api/sentiment/stock/{symbol} 接千股千评 stock_comment_em | implement | backend | t1 | 返回该股机构参与度/综合得分等真实值；未覆盖标的 `empty:true` 而非假成功 |
| t5 | 删除 SentimentDataSource 整体 + 退役 quant.sentiment_data 死模型 | implement | backend | t2,t3,t4 | 全仓零引用（含 `import random`/5 个 mock 方法消失）；漂移探针「内联缺表」减 1；门禁 allowlist 收敛 |
| t6 | 测试：契约 / 降级 / 防 mock 护栏 | test | backend | t5 | 7 端点契约 + 降级路径 + 源码护栏全覆盖；全绿 |
| t7 | 线上真实验证（重启后逐端点实测 + 两次一致性 + 拔源降级） | test | fullstack | t6 | 7 端点 curl 响应贴出；两次一致；降级路径人工验证 |
| t8 | 文档与门禁收敛 | doc | doc | t7 | 工作日志更新；REQ 目录文档齐备；项目说明书 manual_updates 写入 |
| t9 | **（可选）** 为股东/基金类方法增设 eastmoney 直连第二源，使故障转移真正生效 | implement | backend | t1 | 至少 1 个方法有 2 个源；拔掉 akshare 后自动切换且 `attempted_sources` 含两个源 |

> t9 为**可选**：不做则上述方法为「单源 + 框架就绪」。批准时可明确剔除。

## 六、风险与不做的事

- **不做**：不改 `/api/provider/*`（已核实诚实）；不动 agent 工具契约；不新增数据表。
- **风险 1**：akshare 上游限频 → TTL 缓存 + 显式降级，不静默；
- **风险 2**：报告期回退取不到 → 显式 `empty:true`，不伪造；
- **风险 3**：契约变更遇未知外部调用方 → 文档明示 + 保留旧键并标 `deprecated`。
