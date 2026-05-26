# K线回填系统 - 快速参考卡

## 🚀 常用命令

```bash
# 进入项目目录
cd /Users/mac/Documents/ai/pi-investment/quant

# 单只股票 - 日线（2年）
python scripts/backfill_klines.py --data-type daily --symbols 600519.SH

# 多只股票 - 日线
python scripts/backfill_klines.py --data-type daily --symbols 600519.SH,000001.SZ,000858.SZ

# 全市场 A 股 - 日线（2年）
python scripts/backfill_klines.py --data-type daily --market A

# 全市场 A 股 - 日线（最近7天，日常更新）
python scripts/backfill_klines.py --data-type daily --market A --target-days 7

# 港股 - 日线
python scripts/backfill_klines.py --data-type daily --market HK

# 分钟线（1年）
python scripts/backfill_klines.py --data-type minute --symbols 600519.SH

# 重置进度，从头开始
python scripts/backfill_klines.py --data-type daily --market A --reset-progress

# 自定义批次大小
python scripts/backfill_klines.py --data-type daily --market A --batch-size 20
```

---

## 📋 参数速查

| 参数 | 说明 | 示例 |
|------|------|------|
| `--data-type` | 数据类型 (必需) | `daily`, `minute` |
| `--symbols` | 股票代码列表 | `600519.SH,000001.SZ` |
| `--market` | 市场过滤 | `A`, `HK` |
| `--target-days` | 回填天数 | `730` (日线), `365` (分钟线) |
| `--batch-size` | 批次大小 | `10` (默认) |
| `--reset-progress` | 重置进度 | 无参数，添加即启用 |

---

## ⏱️ 预估耗时

| 场景 | 股票数量 | 数据类型 | 预估耗时 |
|------|---------|---------|---------|
| 单只股票 | 1 | 日线 (2年) | ~50秒 |
| 单只股票 | 1 | 分钟线 (1年) | ~4分钟 |
| 沪深300 | 300 | 日线 (2年) | ~4小时 |
| 全市场 A 股 | 4000 | 日线 (2年) | ~15小时 |
| 日常增量 | 4000 | 日线 (7天) | ~10分钟 |

---

## 🔍 数据验证

```bash
# 检查数据新鲜度
psql -d quant_investment -c "
SELECT MAX(trade_date) as latest_date,
       COUNT(DISTINCT symbol) as symbol_count
FROM quant.daily_klines;
"

# 检查单只股票数据量
psql -d quant_investment -c "
SELECT symbol, COUNT(*) as days
FROM quant.daily_klines
WHERE symbol = '600519.SH'
  AND trade_date >= CURRENT_DATE - INTERVAL '2 years'
GROUP BY symbol;
"

# 检查缺失数据（2年应有约487个交易日）
psql -d quant_investment -c "
SELECT symbol, COUNT(*) as actual_days, 487 - COUNT(*) as missing_days
FROM quant.daily_klines
WHERE trade_date >= CURRENT_DATE - INTERVAL '2 years'
GROUP BY symbol
HAVING COUNT(*) < 487
ORDER BY missing_days DESC
LIMIT 20;
"

# 检查异常数据
psql -d quant_investment -c "
SELECT symbol, trade_date, close
FROM quant.daily_klines
WHERE close IS NULL OR close = 0
ORDER BY trade_date DESC
LIMIT 20;
"
```

---

## 🛠️ 故障排查

| 问题 | 快速解决 |
|------|---------|
| 数据库连接失败 | `pg_isready -h 127.0.0.1 -p 5432` |
| 分钟线不支持 | `export QUANT_DB_PROVIDER=postgres` |
| 下载失败 | 等待后重新运行（自动跳过已完成） |
| 进度文件损坏 | `rm .backfill_progress.json` |
| 内存不足 | 减小 `--batch-size` 到 5 |

---

## 📁 关键文件

| 文件 | 说明 |
|------|------|
| `scripts/backfill_klines.py` | CLI 入口脚本 |
| `.backfill_progress.json` | 进度文件（自动生成） |
| `logs/backfill_daily.log` | 日志文件（如果配置） |
| `quantsys/data/data_backfiller.py` | 核心下载逻辑 |
| `quantsys/data/gap_detector.py` | 缺口检测逻辑 |

---

## 🔄 Crontab 配置

```bash
# 编辑 crontab
crontab -e

# 添加每日自动回填任务（周一到周五 16:30）
30 16 * * 1-5 cd /Users/mac/Documents/ai/pi-investment/quant && \
    /Users/mac/Documents/ai/pi-investment/.venv-py313/bin/python \
    scripts/backfill_klines.py \
    --data-type daily \
    --market A \
    --target-days 7 \
    >> logs/backfill_daily.log 2>&1
```

---

## 📊 输出示例

### 成功输出
```
============================================================
K-line Data Backfill
============================================================
Data Type:    daily
Target Days:  730
Batch Size:   10
Market:       A
============================================================

Processing [1/10] 600519.SH...
✓ 600519.SH: 487 succeeded, 0 failed, 0 skipped

============================================================
FINAL SUMMARY
============================================================
Symbols Processed:    10/10
Symbols Succeeded:    10
Dates Backfilled:     4870
Dates Failed:         0
Dates Skipped:        0
============================================================

✓ Backfill complete!
```

### 恢复输出（有跳过）
```
Processing [1/10] 600519.SH...
✓ 600519.SH: 100 succeeded, 0 failed, 387 skipped
```

### 失败输出
```
Processing [1/10] 600519.SH...
⚠ 600519.SH: 485 succeeded, 2 failed, 0 skipped
```

---

## 🧪 测试命令

```bash
# 运行所有回填测试
python -m pytest tests/test_backfill*.py -v

# 运行特定测试
python -m pytest tests/test_backfill_klines.py::TestMain::test_main_daily_with_symbols -v

# 测试覆盖率
python -m pytest tests/test_backfill*.py --cov=quantsys.data --cov-report=term-missing
```

---

## 📖 完整文档

详细说明请参考: [kline-backfill-system.md](kline-backfill-system.md)

---

**最后更新**: 2026-05-26
