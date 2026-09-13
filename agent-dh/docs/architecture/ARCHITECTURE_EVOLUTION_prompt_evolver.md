---
id: architecture-architecture-evolution-prompt-evolver
title: 架构演进记录：prompt_evolver → agent自主变更
type: architecture
status: frozen
updated: 2026-09-13
owners: [agent-dh]
tags: [architecture]
---

# 架构演进记录：prompt_evolver → agent自主变更

> **状态：frozen（2026-09-14 标注）**：本文记录 2026-08-28 的架构演进判断（专用 prompt_evolver → agent 自主变更段）。
> 现行的候选/转正门控见 [RFC 008 验证门](../rfcs/008-validation-gate.md) 与 [RFC 007 genome_manager](../rfcs/007-genome-manager.md)；自主能力总览见 [AUTONOMY-SYSTEM](AUTONOMY-SYSTEM.md)。


**日期**: 2026-08-28  
**演进原因**: P0-8 BaseTool重构 + 实践中发现更优架构  
**影响范围**: evolver插件工具层

---

## 原始设计（RFC 005, 2026-08-20）

### prompt_evolver工具
**定位**: 专门的提示词进化工具  
**触发**: 周末自动运行，或盘后daily_distill调用  
**流程**:
```
读取归因报告 + 蒸馏建议
    ↓
LLM改写提示词段落（整体重写，融入建议）
    ↓
生成基因组vN+1草稿（candidate）
    ↓
调用genome_update应用
    ↓
进入观察期（5天），等待validation_gate裁决
```

**实现历史**:
- **f9dcc3b3** (2026-08-20): 实施完成，LLM段落改写，失败回退追加
- **ee0048a2** (2026-08-20): P2验证门集成，prompt_evolver改为candidate模式
- **9481d0ff** (2026-08-21): 审计修复，dry_run显式兜底
- **6ec5cd74** (2026-08-30): P0-8 BaseTool重构时工具被注释（依赖core-tool无法解析）

**原始代码**: packages/evolver/src/tools/PromptEvolverTool.ts（已注释，556行）

---

## 新方案（2026-08-28确认）

### agent自主变更 + genome工具化

**核心理念**: agent是自主决策者，不应被固定流程的工具限制

**架构**:
```
learning_distill → 生成改进建议（呈现给agent）
         ↓
   agent自主决策：
   - 是否采纳建议？
   - 改哪个段落？
   - 何时改？
   - 用什么方式改（LLM重写 or 手工微调）？
         ↓
   调用genome_update（单次原子操作）
         ↓
   stage=candidate → 进入观察期
         ↓
   validation_gate裁决（自动或手动触发）
```

**优势**:
1. **更灵活**: agent可以选择只改部分建议、延迟改、分步改
2. **可观测**: 每次genome_update有独立reason（而非批量改写的一个大reason）
3. **可归因**: 每条规则的生效时间精确到genome_update commit
4. **符合自主能力理念**: agent操作工具，而非被工具流程驱动

**劣势**（需补偿）:
1. ❌ LLM改写逻辑不可见 → ✅ 需暴露或在系统提示词指导agent自己用LLM
2. ❌ 无固定触发时机 → ✅ 由daily_distill/周报提示agent何时应该进化

---

## 当前实现状态（2026-08-28）

### 已实现的能力
| 组件 | 状态 | 说明 |
|------|------|------|
| **genome_update** | ✅ | 6工具全实现，支持candidate模式 |
| **learning_distill** | ✅ | 生成改进建议（LearningDistillTool） |
| **candidate机制** | ✅ | evolver/src 294行代码，candidate_status/judgeCandidates方法 |
| **validation_gate** | ✅ | 代码实现，g10首次真实裁决通过（promoted） |
| **LLM改写逻辑** | ⚠️ | 存在（llmRewriteSection私有方法230行），但agent不可调 |
| **prompt_evolver工具** | ❌ | 注释掉（依赖core-tool） |

### 待补全项
1. **暴露LLM改写能力**（二选一）:
   - 方案A: 恢复prompt_evolver工具，解决core-tool依赖
   - 方案B: 新建llm_rewrite_section轻量工具，只做改写不管流程
   - 方案C: 在系统提示词里教agent"如何用LLM改写段落"（示例prompt）

2. **工具注册**（如选方案A/B）:
   ```typescript
   // packages/evolver/src/index.ts line 386-391
   private registerTools(): void {
     // TODO: 恢复prompt_evolver或注册llm_rewrite_section
     // 或确认采用"agent自主"模式（方案C），此处留空
   }
   ```

3. **candidate_status/validation_gate工具暴露**:
   - 代码存在（candidateStatus/judgeCandidates方法）
   - 需注册为工具，供agent手动触发裁决

---

## 决策记录

### 为什么不急于恢复prompt_evolver？
1. **实践验证**: g8/g10两次真实进化已通过（agent通过其他方式触发了genome_update）
2. **架构优势**: 当前"agent自主"模式更灵活，符合自主能力演进方向
3. **代码存在**: LLM改写逻辑保留在evolver插件，随时可暴露

### 何时需要恢复？
- 发现agent难以自主触发进化（提示词指导不够）
- 需要固定周期自动进化（如"每周日运行"）
- 需要批量改写多个段落的原子操作

### 当前建议（2026-08-28）
**先观察agent自主模式运行效果**，同时：
1. 在系统提示词（principles段）加入"如何进化自己"的指导
2. 注册candidate_status工具（供agent查询观察期状态）
3. 保留llmRewriteSection方法，供未来按需暴露

---

## 相关文档

- **RFC 005**: docs/rfcs/005-self-evolving-agent.md（原始设计）
- **RFC 008**: docs/rfcs/008-validation-gate.md（验证门设计）
- **代码审计**: CODE_AUDIT_2026-08-28.md（当前实现）
- **旧实现**: git show f9dcc3b3:packages/evolver/src/tools/PromptEvolverTool.ts

---

## 附录：prompt_evolver旧设计参数

```typescript
// 旧工具签名（f9dcc3b3）
interface PromptEvolverParams {
  suggestions: Array<{
    section: string;        // 目标段落
    reason: string;         // 改进理由
    content: string;        // 改进内容
    method?: 'llm' | 'append';
  }>;
  dry_run?: boolean;        // 预览模式
  auto_apply?: boolean;     // 自动应用（非dry_run时）
  observe_days?: number;    // 观察期（默认5天）
}

// 核心方法
private async llmRewriteSection(
  section: string,
  currentContent: string,
  suggestion: any
): Promise<{ rewritten: string; method: 'llm' | 'append_fallback' }>
```

该逻辑现在保留在 `packages/evolver/src/index.ts` line 126-230，可按需暴露为独立工具。

---

## 相关页面

- [自主能力总览](AUTONOMY-SYSTEM.md)
- [RFC 005 自进化 Agent](../rfcs/005-self-evolving-agent.md)
- [RFC 007 genome_manager](../rfcs/007-genome-manager.md)
- [RFC 008 验证门](../rfcs/008-validation-gate.md)
