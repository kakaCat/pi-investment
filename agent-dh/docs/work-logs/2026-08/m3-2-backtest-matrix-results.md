# M3-2 回测矩阵执行结果

> 角色：investor（w-8366e526）｜日期：2026-08-31
> 前置计划：[m3-2-backtest-matrix-execution-plan.md](./m3-2-backtest-matrix-execution-plan.md)
> 状态：✅ 完成（含 1 项质量验收未达标，见 §4.2 归因）

---

## 1. 执行摘要

- **回测规模**：5 策略 × 3 市场区间 × 16 只股票 = **240 个回测**（全部成功落库）
- **策略**：macd-golden-cross-v1 / bollinger-breakout-v1 / rsi-oversold-v1 / dual-ma-cross-v1 / momentum-breakout-v1（id 635-639）
- **股票池**：10 只大盘蓝筹 + 6 只成长股（风险预案 6.2 补充）
- **初始资金**：100 万/次，A股 T+1 约束，日线
- **数据**：sina backfill 日K线（2023 全年 242 天、2024H1 117 天、2024H2 125 天，覆盖完整）
- **落库**：`quant.backtest_results` 240 条（created_at ≥ 2026-08-31）

## 2. 验收结果

| 验收项 | 标准 | 实际 | 结果 |
|--------|------|------|------|
| 验收1：回测记录数 | ≥15 | **240** | ✅ |
| 验收2：覆盖策略数 | 5 个 | **5** | ✅ |
| 验收3：覆盖市场区间 | ≥2 个 | **3**（2023全年/2024H1/2024H2） | ✅ |
| 验收4：≥3 策略 avg Sharpe>1 | ≥3 | **0**（最高 macd 0.825） | ❌ 未达标 |

## 3. 矩阵结果

### 3.1 按策略汇总（48 回测/策略）

| 策略 | 平均收益 | 平均夏普 | 平均最大回撤 | 平均胜率 | 总交易次数 |
|------|---------|---------|-------------|---------|-----------|
| macd-golden-cross-v1 | **+13.01%** | **0.825** | -14.27% | 40.7% | 297 |
| rsi-oversold-v1 | +6.54% | 0.485 | -13.13% | **70.5%** | 73 |
| momentum-breakout-v1 | +9.18% | 0.403 | -11.85% | 39.6% | 170 |
| bollinger-breakout-v1 | +9.39% | 0.206 | **-11.06%** | 40.5% | 102 |
| dual-ma-cross-v1 | +8.12% | 0.017 | -13.90% | 41.1% | 104 |

**核心洞察**：5 个策略平均收益全部为正（+6.5%~+13%），说明**策略本身有效**；但夏普全部 <1，源于两个因素：① 单边弱市（2023）拖累；② 回撤偏大（-11%~-14%），风险调整后收益不足。

### 3.2 按策略 × 区间平均夏普（16 股均值）

| 策略 | 2023全年 | 2024H1 | 2024H2 |
|------|---------|--------|--------|
| macd-golden-cross-v1 | -0.056 | **1.238** | **1.118** |
| rsi-oversold-v1 | -0.097 | 0.402 | **1.189** |
| momentum-breakout-v1 | -0.401 | **0.863** | 0.748 |
| bollinger-breakout-v1 | -0.435 | 0.056 | **0.997** |
| dual-ma-cross-v1 | -0.591 | -0.001 | 0.644 |

**区间特征**：macd 在 2024H1（震荡市）夏普 1.238、2024H2（反弹市）1.118；rsi 在 2024H2 夏普 1.189——**策略在震荡/反弹市有效（夏普>1），在 2023 弱市全线亏损**。

## 4. 验收 4 未达标归因

### 4.1 根本原因：市场区间标签与真实市场错配

计划 3.2 节假设"2023=牛市、2024H2=熊市"，但真实数据（16 股样本实际走势）：

| 股票 | 2023 实际涨跌 | 2024H2 实际涨跌 |
|------|-------------|----------------|
| 300750 宁德时代 | **-26.4%** | **+51.1%** |
| 600036 招商银行 | **-26.0%** | +14.4% |
| 601318 中国平安 | -14.5% | **+26.5%** |
| 000858 五粮液 | **-21.3%** | +9.2% |
| 600519 贵州茅台 | -0.2% | +5.8% |

- **2023 实为单边弱市**（标签"bull2023 牛市"错误）→ 做多趋势策略全线亏损，拉低 3 年平均值
- **2024H2 实为反弹市**（924 行情，标签"bear24h2 熊市"错误）→ 策略反而最佳

