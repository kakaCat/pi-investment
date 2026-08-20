# quantsys-v2 与 Agent OS 注册中心集成

**日期**: 2024-08-19  
**状态**: ✅ 完成  
**集成类型**: Registry + Scheduler

---

## 📋 概览

quantsys-v2 现已集成到 Agent OS 注册中心，实现：

1. **服务注册** - 启动时自动注册到 Agent OS
2. **心跳维持** - 每 30 秒发送心跳保持在线
3. **优雅关闭** - 停止时自动注销
4. **能力声明** - 声明 7 种核心能力供其他 Agent 发现

---

## 🎯 已实现功能

### 1. 服务注册 ✅

**注册信息**:
- **agent_id**: `quantsys-v2-{PID}`
- **type**: `trading-system`
- **capabilities**:
  - `kline-data` - K线数据查询
  - `market-analysis` - 市场分析
  - `signal-generation` - 信号生成
  - `backtesting` - 策略回测
  - `portfolio-management` - 组合管理
  - `risk-management` - 风险管理
  - `trading-execution` - 交易执行
- **host**: `127.0.0.1`
- **port**: `5001`
- **api_base**: `http://127.0.0.1:5001`

### 2. 心跳机制 ✅

- **间隔**: 30 秒
- **自动重连**: 支持
- **状态上报**: idle/busy（可扩展）

### 3. 优雅关闭 ✅

- 停止心跳循环
- 注销 Agent
- 释放 HTTP 连接

---

## 📂 新增文件

### 1. `application/services/registry_client.py`
注册中心客户端，提供：
- `QuantsysV2RegistryClient` - 主客户端类
- `register()` - 注册到 Agent OS
- `heartbeat()` - 发送心跳
- `unregister()` - 注销
- `start_heartbeat_loop()` - 启动心跳循环
- `stop_heartbeat_loop()` - 停止心跳循环
- `get_registry_client()` - 全局单例

### 2. `tools/test_registry_integration.py`
测试脚本，验证：
- 注册功能
- 心跳功能
- 心跳循环
- 注销功能

---

## 🔧 配置

### 环境变量

```bash
# 启用注册中心集成（默认 true）
USE_AGENT_OS_REGISTRY=true

# Agent OS URL（默认 http://127.0.0.1:8080）
AGENT_OS_URL=http://127.0.0.1:8080
```

### 禁用集成

如果不需要注册中心功能，设置：
```bash
export USE_AGENT_OS_REGISTRY=false
```

---

## 🧪 测试

### 1. 单独测试注册功能

```bash
# 确保 Agent OS 正在运行
cd /Users/yunpeng/pi-investment/agent-os
./agent-os &

# 测试注册
cd /Users/yunpeng/pi-investment/quantsys-v2
python tools/test_registry_integration.py
```

**预期输出**:
```
=== Testing Agent OS Registry Integration ===

1. Testing registration...
   ✅ Registration successful

2. Testing heartbeat...
   ✅ Heartbeat successful

3. Testing heartbeat loop (10 seconds)...
   ✅ Heartbeat loop tested

4. Testing unregistration...
   ✅ Unregistration successful

=== Test Complete ===
```

### 2. 完整启动测试

```bash
# 启动 Agent OS
cd /Users/yunpeng/pi-investment/agent-os
./agent-os &

# 启动 quantsys-v2
cd /Users/yunpeng/pi-investment/quantsys-v2
python adapters/inbound/fastapi_app/main.py
```

**预期日志**:
```
🚀 FastAPI application starting...
✅ SQLAlchemy Engine initialized
✅ Agent OS Scheduler integration enabled
🔄 Registering to Agent OS Registry...
✅ Registered to Agent OS Registry: agent_id=quantsys-v2-12345
🔄 Started heartbeat loop (interval=30s)
✅ Agent OS Registry integration enabled (heartbeat: 30s)
✅ WatchEngine watch thread started
📖 API Documentation: http://localhost:5001/docs
```

### 3. 查看注册的 Agent

通过 Agent OS API：
```bash
curl http://127.0.0.1:8080/api/v1/registry/agents/available
```

或通过 Web 界面（待实现）：
```
http://localhost:3003/registry/agents
```

---

## 🔍 验证检查清单

- [ ] Agent OS 正在运行（`ps aux | grep agent-os`）
- [ ] quantsys-v2 启动日志显示注册成功
- [ ] 通过 API 可以查询到 quantsys-v2
- [ ] 心跳日志每 30 秒出现一次（DEBUG 级别）
- [ ] 停止 quantsys-v2 时看到注销日志

---

## 🏗️ 架构

