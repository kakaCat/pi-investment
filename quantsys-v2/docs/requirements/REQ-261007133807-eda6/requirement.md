---
sides: [backend]
---

# REQ-261007133807-eda6 · 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

**需求ID**: REQ-261007133807-eda6
**类型**: feature
**作用域**: `quantsys-v2/`（`domain/watch/services/{escalation_checker,disposition,level_resolver}.py`、`application/services/watch_engine/{engine,escalation_coordinator,disposition_engine,notifier,dto}.py`、`application/notification/notification_facade.py`、`infrastructure/notification/formatters/feishu_formatters.py`、`adapters/outbound/repositories/watch_rule_repository.py`、`adapters/inbound/fastapi_app/routes/watch_async.py`、`infrastructure/persistence/migrations/`、`docs/architecture/watch-notification-contract.md`、`tests/`）
**侧**: backend（产物是判定链路 + 库里可查的理由码 + 飞书卡片文案；无前端页面产出，不交原型）
**档位**: 重档（改判定口径 + 改卡面契约 + 新增落库列；依据见文末「档位依据与升级信号」）

## TL;DR

**2026-10-07 用户原话：「③ L1 是agent设置的，也应该设置何时调用agent的规则」**（该句原属 `REQ-261007101318-c392` 的裁定 D-10，被排除并另立为本需求）。

要回答的问题是**一句人话**：*这条盯盘触发，为什么叫了 agent / 为什么没叫？* 今天这句话**没有单一入口能回答**：

```
        今天「叫 agent」的判定分布（读码实测）
  +--------------------------+      +--------------------------------------+
  | EscalationChecker        |      | disposition.decide() 规则 3          |
  | 三条路径（REQ-c9f899 t7  |      | trigger_level == 'L2' → escalated    |
  | 收敛后）：规则显式 escalate|      | （完全另一条路，不经 EscalationChecker）|
  | 宪法级 exit_stop          |      +--------------------------------------+
  | 异常波动 |涨跌幅| ≥ 5%     |                    |
  +--------------------------+                    |
        |  只对 L0/L1 生效（escalation_coordinator 第 33 行短路）  |
        v                                          v
  +---------------------------------------------------------------+
  | disposition.decide() → (disposition, reason 自由文本)          |
  |   预算门 / 五道门 / 去重 …… 每一处的"没叫"也在这里收口          |
  +---------------------------------------------------------------+
        |  reason 只被折进 disposition_reason 一段中文；卡面只把它当布尔用
        v
  +---------------------------------------------------------------+
  | 卡面：🔔 需决策 / ⚡ AI 介入（标签变了）——**理由正文从不出现**    |
  +---------------------------------------------------------------+
```

**本需求要做的**（用户 2026-10-07 17:1x 弹框裁定「A 判定收敛 + 可见化」）：

1. **判据收敛**：把「叫 / 不叫 agent」收成**一个**裁决出口，输出**枚举理由码 + 人话理由 + 命中路径**，
   三处判定（`EscalationChecker` 三条路径、`disposition` 的 L2 规则、预算/门的"没叫"）全部经它产出；
2. **可见化**：理由码**落库**（一条 SQL 可查）、**上卡面**（写清这次为什么叫）、**规则侧显式**（规则上看得出什么条件会叫我）。

> ⚠️ 本需求**不新增任何唤醒量**：它让"叫与不叫"变得可查可读，不放松也不收紧既有判据的阈值口径。

## L1 一句话目标 + 可证伪判定标准

**目标**：「什么时候该叫 agent」有**唯一事实源**——同一输入无论从哪个调用方问，都得到同一个 `(是否叫, 理由码, 理由, 命中路径)`；且这个结论在库里查得到、在卡上读得到、在规则上看得见。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：

1. **单一口径（FR-1）**：同一组 `(rule, condition, quote, result, gate)` 输入，
   经引擎 tick、复核作业、补跑脚本三个调用方得到的 `(是否叫, 理由码, 命中路径)` **逐字段相同**；
   且全仓不存在第二处独立的「`trigger_level == 'L2'` → 叫 agent」判定。
2. **理由码全覆盖（FR-2）**：一次触发后一条 SQL 能同时回答"叫没叫"与"为什么"；
   **"没叫"也必须带码**（预算耗尽 / 观察类 / 金额门 / 增量门 / 经济门 / 去重合并），不得留空。
