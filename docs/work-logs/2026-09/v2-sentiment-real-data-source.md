# sentiment 端点去 mock：7 个端点接真实数据源（REQ-48d896）

**日期**：2026-09-14 | **窗口**：w-2129d492 | **分支**：`feat/sentiment-real-data`
**需求**：REQ-48d896（feature）| **提交**：`08004063` → `6b04cf92` → `7026fed6` → `bda83399`

---

## 一、问题（改造前，证据已固定）

### A. 4 个端点返回**伪造数据**

`adapters/outbound/datasources/sentiment_data_source.py`（388 行）：
- `import random`，**无 akshare、无 requests**；
- 5 个 public 方法 **5/5** 调 `_generate_mock_*`；源码注释自认
  「`# 模拟数据（实际应该从akshare或其他数据源获取）`」；
- 响应恒 `{"success":true,...}`，**无任何 mock/degraded/来源标记**；
- `agent-ts` 的 `V2_ROUTES` 把这 5 条标注为「✅ v2 原生实现完成」。

铁证（同一端点连续两次调用）：
```
/api/stock/600519/top-holders   shares 13132.08 → 31545.16
/api/stock/600519/insider-trades "李四"/178.82/47.12 → "张三"/320.32/22.57
```

### B. 2 个端点**空壳**

`/api/sentiment/market`、`/api/sentiment/stock/{symbol}` → `SentimentAsyncRepository` →
`quant.sentiment_data`：该表**无任何迁移创建过**、唯一写入方 `save_sentiment` **零调用**、
读方法无数据源输入 → 恒 `data:{}` / `data:null` + `success:true`。

### C. 暴露面（改造前已核）
agent-ts 的 `sentiment_cli` 等「从未注册进 allCustomTools」（自证死代码）；
agent-dh `stock_intel` 走 `/api/provider/...` 返回诚实空（已核实 600519 在真源中确实 0 行，
该源仅覆盖 2127 只）→ **不是缺陷**；前端零引用。

---

## 二、已实现审计（用户要求"已经实现的不要重复实现"）

五层核对：①全仓搜 akshare 真源函数名 ②`DataProviderManager` 55 个方法逐一比对
③DB 表名扫描 ④全部路由扫描 ⑤兄弟源（`*_source.py`）排查。

| # | 需求 | 已有？ | 处置 |
|---|---|---|---|
| 1 | 内部人交易 | ✅ `providers/market/akshare.py:448` + `manager.py:950` | **不新增代码**，仅把 mock 路由改指向已有方法 |
| 2 | 十大股东 | ❌ | 新增 provider 方法 |
| 3 | 股东户数变化 | ❌ | 新增 provider 方法 |
| 4 | 基金持股 | ❌ | 新增 provider 方法 |
| 5 | 基金重仓股 | ❌ | 新增 provider 方法 |
| 6 | 千股千评 | ❌ | 新增 provider 方法 |
| 7 | 市场情绪 | ✅ `quant.market_sentiment_daily` 已有真实数据 | **不建取数链**，只读表 |

**另核**：同文件 `/fund-flow` / `/margin` / `/lhb` 已是真实实现
（`FundFlowDataSource` / `MarginDataSource` / `lhb_service`），不在范围。

→ 7 项里只有 5 项需新增实现。

---

## 三、架构：走 provider 多源框架（不直连 akshare）

v1 计划曾写「`SentimentDataSource` 直连 akshare」——**单源且绕过框架**，已废弃。依据：

| 能力 | 证据（`manager.py`） |
|---|---|
| 故障转移：跳过未实现该方法的源 | L339 `if not hasattr(provider, method_name): continue` |
| 熔断 / 健康排序 | L333 `_is_circuit_broken` / L326 `_sort_providers_by_health` |
| 诚实标记 | `source / attempted_sources / empty_sources / provider_errors / empty` |
| 「空结果≠故障」契约 | L318 |

market 域现有 3 源（`akshare` 12 方法 / `sina` 3 / `ths` 4）。

**多源现状（诚实声明）**：#2–#6 当前**只有 akshare 一个真源**（底层封装东财）→
今天 `attempted_sources` 只会是 `["akshare"]`，是**「框架就绪的单源」，不是多源故障转移**；
加第二源（东财直连，本仓已有 `providers/quote/eastmoney.py` 等可照抄）即自动参与。

---

## 四、实现

### 新增 5 个 provider 方法（`providers/market/akshare.py`）+ manager 转发

