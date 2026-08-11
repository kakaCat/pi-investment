# GenericAgent 学习报告 —— 对 pi-investment 的优化启示

> 调研对象：https://github.com/lsdefine/GenericAgent（已克隆至 `/Volumes/ORICO/doc/github/GenericAgent`）
> 调研日期：2026-08-07
> 调研方式：通读 README + 核心源码（agent_loop.py / agentmain.py / ga.py / llmcore.py / reflect/ / memory SOP）
> 目的：提炼可落地机制，指导 agent-ts、quantsys-v2、web-frontend 三项目优化

---

## 一、GenericAgent 是什么

一个**极简、可自我进化的自主 Agent 框架**：约 3K 行种子代码、9 个原子工具、约 100 行 Agent Loop，让任意 LLM（Claude/Gemini/Kimi/MiniMax）获得对本地计算机的系统级控制（浏览器、终端、文件系统、键鼠、屏幕视觉、ADB）。

核心哲学：**不预设技能，靠进化获得能力。** 每解决一个新任务，执行路径自动固化为 Skill 写入记忆，越用越强。有 arXiv 技术报告，主题词是 **Contextual Information Density Maximization（上下文信息密度最大化）**——这是它一切设计的总纲。

```
[新任务] → [自主摸索: 装依赖/写脚本/调试验证] → [固化为 Skill 写入记忆层] → [下次同类任务一句话调用]
```

---

## 二、核心机制深拆（源码级）

### 2.1 分层记忆系统 L0–L4（最值得借鉴）

| 层 | 内容 | 关键约束 |
|---|---|---|
| **L0** | 元规则 + 记忆管理 SOP | 最高优先级行为约束 |
| **L1** | `global_mem_insight.txt` 极简索引 | **硬约束 ≤30 行**！只做"场景关键词 → 记忆位置"的指针 |
| **L2** | `global_mem.txt` 环境事实库 | 路径/凭证/配置等稳定事实，按 `## [SECTION]` 组织 |
| **L3** | `memory/` 目录下几十个 SOP 文件 | 任务级可复用流程（.md + 配套 .py 脚本） |
| **L4** | 会话归档 | scheduler 每 12h 自动压缩原始会话，供长程召回 |

**记忆管理 SOP 的四条公理**（写在 L0，每次蒸馏记忆时强制重读）：

1. **No Execution, No Memory** —— 只有行动验证成功的信息才能写入；严禁把模型的固有知识、推理猜测、未执行的计划写入记忆
2. **已验证数据神圣不可删** —— 重构/GC 时可压缩、可迁移层级，绝不能丢失准确性
3. **禁止存储易变状态** —— 时间戳、PID、Session ID 等一律不入库
4. **最小充分指针** —— 上层只留能定位下层的最短标识，多一词即冗余

> 对照：pi-investment 的 MEMORY.md 已 60+ 条全量进上下文，没有"索引/细节"分层；自我进化审计（2026-08）发现蒸馏环节会写入未验证经验——公理 1 正好对治。

### 2.2 Agent Loop 的省 token 工程（agent_loop.py 全文仅 132 行）

**(a) 每轮注入 anchor prompt**（`ga.py:_get_anchor_prompt`）：
- `<history>`：近 30 轮的一句话摘要，**每 2 轮**重新注入一次
- `<earlier_context>`：更早历史折叠成 `[Agent]（N turns）` 单行，**每 4 轮**注入一次
- `<key_info>`：当前任务的工作记忆（agent 自己通过工具维护）

**(b) 轮次触发的系统纠偏**（`ga.py:turn_end_callback`）：

| 触发 | 注入内容 | 作用 |
|---|---|---|
| turn % 10 | 重新注入全局记忆 L1/L2 索引 | 防止长任务中遗忘能力 |
| turn % 13 | "存 checkpoint，停止无效重试，换策略：1) 探测物理边界 2) 重读 SOP" | 防死循环 |
| turn % 31 | "把关键发现**写入文件**，不要只放工作记忆" | 防信息丢失 |
| turn % 175 | 强制 `ask_user` 汇报进展 | 防盲目长跑 |

