# REQ-261006133733-1fdf · 设计：测试策略与用例

**测试目标**：把「异常检测真的跑」与「失败不许冒充干净」两件事都变成**可证伪的断言**，
并证明第三件事：**读数变化是设计意图，不是回归**。

**新建用例文件（唯一）**：`tests/test_data_validator_anomaly_detection.py`
**打桩点规则**（本仓 CLAUDE.md）：改 `validator.kline_repo` / `service.validator` 用**实例属性替换**
（本仓既有做法），不 patch 符号来源模块；`KlineQualityRepository` 用构造注入或实例替换。

## 1. 用例矩阵（定死输入与期望）（serves: FR-1, FR-2, FR-4）

| 编号 | 用例 | 输入 | 期望（可断言的具体值） |
|---|---|---|---|
| T1 | 正常无异常 | 真 `pl.DataFrame` 40 行、价格/量平稳 | `ok is True`、`has_anomalies is False`、`unknown_reason is None`、`total_anomalies == 0` |
| T2 | 价格异常 | 40 行 + 最后一行 close 抬到 5σ 外 | `ok is True`、`has_anomalies is True`、`price_anomalies` 命中该日、`z_score > 3` |
| T3 | **成交量异常（本缺陷的直击点）** | 40 行 + 最后一行 volume 抬到 5σ 外 | `ok is True`、**`volume_anomalies` 非空**、`total_anomalies ≥ 1`（改前此例必抛错 → 红） |
| T4 | 数据不足 | 20 行 | `ok is True`、`has_anomalies is None`、`unknown_reason == 'insufficient_data'`、`message` 保留既有文案 |
| T5 | 检测失败 | repo 抛 `RuntimeError('boom')` | `ok is False`、`has_anomalies is None`、`unknown_reason` 含 `boom`、`error == unknown_reason`、**不抛** |
| T6 | 键集向后兼容 | 取 T1/T4/T5 三次返回 | 八键齐备（`ok/has_anomalies/unknown_reason/price_anomalies/volume_anomalies/total_anomalies/message/error`） |
| T7 | 质量分：真无异常 | 覆盖率/重复率固定 + T1 检测 | 异常率分量 = 20（总分含满分项） |
| T8 | 质量分：有异常 | 同上 + T2 检测 | 分量 = `max(0, 20 - rate*4)` 且 < 20 |
| T9 | 质量分：数据不足 | 同上 + T4 检测 | 走**重新归一**：`(coverage + dup)/80*100`（**不得**是"含 20 分"的旧值） |
| T10 | 质量分：检测失败 | 同上 + T5 检测 | 分量 = 0；且产生 error 留痕（断言日志被调用） |
| T11 | 消费点：失败计问题 | `check_quality_for_symbol` + T5 检测桩 | `has_issues is True`、条目含 `anomaly_unknown is True`、`anomaly_unknown_reason` 非空 |
| T12 | 消费点：数据不足不计问题 | 同上 + T4 检测桩 | `has_issues` 由 gap/dup 决定（**不因**数据不足为真）；汇总 `insufficient_history_count ≥ 1` |
| T13 | 汇总计数 | 跑 3 只（A/B/C 三态各一） | `anomaly_unknown_count == 1`、`insufficient_history_count == 1`、`stocks_with_issues` 含 C 不含 B |
| T14 | 审计留痕 | T2 + T5 各跑一次 `_record_quality_check` | T2 写 `type='anomaly'` warning（**改前为空转**）；T5 写 `type='anomaly_detection_unknown'` |
| T15 | 静态红线 | 读源码文本 | `application/services/*.py` 中 `has_anomalies` **无真值判断**（无 `if not …['has_anomalies']` / `if …['has_anomalies']:` 形式） |

**不做的用例**（防为凑覆盖率虚增）：不测 Z-score 数学本身；不测 `get_daily_klines`（属仓储层）；
不测 task 232 的排班与交易日门（属 a315）。

## 2. 反例锁（证明这些锁真能抓住原缺陷）（serves: FR-1, FR-5）

| 编号 | 在**改前**代码上应发生什么 |
|---|---|
| L1 | T3 红：`TypeError: cannot select elements using Sequence with elements of type 'str'` 被吞 → `has_anomalies is False`、`volume_anomalies == []` |
| L2 | T9/T10 红：三态分流不存在，数据不足与失败都走 `has_anomalies=False` → 分量恒 20 |
| L3 | T11/T13 红：失败不计问题、无 `anomaly_unknown*` 键 |
| L4 | T14 红：`anomalies` 键不存在 → warning 列表为空 |

**执行方式**：先写用例、在**未改动的代码**上跑一次（记录红），再改实现转绿——
红→绿的输出都进卡片汇报（这是"锁真能抓"的证据，不是流程装饰）。

## 3. 可跑命令与判定（serves: FR-1, FR-2, FR-3, FR-4, FR-5）

```bash
# 1) 新增用例（唯一入口）
./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q

# 2) 既有回归（不得有 1 条变红）
./venv/bin/python -m pytest tests/test_data_quality_job_guardrails.py -q

# 3) 复现（改前必错、改后必对）
./venv/bin/python -c "from application.services.data_quality_service import DataQualityService as D; \
print(D().validator.detect_anomalies('600519.SH','2026-07-01','2026-10-06'))"

# 4) 静态红线（T15）
grep -rn "has_anomalies" application/ adapters/ infrastructure/ | grep -v "is True\|is False\|is None\|'has_anomalies'\|has_anomalies=" || echo STATIC_OK

# 5) 失败日志不再出现（抽样窗口内）
grep -c "检测异常值失败" logs/api.log      # 复验窗口内的新增条数 = 0
```

## 4. 实跑复验（需求判定标准 5）（serves: FR-1, FR-5）

```bash
# 抽样 ≥20 只（真实库、真实 repo）
./venv/bin/python - <<'PY'
from application.services.data_quality_service import DataQualityService
svc = DataQualityService()
syms = [r[0] for r in svc.kline_repo.session.execute(
    __import__('sqlalchemy').text(
      "select symbol from quant.daily_klines group by symbol having count(*) >= 60 order by symbol limit 20")
).fetchall()]
rows = [svc.validator.detect_anomalies(s, '2026-07-01', '2026-10-06') for s in syms]
print('ok=False 数 =', sum(1 for r in rows if r['ok'] is False))
print('total_anomalies 分布 =', sorted(r['total_anomalies'] for r in rows))
PY
```

**判定**：`ok=False 数 == 0` 且 `total_anomalies` **不全为 0**（允许为 0 的样本存在，
但必须出现 >0 的样本，否则说明仍未真正生效）。
**证据形式**：命令 + 原始输出摘要写进卡片汇报与验收材料。

## 5. 读数变化的验收口径（防止把"变真"当回归）（serves: FR-4）

- 验收时**必须先接受**：`data_quality_score` 会下降、`stocks_with_issues` 会上升
  （架构 §6 已列方向与原因）。
- 判定"没坏"的方式不是"数字没变"，而是：
  ① 抽样 20 只 `ok=False == 0`；② `total_anomalies` 出现 >0；③ 既有回归用例全绿；
  ④ 质量分的三个分量可在用例里分别复算（T7–T10）。
