# 错误事件处置：session_leak_detected（a6780ec3）

- **事件 ID**：`a6780ec3-28cb-4e8a-8a7e-c07a8935c544`（source=v2，error，频次 48；首现 09-11 03:35，最近 09-12 23:07）
- **处置窗口**：w-32314d00

## 1. 机制：读操作 autobegin 的事务没归还

`session_guard` 的判定语义（2026-09-11 已由 w-8f2c4cc5 修正，本轮复核确认正确）：

| 情形 | 处置 | 日志级别 |
|---|---|---|
| Session 对象已被 GC（弱引用死） | 只注销（误报） | — |
| 存活但 `in_transaction()==False` | 只注销（未持有连接资源） | warning `session_unregistered_idle` |
| 存活且 `in_transaction()==True` | rollback + close 止血 | **error `session_leak_detected`** |

本轮 39 条 ERROR 的 age 全部落在 **311~359s**（刚过 300s 阈值）→ 都是"持有活动事务超时"这一类，
即 **SQLAlchemy 读操作隐式开启的事务没有被 commit/rollback 掉**：线程做完读之后转去做长时间非 DB 工作
（数百次网络抓取 / 模型训练），或池化线程归还线程池，线程本地 scoped session 就一直握着连接
（idle in transaction）。

## 2. 审计出的四处持有者（按日志签名统计）

| 路径 | 线程 | 次数 |
|---|---|---|
| `opportunity_scoring_service._score_single_stock` → `stock_repository.get_by_symbol` | ThreadPoolExecutor-N | **10+**（最多） |
| `data_jobs._run` → `stock_repository.get_all` | `asyncio_0`（asyncio.to_thread） | 2 |
| `scheduler_tasks.handle_model_train_auto` → `_check_train_needed` | `asyncio_0` | 1 |
| `daily_jobs_bootstrap._job_financial_statements` → `financial_statement_update_job.execute` | `job-financial-statements` | 2（**最后一次 09-12 23:06:41，age=359**） |

最后一条特别说明：周六 23:00 起跑的 `financial_statements` 读了宇宙（开事务）后连续跑 12 小时，
事务全程挂着 → 正是本事件"最近"那条。

## 3. 落地动作（四处补"用完即归还"）

1. `opportunity_scoring_service._score_single_stock`：`finally` 归还会话（池化线程必须每个任务自清）。
2. `data_jobs.DataUpdateJob._run`：`get_all()` 读完后立即 `close_session()`（原先只在 per-symbol 的 `_fetch_one` 里清，外层线程没清）。
3. `scheduler_tasks.handle_model_train_auto`：补 `finally: _release_thread_session()`（此前只在 `_check_train_needed` 单点释放，提前 return 的分支覆盖不到）。
4. `financial_statement_update_job.execute`：宇宙解析后**立即**释放，收尾再释放（覆盖"探活失败早退"分支）。

全部复用既有 `close_session()`（幂等、按线程本地注册表注销）。

## 4. 验证

```console
# ① 线程内实测（修复后真实跑一遍财报 job）
job: {'success': True, 'updated': 1, 'rows': 103, 'balance_rows': 103}
该线程 session.in_transaction(): False        ← 不再挂着事务
guard 注册表中仍存活的 session 数: 0          ← 线程会话已归还

# ② 该事件串不再出现
最后一条 session_leak_detected: 2026-09-12 23:06:41（thread=job-financial-statements, age=359）
2026-09-13 全天新增: 0 条

# ③ 回归测试
$ pytest tests/test_session_release.py -q     → 3 passed
     （评分 worker finally 归还；data_jobs 外层读后归还；财报 job 探活失败早退分支也归还）
```

## 5. 结论

- **事件性质**：真实资源占用（connection idle in transaction），非误报；已在主要四条路径根治，
  guard 仍作为兜底（其"无事务只注销、有事务才报泄漏"的语义正确，无需改动）。
- 通用纪律：**任何"读一下再干很久"的线程路径，读完必须归还线程会话**（`close_session()`），
  池化线程尤其如此——否则事务会以 idle-in-transaction 形式占住连接池坑位。