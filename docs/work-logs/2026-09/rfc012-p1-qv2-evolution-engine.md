# RFC 012 P1：qv2 真实策略进化引擎——进化数据链补真（w-8366e526）

日期：2026-09-03 | 角色：investor（w-8366e526）| 关联：[RFC 012 设计](../rfcs/012-strategy-evolution-engine.md)

## 目标

P0（占位拦截，commit 50df98e6）后，把进化数据链的"引擎"腿从 Agent OS
legacy evolution（0.05×i 占位 + 假 leaderboard）换成 qv2 真实实现：
**策略参数网格 → 逐变体真实回测 → 同批 fitness 归一 → 落库**，P2 再让
agent-dh evolution_run/leaderboard 工具消费真实数据源。

## 交付物

| 文件 | 作用 |
|---|---|
| `quantsys-v2/application/services/strategy_evolution_service.py` | 进化引擎：参数提取/确定性网格/fitness/诚实 degraded |
| `quantsys-v2/adapters/outbound/repositories/strategy_evolution_run_repository.py` | 落库 + runs 聚合读取 |
| `quantsys-v2/infrastructure/persistence/migrations/add_evolution_strategy_runs_table.sql` | `quant.evolution_strategy_runs` 建表（17 列） |
| `quantsys-v2/adapters/inbound/fastapi_app/routes/evolution_engine_async.py` | POST run / GET runs / GET runs/{id} |
| `quantsys-v2/tests/test_strategy_evolution_service.py` | 17 pytest 全绿 |
| `quantsys-v2/.../main.py` | 路由注册（try/except 惯例） |

## 关键设计

1. **网格**：base params 邻域 ±10%（propose/1 代）；generations=2 → ±20/±10；
   generations=3 → 全档 ±20/±10/±5。int 圆整、下限 1、float 4 位、跨档去重、
   确定性（不依赖 dict 序——sorted 键网格）。
2. **fitness（RFC 012 §4）**：单批内 min-max 百分位合成，权重
   0.5·收益 + 0.3·夏普 + 0.2·胜率（单调增三维）；某维全同值或缺失/NaN → 0.5 中性。
   **base 对照组与变体同批归一** → best/improvement 同批可比，不跨 run。
3. **数据诚实性**（承接 2026-09-01 教训）：基线回测失败/零交易 → 整轮
   `data_source=degraded + degraded_reason`，**不产任何 0 分假基线**；
   script 类型、无数值参数、策略不存在同理。degraded 行落库留痕。
4. **落库裁剪**：metrics 弃 trades/equity_curve 大数组，留标量指标列。
5. **读取**：`GET runs` = 每 run 一条 leaderboard 最优行（window row_number
   按 fitness 排序，NULLS LAST）；`GET runs/{run_id}` = 整批变体明细。

## 验证（真实数据）

- 单测 17/17（mock 回测腿：参数提取/网格确定性/归一数学边界/零交易→degraded/
  script→degraded/落库调用）。
- 真实 run（qv2 API，strategy 635 MACD × 600519，2025-09-01~2026-08-31）：
  - propose：HTTP 200，`dataSource=qv2_real`，7 变体全成功，24s
  - full 3 代：15 变体（跨档去重后 15），全成功，improvement 0.709，19s
  - best params `{fastPeriod:13, slowPeriod:26, signalPeriod:9}`（两次 run 一致）
  - 表内 22 行可查、GET runs 聚合 2 行、明细 15 行 fitness 0.0127~0.9082

## 未决/下一步

- **推送**：main 领先 origin 13 commit（含并行会话 9 个），未代推，待人工/并行线就绪统一推。
- **P2**：agent-dh `evolution_run`/`evolution_leaderboard` 工具改造——消费
  `GET /api/evolution/engine/run|runs`，删除 Agent OS legacy 客户端依赖；
  保留 P0 拦截直到 P2 接通。
- **P3（可选）**：fitness 跨 run 可比化（固定参考分/指数化）、多标的批处理。
