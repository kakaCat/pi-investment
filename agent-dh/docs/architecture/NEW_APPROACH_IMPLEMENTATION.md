# 新方案实施完成：Agent自主进化能力

**实施日期**: 2026-08-28 19:20  
**提交**: evolver插件3工具注册（candidate_status, validation_gate, llm_rewrite_section）  
**测试**: schema冒烟测试通过

---

## 新方案架构（已实现）

### 核心理念
Agent是**自主决策者**，不被固定流程工具限制。看到改进建议后，agent自己决定：
- 是否采纳？
- 改哪个段落？
- 何时改？
- 用什么方式改？

### 能力组合（全部就位）

```
┌─────────────────────────────────────────────────────┐
│  1. learning_distill                                 │
│     生成改进建议 → 呈现给agent                        │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  2. llm_rewrite_section (新)                        │
│     agent调用，LLM改写段落融入建议                    │
│     失败时自动回退追加模式                            │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  3. genome_update                                   │
│     应用改写后的段落，stage=candidate进入观察期        │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  4. candidate_status (新)                           │
│     agent查询当前观察中的候选                         │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  5. validation_gate (新)                            │
│     裁决到期候选：对比打标经验 → promote/rollback     │
│     agent可手动触发或由盘后例程自动触发               │
└─────────────────────────────────────────────────────┘
```

---

## 实施细节

### 新增工具（packages/evolver/src/index.ts line 386-476）

#### 1. candidate_status
**签名**:
```typescript
candidate_status() → {
  watching: CandidateRecord[];  // 观察中
  settled: CandidateRecord[];   // 已裁决
  total: number;
}
```

**用途**: agent查询"我有哪些改动在观察期"

#### 2. validation_gate
**签名**:
```typescript
validation_gate(
  action?: 'judge',
  force?: boolean,        // 跳过时间/样本门槛
  min_samples?: number    // 最小样本数（默认3）
) → { verdicts: Verdict[] }
```

**用途**: 裁决到期候选，agent可手动触发或由daily_distill自动调用

**裁决逻辑**（evolver/src line 271-384）:
- 观察期未到 → verdict: watching
- 样本不足（<min_samples）→ extended（延期2天）
- cand_avg显著低于base_avg（差值>0.1）→ rollback + rejected
- 否则 → promote + promoted

#### 3. llm_rewrite_section
**签名**:
```typescript
llm_rewrite_section(
  section: string,               // principles/rules/lessons
  suggestion_reason?: string,
  suggestion_content?: string
) → {
  rewritten: string;
  method: 'llm' | 'append_fallback';
}
```

**用途**: LLM改写段落，失败时追加回退

**LLM prompt**（evolver/src line 126-230）:
- 整体改写，融入建议
- 硬性约束：≤6000字符、禁止{{}}、rules段规则ID只增不删、不与宪法冲突
- 失败时回退追加模式（保证可用性）

---

## 与旧方案对比

| 维度 | 旧方案（prompt_evolver工具） | 新方案（agent自主） |
|------|------------------------------|---------------------|
| **触发** | 固定周末运行 | agent根据建议自主决定 |
| **流程** | 批量改写多段→一次commit | 单段原子操作→多次commit |
| **可归因** | 一个大reason | 每条规则精确commit时间 |
| **灵活性** | 固定流程 | agent可选择性采纳/延迟/分步 |
| **可观测** | 黑盒 | 每次genome_update透明 |
| **工具数** | 1个大工具（556行） | 3个小工具（90行）+ genome/learning已有能力 |

---

## 使用示例（agent视角）

### 场景1：看到蒸馏建议后主动改进
```
1. agent调用 learning_distill → 得到建议"R-008规则负奖励，建议强化前置检索"
2. agent决定采纳，调用 llm_rewrite_section:
   - section: 'rules'
   - suggestion_reason: 'R-008规则负奖励'
   - suggestion_content: '强化前置检索，加上"不检索不下单"约束'
3. 得到改写后的rules段全文
4. agent调用 genome_update:
   - section: 'rules'
   - content: (改写后的全文)
   - stage: 'candidate'
   - reason: '强化R-008前置检索（蒸馏建议）'
5. 进入观察期5天
```

