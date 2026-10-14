# REQ-261006133733-1fdf · 异常值检测静默失效：成交量段迭代错对象（每只必抛错、被 except 吞成无异常）

**需求ID**: REQ-261006133733-1fdf
**类型**: feature（立项弹框作答所得；**实质是缺陷修复**——范围见 D-2）
**作用域**: `quantsys-v2/`（`application/services/data_validator.py` 为主，`application/services/data_quality_service.py` 为下游语义面，`tests/`）
**侧**: backend（无前端产出，不涉及原型）
**档位**: expert（立项弹框作答所得）

## TL;DR

**现象**：今日 `00:01–00:04`，`logs/api.log` 刷出 **7995 条** error：
`检测异常值失败: cannot select elements using Sequence with elements of type 'str'`（来源：「每日数据质量检查」task 232，5686 只全量）。

**根因（本机复现 + traceback 已抓）**：`application/services/data_validator.py:369` 迭代错了对象。

```
detect_anomalies()                                    # data_validator.py:296
  ├─ :328  klines = repo.get_daily_klines(...)        # KlineORMRepository → **polars DataFrame**
  ├─ :341  klines_list = klines.to_dicts()            # list[dict]（正确形态）
  ├─ :356  for kline in klines_list:  ← 价格段：对      ✅ 正常
  └─ :369  for kline in klines:       ← 成交量段：错！  ❌ 迭代 polars DataFrame
             :370 float(kline['volume'])              # 每次拿到的是 pl.Series
             :375 str(kline['trade_date'])            # series['str'] → polars getitem TypeError
```

```
  polars/series/series.py:1485 __getitem__
  polars/_utils/getitem.py:76   raise TypeError("cannot select elements using Sequence with elements of type 'str'")
```

**后果（三档，逐档都有证据）**：

| # | 后果 | 机制 | 证据 |
|---|---|---|---|
| 1 | **异常检测零产出**（100% 假阴性） | K 线 ≥30 行 ⇒ 恒抛错 ⇒ `except`（:389）返回 `has_anomalies=False / total_anomalies=0`，把**已算好的价格异常也一并丢弃** | 复现命令见「判定标准」③ |
| 2 | **质量分被系统性抬高最多 20 分** | `get_data_quality_score`（:434-437）里「异常率」占 20 分，而 `total_anomalies` 恒为 0 ⇒ 该项**恒得满分** | 今日报告 `data_quality_score=95.01` 中这 20 分是白送的 |
| 3 | **日志风暴** | 每只股票一条 error，5686 只全量 | 00:01–00:04 实测 7995 条 |

**本需求要做的（按 D-2）**：把成交量段改回 `klines_list`；**让失败不再冒充「无异常」**（上游必须能区分「真的干净」与「检测没跑成」）；补回归锁；实跑复验 7995 → 0 且异常检测真出结论。

## L1 一句话目标 + 可证伪判定标准

**目标**：让「异常值检测」这条判断**真的运行**，并且**不许再把失败伪装成「数据干净」**——
下游拿到的要么是真实结论，要么是「未知/失败」，不能是"看起来没事"。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：

1. **真 polars 用例（新增）**：喂一个 ≥30 行的真 `pl.DataFrame`（含人造价格/成交量异常）→
   `detect_anomalies` **不得抛错**，且 `total_anomalies ≥ 1`、能列出对应 `price_anomalies` / `volume_anomalies`。
2. **反例锁（改前必红）**：同一条用例在改前跑 → 红（`has_anomalies=False` 且 `error` 非空）；
   证明这条锁真能抓住原缺陷。
3. **失败不再冒充无异常**：注入一个必然失败的桩（例如 repo 抛错）→ 返回值**可区分于**"真没异常"
   （具名字段，具体形态由设计定：`ok=False` / `detection_error=<str>` / `has_anomalies=None` 之类），
   且下游 `has_issues` 判定**不得**把它当成"数据干净"（判定为未知/降级，并留痕）。
4. **质量分不再白送 20 分**：异常率项在"检测失败"时**不得**按 0 计（按未知处置：扣分或标未知，由设计定），
   在"真有异常"时按 `total_anomalies` 计；用两个对照用例锁住（失败 vs 无异常 vs 有异常）。
