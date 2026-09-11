# RFC 013 · 盯盘触发处置状态机（机械优先 + 摘要唤醒）

- **状态**：Phase 1 已实现并线上验证；Phase 2 待做
- **需求**：REQ-f08def
- **作者/窗口**：investor / w-c8cae280
- **日期**：2026-09-11
- **相关**：[RFC 011 分层通知](./011-watch-engine-tiered-notification.md)

---

## 1. 背景与实测证据

盯盘引擎（WatchEngine）运行可靠——近 5 天 200 次触发、100% 通知送达、
0 次 tick 异常 / 0 次条件评估异常 / 0 次通知失败。但它存在三个结构性缺陷，
均由 2026-09-11 的线上数据确认：

| 编号 | 问题 | 实测证据 |
|---|---|---|
| P1 | **触发无终态 = 无闭环** | `quant.watch_triggers` 近 200 条触发 `agent_response` **全为 null**；"触发→处置率" = **0%**。引擎喊了 200 声，没有一声被应过 |
| P2 | **重复通知噪声** | 同一规则同向多阈值在一次跌穿里重复通知：规则 #129 同时挂 `<9.6` 与 `<9.4`，实测两条触发间隔 **0.46 秒**（09:30:09.608 / 09:30:10.069） |
| P3 | **同标的规则重叠** | 601600 单标的 **6 条规则**（#60/#125/#129/#130/#131/#132，跨窗口、跨账户），#129 与 #130/#131 语义重合 → 一次跌穿触发 4+ 条。全库重复标的 12 组 |
| P4 | **分级缺失** | 13 条规则 `action_hint` 无 `trigger_level` → 走隐式默认路径，成本不可控 |

同时必须守住的**硬约束（用户明确）**：所有触发都走 agent 会显著推高 token 成本。
实测现状：近 200 条触发中仅 46 条（23%）走 agent，今日 42 条中仅 2 条——
即分层已在省，但代价是 P1。

## 2. 设计目标

1. **补闭环**：每条触发都有明确终态与处置主体，可量化"触发→处置率"与"平均处置时延"
2. **守 token 预算**：机械可判的绝不唤醒 agent；**唤醒次数与触发数解耦**
3. **治噪声**：同标的同向重复合并为一次通知，但**账不能少记**（保留审计）

## 3. 状态机

### 3.1 状态定义

| 状态 | 含义 | 谁置位 | 是否终态 | 是否唤醒 agent |
|---|---|---|---|---|
| `pending` | 待处置（需人/agent 看一眼） | 引擎 | 否 | 否 |
| `auto_observed` | 机械归档：规则声明 `action_on_trigger=observe/message`，系统按预案观察 | 引擎 | **是** | **否（零 LLM）** |
| `deduped` | 去重合并：同标的同向在去重窗内已有触发 | 引擎 | **是** | **否（零 LLM）** |
| `escalated` | 进 agent 摘要队列（L2 或 escalation_policy 命中） | 引擎 | 否 | 是（**按摘要批量**） |
| `handled` | 已处置（有动作） | agent/人 | **是** | — |
| `ignored` | 知悉但不动作（**必须填 reason**） | agent/人 | **是** | — |
| `expired` | 超期未处置，由盘后清单兜底收敛 | 盘后例程 | **是** | 否 |
| `legacy_unknown` | 状态机上线前的历史数据 | 迁移 | **是** | 否 |

> **处置率口径** = (auto_observed + deduped + handled + ignored + expired) /
> (上述 + pending + escalated)。`legacy_unknown` **不计入分母**——不让历史数据美化指标。

### 3.2 状态迁移

```
                        ┌──────────────┐
   触发（tick 判定命中）  │   引擎决策    │
                        └──────┬───────┘
                               │ decide(rule, condition, escalated)
        ┌──────────────────────┼───────────────────────┐
        │                      │                       │
   observe/message        去重窗内同标的同向        L2 / 升级命中
        │                      │                       │
        ▼                      ▼                       ▼
 ┌──────────────┐      ┌──────────────┐        ┌──────────────┐
 │auto_observed │      │   deduped    │        │  escalated   │
 │  （终态）     │      │ （终态，落库） │        │ （进摘要队列） │
 └──────────────┘      └──────────────┘        └──────┬───────┘
                                                       │ agent 摘要消费
                                          ┌────────────┼────────────┐
                                          ▼            ▼            ▼
                                   ┌──────────┐ ┌──────────┐ ┌──────────┐
                                   │ handled  │ │ ignored  │ │ 过期未动  │
                                   │（终态）   │ │（需 reason）│ │→ expired │
                                   └──────────┘ └──────────┘ └──────────┘

   buy/sell 且非 L2 → pending（需人工/agent 决策，不发 agent 唤醒）
   pending/escalated 未收敛 → 盘后 19:30 未处置清单
```

## 4. 决策规则（纯函数，可单测）

`application/services/watch_engine/disposition.py`

优先级：**升级 > 规则声明的机械动作 > 默认待处置**

```python
def decide(rule, condition, escalated: bool = False) -> tuple[str, str]:
    if escalated:                       return 'escalated',     'L2 行动层或升级策略命中 → 进 agent 摘要队列'
    if trigger_level == 'L2':           return 'escalated',     '规则分级 L2 行动层 → 进 agent 摘要队列'
    if action in ('observe','message'): return 'auto_observed', '规则声明动作 → 系统按预案观察，不唤醒 agent'
    if action in ('buy','sell'):        return 'pending',       '需人工/agent 决策'
    return 'pending', '默认待处置（规则未声明触发动作）'
```

