# 策略回测验证脚本使用指南

## 概述

`weekly_backtest.py` 是一个全面的策略回测验证工具，用于评估量化交易策略的历史表现。

## 功能特性

### 1. 数据准备
- 从SQLite数据库读取历史K线数据
- 支持指定日期范围或最近N天
- 自动处理数据格式转换

### 2. 策略回测
目前支持的策略：
- **RSI反转策略**: 基于相对强弱指标的均值回归策略
- **均线突破策略**: 基于移动平均线交叉的趋势跟踪策略
- **布林带策略**: 基于布林带的突破/反转策略

待添加策略：
- MACD策略
- KDJ策略

### 3. 绩效指标
计算以下关键指标：
- **收益指标**: 总回报率、年化收益率
- **风险指标**: 最大回撤、波动率
- **风险调整收益**: 夏普比率、Sortino比率、Calmar比率
- **交易统计**: 胜率、盈亏比、交易次数
- **期望值**: 平均盈利、平均亏损

### 4. 报告生成
- **JSON报告**: 包含完整的回测数据和指标
- **Markdown报告**: 人类可读的格式化报告
- 策略排名和对比表格
- 优化建议

## 使用方法

### 基本用法

```bash
# 回测最近30天
python scripts/weekly_backtest.py --symbol 000001 --days 30

# 回测最近60天，初始资金200万
python scripts/weekly_backtest.py --symbol 000001 --days 60 --capital 2000000

# 指定日期范围
python scripts/weekly_backtest.py --symbol 000001 --start 2026-04-01 --end 2026-05-18
```

### 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--symbol` | str | 000001 | 股票代码 |
| `--days` | int | 30 | 回测最近N天 |
| `--start` | str | - | 开始日期 (YYYY-MM-DD) |
| `--end` | str | - | 结束日期 (YYYY-MM-DD) |
| `--capital` | float | 1000000 | 初始资金 |
| `--commission` | float | 0.0003 | 手续费率 (0.03%) |
| `--slippage` | float | 0.001 | 滑点率 (0.1%) |

### 示例

#### 1. 快速回测（默认参数）
```bash
python scripts/weekly_backtest.py
```

#### 2. 自定义回测期间
```bash
python scripts/weekly_backtest.py --symbol 000001 --days 90
```

#### 3. 完整参数回测
```bash
python scripts/weekly_backtest.py \
  --symbol 000001 \
  --start 2026-01-01 \
  --end 2026-05-18 \
  --capital 5000000 \
  --commission 0.0002 \
  --slippage 0.0005
```

## 输出文件

### 1. JSON报告
文件名: `backtest_report_{symbol}_{date}.json`

位置: `quant/.pi-invest/`

内容结构:
```json
{
  "report_date": "2026-05-18",
  "symbol": "000001",
  "backtest_period": {
    "start": "2026-04-18",
    "end": "2026-05-18"
  },
  "backtest_config": {
    "initial_capital": 1000000.0,
    "commission": 0.0003,
    "slippage": 0.001
  },
  "results": [
    {
      "strategy_name": "RSI反转",
      "total_return": 0.085,
      "sharpe_ratio": 1.85,
      "max_drawdown": 0.032,
      "win_rate": 0.65,
      "total_trades": 12,
      ...
    }
  ]
}
```

### 2. Markdown报告
文件名: `backtest_report_{symbol}_{date}.md`

位置: `quant/.pi-invest/`

包含内容:
- 回测参数
- 策略表现对比表格
- 最佳策略详情
- 优化建议
- 注意事项

## 回测报告示例

```markdown
# 策略回测报告 - 2026-05-18

## 回测参数
- 股票代码: 000001
- 回测期间: 2026-04-18 至 2026-05-18 (30天)
- 初始资金: 1,000,000元
- 手续费: 0.03%
- 滑点: 0.1%

## 策略表现

| 排名 | 策略 | 总回报 | 夏普比率 | 最大回撤 | 胜率 | 交易次数 |
|------|------|--------|----------|----------|------|----------|
| 1 | RSI反转 | +8.5% | 1.85 | -3.2% | 65% | 12 |
| 2 | 均线突破 | +5.2% | 1.42 | -4.1% | 58% | 8 |
| 3 | 布林带 | +3.8% | 1.15 | -5.3% | 52% | 15 |

## 最佳策略
RSI反转策略表现最佳，建议继续使用。

## 优化建议
- 布林带策略胜率较低，建议调整参数
- 均线突破策略交易次数较少，可能错过机会
```

## 策略参数说明

### RSI反转策略
```python
{
    'rsi_period': 14,           # RSI计算周期
    'oversold_threshold': 30,   # 超卖阈值
    'overbought_threshold': 70, # 超买阈值
    'stop_loss_pct': 0.05,      # 止损比例 (5%)
    'take_profit_pct': 0.10     # 止盈比例 (10%)
}
```

### 均线突破策略
```python
{
    'fast_period': 5,           # 快速均线周期
    'slow_period': 20,          # 慢速均线周期
    'stop_loss_pct': 0.05,      # 止损比例 (5%)
    'take_profit_pct': 0.15     # 止盈比例 (15%)
}
```