5. **实跑复验**：对 ≥20 只股票抽样跑一次真实检测 → `检测异常值失败` 计数 = **0**；
   且这些股票的 `total_anomalies` **不再恒为 0**（允许为 0，但至少要有 >0 的样本，否则说明仍未生效）。
6. **既有回归不破**：`tests/test_data_quality_job_guardrails.py` 等既有用例全过；
   `detect_anomalies` 的**返回键集**保持向后兼容（三个既有字段 `has_anomalies` / `price_anomalies` /
   `volume_anomalies` / `total_anomalies` 仍在，新增字段只增不改）。

## 边界

### 做什么

1. **修迭代对象**：成交量段改用 `klines_list`（与价格段同源），使检测真正产出结论。
2. **改「吞错」语义**（本需求的核心，不是附带）：`except` 路径产出的结果必须**让上游可区分**
   「检测失败」与「确无异常」——现状是把失败写成 `has_anomalies=False` 的**肯定结论**，这是本仓
   反复踩的形态（与 a315 治过的"假成功"同族）。
3. **下游同步**：`data_quality_service.py:152`（质量问题判定）、`:469`（`has_issues`）、
   `data_validator.py:434`（质量分）三处消费点按新语义处置"未知"，并把该事实写进
   质量检查的汇总/台账（**不得静默**）。
4. **回归锁**：真 polars 用例 + 反例锁 + 失败路径用例 + 质量分对照用例。
5. **实跑复验**：抽样真跑一次，给出「error 计数 0」与「异常数不再恒 0」两份证据。

### 不做什么

1. **不做同型扫描的全仓修复**（D-2 明确排除）：全仓另有 10+ 处 `for kline in klines:` 写法
   （`data_backfiller.py:276`、`chan_service.py:220`、`strategy_code_service.py` 多处等），
   它们**未必**是同类缺陷（要看各自拿到的是 polars 还是 `list[dict]`）——本次只登记，不判定、不修。
2. **不改 `KlineORMRepository.get_daily_klines` 的返回类型**（polars 返回是既有契约，全仓多处依赖）。
3. **不改异常判定算法**（仍是 Z-score + `threshold=3.0`；不引入新统计方法）。
4. **不动 `klines.is_empty()` / `to_dicts()` 这些 polars 用法**（它们本身没问题）。
5. **不加"每日错误条数上限"这类日志限流**：修好之后本就不该有这条错误；
   若将来别的路径又刷屏，属另一个决定（登记为后续线）。
6. **不改 task 232 的排班与交易日策略**（`0 0 * * *` / `policy=holidays`，属 REQ-261006093620-a315 的已定口径）。

### 边界理由

- **为什么把「吞错」当核心而不是顺带**：只改一行，功能会好；但**下一次**换个循环写法或换数据源，
  失败又会以"数据干净"的形态静默通过——本需求的价值一半在"让它能红"。
- **为什么不扫全仓**：10+ 处逐一定性需要逐个溯源数据来源，属独立工作量；塞进来会让"修一个 bug"
  变成"一次数据层审计"，且用户已明确选了 B（D-2）。
- **为什么不动返回类型**：`get_daily_klines` 的 polars 返回被全仓多处依赖，改它属于架构级动作。

## 产品定义

### 一句话

让「数据质量检查」里那条**一直在假装正常**的判断真的跑起来——
异常该报就报，跑不成也要说"我没跑成"，而不是给出"数据很干净"的假结论。

### 为什么现在做

1. **它从来就没成功过**：`git log -L` 只追到 2026-07-21 monorepo 并入；此后该文件有 5 次改动，
   没有一次碰到这行 → 在当前仓里**异常检测输出恒为"无异常"**。
2. **代价已经落在读数上**：质量分 20% 的权重恒得满分（今日 `95.01` 里含这白送的 20 分）；
   「有问题的股票」清单少了"仅异常"这一路信号（今日 748 只里不含它们）。
3. **每天还在刷屏**：每只股票一条 error，今天 4 分钟 7995 条——把真错误淹在噪音里
   （本仓 CLAUDE.md 的「失败要响亮」被这条噪音反向削弱）。
