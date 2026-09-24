# REQ-260924213231-b1c4 修 REQ 流水线设计阶段死锁（产物登记入口 + 闸门语义 + 弹框超时）

> 状态：brainstorming（需求分析）｜ 类型：feature ｜ 难度：expert ｜ 创建：2026-09-24
> 立项来源：用户原话「坦克大作战小游戏开发，用另外一个模型有工具报错，不按照规范执行等问题，你帮我调研一下」
> → 调研报告 docs/work-logs/2026-09/req-2cd3-tank-execution-postmortem.md §7.3（6 项平台改进）
> → 用户「立项」→「都添加到本次需求里面」（含调研中另外发现的两点，落为 FR-7 / NFR-1）
> → 需求分析阶段用户反馈：用户原话「我是希望区别 dsh 本身的 ask_user_qustion 的弹框，我希望添加一个标志区分 dsh 和 pm 插件的 ask_user_qustion」→ 落为 FR-8

## 1. 需求概述

### 1.1 一句话目标

让 agent 在「设计 → 拆分」这一步能自己走通：设计文档有**可调用的**登记入口、被闸门拦下时能看懂**为什么被拦、下一步做什么**，且人在环弹框不会被 agent 通道的执行预算掐断——REQ-2cd3 那种「20 分钟空转 + 会话超时死掉」的设计阶段死锁不再出现。

### 1.2 可证伪判定标准

- A1：新建一个 feature 测试需求，agent 只调工具（**不打开看板页面**）就能把 design 阶段 5 份设计文档登记齐全并确认，reqboard_move(design→decomposing) 一次通过，全过程不出现 REQBOARD_MISSING_ARTIFACT。
- A2：构造「文档已落盘但未登记」状态时，reqboard_move 的拒绝信息出现「未登记」字样并给出登记命令；构造「已登记未落章」状态时，信息出现「待确认」字样——两种状态文案不同（现状两者是同一句话「未确认」）。
- A3：在 run_code 里发起 reqboard_ask_confirm 弹框，人隔 5 分钟后再作答，调用正常返回 confirmed=true，不出现 execution deadline reached (120000ms)。
- A4：tools.reqboard_status()（不带参数）正常返回，不报 binding arguments must be lossless JSON。
- A5：reqboard_create 之后，工具返回值 / 台账 status / reqboard_status 的 next_actions 三面一致可解释；且「文档位置」走默认值时返回体或台账显式标注回落（现状：降级路径无该问项、无任何 defaults 留痕）。
- A6：先后发起「pm 弹框」（reqboard_ask_confirm）与「宿主提问」（ask_user_question），人在**不读正文**的前提下能分辨哪个来自 pm 插件——标志由 pm 侧统一注入，不依赖 agent 手写 emoji。

### 1.3 背景与实测证据（REQ-260924162957-2cd3 事故）

- 会话 session-aa3d23b6-20ee-48c5-8621-0ec81c7655bd（2026-09-24 16:28 → 17:29，61 分钟）：61 次工具调用中 17 次报错（28%）。
- design 阶段被 G2 闸门拦了 20 分钟：3 次 reqboard_move 被拒、2 次弹框 120s 超时、2 次证据核验被拒（REQBOARD_EVIDENCE_FAKE，护栏正确）、4 次直调非 run_code 工具、3 次零参绑定失败。
- 用户被迫连喊「推进」「弹框，我点确认」「给我弹框」「什么原因你解决一下」；最终 turn 15 被上游流超时（upstream stream idle 3m ×5 重试）打断。
- 收尾状态：需求停在 decomposing，0 张任务卡、无拆分计划、无验收材料。
- 全量证据：docs/work-logs/2026-09/req-2cd3-tank-execution-postmortem.md

## 2. 现状调查（已核实代码，2026-09-24）

### 2.1 死锁链路（四步自我锁死）

1. 设计文档落盘。提示词只说「设计文档落盘即产物（目录自动发现登记）」（packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md:5），agent 遂认为登记已完成。
2. 但真正的登记动作只挂在 HTTP 渲染路径：src/http/routers/stages.ts:40「渲染前同步需求目录」调用 ArtifactSync（src/adapters/ArtifactSync.ts）。**工具面没有任何等价入口**——agent 不打开页面就永远登记不上。
3. agent 调 reqboard_ask_confirm(kind=design) 撞 REQBOARD_MISSING_ARTIFACT，转而去猜 reqboard_submit(kind=design) → 参数非法（合法值只有 requirement/plan/verification/archive）→ 再转弹框 → 120s 超时。
4. 用户在页面上点了确认，闸门仍报 design/test-cases.md 未确认：src/application/internal/design-gates.ts:145-149 对每份 on-disk 设计文档查产物簿，art === undefined（未登记）与 confirmedAt === undefined（未落章）**产生同一句话「未确认」**；而 ask_confirm 同时回「产物 design 已确认，未重复弹框」（advanced=false）。两条信息互相矛盾，agent 只能盲试直到系统自己补登（17:06:58 的产物自动发现）。

