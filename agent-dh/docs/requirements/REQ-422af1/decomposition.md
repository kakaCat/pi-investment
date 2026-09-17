# REQ-422af1 拆分 · 代码变更盘点与任务划分

> 阶段：decomposing · 窗口 w-41e7e4cd · 上游：plan.md（已批准）+ design/*.md

## 1. 代码层面变更盘点（对照需求 + 技术设计）

### 1.1 新增

| 内容 | 文件 |
|------|------|
| 路由唯一入口与类型 | src/domain/prompt/{index,router,budget,types}.ts |
| 分片源（六节点 × light/heavy + common + 类型档） | src/domain/prompt/fragments/**/*.md |
| 分片生成物 | src/domain/prompt/generated/fragments.ts |
| 生成器与同步门禁 | scripts/inline-prompt-fragments.mjs、scripts/check-prompt-fragments.mjs |
| 注入留痕（ring buffer 写读） | src/application/internal/injection-log.ts |
| 测试 | tests/prompt-router.test.ts、tests/prompt-gates.test.ts、tests/prompt-baseline.test.ts |
| 基线快照 | tests/fixtures/stage-prompts-baseline.json |
| 看板只读块（注入留痕可见） | src/client/ 内新增信息块 + 渲染函数 |

### 1.2 修改

