# K线数据完整性：科创板成交量量纲纠偏 + 指数伪代码成交额净化

- **窗口**：w-23c70356（investor / agent-dh 投资脑，实例 13080）
- **日期**：2026-09-10 22:30 ~ 23:30（盘后，非交易时段，仅数据治理与代码修复，无下单）
- **触发**：用户"这些定时任务是不是有问题，执行时间都太短了" → REQ-e5a251（K线同步静默失败）→ "遗留（未动）修复一下" → "修复，都修复"
- **提交**：b46520b4（成交额估算/自检排除指数与伪代码 + 成交额量级自检）、5efeaad2（科创板成交量量纲修正 + 成交量截面自检）
- **协作窗口**：w-8f2c4cc5（并行修复 amount/VWAP 一致性与数据库 provider 成交额缺失，commit 363b89eb，工作日志 kline-data-integrity-and-universe-remediation.md）

---

## 一、结论速览

| 缺陷 | 规模 | 处置 | 状态 |
|---|---|---|---|
| 科创板(688) 日K volume/amount 被放大 100 倍 | 2,110 行 / 2026-07-24~08-31 | 数据 ÷100 回补 + provider 根因修复 + 截面自检 | 已修 |
| 指数伪代码行 amount 用 volume×close 估算 | 638 行（含 000300 等） | amount 置 NULL + 估算/自检排除清单 | 已修 |
| 成交额量级失控（>1e12 元） | 修复前 651 行 | 现全库 0 行 | 已修 |

月度口径（quant.daily_klines，剔除 399xxx 与含点伪代码、amount is not null，2026-09-10 23:1x 查询）：

| 月份 | 成交额(万亿) | 成交量(万亿股) |
|---|---|---|
| 2026-07 | 50.795 | 2.595 |
| 2026-08 | **46.742** | **2.448** |
| 2026-09（1~10 日） | 15.201 | 0.918 |

修复前 8 月为 133.71 万亿 / 6.367 万亿股 —— 虚增 88.4 万亿（其中本窗口两次修复直接贡献 −88.398 万亿 / −1.310 万亿股）。

---

## 二、缺陷 (a)：科创板成交量 ×100 —— 根因定位

### 2.1 现象与证据链

1. **DB 侧**：修复前 2026-07-24~08-31 共 2,110 行 688 科创板日K的 volume 与 amount 同时放大 100 倍（备份表 quant.bak_starvol_vol_w23c70356 保留原值）。密度分布（quant.daily_klines，2026-09-10 23:0x）：
   - 07-24：84 行（占当日科创板 13.8%）、07-27：20 行（3.3%）
   - **08-14 ~ 08-27：连续 10 个交易日每天固定 196 行（占当日科创板 32.2%）**
   - 08-28：25 行、08-31：21 行
2. **外部源侧**（腾讯 fqkline 接口，2026-09-10 22:xx 抓取，现已被限流 501）：科创板 DB/源比值 = **1**，主板/创业板 = **100**。
3. **独立源校核**（不依赖外部网络）：quant.stocks.avg_volume（股，来自 stock-list 管线，与 K 线管线无耦合）——
   - A 修复行（修复前）中位数 79.159 ×avg_volume
   - B 同标的未修复行（7-8 月）中位数 0.866
   - C 修复行（修复后）中位数 0.792
   - A/C ≈ **99.9 ≈ 精确 100 倍**，2,098/2,098 行整数 100 倍。
4. **反证**：同期非科创板全市场复核仅发现 1 行 ×100 异常（001396 于 2026-08-28，ratio 10000.15），说明 ×100 对其余板块正确。

### 2.2 根因

adapters/outbound/datasources/providers/kline/tencent.py（fallback provider，provider 链：Database → Sina → Baostock(黑名单) → **Tencent** → Akshare）对成交量**无条件** volume_lots * 100，注释写死"volume(手)"。但腾讯该接口**科创板返回的已是「股」、其余板块才是「手」**——该板块例外未被处理，只在同步回退到腾讯源时触发，于是形成 07-24~08-31 的间歇性窗口。

### 2.3 处置

1. **数据回补**：2,110 行 volume/amount ÷100（备份 quant.bak_starvol_vol_w23c70356，remark 标记 volx100_fix_20260910(w-23c70356)）。
2. **根因修复**（5efeaad2）：按板块判定 bare.startswith((688,689)) 时不乘 100，并写明证据链。
3. **回归测试**：tests/adapters/test_tencent_kline_volume_unit.py 6 条单测锁定"股"契约；**故障注入实测**：还原旧行为后 4/6 失败、还原后 6/6 通过（文件 md5 校验一致）。
4. **自检补盲**：新增 _detect_volume_unit_anomalies（截面判据，见第四节）。

