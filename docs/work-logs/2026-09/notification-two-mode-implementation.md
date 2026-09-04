# 通知系统双模式实施计划

**创建时间**: 2026-09-02  
**状态**: 规划中

## 背景

当前通知系统存在架构问题：
1. quantsys-v2 所有通知都调用 `/wake` 唤醒 agent
2. 导致大量不需要 agent 决策的通知也消耗 token
3. agent-os 已经实现了 `/api/v1/notifications/send` 端点（直接发送+记录），但 v2 没有使用

## 目标

实现两种通知模式：

### Mode 1: Wake Agent（需要决策）
- **路径**: v2 → agent-os `/wake` → agent 决策 → agent 调用 notification_send 工具
- **场景**: agent 自己账户的交易、需要智能分析的场景
- **Token**: 高消耗（agent 参与决策）

### Mode 2: Direct Send（不需要决策）
- **路径**: v2 → agent-os `/api/v1/notifications/send` → 记录+发送飞书
- **场景**: 盯盘触发、风险告警、日报、信号推送等大部分通知
- **Token**: 零消耗（agent 不参与）

## 实施步骤

### Phase 1: 扩展 AgentNotificationService

在 `quantsys-v2/application/services/agent_notification_service.py` 中：

1. 添加 `send_notification()` 方法，调用 agent-os 的 `/api/v1/notifications/send`
2. 保留 `notify_agent()` 方法，继续调用 `/wake`
3. 添加配置项区分两种模式

```python
def send_notification(self, title: str, content: str, 
                     priority: str = 'normal') -> bool:
    """直接发送通知（不唤醒 agent）
    
    Args:
        title: 通知标题
        content: 通知内容
        priority: 优先级 (low/normal/high/urgent)
    
    Returns:
        是否成功发送
    """
    # 调用 agent-os /api/v1/notifications/send
    pass
```

### Phase 2: 修改通知调用方

识别哪些场景需要哪种模式：

#### 使用 Direct Send 的场景
- ✅ 盯盘触发 (`watch_triggered`)
- ✅ 风险告警 (`risk_alert`)
- ✅ 日报 (`daily_report`)
- ✅ 信号推送 (`signals_ready`)
- ✅ 股池变化 (`pool_changed`)
- ✅ 止损触发 (`stop_loss_triggered`)

#### 使用 Wake Agent 的场景
- ✅ agent 自己账户交易 (`agent_account_trade_signal`)
- ✅ 需要复杂决策的场景

修改文件：
- `application/services/watch_engine/notifier.py`
- `application/services/scheduler_tasks.py`
- 其他调用 `agent_service.notify_agent()` 的地方

### Phase 3: 测试验证

1. 单元测试：测试两种模式的调用
2. 集成测试：验证 agent-os 端点正确响应
3. 生产验证：检查通知是否正确发送和记录

## 预期效果

- **Token 消耗降低 80%+**（大部分通知不再唤醒 agent）
- **通知延迟降低**（直接发送，不等待 agent 处理）
- **agent-os 完整记录**（所有通知都有日志）
- **agent 专注决策**（只在需要时被唤醒）

## 风险与缓解

### 风险
1. agent-os `/api/v1/notifications/send` 端点可能有 bug
2. 现有代码依赖 agent 处理通知内容格式化

### 缓解
1. 先在非关键通知上测试（如日报）
2. 保留降级机制：agent-os 失败时降级到原有 wake 模式
3. 逐步迁移，先观察一周效果

## 时间估算

- Phase 1: 2 小时
- Phase 2: 4 小时
- Phase 3: 2 小时
- **总计**: 1 个工作日

## 验收标准

- [ ] `AgentNotificationService` 支持两种模式
- [ ] 80%+ 通知使用 Direct Send 模式
- [ ] agent-os 正确记录所有通知
- [ ] Token 消耗显著降低
- [ ] 所有测试通过
