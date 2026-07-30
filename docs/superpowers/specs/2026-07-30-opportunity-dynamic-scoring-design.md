# 机会扫描动态评分系统设计

**日期**: 2026-07-30
**状态**: 已评审（用户确认）
**范围**: quantsys-v2（主）、agent-ts（轻改）

## 1. 背景与问题

**2026-07-30 实施前核查修正**：最初假设"评分引擎写好了但没接入"是过时的。实际调用链：

- agent-ts `opportunity_scan` 工具 → `POST /api/signals/scan` → [signals.py](quantsys-v2/adapters/inbound/api/routes/signals.py)（Flask）/ [signals_async.py](quantsys-v2/adapters/inbound/fastapi_app/routes/signals_async.py)（FastAPI parity）→ **已经在调用 `scoring_service.score_stocks()` 真实评分**
- 硬编码 `score: 75` 的 `/api/opportunities/scan`（[opportunities.py](quantsys-v2/adapters/inbound/api/routes/opportunities.py)）经全仓 grep **无任何调用方**（agent-ts / web-frontend 都不调），是死代码

| 组件 | 状态 |
|---|---|
| `application/services/opportunity_scoring_service.py`（710 行） | ✅ 已接入 `/api/signals/scan`；但评分不区分股票类型、不感知市场环境、资金分仅成交量、**响应无 reasons/breakdown**（agent 无法归因） |
| `application/services/opportunity_scoring_service_v2.py`（660 行） | 有 `_generate_reasons` 思路；无测试、未注册 DI |
| `application/services/scoring/technical_scorer.py` | ✅ RSI/MACD/ADX/量能灰度化评分 |
| `application/services/scoring/fundamental_scorer.py` | ✅ PE/ROE/毛利率/负债/增长灰度化评分（⚠️ 服务传入的 key 是 `pe_ratio` 而 scorer 读 `pe`，存在 key 错位 latent bug，PE 维度一直得 0 分） |
| `application/services/market_regime_detector.py` | ✅ 牛/熊/震荡判定（ADX + 均线排列 + 波动率），未接入评分 |
| `adapters/inbound/api/routes/opportunities.py` | ❌ 死代码（硬编码 score=75，无调用方），删除 |

**真实缺口**：服务评分逻辑本身——不区分股票类型（周期股用成长股权重打分）、不感知市场环境、资金分维度单薄、无打分理由输出。

## 2. 设计目标

1. 路由返回**真实评分**，替换硬编码
2. **逐股程序化分类**（growth/value/cyclical/balanced），不同类股票用不同权重
3. **市场环境感知**：regime 信号连续驱动权重调整
4. **完整证据链**：每股返回 breakdown + reasons + applied_context，agent 可复算可归因
5. **零人工配置**：分类和权重全部由数据算出，不用 yaml/行业名单
6. **数据自愈**：可修复的数据问题自动修复（走统一数据入口），不可修复的显式降级

非目标：不做全市场扫描性能优化；不改动 TechnicalScorer/FundamentalScorer 的评分逻辑本身；北向个股持仓维度（无数据源）。

## 3. 整体架构

```
POST /api/signals/scan  {symbols/stocks, conditions, limit, weights?, no_cache?}
  │  （agent-ts opportunity_scan 的实际调用入口；Flask + FastAPI parity 双实现，
  │    两者都已调用同一个 OpportunityScoringService，增强服务即双端同时受益）
  ▼
routes/signals.py / signals_async.py（保持薄，仅补 diagnostics 透传）
  │
  ▼
OpportunityScoringService.score_stocks()
  │
  ├─ 0. MarketRegimeDetector.detect_regime_signals()  ← 全扫描一次，TTL 30min
  │     → {label, trend_strength, market_risk, liquidity_heat}（连续信号值 0-1）
  │
  ├─ 1. 批量取数（全部批量单查，无 N+1）
  │     batch_get_recent_klines(symbols, days=250)   ← 从 120 放宽到 250（52 周高点需要）
  │     batch_get_fundamentals(symbols)              ← 已有，TTL 1h
  │     季度 income_statements 批量 8 季度            ← 新增批量方法，TTL 24h
  │     fund_flows 批量近 5 日主力净流入              ← 新增批量方法，TTL 5min
  │
  ├─ 2. DataQualityGate（数据检测与自动修复，见 §6）
  │
  ├─ 3. 逐股（线程池并行，沿用现有模式）
  │     a. StockProfileClassifier.classify() → profile（程序化，见 §4.1）
  │     b. TechnicalScorer / FundamentalScorer（逻辑不动）
  │     c. CapitalScorer（新，见 §4.2）
  │     d. CyclePositionScorer（新，仅 cyclical，见 §4.3）
  │     e. 最终权重 = profile 插值基础权重 × regime 信号修正 → 限幅归一化（见 §4.4）
  │     f. 综合分 = Σ(维度分 × 权重)
  │     g. 生成 reasons[] + score_breakdown + applied_context
  │
  └─ 4. 排序、conditions 筛选、截断 limit、返回（含 diagnostics + repair_report）
```

