# K线数据完整性与量纲缺陷修复 + 因子池预筛（2026-09-10, w-8f2c4cc5）

> 一句话：一次「K线覆盖缺口」的排查，挖出 **volume 列整批 ×100 的单位错误（210 万行）**，并闭环了覆盖缺口、因子池污染与错误事件噪声三条支线。

## 0. 触发与四条工作线

| 线 | 原始诉求 | 结论 |
|---|---|---|
| A 数据 | 补 000001 的 K 线空洞（2025-06 → 2026-08），量化并修复同类缺口 | 全窗口对账修复，完整率 4,763 → 5,256 |
| B 工程 | InsufficientDataError 属预期校验，不应报 Unexpected error；错误事件按调用点指纹化 | 日志降级 warning；8 条事件 = 8 个调用点 |
| C 股票池 | 因子入队前预筛非股票标的（定转/指数）与 K线 <26 根 | 预筛实测生效 |
| D（排查中新发现） | volume 单位错误导致量能因子与回测失真 | 三轮修复 2,102,873 行 |

## 1. 线 D（核心发现）：volume 列 ×100 单位错误

**现象**：持仓 600887 伊利股份的 volume_ratio 报 0.0034（正常应≈1），volume_ma5 与当日量能失真。

**根因**：quant.daily_klines.volume 中若干导入批次把「手」当「股」写入（×100 偏小）。价格类因子不受影响，因此**不会自然报警**——只有量能类因子与回测被污染。

**判别口径（关键）**：内证指标 (amount/volume)/close **只能看数量级**，不能当 VWAP 用：

- DB 的 close 为复权价、amount 为原始成交额，两者口径不同 → 正确的行该比值也 ≠ 1（601398 逐年漂移 133.85(2023)/120.14(2024)/106.87(2025)/100.20(2026)）。
- 因此只用「比值 > 5 → volume×100」这条量级规则；605117 2023-05 的 5.5 倍残差经实测是复权口径伪影，**不是** volume 错误。

**三轮修复**：

| 轮次 | 方法 | 行数 |
|---|---|---|
| 1 | amount 自洽判据：amount>0 AND volume>0 AND close>0 AND (amount/volume)/close > 5（trade_date ≥ 2022-01-01） | 1,980,894 |
| 2 | amount=0 无法自证 → 用 60 个位置内最近的 amount 自洽行做参照分类，**仅应用经抽检验证的 x100 类** | 36,547 |
| 3 | 余下 2,658 只按标的新浪行情重取（datalen=320，5 并发），abs(db/sina−1)>5% 才覆盖 | 63,937 |

**为什么第 2 轮只应用 x100**：近邻参照同时给出 93 行 div100 候选，抽检 6/6 全是假阳性（原值已与新浪一致，如 603388 2025-09-01 DB 9,690,200 vs 新浪 9,690,180）→ 盲改会制造新错。所有改动前均落备份表（daily_klines_vol_backup_20260910 / ..._backup2_...）并写 remark 标记（vol_unit_x100_fix_20260910 / ..._fix2_... / sina-volsync-20260910）。

**外部验证**：两轮共抽检 93 行与新浪逐值比对，**100% 一致，中位比值 1.000**（如 600256 2025-06-03 DB 57,260,000 vs 新浪 57,260,003；601398 2025-06-03 272,811,800 vs 272,811,811）。

**效果**：窗口自洽桶 351,093 → **975,521**；持仓实测 600887 volume_ratio 0.0034 → **0.8719**、300677 **1.1011**（factor_values，2026-09-10）。

## 2. 线 A：K线覆盖缺口

**口径**：不用 max(trade_date) 判新鲜度（有最新一根但中间空洞照样「合格」），改用**交易日历逐标的连续性对账**：missing = 日历交易日数 − 该标的在日历日上的 bar 数。日历 = 当日有 ≥4,000 只标的的日期（2025-07-17 ~ 2026-09-10，275 个交易日）。

**000001 平安银行**：补 300 根（2025-06-03 ~ 2026-08-21），窗口内 bar **14 → 282**，总 801；补入行与既有行对同一日新浪收盘偏差 0.0%（口径一致，无价格断层）。

