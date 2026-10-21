# 盯盘消息"混乱"调研报告（2026-10-16）

> 背景：用户反馈 WatchEngine 发到盯盘群的信息太混乱。本报告 = 代码审计（消息格式 ×1、频率/去重 ×1）+ 生产库直查验证。
> 状态：**仅调研，未改代码**。修复方案见 §5，待用户拍板。

## 1.5 病灶聚焦：消息不回答"我该怎么操作"（用户核心痛点，2026-10-16 补查）

生产直查（36 条启用规则）：

| 决策要素 | 覆盖 | 说明 |
|---|---|---|
| `next_action_hint`（"下一步"建议） | **4/36** | 其余 32 条消息只能显示兜底文案 |
| `intent`（意图标注） | **3/36** | watch_level_templates.py:150 兜底显示「❓ 未标注意图」 |
| `action_on_trigger` | 空 19 / observe 16 / sell 1 | observe 不是动作，"观察到什么才叫我"才是规则 |
| `cost_price`（成本线） | 10/36 | 盈亏/仓位建议算不出来 |
| `context` 被运维注记污染 | 多条开头是「[日期 健康检查误停·已恢复 by ...]」 | 真预案被埋在机器注记之后 |

渲染后果（用户视角）：
- 旧路径"下一步"默认显示**「由 agent 汇总时判断（动作 / 继续观察 / 取消盯盘）」**（feishu_formatters.py:120）——对人等于"我也不知道，等 AI 说"；
- 分级路径兜底到 INTENT_ACTION_HINT 通用句（watch_level_templates.py:398-406："观察趋势/结构变化"）——没有价位、没有数量、没有失效条件；
- 用户是 user_main_simulation 最终决策者（agent remind_only 不得下单），但消息里**没有一个"建议动作+参考价位+仓位+依据"的用户决策块**。

**结论：不是用户不会操作，是消息根本没给操作要素。** 四问模型——发生了什么（有）/ 为什么提醒（部分有）/ **现在该做什么（缺）** / 什么条件下重估（缺）——第 3、4 问在 89% 的规则上是空的。

## 1.6 对应方案（决策导向改造，待拍板）

1. **结构化动作字段**：规则补 `action_params`（动作 buy/sell/hold/reduce + 参考价 + 仓位%/数量 + 失效条件）；消息固定四段式渲染，"建议动作"块必出。
2. **缺指引不许裸发**：无 action/intent 的规则触发时，消息如实标注「⚠️ 规则#N 未配置操作指引，已生成补全任务给 agent」（不编造通用文案）；批量生成"补全预案"治理待办。—— 与用户 2026-09-11 定调一致：降噪的正确路径是"让 agent 把规则设好"。
3. **context 注记剥离**：`[日期 注记 by ...]` 机器注记移入独立列（ops_notes），不进用户视野；消息只带真预案。
4. **observe 类必须有"变化判据"**：写规则时强制声明"观察到什么变化才值得叫我"（放量/跌破 N 分钟未收回/次日确认等），否则该规则不允许 observe 直发——这是治复读机的根。
5. **决策分级呈现**：有明确动作建议的（P0/P1）即时单发突出；纯观察复读（P2/P3）聚合（见 §5 P1 降噪）。

## 1. 生产实况（quant_investment 直查，2026-10-16）

| 事实 | 数据 | 来源 |
|---|---|---|
| 今日触发消息量 | **100 条**（高峰 9-10 点 46 条/小时） | `quant.watch_triggers` |
| 观察类占比 | auto_observed 112 / 升级 escalated 2（近 3 日）——**98% 消息不需任何动作** | 同上 disposition |
| 单规则噪音 | rule 232（000963）5 天 13 次；多条规则 2 天 10-11 次 | 同上 |
| 启用规则 | 36 条，全部 `notify_mode=direct` | `quant.watch_rules` |
| 规则重复 | 002007 被 4 条规则盯（含 `002007` vs `002007.SZ` 两种代码格式）；300418/301358/600011/002027 各 2 条 | 同上 |
| 投递路径 | agent-dh:13080 / agent-os:8080 **在线** → 主路径 = agent 网关透传"干巴巴一行"版式 | nc + 日志 |
| 自愈 | 开关全开（WATCH_SELF_HEAL_ENABLED 等），但单日阈值 8 次才抑噪 | `.env` + noise_policy.py:34 |

## 2. 根因一：量 —— price_break 是电平触发，跌穿后每 30 分钟复读

- 条件"现价 ≤ 阈值"只要价格不回升就一直为真；`cooldown_sec=1800` 只决定**多久复读一次**（trigger_judge.py:48，默认 300s）。闩锁（trigger_judge.py:38-40）在条件回落后重新武装，阈值附近抖动 → 回落-再触发循环。
- 单规则理论上限 16 张/日（state_manager.py:13 注释自证实测 23 次）。
- 自愈单日 ≥8 次才抑噪（noise_policy.py:34）→ 每条规则每天先获准吵 7 张卡。
- 2026-09-11 用户否决"观察类静默"（notifier.py:151-155）→ auto_observed 全量逐条推。

## 3. 根因二：重复 —— 一次升级触发最多 5~6 张卡同群