**关键决策**：

1. **删除死路由** `routes/opportunities.py`（无调用方，符合仓库"删除废弃代码"约定）；真正的入口 `/api/signals/scan` 已经是薄路由，只需在响应里补 `diagnostics`。
2. **regime 全扫描只判一次**——它是市场级状态。
3. **收编 v2 服务**：`_generate_reasons` 思路合并进 v1 服务后，删除 `opportunity_scoring_service_v2.py`（无测试无 DI 注册，避免再次新旧并存）。
4. **修复 fundamental key 错位**：服务调 FundamentalScorer 前把 `pe_ratio`→`pe` 等 key 映射正确（latent bug，PE 维度目前恒 0 分）。
5. **常量兜底 + 程序计算 + TTL 缓存三层**（见 §5），兜底常量在代码里（`DEFAULT_*`），不单独配置文件。

## 4. 程序化分类与评分

### 4.1 StockProfileClassifier（逐股分类，不用行业名单）

批量查所有 symbols 近 8 个季度 income_statements（一次批量 SQL），逐股算三个连续指标：

| 指标 | 计算 | 含义 |
|---|---|---|
| `earnings_volatility` | 近 8 季度毛利率标准差（百分点） | 盈利波动大 = 周期特征 |
| `growth_strength` | 最新营收增速 × 毛利率水平（归一化） | 成长特征 |
| `value_strength` | ROE / PE（盈利收益率的质量） | 价值特征 |

分类规则（阈值为代码常量，判定依据全部输出到 reasons）：

```python
if earnings_volatility >= 8:        # 毛利率波动超 8pp，盈利随周期摆动
    profile = 'cyclical'
elif growth_strength 在全池前 30%:   # 池内相对分位，自适应
    profile = 'growth'
elif value_strength 在全池前 30%:
    profile = 'value'
else:
    profile = 'balanced'
```

- growth/value 用**池内相对分位**而非绝对阈值：扫描沪深 300 和扫描创业板，"高成长"的尺度自动不同。
- 行业字段不参与分类（避免死名单），但保留在 applied_context 供参考。
- 季度数据不足 4 期 → balanced + reason 注明。

### 4.2 CapitalScorer（资金面，0-100）

数据：`fund_flows` 表近 5 日主力净流入 + K 线量比。fund_flows 无数据时降级纯量能，reasons 注明。

| 子项 | 分值 | 逻辑 |
|---|---|---|
| 主力净流入方向 | ±30 | 5 日净流入相对流通市值归一化，线性加扣分 |
| 流入加速 | 0-20 | 近 2 日净流入 > 前 3 日均值（资金在进场） |
| 量比 | ±20 | 沿用现有 volume_ratio_5d 逻辑 |
| 量能趋势 | 0-15 | 5 日均量 > 20 日均量 |
| 共振 | 0-15 | 主力流入 + 放量 + 股价上涨三者同向 |

降级时总分按可得子项折算。异常值（单日净流入 > 流通市值 20%）winsorize 截断。

### 4.3 CyclePositionScorer（周期位置，0-100，仅 cyclical）

| 子项 | 分值 | 逻辑 |
|---|---|---|
| 毛利率 QoQ | ±35 | 最近 2 季度环比：连续扩张 → 盈利拐点向上加分；连续收缩 → 扣分 |
| 距 52 周高点 | ±35 | 高点回撤 30-50% → 可能已定价（加分区）；距高点 <10% → 周期顶部警惕（扣分） |
| 同向/背离 | ±30 | 毛利率扩张 + 股价深跌 = 黄金坑（加分）；毛利率收缩 + 股价新高 = 顶部陷阱（重扣分） |

### 4.4 权重：profile 插值 × regime 连续修正

**profile 基础权重随特征强度连续插值**，不是死表：

```python
# 每个 profile 有权重端点（代码常量），实际权重按特征分位在端点间插值
# 例：growth 分位 90% 的股票比 31% 的股票 fundamental 权重更高
PROFILE_WEIGHT_ENDPOINTS = {
    'growth':   {'technical': (0.45, 0.35), 'fundamental': (0.30, 0.40), 'capital': (0.25, 0.25)},
    'value':    {'technical': (0.30, 0.20), 'fundamental': (0.45, 0.55), 'capital': (0.25, 0.25)},
    'cyclical': {'technical': 0.25, 'fundamental': 0.20, 'capital': 0.25, 'cycle': 0.30},
    'balanced': {'technical': 0.50, 'fundamental': 0.30, 'capital': 0.20},
}
```