### 2.4 未闭合项（需外部源复核）

- 001396 于 2026-08-28 仍有 volume ÷100 待修，因腾讯源当前 501 无法复核，**暂不改数**（不凭记忆改数，宪法第5条）。

---

## 三、缺陷 (b)：指数伪代码行成交额污染

### 3.1 现象

指数行（如 000300 沪深300）被当作个股写入 daily_klines，成交额由 volume × close 估算，产生单行 **949 万亿元**级别的伪成交额；同期还有 1,213 行 600000.SH…600009.SH（name=Test）伪代码。

### 3.2 处置

1. 新增 utils/symbol_classifier.py：INDEX_WHITELIST（000001/000300/399001/399005/399006/399300/000016/000905/000852/000906）+ is_index_symbol / is_pseudo_symbol / index_symbols_for_exclusion / index_symbols_sql_predicate；**000001 按 stocks 表核实为平安银行，不得误排除**（否则其成交额缺失告警被吞）。15 条单测通过。
2. adapters/.../manager.py::_ensure_amount 对指数/伪代码提前返回（不估算）。
3. 638 行指数行 amount 置 **NULL**（备份 quant.bak_indexamt_w23c70356，remark amt_nulled_index_pseudo_20260910(w-23c70356)）；未知即未知，不伪造。
4. _count_missing_amount 排除 ^399 / 含点 / 指数白名单，避免每日同步指数后自检必然误报 critical（b46520b4）。
5. 实测守卫必要性：trade_date=2026-09-10 且 volume>0 且 amount IS NULL 修复后全库仅 1 行（399300），排除后每日自检 = 0 行。

---

## 四、自检体系：两条互补的探测器

| 探测器 | 判据 | 盲区 | 标定（2026-07~09 实测） |
|---|---|---|---|
| 成交额时序自检（b46520b4） | 当日 amount > 该股前 40 天中位额 × 50 | 缺陷**连续多日**时参考窗口被自身污染 | 覆盖首日爆发型；本次 32.2% 密度下仍有效 |
| 成交量**截面**自检（5efeaad2） | r=volume/avg_volume，r > 同日**同板块中位数** × 20 | 依赖 avg_volume 可用（12 行无基准） | **召回 2,080/2,098 = 99.1%，全市场误报 727/262,874 = 0.28%** |

标定过程（交叉截面评估脚本 /tmp/xsec_eval_w23c70356.sql，以备份表重建缺陷当时数据作 ground truth）：
- 纯 avg_volume 绝对判据（volume > 10×avg_volume）：召回 99.4% 但**误报 6.0%**（540 标的）→ 噪声不可用，弃用。
- 截面判据 K=20：召回 99.1% / 误报 0.28% → 采用；K=50 召回降至 70.8% 故不采用。
- 已知残余噪声：判据依赖 stocks.avg_volume 的时效/单位一致性，2026-09-10 实测告警 18 行中含 000001/000002/689009 等**基准值可疑**的行 → 日志措辞保留"需独立源复核"，仅告警不自动改数。

---

## 五、验证与运行状态

- 单测：tests/utils/test_symbol_classifier.py 15 passed；tests/adapters/test_tencent_kline_volume_unit.py 6 passed（含故障注入）。
- 集成冒烟（真实库，2026-09-10 23:2x）：amount_scale_anomalies=0、volume_unit_anomalies=18、missing_amount=0。
- data_quality_report(kline, days=3)：overall_score **92.5**，missing/delayed/anomalies 均为空。
- 服务：quantsys-v2 已重启（pid 30606，health ok，Registered job: kline_update），新旧守卫将在**每日 17:40** 的 kline_update 落库后运行。

---

## 六、上报但未动（需决策/授权）

1. **1,213 行 / 10 个伪代码**（600000.SH…600009.SH，name=Test）与裸代码重复 → 建议去重，未动。
2. **38 行 remark=other** 全在 2026-06-03（ratio 0.311~0.497，盘中部分同步）→ 建议标注口径。
3. **复权口径混装**：2026 年各月 vwap > high 行数 01:4,514 / 02:3,199 / 03:4,255 / 04:4,370 / 05:2,398 / 06:117(+144 低于 low) / 07:1,065 / 08:114 / 09:0；按 remark 分组：空 1,227/366,385、vol_unit_x100_fix_20260910 18,791/269,056、本窗口标记 0 → 属前复权/VWAP 口径混用，**RFC 级决策**，不做静默批量改写。
4. **跨窗口归因声明**：月度成交额降幅非单一窗口贡献——并行窗口填入 1,855,934 行 amount_est_vwap_20260910、vol_unit_x100_fix_20260910 标记 269,056 行；本窗口直接贡献为科创板 −88.398 万亿（08 月）/−3.012 万亿（07 月）与指数 −75,830.5 万亿。

