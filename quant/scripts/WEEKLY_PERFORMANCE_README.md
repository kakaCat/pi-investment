# 每周绩效分析脚本使用指南

## 概述

`weekly_performance.py` 是一个用于分析量化交易系统每周表现的脚本。它会收集本周的交易信号数据，分析策略表现、因子有效性，并生成详细的绩效报告。

## 功能特性

### 1. 数据收集
- 读取本周所有交易信号（从 `signals.json`）
- 读取回测报告（如果有）
- 统计信号数量、类型分布
- 支持历史数据对比

### 2. 信号质量分析
- 统计买入/卖出信号数量
- 分析信心度分布
- 识别信号质量问题
- 计算平均信心度

### 3. 策略表现分析
- 统计各策略生成的信号数量
- 计算各策略的平均信心度
- 识别表现最好和需要优化的策略
- 买卖信号分布

### 4. 因子有效性分析
- 统计各因子的使用频率
- 识别最常用的因子
- 分析因子对信号的贡献

### 5. 趋势对比
- 对比上周数据（如果有）
- 识别改进或退步趋势
- 计算变化百分比

### 6. 智能建议
- 根据分析结果生成优化建议
- 识别潜在问题
- 提供可操作的改进方向

### 7. 报告生成
- Markdown 格式报告（易读）
- JSON 格式报告（易于程序处理）
- 保存到 `.pi-invest/performance_reports/` 目录

## 使用方法

### 基本用法

分析本周数据：

```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/weekly_performance.py
```

### 指定周期

分析特定周：

```bash
# 分析 2026年第20周
python3 scripts/weekly_performance.py --year 2026 --week 20
```

### 自定义项目目录

```bash
python3 scripts/weekly_performance.py --quant-dir /path/to/quant
```

### 查看帮助

```bash
python3 scripts/weekly_performance.py --help
```

## 输出文件

脚本会在 `.pi-invest/performance_reports/` 目录下生成两个文件：

1. **Markdown 报告**: `performance_report_YYYY-WWW.md`
   - 人类可读的格式
   - 包含表格、统计数据和建议
   - 适合直接查看和分享

2. **JSON 报告**: `performance_report_YYYY-WWW.json`
   - 机器可读的格式
   - 包含完整的分析数据
   - 适合程序处理和历史对比

示例文件名：
- `performance_report_2026-W21.md`
- `performance_report_2026-W21.json`

## 报告内容说明

### 1. 本周概况
- 交易日数量
- 生成信号总数（买入/卖出）
- 平均信心度
- 买入占比
- 信心度分布

### 2. 策略表现
| 策略 | 信号数 | 买入 | 卖出 | 平均信心度 | 评价 |
|------|--------|------|------|------------|------|
| RSI反转 | 15 | 12 | 3 | 0.82 | 优秀 |
| 均线突破 | 12 | 8 | 4 | 0.65 | 良好 |

**评价标准**：
- 优秀: 平均信心度 ≥ 0.8
- 良好: 平均信心度 ≥ 0.6
- 一般: 平均信心度 ≥ 0.4
- 需优化: 平均信心度 < 0.4

### 3. 因子分析
- 最常用因子 Top 10
- 使用频率统计
- 帮助识别关键因子

### 4. 热门股票
- 生成信号最多的股票 Top 10
- 帮助识别市场热点

### 5. 对比上周
- 信号数量变化
- 平均信心度变化
- 买入/卖出信号变化
- 百分比显示

### 6. 优化建议
基于分析结果自动生成的建议，例如：
- 信号数量异常提醒
- 信心度优化建议
- 策略权重调整建议
- 市场环境提示

## 定时任务配置

### 方式1: 使用 cron（推荐）

每周一早上 9:00 自动生成上周报告：

```bash
# 编辑 crontab
crontab -e

# 添加以下行
0 9 * * 1 cd /Users/mac/Documents/ai/pi-investment/quant && python3 scripts/weekly_performance.py >> logs/weekly_performance.log 2>&1
```

### 方式2: 集成到 scheduler.py

在 `scripts/scheduler.py` 中添加每周任务：

```python
# 每周一 9:00 生成绩效报告
schedule.every().monday.at("09:00").do(run_weekly_performance)

def run_weekly_performance():
    """运行每周绩效分析"""
    logger.info("开始每周绩效分析...")
    subprocess.run([
        sys.executable,
        os.path.join(SCRIPTS_DIR, 'weekly_performance.py')
    ])
```

## 数据要求

### 必需数据
- `.pi-invest/signals.json`: 交易信号数据

### 可选数据
- `.pi-invest/backtest_report_*.json`: 回测报告
- 上周的绩效报告（用于对比）

### 信号数据格式

```json
{
  "generated_at": "2026-05-18T21:08:27.418968",
  "date": "2026-05-18",
  "summary": {
    "total": 5,
    "buy": 2,
    "sell": 3
  },
  "signals": [
    {
      "symbol": "000001",
      "strategy": "RSI反转",
      "signal": "BUY",
      "reason": "RSI超卖 (18.29 < 30)",
      "price": 10.86,
      "confidence": 1.0,
      "date": "2026-05-18",
      "timestamp": "2026-05-18T21:08:27.337531"
    }
  ]
}
```

