# REQ-261016155500-4f2a: 盯盘消息决策化改造——让每条消息回答"我该怎么操作"

**需求ID**: REQ-261016155500-4f2a
**类型**: feature（存量改造，含数据模型变更）
**作用域**: `quantsys-v2/` 的 WatchEngine 通知链路（`application/services/watch_engine/`、
`application/notification/`、`infrastructure/notification/formatters/`、
`domain/watch/`、`adapters/outbound/repositories/watch_rule_repository.py`、
`quant.watch_rules` 表）
**档位**: 中档（改数据模型 + 通知渲染主链路 + 用户直接可见行为；升级触发见文末）
**调研依据**: `docs/investigations/2026-10-16-watch-messaging-chaos.md`（§1.5 / §1.6 为本需求直接来源）

## TL;DR

用户核心痛点不是"消息太多太乱"，而是**看到盯盘信息不知道该如何操作**。
生产直查证实：这是数据缺口，不是用户问题——

```
36 条启用规则
  ├─ next_action_hint（下一步建议）  填了 4 条  ← 89% 空缺
  ├─ intent（意图）                  填了 3 条
  ├─ action_on_trigger               空 19 · observe 16 · sell 仅 1
  └─ cost_price（算盈亏/仓位用）      填了 10 条
        ↓
渲染兜底 = 「下一步：由 agent 汇总时判断」（feishu_formatters.py:120）
        或 「观察趋势/结构变化」通用句（watch_level_templates.py:398-406）
        ↓
用户（user_main_simulation 最终决策者，agent 宪法限制不得代下单）
收到的消息里没有：建议动作 / 参考价位 / 仓位 / 失效条件
```

本需求做两件事：**给规则补上结构化操作指引（数据）** + **消息固定四段式渲染（呈现）**，
并捆绑两个正确性修复（去重吞止损、notified 口径撒谎）。观察类复读改聚合推送，
需要你重新拍板（2026-09-11 曾否决"观察类静默"——本需求是合屏不是过滤）。

## 边界

### 做什么

1. **结构化动作字段**：`quant.watch_rules` 增加 `action_params`（JSONB：动作 buy/sell/hold/reduce、
   参考价、仓位%/数量、失效/重估条件）；规则 CRUD API 支持读写；存量规则数据迁移 +
   批量生成"补全预案"治理待办交 agent 回填。
2. **消息四段式渲染**：触发消息固定为「事实 → 意义 → 建议动作 → 重估条件」四段；
   「建议动作」块必出，取值优先级 `action_params` > `next_action_hint` > intent 映射；
   全空时如实标注「⚠️ 规则#N 未配置操作指引，已派补全任务」，**禁止编造通用文案**。
3. **observe 类变化判据**：`observe` 类规则须声明「观察到什么变化才值得叫我」
   （放量 / 跌破 N 分钟未收回 / 次日确认等）；无判据的 observe 触发**不直发**，
   转入 15 分钟聚合卡。
4. **观察类聚合卡**：同标的同向的 observe 触发按 15 分钟窗口合成一张卡
   （"000963 今日第 5 次跌破 213.44，现价 208.3，最高触及 219"），
   保留推送原则（不静默、可逐条溯源），只改呈现密度。
5. **context 注记剥离**：规则预案里的机器注记（`[日期 注记 by ...]`）移入独立列
   `ops_notes`（JSONB 数组），消息只带真预案，注记不进用户视野。
6. **正确性捆绑修复**：
   - 去重命中但原判 escalated / exit_stop 时**不再改写为 deduped**，只合并展示不吞消息
     （现 engine.py:441-444 会吞掉止损级触发，资损风险）；
   - `notified` 元数据与真实发送一致（现 engine.py:517 把已发送的 auto_observed 记为
     notified=False）。

### 不做什么

- **不动投递拓扑**：agent-os 网关优先 / 直飞书降级的 `send_with_fallback` 结构原样保留；
  **消息仍然全部走 agent 网关投递、agent 仍是处置主体**——本需求只把"内容在哪里渲染"
  前移到 facade（设计 §3.4 有逐类消息的链路对照表）；
  三套渲染版式统一（分级卡/旧意图卡/网关平铺文本的收敛）通过"单一渲染器出稿、
  两路径共用同一份正文"实现，不改投递结构。
- **不合并回执链**：升级回执/超时回执/处置回执的"一待办一卡"改造不在本轮
  （`watch_sla_job.py` / `receipt_service.py` 保持现状）。
- **不动 digest 唤醒机制**：since 窗口 / 200 条上限 / 日预算口径维持现状（另立需求）。
- **不静默任何信息类别**：观察类全部可见（聚合卡内逐条可溯源），与你 2026-09-11 的
  定调一致——本轮只是把"逐条刷屏"改成"合屏呈现"。
