---
requirement_refs: [FR-1, FR-2, FR-3, FR-4]
---

# 后端设计（REQ-261007133807-eda6）

> `sides: [backend]` 的条件必交文档。服务端落地细节：改哪些函数、签名、顺序、降级、可观测性。

## 服务与接口实现 `serves: FR-1, FR-2, FR-3, FR-4`

| 编号 | 类型 | 名称 | 职责说明 | 输入 | 输出 | 调用方 | 依赖 | serves |
|---|---|---|---|---|---|---|---|---|
| S-1 | domain 纯函数 | `decide_escalation` | 唯一裁决出口（15 条判据顺序表） | rule/condition/quote/result/gate/cfg | `Verdict` | `engine.tick`、`disposition.decide` | `require_metric` | FR-1 |
| S-2 | domain 纯函数 | `decide_escalation_paths` | 只判三条可信路径（供兼容壳） | 同上（无 gate/cfg） | `Optional[Verdict]` | `EscalationChecker.should_escalate` | S-1 内部步骤 | FR-1 |
| S-3 | domain 纯函数 | `explain_escalation` | 规则侧「何时会叫我」人话说明 | rule | `str` | `GET /api/watch/rules` | `EscalationPolicy` | FR-4 |
| S-4 | domain 函数 | `Verdict.overridden` | 去重/抑噪覆盖裁决（返回新实例，保留原判） | code/reason | `Verdict` | `engine.tick` | — | FR-2 |
| S-5 | application | `engine.tick` 接线 | 一次裁决 → 处置 → 覆盖 → 落库/通知 | 既有 tick 输入 | 事件列表（增 `escalation_code`） | 调度线程 / 脚本 | S-1、S-4 | FR-1、FR-2 |
| S-6 | application | `notifier._record` / `_build_payload` | 两列落库 + 变量透传 | verdict | `WatchTrigger` / `TriggerPayload` | `engine.tick` | 仓储 IF-5 | FR-2、FR-3 |
| S-7 | infra 渲染 | `_escalation_line`（两处） | 卡面「升级原因」行 | `WatchCardItem` / vars | Markdown 行 | `feishu_formatters`、`watch_level_templates` | — | FR-3 |
| S-8 | inbound | `_policy_or_default`（路由内 helper） | 缺省显式化升级策略 | 请求体字段 | `dict` | 规则写入口（含 batch） | `EscalationPolicy` | FR-4 |

**新增开关**：无。理由：本需求不引入行为分叉（缺省显式化与旧默认**同值**），
回滚靠代码回退 + 两列可空即可；多一个开关反而制造"开关组合"的测试面。

## 数据流 `serves: FR-1, FR-2, FR-3`

```
tick() ─┬─ quote/condition/result（既有）
        ├─ GateContext（既有：intent/amount/last_intervention/expected_value/daily_wake_count/trigger_kind/change_pct）
        ├─ S-1 decide_escalation(...) ──────────────► verdict
        ├─ disposition.decide(..., verdict=verdict) ─► (disposition, reason)   ← 既有语义
        ├─ dedup.check(...) 命中 ──► S-4 verdict.overridden(DEDUPED, 原判=verdict.reason)
        ├─ notifier.notify(..., verdict=verdict)
        │     ├─ S-6 _record() → escalation_code / escalation_reason
        │     └─ S-6 _build_payload() → variables{escalation_code, escalation_reason}
        │             └─ S-7 渲染（旧路径 / 分级路径）
        └─ events.append({... , 'escalation_code': verdict.code})
```

**顺序不变式**：裁决在**去重之前**、落库在**通知之前**（既有顺序）；覆盖只发生在裁决与落库之间。

## 关键逻辑 `serves: FR-1, FR-2, FR-3, FR-4`

### S-1 `decide_escalation` 顺序实现 `serves: FR-1`