### 2.2 代码坐标汇总

| 问题 | 坐标 | 现状 |
|---|---|---|
| 登记只挂 HTTP 渲染 | http/routers/stages.ts:40 · adapters/ArtifactSync.ts:57 | 工具面无入口、无可查询状态 |
| 未登记 / 未落章同文案 | application/internal/design-gates.ts:148 | 两种病因都输出「未确认」 |
| 弹框预算 1 小时 vs agent 通道 2 分钟 | domain/limits.ts:48-54（timeoutInteractiveMs = 3,600,000，2026-09-23 用户裁定） | 外层 run_code 120s 死线先到 |
| 零参调用被绑定层拒 | tools.reqboard_status() | binding arguments must be lossless JSON（事故 3 次） |
| 无 kind=design | reqboard_submit 工具契约 | 模型猜测后撞枚举（事故 1 次） |
| 降级路径丢第四问 | tools/CaptureTool/CaptureTool.ts:52,60 · internal/capture-mapping.ts:190-196 · use-cases/CaptureRequirement.ts:199（docBasePath = docLocation）vs internal/support.ts:220-232 | reqboard_create 无 doc_location 入参、无 defaults 标注 |
| 提示词未写登记时机 | domain/prompt/fragments/design/heavy/overrides.md:5 | 只给结论不给命令与触发者 |
| pm 弹框与宿主提问同通道、无来源标志 | adapters/UserQuestionsAdapter.ts:40-44 · use-cases/AskConfirm.ts:96-100（header 固定「确认」） · AcceptSheet.ts:63-71 | 弹框本体无来源标识，人只能读正文分辨 |

### 2.3 调查结论

一句话根因：**agent 被要求走一条只有人能触发的登记路径，而闸门反馈把「未登记」伪装成「未确认」**；再叠加弹框超时、零参绑定两处工具面缺陷，形成 20 分钟空转。事故模型的越界行为（直调 write ×4、猜 API）是放大器，不是根因。

## 3. 产品定义

- 产品名称：REQ 流水线（项目看板 dsh-pmboard 的 reqboard 工具族）
- 类型：内部工程平台能力（面向 agent，不面向终端用户）
- 定位：把「需求分析 → 设计 → 拆分 → 实施 → 验收」的阶段纪律，做成 agent 与人都能收敛的闸门
- 核心价值：阶段推进不再依赖「人恰好打开过看板页面」这一隐式前提

## 4. 用户与角色

- 主用户：DSH 窗口里的 agent（唯一会调 reqboard_* 的主体）——需要可执行的下一步，而不是一句自相矛盾的状态提示。
- 次用户：投资人（人）——闸门应只在「需要人裁决」时打扰他，不该把平台的登记缺口变成他的人工操作项（事故中它被要求去页面手动勾选，而页面并没有那个粒度）。
- 维护者：本仓开发者——需要这类修复被 vitest 门禁锁死，避免回归。

## 5. 边界

做什么：
- 只动 reqboard 工具族 + 看板渲染路径 + 阶段提示词三处，范围以四个点收口：登记入口、闸门文案、弹框超时、零参绑定（FR-1~FR-4），外加两处对齐（FR-5/FR-7）与一处韧性（FR-6）。
- 每项改动都要自带可回归的 vitest 用例（本仓已有 packages/web/dsh-pmboard/tests/）。

不做什么：
- 不改流水线阶段划分，不放松任何人工闸门（闸门「该不该拦」的判定标准不动，只改「怎么告诉 agent」）。
- 不做 REQ-260924162957-2cd3 坦克游戏的实施（另一条需求），不重写 ArtifactSync 的扫描规则与幂等语义。
- 不删改 reqboard_submit 既有四类 kind 的契约、不引入新的网络/LLM 依赖。
- 不改宿主 DSH 包（@deepseek-ai/dsh-*）：给 DSH 原生 ask_user_question 弹框也打标属上游改动，本次不做——只保证 pm 侧弹框可辨识（FR-8）。

## 6. 功能点

- **FR-1: 设计产物登记入口与登记态查询由 agent 可触发**
  现状：登记只在看板页面渲染时发生（stages.ts:40），工具面没有入口，agent 只能等人打开页面。
  目标：给 agent 一个可调用的登记入口（新增扫描/登记工具，或为 reqboard_submit 增补 kind=design——二选一在 design 阶段定），并让 reqboard_status 返回本需求设计文档逐份的登记态（已登记 / 待确认 / 已落章）。
  验收：A1。