| 方法 | 真源 | 实测 |
|---|---|---|
| `get_top_holders(symbol, holder_type)` | `stock_gdfx_top_10_em` / `stock_gdfx_free_top_10_em` | ✅ 10 条（茅台集团 54.5%），report_date 2026-06-30 |
| `get_holder_changes(symbol, periods)` | `stock_zh_a_gdhs_detail_em` | ✅ 股东户数 296404（**最新在前**） |
| `get_fund_holdings(symbol, quarter)` | `stock_fund_stock_holder` | ✅ 992 只基金 |
| `get_top_fund_stocks(fund_type, limit)` | `stock_report_fund_hold` | ⚠️ **上游损坏 → 诚实失败**（见 §五） |
| `get_stock_comment(symbol)` | `stock_comment_em` | ✅ 机构参与度 0.4675 / 综合得分 75.2 |

### 关键设计点

1. **健康空 vs 硬失败严格区分**：akshare 在「报告期无数据」时抛**解析异常**
   （实测 `ValueError: Length mismatch`），与网络故障是两类 →
   `_is_transport_error()` 分流：数据缺失→空 records（`empty:true`）；传输故障→`None`（进熔断）。
   把「无数据」当故障会误伤健康源；把「网络挂」当无数据就是**假成功**。
2. **JSON 安全**：`_df_records()` 把日期列 stringify —— `datetime.date` 不是 JSON 可序列化类型，
   直接塞进响应会让路由在编码阶段 500（`get_index_daily` 早已在其内部做过同一件事）。
3. **TTL 缓存**：`stock_inner_trade_xq`(2.5 万行)/`stock_comment_em`(5196 行)/
   `stock_report_fund_hold`(5225 行) 都是**全市场**接口、单股调用只是本地过滤 →
   5/10/30 分钟 TTL，避免每请求打上游；失败/空**不写入缓存**。
4. **复用而非重写**：前缀规则用已有的 `market_prefixed()`（全仓唯一实现），本处只做大小写转换。
5. **端点统一诚实标记**：`provider_payload()` 让每个响应都带
   `source / attemptedSources / emptySources / empty / degraded`；
   provider 失败时返回 **502**（不再 `success:true` 掩盖）。
6. **健康空自描述**：源正常但该标的无数据 → 补 `empty:true`
   （manager 在 success 分支不会置位，只给 `total:0` 会让调用方误判为"字段没返回"）。

### 契约变更（零消费者，已文档化）

- 记录键由伪造英文名（`holderName`/`shares`）改为**数据源原生列**（中文列名）；
- `/api/sentiment/market`：由「按个股情绪分类计数」改为**真实市场级指标**
  （涨跌家数/涨跌家数比/新高新低/量能比/总成交额/波动率/恐贪指数），旧键保留并标 `deprecated`；
- `/api/sentiment/stock/{symbol}`：返回**千股千评指标**，**不冒充「情绪分类」**。

---

## 五、上游缺陷：基金重仓股**拒绝返回**（诚实失败）

`ak.stock_report_fund_hold` 返回的表**列名与值错位**：

```
列名:      序号 | 股票代码 | 股票简称 | 持有基金家数 | 持股总数 | 持股变动比例
实际值:    56   | -42049165018.7 | '600519' | '01'      | 1697     | -20784953
```

已试三种替代，均不可用：
1. 换报告期：`20241231` / `20250331` / `20260630` **全部错位**；
2. `fund_report_stock_cninfo`（巨潮）→ `KeyError: 'records'`（接口已变）；
3. `fund_portfolio_hold_em` → 按基金查，无法产出「重仓股排行」。

**处置**：provider 侧加**完整性校验** —— 检测「股票代码」列不是 6 位代码即判上游损坏 →
记 `logger.error` 并返回 `None`。端点因此**诚实返回 502**（`provider_errors` 注明
"数据校验未通过（非空但无效）"），**绝不把错位表当数据**；上游修复后自动恢复。

> 这是本次改造最该守住的一条：把"假数据"的来源从本仓替换成上游，同样是假数据。

---

## 六、验证

| 项 | 结果 |
|---|---|
| 新增测试 `tests/test_sentiment_real_data.py` | **27 passed**（上游错位拒收 / 健康空 vs 硬失败 / TTL 缓存命中 / 7 端点契约 / 502 降级 / 防 mock 源码护栏） |
| 漂移门禁 `test_orm_db_drift.py` | 6 passed（悬空基线收敛 1 条） |
| 回归 | 343 passed（3 failed 均在 main 上同样失败 → **既有**，见下） |
| 线上 7 端点 | top-holders/holder-changes/fund-holdings/insider-trades/market/stock 均 200 真实数据；top-fund-stocks **502 诚实失败** |
| **两次调用一致性** | 4 个端点在改造前后做对比：改造后**完全一致**（改造前随机） |
| 边界用例 | 无效标的 → 200 + `holders:[]` + `empty:true` + `source`；不存在的季度 → 空 + `empty:true` |

