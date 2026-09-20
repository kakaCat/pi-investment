---
req_id: REQ-e3b6a0
doc: design/interfaces.md
serves: FR-1, FR-2, FR-4, FR-5, FR-7, FR-9, FR-10
---

# 接口设计：端口、装饰器与工具契约

## 1. 端口一览 `serves: FR-2, FR-10`

```ts
// application/ports.ts —— 新增两个端口，扩展一个既有端口

/** 后置链登记端口（Phase A 只登记） */
export interface GatePostChainPort {
  /** 登记一次闸门作答；幂等键 (windowKey, gate, decidedAt)。永不抛。 */
  enqueue(ctx: ConfirmContext): void
}

/** 会话投递端口（H4 与通道 B 共用；唯一实现见 AgentDeliverer） */
export interface AgentDeliveryPort {
  /** 投递一条续跑消息；窗口不在线 / 无 followup / 抛错 → 返回结构化结果，不抛。 */
  deliver(windowKey: string, message: { text: string; plugin: string }):
    { delivered: boolean; reason?: string }
}

/** 扩展：弹框端口增加"这次弹框属于哪个门"的声明 */
export interface UserQuestionPort {
  available(): boolean
  ask(questions: readonly AskQuestion[], opts: {
    agent?: unknown
    signal?: unknown
    /** ★ 新增：闸门声明。带它就自动获得链能力；不带 = 通用征询，不进链。 */
    gate?: GateId
  }): Promise<readonly AskAnswer[]>
}
```

## 2. GateAwareQuestions：让所有 pm 弹框自动获得能力 `serves: FR-1, FR-10`

```ts
// adapters/GateAwareQuestions.ts —— UserQuestionPort 装饰器
export class GateAwareQuestions implements UserQuestionPort {
  constructor(
    private readonly inner: UserQuestionPort,
    private readonly chain: GatePostChainPort,
    private readonly clock: Clock,
  ) {}

  available(): boolean { return this.inner.available() }

  async ask(questions, opts) {
    const answers = await this.inner.ask(questions, opts)      // ① 委托真实 UI，协议零变化
    if (opts.gate !== undefined && answers.length > 0) {
      const windowKey = windowKeyOf(opts.agent)
      if (windowKey !== undefined) {
        this.chain.enqueue({                                    // ② 只登记
          windowKey, gate: opts.gate, answers, decidedAt: this.clock.now(),
          from: /* 由用例后续写入台账；此处仅登记门与答案 */ undefined as never,
          to:   undefined as never,
          verdict: "affirmative",
        })
      }
    }
    return answers                                              // ③ 原样返回
  }
}
```

**注**：`from` / `to` / `verdict` 在 Phase B 执行时**从台账重新读取**（而不是装饰器猜测），保证"作答并推进之后"的时序正确（FR-4 / AC-4.1）。

## 3. GatePostChain：五个 handler 的契约 `serves: FR-2`

```ts
export type HandlerOutcome =
  | { kind: "continue" }
  | { kind: "skip"; code: string; reason: string }
  | { kind: "degraded"; code: string; reason: string }

export interface GateHandler {
  readonly name: "h1-advance" | "h2-compact" | "h3-inject" | "h4-resume" | "h5-audit"
  run(input: ChainInput): Promise<HandlerOutcome>   // 永不抛
}

export interface ChainInput {
  ctx: ConfirmContext        // Phase B 执行时已用台账刷新 from/to/verdict
  session: unknown           // 会话句柄（Phase B 才有）
}
```

| handler | 输入 | 产出 | 失败语义 |
|---|---|---|---|
| h1-advance | `ChainInput` | 已落库的 `ConfirmContext` | **抛**（裁决失败必须响亮；h1 在 Phase A 由用例完成，Phase B 只做校验） |
| h2-compact | + `AgentDeliveryPort` 无关 | `isolateNodeContext` 结果 | skip / degraded |
| h3-inject | + `InjectionLogPort` | 注入文本与留痕 | degraded（无提示词时仍发摘要） |
| h4-resume | + `AgentDeliveryPort` | 投递结果 | degraded |
| h5-audit | + 两个留痕端口 | — | degraded |

## 4. AgentDeliverer：唯一的投递实现 `serves: FR-5`

```ts
// adapters/AgentDeliverer.ts
import { createUserMessage } from "@deepseek-ai/dsh-llm"

export class AgentDeliverer implements AgentDeliveryPort {
  constructor(private readonly resolveAgents: () => unknown, private readonly plugin = "dsh-pmboard") {}

  deliver(windowKey, message) {
    const agents = this.resolveAgents() as { get?: (id: string) => unknown } | undefined
    const agent = typeof agents?.get === "function" ? agents.get(windowKey) : undefined
    const followup = (agent as { followup?: (m: unknown) => void } | undefined)?.followup
    if (typeof followup !== "function") return { delivered: false, reason: "窗口不在线或无 followup 能力" }
    try {
      followup.call(agent, createUserMessage({
        content: [{ type: "text", text: message.text }],
        source: { kind: "plugin", plugin: message.plugin },
      }))
      return { delivered: true }
    } catch (e) { return { delivered: false, reason: String(e) } }
  }
}
```

