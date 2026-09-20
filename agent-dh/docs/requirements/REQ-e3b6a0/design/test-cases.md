---
req_id: REQ-e3b6a0
doc: design/test-cases.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
---

# 测试策略：AC → 用例映射

## 1. 测试层级与范围 `serves: FR-2`

| 层级 | 覆盖 | 运行方式 |
|---|---|---|
| 单元（domain） | GateCatalog 纯规则、难度映射、幂等键、问题卡派生 | `vitest`（零 IO） |
| 单元（application） | 链序 / 短路 / 降级、H2 自足判定、H3 时序、答案映射 | `vitest` + 端口替身 |
| 集成（adapters） | GateAwareQuestions 装饰、AgentDeliverer 三态、HTTP 确认端点 | `vitest` + fake 会话/agents |
| **E2E** | G0 立项 → G1 确认 → agent 自动进入 design；两个留痕文件各新增一条 | 真实 :13080 手工走查 + 证据留存 |

## 2. AC → 用例映射 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6`

| AC | 层级 | 用例要点 | 期望 |
|---|---|---|---|
| AC-1.1 | 单元(application) | 只加一行 gate 配置，不改用例代码 | 该门作答后链被触发 |
| AC-1.2 | 单元 | 同 `(windowKey, gate, decidedAt)` 重复 enqueue | 每 handler 只跑一次 |
| AC-2.1 | 单元 | 注入 5 个 fake handler | 顺序 H1→H2(skip)→H3→H4→H5；H2 skip 不阻断 H3 |
| AC-2.2 | 单元 | H2/H4 抛错 | H1 落库不变、工具返回值不变、仅 warn |
| AC-3.1 | 单元 | 走一次 H2 | `isolateNodeContext` 被调、`status=replaced`、`range` 自首个非 system 节点 |
| AC-3.2 | 单元 | ①需求文档不存在 ②`idle()=false` ③触达不到 | 分别为 skip(带 code) / skip / fallback(仍返回输入包文本) |
| AC-3.3 | 单元 | 断言 `artifactSeq < replacementSeq`；构造不平衡边界 | 先落盘再遗弃；不平衡 → rejected |
| AC-3.4 | 单元 | 注入替身 scheduler | 断言派发内不同步执行 Phase B |
| AC-4.1 | 单元 | fake 台账在 H1 前后取 `revision` | 取词发生在落库之后；G1 消息含 design 档片段 id、不含 brainstorming 档 |
| AC-4.2 | 单元 | 选「需要修改」 | 节点未推进、H2 未执行、消息含当前阶段提示词与 `user_feedback` |
| AC-5.1 | 单元 | 断言经 `agents.get(id).followup` 且消息为 `createUserMessage` 形状 | 形状正确；`grep` 断言 0 处 `agents.followup(` |
| AC-5.2 | 单元 | agent 离线 / 无 followup / 抛错 | 只 warn，返回值与成功路径一致 |
| AC-6.1 | 集成 | 跑一次链 | `prompt-injection-log.json` 与 `node-isolation-log.json` 各新增一条 |

## 3. 立项 pm 弹框与答案映射 `serves: FR-7`

| AC | 层级 | 用例要点 | 期望 |
|---|---|---|---|
| AC-7.1 | **E2E** | 真实走一次立项 | 作答后不再输入任何消息，agent 自动产出并登记 `requirement.md` |
| AC-7.2 | 集成 | 注入 fake `UserQuestionPort` 调 `reqboard_capture` | `ask()` 被调用（三问同批）；需求已存在且 `sourceSessionId` = 本窗口（同一次调用内完成） |
| AC-7.3 | 静态 | `grep -n "ask_user_question" capture-section.ts` | 0 命中；三处口径一致为三问 |
| AC-7.4 | 单元 | 名称给 `custom`、类型/难度给 `selected[0]`；再构造缺失 | 映射正确；缺失走默认且 `defaults_used` 非空 |

## 4. 看板通道与领域收敛 `serves: FR-9, FR-10`

| AC | 层级 | 用例要点 | 期望 |
|---|---|---|---|
| AC-9.1 | 集成 | `POST /req/artifact/confirm` + fake 投递端口 | 落章 `confirmedVia=board`、状态已推进、投递被调一次 |
| AC-9.2 | 集成 | `agents.get` 返回 undefined | 只落章、未推进、响应含"窗口不在线" |
| AC-9.3 | 集成 | 先 B 后 A（同 gate） | 链只跑一轮、状态只推进一次 |
| AC-10.1 | 静态 | `grep -rn "ADVANCE_MAP\|ARTIFACT_CONFIRM_GATES" src` | 只剩领域内一处定义 |
| AC-10.2 | 单元 | 新增一个带 `opts.gate` 的假弹框用例 | 链被登记；未改装饰器与链代码 |
| AC-10.3 | 静态 | `tests/layer-boundary.test.ts` | 通过；`domain/gate/**` 零 import `node:`/`@deepseek-ai/*` |

## 5. 门禁与线上核验 `serves: FR-8`

| AC | 命令 | 期望 |
|---|---|---|
| AC-11.1 | `cd packages/pages/dsh-pmboard && npx vitest run`；`npx tsc --noEmit -p tsconfig.json` | 全绿 / 无新增错误 |
| AC-11.2 | 重启 :13080 后真实走一次 G1 | 点肯定项后不再输入任何消息，agent 自动开始 design；两个留痕文件各新增一条 |
| AC-11.3 | `grep -nE "批准拆分计划\|decomposing → implementing" docs/guides/reqboard-workflow.md` | 闸门表与 `ArtifactSpec.ts:38` 逐条一致 |

## 6. 故障注入（不只测成功路径） `serves: FR-2, FR-3`

| 注入 | 期望 |
|---|---|
| Phase B 在 session/event 派发内被同步调用 | 被既有 D-17 保护拦下并留痕，不崩 |
| `isolateNodeContext` 抛未预期异常 | 链降级、只 warn、不回滚 H1 |
| 端口未注入（`delivery` / `chain` 缺失） | 各 handler 走 degraded，工具返回值不变（向后兼容） |
| 台账在 Phase A 与 Phase B 之间被外部改写 | Phase B 以台账**实时** `from/to` 为准；状态不符则 skip 并留痕 |
