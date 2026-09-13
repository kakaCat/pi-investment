# session_leak_detected 复发处置：快照 job 只读不归还会话（看板事件 a6780ec3）

- 时间：2026-09-13 18:57｜窗口：w-32314d00（投资脑 investor）
- 事件：`session_leak_detected` 累计 50 次；首现 09-11 03:35，复发至 09-13 18:27

## 1. 先做归因：这条不是"又坏了"，而是"还剩一条"

按会话来源聚合日志里 40 条泄漏记录（traceback 首帧）：

| 来源 | 次数 | 末次出现 | 判定 |
|------|------|----------|------|
| opportunity_scoring_service.py:366 `_score_single_stock` | 32 | 09-11 23:05 | 修前，已停止 |
| jobs/data_jobs.py:125 `_run` | 2 | 09-12 22:35 | 修前，已停止 |
| daily_jobs_bootstrap.py:858 `_run_job` | 2 | 09-12 23:06 | 修前，已停止 |
| scheduler_tasks.py:1149 / :236 | 1+1 | 09-10 / 09-11 | 修前，已停止 |
| scheduler/job_executor.py:74 | 1 | 09-12 15:50 | 修前，已停止 |
| **evolution/daily_snapshot_service.py:257 `run` → :240 `_has_bar`** | **1** | **09-13 18:26** | **未修** |

结论：此前 6 条来源各自修完后均已停止，本路径是**剩下唯一**的泄漏点。

## 2. 根因

`EquitySnapshotJob._has_bar()` 解析 `IKlineRepository` 做只读查询：
`kline_repository.get_daily_klines` 走 `self.session`（scoped session）→ autobegin 事务 →
服务层用完既不 commit 也不 close → 连接挂在 `idle in transaction`，
337 秒后被 PostgreSQL 按 `idle_in_transaction_session_timeout` 强杀，
`session_guard` 随即报 `session_leak_detected`（并伴随 `leaked_session_already_closed_by_db`）。

## 3. 修复与验证

`_has_bar` 用 `try/finally` 归还会话（`close_session()`，与既有 6 处修法同一约定）：

```
$ PYTHONPATH=. venv/bin/python /tmp/verify_snapshot_leak.py    # 开启 session_guard 实测
baseline active_sessions = 0
--- (1) 旧泄漏形态：只读不归还 ---
    rows = 1
    active_sessions = 1        ← 泄漏被 guard 登记
    in_transaction = True
--- (2) 修复后的 _has_bar ---
    has_bar(2026-09-11) = True
    active_sessions = 0        ← 无泄漏
    in_transaction = False
```

其余证据：
- 重启 v2：启动 **18:57:33 > 文件 mtime 18:57:09**，`/health` ok；重启后泄漏计数 **0**；
- 端到端跑该 job：`daily snapshots written date=2026-09-11 skipped=0 written=7`（功能正常）。

## 4. 残留与线索

- 本族是**按调用点逐个修**（新代码仍可能引入新泄漏点）。系统性方案是在只读仓储方法里统一
  收尾（`_end_read()`），但会改变 scoped session 的生命周期语义、影响面大，未擅自实施。
- 跑 job 时该 job 自己报了一条告警值得单独看：
  `日收益率异常偏大: agent_brain 2026-09-11 daily_return=4.0105 total_value=500396.0 —— 请核查基准快照与当日估值完整性`
  （401% 日收益，通常是基准快照缺失导致的分母异常，非真实收益）。仅登记，未深查。