```python
def decide_escalation(rule, condition, quote, result, gate=None, cfg=None) -> Verdict:
    cfg = cfg or InterventionConfig()
    gate = gate or GateContext()
    intent = intent_of(rule)                       # 复用 disposition.intent_of（同源）
    level = _trigger_level(rule)                   # L0/L1/L2（缺省 L1）

    # 1 宪法级（不看 auto_escalate、不看预算）
    if intent in CONSTITUTIONAL_INTENTS:
        return Verdict(True, CONSTITUTIONAL_INTENT, '宪法动作（exit_stop）：无条件介入…', path)
    # 2 预算门
    if gate.daily_wake_count >= cfg.daily_budget:
        return Verdict(False, BUDGET_EXHAUSTED, '预算门：当日介入预算已耗尽 → 进日终汇总', path)
    # 3/4 三条可信路径（仅 L0/L1；auto_escalate=false 时不判）
    hit = decide_escalation_paths(rule, condition, quote, result)
    if hit is not None:
        return hit
    # 5 L2 分级
    if level == 'L2':
        return Verdict(True, RULE_LEVEL_L2, '规则分级 L2 行动层（买卖节点）→ 进 agent 摘要队列', path)
    # 6 元触发轻门
    if gate.trigger_kind == 'meta':
        return _meta_verdict(rule, gate, cfg)
    # 7–12 五道门（意图 / 金额 / 增量 / 经济 / 动作）
    ...
    # 13 兜底
    return Verdict(False, UNKNOWN, '未接入裁决（按不打扰处理）', path)
```

- **文案逐字沿用**收敛前 `disposition.decide` 与 `EscalationChecker` 的中文（兼容锁 TC-3）；
- `decide_escalation_paths` 内部先看 `auto_escalate`：为 `False` 时**只跳过第 3、4 条**，
  不影响第 1、5 条（与收敛前一致，见 architecture.md 纪律）。

### S-3 `explain_escalation` 分支 `serves: FR-4`

| 规则形态 | 说明文案（要点） |
|---|---|
| `trigger_level=L2` | `L2 行动规则｜无条件叫我（买卖节点需拍板）` |
| `auto_escalate=false` | `已关闭自动升级：三条升级路径不生效，但止损与 L2 分级仍会叫我` |
| `action_hint.escalate=true` | `规则显式声明：命中即叫我（不看阈值）` |
| `anomaly_change_pct` 已覆写 | `会自动叫我：涨跌幅 ≥ {n}%（规则覆写阈值）` |
| 未声明策略（`NULL`） | `策略未声明（按默认口径：涨跌幅 ≥ 5.0%）` |
| `intent=trend_observe` | 追加 `注：观察类规则仅知悉，不因动作门槛叫我` |

### S-5 tick 接线（改动点） `serves: FR-1, FR-2`

- `engine.py:453` 的 `self.escalation.check(...)` → `decide_escalation(rule, cond, quote, result, gate=self._gate_context(...), cfg=self.disposition.cfg)`；
- `engine.py:462` 的 `disposition.decide(..., escalated=bool(reason), escalation_reason=reason)`
  → `disposition.decide(..., verdict=verdict)`（`escalated`/`escalation_reason` 两参保留兼容，内部不再使用）；
- 去重分支（`engine.py:466-471`）命中时追加 `verdict = verdict.overridden(DEDUPED, ...)`；
- 通知与落库新增 `verdict` 入参；`events.append` 增 `escalation_code` 字段（可观测性，不改既有键）。

### S-7 渲染实现要点 `serves: FR-3`

```python
def _escalation_line(item) -> Optional[str]:
    code = str(getattr(item, 'escalation_code', '') or '').strip()
    reason = str(getattr(item, 'escalation_reason', '') or '').strip()
    if not code and not reason:
        return None                                   # 无理由 → 不渲染（不臆造）
    path = PATH_LABEL.get(code, code)                 # 码 → 路径标签（单表）
    body = reason or code                             # 只有码时显示码本身
    return '**升级原因**：' + (path + '｜' + body if reason else body)
```