## 常见问题

### Q1: 报告显示"本周暂无交易信号数据"

**原因**：
- 本周还没有运行信号生成任务
- signals.json 文件不存在或为空
- 信号日期不在本周范围内

**解决**：
```bash
# 先运行信号生成
python3 scripts/generate_signals.py

# 再运行绩效分析
python3 scripts/weekly_performance.py
```

### Q2: 如何查看历史报告？

所有历史报告都保存在 `.pi-invest/performance_reports/` 目录：

```bash
# 查看所有报告
ls -lh .pi-invest/performance_reports/

# 查看特定周的报告
cat .pi-invest/performance_reports/performance_report_2026-W20.md
```

### Q3: 如何对比多周数据？

可以编写脚本读取多个 JSON 报告进行对比：

```python
import json
import glob

reports = []
for file in sorted(glob.glob('.pi-invest/performance_reports/*.json')):
    with open(file) as f:
        reports.append(json.load(f))

# 对比分析
for report in reports:
    print(f"Week {report['week']}: {report['signal_quality']['total']} signals")
```

### Q4: 信心度分布不均匀怎么办？

如果大部分信号集中在低信心度区间：
1. 检查策略参数是否过于宽松
2. 考虑增加过滤条件
3. 优化信心度计算公式
4. 提高信号生成阈值

### Q5: 如何增加新的分析维度？

编辑 `weekly_performance.py`，在 `WeeklyPerformanceAnalyzer` 类中添加新方法：

```python
def analyze_custom_metric(self, signals: List[Dict]) -> Dict:
    """自定义分析"""
    # 你的分析逻辑
    return result
```

然后在 `analyze()` 方法中调用并添加到报告中。

## 最佳实践

### 1. 定期运行
- 建议每周一早上自动运行
- 及时发现策略问题
- 积累历史数据用于长期分析

### 2. 结合实际交易
- 将报告建议与实际交易结果对比
- 验证策略的真实有效性
- 调整策略权重

### 3. 持续优化
- 根据报告建议调整策略参数
- 关注信心度趋势
- 淘汰表现不佳的策略

### 4. 数据备份
- 定期备份 performance_reports 目录
- 保留历史数据用于长期分析
- 建立数据版本管理

### 5. 报告分享
- Markdown 格式便于团队分享
- 可以转换为 PDF 或 HTML
- 集成到周报或月报中

## 扩展功能建议

### 1. 可视化图表
使用 matplotlib 或 plotly 生成图表：
- 信号数量趋势图
- 信心度分布直方图
- 策略表现对比图
- 因子使用热力图

### 2. 邮件通知
分析完成后自动发送邮件：
```python
import smtplib
from email.mime.text import MIMEText

def send_report_email(report_path):
    # 发送邮件逻辑
    pass
```

### 3. 实际交易结果对比
如果有实际交易记录，可以对比：
- 信号准确率
- 实际盈亏
- 策略胜率

### 4. 多周期分析
除了每周，还可以生成：
- 每月绩效报告
- 季度绩效报告
- 年度绩效报告

## 技术细节

### 周数计算
使用 ISO 8601 标准：
- 周一是一周的第一天
- 第一周包含该年的第一个周四
- 使用 `datetime.isocalendar()` 方法

### 数据过滤
根据信号的 `date` 字段过滤：
```python
signal_date = datetime.fromisoformat(signal['date'])
if start_date <= signal_date <= end_date:
    # 包含在本周
```

### 错误处理
- 文件不存在：友好提示
- 数据格式错误：跳过并记录警告
- 计算异常：使用默认值

## 日志说明

脚本运行时会输出详细日志：

```
2026-05-18 21:16:22,264 [INFO] ============================================================
2026-05-18 21:16:22,264 [INFO] 每周绩效分析任务开始
2026-05-18 21:16:22,264 [INFO] 运行时间: 2026-05-18 21:16:22
2026-05-18 21:16:22,264 [INFO] ============================================================
2026-05-18 21:16:22,264 [INFO] 开始分析 2026年第21周 的绩效
2026-05-18 21:16:22,264 [INFO] 日期范围: 2026-05-18 至 2026-05-24
2026-05-18 21:16:22,264 [INFO] 从 signals.json 读取到 5 条信号，本周有 5 条
2026-05-18 21:16:22,264 [INFO] 找到 0 份本周回测报告
```

## 贡献与反馈

如果你有改进建议或发现问题：
1. 检查日志输出
2. 查看生成的 JSON 报告
3. 根据需要修改脚本
4. 测试后提交改进

## 相关脚本

- `generate_signals.py`: 生成交易信号
- `calculate_factors.py`: 计算技术因子
- `risk_check.py`: 风险检查
- `scheduler.py`: 定时任务调度

## 许可证

本脚本是 pi-investment 项目的一部分。
