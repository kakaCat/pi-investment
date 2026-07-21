# V13策略模拟交易系统 - 使用指南

## 系统概述

V13策略的完整模拟交易系统，已实现所有核心功能。

**当前状态**: ✅ 功能完整，可以使用

## 目录结构

```
live_trading/
├── config_simulation.yaml      # 配置文件
├── simulation_trader.py        # 主交易引擎（完整）
├── simulation_broker.py        # 模拟券商接口（完整）
├── factor_calculator.py        # 因子计算器（完整）
├── v13_factors.py             # 85个因子函数（完整）
├── README.md                   # 本文件
├── data/                       # 数据存储
│   ├── positions.json         # 持仓数据
│   └── trades.csv             # 交易记录
├── logs/                       # 运行日志
├── models/                     # 模型文件
│   ├── v13_model.json        # XGBoost模型
│   └── valid_factors.json    # 有效因子列表
└── reports/                    # 每日报告
```

## 快速开始

### 步骤1: 首次训练模型

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python live_trading/simulation_trader.py
```

选择 `1. 训练模型`

**训练过程**：
- 获取200只创业板股票
- 加载2024-06-01至2025-06-30的历史数据
- 计算85个因子
- 筛选有效因子（IC > 0.02）
- 训练XGBoost模型
- 保存模型到 `models/v13_model.json`

**预计时间**：3-5分钟

### 步骤2: 执行模拟交易

```bash
python live_trading/simulation_trader.py
```

选择 `2. 加载模型` → `3. 执行每日检查`

**执行流程**：
1. 检查是否到调仓日（每5天）
2. 获取最新数据并计算85个因子
3. 模型预测Top 5股票
4. 执行模拟交易
5. 保存持仓和生成报告

### 步骤3: 查看结果

```bash
python live_trading/simulation_trader.py
```

选择 `4. 查看持仓` 或 `5. 查看交易记录`

## 实现状态

### ✅ 已完成（全部核心功能）

**基础设施**：
- [x] 配置系统（YAML）
- [x] 日志系统
- [x] 持仓管理（保存/加载）
- [x] 数据存储（JSON/CSV）

**数据层**：
- [x] 通过DataService获取数据库数据
- [x] 85个因子计算（从V13提取）
- [x] 最新因子获取

**模型层**：
- [x] 模型训练（XGBoost）
- [x] 因子筛选（IC > 0.02）
- [x] 模型保存/加载
- [x] 模型预测

**交易层**：
- [x] 模拟券商接口
- [x] 买卖交易（手续费+滑点+印花税）
- [x] 持仓调整
- [x] 交易记录

**策略层**：
- [x] 调仓周期检测（5天）
- [x] Top 5选股
- [x] 止盈止损风控
- [x] 仓位动态调整

**监控层**：
- [x] 每日报告生成
- [x] 持仓状态监控
- [x] 交易历史查询

## 使用流程

### 初次使用（完整流程）

```bash
# 1. 训练模型（首次必须）
python live_trading/simulation_trader.py
# 选择 1 → 等待训练完成

# 2. 首次调仓
python live_trading/simulation_trader.py
# 选择 2 → 加载模型
# 选择 3 → 执行每日检查（会立即调仓）

# 3. 查看结果
python live_trading/simulation_trader.py
# 选择 4 → 查看持仓
# 选择 5 → 查看交易记录
```

### 日常使用（每天执行）

```bash
python live_trading/simulation_trader.py
# 选择 2 → 加载模型
# 选择 3 → 执行每日检查
```

**系统会自动判断**：
- 如果未到调仓日：显示"距离下次调仓还有X天"
- 如果到了调仓日：自动执行调仓

### 数据架构

**数据流**：
```
数据库（PostgreSQL）
    ↓
DataService.kline.get_stock_kline()
    ↓
最近100天K线数据
    ↓
v13_factors.calculate_v13_factors()
    ↓
85个因子
    ↓
XGBoost模型预测
    ↓
Top 5股票
    ↓
SimulationBroker执行交易
```

**不会重新获取数据**：
- ✅ 使用数据库中已有的数据
- ✅ 通过DataService标准接口
- ❌ 不直接调用akshare
- ❌ 不重复下载数据

## 配置说明

编辑 `config_simulation.yaml`：

```yaml
# 初始资金
initial_capital: 100000  # 10万模拟资金

