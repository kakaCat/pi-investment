# 筹码分布（成本分布）服务设计

日期：2026-08-11
状态：已获用户批准
方案：方案 A —— 基于日 K 线的三角分布 + 换手率衰减模型

## 背景与目标

市场没有公开的"分价位买入量"数据，但可以用日 K 线 OHLCV + 换手率建模推算**持仓成本分布**（筹码分布），进而回答：市场把这只股票定价在什么位置、上方套牢压力多大、下方支撑在哪里。这是博弈模块的天然因子输入（识别恐慌盘、出货区、获利盘压力）。

已确认的数据基础：

- `quant.daily_klines`：OHLCV + `turnover_rate`，1994 至今，5685 只股票，约 450 万行。近期换手率覆盖约 94%/日；历史缺失时回退估算
- `quant.stocks.circulating_mv`：流通市值，用于换手率回退估算
- `quant.minute_klines` 数据停在 2026-05-29（断更），本方案不依赖分钟线

## 用户已确认的决策

1. **消费方式**：批量预计算落表（全市场每日指标）+ 按需查询（单票完整分布曲线），两者都要
2. **回溯窗口**：全历史滚动——每只股票从上市第一天起算，存量分布随每日增量滚动维护

## 架构

新建 `quantsys-v2/services/chip_distribution/`，三个单元，各自单一职责：

| 模块 | 职责 | 依赖 |
|---|---|---|
| `calculator.py` | 纯计算：K 线序列 → 筹码分布。numpy 向量化，无 IO | numpy |
| `repository.py` | 数据访问：读 daily_klines/stocks，写筹码状态表和指标表 | SQLAlchemy session |
| `service.py` | 编排：增量更新、首次回填、批量任务入口 | calculator + repository |

## 计算模型（calculator）

每只股票维护一个价位桶数组：`(price_min, bin_width, counts[N])`，N=200 桶，覆盖该股票历史 `[min_low, max_high]`。价格区间扩张时重分桶（旧分布按桶线性重采样）。

每日两步：

1. **衰减**：`counts *= (1 - min(turnover_rate, 1.0))`——换手率 t 意味存量筹码 t 比例被换手
2. **新增**：当日成交量按三角分布摊到 `[low, high]` 区间，峰值在典型价 `(H+L+2C)/4`，新增总量 = 当日换手率（归一化口径）

规则细节：

- 换手率缺失回退链：`daily_klines.turnover_rate` → `volume × close / stocks.circulating_mv` → 当日全市场中位数（记 warning）
- 换手率封顶 100%
- 停牌/缺 K 线日：不衰减不新增（筹码不动）
- 总量不变式：`sum(counts) ≈ 1`（归一化），作为单测核心断言

## 存储（两张新表）

```sql
-- 每股票一行，增量计算的"内存"
quant.chip_distribution_state
  symbol        text PK
  price_min     double precision
  bin_width     double precision
  counts        bytea          -- numpy float64 数组序列化
  last_trade_date date
  updated_at    timestamptz

-- 每日摘要指标，全市场约 5270 行/日
quant.chip_metrics
  symbol        text
  trade_date    date
  profit_ratio  double precision   -- 获利盘比例：收盘价以下筹码占比
  avg_cost      double precision   -- 平均持仓成本
  cost_90_low   double precision
  cost_90_high  double precision   -- 90% 成本区间
  cost_70_low   double precision
  cost_70_high  double precision   -- 70% 成本区间
  peak_price    double precision   -- 最大密集峰价位
  concentration double precision   -- 集中度：70% 区间宽度 / 区间中位价，越小越集中
  PRIMARY KEY (symbol, trade_date)
```

完整分布曲线不落每日历史（体积太大），靠 state 表 + 当日 K 线现场还原；`chip_metrics` 支撑全市场扫描和因子计算。

## 任务与回填

- **每日调度**：挂在现有 kline 更新（cron 17:40）之后。对每个当日有交易的 symbol：读 state → 衰减 + 新增 → 写回 state → 算指标落 `chip_metrics`。单票 O(200 桶)，全市场秒级
- **首次回填**：一次性脚本按 symbol 分批流式读约 450 万行 K 线，per-symbol 向量化循环，预计分钟级。回填期间表可读（指标逐 symbol 出现）
- **停牌/缺数据日**：跳过，不衰减

## 对外接口

- **FastAPI**：`GET /api/analysis/chip-distribution/{symbol}`——返回完整分布曲线（从 state 现场还原，含当日衰减）+ 最新指标
- **agent-ts 工具**：`chip_analysis`——返回决策上下文而非裸数据：获利盘比例、当前价相对密集峰的位置（上方套牢压力/下方支撑）、集中度趋势
- **全市场扫描**（如"获利盘 < 10% 的恐慌股"）：直接 SQL 查 `chip_metrics`，走现有因子/扫描链路

## 测试

- calculator 单测（合成 K 线）：
  - 归一化不变式 `sum(counts) ≈ 1`
  - 衰减收敛：持续高换手后旧筹码趋近 0
  - 三角分布峰值落在典型价
  - 换手率缺失回退链各级行为
  - 停牌日筹码不变
- 集成测试：真实股票（600519）跑全历史，校验 `profit_ratio ∈ [0,1]`、指标符合常识（暴跌后获利盘骤降）
- 遵循仓库现有 pytest 模式；注意 baseline 存在预存在的失败清单，只保证新增测试绿

## 明确排除（YAGNI）

- 分钟线/tick 级精度（数据断更且非必需）
- 分布曲线的每日历史快照（体积大，指标已覆盖扫描需求）
- 前端可视化（后续单独立项）
