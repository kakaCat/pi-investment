# QuantSys调度器服务部署指南

## 概述

QuantSys调度器是一个企业级的任务调度系统，负责V13策略的自动化交易、数据更新、风险检查等定时任务。

## 架构

- **调度引擎**: APScheduler (事件驱动)
- **持久化**: PostgreSQL (任务配置和执行记录)
- **API管理**: RESTful API
- **服务管理**: systemd/launchd

## 部署方法

### macOS部署 (launchd)

```bash
# 1. 复制配置文件到系统目录
cp deployment/quantsys-scheduler.plist ~/Library/LaunchAgents/

# 2. 加载服务
launchctl load ~/Library/LaunchAgents/quantsys-scheduler.plist

# 3. 启动服务
launchctl start com.quantsys.scheduler

# 4. 查看状态
launchctl list | grep quantsys

# 5. 查看日志
tail -f logs/scheduler_daemon.log
```

### Linux部署 (systemd)

```bash
# 1. 复制配置文件到系统目录
sudo cp deployment/quantsys-scheduler.service /etc/systemd/system/

# 2. 重新加载systemd配置
sudo systemctl daemon-reload

# 3. 设置开机自启动
sudo systemctl enable quantsys-scheduler

# 4. 启动服务
sudo systemctl start quantsys-scheduler

# 5. 查看状态
sudo systemctl status quantsys-scheduler

# 6. 查看日志
sudo journalctl -u quantsys-scheduler -f
```

## 手动运行（开发测试）

```bash
# 前台运行
python3 scheduler_daemon.py

# 后台运行
nohup python3 scheduler_daemon.py > logs/scheduler_daemon.log 2>&1 &
```

## API管理

调度器提供完整的RESTful API用于任务管理：

### 查看调度器状态
```bash
curl http://127.0.0.1:5001/api/scheduler/status
```

### 查看所有任务
```bash
curl http://127.0.0.1:5001/api/scheduler/tasks
```

### 查看任务详情
```bash
curl http://127.0.0.1:5001/api/scheduler/tasks/v13_daily_trading
```

### 手动触发任务
```bash
curl -X POST http://127.0.0.1:5001/api/scheduler/tasks/v13_daily_trading/trigger
```

### 启用/禁用任务
```bash
# 启用
curl -X POST http://127.0.0.1:5001/api/scheduler/tasks/v13_daily_trading/enable

# 禁用
curl -X POST http://127.0.0.1:5001/api/scheduler/tasks/v13_daily_trading/disable
```

### 查看执行历史
```bash
curl "http://127.0.0.1:5001/api/scheduler/history?task_id=v13_daily_trading&limit=10"
```

## 任务列表

系统已配置以下6个定时任务：

| 任务名称 | 描述 | 执行时间 | 功能 |
|---------|------|---------|------|
| v13_daily_trading | V13模拟交易每日检查 | 交易日 14:25 | 检查止损、执行调仓 |
| kline_update | K线数据更新 | 交易日 16:00 | 更新创业板K线数据 |
| v13_verification | V13预测验证 | 交易日 15:30 | 验证5天前的预测准确性 |
| v13_risk_check | V13风险检查 | 交易日 16:00 | 检查账户风险指标 |
| v13_weekly_report | V13周报生成 | 每周一 09:00 | 生成周度策略表现报告 |
| data_quality_check | 数据质量检查 | 交易日 08:00 | 检查K线和因子数据完整性 |

## 监控和告警

- **日志文件**: `logs/scheduler_daemon.log`
- **错误日志**: `logs/scheduler_daemon_error.log`
- **执行记录**: 存储在`quant.scheduler_runs`表
- **飞书告警**: 任务失败时自动发送通知（需配置FEISHU_WEBHOOK_URL）

## 故障排查

### 服务无法启动
```bash
# 检查日志
tail -50 logs/scheduler_daemon_error.log

# 检查数据库连接
psql -U quant -d quant_db -c "SELECT 1"

# 手动运行测试
python3 scheduler_daemon.py
```

### 任务未执行
```bash
# 检查任务配置
curl http://127.0.0.1:5001/api/scheduler/tasks/v13_daily_trading

# 查看执行历史
curl http://127.0.0.1:5001/api/scheduler/history?task_id=v13_daily_trading

# 手动触发测试
curl -X POST http://127.0.0.1:5001/api/scheduler/tasks/v13_daily_trading/trigger
```

## 维护操作

### 停止服务
```bash
# macOS
launchctl stop com.quantsys.scheduler
launchctl unload ~/Library/LaunchAgents/quantsys-scheduler.plist

# Linux
sudo systemctl stop quantsys-scheduler
```

### 重启服务
```bash
# macOS
launchctl stop com.quantsys.scheduler
launchctl start com.quantsys.scheduler

# Linux
sudo systemctl restart quantsys-scheduler
```

### 更新配置
```bash
# 1. 修改数据库中的任务配置
# 2. 重启服务使配置生效

# macOS
launchctl restart com.quantsys.scheduler

# Linux  
sudo systemctl restart quantsys-scheduler
```

## 注意事项

1. **数据库依赖**: 服务启动前确保PostgreSQL正常运行
2. **环境变量**: 确保.env文件包含正确的数据库连接信息
3. **Python版本**: 需要Python 3.8+
4. **依赖包**: 确保已安装apscheduler、sqlalchemy等依赖
5. **权限**: 日志目录需要有写入权限

## 联系方式

遇到问题请查看日志或联系系统管理员。
