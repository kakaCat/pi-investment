# RFC 015: 三项数据能力补强的 DDD 方案（产业链图谱 / 政策·事件源 / 分钟线·交易状态）

- **状态**: 提案（待评审）
- **作者**: investor / w-f436d4ea
- **日期**: 2026-09-11
- **关联**: REQ-cf627b（决策基础设施补强）；ADR-001（六边形架构）
- **范围**: quantsys-v2 后端 + agent-dh 工具暴露层

---

## 0. 为什么要做（问题来自实盘，不是设想）

| 缺口 | 实证场景（2026-09-11 本窗口） |
|---|---|
| 无产业链图谱 | 扫玻纤链时**手工硬编码**上游/中游/下游成员（玻纤→电子布→CCL→PCB）；次试 `mainline_stocks(sector="玻璃行业")` 直接报 Sector not found——链式扫描（决策原则#4）实际不可执行 |
| 无政策/个股事件源 | 农业崩盘归因**100% 依赖 web_search 外部新闻**（六部门文件、秋粮丰产、小麦托市）；`event_calendar` 未来 14 天仅 4 条纯宏观事件，无政策文件、无个股财报/解禁/定增 |
| 无分钟线/交易状态 | 下单无分钟级择时、无停牌/ST/涨跌停判断、无滑点预估；`data_fetch_dividend` 类工具曾因缺状态校验产出假结论 |

**架构约束**：必须遵循 ADR-001 六边形架构（domain/ports + models → application/services → adapters/inbound|outbound → infrastructure），依赖方向 Adapters → Domain（DIP）。应用层**禁止**直接 import 适配器实现（历史审计 157 处违规）。

## 0.1 复用现状（重要：三项缺口的基础设施已存在大半）

| 已存在 | 位置 | 结论 |
|---|---|---|
| `quant.minute_klines` 表 + `MinuteKline` ORM | `infrastructure/persistence/orm/models/kline.py`（含 trade_datetime 与 (symbol,trade_datetime) 索引） | ③ **无需新建存储**，缺的是端口/服务/路由/工具 |
| `stocks.is_st` / `stocks.is_suspended` 列 + 索引 | `orm/models/stock.py` | ③ 交易状态**存储已就绪** |
| `quant.event_calendar`（67 条宏观事件）+ `/api/events` 路由 | 既有 | ② **扩展**而非重建，新增 scope=individual/policy |
| `domain/models/` 仅 `market_data.py` | — | 三个特性均需新增领域模型模块 |
| `adapters/outbound/datasources/providers/` 多源+熔断+动态优先级 | `manager.py` | 新数据源**接入同一故障转移框架**，不另起链路 |

---

## 1. 统一分层映射（三项共用）

```
adapters/inbound/fastapi_app/routes/*.py      ← 入站适配器（HTTP → 用例）
            ↓ 调用（仅依赖端口类型）
application/services/*_service.py             ← 应用层（编排用例，禁止 import 适配器）
            ↓ 依赖抽象
domain/models/*.py   +   domain/ports/*.py    ← 领域层（模型/VO + 端口 ABC）
            ↑ 实现接口（依赖倒置）
adapters/outbound/datasources/providers/*     ← 出站适配器（外部数据源，逐 provider 实现）
adapters/outbound/repositories/*              ← 出站适配器（ORM 持久化）
            ↓
infrastructure/persistence/orm + migrations   ← 基础设施（表/迁移/调度）

agent-dh/packages/*/src/tools/*               ← 消费侧（DSH 工具，经 quantsys-v2-client 调 /api）
```

**领域层组织方式（实测现状，务必对齐）**：`domain/` 按**限界上下文分子目录**组织——`domain/trading/`、`domain/scoring/`、`domain/portfolio/`、`domain/chip_distribution/` 各自带 `service.py` 或 `services/`；**不存在**扁平的 `domain/services/`。共享模型放 `domain/models/`，共享端口放 `domain/ports/`。
→ 本方案三项分别落到：`domain/industry_chain/`（新限界上下文）、`domain/events/`（新限界上下文）、`domain/trading/`（**已存在**，复用）。

