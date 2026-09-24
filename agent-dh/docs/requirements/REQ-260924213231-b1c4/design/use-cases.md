---
requirement_refs: [FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, FR-8]
---

# 用户场景（REQ-260924213231-b1c4）

> 读者：工程 / agent。只承载需求文档放不下的多角色/多分支场景；功能点明细见 requirement.md §6。
> 角色：**agent**（主用户，唯一会调 reqboard_* 的主体）、**人**（次用户，只在需要裁决时被打扰）、**维护者**。

## 场景总览 <!-- serves: FR-1, FR-2, FR-3, FR-6, FR-7, FR-8 -->

| 场景 | 角色 | 触发 | 完成标志 | serves |
|---|---|---|---|---|
| UC-1 | agent | 设计文档落盘后 | 5 份登记齐 + 一次确认落章 + move 通过 | FR-1, FR-2 |
| UC-2 | agent | reqboard_move 被 G2 拦下 | 从消息读出「未登记 / 待确认」与唯一命令 | FR-2 |
| UC-3 | agent + 人 | run_code 内发起弹框，人离开 | 发起调用不失败；答复后有 confirmed=true | FR-3 |
| UC-4 | agent（弹框不可用时） | reqboard_capture 不可用，走 reqboard_create | 文档位置有值或显式回落留痕 | FR-7 |
| UC-5 | 人 | 先后出现 pm 弹框与宿主提问 | 不读正文即可分辨来源 | FR-8 |
| UC-6 | agent（新窗口） | 上一回合被上游 TIMEOUT 打断 | 输入包含断点：阶段 + 未完成动作 | FR-6 |

## UC-1 设计文档登记与确认 <!-- serves: FR-1, FR-2, FR-5 -->

- **用例角色**：agent（run_code 内只调工具，**不打开看板页面**）
- **前置条件**：需求处于 design；5 份设计文档已写入 `docs/requirements/<REQ>/design/`
- **交互流程**：
  1. 调 `reqboard_submit(kind=design)` → 返回逐份态（5 份 registered=true, confirmed=false）
  2. 调 `reqboard_ask_confirm(target=artifact, kind=design)` → 人在宽限内点「确认推进」
  3. 返回 `confirmed=true, advanced=true`，需求进入 decomposing
- **异常流**：① 目录里少一份 → move 被拦，消息点名缺哪份；② 有未登记新增件 → ask_confirm 返回 `gate_failure`；
  ③ 弹框超宽限 → 返回 pending+ticket，agent 稍后用回执查询（UC-3）
- **后置条件**：全部 kind=design 产物有确认章，需求状态 = decomposing
- **完成标志**：A1 —— 全程不出现 `REQBOARD_MISSING_ARTIFACT`，move 一次通过

## UC-2 被闸门拦下后看懂原因与下一步 <!-- serves: FR-2 -->

- **用例角色**：agent
- **前置条件**：任一内容/形态闸门被触发（设计文档缺条目、缺确认章、章节缺 serves、编号悬空、必交文档未交、设计里混入拆分内容…）
- **交互流程**：
  1. 调工具（`reqboard_move` / `reqboard_submit(kind=plan)` / `reqboard_decompose`）
  2. 读拒绝消息，按**三要素信封**拆分：`<tool> 未执行：<what> —— <why>。补齐：<how>`——
     what = 哪份文档/哪一条；why = 报错原因（未登记 / 未落章 / 缺 serves / 悬空引用 / 未交文档 / 混入拆分内容…）；how = 可复制的一步
  3. 照 `how` 修一步（如补 `serves: FR-#`、按模板生成 `design/frontend.md`、或写 `design_exempt=…=理由`），重试
- **异常流**：① 若人在看板已点确认、但磁盘仍有新增未登记件 → `ask_confirm` 早返回补一句「仍有 N 份未登记」，两处消息不再互相矛盾；
  ② 若 `gaps` 为空/形态不认识 → 信封如实写「未分类缺口」+ 通用下一步，**不伪造 why**
- **后置条件**：缺口清零，工具调用通过
- **完成标志**：A2 —— 两种病因产出两句不同文案，各带唯一下一步命令；且**每条内容闸门消息都同时含 why 与 how**（TC-21）

## UC-3 长等弹框（人离开 5 分钟后作答） <!-- serves: FR-3 -->

