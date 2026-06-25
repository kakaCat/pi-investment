# 定时任务配置指南

## 配置内容

```bash
# PI Investment Agent 定时任务
# 早盘分析 - 每个工作日 9:00
0 9 * * 1-5 ./scripts/morning_analysis.sh >> /tmp/morning_analysis.log 2>&1

# 实时监控 - 每个工作日 9:00-15:00 每5分钟
*/5 9-15 * * 1-5 cd /Users/mac/Documents/ai/pi-investment && ./scripts/realtime_monitor.sh >> /tmp/realtime_monitor.log 2>&1

# 每日学习 - 每天 18:00
0 18 * * * cd /Users/mac/Documents/ai/pi-investment && ./scripts/daily_learning.sh >> /tmp/daily_learning.log 2>&1
```

## 安装步骤

### 方法1: 直接安装（推荐）

```bash
crontab /tmp/pi_investment_crontab.txt
```

### 方法2: 手动编辑

```bash
crontab -e
# 然后粘贴上面的内容
```

## 验证

```bash
# 查看已安装的定时任务
crontab -l

# 查看日志
tail -f /tmp/morning_analysis.log
tail -f /tmp/realtime_monitor.log
tail -f /tmp/daily_learning.log
```

## 测试

```bash
# 手动执行测试
./scripts/morning_analysis.sh
./scripts/realtime_monitor.sh
./scripts/daily_learning.sh
```

## 卸载

```bash
# 删除所有定时任务
crontab -r

# 或者编辑删除特定任务
crontab -e
```

## 注意事项

1. 确保脚本有执行权限：`chmod +x scripts/*.sh`
2. 确保后端服务运行：quantsys-v2 需要在 localhost:5001
3. 查看日志了解执行情况
4. cron 环境变量与 shell 不同，可能需要在脚本中设置 PATH
