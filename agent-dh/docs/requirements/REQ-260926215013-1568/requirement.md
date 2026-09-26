# REQ-260926215013-1568: Dive 续跑与采集全量对齐 DSH Goal driver

**需求ID**: REQ-260926215013-1568
**类型**: feature（对齐重构）
**作用域**: dsh-pmboard 插件（Dive 两半：会话驱动器 + 续跑驱动器）

## 边界

### 做什么

1. **会话驱动器（session-driver.ts）补齐 Goal driver 的 5 条纪律**：pre-step 竞态栅栏、inbox 竞争让位、耐久检查点、驱动串行化、teardown fail-closed。
2. **续跑驱动器（ReqboardDiveManager）按 Goal driver 重写**：驱动点改为整 agent 空闲；回合计数改为 reservation→admission；回合上限改终态阻塞；回合消息带 source 标识与不变量守卫。
3. **两半共用一套驱动状态机语义**：一个 agent 一个 driver 状态（attempt / competingQueued / needsCheckpoint / requested / run），两路订阅（session/event 采集 + agent/status 驱动）由 Dive 服务持有。

### 不做什么

- **不引入 dsh-goal-round-driver 依赖**：本机未挂该包（config/cordis.yml 只有 tool-goal / command-goal），本需求是**照其形自实现**，不把 Goal 的包加进 profile。
- **不改 Goal 自身的语义**：Dive 仍以 dsh-reqboard.json 台账为唯一事实源，不把需求状态搬进 Goal 的 goal 实体。
- **不改阶段配置语义**：stage-configs.ts 的每阶段 maxRounds 保留（Goal 无配置、上限来自目标本身；此处是合理适配）。
- **不动已对齐的部分**：session-driver 的驱动点（agent/status === idle）与 session/event 只做簿记，已于 2026-09-26 完成，本次只增量补 5 条纪律。

### 边界理由

- **对齐的是机制，不是依赖**：Goal driver 的价值在"只在整 agent 空闲起一轮 + 竞态栅栏 + 准入计数"，复刻机制即可，无需把 Goal 的实体模型搬进来。
- **台账唯一事实源不变**：Dive 的持久化对象是需求/任务，Goal 的是 goal，两者生命周期语义不同。

---

## 产品定义

### 一句话

把 Dive 的两半驱动器（会话采集 + 自动续跑）逐条对齐 @deepseek-ai/dsh-goal-round-driver 的机制，消除"会打断正在跑的回合"与"回合数被乐观吃掉后静默停跑"两类行为偏差。

### 为什么现在做

逐条核对（2026-09-26）发现 Dive 相对 Goal driver 有 **14 项未对齐**，其中两项会产生真实故障：

- **打断**：续跑挂在 reqboard/requirement-moved（状态推进事件）上，需求一被推进就 followup()，哪怕该窗口正忙——Goal driver 的铁律是 *A round starts only at whole-agent idle*。
- **静默停跑**：incrementRound 在 followup() 之后**无条件** +1（投递失败/被拒也算一回合），到上限时只打一行 warn、无终态、无告警 → 表现就是"Dive 莫名其妙不跑了"。

### 对齐基线（唯一参照）

agent-dh/node_modules/.pnpm/@deepseek-ai+dsh-goal-round-driver@0.1.6-alpha.2.../node_modules/@deepseek-ai/dsh-goal-round-driver（lib/index.js + README.md）。

---

## 用户与角色

### 主要用户

- **Dive armed 模式（AI Agent）**：唯一使用者。对齐后它的续跑只在整 agent 空闲时起一轮，人类插话时自动让位，回合耗尽的终态写进台账。
- **窗口 agent 自己**：收到的是同一条带 source 标识的回合消息；无法再被"状态推进即续跑"在半途插队。

### 次要用户

- **看板/人**：回合上限阻塞变成台账里的终态 + comment + warn，而不是日志里刷一行就没了。

---

## 功能点