- **用例角色**：agent + 人
- **前置条件**：弹框通道可用（活窗口 + 直接人工回合）
- **交互流程**：
  1. agent 在 run_code 内调 `reqboard_ask_confirm(target=artifact, kind=design)`
  2. 宽限内无人作答 → 工具返回 `{success:true, confirmed:false, pending:true, ticket:'pc-…'}`，**agent 的 run_code 正常结束**
  3. 人 5 分钟后作答 → 后台落章 + 推进 + 通过 AgentDeliverer 唤醒窗口
  4. agent 调 `reqboard_confirm_receipt(ticket)` → `confirmed=true, advanced=true`
- **异常流**：① 弹框通道不可用 → `fallback=board`（人去看板确认）；② 回执过期 → 改读
  `reqboard_status.design_docs[].confirmed`（以台账为准，不猜）；③ 用户选「需修改」→ 回执带
  `user_feedback`，不推进
- **后置条件**：确认结果落到台账；不产生任何「120s 判定失败」
- **完成标志**：A3 —— 发起调用无 deadline 报错；答复后 confirmed=true 可取得

## UC-4 立项降级路径不丢文档位置 <!-- serves: FR-7 -->

- **用例角色**：agent（弹框通道不可用时）
- **前置条件**：`reqboard_capture` 返回 `fallback=board` 或本窗口无弹框权限
- **交互流程**：
  1. 用户在对话里给出名称/类型/难度（可不给位置）
  2. agent 调 `reqboard_create(title, category, prompt_difficulty, doc_location?)`
  3. 返回值含 `doc_location` 与 `defaults_used`；台账写入 `docBasePath`
- **异常流**：位置形态非法（绝对路径/含 ..）→ `REQBOARD_INVALID_INPUT`，不静默改路径
- **后置条件**：需求创建并推进到 brainstorming；文档路径三面（返回值 / 台账 / 输入包）一致
- **完成标志**：A5 / FR-7 —— 不传则显式回落留痕；传 `docs/rfcs/` 则产物路径按它生成

## UC-5 分辨 pm 弹框与宿主提问 <!-- serves: FR-8 -->

- **用例角色**：人
- **前置条件**：窗口先后出现 pm 插件发起的确认弹框与宿主 `ask_user_question`
- **交互流程**：
  1. pm 侧构造问题（AskConfirm / AcceptSheet / capture 四问 / 失败处置）统一经 `pmHeader()`
  2. 人看到 header 前缀 `📋 PM · ` → 判定来自 pm 插件；无前缀 = 宿主原生提问
- **异常流**：agent 不得靠正文 emoji 冒充；标志由 pm 侧注入，与 agent 文案无关
- **后置条件**：两种来源一眼可辨
- **完成标志**：A6 / FR-8 —— 不读正文即可分辨，且标志非 agent 手写

## UC-6 回合中断后续跑有据 <!-- serves: FR-6 -->

- **用例角色**：agent（新窗口或少上下文窗口）
- **前置条件**：上一回合因上游 TIMEOUT 中断；需求台账已有断点记录
- **交互流程**：
  1. **写入器 A（自动，发生在中断之前）**：每次交棒工具成功（submit / ask_confirm / move / decompose / task_move / accept_sheet），pmboard 在 mutate 尾部调 `stampCheckpoint`，把「当前阶段 + 下一步命令」写进 `req.interruption`（幂等：未变化不写）
  2. **写入器 B（自动，中断当下）**：回合以异常收尾时，宿主在 `session/event` 发 `turn/end`（`data.reason.kind ∈ {aborted, error, interrupted}`）；`CaptureHook` 读 `data.reason` → `turnEndOutcome` → 只发信号，组合根经异步边界调 `noteInterruption` 覆盖 `reason`（`error:<code>:<message>` 等）
  3. **写入器 B′（显式兜底）**：事件入口不可得时，agent/续跑路径调 `reqboard_note_interruption(reason)` 补写
  4. 续跑时构造节点输入包 → 条件追加「## 断点」节：阶段 + 未完成动作 + 中断原因 + 时间
- **异常流**：① 无断点（老需求）→ 不渲染该节，其余节逐字不变（零误伤）；② 事件形态不认识 → 不写、不报错（A 的 checkpoint 仍在）；③ 台账写失败 → 只 warn，不打断流水线
- **后置条件**：断点落在需求台账（单一事实源，后写覆盖前写），不写 Session 副本
- **完成标志**：FR-6 —— 注入一次 TIMEOUT 后，续跑包含断点章节（TC-15 / TC-15b）