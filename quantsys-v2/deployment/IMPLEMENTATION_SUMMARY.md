# V13策略企业级调度系统实施总结

## 项目概述

将V13策略的定时任务从传统的crontab管理升级为**企业级调度系统**，实现：
- 数据库持久化配置
- RESTful API管理
- Web界面监控
- 独立服务进程
- 完整执行日志

## 实施成果

### ✅ 1. 后端调度系统

#### 1.1 数据库配置
- **表结构**:
  - `scheduler_task_configs` - 任务配置表
  - `apscheduler_jobs` - APScheduler内置调度状态表
  - `scheduler_runs` - 执行历史记录表

- **已配置任务**:
  | 任务名称 | 执行时间 | 描述 |
  |---------|---------|------|
  | v13_daily_trading | 交易日 14:25 | V13模拟交易每日检查 - 检查止损、调仓 |
  | kline_update | 交易日 16:00 | K线数据更新 - 更新创业板K线数据 |
  | v13_verification | 交易日 15:30 | V13预测验证 - 验证5天前的预测准确性 |
  | v13_risk_check | 交易日 16:00 | V13风险检查 - 检查账户风险指标 |
  | v13_weekly_report | 每周一 09:00 | V13周报生成 - 生成周度策略表现报告 |
  | data_quality_check | 交易日 08:00 | 数据质量检查 - 检查K线和因子数据完整性 |

#### 1.2 调度服务
- **文件**: `scheduler_daemon.py`
- **功能**:
  - 独立守护进程
  - 动态加载数据库任务配置
  - 支持优雅启动/停止
  - 完整日志记录
  - 健康检查和自动重启

#### 1.3 RESTful API
- **端点**: `http://127.0.0.1:5001/api/scheduler/*`
- **功能**:
  ```bash
  GET  /api/scheduler/status              # 调度器状态
  GET  /api/scheduler/tasks               # 任务列表
  GET  /api/scheduler/tasks/{name}        # 任务详情
  POST /api/scheduler/tasks/{name}/enable  # 启用任务
  POST /api/scheduler/tasks/{name}/disable # 禁用任务
  POST /api/scheduler/tasks/{name}/trigger # 手动触发
  GET  /api/scheduler/history             # 执行历史
  ```

#### 1.4 服务化部署
- **macOS**: `deployment/quantsys-scheduler.plist` (launchd)
- **Linux**: `deployment/quantsys-scheduler.service` (systemd)
- **启动方式**:
  ```bash
  # 前台运行
  python3 scheduler_daemon.py
  
  # macOS开机自启动
  cp deployment/quantsys-scheduler.plist ~/Library/LaunchAgents/
  launchctl load ~/Library/LaunchAgents/quantsys-scheduler.plist
  launchctl start com.quantsys.scheduler
  
  # Linux开机自启动
  sudo cp deployment/quantsys-scheduler.service /etc/systemd/system/
  sudo systemctl enable quantsys-scheduler
  sudo systemctl start quantsys-scheduler
  ```

### ✅ 2. 前端监控界面

#### 2.1 页面位置
- **URL**: `http://localhost:3001/simulation-trading`
- **文件**: `web-frontend/src/views/SimulationTrading/index.vue`

#### 2.2 新增功能
- **V13调度任务卡片**:
  - 显示所有V13相关任务
  - 实时任务状态（启用/禁用）
  - 执行时间（Cron表达式）
  - 任务描述信息

- **任务操作**:
  - ✅ 启用/禁用任务按钮
  - ✅ 手动触发执行按钮
  - ✅ 自动刷新（30秒）

- **执行历史**:
  - 最近10条执行记录
  - 执行状态（成功/失败）
  - 执行时间和耗时
  - 错误信息展示

#### 2.3 界面预览
```
┌─────────────────────────────────────────┐
│ ⏰ V13调度任务              [刷新]      │
├─────────────────────────────────────────┤
│ 任务名称 | 描述 | 执行时间 | 状态 | 操作 │
│ v13_daily_trading | ... | 25 14... | ✓ 启用 | [禁用][触发] │
│ kline_update      | ... | 0 16...  | ✓ 启用 | [禁用][触发] │
│ ...                                      │
├─────────────────────────────────────────┤
│ 最近执行记录                             │
│ 任务 | 状态 | 开始时间 | 耗时 | 错误    │
│ v13_daily_trading | ✓ 成功 | 2026-06-30... | 234ms | - │
└─────────────────────────────────────────┘
```

## 架构对比

### 之前 (Crontab)
```
❌ 配置分散在crontab和代码中
❌ 无法动态管理（需要编辑crontab）
❌ 没有统一的执行日志
❌ 无法通过API查询和控制
❌ 无Web界面监控
❌ 启动停止需要手动管理
```

### 现在 (企业级系统)
```
✅ 任务配置集中在数据库
✅ 支持动态启用/禁用/触发
✅ 完整的执行记录和日志
✅ RESTful API统一管理
✅ Web界面实时监控
✅ systemd/launchd服务管理
✅ 开机自启动
```

