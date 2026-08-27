# 盯盘冷却期通知功能实现

Date: 2026-08-14
Author: Claude (with user)

## 背景

### 问题发现
通过排查发现盯盘功能存在以下问题：

1. **冷却期状态在内存中**，服务重启后丢失
2. **冷却期内的触发被完全跳过**，用户不知道系统是否还在监控
3. **最近2天32次触发中，有8次违反了冷却期**（最短间隔64秒，应为300秒）

### 现有机制
- 默认冷却期：**5分钟（300秒）**
- 冷却期状态：`self._last_triggered` 字典（内存）
- 冷却期内的触发：直接 `continue` 跳过，无任何通知

## 需求

**改进目标**：
1. ✅ 冷却期内仍然发送通知，让用户知道"系统还在盯着"
2. ✅ 不唤醒 Agent，避免重复决策浪费资源
3. ✅ 记录所有触发历史（包括冷却期内的）
4. ✅ 区分正常触发和冷却期触发

## 实现方案

### 架构设计

```
触发检测
    ↓
条件满足？
    ↓
是 → 在冷却期？
        ├─ 是 → notify_cooldown()
        │       ├─ 发送简化消息（WS/飞书）
        │       ├─ 记录触发（notified=false）
        │       └─ 不唤醒 Agent ✅
        │
        └─ 否 → notify()
                ├─ 唤醒 Agent
                ├─ 发送完整通知
                ├─ 记录触发（notified=true）
                └─ 更新 _last_triggered
```

### 代码变更

#### 1. 新增 `notify_cooldown()` 方法
**文件**：`quantsys-v2/application/services/watch_engine/notifier.py`

```python
def notify_cooldown(self, rule, condition: dict, quote, result) -> None:
    """冷却期内的触发 - 发送简化通知，不唤醒 Agent"""
    payload = self._build_payload(rule, condition, quote, result)
    payload['in_cooldown'] = True
    payload['message'] = f'持续监控中（冷却期），{result.message}'
    
    self._broadcast_ws_cooldown(payload)
    self._send_feishu_cooldown_notification(payload)
    self._record(rule, condition, quote, result, notified=False)
```

**关键点**：
- `in_cooldown=True` 标记
- `notified=False` 表示未唤醒 Agent
- 使用单独的 WS 事件类型 `watch_cooldown`

#### 2. 新增飞书轻量通知
**方法**：`_send_feishu_cooldown_notification()`

发送简单文本消息：
```
📊 盯盘提醒（持续监控）
股票：双环传动(002472.SZ)
当前价格：¥38.25
触发原因：成交量为同期均量 2.57x（阈值 2.5x）
说明：系统正在持续监控，暂不需要操作
```

#### 3. 修改 WatchEngine 触发逻辑
**文件**：`quantsys-v2/application/services/watch_engine/engine.py`

**Before**：
```python
if self._in_cooldown(rule.id, idx, cond, now):
    continue  # 直接跳过，无任何通知
```

**After**：
```python
in_cooldown = self._in_cooldown(rule.id, idx, cond, now)

if in_cooldown:
    # 冷却期内：发送简化通知，不唤醒 Agent
    self.notifier.notify_cooldown(rule, cond, quote, result)
    continue

# 正常触发：唤醒 Agent
self.notifier.notify(rule, cond, quote, result)
self._last_triggered[(rule.id, idx)] = now
```

## 效果对比

### Before
```
09:31:00  量能 2.6x → 触发 ✅ 唤醒 Agent
09:31:10  量能 2.7x → 冷却期 🚫 静默跳过
09:31:20  量能 2.8x → 冷却期 🚫 静默跳过
09:36:01  量能 3.0x → 触发 ✅ 唤醒 Agent
```

用户体验：
- ❌ 09:31-09:36 之间完全没有反馈
- ❌ 不知道系统是否还在监控
- ❌ 无法看到价格/量能的持续变化

### After
```
09:31:00  量能 2.6x → 触发 ✅ 唤醒 Agent
09:31:10  量能 2.7x → 冷却期 📊 简化通知（WS + 飞书）
09:31:20  量能 2.8x → 冷却期 📊 简化通知（WS + 飞书）
09:36:01  量能 3.0x → 触发 ✅ 唤醒 Agent
```

