# Agent 领域拆分：三 Agent 架构（Domain Split）

- 日期：2026-08-13
- 状态：待评审
- 关联：`2026-08-13-memory-recall-redesign.md`（共享 flow 分类法；记忆 Agent 是其中召回审计的执行者）

---

## 1. 动机与目标

单个通用 agent 处理所有领域的事情，工具 ~110 个还在增多，四个痛点（用户 2026-08-13 确认全选）：

- **误操作风险**：扫描任务里 agent 可能误调交易工具——提示词约束不可靠，要结构性消除
- **专业深度**：交易/进化/记忆是不同领域，一份通用提示词写不深
- **成本**：例行扫描不需要强模型
- **制衡/安全**：审计/评审不该由执行者自己做（运动员/裁判员分离）

**目标**：拆为三个领域 Agent，责任明确化；对用户仍是一个系统（统一入口）；内部提示词、工具、记忆三层硬隔离。

**明确不做的细拆**：不做按任务粒度的多角色（scan-quick/analyst 等五个角色的方案已被用户否决为"太细"）；金融执行保持一个 agent，只允许渠道级提示词微调。

## 2. 三 Agent 定义

| | 🏦 金融 Agent（Worker） | 🧬 进化 Agent（Evolver） | 🧠 记忆 Agent（Mnemonist） |
|---|---|---|---|
| 职责 | 一切执行：扫描/交易/分析/问答/盯盘响应。**现状核心不动** | RSI 递归自我改进：改/加工具、改 skill、评审系统行为、提改进意见 | 记忆全生命周期：召回审计、初标、蒸馏整理、质量巡检 |
| 系统提示词 | 现有 8 层继续演进；Channel 层按渠道微调（飞书/TUI/web） | 改造者人设 + 改动纪律（worktree 规则、测试先行、autoExecute 默认关） | 图书管理员人设 + 相关性判定标准 + 标注契约 |
| 工具组 | FIN_TOOLS（现状主体：数据/交易/分析） | EVOLUTION_TOOLS（代码与 skill 读写、claude_code 委托、evolution 工具）**无交易工具** | MEMORY_TOOLS（recall_audit、memory_*、只读数据查询）**无交易工具** |
| 模型 | 按任务档位（model_switch 现状保留） | pro（改代码要强度） | flash（初标是体力活） |
| 记忆读写 | 业务域读写（daily/experience/watch…） | evolution 域写，业务域只读 | 记忆域管理权，业务域只读 |

## 3. 隔离机制（三层硬边界）

### 3.1 工具隔离（结构层，不靠提示词自觉）

- `allCustomTools` 注册表按组拆分：`FIN_TOOLS` / `EVOLUTION_TOOLS` / `MEMORY_TOOLS` / `SHARED_BASE_TOOLS`（记忆读写、任务、计划等公共工具）。
- 会话创建时按 agent 类型过滤工具列表——**不在列表里的工具对 LLM 不可见、不可达**。模式参照 skill-guard 白名单，但作用点是会话工具注册而非运行时拦截。
- 契约：分组是**编译期常量**（TS 数组），每组工具归属唯一；新增工具必须显式归组（`npm run check:tool-refs` 扩展检查：未归组工具报错）。

### 3.2 提示词隔离

- 8 层 builder 按 agent 出变体：Identity/Soul/Tools 层各自独立。
- 金融 agent 提示词里没有"怎么改代码"；进化 agent 提示词里没有"怎么下单"；记忆 agent 提示词聚焦判定标准与标注格式。
- 金融 agent 的渠道微调只动 Channel 层（飞书简短/TUI 详细/web 带格式），其余七层共享——**不允许**为渠道复制整套提示词。

### 3.3 记忆隔离

- memory scope 读写权按 agent 划分（写权限各自封闭，读权限按需开放）：
  - 金融：读全部，写业务域（daily/experience/watch/portfolio…）
  - 进化：读全部，写 evolution 域（报告/提案/评审结论）
  - 记忆：读全部，写记忆域（标注/蒸馏产物/质量报告）
- 写权限在 memory 工具层按会话 agent 类型校验（工具知道自己在哪个 agent 会话里）。

## 4. 协作方式（共享存储即通道，无消息总线）

```
进化 Agent ──改工具/skill──→ 代码库 ──下次会话生效──→ 金融 Agent
记忆 Agent ──优化质量门/标注──→ v2 记忆服务 ←──召回── 金融 Agent
三者 ──共享 PG + 记忆库── 报告/经验/审计 互相可读
```

- 入口统一：飞书/TUI/web/调度/wake 消息**默认进金融 Agent**；进化任务（weekly_evolution 等）路由进化 Agent；记忆任务（召回审计、蒸馏）路由记忆 Agent。
- 路由点：调度任务注册时声明 `agent` 字段；wake 事件固定金融；交互渠道固定金融（渠道微调仅 Channel 层）。
- 进化 Agent 改动纪律：**skill 文件可直接改**（低风险）；**代码/工具改动走提案 + 人工/Claude 审查**（制衡落点；沿用 autoExecute 默认关契约）。
- 现阶段角色间不直接通话；如出现"进化 agent 需要金融 agent 的生产数据"类需求，经 PG/记忆库传递，不加消息总线（YAGNI）。

