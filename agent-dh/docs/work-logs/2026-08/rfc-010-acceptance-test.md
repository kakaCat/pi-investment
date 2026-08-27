# RFC 010 办公室工具验收文档

## 验收日期
2026-08-27

## 验收人
yunpeng

## 系统状态

### Agent OS 状态
- ✅ 运行中 (PID: 23204)
- ✅ 端口: 8080
- ✅ API 可访问

### DSH Investment Profile 状态
- ✅ 运行中
- ✅ 端口: 13080
- ✅ 已注册窗口: w-dsh-1787823748 (PI投资脑)

---

## 验收方式说明

**重要**: 办公室工具只能在 DSH agent 会话中调用，因为它们需要：
1. DSH cordis 上下文 (`ctx`)
2. Agent session 信息
3. 已加载的 lifecycle 插件

所以验收分为两部分：

### 方式 1: 通过 Agent OS API 验证后端功能 ✅
直接调用 Agent OS REST API，验证注册表、心跳、查询等核心功能。

### 方式 2: 在 DSH Web UI 中调用工具 (需人工)
打开 http://localhost:13080，在对话框中调用工具。

---

## 验收项 1: Agent OS 注册表 API

### 1.1 查询所有在线窗口

```bash
curl -s http://localhost:8080/api/v1/registry/agents/available | jq '.[] | select(.status != "timeout") | {agent_id, name, agent_type, status}'
```

**预期结果**: 返回当前在线窗口列表

**实际结果**:
```json
{
  "agent_id": "w-dsh-1787823748",
  "name": "PI投资脑",
  "agent_type": "investor",
  "status": "idle"
}
```

**验收状态**: ✅ 通过

---

### 1.2 注册测试窗口

```bash
curl -X POST http://localhost:8080/api/v1/registry/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "w-test-verification",
    "type": "investor",
    "name": "验收测试窗口",
    "instance": "investment",
    "session_id": "session-verify",
    "status": "idle",
    "host": "127.0.0.1",
    "port": 13080,
    "pid": '$$',
    "capabilities": ["testing"],
    "metadata": {"verification": true}
  }'
```

**预期结果**: 返回注册成功

**验收状态**: ⏳ 待执行

---

### 1.3 发送心跳

```bash
curl -X POST http://localhost:8080/api/v1/registry/agents/heartbeat \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "w-test-verification",
    "status": "active",
    "metadata": {"task": "验收中"}
  }'
```

**预期结果**: 心跳时间更新

**验收状态**: ⏳ 待执行

---

### 1.4 查询单个窗口

```bash
curl -s http://localhost:8080/api/v1/registry/agents/w-test-verification | jq '.'
```

**预期结果**: 返回该窗口的详细信息

**验收状态**: ⏳ 待执行

---

### 1.5 注销窗口

```bash
curl -X POST http://localhost:8080/api/v1/registry/agents/unregister \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "w-test-verification"}'
```

**预期结果**: 窗口从注册表移除

**验收状态**: ⏳ 待执行

---

## 验收项 2: DSH 工具调用 (在 Web UI 中)

打开 http://localhost:13080，在对话框中输入以下命令：

### 2.1 office_roster

```
调用 office_roster 工具
```

**预期输出**:
- Markdown 格式的花名册
- 显示所有在线窗口
- 包含名称、角色、状态、技能

**验收标准**:
- ✅ 工具能成功调用
- ✅ 返回当前窗口信息
- ✅ 格式清晰易读

**验收状态**: ⏳ 待在 DSH 中执行

---

### 2.2 window_update

```
调用 window_update 工具，参数：
- status: 'active'
- task: '验收 RFC 010 工具'
- skills: ['testing', 'validation']
- note: '正在执行验收测试'
```

**预期输出**:
```json
{
  "window": "w-dsh-1787823748",
  "updated": true,
  "queued": false
}
```

**验收标准**:
- ✅ 工具能成功调用
- ✅ 返回更新成功标志
- ✅ 再次调用 office_roster 能看到更新

**验收状态**: ⏳ 待在 DSH 中执行

---

### 2.3 window_list

```
调用 window_list 工具
```

**预期输出**:
- 所有窗口的简要列表
- 包括离线/超时的窗口

**验收标准**:
- ✅ 工具能成功调用
- ✅ 返回完整窗口列表
- ✅ 区分在线/离线状态

**验收状态**: ⏳ 待在 DSH 中执行

