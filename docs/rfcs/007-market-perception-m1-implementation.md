# RFC 007: M1 市场感知实施方案（regime 落库 / 主线识别 / 情绪时间序列）

| 字段 | 值 |
|---|---|
| 状态 | 🟡 设计待评审 |
| 创建 | 2026-08-20（agent-dh k3） |
| 上游 | [RFC 004 盈利引擎设计](004-profit-engine-design.md) M1 模块；[RFC 005 工单包](005-profit-engine-work-tickets.md) M1-1/M1-2/M1-3 |
| 负责方 | 挣钱线（agent-dh）主实施；涉及 quantsys-v2 后端小改（单仓库内完成） |

---

## 1. 现状侦察结论（2026-08-20 实测）

| 现有资产 | 状态 | 复用方式 |
|---|---|---|
| `market_sentiment_service.py` | ✅ 可用：涨跌家数/量能/新高新低/波动率/情绪分五维指标已能算 | M1-3 直接调用其指标计算，只补"落库" |
| `ds.kline.get_market_breadth()` | ⚠️ 覆盖缺陷：基于 daily_klines 聚合，2026-08-20 实测涨跌家数仅 245/74（疑似当日全市场同步未完成时统计） | M1-3 前置修复：落库时校验覆盖量，不足则标记 partial |
| `akshare.get_zt_pool(date)`（stock_zt_pool_em） | ✅ 涨停池数据源已存在 | M1-2 涨停聚类的输入 |
| `sector_analysis` / 板块资金流 | ✅ 工具存在 | M1-2 资金流维度的输入 |
| `POST /api/scheduler/tasks` | ✅ 调度任务 API 齐备 | 每日 15:30 落库任务的挂载点 |
| regime 判定 | ⚠️ 散落在 opportunity_scan 内部（sideways+权重自适应），不落库、不可查历史 | M1-1 重写为独立可落库的判定器 |

**核心问题**：三个能力都是"即用即弃"的一次性计算，无法回答"上周三是什么市、当时在炒什么"。M1 = 把它们变成可查询的时间序列资产。

## 2. 总体架构

```
每日 15:30（收盘后）调度任务 market_daily_snapshot
        │
        ├─→ M1-3 情绪指标计算（复用 market_sentiment_service）─┐
        ├─→ M1-1 regime 判定（读情绪指标+指数趋势）           ├─→ PostgreSQL
        └─→ M1-2 主线识别（涨停池+板块资金流+催化剂）          ─┘   quant 三张新表
                                                                    │
盘前/决策时 agent 查询 API ←────────────────────────────────────────┘
（GET /api/market/regime、/api/market/themes、/api/market/sentiment-history）
```

**实施位置**：判定/识别/落库逻辑全部放 quantsys-v2 后端（新 `application/services/market_perception_service.py`），agent-dh 侧不加新插件——agent 通过现有 HTTP 客户端读结果，LLM 只参与 M1-2 的催化剂命名（由盘后调度例程中的 agent 调用补充）。

## 3. M1-1 regime 每日落库

### 表结构

```sql
CREATE TABLE quant.market_regime (
    trade_date      date PRIMARY KEY,
    regime          text NOT NULL,        -- trend_up/trend_down/range/panic/euphoria
    index_trend_score double precision,   -- 沪深300 相对 MA20/MA60 位置得分 [-1,1]
    sentiment_score double precision,     -- 情绪分 [0,100]
    volume_ratio    double precision,     -- 量能比（5日均/20日均）
    ad_ratio        double precision,     -- 涨跌家数比
    reason          text NOT NULL,        -- 人读判定依据
    created_at      timestamptz DEFAULT now()
);
```

### 判定规则（规则先行，可解释，不上模型）

| 规则（按优先级） | 判定 |
|---|---|
| 情绪分 ≤20 且 量能萎缩 且 指数5日跌 >3% | `panic` |
| 情绪分 ≥80 且 量能比 >2 且 涨家占比 >70% | `euphoria` |
| 指数 >MA20 且 MA20>MA60 且 5日涨 >1% | `trend_up` |
| 指数 <MA20 且 MA20<MA60 且 5日跌 >1% | `trend_down` |
| 其余 | `range` |

`reason` 字段记录命中规则的原始指标值，如 `"指数+1.2%站MA20上方, MA20>MA60, 量能2.7x → trend_up"`。

### API 与回填

- `POST /api/market/perception/snapshot`（内部用，调度任务调用）：计算并落库当日 regime + 情绪
- `GET /api/market/regime?days=20`：查 regime 时间序列
- 回填：脚本 `tools/backfill_market_regime.py`，用 daily_klines 历史重算近 120 交易日（供 M1-2 回放验收和 M4-1 仓位映射回测）

### 验收（对应 RFC005 M1-1）

```bash
curl "localhost:5001/api/market/regime?days=5"
```
标准：每个交易日 1 条，含 reason 字段；回填后历史 ≥120 条。

## 4. M1-3 情绪时间序列落库

### 表结构