**(c) `no_tool` 拦截**（`ga.py:do_no_tool`）：模型一轮没调任何工具时引擎自动触发——
- 空响应 → 自动重试（3 次后退出）
- 响应截断（流异常/max_tokens）→ 提示分小步重来
- **只贴了一大段代码没调工具** → 引擎追问"你是要执行还是仅展示？"
- plan 模式下声称完成但没跑验证步骤 → **拦截完成声明**，强制先 VERIFY

**(d) 历史压缩**（`llmcore.py:compress_history_tags`）：每 5 轮扫描一次，把旧消息里的 `<thinking>/<tool_use>/<tool_result>` 截断到 800 字符。

效果：上下文窗口稳定 <30K，是主流 agent（200K–1M）的零头，token 成本低一个数量级。

### 2.3 Reflect 模式 —— 自主性的极简实现（reflect/）

`python agentmain.py --reflect <script.py>`：加载一个监控脚本，每 INTERVAL 秒调 `check()`，**返回字符串就作为 prompt 触发一次完整 agent 任务**。脚本热重载（mtime 变化自动 reload）。现有实现：

- **`scheduler.py`**（131 行）：cron 式定时任务。任务 = `sche_tasks/*.json`（prompt + repeat + schedule + enabled）；执行记录 = `done/<时间戳>_<任务id>.md`；冷却窗口防重复触发；超过 max_delay（默认 6h）不补跑。**没有 APScheduler、没有数据库，全是文件。**
- **`goal_mode.py`**（113 行）：**时间预算驱动的自驱循环**——"持续优化 X 共 N 小时"，预算没耗尽 agent 无法宣告完成，每次唤醒在 创造 → 检验（轮换身份：读者/测试工程师/领导…）→ 改进 三阶段中选一个。
- **`agent_team_worker.py` / checklist_master.py**：多 agent 协同。

> 对照：pi-investment 的 scheduler daemon 经历过合盖休眠丢任务、misfire、僵尸 run 等多轮事故。GA 的方案简单一个数量级：文件即任务、文件即状态、错过不补跑。

### 2.4 工具集：9 个原子工具 + code_run 万能扩展

`code_run / file_read / file_write / file_patch / web_scan / web_execute_js / ask_user / update_working_checkpoint / start_long_term_update`

关键不是"少"，而是**能力增长路径**：缺能力 → agent 用 `code_run` 现场装包写脚本 → 验证成功 → 固化为 L3 SOP（.md 流程 + .py 脚本）→ 下次一句话调用。

几个工具的细节设计很值得抄：
- `file_patch`：old_content 必须**唯一匹配**否则报错并给出建议（"提供更长上下文"或"分小步改"）；匹配 0 次时提示"先 file_read 确认现状"
- `file_read`：读不到文件时自动用 difflib 在邻近目录找相似文件名返回 "Did you mean"；大文件按行数动态计算单行截断长度
- `file_write`：单次写入 >5000 字节时，下一轮回注系统提示 **"WRITE TOO LONG! MUST RECHECK HALLUCINATIONS!"**——大写入是幻觉高发区
- `web_scan`：工具描述里直接写"应当多用 execute_js，少全量观察 html"——**把使用策略写进工具描述**，比写进系统提示更有效

### 2.5 TMWebDriver：真实浏览器而非无头沙箱

Chrome 扩展 + 本地 WebSocket/HTTP server（依赖只有 bottle + simple-websocket-server），驱动**用户真实浏览器**：保留登录态、Cookie、扩展、指纹。reCAPTCHA v3 拿 0.9 真人分，SannySoft 56/56、bot.incolumitas 36/36 全过。配合 `simphtml.py`（873 行）做信息密度驱动的 HTML 简化（过滤边栏/浮动元素，只留主体）。

### 2.6 子 agent 与干预：纯文件协议

`--task <IODIR>` 起后台子 agent 进程，主 agent 通过目录文件交互：`input.txt`（下达）、`reply.txt`（追问）、`_stop`（终止）、`_intervene`（注入指令，下一轮 prompt 以 `[MASTER]` 前缀插入）、`_keyinfo`（注入工作记忆）。零 IPC 依赖，天然可审计、可恢复。

