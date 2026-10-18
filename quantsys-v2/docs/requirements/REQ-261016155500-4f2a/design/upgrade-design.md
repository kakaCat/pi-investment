# 盯盘系统升级设计（REQ-261016155500-4f2a）

> 版本：v1.0（2026-10-16）· 状态：待用户确认
> 依据：`docs/investigations/2026-10-16-watch-messaging-chaos.md`（问题清单全集）
> 原则：① 每条消息必须让用户 10 秒内知道"发生了什么 / 关我什么事 / 我现在该做什么 / 什么时候重新看"；
> ② 不静默任何市场事实（2026-09-11 用户定调），降噪靠**合屏**与**修规则**，不靠吞消息；
> ③ 消息本体即富文本——agent-os 网关与直飞书降级看到**同一份内容**。

## 1. 现状问题 → 设计决策总表

| # | 问题（调研报告 §） | 决策 | 落点 |
|---|---|---|---|
| 1 | 89% 规则无操作指引，消息兜底"由 agent 汇总时判断" | 结构化 action_params + 四段式渲染，缺指引如实标注+派治理待办 | §2/§3/§6 |
| 2 | price_break 电平复读，单规则最多 16 卡/日 | 闩锁重新武装加迟滞 + 每规则每条件日上限 | §4.1 |
| 3 | 一次触发最多 5~6 张卡同群 | 回执收敛：一待办最多两卡（超时 P0/P1 + 结果）；升级回执下线 | §5 |
| 4 | 三套渲染版式随投递成败漂移 | 单一渲染器，消息本体在 facade 组装完成 | §3.3 |
| 5 | 去重吞止损级触发 | dedup 守卫：escalated/exit_stop 只合并展示不吞 | §4.2 |
| 6 | notified 元数据撒谎 | 落库与真实发送结果对齐 | §4.2 |
| 7 | P2 收盘 3 分钟连升 3 级 | 晋升延长 due_at +30min | §5.2 |
| 8 | 自愈阈值 8/日过高；与 meta_review 双头治理 | 阈值 8→3；burst 归自愈一家管 | §4.4 |
| 9 | digest 积压隐形（since+limit 200） | 积压单独成段可见 | §4.5 |
| 10 | 同股多规则重复盯（002007×4 等 5 组） | 合并迁移 + 代码格式归一 | §6.2 |
| 11 | context 被机器注记污染 | 注记剥离到 ops_notes 独立列 | §6.3 |
| 12 | overlap_reported 内存态重启丢失 | 纳入 runtime state 持久化 | §4.6 |
| 13 | 通知失败 at-least-once 可重发 | 先落库后发送，重试只补 notified | §4.3 |

## 2. 统一消息模型（WatchMessage）

新增 `domain/watch/services/watch_message.py`——**所有盯盘消息（触发/聚合/回执/治理）
先构造为统一模型，再由唯一渲染器出稿**。渠道只看到成品 title+text（+飞书卡片 payload）。

```python
@dataclass
class WatchMessage:
    kind: str            # trigger | observe_digest | eod_rollup | receipt_timeout | receipt_result | governance
    level: str           # P0 | P1 | P2 | P3
    symbol: str
    name: str
    account: str | None
    intent: str | None
    fact: FactSection        # 条件文案 / 现价 / 涨跌幅 / 盈亏
    meaning: str             # 「这条提醒为了」：intent 目的句
    action: ActionSection    # verb(buy/sell/hold/reduce/observe/missing) + 参考价 + 仓位/数量 + 来源
    reevaluate: str | None   # 失效/重估条件
    trace: TraceSection      # rule_id / trigger_ids / todo_id / dup_of
```

**ActionSection.source 取值优先级**：`rule.action_params` > `rule.next_action_hint` > intent 映射 >
`missing`（此时渲染"⚠️ 规则#N 未配置操作指引，已派补全任务"，**禁止**"由 agent 汇总时判断"类推责文案）。

## 3. 消息分类、路由与渲染

### 3.1 分类与密度

| 类别 | 触发条件 | 呈现 | 频率上限 |
|---|---|---|---|
| 即时触发卡 | escalated / L2 / P0 / P1 / 有判据且满足的 observe | 单发，红(P0)/橙(P1)/蓝(P2) | 每规则每条件 ≤2 张/日（§4.1） |
| 观察聚合卡 | 无判据 observe / 判据未满足的复读 | 同标的 15min 合屏一张 | 每标的 ≤8 张/日 |
| 日终汇总 | P3 + 当日全部触发统计 | 收盘后一张 | 1 张/日 |
| 超时回执 | 仅 P0/P1 待办 SLA 违约 | 单发，高优 | 每待办 1 张 |
| 结果回执 | 待办关闭 | 单发（含全过程时间线） | 每待办 1 张 |
| 治理消息 | 规则重叠/缺指引/自愈抑噪 | 合屏（每日最多 1 张/类） | — |

