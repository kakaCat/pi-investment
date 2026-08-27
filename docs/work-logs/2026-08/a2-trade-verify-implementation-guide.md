# A-2 trade_verify 例行化实施指南 + 调度系统问题报告

| 字段 | 值 |
|---|---|
| 日期 | 2026-08-28 01:00 |
| 编制 | agent-dh k3（审计+文档角色） |
| 状态 | 🟡 实施指南就绪，等有 DSH 上下文的 agent 执行 |

---

## 任务目标（A-2）

每日收盘后自动执行 `trade_verify` 对账，异常时飞书告警。验收标准：连续 2 个交易日自动触发（created_at 时间戳为证）。

---

## 推荐方案：通过 DSH Web UI 挂载（最可靠）

### 步骤

1. 访问 `http://localhost:13080`（investment profile）
2. 在对话框中发送：
   ```
   用 scheduler_manage 创建每日 trade_verify 任务：
   - action: create
   - name: "每日交易对账"
   - cron: "0 16 * * 1-5"  (工作日 16:00)
   - command: "trade_verify"
   ```

3. DSH 调用 `scheduler_manage` 工具，该工具会：
   - 调用 quantsys-v2 scheduler API 或 Agent OS reminder API
   - 返回任务 ID 和 next_run_at

4. 验证：次日 16:00 后执行 `scheduler_manage(action="list")`，查看 last_run_at 是否更新

### 备选：直接用工具（如果你在 DSH CLI/TUI）

```javascript
// 在 DSH REPL 或通过 agent 对话
scheduler_manage({
  action: "create",
  name: "每日交易对账",
  cron: "0 16 * * 1-5",
  command: "trade_verify"
})
```

---

## 🔴 调度系统基建问题（审计发现）

在尝试通过 curl 直接挂载时，发现**三个调度系统都有问题**：

### 1. quantsys-v2 scheduler API 不一致

**测试**：
```bash
# 创建任务 - 返回 success: true, id: 307
curl -X POST http://localhost:5001/api/scheduler/tasks \
  -d '{"name":"daily_trade_verify", "cron":"0 16 * * 1-5", ...}'
# → {"success": true, "data": {"id": 307, ...}}

# 查询任务列表 - 找不到刚创建的任务
curl http://localhost:5001/api/scheduler/tasks
# → {"tasks": [...]} 中无 daily_trade_verify

# 按 ID 查询 - Method Not Allowed
curl http://localhost:5001/api/scheduler/tasks/307
# → {"success": false, "error_code": "HTTP_405"}
```

**结论**：创建 API 返回成功但任务未持久化，或列表 API 与创建 API 隔离（不同存储？）。

### 2. Agent OS 不稳定 + API 404

**观察**：
- 08-27 15:30 在线（M1 snapshot 自动触发）
- 08-27 23:59 宕机（board_post/memory ECONNREFUSED）
- 08-28 00:54 在线（curl health 通）
- 08-28 01:00 部分端点 404（`POST /api/v1/reminders` → 404 page not found）

**结论**：Agent OS 近期频繁重启或路由不稳定，不适合作为唯一调度宿主。

### 3. scheduler_manage 工具的实际后端未知

`@pi-investment/scheduler` 插件的 `scheduler_manage` 工具封装了调度逻辑，但：
- 不清楚它调的是 quantsys-v2 scheduler 还是 Agent OS reminder
- 两者都有问题时，工具行为未知

---

## 建议（给基建线）

### P1：统一调度层

当前三个系统（quantsys-v2 scheduler / Agent OS reminder / DSH schedule 包）职责重叠但互不兼容。建议：

1. **短期**：明确 `scheduler_manage` 工具的后端选择逻辑（优先 quantsys-v2，降级 Agent OS）
2. **中期**：修复 quantsys-v2 scheduler API 的持久化/查询问题
3. **长期**：废弃 Agent OS 的 reminder 功能，统一到 quantsys-v2（Agent OS 本身已是 legacy Go 项目）

### P2：调度验证门

M1 调度"挂了 4 天没生效"的教训应固化为规则：

- 任何调度挂载必须提供**次日真实触发时间戳**（last_run_at）
- 挂载操作返回成功≠调度生效，需验证 next_run → 实际 run → last_run 完整链路

---

## A-2 当前状态

| 项 | 状态 |
|---|---|
| 实施指南 | ✅ 就绪（本文档） |
| 挂载动作 | 🟡 等有 DSH 上下文的 agent 通过 Web UI 执行 `scheduler_manage` |
| 验收 | ⏳ 挂载后 2 个交易日观察 |

**下一步**：请在 DSH Web UI (localhost:13080) 中调用上述 `scheduler_manage` 命令，挂载完成后告知我，我在次日 16:00 后做验收复核。
