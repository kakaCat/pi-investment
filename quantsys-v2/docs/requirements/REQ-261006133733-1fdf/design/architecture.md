# REQ-261006133733-1fdf · 设计：架构

## 1. 缺陷定位（一行错 + 一层吞）（serves: FR-1, FR-2）

```
DataValidator.detect_anomalies                # application/services/data_validator.py:296
  ├─ :328  klines = self.kline_repo.get_daily_klines(...)   # KlineORMRepository → polars DataFrame
  ├─ :331  if klines.is_empty() or len(klines) < 30: return  # 「数据不足」早退（本次改为三态语义）
  ├─ :341  klines_list = klines.to_dicts()                  # list[dict]（正确形态）
  ├─ :356  for kline in klines_list:   ← 价格段：**对**      ✅ 只在 :369 价格段之后未被复用
  └─ :369  for kline in klines:        ← 成交量段：**错**    ❌ 迭代 polars DataFrame
             :370  float(kline['volume'])   → pl.Series[...]   → TypeError（polars/_utils/getitem.py:76）
             :375  str(kline['trade_date'])
```

- **错法**：polars 的 `for row in df` 产出的是 **Series**（不是 dict），`series['volume']` 会被当成
  "用字符串序列选择元素" → `TypeError: cannot select elements using Sequence with elements of type 'str'`（E3）。
- **吞法**：`except`（:389-396）把异常变成 `{'has_anomalies': False, 'total_anomalies': 0, 'error': …}`
  ——**失败被写成了"数据干净"的肯定结论**；`error` 字段虽在，但三处消费点都不读它（E5/E6）。

**由此得出一条设计纪律**（本需求的核心，FR-2）：
> 一个函数**不得**用它"正常返回"的取值来表达"我没跑成"。失败必须是**具名的第三态**。

## 2. 三态模型（本设计的中心）（serves: FR-1, FR-2）

| 态 | 语义 | 载体 |
|---|---|---|
| A 正常 | 真的检测过 | `ok=True` + `has_anomalies ∈ {True, False}` + `unknown_reason=None` |
| B 数据不足 | 判定**不适用**（K 线 <30 行） | `ok=True` + `has_anomalies=None` + `unknown_reason='insufficient_data'` |
| C 检测失败 | 判定**没跑成** | `ok=False` + `has_anomalies=None` + `unknown_reason=<错误摘要>` |

- **为什么 `has_anomalies` 要变 `None` 而不是留 `False`**：`None` 让"未知"在**类型层**就无法被误读成
  "干净"；同时保留键名，旧消费者不会 KeyError（契约见 interfaces.md §1）。
- **为什么 B 与 C 分开**：B 是**正常业务情形**（次新股/长停股），扣它 20 分是错的；
  C 是**故障**，必须计 0 分并留痕。二者处置不同，故必须可区分。
- **为什么 `total_anomalies` 不能当结论**：C 与 B 都返回 0；只有配合 `ok` / `unknown_reason` 才有意义。

## 3. 下游处置：三处消费点，一份规则（serves: FR-3, FR-4）

```
detect_anomalies ──► check_quality_for_symbol (:152)  ──► has_issues / stocks_with_issues / 审计
                 ├──► check_data_quality_single (:469) ──► has_issues / 汇总
                 └──► get_data_quality_score (:434)    ──► 异常率分量（20 分）
```

| 消费点 | 失败（C） | 数据不足（B） | 有/无异常（A） |
|---|---|---|---|
| **问题判定** `has_issues` | **计入问题**（"待查"，不得当干净） | 不计入（新股不是质量问题），单独计数 | 按 `is True` 计入 |
| **汇总** | `anomaly_unknown_count += 1` | `insufficient_history_count += 1` | 既有字段不变 |
| **质量分异常率分量** | **0 分** + error 留痕 | **剔除该分量并重新归一**（不奖不罚） | 既有公式 |
| **审计 warnings** | 新 `type='anomaly_detection_unknown'` | 同左（reason 区分） | 遍历两个真实键写 anomaly warning（修既有空转） |

**单一规则原则**：`:152` 与 `:469` 两处必须用**同一套判定**（`is True` / `is None` + `ok`），
不许各写一份（本仓反复踩"同一件事两处实现"）。

## 4. 文件结构（新建 / 修改 / 删除，各自职责一句话）（serves: FR-1, FR-2, FR-3, FR-4, FR-5）

| 动作 | 文件 | 职责一句话 |
|---|---|---|
| **修改** | `application/services/data_validator.py` | ① `detect_anomalies` 成交量段改迭代 `klines_list`；② 返回三态（§2）；③ `get_data_quality_score` 异常率分量按三态分流 |
| **修改** | `application/services/data_quality_service.py` | ① `:152-190` 与 `:469-481` 两处按 §3 判据处置并新增键；② 汇总新增两个计数；③ `_record_quality_check` 修 `anomalies` 空转 + 增未知 warning |
| **新建** | `tests/test_data_validator_anomaly_detection.py` | 真 polars 正/负例、反例锁、失败注入、三态契约、质量分三态、消费点计数（用例矩阵见 test-cases.md） |
| **不改** | `adapters/outbound/repositories/kline_repository.py` | `get_daily_klines` 的 polars 返回是既有契约（多处依赖） |
| **不改** | `infrastructure/jobs/data_quality_check_job.py` | 排班/交易日策略/告警阈值属 a315 已定口径；本需求只让它的读数变真 |
| **不改** | 其余 10+ 处 `for … in klines:` | 同型扫描属后续线（边界「不做什么」1） |
| **删除** | —— | 无 |

## 5. 回滚与灰度（serves: FR-3）

- **零迁移、零开关**：纯代码；回滚 = 还原提交（回滚后行为回到"假阴性 + 7995 条日志"）。
- **不需要**灰度：改动集中在一条判断链；风险点只在"读数变化"（见 §6），而那正是本需求的目的。
- **可部分回滚**：① 只回滚 `data_validator` 的迭代修复 → 检测恢复正常但失败仍被吞（**不推荐**，
  等于保留本需求要消灭的形态）；② 只回滚质量分分流 → 分数回到白送 20 分。

## 6. 读数会变差（必须写进验收口径，否则会被误判为回归）（serves: FR-4）

| 读数 | 方向 | 原因 |
|---|---|---|
| `data_quality_score` | **下降** | 异常率分量第一次有依据（此前恒 20 分白送） |
| `stocks_with_issues` | **上升** | 多出"有异常"与"检测失败（待查）"两类 |
| `检测异常值失败` 日志 | **归零** | 迭代修好（今日基线 7995 条/4 分钟） |

**验收必须先接受这条前提**：这三项不是回归，是**读数从假变真**。
历史质量分与"有问题的股票"清单需要按此重新解读（需求「后续线」4）。

## 7. 不做什么（防范围蔓延）（serves: FR-5）

1. 不扫全仓 10+ 处同型 `for kline in klines:`（E9）——只登记（后续线 1）。
2. 不改 `get_daily_klines` 返回类型、不引入 pandas/polars 适配层。
3. 不改 Z-score 算法、阈值、异常定义（不把异常当交易信号，R3）。
4. 不加日志限流/聚合、不加开关、不加表列。
5. 不动 task 232 的排班与 `policy=holidays`（属 a315 口径）。
6. 不修同批 294 条 `data_backfiller`「All data providers failed」（后续线 2）。
