# 数据获取脚本使用说明

## 脚本列表

### 核心数据脚本

#### 1. fetch_hs300_data.py - 获取沪深300成分股数据

**用途**: 首次运行，获取沪深300成分股的2年历史数据

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/fetch_hs300_data.py
```

**功能**:
- 获取沪深300成分股列表（300只股票）
- 获取每只股票的2年历史K线数据（约730天）
- 保存到数据库 `quantsys/data/stocks.db`

**预计时间**: 30-60分钟（取决于网络速度）

---

#### 2. daily_update.py - 每日数据更新

**用途**: 每天更新最新的K线数据

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/daily_update.py
```

**功能**:
- 更新数据库中所有股票的最近5天数据
- 适合每天定时运行

**预计时间**: 5-10分钟

---

#### 3. calculate_factors.py - 计算技术因子

**用途**: 计算各种技术指标因子

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/calculate_factors.py
```

**功能**:
- 计算均线（MA5, MA10, MA20, MA60）
- 计算动量指标（RSI, MACD, KDJ）
- 计算波动率指标（BOLL, ATR）
- 保存到 factor_values 表

---

#### 4. generate_signals.py - 生成交易信号

**用途**: 基于因子值生成交易信号

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/generate_signals.py
```

**功能**:
- 运行多个交易策略（RSI反转、均线突破、MACD等）
- 生成买入/卖出信号
- 计算信号信心度
- 保存到 `.pi-invest/signals.json`

---

#### 5. risk_check.py - 风险检查

**用途**: 对交易信号进行风险检查

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/risk_check.py
```

**功能**:
- 检查信号的风险指标
- 过滤高风险信号
- 生成风险报告

---

#### 6. daily_report.py - 每日报告生成

**用途**: 汇总当日数据并生成每日报告

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/daily_report.py

# 指定输出目录
python3 scripts/daily_report.py --output-dir .pi-invest
```

**功能**:
- 汇总交易信号数据
- 统计市场概况和因子分布
- 汇总风险预警信息
- 汇总ML预测结果（如果有）
- 生成 Markdown 和 JSON 格式报告

**输出**:
- `.pi-invest/daily_report_YYYY-MM-DD.md` - Markdown格式报告
- `.pi-invest/daily_report.json` - JSON格式报告摘要

**报告内容**:
- 📊 市场概况（股票数、K线覆盖、因子覆盖率）
- 🎯 交易信号（买入/卖出信号统计、Top 5信号）
- 📈 因子分布（各因子计算覆盖情况）
- ⚠️ 风险预警（持仓风险、止损预警）
- 🤖 ML预测（看涨/看跌预测统计）

---

### 分析与报告脚本

#### 7. weekly_performance.py - 每周绩效分析

**用途**: 分析每周交易信号和策略表现

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/weekly_performance.py

# 分析特定周
python3 scripts/weekly_performance.py --year 2026 --week 20
```

**功能**:
- 收集本周交易信号数据
- 分析信号质量和策略表现
- 统计因子有效性
- 生成 Markdown 和 JSON 格式报告
- 对比历史趋势
- 提供优化建议

**输出**:
- `.pi-invest/performance_reports/performance_report_YYYY-WWW.md`
- `.pi-invest/performance_reports/performance_report_YYYY-WWW.json`

**详细文档**: 查看 [WEEKLY_PERFORMANCE_README.md](WEEKLY_PERFORMANCE_README.md)

---

#### 8. visualize_performance.py - 绩效可视化（可选）

**用途**: 为绩效报告生成可视化图表

**依赖**: `pip install matplotlib`

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/visualize_performance.py

# 可视化特定周
python3 scripts/visualize_performance.py --year 2026 --week 21
```

**功能**:
- 信号分布图（饼图、柱状图）
- 策略表现对比图
- 因子使用频率图
- 多周趋势图

**输出**:
- `.pi-invest/performance_reports/charts/YYYY-WWW_*.png`

---

### 调度与测试脚本

#### 9. scheduler.py - 任务调度器

