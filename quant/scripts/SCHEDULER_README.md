# Python 定时任务调度器使用说明

## 📦 安装依赖

```bash
cd /Users/mac/Documents/ai/pi-investment/quant
pip install apscheduler
```

## 🚀 启动调度器

### 方式 1：前台运行（开发测试）
```bash
python3 scripts/scheduler.py
```

### 方式 2：后台运行（生产环境）
```bash
# 使用 nohup 后台运行
nohup python3 scripts/scheduler.py > logs/scheduler.log 2>&1 &

# 查看进程
ps aux | grep scheduler.py

# 停止调度器
pkill -f scheduler.py
```

### 方式 3：使用 systemd（推荐）
创建系统服务，开机自启动：

```bash
# 创建服务文件
sudo nano /etc/systemd/system/quant-scheduler.service
```

内容：
```ini
[Unit]
Description=Quant System Scheduler
After=network.target

[Service]
Type=simple
User=mac
WorkingDirectory=/Users/mac/Documents/ai/pi-investment/quant
ExecStart=/usr/bin/python3 /Users/mac/Documents/ai/pi-investment/quant/scripts/scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable quant-scheduler
sudo systemctl start quant-scheduler

# 查看状态
sudo systemctl status quant-scheduler

# 查看日志
sudo journalctl -u quant-scheduler -f
```

---

## 📋 定时任务列表

### 每日任务（周一至周五）

| 时间 | 任务 | 说明 |
|------|------|------|
| 09:00 | 风险检查 | 开盘前检查持仓风险、止损价位 |
| 16:00 | 数据更新 | 更新沪深300成分股K线数据 |
| 16:30 | 因子计算 | 计算42个技术因子和基本面因子 |
| 17:00 | 信号生成 | 运行策略，生成买入/卖出信号 |
| 17:30 | ML预测 | 使用机器学习模型预测涨跌 |
| 18:00 | 每日报告 | 汇总当日数据，生成Markdown和JSON报告 |

### 每周任务

| 时间 | 任务 | 说明 |
|------|------|------|
| 周六 20:00 | ML模型重训练 | 使用最新数据重新训练模型 |
| 周日 10:00 | 策略回测 | 验证策略近期表现 |
| 周日 20:00 | 绩效分析 | 分析本周交易绩效 |

---

## 📊 任务执行流程

```
周一至周五（交易日）：
09:00 → 风险检查 ✓ (已实现)
       ↓
16:00 → 数据更新 ✓ (已实现)
       ↓
16:30 → 因子计算 ✓ (已实现)
       ↓
17:00 → 信号生成 ✓ (已实现)
       ↓
17:30 → ML预测 (待实现)
       ↓
18:00 → 每日报告 ✓ (已实现)

周六：
20:00 → ML模型重训练 (待实现)

周日：
10:00 → 策略回测 (待实现)
20:00 → 绩效分析 (待实现)
```

---

## 🔍 监控与调试

### 查看日志
```bash
# 实时查看调度器日志
tail -f logs/scheduler.log

# 查看最近100行
tail -100 logs/scheduler.log

# 搜索错误
grep "ERROR" logs/scheduler.log
```

### 手动触发任务
修改 `scheduler.py`，添加测试代码：
```python
if __name__ == '__main__':
    # 测试单个任务
    task_daily_update()
    
    # 或启动调度器
    # main()
```

### 调整任务时间
编辑 `scheduler.py`，修改 `CronTrigger` 参数：
```python
# 改为每天 15:30
scheduler.add_job(
    task_daily_update,
    CronTrigger(hour=15, minute=30, day_of_week='mon-fri'),
    id='daily_update',
    name='每日数据更新'
)
```

---

## ⚙️ 配置说明

### 时区设置
调度器使用 `Asia/Shanghai` 时区，所有时间为北京时间。

### 任务依赖
任务按时间顺序执行，确保数据流正确：
1. 数据更新 → 2. 因子计算 → 3. 信号生成 → 4. ML预测 → 5. 报告生成

### 错误处理
- 每个任务独立执行，一个任务失败不影响其他任务
- 错误会记录到日志文件
- 可配置失败重试机制

---

## 🎯 下一步开发

### P0 - 立即实现
- [x] 数据更新（已完成）
- [x] 因子计算脚本（已完成）
- [x] 信号生成脚本（已完成）
- [x] 每日报告脚本（已完成）
- [x] 风险检查脚本（已完成）

### P1 - 短期实现
- [ ] ML预测脚本

### P2 - 中期实现
- [ ] ML模型重训练
- [ ] 策略回测
- [ ] 绩效分析

---

## 🐛 故障排查

### 问题1: 调度器无法启动
**检查**:
```bash
# 检查 Python 版本
python3 --version

# 检查依赖
pip list | grep apscheduler

# 重新安装
pip install --upgrade apscheduler
```

### 问题2: 任务未按时执行
**检查**:
```bash
# 查看系统时间
date

# 查看时区
timedatectl

# 查看调度器日志
tail -f logs/scheduler.log
```

### 问题3: 数据库锁定
**解决**:
```bash
# 检查是否有其他进程在使用数据库
lsof quantsys/data/stocks.db

# 如果有，停止相关进程
kill <PID>
```

---

## 📚 参考资料

- [APScheduler 文档](https://apscheduler.readthedocs.io/)
- [Cron 表达式说明](https://crontab.guru/)
- [systemd 服务管理](https://www.freedesktop.org/software/systemd/man/systemd.service.html)

---

## 💡 使用建议

1. **开发阶段**: 使用前台运行，方便调试
2. **测试阶段**: 使用 nohup 后台运行，观察稳定性
3. **生产环境**: 使用 systemd 服务，确保开机自启动
4. **定期检查**: 每周查看日志，确保任务正常执行
5. **备份数据**: 定期备份数据库和模型文件