### 场景2：主动查询观察期状态
```
agent: 我上周改了rules段，现在观察期怎么样了？
→ 调用 candidate_status
→ 看到 watching: [{ section: 'rules', observe_until: '2026-09-02', genome_version: 'g16' }]
agent: 还有4天到期
```

### 场景3：手动触发裁决
```
agent: 我想立即验证上周的改动，不等5天了
→ 调用 validation_gate(force: true)
→ 得到 { verdicts: [{ verdict: 'promoted', reason: 'cand_avg 0.15 vs base 0.08' }] }
agent: 改动已转正，g16成为正式版
```

---

## 配套系统提示词更新（TODO）

需要在principles或rules段加入**"如何进化自己"指导**：

```markdown
## 自我进化流程

当你发现决策模式可以改进时（如某条规则持续低奖励、或出现新的成功经验）：

1. **获取改进建议**：调用 learning_distill 分析经验库
2. **改写段落**：调用 llm_rewrite_section 融入建议（LLM会帮你整体重写）
3. **应用候选版本**：调用 genome_update(stage='candidate') 进入观察期
4. **查询状态**：调用 candidate_status 查看观察期进度
5. **裁决验证**：5天后自动裁决，或调用 validation_gate(force=true) 立即裁决

**原则**：
- 每次只改一个段落（可归因）
- 改动理由明确写在 genome_update 的 reason 里
- 观察期至少3个样本才能裁决（保证统计可靠）
- 改动失败会自动回滚，保留wip分支供复盘
```

---

## 测试状态

| 测试项 | 状态 | 证据 |
|--------|------|------|
| Schema合规 | ✅ | npx vitest run tests/plugin-schema.smoke.test.ts -t "evolver" PASSED |
| candidate_status工具 | ✅ | 代码注册，依赖readCandidates（已实现） |
| validation_gate工具 | ✅ | 代码注册，依赖judgeCandidates（294行实现，g10已真实裁决通过） |
| llm_rewrite_section工具 | ✅ | 代码注册，依赖llmRewriteSection（230行实现，f9dcc3b3实证过） |
| 端到端集成 | ⏳ | 等待重启DSH profile，agent首次调用验证 |

---

## 实施清单

- [x] 注册candidate_status工具（查询观察期）
- [x] 注册validation_gate工具（裁决候选）
- [x] 注册llm_rewrite_section工具（LLM改写）
- [x] Schema冒烟测试通过
- [x] 创建架构演进文档（ARCHITECTURE_EVOLUTION_prompt_evolver.md）
- [x] 创建实施总结文档（本文档）
- [ ] 系统提示词加入"如何进化自己"指导（待补）
- [ ] 重启DSH profile，agent首次调用验证
- [ ] 观察一周agent自主进化行为
- [ ] 根据实践反馈调整工具参数/提示词指导

---

## 相关文档

- **架构演进**: docs/architecture/ARCHITECTURE_EVOLUTION_prompt_evolver.md
- **代码审计**: CODE_AUDIT_2026-08-28.md
- **RFC 005**: docs/rfcs/005-self-evolving-agent.md（原始设计）
- **RFC 008**: docs/rfcs/008-validation-gate.md（验证门）
- **旧实现**: git show f9dcc3b3:packages/evolver/src/tools/PromptEvolverTool.ts

---

## 下一步

1. **立即**: 重启DSH profile，让3个新工具生效
2. **本周**: 观察agent是否会主动调用learning_distill和llm_rewrite_section
3. **下周**: 如果agent不主动进化，补充系统提示词指导
4. **长期**: 积累进化案例，评估新方案 vs 旧方案的实际效果

---

**实施人**: PI投资顾问·投资脑 (w-a8a89c6a)  
**代码位置**: packages/evolver/src/index.ts line 386-476  
**测试**: ✅ tests/plugin-schema.smoke.test.ts PASSED
