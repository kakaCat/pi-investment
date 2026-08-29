# QuantSys-V2 假死问题 - 快速诊断和修复指南

## 🚨 紧急响应流程

当系统假死时，按以下顺序操作：

### 1. 快速诊断（1 分钟）
```bash
# 运行健康检查
cd /Users/yunpeng/pi-investment/quantsys-v2
./scripts/health_check.sh
```

关注输出中的：
- ❌ API 无响应或超时
- ⚠️ 挂起事务超过 60 秒
- ⚠️ 连接数接近 50 (连接池耗尽)

### 2. 立即止血（1 分钟）
```bash
# 终止挂起的事务
python scripts/fix_idle_transactions.py --check --kill --threshold 60

# 如果仍然卡死，重启服务
launchctl kickstart -k gui/$(id -u)/com.pi-investment.v2-api
# 或手动重启
pkill -f "fastapi_app/main.py" && python adapters/inbound/fastapi_app/main.py &
```

### 3. 启动监控（持续运行）
```bash
# 后台运行监控脚本
nohup python scripts/fix_idle_transactions.py --monitor --kill --threshold 300 --interval 60 > logs/idle_transaction_monitor.log 2>&1 &

# 查看监控日志
tail -f logs/idle_transaction_monitor.log
```

---

## 📊 核心指标监控

### 数据库连接状态
```sql
-- 查看连接分布
SELECT state, count(*), max(EXTRACT(EPOCH FROM (now() - state_change))::int) as max_idle_sec
FROM pg_stat_activity 
WHERE datname='quant_investment' 
GROUP BY state;
```

**正常值**:
- `idle`: < 20 个
- `active`: < 5 个
- `idle in transaction`: 0 个（关键！）

**告警阈值**:
- `idle in transaction` > 0 且超过 60 秒 → 🚨 立即处理
- 总连接数 > 40 → ⚠️ 连接池接近耗尽

### API 响应时间
```bash
# 测试健康接口响应
time curl http://localhost:5001/api/health
```

**正常值**: < 1 秒  
**告警阈值**: > 3 秒 → ⚠️ 系统负载过高

---

## 🔧 已部署的防护措施

### 1. 数据库超时保护 ✅
```sql
ALTER DATABASE quant_investment SET idle_in_transaction_session_timeout = '5min';
```
- 5 分钟后自动终止挂起事务
- 防止单个泄漏连接长期占用

### 2. 连接池扩容 ✅
```python
pool_size: 20  (原 10)
max_overflow: 30  (原 20)
总容量: 50 个连接 (原 30)
```

### 3. 自动清理中间件 ✅
- 每个 HTTP 请求结束后自动 `close_session()`
- 异常时也会正确清理
- 位置: `adapters/inbound/fastapi_app/middleware/session_cleanup.py`

### 4. Session 泄漏检测 ✅
- 后台线程每分钟检查超过 5 分钟的 Session
- 自动回滚和关闭泄漏的 Session
- 记录泄漏点调用栈
- 位置: `infrastructure/persistence/orm/session_guard.py`

### 5. 持续监控脚本 ✅
- 每 60 秒检查数据库挂起事务
- 自动终止超过 5 分钟的事务
- 记录告警日志
- 位置: `scripts/fix_idle_transactions.py`

---

## 🐛 常见故障模式

### 模式 1: 连接池耗尽
**症状**: API 响应慢（30秒超时），日志显示 "QueuePool limit"  
**原因**: Session 未关闭，连接以 `idle in transaction` 状态泄漏  
**修复**: 
```bash
python scripts/fix_idle_transactions.py --check --kill --threshold 60
```

### 模式 2: 表锁阻塞
**症状**: 写操作挂起，读操作正常  
**原因**: 未提交的事务持有表锁  
**诊断**:
```sql
SELECT pid, state, wait_event_type, wait_event, left(query, 80)
FROM pg_stat_activity 
WHERE wait_event_type = 'Lock';
```
**修复**: 终止阻塞进程 `SELECT pg_terminate_backend(pid)`

### 模式 3: 数据源超时堆积
**症状**: 日志大量 "Provider baostock.get_klines 超时（>60s）"  
**原因**: 外部数据源网络问题，超时任务占用线程  
**修复**: 临时禁用数据回填任务，等待网络恢复

---

## 📂 关键文件位置

### 配置文件
- [infrastructure/config/settings.py](infrastructure/config/settings.py) - 连接池配置

### 核心代码
- [infrastructure/persistence/orm/config.py](infrastructure/persistence/orm/config.py) - ORM 初始化
- [infrastructure/persistence/orm/session_guard.py](infrastructure/persistence/orm/session_guard.py) - 泄漏检测
- [adapters/inbound/fastapi_app/main.py](adapters/inbound/fastapi_app/main.py) - FastAPI 主程序
- [adapters/inbound/fastapi_app/middleware/session_cleanup.py](adapters/inbound/fastapi_app/middleware/session_cleanup.py) - 清理中间件

### 运维脚本
- [scripts/fix_idle_transactions.py](scripts/fix_idle_transactions.py) - 监控和终止脚本
- [scripts/health_check.sh](scripts/health_check.sh) - 健康检查
- [scripts/emergency_fix.sh](scripts/emergency_fix.sh) - 紧急修复

### 文档
- [docs/SYSTEM-FREEZE-FIX.md](docs/SYSTEM-FREEZE-FIX.md) - 完整诊断报告
- [docs/SYSTEM-FREEZE-FIX-COMPLETE.md](docs/SYSTEM-FREEZE-FIX-COMPLETE.md) - 修复总结

---

## 📞 升级路径

如果以上措施仍无法解决问题：

1. **检查系统资源**: `top`, `free -h`, `df -h`
2. **检查网络**: `ping 8.8.8.8`, `curl -I google.com`
3. **检查 PostgreSQL 日志**: `/usr/local/var/postgres/server.log`
4. **启用 SQL 日志**: 修改 `settings.py` 中 `echo: True`
5. **联系开发团队**: 提供 `~/v2-api.log` 和 `logs/idle_transaction_monitor.log`

---

**最后更新**: 2026-08-28  
**维护者**: PI Investment Team