```sql
CREATE TABLE quant.market_sentiment_daily (
    trade_date       date PRIMARY KEY,
    up_count         int, down_count int, flat_count int,
    ad_ratio         double precision,
    new_high_count   int, new_low_count int,
    volume_ratio     double precision,   -- 近5日均量/前20日均量
    total_turnover   double precision,   -- 全市场成交额
    volatility       double precision,
    fear_greed_index double precision,
    coverage         int,                -- 统计覆盖股票数（数据质量自查）
    partial          boolean DEFAULT false,  -- coverage < 4000 时标记
    created_at       timestamptz DEFAULT now()
);
```

### 关键修复（前置）

实测发现涨跌家数 245/74 远低于全市场量级——`get_market_breadth()` 依赖 daily_klines 当日同步完成度。落库逻辑必须：
1. 记录 `coverage`（参与统计的股票数）；
2. `coverage < 4000` 时 `partial=true` 并在 `data_quality_report` 出告警；
3. 调度时间 15:30 若当日同步未完成则 16:30 补跑一次（scheduler 已有重试惯例）。

### 验收（对应 RFC005 M1-3）

```bash
psql quant_investment -c "SELECT * FROM quant.market_sentiment_daily ORDER BY trade_date DESC LIMIT 5"
```
标准：最近 5 个交易日每天 1 条、字段完整、coverage ≥4000（或 partial 有告警记录）。

## 5. M1-2 每日主线识别器

### 流程

```
涨停池（get_zt_pool 当日）
  → 按行业/概念聚类，≥3只涨停的板块 = 主线候选
  → 叠加板块资金流方向（sector_analysis 主力净流入）
  → 排序取 Top3
  → 催化剂关联：盘后例程中 agent（LLM）为主题命名+关联事件
    （如「8/18 农业涨停潮 + 厄尔尼诺新闻 → 粮食安全」）
  → 落库 quant.market_theme
```

### 表结构

```sql
CREATE TABLE quant.market_theme (
    id              serial PRIMARY KEY,
    trade_date      date NOT NULL,
    rank            int NOT NULL,          -- 1/2/3
    theme           text NOT NULL,         -- 主线名（LLM 命名，如"粮食安全"）
    sector          text,                  -- 聚类板块（如"农牧饲渔"）
    limit_up_count  int,                   -- 涨停数
    stocks          jsonb,                 -- 代表股 [{symbol,name,reason}]
    fund_flow       double precision,      -- 板块主力净流入（亿）
    catalyst        text,                  -- 催化剂描述（LLM 关联）
    confidence      double precision,      -- 0-1
    created_at      timestamptz DEFAULT now(),
    UNIQUE(trade_date, rank)
);
```

### 分工说明

涨停聚类+资金流+排序是确定性逻辑（后端 service 做）；**催化剂关联是 LLM 强项**，由盘后例程（schedule 任务）中的 agent 读取当日聚类结果后命名并回写（`PUT /api/market/themes/{id}` 补 catalyst/theme 字段）。这复刻了 8/18 人工复盘的正确路径，但自动化。

### 验收（对应 RFC005 M1-2）

```bash
# 回放测试：用回填/历史数据重算 2026-08-18
curl -X POST localhost:5001/api/market/perception/backfill-theme -d '{"date":"2026-08-18"}'
curl "localhost:5001/api/market/themes?date=2026-08-18"
```
标准：输出 Top3 中含农业相关主线（农牧饲渔/种业/粮食安全之一）；首周与人工复盘一致率 ≥70%。

## 6. 工单拆分（每单可独立验收）

| ID | 工单 | 依赖 | 验收命令 | 预估 |
|---|---|---|---|---|
| M1-1a | 建 3 张表 + `market_perception_service` 骨架 | 无 | `\dt quant.market_*` 三表存在 | 0.5d |
| M1-1b | regime 判定器 + snapshot API + 调度挂载 | M1-1a | `curl /api/market/regime?days=5` 有记录 | 0.5d |
| M1-1c | regime 历史回填 120 日 | M1-1b | 回填后 `COUNT(*) ≥120` | 0.5d |
| M1-3a | 情绪落库 + coverage/partial 自查 + 质量告警 | M1-1a | 最近 5 日记录字段完整 | 0.5d |
| M1-2a | 涨停聚类 + 资金流排序 + theme 落库 | M1-1a | 当日 theme Top3 落库 | 1d |
| M1-2b | 催化剂 LLM 关联（盘后例程接线 + 回写 API） | M1-2a | 8/18 回放含农业主线 | 0.5d |

总预估：**3.5 个工作日**（含验收）。

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| daily_klines 当日同步延迟导致 15:30 落库 partial | coverage 自查 + 16:30 补跑 + 质量告警（M1-3a 内置） |
| 涨停池数据源（东财）当日不可用 | get_zt_pool 返回空时主线落库跳过并记告警，不造数据 |
| regime 规则阈值主观 | reason 字段留全部原始指标值，阈值调整不改表结构；运行 2 周后复盘校准 |
| LLM 催化剂命名漂移（每日叫法不一致） | 命名时传入近 7 日已有 theme 列表供对齐，保持命名连续性 |

## 8. 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-20 | 创建。基于实测侦察：sentiment service 可复用、zt_pool 数据源已在、breadth 覆盖缺陷确认（245/74）、scheduler API 齐备 |