**一个市场事件在盯盘群的出现次数：最多 3 张**（即时触发卡 + 超时回执[仅 P0/P1] + 结果回执），
观察类最多 1 张聚合卡 + 日终汇总一次提及。对比现状的 5~6 张。

### 3.2 升级回执下线（需用户确认项 A）

现状 L1→L2 / L2→L3 各发一张"升级即回执"聚合卡。升级是**引擎内部状态机迁移**，
不是市场事实——保留在 `watch_todos` 时间线与结果回执中可溯源，盯盘群不再单发。
（与用户 2026-09-11"不替用户过滤市场信息"不冲突：该原则保护的是行情事实，不是引擎日志。）

### 3.3 单一渲染器（消灭三套版式）

```
engine/notifier ──┐
digest ───────────┼─▶ WatchMessage ──▶ WatchMessageRenderer ──▶ RenderedMessage
receipt_service ──┘        (domain)         (infrastructure)      {title, text, card}
                                        │
              facade.send_watch_triggered┤  text → Notification.content（agent-os 网关裸转发也是全文）
              FeishuChannel formatter ───┘  card → 飞书卡片（降级路径）
```

- 新增 `infrastructure/notification/formatters/watch_message_renderer.py`：唯一出稿点，
  四段式骨架 `事实 → 意义 → 建议动作 → 重估条件`，text 与 card 同源生成（card = text 分段+颜色）。
- `notification_facade._enrich_watch_content` 退役：content 直接由渲染器产出，
  不再"网关丢失后补"。`WatchTriggeredFormatter`（feishu_formatters.py）与
  `watch_level_templates.py` 改为薄适配层调用渲染器；旧渲染代码随引用清零后删除。
- emoji/颜色语义统一：颜色只表达级别（P0 红/P1 橙/P2 蓝/P3 灰），方向只在正文文字表达；
  🛑 仅用于 exit_stop 意图；🔔 仅用于"真的需要用户决策"（action.verb ≠ observe/missing）。

### 3.4 投递链路（**不变**，2026-10-16 用户提问后显式补记）

> 用户问："以后消息都直接发送不走 agent 了吗？"——**不是**。本次改造只移动
> "消息内容在哪里渲染"（从渠道层前移到 facade），**消息走哪条路一米都不动**：

| 消息 | 现行链路 | 升级后链路 |
|---|---|---|
| 非 L2 触发/聚合卡/回执 | `send_with_fallback(agent, feishu)`：AgentChannel → agent-os 网关 → notification_channels 表 → **盯盘群 webhook**；agent-os 不可达才降级直飞书 | **完全不变**（变化仅在于网关转发的 content 从"干巴巴一行"变成渲染器产出的完整四段式正文） |
| L2 / escalated 触发 | wake 通道投 target_agent（agent 处置决策），失败降级飞书 | **完全不变** |
| 摘要唤醒 | `agent_service.notify_agent` → POST /wake → agent-dh 处置 | **完全不变** |
| agent 的处置回执 | facade.send_watch_receipt → AgentChannel → 盯盘群 | **完全不变**（卡片收敛为一待办最多两卡，见 §5） |

即：**agent 仍然是处置主体**，所有处置（handled/ignored + reason）仍由 agent 完成；
用户在群里看到的每一条消息依然经过 agent-os 网关投递。本次改造动的是"渲染位置"与
"消息密度"，不动"投递拓扑"与"处置权责"。

## 4. 引擎触发语义与正确性

### 4.1 迟滞闩锁 + 日上限（治复读）

- 现状：闩锁在条件回落即重新武装，阈值附近抖动 → 每 cooldown（300s~1800s）复读一张。
- 改为：条件触发后，**重新武装要求价格离开阈值一个迟滞带**
  `hysteresis = max(0.5% × 阈值, 最小报价单位×5)`——上破条件需回落到 阈值×(1-h) 以下、
  下破条件需回升到 阈值×(1+h) 以上才重新武装。迟滞带内的小幅反复穿越不再发声。
- 兜底日上限：每规则每条件 **≤2 次/交易日**（可配 `daily_cap_per_condition`，默认 2），
  超限只落库不通知（suppressed=true 归档，与自愈抑噪同通道，可溯源）。
- 影响面：`trigger_judge.py`（武装判定）+ `state_manager`（每日计数，入 runtime state）。

### 4.2 dedup 守卫 + notified 口径

- `engine.py:441-444`：dedup 命中时，仅当原 disposition ∈ {pending, auto_observed, ignored, expired}
  才改判 deduped；escalated / exit_stop 命中 → **保留升级通道照发**，
  标题追加「（与规则#M 同事件，合并展示）」，正文合并两条规则的触发事实。
