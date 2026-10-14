# 数据模型设计（REQ-261006190953-fc43）

## 1. 不加"是否交易日"列：为什么（serves: FR-1）

`quant.simulation_equity_snapshot` 现行列（实测 `\d`）：
`id` / `account_name` / `snapshot_date` / `cash` / `position_value` / `total_value` /
`daily_return` / `cumulative_return` / `drawdown` / `created_at`，唯一键 `(account_name, snapshot_date)`。

**决定：不改 schema、不加列。** 三条理由：

1. **交易日是日历的函数**：落成列就必须在每次写入时正确填写，而"填错"正是本次缺陷的形态
   （写入方各写各的）；口径由 `quant.trading_calendar` 唯一决定，冗余列只会造出第二个真源。
2. **读取端仍要 join 日历**：既然读取端必须兜底过滤（FR-4），列带不来任何性能或正确性收益。
3. **避免 35 行的迁移语义争论**：加列就要给存量脏行定一个历史的 `is_trading_day` 值，
   而本需求已裁定这些行**删除**（D-4），加列等于给化石立碑。

> **顺带纠正一条失真的注释**：`application/services/trading_day_guard.py` 的模块 docstring 写着
> 08-08 那 5 条周末快照「现已标记 `is_synthetic=true` 并从统计口径排除」——
> **实测该列不存在、`is_synthetic` 全仓零代码引用**（只在那一行 docstring 里出现）。
> 这是**未实现的缓解措施被写成既成事实**，本需求一并改掉该注释，改为指向本设计。

## 2. 备份表结构（serves: FR-6, FR-7）

表名沿用本仓既有命名惯例（参照 `quant.bak_index_rows_w_f4aa1f6a`）：

```
quant.bak_equity_snapshot_nontrading_w_0a409569
```

```sql
create table if not exists quant.bak_equity_snapshot_nontrading_w_0a409569 (
  account_name      varchar(50)  not null,
  snapshot_date     date         not null,
  cash              numeric(15,2) not null,
  position_value    numeric(15,2) not null,
  total_value       numeric(15,2) not null,
  daily_return      numeric(10,4),
  cumulative_return numeric(10,4),
  drawdown          numeric(10,4),
  created_at        timestamp,
  -- 备份专用列（原表没有）
  backed_up_at      timestamp    not null default now(),
  deleted_reason    text         not null,
  primary key (account_name, snapshot_date)
);
```

**判据（删除前置）**：备份表行数必须 **≥ 待删行数**，否则脚本中止（不许"先删了再说"）。

## 3. 删除口径（serves: FR-6）

> ⚠️ **2026-10-06 修订（实施期，裁定 D-6）——本节原谓词已被推翻，以下为现行口径。**
> 原谓词写的是 `join calendar … and is_trading_day = false`（本意"宁可漏删不可误删"）。
> **实施期实测：生产 `quant.trading_calendar` 23373 行 `is_trading_day` 全是 true、一条 false 都没有**
> ——它是**白名单**（只列交易日，缺行即非交易日）。旧谓词因此匹配 **0 行**，`--expect 35` 永不成立，
> **一行脏数据都清不掉**。改由用户裁定为白名单语义，防误删改由"覆盖范围"承担。
> 代码实现见 `infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py` 的
> `_non_trading()`（五处 SQL 共用的唯一实现）；需求侧裁定见 `requirement.md` 的 D-6。

**判据（唯一，可复跑）**——由交易日历判定，不是日期硬编码：

```sql
delete from quant.simulation_equity_snapshot s
where s.snapshot_date between
        (select min(trade_date) from quant.trading_calendar where exchange = 'ALL')
        and (select max(trade_date) from quant.trading_calendar where exchange = 'ALL')
  and not exists (
        select 1 from quant.trading_calendar c
         where c.exchange = 'ALL'
           and c.trade_date = s.snapshot_date
           and c.is_trading_day is true);
```

- **实测待删：35 行**（5 账户 × 7 天：`2026-08-08` / `08-15` / `08-29` / `09-05` / `09-06` / `09-12` / `10-02`）——
  改用白名单谓词后，生产 dry-run 实测命中 **35 行**。
- 以"日历判非交易日"为判据而非硬编码日期：若执行当日发现行数 ≠ 35，**脚本必须打印实际行数并要求确认**
  （可能是期间新增了脏行——那正是本需求要堵的路，不能悄悄多删或少删）。
