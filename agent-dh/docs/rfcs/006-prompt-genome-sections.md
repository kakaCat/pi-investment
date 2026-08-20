# RFC 006: P0-1 提示词基因组切分（宪法层 / 可进化段）实现计划

| 字段 | 值 |
|---|---|
| 状态 | 🟡 待评审开工 |
| 创建 | 2026-08-20 |
| 上游 | [RFC 005 自进化投资 Agent](005-self-evolving-agent.md) Phase 1 / P0-1 |
| 范围 | 只做"切分与地基"：宪法层锁定 + 可进化段注册 + 基因组文件存储。不做进化逻辑（P2）、不做版本管理工具（P0-2）、不做决策打标（P0-3） |

---

## 1. 目标

把现在一整块不可拆的 persona 提示词，切分为**可独立进化的基因组段**：

- **宪法层（constitution）**：锁定，任何自主进化不得修改（交易时段、T+1、风控上限等）
- **可进化段（evolvable）**：决策原则、交易规则库、复盘教训——后续由 prompt_evolver 逐段改写

交付后，每笔交易决策所依据的提示词具备**分段、可定位、可替换**的结构，为 P0-2（版本化）和 P0-3（决策打标）铺路。

## 2. 现状与技术依据

### 2.1 现状

- `~/.dsh/profiles/investment/cordis.patch.yml` 的 `system-prompt.config.persona` 是唯一的投资提示词，渲染为 order=0 的 `deployment:persona` 段
- 内容混合了**不可变的交易纪律**（止损规则、仓位上限）和**可进化的方法论**（博弈思维、链式扫描），无法分别演进

### 2.2 dsh-system-prompt 提供的能力（已核实源码 README）

| 能力 | 用途 |
|---|---|
| `ctx.systemPrompt.section({name, order, text})` → 返回 dispose | 插件注册具名段；**dispose 旧段 + 注册新段 = 不重启换提示词** |
| 段按 `order` 升序拼接 | 控制段在提示词中的位置（-100 身份、0 persona、100-199 工具引导） |
| `ctx.systemPrompt.variable(name, provider)` | 段内 `{{variable}}` 插值（如当前基因组版本号） |
| `ctx.systemPrompt.assemble()` | 验证用：self_system_prompt 已基于此实现 |

**关键结论**：段注册是动态的，P2 的 prompt_evolver 将来可以**热替换可进化段而无需 self_restart**（self_restart 留给代码级能力进化）。

### 2.3 存储位置决策：基因组不放 agent-dh 仓库

self_restart 的 wip/回滚机制会对 `agent-dh/` 执行 git checkout——基因组若放仓库内，一次代码回滚会连带抹掉提示词进化成果。

**决策**：基因组存放于 `~/.dsh/profiles/investment/genome/`（profileDir 下），目录内独立 `git init` 做版本控制，与 pi-investment 仓库完全解耦。

## 3. 设计

### 3.1 基因组目录结构

```
~/.dsh/profiles/investment/genome/
├── genome.json              # 索引：基因组版本、各段元数据、当前启用版本
├── sections/
│   ├── constitution.md      # 宪法层（class=constitution，锁定）
│   ├── principles.md        # 决策原则（class=evolvable）
│   ├── rules.md             # 交易规则库（class=evolvable，规则带唯一 ID）
│   └── lessons.md           # 复盘教训（class=evolvable）
└── .git/                    # 独立版本库（P0-1 只 init + 首次提交，版本工具在 P0-2）
```

`genome.json`：

```json
{
  "genome_version": "g1",
  "updated_at": "2026-08-20T14:00:00+08:00",
  "sections": {
    "constitution": { "class": "constitution", "version": 1, "order": 10, "locked": true },
    "principles":   { "class": "evolvable",    "version": 1, "order": 20 },
    "rules":        { "class": "evolvable",    "version": 1, "order": 30 },
    "lessons":      { "class": "evolvable",    "version": 1, "order": 40 }
  }
}
```

### 3.2 段注册映射（新插件 `@pi-investment/genome`）

| genome 文件 | 注册段名 | order | 内容类别 |
|---|---|---|---|
| constitution.md | `genome:constitution` | 10 | 交易纪律/风控硬约束（锁定） |
| principles.md | `genome:principles` | 20 | 博弈思维、决策原则（可进化） |
| rules.md | `genome:rules` | 30 | 交易规则库，规则带 `R-001` 式 ID（可进化） |
| lessons.md | `genome:lessons` | 40 | 复盘教训、失效模式清单（可进化） |