触发卡(engine.py:474) + L1→L2 升级回执 + L2→L3 升级回执(watch_sla_job.py:141-194) + L3 超时回执 + 处置后回执(receipt_service.py:168-209)；digest 还把同一 trigger 再投 agent（UNRESOLVED 含 escalated，disposition.py:33）。

- P2 待办收盘 3 分钟连升 3 级：promote 不延长 due_at（watch_todo_repository.py:171-197）。
- result 回执即时发、escalate/timeout 聚合成卡，两种风格混用（receipt_service.py:58,313-332）。

## 4. 根因三：格式 —— 三套版式并存，用户看到哪套取决于投递成败

| 路径 | 版式 | 证据 |
|---|---|---|
| agent-os 网关（主路径） | `盯盘触发 - 名称（代码）` + 平铺正文，无颜色/级别/意图 | notification_facade.py:205-212 |
| 直飞书 + 有 level | P0 红卡/P1 橙卡/P2 蓝卡/P3 灰卡 | watch_level_templates.py:246-341 |
| 直飞书 + 无 level | 旧意图卡，按涨跌方向配色 | feishu_formatters.py:90-126 |

格式审计 14 条问题清单（均附 文件:行号）：

1. 触发事实在分级卡正文重复两次（facade:208 内嵌 + watch_level_templates.py:218）
2. `🔔 需决策` 在分级路径硬编码（watch_level_templates.py:215），L1 直发也显示需决策，与旧路径动态 mode_tag 矛盾（feishu_formatters.py:84-87）
3. escalation_reason 在分级路径完全丢失（watch_level_templates.py:425-459 不读该字段）
4. 回执类型三处重复：watch_channels.py:73 + receipt_service.py:208-209 + :220-224
5. P2/P3 单行无字段标签 vs P0/P1 八个标签行，密度不统一（watch_level_templates.py:304-307）
6. 分隔符混排 `·`/`｜`/全角空格（watch_level_templates.py:173,182,204）
7. 🛑 emoji 双义：exit_stop 意图标签（feishu_formatters.py:43）= P0 标题前缀（watch_level_templates.py:267）
8. 颜色语义双轨：方向配色 vs 级别配色，同事件随路径变色
9. 意图标签在分级卡标题+首行各出现一次（:216,267）
10. 名称缺失兜底文案三处不一致（:91 / receipt_service.py:159-160 / facade:205-207）
11. `⚠️ 未知级别…按 P2 处理` 内部细节外露（:132-136）
12. notifier.py:50-61 `_direction_advice` 僵尸文案（与意图相反，无调用方）
13. trigger_level(L0-L2) 与 watch_level(P0-P3) 两套分级卡片层面无映射
14. notified 元数据撒谎：auto_observed 实际发送但 engine.py:517 记 notified=False

## 4b. 正确性隐患（比"乱"更严重）

1. **去重吞止损**：engine.py:441-444 dedup 命中后无条件改判 `deduped`，即使 decide() 已判 escalated（exit_stop 宪法豁免）——同标的同向 60s 内别规则先响，止损消息被合并消失。
2. **digest 积压隐形**：`since=last_at` + limit 200（digest_service.py:88,271），更早未处置触发永远进不了摘要但仍积库；日预算 8 按账户段单 tick 可打空、失败账户 25min 才重试（:267-357）。
3. **通知失败 at-least-once 重发**：engine.py:475-478 失败不 mark_emitted，重试窗口内同事件可发两次。
4. **双头治理**：自愈（≥8/日）与元触发 burst（≥5/日）阈值打架；修规则待办跨日重复建（noise_self_heal_service.py:28）。
5. overlap_reported 内存集合不持久化，重启重复落治理项（state_manager.py:76,172）。
6. 去重键 (标的,方向) 与冷却键 (rule,cond_idx) 粒度不一致；combined 方向退化（disposition.py:106）。

## 5. 修复方案（按性价比排序，待拍板）

| 优先级 | 动作 | 效果 |
|---|---|---|
| P0 | ①dedup 命中但原判 escalated/宪法级 → 保留升级通道只合并展示；②engine.py:517 notified 口径与真实发送一致 | 消除资损风险、恢复可观测 |
| P1 降噪 | ③price_break 类改当日一次性（回落再穿越才重发）或 cooldown→2h；④自愈单日阈值 8→3；⑤**观察类改 15min 聚合卡**（保留推送原则，合成一张）；⑥合并 5 组重复规则、统一代码格式 | ~100 条/日 → 15-25 条/日 |
| P1 去重展示 | ⑦升级/超时回执并入"一待办一卡"；⑧P2 晋升延长 due_at +30min | 一次事件 ≤2 张卡 |
| P2 格式 | ⑨级别/意图/颜色渲染前移到 facade content，agent-os 与直飞书同版式；修 14 条格式清单 | 版式一致、有层级 |

⚠️ ⑤ 触及 2026-09-11 用户否决记录（"不该由机器替用户过滤"）——聚合卡是合屏不是过滤，需重新拍板。

## 附：频控参数速查（频率审计）

冷却默认 300s / 去重窗 60s / 介入预算 8·日 + 同标的 4h / 摘要唤醒 1500s·8 次·200 条 / 回执 SLA P0=300s·P1=1800s·P2=收盘 / 自愈 8·日·24h·600s 扫描 / 元触发 burst 5·日·idle 14 日 / tick 60s·fast 10s。