**regime 信号连续修正**（MarketRegimeDetector 暴露连续信号值，不止离散标签）：

```python
w_tech = base.tech × (1 + 0.5 × (trend_strength - 0.5))   # 趋势越强技术权重越大
w_fund = base.fund × (1 + 0.6 × (market_risk - 0.4))      # 风险越大基本面权重越大
w_cap  = base.cap  × (1 + 0.5 × (liquidity_heat - 0.5))   # 量能越热资金权重越大
# cyclical 的 cycle 权重不参与 regime 修正
→ 限幅：单维权重 ∈ [0.15, 0.60] → 归一化
```

**覆盖规则**：调用方传 `weights` 参数 → 覆盖整个动态机制（显式 > 隐式），reasons 注明 `"使用调用方指定权重"`，`weights_source: "override"`。

## 5. 缓存与兜底（常量兜底 + 程序计算 + TTL）

```
请求 → 查缓存（命中直接用）→ 未命中/过期 → 程序计算 → 写缓存
     → 计算失败/数据不足 → 代码兜底常量 + reasons 注明
```

| 数据 | 自然更新频率 | TTL | 兜底 |
|---|---|---|---|
| 季度财务 / profile 分类 | 一季一次 | 24h | balanced |
| regime 信号 | 盘中缓慢变化 | 30min | sideways 不调整 |
| fund_flows 主力净流入 | 逐日 | 5min | 纯量能评分 |
| 基本面快照（PE/ROE） | 逐日 | 1h | 该维度中性分 50 |
| K线/技术指标 | 盘中实时 | 不缓存 | 数据不足跳过该股 |

每次降级写 reasons + `diagnostics.degraded` 计数（不许静默降级）。

性能估算（100 股）：新增 2 个批量查询 ~60ms；分位/权重计算微秒级；K线 120→250 天使指标计算 CPU 近翻倍（服务已有线程池并行）。冷扫描 3-6s，缓存热 1-2s。

## 6. 数据质量检测与自动修复（DataQualityGate）

评分前每股过一道检测（复用 quantlib DataValidator）：

| 检测 | 判定 | 自动修复 | 修不了 |
|---|---|---|---|
| K线缺口 | 近 5 交易日缺数据 | ✅ 按需调 DataProviderManager 补抓（统一入口，不 bypass） | 跳过该股 + 计数 |
| K线脏数据 | 价格 ≤0、amount=0 但 volume>0 | ⚠️ 该 bar 剔除出指标计算（不重抓） | 剔除后 <120 根 → 跳过 |
| 基本面过期 | updated_at > 7 天 | ✅ 触发该股基本面刷新 | 中性分 50 + 注明 |
| 资金流缺失 | 近 5 日无记录 | ✅ 尝试按需补抓 | 降级纯量能 |
| 季度财报不足 | <4 期 | ❌ 不可修（未披露） | profile=balanced |
| 异常值 | 单日净流入 > 流通市值 20% | ⚠️ winsorize 截断 + 标记 | 截断后照常评分 |

**三条铁律**：

1. 修复必须走 DataProviderManager 统一入口（多数据源 failover/熔断/限速白捡）
2. 修复有预算：单次扫描最多触发 20 只股票补抓，超出直接降级（防扫描变回填任务）
3. 修复全程可见：`diagnostics.repair_report = {attempted, succeeded, failed, skipped_over_budget}`；修过的股票 reasons 加 `"K线缺口已自动补抓(3根)"`

**不做**：不补历史大段缺口（scheduler_daemon 数据管道职责）；不插值编造财报；修复失败不让整次扫描失败。

## 7. API 契约

### 请求（向后兼容，只加可选字段）

`POST /api/signals/scan`（Flask + FastAPI parity 同步生效）

```json
{
  "symbols": ["600519"],      // 可选，不变（也兼容 stocks 字段）
  "limit": 20,                 // 不变
  "conditions": [...],         // 不变
  "weights": {...},            // 可选，传入=覆盖动态机制
  "no_cache": false            // 🆕 跳过缓存强制重算（调试）
}
```

### 响应（每股完整证据链）

