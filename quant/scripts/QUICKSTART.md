# 每周绩效分析 - 快速开始

## 一分钟快速开始

```bash
cd /Users/mac/Documents/ai/pi-investment/quant

# 1. 生成本周绩效报告
python3 scripts/weekly_performance.py

# 2. 查看报告
cat .pi-invest/performance_reports/performance_report_2026-W21.md

# 3. 生成可视化图表（可选）
python3 scripts/visualize_performance.py
```

## 完整工作流

### 每日任务（自动化）

```bash
# 方式1: 使用调度器（推荐）
python3 scripts/scheduler.py

# 方式2: 手动运行
python3 scripts/daily_update.py        # 更新数据
python3 scripts/calculate_factors.py   # 计算因子
python3 scripts/generate_signals.py    # 生成信号
python3 scripts/risk_check.py          # 风险检查
```

### 每周任务

```bash
# 每周一早上运行
python3 scripts/weekly_performance.py

# 可选：生成图表
python3 scripts/visualize_performance.py
```

## 报告示例

### Markdown 报告

```markdown
# 每周绩效分析报告 - 2026年第21周

## 本周概况
- 交易日: 5天
- 生成信号: 5个 (买入: 2, 卖出: 3)
- 平均信心度: 0.49

## 策略表现
| 策略 | 信号数 | 平均信心度 | 评价 |
|------|--------|------------|------|
| RSI反转 | 1 | 1.00 | 优秀 |
| 均线突破 | 4 | 0.36 | 需优化 |

## 优化建议
1. 信号数量较少，建议检查数据更新
2. RSI反转策略表现优秀，建议增加权重
3. 均线突破策略需要优化参数
```

### 可视化图表

生成的图表包括：
- 📊 信号分布图（买入/卖出、信心度分布）
- 📈 策略表现图（信号数量、平均信心度）
- 🔍 因子使用图（使用频率 Top 10）
- 📉 趋势图（多周对比）

## 定时任务配置

### 方式1: 使用 cron

```bash
# 编辑 crontab
crontab -e

# 添加每周一 9:00 运行
0 9 * * 1 cd /Users/mac/Documents/ai/pi-investment/quant && python3 scripts/weekly_performance.py >> logs/weekly_performance.log 2>&1
```

### 方式2: 集成到 scheduler.py

在 `scheduler.py` 中已经包含了每周任务，直接运行即可：

```bash
python3 scripts/scheduler.py
```

## 常见问题

### Q: 报告显示"本周暂无交易信号数据"？

**A**: 先运行信号生成任务：
```bash
python3 scripts/generate_signals.py
python3 scripts/weekly_performance.py
```

### Q: 如何查看历史报告？

**A**: 所有报告保存在 `.pi-invest/performance_reports/`：
```bash
ls -lh .pi-invest/performance_reports/
cat .pi-invest/performance_reports/performance_report_2026-W20.md
```

### Q: 如何生成可视化图表？

**A**: 需要先安装 matplotlib：
```bash
pip install matplotlib
python3 scripts/visualize_performance.py
```

### Q: 如何分析特定周的数据？

**A**: 使用 `--year` 和 `--week` 参数：
```bash
python3 scripts/weekly_performance.py --year 2026 --week 20
python3 scripts/visualize_performance.py --year 2026 --week 20
```

## 文件结构

```
quant/
├── scripts/
│   ├── weekly_performance.py          # 主脚本
│   ├── visualize_performance.py       # 可视化脚本
│   ├── test_weekly_performance.py     # 测试脚本
│   ├── WEEKLY_PERFORMANCE_README.md   # 详细文档
│   └── README.md                      # 总体说明
│
└── .pi-invest/
    ├── signals.json                   # 交易信号数据
    └── performance_reports/           # 绩效报告目录
        ├── performance_report_2026-W21.md    # Markdown 报告
        ├── performance_report_2026-W21.json  # JSON 报告
        └── charts/                           # 图表目录
            ├── 2026-W21_signal_dist.png
            ├── 2026-W21_strategy_perf.png
            ├── 2026-W21_factor_usage.png
            └── 2026-W21_trend.png
```

## 下一步

1. **查看详细文档**: [WEEKLY_PERFORMANCE_README.md](WEEKLY_PERFORMANCE_README.md)
2. **运行测试**: `python3 scripts/test_weekly_performance.py`
3. **配置定时任务**: 设置每周自动生成报告
4. **自定义分析**: 根据需要修改 `weekly_performance.py`

## 技术支持

如有问题：
1. 查看日志输出
2. 运行测试脚本验证
3. 检查数据文件是否存在
4. 查看详细文档

---

**提示**: 建议每周一早上查看报告，根据建议调整策略参数。
