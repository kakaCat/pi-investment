# REQ-261006163444-8e4f · 测试证据

所有命令在仓根执行，Python 用 `./venv/bin/python`。

## 1. 用例全绿（本次交付前最后一次新鲜运行）

```
$ ./venv/bin/python -m pytest tests/test_kline_domain.py tests/test_data_quality_alert_scope.py \
      tests/test_data_quality_job_guardrails.py tests/test_data_validator_anomaly_detection.py -q
✓ Test database validated: quant_test
collected 59 items
notify-guard intercepted=0 egress=0 offenders=[]
============================== 59 passed in 1.05s ==============================
```

| 文件 | 条数 | 覆盖 |
|---|---|---|
| `tests/test_kline_domain.py` | 14 | 设计 T1–T7、契约用例、**集成回归锁**（build 必须取够 5 个交易日） |
| `tests/test_data_quality_alert_scope.py` | 12 | 设计 T8–T17 + 反例锁 L1（同日两行不翻倍）、L2（旧口径必误报） |
| `tests/test_data_quality_job_guardrails.py` | 17 | 既有护栏（替身已补 `per_symbol` 与 `kline_repo`，4 处告警调用改新签名） |
| `tests/test_data_validator_anomaly_detection.py` | 16 | 既有（REQ-261006133733-1fdf），确认新增返回键不影响旧消费者 |

## 2. 分域判据复算（代码 与 SQL 互证）

```
$ ./venv/bin/python -c "from application.services.kline_domain import build_domain_snapshot; \
    from adapters.outbound.repositories.kline_repository import KlineORMRepository; \
    s=build_domain_snapshot(KlineORMRepository()); \
    print(len(s.tradable), len(s.observing), len(s.stock), sorted(s.dropped_new))"
5280 3 403 ['002813', '603183']
```

```sql
-- SQL 侧独立复算（同一口径）
with r as (select trade_date, row_number() over (order by trade_date desc) rn
           from (select distinct trade_date from quant.daily_klines) t),
     m as (select symbol, max(trade_date) mx from quant.daily_klines group by 1),
     g as (select m.symbol, coalesce(min(r.rn)-1, 9999) gap from m left join r on r.trade_date=m.mx group by m.symbol)
select case when gap=0 then 'tradable' when gap<=4 then 'observing' else 'stock' end k, count(*)
from g group by 1 order by 1;
--  tradable | 5280
--  observing|    3
--  stock    |  403
```

## 3. 计数去重的现场证据（本需求的第一性证据）

```
$ psql -d quant_investment -tc "select count(*) || ' rows / ' || count(distinct symbol) || ' syms' \
    from public.kline_data_quality where created_at::date=current_date and grade='D';"
1207 rows / 404 syms
```

当天共跑了 3 次全市场检查（00:00 自动、13:48 手动、16:51 本次复验），
**行数 1207 / 标的 404**——这正是"按行计数"会翻倍三倍的原因。
修复前 13:54 那条告警报的是 806（两次运行的 403×2），按 distinct 只有 404，
且单次运行本就不越 500 阈值。

## 4. 审计列与回填

```
$ psql -d quant_investment -c "select symbol, original_count, cleaned_count, grade from public.kline_data_quality order by created_at desc limit 4;"
 symbol | original_count | cleaned_count | grade
--------+----------------+---------------+-------
 920895 |             60 |            46 | C
 920167 |             60 |            46 | C
 920651 |             60 |            46 | C
 920378 |             60 |            46 | C
```

`original_count = 60`（窗口交易日数）；修复前该列取的是不存在的键 `expected_days`，**恒为 0**。

## 5. 全市场实跑复验（2026-10-06 16:51–16:53，5686 只）

```
ALERT_SCOPE tradable
DOMAIN {"last_trade_date": "2026-09-30", "prev_trade_date": "2026-09-29", "tradable_count": 5280,
        "observing_count": 3, "stock_count": 403, "stats_symbols": 5280, "partial": false, "degraded": false}
DROPPED {"count": 2, "symbols": ["002813", "603183"], "truncated": false, "known": true, "reason": null}
THRESHOLDS {"d_grade": 20, "score": 88.0, "coverage_info": 97.0, "backfill_fail_rate": 50.0, "backfill_min_sample": 10}
BACKFILL {"total_stocks": 50, "success_count": 0, "failed_count": 50, "total_days_filled": 0, "elapsed_time": 23.63}
PER_SYMBOL_IN_RESULT False
```

