# REQ-261006163444-8e4f · 设计：测试策略与用例

> 全部命令在仓根、用 `./venv/bin/python` 执行。用例文件：`tests/test_kline_domain.py`（纯函数）、
> `tests/test_data_quality_alert_scope.py`（作业口径）；并同步更新既有替身
> `tests/test_data_quality_job_guardrails.py:70` 的 `check_data_quality` 假实现（补 `per_symbol`，契约变更所致）。

## 1. 用例矩阵（定死输入与期望）（serves: FR-1, FR-2, FR-4, FR-5）

| # | 输入（构造） | 期望 | 锚点 |
|---|---|---|---|
| T1 | 交易日 `[09-30, 09-29, 09-28]`；标的 A mx=09-30、B mx=09-28、C mx=08-01 | A∈tradable(gap 0)、B∈observing(gap 2)、C∈stock | 三分法 |
| T2 | gap 恰好 **4** 与 **5** 各一只 | 4 → observing；5 → stock（边界闭合：`1<=gap<=4` / `gap>=5`） | 边界 |
| T3 | 一只 mx=09-29（gap 1） | 同时在 `observing` 与 `dropped_new` | 掉出定义 |
| T4 | `trade_dates_desc` 只有 1 个元素 | `prev_trade_date is None`、`dropped_known is False`、`dropped_new` 为空 | 不可判 |
| T5 | `trade_dates_desc=[]`、`symbol_last_dates=[]` | `degraded is True`、`degrade_reason` 非空、三个集合为空、**不抛异常** | 退化 |
| T6 | 某标的 mx 不在交易日集合内 | 落 `stock`、`gap_days[s]==9999`、日志 warning 点名 | 脏数据 |
| T7 | 任意输入（属性断言） | `tradable`/`observing`/`stock` 两两不相交，且并集 == `set(gap_days)`、三者计数之和 == `len(gap_days)` | 不变量 |
| T8 | `domain`（域内 3 只 / 存量 2 只）+ `per_symbol`：域内评分 `[100, 90, 82.5]`、存量 `[25, 25]` | `mean_score = 90.83`（**不含**存量）；`d_grade` 只数域内 `'D'` | 分母 |
| T9 | 域内 D 级 = 3（阈值 20）→ 再改为 21 | 3：无 `quality_grade` 告警；21：产生 warning「D级股票数量过多」 | 阈值分支 |
| T10 | 域内均值 90.84（阈值 88.0）→ 再改为 87.9 | 90.84：无告警；87.9：产生 warning「数据质量评分偏低」 | 阈值分支 |
| T11 | `dropped_new` = 3 只 / 25 只 | 3：正文列 3 只且 `dropped_truncated=False`；25：`count=25`、`symbols` 只 20 只、`truncated=True` | 截断不冒充 |
| T12 | 回填 n=7 失败 5；再 n=10 失败 6 | 7：**不判**失败率，正文写样本与门槛；10：`失败率 60% > 50%` → error | 样本门槛 |
| T13 | `per_symbol` 里 5 只死标的 + 2 只活标的均有缺失天，`tradable` 只有那 2 只 | 回填目标 == 那 2 只（死标的**不出现**） | 纪律 B |
| T14 | 任一 `_persist_quality_audit` 调用（`gap_info={'total_trading_days': 60, 'actual_days': 55, ...}`） | 写入 `original_count == 60`（**非 0**） | 审计列 |
| T15 | 同一 `(grade='D')` 在当天写入两批各 403 行（不同 symbol 交集 402） | `count_by_grade_on('D')` == distinct 标的数（**不是** 806） | 去重 |
| T16 | `per_symbol` 覆盖 4120 只、`tradable` 5280 只 | `partial=True`，正文写「统计 4120/5280（已截断）」 | 诚实标注 |
| T17 | `quality_result` **不含** `per_symbol` | 产生 error 告警 `qa_scope_unavailable`；`result['alert_scope']=="degraded"`；**不调用** `count_by_grade_on` 兜底 | 降级响亮 |

## 2. 反例锁（证明这些锁真能抓住原缺陷）（serves: FR-1, FR-2, FR-5）

| 锁 | 用例 | 改前应红（记录为证据） |
|---|---|---|
| L1 | T15（同日两批行） | 改前 `count_by_grade_on('D')` 返回 **806**（行数）≠ distinct ⇒ 红 |
| L2 | T8/T9 用今日真实事实（域内 D=3、均值 90.84）走**旧口径**（全库 5686 + 阈值 95.0） | 改前必然产出两条 warning（D级 500 越线 + 评分 86.28 < 95）⇒ 红 |
| L3 | T14 | 改前 `original_count == 0` ⇒ 红 |
| L4 | T13 用今日真实 7 只目标 | 改前目标含 5 只已退市（000013/000602/000606/000939/002288）⇒ 红 |

