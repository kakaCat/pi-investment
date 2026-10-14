---
req_id: REQ-261004102115-d3de
title: 应有交易日的落点、解析链与回滚
doc: design/architecture
serves: FR-1, FR-2, FR-3
---

# 架构设计（REQ-261004102115-d3de）

**前提**：本需求**不改运行时架构**——不新增服务、不新增表、不改探针的"不依赖被监控进程"硬约束，
只把"哪天该有数据"这一个判断从"猜周一至周五"换成"查交易日历"。

## 目标与判定（serves: FR-1, FR-2, FR-3）

**目标**：探针与进程内 `freshness_guard` 对"应有交易日"给出**同一个、节假日感知的**答案。

可证伪判定：

1. `./venv/bin/python tools/health_probe.py --dry-run` → `"healthy": true`、`expected=2026-09-30`、
   `expected_source=calendar`，退出码 `0`；
2. `./venv/bin/python tools/health_probe.py --dry-run --max-lag-days -1` → 仍判异常、退出码 `2`；
3. `./venv/bin/python -m pytest tests/test_trading_day_resolver.py tests/test_health_probe.py -q` → 全过。

## 落点与依赖方向（serves: FR-1, FR-2, FR-3）

新增**一个**模块：`application/services/trading_day_resolver.py`（application 层，纯逻辑 + 两个只读端口）。

| 调用方 | 现状 | 改成 |
|---|---|---|
| `tools/health_probe.py:63-85` `expected_trading_day()` | 复用 `_last_trading_day` | 调 `last_closed_trading_day()`，把 `source` 带进报告 |
| `adapters/inbound/fastapi_app/daily_jobs/pipeline.py:76`（evening 同步基准日） | `_last_trading_day(now)` | 同上 |
| `adapters/inbound/fastapi_app/daily_jobs/pipeline.py:177`（freshness_guard） | `_last_trading_day(now-1d)` | 同上（**注意次日基准的既有语义：改用 `ref=now-1d` 传入，语义不变**） |

依赖方向合法：`tools/` 与 `adapters/inbound/` → `application/`，无反向依赖，无环。
`daily_jobs_bootstrap` 的转发导出（`_last_trading_day`）**保留**（44 个模块的导入路径不动），
内部改为调用 resolver——见 `interfaces.md` 的兼容段。

## 解析链（serves: FR-1）

```
last_closed_trading_day(ref)
  │  anchor = ref.date() if ref.time() >= 15:30 else ref.date() - 1 天
  ├─ ① quant.trading_calendar 表（离线、快）  ── 需覆盖 anchor（max(trade_date) >= anchor）
  ├─ ② DataProviderManager.get_trading_calendar（AKShare，含未来交易日）
  └─ ③ 周一~周五回退（= 现有行为，且 source 明确标为 weekday_fallback）
  返回 {date, source, degraded}
```

- 任一级失败**不抛异常**，降级到下一级并记一条 warning；三级全失败才回退到"上一工作日"。
- `source` 必须一路带到调用方（探针进 JSON 与告警正文，守卫进 result）。

## 为什么 ② 不能被省掉（serves: FR-1）

`quant.trading_calendar` **当前 0 行**，且它的唯一刷新脚本 `tools/refresh_trading_calendar.py`
是从 `daily_klines` 的 `DISTINCT trade_date` 灌的——**K 线里天然没有未来交易日**，
所以"只读表"会在表刚填好就立刻过期。②用 AKShare 的官方日历（实测已含 2026-10-08/09/12 等未来日期），
是让①②互补而不是互相重复：表管快，provider 管新。

## 已知并存的第三个口径（serves: FR-1）

`tools/check_data_contracts.py:239-261` 的 `compute_expected_trading_day()` **已是同一语义的既有实现**
（日历表优先、空表降级周一至周五 + `holiday_slack_weekdays` 冗余）。

**本次不合并**，理由（不是遗漏，是取舍）：

1. 它自带 `calendar_available` 这个**双向**信号（表可用时按交易日计数、不可用时按工作日 + 节假日冗余），
   与探针"单一 expected + lag"的形状不同，合并会牵动另一个工具的判定面与测试面；
2. 它已正确避开本次的坑（实测它在 10-02 给的是"工作日口径 + 3 天冗余"，故没报错），
   不属于"正在误报"的那条路径。

**登记为后续收敛项**：三个口径（resolver / check_data_contracts / data_contracts 配置）最终应收成一个，
但不塞进本次——这正是需求文档里"出现第二个未定决策即升级重档"的边界。

## 探针的硬约束如何保持（serves: FR-2）

- 不 import FastAPI 应用、不依赖 5001 进程存活（探针只新增 `application` 层的纯函数依赖）；
- 新增依赖只有"读一个表 + 调一次已有 provider"；**不新增第三方库**；
- 失败仍然按原语义分流：被监控对象异常 → exit `2`；探针自身配置/依赖错误 → exit `3`。
  **日历源不可用不算探针自身错误**（→ 降级 + 标注，不返回 3）。

## 回滚路径（serves: FR-1, FR-2, FR-3）

- 代码：单 commit 可整体 revert，回滚后行为＝现状（周一至周五口径）；
- 数据：本需求**只读**现有表、不写入任何生产数据（表回填由既有脚本人工执行，见 `data-model.md`）；
- 配置：`deployment/launchd/com.pi-investment.health-probe.plist` **不改**（参数与周期保持）。
