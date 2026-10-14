---
requirement_refs: [FR-1, FR-2, FR-3, FR-4]
---

# 接口设计（REQ-261007133807-eda6）

> 每个接口标注 `serves: FR-x`（缺标注 = 孤儿接口被门禁拦）。

## 接口清单 `serves: FR-1, FR-2, FR-3, FR-4`

| 接口 id | 形态 | 职责 | 输入 | 输出 | 错误语义 | serves |
|---|---|---|---|---|---|---|
| IF-1 | domain 纯函数 `decide_escalation` | **唯一裁决出口**：这条触发要不要打断 agent | `rule, condition, quote, result, gate=None, cfg=None` | `Verdict` | metric 不符 → 抛 `WatchMetricContractViolation`；未知输入 → `code=UNKNOWN`（不抛） | FR-1 |
| IF-2 | domain 函数 `explain_escalation` | 规则侧「什么条件会叫我」人话说明 | `rule` | `str`（一句话） | 无法判定 → 返回显式「策略未声明（按默认口径）」而非空串 | FR-4 |
| IF-3 | domain 兼容壳 `EscalationChecker.should_escalate` | 保持既有调用方与用例不变 | 既有 6 参 | `Optional[str]`（reason 文案**逐字不变**） | 同改造前 | FR-1 |
| IF-4 | application `disposition.decide`（签名扩展） | Verdict → `disposition` 字符串映射 | 既有 5 参 + 新增 `verdict=None` | `(disposition, reason)` | `verdict` 为 `None` 时自裁决（行为同改造前） | FR-1 |
| IF-5 | 仓储 `WatchTriggerRepository.record`（扩展） | 理由码/理由落库 | 既有参数 + `escalation_code=None, escalation_reason=None` | `WatchTrigger` | 写库失败 → 抛给调用方；**调用方吞掉并留痕**（不阻断通知） | FR-2 |
| IF-6 | HTTP `GET /api/watch/rules`（追加字段） | 规则列表带「何时会叫我」 | 既有 query（`symbol`/`enabled`/`account`） | 既有字段 + `escalation_explain` | 说明算不出 → 返回「策略未声明（按默认口径）」 | FR-4 |
| IF-7 | HTTP `POST/PUT/PATCH /api/watch/rules` + `POST /api/watch/rules/batch` | 缺省写显式升级策略 | 既有 body（其中 `escalation_policy` 可选） | 既有响应 | `escalation_policy` 非对象 → 400（既有）；缺省**不报错**，写显式默认值 | FR-4 |
| IF-8 | 渲染契约（两条渲染路径） | 卡面「升级原因」行 | notification variables（含 `escalation_code` / `escalation_reason`） | 卡片 Markdown | 无理由 → **隐藏该行**；码未知 → 显示码本身（不臆造句子） | FR-3 |
| IF-9 | CLI 迁移脚本 | 两个库各加两列 | `--apply --dsn <dsn>` | 退出码 0 + 两列读数 | 非 0 即失败（含 `lock_timeout` 超时） | FR-2 |

## 裁决出口（IF-1）`serves: FR-1`

```python
# domain/watch/services/escalation_verdict.py
def decide_escalation(rule, condition: dict, quote, result,
                      gate: Optional[GateContext] = None,
                      cfg: Optional[InterventionConfig] = None) -> Verdict: ...

def decide_escalation_paths(rule, condition: dict, quote, result) -> Optional[Verdict]:
    """只有三条可信路径（含 L0/L1 与 auto_escalate 短路）；无命中返回 None。
    供兼容壳 IF-3 使用——它不得包含预算门/五道门（那属 disposition 侧）。"""
```

- **入参语义**：`rule` 为 `WatchRule`（含 `action_hint` / `escalation_policy` / `intent`）；
  `quote` 支持 `QuoteData` 或行情对象（回落 `change_pct` / `prev_close`）；
  `result` 是条件判定结果（`pct_change` 条件时**必须**带 `MetricKind.PCT_CHANGE`）；
  `gate` 缺省 = `GateContext()`（信息不足 → 对应门跳过，与改造前一致）。
- **出参**：`Verdict`（字段见 data-model.md）；`path` 由码表派生。
- **纯函数**：无 I/O、无外部状态、无随机；同输入必得同输出（并发与回放的前提）。
- **错误语义**：metric 契约不符**抛错**（沿用 `require_metric`）；其余输入缺陷一律降级为 `UNKNOWN`
  并把原文留在 `note` 里，**不抛**——裁决不许因为脏数据而消失。

## 规则侧说明（IF-2）`serves: FR-4`

```python
def explain_escalation(rule) -> str
```

