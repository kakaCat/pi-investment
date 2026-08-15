# WP-10: Agent OS Scheduler 部署指南

> **创建时间**: 2026-08-15  
> **状态**: Ready for Deployment  
> **相关文档**: [WP-10-SCHEDULER-INTEGRATION.md](plans/WP-10-SCHEDULER-INTEGRATION.md)

---

## 概述

本文档提供 Agent OS Scheduler 集成的部署步骤、配置说明、验证方法和故障排查指南。

## 架构变更

### Before (本地调度)
```
agent-ts
  └── node-cron (本地调度)
       ├── morning_ai_analysis
       ├── realtime_quick_check
       └── daily_ai_review
```

### After (Agent OS 调度)
```
Agent OS Scheduler (集中调度)
  ├── Task: morning_ai_analysis
  ├── Task: realtime_quick_check  
  └── Task: daily_ai_review
       ↓ Cron 触发
  Webhook POST → agent-ts:3002/api/webhook/agent-os/trigger
       ↓ 创建 Session
  执行任务
```

---

## 部署步骤

### Step 1: 配置环境变量

编辑 `agent-ts/.env`：

```bash
# Agent OS Scheduler 集成
AGENT_OS_SCHEDULER_ENABLED=true           # 启用 Agent OS 调度器
AGENT_WEBHOOK_BASE_URL=http://localhost:3002  # Webhook 基础 URL
AGENT_OS_ENABLED=true                     # 启用 Agent OS 客户端
AGENT_OS_URL=http://localhost:8080       # Agent OS API 地址
```

### Step 2: 启动服务

```bash
# 1. 启动 Agent OS
cd agent-os
./scripts/deploy.sh

# 2. 启动 agent-ts
cd agent-ts
npm run dev
```

### Step 3: 验证部署

```bash
# 运行集成测试
cd agent-ts
./scripts/test-agent-os-scheduler.sh
```

---

## 回滚方案

如果需要回滚到本地调度器：

```bash
# 修改环境变量
echo "AGENT_OS_SCHEDULER_ENABLED=false" >> agent-ts/.env

# 重启 agent-ts
cd agent-ts
npm run dev
```

---

详细文档请参考完整版部署指南。

**文档版本**: 1.0  
**最后更新**: 2026-08-15