3. **卡面可读（FR-3）**：规则显式升级 / 宪法级止损 / 异常波动三条路径产出的卡片，
   正文**必须各带一条可区分的「升级原因」**；无升级时**不臆造**该行（宁缺勿造）。
4. **规则侧显式（FR-4）**：新建规则不传 `escalation_policy` 时，库里落的是**显式默认值**（不再是 NULL/空）；
   规则查询能读到人话版的「什么条件会叫我」；**旧规则不改也照常跑**（向后兼容）。
5. **文档与代码同源（FR-5）**：`opportunity_to_watch_rule_service.py` 那句「触发频率异常时升级」不得再存在；
   `docs/architecture/watch-notification-contract.md` 的判据表与代码枚举**同源**（改一处必须改另一处）。
6. **不破现状**：`pytest tests/services/test_escalation_checker.py tests/services/test_metric_contract.py tests/application/test_watch_disposition.py tests/application/test_watch_disposition_engine.py tests/services/test_watch_engine.py -q` 全过，
   且**唤醒量不增**（同输入下 `disposition == 'escalated'` 的条数与改造前一致）。

## 边界

### 做什么

1. **单一裁决出口（FR-1）**：把「叫 / 不叫 agent」的判定收敛到**一个**纯函数出口，
   输出结构化裁决（至少含：`是否叫`、`理由码`（受控枚举）、`人话理由`、`命中路径`）；
   现有 `EscalationChecker` 的三条可信路径与 `disposition.decide()` 的第 3 条（L2 规则）都必须**经它产出**，
   禁止任何调用方另起一处 `trigger_level == 'L2'` 判定；预算门 / 五道门 / 去重等"没叫"的结论同样必须在同一出口给出码。
2. **理由码落库（FR-2）**：每次触发把 `理由码 + 人话理由 + 命中路径` 落到 `quant.watch_triggers`
   （新列，名字以 design 为准），使「这次为什么叫了/没叫」**一条 SQL 可查**；
   `escalated` 之外的处置（`deduped` / `auto_observed` / `pending` …）也必须带码，不许留 NULL。
3. **卡面写理由（FR-3）**：飞书盯盘卡正文**追加**「升级原因」行（命中路径 + 人话理由）；
   `REQ-261007101318-c392` 已定的四段契约（触发事实 / 意图 / 级别 / 下一步）**保持不变**，本需求只做追加；
   分级渲染路径（`watch_level_templates`）与旧渲染路径（`feishu_formatters`）**两条都必须写**，不许只补一条。
4. **规则侧显式化 + 只读回显（FR-4）**：创建/修改规则的入口（`POST/PUT/PATCH /api/watch/rules`、批量接口）
   在缺省时把**生效策略写成显式值**（默认可覆写）；查询接口在**不破坏原字段**的前提下，
   追加人类可读的「什么条件会叫我」说明；未显式声明的**存量规则不拒**、仍按既有默认口径运行。
5. **文档同源（FR-5）**：修正陈旧 docstring（`opportunity_to_watch_rule_service.py:17` 等把已删路径写成现行规则的文案），
   并把判据表写进 `docs/architecture/watch-notification-contract.md`（该文件 §6 已挂着指向本需求的指针）。

### 不做什么

1. **不新增、不恢复任何被删除的历史升级路径**（触发频率 / 量能异常 / 价格偏差 / 核心区域 / 多规则共振）——
   它们在 `REQ-c9f899 t7` 被逐条实证为不可信，本需求只做**收敛与可见化**，不复活它们。
2. **不改既有判据的阈值口径**：异常波动默认 5%（`DEFAULT_ANOMALY_CHANGE_PCT`）、每日介入预算 8、
   金额门 1% / 增量门 4h / 经济门 k=3 一律照旧；本需求不放松也不收紧。
3. **不定义 L0/L1/L2 三档的新含义**：L2 = 行动层（买卖节点必须 agent 终判）沿用既有定义，
   本需求只保证它**在同一个出口被判、并把理由说出来**。
