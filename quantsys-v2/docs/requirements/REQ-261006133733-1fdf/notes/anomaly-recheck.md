# 异常检测复验（REQ-261006133733-1fdf · t4）

**复验目的**：证明修好后 ① 异常检测**真的产出结论**、② 报错不再发生、③ 读数变化是设计意图。
**自律**：单测与实跑分开写；没取到的窗口就写「未取到」+ 原因，不用单测顶替。

---

## 0. 一个必须先说的口径坑（否则证据是假的）

`logs/api.log` 里**中文被写成 `\uXXXX` 转义**（structlog JSON 序列化）。因此：

```bash
grep -c "检测异常值失败" logs/api.log     # ❌ 恒为 0 —— 假绿！中文模式根本匹配不到
```

**正确口径**（本文件全部用它）：

```bash
./venv/bin/python - <<'PY'
import json, collections
c = collections.Counter()
for line in open('logs/api.log', encoding='utf-8', errors='replace'):
    line = line.strip()
    if not line.startswith('{'): continue
    try: o = json.loads(line)
    except Exception: continue
    if '检测异常值失败' in str(o.get('event', '')):
        c[str(o.get('timestamp',''))[:16]] += 1
print('总条数 =', sum(c.values()), '| 按分钟 =', dict(sorted(c.items())))
PY
```

> 该坑也影响 design/test-cases.md §3 第 5 条与本卡原 acceptance 的写法；
> 已在本文件给出可用替代，**不改设计文档**（属验证口径的落地细节）。

---

## 1. 抽样实跑（≥20 只，真实库，新代码）

**命令**：

```bash
./venv/bin/python - <<'PY'
from sqlalchemy import text
from application.services.data_quality_service import DataQualityService
svc = DataQualityService()
syms = [r[0] for r in svc.kline_repo.session.execute(text(
    "select symbol from quant.daily_klines where trade_date >= '2026-07-01' "
    "group by symbol having count(*) >= 60 order by symbol limit 20")).fetchall()]
rows = [(s, svc.validator.detect_anomalies(s, '2026-07-01', '2026-10-06')) for s in syms]
print('ok=False 数 =', sum(1 for _, r in rows if r['ok'] is False))
print('分布 =', sorted(r['total_anomalies'] for _, r in rows))
PY
```

**原始输出摘要（2026-10-06 13:47 实测）**：

```
样本数 = 20 | 前 3 只 = ['000001', '000002', '000006']
ok=False 数 = 0 []
total_anomalies 分布 = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 4, 4]
有异常样本数 = 19 / 20
来源标注（unknown_reason 集合）= []
```

**判读（三条都满足）**：
1. `ok=False` = **0**（改前：每只必失败）；
2. `total_anomalies` **不恒为 0**——19/20 报出 1~4 个异常（改前：恒 0）；
3. `unknown_reason` 集合为空 ⇒ 没有"未知"混在结果里。

> 对照：改前同口径下这 20 只每一只都会走 `except`，返回 `has_anomalies=False / total_anomalies=0`
> ——即「全市场异常检测零产出」。

---

## 2. 报错窗口（改前风暴 vs 改后静默）

**原始输出摘要（2026-10-06 13:47 实测）**：

```
总条数 = 7995
  2026-10-06T00:01  789
  2026-10-06T00:02 4392
  2026-10-06T00:03 2814
```

**判读**：
- 7995 条**全部**落在 `00:01–00:03`（task 232 当天的运行窗口，旧代码）；
- 改后时段（13:21 起）**新增 0 条**（同一扫描口径）。

**必须同时说明的一件事（否则读者会误以为已彻底解决）**：
> 运行中的服务进程启动于 **13:21:33**，而 `data_validator.py` 的修复时间戳是 **13:46**
> ⇒ **进程内存里仍是旧代码**。今晚 `00:00` 的 task 232 若不重启服务，会**再次刷出 7995 条**。
> 即"改后 0 条"目前只证明**新代码不再产生**，还**没有**证明**线上不再产生**（见 §4）。

---

## 3. 读数变化对照（架构 §6：这是变真，不是回归）

| 读数 | 方向 | 本次复验的支撑 |
|---|---|---|
| 异常率分量（质量分的 20 分） | **不再恒满分** | 19/20 样本报出异常 ⇒ 该项第一次有扣分依据（样本 1~4 个异常 ≈ 2.5%~10% 异常率 ⇒ 分量 10~0 分） |
| `stocks_with_issues` | **上升** | 19/20 有异常 ⇒ 只靠异常也该进问题清单（改前它们是"干净"） |
| `data_quality_score` | **下降** | 由上一行直接推出：今日 `95.01` 里原本含白送的 20 分 |
| `检测异常值失败` 日志 | **归零（新代码口径）** | §2：改后时段新增 0 条 |
| `anomaly_unknown_count` | 新增可见 | 失败才计数；本次样本 0（无失败） |
| `insufficient_history_count` | 新增可见 | 本次样本 K 线 ≥60 行，故 0 |