### 布林带策略
```python
{
    'period': 20,               # 布林带周期
    'num_std': 2.0,             # 标准差倍数
    'stop_loss_pct': 0.05,      # 止损比例 (5%)
    'take_profit_pct': 0.10     # 止盈比例 (10%)
}
```

## 回测引擎配置

### 交易成本
- **手续费**: 默认0.03% (万三)
- **滑点**: 默认0.1% (千一)

### 资金管理
- 每次交易使用99.9%的可用资金
- 预留0.1%用于手续费
- 自动计算最大可买入股数

### 信号执行
- 买入: 价格 × (1 + 滑点)
- 卖出: 价格 × (1 - 滑点)
- 按时间顺序逐条处理K线数据

## 优化建议解读

脚本会自动生成优化建议，包括：

### 1. 胜率相关
- **胜率 < 40%**: 建议调整参数或增加过滤条件
- **胜率 > 60%**: 策略表现良好

### 2. 交易频率
- **交易次数 < 3**: 可能错过机会，建议放宽条件
- **交易次数 > 50**: 交易过于频繁，建议提高信号质量

### 3. 风险控制
- **最大回撤 > 15%**: 建议加强风险控制
- **最大回撤 < 10%**: 风险控制良好

### 4. 风险调整收益
- **夏普比率 < 1.0**: 风险调整后收益不佳
- **夏普比率 > 1.5**: 优秀的风险调整收益
- **夏普比率 > 2.0**: 卓越表现

## 注意事项

### 1. 数据要求
- 确保数据库中有足够的历史数据
- RSI策略至少需要14天数据
- 均线策略至少需要20天数据
- 布林带策略至少需要20天数据

### 2. 回测局限性
- 回测结果基于历史数据，不代表未来表现
- 未考虑市场冲击成本
- 未考虑极端行情下的流动性问题
- 假设所有订单都能成交

### 3. 实盘差异
- 实际交易中滑点可能更大
- 可能面临部分成交或无法成交
- 需要考虑资金容量限制
- 市场环境变化可能影响策略有效性

### 4. 使用建议
- 定期运行回测评估策略表现
- 结合多个时间周期进行验证
- 关注策略在不同市场环境下的表现
- 根据回测结果调整策略参数
- 建议先进行模拟交易验证

## 集成到工作流

### 1. 每周定期回测
```bash
# 添加到crontab
0 9 * * 1 cd /path/to/quant && python scripts/weekly_backtest.py --days 30
```

### 2. 与其他脚本配合
```bash
# 先更新数据，再运行回测
python scripts/daily_update.py
python scripts/weekly_backtest.py --days 30
```

### 3. 批量回测多只股票
```bash
# 创建批量回测脚本
for symbol in 000001 000002 600000 600036; do
    python scripts/weekly_backtest.py --symbol $symbol --days 60
done
```

## 扩展开发

### 添加新策略

1. 在 `quantsys/strategies/classic/` 创建新策略文件
2. 继承 `BaseStrategy` 类
3. 实现 `calculate_signals()` 方法
4. 在 `weekly_backtest.py` 中注册策略:

```python
from quantsys.strategies.classic.macd import MACDStrategy

# 在 get_available_strategies() 中添加
strategies = [
    # ... 现有策略 ...
    ('MACD', MACDStrategy, {
        'fast_period': 12,
        'slow_period': 26,
        'signal_period': 9
    }),
]
```

### 自定义绩效指标

修改 `quantsys/strategies/utils.py` 中的 `generate_backtest_report()` 函数添加新指标。

### 自定义报告格式

修改 `WeeklyBacktester.generate_markdown_report()` 方法自定义报告内容和格式。

## 故障排除

### 问题1: 没有数据
```
错误: 加载 000001 数据失败
解决: 先运行 python scripts/fetch_hs300_data.py 获取数据
```

### 问题2: 交易次数为0
```
原因: 回测期间太短，策略未产生信号
解决: 增加 --days 参数，建议至少60天
```

### 问题3: 导入错误
```
错误: ModuleNotFoundError: No module named 'quantsys'
解决: 确保在 quant 目录下运行脚本
```

### 问题4: 数据库锁定
```
错误: database is locked
解决: 确保没有其他进程正在访问数据库
```

## 性能优化

### 1. 并行回测
未来可以添加多进程支持，同时回测多只股票：
```python
from multiprocessing import Pool
# 实现并行回测逻辑
```

### 2. 缓存优化
对于相同的数据和参数，可以缓存计算结果。

### 3. 数据库优化
- 为常用查询字段添加索引
- 使用批量查询减少数据库访问次数

## 相关文档

- [策略开发指南](../quantsys/strategies/README.md)
- [回测引擎文档](../quantsys/strategies/backtest.py)
- [因子计算文档](../quantsys/factors/README.md)

## 更新日志

### 2026-05-18
- 初始版本发布
- 支持3个经典策略回测
- 生成JSON和Markdown报告
- 自动策略排名和优化建议

## 贡献

欢迎提交Issue和Pull Request改进此工具。

## 许可证

MIT License