### 2.7 多模型容错

`llmcore.py` 支持多 key 配置 + **MixinSession**：多家模型串成 fallback 链，一家挂了自动切下一家且**保留历史**。`next_llm()` 运行时热切换。

---

## 三、对照 pi-investment 现状的差距分析

| 维度 | GenericAgent | pi-investment 现状 | 差距 |
|---|---|---|---|
| 上下文管理 | 密度最大化：折叠历史+定期回注+标签压缩，稳定 <30K | agent-ts 1M 上下文配 128K 工作窗口，靠 SDK 截断 | **大**。成本与噪声差距一个数量级 |
| 记忆分层 | L0-L4 硬约束，索引 ≤30 行 | MEMORY.md 60+ 条全量进上下文 | **中**。缺"索引/细节"分离 |
| 记忆质量 | No Execution, No Memory 公理 | 审计发现蒸馏会写入未验证经验 | **中**。缺写入门禁 |
| 死循环防护 | turn%13/31/175 引擎侧强制纠偏 | 依赖模型自觉；wake LLM 错误曾被静默吞掉 | **大**。引擎侧无兜底 |
| 空调工具检测 | no_tool 拦截+大写入幻觉警告 | DeepSeek one-tool-at-a-time quirk 只能靠提示词 | **中** |
| 定时任务 | 131 行文件式 scheduler，错过不补跑 | daemon + APScheduler，多次休眠/misfire/僵尸事故 | **理念差异**，各有取舍 |
| 能力进化 | code_run 现场扩展 → 固化 SOP | 60+ 预置工具 + 缠论/记忆/经验三条真实闭环 | **理念差异**：预置 vs 生长 |
| 子任务干预 | _intervene/_keyinfo 文件注入 | gateway + wake channel，曾崩溃且难复现 | **中**。文件协议更可调试 |
| 多模型 | MixinSession 自动 fallback 保历史 | model_switch 需手动，无自动降级 | **小** |

**但要客观**：两项目标不同。GA 是通用电脑操作 agent，pi-investment 是垂直领域（投研）系统，60+ 领域工具封装了数据契约（如 kline amount 单位、资金流万元），这些契约本身是护城河，不该砍。该学的是**机制**，不是**形态**。

---

## 四、优化建议（按优先级）

### P0 —— 直接解决已发生的事故

**1. agent-ts：引擎侧纠偏注入（对标 turn%13/31/175）**
- 在 agent loop 里加 turn 计数，按周期注入系统提示：
  - 每 10 轮：回注核心记忆索引
  - 每 13 轮：强制 checkpoint + "停止无新信息的重试"
  - 每 30 轮：强制把关键发现写入文件
  - 每 150+ 轮：强制 ask_user/上报（对接 web-frontend 通知）
- 价值：直接防 DeepSeek 长跑死循环；不依赖模型自觉
- 工作量：小（agent loop 一处改动）

**2. agent-ts：no_tool 拦截器**
- 模型一轮未调工具时引擎检测：① 空响应→自动重试；② 响应以单个大代码块结尾→追问"执行还是展示"；③ 完成声明但无验证痕迹→拦截
- 价值：对治 one-tool-at-a-time quirk、"光说不练"、wake LLM 静默失败那类事故
- 工作量：小

**3. agent-ts 记忆蒸馏：写入门禁（No Execution, No Memory）**
- 在记忆/经验蒸馏 prompt 和审核逻辑里加入公理：**只允许写入有工具调用证据链的信息**；蒸馏输出必须引用证据（工具结果位置）
- 价值：对治自我进化审计发现的"未验证经验入库"问题
- 工作量：小（prompt + 校验函数）

### P1 —— 结构性省 token 与可观测性

**4. agent-ts：MEMORY.md 分层改造（L1 索引 ≤30 行 + L2/L3 细节文件）**
- MEMORY.md 只留"场景关键词 → 记忆文件名"一行式指针；细节留在各 memory 文件里，agent 按需 file_read
- 价值：每次会话节省数千 token；条目可继续增长不撑爆上下文
- 工作量：中（需要一次性重构 + 迁移现有 60+ 条）

