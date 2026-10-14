---
requirement_refs: [FR-1, FR-2, FR-4]
---

# 数据模型设计（REQ-261007133807-eda6）

> 每个数据结构标注 `serves: FR-x`（缺标注 = 孤儿结构被门禁拦）。

## 新增/修改的数据结构 `serves: FR-1, FR-2`

### Verdict（领域值对象，新增） `serves: FR-1, FR-2`

`domain/watch/services/escalation_verdict.py`

| 字段 | 类型 | 必填 | 语义 | 取值/约束 |
|---|---|---|---|---|
| `should_wake` | `bool` | ✅ | 是否打断 agent | 由命中码决定，不由调用方传 |
| `code` | `str` | ✅ | 理由码（受控枚举） | ∈ `EscalationCode.ALL`；未知一律 `UNKNOWN` |
| `reason` | `str` | ✅ | 人话理由（进卡面与库） | 非空；被覆盖时含「原判：…」段 |
| `path` | `str` | ✅ | 命中路径标签（**码的派生属性**，不落库） | 由 `EscalationCode → PATH_LABEL` 单表推导 |
| `note` | `str` | — | 附加说明（如「规则已关闭自动升级」） | 可为空；空则卡面不渲染附加段 |

**不可变**：`@dataclass(frozen=True)`；去重/抑噪覆盖用 `verdict.overridden(code, reason)` 返回**新实例**
（不原地改 —— 裁决对象一旦产生即事实，覆盖必须可追溯）。

### EscalationCode（受控枚举，新增） `serves: FR-1, FR-2`

`domain/watch/services/escalation_verdict.py` —— **码表是本需求唯一的词表事实源**，
卡面路径标签、落库值、`docs/architecture/watch-notification-contract.md §6` 判据表全部由它派生。

| 码 | 语义 | 叫 agent | 来源（收敛前等价点） |
|---|---|---|---|
| `CONSTITUTIONAL_INTENT` | 宪法级意图（`exit_stop` 止损铁律） | ✅ | `disposition.decide` 规则 0 |
| `BUDGET_EXHAUSTED` | 当日介入预算已耗尽 | ❌ | `decide` 规则 1 |
| `RULE_EXPLICIT_ESCALATE` | 规则显式声明 `action_hint.escalate=true` | ✅ | `EscalationChecker` 路径 1 |
| `ANOMALY_CHANGE_PCT` | 异常波动达阈值 | ✅ | `EscalationChecker` 路径 3 |
| `RULE_LEVEL_L2` | 规则分级 L2（买卖节点需拍板） | ✅ | `decide` 规则 3 |
| `META_REVIEW` | 元触发过轻门（进复核队列） | ✅ | `decide` 规则 4 |
| `OBSERVE_INTENT` | 观察类（意图门） | ❌ | `decide` 规则 5① |
| `AMOUNT_BELOW_THRESHOLD` | 金额门未过 | ❌ | `decide` 规则 5② |
| `SAME_TOPIC_COOLDOWN` | 增量门（同标的同议题 4h 内） | ❌ | `decide` 规则 5③ |
| `ECONOMIC_BELOW_K` | 经济门未过 | ❌ | `decide` 规则 5⑤ |
| `GATES_PASSED_ACTION` | 价格触发过五道门且声明买卖动作 | ✅ | `decide` 规则 5 尾 |
| `PENDING_NO_ACTION` | 过门但未声明动作（待处置） | ❌ | `decide` 规则 5 尾 |
| `DEDUPED` | 去重合并（**裁决后覆盖**） | ❌ | `engine` 去重分支 |
| `SUPPRESSED` | 抑噪期归档（**裁决后覆盖**） | ❌ | `engine` 抑噪分支 |
| `UNKNOWN` | 未接入/输入缺省（**禁止臆造**） | ❌ | 新增 |

> **叫/不叫两侧都在表内**是刻意的：用户追问的是因果，只记录"叫"的理由等于把成本控制留成黑盒
> （需求文档 §边界理由）。`BUDGET_EXHAUSTED` 与四道门就是「为什么没叫」的答案。

### `quant.watch_triggers`（表变更） `serves: FR-2`

| 列 | 类型 | 空 | 默认 | 语义 |
|---|---|---|---|---|
| `escalation_code` | `TEXT` | ✅ | `NULL` | 受控枚举码；`NULL` = 改造前未记录（**不作回填**） |
| `escalation_reason` | `TEXT` | ✅ | `NULL` | 人话理由（被覆盖时含「原判：…」段） |

**为什么是两列而不是三列**：`path`（命中路径）是码的静态属性，单开一列等于同一事实两份；
码表改名时会漂移。查询要路径时按码映射（或按前缀过滤），见 architecture.md 关键决策 2。