- 输出的是**当前生效口径**的一句话，形如：
  - `L1 观察规则｜会自动叫我：涨跌幅 ≥ 5%（规则未覆写阈值）｜规则显式 escalate=true 时不看阈值，直接叫我`
  - `L2 行动规则｜无条件叫我（买卖节点需拍板）`
  - `已关闭自动升级（auto_escalate=false）：三条升级路径不生效，但止损与 L2 分级仍会叫我`
- **必须如实**：策略字段缺失时说"未声明（按默认口径）"，不假装规则已显式声明。
- 与 `decisionRefs` 无关：它是纯计算，不落库。

## 落库接口（IF-5）`serves: FR-2`

```python
WatchTriggerRepository.record(rule_id, symbol, condition, trigger_price,
                              detail=None, notified=False, disposition='pending',
                              disposition_reason=None, disposition_by='system',
                              dup_of=None, suppressed=False,
                              escalation_code=None, escalation_reason=None) -> WatchTrigger
```

- `escalation_code` 必须是 `EscalationCode.ALL` 内的值；调用方传 `UNKNOWN` 而不是 `None`
  （`None` 只用于"根本没走到裁决"的历史/异常路径）。
- **"没叫"也要写码**：`deduped` / `auto_observed` 的触发同样带码（判据 3 的 SQL 会逐行读）。
- 写库失败**不阻断**通知：由 `notifier._record()` 吞掉并 `logger.error`（既有降级语义）。

## HTTP API 变更 `serves: FR-4`

### GET /api/watch/rules（追加字段） `serves: FR-4`

响应条目**追加**（不改既有字段）：

```json
{
  "id": 32, "symbol": "300534.SZ", "enabled": true,
  "escalation_policy": {"auto_escalate": true, "anomaly_change_pct": 5.0},
  "escalation_explain": "L1 观察规则｜会自动叫我：涨跌幅 ≥ 5%（规则未覆写阈值）"
}
```

- 兼容：旧客户端忽略新字段即可；`escalation_policy` 仍原样返回（**不替换**）。
- 旧规则 `escalation_policy` 为 `NULL` 时：`escalation_explain` 写「策略未声明（按默认口径）」，
  同时 `escalation_policy` 仍为 `NULL`（**读不篡改数据**——显式化只发生在新写入）。

### POST/PUT/PATCH /api/watch/rules（缺省显式化） `serves: FR-4`

- 规则：请求体未带 `escalation_policy`（或为 `null`）→ 落库写入
  `EscalationPolicy.default().to_dict()` = `{"auto_escalate": true, "anomaly_change_pct": 5.0}`；
- 带了 → 原样写入（**可覆写**），字段缺失的键**合并默认值**后写入（避免半个策略）；
- `escalation_policy` 非对象 → 400（既有校验，保持）；
- 批量入口 `POST /api/watch/rules/batch` 的 `create` / `update` 分支同样适用；
- **不拒**未声明的调用方（向后兼容，见 D-4）。

## 卡面渲染契约（IF-8）`serves: FR-3`

两条渲染路径共用同一段渲染规则（`infrastructure/notification/formatters/`）：

| 条件 | 旧渲染 `feishu_formatters` | 分级渲染 `watch_level_templates` |
|---|---|---|
| `escalation_reason` 非空 | 正文追加 `**升级原因**：{path}｜{reason}` | `_skeleton_lines` 在「处置」行后追加同一行 |
| `escalation_code` 有值而 `reason` 为空 | 显示码本身（`**升级原因**：{code}`） | 同上 |
| 两者皆空 | **不渲染该行**（不臆造） | **不渲染该行** |
| 变量缺失（旧调用方） | 行为与改造前完全一致 | 行为与改造前完全一致 |

行序：保持 c392 四段契约的顺序，`升级原因` 追加在「**处置**」之后、「**下一步**」之前（不打断原有阅读动线）。

## 删除的接口 `serves: FR-1`

无。本需求不删除任何对外接口或既有函数；`EscalationChecker.should_escalate`、
`disposition.decide`、`EscalationCoordinator.check` 一律保留（兼容壳）。

## 关键决策与取舍 `serves: FR-1, FR-3`

1. **不新开 HTTP 端点解释"为什么"**：先把事实写进库里（`watch_triggers` 两列）+ 卡面；
   查询用既有 `GET /api/watch/triggers` 即可（新列随之返回）。新增 explain 端点属 UI 需求，
   本需求 `sides=[backend]` 不引入。
2. **`GET /api/watch/rules` 只加一个字段**（`escalation_explain`）：不把策略结构改成嵌套对象
   （那会破坏既有消费方的字段路径）。
3. **渲染规则写在设计里、实现在两个 formatter 各一处**：两条渲染路径本就是两套模板，
   强行合并渲染器属范围外重构；本需求用同一张"条件 → 行为"表锁死两者一致（测试逐条对拍）。