---

## 七、留痕

- decision_audit：DEC-20260910232024-821fb7c4（本次根因修复）、DEC-20260910225104-b1c4bd64（h1 数据回补）、DEC-20260910223611-95c7d20c（bug_fix）、DEC-20260910223611-af8dcc3b（data_repair）及 risk_control 记录（指数污染与守卫 D/E）
- memory：49a2afa0-9a2b-4fe5-8b26-04b296a43ca4（量纲根因+盲区教训）、8874daaa-…（前序）
- 公告板纯记录帖：13c78472-…、a062de22-…
- 飞书：eba1c44a-…、9542fad1-… 及本次

---

## 八、验收证据（2026-09-10 23:5x ~ 00:2x，psql 直查 quant_investment）

| 验收项 | 结果 |
|---|---|
| 科创板剩余 ×100 行（>=2026-06-01，volume > 50×avg_volume） | **0** |
| 真指数行（399族 + 000300）amount 非空 | **0**（共 638 行全部 NULL） |
| 全库 amount > 1e12 | **0** |
| 2026-08 成交额（剔指数伪行/含点伪代码） | **46.736 万亿**（未剔指数伪行 46.742，差 0.006 万亿） |
| 全库 volume < 0 | **0**（volume = 0 共 131 行，为停牌零成交，正常） |
| data_quality_report(kline, 3d) | 92.5，无缺失/延迟/异常 |

### 追加发现 1（重要陷阱，已被现有设计挡住）

白名单里的 000016 / 000852 / 000905 / 000906 在 stocks 表中**都是真实个股**：*ST康佳A / 石化机械 / 厦门港务 / **浙商中拓**（000906，原注释未列出）。验收时若按"代码白名单"直接批量把 amount 置 NULL，会误伤 5 个真实标的合计 1,251 行真实成交额（其中 199 行落在 2026-07 以后）。is_index_symbol 的 stocks 表二次校验（list_date 非空即按个股处理）正是为此设置 —— 本次实测证明它有效：000001 平安银行 52 行、000016/000852/000905/000906 合计 199 行的金额都是真实个股数据，**未被动过**（宪法第5条：不确定即不臆断）。

### 追加发现 2（上报未动）：含点伪代码行曾被并行窗口的成交额回填任务写入

600000.SH…600009.SH 共 1,213 行的 remark 全部为 amount_est_vwap_20260910（= 并行窗口 w-8f2c4cc5 的成交额回填标记），每只金额高度雷同（122.4 亿元），name=Test，属测试/回测数据混入生产表；且写入方仍在持续写（最新行 2026-09-10）。现已由 is_pseudo_symbol（含 "." 即伪代码）从估算与自检路径排除（b46520b4），这些行的金额对下游统计已惰性；**行本身是否删除需决策**，本窗口未动，另建议定位写入方（疑似以 600000.SH 形式落库的回测/测试代码）。

### 追加发现 3（口径提示）

quant.stocks 中缺少部分新上市标的记录（如 001220、001396、301522、301556、301557、301592、301613、301626、301628 等），导致 ① 这些标的没有 avg_volume 基准、截面自检对其失效；② 任何"以 stocks 表反查是否为指数/存在性"的逻辑会把它们误判。属 universe 修复范畴（与 w-8f2c4cc5 工作线重叠），本次仅记录。

---

## 九、伪代码清理 + 双层防护（2026-09-11 00:0x ~ 00:4x，用户批准"全部执行"）

承接追加发现 2 的待决策项。用户经 ask_user_question 选择「全部执行（推荐）」＝备份 → 清理 → 补写入侧防护 → 验证不复发。

### 9.1 清理决策依据（先证真伪，再决定删/改）

| 检验 | 结果 |
|---|---|
| 10 只 `600000.SH`…`600009.SH` 的 stocks 记录 | name 全为 `Test`、`list_date` 为 NULL |
| 600001/600002/600003/600005 真实身份 | 邯郸钢铁/齐鲁石化/ST东北高/武钢股份——**均已退市**，裸码无 K 线；伪码却有 2026-05-06~09-02 共 120 行"行情" |
| 与真实裸码的同日收盘价比对 | 78~85 天重叠中 0 天完全相同（仅 600007/600009 有 12 天）→ **非同一证券**，改名合并会污染真数据 |
| 引用面（删前扫描） | daily_klines 1,213 / factor_values 174 / public.kline_data_quality 110 / stocks 10；池子、成交、盯盘、止损、回测表 **0** 引用 |
| 写入方 | 就是 kline_update_job（以 stocks 为宇宙逐日同步）→ 不删 stocks 行必然复发 |