### `EscalationPolicy`（领域模型，显式化） `serves: FR-4`

`domain/watch/models.py` —— 字段不新增，只把**默认值显式化**并补序列化口：

| 方法 | 现状 | 设计后 |
|---|---|---|
| `default()` | `EscalationPolicy(auto_escalate=True)`（`anomaly_change_pct=None`） | `EscalationPolicy(auto_escalate=True, anomaly_change_pct=5.0)` —— 与 `EscalationChecker.DEFAULT_ANOMALY_CHANGE_PCT` **同值**（单一事实源：取该常量，不手写 5.0） |
| `to_dict()` | 无 | 新增：**只输出被判定消费的两个字段**（`auto_escalate`、`anomaly_change_pct`），不回写历史字段（频率/量能/价格偏差/核心区域/共振） |

## 兼容性分析 `serves: FR-2, FR-4`

| 对象 | 旧数据/旧调用方 | 设计后的处理 |
|---|---|---|
| `watch_triggers` 旧行 | `escalation_code IS NULL`（本机实测 89/89） | 读侧显示「未记录（改造前）」；**不回填**——回填等于臆造理由 |
| `watch_rules.escalation_policy` 旧行 | `NULL`（本机实测 7/7） | 判定侧 `_threshold()` 已把 `None` 当默认阈值；显式化只影响**新写入**，旧规则行为不变 |
| `EscalationPolicy` 历史字段 | JSONB 里可能残留 | `to_dict()` 不写回；解析侧字段保留（只读兼容） |
| `EscalationChecker.should_escalate` | 12 处调用方 + 既有用例 | 保留兼容壳，返回类型与文案逐字不变 |
| `disposition.decide` | 多调用方（含 `market_watch_service`） | 新增可选参数 `verdict`；不传时行为与改造前一致 |
| API 响应 `GET /api/watch/rules` | 既有消费方读固定字段 | **纯追加** `escalation_explain`；不改既有字段 |
| 规则写入口 | 可能不传 `escalation_policy` | 缺省写显式默认值；请求体语义不变（未声明不拒） |

## 迁移与回滚 `serves: FR-2`

**迁移脚本**：`infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py`（新增）

- 语句：`ALTER TABLE quant.watch_triggers ADD COLUMN IF NOT EXISTS escalation_code TEXT;`（及 `escalation_reason`），
  进入前 `SET lock_timeout = '30s'`（本仓要求：无上限 DDL 会被 `idle in transaction` 连接锁死）；
- **两个库都跑**（生产 `quant_investment` 与测试库 `quant_test`），显式 DSN，例如：

```bash
python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py --apply \
  --dsn postgresql://mac@127.0.0.1:5432/quant_test
python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py --apply \
  --dsn postgresql://mac@127.0.0.1:5432/quant_investment
```

- 幂等：`ADD COLUMN IF NOT EXISTS`；`--apply` 后打印两列的 `information_schema` 读数供复核；
- 漏跑的信号：`tests/test_orm_db_drift.py` 报红（既有门禁）。

**回滚**：

1. 代码回滚（`git revert`）→ 新列不再写，但**列保留**（可空，旧代码忽略）；
2. 若需彻底回退 schema：`ALTER TABLE quant.watch_triggers DROP COLUMN escalation_code, DROP COLUMN escalation_reason;`
   —— 只有在新列被证明有害时才做，且**必须两库同时执行**；
3. 数据无需回滚：两列本就是新增可空列，无既有列被改写。

**不新增索引**：码列基数低（15 个值）、查询以 `rule_id` / `triggered_at` 为主（既有索引已覆盖）；
若后续出现"按码聚合"的看板需求，再单独评估 —— 本需求不预先加索引。

## 关键决策与取舍 `serves: FR-1, FR-2, FR-4`

1. **码表只定义一次**（`EscalationCode`）：文案、落库值、文档判据表三处都从它派生；
   任何"在卡面里硬写一句中文理由"的写法都会立刻产生第二事实源。
2. **理由码与 disposition 是两把尺子**：`disposition` 说"这条触发落到哪个状态"（6 个值，状态机用），
   码说"为什么不叫/为什么叫"（15 个值，因果用）。刻意不把两者合并 —— 合并后状态机会被码表膨胀。
3. **`reason` 是自由文本、`code` 是受控词表**：机器读码、人读理由；两者不同源但由同一次裁决一起产出，
   不会各说各话。
4. **被覆盖时保留「原判」**：`DEDUPED` 覆盖 `ANOMALY_CHANGE_PCT` 时，理由文本形如
   `去重合并（同标的同向 60s 内）；原判：异常波动：涨跌幅 -6.10% 达到阈值 5.0%`
   —— 使得"本来会叫、被压掉了"这件事在库里可查（否则成本控制仍然不可见）。
