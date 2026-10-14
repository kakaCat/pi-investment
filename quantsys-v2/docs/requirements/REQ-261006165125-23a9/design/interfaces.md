# 设计 · 接口与数据契约（每日任务空结果不发飞书）

**需求ID**: REQ-261006165125-23a9
**类型**: feature
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

约定：本文件里的签名即**契约**——拆分与实施阶段按此写，不得就地改名/改语义；
确需变更请退回 design 阶段改本文档。

## 1. 新模块 `daily_jobs/notify_policy.py`（纯函数，唯一判据入口）（serves: FR-1, FR-2, FR-4, FR-6, FR-7）

```python
NO_OP_STATUSES: frozenset[str] = frozenset({'no_event', 'no_op'})
RUNNING_NOTICE_DEFAULT_SECONDS: float = 60.0

def is_no_op(result: Any) -> bool: ...
def notify_noop_enabled() -> bool: ...
def running_notice_seconds() -> float: ...
def should_send_start() -> bool: ...
def should_send_completion(*, result: Any, manual: bool = False) -> bool: ...
```

### 1.1 `is_no_op(result) -> bool`（serves: FR-1）

**返回 True 当且仅当**：`isinstance(result, dict)` 且满足二者之一
1. `result.get('no_output') is True`（严格 `is True`：`1`、`'true'`、`'yes'` 都不算），或
2. `result.get('status')` 是 `str` 且 `.strip().lower()` 落在 `NO_OP_STATUSES`（`no_event` / `no_op`）。

**其余一律 `False`**：`None`、非 dict（含字符串/列表）、未知 status、缺失键、`status` 非字符串。
理由（R4）：判宽了会静默掉真产出，故白名单 + 默认外发；新增"无事"取值必须改本模块常量（设计阶段登记）。

### 1.2 `notify_noop_enabled() -> bool`（serves: FR-7）

读环境变量 `DAILY_JOBS_NOTIFY_NOOP`，复用既有 `interval._env_flag` 语义
（`'1' / 'true' / 'yes' / 'on'`，忽略大小写与首尾空格；未设或其它值 → `False`）。
**默认 `False` = 新行为**（无事不发）。**不得抛异常**。

### 1.3 `running_notice_seconds() -> float`（serves: FR-3, FR-7）

读 `DAILY_JOBS_RUNNING_NOTICE_SECONDS`：

| 输入 | 返回 | 语义 |
|---|---|---|
| 未设 / 空串 / 非数 | `60.0` | 默认阈值 |
| `<= 0` 的数 | `0.0` | **显式关闭**该提示（不 arm timer） |
| 正数 | 该值 | 阈值 |

不得抛异常；`0.0` 是"关闭"，**不是**"立刻发"（`_arm_running_notice` 对 `<= 0` 直接返回 `None`）。

### 1.4 `should_send_start() -> bool`（serves: FR-7 · 回滚口）

`return notify_noop_enabled()`——**只有**开关打开（恢复旧行为）时才立即发开始消息；
默认路径返回 `False`（开始消息改由 §3 的阈值提示承担）。**没有 `manual` 分支**：人工触发也不发开始消息，
只在结束时回一条带「（人工触发）」的完成消息（FR-6）。

### 1.5 `should_send_completion(*, result, manual=False) -> bool`（serves: FR-1, FR-2, FR-4, FR-6）

```
manual is True                                    → True       # FR-6：人工触发必有回执
notify_noop_enabled() is True                     → True       # FR-7：旧行为，完成必发
is_no_op(result) is True                          → False      # FR-2：无事不发
otherwise                                         → True       # 有产出照发
```
**失败不经过本函数**：调用方在调它之前已用 `find_result_failure` + `try/except` 分流；
本函数**不**负责失败判定（避免两套失败口径）。

## 2. 修改 `daily_jobs/runtime.py`（serves: FR-2, FR-3, FR-4, FR-6, FR-7）

```python
def _run_job(job: JobDef, run_date: str, manual: bool = False) -> None: ...
def _arm_running_notice(job: JobDef) -> Optional[threading.Timer]: ...
def _send_running_notice(job_id: str, description: str, secs: float) -> None: ...
```

### 2.1 `_run_job` 行为契约（逐分支）（serves: FR-2, FR-3, FR-4, FR-6, FR-7）