# 策略参数
strategy:
  rebalance_days: 5      # 调仓周期
  top_n: 5               # 持仓数量
  position_weight: 0.18  # 单只股票18%

# 交易成本
trading:
  commission_rate: 0.0003  # 万3手续费
  slippage_rate: 0.001     # 千1滑点

# 止盈策略
take_profit_levels:
  - threshold: 0.50      # 50%收益
    position: 0.4        # 减仓到40%
  - threshold: 0.40      # 40%收益
    position: 0.6        # 减仓到60%
  - threshold: 0.30      # 30%收益
    position: 0.8        # 减仓到80%

# 止损策略
drawdown_stops:
  - threshold: -0.20     # -20%回撤
    position: 0.3        # 减仓到30%
  - threshold: -0.15     # -15%回撤
    position: 0.6        # 减仓到60%
  - threshold: -0.10     # -10%回撤
    position: 0.8        # 减仓到80%
```

## 文件说明

### 核心模块

**simulation_trader.py** - 主交易引擎
- 模型训练和加载
- 每日调仓检查
- 交易执行
- 报告生成

**v13_factors.py** - 85个因子
- 从V13脚本提取
- 25个技术因子
- 18个基本面因子
- 10个资金流因子
- 32个高级因子

**factor_calculator.py** - 因子计算器
- 通过DataService获取数据
- 调用v13_factors计算因子
- 返回最新因子值

**simulation_broker.py** - 模拟券商
- 买卖交易
- 手续费计算（万3）
- 滑点模拟（千1）
- 印花税（千1，仅卖出）

### 数据文件

**data/positions.json** - 持仓数据
```json
{
  "cash": 50000,
  "portfolio": {
    "300750": {
      "shares": 100,
      "avg_price": 150.5
    }
  },
  "peak_value": 110000,
  "last_rebalance_date": "2026-06-20"
}
```

**models/v13_model.json** - XGBoost模型
- 训练好的模型参数
- 直接加载即可使用

**models/valid_factors.json** - 有效因子
```json
["momentum_5d", "volatility_5d", "rsi_14", ...]
```

**reports/daily_YYYY-MM-DD.json** - 每日报告
```json
{
  "date": "2026-06-20",
  "cash": 50000,
  "total_value": 110000,
  "return": 0.10,
  "drawdown": -0.05
}
```

## 常见问题

### Q: 模型训练报错？
**A**: 检查数据库连接，确保quant_investment数据库有数据

### Q: 因子计算失败？
**A**: 需要至少100天的历史数据，确保数据库数据完整

### Q: 如何重新训练模型？
**A**: 删除 `models/v13_model.json`，然后选择"1. 训练模型"

### Q: 调仓频率可以改吗？
**A**: 可以，修改 `config_simulation.yaml` 中的 `rebalance_days`

### Q: 可以修改持仓数量吗？
**A**: 可以，修改 `config_simulation.yaml` 中的 `top_n`

### Q: 如何清空持仓重新开始？
**A**: 删除 `data/positions.json`

## 与回测结果对比

### V13回测结果（理论）
- 年化收益：58.99%
- 最大回撤：-7.16%
- 夏普比率：2.54

### 模拟盘预期（保守）
- 年化收益：≈40-45%（回测的70-75%）
- 最大回撤：≈-10%~-12%（略大于回测）
- 原因：实际滑点、数据延迟、执行偏差

## 下一步

### 方案1：继续模拟验证（1-2个月）
- 每天运行系统
- 记录模拟交易
- 对比回测结果
- 发现并修复问题

### 方案2：小资金实盘（3-6个月）
- 接入真实券商API
- 5-10万真实资金
- 逐步建立信心
- 验证策略有效性

### 方案3：手动执行（立即开始）
- 系统生成信号
- 人工复核
- 券商APP下单
- Excel记录

## 技术支持

需要帮助？告诉我：
1. "模型训练失败" - 排查训练问题
2. "因子计算报错" - 检查数据问题
3. "交易执行异常" - 调试交易逻辑
4. "接入真实券商" - 实盘API对接