结论：**删除而非修复**（改名会污染真实序列，保留则以 stocks 为源的同步会持续回写）。

### 9.2 执行（/tmp/testpseudo_delete_w23c70356.py）

先备份后删，逐表 `backed_up == deleted` 且 `left == 0`，共 **1,507 行**：

| 表 | 行数 | 备份表 |
|---|---|---|
| quant.daily_klines | 1,213 | quant.bak_testpseudo_w23c70356_daily_klines |
| quant.factor_values | 174 | quant.bak_testpseudo_w23c70356_factor_values |
| public.kline_data_quality | 110 | public.bak_testpseudo_w23c70356_quality |
| quant.stocks | 10 | quant.bak_testpseudo_w23c70356_stocks |

（quant_compat.* 是 quant.* 的 VIEW，无需单独清理；并行窗口的 quant.daily_klines_amount_backup_20260910 未动。）

### 9.3 防护（提交 9d2ac122）

1. **选股 SQL 形状过滤**：`STANDARD_SYMBOL_SQL = "s.symbol ~ '^[0-9]{6}$'"`，all/gem/batch/priority 四个分支全部接入——伪代码不再进同步队列。
2. **写入循环兜底**：update_gem_klines 循环内非 6 位裸码直接 `skipped`（连 provider 请求都不发），显式 symbols 入参也穿不过。
3. **f-string 陷阱**（实测踩到）：batch 分支是 f-string，把 `'^[0-9]{6}$'` 直接写进去会被渲染为 `'^[0-9]6$'`（过滤静默失效）→ 改用 `{STANDARD_SYMBOL_SQL}` 插值，并加测试锁定该形态。

### 9.4 变异测试（证明测试真的能抓住回退，三次注入后均已还原，md5 一致 7e4462a03071ca20bdb7520e7b77b183）

| 注入 | 预期 | 实际 |
|---|---|---|
| 去掉写入循环兜底 | 对应测试 FAILED | ✅ FAILED |
| batch 分支改回字面量（brace trap） | f-string 测试 FAILED | ✅ FAILED |
| 去掉 all 分支形状过滤 | 不变量测试 FAILED | ✅ FAILED |

### 9.5 顺带修复的两处"静默失效的回归测试"

- `tests/test_kline_amount_fix.py` 的 `TENCENT_RESPONSE` 仍写 `qfqday`，而 provider 自 **2026-07-23（84ce0cc2）** 起只读 `node['day']` → 该回归测试自 07-23 起从未跑到断言（只打印 "Tencent returned no data"）。fixture 键更正为 `day`，断言（volume×100、amount = 股×close）恢复生效。
- `tests/infrastructure/test_kline_update_selection.py` 改为断言**不变量**而非造污染行：四个 scope 的实际查询结果不得含非 6 位符号（测试库 quant_test 里确实存在 `600000.SH` 行，故该断言能真实抓住回退）。不往 stocks 塞含点行是因为 `quant.portfolio_holdings` 上有 FK `portfolio_holdings_symbol_fkey → quant.stocks(symbol)`——塞/删都会撞 FK（实测：删 `600000.SH` 报 "still referenced from table portfolio_holdings"）。

### 9.6 验收（2026-09-11 00:4x，psql 直查 quant_investment）

| 验收项 | 结果 |
|---|---|
| quant.stocks 非 6 位裸码行 | **0**（总 5,856 行） |
| quant.daily_klines 非 6 位裸码行 | **0** |
| factor_values / kline_data_quality 含点行 | **0 / 0** |
| 备份表在档 | 1,213 行（可回滚） |
| 回归测试 | **37 passed**（本次相关 5 个测试文件） |

> 待观察：2026-09-11 17:40 的定时同步应保持非标准码 0 行（防护已生效；该次同步前 qv2 需重启加载新代码）。

### 9.7 诚实边界

- 本次只清理**生产库**；测试库 quant_test 里同样的 `600000.SH` 行（及其持仓子行）未动——那是测试库，清理属另一条线。
- `quant.portfolio_holdings` 曾存在引用伪代码的行（FK 报错即证），在我做清理扫描时该行已不在（其余窗口/并行活动清理过），**本窗口未对其做任何删除**；此点记录在案以免日后误判为"漏查"。
- 本窗口对上述统计口径的直接贡献仅限两处：科创板 −88.398 万亿（08 月）/ −3.012 万亿（07 月）与指数伪行 amount 移除；其余由并行窗口完成，已在前文注明。