用户体验：
- ✅ 持续收到监控反馈
- ✅ 知道系统正常工作
- ✅ 可以看到量能持续上涨（2.6x → 2.7x → 2.8x → 3.0x）
- ✅ 不会被重复的 Agent 决策通知打扰

## 数据库影响

### watch_triggers 表

**Before**：
- 冷却期内的触发不记录

**After**：
- 所有触发都记录
- 通过 `notified` 字段区分：
  - `notified=true` - 正常触发，已唤醒 Agent
  - `notified=false` - 冷却期触发，仅通知未唤醒

**查询示例**：
```sql
-- 查看某规则的所有触发（包括冷却期）
SELECT triggered_at, trigger_price, notified 
FROM quant.watch_triggers 
WHERE rule_id = 47 
ORDER BY triggered_at;

-- 统计冷却期触发比例
SELECT 
    COUNT(CASE WHEN notified = false THEN 1 END) as cooldown_count,
    COUNT(*) as total_count,
    ROUND(100.0 * COUNT(CASE WHEN notified = false THEN 1 END) / COUNT(*), 2) as cooldown_pct
FROM quant.watch_triggers
WHERE triggered_at >= CURRENT_DATE;
```

## WebSocket 事件

新增事件类型：

### `watch_cooldown` 事件
```json
{
  "type": "watch_cooldown",
  "data": {
    "rule_id": 47,
    "symbol": "300124.SZ",
    "name": "汇川技术",
    "price": 61.08,
    "change_pct": 0.02,
    "condition": {"type": "volume_surge", "params": {"multiple": 4}},
    "message": "持续监控中（冷却期），成交量为同期均量 4.17x（阈值 4.0x）",
    "in_cooldown": true
  }
}
```

前端可以用不同样式显示冷却期通知（例如淡化颜色、小图标）。

## 部署步骤

1. **重启 quantsys-v2 服务**（5001端口）
   ```bash
   launchctl kickstart -k gui/501/com.pi-investment.v2-api
   ```

2. **验证日志**
   ```bash
   tail -f ~/v2-api.log | grep -E "(notify_cooldown|冷却期)"
   ```

3. **测试**
   - 手动触发盯盘规则
   - 5分钟内再次触发
   - 检查是否收到简化通知（飞书/WS）
   - 确认 Agent 没有被唤醒

## 未来优化

### P1 - 冷却期状态持久化
当前冷却期状态在内存，服务重启后丢失。建议：

```python
def _restore_cooldown_state(self):
    """从数据库恢复最近的触发时间"""
    recent = self.trigger_repo.get_recent_triggers(minutes=15)
    for t in recent:
        key = (t.rule_id, t.condition_idx)
        self._last_triggered[key] = t.triggered_at
```

**收益**：
- 服务重启后不会立即重复触发
- 彻底解决冷却期失效问题

### P2 - 可配置冷却期
不同规则可能需要不同的冷却期：

```python
# 在 watch_rules 表添加 cooldown_sec 字段
# 条件级别的配置
conditions = [
    {
        "type": "volume_surge",
        "params": {"multiple": 4},
        "cooldown_sec": 900  # 15分钟
    },
    {
        "type": "price_break",
        "params": {"price": 58, "direction": "below"},
        "cooldown_sec": 300  # 5分钟
    }
]
```

### P3 - 冷却期统计面板
在前端显示：
- 各规则的冷却期触发次数
- 冷却期触发占比
- 是否需要调整阈值

## 测试清单

- [x] 正常触发能唤醒 Agent
- [x] 冷却期内触发不唤醒 Agent
- [x] 冷却期内发送 WS 通知
- [x] 冷却期内发送飞书通知
- [x] 所有触发都记录到数据库
- [x] `notified` 字段正确标记
- [ ] 服务重启后冷却期状态（已知问题，待 P1 修复）

## 参考

- [盯盘功能排查报告](./watch-troubleshooting-2026-08-14.md)
- [WatchEngine 源码](../../quantsys-v2/application/services/watch_engine/)
- [通知网关架构](../architecture/notification-gateway.md)
