# REQ-261006133733-1fdf · 拆分计划

**需求**：[requirement.md](requirement.md) · **设计**：[design/](design/)（architecture / interfaces / data-model / test-cases / use-cases，均已确认）
**侧**：backend（无 UI，无原型锚点）
**一句话目标 + 做法**：让异常值检测**真的运行**，并且**失败不再冒充「无异常」**——
改 `detect_anomalies` 的迭代对象与返回三态（`ok` / `has_anomalies: True|False|None` / `unknown_reason`），
三处消费点按三态处置（失败计问题、数据不足不计问题；质量分分量分别给 0 分 / 重新归一），
再用一条真 polars 用例锁住它、抽样 20 只实跑复验。

## 1. 代码层面变更盘点（对照需求 + 设计）

| 动作 | 文件 / 符号 | 说明 |
|---|---|---|
| **修改** | `application/services/data_validator.py` · `DataValidator.detect_anomalies` | ① 成交量段改迭代 `klines_list`（:369）；② 返回三态（`ok` / `unknown_reason` / `has_anomalies: Optional[bool]`，`error` 保留为兼容别名）；③ 数据不足早退改为 B 态（`has_anomalies=None`，`message` 文案不变） |
| **修改** | `application/services/data_validator.py` · `get_data_quality_score` | 异常率分量按三态分流：有异常按既有公式；确无异常 20 分；**数据不足剔除该分量并重新归一**；**失败给 0 分 + error 留痕** |
| **修改** | `application/services/data_quality_service.py` | ① `:152-190` 与 `:469-481` 两处按同一规则处置（失败计 `has_issues`、数据不足不计但计数）；② 汇总新增 `anomaly_unknown_count` / `insufficient_history_count`；③ 条目新增 `anomaly_unknown` / `anomaly_unknown_reason`；④ `_record_quality_check` 修 `anomalies` 空转（改遍历两个真实键）+ 增 `anomaly_detection_unknown` warning |
| **新建** | `tests/test_data_validator_anomaly_detection.py` | T1–T15 用例矩阵 + 反例锁 L1–L4（在**改前**代码上先跑红） |
| **新建** | `docs/requirements/REQ-261006133733-1fdf/notes/anomaly-recheck.md` | 实跑复验留档（抽样 ≥20 只、日志归零、读数变化对照） |
| **不改（显式）** | `adapters/outbound/repositories/kline_repository.py`（polars 返回契约）、`infrastructure/jobs/data_quality_check_job.py`（排班/阈值）、其余 10+ 处同型循环（后续线） | 见设计 §7 与需求边界 |
| **删除** | —— | 无 |

**为什么没有「迁移与兼容」单独卡**（feature 档要求单列）：本次**零 DDL、零回填、零开关**，
回滚 = 还原提交（data-model.md §1）。兼容性由两件事承载并已落在卡里：
① 返回**键集只增不改**（T6 锁）；② `has_anomalies` 类型放宽后**禁止真值判断**的静态红线（T15 锁）。

## 2. 批次与依赖

```
批次 1（可并行：两个不同文件）
  t1  data_validator：迭代修复 + 三态返回 + 质量分分流
  t2  data_quality_service：两处消费点 + 汇总计数 + 审计留痕
批次 2
  t3  真 polars 用例与反例锁（先红后绿）        depends_on: t1, t2
批次 3
  t4  抽样实跑复验与读数对照留档                depends_on: t3
```

- 无前向引用；`t3` 引用 `t1`/`t2`，`t4` 引用 `t3`。
- **契约先行**由设计阶段满足（interfaces.md §1–§3 已把三态、字段、消费点规则定死），
  故不再单列"契约卡"——避免两张卡改同一文件互相冲突。

## 3. 任务表

> 「关联 D-x」：D-2 = 用户裁定的范围 B（一行修 + 吞错改造 + 回归锁 + 实跑复验）。
> 「原型锚点」：本需求 `side=backend`，无 UI → 全部不适用。