**既有失败**（与本次无关，main 上同样失败）：
`tests/integration/test_provider_failover.py::TestCircuitBreaker` 3 例（熔断状态跨测试泄漏）、
`test_simulation_account_repository::test_get_balance`、`test_trade_cash_race`。

---

## 七、遗留

1. **`/api/sentiment/top-fund-stocks` 目前不可用**（上游错位）—— 需要产品决策：
   等上游修复 / 换成"按指数成分股聚合 `stock_fund_stock_holder`"（语义变成子集，且需定时任务+新表）。
2. `public.audit_log`、`quant.async_factors` 两个悬空模型仍在门禁豁免名单（各自需产品决策）。
3. 兄弟源 `fund_flow_source` / `margin_data_source` 仍是顶层单上游包装，**未迁入框架**（不在本需求范围）。
4. 门禁以**测试库**为口径，"测试库有、生产没有"的形态看不见（已知盲区，已登记在测试文件注释）。

---

## 八、t9：东财直连第二源（同日追加）

### 8.1 为什么加（第二个理由比"多一个源"更重要）

1. **多源故障转移**：这些数据此前只有 akshare 一个源，第三方包失效即无兜底；
2. **修上游解析缺陷**：akshare 对这几个接口用**位置式列名**——把 N 个名字按顺序硬套到
   东财返回的数组上，东财字段一变就整体错位。实测 `stock_report_fund_hold`：

   | 列名 | akshare 给的值 | 东财真实字段 |
   |---|---|---|
   | 股票简称 | `'300308'`（其实是代码） | SECURITY_CODE |
   | 持有基金家数 | `'01'`（其实是机构类型） | ORG_TYPE |
   | 持股总数 | `3578`（其实是家数） | HOULD_NUM |
   | 股票代码 | `141398625194.02`（其实是持股市值） | — |

   直连按**字段名**取值，从结构上不可能发生错位 → **修好了此前被我判为"上游不可用"的
   `/api/sentiment/top-fund-stocks`**。

### 8.2 实现

| 方法 | 东财接口 | 实测 |
|---|---|---|
| `get_top_holders` | `RPT_F10_EH_HOLDERS` / `RPT_F10_EH_FREEHOLDERS` | ✅ 茅台集团 54.5%（取最新报告期+按名次排序） |
| `get_holder_changes` | `RPT_HOLDERNUM_DET` | ✅ 296404（与 akshare 一致） |
| `get_top_fund_stocks` | `dataapi/zlsj/list` | ✅ **中际旭创 300308 / 3578 只基金 / 2727 亿**（语义正确） |
| `get_stock_comment` | `RPT_DMSK_TS_STOCKNEW` | ✅ 机构参与度 0.4675 / 综合得分 75.2 |

**不覆盖 `get_fund_holdings`**：东财 `RPT_MAINDATA_MAIN_POSITIONDETAILS` 混装银行/保险/券商
所有机构类型，且 `ORG_TYPE_NAME` 实测为 None，无法可靠筛出"基金"——硬筛会改契约语义；
而 akshare 那条走的是**新浪**（`vip.stock.finance.sina.com.cn`），上游本就独立，无兜底缺口。

### 8.3 两个设计决定

1. **抽 `providers/market/_common.py`**：缓存/前缀/报告期/JSON 安全/失败判定两源**共用一份**。
   若各写一份，两个源会演化出不同口径 —— 本仓"平行实现"已出过多次事故。
2. **刻意不继承 `MarketProvider`**：那个 ABC 强制 `get_market_overview`/`get_lhb_stock`/`get_lhb_daily`。
   为满足 ABC 写"返回 None"的空实现，会让每次行情/龙虎榜查询都调用它并记一次失败 → 污染健康分。
   改继承 `BaseDataProvider[MarketData]`，`_try_providers` 的 `hasattr` 会正确跳过本源。
3. **注册在末位**：正常时 akshare 先服务（行为不变），仅在其失败/拒绝返回时兜底。

### 8.4 顺带修的分类缺陷

框架只在 provider **自报 `last_error`** 时才判「真故障」（`manager.py:396`）；
否则 `None` 会被归为「非空但无效」，**错误原因丢失**。我上一轮的完整性拒收没设 `last_error`，
线上因此显示成 `"数据校验未通过（非空但无效，不计入健康分）"` —— 分类错误。
本次给 akshare 源补齐 `last_error` 纪律（14 处，含每次调用开头重置，避免上次失败串到本次）。

