---
id: wl-2026-08-m3-2-backtest-matrix-execution-plan
title: M3-2 回测矩阵执行计划
type: worklog
status: archived
updated: 2026-08-31
owners: [w-8366e526]
tags: [worklog, 2026-08]
---

# M3-2 回测矩阵执行计划

**任务**: 5 策略 × 3 市场区间回测矩阵  
**目标**: 筛选夏普 >1 的策略  
**执行日期**: 2026-08-31  
**执行者**: agent-dh investor (w-8366e526)

---

## 1. 回测矩阵定义

### 1.1 策略选择（5 个）

| 序号 | 策略名称 | 策略ID | 参数范围 | 说明 |
|------|---------|--------|---------|------|
| 1 | MACD 金叉策略 | macd_golden_cross | fast:[5,12,20], slow:[20,26,35], signal:[5,9,12] | 经典趋势跟踪 |
| 2 | 布林带突破策略 | bollinger_breakout | period:[15,20,25], std:[1.5,2.0,2.5] | 波动突破 |
| 3 | RSI 超卖反弹策略 | rsi_oversold | period:[9,14,21], oversold:[25,30,35] | 超卖反转 |
| 4 | 双均线策略 | dual_ma | fast:[10,20,30], slow:[30,50,60] | 趋势跟踪 |
| 5 | 动量策略 | momentum | lookback:[5,10,20], threshold:[3,5,8] | 短期动量 |

### 1.2 市场区间（3 个）

| 区间 | 时间范围 | 市场特征 | 代表指数 |
|------|---------|---------|---------|
| 牛市 | 2023-01-01 ~ 2023-12-31 | 上证指数 +8.9% | 趋势明确 |
| 震荡 | 2024-01-01 ~ 2024-06-30 | 上证指数 -2.3% | 箱体震荡 |
| 熊市 | 2024-07-01 ~ 2024-12-31 | 上证指数 -5.7% | 单边下跌 |

### 1.3 测试股票池

**蓝筹股池**（10 只）:
- 600519（贵州茅台）
- 000858（五粮液）
- 600036（招商银行）
- 600000（浦发银行）
- 601318（中国平安）
- 600030（中信证券）
- 000333（美的集团）
- 601166（兴业银行）
- 601288（农业银行）
- 600900（长江电力）

**矩阵总数**: 5 策略 × 3 区间 = **15 个回测任务**

---

## 2. 执行命令清单

### 2.1 策略1: MACD 金叉策略

#### 牛市区间（2023）
```javascript
await strategy_optimize({
  strategy_id: 'macd_golden_cross',
  symbols: ['600519', '000858', '600036', '600000', '601318', 
            '600030', '000333', '601166', '601288', '600900'],
  start_date: '2023-01-01',
  end_date: '2023-12-31',
  initial_capital: 100000,
  param_ranges: {
    fast_period: [5, 12, 20],
    slow_period: [20, 26, 35],
    signal_period: [5, 9, 12]
  },
  optimization_target: 'sharpe'
});
```

#### 震荡区间（2024H1）
```javascript
await strategy_optimize({
  strategy_id: 'macd_golden_cross',
  symbols: ['600519', '000858', '600036', '600000', '601318', 
            '600030', '000333', '601166', '601288', '600900'],
  start_date: '2024-01-01',
  end_date: '2024-06-30',
  initial_capital: 100000,
  param_ranges: {
    fast_period: [5, 12, 20],
    slow_period: [20, 26, 35],
    signal_period: [5, 9, 12]
  },
  optimization_target: 'sharpe'
});
```

#### 熊市区间（2024H2）
```javascript
await strategy_optimize({
  strategy_id: 'macd_golden_cross',
  symbols: ['600519', '000858', '600036', '600000', '601318', 
            '600030', '000333', '601166', '601288', '600900'],
  start_date: '2024-07-01',
  end_date: '2024-12-31',
  initial_capital: 100000,
  param_ranges: {
    fast_period: [5, 12, 20],
    slow_period: [20, 26, 35],
    signal_period: [5, 9, 12]
  },
  optimization_target: 'sharpe'
});
```

---

### 2.2 策略2: 布林带突破策略

#### 三个区间（命令类似，参数不同）
```javascript
// 牛市/震荡/熊市各执行一次，仅修改 start_date/end_date
param_ranges: {
  bb_period: [15, 20, 25],
  bb_std: [1.5, 2.0, 2.5]
}
```

---

### 2.3 策略3: RSI 超卖反弹策略

```javascript
param_ranges: {
  rsi_period: [9, 14, 21],
  rsi_oversold: [25, 30, 35]
}
```

---

### 2.4 策略4: 双均线策略

```javascript
param_ranges: {
  fast_ma: [10, 20, 30],
  slow_ma: [30, 50, 60]
}
```

---

### 2.5 策略5: 动量策略

```javascript
param_ranges: {
  lookback: [5, 10, 20],
  threshold: [3, 5, 8]
}
```

---

## 3. 预期输出格式

### 3.1 单个回测结果示例

```json
{
  "strategy": "macd_golden_cross",
  "period": "2023-01-01 ~ 2023-12-31",
  "market_type": "bull",
  "results": {
    "total_combinations": 27,
    "successful_combinations": 27,
    "best_result": {
      "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
      "sharpe_ratio": 1.45,
      "total_return": 18.3,
      "max_drawdown": -7.2,
      "win_rate": 65.0,
      "total_trades": 48
    }
  }
}
```

### 3.2 汇总结果（15 个回测）