## 5. 与已有决定的关系

- **2026-08-07 双 agent 三权分立**：进化 Agent 是其承载架构，提案者/评审者分离语义不变。
- **skills 纳入进化写路径（P0a 评审议题）**：进化 Agent 工具组直接含 skill 读写，随 A2 落地。
- **召回重设计 spec**：记忆 Agent 是"agent 初标"执行者；召回策略表的 flow 分类与本 spec 的 agent 路由共用同一 flow 枚举（`interactive-chat`/`skill-invocation`/`scheduled-task`/`wake-event`）。

## 6. 代码落位（agent-ts）

```
src/domain/agent-roles/
  types.ts              # AgentKind = 'fin' | 'evolution' | 'memory'；RoleProfile
  profiles.ts           # 三个 profile 声明（工具组/模型档位/记忆 scope/提示词变体名）
src/infrastructure/tools/groups.ts   # allCustomTools 分组（编译期常量）
src/core/agent/system-prompt.ts      # builder 增加 agentKind 参数，出变体
src/services/scheduler/init-agent-tasks.ts  # 任务注册增加 agent 字段
src/api/extensions/                  # 如需 per-agent 扩展差异在此处理
```

会话工厂改动：`createSession({ agentKind })` → 按 profile 过滤工具 + 选提示词变体 + 模型档位（经 services/llm 会话级，不动全局 llm-state.json）。

## 7. 阶段计划与多模型执行策略

**分工原则**（用户 2026-08-13 指令）：执行模型能力有限，契约写死（文件/接口/命令/验收），Claude 终审。难度：L=机械可抄（其他模型）；M=局部架构+契约可写死（其他模型+Claude 审查）；H=架构判断/跨层契约（Claude 亲做）。

**Claude 验收规程**（每个非 Claude 任务后必做）：对契约逐字核对 → 亲自跑验收命令 → 回查事实源。

| 阶段 | 任务 | 内容 | 难度 | 执行者 | 验收 |
|---|---|---|---|---|---|
| A0 | A0-T1 | `tools/groups.ts` 分组：全部 ~110 工具归组（FIN/EVOLUTION/MEMORY/SHARED），check:tool-refs 扩展校验未归组报错 | M | 其他模型 | `npm run check:tool-refs` 过；分组 diff Claude 逐组审 |
| A0 | A0-T2 | `domain/agent-roles/`（types + 三 profile 声明），默认 fin = 现状全集 | L | 其他模型 | jest：fin 工具集与现状 allCustomTools 完全相等 |
| A0 | A0-T3 | 会话工厂 `agentKind` 参数（默认 fin，零行为变化）+ system-prompt builder 变体机制 | H | **Claude** | 现有全部测试过；fin 会话工具/提示词与现状逐字节一致 |
| A1 | A1-T1 | 记忆 Agent：MEMORY 组提示词 + `recall_audit` 工具 + 会话接入 | M | 其他模型 | 记忆会话无交易工具（结构性测试）；recall_audit list/stats/feedback 真跑通 |
| A1 | A1-T2 | 每日召回审计任务注册（agent=memory，初定 19:00） | L | 其他模型 | 调度表有记录；真触发一次产出日报 |
| A2 | A2-T1 | 进化 Agent：EVOLUTION 组提示词（含改动纪律）+ skill 文件读写工具 | M | 其他模型 | 提示词含 worktree/测试/autoExecute 纪律条款（Claude 审文案） |
| A2 | A2-T2 | weekly_evolution 迁移到进化 Agent + 提案-评审流程接线 | H | **Claude** | 跑一次周度进化干跑（dry-run），提案落 evolution 域、不自动执行 |
| A3 | A3-T1 | 金融 Agent Channel 层渠道微调（飞书/TUI/web） | M | 其他模型 | 三渠道各发一条消息，提示词快照 diff 仅 Channel 层不同 |
| A4 | A4-T1 | 分账统计：按 agent 统计 token 成本/任务质量，观察一周调档 | M | Claude+记忆Agent | 统计日报产出一周 |

**依赖关系**：A1 依赖召回 spec 的 P1-T4（审计 API）。A0 是全部前置。

## 8. 风险

- **工具分组错误**（金融工具漏进 FIN 组）→ A0-T1 的 Claude 逐组审查 + fin 等价性测试兜底。
- **进化 Agent 改坏 skill** → skill 改动直接生效但可由 git 回滚；代码改动强制提案制。
- **三 agent 记忆域权限串味** → 工具层校验 + A4 观察期抽查。
- **渠道微调漂移**（Channel 层越改越大）→ A3 契约：Channel 层只改语气/格式，禁止放业务规则。
