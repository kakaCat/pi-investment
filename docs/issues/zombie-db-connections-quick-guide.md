# PostgreSQL 僵尸连接问题 - 快速指南

## 🚨 问题症状

```
FATAL: sorry, too many clients already
```

- quantsys-v2 启动失败
- 无法执行任何工具（analysis_swing_points 等）
- 数据库连接数耗尽

## 🔍 快速诊断

```bash
# 1. 检查连接数
./scripts/monitor-db-connections.sh

# 2. 查看空闲连接详情
psql -h 127.0.0.1 -U mac -d postgres -c "
  SELECT pid, state, 
         EXTRACT(EPOCH FROM (NOW() - state_change))/60 AS idle_minutes
  FROM pg_stat_activity 
  WHERE datname='quant_investment' AND state='idle'
  ORDER BY state_change 
  LIMIT 10;"
```

## ⚡ 紧急修复（5分钟）

### 步骤 1：清理空闲连接

```bash
# 自动清理超过30分钟的空闲连接
./scripts/cleanup-idle-connections.sh

# 或手动清理所有空闲连接（更激进）
psql -h 127.0.0.1 -U mac -d postgres -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE datname='quant_investment' 
    AND state='idle' 
    AND pid <> pg_backend_pid();"
```

### 步骤 2：重启 quantsys-v2

```bash
# 杀掉可能占用端口的僵尸进程
lsof -i :5001 | grep LISTEN | awk '{print $2}' | xargs kill -9
lsof -i :5003 | grep LISTEN | awk '{print $2}' | xargs kill -9

# 重启服务
cd quantsys-v2 && python start_all.py
```

### 步骤 3：验证

```bash
# 检查服务状态
curl http://127.0.0.1:5001/api/health

# 监控连接数
./scripts/monitor-db-connections.sh
```

## 🛡️ 预防措施（推荐配置）

### 1. PostgreSQL 配置优化

编辑配置文件：
```bash
# macOS Homebrew 路径
vim /opt/homebrew/var/postgresql@14/postgresql.conf
```

添加以下配置：
```ini
# 自动终止空闲事务（5分钟）
idle_in_transaction_session_timeout = 300000

# 语句超时（30秒）
statement_timeout = 30000

# 增加最大连接数
max_connections = 200
```

重启 PostgreSQL：
```bash
brew services restart postgresql@14
```

### 2. 定时清理（推荐）

添加 cron 任务，每小时自动清理：
```bash
crontab -e
```

添加：
```cron
# 每小时清理空闲连接
0 * * * * /Users/mac/Documents/ai/pi-investment/scripts/cleanup-idle-connections.sh >> /tmp/pg-cleanup-cron.log 2>&1

# 每30分钟监控连接数
*/30 * * * * /Users/mac/Documents/ai/pi-investment/scripts/monitor-db-connections.sh >> /tmp/pg-monitor-cron.log 2>&1
```

### 3. 代码改进（长期方案）

详见：[docs/issues/zombie-db-connections-solution.md](zombie-db-connections-solution.md)

核心改进：
- ✅ 使用连接池（psycopg2.pool）
- ✅ 实现 Context Manager 确保连接关闭
- ✅ 添加连接健康检查端点

## 📊 监控仪表板

### 当前连接状态
```bash
./scripts/monitor-db-connections.sh
```

输出示例：
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PostgreSQL 连接监控 - 2026-06-10 13:39:12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据库: quant_investment
总连接数: 37 / 100 (37%)
  - 活动连接: 0
  - 空闲连接: 37
  - 事务中空闲: 0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OK: 连接数正常
```

### 告警阈值
- 🟢 正常：< 80 连接
- 🟡 警告：80-89 连接
- 🔴 严重：≥ 90 连接

## 🔧 故障排除

### Q: 清理脚本执行失败
**A**: 检查 PostgreSQL 服务状态
```bash
pg_isready -h 127.0.0.1 -p 5432
```

### Q: 清理后连接数仍然很高
**A**: 可能有活动连接或服务正在使用，检查：
```bash
# 查看活动连接
psql -h 127.0.0.1 -U mac -d postgres -c "
  SELECT pid, state, query 
  FROM pg_stat_activity 
  WHERE datname='quant_investment' AND state='active';"
```

### Q: quantsys-v2 启动后立即耗尽连接
**A**: 代码存在连接泄漏，需要实施长期方案（连接池）

## 📝 相关文档

- [完整解决方案](zombie-db-connections-solution.md)
- [PostgreSQL 连接池文档](https://www.psycopg.org/docs/pool.html)
- [CLAUDE.md - 数据库配置](../../CLAUDE.md#environment-setup)

## 🆘 紧急联系

如果问题持续无法解决：
1. 检查日志：`/tmp/quantsys-v2-startup.log`
2. 重启 PostgreSQL：`brew services restart postgresql@14`
3. 查看详细文档：`docs/issues/zombie-db-connections-solution.md`
