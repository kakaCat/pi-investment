# RFC 008: P2 验证门（Validation Gate）——回测 + 模拟盘 A/B + 自动裁决

| 字段 | 值 |
|---|---|
| 状态 | 🟡 设计待评审 |
| 创建 | 2026-08-20 |
| 上游 | [RFC 005 §4.6](005-self-evolving-agent.md)（验证门原则）、[RFC 007](007-genome-manager.md)（genome_update 唯一写入口）、P0-3（打标）、P1（盘后调度已上线） |
| 定位 | 自动进化的**安全闸**：任何基因组新版本（提示词/规则/参数）必须过门才能正式启用 |

---

## 1. 为什么需要验证门

P1 的蒸馏闭环已能产出改进提案（prompt_evolver），但"提案直接生效"等于拿组合给未验证的想法陪葬。验证门是**自然选择的选择压力模拟器**：

```
蒸馏提案（变异体） → [验证门] → 通过：正式版基因组 → 实盘/模拟盘使用
                              → 失败：记录"此路不通" → 喂回经验库（失败也是知识）
```

没有验证门，进化就是随机漂移；有了它，进化才是定向选择。

## 2. 两级门设计

### 2.1 第一级：回测门（快速、便宜、必要条件）

对**规则/参数类**变更（rules 段、策略参数）：

| 项 | 内容 |
|---|---|
| 方法 | `strategy_execute(mode=backtest)` 在三个市场区间回测：牛市段 / 熊市段 / 震荡段 |
| 通过条件 | 样本外夏普 > 1；最大回撤不劣于当前版本；三区间无一时段崩溃（收益 < -15%） |
| 不适用场景 | 提示词语义类变更（principles/lessons）无法直接回测 → 跳过本门，直接进第二级但延长观察期 |

### 2.2 第二级：模拟盘 A/B 门（真实决策环境）

| 项 | 内容 |
|---|---|
| 机制 | 新版本基因组在 agent_virtual 模拟盘启用，与基准版本对比 |
| 观察期 | 默认 5 个交易日（提示词类变更 10 个交易日，样本更敏感） |
| 对比维度 | ①交易胜率 ②盈亏比 ③组合回撤 ④决策质量（每笔交易的 reason 是否引用了合理规则，R-005 合规率） |
| 裁决 | 任一维度显著恶化（如胜率下降 >10pp 或回撤 > 基准 1.5 倍）→ 自动 genome_rollback + 记录失败原因；全部不劣于基准 → 标记正式版 |

**A/B 的技术实现约束**：同一进程同一时刻只有一个基因组生效。A/B 不是并行双跑，而是**时间切片**——观察期内用新版，与上一版本的历史同期指标对比（ genomic_version 打标让按版本分组统计成为可能）。并行双账户 A/B 列为后续增强（需要第二个虚拟账户）。

### 2.3 提示词类变更的特殊处理

提示词改写的效果无法回测（它不直接产生交易信号），只能看模拟盘决策质量。因此：

- prompt_evolver 生成的段更新 → `genome_update` 应用 → **标记为"观察版"**（history 记 `stage: candidate`）
- 观察期内盘后调度（schedule-1 例程）自动对比 candidate vs 上一正式版的打标经验表现
- 裁决：达标 → history 标 `stage: active`；不达标 → `genome_rollback` + 失败原因入经验库

## 3. 组件设计（新工具，evolver 插件扩展）

### 3.1 `validation_gate`（核心工具）

| 参数 | 说明 |
|---|---|
| `target` | 待验证对象：`{ type: 'genome_candidate', section, version }` 或 `{ type: 'rule', rule_id }` |
| `level` | `backtest` / `paper_ab` / `both`（默认 both） |
| `observe_days` | 模拟盘观察期（默认 5） |

执行流：
1. 识别变更类型（规则/参数 → 回测适用；提示词 → 跳过回测）
2. 回测门：三区间回测，输出通过/失败 + 指标矩阵
3. 通过后进入模拟盘观察：history 标 candidate，创建观察期检查点（到期由盘后例程裁决）
4. 裁决日：对比 candidate 期 vs 基线期的打标经验（reward/胜率/R-005 合规率）
5. 输出裁决结果；通过则 promote，失败则 genome_rollback

### 3.2 `candidate_status`（查询候选状态）

列出当前观察中的基因组候选：版本、剩余观察天数、当前对比指标。

### 3.3 genome.json 扩展

history 条目增加 `stage` 字段：`candidate | active | rejected`，以及 `baseline_version`（对比基准）。`promote` 时生成新的 history 条目（type=promote）。

