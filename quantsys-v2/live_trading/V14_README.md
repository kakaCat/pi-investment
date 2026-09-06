# V14 策略工具使用指南

**策略版本**: V14 (多因子量化选股)  
**更新日期**: 2026-09-06  
**目录**: `quantsys-v2/live_trading/`

---

## 概述

V14 是基于机器学习的多因子选股策略，使用 XGBoost 模型预测股票未来收益。本文档说明 live_trading/ 目录中所有 V14 相关工具的用途和使用方法。

### 策略特点

- **模型**: XGBoost 回归
- **因子**: 85+ 个技术/基本面/资金流因子
- **持仓**: Top 5 股票
- **调仓周期**: 5 天
- **目标市场**: 创业板

---

## 工具分类

### 📊 1. 训练工具（7 个）

#### 1.1 `train_v14_model.py` ✅ **主版本**

**用途**: V14 模型标准训练流程

**功能**:
- 获取创业板股票历史数据
- 计算 85+ 个因子
- 训练 XGBoost 模型
- 保存模型到 `models/v14_model.json`

**使用**:
```bash
python live_trading/train_v14_model.py
```

**参数**（代码内配置）:
- `train_start`: 训练开始日期（默认 2024-01-01）
- `train_end`: 训练结束日期（默认 2025-12-31）
- `n_stocks`: 股票数量（默认 200）

**输出**:
- `models/v14_model.json` - 训练好的模型
- `models/valid_factors.json` - 有效因子列表
- 训练日志

---

#### 1.2 `train_v14_standalone.py`

**用途**: 独立训练版本（不依赖 DataService）

**使用场景**: 离线训练、数据迁移测试

**使用**:
```bash
python live_trading/train_v14_standalone.py
```

**区别**: 
- ✅ 直接读取本地数据文件
- ❌ 不连接数据库

---

#### 1.3 `train_v14_p0_optimized.py`

**用途**: P0 参数优化版本

**优化内容**:
- 超参数网格搜索
- 交叉验证
- 特征选择

**使用**:
```bash
python live_trading/train_v14_p0_optimized.py
```

---

#### 1.4 `train_optimized_model.py`

**用途**: 通用优化训练框架

**功能**:
- Optuna 超参数优化
- 自动保存最佳模型

**使用**:
```bash
python live_trading/train_optimized_model.py --trials 100
```

---

#### 1.5 `train_expanded_model.py`

**用途**: 扩展因子池训练

**新增因子**:
- 高级技术指标
- 市场微观结构因子
- 另类数据因子

---

#### 1.6 `validate_model_ic.py` ✅ **验证必备**

**用途**: 验证模型 IC（信息系数）

**使用**:
```bash
python live_trading/validate_model_ic.py --model models/v14_model.json
```

**输出**:
- IC 值（目标 > 0.05）
- IC_IR 值（目标 > 1.0）
- 因子重要性排名

**示例输出**:
```
Model IC: 0.0823
IC_IR: 1.45
Top Factors:
  1. momentum_20d: 0.156
  2. volatility_5d: 0.134
  3. rsi_14: 0.112
```

---

#### 1.7 `calculate_v14_ic_ir.py`

**用途**: 批量计算 IC/IR 指标

**使用**:
```bash
python live_trading/calculate_v14_ic_ir.py --start 2025-01-01 --end 2026-08-31
```

**输出**: IC 时间序列图表

---

### 🔬 2. 回测工具（6 个）

#### 2.1 `backtest_v14_quick.py` ✅ **快速验证**

**用途**: 快速回测（少量股票，短周期）

**使用**:
```bash
python live_trading/backtest_v14_quick.py
```

**配置**:
- 股票数: 50
- 时间段: 最近 6 个月
- 输出: 简化指标

**适用场景**: 模型迭代快速验证

---

#### 2.2 `backtest_v14_p0.py`

**用途**: P0 版本回测

**使用**:
```bash
python live_trading/backtest_v14_p0.py
```

---

#### 2.3 `backtest_v14_optimized.py` ✅ **标准回测**

**用途**: 完整回测流程

**功能**:
- 滑点模拟
- 手续费计算
- 完整绩效指标

**使用**:
```bash
python live_trading/backtest_v14_optimized.py --start 2025-01-01 --end 2026-08-31
```

**输出**:
```
Total Return: 45.23%
Annualized Return: 38.45%
Max Drawdown: -8.56%
Sharpe Ratio: 2.34
Win Rate: 62%
Total Trades: 24
```

---

#### 2.4 `backtest_v14_optimized_full.py`

**用途**: 全市场回测（所有创业板）

**警告**: 运行时间长（2-3 小时）

**使用**:
```bash
python live_trading/backtest_v14_optimized_full.py
```

---

#### 2.5 `backtest_new_model.py`

**用途**: 测试新训练的模型

**使用**:
```bash
python live_trading/backtest_new_model.py --model models/v14_model_new.json
```

