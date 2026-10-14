# REQ-261006133733-1fdf · 设计：接口与契约

**本文件定死**：`detect_anomalies` 的三态返回契约、质量分分量口径、三处消费点的处置规则。
拆分与实施阶段**不得**自行改这些签名与字段语义；要改先回本设计。

## 1. `DataValidator.detect_anomalies` 三态契约（核心）（serves: FR-1, FR-2）

```python
def detect_anomalies(
    self, symbol: str, start_date: str, end_date: str, threshold: float = 3.0
) -> Dict:
    """Z-score 异常检测。**不抛**；失败以 `ok=False` 表达（不得冒充「无异常」）。"""
```

**返回键集（三态，逐态定死）**：

| 键 | 类型 | A. 正常（有/无异常） | B. 数据不足 | C. 检测失败 |
|---|---|---|---|---|
| `ok` | `bool` | `True` | `True` | **`False`** |
| `has_anomalies` | `Optional[bool]` | `True` / `False` | **`None`** | **`None`** |
| `unknown_reason` | `Optional[str]` | `None` | `'insufficient_data'` | 错误摘要（≤200 字符，形如 `TypeError: …`） |
| `price_anomalies` | `List[dict]` | 前 10 条 | `[]` | `[]` |
| `volume_anomalies` | `List[dict]` | 前 10 条 | `[]` | `[]` |
| `total_anomalies` | `int` | 真实计数 | `0` | `0` |
| `message` | `str` | `''` | `'Insufficient data for anomaly detection'`（**既有文案不变**） | `''` |
| `error` | `Optional[str]` | `None` | `None` | **= `unknown_reason`**（兼容别名，保留既有键） |

**不变量**：
1. **`has_anomalies is False` 只在「真的检测过且没有异常」时出现**。未知一律 `None`。
2. **`total_anomalies` 不得单独作为结论**——`ok=False` / `unknown_reason` 非空时它恒为 `0`，
   下游必须先看 `ok` 与 `unknown_reason`（见 §3 的消费点规则）。
3. `has_anomalies` **类型放宽为 `Optional[bool]`**：调用方**禁止**用真值判断
   （`if not info['has_anomalies']`）——`None` 也是假值，那正是本次要消灭的陷阱；
   一律写 `is True` / `is False` / `is None`。
4. 方法**不抛**（既有约定）；`price_anomalies` / `volume_anomalies` 的元素形状不变
   （`{'date','close','z_score'}` / `{'date','volume','z_score'}`）。
5. `threshold` 默认 `3.0`、算法（Z-score）**不变**（不在本需求范围）。

## 2. `DataValidator.get_data_quality_score` 分量口径（serves: FR-4）

```python
def get_data_quality_score(
    self, symbol: str, start_date: str, end_date: str, coverage_rate: float
) -> float
```

三个分量：覆盖率 60 分 + 重复率 20 分 + **异常率 20 分**。异常率分量**按检测三态分流**：

| 检测状态 | 异常率分量 | 理由 |
|---|---|---|
| **有异常**（`has_anomalies is True`） | `max(0, 20 - anomaly_rate * 4)`（**既有公式不变**） | 有证据 |
| **确无异常**（`has_anomalies is False`） | `20`（满分，**既有语义**） | 有证据 |
| **数据不足**（`unknown_reason == 'insufficient_data'`） | **该分量剔除并重新归一**：`(coverage_score + duplicate_score) / 80 * 100` | 短历史新股不该因"没得判"被扣 20 分；也不该白拿 |
| **检测失败**（`ok is False`） | **`0` 分**，并记一条 error 日志（含 `symbol` / `unknown_reason`） | 没跑成就不给分（无魔法常数）；失败事实由 §3 的计数与日志可见 |

> **今日现状对照**：因为恒走失败路径，异常率分量**恒得 20 分**（白送），
> 今日 `data_quality_score=95.01` 里含这 20 分。改后该分量的取值第一次有了依据。

## 3. 三处消费点的处置契约（serves: FR-3）

### 3.1 `data_quality_service.check_quality_for_symbol`（单股，`:152-190`）（serves: FR-3）

- 读取后先算两个判定量：
  - `anomaly_unknown = anomaly_info.get('has_anomalies') is None`
  - `anomaly_failed  = anomaly_info.get('ok') is False`
- **`has_issues` 判据**（定死）：
  `gap > 0` **或** `has_duplicates` **或** `has_anomalies is True` **或** `anomaly_failed`
  —— 即**检测失败计入问题**（宁可当"待查"，不得当"干净"）；
  **`insufficient_data` 不计入 `has_issues`**（新股不是质量问题），但必须单独计数。
- 写入 `stocks_with_issues` 的条目**新增**两键：
  `'anomaly_unknown': bool`、`'anomaly_unknown_reason': Optional[str]`；
  既有键（`has_anomalies` / `anomaly_count`）保留（`has_anomalies` 可能为 `None`）。

### 3.2 `data_quality_service.check_data_quality`（汇总，`:205/:223/:238`）（serves: FR-3）

汇总字典**新增**两键（只增不改）：

| 新键 | 含义 |
|---|---|
| `anomaly_unknown_count` | 因**检测失败**而未知的股票数（`ok is False`） |
| `insufficient_history_count` | 因**数据不足**而未知的股票数（`insufficient_data`） |

### 3.3 `data_quality_service.check_data_quality_single` 附近（`:469-481`）（serves: FR-3）

同 §3.1 的判据与新增键（同一份规则，**不得各写一份**——两处都必须 `is True` / `is None` 显式判定）。

### 3.4 审计落库 `_record_quality_check`（`:546`）（serves: FR-3）

- **修既有空转**：现在读 `anomaly_info.get('anomalies', [])` —— 该键**从不存在**（返回里是
  `price_anomalies` / `volume_anomalies`）⇒ 异常从未进审计 warnings。改为遍历两个真实键。
- **新增未知留痕**：`has_anomalies is None` 时写一条
  `{'type': 'anomaly_detection_unknown', 'reason': <unknown_reason>, 'message': …}` 进 `warnings`。

## 4. 数据契约（是否改表）（serves: FR-3）

- **零 DDL / 零迁移**：审计走既有 `public.kline_data_quality` 的 `errors` / `warnings`（**jsonb**），
  汇总随任务结果写 `quant.scheduler_runs.result`（jsonb）→ 新增键不需要改表。
- 新增的 JSON 键（§3.2/§3.4）**只增不改**，旧消费者忽略未知键即可。

## 5. 错误语义与日志（serves: FR-2, FR-3）

| 事件 | 级别 | 触发 | 字段 |
|---|---|---|---|
| `检测异常值失败: <原因>`（既有文案保留） | `error` | `ok=False` | 既有仅文字；**新增** `symbol` / `unknown_reason` 到结构化字段（不删原文案） |
| 质量分失败留痕（新） | `error` | `get_data_quality_score` 遇 `ok=False` | `symbol` / `unknown_reason` |

- 修好后**正常路径不再产生**上述 error（今日基线：4 分钟 7995 条）。
- **不加**日志限流/聚合（边界「不做什么」第 5 条）。

## 6. 静态与兼容红线（serves: FR-2, FR-5）

1. `grep -rn "has_anomalies" application/ adapters/ infrastructure/` 的每一处都必须是
   `is True` / `is False` / `is None` 显式判定；**禁止**真值判断（`if not …` / `if …`）。
2. 既有键一个都不许删（`ok` 只能进 `ok=True` 路径判断的前置，不得替换 `has_anomalies` 的存在性）。
3. `KlineORMRepository.get_daily_klines` 的返回类型（polars DataFrame）**不动**。