- 回归测试：同标的同向 60s 窗内双规则先后触发、后响者为 exit_stop → 止损消息必达。
- `engine.py:517`：notified 字段 = notifier 真实发送结果（facade_result.success），
  与 disposition 解耦。

### 4.3 落库先于发送（治 at-least-once 重发）

- 现状：notify 抛错 → 不落库不闩锁 → 下 tick 重发，窗口内可双发。
- 改为：先 `_record(notified=False)` 拿 trigger_id → 发送 → `update_notified(trigger_id, success)`；
  发送异常时下 tick 通过"同条件已有未通知记录"短路，只补发不重建。
  （repo 需补 `mark_notified(trigger_id, ok)` 一个方法。）

### 4.4 自愈阈值收敛 + 双头治理合并

- `noise_policy.DEFAULT_MAX_TRIGGERS_PER_DAY: 8 → 3`（配合 §4.1 日上限 2，
  触发 3 次/日只可能来自多条件规则，必是规则设计问题）。
- meta_review 的 burst≥5/日 检查下线（与自愈重复），保留 idle≥14 日 / stage≥7 日 /
  到期≤2 日三类；修规则待办跨日复用（同规则有未关闭的修规则待办则不重复建）。

### 4.5 digest 积压可见

- `build_digest` 保留 since 增量段，另加「积压（自上次处置前遗留）」段：
  统计 UNRESOLVED 中 triggered_at < since 的数量与最旧时间，超 limit 的溢出如实报数
  （"另有 N 条未入摘要，最旧 M 天前"）。预算口径不变。

### 4.6 overlap_reported 持久化

- 并入 `watch_runtime_state` 既有持久化通道（state_manager snapshot/restore 加一组键）。

## 5. 回执收敛：一待办最多两卡

### 5.1 卡片矩阵

| 事件 | 现状 | 改后 |
|---|---|---|
| L1→L2 / L2→L3 晋升 | 各 1 张聚合卡 | **下线**（入待办时间线 + 结果回执展示） |
| L3 超时 | 1 张（risk_stop 高优） | 仅 P0/P1 发；P2 超时只入日终汇总 |
| 处置完成 | 1 张即时 | 保留，增加全过程时间线（触发→晋升→关闭） |

### 5.2 P2 due_at 修正

- 现状 P2 due_at=当日收盘，收盘后 60s 巡检 L1→L2→L3→timeout 三分钟三连。
- 改为 P2 due_at=收盘+30min；每次晋升 due_at 再 +30min；P2 到 L3 超时**不发卡**，
  记日终汇总"逾期未处置 P2 待办 N 条"。

## 6. 数据模型与规则治理

### 6.1 新列（迁移 `infrastructure/persistence/migrations/20261016_watch_rules_upgrade.py`）

```sql
ALTER TABLE quant.watch_rules ADD COLUMN action_params JSONB;   -- {action, reference_price, position_pct|quantity, invalidation, observation_criterion}
ALTER TABLE quant.watch_rules ADD COLUMN ops_notes JSONB;        -- 机器注记数组 [{at, by, text}]
```
- 幂等（IF NOT EXISTS）；回滚 = drop column（无数据依赖，新列默认 NULL 不改变现行行为）。
- 同步 ORM（`watch_rule_repository.py`）、domain 模型、`watch_async.py` CRUD（含 action 枚举校验：
  buy/sell/hold/reduce/observe）。

### 6.2 重复规则合并（数据脚本，一次性，干跑先行）

5 组：`002007:{157,193,199} + 002007.SZ:59`、`300418:{248,249}`、`301358:{242,247}`、
`600011:{235,259}`、`002027:{245,256}`。
- 统一 symbol 为 6 位纯代码（引擎 `_norm_symbol` 已按此取数，仓储同步归一）；
- 每组保留信息最全的一条（有 cost_price/action_hint/context 长者优先），
  其余规则的 conditions 并入保留者（conditions 是数组，天然支持多档），原规则 disable
  并在 ops_notes 记合并溯源；
- **干跑输出合并计划 → 用户确认 → 执行**（数据操作，脚本 `--dry-run` 默认开）。

### 6.2.1 合并计划（2026-10-16 生产数据核对，✅ 已按账户归属修正后执行）

> ⚠️ 修正（2026-10-16，核对 linked_account 后）：原计划的 002007 组合并要求
> 59 与 157/193/199 并成一条——但 59 属 **user_main_simulation**、157/193/199 属
> **agent_brain**。跨账户合并违反 2026-09-11 用户定调（"同一标的被两个账户盯盘时
> 绝不合并——合并 = 把 A 账户的止损预案投给 B 账户的 agent"，digest_service.py:83）。
> 故 002007 拆为两组，59 只做 symbol 归一；合并数 7 → 6，启用规则 36 → **30**。

