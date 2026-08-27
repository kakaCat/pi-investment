# 线B Step 2：每日K线同步临时方案

## 背景

紧急回填脚本（emergency_backfill_0826_0827.py）完成后，需要挂载每日自动同步任务，避免再次断崖。

## 方案：通过 reminder 触发回填脚本

由于 quantsys-v2 已废弃，无法直接调用其 scheduler。使用 Agent OS reminder 每晚 21:00 触发回填脚本。

### Reminder 配置

```javascript
reminder_create({
  name: "daily-kline-sync-emergency",
  cron: "0 0 21 * * 1-5",  // 工作日 21:00（给数据源同步留6小时缓冲）
  prompt: `执行 K线每日同步（临时方案）：

调用 bash 命令：
cd /Users/yunpeng/pi-investment/quantsys-v2 && source activate-py313.sh && python scripts/emergency_backfill_0826_0827.py

完成后汇报：
- 回填股票数
- 新增记录数
- 任何失败/异常

注意：这是临时方案，中期需实现 @pi-investment/data-sync 插件。`,
  window: "w-6807aa37"
})
```

### ⚠️ 已知限制

1. **reminder prompt 调用 bash 的可靠性未知**：
   - DSH agent 执行环境可能无法直接运行 bash 命令
   - Python 虚拟环境激活在 reminder context 中可能失败

2. **脚本硬编码 08-26/27**：
   - 当前脚本只回填这两天，需要改为"检测昨日是否缺失"
   - 或者每次回填最近 3 天（容错但有重复）

### 脚本改进版（检测昨日）

```python
# 修改 emergency_backfill_0826_0827.py
from datetime import date, timedelta

def main():
    # 检测昨日是否缺失
    yesterday = date.today() - timedelta(days=1)
    
    # 跳过周末
    if yesterday.weekday() >= 5:  # 周六=5, 周日=6
        logger.info(f"{yesterday} 是周末，跳过")
        return
    
    # 检查昨日数据
    with get_session() as session:
        result = session.execute(text(
            f"SELECT COUNT(*) FROM quant.daily_klines WHERE trade_date = '{yesterday}'"
        ))
        count = result.scalar()
    
    logger.info(f"{yesterday} 当前记录数: {count}")
    
    # 如果少于4000条，视为不完整，触发回填
    if count < 4000:
        logger.info("数据不完整，开始回填...")
        # ... 原回填逻辑 ...
    else:
        logger.info("数据完整，无需回填")
```

### 验收标准

挂载后次日（08-29）21:00 后验证：
1. reminder 最近触发时间更新
2. `SELECT COUNT(*) FROM quant.daily_klines WHERE trade_date = '2026-08-28'` ≥ 4500

---

## 执行步骤

1. **等 bash-2 完成**（紧急回填 08-26/27）
2. **验证回填结果**（08-26/27 各 ≥4500 条）
3. **改进脚本**（检测昨日，见上）
4. **挂载 reminder**（上述配置）
5. **次日验收**

---

## 当前状态：等 bash-2 完成