**反例锁纪律**：四条锁必须在**改动前的代码**上跑一次并保留输出（写进任务汇报），
否则无法证明"锁真的能抓"，只能证明"现在恰好是绿的"。

## 3. 可跑命令与判定（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

### 3.1 用例（serves: FR-6）

```bash
./venv/bin/python -m pytest tests/test_kline_domain.py tests/test_data_quality_alert_scope.py -q   # 全过
./venv/bin/python -m pytest tests/test_data_quality_job_guardrails.py -q                            # 既有回归全过
```

### 3.2 分域与去重的独立复算（SQL，与代码实现互证）（serves: FR-1, FR-2）

```bash
# 三层计数（期望 5280 / 3 / 403，合计 5686）
psql -d quant_investment -c "
with r as (select trade_date, row_number() over (order by trade_date desc) rn
           from (select distinct trade_date from quant.daily_klines) t),
     m as (select symbol, max(trade_date) mx from quant.daily_klines group by 1),
     g as (select m.symbol, coalesce(min(r.rn)-1, 9999) gap from m left join r on r.trade_date=m.mx group by m.symbol)
select case when gap=0 then 'tradable' when gap<=4 then 'observing' else 'stock' end k, count(*)
from g group by 1 order by 1;"

# distinct 计数（改后代码应返回 404，而非 806）
psql -d quant_investment -c "select count(*) rows, count(distinct symbol) syms
  from public.kline_data_quality where created_at::date = current_date and grade='D';"
```

### 3.3 实跑一次检查并读告警段（serves: FR-2, FR-3）

```bash
./venv/bin/python -c "…触发 task 232 一次（或走既有手动触发路径）…"
grep -A 25 "data_quality_alert" logs/api.log | tail -30
```

判定：正文含 `检查域: 可交易 … / 观察中 … / 存量 …`、`本期掉出可交易域`、`统计 N/N 只`；
**不含**「D级股票数量过多」「数据质量评分偏低」两项。

### 3.4 回填限域与噪音归零（serves: FR-4）

```bash
psql -d quant_investment -c "select count(*) from quant.daily_klines where trade_date='2026-09-30'
  and symbol in (<本轮回填目标>);"     # == 目标只数（100% 在域）
grep -c "All data providers failed" logs/api.log   # 复验窗口内新增 = 0（今日基线 374，全部来自退市标的）
```

### 3.5 审计列（serves: FR-5）

```bash
psql -d quant_investment -c "select symbol, original_count, cleaned_count
  from public.kline_data_quality order by created_at desc limit 5;"   # original_count > 0
```

## 4. 实跑复验（产出的两份证据）（serves: FR-2, FR-4)

1. **告警正文全文**（`logs/api.log` 的 `data_quality_alert` 段）：证明域内口径生效、掉出名单可见。
2. **run 结果 jsonb**：`quant.scheduler_runs` 最新一条的 `result` 含 `domain`（三层计数 + `last_trade_date`）、
   `domain_dropped`、`alert_scope == "tradable"`、`alert_thresholds`，且**不含** `per_symbol`。

```bash
psql -d quant_investment -c "select result->'domain', result->'domain_dropped', result->'alert_scope'
  from quant.scheduler_runs where task_id=232 order by started_at desc limit 1;"
```

## 5. 读数变化的验收口径（防止把"变真"当回归）（serves: FR-2）

| 读数 | 旧 | 新（同日数据） | 判定 |
|---|---|---|---|
| D级告警 | 806 只 → warning | 域内 3 只 → 无 | **通过**（不是漏报，是去掉死标的+重复计数） |
| 评分告警 | 86.28 < 95 → warning | 90.84 > 88.0 → 无 | **通过** |
| 回填失败率 | 71.4% (5/7) → error | 域内目标且 n≥10 才判 | **通过** |
| 告警条数 | 3 项（2 误报 + 1 无效样本） | 1 项（掉出域 warning，2 只） | **通过** |

**验收必须先接受**：前三项从红转绿**不是**"告警坏了"，而是分母从假变真（architecture.md §6）。
若有人要求"必须仍然报 D级过多"，说明其要的是旧口径——那属于 D-2 已否决的选项。

## 6. 不测什么（避免用例越界）（serves: FR-6）

1. 不测 `is_delisted`/`is_suspended` 标记（不属本需求，后续线 1）。
2. 不测评分公式与 Z-score 阈值（后续线 3）。
3. 不测告警渠道投递本身（既有 `NotificationFacade` 契约不变；测试期外发由 `notify_guard` 兜底）。
4. 不测整个采集管道停摆的检测（architecture.md §8 已登记盲区，责任方是 `freshness_guard`）。