4. **修复面小、可当天收口**：一行改 + 一处 except 语义 + 三条用例 + 一次抽样复跑。

### 成功长什么样

- `detect_anomalies('600519.SH', …)` 返回真实结论：正常股票 `total_anomalies=0` 且**无 error 字段**；
  含异常样本 `total_anomalies ≥ 1` 且列出日期与 z_score。
- 日志里**不再出现** `检测异常值失败`（今日基线：7995 条/4 分钟）。
- 注入失败时：返回值可区分"未知"，下游 `has_issues` / 质量分**不把未知当干净**，且留下可见痕迹。
- 质量分的异常率项**不再恒得满分**（有异常就扣分、检测失败按未知处置）。

## 用户与角色

- **项目所有者（人类）**：判断标准是"质量分不再白送 20 分、日志不再刷屏、异常真的报出来"。
- **窗口 AI Agent（本需求实施者）**：改动集中在 `data_validator.py` 一个方法 + 三处消费点语义 + 用例。
- **后续维护者 / 新会话**：需要一条明确规则——**"检测没跑成"不得写成"检测结果为正常"**；
  任何 `except` 返回**肯定结论**的写法都属同类缺陷（本需求是第一个被点名的，不是最后一个）。

## 功能点（G2 条款）

**FR-1: 成交量异常检测必须真正运行**
`detect_anomalies` 的成交量循环改用 `klines_list`（`to_dicts()` 的 `list[dict]`，与价格段同源），
使该判断在 K 线 ≥30 行时**不再抛错**；返回 `volume_anomalies` 与计入 `total_anomalies`。
判据：真 polars 用例（含人造成交量尖峰）→ `volume_anomalies` 非空、`total_anomalies ≥ 1`；
改前同用例必须红（反例锁）。

**FR-2: 失败不得冒充「无异常」（本需求的语义核心）**
`except` 路径的返回值必须让调用方**可区分**三种状态：**确无异常** / **有异常** / **检测失败（未知）**；
具名载体由设计定（如新增 `ok: bool` 或 `detection_error: Optional[str]`），
但**不得**再用 `has_anomalies=False` 单独表达"失败"。既有键 `has_anomalies` / `price_anomalies` /
`volume_anomalies` / `total_anomalies` 保持存在（向后兼容）。

**FR-3: 下游消费点按三态处置并把未知留痕**
三处消费点须显式处置"未知"，**不得**当成"干净"：
① `data_quality_service.py:152-190`（单股质量问题）② `:469-481`（`has_issues` 汇总）
③ `data_validator.py:434-437`（质量分异常率项）。
"未知"必须写进质量检查的汇总/台账（可见、可数），而不是只留一条 error 日志。

**FR-4: 质量分的异常率项不得白送满分**
`get_data_quality_score` 的异常率项：**有异常**按 `total_anomalies` 计；
**检测失败（未知）**不得按 0 计（按未知处置，具体扣分/标注由设计定）；
并保证今日那种"恒 0"不可能再出现（用例锁：失败 vs 无异常 vs 有异常三态对照）。

**FR-5: 回归锁与实跑复验**
新增用例至少覆盖：真 polars ≥30 行（正/负例）、反例锁（改前红）、失败路径可区分、
质量分三态对照、返回键集向后兼容；
并对 ≥20 只股票真跑一次抽样，产出「`检测异常值失败` = 0 条」与「`total_anomalies` 不再恒 0」两份证据。

## 现状取证（2026-10-06 实测）