**FR-1: pre-step 竞态栅栏**
在 agent/pre-step 上装栅栏：对本驱动器登记在飞的回合消息，进入 step **之前与之后**各校验一次（需求 id/revision 未变、仍 armed+active、round 仍是 roundsInStage+1、内容与登记逐字一致）；任一不成立 → 返回 reject，并把同批其它已认领消息按原顺序放回 inbox。

**FR-2: inbox 竞争让位（competingQueued）**
监听 agent/inbox/inserted：若入队消息不是本驱动器登记的那条 → 置 competingQueued = true，并把仍在 queued 的 attempt 标 stale。agent/status = idle 时复位。语义：**人类工作优先，自动工作让位到下次空闲**。

**FR-3: 耐久检查点**
排队前必须先落盘：await 台账写队列排空（reqboard.store.read(() => undefined)，与既有 persistArtifacts 同口径），**await 之后重查**需求 revision/phase 与竞争输入再决定是否排队；检查点失败 → 解除武装并 warn，不再起新回合。

**FR-4: 驱动串行化与合并触发**
每 agent 的驱动经 ctx.agents.withoutInitiator() 串行执行；多次触发合并为 requested 标志 + 单条 run 链（run 期间新触发只置位，不叠加执行）。驱动内异常只 warn + 解除武装，绝不冒泡进事件循环。

**FR-5: teardown fail-closed**
插件卸载/驱动停用时：先**关闭准入**（置 stopping，拒绝新排队），再解除武装每个在飞需求，取消在飞回合（cause = parent），最后等待驱动与 agent 静默；teardown 期间到达的触发一律丢弃。

**FR-6: 续跑驱动点改为整 agent 空闲**
续跑只在 agent/status === 'idle' 且（a）该 agent 仍存活、（b）competingQueued 为假、（c）其绑定需求 armed && phase === 'active' 时起一轮。reqboard/requirement-moved 改为**只置待检查标志并请求一次驱动**，不再直接 followup。

**FR-7: reservation → admission 回合计数**
排队时预留 round = roundsInStage + 1 并登记 attempt（含 messageId/content/source）；**只有该消息真正进入 history**（user/message 事件 id 匹配且 pre-step 放行）才把 roundsInStage + 1 落库。被 reject / discarded / 取消 / stale 的预留**不计数**，且下次仍用同一个 round 号。

**FR-8: 回合上限终态阻塞**
roundsInStage >= maxRounds 时写**终态**：dive.phase = 'paused' + pausedReason = 'round-limit'（含上限值与阶段），并 warn 一次。此后不再重复判定、不再起轮。

**FR-9: 异常收尾（max-tokens / aborted / 取消）**
- turn/end.reason.kind === 'max-tokens' → 解除武装；
- aborted：attempt 已 claimed/admitted → 标记 cancelled，并在下一次空闲时暂停该需求；否则直接解除武装；
- agent/error → 解除武装；agent/disposed → 清理该 agent 的 driver 状态。

**FR-10: 回合消息带 source 标识 + 内容不变量**
回合消息必须带机器可识别的来源标识 source: { kind: 'dive', requirementId, revision, round }；不变量：**只有内容与登记逐字一致**且 source 匹配时才认领该消息；任何不一致者在 pre-step 被拒并留痕（防止旧 revision 的回合混入）。

**FR-11: 可观测与失败响亮**
上述每一步（起轮 / 拒绝 / 让位 / 检查点失败 / 终态阻塞 / teardown）都要有结构化留痕：logger.warn 或台账 comment；**禁止静默降级**（尤其"到上限静默停跑"与"投递失败仍计数"两类）。

---

## 可证伪判定标准

**验收命令**（主命令）：

~~~bash
cd agent-dh/packages/web/dsh-pmboard && npx vitest run tests/dive-manager-alignment.test.ts
~~~

**必须看到的断言**（每条对应一个 FR，全部为可证伪的输入→输出）：