4. **不做前端 / 看板页面**（side=backend，不交原型）：卡片是飞书 Markdown 文本，不是本仓前端页面。
5. **不合并各仓飞书机器人、不改 agent 侧（agent-ts）的规则创建实现**：本需求只覆盖 v2 侧的判定、落库、卡面与 API。
6. **不引入"自动下单 / 自动处置"**：盯盘引擎仍只做"判定 → 落库 → 通知"，绝不产生委托（既有铁律）。
7. **不做规则治理**（重叠规则 / 阈值失真 / 静默去重）：属 `REQ-f08def` 系列既有范围。

### 边界理由

- **为什么必须收敛到一个出口，而不是"再写一份说明文档"**：用户问的是**因果**（"为什么叫了"），
  而今天的因果分散在两处判定（E1）且第三处（`level_resolver`）只做级别映射——
  文档式回答会在下一次改判据时立刻失真（这正是 E6 陈旧文案的成因）。
  只有让**判定本身**产出结构化的理由，理由才不会再漂移。
- **为什么"没叫"也要有码**：用户硬约束是"不能所有触发都叫 agent——成本必须与利润一致"（`disposition.py` 首注）。
  只记录"叫了"的理由，等于把**成本控制**这条主线留成黑盒：预算压掉了几次、为什么压，事后无人能答。
- **为什么卡面是追加而不是重写**：`REQ-261007101318-c392` 的四段卡面契约刚经用户裁定（其 D-9「这个卡片同意」），
  在同一张卡上重写契约等于让已验收的东西重新验收；追加一行「升级原因」是**纯增益**。
- **为什么规则侧必须先兼容存量**：实测 7 条存量规则**全部**没有 `escalation_policy`（E4），
  若改成"未声明即拒"，等于把线上存量规则一次性判死——这不是收敛，是爆破。

## 产品定义

### 一句话

「什么时候该叫 agent」是一份**可查的裁决**，而不是散落在两份代码里的默认行为：
叫与不叫都要给得出理由码，理由要在库里查得到、在卡上读得到、在规则上看得见。

### 为什么现在做

1. **同一个问题已经逼出过一次全盘取证**：`REQ-261007101318-c392` 里"这张卡让买让卖、还是交给 agent"
   的疑问，根因之一就是**级别与理由不可见**；该需求只做到"如实呈现级别"，
   判据本身的收敛被显式排除（其 D-10）并指向本需求。
2. **判据分散导致"改了不知道改哪"**：`EscalationChecker` 与 `disposition` 各自判一次"叫 agent"（E1），
   `level_resolver` 第三处把 `L2` 映成 `P1`（E1）——三处必须同时改对，才不发散。
3. **理由已被算出来，却半途丢弃**：`escalation_reason` 一路传到渲染层，只被当成布尔用于选标签（E2）——
   成本最高的那一步（判定）已经做完，收益（可读）却漏在最后一米。
4. **文档已经在说假话**：`opportunity_to_watch_rule_service.py:17` 仍写「触发频率异常时升级L2」，
   而该路径 2026-09-18 已删除（E6）——文档成了第二事实源，且是错的那个。

### 成功长什么样

1. 用户看到一张盯盘卡时，除了"要不要动作"，还能看到**这次为什么叫了我**（或为什么没叫）。
2. 排障时**一条 SQL** 回答"这条触发为什么叫/没叫"，不用再读代码、翻日志。
3. agent 建规则时，"什么条件会叫我"是**写下来的**，不是从默认值里猜的。
4. 改判据只改**一个**地方，文档与卡面不会各自漂移。

## 用户与角色

| 角色 | 关心什么 | 本需求给他的东西 |
|---|---|---|
| 投资人（人） | 这条触发为什么打扰我、要不要动手 | 卡面「升级原因」行：命中路径 + 人话理由；无升级则不臆造 |
| 投资脑（agent） | 该不该处置、判据是否可信 | 单一裁决出口 + 枚举理由码；规则侧显式声明"何时叫我"，不再靠默认值猜 |
| 运维/排障者 | 复发时能否一条查询定位 | `quant.watch_triggers` 的理由码列：「叫没叫 + 为什么」一条 SQL 可查（含"没叫"的码） |
| 后续开发者 | 改判据会不会漏改一处 | 判据收敛到一个出口 + 文档判据表与代码枚举同源（FR-5） |