| 编号 | 证据 |
|---|---|
| E1 | **报错形态**：`logs/api.log` 00:01:50–00:04:24 共 7995 条 `application.services.data_validator` error「检测异常值失败: cannot select elements using Sequence with elements of type 'str'」；同批另有 294 条 `data_backfiller`「All data providers failed」（**另一件事**，不在本需求） |
| E2 | **根因代码**：`application/services/data_validator.py:356` 价格段用 `klines_list`；`:369` 成交量段用 `klines`（polars DataFrame）；`:341` 定义 `klines_list = klines.to_dicts()` |
| E3 | **完整 traceback（本机复现）**：`:370 float(kline['volume'])` → `polars/series/series.py:1485 __getitem__` → `polars/_utils/getitem.py:76 TypeError: cannot select elements using Sequence with elements of type 'str'` |
| E4 | **复现命令**：`DataQualityService().validator.detect_anomalies('600519.SH','2026-07-01','2026-10-06')`（默认 repo = `KlineORMRepository`，返回 polars；62 行数据）→ 抛 TypeError |
| E5 | **失败被吞成"干净"**：`:389-396` `except` 返回 `{'has_anomalies': False, 'price_anomalies': [], 'volume_anomalies': [], 'total_anomalies': 0, 'error': str(e)}` —— 注意 `has_anomalies=False` 是**肯定结论**，`error` 字段虽在，但三处消费点都不读它 |
| E6 | **消费点**：`data_quality_service.py:152`（取 `has_anomalies`/`total_anomalies` 进 `stocks_with_issues`）、`:469-481`（`has_issues` 判据之一）、`data_validator.py:434-437`（质量分异常率项 20 分） |
| E7 | **零测试覆盖**：全仓无一条用例用真 `DataValidator` + polars DataFrame 调 `detect_anomalies`；`tests/test_data_quality_job_guardrails.py:165` 是**替身 stub**（`def detect_anomalies(self, symbol, ...)` 直接返回固定值）；`tests/test_anomaly_detection_stage.py` 属回测阶段另一物 |
| E8 | **历史**：`git log -L 369,370:application/services/data_validator.py` 只追到 2026-07-21 的 monorepo 并入提交；该文件此后 5 次改动（最近 `4a2ddbdb` 修线上 500）均未触及此行 |
| E9 | **同型写法清单（只登记，不判定）**：全仓另有 10+ 处 `for kline in klines:` / `for k in klines:`：`data_backfiller.py:276`、`chan_service.py:220`、`strategy_code_service.py:1456/1518/1623/1668/1939/1955/2051` 等；是否同病取决于各自数据来源是 polars 还是 `list[dict]` |
| E10 | **今日运行读数（受影响面）**：task 232 扫 5686 只、`data_quality_score=95.01`、`stocks_with_issues=748`、`total_missing_days=28369`；其中「异常率」这一路信号恒为 0 |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1（不是"每天都错"）**：只有当 K 线 **≥30 行**才走到成交量段（`:331` 不足 30 行会提前返回），
  所以新股/长停股不受影响；但全市场绝大多数股票都 ≥30 行 → 实际是"几乎全量失败"。
- **R2（修好之后读数会变差，这是好事）**：质量分会**下降**（异常率不再白送）、
  「有问题的股票」数会**上升**（多出"仅异常"那一类）。这不是回归，是此前的读数虚高。
- **R3（异常本身的业务价值有限，但不该是"假"）**：Z-score>3 多为除权、停牌复牌、真实异动等，
  本仓已有专门处理；本需求的诉求是**读数真实**与**失败可见**，不是把异常当交易信号。
- **R4（另一条噪音不属本需求）**：同批 294 条 `data_backfiller`「All data providers failed」
  与休市日回补有关，独立登记（已见于 REQ-261006130750-0654 的后续线）。

## 接口与数据契约

- **对外接口**：无新增/变更（无 HTTP、无 CLI）。
- **函数契约**：`DataValidator.detect_anomalies(symbol, start_date, end_date, threshold=3.0) -> Dict`
  - **保持**：既有四键 `has_anomalies` / `price_anomalies` / `volume_anomalies` / `total_anomalies`
    继续存在且含义不变（`has_anomalies` 仅在"真的检测过且无异常"时为 `False`）。
  - **新增（形态由设计定稿）**：表达"失败/未知"的具名字段（建议 `ok: bool` + `detection_error: Optional[str]`）。
  - **错误语义**：方法**不抛**（既有约定），但失败必须**可被上游识别**。
- **数据契约**：不新增表/列/迁移；质量检查结果里"未知"的承载方式（汇总计数或台账字段）
  由设计定，但必须**可见**（FR-3）。
- **兼容/回滚**：纯代码改动；回滚 = 还原提交（回滚后行为回到"假阴性 + 7995 条日志"）。

## 判定标准（可跑）

> 命令均在仓根、用 `./venv/bin/python` 执行；新增用例文件名在拆分阶段定稿
> （建议 `tests/test_data_validator_anomaly_detection.py`）。

