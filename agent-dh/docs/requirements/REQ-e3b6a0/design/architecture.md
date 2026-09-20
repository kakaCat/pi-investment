---
req_id: REQ-e3b6a0
doc: design/architecture.md
serves: FR-1, FR-2, FR-3, FR-9, FR-10
---

# 架构设计：人工闸门域 + 确认后置链

## 1. 目标结构 `serves: FR-10`

把"人工闸门"从散落在用例里的判断，收敛成一个**有边界的领域**；把"确认之后要发生什么"收敛成**一条切面 + 一条责任链**。

```
domain/gate/                 闸门领域（纯规则：零 I/O、零 import）
  GateSpec.ts                单个闸门的形状
  GateCatalog.ts             唯一事实源：G0..G4 五道门 + 白名单 + 问题卡

application/gate/            后置链（编排，只依赖端口）
  GatePostChain.ts           Handler 契约 + 有序执行 + 短路 / 降级 / 幂等
  handlers/                  h1-advance · h2-compact · h3-inject · h4-resume · h5-audit
  PendingGate.ts             两相之间的登记表（Phase A 写、Phase B 读）

adapters/                    通道与投递（唯一碰会话 / fs 的地方）
  GateAwareQuestions.ts      UserQuestionPort 装饰器：所有 pm 弹框自动获得能力
  AgentDeliverer.ts          agents.get(id).followup(createUserMessage) 的唯一实现
```

依赖方向单向：`adapters → application → domain`，`index.ts`（组合根）在最外层装配。

## 2. 切面织入点 `serves: FR-1`

**唯一 join point**：`人工闸门被作答 且 裁决已落库`。

```
  UserQuestionPort.ask(...)                    ← 通道（唯一出口）
        │  GateAwareQuestions 装饰器：委托真实 UI，拿到 answers
        ▼
  chain.enqueue(ConfirmContext)                ← ★ 织入点（只登记，不执行链）
        │
  用例随后完成 H1：落章 + 状态推进 + 绑定窗口   ← 先落盘
        │
  turn/end（agent 空闲）                        ← 轮次边界
        ▼
  Phase B：H2 → H3 → H4 → H5                    ← 后遗弃
```

为什么织入点在**装饰器**而不是各用例：新增一道门 / 一个新弹框入口时，**零额外代码**即获得能力（FR-10 / AC-10.2）。

## 3. 两相执行模型 `serves: FR-2`

**Phase A（内联相，agent 忙）**：装饰器只 `enqueue`；H1 由用例完成。此相**不做任何会话写操作**。

**Phase B（边界相，agent 空闲）**：在 `turn/end` 之后经 `setImmediate` 异步边界执行 H2..H5。

三条硬约束（沿用既有实测结论，不得绕过）：

1. **必须移出 session/event 派发**：`session append cannot reenter while another append is being published`（D-17 实测），故 Phase B 只允许在异步边界跑；
2. **必须 agent 空闲**：surface replace 要求 `idle()`（`turnBoundary.openTurnStartSeq === null`）；
3. **失败只 warn**：Phase B 任一 handler 失败不回滚 H1 已落库的裁决，不改变工具返回值。

复用既有的 `createNodeSettlementDispatcher`（`application/internal/node-settlement.ts`）作为 Phase B 的**时机与失败隔离层**，不另造调度器；本需求只把它的触发源从"绑定窗口收到用户消息"扩展为"闸门被作答"。

## 4. H2 压缩上下文：接入既有实现 `serves: FR-3`

不新写压缩，接入 `application/use-cases/IsolateNodeContext.ts`：

| 要素 | 处置 |
|---|---|
| 输入包 | 复用 `buildNodeInputPackage`（路由提示词 + 需求文档投影 + 台账投影五字段，INV-9 不读会话历史） |
| 三条纪律 | 先落盘再遗弃 / 边界 tool 配对平衡 / 只在轮次边界——**原样遵守，不放松** |
| 降级链 | 触达不到 → fallback（开新窗口指引）；agent 忙 → skip；边界不平衡 → rejected |
| **自足判定（新增）** | 路由提示词可用 **且** 需求文档已落盘。任一不满足 → **H2 跳过**，只跑 H3+H4 |
| 开关 | 沿用 `NODE_ISOLATION`（默认关）。D1 决策：链先开，H2 后开 |