**验收前提（必须接受）**：上表前三行是**读数从假变真**，不是回归。
历史质量分与"有问题的股票"清单需按此重新解读（需求「后续线」4）。

---

## 4. 完整复验（用户批准：重启 + 手动触发一次 task 232）✅

**动作**（2026-10-06）：
1. `13:48:28` `launchctl kickstart -k gui/501/com.pi-investment.v2-api` → 新 PID **99249**，`/health` = ok
   （上一次重启 `13:21:33` 只带上了交易日门修复，**不含**本次 data_validator 修复）；
2. `13:48:28` `POST /api/scheduler/tasks/232/trigger` → `{"success":true,"message":"Task 232 dispatched asynchronously"}`。

**整跑结果（run id 3382，`quant.scheduler_runs`）**：

```
status = success | 13:48:51.210811 → 13:54:22.238932 | duration_ms = 331028（≈5.5 分钟）
```

**当次 `check_summary`（原文，节选）**：

```json
{
    "total_stocks": 5686,
    "checked_stocks": 5686,
    "skipped_stocks": 0,
    "check_truncated": false,
    "avg_coverage_rate": 91.7,
    "data_quality_score": 86.28,
    "stocks_with_issues": 4623,
    "total_missing_days": 28309,
    "anomaly_unknown_count": 0,
    "insufficient_history_count": 402
}
```

**三项预测逐一命中（与今日 00:00 的旧代码基线对照）**：

| 读数 | 00:00 基线（旧代码） | 13:48 复跑（新代码） | 方向 | 判读 |
|---|---|---|---|---|
| `检测异常值失败` 新增条数 | **7995**（00:01–00:03） | **0** | ↓ | 迭代修好，风暴消失 |
| `data_quality_score` | **95.01** | **86.28** | ↓ 8.73 | 异常率分量第一次有依据（不再是白送的 20 分） |
| `stocks_with_issues` | **748** | **4623** | ↑ | 多出"仅异常"那一类股票（改前它们被记成干净） |
| `anomaly_unknown_count` | 键不存在 | **0** | 新增 | 无失败（"新键已落台账"与 0 同时成立） |
| `insufficient_history_count` | 键不存在 | **402** | 新增 | 402 只因历史不足而"没得判"——不再混进"干净" |

**这与 design/architecture.md §6 的预测完全一致**：读数不是坏了，是从假变真。

**一个必须响着报的副作用（本次复验新发现，超出原预测）**：
`Z-score > 3` 的既有阈值把 **4623/5686（81%）** 的股票判为"有异常"——它把除权、长停复牌、
真实异动等一并算进来（需求 R3 已预判"异常的业务价值有限"）。改前那份"748 只有问题"之所以好看，
一半原因是这一路信号恒为 0。**阈值是否需要重定属另一项决定**（本需求边界明确不改算法），
但"81% 有异常"本身会削弱质量门禁的可用性，必须在验收时被看见，不能被"修好了"盖过去。

---

## 5. 未取到的窗口（如实登记）

| 窗口 | 状态 | 说明 |
|---|---|---|
| task 232 用新代码的整跑 | ✅ **已取到** | §4（run 3382，success） |
| 质量分 / 问题清单的真实变化量 | ✅ **已取到** | §4 对照表 |
| 「历史读数重解读」的后续处置 | ⏳ 未做 | 属需求「后续线」4；本次只登记方向与量级 |

**复跑清单（若需再次取证）**：

```bash
# ① 触发一次数据质量检查（或等 00:00 自然运行），随后用 §0 的 Python 口径统计：
#    "检测异常值失败" 条数 → 期望 0
# ② 读当次 check_summary，期望含 anomaly_unknown_count / insufficient_history_count 两键
psql -h 127.0.0.1 -U mac -d quant_investment -At -c \
  "select jsonb_pretty(result->'details'->'details'->'check_summary') from quant.scheduler_runs \
   where task_id=232 order by started_at desc limit 1"
# ③ 对照 00:00 基线：data_quality_score 应下降、stocks_with_issues 应上升（§4）
```

**纪律**：未取到就继续标「未取到」，不得改用例通过当观察结论。