**纪律**：
1. 领域层零外部依赖（仅 `abc` + `typing` + 标准库）
2. 应用层构造函数**局部导入**具体实现（DI），类型注解一律用端口 ABC
3. 每个 provider 必须实现 `name` 属性并注册进 `manager` 的对应 provider 列表（复用熔断/动态优先级/stale-while-error）
4. 数据源失败与空结果**语义分离**：失败 fail-loud，禁止静默返回空（2026-09-11 教训：分红 provider 读错列名致全 0 被误读为"不分红"）

---

## 1.5 多数据源设计（三项**强制**，非可选）

### 1.5.1 为什么强制——今日实证的三种"假多源"

| 反模式 | 实证（2026-09-11） | 后果 |
|---|---|---|
| **框架有、只挂一个源** | `dividend_providers = [akshare]`（`_try_providers` 熔断/动态优先级齐备，但无可故障转移对象） | 单点故障即全链路失败；`/api/dividends/screen` 报 "All data providers failed" |
| **源接上了、字段映射错** | akshare 分红 provider 读 `每股派息/股息率/除权除息日`，而该接口真实列是 `派息比例/除权日/股权登记日` | **静默全 0**，被误读为"该公司不分红"（比报错危险） |
| **源之间口径不一致** | `fund_flow` DB 缓存经 sina 落库时 large/big 档为 null，东财 clist 路径四档齐全 | 因子出现"部分档位恒 0"，跨源拼出的数据不自洽 |

**结论**：多数据源不是"注册两个类"，而是三条硬约束同时满足。

### 1.5.2 硬约束（每项特性都必须过）

1. **≥2 个独立通道**：同一数据类型的 provider 必须来自**不同上游通道**（例：腾讯 / 东财 / 新浪 / akshare / 本地 DB 各算一个通道）。禁止把同一个上游 API 包两个类充数。
2. **复用既有故障转移框架**：provider 注册进 `adapters/outbound/datasources/manager.py` 的对应列表，自动获得 `_try_providers`（独立超时 + 熔断 + 动态降权 + attempted_sources 透传），**不得另起并行链路**。
3. **契约先验证再注册**：每个新 provider 的字段映射必须先用**真实响应**打样核对（今日教训：mock 与理想 payload 会让错映射通过测试）；未验证的 provider 不得进注册表。
4. **本地 DB 兜底作为最后一级**：所有三项都必须有一条 "DatabaseXxxProvider"（读本地表），保证上游全挂时链路不中断且**显式标记 stale**（stale-while-error）。
5. **失败与空结果语义分离**：全部源失败 → **显式失败**；某源返回空 → 继续下一源；**禁止**用空结果/0 值冒充成功。
6. **跨源一致性校验**：当 ≥2 源同时返回时做比对，超阈值分歧 → 标注 `cross_source_conflict` + 取**保守值** + 记入体检探针（例：交易状态冲突时以"不可交易"为准）。

### 1.5.3 响应契约（三项统一）

```json
{ "success": true, "data": {...},
  "source": "tencent",                    // 实际服务源
  "attempted_sources": ["tencent","eastmoney"],
  "degraded": false, "stale": false,
  "cross_source_conflict": null,          // 非 null 时含分歧细节
  "as_of": "2026-09-11T14:05:00+08:00"    // 数据时点（R-013 标注要求）
}
```

---

## 2. ① 产业链图谱（Industry Chain Graph）

### 2.1 领域层