| 文件 | 改什么 |
|------|--------|
| src/domain/stage/StagePromptSpec.ts | 常量直取退役：文本搬进分片兜底档；仅保留类型与「下一步」派生 |
| src/application/internal/capture-section.ts | 每回合注入改调 resolveStagePrompt（传 stage/difficulty/category/budget） |
| src/adapters/CaptureHook.ts | 状态转移后注入改调 resolveStagePrompt（同一入口，INV-1） |
| src/client/*（看板需求详情） | 增加「当前节点 + 本次注入 routeKey/片段数/字符数」只读块 |
| tests/stage-prompts.test.ts | **断言不改**（INV-7 对照物）；仅新增用例文件 |
| docs/architecture/workflow-stages.md | 增「提示词加载路由」一节 + 工具面与本路由的关系 |

### 1.3 删除

| 文件/符号 | 理由 |
|-----------|------|
| STAGE_PROMPTS 常量与 stagePromptFor 直取路径 | 双入口会绕过路由（违反 INV-1）；P0 等价核验通过后删除 |

## 2. 工作流划分与工作量预估

| 期 | 任务 | 预估 |
|----|------|------|
| P0 | 快照冻结；分片库骨架 + 生成器；路由解析；P0 落位与注入点切换；六条门禁；注入留痕 | ~2 天 |
| P1 | 六节点 light/heavy 分片内容 + 要素门禁 | ~1.5 天 |
| P2 | 类型档（六节点 × 六类型）+ 断言 | ~1 天 |
| P3 | surface 替换执行模型；结算点接入（默认关）；看板可见；文档同步 | ~2 天 |

**拆分原则**：P0 内部按"先有对照物（快照）→ 再有新通路（生成器/路由）→ 再切换（落位）→ 再验（门禁/等价）"排序，任何一步不等价就停下；P3 全部默认关，可独立回滚。

## 3. 与设计的一致性

本拆分**不含新技术决策**：数据层结论、模块目录、门禁清单、分期开关均来自 design/*.md，逐条对应。若实施中发现设计不成立（如 surface 替换违反不变量），按纪律回到 planning 重新提交计划，不在拆分阶段二次创作设计。

## 4. 拆分后修订（D-13/D-14，2026-09-17 用户澄清）

**背景**：用户明确"难度档 = 完全 superpowers skill 原文 + 渐进式披露；我们是节点推进，相当于选中，不需要匹配；加载具体内容就是披露的方式"。

**受影响任务**：

| 卡 | 原实现 | 修订后 |
|----|--------|--------|
| t7 | 按八要素**自己写**六节点 light/heavy | **vendor superpowers v6.3.0（commit b36e082, MIT）原文**作为 heavy；light 仍自写精简；新增 vendor 目录与 ATTRIBUTION；要素门禁改为"逐项核对原文八要素存在"（不再由我们重写） |
| t8 | 类型档自写 | 不变（类型档 superpowers 无对应内容，仍自写） |
| t9/t10 | surface 替换 | 不变 |

**追加验收锚点（t7）**：src/domain/prompt/vendor/superpowers/ATTRIBUTION.md 存在且写明 repo/tag/commit/许可/抓取时点；`.dsh-data` 外无运行时读盘（vendor 走构建内联）；tests/prompt-tiers.test.ts 断言 brainstorming/heavy 与 vendor 原文逐字一致（不得改写）。

**体量事实**：14 份合计约 14.4 万字节；单份最大 32,339（subagent-driven-development）。故 heavy 只注入**主 skill 全文**，附属 skill 按需注入（同一次最多挂一个）——避免 implementing 节点一次吃掉约 5.6 万字节。

## 5. t7 实施口径（据 brainstorming 对照结论，2026-09-17）

证据：docs/requirements/REQ-422af1/design/brainstorming-vs-superpowers.md（234 行；覆盖 superpowers 250 行文件的全部 9 个标题 + 15 处粗体子节；122 处行号引用）。

**差距实测**：等价 14 ｜ 更弱 6 ｜ 我方更强 2 ｜ 我方独有 1 ｜ **完全缺失 21**（三路径框架、Red Flags 表、Spike/Bounded 清单、YAGNI、Design for isolation、Working in existing codebases、设计覆盖面、视觉伴侣 5 处、提议独立成一条消息、git commit 设计文档等）。我方原文对 YAGNI/Red Flags/isolation/Spike 的 grep 命中数 = 0。

**t7 定稿口径**：

1. brainstorming/heavy **整份 vendor 250 行 / 15,456 字节原文**（不拆分、不改写）——保证 t7 的"与 vendor 原文逐字一致"断言成立。
2. 注入顺序固定为三段：`vendor 原文` → `overrides 附加片段（floor，不可裁）` → `common/iron-rules`。
3. overrides 附加片段 6+1 条：节点交棒行、落盘路径、**显式否掉 server/http 与浏览器本体**、任务语义（把 skill 里的 create-a-task 映射到 reqboard 任务卡）、闸门（reqboard_ask_confirm）、节点归属。
4. brainstorming/light 自写 5 条：L1 目标可证伪 / L2 ≤3 条边界 / L3 轻路径依据+单向升级 / L4 闸门+下一步 / L5 **轻档≠无产物**（对抗原文对 Spike/Bounded 的"无 spec"豁免——与本仓产物闸门冲突，故显式否掉该豁免）。
5. 其余五节点映射：planning→writing-plans(7,053B)；implementing→executing-plans 主 + TDD/SDD/worktrees/dispatching/code-review 附属按需；accepting→verification-before-completion 主 + requesting/receiving-code-review 附属；archived→finishing-a-development-branch；横切 systematic-debugging / writing-skills / using-superpowers。
6. **口径例外**：**decomposing 在 14 份 skill 里无对应**（14 份里没有拆分/DAG 相关 skill）——heavy 无法 vendor 原文，需单独定口径（见下）。


## 6. P0 实施裁决（父窗口，2026-09-17 对 t1-t6 复核后）

**复核方式**：不采信 subagent 自述，父窗口亲自重跑——同步门禁正常态 exit 0、亲手故障注入（改 md 不重建）exit 1 且恢复后 exit 0、直取 grep 0/0、四个新测试文件 50/50 通过、快照与分片/生成物落盘核实。

**对三处偏离的裁决**：

| 偏离 | 事实 | 裁决 |
|------|------|------|
| (a) STAGE_PROMPTS / stagePromptFor 未物理删除，改为派生兼容视图 | 冻结测试 tests/stage-prompts.test.ts 直接 import 并索引这两个符号，删除必然编译失败——与「P0 零行为变更」硬约束冲突；实测 src 下 STAGE_PROMPTS[ 与 stagePromptFor( 直取命中均为 0 | **接受**：P0 期以派生视图兜住冻结测试；**P1 引入一步「冻结测试迁移」**（把断言迁到 resolveStagePrompt 后删除兼容壳），届时等价性已由 prompt-baseline.test.ts 与快照独立保证 |
| (b) 链声明用结构化表 domain/prompt/chain.ts 承载，未写进兜底档文本 | 写进文本即破坏逐字等价（6 份现文本无此行）；门禁 5 已校验该表（label 含「下一步：」+ next ∈ REQ_TRANSITIONS + tool 已注册） | **接受**：P1 文本物化（那时注入文本按设计变化，不再受等价约束） |
| (c) common/iron-rules 在 P0 为空文件（0 字节），⑤ 层恒并入但贡献 0 字符 | 一旦有正文，解析结果就不等于快照 | **接受**：铁律正文随 P1 落地；P0 保留「⑤ 层存在且恒并入」的结构事实 |

**纪律评价**：实施方主动上报偏离而非静默改写设计，做法正确，予以保留。三处均属「设计内部自相矛盾」而非实施偷工，故不改设计、只记录。


## 7. P1 口径补充与关单状态（2026-09-17）

**decomposing 口径例外（用户拍板）**：decomposing 在 superpowers 14 份里无对应 skill → **自写完整档 + 抽可迁移要点**（不 vendor 任何原文）。理由：我们的拆分纪律（变更盘点 / 卡四要素 / 依赖批次 / 确认门）已成熟，skill 里没有可对齐的拆分内容。

**P0 关单状态**：

| 卡 | 状态 | 说明 |
|----|------|------|
| t1 快照 | done | 父窗口复核：连跑两次 diff 为空、先于取词改动 |
| t2 生成器 | done | 复核：同步门禁亲手故障注入（改 md → exit 1，恢复 → exit 0） |
| t3 路由 / t4 落位 / t5 门禁 / t6 留痕 | in_review（待关） | 内容已复核通过（50/50 新测试、基线逐字一致、六门禁可红）；**done 被构建新鲜度门拦下**：t7 正在改 src，lib/client.js 立即变旧 → 属门禁正确行为，等 t7 落地后 `pnpm build:client` 再关 |

**证据**：全量套件 1 failed | 678 passed（唯一失败为改动前既有）；tsc 0 错误；四条既有机械门禁全绿。


## 8. P1（t7）落地记录与设计偏差（父窗口复核后）

**分片目录结构（已定型）**：

    fragments/<stage>/light.md              轻档（自写）
    fragments/<stage>/heavy.md              heavy 主内容（5 节点=vendor 原文镜像；decomposing=自写）
    fragments/<stage>/heavy/overrides.md    overrides 附加片段（priority=floor，永不裁）
    fragments/common/iron-rules.md          ⑤ 全局铁律（P1 起有正文）

**父窗口独立复核结论**：14/14 vendor 文件与 origin/main 逐字节一致；brainstorming/heavy.md 与 vendor 原文 cmp 逐字节一致；六节点 light(855-1218) < heavy(1641-17193) 6/6；全量 1 failed(既有) | 742 passed、tsc 0 错误；兼容壳代码引用 0（仅 2 处注释提及）。

**三处设计偏差（已接受并记录）**：

| 偏差 | 事实 | 裁决 |
|------|------|------|
| 注入预算 8000 → **24000** | heavy 主 skill 按设计永不裁，实测最大解析结果 17,193 字符（brainstorming/heavy），8000 装不下 | **接受**：预算上调是"heavy=原文"的必然结果；已回写 design/fragments.md §8 |
| 新增 `isPromptStage` 闸（draft/done/canceled 不注入） | 铁律正文非空后，draft 状态会只捞到 ⑤ 铁律，被误判为"有阶段提示词" | **接受**：这是 P1 引入正文后的必要回归修复，属实现细节不属设计变更 |
| router 注入顺序修正 | 原按 id 混排会让 ⑤ 铁律排到节点内容之前（planning/implementing/decomposing） | **接受**：修正为「①-④ 选中片段在前 → ⑤ 铁律在后」，符合 design/architecture.md §4 的合并语义 |

**未完成（明确记录，不掩盖）**：按需片段（TDD / SDD / worktrees / dispatching / code-review / systematic-debugging / writing-skills / using-superpowers）**只 vendor 落盘、未注册为分片**——注册即需被路由或 include 命中，否则违反门禁 4「无孤岛」；include 机制属"节点内子步骤"设计，超出 t7 六节点两档范围，留待后续需求。


## 9. 遗留问题（本需求边界外，需另立卡/需求）

**浏览器包包含提示词分片（父窗口独立确认）**：

- 事实：`grep -c "Three Paths" packages/pages/dsh-pmboard/lib/client.js` = 1；bundle 由 217,154 → 293,225 bytes（约 +76KB），其中 t11 自身仅约 +2KB。
- 链路：shared/protocol → domain/stage/StagePromptSpec → domain/prompt/index → generated/fragments（t7「节点即选择器」后 StagePromptSpec 引用 prompt/index）。HEAD 的 bundle 里没有这些分片文本，是本次重建让它第一次进入客户端产物。
- 性质：① 体积（每次会话下载 +76KB）② 面（提示词库发到浏览器，虽非机密但没必要）。提示词是**服务端注入**用的，客户端不需要。
- 处置建议：另立需求收敛（动 shared/protocol 或 domain/prompt 的导出边界，让 client 侧不经过 prompt/index）。本需求不私扩范围。

**待办提醒**：REQ-422af1 全部任务收口后需**统一重建一次 client 产物**（并行写入期间 src mtime 持续变化，逐次重建会互相作废）。


## 10. 浏览器包泄露：已修复（本需求引入的回归，父窗口亲修）

**结论**：修好了。`lib/client.js` **293,225 → 209,934 字节**（-83KB），`grep -c "Three Paths" lib/client.js` = **0**，说明提示词分片已不再进浏览器包。

**根因（精确定位）**：`src/shared/protocol.ts:393` 有一行**值再导出**

    export { ALL_STAGE_PROMPT_KEYS } from '../domain/stage/StagePromptSpec.js'

客户端要打包 shared/protocol，于是把 StagePromptSpec 拖进来；而 t7 之后 StagePromptSpec 反过来 `import PROMPT_STAGES from ../prompt/index.js` → 一路拉进 generated/fragments（全部分片文本）。HEAD 的 bundle 里没有这些文本，是本需求的重建让它第一次进了客户端产物 —— 故判定为**本需求引入的回归**，按回归修复处理，不另立需求。

**修法（反转依赖，不删任何能力）**：让 StagePromptSpec 还原为**叶子模块**（权威定义 6 个阶段键，零 import），`domain/prompt/types.ts` 改为从它引用（依赖方向变为 prompt → stage）。这样 shared/protocol 的值再导出只带 6 个字符串，不再牵引分片库。

**验证**：tsc exit 0；5 个提示词测试文件 267/267 通过；build:client + 哨兵通过（209,934 bytes）。

**过程教训（记录）**：修好后首次 tsc 报 exit 2，复跑 exit 0 —— 原因是 t10 子代理正在并发改 src，门禁跑在"半个写入"的状态上。**结论：最终门禁必须在所有写入者停止后再跑一次**。

