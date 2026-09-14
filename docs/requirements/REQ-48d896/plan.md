# REQ-48d896 实施计划：sentiment 端点去 mock，接真实数据源

## 一、问题（已实测固定证据）

### A. 5 个端点返回**伪造数据**
`adapters/outbound/datasources/sentiment_data_source.py`（388 行）：
- `import random`，**无 akshare、无 requests**；
- 5 个 public 方法 **5/5** 调用 `_generate_mock_*`；
- 源码注释自认：`# 模拟数据（实际应该从akshare或其他数据源获取）`。

铁证（同一端点连续两次调用）：
```
/api/stock/600519/top-holders   shares 13132.08 → 31545.16
/api/stock/600519/insider-trades "李四"/178.82/47.12 → "张三"/320.32/22.57
```
响应体恒 `{"success":true,...}`，**无任何 mock/degraded 标记**。
`agent-ts` 的 `V2_ROUTES` 把这 5 条标注为「✅ v2 原生实现完成」。

### B. 2 个端点**空壳**
`/api/sentiment/market`、`/api/sentiment/stock/{symbol}` → `SentimentAsyncRepository` →
`quant.sentiment_data`：该表**无任何迁移创建**、写入方 `save_sentiment` **零调用**、
读方法无数据源输入 → 恒返回 `data:{}` / `data:null` + `success:true`。

### C. 已核实的暴露面（当前无消费者）
- agent-ts：`sentiment_cli` 等 CLI「从未注册进 allCustomTools」（自证死代码）→ 调不到；
- agent-dh：`stock_intel` 走 `/api/provider/stock/{symbol}/insider-trades`，实测 `records:[], total:0, source:akshare` ——
  经核实 600519 在真源中确实命中 0 行（该源覆盖 2127 只），**属诚实空，不是缺陷**；
- web 前端：5 个端点零引用。

→ 结论：端点活着但无人调，**任何外部调用方都会拿到伪造数据**。

## 二、真实数据源可行性（已逐个实测，akshare 1.18.81）

| 端点 | 真源函数 | 实测结果 |
|---|---|---|
| `/api/stock/{symbol}/holder-changes` | `stock_zh_a_gdhs_detail_em(symbol)` | ✅ 63 行×15 列（股东户数/增减/户均持股） |
| `/api/stock/{symbol}/top-holders` | `stock_gdfx_top_10_em` / `stock_gdfx_free_top_10_em` | ✅ 10 行×7/8 列（需 `sh600519` 前缀 + 报告期） |
| `/api/stock/{symbol}/fund-holdings` | `stock_fund_stock_holder(symbol)` | ✅ 992 行×7 列（基金名称/持仓/占比/市值） |
| `/api/stock/{symbol}/insider-trades` | `stock_inner_trade_xq()` | ✅ 25,758 行×9 列，覆盖 2127 只（全市场，需按符号过滤） |
| `/api/sentiment/top-fund-stocks` | `stock_report_fund_hold(symbol,date)` | ✅ 5225 行×9 列，**列名与现契约一一对应**（持有基金家数/持股总数/持股市值） |
| `/api/sentiment/market` | `quant.market_sentiment_daily`（库内） | ✅ 真实数据（2026-09-14：涨2278/跌1714/ad 1.33/恐贪 60） |
| `/api/sentiment/stock/{symbol}` | `stock_comment_em()` 千股千评 | ✅ 5196 行×14 列（机构参与度/综合得分/换手率/市盈率/主力成本） |

## 三、设计

1. **数据层**：重写 `SentimentDataSource` 为真实实现，**保留 public 方法名与返回键**；
   每个响应新增诚实元数据 `source`（如 `akshare:stock_inner_trade_xq`）、`as_of`；
   失败时返回 `{degraded: true, error: "...", source: ...}`，**绝不返回无标记的空/假数据**。
2. **缓存**：`stock_inner_trade_xq`（2.5万行）与 `stock_comment_em`（5196行）为全市场拉取，
   加进程内 TTL 缓存（内部交易 5min、千股千评 10min、基金持仓 30min），避免每请求打上游。
3. **符号与报告期**：`600519 → sh600519` 前缀映射；十大股东需报告期 →
   从最近季度向前回退直至取到数据（最多回退 4 期），并将实际报告期写进响应 `report_date`。
4. **契约变更（2 个空壳端点）**：现契约是按个股情绪分类计数（`bullish/bearish/neutral/total`），
   但真源是市场级指标 → **改用真实指标键**（`up_count/down_count/ad_ratio/fear_greed_index/volume_ratio`）
   并在响应注明口径；因零消费者，变更风险可控，但必须写进文档。
5. **退役死模型**：删除 `SentimentAsyncRepository` + `quant.sentiment_data` 模型
   （无表、无写方、2 个消费者改走真实路径后即无引用）→ 顺带从漂移门禁 allowlist 收敛 1 条。
6. **防回归**：新增源码级护栏测试 —— 断言 `sentiment_data_source.py` 中
   `_generate_mock_*` 与 `import random` **不再存在**；断言降级路径必带显式标记。

## 四、任务表

| key | 标题 | phase | side | 依赖 | 验收标准 |
|---|---|---|---|---|---|
| t1 | 重写 SentimentDataSource 接 akshare 真源（5 方法 + TTL 缓存 + 降级标记） | implement | backend | — | 5 方法均真实拉取；拔网/异常时返回 `degraded:true + error + source`；无 `random`；单测 mock akshare 全绿 |
| t2 | 5 个 mock 端点接真实数据层并统一来源标注 | implement | backend | t1 | 7 端点中 5 个实测返回真实值；连续两次调用结果**一致**（非随机）；响应含 `source`/`as_of` |
| t3 | /api/sentiment/market 接 quant.market_sentiment_daily 并明确新契约 | implement | backend | t1 | 返回真实涨跌家数/恐贪指数；无数据时显式 `degraded`；文档记录契约变更 |
| t4 | /api/sentiment/stock/{symbol} 接 stock_comment_em 千股千评 | implement | backend | t1 | 返回该股机构参与度/综合得分等真实值；未覆盖的标的显式 `empty:true`，非假成功 |
| t5 | 退役 quant.sentiment_data 死模型与 SentimentAsyncRepository | implement | backend | t2,t3,t4 | 全仓零引用；探针「内联缺表」减 1；门禁 allowlist 同步收敛 |
| t6 | 测试：契约/降级/防 mock 护栏 | test | backend | t2,t3,t4,t5 | 新增测试覆盖 7 端点契约 + 降级路径 + 源码护栏（禁 `_generate_mock_*`）；目标全绿 |
| t7 | 线上真实验证（重启后逐端点实测 + 两次一致性） | test | fullstack | t6 | 7 端点 curl 实测贴出响应；两次调用一致；降级路径人工拔源验证 |
| t8 | 文档与门禁收敛 | doc | doc | t7 | 工作日志更新；REQ 目录文档齐备；pyramid manual_updates 写入项目说明书 |

## 五、风险与不做的事

- **不做**：不改 `/api/provider/*`（已核实诚实）；不动 Agent 工具契约；不引入新表（除退役）。
- **风险 1**：akshare 上游不稳定/限频 → 用具 TTL 缓存 + 显式降级，不静默；
- **风险 2**：十大股东报告期回退可能 4 期都取不到 → 返回 `empty:true + report_date:null`，不伪造；
- **风险 3**：契约变更若存在未知外部调用方 → 文档明示 + 保留旧键名映射（`bullish/bearish/neutral` 置 null 并注明 deprecated）。
