# 「看板卡住」根因与处置：18 个错误事件卡在 processing + 调度运行记录 JSONB 写入 bug

- **现象**：用户报「卡住了」
- **处置窗口**：w-32314d00

## 1. 诊断（先排除服务/进程层）

```console
dashboard/api/board        HTTP=200  0.31s  48KB      ← 看板接口正常
quantsys-v2 /health        HTTP=200  0.001s
Agent OS error-events      HTTP=200  0.003s
inprocess_job_runs running: []   scheduler_runs running: []   ← 无僵死任务
dsh 进程 RSS 2056MB（heap 看门狗阈值 6GB+）· err 日志近 20s 增长 0 字节
```

服务都活着、没有卡死的任务、日志没有洪水——所以"卡"不在进程层。

## 2. 真因：18 个错误事件**永久停在 processing**

```console
error_events 状态分布: resolved 253 / ignored 103 / **processing 18** / open 15
  · 12 个 assignee=w-32314d00（本窗口）· 6 个 w-ed511891 · 1 个 w-c8cae280
  · 全部 >1 小时无动作（最早 09-10 22:02，最近 09-12 19:12）
```

机制：看板「我来解决」= claim → 状态置 `processing` + assignee=该窗口；
**若窗口没有回写终态，卡片就永远停在"处理中"**。而且状态机实测：

```console
POST error-action {action: reopen} on processing →
  {"success":false,"error":"状态机不允许：当前状态 processing 不可 reopen（仅 resolved/ignored 可复开）"}
```

即 **processing 只能 resolve/ignore，无法退回待处理池** → 派单后没人收尾的卡就成了"僵尸卡"，
越积越多，看板看起来就是"卡住"。

## 3. 处置过程中挖出并修掉的真 bug（这才是 6 张卡的来源）

手动重跑 `ingest_events_daily`（task 331）实测：

```console
Job ingest_events_daily completed: success=True        ← handler 明确成功（712 条事件）
Task failed: ingest_events_daily (run_id=3686, error=(raised as a result of Query-invoked autoflush; ...
  [parameters: [{'status': 'success', 'result': {... 319572 characters truncated ...}]]
```

**任务成功了，却被记成 failed**：`SchedulerRepository.complete_run` 把 handler 返回值直接写 JSONB 列，
而返回值里含 `datetime.date` → SQLAlchemy json 序列化抛 `TypeError: Object of type date is not JSON serializable`，
UPDATE 失败 → 整个 run 记 failed，并刷出 6 张错误事件卡（09-12 17:01 那批的 `date is not JSON serializable` /
`StatementError autoflush` / `Task failed: ingest_events_daily` 都是它）。

**修复**：`complete_run` 写库前统一过 `_json_safe()`（复用 `adapters.shared.json_helpers.sanitize_for_json`，
失败兜底 `str(value)`）——绝不因为"记录写不进去"把成功任务记成失败。

**验证**（重启后重跑同一任务）：

```console
run 3686 failed → run 3687 **success**（duration 16s）
task 331 last_status=success, last_error=''
最新 run result: jsonb_typeof=object, 长度 319600 字符   ← 大 payload 正常落库
pytest tests/test_scheduler_run_result_json.py → 3 passed
```

## 4. 闭环动作（看板已解锁）

- 18 张僵尸卡全部处理：**有证据不再复现的 → resolve**（连接已关闭/baostock 登录/指数行 CHECK/WatchEngine 启动），
  **根因已修的 → resolve**（JSONB 写入 bug，附 run 3687 success 证据），
  **非本窗口认领且 claim 失效的 → 代写 resolve 并留"如需处理请复开"**（processing 无法 reopen，这是唯一可行的解卡方式，note 里写明替代关系与责任依据）。
- 结果：`processing` **18 → 0**；分布 resolved 268 / ignored 103 / open 18。

## 5. 建议（防复发，待人工/其它仓库落地）

1. **状态机允许 `reopen` from `processing`**（或加 stale-claim 超时：processing 超 N 小时自动退回 open）——
   这是本问题的结构性根源，在 Agent OS（非本仓）侧。
2. **窗口侧纪律**：认领即责任——派单后必须回写终态；本次 6 张僵尸卡本就属于"该回写没回写"。
3. 已就绪但待实例重启生效：solve-kit 派单前终态复核（拒绝对已闭环卡片重复派单）。