## 功能点（G2 条款）

- **FR-1: 「叫 / 不叫 agent」收敛为单一裁决出口（含枚举理由码）**
  必须存在**唯一**出口回答"这条触发要不要打断 agent"，返回结构化裁决：
  `是否叫`（bool）、`理由码`（受控枚举）、`人话理由`（str）、`命中路径`（来源标识，如 规则显式/宪法级/异常波动/规则分级L2/预算门/观察类/金额门/增量门/经济门/去重合并）；
  `EscalationChecker` 的三条可信路径与 `disposition.decide()` 的 L2 规则**都必须经它产出**；
  **禁止**任何调用方另起一处 `trigger_level == 'L2'` 的叫醒判定（级别→P 档的映射仍可保留，但不得独立决定"叫不叫"）；
  该出口必须为**纯函数**（无 I/O、无外部状态），同一输入必得同一裁决。

- **FR-2: 裁决结果落库——「为什么叫/没叫」一条 SQL 可查**
  每次触发落库时写入 `理由码 + 人话理由 + 命中路径`（`quant.watch_triggers` 新增列，列名与类型以 design 为准）；
  **覆盖全部处置结局**：`escalated` / `pending` / `deduped` / `auto_observed` 一律带码，不得留 NULL；
  历史行保持 NULL 并显式解释为"改造前未记录"（不做回填臆造）；写库失败**不得阻断**通知与记账，但必须响亮留痕。

- **FR-3: 卡面显式写出升级理由（两条渲染路径都写）**
  飞书盯盘卡正文追加「升级原因」行，内容 = 命中路径 + 人话理由；
  旧渲染路径（`feishu_formatters`）与分级渲染路径（`watch_level_templates`）**都必须写**；
  无升级理由时**隐藏该行**（不臆造、不写空）；
  与 `REQ-261007101318-c392` 的四段契约（触发事实 / 意图 / 级别 / 下一步）**并存不替换**。
  **判据**：`pytest tests/notification -q -k "escalation or reason"` 全绿；规则显式升级 / 宪法级止损 / 异常波动三条路径产出的卡正文各含一条**可区分**的「升级原因」行（分级与旧渲染两条路径各至少 1 条用例）；无升级理由时该行**不出现**。

- **FR-4: 规则侧显式化 + 只读回显（兼容存量）**
  创建/修改规则的入口在缺省时把**生效策略写成显式值**（可覆写，默认 = `auto_escalate=true` + 异常波动阈值取 checker 默认值），
  使"什么条件会叫我"在规则上**看得见**；查询接口**追加**（不替换）人类可读的「何时会叫我」说明字段；
  **存量规则不拒**：未显式声明的旧规则仍按既有默认口径运行，语义不变。
  **判据**：新建规则**不传** `escalation_policy` 时，`psql -c "select escalation_policy from quant.watch_rules where id=<新id>"` 读回**非空**且等于显式默认值（`auto_escalate=true`）；`GET /api/watch/rules` 响应含人类可读的「何时会叫我」字段；存量 7 条未声明规则的触发处置与改造前**逐字段一致**。

- **FR-5: 判据文档与代码同源（修陈旧文案 + 落判据表）**
  `opportunity_to_watch_rule_service.py` 等处的「触发频率异常时升级」一类**已被删除路径**的表述必须清除；
  「何时叫 agent」的判据表写进 `docs/architecture/watch-notification-contract.md`，
  且与代码中的理由码枚举**同源**（枚举改名必须同步文档，改一处必须改另一处）。

## 现状取证（2026-10-07 实测）

