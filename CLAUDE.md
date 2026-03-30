# pi-investment 项目配置

## 项目简介
AI 股票投资顾问，基于 piagent 架构，使用 DeepSeek + GPT-5.4 双模型协作。

---

## 🤖 Codex 子 Agent 使用规则

Claude Code 直接通过 `codex exec` CLI 调用 Codex，无需 MCP 或 bridge。

### 调用方式

```bash
# 任意任务（同步，结果写入文件后读取）
codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral \
  -C /Users/mac/Documents/ai/pi-investment \
  -o /tmp/codex-out.txt \
  "你的 prompt"
cat /tmp/codex-out.txt

# code review（基于 git 未提交变更）
codex exec review --uncommitted --ephemeral \
  -C /Users/mac/Documents/ai/pi-investment \
  -o /tmp/codex-review.txt \
  "重点关注边界条件和异常处理"
cat /tmp/codex-review.txt
```

### 用户显式要求委托时

当用户说 `'Delegate this task to Codex agent. Do not implement yourself - coordinate the agent, wait for completion, then show me the results.'` 时：

- 不要自己实现
- 使用 `codex exec` 命令委托给 Codex
- 等待 Codex 完成
- 向用户展示结果

### 什么时候必须调用 Codex

**以下场景，在完成主要工作后，自动用 Bash 工具执行 codex exec，无需用户提示：**

1. **写完或修改了业务逻辑代码**（`.ts`、`.py` 文件）→ `codex exec review --uncommitted`
2. **修复 bug 后** → `codex exec "确认修复是否完整，有无引入新问题"`
3. **实现复杂算法**（技术指标、投资分析、持仓计算）→ `codex exec "验证逻辑正确性"`
4. **重构代码后** → `codex exec review --uncommitted`

### 什么时候不需要调用 Codex

- 只读文件、搜索代码、回答问题
- 修改配置文件（`.json`、`.toml`、`.env`）
- 写文档、注释、简单改动（< 5 行）

### 结果处理

- Codex 结果作为参考，**我自己判断是否需要跟进修改**
- 发现重要 bug → 立即修复
- 发现优化建议 → 告知用户，由用户决定

---

## 项目技术栈

- **语言**: TypeScript (Node.js 22+)
- **主模型**: DeepSeek Chat（agent loop）
- **子模型**: GPT-5.4 via Codex（code review）
- **市场数据**: AkShare-TS（新浪/东财/stooq）
- **持仓管理**: `.pi-invest/portfolio.json`
- **复盘报告**: `.pi-invest/reviews/`

## 关键文件

- `src/index.ts` — 主入口
- `src/tools/invest-tools.ts` — 工具路由
- `src/infrastructure/akshare-ts/index.ts` — TS 原生数据层