```json
{
  "success": true,
  "data": {
    "opportunities": [{
      "symbol": "601899", "name": "紫金矿业",
      "score": 78.5, "signal_type": "buy", "risk_level": "medium",
      "score_breakdown": {
        "technical":   {"total": 72, "weight": 0.28, "weighted": 20.2,
                        "details": {"rsi": 18.5, "macd": 15.0, "adx": 10.0, "volume": 16.0, "resonance": 10.0}},
        "fundamental": {"total": 65, "weight": 0.22, "weighted": 14.3,
                        "details": {"pe": 8.0, "roe": 14.0, "gross_margin": 10.0, "debt_ratio": 12.0, "revenue_growth": 8.0, "resonance": 10.0}},
        "capital":     {"total": 81, "weight": 0.22, "weighted": 17.8, "details": {"main_inflow": 28}},
        "cycle":       {"total": 87, "weight": 0.28, "weighted": 24.4,
                        "details": {"margin_qoq": 30, "from_52w_high": 32, "alignment": 25}}
      },
      "reasons": [
        "盈利波动率9.2pp，判定为周期股",
        "周期位置佳：毛利率连续2季扩张(+3.1pp)，股价距52周高点回撤38%",
        "主力资金连续3日净流入(累计2.3亿)，流入加速",
        "RSI超卖(28.5)+MACD金叉共振",
        "当前震荡市，权重未调整"
      ],
      "applied_context": {
        "profile": "cyclical",
        "profile_signals": {"earnings_volatility_pp": 9.2, "growth_pct": 45, "value_pct": 88},
        "market_regime": {"label": "sideways", "trend_strength": 0.42, "market_risk": 0.55, "liquidity_heat": 0.38},
        "final_weights": {"technical": 0.28, "fundamental": 0.22, "capital": 0.22, "cycle": 0.28},
        "weights_source": "auto",
        "cache": {"fundamentals": "hit", "regime": "hit", "fund_flow": "computed"}
      },
      "entry_price": 18.42, "stop_loss": null, "target_price": null,
      "technical_score": 72, "fundamental_score": 65, "capital_score": 81,
      "reason": "盈利波动率9.2pp，判定为周期股"
    }],
    "count": 20, "symbols_scanned": 100, "scan_time": "...",
    "diagnostics": {
      "universe_size": 100, "scored": 87,
      "skipped_insufficient_klines": 8, "skipped_condition_filter": 5, "errors": 0,
      "degraded": {"fund_flow_missing": 12, "quarterly_insufficient": 6},
      "repair_report": {"attempted": 8, "succeeded": 6, "failed": 2, "skipped_over_budget": 3},
      "elapsed_ms": 3240
    }
  }
}
```

要点：

1. 证据链完整：`score_breakdown` + `final_weights` 可复算 score
2. 降级显式化：`degraded` + `repair_report`
3. 旧字段保留：`technical_score`/`fundamental_score`/`capital_score`/`reason`（取 reasons[0]），web 前端和老调用方不破

## 8. agent-ts 改动（轻）

- `opportunity_scan` 工具参数不变；description 更新为"profile + regime 动态打分"
- `formatters.ts formatOpportunities` 增加 reasons/breakdown 展示
- 工具测试 mock 更新为新响应形状（用 apiClient 解包后形状，历史教训）

## 9. 错误处理

| 场景 | 行为 |
|---|---|
| 单股评分抛异常 | 跳过该股，errors+1，继续（现有模式） |
| regime 判定失败 | 回退 sideways 不调整，reasons 注明 |
| fund_flows 无数据 | 资金分降级纯量能，degraded 计数 |
| 季度财报 <4 期 | profile=balanced |
| 全部失败 | 返回空列表 + diagnostics，HTTP 200（"没机会" vs "挂了"可区分） |

## 10. 测试策略（pytest，quant_test 库）

1. CapitalScorer / CyclePositionScorer 单测：子项边界 + 降级路径
2. StockProfileClassifier 单测：四类判定 + 数据不足兜底 + 分位计算
3. 权重函数单测：regime 信号 → 权重，限幅与归一化
4. DataQualityGate 单测：各检测项 + 修复预算上限 + 修复失败降级
5. 集成测试：5 只构造股票全链路，验证响应结构 + 证据链可复算（Σ breakdown.weighted ≈ score）
6. 回归：现有 test_opportunity_scoring_service.py / test_opportunity_radar_integration.py 全绿
7. TS：opportunity-scan-tool.test.ts 更新 mock

## 11. 实施步骤（概要）

1. 新增批量取数方法（季度 income_statements、fund_flows 5 日）+ 单测
2. CapitalScorer / CyclePositionScorer + 单测
3. StockProfileClassifier + 权重函数 + 单测
4. MarketRegimeDetector 暴露连续信号值（detect_from_dataframe）+ 缓存封装
5. DataQualityGate + 修复预算 + 单测
6. OpportunityScoringService 编排整合（合并 v2 reasons 思路 + fundamental key 映射修复）+ 集成测试
7. signals 路由补 diagnostics 透传 + 删除死路由 opportunities.py + 删除 opportunity_scoring_service_v2.py
8. agent-ts 类型/formatter/测试更新
9. 全量回归（注意预存在失败清单，区分回归）
