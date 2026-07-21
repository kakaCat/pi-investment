# V13模拟交易系统 - 数据库版升级完成

## 升级内容

### ✅ 已完成的改进

1. **创建数据库表**
   - `simulation_account` - 账户状态表
   - `simulation_positions` - 持仓表
   - `simulation_trades` - 交易记录表
   - `simulation_daily_reports` - 每日报告表

2. **使用实时数据接口**
   - `factor_calculator.py` - 改用 `ds.kline.get_latest()`
   - `simulation_trader.py` - 改用 `ds.kline.get_latest_daily_kline()`

3. **创建Repository层**
   - `simulation_repository.py` - 完整的数据库操作接口

4. **重构交易系统**
   - 所有状态保存到数据库
   - 交易记录自动持久化
   - 每日报告自动保存

## 架构对比

### 旧版（JSON文件）
```
数据存储: positions.json + trades.csv
数据获取: get_stock_kline(start_date, end_date)
持久化: 手动保存JSON
查询: 读取文件
```

### 新版（数据库）
```
数据存储: PostgreSQL表
数据获取: get_latest(limit) / get_latest_daily_kline()
持久化: 自动保存到数据库
查询: SQL查询，支持复杂统计
```

## 使用方法

### 1. 初始化数据库（仅首次）

数据库表已自动创建，无需手动操作。

### 2. 使用新版系统

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python live_trading/simulation_trader.py
```

**新增功能**：
- 选项6: 查看每日报告（从数据库）
- 所有数据自动保存到数据库
- 支持SQL查询统计

### 3. 数据查询示例

```sql
-- 查看账户状态
SELECT * FROM quant.simulation_account WHERE account_name = 'default';

-- 查看当前持仓
SELECT * FROM quant.simulation_positions 
WHERE account_name = 'default' AND shares > 0
ORDER BY market_value DESC;

-- 查看交易记录
SELECT * FROM quant.simulation_trades 
WHERE account_name = 'default' 
ORDER BY trade_time DESC 
LIMIT 20;

-- 查看每日收益曲线
SELECT 
    report_date,
    total_value,
    cumulative_return,
    drawdown
FROM quant.simulation_daily_reports
WHERE account_name = 'default'
ORDER BY report_date DESC
LIMIT 30;

-- 统计交易次数和手续费
SELECT 
    COUNT(*) as trade_count,
    SUM(commission) + SUM(COALESCE(stamp_duty, 0)) as total_cost
FROM quant.simulation_trades
WHERE account_name = 'default';

-- 每日交易统计
SELECT 
    trade_date,
    COUNT(*) as trades,
    SUM(CASE WHEN action = 'BUY' THEN amount ELSE 0 END) as buy_amount,
    SUM(CASE WHEN action = 'SELL' THEN amount ELSE 0 END) as sell_amount
FROM quant.simulation_trades
WHERE account_name = 'default'
GROUP BY trade_date
ORDER BY trade_date DESC;
```

## 数据流

```
1. 获取数据
   Database → DataService.kline.get_latest() → 最近100条K线

2. 计算因子
   K线数据 → v13_factors.calculate_v13_factors() → 85个因子

3. 模型预测
   因子 → XGBoost → Top 5股票

4. 执行交易
   交易 → SimulationBroker → SimulationRepository → Database

5. 保存报告
   报告 → SimulationRepository.save_daily_report() → Database
```

## 新增的Repository方法

### 账户管理
- `get_account()` - 获取账户信息
- `update_account()` - 更新账户状态

### 持仓管理
- `get_all_positions()` - 获取所有持仓
- `get_position(symbol)` - 获取单个持仓
- `upsert_position()` - 插入或更新持仓
- `delete_position()` - 删除持仓
- `update_position_prices()` - 批量更新价格

### 交易记录
- `add_trade()` - 添加交易记录
- `get_trades(limit)` - 获取交易记录
- `get_trade_count()` - 统计交易次数
- `get_total_commission()` - 计算总手续费

### 每日报告
- `save_daily_report()` - 保存每日报告
- `get_daily_reports(limit)` - 获取报告列表
- `get_latest_report()` - 获取最新报告

## 优势

### 1. 数据持久化
- ✅ 所有数据自动保存数据库
- ✅ 不会丢失
- ✅ 支持回溯查询

### 2. 实时数据
- ✅ 使用 `get_latest()` 接口
- ✅ 减少不必要的日期计算
- ✅ 更符合实时交易场景

### 3. 查询能力
- ✅ SQL统计分析
- ✅ 复杂查询
- ✅ 数据可视化准备

### 4. 多账户支持
- ✅ 通过 `account_name` 区分
- ✅ 可以运行多个策略
- ✅ 方便对比测试

## 兼容性

### 保留的功能
- ✅ JSON文件报告（兼容旧版）
- ✅ 配置文件格式不变
- ✅ 模型文件格式不变

### 变更的部分
- ❌ 不再使用 `positions.json`
- ❌ 不再使用 `trades.csv`
- ✅ 改用数据库查询

## 下一步

系统已完整升级，可以：

1. **开始测试**
   ```bash
   python live_trading/simulation_trader.py
   # 选择 1 训练模型
   # 选择 3 执行每日检查
   ```

2. **查看数据**
   ```bash
   # 选择 4 查看持仓
   # 选择 5 查看交易记录
   # 选择 6 查看每日报告
   ```

3. **SQL分析**
   ```bash
   psql -U mac -d quant_investment
   # 执行上面的查询示例
   ```

## 问题排查

### Q: 找不到数据库表？
A: 运行 `create_simulation_tables.sql` 创建表

### Q: 报错"connection refused"？
A: 检查PostgreSQL是否运行

### Q: 数据为空？
A: 首次使用需要先训练模型并执行调仓

### Q: 想清空数据重新开始？
A: 
```sql
TRUNCATE quant.simulation_trades, 
         quant.simulation_positions, 
         quant.simulation_daily_reports;
UPDATE quant.simulation_account 
SET cash = 100000, total_value = 100000, peak_value = 100000 
WHERE account_name = 'default';
```

## 文件清单

```
live_trading/
├── create_simulation_tables.sql   # 数据库表创建脚本 ✅
├── simulation_repository.py       # 数据库Repository ✅
├── factor_calculator.py           # 因子计算器（已升级）✅
├── simulation_trader.py           # 主交易引擎（已升级）✅
├── simulation_broker.py           # 模拟券商（不变）
├── v13_factors.py                 # 85个因子（不变）
├── config_simulation.yaml         # 配置文件（不变）
└── README.md                      # 使用说明（待更新）
```

系统已全面升级完成！