- ⚠️ **防误删现在靠覆盖范围**：只删 `min(trade_date)~max(trade_date)`（实测 `1994-03-01~2026-12-31`）
  **之内**的日期；范围之外（例如日历尚未铺到的日期）**一律不动**——保住原谓词"宁可漏删"的意图，
  同时不再要求日历显式写 `false` 行。

## 4. 重算口径（serves: FR-5, FR-6）

删除会让**后续行的基准整体前移**，因此逐账户按 `snapshot_date` 升序**全序列重放**：

| 字段 | 重算口径 | 依据 |
|---|---|---|
| `daily_return` | `(total_value - external_flow_on(account, day) - prev_total) / prev_total`，`prev` = **上一个交易日**的有效快照（`total_value>0` 且 `total_value>=cash`） | 复用 `SimulationORMRepository.calculate_daily_return`（**不另写公式**） |
| 快照 `drawdown` | 序列峰谷：`peak` 从 `initial_capital` 起逐日 `max(peak, total_value)`，`drawdown = total_value/peak - 1`（**负号口径**） | 与 `_snapshot_one` / `backfill_account` 现行写法一致 |
| `cumulative_return` | `total_value / initial_capital - 1`（行内自洽，不依赖序列） | 现行写法 |
| `simulation_account.peak_value` / `max_drawdown` | 调 `recompute_account_max_drawdown(account_name)`（唯一真源 = 净值序列，负号峰谷口径） | 既有方法，不另算 |

**为什么必须全序列重放而不是"只补被删行之后的"**：`peak` 是前缀最大值，删掉一个中间行会改变其后
每一行的 `drawdown`；`daily_return` 的基准也会跨行前移。只补局部必然留下不一致。

**重算完成判据**：把重算结果与"按当前库内序列独立复算一遍"的结果逐行比对，**零差异**
（`tools/verify_equity_snapshot_consistency.py`，见 `test-cases.md` §5）。

## 5. 迁移方式与回滚（serves: FR-6, FR-7）

**脚本**：`infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py`

```
python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py            # dry-run（缺省）
python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py --apply    # 落库
python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py --rollback # 从备份表恢复
```

| 阶段 | dry-run 行为 | --apply 行为 |
|---|---|---|
| 1 备份 | 打印将备份的行数与账户分布 | `insert ... select ... on conflict do nothing` + 校验行数 ≥ 待删行数 |
| 2 删除 | 打印将删的 35 行（账户 × 日期清单） | 执行 §3 的 delete，回执实际删除行数 |
| 3 重算 | 打印每个账户将重算的行数与受影响的 `daily_return` 差异条数 | 全序列重放 + `recompute_account_max_drawdown` |
| 4 校验 | — | 跑一致性校验 + §3 判据（非交易日行数 = 0） |

- **DDL / 锁**：建备份表是 DDL，须带 `lock_timeout='30s'`（本仓既有要求：无上限的 DDL 会挂在
  `idle in transaction` 上无限等锁）。
- **两个库**：本迁移**不改 ORM 模型**（不新增列/表到模型层），故不会触发 `tests/test_orm_db_drift.py`；
  备份表为 `bak_*` 非模型表。按本仓惯例，测试库若也要跑，用 `--dsn` 显式指定（幂等）。
- **回滚**：`--rollback` 从备份表 `insert ... select ... on conflict (account_name, snapshot_date) do nothing`
  + 重跑第 3 步重算 + 打回 `max_drawdown`。
  ⚠️ 回滚**必然要写回非交易日行**，因此走**脚本内的显式 SQL**（不经过仓储闸门），
  且脚本必须**响亮打印**「正在恢复 N 行非交易日净值行——这是回滚动作，不是正常写入」。
  仓储层的 `force=True` 保留给测试构造与后续运维，**不用于本回滚路径**。

## 6. 幂等与并发（serves: FR-6, FR-7）

| 关注点 | 设计 |
|---|---|
| 幂等 | 备份 `on conflict do nothing`；删除按日历判据（再跑删 0 行）；重算是全量重放（同输入同输出）。三步均可重复执行 |
| 并发写入 | 删除/重算期间要求**无并发写入**：闸门上线后非交易日本就不写；仍带 `lock_timeout` 并在检测到锁等待时中止而非死等 |
| 与调度关系 | 迁移**不进调度**，由人手工执行（本仓纪律：脚本只作测试/运维入口，不承担生产调度） |
| 误删防护 | §3 的两个负向约束：行数≠35 时要求确认；`is_trading_day is null` 不动 |