---

#### 2.6 `compare_v13_v14.py` ✅ **对比分析**

**用途**: V13 vs V14 性能对比

**使用**:
```bash
python live_trading/compare_v13_v14.py
```

**输出**:
```
Metric          V13      V14      Winner
─────────────────────────────────────────
Return          58.99%   45.23%   V13
Max Drawdown    -7.16%   -8.56%   V13
Sharpe Ratio    2.54     2.34     V13
Win Rate        65%      62%      V13
```

---

### ⚙️ 3. 执行工具（3 个）

#### 3.1 `execute_v14_full_rebalance.py` ⚠️ **生产慎用**

**用途**: 完整调仓（卖出所有 + 买入新标的）

**使用**:
```bash
python live_trading/execute_v14_full_rebalance.py --account agent_virtual
```

**警告**: 
- 会清空所有持仓
- 生产环境需要人工确认

---

#### 3.2 `execute_v14_rebalance_fixed.py` ✅ **推荐**

**用途**: 修复版调仓（增量调整）

**功能**:
- 只卖出不在新名单的股票
- 只买入新增的股票
- 保留持仓中仍符合条件的股票

**使用**:
```bash
python live_trading/execute_v14_rebalance_fixed.py --account agent_virtual --dry-run
```

**参数**:
- `--account`: 账户名称
- `--dry-run`: 模拟运行（不实际下单）

---

#### 3.3 `test_v14_rebalance.py`

**用途**: 调仓逻辑测试

**使用**:
```bash
python live_trading/test_v14_rebalance.py
```

---

### 📈 4. 分析工具（4 个）

#### 4.1 `analyze_v14_factors.py` ✅ **因子分析**

**用途**: 分析因子有效性和相关性

**使用**:
```bash
python live_trading/analyze_v14_factors.py --output reports/factor_analysis.html
```

**输出**:
- 因子 IC 排名
- 因子相关性矩阵
- 因子分布图

---

#### 4.2 `v14_factor_calculator.py`

**用途**: 单只股票因子计算

**使用**:
```python
from live_trading.v14_factor_calculator import V14FactorCalculator

calculator = V14FactorCalculator()
factors = calculator.calculate("600519.SH", "2026-09-06")
print(factors)
```

---

#### 4.3 `optimize_annual_return.py`

**用途**: 年化收益优化

**使用**:
```bash
python live_trading/optimize_annual_return.py
```

---

#### 4.4 `optimize_strategy_config.py`

**用途**: 策略配置优化（调仓周期、持仓数等）

**使用**:
```bash
python live_trading/optimize_strategy_config.py --target sharpe_ratio
```

**优化参数**:
- `rebalance_days`: 调仓周期（3/5/10 天）
- `top_n`: 持仓数量（3/5/10 只）
- `position_weight`: 仓位权重

---

### 🔧 5. 诊断工具（2 个）

#### 5.1 `diagnose_data_loss.py`

**用途**: 诊断数据丢失问题

**使用**:
```bash
python live_trading/diagnose_data_loss.py --symbol 600519.SH --date 2026-09-06
```

**检查项**:
- K 线数据完整性
- 因子计算是否有 NaN
- 数据源可用性

---

#### 5.2 `test_risk_integration.py`

**用途**: 风控模块集成测试

**使用**:
```bash
python live_trading/test_risk_integration.py
```

---

### 🛠️ 6. 其他工具

#### 6.1 `multi_source_data_fetcher.py`

**用途**: 多源数据获取器（akshare/tushare/baostock）

**使用**:
```python
from live_trading.multi_source_data_fetcher import MultiSourceDataFetcher

fetcher = MultiSourceDataFetcher()
data = fetcher.get_klines("600519.SH", "2026-01-01", "2026-09-06")
```

---

## 典型工作流

### 工作流 1: 训练新模型

```bash
# 1. 训练模型
python live_trading/train_v14_model.py

# 2. 验证 IC
python live_trading/validate_model_ic.py --model models/v14_model.json

# 3. 快速回测
python live_trading/backtest_v14_quick.py

# 4. 完整回测
python live_trading/backtest_v14_optimized.py

# 5. 与 V13 对比
python live_trading/compare_v13_v14.py
```

### 工作流 2: 因子优化

```bash
# 1. 分析因子
python live_trading/analyze_v14_factors.py

# 2. 训练扩展模型
python live_trading/train_expanded_model.py

# 3. 验证新模型
python live_trading/validate_model_ic.py --model models/v14_expanded.json

# 4. 对比回测
python live_trading/backtest_new_model.py --model models/v14_expanded.json
```

### 工作流 3: 生产执行

