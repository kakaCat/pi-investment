---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
---

# 用户场景（REQ-261007133807-eda6）

## 场景总览 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

| 场景 | 角色 | 触发 | 完成标志 | serves |
|---|---|---|---|---|
| UC-1 | 投资人（人） | 收到一张盯盘卡 | 卡面给出「升级原因」：这次为什么叫了我 / 为什么没叫 | FR-3 |
| UC-2 | 投资脑（agent） | 新建或修改一条盯盘规则 | 规则上写下了"什么条件会叫我"，事后可回看 | FR-4 |
| UC-3 | 排障者 | 追问"这条触发为什么叫了 agent" | 一条 SQL 得到码 + 理由 + 命中路径 | FR-2 |
| UC-4 | 后续开发者 | 要改"何时叫 agent"的口径 | 只改一个出口；文档与卡面与代码不漂移 | FR-1、FR-5 |
| UC-5 | 投资人（人） | 收到一张"没叫 agent"的卡（预算/去重压掉） | 库里能看出它**本来会不会叫**（原判保留） | FR-2 |

## UC-1 收到卡片：这次为什么叫我 `serves: FR-3`

1. 盯盘触发命中异常波动（|涨跌幅| 6.1% ≥ 5.0%）→ 引擎裁决为 `ANOMALY_CHANGE_PCT`（叫）。
2. 飞书卡正文在「**处置**：L2 行动（需 agent 介入处置）」之后多一行：

```
**升级原因**：异常波动｜涨跌幅 -6.10% 达到阈值 5.0%
```

3. 若这次**没叫**（例如当日预算已用完），卡片只在确有理由时保留该行（预算门属"没叫"的原因，
   只落库不在卡面渲染 —— 卡面是打扰物，把"没叫你"写满卡面本身就是噪音）。

**完成标志**：同一句"下破"在 `entry` 与 `exit_stop` 下的卡片不仅意图不同，
**升级原因也不同**（后者是 `CONSTITUTIONAL_INTENT`：无条件叫我）。

## UC-2 建规则：写下"什么条件会叫我" `serves: FR-4`

1. agent 调 `POST /api/watch/rules`，**没有**传 `escalation_policy`。
2. 服务端写入显式默认值 `{"auto_escalate": true, "anomaly_change_pct": 5.0}`（不再是 `NULL`/`{}`）。
3. 之后 `GET /api/watch/rules` 返回：

```
"escalation_policy": {"auto_escalate": true, "anomaly_change_pct": 5.0},
"escalation_explain": "L1 观察规则｜会自动叫我：涨跌幅 ≥ 5%（规则未覆写阈值）"
```

4. 若 agent 显式声明 `escalate=true`，说明变成：
   `L1 观察规则｜规则显式声明：命中即叫我（不看阈值）`。

**完成标志**：无需读代码即可回答"这条规则在什么情况下会叫我"；存量规则**不被拒绝**，
其说明为「策略未声明（按默认口径）」。

## UC-3 排障：一条 SQL 回答因果 `serves: FR-2`

```sql
select triggered_at, rule_id, disposition,
       escalation_code, left(escalation_reason, 60) as reason
from quant.watch_triggers
where triggered_at::date = current_date
order by triggered_at desc limit 10;
```

样例读数：

```
 triggered_at        | rule_id | disposition   | escalation_code    | reason
 2026-10-08 10:12:03 |      32 | escalated     | ANOMALY_CHANGE_PCT | 异常波动：涨跌幅 -6.10% 达到阈值 5.0%
 2026-10-08 10:12:03 |      29 | deduped       | DEDUPED            | 去重合并（同标的同向 60s 内）；原判：异常波动…
 2026-10-08 10:05:41 |      27 | auto_observed | BUDGET_EXHAUSTED   | 预算门：当日介入预算已耗尽 → 进日终汇总
```

**完成标志**：三行分别回答了"叫了、本来会叫但被去重压下、没叫因为预算"——
**"没叫"也有码**，成本控制不再是黑盒。

## UC-4 改口径：只改一处 `serves: FR-1, FR-5`

1. 新增/调整一条判据 → 只改 `decide_escalation` 的顺序表与码表；
2. 卡面路径标签、`docs/architecture/watch-notification-contract.md` 判据表由码表派生，
   不再手写第二份；
3. 结构判据（TC-8）保证没有第三处 `trigger_level == 'L2'` 的独立叫醒。

**完成标志**：`grep` 判据 0 命中 + 文档判据表与码表逐行对应（同源）。

## UC-5 被压掉的触发：原判可查 `serves: FR-2`

1. 同标的同向 60 秒内再次触发 → 去重合并，`disposition=deduped`、`escalation_code=DEDUPED`；
2. 理由文本保留「原判：异常波动…」，因此"它本来会被判成叫 agent"这件事可查。

**完成标志**：不允许出现"因为被去重所以什么理由都没留下"的行（那正是今天的状态）。

## 关键决策与取舍 `serves: FR-3, FR-4`

1. **卡面只写"叫"的理由，"没叫"的理由落库为主**：卡面是打扰物，把预算/去重的原因写在卡上
   会把"知悉类"卡片变成噪音；但库里必须全量（UC-3/UC-5）。
2. **存量规则只读回显、不自动改写**：自动把 7 条存量规则的策略刷成显式值属于"数据回填"，
   本需求不做（需求文档 §边界理由）。
3. **说明文案由策略与级别共同驱动**：`L2` 规则的说明必须体现"无条件叫我"，
   否则用户会以为 L2 也受 `auto_escalate` 开关影响（事实上不受，见 architecture.md 裁决顺序纪律）。

## 技术方案与亮点 `serves: FR-1, FR-2`

- **因果可查 ≠ 多写日志**：理由来自**判定本身**的返回值（不是事后拼装的日志），
  因此不会出现"日志说升级了、库里看不出来"的两份真相。
- **覆盖也留痕**：去重/抑噪覆盖裁决时保留「原判」，让"本会打扰但被压掉"这条最容易被忽略的路径可见。
