# K 线回填写指数行撞约束（看板事件 585f5a3f）根因与修复

- 时间：2026-09-13｜窗口：w-32314d00（投资脑 investor）
- 事件：`Backfill klines to DB failed for 399001` · CheckViolation `chk_daily_klines_no_indexrows`
- 首次出现：2026-09-12 00:25（evening_pipeline 09-11 23:30 起跑的那一轮）

## 1. 现象

evening_pipeline 回填 399001（深证成指）时插入 `quant.daily_klines` 被 CHECK 约束拒绝：

```
chk_daily_klines_no_indexrows = CHECK ((symbol !~~ '399%') AND symbol <> ALL (ARRAY['000300','399300']))
Failing row contains (399001, 2026-07-13, 14908.98, ..., tencent, SZ)
```

该批 K 线整批回滚，任务在 15:56:08 失败（run 3660，error=connection already closed 的表象之外，
内核就是这次 CheckViolation）。

## 2. 根因（含对既有 note 的更正）

`DataProviderManager._backfill_klines_to_db`（`adapters/outbound/datasources/manager.py`）
**无条件**把网络取回的 K 线写入 `daily_klines`，只在 `infer_market()` 返回 None 时才跳过。
实测 `infer_market('399001') == 'A'`（6 位数字一律判 A 股），**因此指数码不会走跳过分支**，
而是 auto-create 一条 stocks 元数据后去 INSERT 指数行 → 撞约束。

> 更正：该事件在 14:27 首次闭环时的 note 曾写「分表后 backfiller 对指数走 skipped 分支」——
> 这句话**当时并不成立**（代码里没有这个分支）。本次补上了真正的守卫，才让它成为事实。

正确的分表设计（2026-09-11 w-f4aa1f6a）：指数价格存 `quant.index_daily`，键带市场后缀
（`399001.SZ`）；`daily_klines` 只放个股。HTTP 路由层已按此分流，但 bulk 回填路径绕过了路由层。

## 3. 修复

在 `_backfill_klines_to_db` 的 **建 stocks 元数据之前** 加守卫（放在最前，避免为指数造出假个股行）：

```python
from utils.symbol_classifier import is_index_symbol
if is_index_symbol(symbol):
    logger.info(f"Skip kline DB backfill for {symbol}: 指数行不入 daily_klines")
    return False
```

选择「跳过」而非「改写入 index_daily」：路由层已有 index_daily 分流，回填层再写一遍会造成双写；
且指数行的键格式（带后缀）与 daily_klines 契约不同，跨层改写风险大于收益。

## 4. 验证证据

1. 新增单测 `tests/adapters/test_backfill_klines_index_guard.py` —— **3 passed**
   （399 族识别 / 指数被跳过且不触库 / 真实个股不被误拦）；
2. 真实路径调用 `399001` / `399300` / `000300` 均返回 False 且未触库；
3. 重启 v2（14:41:39 启动 > 文件 mtime 14:41:17）→ `/health` ok；
4. 活体：`GET /api/stock/399001/klines` → HTTP 200、`resolved_kind=index`、
   `resolved_symbol=399001.SZ`，新增日志中「Backfill klines to DB failed」0 条。

## 5. 边界与残留

- `tests/adapters` 另有 3 个失败（`float() argument must be ... not 'Mock'`），
  属既有 mock 失配基线问题：这两个测试文件对我的改动模块**零引用**，与本次修复无关。
- 回填层跳过意味着指数 K 线不再进 `daily_klines`（本就该如此）；指数数据的 DB 缓存由
  index-daily 刷新任务负责。