```bash
# 1. 模拟调仓（dry-run）
python live_trading/execute_v14_rebalance_fixed.py --account agent_virtual --dry-run

# 2. 检查调仓计划
# （查看输出的买卖清单）

# 3. 执行真实调仓
python live_trading/execute_v14_rebalance_fixed.py --account agent_virtual

# 4. 验证执行结果
curl "http://127.0.0.1:5001/api/positions?account_name=agent_virtual"
```

---

## 配置文件

### `config_simulation.yaml`

```yaml
# V14 策略配置
strategy:
  name: "V14多因子选股"
  version: "1.0"
  
  # 调仓参数
  rebalance_days: 5       # 调仓周期
  top_n: 5                # 持仓数量
  position_weight: 0.18   # 单只股票权重（18%）
  
  # 股票池
  market: "ChiNext"       # 创业板
  min_market_cap: 10      # 最小市值（亿）
  
# 风控参数
risk:
  max_position_pct: 0.25  # 单只最大仓位 25%
  stop_loss: -0.10        # 止损线 -10%
  take_profit: 0.30       # 止盈线 +30%
  
# 交易成本
trading:
  commission_rate: 0.0003  # 万3手续费
  slippage_rate: 0.001     # 千1滑点
  stamp_duty: 0.001        # 千1印花税（仅卖出）
```

---

## 性能基准

### V14 回测结果（2025-01-01 至 2026-08-31）

| 指标 | 值 | 说明 |
|------|-----|------|
| 总收益 | 45.23% | 20 个月 |
| 年化收益 | 38.45% | |
| 最大回撤 | -8.56% | |
| 夏普比率 | 2.34 | > 2 优秀 |
| 胜率 | 62% | |
| 交易次数 | 24 | 平均持仓 5 天 |
| IC | 0.082 | > 0.05 有效 |
| IC_IR | 1.45 | > 1.0 稳定 |

---

## 常见问题

### Q1: 训练模型需要多长时间？

**A**: 
- 快速训练（50 股票）: 2-3 分钟
- 标准训练（200 股票）: 10-15 分钟
- 完整训练（全市场）: 1-2 小时

### Q2: IC 值多少算合格？

**A**:
- IC > 0.05: 有效
- IC > 0.08: 良好
- IC > 0.10: 优秀

### Q3: V13 和 V14 哪个更好？

**A**:
- **V13**: 收益更高（58.99% vs 45.23%），但基于固定规则
- **V14**: 机器学习模型，更灵活，可持续优化
- **建议**: 两者结合使用，分散风险

### Q4: 如何选择调仓周期？

**A**:
- **3 天**: 高频交易，手续费高
- **5 天**: 平衡（推荐）
- **10 天**: 低频，更稳定

### Q5: 模型需要多久重新训练？

**A**:
- **推荐**: 每月重新训练一次
- **触发条件**: IC 持续下降 < 0.03 时立即重新训练

---

## 脚本状态标记

| 脚本 | 状态 | 推荐使用 |
|------|------|---------|
| `train_v14_model.py` | ✅ 生产 | 是 |
| `train_v14_standalone.py` | ⚠️ 实验 | 否 |
| `train_v14_p0_optimized.py` | ⚠️ 实验 | 否 |
| `train_optimized_model.py` | ⚠️ 开发中 | 否 |
| `train_expanded_model.py` | ⚠️ 开发中 | 否 |
| `validate_model_ic.py` | ✅ 生产 | 是 |
| `calculate_v14_ic_ir.py` | ✅ 生产 | 是 |
| `backtest_v14_quick.py` | ✅ 生产 | 是 |
| `backtest_v14_p0.py` | ⚠️ 实验 | 否 |
| `backtest_v14_optimized.py` | ✅ 生产 | 是 |
| `backtest_v14_optimized_full.py` | ✅ 生产 | 是 |
| `backtest_new_model.py` | ✅ 生产 | 是 |
| `compare_v13_v14.py` | ✅ 生产 | 是 |
| `execute_v14_full_rebalance.py` | ⚠️ 慎用 | 否 |
| `execute_v14_rebalance_fixed.py` | ✅ 生产 | 是 |
| `test_v14_rebalance.py` | ✅ 测试 | 是 |
| `analyze_v14_factors.py` | ✅ 生产 | 是 |
| `v14_factor_calculator.py` | ✅ 生产 | 是 |
| `optimize_annual_return.py` | ⚠️ 实验 | 否 |
| `optimize_strategy_config.py` | ⚠️ 实验 | 否 |
| `diagnose_data_loss.py` | ✅ 工具 | 是 |
| `test_risk_integration.py` | ✅ 测试 | 是 |

---

## 下一步

- 📖 查看 [V13 模拟交易系统文档](../live_trading/README.md)
- 📖 阅读 [策略回测指南](../docs/guides/BACKTEST-GUIDE.md)
- 📖 学习 [因子工程](../docs/guides/FACTOR-ENGINEERING.md)

---

**文档版本**: 1.0  
**最后更新**: 2026-09-06  
**维护者**: quantsys-v2 团队
