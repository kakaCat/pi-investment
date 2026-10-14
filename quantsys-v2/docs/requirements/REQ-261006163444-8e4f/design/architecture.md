# REQ-261006163444-8e4f · 设计：架构

## 1. 缺陷定位（三处口径缺陷，一处审计列取错键）（serves: FR-1, FR-2, FR-4）

```
每日数据质量检查（task 232, infrastructure/jobs/data_quality_check_job.py）
  ├─ :184  service.check_data_quality(...)          # 全库 5686 只，明细被 [:50] 截断（:270）
  ├─ :218  _release_db_session("回填前")
  ├─ :229  auto_backfill → targets = symbols_with_issues[:limit]   ❌ 缺陷 3：样本来自被截断的明细
  │          └─ :243  sort(key=missing_days_count, reverse=True)   ❌ 缺失最多的=退市股 → 排最前
  └─ :346  _check_quality_alerts(result, quality_threshold)
             ├─ :407  count_by_grade_on('D')      ❌ 缺陷 1：按 created_at 日期数**行数**，同日多跑即翻倍
             ├─ :420  backfill_fail_rate = failed/total   ❌ 缺陷 2：分母 = 上面那批无效目标
             └─ :425/:432/:439  阈值 500 / 95.0 / 50%     ❌ 缺陷 4：分母含死标的，95.0 高于口径上限
             └─ :619  original_count=gap_info.get('expected_days', 0)  ❌ 缺陷 5：键不存在 → 恒 0
```

| # | 缺陷 | 现语义 | 证据 |
|---|---|---|---|
| 1 | 计数按行不按标的 | `count_by_grade_on` = `count(id) where date(created_at)=today` | 今日 806 行 / distinct 404；单次各 403（E3/E4） |
| 2 | 统计分母含死标的 | 检查域 = `daily_klines` 全部 distinct symbol（5686） | 域内 90.84 / 全库 86.28；覆盖 98.54% / 91.70%（E5/E7） |
| 3 | 回填样本取自截断明细 + 按缺失天数降序 | `stocks_with_issues[:50]` 中"有缺失天"者，按缺失天数降序 | 7 只目标里 5 只已退市（E10/E14） |
| 4 | 阈值与口径错配 | D级>500 / 评分<95.0 | 评分上限 `0.6×覆盖率+40` = 95.02（E8） |
| 5 | 审计列取错键 | `expected_days`（不存在） | 真实键 `total_trading_days`（E11） |

**由此得出两条设计纪律**：

> **纪律 A**：告警指标的"分母"必须是**可交易域**，且**分母口径变更必须同步重定阈值**。
> **纪律 B**：从"被截断的展示明细"里取样本做统计或动作，一律视为缺陷——统计要用全量事实。

## 2. 分域模型（本设计的中心）（serves: FR-1, FR-3）

```
                     quant.daily_klines
                            |
                 D_last = max(trade_date)          <- 数据事实，不依赖 is_delisted/is_suspended
                            |
        +-------------------+-------------------+
        |                   |                   |
   gap == 0 日          gap 1..4 日         gap >= 5 日
        v                   v                   v
   可交易域 tradable     观察中 observing      存量 stock
   (5280 只)            (3 只)              (403 只)
        |                   |                   |
   三项告警只看这里      dropped_new 名单    不告警、不占配额
                       进告警正文(warning)   仅在正文里报数
```

- **`gap` 定义**：某标的**最后一个有 K 线的交易日**，到 `D_last` 之间隔了几个交易日（`D_last` 本身计 1）。
  由 `daily_klines` 的 distinct `trade_date` 降序排名 + 每标的 `max(trade_date)` 现算，**零新增状态**。
- **为什么用数据事实而不是标记**（D-3）：`is_delisted`/`is_suspended` 只覆盖死标的的 46%（161/351），
  且 55 只停更标的**全部未标**（E6）——标记不足以定义域；而"末日有无 K 线"零污染、覆盖 100%。