`domain/industry_chain/model.py`（新建限界上下文，对齐 `domain/chip_distribution/` 的组织方式）
```python
class ChainStage(str, Enum):        # 值对象
    UPSTREAM = 'upstream'; MIDSTREAM = 'midstream'; DOWNSTREAM = 'downstream'; TERMINAL = 'terminal'

@dataclass(frozen=True)
class RevenueExposure:              # 值对象：主营占比（0-1）+ 口径来源
    ratio: float; basis: str; as_of: str

@dataclass
class ChainMember:                  # 实体
    symbol: str; name: str; stage: ChainStage
    exposure: Optional[RevenueExposure]
    role: str                       # 龙头/二线/弹性标的
    evidence: str                   # 证据（主营构成/公告/研报），可追溯

@dataclass
class ChainNode:                    # 实体：环节
    node_id: str; name: str; stage: ChainStage
    upstream_of: List[str]; downstream_of: List[str]   # 有向关系

@dataclass
class IndustryChain:                # 聚合根
    chain_id: str; name: str; nodes: List[ChainNode]; members: List[ChainMember]
    def members_at(self, stage: ChainStage) -> List[ChainMember]: ...
    def symbol_stages(self, symbol: str) -> List[ChainStage]: ...
```

`domain/ports/datasource_ports.py` 新增
```python
class IIndustryChainProvider(ABC):
    @property @abstractmethod
    def name(self) -> str: ...
    @abstractmethod
    def list_chains(self) -> Optional[List[Dict]]: ...          # 全部产业链清单
    @abstractmethod
    def get_chain(self, chain_id_or_name: str) -> Optional[List[Dict]]: ...   # 环节+成员原始行
    @abstractmethod
    def get_revenue_exposure(self, symbol: str) -> Optional[List[Dict]]: ...  # 主营构成（占比口径）
```

`domain/ports/repository_ports_extended.py` 新增 `IIndustryChainRepository`
（`list_chains` / `get_chain` / `get_chain_by_symbol` / `upsert_chain` / `search_nodes`）

### 2.2 应用层 · `application/services/industry_chain_service.py`

| 用例 | 说明 |
|---|---|
| `build_chain(chain_id)` | 编排：provider 拉取原始行 → 领域规则（环节归位/去重/主营占比阈值）→ repository 落库 |
| `list_chains()` | 产业链清单（带成员数与最近刷新时间） |
| `get_chain(name)` | 单链全貌（按环节分组） |
| `map_symbol(symbol)` | **个股→所属链/环节/主营占比**（链式扫描的关键查询） |
| `chain_scan(name)` | **链式扫描**：按环节分组 + 挂实时行情/资金流（复用既有 quote/fund_flow 端口） |

### 2.3 出站适配器（多源矩阵，按 1.5 硬约束）

| 优先级 | Provider | 通道 | 提供字段 | 失败降级 |
|---|---|---|---|---|
| 0（权威） | `CuratedChainProvider` | 人工策展 seed（`domain/industry_chain/seed/*.yaml`） | 环节拓扑（node 与上下游关系） | 不可降级：拓扑唯一来源，缺失即 fail-loud |
| 1 | `EastmoneyRevenueProvider` | 东财 F10 主营构成 | 成员**归位证据**（产品/行业占营收比） | → akshare 同义接口 |
| 2 | `AkshareRevenueProvider` | akshare `stock_zygc_em` | 同上（同数据不同通道） | → 概念成分 |
| 3 | `AkshareConceptProvider` | akshare 概念/行业成分 | 候选成员（低置信） | → 本地 DB |
| 4 | `DatabaseChainProvider` | `quant.industry_chain_member` | 上次成功图谱 | stale-while-error |

**交叉校验**：主营构成（优先级 1/2）与概念成分（3）对同一标的归位冲突时 → **以主营构成为准**，并把冲突写入 `evidence_conflict` 供人工复核（不静默取其一）。