- **不改自愈阈值**：noise_policy 的 8 次/日阈值维持现状（另立需求统一治理阈值口径）。

### 边界理由

- 痛点收敛在"消息不回答如何操作"：数据缺口（FR-1/3/5）与呈现缺位（FR-2/4）是
  同一根因的两半，拆开实施会出现"数据补了但消息没改"或反之的中间态，用户无感。
- 投递拓扑 / 回执链 / digest 是噪音与格式的根因，但手术面大、与"可操作"无直接关系，
  分开立项可以让本轮快速改变用户每天看到的东西。

## 产品定义

### 一句话

每条盯盘消息必须让用户在 10 秒内回答："发生了什么、关我什么事、**我现在该做什么**、
什么时候重新看"——做不到这一点的消息不许裸发，回去补数据。

### 为什么现在做

1. **98% 的消息无决策价值**：近 3 日 220 条触发中 escalated 仅 2 条，其余全部是
   观察类复读（price_break 电平触发，跌穿后每 30 分钟重发一张同样的卡，
   单规则实测 5 天 13 次）——真正需要操作的 2 条被埋在 100 条/日的噪音里。
2. **决策要素 89% 空缺**（见 TL;DR 数据）：这不是渲染能修的问题，必须先补数据再改呈现；
   渲染兜底文案「由 agent 汇总时判断」对用户等于"不知道，等 AI 说"。
3. **你是最终决策者但消息不面向你**：`user_main_simulation` 账户 agent 被宪法限制
   不得下单（remind_only），操作建议必须写给用户本人，而当前模板是写给 agent 的
   处置流程（PATCH /api/watch/triggers...）。
4. **有正确性资损风险**：去重可吞掉止损级触发（exit_stop 宪法级），修数据呈现时
   必须一并修掉，否则止损消息可能永远到不了你眼前。

### 现状实测（全部可复核，2026-10-16 采集）

| 维度 | 实测值 | 证据 |
|---|---|---|
| 今日触发消息量 | 100 条（高峰 9-10 点 46 条/小时） | `quant.watch_triggers` 当日 disposition<>'deduped' |
| 观察类占比 | 112 : 2（近 3 日 auto_observed : escalated） | 同上 group by disposition |
| next_action_hint 覆盖 | 4/36 启用规则 | `quant.watch_rules` where enabled |
| intent 覆盖 | 3/36 | 同上 |
| action_on_trigger | 空 19 / observe 16 / sell 1 | 同上 action_hint->>'action_on_trigger' |
| 重复盯盘 | 002007×4 条规则（含两种代码格式）；300418/301358/600011/002027 各×2 | 同上 group by split_part(symbol,'.',1) |
| 预案被注记污染 | 多条 context 以「[日期 健康检查误停·已恢复 by ...]」开头 | 同上 context like '[%' |
| 去重吞止损 | dedup 命中后无条件改判 deduped（engine.py:441-444），escalated 也吞 | 代码审读 |
| notified 口径 | auto_observed 实际已发消息但记 notified=False（engine.py:517） | 代码审读 + 库表 notified=t 佐证 |

## 用户与角色

- **项目所有者（人类，user_main_simulation 持有者）**：唯一最终决策者。
  验收标准 = 任意抽一条触发消息，10 秒内能说出"我该做什么或为什么不用做"。
- **窗口 AI Agent（回填执行者）**：接收"补全预案"治理待办，为存量规则补
  action_params / intent / 变化判据；补全质量由用户在飞书群里的反馈闭环。
- **处置 agent（agent-dh）**：接收结构化字段后的消息与待办，动作建议不再需要
  从自由文本预案里猜。

## 功能点

**FR-1: 结构化动作字段（数据层）**
`quant.watch_rules` 新增 `action_params` JSONB（schema：action ∈ buy/sell/hold/reduce/
observe、reference_price、position_pct | quantity、invalidation（重估条件））与
`ops_notes` JSONB（机器注记数组）；`watch_async.py` CRUD 支持读写并校验 action 枚举；
迁移脚本对存量 152 条规则安全加列（默认 NULL，不改行为）。

**FR-2: 消息四段式渲染（呈现层）**
触发消息（含 agent-os 主路径与直飞书降级路径的消息本体）固定四段：
`事实（触发条件+现价+涨跌/盈亏）→ 意义（intent 标签+目的）→ 建议动作 → 重估条件`。
「建议动作」取值优先级：action_params.action 描述 > next_action_hint > intent 映射；
四要素全空时渲染「⚠️ 规则#N 未配置操作指引，已派补全任务给 agent」，**禁止**输出
「由 agent 汇总时判断」类兜底推责文案。旧路径（feishu_formatters.py）与分级路径
（watch_level_templates.py）两条渲染链都要落地四段式。

