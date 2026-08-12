---
name: declared-tools
description: Test skill declaring tools without backtick-call formatting
---

# Test Skill - Declared Tools Section

## 允许的工具
- portfolio_status()
- data_fetch_quote()（新闻：fields: ['news']）
- risk_controller()（command: 'stop_loss' / 'position_size'）

## 工作流程

1. 获取持仓 - 调用 portfolio_status({ action: 'get' })
2. 展示结果