- **FR-2: 闸门拒绝信息区分「未登记」与「未落章」，并给出唯一可行下一步**
  现状：design-gates.ts:148 两种病因同一句话「未确认」。
  目标：按文件标注「未登记（产物簿无此条，先登记）」或「待确认（已登记未落章，先确认）」，并附唯一命令；同时消解与 ask_confirm「已确认，未重复弹框」的表述冲突（后者须补一句「仍有 N 份未登记」）。
  验收：A2。
- **FR-3: 交互式确认不被 agent 执行预算掐断**
  现状：弹框自身预算 1 小时（limits.ts:52，用户 2026-09-23 裁定），但从 run_code 发起时外层 120s 死线先到，人被记成失败。
  目标：人在环确认的等待不占用调用方执行预算（异步投递 + 回执），或调用方预算自动让位给交互预算；不再出现 120s 判定失败。
  验收：A3。
- **FR-4: 零参数工具可直接调用**
  现状：零参调用被绑定层拒（binding arguments must be lossless JSON），事故中出现 3 次。
  目标：零参调用等价于传 {}，正常返回。
  验收：A4。
- **FR-5: 阶段提示词写清设计文档的登记路径**
  现状：设计阶段提示词只说「落盘即产物」，没说何时由谁触发，也没说「不要尝试 reqboard_submit(kind=design)」——直接诱发事故中的 3 次无效尝试。
  目标：在设计阶段提示词里写明登记命令与时机（FR-1 落地后的命令名）；若跑在没有登记入口的版本上，明说「落盘后需打开看板详情页触发登记」。
  验收：提示词片段基线快照测试更新，并断言包含登记命令。
- **FR-6: 上游流超时/回合失败保留断点，续跑有据**
  现状：turn 15 因 upstream stream idle 3m ×5 失败后，已读的 7 份文档与「下一步写 decomposition.md」全部丢失，需求停在 decomposing 无人知道断点在哪。
  目标：回合以上游 TIMEOUT 失败时，在需求/Session 留一条断点记录（当前阶段 + 未完成动作），并在下一次节点输入包里带出；用本仓既有 fault injection 手段可构造验证。
  验收：注入一次 TIMEOUT 后，续跑包或留痕含断点章节。
- **FR-7: 立项降级路径不丢「需求文档位置」**
  现状：第四问只存在于 reqboard_capture 弹框路径；弹框通道不可用时走 reqboard_create，该工具入参没有文档位置，台账也不写 docBasePath、不标注回落默认值，与弹框路径的 defaults_used 留痕不对等。
  目标：降级路径能取到文档位置（工具暴露入参），或至少显式回落并留痕；消费端缺省仍为 docs/requirements/<REQ>/（node-input-package.ts:198），保持向后兼容。
  验收：不传位置时返回值/台账可见「已回落默认」；传自定义位置（如 docs/rfcs/）时产物路径按它生成。
- **FR-8: pm 弹框与 DSH 原生提问弹框可区分（来源标志）**
  现状：reqboard_ask_confirm / 立项四问 / 验收弹框与宿主原生 ask_user_question 走的是同一个通道（adapters/UserQuestionsAdapter.ts:40-44 直接把 AskQuestion 交给宿主的 userQuestions 服务），弹框本体没有任何「来自 pm 插件」的标识——人分不清是谁在问，只能读正文（本次需求分析阶段用户即因此提出该反馈）。
  目标：pm 插件发起的提问统一带一个可辨识的来源标志（落到 header 前缀，或宿主若支持的扩展字段，例如「📋 PM 确认」），标志由 pm 侧在构造 questions 的三处统一注入（use-cases/AskConfirm.ts:96-100、AcceptSheet.ts:63-71、CaptureRequirement.ts:142），**不依赖 agent 在 question 文本里手写 emoji**；宿主原生 ask_user_question 保持原样，两者一眼可辨。
  验收：A6。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-41f158、t-9a6bdb、t-6eca2a、t-7e9633、t-145cb0 |
| FR-2 | ✅ 已接收 | t-954348 |
| FR-3 | ✅ 已接收 | t-41f158、t-5f2a65 |
| FR-4 | ✅ 已接收 | t-6cfab3 |
| FR-5 | ✅ 已接收 | t-216224 |
| FR-6 | ✅ 已接收 | t-41f158、t-7b5e7a、t-145cb0 |
| FR-7 | ✅ 已接收 | t-41f158、t-fbde12 |
| FR-8 | ✅ 已接收 | t-9f96a1 |

> 无未接收条款（8 条全部有落点）。

