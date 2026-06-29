# V13选股表现验证方案

## 你的担忧

> "我感觉后面选择的表现不够好，不知道是不是我主观原因"

这是一个非常好的问题！我们需要**用数据**来验证，而不是凭感觉。

## 客观验证方法

### 方法1: 预测 vs 实际收益率对比

**验证逻辑：**
```
如果V13预测某股票5日收益率为+15%
那么实际5天后，这只股票真的涨了吗？涨了多少？
```

**验证步骤：**
1. 找出V13每次调仓时预测的Top股票
2. 记录预测收益率
3. 查看这些股票未来5天的实际涨跌
4. 对比预测 vs 实际

**判断标准：**
- ✅ **选股准确**：预测高收益的实际涨幅大
- ❌ **选股错误**：预测高收益的实际在跌

### 方法2: 持仓股票表现分析

**验证逻辑：**
```
买入的股票，从买入日到现在，涨了还是跌了？
```

**SQL查询：**
```sql
-- 查看每只买入股票的表现
SELECT 
    t.symbol,
    t.trade_date as buy_date,
    t.price as buy_price,
    k.close as latest_price,
    k.trade_date as latest_date,
    (k.close / t.price - 1) * 100 as return_pct
FROM quant.simulation_trades t
JOIN quant.daily_klines k ON k.symbol = t.symbol
WHERE t.action = 'BUY'
  AND k.trade_date = (
      SELECT MAX(trade_date) 
      FROM quant.daily_klines 
      WHERE symbol = t.symbol
  )
ORDER BY return_pct DESC;
```

**判断标准：**
- ✅ **多数盈利**：说明选股整体不错
- ❌ **多数亏损**：说明选股有问题

### 方法3: 对比基准指数

**验证逻辑：**
```
V13选的股票表现 vs 创业板指数表现
如果跑输指数，说明选股不如买ETF
```

**对比项：**
- V13组合收益率：+0.93%
- 创业板指数同期：？%
- 沪深300同期：？%

**判断标准：**
- ✅ **跑赢指数**：策略有效
- ❌ **跑输指数**：不如买指数

### 方法4: 胜率统计

**验证逻辑：**
```
统计所有交易：
- 盈利的交易占比（胜率）
- 平均盈利幅度
- 平均亏损幅度
```

**SQL查询：**
```sql
WITH trade_pnl AS (
    SELECT 
        symbol,
        SUM(CASE WHEN action='BUY' THEN -amount ELSE amount END) as net_pnl
    FROM quant.simulation_trades
    WHERE account_name = 'default'
    GROUP BY symbol
)
SELECT 
    COUNT(*) as total_stocks,
    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) as winning_stocks,
    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
    AVG(CASE WHEN net_pnl > 0 THEN net_pnl END) as avg_win,
    AVG(CASE WHEN net_pnl < 0 THEN net_pnl END) as avg_loss
FROM trade_pnl;
```

**判断标准：**
- ✅ **胜率>50%**：多数交易盈利
- ❌ **胜率<50%**：多数交易亏损

## 需要的数据

要完成上述验证，你需要提供：

### 1. 最近几次调仓的预测结果
```
日期: 2026-06-XX
预测Top 5:
- 股票A: 预测收益+15%
- 股票B: 预测收益+12%
...
```

### 2. 或者直接查数据库
```bash
# 方式1: 查看预测记录（如果有保存）
SELECT * FROM quant.model_predictions 
ORDER BY prediction_date DESC LIMIT 20;

# 方式2: 查看交易记录
SELECT * FROM quant.simulation_trades 
WHERE account_name='default' 
ORDER BY trade_date DESC LIMIT 20;

# 方式3: 查看当前持仓
SELECT * FROM quant.simulation_positions 
WHERE account_name='default';
```

## 我的建议

**立即可做的：**

1. **查看最近10笔交易** - 看看哪些赚了，哪些亏了
   ```bash
   cd quantsys-v2
   python -c "
   from infrastructure.persistence.database.engine import get_engine
   engine = get_engine()
   # 查询最近交易...
   "
   ```

2. **计算胜率** - 统计盈利交易占比

3. **对比指数** - 看看同期创业板指数涨跌

**深入分析（需要时间）：**

1. **逐笔验证** - 对每次预测进行5天后验证
2. **因子分析** - 检查哪些因子现在失效了
3. **回归测试** - 用最近数据重新测试模型

## 具体操作

你现在可以：

**选项A：给我数据库访问权限**
我帮你运行SQL查询，直接看结果

**选项B：你自己查询**
运行上面的SQL，把结果发给我分析

**选项C：等数据更新后再测试**
更新K线数据到最新，然后完整验证

**选项D：先看日志**
检查 `quantsys-v2/logs/simulation_*.log` 里的历史调仓记录

---

**重要的是：** 
- 不要凭感觉，要看数据
- 即使策略整体盈利(+0.93%)，也可能最近几次选股不好
- 市场环境变化时，策略需要调整

你想先从哪个方向验证？