| key | 标题 | phase / side | depends_on | 关联 D-x | 原型锚点 | footprint（files/anchors/chars） | DU |
|---|---|---|---|---|---|---|---|
| t1 | 让异常检测真的运行，并输出可区分的三态 | implement / backend | — | D-1, D-2 | 不适用 | 1 / 10 / 3200 | 7.60 |
| t2 | 下游按三态处置：失败不再当干净、数据不足不扣分 | implement / backend | — | D-2 | 不适用 | 1 / 8 / 2200 | 6.10 |
| t3 | 真 polars 回归锁与反例锁（先红后绿） | test / backend | t1, t2 | D-2 | 不适用 | 1 / 15 / 3000 | 10.00 |
| t4 | 抽样实跑复验与读数对照留档 | test / backend | t3 | D-2 | 不适用 | 1 / 5 / 1000 | 4.00 |

### t1 · 让异常检测真的运行，并输出可区分的三态

- **implementation**：改 `application/services/data_validator.py`。
  ① `detect_anomalies` 成交量段 `for kline in klines:` → `for kline in klines_list:`（:369，与价格段同源）；
  ② 数据不足早退（:331-338）改为 B 态：`ok=True, has_anomalies=None, unknown_reason='insufficient_data'`，
     `message` 文案**逐字不变**；
  ③ 成功路径返回 `ok=True, has_anomalies=<bool>, unknown_reason=None, error=None`（既有四键语义不变）；
  ④ `except` 路径返回 `ok=False, has_anomalies=None, unknown_reason=<摘要≤200>`，`error` = 同摘要（兼容别名），
     并把 `symbol` / `unknown_reason` 加进 error 日志的结构化字段（**保留既有中文文案**）；
  ⑤ `get_data_quality_score` 异常率分量按 interfaces.md §2 四态分流（有异常=既有公式；
     确无异常=20；数据不足=剔除并重新归一 `(coverage+dup)/80*100`；失败=0 且记 error）。
  依据 design/interfaces.md §1–§2。
- **acceptance**（可执行、可证伪）：
  1. `./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q -k "three_state or volume_anomaly or insufficient or detection_failure or score"` → 全过；
  2. 真库探针：`./venv/bin/python -c "from application.services.data_quality_service import DataQualityService as D; print(D().validator.detect_anomalies('600519.SH','2026-07-01','2026-10-06'))"`
     → 输出 **无** `error`（或 `error is None`）、`ok is True`、`total_anomalies` 为真实计数（可 0）；
  3. 失败注入探针：repo 抛错时返回 `ok is False` 且 `has_anomalies is None`（**不得**是 `False`），且**不抛**；
  4. `grep -rn "has_anomalies" application/services/data_validator.py` 每处均为 `is True` / `is False` / `is None` / 字面量赋值。

### t2 · 下游按三态处置：失败不再当干净、数据不足不扣分

- **implementation**：改 `application/services/data_quality_service.py`。
  ① 抽出**同一份**判定（例如模块内 helper）：`anomaly_failed = info.get('ok') is False`、
     `anomaly_unknown = info.get('has_anomalies') is None`；
  ② `:152-190` 与 `:469-481` 两处都用它：`has_issues` 判据 = `gap>0 or dup or has_anomalies is True or anomaly_failed`；
     条目新增 `anomaly_unknown` / `anomaly_unknown_reason`（既有键保留）；
  ③ 汇总（`:205/:223/:238`）新增 `anomaly_unknown_count`（失败）与 `insufficient_history_count`（数据不足）；
  ④ `_record_quality_check`（:546）改为遍历 `price_anomalies` + `volume_anomalies` 写 `type='anomaly'` warning，
     并在未知时写 `type='anomaly_detection_unknown'`（带 `reason`）。
  依据 design/interfaces.md §3。
- **acceptance**：
  1. `./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q -k "consumer or summary or audit"` → 全过；
  2. `./venv/bin/python -m pytest tests/test_data_quality_job_guardrails.py -q` → 全过（既有护栏不被带坏）；
  3. 三态汇总探针：对 3 只（正常/数据不足/失败）跑一次 `check_quality_for_symbol` 口径 →
     `anomaly_unknown_count == 1`、`insufficient_history_count == 1`（顺序可换，计数必须对得上）；
  4. 审计探针：注入失败 → `_record_quality_check` 写入的 warnings 含 `anomaly_detection_unknown`；
     有异常 → 含 `type='anomaly'`（**改前恒为空**，见 L4）；
  5. 静态：`grep -rn "has_anomalies" application/services/data_quality_service.py` → 0 处真值判断。