**全市场对账回填**：1,286 只标的补 **31,595** 根（sina-gapfill）。补行前先用重叠日 db_close/sina_close 中位比校正复权口径（偏差 >2% 才应用，36 只命中），volume 用新浪原值（股），amount ≈ volume × 原始收盘。

| 窗口完整度 | 修复前 | 修复后 |
|---|---|---|
| A 完整 ≥98% | 4,763 | **5,256** |
| B 轻微缺口 90-98% | 325 | 133 |
| C 中度缺口 50-90% | 317 | **17** |
| D 重度缺口 <50% | 1 | 0 |
| Y 次新股（窗口后上市，合理） | 132 | 132 |

近端覆盖同步恢复：2026-09-10 当日 bar 数 2,514 → **5,501**。

**残留**：150 只（119 普通 + 31 ST/退市）仍有 6-37 日缺口，属**数据源限制**（新浪同样无这些日期的数据，多为停牌/*ST），且 ST 类已被线 C 排除在因子池外，不影响决策链。
另有 531,769 行 amount=0（无金额，无法内部自证）；其中已由新浪按标的校准（volsync/gapfill/catchup）覆盖，剩余部分由夜间覆盖感知同步长期收敛。

## 3. 线 B：错误事件噪声治理

- infrastructure/quantlib/core/base_calculator.py：InsufficientDataError / DataValidationError / ValueError 属**预期校验**，由 error 降为 warning（不再进 Unexpected error 管道）。
- 事件指纹按调用点分裂：实测库中 8 条 InsufficientData 事件 = **8 个独立调用点**（atr14 / bollinger_lower·middle·upper / macd / macd_histogram / macd_signal / rsi14）→ 一次故障不再刷成多事件，指纹化正确、无需额外改动。
- 另修复 daily_orchestrator.py 与 legacy_adapters.py 的 structlog 参数冲突（4 处 event= 与位置参数撞名 → TypeError）。
- 验证：重启服务加载新代码后跑 52 只因子任务——[error 行 0、Traceback 0、error_events 增量 **0**。

## 4. 线 C：因子池预筛

application/services/scheduler_tasks.py 新增 MIN_BARS_FOR_FACTORS = 26（MACD 最长窗口）与非股票标的识别（定转 / 指数 / 退市），因子任务入队前预筛并回报 universe_dropped / universe_dropped_examples。

实测（52 只输入 → 37 只入选）：剔除 1 退市 / 5 ST / 5 非股票标的 / 4 K线<26根，样例 [000001 14bar, 600001.SH Test, 810013 万通定转, 832317 0bar, ...]，status=success, failed=[]。

## 5. 代码变更（本工作线）

```
adapters/outbound/datasources/providers/kline/sina.py      datalen 300→1023；去掉错误的 volume ×100 换算
adapters/outbound/datasources/manager.py                   get_klines 覆盖感知 + _expected_last_bar_date
adapters/inbound/fastapi_app/daily_jobs_bootstrap.py       KLINE_COVERAGE_FRESH_THRESHOLD=0.98 + 缺口补扫（已在 41f19484 提交）
application/services/scheduler_tasks.py                    线 C 预筛（MIN_BARS=26 / 非股票标的）
infrastructure/quantlib/core/base_calculator.py            预期校验异常降级为 warning
infrastructure/persistence/database/engine.py              _resolve_db_dsn 二级/三级回退（config → PG* 环境变量）
application/services/daily_orchestrator.py                 structlog event= 参数冲突
application/notification/legacy_adapters.py                同上（4 处）
```

## 6. 影响面与风险

- **对现网决策的影响**：价格类因子与 5-10 日量能因子在 2026-09-10 当日 bar 修复后已恢复正常；本轮修复的主要受益面是**回测/复盘与长窗口量能因子**。
- **不可用 amount 作为 VWAP**：601398 的 amount/volume 与复权收盘逐年漂移，修复规则一律基于**数量级**而非比值本身。
- **运维提示**：数据源冻结/降级期间产生的风控信号仍须降级为「待复核」（见 v8 经验教训「生命周期与风控的数据新鲜度」）。

## 7. 留痕

- decision_audit：DEC-20260910221124-5bfdb013（decision_type=risk_control）
- memory_write：e0022176-699e-4578-81b6-7728cf5d6c01（namespace=analysis）
- experience_write：9e233e77-...（连续性对账口径）、0ac77ef5-...（单位错误双通道发现法）