数据源现实（诚实评估）：
- **无现成"产业链"接口**。可组合：东财行业/概念成分（链的粗粒度）+ **主营构成**（akshare `stock_zygc_em`，提供"XX产品占营收 N%"——这是把标的归位到环节的**唯一硬证据**）
- 因此 `chain_nodes`（环节拓扑）**必须人工策展**（初始 5-8 条主线：玻纤/电子布/PCB、造船、电力、锂电、光伏、半导体），成员映射自动化
- 置信度分级：`evidence='主营构成'` > `'行业分类'` > `'概念成分'`，写入 repository 供 UI/工具标注

### 2.4 入站适配器 · `routes/industry_chain_async.py`
`GET /api/industry-chains` ｜ `GET /api/industry-chains/{name}` ｜ `GET /api/stocks/{symbol}/chain` ｜ `POST /api/industry-chains/{name}/scan`

### 2.5 基础设施
迁移 `015_industry_chain.sql`：`quant.industry_chain` / `industry_chain_node`（含 upstream_of/downstream_of）/ `industry_chain_member`（symbol, node_id, stage, exposure_ratio, evidence, as_of），唯一键 (chain_id, symbol, node_id)。
调度：`industry_chain_refresh`（周更，周日 20:00，参照 finance 周更任务注册进 `scheduler_tasks`）。

### 2.6 工具暴露（agent-dh）
新增 `industry_chain` 插件工具 3 个：`chain_list` / `chain_scan`（替代手工链式扫描）/ `symbol_chain`；
**强化** `mainline_stocks`：sector 名解析失败时报"可用 sector 清单"而非裸错（今日 `Sector not found` 的直接修复）。

---

## 3. ② 政策 · 个股事件源（Policy & Corporate Event Feed）

### 3.1 领域层 · `domain/events/model.py`（新建限界上下文）+ `domain/events/service.py`（事件归并/去重/影响判定）
```python
class EventScope(str, Enum):   MACRO='macro'; INDUSTRY='industry'; INDIVIDUAL='individual'
class EventType(str, Enum):    POLICY='policy'; EARNINGS='earnings'; UNLOCK='unlock'
                               PLACEMENT='placement'; SHAREHOLDER_MEETING='shareholder_meeting'
                               REGULATORY='regulatory'; DIVIDEND='dividend'
@dataclass
class MarketEvent:            # 聚合根
    event_id: str; scope: EventScope; type: EventType; title: str
    effective_date: str; announce_date: str; importance: int      # 1-3
    symbols: List[str]; industries: List[str]
    source: str; url: str; summary: str; raw: Dict
    def affects(self, symbol: str) -> bool: ...
```

端口：`IMarketEventProvider`（`fetch_policy` / `fetch_symbol_events`）、`IMarketEventRepository`（`upsert` / `list` / `for_symbol` / `upcoming`）。

### 3.2 应用层 · `application/services/event_feed_service.py`
`ingest_policy()` / `ingest_symbol_events(symbols)` / `list_events(scope,type,range)` / `events_for_symbol(symbol)` / `upcoming(days)` / **`link_to_watchlist()`（事件→盯盘规则联动：解禁/财报自动挂规则）**

### 3.3 出站适配器（多源矩阵，按 1.5 硬约束）

**个股事件**（全自动化，≥3 独立通道）

| 优先级 | Provider | 通道 | 覆盖类型 |
|---|---|---|---|
| 1 | `EastmoneyNoticeProvider` | 东财大事提醒 | 财报/解禁/定增/股东会/减持 |
| 2 | `CninfoDisclosureProvider` | 巨潮公告（法定披露） | 全部公告类型（权威） |
| 3 | `AkshareUnlockProvider` | akshare 解禁排队 | 解禁（结构化） |
| 4 | `DatabaseEventProvider` | `quant.event_calendar` | 上次成功入库（stale 标注） |

**交叉校验**：同一 (symbol, 日期, 类型) 多源并存 → 按 `evidence_hash` 幂等去重，保留**权威度最高**源（巨潮 > 东财），差异记入 `source_divergence`。

**政策事件**（半自动，≥2 通道 + 人工兜底）

