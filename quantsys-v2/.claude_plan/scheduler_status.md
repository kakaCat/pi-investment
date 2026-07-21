# 调度任务系统问题总结

**检查日期:** 2026-06-24  
**状态:** ⚠️ **Scheduler 服务未运行**

---

## 问题概述

### 核心问题
❌ **Scheduler 服务进程未启动**
- 数据库中有 18 个调度任务配置
- API 可以查询和管理任务
- 但实际执行器(scheduler.py)未运行
- **结果:所有定时任务都不会执行**

---

## 详细检查结果

### ✅ 已完成的 SQLAlchemy 迁移
1. ✅ scheduler.py 已迁移到 `engine.raw_connection()`
2. ✅ 所有方法(13个)已加 `finally: conn.close()` 归还连接
3. ✅ 无遗留 `_ensure_db()` 或 `init_connection_pool()` 调用
4. ✅ 编译通过,代码语法正确

### ❌ 服务未启动
```bash
$ ps aux | grep scheduler
# 无输出 - 服务未运行
```

### ✅ 任务配置正常
```bash
$ curl http://127.0.0.1:5001/api/scheduler/tasks
# 返回 18 个任务配置
# 所有任务均为 enabled: true
```

### ❌ 无执行记录
```bash
$ curl http://127.0.0.1:5001/api/scheduler/runs
# 返回空列表或格式错误
# 说明近期无任务执行
```

---

## 根本原因

**Scheduler 是独立的后台服务进程,需要手动启动。**

SQLAlchemy 迁移只改了代码,但:
1. 没有重启 scheduler 服务(如果之前在运行)
2. 或者 scheduler 从未启动过

---

## 解决方案

### 方案 1: 手动启动 Scheduler 服务

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 后台启动 scheduler
nohup python infrastructure/scheduler/scheduler.py > /tmp/scheduler.log 2>&1 &

# 记录 PID
echo $! > /tmp/scheduler.pid

# 验证启动
sleep 3
ps aux | grep scheduler.py | grep -v grep
```

### 方案 2: 使用 systemd 服务(推荐生产环境)

```ini
# /etc/systemd/system/quantsys-scheduler.service
[Unit]
Description=QuantSys V2 Scheduler Service
After=network.target postgresql.service

[Service]
Type=simple
User=mac
WorkingDirectory=/Users/mac/Documents/ai/pi-investment/quantsys-v2
ExecStart=/Users/mac/Documents/ai/pi-investment/quantsys-v2/.venv/bin/python infrastructure/scheduler/scheduler.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/quantsys-scheduler.log
StandardError=append:/var/log/quantsys-scheduler.log

[Install]
WantedBy=multi-user.target
```

```bash
# 启动服务
sudo systemctl daemon-reload
sudo systemctl start quantsys-scheduler
sudo systemctl enable quantsys-scheduler
sudo systemctl status quantsys-scheduler
```

### 方案 3: 使用 supervisor(推荐)

```ini
# /etc/supervisor/conf.d/quantsys-scheduler.conf
[program:quantsys-scheduler]
command=/Users/mac/Documents/ai/pi-investment/quantsys-v2/.venv/bin/python infrastructure/scheduler/scheduler.py
directory=/Users/mac/Documents/ai/pi-investment/quantsys-v2
user=mac
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/quantsys-scheduler.log
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start quantsys-scheduler
sudo supervisorctl status
```

---

## 启动后验证

### 1. 检查进程
```bash
ps aux | grep scheduler.py
# 应看到进程
```

### 2. 检查日志
```bash
tail -f /tmp/scheduler.log
# 应看到类似:
# INFO - Scheduler started with 18 tasks
# INFO - Next run: task_name at 2026-06-24 16:00:00
```

### 3. 检查执行记录
```bash
# 等待几分钟后
curl http://127.0.0.1:5001/api/scheduler/runs?limit=5
# 应看到最近执行记录
```

### 4. 检查数据库连接
```bash
lsof -nP -iTCP:5432 | grep scheduler
# 应看到 scheduler 进程的连接
```

---

## SQLAlchemy 迁移对 Scheduler 的影响

### ✅ 迁移已完成
| 项目 | 状态 | 说明 |
|---|---|---|
| 连接获取 | ✅ | `engine.raw_connection()` |
| 连接归还 | ✅ | 15 处 `conn.close()` |
| 线程安全 | ✅ | 方法级借还,无全局缓存 |
| 旧 API 移除 | ✅ | 无 `_ensure_db()` 残留 |
| 编译验证 | ✅ | 无语法错误 |

### 📝 需要注意
1. **Scheduler 需要初始化 Engine**
   ```python
   # scheduler.py 应在启动时调用
   from infrastructure.persistence.database.engine import init_engine
   init_engine(pool_size=5, max_overflow=10)
   ```

2. **连接池容量规划**
   - Scheduler 建议: pool_size=5, max_overflow=10 (总容量 15)
   - 避免与 API 服务(容量 30)争抢连接

3. **监控 Scheduler 连接数**
   ```bash
   lsof -nP -iTCP:5432 | grep scheduler | wc -l
   # 应 <= 15
   ```

---

## 检查清单

启动 Scheduler 前:
- [x] SQLAlchemy 迁移已完成
- [x] scheduler.py 编译通过
- [ ] **Engine 初始化代码已加(需确认)**
- [ ] 日志目录可写
- [ ] PostgreSQL 可连接

启动 Scheduler 后:
- [ ] 进程正在运行
- [ ] 日志无错误
- [ ] 有执行记录产生
- [ ] 连接数正常(< 15)

---

## 建议

### 立即执行
1. **检查 scheduler.py 是否调用 `init_engine()`**
   ```bash
   grep -n "init_engine" infrastructure/scheduler/scheduler.py
   ```
   如果没有,需要在 `if __name__ == "__main__"` 块加上

2. **手动启动 scheduler 测试**
   ```bash
   cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
   python infrastructure/scheduler/scheduler.py
   # 观察输出,按 Ctrl+C 停止
   ```

3. **如果正常,后台启动**
   ```bash
   nohup python infrastructure/scheduler/scheduler.py > /tmp/scheduler.log 2>&1 &
   ```

### 生产环境
- 使用 systemd 或 supervisor 管理 scheduler 进程
- 配置自动重启(Restart=always)
- 配置日志轮转(避免日志文件过大)
- 添加健康检查(定期检查进程是否存在)

---

## 总结

**调度任务的问题不是 SQLAlchemy 迁移造成的,而是 Scheduler 服务本身未运行。**

✅ **迁移工作已完成:** scheduler.py 代码已正确迁移到 SQLAlchemy Engine  
❌ **运维问题:** Scheduler 服务进程需要启动  

**下一步:** 启动 Scheduler 服务并验证任务执行正常。
