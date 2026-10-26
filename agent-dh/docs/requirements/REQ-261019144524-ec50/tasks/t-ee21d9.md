# t-ee21d9 策略库治理清单（TEST 残留盘点 + unmeasured 补测可行性）·取数调研

> 子卡（父卡 t-ab4c82 · 阶段 collect）——由自动实施链展开；本卡文档在验收前按 queue.json 台账回填（2026-10-19，w-503df447）。

## 在做什么
策略库治理清单（TEST 残留盘点 + unmeasured 补测可行性）·取数调研

## 状态
done（lastRun.ok=True）

## 完工记录（台账回填，原文）

- collect 阶段完成（2026-10-19，来源标注对齐 R-013）：①策略库全量盘点——当前库共 22 条（user 5 + builtin 17，GET /api/strategies 分页拉全，非抽样）：TEST 残留 0 条（无 test/TEST 命名命中，此前 101 条时代的残留已随库清理消失，当前 user 策略仅剩 5 条）；业绩轴 5/5 user 策略全 unmeasured（163/178/179/193 structure=unknown、202 structure=invalid+unmeasured），builtin 17 条无业绩口径字段；②接口可用性抽查——回测接口可用且引擎功能正常（直接 POST /api/backtest/strategy 策略 202/002007 一年窗：equity 100000→82664、184 天有持仓、首持仓 2026-01-09）；两只 unmeasured 策略（163/600519 全年、178/002007 半年）回测均正常返回权益曲线但全程 positionValue=0，属真实无信号而非引擎故障；③unmeasured 补测可行，但判据禁用 totalTrades（已知缺陷当轮复现：有持仓时仍计 0），应以权益曲线变动/持仓天数为准；evolution_leaderboard(202) 显示 3 轮进化全 degraded（基线零交易判据）。