### t3 · 真 polars 回归锁与反例锁（先红后绿）

- **implementation**：新建 `tests/test_data_validator_anomaly_detection.py`，实现 design/test-cases.md 的
  T1–T15：真 `pl.DataFrame`（≥40 行）正/负例、成交量异常直击（T3）、数据不足 B 态、失败 C 态、
  键集兼容、质量分四分态、两处消费点计数、审计 warnings、静态红线。
  并**先在本卡开工前（改前）状态上跑一遍**记录 L1–L4 的红（`detect_anomalies` 抛错被吞）。
- **acceptance**：
  1. `./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q` → 全过（≥15 条）；
  2. `./venv/bin/python -m pytest tests/test_data_quality_job_guardrails.py -q` → 全过；
  3. 反例锁记录：T3 在**还原 t1 的一行改动**后必须变红（改动前后各跑一次，输出进卡片汇报）；
  4. 静态红线：`grep -rn "has_anomalies" application/ adapters/ infrastructure/ | grep -v "is True\|is False\|is None\|'has_anomalies'\|has_anomalies="` → 空；
  5. `notify-guard` 会话末 `egress=0`。

### t4 · 抽样实跑复验与读数对照留档

- **implementation**：新建 `docs/requirements/REQ-261006133733-1fdf/notes/anomaly-recheck.md`，记录：
  ① 抽样 ≥20 只（K 线 ≥60 行）跑 `detect_anomalies` → `ok=False` 数、`total_anomalies` 分布（须出现 >0）；
  ② 复验窗口内 `grep -c "检测异常值失败" logs/api.log` = 0（对照今日基线 7995 条/4 分钟）；
  ③ 读数变化对照：质量分（异常率分量不再白送）与 `stocks_with_issues` 方向，按架构 §6 口径写明
     "这是读数变真、不是回归"；
  ④ 若窗口内未重跑质量检查（task 232 每日 00:00），如实写明"未取到当日复跑"，**不得**用单测顶替。
- **acceptance**：
  1. 观察文件存在且三条（第④条为窗口说明）齐备，各带命令 + 原始输出摘要；
  2. `ok=False` 计数 = 0；
  3. `total_anomalies` 分布中出现 **>0** 的样本；
  4. 复验窗口内 `检测异常值失败` 新增条数 = 0。

## 4. 容量纪律（一轮装多少：先算，再切）

- 口径：`detailUnits = files×1 + anchors×0.5 + chars/2000`，容量缺省 **16 DU**（权重与容量只在 `src/domain/limits.ts` 定义一次，本计划不另抄）。
- 核算：t1 = 7.60 / t2 = 6.10 / t3 = 10.00 / t4 = 4.00 —— **全部 ≤ 16 DU，无超容量卡**（故无「⚠️超容量」标记）。
- 拆卡依据：**按文件 + 阶段切**（`data_validator` 卡、`data_quality_service` 卡各自独立可验、可单独回滚；
  用例卡与实跑卡分离）。两处消费点**同属一个文件**故合为一卡——避免拆成两张卡改同一个文件互相冲突。

## 5. 边界校验（不超范围、卡可独立验收）

- 每张卡只凭卡片即可开工：implementation 点到**具体文件 + 符号 + 行号 + 期望形态**，
  acceptance 全是可跑命令 + 期望输出；零会话历史的新窗口也能执行。
- 不二次创作设计：三态字段名、消费点规则、质量分分流**逐字来自** interfaces.md；
  实施中若发现设计有误（例如某消费点还有第三种用法），**回设计阶段**改设计后重新提交计划。
- 范围外**不建卡**：同型扫描（E9）、`data_backfiller` 的 294 条失败、日志限流、
  质量阈值调整 —— 全部登记在需求「后续线」。

## 6. 不做什么（照抄设计边界）

1. 不改 `get_daily_klines` 返回类型、不引入 pandas/polars 适配层。
2. 不改 Z-score 算法 / 阈值 / 异常定义。
3. 不加表列 / 迁移 / 开关 / 日志限流。
4. 不动 task 232 的排班与告警阈值；不扫全仓同型循环。
5. 不回填/不追认历史质量读数（只在新读数里体现）。
