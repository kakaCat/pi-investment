# REQ-261020014122-d659 回测判据与 evolution_run schema 修复（解除策略补测阻塞）

- **类型**：feature（expert）
- **创建**：2026-10-20 · w-503df447（investor）
- **上游**：REQ-261019144524-ec50《进化闭环有效性改造》spike 报告 §5 后续卡 2；w4-strategy-cleanup.md §4（缺陷实证）

## 1. 背景与问题陈述

策略库 5 条 user 策略 100% unmeasured，补测（P4 验收指标：measured 占比 ≥50%）被两个实测缺陷阻塞：

1. **回测「零交易」判据缺陷**（连续 4 周复现）：`run_backtest_from_signals` 的 `trades` 只在 SELL 分支 append（strategy_backtest_service.py L254 起的循环内），**窗口结束不强制平仓**——开仓未平仓的回测 `total_trades=0`。实证：策略 202/002007 一年窗 equity 100000→82664（184 天有持仓、实际收益 -23.18%），`totalTrades=0` 被 `strategy_evolution_service.py` L198 的 `MIN_TRADES=1` 门槛误判为「窗口无信号」拒绝进化。
2. **evolution_run 降级被工具 schema 拦成硬错误**：后端诚实降级（data_source=degraded）时响应无 best_params/best_metrics/fitness，而工具输出 schema 把这些字段当必填 → 返回 `returned invalid output` 硬错误，**降级原因被消灭**（同一事实 evolution_leaderboard 能正常返回 degraded_reason）。lessons 已有纪律：「降级路径的输出形状必须与成功形状分离」。

## 2. 产品定义

修通「策略回测 → 进化/补测」链路的判据与观测边界，使：①有持仓但未平仓的回测不再被误判为无信号；②evolution_run 降级返回携带可读原因而非硬错误。修通后执行 163/178/179/193 的 OOS 补测（补测执行本身可留到本需求收尾或下一张卡，但链路必须先通）。

## 3. 用户与角色

- 直接用户：投资脑（本实例）——evolution_run / strategy_execute(backtest) 的调用方；
- 间接受益：策略线（v13/v14 等账户的策略度量同样走该判据）；
- 复核者：人类用户（验收时按测试用例复跑）。

## 4. 功能点

- **FR-1: 回测窗口末强制平仓计账**——`run_backtest_from_signals` 循环结束时若仍有持仓，按末日收盘价强制平仓并把该笔计入 trades（标记 `forced_close=true`），使 total_trades 语义 =「发生过的往返交易数」而非「恰好平仓的交易数」；权益曲线不受影响（持仓市值本已按末日价计入）。
- **FR-2: 判据口径声明**——metrics 增加 `open_position_at_end`（bool）与 `forced_closes`（int）字段，调用方（进化/补测）可区分「真无信号」与「有信号未平仓」；MIN_TRADES 门槛语义不变但判据从此正确。
- **FR-3: evolution_run 降级形状合法化**——工具输出 schema 增加降级分支（best_params/best_metrics/fitness 在 data_source=degraded 时允许缺省/null），或执行层在降级分支补齐占位字段并显式标 `degraded: true`；两种实现取其一，判据 = 降级调用返回 200 且 degraded_reason 原文可达（与 evolution_leaderboard 行为一致）。
- **FR-4: 故障注入实测**——按 lessons「故障路径必须故障注入实测」：构造「开窗未平仓」回测用例断言 total_trades≥1 且 forced_closes=1；构造降级场景断言 evolution_run 返回 degraded_reason 而非硬错误。
- **FR-5: 回归验证**——修复后重跑 spike 期间的实证用例（策略 202/002007 一年窗）：evolution_run(propose) 不再报 invalid output；若变体回测仍全降级，degraded_reason 必须可读。

## 5. 边界（不做什么）

- 不改 fitness 归一公式、不改参数网格生成逻辑、不改 MIN_TRADES 阈值数值；
- 不动分钟线 T+1 约束逻辑；
- 不做策略补测的参数寻优（只修链路；补测执行为可选项或后续卡）；
- 不重构 strategy_backtest_service 的其它分支（分批买卖、自定义价格校验保持原样）；
- evolution 包是 dist 加载（package.json main=./dist/index.mjs）——改源码必须 pnpm build + 重启生效，发版走 scripts/restart-with-build.sh（lessons 教训：改源码≠已生效）。

## 6. 验收锚点

- `npx vitest run`（quantsys-v2 对应测试）含 FR-4 两个故障注入用例全绿；
- 实调 `strategy_execute(mode=backtest, strategy_id=202, symbol=002007, 一年窗)`：total_trades ≥1 且含 forced_closes 字段；
- 实调 `evolution_run(202, 002007, propose)`：返回 success（qv2_real 或 degraded），degraded 时 degraded_reason 非空且无 schema 硬错误；
- evolution_leaderboard(202) 与 evolution_run 对同一降级事实的表述一致。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t1 |
| FR-2 | ✅ 已接收 | t1 |
| FR-3 | ✅ 已接收 | t2 |
| FR-4 | ✅ 已接收 | t1、t2 |
| FR-5 | ✅ 已接收 | t3 |

> 无未接收条款（5 条全部有落点）。

<!-- reqboard:marks:end -->

## 7. 风险

- 强制平仓会改变历史回测的 trades 计数（只增不减）——旧报告与新口径不可直接比较，须在 FR-2 字段与文档中声明口径变更时点；
- evolution 包构建曾有 dts 推断类型失败清空 dist 的前科（lessons）——构建后必须校验 dist 产物含关键符号再重启。