1. FR-1：构造 revision 已变的在飞回合 → pre-step 返回 reject，且同批其它已认领消息被放回。
2. FR-2：回合排队后插入一条人类消息 → competingQueued 为真、该 attempt 标 stale、agent idle 后不立即起轮。
3. FR-3：落盘检查点未完成 → 不排队；检查点失败 → 该需求 activation === 'disarmed'。
4. FR-4：连发 3 次触发 → 驱动体只执行 1 次（合并）；驱动体抛错 → 不产生未捕获异常/未处理 rejection。
5. FR-5：teardown 后触发驱动 → 不再排队；在飞回合被取消。
6. FR-6：agent 非 idle 时推进需求（requirement-moved）→ **不 followup**；置 idle 后才起轮。
7. FR-7：排队后消息被 discard → roundsInStage **不变**；消息 admitted → 恰好 +1（不重复计数）。
8. FR-8：roundsInStage === maxRounds → dive.phase === 'paused' 且 pausedReason === 'round-limit'，再触发 idle 不再起轮。
9. FR-9：三种收尾形态（max-tokens / aborted / error）分别得到解武装或 cancelled+pause 的预期终态。
10. FR-10：伪造一条 source 不匹配或内容不一致的回合消息 → pre-step 拒进，且留痕含拒绝原因。
11. FR-11：上述每条路径都有 warn/comment 留痕断言（无留痕即失败）。

**回归**（不得新增失败）：

~~~bash
cd agent-dh/packages/web/dsh-pmboard && npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts
npx tsc --noEmit -p tsconfig.json     # 包级错误数不得高于改动前基线
~~~

---

## 依赖与风险

### 依赖

- DSH 公开 API（已核）：agents.withoutInitiator / currentInitiator（dsh-agent/lib/types/index.d.ts:219,254）、agent/pre-step（runtime-types.d.ts:304）、agent/status、agent/inbox/*、sessions.flush（dsh-session/lib/types/index.d.ts:420）。
- stage-configs.ts 的 maxRounds（FR-8 的上限来源）。
- pmboard 的 inject 需从 ['agents','reqboard'] 扩到含 goals / sessions（若实现中确实需要读 Goal/session 服务；否则不扩，避免无谓依赖）。

### 风险

1. **行为变更风险**：续跑由"状态推进即触发"改为"空闲才起轮"。若某窗口长期不空闲，续跑会推迟——这是**期望行为**，但需在设计里写清"什么时候仍会跑"。
2. **并发写风险**：ReqboardDiveManager.ts 与 session-driver.ts 近期被多个窗口改动，实施前必须先取最新内容、按文件认领，禁止整文件覆盖他人改动。
3. **线上影响**：改动落在 :13080 正在运行的插件上，需重启才生效；实施完成后必须重建 + 重启 + 复跑回归。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-aa2ec9、t-0ddfb1、t-620dc0 |
| FR-2 | ✅ 已接收 | t-0ddfb1、T-4、t-620dc0 |
| FR-3 | ✅ 已接收 | t-0ddfb1、T-4、t-620dc0 |
| FR-4 | ✅ 已接收 | t-0ddfb1、t-620dc0 |
| FR-5 | ✅ 已接收 | t-aa2ec9、T-4、t-1aa789、t-620dc0 |
| FR-6 | ✅ 已接收 | t-0ddfb1、T-4、t-1aa789、t-620dc0 |
| FR-7 | ✅ 已接收 | t-aa2ec9、t-0ddfb1、t-620dc0、t-2b3e57 |
| FR-8 | ✅ 已接收 | t-aa2ec9、t-0ddfb1、t-620dc0、t-2b3e57 |
| FR-9 | ✅ 已接收 | t-0ddfb1、t-1aa789、t-620dc0 |
| FR-10 | ✅ 已接收 | t-aa2ec9、t-0ddfb1、t-4a74c8、t-620dc0 |
| FR-11 | ✅ 已接收 | t-0ddfb1、t-620dc0、t-2b3e57 |

> 无未接收条款（11 条全部有落点）。

<!-- reqboard:marks:end -->