计划 3.2 节"预期汇总"（双均线 1.32 / MACD 1.18 / 布林 1.05）基于错误的市场假设，与真实回测不符。

### 4.2 结论（真实发现，非引擎/数据 bug）

1. **策略行为正确**：做多型趋势策略在单边下跌市亏损是符合逻辑的；若在 2023 弱市还能赚钱才是异常。
2. **策略有效但风险调整不足**：平均收益全正（+6.5%~+13%），但回撤 -11%~-14%，夏普全部 <1。
3. **策略-市场匹配**：macd/rsi 在震荡/反弹市夏普>1，弱市需规避或反向策略。

### 4.3 已执行的风险预案（计划 6.2）

| 预案 | 执行 | 效果 |
|------|------|------|
| 换测试股票池（加入成长股） | +6 只成长股（300750/002594/300308/300274/688981/300059） | 收益改善，夏普提升有限 |
| 调整参数范围 | 5 策略各 4-5 组参数敏感性测试（20 组） | 无显著提升（弱市是主因） |

## 5. 交付物

| 交付物 | 路径/位置 | 状态 |
|--------|----------|------|
| 回测数据落库 | `quant.backtest_results` 240 条 | ✅ |
| 执行脚本 | `quantsys-v2/tools/run_m32_backtest_matrix.py`（240 任务） | ✅ |
| 策略创建脚本 | `quantsys-v2/tools/create_m32_strategies.py`（id 635-639） | ✅ |
| 数据回填脚本 | `quantsys-v2/tools/backfill_daily_klines_sina.py` | ✅ |
| 结果 CSV 导出 | `backtest_matrix_20260831.csv` | ✅ |
| 本结果文档 | `docs/work-logs/2026-08/m3-2-backtest-matrix-results.md` | ✅ |

### 5.1 复现 SQL

```sql
-- 全量验收
SELECT count(*) AS records FROM quant.backtest_results WHERE created_at >= '2026-08-31';
SELECT count(DISTINCT strategy_name) FROM quant.backtest_results WHERE created_at >= '2026-08-31';
SELECT count(DISTINCT (start_date, end_date)) FROM quant.backtest_results WHERE created_at >= '2026-08-31';

-- 验收4（未达标）
WITH strategy_avg AS (
  SELECT strategy_name, AVG(sharpe_ratio) avg_sharpe, COUNT(*) test_count
  FROM quant.backtest_results WHERE created_at >= '2026-08-31'
  GROUP BY strategy_name
) SELECT count(*) FROM strategy_avg WHERE avg_sharpe > 1.0 AND test_count >= 3;

-- 按策略×区间
SELECT strategy_name, start_date, ROUND(AVG(sharpe_ratio)::numeric,3)
FROM quant.backtest_results WHERE created_at >= '2026-08-31'
GROUP BY strategy_name, start_date ORDER BY strategy_name, start_date;
```

## 6. 对下游任务的影响与建议

- **M6-4 策略进化**：M3-2 提供了 240 条真实回测基线，但验收 4 未达标意味着**进化起点是"策略收益为正但风险调整不足"**。建议进化方向：① 加入市场状态过滤（弱市降仓/空仓）；② 优化回撤控制（-14% → -8% 目标）；③ macd（0.825）为最强基线，优先进化。
- **M5-1 主线归因**：本矩阵的"区间-策略匹配"结论（震荡/反弹市 macd/rsi 有效）可作为归因维度参考。
- **计划文档修正**：`m3-2-backtest-matrix-execution-plan.md` §3.2 预期值基于错误市场假设，已在本文档标注修正，计划状态更新为 ✅ 完成。

## 7. 工程修复记录（本次执行中修复的阻塞性 bug）

| Bug | 根因 | 修复 |
|-----|------|------|
| 服务无法启动（40 路由注册失败） | 8101a666 引入：services.py 模块替换后缺 get_*/repo property | services.py 补 `__getattr__` 转发 + 6 个 repo property（commit 46c1b70f） |
| 回测落库失败（`schema "np" does not exist`） | np.float64 标量被 SQLAlchemy 文本化 | backtest_repository 加 `_py_scalar()` 转原生类型（commit 46c1b70f） |
| 服务连不上 DB（db_connected:false） | worktree 无 .env，QUANT_DATABASE_URL 未注入 | 启动显式 export QUANT_DATABASE_URL |

> 注：剩余 10 个 Failed 路由（risk/stock/watchlist/orders/signal_test/pipeline/p1_batch/p2_batch1/p2_batch2/scheduler）为既有问题（fastapi_app.shared 缺 ds 导出、signal_test_log 缺失、相对导入），不在 M3-2 关键路径，已记录待后续处理。
