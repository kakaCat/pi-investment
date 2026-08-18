# Agent-DH 示例

本目录包含 Agent-DH 的实用示例，帮助你快速上手。

## 📚 示例列表

### 1. 简单 Agent (`1-simple-agent.ts`)

**适合**: 初学者

**内容**:
- 创建 Agent Loop
- 注册 Agent 到 Agent OS
- 发送心跳
- 执行简单任务
- 优雅关闭

**运行**:
```bash
# 先构建
cd agent-dh
pnpm build

# 使用 tsx 运行（推荐）
npx tsx examples/1-simple-agent.ts

# 或编译后运行
tsc examples/1-simple-agent.ts --module esnext --target es2020 --moduleResolution node
node examples/1-simple-agent.js
```

### 2. 策略回测 (`2-backtest-strategy.ts`)

**适合**: 量化策略开发者

**内容**:
- 列出可用策略
- 执行策略回测
- 分析回测结果
- 策略评分和评级
- 参数优化建议

**运行**:
```bash
npx tsx examples/2-backtest-strategy.ts
```

**输出示例**:
```
=== 策略回测示例 ===

[1] 查询可用策略...
    找到 18 个内置策略

[2] 使用策略: 双均线策略

[3] 开始回测...
    股票: 600000.SH (浦发银行)
    时间: 2024-01-01 至 2024-12-31

[4] 回测结果:
    ┌─────────────────────────────────────┐
    │ 总收益率:    25.30%
    │ 年化收益率:  25.30%
    │ 夏普比率:    1.85
    │ 最大回撤:    -12.50%
    │ 胜率:        55.60%
    │ 交易次数:    23
    └─────────────────────────────────────┘

[5] 策略评估:
    综合评分: 78/100
    评级: B
    建议: 表现尚可，建议进行参数优化。
```

### 3. 股票池管理 (`3-pool-management.ts`)

**适合**: 投资组合管理

**内容**:
- 创建股票池
- 添加/移除成员
- 查询池成员
- 刷新股票池
- 池管理最佳实践

**运行**:
```bash
npx tsx examples/3-pool-management.ts
```

**输出示例**:
```
=== 股票池管理示例 ===

[1] 查询现有股票池...
    当前有 3 个股票池

[2] 创建新股票池...
    ✓ 股票池已创建
      ID: 15
      名称: 高 ROE 价值池

[3] 添加股票成员...
    ✓ 已添加: 贵州茅台 (600519.SH), ROE: 30.5%
    ✓ 已添加: 招商银行 (600036.SH), ROE: 16.8%
    ✓ 已添加: 五粮液 (000858.SZ), ROE: 22.3%
    ✓ 已添加: 中国平安 (601318.SH), ROE: 17.2%

[4] 查询池成员...
    股票池 "高 ROE 价值池" 当前有 4 个成员
```

### 4. 完整交易 Agent (`4-trading-agent.ts`)

**适合**: 生产环境

**内容**:
- Agent 注册和启动
- 获取市场数据
- 分析市场风格
- 执行策略回测
- 生成交易信号
- 监控和报告

**运行**:
```bash
npx tsx examples/4-trading-agent.ts
```

**特点**:
- 完整的交易流程
- 多标的分析
- 信号生成
- 状态报告
- 可定时运行

---

## 🔧 运行前准备

### 1. 安装依赖

```bash
cd agent-dh
pnpm install
pnpm build
```

### 2. 启动服务

**Agent OS** (Go):
```bash
cd ../agent-os
go run cmd/server/main.go
# http://localhost:8080
```

**QuantsysV2** (Python):
```bash
cd ../quantsys-v2
python adapters/inbound/fastapi_app/main.py
# http://localhost:5001
```

### 3. 配置环境变量

```bash
export AGENT_OS_BASE_URL=http://localhost:8080
export QUANTSYS_V2_BASE_URL=http://localhost:5001
```

---

## 📦 使用 tsx（推荐）

为了方便运行 TypeScript 示例，推荐安装 `tsx`:

```bash
# 全局安装
npm install -g tsx

# 或使用 npx（无需安装）
npx tsx examples/1-simple-agent.ts
```

---

## 🎯 学习路径

### 初学者
1. 先运行 `1-simple-agent.ts` 了解基本概念
2. 阅读代码注释理解每个步骤
3. 修改参数观察不同的行为

### 进阶
1. 运行 `2-backtest-strategy.ts` 学习策略回测
2. 尝试不同的股票和时间范围
3. 实现自己的策略评估逻辑

### 高级
1. 运行 `3-pool-management.ts` 学习投资组合管理
2. 创建自己的筛选条件
3. 结合回测优化股票池

### 生产环境
1. 研究 `4-trading-agent.ts` 的完整流程
2. 根据业务需求定制
3. 添加错误处理和日志
4. 部署到生产环境

---

## 💡 最佳实践

### 1. 错误处理

```typescript
try {
  const result = await client.quantsysV2.backtestStrategy({...});
} catch (error) {
  console.error('回测失败:', error.message);
  // 降级或重试
}
```

### 2. 日志记录

```typescript
console.log(`[${new Date().toISOString()}] Agent 启动`);
console.log(`[${new Date().toISOString()}] 任务完成`);
```

### 3. 资源清理

```typescript
// 总是在结束时清理资源
try {
  // 业务逻辑
} finally {
  await agentLoop.stopAll();
}
```

### 4. 配置管理

```typescript
// 使用环境变量
const config = {
  agentOS: {
    baseURL: process.env.AGENT_OS_BASE_URL || 'http://localhost:8080',
  },
  quantsysV2: {
    baseURL: process.env.QUANTSYS_V2_BASE_URL || 'http://localhost:5001',
  },
};
```

---

## 🐛 常见问题

### Q: 示例运行时报连接错误

**A**: 检查 Agent OS 和 QuantsysV2 是否正在运行：

```bash
# 检查 Agent OS
curl http://localhost:8080/health

# 检查 QuantsysV2
curl http://localhost:5001/docs
```

### Q: 回测数据不足

**A**: 运行数据更新脚本：

```bash
cd quantsys-v2
python scripts/update_klines_recommended.py
```

### Q: Agent 注册失败

**A**: 检查数据库是否已创建表：

```bash
psql -U your_user -d agent_os -c "\dt"
```

### Q: TypeScript 编译错误

**A**: 确保已安装依赖并构建：

```bash
cd agent-dh
pnpm install
pnpm build
```

---

## 🔗 相关资源

- [快速开始指南](../QUICKSTART.md)
- [API 文档](../docs/api-reference.md)（待创建）
- [项目总结](../docs/project-summary.md)

---

## 🤝 贡献

欢迎提交新的示例！请确保：
1. 代码清晰且有注释
2. 包含运行说明
3. 测试通过
4. 更新本 README

---

祝你使用愉快！🚀
