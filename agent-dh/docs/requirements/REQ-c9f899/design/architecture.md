# 技术设计 · 架构（REQ-c9f899）

> 目标节点：planning。本文只回答「怎么做」，不产出任务卡（属拆分阶段）。

## 1. 设计目标（对应需求的不变式）

| 需求不变式 | 技术落点 |
|-----------|----------|
| I1 不得滞留（时效） | 待办表 + 到期巡检 job 的**机械晋升**（不依赖 agent 主动） |
| I2 处置对象可以是规则 | 待办终态含「规则变更」动作；规则自愈服务产出修规则待办 |
| I3 必有终态 | 待办终态枚举封闭（handled/ignored/expired），巡检强制收敛 |
| I4 agent 必参与 | L3 待办必须绑定处置记录（decision_audit 引用），否则不得关闭 |
| I5 账户定接收者 | 路由函数（纯函数）：account → owner_kind/owner_ref/autonomy |
| 噪音治理 | 判据 metric 化 + 反复触发抑噪（R6）+ 聚合 |
| 冷却是真的 | runtime 状态落库并启动恢复（R10） |

## 2. 组件图与职责

~~~
WatchEngine（进程内 daemon）
  ├─ RuleEvaluator / TriggerJudge    —— 判定与闩锁（状态改读 WatchRuntimeStore）
  ├─ EscalationPolicyService         —— 只保留「宪法级 + 异常波动 + 规则显式声明」
  ├─ LevelResolver（纯函数，domain）  —— 级别判定：intent × 持仓 × 宪法级 → P0..P3
  ├─ Router（纯函数，domain）         —— account → owner（agent/user）+ autonomy
  ├─ TodoService（应用）              —— 落待办、认领、关闭（终态强制校验）
  ├─ ReceiptService（应用）           —— 三段回执（升级即/处置后/超时）
  ├─ NoiseSelfHealService（应用）      —— 反复触发判定 → 抑噪 + 修规则待办
  └─ MarketWatchService              —— 市场级（并入同一待办通道）

WatchSlaJob（独立定时任务，每 1 分钟）   —— 到期巡检：晋升 L1→L2→L3、超时回执、升级给用户
WatchHeartbeatJob（独立定时任务，每 1 分钟）—— 引擎心跳缺失/影子超期 → 飞书告警
~~~

**关键分层纪律**：级别判定、路由、终态校验、反复触发判定全部是**domain 纯函数**，应用层只做编排与持久化——避免出现第二份真相（现健康度两份真相的教训）。

## 3. 判据 metric 化（根治「现价当量比」）

- EvalResult 增加 metric: MetricKind（price / pct_change / pnl_pct / velocity_pct / volume_ratio / indicator_value / event_flag / sector_strength）与 unit。
- 每个条件 handler 显式产出 metric；combined 的 metric 为 composite 并携带子 metric 列表。
- **消费侧契约**：EscalationPolicyService、异常波动判定、消息渲染、自愈统计凡读 result.value，必须先声明期望 metric；不匹配即拒（响亮抛错，不静默兜底）。
- 回归：price_break 触发绝不允许进入量能路径（用规则 #162 场景做回归用例）。

## 4. 闭环状态机

~~~
触发 ──► TodoService.create(level, owner, sla)
                     │
              ┌──────┴──────┐
        P0/P1 │             │ P2/P3
      直接 L3◄─┘             └─► L1 ──(SLA 到期/认领)──► L2 ──(到期)──► L3
                                                          │
                              L3 ──(处置)──► 终态 handled/ignored/expired
                                                          │
                          终态后：回执 + 规则生命周期（退役/续期/自愈清除）
~~~

- **唯一收敛权威 = WatchSlaJob**（机械、可测、不依赖 agent 主动性）：扫描非终态且 due_at < now 的待办 → 晋升一级；已在 L3 仍超时 → 升级给用户（P0 直接 @）。
- 承压保护：同一规则在抑制期内产生的触发不再新建待办（只落 P3 聚合），防止待办表被噪声灌满。

## 5. 规则自愈（R6）

- **判定输入**（全部落库聚合，不依赖内存）：同规则当日触发次数、连续触发天数、同标的同向重复度、阈值与现价偏差。
- **超限动作（顺序固定）**：① 置规则为抑噪态（新触发只进 P3 聚合）② 自动临时延长冷却（写 runtime 状态，不改规则的静态配置）③ 生成「修规则」待办（P1，owner 按账户）。
- **修复动作枚举**（受账户授权约束）：延长冷却 / 调整阈值或方向 / 拆分或合并规则 / 退役。修复后清除抑噪态，恢复原级别。
- **不做的事**：抑噪只改投递级别，不改判定结果——真信号仍进 L3，且在聚合摘要里可见。

## 6. 状态持久化（R10）

- 新增 runtime 状态存储（闩锁 / 冷却基准 / 去重窗 / 触发事件窗口），每 tick 批量 upsert、启动时恢复。
- 价格历史（velocity 用）改为从 minute 数据恢复或落轻量表，避免重启后 30 分钟盲区。
- 写入节流：只在状态变化时写，避免每 tick 全量落库。

## 7. 投递与「颜值」

- 在 infrastructure/notification/formatters 新增按级别的盯盘模板（P0 红卡/P1 橙卡/P2 蓝卡/P3 汇总），模板输入只认结构化字段，禁止拼接式消息。
- 修复两处已确认的空转：① 频道金额门（策略对象缺 account_total 注入）② target_agent 无消费者。
- P2/P3 聚合器：按账户 × 标的 × 时段聚合；聚合窗口与上限可配。

## 8. 观测（最小保留，非面板）

- 心跳：引擎每 tick 写 heartbeat 时间；WatchHeartbeatJob 检测缺失（>3 分钟）→ 飞书 alerts。
- 影子模式超期（>48h）→ 飞书 alerts 提请裁决。
- 这两条是「闭环必达」可验收的前提，不属于用户裁定排除的「控制台页面」。

## 9. 与现有实现的关系（改造而非推倒）

| 现有组件 | 处置 |
|----------|------|
| engine.tick 主循环 | 保留；判定与升级段重构，新增 TodoService 落点 |
| StateManager（内存） | 保留接口，底层换持久化 store（行为等价 + 可恢复） |
| EscalationChecker 5 类 | 删除 4 类，保留宪法级与异常波动；量能路径移除 |
| DispositionEngine 五道门 | 保留金额/意图/增量/经济门，改为产出 level + owner，而非直接决定「叫不叫 agent」 |
| digest_service 摘要门 | 由 TodoService + WatchSlaJob 取代（唤醒与晋升统一到待办） |
| notifier / NotificationFacade | 保留，改为按级别选模板 + 接回执 |
| meta_review_service | 并入 NoiseSelfHealService（治理项进 P1 待办） |
| position_lifecycle_service | 保留，修复账户范围（按规则归属逐账户判定） |
| RuleHealthChecker（死代码） | 删除，健康度只留一处（daily job 内联实现收口到 domain） |

## 10. 设计自查

- **无占位符**：所有阈值给出默认值与「可调」标注，不写 TBD。
- **无矛盾**：抑噪（自动）与规则修改（授权）分离；观测最小集与「不做面板」不冲突（已在需求 §6 裁决）。
- **无蔓延**：不引入消息队列/推送基础设施（方案 C 已否决）；不改交易宪法与账户事实源。
- **可回滚**：全部改动由开关与 additive 表结构支撑（见 migration 文档）。