**形状纪律**：`ctx.agents` 是 `AgentRegistry`（只有 `get/list/roots/...`），`followup` 在 **Agent 实例**上。
禁止 `agents.followup(id, msg)`（现状 bug）。`grep -rn "agents\.followup(" packages/pages/dsh-pmboard/src` 必须 0 命中（AC-5.1）。

## 5. reqboard_capture：立项 pm 专有弹框工具 `serves: FR-7`

```
reqboard_capture()
  参数：无（三问内容由工具内部构造）
  输出：
    success            boolean
    requirement_id     string   创建成功时的 REQ id
    answers            object   三问作答摘要（名称/类型/难度）
    defaults_used      string[] 缺失选项走默认值的清单（不静默猜）
    fallback           "board"  弹框通道不可用时
    note               string
  行为：
    ① 经 deps.questions.ask([三问], { agent, signal, gate: "G0" }) 弹 pm 专有弹框
    ② 答案映射 → reqboard_create（title / category / prompt_difficulty / summary / reason）
    ③ 绑定本窗口（sourceSessionId）→ 需求进 draft → 自动推进 brainstorming
    ④ 登记 G0 的 PendingGate（由装饰器完成，工具本身不碰链）
    ⑤ 通道不可用 → fallback=board，不伪造立项（FR-7 第 5 条）
```

## 6. CaptureHook 注入文案的改动契约 `serves: FR-7`

- `application/internal/capture-section.ts` 的文案：把"调用 `ask_user_question`"改为"调用 `reqboard_capture`"；
- 三处口径统一为**三问**（`capture-section.ts` / `QueryState.ts:63` / `tools/CreateTool/prompt.ts` 以最后者为事实源）；
- 判据：`grep -n "ask_user_question" …/capture-section.ts` → 0 命中（AC-7.3）。

## 7. 看板确认端点的接口变更 `serves: FR-9`

```
POST /dashboard/api/reqboard/req/artifact/confirm
  请求：{ id, kind }                       // 不变
  响应：{ ...requirement,
          advanced?: boolean,              // 新增：是否已自动推进
          delivered?: boolean,             // 新增：是否已投递到窗口
          note?: string }                  // 新增：离线/重复时的如实说明
```

组合根需给 `createReqboardHandler` 新增依赖：`delivery?: AgentDeliveryPort`、`agents?: () => unknown`、`chain?: GatePostChainPort`。

## 8. 待实测契约（写进 t1 交付物） `serves: FR-5`

| ID | 待验事项 | 判据 | 回退方案 |
|---|---|---|---|
| **V1** | `surface replace` 是否唤醒 driver | 在**一次性 agent**（`agents.create`）上跑一次 replace，观察是否自动开新回合 | 若不唤醒（静态实证倾向此结论）：H4 显式 `followup`；若唤醒：H4 只发摘要，避免重复回合 |
| **V2** | 根 ctx 能否收到宿主发起的 `user-questions/request` | 注册只记日志的中间件 → 触发一次 `ask_user_question` → 看日志 | 本需求不依赖 V2（D2 已定发起侧换手）；仅记录以备将来 |

> V1 实测**必须在隔离环境**（一次性 agent 或独立 profile 端口）进行，**不得在我自己这条会话上做 surface 替换**。

### 8.1 V1 实测结论（t1 交付，2026-09-20） `serves: FR-5`

**结论：`surface replace` 不唤醒 driver。→ H4 采用 `followup`（显式唤醒）。**

证据（运行时探针 `scripts/spike/replace-wake-probe.mjs`，用真实 `@deepseek-ai/dsh-session`，user/message 形状逐字对齐 `NodeIsolationAdapter.replace`）：

```
[1] Session 公开方法: append, deriveEventMessage, deriveMessages, eventAt, id, isOwnSeq,
    ownEvents, requestContext, requestHeader, seq, snapshotEvents, surface
[2] 其中可能唤醒 driver 的 API: []                      ← 无 wake/inbox/send/followup/steer/inject
[3] replace 前 surface nodes: [0,1,2]
[4] replace 事件 seq = 3 | 系统段 seq = 0
[5] replace 后 surface nodes: [0,3]                    ← 压缩成 [系统段, 节点输入包]
[6] 模型可见消息: system:系统段 | user:节点输入包
[7] 替换后还看得见历史吗: false
[8] 全程唤醒调用: 无（Session API 无唤醒原语）
```

源码侧旁证（`dsh-agent-loop/lib/index.js`）：

- 唤醒只走 inbox：`followup(i) → send(i,"next-turn",true)`、`steer(i) → send(i,"next-step",true)`、`inject(i) → send(i,"next-step",false)`；
- `isReplacementSurfaceEvent` 在 loop 里**只做一件事**：清掉受影响的 retained 句柄（`this.retained = null`），既不投递也不唤醒。

**对设计的影响（已落到 §4 与架构文档 §5）**：

1. Phase B 顺序固定为 **先 H2（replace）后 H4（followup）**；
2. H4 的唤醒消息用**简短摘要**（提示词全文已在输入包内，避免重复）；
3. 若 H2 跳过/降级 → H4 的消息改为"摘要 + 阶段提示词全文"（D5 分流）；
4. V1 的残留不确定性已消除，不再需要"先摘要还是先 followup"的运行时保留方案。