**FR-3: 存量补全治理（回填闭环）**
迁移后为「enabled 且四要素全空」的规则批量建 P2「补全预案」待办（交处置 agent，
幂等：同一规则未关闭的补全待办不重复建）；待办 close 时回执须带回填结果摘要；
补全进度可在 `GET /api/watch/rules` 看到缺指引规则清单（lint 视图）。

**FR-4: 观察类变化判据 + 聚合卡（降噪呈现）**
- 规则创建/更新时 observe 类强制 `action_params.observation_criterion`（或独立列），
  声明"什么变化才值得叫我"；存量 observe 规则进 FR-3 补全清单。
- 引擎侧：observe 类触发若规则无判据 → 不直发即时卡，进 15 分钟聚合缓冲；
  有判据且判据满足 → 维持即时单发。
- 聚合卡格式：`[标的] 今日第 N 次 [条件简述]，现价 X（区间 low~high），
  逐条溯源 #trigger_id...`；缓冲到期 flush 一张卡，当日收盘 flush 残余。

**FR-5: context 注记剥离**
机器注记（正则 `^\[.*by \w+/\S+\]` 或健康检查巡检写入）从 `context` 移入 `ops_notes`；
消息与 digest 摘要只引用剥离后的真预案；迁移脚本对存量 context 执行一次性剥离。

**FR-6: 正确性捆绑修复**
- `engine.py` 去重改写加守卫：仅当原 disposition ∈ {pending, auto_observed} 时才允许
  改判 deduped；escalated / exit_stop 命中去重窗 → 保留升级通道，消息标题标注
  「（与规则#M 同事件，已合并展示）」，不丢消息。补回归测试覆盖"60s 窗内双规则
  先后触发、后响者为止损级"场景。
- `engine.py:517` notified 口径与 notifier 实际发送对齐（auto_observed 推了就是
  notified=True）。

## 验收标准（跑什么、看到什么算过）

1. **单测**：`pytest tests/services tests/application -k watch` 全绿；新增用例覆盖
   FR-6 止损不被 dedup 吞、FR-2 四段式渲染（含全空标注分支）、FR-4 聚合缓冲
   flush 语义。
2. **数据**：迁移后 `select count(*) from quant.watch_rules where enabled
   and action_params is null and next_action_hint is null` = 0（全部有指引或被
   补全待办覆盖）；`context` 中机器注记条数 = 0（均移入 ops_notes）。
3. **消息体**：抽样当日 ≥5 条不同规则的触发消息（查 `quant.watch_triggers` +
   对应消息），每条都能指出「建议动作」段；四要素全空的规则消息显示缺指引标注
   而非兜底文案。
4. **降噪**：开盘后连续观察 1 个交易日，同一规则同一条件的 observe 复读即时卡
   ≤1 张（其余进聚合卡）；当日触发消息总量较改造前同日基线（100 条）下降 ≥60%。
5. **止损链路**：构造/回放"同标的同向 60s 内双规则触发、其一为 exit_stop"场景，
   止损消息到达盯盘群且标注合并来源（不消失）。
6. **不回退**：`WATCH_TODO_ENABLED` / 回执链 / digest 唤醒现有测试不破；
   `python tools/check_scheduler_dedup.py` 退出码 0。

## 相关

- 调研报告：`docs/investigations/2026-10-16-watch-messaging-chaos.md`（含 14 条格式问题、
  频控参数表、正确性隐患全清单）
- 后续独立需求（不在本轮）：三套渲染版式统一（P2 格式）、回执一待办一卡（P1 去重展示）、
  digest 积压治理、自愈阈值口径统一。
- 关联裁定：2026-09-11「观察类必须推送、机器不替用户过滤」——本需求 FR-4 为
  合屏呈现，实施前需用户对"无判据 observe 不直发"显式确认。

## 中档依据与升级触发

- **为什么是中档**：动数据模型（watch_rules 加列 + 迁移）、动通知渲染主链路
  （两条渲染链 + facade 消息本体）、用户可见行为变化（四段式/聚合卡/缺指引标注），
  决策点不止一个（observe 判据口径、聚合窗口 15min、补全待办的级别与路由）。
- **单向升级触发**：实施中出现以下任一信号即升级重档并停手——
  要改 Agent OS 网关协议或投递拓扑（send_with_fallback 结构）、
  要给 watch_triggers 加列、要把聚合卡做成独立消息子系统（新表 + 新调度）。