| 编号 | 结论 | 证据（可复现） |
|---|---|---|
| E1 | **「叫 agent」判据分散在两处判定 + 一处级别映射**：`EscalationChecker` 三条路径（规则显式 / 宪法级 `exit_stop` / 异常波动 ≥ 阈值）；`disposition.decide()` 第 3 条 `trigger_level=='L2'` → escalated；`level_resolver` 第 4 条又把 `L2` 映成 P1 | [escalation_checker.py:62-69](/Users/mac/Documents/ai/pi-investment/quantsys-v2/domain/watch/services/escalation_checker.py#L62-L69)（三条路径）、[disposition.py:161-168](/Users/mac/Documents/ai/pi-investment/quantsys-v2/domain/watch/services/disposition.py#L161-L168)（L2 规则路径）、[level_resolver.py:128-130](/Users/mac/Documents/ai/pi-investment/quantsys-v2/domain/watch/services/level_resolver.py#L128-L130)（L2→P1） |
| E2 | **升级原因算出来了，卡面只把它当布尔用**：`escalation_reason` 只用于选标签（`🔔 需决策` vs `⚡ AI 介入`）与是否简化预案，**理由正文从不出现**；全仓消费方仅此一处 | [feishu_formatters.py:74-85](/Users/mac/Documents/ai/pi-investment/quantsys-v2/infrastructure/notification/formatters/feishu_formatters.py#L74-L85)、[:116](/Users/mac/Documents/ai/pi-investment/quantsys-v2/infrastructure/notification/formatters/feishu_formatters.py#L116)；`grep -rn escalation_reason infrastructure/notification/formatters/watch_level_templates.py` → **0 命中** |
| E3 | **两条判定互不知情**：协调器只对 `L0/L1` 调 checker，`L2` 直接短路为"不升级"，随后由 `disposition` 的 L2 规则叫醒——同一件事两条路 | [escalation_coordinator.py:33-35](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/escalation_coordinator.py#L33-L35) |
| E4 | **规则侧全空（存量实测）**：7 条规则中 `escalation_policy` **有值 0 条**（非空 JSONB 0 条），`action_hint.trigger_level` 与 `intent` 同样为空 | `psql -h 127.0.0.1 -U mac -d quant_investment -c "select count(*) total, count(escalation_policy) with_policy, count(*) filter (where escalation_policy::text not in ('{}','null')) non_empty from quant.watch_rules;"` → `7 \| 0 \| 0`；`select id,symbol,action_hint->>'trigger_level',escalation_policy,intent from quant.watch_rules` → 全空 |
| E5 | **库里结构上不带「为什么」**：触发表只有 `disposition` + 自由文本 `disposition_reason`；本机 89 条触发里 **82 条连 `disposition` 都是 NULL**，`escalated` **0 条** | `psql ... -c "select disposition, count(*), count(disposition_reason) from quant.watch_triggers group by 1;"` → `(NULL) 82 \| 0`、`meta_review 7 \| 7`、`escalated` 无行；列定义见 [watch_rule_repository.py:88-102](/Users/mac/Documents/ai/pi-investment/quantsys-v2/adapters/outbound/repositories/watch_rule_repository.py#L88-L102) |
| E6 | **文档在说已被删除的路径**：`opportunity_to_watch_rule_service.py:17` 写「价格偏差>5%或**触发频率异常**时升级L2」，而本模块同一段已注明收敛只留总开关 | [opportunity_to_watch_rule_service.py:17](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/opportunity_to_watch_rule_service.py#L17) vs [models.py:73-77](/Users/mac/Documents/ai/pi-investment/quantsys-v2/domain/watch/models.py#L73-L77) |
| E7 | **理由只被折进一段中文自由文本**：`escalation_reason` 仅在 `escalated` 分支被拼进 `disposition_reason`（`｜原始原因：…`），且落库路径 `WatchTriggerRepository.record(...)` **不接受**任何升级理由/码参数 | [disposition.py:162-164](/Users/mac/Documents/ai/pi-investment/quantsys-v2/domain/watch/services/disposition.py#L162-L164)；[watch_rule_repository.py:295-298](/Users/mac/Documents/ai/pi-investment/quantsys-v2/adapters/outbound/repositories/watch_rule_repository.py#L295-L298)；notifier 落库只写 `{'value','message'}`（[notifier.py:344-356](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/notifier.py#L344-L356)） |
| E8 | **没有「为什么」的查询入口**：watch 路由共 12 条，无 explain/why 类接口，也没有单规则详情 GET（只有列表 + 批量 + 触发器查询） | `grep -n "@router\." adapters/inbound/fastapi_app/routes/watch_async.py` → 28/54/139/144/149/166/177/207/227/252/331 行；`/api/watch/rules/{rule_id}` 仅 PUT/PATCH/DELETE |
| E9 | **级别语义与唤醒解耦后，理由反而更不可见**：`notifier._build_payload` 在有 `escalation_reason` 时把 `trigger_level` 强制改成 `L2`，于是"规则本来就是 L2"与"因升级才变 L2"在卡面上**同形** | [notifier.py:280-282](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/notifier.py#L280-L282) |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1**：理由**不是完全不可考**——`escalated` 分支确实把「原始原因」拼进了 `disposition_reason`（E7）。
  本需求要的是**结构化 + 覆盖全部结局 + 可见**，不是"从零造一套日志"。
- **R2**：判定链已有一个较干净的出口形态——`disposition.decide()` 本就返回 `(disposition, reason)`（[disposition.py:137-140](/Users/mac/Documents/ai/pi-investment/quantsys-v2/domain/watch/services/disposition.py#L137-L140)）。
  收敛是**把它补成全量 + 加码**，不是推翻重写；这也是本需求能保持"唤醒量不增"的原因。
- **R3（强度限定）**：E4/E5 的库读数来自本机 `quant_investment`（7 条规则 / 89 条触发，`escalated` 0 条），
  **样本小且不必然等同生产库**——它只能证明"库里结构上不带理由码、存量规则全无策略"，
  **不能**据此推断"线上从未唤醒过 agent"。凡引用库读数，一律按此强度限定。
- **R4**：`EscalationChecker` 的三条路径本身是**可信的收敛结果**（`REQ-c9f899 t7` 逐条实证删除五条历史路径），
  本需求**不质疑**这三条；不要在实施中顺手"优化"它们。

## 失败与并发路径

### 失败路径

1. **判据输入不合法 → 响亮抛错，不得静默归档**：沿用 `require_metric` 契约（[escalation_checker.py:107-111](/Users/mac/Documents/ai/pi-investment/quantsys-v2/domain/watch/services/escalation_checker.py#L107-L111)）——
   metric 不符时**抛错**，绝不把"算不出涨跌幅"降级成"不升级"。
2. **理由码落库失败 → 不阻断通知/记账，但响亮留痕**：沿用既有 at-least-once 语义（通知失败下个 tick 重试），
   理由列写失败只记 `logger.error`，不得让通知或触发记账失败。
3. **理由码未知/缺失 → 显式输出 UNKNOWN，禁止臆造**：枚举里没有的输入一律返回 `UNKNOWN` 码并保留原始文本；
   卡面遇未知码时**显示码本身**，不隐藏、不编一句像理由的话。
4. **迁移失败/漏跑 → 由既有漂移门禁兜住**：新增列走 `infrastructure/persistence/migrations/`，
   **两个库都跑**并带 `lock_timeout`（本仓既有要求，[CLAUDE.md 同节](/Users/mac/Documents/ai/pi-investment/quantsys-v2/CLAUDE.md)），
   否则 `tests/test_orm_db_drift.py` 会红。

### 并发重复

1. **裁决是纯函数**：同一 `(rule, condition, quote, result, gate)` 无论被引擎 tick、补跑脚本还是复核作业调起，
   `(是否叫, 理由码, 命中路径)` 必须逐字段相同（判据 1 的并发版）。
2. **同一触发被多路径调起 → 理由码与处置同源**：去重/预算先命中即返回，其码必须写出（`deduped` / `budget_exhausted`），
   不得因为"已被别的调用方处理"而留 NULL。
3. **落库写入并发**：`watch_triggers` 是"一触发一行"，理由列随该行写入，不存在跨行更新竞争；
   若 design 阶段改为独立裁决表，则必须在该表上定义幂等键（同触发同键只写一次）。

### 状态机非法迁移

**不适用：本需求不改 `watch_triggers.disposition` 的状态机**（取值集合与迁移规则照旧），
只新增理由列的写入与读取；处置状态仍由 `disposition.decide()` 产出、由既有处置接口推进。

## 接口与数据契约

| 接口/对象 | 现状 | 本需求后 | 兼容性 |
|---|---|---|---|
| 裁决出口 | `EscalationChecker.should_escalate(...) -> Optional[str]`（只覆盖 L0/L1 三条路径）+ `disposition.decide(...) -> (disposition, reason)`（另一处） | **单一出口**：输入 `(rule, condition, quote, result, gate)` → 输出 `(是否叫, 理由码, 人话理由, 命中路径)`；三处判定全部经它产出 | 内部接口，调用方收敛到一处；纯函数，可单测、无 I/O |
| 理由码枚举 | 不存在（只有中文自由文本） | 受控枚举（含"叫"与"没叫"两侧，至少覆盖 E1/E7 列出的全部路径） | 新增；枚举值是**受控词表**，改名必须同步 FR-5 的文档判据表 |
| `quant.watch_triggers` | `disposition` / `disposition_reason`（自由文本），无理由码列；`record()` 不接受理由参数 | 新增 `理由码 + 人话理由 + 命中路径`（列名/类型/是否 JSONB 以 design 为准） | 新增 nullable 列；历史行 NULL = "改造前未记录"；通知与记账**不依赖**新列即可工作（回滚 = 停写） |
| `POST/PUT/PATCH /api/watch/rules`（含批量） | `escalation_policy` 可选，缺省不写（实测存量 7 条全 NULL） | 缺省时写**显式默认值**（可覆写） | 语义收紧：缺省从"无声明"变"显式默认"；**老调用方无须改**，未声明不拒 |
| `GET /api/watch/rules` | 原样返回 `escalation_policy` JSON | **追加**人类可读的「何时会叫我」说明字段 | 纯追加字段，向后兼容；不改原字段语义 |
| 飞书卡正文 | 升级理由只影响标签，正文无理由行；两条渲染路径都不写 | 追加「升级原因」行（命中路径 + 人话理由）；无升级则隐藏 | 追加不删；与 c392 的四段契约并存；**分级与旧渲染两条路径都要写** |

**迁移与回滚**：新增列走 `infrastructure/persistence/migrations/`（**两个库都跑**，带 `lock_timeout`）；
回滚 = 停写新列（列保留、通知与判定不受影响），理由码枚举与裁决出口可独立回退（调用方按旧布尔路径工作）。

## 判定标准（可跑）

```bash
# 1) 单一口径：三条升级路径 + L2 路径 + 预算/门路径在**同一出口**产出 code/path，
#    且同一输入从三个调用方得到逐字段相同的裁决
pytest tests/services/test_watch_escalation_verdict.py -q

# 2) 无第二处独立叫醒判定（收敛的结构判据）
grep -rn "trigger_level.*==.*'L2'\|=='L2'\|== \"L2\"" application/ domain/ | grep -v "level_resolver\|escalation_verdict"

# 3) 理由码落库可查（触发后一条 SQL；含"没叫"的码）
psql -h 127.0.0.1 -U mac -d quant_investment -c \
 "select triggered_at, rule_id, disposition, escalation_code, left(escalation_reason,60) \
  from quant.watch_triggers where triggered_at::date = current_date order by triggered_at desc limit 10;"

# 4) 卡面理由行：三条路径各带可区分的「升级原因」，且两条渲染路径都写
pytest tests/notification -q -k "escalation or reason"

# 5) 不破现状 + 唤醒量不增（同输入下 escalated 条数与改造前一致）
pytest tests/services/test_escalation_checker.py tests/services/test_metric_contract.py \
       tests/application/test_watch_disposition.py tests/application/test_watch_disposition_engine.py \
       tests/services/test_watch_engine.py -q

# 6) 陈旧文案归零（历史归档与需求文档除外）
grep -rn "触发频率异常" application/ domain/ docs/architecture/ | grep -v docs/requirements
```

> 判据 3 的列名以 **design** 阶段定稿为准（本文件只钉"必须有、必须覆盖没叫的结局"）。
> 判据 5 的"唤醒量不增"是**回归锁**：本需求只做收敛与可见化，任何 `escalated` 条数变化都算超范围。

## 档位依据与升级信号

**重档**，三条独立依据：

1. **改判定口径**：把两处判定收敛成一个出口，直接触碰"什么时候打扰 agent"这条决策链——
   影响所有调用方（tick / 补跑脚本 / 复核作业），必须带回归锁（判据 1、5）。
2. **改卡面契约**：卡片是**给人看的契约**，且刚经用户裁定（c392 的 D-9）——
   本需求只做追加，但两条渲染路径（分级 / 旧）必须同步，否则会出现"有时有理由有时没有"。
3. **新增落库列 + 改 API 缺省语义**：迁移要两个库都跑；规则接口的缺省语义从"无声明"变"显式默认"，
   属**对外可观测的行为变更**（虽然老调用方无须改）。

**升级信号（预先登记，供后续引用）**：

- 若实施中发现"叫/不叫"的判据需要**按规则类型分档**（例如观察类与交易类用两套预算口径），
  说明本需求的范围不足以承载，应拆出「升级判据分档」的独立需求。
- 若实施中发现规则侧显式化需要**回填存量规则**（而不只是"不改也照跑"），
  应先取得用户对回填口径的裁定，再单独立项——本需求不做存量回填。
- 若"为什么没叫"需要覆盖**引擎未触发的规则**（静默/到期类元触发），属另一条链（元触发轻门），
  本需求只覆盖"触发已发生但被压掉"的情形。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 交接方窗口用户消息（2026-10-07 13:0x，经 `REQ-261007101318-c392` 的 D-10 转记）：「③ L1 是agent设置的，也应该设置何时调用agent的规则」 | 本项**立为独立需求**（判据收敛 + 显式化 + 可见化），不在 c392 内实现 | FR-1、FR-2、FR-3、FR-4、FR-5 | 承接凭证：`reqboard_capture(on_window_bound=handoff)` 回执 `bound_policy=handoff`；本窗口 = owner `session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49` |
| D-2 | 立项五问弹框作答（本需求，2026-10-07 13:38，留痕 `comments.jsonl` c-da9a98） | 名称「「何时叫 agent」判据收敛与可见化（升级路径单一入口）」/ 类型 **feature** / 难度 **expert** / 文档落 `docs/requirements/<REQ>/` | FR-2、FR-5 | 类型与难度决定文档集与档位：本文件存在且经 `reqboard_submit(kind=requirement)` 登记（回执 `registered: true`） |
| D-3 | 本窗口弹框作答（2026-10-07 17:1x）：「A 判定收敛 + 可见化（推荐）」 | **范围 = A**：既做单一裁决出口（枚举理由码），也做理由码落库 + 卡面可见 + 规则侧显式；不选"只可见化"或"只收敛" | FR-1、FR-2、FR-3、FR-4 | 用户选项原文；本产物经 `reqboard_ask_confirm(target=artifact, kind=requirement)` 落章 |
| D-4 | 本窗口弹框作答（2026-10-07 17:1x）：「创建/修改时显式化 + 只读回显（推荐）」 | 规则侧强度：创建/修改时写**显式生效值**并可覆写 + 查询只读回显；**未显式声明的存量规则不拒**、语义不变（明确否掉"强制声明即拒"） | FR-4 | 同上；E4 实测存量 7 条策略全 NULL ⇒ 必须兼容存量 |
| D-5 | 本 agent 读码所得（E1~E9、R1~R4），供 design 阶段遵守 | ① 判定收敛到**一个**出口，禁止第三处 `trigger_level=='L2'` 独立叫醒；② 理由码**枚举 + 全量覆盖**（含"没叫"的码），不许只覆盖 `escalated`；③ 卡面是**追加行**，不得重写 c392 已定四段契约；④ **唤醒量不增**（回归锁）；⑤ 不复活已删除的五条历史升级路径 | FR-1、FR-2、FR-3、FR-5 | E1/E2/E3/E7/E9 的 file:line 取证；R2（`decide()` 已有出口形态）与 R4（三条路径本身可信） |

## 下一步

下一步：design —— 用 `reqboard_ask_confirm(target=artifact, kind=requirement)` 交棒；未获批准不得进入设计/实施。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-d24cfb、t-2f1402、t-fa9574、t-2fbc40、t-08d545、t-8097f7 |
| FR-2 | ✅ 已接收 | t-d24cfb、t-08d545、t-761703、t-fc92ab、t-8097f7 |
| FR-3 | ✅ 已接收 | t-ba3f1f、t-8097f7 |
| FR-4 | ✅ 已接收 | t-152a0b、t-9cd059、t-7c7d38、t-8097f7 |
| FR-5 | ✅ 已接收 | t-435423、t-8097f7 |

> 无未接收条款（5 条全部有落点）。

<!-- reqboard:marks:end -->
