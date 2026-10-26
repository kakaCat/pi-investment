---
title: 盯盘执行闭环三接缝
kind: guide
status: active
updated: 2026-10-21
serves: [REQ-261021194640-69b8]
---

# 盯盘执行闭环三接缝 #exec-loop

> 结论来源：REQ-261021194640-69b8（feature，2026-10-21 归档）。
> 一句话：agent 下单与终判；v2 只保证「成交回来能收敛、消息来了能建单、待办关掉能改规则」。

## 三条接缝的边界 #boundaries

| 接缝 | 触发点 | 落点 | 失败语义 |
|---|---|---|---|
| 成交回写 | `qs_trading` 的 `execute_trade` 落库提交后 | `notify_fill` → `FillSyncService.on_fill` → 待办 handled / 触发 handled + 时延 / 卖出规则退役 / 持仓状态翻转 | 回执失败不阻断成交；`detail.exec` 与待办收敛各自幂等、只写一次 |
| 消息投递 | 新闻扫描 / 政策扫描命中 critical | `NewsTodoBridge.dispatch` → P1 待办（`action_kind=rule_change`，evidence 记来源与命中词） | 桥失败只记日志，发卡与扫描结果不受影响；soft 只发卡不建单 |
| 待办闭环 | agent 调关闭接口（带决策审计号） | `TodoService.close(rule_change=...)` → `RuleChangeLinkage` → 规则变更（停用/降级需理由） | 联动先于收敛执行：联动失败 → 待办不收敛（422），避免「规则没改但待办显示已办」 |

## 状态与口径 #states

- 执行待办三态：执行 / 不执行 / 超时；关闭必须带决策证据（`decision_audit_id`）。
- 执行期限：P0 且 `action_kind='trade'` 的待办按库端 `created_at + WATCH_EXEC_SLA_MIN`（默认 30 分钟）计时，
  到期仍未收敛才转超时；不依赖应用侧 naive `due_at`。
- 统计：`GET /api/watch/exec/stats`（since/until 可选）返回三态计数与处理时延 p50/p95；
  空样本返回 0 / null，不伪造 0。
- 盘后窗口：sidecar 分盘中段与盘后段；盘后段只跑消息扫描（交易日 08:00–22:00，服务内节流）
  与收盘日报（一日一次），不重跑回填/生命周期等日频任务。

## 迁移与回滚 #migration

- `watch_todos.evidence`（JSONB，可空）由 `20261021_watch_todos_evidence.py` 迁移：
  默认 dry-run，`--apply` 才写；重跑 changed=0。生产库与测试库均已执行。
- 回滚方式：端口与装配全可空——不注入桥 = 只发卡；不注册监听 = 成交回写 no-op；`evidence` 为空即旧行为。
- 生产生效需重启 5001 进程（`launchctl kickstart -k gui/501/com.pi-investment.v2-api`），
  重启后核对三处：`watch_triggers.detail` 出现 `exec` 键、盘后日志有扫描轮次、统计端点可读。