**去重语义**（关键边界，均已单测覆盖）：

- 去重键 = (`归一化标的`, `方向`)。`601600.SH` 与 `601600` 视为同一标的（这是 P3 的根因）
- 窗内重复 → `deduped` + `dup_of` 指向首发触发，**仍落库**（`notified=False`）
- **反方向不合并**：上破与下破是两件事，不得互相吞掉
- **窗过期仍报**：超过去重窗的真实二次破位照常通知（否则会吞掉真信号）
- 去重窗默认 **60 秒**，常量 `DEDUP_WINDOW_SEC`

## 5. 数据模型

`quant.watch_triggers` 新增列（迁移 `20260911_watch_trigger_disposition.py`）：

| 列 | 类型 | 说明 |
|---|---|---|
| `disposition` | varchar(20) | 状态机当前态 |
| `disposition_reason` | text | 处置说明 / 系统归档原因（**新触发必非空，迁移幂等护栏依赖它**） |
| `disposition_by` | varchar(50) | 处置主体：`system` / `agent:<window>` / `user` |
| `disposition_at` | timestamp | 处置时间（pending/escalated 为 NULL） |
| `dup_of` | integer | 被合并到哪条触发（去重溯源） |

索引：`(disposition, triggered_at DESC)`、`(symbol, triggered_at DESC)`。

**迁移幂等护栏**：历史回填条件为 `disposition='pending' AND disposition_reason IS NULL`。
不能用 `IS NULL OR ='pending'`——重跑会把上线后的真实 pending 误标 legacy（**本次实测踩过**，
误标 #1727/#1730 两条，已修复）。

## 6. API 契约

| 端点 | 用途 |
|---|---|
| `GET /api/watch/triggers?symbol=&disposition=` | 触发记录（可按状态过滤） |
| `GET /api/watch/triggers/stats?date=` | 处置率统计（验收指标数据源） |
| `GET /api/watch/triggers/unresolved?date=` | **盘后未处置清单**（pending/escalated 按标的聚合） |
| `PATCH /api/watch/triggers/{id}` | 处置：`handled` / `ignored`（强制 reason）/ `expired` |

## 7. Token 预算（本设计的第一性原则）

**唤醒次数必须与触发数解耦**：

| 项 | 现状 | 设计目标 |
|---|---|---|
| agent 唤醒机制 | escalated 逐条入队（Phase 1） | **按摘要批量**：盘中定时 + 盘后一次（Phase 2） |
| 唤醒次数/日 | 今日 2（基线） | ≤4，**且不随触发数增长** |
| 零 LLM 部分 | — | observe/message 类 + 去重类**全部系统自转** |
| 机械判定比例 | — | 目标 ≥80% 触发不进 agent |

## 8. 验收指标

| 指标 | 基线 | 目标 | 现状（2026-09-11） |
|---|---|---|---|
| 触发→处置率 | **0%** | ≥95% | **54.55%**（上线首日，含 5 条待处置） |
| agent 唤醒次数/日 | 2 | ≤4 | 3（escalated） |
| 单次跌穿的重复通知条数 | ≥2 | 1 | **已验证**：10 条触发 → 2 条通知 |
| 无分级规则数 | 13 | 0 | **0**（现 L0=1 / L1=23 / L2=9） |

## 9. 上线与验证记录（Phase 1）

- 提交：`dbe0c04e`（状态机 + 去重 + API + 迁移）、`166dafe0`（幂等护栏 + 测试修复）
- 测试：新增 15 个（含"去重时不发消息但落库""反方向不吞""窗过期仍报""L2 升级"），
  盯盘套件 **38 passed / 0 failed**
- **线上实证**：2026-09-11 13:00:42 下午开盘后 8 秒内 10 条触发 →
  **2 escalated + 8 deduped**（#1724/#1725/#1729/#1731/#1732 合并入 #1723/#1726）。
  旧逻辑会发 10 条飞书，现仅 2 条，账一条未少记

## 10. Phase 2（待做）

1. **摘要式批量唤醒**：把 escalated 队列按固定时点（盘中定时 + 盘后）打包为**一次** LLM 调用
2. **盘后未处置清单接入 19:30 例程**：对 pending/escalated 自动生成待办；超期自动 `expired`
3. **飞书消息可读性设计**（用户指定：闭环完成后专题讨论）——处置状态已落库，
   为"该说什么、不该说什么"提供事实基础：`deduped` 不该发；`escalated` 必须发且一眼看清"该谁做什么"

## 11. 已知限制

- 去重窗为**进程内内存**（`_recent_notified`），跨进程/重启不共享；重启后 60s 内可能多通知一次（可接受）
- `escalated` 目前无人消费（Phase 2 前）——存量会堆积在未处置清单里
- 状态机只管**盯盘触发**；策略信号（signal_track）与告警（market_alert）尚未接入同一状态机
- 去重按"标的+方向"，同标的**同方向但语义不同**的阈值（如"减半"与"清仓"两条规则）会被合并，
  代价是盘后清单里只看到首发规则——如需区分需引入语义分组键
