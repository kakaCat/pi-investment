# 后端工作工单（W1-W3）—— 2026-08-25 投资脑出单，执行模型施工，投资脑审计

> 用法：每单含目标、改动点、实施步骤、验收命令。**验收命令全过 = 完成**，完成后通知投资脑审计。
> 红线：①只改工单指定文件；②不要动 `agent-dh/` 目录（投资脑领地）；③每单独立提交 commit。

---

## W1（最高优先级）M0 数据回填：K 线历史 ≥120 交易日 + 指数 K 线

**背景**：当前 `daily_kline` 表只有 ~100 个交易日（2026-03-25 起）。MA60 策略回测、窗口化（牛/熊/震荡）回测、regime 趋势维度全部因此受限。指数 K 线（000300/399300）完全缺失。

### W1-1 个股日 K 回填
- **目标**：全部持仓股 + 各股票池成员 + 指数成分龙头（≥200 只），`daily_kline` 历史 ≥250 个自然日（≥160 交易日）
- **改动点**：`quantsys-v2/application/services/data_backfiller.py`（已有，自查接口）
- **步骤**：
  1. 查当前每只标的 `MAX(trade_date)`/`MIN(trade_date)`
  2. 用 akshare `stock_zh_a_hist`（或现有 provider）按 `start_date=2025-01-01` 回填缺失段，幂等（已存在日期跳过）
  3. 写入走 `KlineORMRepository` 批量 upsert
- **验收命令**：
  ```bash
  python3 -c "
  from adapters.outbound.repositories.kline_repository import KlineORMRepository
  r = KlineORMRepository()
  df = r.get_range(symbol='600519', start_date='2025-06-01', end_date='2026-08-25')
  print(len(df))  # 必须 ≥200
  "
  curl -s "http://localhost:5001/api/stock/600519/klines?start_date=2025-06-01&end_date=2026-08-25" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['klines']))"
  # 两个都必须 ≥200
  ```

### W1-2 指数 K 线
- **目标**：沪深300（000300/399300）、上证指数（000001）日线 ≥250 自然日
- **改动点**：回填器 + `daily_kline` 表（symbol 用 `000300`/`000001`）；数据源 akshare `stock_zh_index_daily`
- **验收命令**：
  ```bash
  curl -s "http://localhost:5001/api/stock/000300/klines?start_date=2025-06-01&end_date=2026-08-25" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('klines',[])))"
  # 必须 ≥200，当前返回 "No kline data"
  ```

### W1-3 回填常态化
- **目标**：每日凌晨自动增量回填（防再次断粮）
- **改动点**：后端调度器（`scheduler_manage` 可见的 40 个任务里加一项，或现有每日 02:00 任务挂接）
- **验收**：`scheduler_manage list` 可见回填任务；`SELECT MAX(trade_date) FROM daily_kline` 每日 = 最近交易日

---

## W2 battlefield_assessor / opponent_behavior 模板化修复

**背景**：`pool_battlefield` 对 pool 27/35 返回逐字节相同输出（78.5 分同模板）；`opponent_behavior` 同为模板嫌疑。验收不通过（投资脑 2026-08-23 实测）。

- **改动点**：`quantsys-v2/application/services/battlefield_assessor.py`、`opponent_behavior_service.py`
- **要求**：接入真实数据源——池内成分股的资金流（fund_flow）、换手率、涨跌幅分布、北向（如有）。评分必须对**不同池/不同日期**产生**不同数值**；数据源缺失时显式返回 `data_quality: 'degraded'` 并说明缺什么，**禁止返回固定模板分**
- **验收命令**：
  ```bash
  # 两个池评分必须有差异，且能说明差异来源
  curl -s "http://localhost:5001/api/game/pools/27/battlefield-assessment" > /tmp/b27.json
  curl -s "http://localhost:5001/api/game/pools/35/battlefield-assessment" > /tmp/b35.json
  diff /tmp/b27.json /tmp/b35.json && echo "FAIL: 输出仍然相同" || echo "PASS: 输出有区分度"
  ```

---

## W3 数据质量自查清单（防再犯）

今天后端连环故障（memory 500 / sectors 500 / orders 无持仓 / 回测 DI / services.yaml 循环依赖）全是重构后**没有端点级回归**导致的。要求建立最小回归：

- **改动点**：`quantsys-v2/tests/` 新增 `test_api_smoke.py`
- **要求**：覆盖以下端点的"调用不 500"冒烟（每端点一个用例，断言 success 字段或非 5xx）：
  `/api/memory/search`、`/api/memory`（POST）、`/api/market/sectors`、`/api/market/sector/{name}`、`/api/portfolio/positions`、`/api/orders/create`（sell 校验路径）、`/api/backtest/run`、`/api/risk/metrics`
- **额外**：`config/services.yaml` 变更必须过"注册冒烟"（`register_all_services()` 无异常 + 无循环依赖）
- **验收**：`pytest tests/test_api_smoke.py -q` 全绿；每次重构合并前必跑

---

## 已完成核销（勿重复施工）

| 项 | 状态 |
|---|---|
| memory 500（config 空 dict） | ✅ 已修（embedding.py 双兼容兜底，main `07f62b2c`） |
| sectors 500（MarketData 未解包） | ✅ 已修（main `07f62b2c`） |
| 卖出"无持仓记录" | ✅ 已修（order_service 走 simulation_*，main `07f62b2c`） |
| 回测 DI（循环依赖/None 仓储） | ✅ 已修（main `99521cd1` + services.yaml/shared/__init__） |
| trade_verify 404 | ✅ agent-dh 本地对账替代 |
| manipulation_detect 契约错位 | ✅ agent-dh 本地个股评分替代 |

## 审计约定（投资脑负责）

每单完成后：
1. 我跑工单里的验收命令复核
2. W1 回填后我重跑 5 策略 × 3 窗口回测矩阵（M3-2 验收）
3. 任何契约变更（参数/返回结构新增必填或改语义）必须先在公告板/工单回复里声明，**不允许静默变更**——今天 orders/create 新增 order_type 必填就是静默变更打断了交易链路