## 技术栈

### 后端
- **调度引擎**: APScheduler 3.x
- **持久化**: PostgreSQL
- **API框架**: Flask
- **ORM**: SQLAlchemy
- **进程管理**: systemd/launchd

### 前端
- **框架**: Vue 3 + TypeScript
- **UI组件**: Element Plus
- **图表**: ECharts
- **状态管理**: Vue Composition API

## 使用指南

### 1. 启动调度服务
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python3 scheduler_daemon.py
```

### 2. 访问Web界面
```bash
# 打开浏览器访问
http://localhost:3001/simulation-trading
```

### 3. API调用示例
```bash
# 查看所有任务
curl http://127.0.0.1:5001/api/scheduler/tasks

# 手动触发任务
curl -X POST http://127.0.0.1:5001/api/scheduler/tasks/v13_daily_trading/trigger

# 查看执行历史
curl http://127.0.0.1:5001/api/scheduler/history?limit=10
```

### 4. 查看日志
```bash
# 调度器日志
tail -f logs/scheduler_daemon.log

# 错误日志
tail -f logs/scheduler_daemon_error.log
```

## 文件清单

### 后端文件
```
quantsys-v2/
├── scheduler_daemon.py                           # 调度器守护进程
├── application/services/
│   ├── enterprise_scheduler.py                   # 企业级调度服务
│   └── unified_scheduler.py                      # 统一调度服务
├── adapters/
│   ├── inbound/api/routes/
│   │   └── scheduler_enterprise.py               # 调度器管理API
│   └── outbound/repositories/
│       └── scheduler_repository.py               # 调度任务Repository
├── infrastructure/
│   ├── persistence/orm/models/
│   │   └── scheduler.py                          # 调度任务ORM模型
│   └── jobs/                                     # Job任务文件
│       ├── v13_trading_job.py
│       ├── kline_update_job.py
│       ├── verification_job.py
│       ├── risk_check_job.py
│       ├── weekly_report_job.py
│       └── data_quality_check_job.py
├── scripts/
│   └── init_v13_scheduler.py                     # 初始化脚本
└── deployment/
    ├── quantsys-scheduler.plist                  # macOS服务配置
    ├── quantsys-scheduler.service                # Linux服务配置
    ├── README.md                                 # 部署文档
    └── IMPLEMENTATION_SUMMARY.md                 # 本文档
```

### 前端文件
```
web-frontend/
└── src/views/SimulationTrading/
    └── index.vue                                 # 模拟交易监控页面（已更新）
```

## 数据流程

```
┌──────────────┐
│  数据库配置   │ scheduler_task_configs
└──────┬───────┘
       │
       ↓
┌──────────────┐
│scheduler_daemon│ 加载任务配置
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ APScheduler  │ 定时触发
└──────┬───────┘
       │
       ↓
┌──────────────┐
│   Job执行    │ v13_trading_job等
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ 执行记录保存  │ scheduler_runs
└──────────────┘
       │
       ↓
┌──────────────┐
│  API查询     │ /api/scheduler/history
└──────┬───────┘
       │
       ↓
┌──────────────┐
│  Web界面展示  │ simulation-trading页面
└──────────────┘
```

## 监控和维护

### 健康检查
```bash
# 检查调度器进程
ps aux | grep scheduler_daemon

# 检查任务状态
curl http://127.0.0.1:5001/api/scheduler/status
```

### 日志分析
```bash
# 查看今天的执行日志
grep "$(date +%Y-%m-%d)" logs/scheduler_daemon.log

# 查看失败的任务
grep "ERROR" logs/scheduler_daemon.log
```

### 故障恢复
```bash
# 重启调度器
pkill -f scheduler_daemon.py
python3 scheduler_daemon.py &

# 或使用systemd/launchd重启
launchctl restart com.quantsys.scheduler
```

## 后续改进方向

### 1. 任务监控告警（待实现）
- [ ] 集成飞书webhook
- [ ] 任务失败自动通知
- [ ] 任务超时告警
- [ ] 邮件通知支持

### 2. 高级功能
- [ ] 任务依赖关系
- [ ] 任务重试机制
- [ ] 分布式调度支持
- [ ] Web管理后台
- [ ] 任务执行统计图表

### 3. 性能优化
- [ ] 任务执行性能监控
- [ ] 数据库查询优化
- [ ] 日志归档策略
- [ ] 历史数据清理

## 总结

✅ **企业级调度系统实施完成！**

- 6个V13任务已配置到数据库
- 独立调度服务进程运行正常
- RESTful API管理接口可用
- Web界面实时监控上线
- 开机自启动配置就绪

系统已准备好投入生产使用，从传统crontab成功升级为现代化的企业级调度平台。

---

**实施日期**: 2026-06-30  
**实施人员**: System Team  
**文档版本**: v1.0