**用途**: 统一管理所有定时任务

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python3 scripts/scheduler.py
```

**功能**:
- 每日数据更新
- 每日因子计算
- 每日信号生成
- 每日风险检查
- 每周绩效分析

**详细文档**: 查看 [SCHEDULER_README.md](SCHEDULER_README.md)

---

#### 10. setup_cron.sh - 设置定时任务

**用途**: 自动设置每天18:00运行数据更新

**运行方式**:
```bash
cd /Users/mac/Documents/ai/pi-investment/quant/scripts
./setup_cron.sh
```

**功能**:
- 添加cron定时任务
- 每周一至周五 18:00 自动运行 daily_update.py
- 日志保存到 `logs/daily_update.log`

---

## 使用流程

### 首次使用

1. **获取沪深300数据**（首次运行）:
   ```bash
   cd /Users/mac/Documents/ai/pi-investment/quant
   python3 scripts/fetch_hs300_data.py
   ```

2. **设置定时任务**（可选）:
   ```bash
   cd scripts
   ./setup_cron.sh
   ```

### 日常使用

- **自动更新**: 定时任务会在每天18:00自动运行
- **手动更新**: 
  ```bash
  python3 scripts/daily_update.py
  ```

- **生成交易信号**:
  ```bash
  # 完整流程
  python3 scripts/calculate_factors.py  # 计算因子
  python3 scripts/generate_signals.py   # 生成信号
  python3 scripts/risk_check.py         # 风险检查
  python3 scripts/daily_report.py       # 生成每日报告
  ```

- **每周绩效分析**:
  ```bash
  # 分析本周
  python3 scripts/weekly_performance.py
  
  # 生成可视化图表（可选）
  python3 scripts/visualize_performance.py
  ```

### 查看日志

```bash
# 查看最新日志
tail -f logs/daily_update.log

# 查看历史日志
cat logs/daily_update.log

# 查看调度器日志
tail -f logs/scheduler.log
```

### 查看报告

```bash
# 查看最新每日报告
cat .pi-invest/daily_report_$(date +%Y-%m-%d).md

# 查看每日报告JSON
cat .pi-invest/daily_report.json | python3 -m json.tool

# 查看最新绩效报告
cat .pi-invest/performance_reports/performance_report_2026-W21.md

# 列出所有报告
ls -lh .pi-invest/performance_reports/

# 查看信号数据
cat .pi-invest/signals.json | python3 -m json.tool
```

---

## 定时任务管理

### 查看定时任务
```bash
crontab -l
```

### 编辑定时任务
```bash
crontab -e
```

### 删除定时任务
```bash
crontab -l | grep -v 'daily_update.py' | crontab -
```

### 修改运行时间

编辑 crontab，修改时间配置：
```bash
crontab -e
```

时间格式说明：
```
分 时 日 月 周
0 18 * * 1-5  # 每周一至周五 18:00
0 9 * * *     # 每天 9:00
30 15 * * *   # 每天 15:30
```

---

## 故障排查

### 问题1: 网络连接失败

**症状**: 提示 `ProxyError` 或无法连接

**解决**: 脚本已自动禁用代理，如果仍有问题，检查网络连接

### 问题2: 定时任务未执行

**检查步骤**:
1. 确认定时任务已添加: `crontab -l`
2. 检查日志文件: `tail -f logs/daily_update.log`
3. 手动运行测试: `python3 scripts/daily_update.py`

### 问题3: 数据库锁定

**症状**: 提示 `database is locked`

**解决**: 等待其他进程完成，或重启脚本

---

## 数据库查询

### 查看数据统计
```bash
sqlite3 quantsys/data/stocks.db "
SELECT 
    COUNT(DISTINCT symbol) as stocks,
    COUNT(*) as records,
    MIN(date) as earliest,
    MAX(date) as latest
FROM daily_klines;
"
```

### 查看最新数据
```bash
sqlite3 quantsys/data/stocks.db "
SELECT symbol, MAX(date) as latest_date
FROM daily_klines
GROUP BY symbol
ORDER BY latest_date DESC
LIMIT 10;
"
```

---

## 注意事项

1. **运行时间**: 建议在交易日收盘后（18:00之后）运行
2. **网络要求**: 需要稳定的网络连接
3. **磁盘空间**: 300只股票2年数据约需要 50-100MB
4. **数据源**: 使用 akshare 从东方财富获取数据
5. **更新频率**: 建议每天更新一次即可

---

## 联系支持

如有问题，请检查：
1. Python版本 >= 3.8
2. 已安装 quantsys 包: `pip install -e .`
3. 已安装 akshare: `pip install akshare`
