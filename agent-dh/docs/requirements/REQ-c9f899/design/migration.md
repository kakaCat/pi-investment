# 技术设计 · 迁移与回滚（REQ-c9f899）

## 1. 开关清单（全部可独立回滚）

| 开关 | 默认 | 作用 |
|------|------|------|
| WATCH_RUNTIME_PERSIST_ENABLED | true | 状态落库（R10）；关=回内存态 |
| WATCH_TODO_ENABLED | false | 新闭环（建待办、巡检、回执）；关=只落 triggers（旧行为） |
| WATCH_SELF_HEAL_ENABLED | false | 规则自愈（抑噪 + 修规则待办） |
| WATCH_HEARTBEAT_ALERT_ENABLED | true | 引擎心跳/影子超期告警 |
| WATCH_DIGEST_DRY_RUN | true | 保留：暖启动期影子核对 |

## 2. 灰度顺序（每步独立可停、可回）

1. **建表**（additive，无行为变化）→ 校验：迁移脚本可重复执行、表结构断言通过。
2. **runtime 持久化**（写库 + 启动恢复）→ 校验：重启后冷却仍生效（对比触发间隔）。
3. **判据 metric 化**（含消费侧契约）→ 校验：#162 场景回归 + 全量 watch 测试 + domain 测试零新增失败。
4. **todo 双写**（triggers 与 todos 并行落）→ 校验：双写一致率 100%，旧路径不受影响。
5. **切换收敛权威到 WatchSlaJob**（digest 摘要门转只读）→ 校验：人为造超时待办，巡检能在 1 分钟内晋升并回执。
6. **开自愈**（WATCH_SELF_HEAL_ENABLED=true）→ 校验：#119/#92 类规则进入抑噪，且生成修规则待办。
7. **真开唤醒**（WATCH_DIGEST_DRY_RUN=false，先只对 agent_brain）→ 校验：影子核对一份摘要样本后再开；开后有回执两段。

## 3. 数据迁移

- **172 条积压收敛脚本**（一次性，幂等）：
  - disposition ∈ (escalated, pending) → 建 todo（level=P1，flow_state=L3，owner 按账户路由），保留 trigger_id 溯源；
  - disposition=meta_review 且 condition.type=rule_overlap → 建「修规则」todo；
  - 其余 → 置 expired，close_reason 写明「历史积压，迁移期收敛」。
  - 输出台账：before/after 计数，任何一条未收敛即报错（响亮）。
- **metric 回填**：watch_triggers.metric 置 unknown（不猜测，R-013）。
- **不删除旧表**：watch_digest_state 只读保留；watch_triggers/watch_rules 原列不动。

## 4. 回滚步骤

| 触发条件 | 动作 |
|----------|------|
| 新闭环异常（待办不收敛/回执风暴） | WATCH_TODO_ENABLED=false → 回旧 triggers 路径；todos 表保留数据供复盘 |
| 自愈误伤规则 | WATCH_SELF_HEAL_ENABLED=false + 用 watch_rule_changes 逐条反向应用 |
| 状态持久化导致 tick 变慢 | WATCH_RUNTIME_PERSIST_ENABLED=false → 回内存态 |
| 唤醒产生异常委托 | WATCH_DIGEST_DRY_RUN=true 立即回影子；已产生的委托按交易纪律另行处置并留痕 |

**回滚演练**：迁移期必须在测试环境各演练一次（开关切换 + 反向应用），演练记录进实施文档。

## 5. 兼容

- agent-dh 侧工具无需改动即可继续用；新增能力（待办查询/关闭）通过工具层后续增量暴露。
- 交易宪法、账户事实源（R-019）、止损口径均不变。