<!-- reqboard:marks:end -->

## 7. 接口与数据契约

| 接口面 | 现状 | 目标 | 兼容性 |
|---|---|---|---|
| reqboard_submit | kind 仅 requirement / plan / verification / archive | 增补 design 种类，或由新工具承担登记 | 纯新增，既有四值语义不变 |
| reqboard_status | 不返回设计文档逐份登记态 | 新增逐份登记态字段 | 新增字段，旧消费方忽略即兼容 |
| reqboard_ask_confirm（弹框路径） | 超时被判失败；成组确认与逐份状态表述冲突 | 超时不再判失败；补成组/逐份语义 | 返回字段只增不改 |
| 工具绑定层 | 零参调用被拒 | 接受零参（等价 {}） | 放宽，不影响有参调用 |
| 弹框来源标志 | pm 弹框与宿主提问同通道、弹框本体无来源标识 | pm 侧统一注入可辨识标志（header 前缀，或扩展字段） | 不改宿主 schema；若走扩展字段则只增不改 |
| 新增登记能力 | 不存在 | 必须幂等（同 path 已登记 → 跳过），与 ArtifactSync 语义一致 | 与既有自动发现共用幂等判定 |

## 8. 迁移与兼容

- 老需求记录（artifacts 为空/undefined 的 legacy）继续放行，不因本次改动被追溯拦下（沿用既有 isLegacy 分支）。
- 不改设计文档命名与目录结构；REQ-260924162957-2cd3 这类「已写完 6 份设计文档」的历史需求，修复后应能直接走通 design→decomposing。
- 回滚：不迁移数据、不改台账必填字段；新增字段缺失时消费者按旧行为处理。

## 9. 非功能需求

- **NFR-1: 台账三面一致**
  实测（本次立项）：reqboard_create 返回 status=draft，约 1 分钟后系统自动推进 draft→brainstorming（留痕正确），但 reqboard_status 的 next_actions 只列 draft。要求修复后三面一致可解释：要么 create 直接返回终态，要么明示「已被接手窗口会自动推进」。
- **NFR-2: 既有护栏强度不降低**
  REQBOARD_EVIDENCE_FAKE（拒绝伪造证据）、REQBOARD_MOVE_REJECTED（文档未齐不放行）、同一产物不重复弹框，三条必须继续生效；不得以「改善体验」为由放松任何人工闸门。

## 10. 验收汇总

| 编号 | 验什么 | 怎么验 | 预期 |
|---|---|---|---|
| FR-1 | 登记入口 agent 可调 | 新建测试需求，只调工具登记 5 份设计文档 | 一次通过，无 REQBOARD_MISSING_ARTIFACT |
| FR-2 | 两种状态文案区分 | 分别构造未登记 / 未落章，读 move 拒绝文案 | 文案不同，且各带下一步命令 |
| FR-3 | 弹框不受 120s 影响 | run_code 内发起弹框，隔 5 分钟作答 | confirmed=true，无 deadline 报错 |
| FR-4 | 零参可调 | tools.reqboard_status() | 正常返回 |
| FR-5 | 提示词含登记说明 | 片段基线快照断言 | 含登记命令，且明确不要猜 kind=design |
| FR-6 | 断点留痕 | 注入一次上游 TIMEOUT | 续跑包/留痕含断点章节 |
| FR-7 | 位置问项不丢 | 不传 / 传自定义位置各一次 | 回落留痕 / 路径生效 |
| FR-8 | pm 弹框可辨识 | 先后发起 pm 弹框与宿主提问 | 不读正文即可分辨来源，且标志非 agent 手写 |

测试层级（供 E2E 覆盖读数）：

| 层级 | 范围 |
|---|---|
| 单元 | 闸门文案、零参绑定、docBasePath 回落、断言幂等 |
| 集成 | SubmitArtifact / AskConfirm / Move 工具链 + ArtifactSync 幂等 |
| E2E | 脚本复跑 REQ-2cd3 设计阶段：落盘 5 份设计文档 → 登记 → 确认 → move 通过 |

## 11. 风险与开放项

- 开放项 1：登记入口形态（新工具 vs reqboard_submit 增 kind=design）——design 阶段定，两者都必须保证幂等与 legacy 兼容。
- 开放项 2：FR-3 的异步化会牵动工具调用模型（投递 + 回执），可能触及宿主 run_code 语义，design 阶段需评估面。
- 开放项 3：FR-6 断点留痕的落点（Session state 还是需求台账）必须在 design 里定死，避免「两份真相」。
- 风险：改动落在 packages/web/dsh-pmboard（:13080 实际加载的插件），须走 worktree + relink 体检，避免硬链接副本静默停在旧版本。