### 8.5 验证

```
实测 failover（akshare 因错位拒收 → eastmoney 兜底）:
  get_top_fund_stocks  success=True  source=eastmoney  attempted=['akshare','eastmoney']
  首条 {"股票代码":"300308","股票简称":"中际旭创","持有基金家数":3578,...}

线上（重启后）:
  GET /api/sentiment/top-fund-stocks → 200  ← 修复前是 502
  {"fundType":"基金持仓","reportDate":"2026-06-30","stocks":[{"序号":1,"股票代码":"300308",
   "股票简称":"中际旭创","持有基金家数":3578,"持股总数":214732617,"持股市值":272710423590}]}
  其余 7 个端点均 200；两次调用一致；source/attemptedSources/empty/degraded 标记在位

测试:
  tests/test_eastmoney_market_provider.py  10 passed（字段映射语义/最新报告期/last_error 必设/
    异常绝不出抛/健康空/拔掉 akshare 自动切换/错位场景兜底为正确数据）
  回归 355 passed（3 failed 在 main 上同样失败 → 既有）
```

### 8.6 遗留（t9 完成后）

1. `get_fund_holdings` 仍是 akshare 单源（但那是新浪上游，与东财不同通道）；
2. 多源现状更正为：#2–#6 中 **4 个方法有 2 个源**（akshare + eastmoney），
   `get_fund_holdings` 1 个源。**不再有"单源无兜底"的数据类型**（除该条）。
3. `public.audit_log`、`quant.async_factors` 两个悬空模型仍在门禁豁免名单（需产品决策）。

---

## 九、独立审查与整改（2026-09-14 深夜）

**触发**：用户追问"验收前是否 review 和测试了"。诚实回答：测试做了、**独立审查没做** ——
我提交 reqboard_verify_submit 时手里只有自审，而本仓此前（ORM 改造）正是用独立 subagent 审出
5 个真问题的。作为补救，先自己做了对抗性检查，再启动独立只读审查。

### 9.1 自查（对抗性检查）查出 3 个真 bug

「6 类畸形上游响应 × 4 方法」打下来，问题全在**我自己的新代码**：

| # | Bug | 危害 |
|---|---|---|
| 1 | **全 None 记录冒充数据** —— 东财源是显式字段映射，上游改名后产出「结构在、值全 None」的记录并报 total=10 | 调用方看到 10 条、每格 None，而上游其实已换字段 —— 正是本需求要消灭的"用空值冒充数据"，且静默掩盖 schema 漂移 |
| 2 | **schema 漂移被归为"健康空"**（第一版修复） | empty 在框架里=「该源确实没数据」，不记故障 → 字段改名后该源永远安静返回空 |
| 3 | **本地合成字段掩盖漂移** —— top_fund_stocks 的「序号」由我生成、恒非 None，让"全 None"判定永远为假 | 实测漏判：改名后仍报 total=1 |

修法：区分「真的没有行 → 健康空」与「有行却映射不出 → 真故障」；合成字段不计入内容判定。
（另有：未使用的 import、我引入后未使用的辅助函数、漂移日志用了过滤后行数 —— 一并清掉。）

### 9.2 独立审查（subagent，只读）的核心发现

审查者在 **HEAD=e1d142fe** 上核验，全程只读（探针写在 /tmp）。结论 **2 严重 + 5 中 + 8 低**。
**H1 是真的、而且是我这轮最该发现却没发现的**：

> **H1：akshare 的「健康空」吞掉解析/字段漂移失败，并短路掉新加的东财兜底源。**
> akshare 对「报告期无数据」与「接口改名/结构变更」**都抛解析异常**，旧实现一律 continue，
> 四期全败后返回 `empty:True` 且 `last_error=None` → manager 走成功分支 →
> **东财兜底源根本不被尝试**。而接口改名正是这个形态 → 该源会永远安静返回空。
> 更要命的是：**我自己的测试把这个错误行为锁成了期望值**
> （`test_top_holders_all_periods_missing_is_healthy_empty`）。

其余：H2（`?date=X` 静默回退到最近一天）、M1（insider 的 last_error 串味）、
M2（/sentiment/stock 忽略顶层 empty）、M3（两源键集不等价而 docstring 声称相同）、
M4（`degraded` 是死字段）、M5（状态码不一致）、L1–L8。

