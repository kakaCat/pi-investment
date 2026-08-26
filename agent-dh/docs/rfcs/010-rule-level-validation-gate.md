# RFC 009: 规则级验证门（Rule-level Validation Gate）

| 字段 | 值 |
|---|---|
| 状态 | 🟢 工具框架上线，待数据积累与服务配置 |
| 创建 | 2026-08-25 |
| 实施 | 2026-08-26（并行窗口协作） |
| 上游 | [RFC 008 验证门](008-validation-gate.md)、[RFC 005 M3-3](005-self-evolving-agent.md) |

---

## 1. 要解决的问题

段级验证门（RFC 008）以整个段版本为裁决单位。**盲区**：一段里同时有好规则和坏规则时，观察期平均表现被中和——好规则被坏规则拖累、坏规则被好规则掩护。

**规则级验证门**把考核粒度下推到**单条 R-xxx**，让每条规则独立上/下。

## 2. 设计

### 2.1 裁决规则（RuleGate）

`rule_gate` 工具（evolver 插件，06e1b7f1）读经验库按 R-xxx 聚合成绩，产出三类动作：

| 条件 | 动作 | 落地方式 |
|---|---|---|
| 样本≥3 且 avg_reward < -0.1 | **deprecate 淘汰** | 从 rules 段移除 → candidate 观察 |
| 样本≥5 且 avg_reward > 0.3 且 success_rate > 0.7 | **strengthen 强化** | 规则精髓提炼 → principles candidate |
| 样本≥10 且 success_rate > 0.8 | **promote 固化** | 标记"已验证" |

**关键安全设计**：淘汰也走 candidate（可逆），观察期不劣于基线才转正。

### 2.2 数据流

```
R-005 reason打标 → experience库（rules_used[]）
↓
rule_scoreboard（learning）→ 写共享快照（scope='analytics:rule_scoreboard'）
↓
rule_gate（evolver）→ 读快照/内联计算 → 提案
↓
genome_update(candidate) → validation_gate观察期裁决
```

## 3. 实施状态

| 组件 | 状态 | 说明 |
|---|---|---|
| **rule_gate 工具** | ✅ 上线 | 06e1b7f1（osMemory内联计算） |
| **共享数据写入** | ✅ 完成 | learning rule_scoreboard 写 scope='analytics:rule_scoreboard' |
| **数据积累** | ⏳ 等待 | R-005 今日首次上线，需 1-2 周积累带规则ID的真实成交 |
| **Agent OS 配置** | ⚠️ 待配 | rule_gate 依赖 osMemory 服务（localhost:8080），当前未运行返回 fetch failed |

## 4. 实施协作说明

本 RFC 由**两个并行窗口协作**完成：
- **窗口 A**（本窗口）：方案设计 + learning 共享数据写入（kind='experience' 修正数据库约束）
- **窗口 B**（并行）：rule_gate 工具实现（06e1b7f1，osMemory 内联计算）

最终采用窗口 B 的实现（osMemory 避免跨插件调用复杂度）+ 窗口 A 的共享数据写入（备用数据源）。

## 5. 后续工作

1. **立即可做**：配置 Agent OS 服务或修改 rule_gate 改用 qv2 直接读 memory（绕过 Agent OS）
2. **等数据**：R-005 积累 1-2 周后，rule_scoreboard 才有非空成绩单
3. **盘后例程接入**（步骤 3）：每日盘后自动跑 rule_gate + 日报附提案

## 6. 与现有验证门的分工

| | 段级（RFC 008，运行中） | 规则级（本 RFC，待数据） |
|---|---|---|
| 对象 | 段版本（如 lessons v4） | 单条 R-xxx |
| 触发 | prompt_evolver 产出 | rule_gate 产出 |
| 用途 | 提示词语义改写 | 规则库增删/强化 |
| 状态 | g10 首个候选待裁决（明日盘后） | 工具上线，等数据 |

---

**决策**：RFC 009 工具框架已上线，数据积累中。当前优先级：①仓位硬校验（立即可做）、g10 裁决（明日盘后）、Phase 4 元学习（等数据）。