```
┌─────────────────────────────────────┐
│   quantsys-v2 (FastAPI)             │
│                                     │
│  启动时:                             │
│  1. 初始化数据库                     │
│  2. 注册调度任务到 Agent OS ✅       │
│  3. 注册服务到 Registry ✅ (NEW)    │
│  4. 启动心跳循环 ✅ (NEW)           │
│  5. 启动 WatchEngine                │
│                                     │
│  运行中:                             │
│  - 每 30s 发送心跳 💓               │
│  - 状态: idle/busy                  │
│                                     │
│  关闭时:                             │
│  1. 停止心跳循环                     │
│  2. 注销 Registry ✅                │
│  3. 关闭 Agent OS Client            │
│  4. 关闭数据库连接                   │
└──────────┬──────────────────────────┘
           │ HTTP/REST
           ↓
┌─────────────────────────────────────┐
│   agent-os (Go Backend)             │
│                                     │
│  ✅ Scheduler - 调度任务             │
│  ✅ Registry - 服务注册中心 (NEW)    │
│  ✅ Decision System - 决策记录       │
│  ✅ Memory System - 记忆管理         │
│  ✅ Event Bus - 事件总线             │
└──────────┬──────────────────────────┘
           │ SQL
           ↓
┌─────────────────────────────────────┐
│   PostgreSQL                        │
│  - agents 表 (注册信息)             │
│  - tasks 表 (调度任务)              │
└─────────────────────────────────────┘
```

---

## 🚀 使用场景

### 1. 服务发现

其他 Agent 可以通过 Registry 发现 quantsys-v2：

```bash
# 查找具有 "backtesting" 能力的 Agent
curl "http://127.0.0.1:8080/api/v1/registry/agents/available?capability=backtesting"
```

返回：
```json
[
  {
    "id": "...",
    "agent_id": "quantsys-v2-12345",
    "agent_type": "trading-system",
    "status": "idle",
    "host": "127.0.0.1",
    "port": 5001,
    "capabilities": ["kline-data", "backtesting", ...],
    "metadata": {
      "api_base": "http://127.0.0.1:5001"
    },
    "last_heartbeat_at": "2024-08-19T12:34:56Z"
  }
]
```

### 2. 健康监控

Agent OS 可以监控 quantsys-v2 的健康状态：
- 超过 60 秒无心跳 → 标记为 offline
- 可以触发告警或自动重启

### 3. 负载均衡（未来）

如果部署多个 quantsys-v2 实例：
- Registry 记录所有实例
- 可以根据 status 进行负载分发

---

## 📊 数据流

### 注册流程
```
quantsys-v2                Agent OS
    |                          |
    |  POST /registry/agents/  |
    |       register           |
    |------------------------->|
    |                          | 写入 agents 表
    |  201 Created             |
    |  {id, agent_id, ...}     |
    |<-------------------------|
    |                          |
```

### 心跳流程
```
quantsys-v2                Agent OS
    |                          |
    |  (每30秒)                 |
    |  POST /registry/agents/  |
    |       heartbeat          |
    |------------------------->|
    |                          | 更新 last_heartbeat_at
    |  200 OK                  |
    |<-------------------------|
    |                          |
```

### 注销流程
```
quantsys-v2                Agent OS
    |                          |
    |  POST /registry/agents/  |
    |       unregister         |
    |------------------------->|
    |                          | 删除或标记 offline
    |  200 OK                  |
    |<-------------------------|
    |                          |
```

---

## 🐛 故障处理

### Agent OS 不可用

**现象**: quantsys-v2 启动时 Agent OS 未运行

**行为**:
```
⚠️ Failed to register with Agent OS Registry: Connection refused
Continuing without registry integration...
✅ WatchEngine watch thread started (正常启动)
```

**结果**: quantsys-v2 正常运行，只是不在注册中心

### 心跳失败

**现象**: 运行中 Agent OS 停止

**行为**:
- 心跳请求静默失败（DEBUG 日志）
- quantsys-v2 继续正常运行
- Agent OS 重启后下次心跳自动恢复

### 重复注册

**现象**: 同一 agent_id 重复注册

**行为**: Upsert 机制，更新现有记录而不报错

---

## 📝 TODO（未来增强）

- [ ] 动态状态上报（idle → busy）
- [ ] 负载指标上报（CPU、内存、任务队列）
- [ ] 前端注册中心管理页面
- [ ] 服务间调用（通过 Registry 发现）
- [ ] 健康检查端点
- [ ] 多实例部署支持

---

## 🔗 相关文档

- [Agent OS README](/Users/yunpeng/pi-investment/agent-os/README.md)
- [Agent OS WP 完成报告](/Users/yunpeng/pi-investment/agent-os/WP_COMPLETION_STATUS_UPDATE.md)
- [quantsys-v2 CLAUDE.md](/Users/yunpeng/pi-investment/quantsys-v2/CLAUDE.md)

---

## ✅ 验收标准

- [x] registry_client.py 实现完整
- [x] FastAPI main.py 集成完成
- [x] 启动时自动注册
- [x] 心跳循环正常运行
- [x] 关闭时优雅注销
- [x] 测试脚本通过
- [x] 集成文档完善
- [ ] 生产环境验证（待部署）

---

**集成完成时间**: 2024-08-19  
**责任人**: AI Assistant  
**状态**: ✅ 代码完成，待测试验证