审查同时**独立核实**了我"仓内零消费者"的声称：**字段级成立**（无任何代码解析旧伪造英文键、
无 bullish/bearish/neutral/total 读取方），但**我发现 agent-ts 的端点注册表仍可经通用派发
调用这些端点** → 我原先"端点不可达"的说法不准确，已在验收材料中更正。

### 9.3 逐条整改

| 编号 | 整改 |
|---|---|
| H1 | 报告期循环改**锁存**：任一期报过非网络异常 → 最终无数据即按故障上报（触发 failover、原因可见）；只有四期"干净地空"才算健康空。同步把锁错行为的测试拆成「失败」与「干净空」两条 |
| H2 | 显式请求的日期取不到 → 返回 requestedDate + requestedDateMissing + empty + degraded，**不回退** |
| M1 | insider_trades 补 last_error（重置 + 三条失败路径，含"代码列改名"） |
| M2 | /sentiment/stock 统一走 provider_payload（认顶层 empty），并补 null 键保持契约稳定 |
| M3 | akshare 侧 docstring 写明多出「股份类型」及与东财的差异；**manager 成功分支补 provider_errors**（原只在全失败分支返回 → 线上实测恒空） |
| M4 | `degraded` = 有源失败/空过（或 attempted>1）。**线上实测已由恒 false 变为 true** |
| M5 | /sentiment/stock 失败改 502（与其余 6 个端点一致） |
| L1 | TTL 改为**前缀匹配**（`fund_hold:<type>:<period>` 此前永不命中 1800s 配置） |
| L2 | stock_comment 两条失败路径补 last_error |
| L3 | **更正我写错的技术论断**：声称"_try_providers 只捕获超时、其它异常会穿透"是错的 —— manager.py:411 有兜底 except Exception。不外抛的收益是**保原因**，不是防崩溃 |
| L4 | provider_payload 透出 fetched_at（注释说明其为取数时间、上限=TTL） |
| L5 | /market 无数据与 partial（coverage 不足）标 degraded |
| L6 | 未知 fund_type 显式失败（原静默降级为基金持仓）；注明「all」本源等价「基金持仓」 |
| L7 | /market 由 async def 改普通 def（FastAPI 放 threadpool，不阻塞事件循环） |
| L8 | insider 的 days 过滤改为解析成 date 再比；**解析不出的行保留**并单列 undated_records |

**测试质量**（审查点名"改了实现仍全绿"）：补了 H2、M2 的用例，另加 H1 端到端 failover、
M1 串味、M5 502、L1 前缀 TTL、L6 未知类型、L8 日期、M3 键差异/provider_errors 透出。

### 9.4 我自己引入并修掉的测试污染（值得单记）

新用例曾**直接赋值 `em.requests.get`**（未用 monkeypatch、无还原）→ 污染全局
→ 组合运行时把 3 个 `tests/migration` parity 用例带崩，**而隔离跑却全绿**。
这正是"隔离绿、组合红"的经典形态。已改回 monkeypatch，并加正则自查确认无残留。

### 9.5 整改验证：与基线**同命令对照**

```
同一条组合命令（我的 5 个套件 + tests/migration）:
  worktree(含改动)  15 failed / 650 passed
  main(基线)        15 failed / 641 passed     ← 失败集完全相同，零新增失败
  （差 9 例 = 我新增的测试）

目标套件: test_eastmoney_market_provider 23 + test_sentiment_real_data 28
          + test_orm_db_drift 6 = 57 passed
tests/migration 单独跑: worktree 与 main 同为 12 failed（既有）

线上（重启后）:
  /api/sentiment/top-fund-stocks → providerErrors={'akshare': "上游 基金持仓 列错位
    （股票代码 列非 6 位代码，样例 [141398625194.02, ...]）"}  ← M3 修复前恒为空
    degraded:true / attemptedSources:['akshare','eastmoney']    ← M4 修复前恒 false
  /api/sentiment/market?date=2020-01-01 → requestedDate=2020-01-01,
    requestedDateMissing:true, empty:true, degraded:true        ← H2 修复前会回退到 09-12
  7 个端点全部 200
```

### 9.6 审查未能覆盖的（诚实转述）

审查者明确列出**没能验证**的部分：未实测 akshare `stock_gdfx_free_top_10_em` 的键集；
未做并发/压测（L7 阻塞事件循环的实际影响、冷缓存时全市场接口 2.5 万行/5196 行在请求路径上的
延迟与内存）；未查生产库 `market_sentiment_daily` 的真实数据分布（partial/volatility 是否 NaN）；
无法验证上游长期行为（限流/字段改名）与线上真实响应。**这些仍是未知，未因为我改了就消失。**
