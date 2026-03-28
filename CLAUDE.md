# pi-investment 项目配置

## 项目简介
AI 股票投资顾问，基于 piagent 架构，使用 DeepSeek + GPT-5.4 双模型协作。

---

## 🤖 Codex 子 Agent 使用规则

项目集成了 Claude Code（主 Agent）+ Codex（子 Agent）双向通信桥。
Codex 工具：`mcp__codex__task`、`mcp__codex__review`、`mcp__codex__status`

### 什么时候必须调用 Codex

**以下场景，在完成主要工作后，自动调用 Codex，无需用户提示：**

1. **写完或修改了业务逻辑代码**（`.ts`、`.py` 文件）
   - 调用 `mcp__codex__review`，让 Codex review 变更
   - focus：边界条件、潜在 bug、未处理的异常

2. **新增工具函数 / API 接口**
   - 调用 `mcp__codex__task`，让 Codex 分析接口设计是否合理
   - prompt 示例："review 这个新增函数的参数设计和返回值是否合理"

3. **修复 bug 后**
   - 调用 `mcp__codex__task`，让 Codex 确认修复是否完整，有无引入新问题

4. **重构代码后**
   - 调用 `mcp__codex__review`，让 Codex 检查重构后的代码质量

5. **实现复杂算法或数据处理逻辑**（技术指标、投资分析、持仓计算）
   - 调用 `mcp__codex__task`，让 Codex 验证逻辑正确性

### 什么时候不需要调用 Codex

- 只读文件、搜索代码、回答问题
- 修改配置文件（`.json`、`.toml`、`.env`）
- 写文档、注释
- 简单的变量重命名
- 已经明确是小改动（< 5 行）

### 调用方式

```
// 快速 review（推荐，大多数场景）
mcp__codex__review({ focus: "边界条件和异常处理" })

// 特定任务
mcp__codex__task({ prompt: "检查 XXX 函数的逻辑是否正确..." })
```

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
- `bridge/codex-bridge.ts` — Codex 通信桥
- `bridge/codex-mcp.ts` — MCP server（Claude Code 调用入口）