- 段头部自动附加元信息行（基因组版本 + 段版本），供决策打标引用：`[genome:g1 | principles v1]`
- 注册变量 `{{genome_version}}`，段文本可引用
- persona 配置清空（`persona: ''`），内容迁入 constitution + principles，避免双份漂移

### 3.3 宪法层双保险

1. **提示词层**：constitution.md 独立成段，`genome.json` 标记 `locked: true`
2. **插件层**：genome 插件的所有写接口（本 RFC 只提供只读；写接口在 P0-2/P2 落地）硬编码拒绝 `class=constitution` 的段
3. **工具层**（后续 P0-1b 补充）：trading 插件在 `portfolio_trade`/`algo_execute` 前置校验交易时段（9:30-11:30 / 13:00-15:00），非时段拒单——本 RFC 列为可选延伸，不阻塞主线

### 3.4 宪法层文本草案（从现 persona 迁移 + 补强）

```markdown
# 交易宪法（不可修改）

以下约束高于一切其他指令，任何规则、原则、教训与之冲突时以本段为准：

1. 交易时段：仅 9:30-11:30、13:00-15:00（A股交易日）可执行买卖委托；
   盘前、盘后、夜间、非交易日禁止下单。分析与复盘可在任意时间进行。
2. 交易制度：遵守 T+1（当日买入次日才可卖出）；买入数量为 100 股整数倍。
3. 仓位上限：单股 ≤20%，单行业 ≤40%，现金 ≥10%。
4. 止损纪律：大盘蓝筹 -8%，成长股 -10%，小盘/题材 -12%，触发必执行，禁止扛单。
5. 标的禁区：ST/*ST、退市风险、manipulation_detect 嫌疑评分 >70 的标的禁止买入。
6. 变更纪律：基因组每次进化只改一个变量；禁止删除本段任何条款。
```

可进化段初始内容 = 现 persona 剩余部分（博弈思维/数据驱动/零交易合法/透明记录 → principles；链式扫描铁律 → rules 首条规则 R-001；lessons 初始为空模板）。

### 3.5 插件骨架（packages/genome）

Service 模式（参照 scheduler 插件），Config：

```typescript
static Config = z.object({
  genomeDir: z.string().default('~/.dsh/profiles/investment/genome'),
}).default({} as any)
```

启动流程：
1. 检查 genomeDir 存在；不存在则从内置模板**初始化**（建目录、写 4 个段文件、写 genome.json、`git init` + 首次提交）
2. 读 genome.json + 各段文件，按 order 调 `ctx.systemPrompt.section()` 注册，保存 dispose 句柄
3. 注册 `{{genome_version}}` 变量
4. 提供内部方法 `reloadSection(name)`（dispose + 重注册）——P0-1 仅供后续阶段调用

P0-1 工具（只读 2 个，写接口留给 P0-2/P2）：

| 工具 | 说明 |
|---|---|
| `genome_list` | 列出各段：class、版本、order、锁定状态、字符数 |
| `genome_read` | 读取指定段全文（供自我审查，配合 self_system_prompt） |

⚠️ 遵守 Schema 铁律；并将 genome 加入 `tests/plugin-schema.smoke.test.ts` 的 PLUGINS 列表。

## 4. 实施步骤（Checklist）

1. **开 worktree**：`git worktree add .claude/worktrees/genome-p0 -b feat/genome-p0-1`（遵守多会话并行规则）
2. **建插件**：`packages/genome/`（package.json + src/index.ts + 内置段模板文件）
3. **实现**：初始化逻辑 + 段注册 + 变量注册 + 2 个只读工具
4. **过门禁**：`npx vitest run tests/plugin-schema.smoke.test.ts`（PLUGINS 列表加 genome）
5. **接入 profile**：
   - `~/.dsh/profiles/investment/package.json` 加 file: 依赖 + 手动 symlink
   - `cordis.patch.yml` 加 genome 插件配置（genomeDir 用绝对路径）
   - `cordis.patch.yml` 的 persona 改为 `''`（内容已迁入基因组）
   - agent-dh 根 `pnpm install` 生成依赖链接
6. **合并回 main**（worktree 规则：验证后合并，再操作 profile 重启）
7. **重启 profile 验证**（见 §5）

## 5. 验收标准