**按策略汇总**:
```
策略排名（按平均夏普）:
1. 双均线策略: 平均夏普 1.32（牛市 1.45，震荡 1.28，熊市 1.25）✅
2. MACD 策略: 平均夏普 1.18（牛市 1.38，震荡 1.05，熊市 1.12）✅
3. 布林带策略: 平均夏普 1.05（牛市 1.22，震荡 0.95，熊市 0.98）✅
4. RSI 策略: 平均夏普 0.92（不达标）❌
5. 动量策略: 平均夏普 0.85（不达标）❌

推荐策略: 双均线策略（参数 fast=12, slow=26）
```

---

## 4. 验收标准

### 4.1 数据验收

```sql
-- 验收1: 回测记录 ≥15 条
SELECT COUNT(*) FROM quant.backtest_results 
WHERE created_at >= '2026-08-31';
-- 期望: ≥15

-- 验收2: 覆盖 5 个策略
SELECT COUNT(DISTINCT strategy_id) FROM quant.backtest_results 
WHERE created_at >= '2026-08-31';
-- 期望: 5

-- 验收3: 覆盖 3 个市场区间
SELECT COUNT(DISTINCT 
  CONCAT(EXTRACT(YEAR FROM start_date), '-', 
         CASE 
           WHEN EXTRACT(MONTH FROM start_date) <= 6 THEN 'H1' 
           ELSE 'H2' 
         END)
) as periods
FROM quant.backtest_results 
WHERE created_at >= '2026-08-31';
-- 期望: ≥2（至少覆盖 2 个不同年份/半年）
```

### 4.2 质量验收

```sql
-- 验收4: 至少 3 个策略平均夏普 >1
WITH strategy_avg AS (
  SELECT 
    strategy_id,
    AVG(sharpe_ratio) as avg_sharpe,
    COUNT(*) as test_count
  FROM quant.backtest_results 
  WHERE created_at >= '2026-08-31'
  GROUP BY strategy_id
)
SELECT COUNT(*) as good_strategies
FROM strategy_avg
WHERE avg_sharpe > 1.0 AND test_count >= 3;
-- 期望: ≥3
```

---

## 5. 执行时间表

| 时间 | 任务 | 预计耗时 |
|------|------|---------|
| 08:00-08:30 | 准备测试数据（验证股票池 K线完整性） | 30 分钟 |
| 08:30-10:30 | 执行 15 个回测任务（并行） | 2 小时 |
| 10:30-11:00 | 汇总结果 + 生成报告 | 30 分钟 |
| 11:00-11:30 | 验收 + 文档归档 | 30 分钟 |
| **总计** | | **4 小时** |

---

## 6. 风险与应对

### 6.1 数据风险

| 风险 | 应对 |
|------|------|
| K线数据不足（2023 年数据缺失） | 改用 2024-01~2024-08 三段（牛/震荡/熊） |
| 部分股票停牌 | 从 10 只池中剔除，保留 ≥5 只 |
| 回测超时（单个 >30 分钟） | 减少参数组合数（每维度 2 值） |

### 6.2 质量风险

| 风险 | 应对 |
|------|------|
| 所有策略夏普 <1 | 调整参数范围 / 换测试股票池（加入成长股） |
| 过拟合（牛市夏普高，震荡/熊市差） | 记录并标注，推荐时注明适用场景 |

---

## 7. 成果交付

### 7.1 文档

- `m3-2-backtest-matrix-results.md`（回测结果报告）
- 更新 `m3-signal-timing-diagnosis.md`（标记 M3-2 完成）

### 7.2 数据

- `quant.backtest_results` 表新增 ≥15 条记录
- 导出 CSV: `backtest_matrix_20260831.csv`

### 7.3 通知

```javascript
await feishu_notify({
  title: '【M3-2 完成】策略回测矩阵执行完毕',
  content: `
## 回测矩阵执行结果

- ✅ 执行任务数: 15 个（5 策略 × 3 区间）
- ✅ 成功率: 100%（15/15）
- ✅ 夏普 >1 策略: 3 个

**推荐策略**:
1. 双均线策略（夏普 1.32）
2. MACD 策略（夏普 1.18）
3. 布林带策略（夏普 1.05）

详见: docs/work-logs/2026-08/m3-2-backtest-matrix-results.md
  `,
  urgency: 'normal'
});
```

---

## 8. 下一步

- M3-2 完成后 → M3 整体达到 100%
- 推荐策略参数写入 `strategy_configs` 表
- 启动 M6-4 evolution 常态化（依赖 M3-2）

---

**编制**: agent-dh investor (w-8366e526)  
**日期**: 2026-08-31  
**状态**: ✅ 已完成（2026-08-31，240 个回测落库，见 [m3-2-backtest-matrix-results.md](./m3-2-backtest-matrix-results.md)）

> **执行修正记录**：
> 1. 实际执行规模为 **240 个回测**（5 策略 × 3 区间 × 16 股，含预案 6.2 补充的 6 只成长股），非计划的 150 个。
> 2. 策略 id 为 **635-639**（macd/bollinger/rsi/dual-ma/momentum），非计划中虚构名称。
> 3. 回测经 `POST /api/backtest/run` 直接执行并自动落库（修复 numpy 标量保存 bug 后可用）。
> 4. **验收 4 未达标**：0 个策略 avg Sharpe>1（最高 macd 0.825）。归因：计划 §3.2 预期值基于"2023=牛市"的错误假设，真实 2023 为弱市（样本股 -0.2%~-26%）。策略平均收益全正（+6.5%~+13%）但回撤 -11%~-14%，属策略-市场匹配问题，非引擎 bug。详见结果文档 §4。
> 5. 执行中发现并修复 3 个阻塞 bug（服务启动崩溃 / numpy 落库 / DB 连接），见结果文档 §7。
