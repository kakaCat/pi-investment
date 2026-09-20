- Agent 接入：[wake-adapter.ts](../../agent-ts/src/api/adapters/wake-adapter.ts)
- 单元测试：[tests/services/test_watch_engine.py](../../quantsys-v2/tests/services/test_watch_engine.py)

---

**文档版本**：v1.0  
**最后更新**：2026-08-24  
**维护者**：kakaCat

---

## 12. REQ-c9f899 重构（2026-09-18 上线）：待办化闭环

> 本页第 1-11 章描述的是重构前「触发→直接通知」的形态。2026-09-18 全量切换后，主链路改为**待办化闭环**。
> 设计/实施/验收档案：agent-dh/docs/requirements/REQ-c9f899/。

**主链路**：触发 → 判据（metric 化）→ 级别判定（P0–P3 纯函数）→ 落待办（P0/P1/P2 建，P3 与 deduped 不建）→ 流转（L1 通知 → L2 待办 → L3 处置）→ 终态（handled/ignored/expired，ignored 必填 NEXT 条件）→ 三段回执（升级即/处置后/超时，幂等键 (todo_id, kind, digest)）。

| 维度 | 重构后 |
|---|---|
| 收敛权威 | WatchSlaJob（进程外，60s）：到期机械晋升 L1→L2→L3；已在 L3 仍超时 → 写 timeout 回执 |
| 判据 | EvalResult.value 语义由 MetricKind 唯一确定；消费侧必须 require_metric 声明——根治「现价当量比」（线上曾有 19 条假「量能异常」） |
| 升级链 | 只留 规则显式声明 / 宪法级 / 异常波动；历史五类（频率·量能异常·价格偏差·核心区域·多规则共振）**已删除** |
| 级别 | P0 红卡@你不可静默（宪法级）/ P1 橙卡待决策 / P2 蓝卡知悉 / P3 不单独推送（日终汇总）；由 level_resolver 按 意图×持仓×宪法级 机器判定 |
| 规则自愈 | 反复触发（单日 ≥8 或 连续 ≥3 日日均 ≥4）→ 自动抑噪为 P3 聚合 + 延长冷却 + 生成「修规则」待办；修复权限按账户分级（自有账户 agent 自主，用户账户只提请） |
| 账户路由 | agent 自有账户 → agent 处置（可自主）；用户账户 → 通知本人，agent 只出建议；策略账户 → 不介入 |
| 状态持久化 | 闩锁 / 冷却基准 / 去重窗 / 触发事件窗 / 价格历史（velocity）跨重启落库 |
| 观测 | 引擎心跳 + GET /api/watch/metrics + 心跳缺失/影子模式超期告警（进程外） |
| 端点 | /api/watch/todos（查询/认领/关闭）、/api/watch/rules/{id}/noise、/api/watch/rules/{id}/repair、/api/watch/metrics |
| 灰度 | 全部开关化（WATCH_TODO_ENABLED / WATCH_SELF_HEAL_ENABLED / WATCH_RUNTIME_PERSIST_ENABLED / WATCH_DIGEST_DRY_RUN），默认全关，2026-09-18 起全量开启 |