告警正文（日志 `data_quality_alert` 段，节选）：

```
📊 数据质量告警（3 项）
时间: 2026-10-06 16:53:50
口径: 可交易域（最后交易日 2026-09-30）｜统计 5280/5280 只
检查域:
  可交易 5280 ｜ 观察中 3 ｜ 存量 403
本期掉出可交易域: 2 只
  002813、603183
域内指标:
  评分 90.87（阈值 88.0）
  平均覆盖率 98.58%（信息项，阈值 97.0）
  D级 1 只（阈值 20）
```

**判定**：旧两条误报（D级 806 过多 / 评分 86.28 偏低）**不再出现**；正文三段齐。

**未通过的一项**：`All data providers failed` 150 条（回填 0/50）。
根因与后续线建议见 `notes/migration-rollback.md` 第七节与 `reviews/review.md` §3。

## 6. 任务覆盖标注（机器可解析）

> 每条 `covers:` 指向该任务/子卡的验收落点；证据即上文章节。

covers: t-839a64 — 分域纯函数模块落地，§2 复算 5280/3/403；§1 中 test_kline_domain.py 14 条
covers: t-721a23 — 研发段：模块落盘并实测（frozen、无 DB 依赖、gap 边界）
covers: t-b0347e — 联调段：接口签名与失败路径契约核对（鸭子类型入参）
covers: t-225332 — 复核段：对照设计 interfaces §1 无偏离
covers: t-a0b465 — 测试段：13→14 条用例全绿（§1）

covers: t-f2d177 — 仓储两方法与 distinct 计数，§3 计数去重实证
covers: t-0724f1 — 研发段：count_by_grade_on 改 distinct（404 而非 806）
covers: t-d8de1a — 联调段：两个只读方法被分域模块真实调用，§2 与 SQL 一致
covers: t-1aabe8 — 复核段：SQL 形态与 _safe_rollback 语义核对
covers: t-306059 — 测试段：§1 中 test_t15_L1_count_is_distinct_not_rows

covers: t-baed9f — 服务层 per_symbol 与 original_count 取键，§4 审计列 0 → 60
covers: t-2c8a18 — 研发段：per_symbol 8 键与 grade 单点计算
covers: t-3b5da9 — 联调段：作业层真实消费 per_symbol（回填与统计）
covers: t-acb9b3 — 复核段：对照 design/data-model §6 无偏离
covers: t-097096 — 测试段：§1 中 test_t14_original_count_key

covers: t-6e752d — 作业层接线，§5 全市场实跑字段与正文
covers: t-e5556c — 研发段：四个阈值键、快照、回填限域、新签名、降级分支
covers: t-3fe312 — 联调段：真库端到端小样本实跑；抓出并修正交易日取数不足
covers: t-e8d8e3 — 复核段：对照 design/interfaces §4/§5 无偏离
covers: t-cba0af — 测试段：§1 中 test_data_quality_alert_scope.py 12 条与既有护栏 17 条

covers: t-588941 — 分域用例卡，§1 test_kline_domain.py
covers: t-eb3ca1 — 研发段：14 条用例落盘
covers: t-21bcc0 — 复核段：用例与设计 T1-T7 逐条对齐
covers: t-0da0b9 — 测试段：pytest 14 passed

covers: t-ddb59a — 告警口径用例卡，§1 test_data_quality_alert_scope.py
covers: t-8138f0 — 研发段：12 条 + L1/L2 反例锁 + 既有替身适配
covers: t-f7a18c — 复核段：T8-T17 逐条有落点；L3/L4 有效性评级见 reviews/review.md §4
covers: t-37d890 — 测试段：四文件 59 passed

covers: t-a300ce — 阈值配置变更与实跑复验，§5 全市场实跑
covers: t-067110 — 研发段：配置 95.0 → 88.0 并采集四份证据
covers: t-6253e3 — 联调段：实跑输出与 run 结果字段逐项一致
covers: t-0607de — 复核段：四项验收逐条裁决（3 过 1 不过）
covers: t-7a9c7e — 测试段：回归 59 passed，实跑无测试外发

covers: t-3faf17 — 迁移/兼容/回滚清单，notes/migration-rollback.md
covers: t-5cd45f — 研发段：七节清单落盘（含第七节实跑复验与新发现）
covers: t-a331d8 — 复核段：清单与 design/data-model §1/§5 对照一致
