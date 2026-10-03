# 诊断检查器使用指南（本项目自带的 4 把"筛子"）

**目标读者**：在本仓排查"数据 / 契约 / 漂移"类问题的工程师
**来源**：`REQ-261001145152-3982`（V2 全面审查）产出并固化
**一句话**：**先跑筛子缩小范围，再动手改** —— 本次审查里最难的三个问题都不是通读代码找到的。

---

## 为什么要有这份指南

本项目排查排障时常犯的错是"**从症状直接跳到改代码**"。但有几类问题有**可复跑的判据**，
一条命令就能把候选缩到可手查的范围。四个检查器都是**只读**的，随时可跑。

| 检查器 | 回答什么问题 | 典型误判（没有它时） |
|---|---|---|
| `tools/check_scheduler_dedup.py` | 调度是不是真的只剩一套、有没有漏跑/重复 | "任务都在跑吧" → 实际有任务日日报错 |
| `tools/check_orm_drift_vs_production.py` | **生产库**缺不缺 ORM 声明的东西 | "测试全绿" → 生产缺表，接口必 500 |
| `tools/check_silent_fallbacks.py` | 哪些地方"失败"与"空数据/成功"**不可区分** | "日志里只是些 warning" → 功能其实恒空 |
| `tools/check_action_case_consistency.py` | 枚举列大小写是否统一、哪些比较会静默漏行 | "库里数据是干净的" → 混写导致漏行 |

---

## 1. 调度自检

```bash
cd quantsys-v2 && source activate-py313.sh
python tools/check_scheduler_dedup.py
```

判据三条：① cron 撞点 = 0；② 每 job 每日仅 1 条 **success**；③ `adapters/` 单一调度入口。
退出码 `0` 全过 / `2` 有判据未过 / `3` 检查器自身出错。

⚠️ ②里的「连续 **3 个交易日**」是**时间型**判据 —— 必须等真实交易日累积，
   **休市期（如国庆）会让窗口后移**。未达之前不要把它当通过，也不要为了变绿去改数据。

## 2. 生产方向的结构漂移

```bash
python tools/check_orm_drift_vs_production.py            # 只读，查生产
python tools/check_orm_drift_vs_production.py --strict   # 有漂移即退出码 2
```

**为什么需要它**：`tests/test_orm_db_drift.py` 只查一个方向 ——「模型声明、**测试库**没有」。
**生产库的反向漂移长期无人看守**，于是攒出 7 张「ORM 有模型、生产库没表」的对象，
其中两张直接造成线上故障（`POST /api/memory` 恒 500；每日 16:45 的 `event_calendar_check`
查询报错被吞 → 毒化会话 → 台账假失败）。

⚠️ **它刻意不进 pytest**：本仓有"测试禁止连生产库"的三层防护，把它塞进套件会破坏该设计。
⚠️ 它的输出是**模型驱动**的：报出的表可能只是"声明了但没人查"，
   **必须与"是否有代码在查它"一起判断**。

## 3. 静默兜底（失败与空数据不可区分）

```bash
python tools/check_silent_fallbacks.py            # 候选清单
python tools/check_silent_fallbacks.py --strict   # 有命中即退出码 2
```

判据：**当一个读/写的失败，与"空结果 / 成功"在返回值上无法区分、且不留 error 级痕迹时，
它就是隐患** —— 因为调用方会照常往下走。

实战例子（本仓真实发生）：`get_rule_trigger_stats()` 因无主触发（`rule_id` 为 NULL，
外键 `ON DELETE SET NULL` 造成）排在分组第一行 → `int(None)` 抛错被吞 →
**统计在生产恒返回空字典**；日志里只有 warning，极易被当成噪音。

⚠️ **命中 ≠ bug**：有合法的静默返回（例："账户不存在"与"算不出来"在调用方语义相同）。
   工具只把候选缩到**可手查的范围**，不是自动定罪。

## 4. 枚举大小写一致性

```bash
python tools/check_action_case_consistency.py
```

扫两件事：库里枚举列的大小写是否混写；代码里哪些 `action == '...'` 比较**会因大小写静默漏行**。

⚠️ **不能机械"一律 lower"**：本仓两张表契约**相反** ——
   `quant.trades` 受 CHECK 约束强制**小写**（那里的敏感比较是**对的**），
   `quant.simulation_trades` 强制**大写**。

---

## 用它们排障的推荐顺序

```
症状（接口为空/500、报表不对、任务没跑）
   ↓
① 该症状对应的筛子（上表）→ 拿到**候选清单**
   ↓
② 逐个"验声明"：对每个候选，用**生产数据**或**实际调用**确认真伪
   （本次审查靠这一步推翻了 3 个假设、也确认了 3 处端点其实健康）
   ↓
③ 只有确认是真问题才改代码；改完**把判据固化**（能写成筛子的就写成筛子）
```

**最后一条最重要**：本次审查里最值钱的产物不是某个 bug 修复，而是**把经验变成可重复的动作**。
下一个遇到同类问题的人，不必从零摸索。

---

## 附：本次审查沉淀的其它"可复跑"资产

| 资产 | 用途 |
|---|---|
| `infrastructure/persistence/migrations/20261002_create_missing_orm_tables.py` | 幂等补齐"模型有、库表无"的表（默认 dry-run，`--apply` 才执行） |
| `infrastructure/persistence/migrations/20261002_scheduler_tasks_missing_columns.py` | 补齐 `scheduler_tasks` 缺失列（APSchedulerService 加载不了任务的根因） |
| `docs/requirements/REQ-261001145152-3982/design/audit-report.md` | 本次审查的证据与因果链（§W 假失败链条、§X 追查与自查修正、§Y 被推翻的假设、§Z 基线对照） |
| `docs/requirements/REQ-261001145152-3982/design/optimization-backlog.md` | 按"可落卡"字段写的待办（含每条**为什么这次不做**） |
