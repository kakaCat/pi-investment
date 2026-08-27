# 交易执行协议（Trade Execution Protocol）

**版本**: v1.0  
**生效日期**: 2026-08-26  
**适用范围**: 所有 agent 实例、基建线、手动干预

---

## 协议目标

确保**所有交易**都被正确打标（genome_version + rules_used）并进入经验库，支持：
1. 规则级归因（哪条规则在赚钱/亏钱）
2. 验证门裁决（基于真实交易表现）
3. 经验蒸馏与进化

---

## 强制约束

### 1. 统一入口原则

**所有下单必须通过 agent-dh 的工具接口**，禁止直接调用 quantsys-v2 后端：

✅ **正确**：通过 portfolio_trade 工具，reason 参数带规则 ID
❌ **错误**：直接 POST http://localhost:5001/api/trade/execute（绕过打标）

### 2. reason 参数规范

**reason 必填**，格式：`R-XXX 规则名 + 一句话理由`

示例：
- R-001 买入前确认 + R-006 仓位映射：regime=panic 上限100%，当前13.1%可加仓
- R-002 卖出前确认 + R-007 回撤熔断：触发止损线-8%

### 3. 紧急干预例外

熔断减仓、风控平仓等紧急情况允许后端直接执行，但**事后必须补记** experience_write。

---

## 技术保障

### agent-dh 层（已实现 ✅）

- portfolio_trade 工具自动捕获 genome_version
- learning 插件 auto-track 自动提取 rules_used（从 reason 文本）
- 所有工具调用经过 post-execute hook → 打标 → OS memory

### quantsys-v2 层（待基建线实现）

在 v2 的 /api/trade/execute 增加：
1. 接收 genome_version 和 reason 参数（可选）
2. 执行成功后自动调用 Agent OS /api/v1/memory 写入经验
3. 绕过 agent-dh 的直接调用也能被打标

---

## 验收标准

每笔交易在 OS memory 中必须有对应记录，包含：
- kind: 'experience'
- genome_context.genome_version（如 'g14'）
- genome_context.rules_used（如 ['R-001', 'R-006']）
- reward（真实盈亏）

验证：curl "http://localhost:8080/api/v1/memory/search?kind=experience&q=portfolio_trade"

---

## 违规处理

直接调用 v2 后端绕过打标的交易：
- 不进入经验库 → 不参与验证门裁决 → 不被进化系统学习
- 相当于"数据黑洞"，浪费真金白银换来的经验

**原则**：宁可拒单（工具调用失败有错误提示），不可静默绕过（数据丢失无人知晓）。