- **`dropped_new` 定义**：`gap == 1` 的标的 = 上一交易日在域、本交易日不在。这正是"当天掉队"的集合，
  含两种情况：**真停牌**（约 2 只/日，E12）与**采集漏批**（整批出现）。二者在设计上不需要区分——
  都是"值得看一眼"的事实，由人判断（D-4）。
- **为什么不做状态持久化**：`gap` 由 `daily_klines` 现算，因此"上期在域"不需要存快照——
  上一交易日就是 `trade_dates_desc[1]`。⇒ **零迁移、零新表**（若有需要见「升级信号」）。

### 2.1 存量与观察中的转档（serves: FR-3）

- `gap ∈ [1,4]` ⇒ 观察中，**每次**都进告警正文的"本期掉出"名单（warning 级）；
- `gap ≥ 5` ⇒ 存量，**只在正文里报一个数**（+ 抽样名单），不再逐日重复点名。
- 因此"新掉出"天然只亮相 4 天 → 之后自动安静；**不需要**额外的"已通知过"状态。

## 3. 告警口径：三个指标的分母（serves: FR-2, FR-4）

| 告警项 | 旧分母 | 新分母 | 新阈值 | 备注 |
|---|---|---|---|---|
| D级股票数量过多 | 当日**行数** | 可交易域内 **distinct 标的**（来自本次 run 的 per-symbol 记录） | > 20 只 | 今日域内真值 3 只 |
| 数据质量评分偏低 | 全库 5686 只均值 | 可交易域内均值 | < 88.0 | 今日域内 90.84 |
| 回填失败率过高 | 被截断明细里"有缺失天"的 7 只 | 可交易域内目标，且**分母 ≥ 10 才判** | > 50% | 今日基线 5/7 |
| 平均覆盖率 | 全库 | 可交易域内 | 仅信息项（97.0 只标色不告警） | 今日域内 98.54% |
| **本期掉出可交易域** | ——（新增） | `gap == 1` 的标的 | > 0 即 warning（不是 error） | 今日基线 2 只 |

- **统计口径改为全量事实**：三个指标一律基于 `check_data_quality` 返回的 **per-symbol 记录**
  （5686 条，本 run 现算），不再读 `kline_data_quality` 表、不再受 `stocks_with_issues[:50]` 影响（纪律 B）。
  ⇒ `count_by_grade_on` 退出主路径，但仍**修对语义**（FR-2 ②），因为它是对外可复算的取证口径。
- **阈值可变性**：`quality_threshold`（既有 param）继续生效，缺省由 90.0 改为 **88.0**；
  新增 param `d_grade_threshold`（缺省 20）、`coverage_info_threshold`（缺省 97.0）。
  task 232 现有 params 里 `quality_threshold: 95.0` 必须同步改为 `88.0`（见 data-model.md §5）。

## 4. 文件结构（新建 / 修改 / 不改，各自职责一句话）（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

| 动作 | 文件 | 职责一句话 |
|---|---|---|
| **新建** | `application/services/kline_domain.py` | 纯函数分域：`classify_domain()` / `build_domain_snapshot()` / `DomainSnapshot`；**不碰 DB**（读由仓储给） |
| **新建** | `tests/test_kline_domain.py` | 分域判据的纯函数用例（含 gap=0/1/4/5 边界、无 prev、空表退化） |
| **新建** | `tests/test_data_quality_alert_scope.py` | 告警口径用例：distinct 计数、域内阈值分支、掉出名单、回填样本门槛、`original_count` |
| **修改** | `adapters/outbound/repositories/kline_repository.py` | `KlineORMRepository` 新增两个只读方法（交易日倒序、每标的最后交易日）——`daily_klines` 的归属方 |
| **修改** | `adapters/outbound/repositories/kline_quality_repository.py` | `count_by_grade_on` 改 distinct 语义 + 可选 `symbols` 限定 |
| **修改** | `application/services/data_quality_service.py` | `check_data_quality` 返回 `per_symbol`（全量、含 grade/coverage/quality_score/missing_days_count）；`_persist_quality_audit` 修 `original_count` 取键；grade 只算一次 |
| **修改** | `infrastructure/jobs/data_quality_check_job.py` | 建快照 → 域内聚合 → 新告警判据 → 回填目标只在域内选 → 结果新增 `domain`/`domain_dropped`/`alert_scope` |
| **不改** | `application/services/data_validator.py` | 评分公式、Z-score 阈值、等级分数线属 REQ-261006133733-1fdf 与后续线 3 |
| **不改** | `application/services/data_gap_detector.py` | 缺口检测（`total_trading_days` / `avg_coverage_rate`）语义不变，只是消费者换了 |
| **不改** | 表结构 / 迁移 | 零 schema 变更（见 data-model.md §1） |
| **删除** | —— | 无 |