## 4. 与现有组件的接线

```
experience_distill（每日） → 提案
    ↓
prompt_evolver（dry_run=false 前必须先过门！）
    ↓ 修改：evolver 不再直接调 genome_update 生效，
    ↓ 而是调 genome_update 标 candidate + 创建 validation_gate 观察
    ↓
盘后例程（schedule-1）每日检查 candidate_status
    ↓ 观察期结束
裁决：promote（标 active）或 genome_rollback（标 rejected + 失败入经验库）
```

**关键改动**：prompt_evolver 的 `auto_apply`/`daily_distill` 的 auto_apply 路径必须改为"应用为 candidate + 创建观察"，而非直接转正。当前 daily_distill 默认 auto_apply=false，安全；本 RFC 实施后 auto_apply=true 也只会进入观察态，不会直接转正。

## 5. 失败知识的闭环

验证门拒绝的每个提案都是高价值经验：

- `experience_write`：scenario="提案 X 未过验证门"，outcome=loss，lesson=失败原因（如"该规则在震荡市回撤超限"）
- 蒸馏时这些"此路不通"记录会**降低同类提案的生成概率**——进化记忆不只记成功经验

## 6. 实施步骤与验收

| 步骤 | 内容 | 验收 |
|---|---|---|
| 1 | genome.json history 增加 stage 字段 + promote 流程 | genome_update 支持 stage 参数，默认 candidate |
| 2 | `validation_gate` 工具（回测门） | 对一个已知规则跑三区间回测出指标矩阵 |
| 3 | 模拟盘观察期机制 + `candidate_status` | 创建一个 candidate，candidate_status 可查 |
| 4 | 盘后例程裁决逻辑接入 schedule-1 提示词 | 更新 schedule 提醒文案包含裁决步骤 |
| 5 | prompt_evolver 改为 candidate 模式 | dry_run=false 应用后是 candidate 而非正式版 |
| 6 | E2E：完整走一轮"提案→观察→裁决" | 一个 candidate 被 promote 或 rejected，全程留痕 |

## 7. 风险

| 风险 | 对策 |
|---|---|
| 5 天观察期样本太少，裁决噪音大 | 提示词类延长到 10 天；连续证据不足时延期而非强行裁决 |
| 时间切片 A/B 受市场行情差异污染 | 裁决指标用相对基准的差值而非绝对值；行情 regime 纳入对比上下文 |
| candidate 期策略恶化造成实际亏损 | 模拟盘无真金白银；candidate 期仓位上限收紧（宪法层仓位上限 × 50%） |
| 验证门本身 bug 导致误转正 | 裁决默认保守：证据不足 = 不 promote；promote 需明确达标 |

---

## 8. 评审记录

### 2026-08-20 评审（agent-dh k3）— ✅ 通过，附 4 条修改意见

两级门设计合理，candidate/promote/rollback 与基因组系统接线清晰，风险表覆盖到位（保守默认值好评）。以下意见建议实施前纳入：

1. **上游引用断裂（须修）**：`005-self-evolving-agent.md` 和 `007-genome-manager.md` 在本目录不存在（agent-dh/docs/rfcs 仅有 003/004/008），且与仓库 docs/rfcs/ 的 005（盈利引擎工单包）编号撞车。两套 RFC 编号体系并存必然混乱——建议统一编号（仓库 docs/rfcs 为唯一序列），或本系列加前缀（如 ADH-005）。
2. **回测门的"规则→回测"映射未定义**：rules 段变更（如止损线 -8%→-10%）如何变成 strategy_execute 的回测参数？需要一层映射机制或明确"仅策略参数类变更走回测门，纯文本规则直接进模拟盘门"。
3. **裁决最小样本数缺失**：宪法允许零交易，5 天观察期 candidate 可能 0 笔决策。建议写明：candidate 期决策数 <3 笔时自动延期而非裁决（风险表已提"证据不足延期"，此处落成具体数字）。
4. **candidate 期仓位×50% 的执行机制未定义**：宪法在系统提示词层，临时收紧需要 genome constitution 支持参数化或由 risk_controller 读取 candidate 标志——实施步骤中应明确走哪条路。

另：本 RFC 回测门应直接引用 docs/rfcs/006 的 V1 回测有效性规范（最小窗口/最小样本/成本模型），保证全系统只有一把尺子。

**下一步**：评审通过后按 §6 实施（预计 3-4 天）。实施后 daily_distill 的 auto_apply 才能安全打开，自动进化闭环正式完整。