- 插入位置：`_skeleton_lines`（分级路径）与 `feishu_formatters` 的 lines 列表，
  均在「**处置**」行之后、「**下一步**」行之前；
- `WatchCardItem` 新增 `escalation_code: str = ''` / `escalation_reason: str = ''`（缺省空 → 旧调用方行为不变）。

## 错误处理 `serves: FR-1, FR-2`

| 场景 | 处理 | 留痕 |
|---|---|---|
| `pct_change` 条件但 metric 不符 | 抛 `WatchMetricContractViolation`（不降级为"不升级"） | 异常上抛到 tick 的既有 try（该规则本轮跳过，下个 tick 重试） |
| 码/理由写库失败 | 吞异常，通知与处置继续 | `logger.error('触发记录落库失败'…)`（既有文案） |
| 渲染遇到未知码 | 显示码本身 | 不额外记日志（渲染层无状态） |
| `escalation_policy` 非对象 | 400（既有校验） | 既有错误响应 |
| 旧规则无策略 | 按默认口径裁决 + 说明写「未声明」 | 无（不写库） |
| 迁移漏跑 | `test_orm_db_drift.py` 红 | 门禁即留痕 |

## 数据库设计 `serves: FR-2`

### 新增/修改表 `serves: FR-2`

| 表 | 动作 | 内容 |
|---|---|---|
| `quant.watch_triggers` | 新增两列 | `escalation_code TEXT NULL`、`escalation_reason TEXT NULL` |

### 字段说明 `serves: FR-2`

- `escalation_code`：受控枚举（见 data-model.md 码表），`NULL` = 改造前未记录；
  长度实际 ≤ 32 字符（`TEXT` 无需 `VARCHAR`，本仓既有列多为 `TEXT`/`String`）。
- `escalation_reason`：人话理由，含「原判：…」段（被覆盖时）。

### 索引设计 `serves: FR-2`

**不新增索引**：码列基数低（15 值），主查询走 `rule_id` / `triggered_at` 既有索引；
按码聚合的看板需求尚未出现 —— 出现时再单独立项评估（YAGNI）。

### 约束说明 `serves: FR-2`

- 两列**不加** `NOT NULL`（历史行为 NULL，回滚也要求可空）；
- **不加** `CHECK` 约束到码枚举：码表在代码里演进（新增码不需要迁移），
  用 `CHECK` 会把"加一个码"变成"改 schema + 两个库迁移"；受控性由 `EscalationCode.ALL` +
  单测保证（写库侧对非枚举值一律先归一为 `UNKNOWN`）。

## 性能考量 `serves: FR-1, FR-2`

- 裁决是纯函数、无 I/O：单次 tick 的裁决开销 = 常数级比较（`quote` 已取好，不新增外部调用）；
- 不新增查询：`GateContext` 由既有字段组装，`explain_escalation` 只读规则对象（不查库）；
- 落库仍是**一条 INSERT**（只多两个参数），不新增写放大；
- 卡面多一行字符串拼接（可忽略）。

## 安全设计 `serves: FR-4`

### 鉴权 `serves: FR-4`

不变：`/api/watch/*` 沿用既有部署边界（本机服务、无对外鉴权），本需求不引入新端点。

### 输入校验 `serves: FR-4`

- `escalation_policy` 必须是对象（既有校验保留）；
- 新增：`anomaly_change_pct` 若给出必须是正数（`> 0`，非数字或 ≤0 → 400），
  防止"阈值 0 导致每次都升级"这类静默放大；
- `auto_escalate` 必须可解析为布尔（字符串 `"false"` 与 `false` 都接受，与既有 JSONB 宽容度一致）。

### 敏感信息 `serves: FR-4`

理由文本可能含行情数值与规则上下文（既有卡片已经包含同类信息），
**不新增**任何密钥/账户敏感字段写入 `escalation_reason`。
