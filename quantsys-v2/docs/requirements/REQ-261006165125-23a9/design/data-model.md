# 设计 · 数据模型与迁移（每日任务空结果不发飞书）

**需求ID**: REQ-261006165125-23a9
**类型**: feature
serves: FR-1, FR-2, FR-5, FR-7, FR-8

## 1. 结论：零 DDL、零迁移、零回填（serves: FR-5）

本需求**不新增/不修改任何表、列、索引、约束**，也不写任何数据迁移脚本。
静默是**消息层的决策**：飞书少发两条，`quant.inprocess_job_runs` 的写入路径与形状逐字不变。

| 对象 | 变化 |
|---|---|
| `quant.inprocess_job_runs`（表/schema） | 无 |
| `adapters/outbound/repositories/job_run_repository.py` | 无 |
| 既有数据 | 无回填、无清洗、无状态改写（历史 `success` + `no_event` 行原样保留） |
| 需要新增的存储 | 无（判据只读 `result` 内存对象） |

## 2. 被消费的 `result` 契约（只读，不新增键）（serves: FR-1, FR-2）

`result` 是 JSONB 落库、同时被通知层读取的既有结构。本需求把它**读**成"无事/有事"：

| 键 | 类型 | 现状来源 | 本设计的读法 |
|---|---|---|---|
| `no_output` | bool | `pipeline.py:236`（`computed_ok == 0`）等 | `is True` 才判无事（严格布尔） |
| `status` | str | `health.py:231` 的 `'no_event'` | `.strip().lower()` 落在 `{'no_event','no_op'}` 才判无事 |

**新增键：无。** 本需求明确不动 `no_output` 的**产生侧**（各 handler 自报口径），
因此不存在"新旧 result 形状兼容"问题——老行、新行都按同一读法处理。

现实样本（现状取证，两条路径都命中判据）：

```jsonc
// quant.inprocess_job_runs.result（2026-10-06 event_calendar_check）→ is_no_op = True（status 命中）
{"status": "no_event", "pending_in_window": 0, "notified": 0}

// evolution_fitness 零产出窗口 → is_no_op = True（no_output 命中）
{"summary": "本次无有效产出（最近有效：从未）", "computed_ok": 0, "no_output": true, "detail": {...}}
```

反面样本（**必须判为"有事"**，回归锁里逐条断言）：

```jsonc
{"updated": 12}                       // 无判据键 → 发
{"status": "success", "updated": 3}   // status 不在白名单 → 发
{"status": "no_event", "success": false}  // 无事但内层失败 → 失败优先，发 🚨（FR-4）
"字符串/列表形态的 result"              // 非 dict → 发
```

## 3. `status` 取值集合不变（serves: FR-5）

`quant.inprocess_job_runs.status` 仍只有 `running` / `success` / `failed` / `skipped`：

- "无事"**不**记 `skipped`、**不**新增取值（沿用既有裁定：改 status 会牵动 2h 失败重试与跨日补跑链）；
- `skipped` 仍只由交易日门产生，其"不打扰"由早退分支保证（本设计不改）；
- 消费方兼容性不变：`is_due` 对未知 status 落 `False`；`_job_failure_watch` 只看 `failed`；
  `_reap_orphan_runs` 只看 `running`。

## 4. 配置契约（新增 2 个环境变量）（serves: FR-7）

见 interfaces.md §4 的取值表。数据层视角只强调三点：

1. **无默认值落库行为**：两个开关都只影响"发不发消息"，不参与任何持久化决策；
2. **坏值安全**：解析容错（非数 → 默认 60；未设 → 默认 `false`），**不得**让宿主线程因配置错误挂掉；
3. **可回滚**：`DAILY_JOBS_NOTIFY_NOOP=true` 一步恢复旧行为（改 plist 环境变量 + `launchctl kickstart -k`）。

## 5. 静默之后，"跑过没跑过"仍然可查（serves: FR-2, FR-5, FR-8）

静默**只**减少外发，不减少留痕。三条可查路径（实施阶段需逐条验证可用）：

| 路径 | 查什么 | 命令/调用 |
|---|---|---|
| 台账表 | 当天是否跑过、结果是什么 | `select job_id, status, result, finished_at from quant.inprocess_job_runs where run_date = current_date order by job_id;` |
| 应用日志 | 生命周期与判据命中 | `logger.info("inprocess_job_start"/"inprocess_job_done")` 不变；新增 `inprocess_job_notify_skipped`（记 job_id + 命中的判据键，便于回答"为什么没收到消息"） |
| HTTP 巡检 | 今日状态一览 | `GET /api/jobs/inprocess/today`（响应字段不变，含 `status`/`result`） |

**新增日志事件**（唯一的新增可观测点，`runtime.py` 内）：
`logger.info("inprocess_job_notify_skipped", job=..., reason="no_op"|"manual_gate_off"...)` ——
理由：收到"今天怎么没有消息"的疑问时，日志能直接给出答案，而不是靠推断。

## 6. 迁移与回滚（serves: FR-7）

- **数据回填**：不需要（历史数据无需改写）。
- **灰度**：单机单进程，无需灰度；开关即是回滚面。
- **回滚步骤**（任一即可）：
  1. 配置级：`DAILY_JOBS_NOTIFY_NOOP=true` → 旧行为（立即开始 + 完成必发 + ⚠️ 语气）；
  2. 局部级：`DAILY_JOBS_RUNNING_NOTICE_SECONDS=0` → 关掉"仍在运行"提示，其余不变；
  3. 代码级：`git revert`（无 schema、无数据，回滚后无残留）。
- **回滚后一致性**：无中间态（静默期没有写入任何"已通知"标记，重复通知/漏通知都不会因回滚而产生）。
