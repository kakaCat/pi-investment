# REQ-261020014122-d659 拆分计划：回测判据与 evolution_run schema 修复

- **依据设计**：docs/requirements/REQ-261020014122-d659/design/（五份已落章；合一总览 design.md）
- **规模**：4 个文件改动（2 生产 + 2 测试），无新组件、无 DB 变更 → 4 张任务卡，依赖安全序排列。

## 1. 代码层面变更盘点

- **新增**：`quantsys-v2/tests/test_backtest_forced_close.py`（pytest，C1 故障注入 + C2/C3 回归）
- **修改**：
  - `quantsys-v2/packages/qs_strategy/qs_strategy/application/services/strategy_backtest_service.py` —— `run_backtest_from_signals` 主循环后（现 L510 与 L512 之间）增强制平仓计账段；metrics 加 `open_position_at_end`/`forced_closes` 两键
  - `agent-dh/packages/tools/evolution/src/tools/EvolutionRunTool/EvolutionRunTool.ts` —— `normalizeRunResult` 对 `best_params`/`best_metrics`/`fitness`/`fitness_improvement` 四个 null 键做白名单剔除（沿用 :46 `degraded_reason` 同款模式）
  - `agent-dh/apps/web/tests/evolution-qv2-contract.test.ts` —— 新增 C4 用例（线上真实「显式 null」降级形状）
  - `quantsys-v2/CHANGELOG.md`（或等价变更记录）—— `total_trades` 口径变更时点声明
- **删除**：无
- **明确不动**：`strategy_evolution_service.py`（MIN_TRADES 数值/判据位置/归一公式/网格生成零改动）；prompt.ts output schema；分钟线 T+1、分批买卖、自定义价格校验分支；evolution_leaderboard。

## 2. 批次与依赖

```
t1（后端：强制平仓计账+字段）      t2（工具侧：null 剔除+C4）
   │                                 │
   ├───────────────┬────────────────┘
   ▼               ▼
   t4（doc：口径变更声明，dep t1）   t3（verify：发版+实证回归 FR-5，dep t1,t2）
```

- t1 与 t2 互不依赖，可并行；t3 依赖两者完成；t4 依赖 t1（声明须与实现口径一致）。
- 接口/数据契约已在 design/interfaces.md 与 data-model.md 定死（字段名/类型/口径/副作用边界），实现卡不再二次创作。

## 3. 覆盖对照表

| 需求条款 | 接收任务 |
|---|---|
| FR-1（窗口末强制平仓计账） | t1 |
| FR-2（判据口径字段 open_position_at_end/forced_closes） | t1 |
| FR-3（evolution_run 降级形状合法化） | t2 |
| FR-4（故障注入实测） | t1, t2 |
| FR-5（实证回归） | t3 |

（t1 承接 FR-4 的 C1-C3 后端用例，t2 承接 C4 工具侧用例；口径变更声明 t4 为 FR-1 的兼容性配套，不单独对应条款。）

## 4. 任务表

| key | title | phase | side | depends_on |
|---|---|---|---|---|
| t1 | 回测窗口末强制平仓计账与口径字段 | implement | backend | — |
| t2 | evolution_run 降级 null 键剔除与契约用例 | implement | backend | — |
| t3 | 发版部署与实证回归（FR-5） | test | fullstack | t1, t2 |
| t4 | total_trades 口径变更声明落 changelog | doc | doc | t1 |

（完整 implementation/acceptance 见提交时的 tasks 表。）

## 5. 验收锚点（与 design/test-cases.md §4.4 一致）

- `cd quantsys-v2 && python -m pytest tests/test_backtest_forced_close.py -v` —— C1-C3 全绿
- `cd agent-dh && npx vitest run apps/web/tests/evolution-qv2-contract.test.ts` —— C4 + 回归全绿
- `cd agent-dh && npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` —— schema 门禁回归
- 发版走 `agent-dh/scripts/restart-with-build.sh`，构建后 grep dist 产物确认新符号
- 实证三步骤：strategy_execute(backtest, 202, 002007, 一年窗) total_trades≥1 且含新字段；evolution_run(202, 002007, propose) 无 schema 硬错误且 degraded_reason 可读；evolution_leaderboard(202) 表述一致

## 6. 风险

- evolution 包构建清空 dist 前科 → t3 含 dist 产物校验，失败按「未生效」处理；
- 口径变更新旧报告不可比 → t4 声明时点；
- null 剔除误伤 → 白名单化，C4 与既有 REAL_RUN 用例双向锁死。