## 5. 回滚与灰度（serves: FR-2, FR-4）

- **零迁移、零开关**：纯代码 + 一条配置行 UPDATE。回滚 = 还原提交 + 把 `quality_threshold` 改回 95.0。
- **可部分回滚**：① 只回滚告警口径 → 回到"死标的入域 + 同日多跑翻倍"的旧红；② 只回滚回填限域 →
  回到"额度被退市股吃掉、374 条无效 `All data providers failed`"。
- **灰度不需要**：告警是旁路，不影响数据管道与交易链路；判错只影响一条飞书卡片的红/绿。
- **首次上线后的必做动作**：阈值为临时锚定值（E13 只有 2 次全市场运行），须按 FR-4 ③ 在累计
  ≥10 个交易日后用域内实测分布重新标定一次。

## 6. 读数会变（必须写进验收口径，否则会被误判成"漏报"）（serves: FR-2）

| 读数 | 方向 | 原因 |
|---|---|---|
| D级告警 | **从红转绿**（806 → 域内 3） | 去掉死标的与重复计数 |
| 评分告警 | **从红转绿**（86.28 → 90.84） | 分母改为可交易域 |
| 回填失败率 | **消失或大幅下降**（71.4% → 域内且 n≥10 才判） | 目标不再含退市股 |
| 告警正文 | **多了三段**（检查域计数 / 掉出名单 / 覆盖率信息项） | 新口径的可核验性 |
| 告警条数 | 健康日 **1 项**（掉出域，warning） | 掉出域是常态化哨兵，不是故障 |

**验收必须先接受这条前提**：前三项不是"漏报"，是**从假红变真绿**。

## 7. 不做什么（防范围蔓延）（serves: FR-3, FR-5）

1. 不补 239 只标的的 `is_delisted`/`is_suspended` 标记（D-4 的 B 选项，后续线 1）——
   本设计用 `dropped_new` 哨兵替代"靠标记定义域"。
2. 不改评分公式、异常 Z-score 阈值、等级分数线（后续线 3）。
3. 不改检查窗口（`MAX_CHECK_DAYS=90`）、排班（`0 0 * * *`）、`policy=holidays`。
4. 不回填历史 `kline_data_quality` 行的 `original_count`。
5. 不新增告警渠道、不加限流、不加开关。
6. 不动服务层 `stocks_with_issues[:50]` 截断本身（它是展示上限）；只把统计与回填与它**解耦**。

## 8. 已知盲区（本设计覆盖不到，必须显式登记）（serves: FR-3）

- **整个采集管道停摆**：此时 `D_last` 本身滞后（例如仍停在 09-30），分域快照会认为"大家都正常"，
  `dropped_new` 为空 ⇒ 本设计的哨兵**测不到这一类事故**。
  责任方是既有 `freshness_guard`（`docs/architecture/trading-day-freshness.md`），
  本需求**不重复建设**，只要求在告警正文里打印 `D_last`（人一眼能看出它是不是当前交易日）。
- **新股/次新股**：上市不足 5 个交易日者会落进"观察中"，属误报；正文里靠"名单 + 上市日"
  人工辨认，不在本需求加规则（加规则要引入 `list_date` 依赖，属范围外）。
- **BSE（920xxx）等跨市场代码**：分域只用 `daily_klines` 事实，与交易所无关，天然兼容（E5 已含 920685）。