| 分支 | 触发条件 | 外发 | 台账 | 变化 |
|---|---|---|---|---|
| 交易日门跳过 | `job.trading_days_only` 且门判休市 | **无** | `skipped` | 不变 |
| 开始 | `should_send_start()` 为真（仅开关打开） | 「▶️ 每日任务开始：…」 | — | 由无条件改为条件式 |
| 内层失败 | `find_result_failure(result)` 命中 | 「🚨 每日任务失败：…」 | `failed` | 不变 |
| 成功 + 无事 | `should_send_completion(...)` 为假 | **无** | `success`（result 原样） | **本次核心变化** |
| 成功 + 有产出 | `should_send_completion(...)` 为真 | 「✅ 每日任务完成：…」 | `success` | 文案由 `alerting.format_completion` 组装 |
| 异常 | handler 抛异常 | 「🚨 每日任务失败：…」 | `failed` | 不变 |

`manual=True` 只影响完成消息（FR-6），**不**影响失败路径（失败一律照发）。

### 2.2 `_arm_running_notice(job) -> Optional[threading.Timer]`（serves: FR-3）

```
secs = running_notice_seconds()
if secs <= 0: return None
t = threading.Timer(secs, _send_running_notice, args=(job.job_id, job.description, secs))
t.daemon = True; t.start(); return t
```
- 调用点在 `job.handler()` **之前**；`finally: if t is not None: t.cancel()`。
- 回调消息文案：`f"⏳ 每日任务仍在运行：{job_id}\n{description}\n已跑 {_format_elapsed(secs)}"`
  （`_format_elapsed` 复用 alerting 的既有实现，秒级显示）。
- **回调必须住在 `runtime.py`**：它读 `runtime._send_feishu` 全局名，测试与 notify-guard 的打桩点因此不变。
- 回调自身异常必须被吞掉并记 `logger.error("inprocess_job_running_notice_error", ...)`——
  提示失败不许影响任务线程（timer 线程里的异常会静默丢失，属必须显式处理的点）。

### 2.3 `trigger_job(job_id, force=False) -> Dict[str, Any]`（serves: FR-6）

**签名与返回体不变**（HTTP 契约不动），仅把内部线程调用改为
`threading.Thread(target=_run_job, args=(job, today), kwargs={'manual': True}, ...)`。

## 3. 修改 `daily_jobs/alerting.py`（serves: FR-2, FR-6, FR-7）

```python
def format_completion(job_id: str, description: str, elapsed: float,
                      result: Any, *, manual: bool = False,
                      warn_no_output: bool = False) -> str: ...
```

- 标题选择（优先级从上到下）：
  1. `manual is True` → `✅ 每日任务完成（人工触发）：{job_id}`
  2. `warn_no_output is True` → `⚠️ 每日任务完成（无有效产出）：{job_id}`
  3. 否则 → `✅ 每日任务完成：{job_id}`
- 正文：`{description}\n耗时: {_format_elapsed(elapsed)}` + `\n{_summarize_result(result)}`（摘要为空则不加）。
- `warn_no_output` 由调用方（runtime）算：`notify_policy.notify_noop_enabled() and result.get('no_output') is True`
  ——即**仅旧行为下**才保留 ⚠️ 语气（与 REQ-261005210015-1603 FR-3 逐字一致的可回滚形态）。
- **不改** `_send_feishu`（通道降级链）、`_summarize_result`、`_format_elapsed`、`_job_failure_watch`。

## 4. 环境变量契约（新增 2 个，均可回滚）（serves: FR-7）

| 变量 | 取值 | 默认 | 语义 |
|---|---|---|---|
| `DAILY_JOBS_NOTIFY_NOOP` | `1/true/yes/on` | `false` | `true` = 恢复旧行为：立即发开始 + 完成必发（零产出 ⚠️）；无事不发的规则**整体停用** |
| `DAILY_JOBS_RUNNING_NOTICE_SECONDS` | 浮点 | `60` | `>0` = 超阈值发「⏳ 仍在运行」；`<=0` = 关闭该提示；非数 = 回落 60 |

两者只影响**消息层**，不影响台账、重试、补跑、巡检（FR-5）。

## 5. 对外契约：零变更（serves: FR-5）

- HTTP：`POST /api/jobs/inprocess/{job_id}/run`、`GET /api/jobs/inprocess/today` 的路径、入参、响应字段**均不变**；
  人工触发只是**多了**一条回执消息，不影响响应体与状态码。
- 台账与仓储：`job_run_repository` 的读写方法签名与列集**不变**。
- 飞书/agent 通知通道：`_send_feishu` → `NotificationFacade`（agent 优先、飞书降级）**不变**，
  变的只是"什么时候调它"。

## 6. 错误语义（serves: FR-1, FR-3, FR-4）

- `notify_policy` 全部函数**不得抛异常**（env 坏值、result 任意形状都返回默认值）。
- 失败优先：`find_result_failure` 命中 → 必发 🚨（即 `result` 同时含 `no_event` 与 `success=False` 时，以失败为准）。
- 提示回调失败（`_send_running_notice` 内异常）→ 记日志、不影响任务终态与台账。
