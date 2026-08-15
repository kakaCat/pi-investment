# WP-10: Agent OS Scheduler 故障排查指南

> **创建时间**: 2026-08-15  
> **适用版本**: WP-10 及以后  
> **相关文档**: [WP-10-DEPLOYMENT.md](WP-10-DEPLOYMENT.md)

---

## 快速诊断

### 健康检查清单

```bash
# 1. Agent OS
curl -sf http://localhost:8080/health

# 2. agent-ts Webhook
curl -sf http://localhost:3002/api/health

# 3. 环境变量
echo $AGENT_OS_SCHEDULER_ENABLED

# 4. 任务数量
curl -s http://localhost:8080/api/v1/scheduler/tasks?owner=fin-agent | jq length
```

---

## 常见问题

### 问题 1: 任务未自动注册

**症状**: agent-ts 启动时没有任务注册日志

**解决方案**:

```bash
# 1. 确保 Agent OS 运行
curl http://localhost:8080/health

# 2. 确认环境变量
cat agent-ts/.env | grep AGENT_OS_SCHEDULER_ENABLED

# 3. 重启 agent-ts
cd agent-ts
npm run dev
```

---

### 问题 2: Webhook 触发失败

**症状**: Agent OS 显示任务已触发，但 agent-ts 无反应

**解决方案**:

```bash
# 1. 测试 webhook 端点
curl http://localhost:3002/api/webhook/agent-os/trigger \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test",
    "task_name": "test",
    "execution_id": "test",
    "payload": {
      "kind": "agent_turn",
      "message": "test"
    }
  }'

# 2. 检查 agent-ts 是否启动
ps aux | grep "node.*agent-ts"

# 3. 查看日志
tail -f ~/agent-ts.log | grep Webhook
```

---

### 问题 3: 任务执行报错

**症状**: Webhook 成功触发但任务执行失败

**解决方案**:

```bash
# 1. 查看详细错误
tail -100 ~/agent-ts.log | grep -A 20 "Webhook"

# 2. 检查后端服务
curl http://localhost:5001/health

# 3. 检查 LLM API
echo $DEEPSEEK_API_KEY
```

---

### 问题 4: 任务重复执行

**症状**: 同一个任务在短时间内执行多次

**解决方案**:

```bash
# 1. 检查运行的进程
ps aux | grep "node.*agent-ts"

# 2. 清理重复任务
for task_id in $(curl -s http://localhost:8080/api/v1/scheduler/tasks?owner=fin-agent | jq -r '.[].id'); do
  curl -X DELETE http://localhost:8080/api/v1/scheduler/tasks/$task_id
done

# 3. 重启 agent-ts
cd agent-ts
npm run dev
```

---

## 高级调试

### 1. 启用详细日志

```bash
# agent-ts/.env
LOG_LEVEL=debug
```

### 2. 手动模拟 Webhook 调用

```bash
curl -X POST http://localhost:3002/api/webhook/agent-os/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "task_name": "morning_ai_analysis",
    "execution_id": "660e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "kind": "agent_turn",
      "message": "执行早盘分析任务",
      "agentKind": "fin"
    }
  }' \
  -w "\n\nHTTP Status: %{http_code}\nTime: %{time_total}s\n"
```

---

**文档版本**: 1.0  
**最后更新**: 2026-08-15