| 组 | 保留 | 并入并 disable | 合并后条件 | 理由 |
|---|---|---|---|---|
| 002007（agent_brain） | **157**（有 cost 13.27） | 193, 199 | pnl below -8 · pnl above 10 · price above 15（3 档） | 同账户同成本，三条件天然一条规则 |
| 002007（user_main_simulation） | **59**（intent=trend_observe） | —（仅 symbol 归一） | 原 3 档不变（below 12.85 / above 13.55 / below 12.19） | 跨账户不合，59 保留独立 |
| 002027 | **256**（5 档最全） | 245 | below 5.2/4.96/4.84 · above 5.34/5.47 · + below 5.14（6 档） | 245 的 below 5.14 与 256 的 below 5.2 档位不重合，并入；symbol 归一为 002027 |
| 300418 | **248**（有 next_action_hint） | 249 | below 41.28 · below 41.7 · above 45.4 · below 39.1（4 档） | 248 是 5 组中唯一有"下一步"字段的规则，保留 |
| 301358 | **247**（3 档） | 242 | below 46.12 · above 48.1 · above 50 · below 47.16（4 档） | 242 的 below 47.16 与 247 的 below 46.12 不重合，并入 |
| 600011 | **259**（combined 量价条件） | 235 | combined(上破 7.65 AND 放量 1.5x) · below 7.1（2 档） | 259 的 combined 是更完整表达；235 单档 below 7.1 并入 |

合并后被 disable 的规则：193, 199, 245, 249, 242, 235（共 6 条）；
启用规则数 36 → 30。59 保留但 symbol 由 `002007.SZ` 归一为 `002007`。
所有保留规则 symbol 统一为 6 位纯代码。

### 6.3 context 注记剥离（迁移内含）

- 正则识别机器注记行（`^\[.*(by \w+/\S+|健康检查|事实校正|误停).*\]`），从 context 移入 ops_notes；
- 消息与 digest 只引用剥离后的真预案。

### 6.4 缺指引 lint 与补全闭环

- `GET /api/watch/rules?lint=missing_guidance`：返回四要素（action_params/next_action_hint/
  intent/action_on_trigger）全空的启用规则清单；
- 迁移后对每条 lint 命中建 P2「补全预案」待办（幂等：同规则有未关闭补全待办则跳过），
  交处置 agent 回填，close 回执带回填摘要。

## 7. 分阶段实施映射

| 工作流阶段 | 覆盖设计章节 | 主要文件 |
|---|---|---|
| data-rules | §6 全部 | migrations、watch_rule_repository、watch_async、tools/merge_watch_rules.py |
| messaging | §2、§3、§5 | watch_message.py、watch_message_renderer、facade、receipt_service、watch_sla_job |
| engine | §4 全部 | trigger_judge、engine、deduplication_manager、noise_policy、digest_service、state_manager |
| validate | 验收 6 条 | tests/、tools/、模拟交易日回放 |

依赖：messaging 依赖 data-rules 的新列（ActionSection 取数）；engine 与 messaging 可并行
（接口以 WatchMessage 模型契约为界）；validate 收尾。

## 8. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 迟滞带让真实二次穿越失声 | 迟滞带 0.5% 远小于规则阈值间距（实测多档规则档距 ≥3%）；日上限 2 保兜底 |
| observe 聚合被认为"过滤" | 聚合卡逐条列 trigger_id 可溯源；日终汇总全量点名；需用户确认项 A/B 通过后实施 |
| 渲染器切换期两套并存 | feature flag `WATCH_MSG_V2=true` 灰度：新渲染器产出与旧并行落日志对比 1 个交易日再切 |
| 迁移改坏 context | 剥离前先全量备份 `watch_rules`（pg_dump 单表）；脚本幂等可重跑 |
| 回执下线漏重要信号 | 超时回执（P0/P1）保留高优通道；晋升事件仍在 digest 与结果回执时间线可见 |

**回滚**：代码层 flag 切回旧渲染；数据层新列 drop（无依赖）；合并规则从 ops_notes 溯源恢复
（disable 不 delete，一键 re-enable）。

## 9. 需用户确认的两个决策点（✅ 2026-10-16 均已确认）

- **A. 升级回执（L1→L2 / L2→L3）从盯盘群下线**，改入待办时间线与结果回执（§3.2）。
  → **用户已同意下线**。
- **B. 无变化判据的 observe 触发不即时单发**，进 15 分钟聚合卡（§3.1）——
  这是对 2026-09-11「观察类必须推送」定调的细化：全部仍推送，只是合屏。
  → **用户已同意聚合**。
