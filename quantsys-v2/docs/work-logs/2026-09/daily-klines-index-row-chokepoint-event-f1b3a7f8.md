# daily_klines 指数行统一收口（看板事件 f1b3a7f8 / 585f5a3f 家族）

- 时间：2026-09-13｜窗口：w-32314d00（投资脑 investor）
- 家族：5 条事件、共 11 次撞约束（bc64397b / d0f549d1 / bbb56df6 / 585f5a3f / f1b3a7f8）

## 1. 为什么先修的还不够

上一轮只在 `DataProviderManager._backfill_klines_to_db` 加了 `is_index_symbol` 守卫，
覆盖的是**回填**这一条路径。但 `daily_klines` 的写入路径不止一条：

```
DataProviderManager._backfill_klines_to_db      → manager.py     （已修）
pipeline_exec.py:140        kline_repo.save_klines(...)          ← 未覆盖
data_backfiller.py:194      kline_repo.save_daily_klines(...)    ← 未覆盖
stock_async.py:327          ds.kline.save_daily_klines(...)      ← 未覆盖
```

三条未覆盖路径最终都汇聚到 `KlineORMRepository.batch_insert_daily_klines`。
逐条加守卫＝永远漏一条，因此改为在**汇聚点**收口。

## 2. 修复

1. 新增模块级 `filter_index_rows(klines)`（`kline_repository.py`）：
   先取唯一代码、再判 `is_index_symbol`（避免按行查 stocks 表放大查询），
   返回 (保留行, 被剔除代码列表)；
2. `batch_insert_daily_klines` 在**建 stocks 元数据之前**调用它：
   剔除指数行并打 warning，全部为指数行时直接返回 True（无事可做 ≠ 失败，调用方不必重试）。

## 3. 验证证据

1. 新增单测 `tests/adapters/test_daily_klines_index_row_filter.py` —— **4 passed**，
   含「全指数批次返回 True 且**不访问 session**」（用 property 打桩，访问即 AssertionError）；
2. 活体复现：`filter_index_rows([399001, 600519, 399300, 000300])`
   → kept=['600519']，dropped=['000300','399001','399300']，并打印跳过说明；
3. 全指数批次 `batch_insert_daily_klines([399001, 399300])` → True；
4. 重启 v2：**启动 14:44:50 > 文件 mtime 14:44:27**，`/health` ok；
5. **误删防线实测**（歧义码不能把真个股当指数删掉）：

```
000001 平安银行   is_index=False   ← 保留
000016 *ST康佳A   is_index=False   ← 保留
000905 厦门港务   is_index=False   ← 保留
000852 石化机械   is_index=False   ← 保留
000906 浙商中拓   is_index=False   ← 保留
000300/399300/399001              ← 剔除
```

## 4. 边界与残留

- `-k kline` 全量跑有 4 failed / 14 errors，均为**既有 API 漂移**（`'DataService' object has no
  attribute 'batch_get_klines'`、`'StrategyORMRepository' object has no attribute 'close'`、
  `module 'domain.quantlib.stages.data_pipeline' has no attribute 'factor_compute_stage'`），
  无一触及本次改动模块。
- **残留风险**：`is_index_symbol` 对白名单码依赖 `stocks.list_date` 定夺身份；若某只真个股
  的 stocks 行缺 list_date，会被误判为指数而剔除其 K 线。当前实测 5 个歧义真个股均正常保留，
  且剔除动作有 warning 日志（含代码清单）可回溯。若要彻底消除该风险，需把过滤条件收敛为
  「与 DB 约束完全等价的谓词」（399* 或 {000300,399300}）——本轮未做，登记为线索。

- 顺带核验：`quant.index_daily` 各指数最新日期 2026-09-11（8 个指数一致），指数数据不陈旧。