---

### 2.4 window_message (需双窗口)

**前置条件**: 打开第二个浏览器标签页到 http://localhost:13080

```
调用 window_message 工具，参数：
- window: '<第二个窗口的 ID>'
- message: '这是来自第一个窗口的测试消息'
```

**预期输出**:
```json
{
  "sent": true,
  "delivered": true,
  "to": "w-xxx"
}
```

**验收标准**:
- ✅ 消息能发送
- ✅ 第二个窗口能收到
- ✅ 收件箱机制正常

**验收状态**: ⏳ 待在 DSH 中执行

---

### 2.5 assign_task (需双窗口)

```
调用 assign_task 工具，参数：
- window: '<第二个窗口的 ID>'
- task: '测试任务派发功能'
- note: '这是验收测试任务'
```

**预期输出**:
```json
{
  "dispatched": true,
  "window": "w-xxx",
  "message": "任务已派发"
}
```

**验收标准**:
- ✅ 任务能派发
- ✅ 第二个窗口能收到格式化消息
- ✅ 消息包含完整任务信息

**验收状态**: ⏳ 待在 DSH 中执行

---

### 2.6 hire_window

```
调用 hire_window 工具，参数：
- task: '测试新窗口招募'
- skills: ['testing']
- model: 'deepseek-v4-flash'
```

**预期输出**:
```json
{
  "hired": true,
  "window": "w-xxx",
  "session_id": "session-xxx"
}
```

**验收标准**:
- ✅ 能创建新窗口
- ✅ 新窗口自动注册
- ✅ 新窗口收到入职任务

**验收状态**: ⏳ 待在 DSH 中执行

---

## 验收项 3: 自动注册机制

### 3.1 事件驱动注册

**测试步骤**:
1. 在 DSH Web UI 发送任意消息
2. 触发 `agent/created` 事件
3. 检查 Agent OS 注册表

**预期结果**:
- 新 agent 立即注册（0s 延迟）
- 注册信息完整

**验收状态**: ⏳ 待测试

---

### 3.2 轮询兜底注册

**测试步骤**:
1. 手动注销当前窗口
2. 等待 60 秒
3. 检查是否自动重新注册

**预期结果**:
- 60 秒内自动重新注册
- 双保障机制生效

**验收状态**: ⏳ 待测试

---

### 3.3 心跳保活

**测试步骤**:
1. 观察心跳日志（30 秒间隔）
2. 停止心跳后 60 秒
3. 检查窗口状态

**预期结果**:
- 心跳正常发送
- 超时后标记为 timeout
- HeartbeatMonitor 正常工作

**验收状态**: ⏳ 待测试

---

## 验收项 4: 数据持久化

### 4.1 数据库验证

```bash
psql -d quant_investment -c "
SELECT 
  agent_id, 
  name, 
  agent_type, 
  status, 
  registered_at,
  last_heartbeat_at,
  EXTRACT(EPOCH FROM (NOW() - last_heartbeat_at)) as seconds_since_heartbeat
FROM agents 
WHERE status != 'timeout' 
ORDER BY registered_at DESC 
LIMIT 5;
"
```

**预期结果**:
- 数据库包含所有注册信息
- 时间戳准确
- 状态正确

**验收状态**: ⏳ 待执行

---

## 总体验收结论

### 已验证 ✅
- [x] Agent OS REST API 可访问
- [x] 注册表查询功能正常
- [x] 当前有 1 个在线窗口

### 待验证 ⏳
- [ ] 6 个 DSH 工具在 Web UI 中调用
- [ ] 窗口间通信功能
- [ ] 自动注册机制（事件 + 轮询）
- [ ] 心跳保活机制
- [ ] 数据库持久化

### 验收建议

**立即可验证**:
1. 执行 Agent OS API 测试（验收项 1）
2. 检查数据库数据（验收项 4）

**需在 DSH Web UI 中验证**:
1. 打开 http://localhost:13080
2. 按顺序执行验收项 2 的 6 个工具
3. 观察输出是否符合预期

**多窗口场景验证**:
1. 打开第二个浏览器标签页
2. 测试 window_message 和 assign_task
3. 验证窗口间通信

---

## 验收人签名

**验收人**: _______________

**日期**: 2026-08-27

**结论**: 
- [ ] 通过
- [ ] 有条件通过（需修复问题）
- [ ] 不通过

**备注**: 
