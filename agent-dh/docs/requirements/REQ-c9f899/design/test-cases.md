# 技术设计 · 测试用例（REQ-c9f899）

## 1. 单元（domain 纯函数，快）

| 用例 | 输入 | 期望 |
|------|------|------|
| metric 契约-正向 | price_break 命中 | result.metric=price |
| **metric 契约-反例（回归 #162）** | price_break，value=388.5 | 升级判定**不得**产出「量能异常」；只允许按 price metric 判定 |
| volume_ratio 正向 | volume_surge，ratio=0.62 | 不升级（阈值 3.0） |
| LevelResolver 真值表 | intent × has_position × constitutional | 宪法级→P0；持仓 exit_*→P0；买卖节点→P1；观察→P3 |
| Router 账户映射 | agent_brain / user_main_simulation / 空 | agent/autonomous；user/remind_only；空=数据缺陷路径 |
| 终态校验 | ignored 无 next_condition | 拒绝；L3+trade 无 decision_audit_id | 拒绝 |
| 自愈阈值 | 单日 8 次 / 连续 3 日日均 4 次 | 命中；7 次不命中 |
| SLA 计算 | 各级别 + due_at | P0=300s / P1=1800s / P2=当日收盘 / P3=无 |

## 2. 集成（应用层 + DB）

| 用例 | 步骤 | 期望 |
|------|------|------|
| 待办生命周期 | 触发 → 建 todo → 到期 → 巡检晋升 → 关闭 | flow_state L1→L2→L3；终态落库；closed_at 非空 |
| 回执三段 | 创建/关闭/超时 | watch_receipts 分别有 escalate/result/timeout，且幂等不重发 |
| 抑噪 | 同规则当日第 9 次触发 | 新触发 suppressed=true、level=P3、不建 todo；生成修规则待办 |
| runtime 恢复 | 写状态 → 重启进程 → 再触发 | 冷却仍生效（间隔 ≥ cooldown） |
| 心跳告警 | 停写 heartbeat 4 分钟 | 触发告警，且不重复刷屏 |

## 3. 故障注入（必须做，防「只测成功路径」）

1. **metric 误用注入**：把量能路径的 metric 期望改成 price → 测试必须红（证明契约真的在拦）。
2. **巡检停摆注入**：停掉 WatchSlaJob → 超时待办不得被静默放过（应出现在 metrics 告警口径里）。
3. **DB 写失败注入**：runtime upsert 抛错 → tick 不得崩溃，且**不得**退化成「无冷却」（应显式降级并告警）。
4. **账户越权注入**：用 agent 身份改用户账户规则 → 必须 403。
5. **重复关闭注入**：同一 todo 两次 close → 第二次 409，且不产生第二条回执。

## 4. 场景矩阵

P0/P1/P2/P3 × 账户（agent_brain / user_main_simulation / 空）× 终态（handled / ignored / expired）× 触发来源（价格/指标/事件/板块）= 覆盖表逐格至少一条；用参数化测试执行。

## 5. 验收脚本（可执行、看输出）

- 迁移反复执行：跑两次迁移脚本，第二次必须零变更（幂等）。
- 积压收敛：迁移前后 counts 对比，未收敛数必须为 0。
- 端到端：造一条 P1 触发 → 观察飞书橙卡 → 关闭 → 观察回执 → 查询 /api/watch/todos 终态。
- 冷却可信：重启前记录 A 规则触发时刻，重启后 1 分钟内再命中 → 不得推送（冷却生效）。
- 回归基线：tests -k watch 全量通过且无新增失败；domain 测试与基线失败集合一致。
