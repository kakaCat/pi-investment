---
id: memory-and-recall
title: 记忆与召回
type: architecture
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [architecture, memory, autonomy]
---

# 记忆与召回

**这页回答**：结论写进哪、下次怎么被想起来、怎么知道检索有没有在工作。

## 结论先行

1. **写入口**：`memory_write`（结论，namespace: default / analysis / experience / decision）、`experience_write`（交易经验）、`decision_audit`（决策，供事后评估）。
2. **读入口**：`memory_search`（语义检索，选对 namespace）、`experience_stats`（历史胜率）、`decision_scores`（决策评分回流）。
3. **决策前必须检索（R-008）**：下单/分析前先查该标的与场景的历史教训，并在 reason 里写明检索结论（"已检索：无不良记录"也算）。
4. **召回质量要能被观测**：`memory_recall_audit` 看注入率与压制原因——注入率低且原因是 `empty-result`，说明**库里没有**而不是检索坏了。
5. **写清实体与关键词**：描述里带股票代码/需求号/模块名，否则未来的自己检索不到。

## 常见坑

- 结论只写在会话里 → 下一次会话等于没发生（会话启动只加载静态层：身份 + 基因组 + 工具清单）；
- 类目放错（分析结论写进 experience，交易经验写进 analysis）→ 检索命中率下降；
- 用策略线账户的评分当自己的业绩先验（要按账户过滤并写明覆盖样本数）。

## 依据

- R-008 / R-008 扩展（分析前读回流产出：业绩归因 + decision_scores）；
- 实测：会话启动的记忆召回注入率偏低（7%），且早期"零命中"实为库中无内容（用 recall audit 区分）。

## 相关页面

- [留痕与文档规范](../standards/audit-and-docs.md) · [自主能力总览](AUTONOMY-SYSTEM.md)
- [RFC-003 学习蒸馏](../rfcs/003-self-learning-distillation.md) · [RFC-008 验证门](../rfcs/008-validation-gate.md)
