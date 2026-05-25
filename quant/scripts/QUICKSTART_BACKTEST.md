# 策略回测快速开始

## 快速使用

### 1. 单只股票回测（最简单）
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python scripts/weekly_backtest.py
```

### 2. 自定义参数回测
```bash
# 回测000001，最近60天
python scripts/weekly_backtest.py --symbol 000001 --days 60

# 回测000002，初始资金200万
python scripts/weekly_backtest.py --symbol 000002 --capital 2000000

# 指定日期范围
python scripts/weekly_backtest.py --start 2026-01-01 --end 2026-05-18
```

### 3. 批量回测多只股票
```bash
# 使用默认参数（60天，100万初始资金）
./scripts/batch_backtest.sh

# 自定义参数
./scripts/batch_backtest.sh --days 90 --capital 5000000
```

## 查看结果

### 查看Markdown报告（人类可读）
```bash
cat .pi-invest/backtest_report_000001_2026-05-18.md
```

### 查看JSON报告（程序处理）
```bash
cat .pi-invest/backtest_report_000001_2026-05-18.json | jq .
```

### 列出所有报告
```bash
ls -lh .pi-invest/backtest_report_*
```

## 报告示例

运行后会看到类似输出：

```
============================================================
策略回测验证脚本
============================================================
回测期间: 2026-03-19 至 2026-05-18
初始资金: 1,000,000 元

开始回测 000002...
加载了 39 条K线数据
  回测策略: RSI反转...
  回测策略: 均线突破...
  回测策略: 布林带...
JSON报告已保存: .pi-invest/backtest_report_000002_2026-05-18.json
Markdown报告已保存: .pi-invest/backtest_report_000002_2026-05-18.md

============================================================
回测完成
============================================================
1. 布林带: 回报 +3.99%, 夏普 2.63, 回撤 0.66%
2. RSI反转: 回报 +0.00%, 夏普 0.00, 回撤 0.00%
3. 均线突破: 回报 -7.77%, 夏普 -3.66, 回撤 10.35%
```

## 常用命令

```bash
# 回测最近30天（默认）
python scripts/weekly_backtest.py

# 回测最近90天
python scripts/weekly_backtest.py --days 90

# 回测特定股票
python scripts/weekly_backtest.py --symbol 600000

# 完整参数示例
python scripts/weekly_backtest.py \
  --symbol 000001 \
  --days 60 \
  --capital 1000000 \
  --commission 0.0003 \
  --slippage 0.001
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--symbol` | 股票代码 | 000001 |
| `--days` | 回测天数 | 30 |
| `--start` | 开始日期 | - |
| `--end` | 结束日期 | - |
| `--capital` | 初始资金 | 1000000 |
| `--commission` | 手续费率 | 0.0003 (0.03%) |
| `--slippage` | 滑点率 | 0.001 (0.1%) |

## 输出文件

- **JSON报告**: `.pi-invest/backtest_report_{symbol}_{date}.json`
- **Markdown报告**: `.pi-invest/backtest_report_{symbol}_{date}.md`

## 支持的策略

1. **RSI反转策略** - 基于RSI指标的均值回归
2. **均线突破策略** - 基于MA交叉的趋势跟踪
3. **布林带策略** - 基于布林带的突破/反转

## 绩效指标

- 总回报率、年化收益率
- 夏普比率、Sortino比率、Calmar比率
- 最大回撤
- 胜率、盈亏比
- 交易次数、平均持仓时间

## 故障排除

### 问题：没有数据
```bash
# 先获取数据
python scripts/fetch_hs300_data.py
```

### 问题：交易次数为0
```bash
# 增加回测天数
python scripts/weekly_backtest.py --days 90
```

### 问题：导入错误
```bash
# 确保在quant目录下运行
cd /Users/mac/Documents/ai/pi-investment/quant
python scripts/weekly_backtest.py
```

## 详细文档

查看完整文档：`scripts/BACKTEST_README.md`

## 集成到定时任务

```bash
# 每周一早上9点运行
0 9 * * 1 cd /path/to/quant && python scripts/weekly_backtest.py --days 30
```
