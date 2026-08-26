# M4-2 Agent OS Scheduler 任务记录

## 任务详情

| 字段 | 值 |
|---|---|
| **任务 ID** | `f59fb4af-470e-4763-9b04-092cace6810c` |
| **名称** | `m4_circuit_breaker_daily_check` |
| **描述** | M4-2 组合回撤熔断每日检查（60日回撤>8%触发减仓+禁止开仓） |
| **Cron** | `0 30 16 * * 1-5`（工作日 16:30） |
| **Command** | `/Users/yunpeng/pi-investment/agent-dh/scripts/os-remind-bridge.sh m4_circuit_breaker_daily_check` |
| **Window** | `w-51c8d482` |
| **Enabled** | `true` |
| **创建时间** | 2026-08-26T10:27:48+08:00 |

## Payload

```json
{
  "prompt": "【M4-2 熔断检查】执行 m4_circuit_breaker_check：计算 60 日最大回撤，若 >8% 触发熔断（减仓一半+禁止开仓+落库+飞书告警），若已熔断且回撤修复则解除。汇报检查结果。",
  "window": "w-51c8d482"
}
```

## 投递链路

```
Agent OS scheduler（cron 触发）
  → os-remind-bridge.sh m4_circuit_breaker_daily_check
  → OS memory（office:reminder:w-51c8d482）
  → lifecycle 60s 轮询
  → agent.followup() 注入 investor 会话
  → investor agent 收到 prompt
  → 调用 m4_circuit_breaker_check 工具
  → 执行熔断检查逻辑
```

## 验证

```bash
# 查看任务列表
curl -s http://localhost:8080/api/v1/scheduler/tasks | jq '.tasks[] | select(.name=="m4_circuit_breaker_daily_check")'

# 手动触发测试
curl -X POST http://localhost:8080/api/v1/scheduler/tasks/f59fb4af-470e-4763-9b04-092cace6810c/trigger
```

## 与 M1 调度对比

| 项 | M1 每日快照 | M4-2 熔断检查 |
|---|---|---|
| 任务名 | market_perception_daily_snapshot | m4_circuit_breaker_daily_check |
| 时间 | 15:30（收盘后） | 16:30（收盘后 1 小时） |
| 工具 | 调用 quantsys-v2 snapshot API | 调用 agent-dh m4_circuit_breaker_check 工具 |
| 状态 | ✅ 生产运行 | ✅ 已创建（待首次触发 2026-08-26 16:30） |