1. **新增用例**：`./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q` → 全过。
2. **既有回归**：`./venv/bin/python -m pytest tests/test_data_quality_job_guardrails.py -q` → 全过。
3. **复现（改前必错、改后必对）**：
   ```
   ./venv/bin/python -c "from application.services.data_quality_service import DataQualityService as D; \
   print(D().validator.detect_anomalies('600519.SH','2026-07-01','2026-10-06'))"
   ```
   改前：含 `error` 且 `total_anomalies=0`（TypeError 被吞）；改后：**无 error**，字段齐全。
4. **反例锁**：在改前的代码上跑新增用例必须红（记录到卡片汇报里，作为"这条锁真能抓"的证据）。
5. **实跑复验（抽样 ≥20 只）**：
   ```
   ./venv/bin/python -c "…遍历 20 只调用 detect_anomalies…"
   grep -c "检测异常值失败" logs/api.log        # 复验窗口内的新增条数 = 0
   ```
   并输出"样本 `total_anomalies` 分布"（不得全为 0）。
6. **下游语义**：注入失败桩后，`data_quality_service` 的汇总里出现"未知/失败"计数
   （具体字段名设计定），且质量分**不因"未知"而按满分计**。

## 档位依据与升级信号

- **档位 = expert**：立项弹框作答（feature / expert，见 D-1/D-2）。
  实质难点：① 修 bug 只是十分之一，**"失败不得冒充结论"的语义改造**要动三处消费点的判断；
  ② 改完读数会变差（R2），验收时必须先接受"读数变真"这个前提，否则会被当成回归打回；
  ③ 需要 polars/pandas 双形态的构造能力才能写出真的反例锁。
- **升级信号**：若设计阶段发现"未知"必须贯穿到**数据契约**（例如质量检查结果表要加列），
  则范围升级为含一次迁移，须在设计文档显式登记并回需求确认。

## 后续线（本次不做，仅登记）

1. **同型扫描**：全仓 10+ 处 `for kline in klines:`（E9）逐一定性——哪些拿的是 polars DataFrame。
2. **`data_backfiller` 的 294 条「All data providers failed」**（休市日回补），独立缺陷。
3. **错误日志风暴的结构性防线**：本次修好后应无此风暴；是否要为"每标的失败"加聚合/限流，
   属另一个决定（不顺手加）。
4. **质量读数口径复盘**：异常率项恢复后，历史质量分与"有问题的股票"清单需要重新解读
   （此前含白送的 20 分）。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 本窗口会话消息（2026-10-06，用户直接消息）原话：「继续」 | 由「报错了」继续下钻：查明今日 7995 条报错的根因并按需立项 | FR-1、FR-2 | 根因 traceback 已存档（E3）；本需求已立项并绑定本窗口（REQ-261006133733-1fdf） |
| D-2 | 本窗口会话消息（2026-10-06，用户回答修复边界弹框）原话：「B：一行修 + 错误不再被吞成「无异常」 + 回归锁（推荐）」 | 范围锁定 B：一行修 + 吞错语义改造 + 回归锁 + 实跑复验；**同型扫描不入范围**（进后续线 1） | FR-1、FR-2、FR-3、FR-4、FR-5 | `ask_user_question` 返回 `selected=["B：…"]`（单选）；排除项落账见边界「不做什么」1 与后续线 1 |

## 下一步

**design** —— 用 `reqboard_ask_confirm(target=artifact, kind=requirement)` 请人确认本需求文档；
获确认后 `reqboard_move` 到 design（设计文档写进 `docs/requirements/REQ-261006133733-1fdf/design/`）。
（本节点不建任务卡、不写设计。）

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-0a6461、t-b1dd5c、t-420a52 |
| FR-2 | ✅ 已接收 | t-0a6461、t-b1dd5c |
| FR-3 | ✅ 已接收 | t-163105、t-b1dd5c |
| FR-4 | ✅ 已接收 | t-0a6461、t-163105、t-b1dd5c |
| FR-5 | ✅ 已接收 | t-b1dd5c、t-420a52 |

> 无未接收条款（5 条全部有落点）。

<!-- reqboard:marks:end -->
