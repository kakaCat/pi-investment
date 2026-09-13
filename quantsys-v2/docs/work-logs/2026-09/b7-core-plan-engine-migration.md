# B7：core_plan_service 去 subprocess psql，收口到 engine（2026-09-13，w-a9ec14d7）

## 背景

`quantsys-v2/application/services/core_plan_service.py` 是**投资脑建仓计划的唯一产出点**
（定时任务 `core_plan_generate`，task id 337，工作日 09:05；agent 09:10 读取
`config/core_plan.json`）。它是钱路：写出来的目标持仓会直接影响建仓动作。

上迁自 `scripts/core_plan.py` 时保留了原脚本的数据访问方式 —— **subprocess 调 psql**。
本次（B7）把它收口到 infrastructure 的 SQLAlchemy engine。

## 为什么必须收口（不是洁癖）

1. **隐式外部依赖**：`psql` 是外部二进制，代码里还自己拼 `PATH="/opt/homebrew/bin:..."`。
   在 launchd 托管环境下属"能跑但不可控"——PATH 一变就静默失效。
2. **拼接 SQL**：账户名等外部值直接进语句（R-019 要求账户来自 agents.json，不该经字符串进 SQL）。
3. **报错信息被吞**：`check=True` 把数据库侧原始报错压成 `CalledProcessError`，
   "查询失败"与"查询成功但为空"难以分辨（本项目已有多次同类事故）。

## 改动

| 位置 | 改动 |
|---|---|
| 取数 helper | `psql`/`psql_csv`/`psql_csv_plain` → `_engine`/`query_df`/`query_rows`/`kline_history` |
| 候选池 `px` | 日期条件改绑定变量 `:def_start`/`:def_end` |
| 账户资金 | 字符串拼接 → 绑定变量 `:acct`；**查不到账户行改为显式 ValueError**（原为 `IndexError`，信息量为零） |
| `hist` / `_gh` | 拼 IN 子句 → `kline_history()` 的 expanding 绑定变量 |
| `ind_mom` 等行业动量 | `psql_csv_plain` → `query_df` |
| 死代码 | 删除 `if __name__ == "__main__": raise SystemExit(main())` —— `main()` 从未随上迁搬过来，是**必然 NameError 的死引用** |
| 文档 | 改正两处与实现不符的说明（见下） |

### dtype 对齐（不是可有可无的美化）

原实现是 `copy (...) to stdout with csv header` → `pd.read_csv`，numeric 列一律落 **float64**；
改走 engine 后 psycopg 对 `numeric` 返回 `decimal.Decimal`，pandas 落 **object** dtype。
object dtype 会让下游排序/均值/比较出现静默差异，故 `_to_float_if_decimal()` 显式收敛。
（实测：`quant.daily_klines` 的 close/amount 是 `double precision` → 本来就 float；
只有 `quant.simulation_account` 的 total_value/cash_available 是 `numeric`。）

### 文档/实现对齐

- 原文案称产出第 3 项是"与当前持仓的差额（需要买/卖多少股）"——**代码从未实现**：
  本服务不读 `position_list`，产出的是"目标组合"而非"待下委托"。按实现改正，
  避免计划文件被消费方当成下单清单。
- 原文案写"09:10 例行任务调用"，实际 cron 是 **09:05 生成 / 09:10 读取**（写错 5 分钟会让
  agent 在校验前就读取旧文件）。

## 等价性验证（钱路必须逐字段比对）

方法：从 HEAD 取出改动前版本，在**同一进程环境、同一时点**分别跑 `generate()`，逐字节比 stdout、
逐字段比 JSON。

**结论：**

- **stdout 逐字节相同**。
- **JSON 除 `generated_at` 外仅 2 处末位差**，且经查证**均非本次移植引入**：
  1. `sector_heat_top5` —— 来自**实时接口** `/api/market/sectors`，重启前后返回不同
     （重启前 49 个行业且全为负，重启后 496 个行业）。该字段**不参与选股**（两版 picks 完全一致）。
  2. `amount_def_avg` 末位差 —— **PostgreSQL 并行聚合的固有非确定性**：
     `EXPLAIN` 显示该查询为 `Parallel Seq Scan → Partial HashAggregate → Gather Merge`，
     同一查询连续 8 次跑出 **4 种不同的末位组合**（000100 与 600895 各在两个相邻 double 间跳）。
     即：这个值**本来就不可重现**，与本次改动无关。

### 顺带证实的旧路径缺陷：pandas CSV 浮点解析不是正确舍入

```
DB 真值（psql 文本 / engine 二进制一致）  1950778427.7948718
旧路径 psql 文本 → pd.read_csv            1950778427.794872     ← 差 1 ULP
新路径 engine 二进制                      1950778427.7948718    ← 精确
float("1950778427.7948718")             1950778427.7948718
pd.read_csv(同一文本)                    1950778427.794872
```

即：**"psql 文本 + pd.read_csv"这条链在最末一位上会静默丢精度**，新路径不再经过文本。
影响量级 1e-16 相对误差，对建仓计划无实际影响，但记录在案：**别把 CSV 往返当作无损通道**。

## 上线验证（三件事齐全才算"能跑"）

沿用既有核验纪律：①job 已注册 ②`next_run_at` 可算 ③**真触发成功**。缺 ① 曾放过两个致命 bug。

1. 重启 v2 载入新代码：`launchctl kickstart -k gui/$(id -u)/com.pi-investment.v2-api`（8s 恢复健康，
   `db_connected: true`）。
   ⚠️ 不重启就触发 = 跑的是**进程内已缓存的旧模块**，验证无效。
2. `POST /api/scheduler/tasks/337/trigger` → `last_status=success`（run_id=3697，14014ms）。
3. 产物核对：`config/core_plan.json` = account `agent_brain`、总资产 500000 / 现金 485920、
   core 15 只 + 成长板子额度 2 只，与 A/B 参照一致。
4. `next run at: 2026-09-14 09:05:00 CST` —— next_run_at 正确推进。

**DSN 可用性同时被证实**：engine 路径需要 `QUANT_DATABASE_URL`（`.env` 第 31 行），
由 `adapters/inbound/fastapi_app/main.py` 的 `load_dotenv` 注入；原 psql 路径不需要它。
若该注入失效，本次改动会让 09:05 任务失败 —— 真触发成功即反证注入有效。

## 遗留

- `tests/research/*.py` 仍各自定义本地 `psql_csv`。按用户裁定「脚本只能测试用」，
  研究脚本用 psql 是允许的，**不在本次范围**。
- `/api/market/sectors` 重启前后返回 49 vs 496 个行业 —— 疑似**降级特征**（行业数骤减 + 全为负值）。
  该接口只用于 `sector_heat_top5` 信息标注，不参与选股，但值得纳入健康核验观察项。
- os 建仓计划的 DSH 工具入口（B8）仍未做，agent 目前直接读 JSON 文件。

## 提交

- refactor(v2): core_plan 去 subprocess psql 收口到 engine（B7）—— 代码 + 本工作日志