**自足判定是 G0 不压缩的依据**：立项那一刻 `requirement.md` 尚未产出，压缩会把"用户为什么提这个需求"一起丢掉。

## 5. H4 唤醒：V1 契约的静态实证结论 `serves: FR-5`

读 `dsh-agent-loop/lib/index.js` 实测：

```js
followup(input) { this.send(input, "next-turn", true);   }   // 唤醒
steer(input)    { this.send(input, "next-step", true);   }   // 唤醒（下一步边界）
inject(input)   { this.send(input, "next-step", false);  }   // 不唤醒
```

唤醒只走 **Agent 的 inbox**（`send → agent/inbox/spliced`）；而 `NodeIsolationAdapter.replace()` 直接调 `session.append('user/message', …, {surfaceOp})`，**不经过 inbox**。

**结论：`replace` 不唤醒 driver。** 因此：

- **H4 必须显式 followup**（不能依赖 replace 自己开新回合）；
- **顺序 = 先 H2（replace）后 H4（followup）**：先压缩成 `[系统段, 输入包]`，再用一条**简短唤醒消息**开新回合，避免"输入包 + 续跑消息"之外再叠一份提示词全文（D5）；
- 唤醒消息内容：作答摘要 + （H2 跳过/降级时）阶段提示词全文。

> **残留不确定**：以上为**静态实证**（高置信）。运行时若发现 replace 后的 append 被 driver 当作输入消费（重复一轮），回退方案：H4 改用 `inject`（不唤醒）+ 由 H2 的 replace 自行触发；design 任务 t1 要求在隔离环境（一次性 agent）跑运行时验证，**结论落在 t1 交付物里**。

## 6. 看板通道 B 纳入切面 `serves: FR-9`

通道 B 是 HTTP 请求，**没有 agent 回合**，因此不能靠 `turn/end` 触发 Phase B。处置：

```
POST /req/artifact/confirm
  ① 落章（现状，保持）
  ② 状态推进（新增：走同一 GateCatalog 白名单）
  ③ 触发 Phase B（新增）：按需求 sourceSessionId 找到绑定窗口 → AgentDeliverer 投递
       └─ 窗口不在线 → 只落章不推进、不投递，响应里如实说明"窗口不在线，请回会话推进"
```

为此需给 HTTP 组合根注入 `agents` 投递能力（现在 `routes.ts` 的 deps 没有它）。

## 7. 领域边界与分层纪律 `serves: FR-10`

| 层 | 允许 | 禁止 |
|---|---|---|
| `domain/gate/**` | 纯数据 + 纯函数 | `node:`、`@deepseek-ai/*`、时间、随机数 |
| `application/gate/**` | 端口调用、编排 | `node:`、`@deepseek-ai/*`、直接碰会话或 fs |
| `adapters/**` | 会话原语、fs、投递 | 业务规则（规则一律回 domain） |
| `index.ts` | 装配与注入 | 业务规则 |

机械门禁：`tests/layer-boundary.test.ts` 已存在，本需求只新增目录，不破规则。

## 8. 与既有设施的关系（不重造） `serves: FR-2, FR-3`

| 既有设施 | 本需求怎么用 |
|---|---|
| `application/internal/node-settlement.ts` | 作为 Phase B 的时机 + 失败隔离层，**扩展触发源**，不重写 |
| `application/use-cases/IsolateNodeContext.ts` | H2 的压缩实现，**直接调用** |
| `application/internal/injection-log.ts` / `isolation-trace.ts` | H5 的两条留痕，**直接调用** |
| `domain/prompt/index.ts resolveStagePrompt` | H3 的唯一取词入口（INV-1） |
| `domain/artifact/ArtifactSpec.ts ARTIFACT_CONFIRM_GATES` | 迁入 `GateCatalog` 后原处改为再导出，避免双真相 |

## 9. 不做 `serves: FR-1`

- 不新写压缩算法（摘要式压缩已排除，见 PRD 边界）；
- 不重写 node-settlement 的调度语义；
- 不改宿主 `ask_user_question` 的行为与协议；
- 不做任务级并行 workflow 的自动推进（另一条线）。