| 优先级 | Provider | 通道 |
|---|---|---|
| 1 | `GovPolicyProvider` | 国务院/发改委发布页 |
| 2 | `CsrcPolicyProvider` | 证监会/交易所发布页 |
| 3 | `ManualPolicySeed` | **人工策展兜底**（抓取失败时的最低保障，带 operator 标记） |

**硬要求**：政策源无稳定免费 API（已有东财 WAF 前例），抓取失败**必须显式失败或落到人工 seed**，禁止静默空——否则"没有政策事件"与"没抓到"无法区分。

### 3.4 入站适配器
扩展现有 `/api/events`：新增 `GET /api/events/feed`（按 scope/type/date 过滤）、`GET /api/events/symbol/{symbol}`、`GET /api/events/upcoming?days=N`。

### 3.5 基础设施
扩展现有 `quant.event_calendar`：加列 `scope` / `symbols text[]` / `source_url` / `evidence_hash`（幂等去重）；
新增 `ingest_events_daily`（每日 17:00）+ `ingest_events_policy`（每 4 小时）。

### 3.6 工具暴露
`event_calendar_check` 扩展 `scope`/`type` 参数；新增 `stock_events`（个股事件排雷，替代现在只能靠 stock_intel 公告）。

---

## 4. ③ 分钟线 · 交易状态（Minute Klines & Trading Status）

### 4.1 领域层 · 扩展 `domain/models/market_data.py`（共享模型）+ `domain/trading/service.py`（**复用已存在的 trading 限界上下文**）
```python
@dataclass
class MinuteKline:      symbol: str; trade_datetime: datetime; period: str  # 1/5/15/30/60min
                        open: float; high: float; low: float; close: float; volume: int; amount: float

@dataclass(frozen=True)
class TradingStatus:    # 值对象：下单前硬约束
    symbol: str; is_st: bool; is_suspended: bool; limit_up: bool; limit_down: bool
    tradeable: bool; reason: str; as_of: str
```

端口：`IMinuteKlineProvider`（`get_minute_klines`）、`IMinuteKlineRepository`（`save` / `get_range` / `latest`）、`ITradingStatusRepository`（复用 stocks 表）。
**关键**：`TradingStatus` 由**领域服务**计算（`domain/trading/service.py` 的 `TradingStatusPolicy`：ST 判定 + 停牌 + 涨跌停价 = 昨收×(1±涨跌幅限制)，主板 10%/创业板科创 20%/ST 5%），不散落在应用层；应用层只做编排。

### 4.2 应用层 · `application/services/microstructure_service.py`
`get_minute_klines(symbol, period, date)` / `get_trading_status(symbol)` / **`estimate_execution(order)`（滑点/冲击成本预估：用分钟线量能 + 当前买卖价差，供 R-003 拆单决策）** / `intraday_context(symbol)`（分时位置：相对当日均价/高低点）

### 4.3 出站适配器（多源矩阵，按 1.5 硬约束）

**分钟线**（≥4 独立通道 + 本地兜底）

| 优先级 | Provider | 通道 | 备注 |
|---|---|---|---|
| 1 | `TencentMinuteProvider` | 腾讯 ifzq.gtimg.cn | 稳定、延迟低，网络首选 |
| 2 | `EastmoneyMinuteProvider` | 东财 push2his | 需经系统代理（本机直连被封） |
| 3 | `SinaMinuteProvider` | 新浪 | 备选通道 |
| 4 | `AkshareMinuteProvider` | akshare `stock_zh_a_hist_min_em` | 慢，末位网络通道 |
| 5 | `DatabaseMinuteKlineProvider` | `quant.minute_klines` | 断网/收盘后兜底，标 `stale` |

**交易状态**（**双通道 + 保守裁决**，这条最关乎资金安全）

| 优先级 | Provider | 通道 | 判定内容 |
|---|---|---|---|
| 1 | `StockTableStatusProvider` | `stocks.is_st` / `is_suspended` | 基础状态（权威静态） |
| 2 | `QuoteDerivedStatusProvider` | 实时行情（腾讯→新浪→东财） | 动态：成交量为 0 → 疑似停牌；现价触及 ±限幅 → 涨/跌停 |

