# 按需 K 线补抓与因子现算（Agent 查不到数据修复）

- 执行：investor / w-0e4ae20d
- 日期：2026-10-28
- 目标：Agent 工具查询 K 线/因子时，本地缺失或落后不再直接返回空；单标的按需补 K 线并现算因子。

## 设计

新增 `adapters/shared/on_demand_market_data.py`：

```text
查询标的
 → 计算“最近已完成交易日”（15:00 前用上一交易日）
 → 查本地最新日期
 → 新鲜：直接返回 db_cache
 → 陈旧：抢该标的单飞锁
     → 再查一次（避免等待期间已被其他请求补齐）
     → 只抓缺失区间（最多 730 天）
     → 全局最多 2 个上游补抓并发
     → 列名归一化为 DailyKline 契约
     → 落库
 → 因子查询：K 线新鲜但因子落后 → 单标的现算并落库
 → 返回 source/as_of/fetched_bars/fresh/degraded/reason
```

约束：

- 单标的/最多 5 标的同步补数；批量 >5 跳过懒补，仍由晚间全市场管道负责。
- 单飞锁按 `kline:<symbol>` / `factor:<symbol>`，避免同一标的并发重复打源。
- 上游失败/空数据/抢锁超时返回 `degraded=true`，不伪造新鲜数据。
- 仅个股日线接懒补；指数表、分钟线不走该路径。
- 入口：`GET /api/stock/{symbol}/klines`、`GET /api/stock/{symbol}/factors`、`POST /api/compute/factors`（≤5标的）。

## 排查中修掉的真实契约缺陷

1. **同名方法覆盖**：`KlineORMRepository` 原有无参 `get_latest_trade_date()`（全市场最新日）。
   新增的 per-symbol 同名方法被类中后定义的方法覆盖，传 symbol 触发
   `TypeError: takes 1 positional argument but 2 were given`。
   修复：现有方法改为 `get_latest_trade_date(symbol=None)`，无参语义不变。
2. **数据源列名契约不一致**：Sina 返回 `日期/开盘/最高/最低/收盘/成交量`，akshare
   另有 `成交额/换手率`；仓储要求 `symbol/trade_date/...`。
   原逻辑虽抓到了数据，却在 `save_daily_klines` 抛 `KeyError: 'symbol'`，缓存失败。
   修复：在懒补边界做列名归一化（中英文列均支持），并补回归测试。

## 验证

- 单测 `tests/adapters/test_on_demand_market_data.py`：**9 passed**
  - 新鲜不抓、陈旧只抓缺口、空源降级、禁用降级、因子现算、列名归一化、方法签名冲突守卫。
- 生产实测 600036（本地 K 线和因子均停在 10/26）：
  - `data_fetch_kline`：5 条 → 6 条，末根 **2026-10-27**；
  - 接口 freshness：`source=lazy_fetch, fresh=true, as_of=2026-10-27`；
  - `factor_calculate`：返回 29 个因子，`source=lazy_compute`、`factor_ref_date=2026-10-27`、`stale_factors=[]`；
  - 数据库落库：600036 K 线 max=2026-10-27；因子 max=2026-10-27。
- 指数 000300 K 线仍走 index 表，未被误补进个股表。
- 因子 GET 返回 `data_freshness`，Agent 工具可直接看到刷新来源。

## 遗留边界

- 全市场 1796 只缺口不会被用户请求自动覆盖，仍需批量补跑/晚间管道；
- 单次补抓最多 730 天，且只补请求区间尾部；超长历史缺口不承诺同步修复；
- 外部源单次请求无显式超时控制，当前靠单飞锁与 2 个并发槽兜底；
- 批量因子接口 >5 标的跳过懒补，返回 `_skipped=batch_limit_exceeded`；
- 若外部源无当日 EOD，仍返回旧缓存 + `degraded`，需等源发布或晚间批处理。

## 提交

- `80ec716aa` 懒补服务与入口接入
- `3625db9f4` 最新日期方法冲突修复
- `0a0381005` 数据源列名归一化