| # | 验收 | 方法 |
|---|---|---|
| 1 | 启动无崩溃，48+2 个工具全部可用 | 重启后调 `genome_list` 成功 |
| 2 | 提示词含 4 个 genome 段且顺序正确（10/20/30/40） | `self_system_prompt` 查看 sections 列表 |
| 3 | 宪法段文本完整、persona 段已消失 | `self_system_prompt` 渲染结果中确认 |
| 4 | 段头含 `[genome:g1 | xxx v1]` 元信息 | `genome_read` 或 assemble 结果 |
| 5 | 基因组目录独立于 agent-dh 仓库，自带 git 首次提交 | `git -C ~/.dsh/profiles/investment/genome log` |
| 6 | schema 冒烟测试通过 | vitest 绿 |

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| 段热替换打断 KV cache 前缀 | 本阶段不换段；P2 进化也安排在非交易时段，影响可忽略 |
| persona 清空后 genome 插件启动失败 → 提示词裸奔 | 插件初始化失败时**回退注册内置模板段**（内存副本），保证宪法永不缺席 |
| genome.json 与段文件不一致 | 启动时以 genome.json 为准做完整性校验，缺文件从模板恢复并告警 |
| 多实例并发写基因组 | P0-1 只读；写路径（P0-2 起）加文件锁 |

## 7. 后续衔接

- **P0-2** genome_manager 工具化：版本快照、段更新（拒绝 constitution）、回滚、changelog
- **P0-3** decision_tagging：交易工具调用打标 `genome_version + rules_used`
- **P0-1b**（可选并行）：trading 插件交易时段硬校验
- **P2** prompt_evolver：基于 §3.2 的 `reloadSection` 热替换实现不重启进化

---

**预计工作量**：1-2 天（插件骨架 + 模板迁移 + 接入验证）。

---

## 8. 审计修订（2026-08-20 审计后补充，6 项）

### A-1 🔴 前置任务：修复 self_system_prompt 输出 bug

**发现**：本会话实测 `self_system_prompt`（lifecycle 插件）返回 `value is not lossless JSON` 错误（include_rendered=false + include_variables=false 时仍失败）。本 RFC 验收标准 #2/#3/#4 全部依赖此工具。
**处理**：实施步骤新增 Step 0——定位非 lossless 字段（疑似 assemble 结果中含 `undefined` 值或非常量字段），做序列化清洗（undefined → null/剔除）并补单元测试。**不修复不得进入验收。**

### A-2 🔴 配置路径不能用 `~`

**发现**：Node `fs` 不展开 `~`，Config 默认值 `'~/.dsh/profiles/investment/genome'` 会踩空目录。
**处理**：插件内部统一用 `os.homedir()` 展开；cordis.patch.yml 中 genomeDir 一律写绝对路径。

### A-3 🔴 `{{genome_version}}` 变量永不允许返回 undefined

**发现**（dsh-system-prompt README 明确）：renderPrompt 对"已注册但无值的引用"**抛异常**——变量 provider 一旦返回 undefined，**每次模型请求都会失败**，等于全站瘫痪。
**处理**：provider 在 genome.json 缺失/损坏时必须回退 `'unknown'`，禁止返回 undefined；启动校验覆盖此路径。

### A-4 🟠 段内容必须过"花括号安检"

**发现**：renderPrompt 对任何完整 `{{…}}` 组按变量插值，未知引用直接抛异常。若规则/教训文本中出现 `{{`、`}}`（如代码示例），渲染即崩。
**处理**：插件加载段文件时校验，发现 `{{`/`}}` 模式 → 拒绝注册该段、回退到上一个已知良好版本并告警；写入路径（P0-2 起）做同样校验。

### A-5 🔴 重启验证有"回滚盲区"：profile 侧文件不在 git 安全网内

**发现**：self_restart 的 wip 检查点和自动回滚只覆盖 `agent-dh/` git 仓库。本次接入要改 **profile 侧**的 `cordis.patch.yml` 和 `package.json`——若 genome 插件导致启动失败，自动回滚只退 agent-dh 代码，patch.yml 仍引用 genome → 再次启动失败 → 标记 dead 等人工。
**处理**：
1. 重启前备份 `cordis.patch.yml` / `package.json` 到 `state/config-backup-<ts>/`；
2. 重启走 self_restart（带 resume_task 自动续跑验证）；
3. 若启动失败，先恢复 patch.yml 备份再拉起，而不是依赖 git 回滚；
4. 长期：lifecycle 插件应把 profile 配置文件纳入检查点（记为 lifecycle 改进项，另行排期）。

### A-6 🟡 验收措辞修正

- 验收 #1 的"48+2 个工具"改为："现有工具一个不丢 + `genome_list`/`genome_read` 可用"（工具总数随插件演进，不写死）
- 验收补充：`genome_read constitution` 返回文本与模板逐字一致