**保守裁决规则**：两通道结论不一致时（如表说可交易、行情显示成交为 0）→ **按"不可交易"处理** + 抛 `cross_source_conflict` + 在 `portfolio_trade` 前置校验中 fail-closed。宁可错杀一次委托，不可在停牌票上误下单。

### 4.4 入站适配器
`GET /api/stocks/{symbol}/minute-klines?period=5&date=YYYY-MM-DD` ｜ `GET /api/stocks/{symbol}/trading-status` ｜ `POST /api/execution/estimate`

### 4.5 基础设施
**无需新表**（`minute_klines` 已存在）；补 `minute_kline_sync` 调度（盘中每 5 分钟增量，仅自选池+持仓，控制数据量）。

### 4.6 工具暴露
新增 `minute_kline`、`trading_status`、`execution_estimate`；
**强化** `portfolio_trade` 与 `watch_manage`：下单/建规则前强制经过 `trading_status` 校验（fail-closed）。

---

## 5. 验收标准（每项都必须可实测，不接受"代码已写"）

| 维度 | 标准 |
|---|---|
| 契约 | 每端口有 provider 实现 + repository 实现；provider 注册进 manager 且 `name` 唯一 |
| **多源（1.5）** | 每类数据 **≥2 个独立通道** 的 provider 注册进 manager；**故障注入实测**——手工屏蔽首选源后仍能出数且 `attempted_sources` 如实反映；跨源冲突有保守裁决与 `cross_source_conflict` 标注 |
| **字段映射** | 每个新 provider 的字段映射经**真实响应**打样核对（禁止仅凭 mock/文档；今日分红全 0 的根因） |
| 依赖方向 | `grep -rn "adapters.outbound" application/` 与 `domain/` **零命中**（ADR-001 红线） |
| 真实数据 | LIVE 用例：chain_scan 返回真实成员与占比；events_for_symbol 返回真实公告事件；minute_kline 返回真实分钟线；trading_status 对 ST/停牌/涨跌停样本判定正确 |
| 失败语义 | 数据源失败 → **显式失败**（不返回空清单/全 0）；空结果与失败分别可辨 |
| 幂等 | 重复 ingest 不产生重复行（唯一键 + evidence_hash） |
| 探针 | `data_quality_report` 各新增 1 条语义探针（链成员非空、事件新鲜度、分钟线可得性、状态字段非默认） |
| 回归 | `pnpm test` 与 `pytest` 全绿；新工具过 `plugin-schema.smoke` |

## 6. 分期建议（按"基础设施已有程度"排序，先摘低垂果实）

| 期 | 内容 | 理由 |
|---|---|---|
| **P1** | ③ 分钟线·交易状态 | 表与状态字段**已存在**，只缺端口/服务/路由/工具——最快见效，且直接提升下单安全（涨跌停/停牌 fail-closed） |
| **P2** | ① 产业链图谱（先 5-8 条主线 + 主营构成映射） | 决策原则#4 链式扫描从"手写"变"查表"，价值最高但需人工策展环节拓扑 |
| **P3** | ② 政策·事件源 | 个股事件可自动化；政策源无稳定免费 API，需采集器+兜底，工程量最大 |

## 7. 风险与不做的事

- **不做**：用 LLM 自动生成产业链拓扑（不可审计）；用新闻标题当事件源（噪声高、无结构化）
- **风险**：政策源抓取稳定性（已有东财 WAF 前例）→ 必须 fail-loud + 人工策展兜底
- **风险**：产业链环节策展有主观性 → 强制带 `evidence` 字段 + 置信度分级，允许质疑
- **明确边界**：本方案不引入新中间件（Kafka/ES）；分钟线只采自选池+持仓，不全市场入库