**5. agent-ts：历史折叠注入（anchor prompt 机制）**
- 长会话中把 N 轮前的历史折叠成单行摘要，按周期回注；旧的 tool_result 截断
- 价值：盯盘/长任务场景的 token 成本降一个量级
- 工作量：中

**6. quantsys-v2：大结果写盘 + 引用返回**
- 对标 `save_to_file` 模式：工具返回大结果（如全市场扫描、长 K 线）时自动写盘，只返回摘要 + 文件路径
- 价值：减少 agent 上下文被数据灌爆
- 工作量：中（逐工具改造，先改返回最大的 5 个）

**7. web-frontend：turn 级运行轨迹可视化**
- GA 的 `temp/model_responses/*.txt` 每次响应全量落盘天然可回放。pi-investment 可在 dashboard 增加"agent 当前 turn / 最近注入的系统纠偏 / checkpoint 内容"面板
- 价值：配合 P0-1/2，让纠偏机制的运行状态对人可见，出事故不用再翻 jsonl
- 工作量：中

### P2 —— 自主性升级

**8. agent-ts：Goal Mode（时间预算自驱循环）**
- "持续优化策略 X 共 N 小时"：预算内 agent 无法宣告完成，唤醒时在 创造/检验/改进 轮换；检验阶段强制换视角（回测工程师/风控/对手盘视角）
- 与四层节奏进化设计互补：周蒸馏管"沉淀"，Goal Mode 管"饱和投入"
- 工作量：大

**9. agent-ts：子 agent 文件协议兜底**
- wake channel 之外增加 `_intervene` / `_keyinfo` 文件注入通道（watch_manage 失败时也能人工兜底干预）
- 价值：文件协议可调试性远好于内存态通道（wake 崩溃难复现的教训）
- 工作量：小

**10. quantsys-v2 / agent-ts：多模型自动 fallback**
- 对标 MixinSession：配置多家模型 fallback 链，一家 401/超时自动切下家且保留历史
- 价值：直接防"LLM 401 静默丢失"类事故复发
- 工作量：中

**11. 浏览器数据源：真实会话采集（对标 TMWebDriver）**
- 东财/新浪频繁封 IP 的背景下，可考虑 Chrome 扩展 + 本地 WS 方案复用用户真实浏览器会话取数，作为反封禁的终极降级层
- 工作量：大，仅在封禁持续恶化时考虑

---

## 五、不建议照搬的

1. **不要砍工具数量** —— 60+ 领域工具的契约封装是护城河；GA 的"9 工具"适合通用电脑操作，不适合有强数据契约的投研
2. **不要全面文件化替代 PG** —— GA 的文件式 scheduler 简单但缺并发与审计；pi-investment 的数据审计链是核心资产。可借鉴的是"任务定义文件化、错过不补跑"的策略，不是存储层
3. **不要引入真实浏览器作为主数据通道** —— 维护成本高，仅作降级备选

---

## 六、参考文件索引（本地克隆）

| 主题 | 文件 |
|---|---|
| Agent Loop 全文 | `/Volumes/ORICO/doc/github/GenericAgent/agent_loop.py`（132 行） |
| 工具实现 + 纠偏注入 | `ga.py`（614 行，重点 `turn_end_callback` / `do_no_tool` / `_get_anchor_prompt`） |
| 任务循环 + SDK | `agentmain.py`（330 行） |
| 多模型/历史压缩 | `llmcore.py`（1196 行，重点 `compress_history_tags` / `MixinSession`） |
| 记忆管理公理 | `memory/memory_management_sop.md` |
| 文件式 cron | `reflect/scheduler.py`（131 行） |
| 时间预算自驱 | `reflect/goal_mode.py`（113 行） |
| 真实浏览器驱动 | `TMWebDriver.py`（288 行）+ `simphtml.py`（873 行） |
| 系统提示词 | `assets/sys_prompt.txt`（"完成发生在现实中"等行动原则值得通读） |
| 技术报告 | `assets/GenericAgent_Technical_Report.pdf` / arXiv:2604.17091 |
