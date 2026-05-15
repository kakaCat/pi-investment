# Evolution System 测试指南

> 更新时间: 2026-05-15  
> 用途: 测试 Evolution 重构后的功能

---

## 🧪 测试方式

### 方式 1: 自动化测试脚本（推荐）

```bash
# 运行测试脚本
tsx src/scripts/test-evolution-flow.ts
```

**测试内容**：
1. ✅ 检查数据文件是否存在
2. ✅ 统计交易数量（买入/卖出）
3. ✅ 运行完整的进化分析
4. ✅ 捕获并显示错误信息

---

### 方式 2: 手动测试（完整流程）

#### 步骤 1: 启动服务
```bash
npm run dev
```

#### 步骤 2: 测试帮助命令
```bash
> /evolution --help
```

**预期输出**：
```
🧬 进化分析命令

用法:
  /evolution                    运行进化分析（默认配置）
  /evolution --view             查看最近一次进化报告
  /evolution --days 30          只分析最近 30 天交易
  ...
```

#### 步骤 3: 查看最近报告
```bash
> /evolution --view
```

**预期输出**：
- 如果有报告：显示最近一次的完整报告
- 如果没有报告：提示运行 `/evolution` 生成

#### 步骤 4: 运行进化分析
```bash
> /evolution --all
```

**预期输出**：

**场景 A: 数据充足**
```
[进化] 配置参数:
  - 目标收益率: 10%
  - 交易窗口: 全部

[进化] 数据检查:
  - 持仓数量: X
  - 交易记录: Y 笔（窗口内: Y 笔）

✅ 数据检查通过，开始分析...

[完整的进化流程...]

✅ 进化分析完成
📊 报告路径: .pi-invest/evolution/evolution-2026-05-15-HHMMSS.md
...
```

**场景 B: 数据不足**
```
[进化] 数据检查:
  - 持仓数量: 0
  - 交易记录: 2 笔（窗口内: 2 笔）

⚠️  交易数据较少（2 笔），分析结果可能不准确。
   建议至少有 3 笔交易才能产生有意义的统计结果。

✅ 数据检查通过，开始分析...
[继续执行，但有警告]
```

**场景 C: 没有数据**
```
[进化] 数据检查:
  - 持仓数量: 0
  - 交易记录: 0 笔（窗口内: 0 笔）

❌ 进化分析失败: 没有交易数据，无法运行进化分析。
请先添加交易记录到 .pi-invest/trades.json
```

---

### 方式 3: 单元测试（开发用）

```bash
# 运行所有测试
npm test

# 运行 evolution 相关测试
npm test -- evolution

# 查看测试覆盖率
npm run test:coverage
```

---

## 📋 测试清单

### 功能测试

- [ ] `/evolution --help` 显示帮助信息
- [ ] `/evolution --view` 查看最近报告
- [ ] `/evolution` 默认配置运行
- [ ] `/evolution --days 30` 自定义时间窗口
- [ ] `/evolution --all` 分析全部交易
- [ ] `/evolution --target 15` 自定义目标收益
- [ ] `/evolution --days 60 --target 12` 组合参数

### 数据检查测试

- [ ] 没有交易数据 → 抛出错误
- [ ] 时间窗口内没有交易 → 抛出错误
- [ ] 交易数量 < 3 → 显示警告但继续
- [ ] 没有持仓数据 → 显示警告但继续
- [ ] 数据充足 → 正常运行

### 文件生成测试

- [ ] 报告文件命名：`evolution-YYYY-MM-DD-HHMMSS.md`
- [ ] 执行结果命名：`execution-YYYY-MM-DD-HHMMSS.json`
- [ ] 同一天多次运行不覆盖
- [ ] 历史记录正确保存

### 代码生成测试（需要 Codex）

- [ ] Codex 可用性检查
- [ ] 代码生成成功
- [ ] 沙箱验证通过
- [ ] 工具注册成功
- [ ] Git 分支创建和合并

### CRON 自动触发测试

- [ ] CRON 配置正确加载
- [ ] 每周日 20:00 自动触发
- [ ] 自动运行完成
- [ ] 报告正确生成

---

## 🐛 常见问题排查

### 问题 1: 编译错误

**现象**：
```
error TS2802: Type 'Map<string, Trade[]>' can only be iterated...
```

**原因**：TypeScript 配置问题（不影响运行）

**解决**：
```bash
# 直接运行（tsx 会处理）
tsx src/scripts/test-evolution-flow.ts

# 或者构建后运行
npm run build
node dist/scripts/test-evolution-flow.js
```

---

### 问题 2: Codex 不可用

**现象**：
```
❌ Codex 代码生成失败: Command failed: codex exec...
```

**排查**：
```bash
# 检查 Codex 是否安装
which codex

# 测试 Codex
codex exec --ephemeral "console.log('test')"
```

**解决**：
- 如果 Codex 不可用，进化分析会跳过代码生成步骤
- 只生成建议，不自动应用

---

### 问题 3: 数据格式错误

**现象**：
```
❌ 进化分析失败: Unexpected token...
```

**排查**：
```bash
# 检查 JSON 格式
cat .pi-invest/trades.json | jq .
cat .pi-invest/portfolio.json | jq .
```

**解决**：修复 JSON 格式错误

---

### 问题 4: 只有卖出没有买入

**现象**：
```
⚠️  只有卖出没有买入，无法计算已实现盈亏
```

**原因**：FIFO 配对需要先有买入，再有卖出

**解决**：
- 添加对应的买入记录
- 或者这些卖出对应的买入在更早的时间（需要补充历史数据）

---

## 📊 测试数据示例

### 最小测试数据（3 笔交易）

```json
// .pi-invest/trades.json
[
  {
    "id": 1,
    "symbol": "600519",
    "name": "贵州茅台",
    "action": "buy",
    "price": 1800,
    "quantity": 100,
    "amount": 180000,
    "date": "2026-04-01T00:00:00.000Z",
    "reason": "测试买入"
  },
  {
    "id": 2,
    "symbol": "600519",
    "name": "贵州茅台",
    "action": "sell",
    "price": 1900,
    "quantity": 50,
    "amount": 95000,
    "date": "2026-04-15T00:00:00.000Z",
    "reason": "测试卖出（盈利）"
  },
  {
    "id": 3,
    "symbol": "600519",
    "name": "贵州茅台",
    "action": "sell",
    "price": 1750,
    "quantity": 50,
    "amount": 87500,
    "date": "2026-05-01T00:00:00.000Z",
    "reason": "测试卖出（亏损）"
  }
]
```

---

## 🎯 预期结果

### 成功运行的标志

1. ✅ 数据检查通过
2. ✅ 进化报告生成（`.pi-invest/evolution/evolution-*.md`）
3. ✅ 执行结果保存（`.pi-invest/evolution/execution-*.json`）
4. ✅ 进化历史更新（`.pi-invest/evolution/history/*.json`）
5. ✅ 经验总结更新（`.pi-invest/evolution/experience-summary.json`）
6. ✅ 控制台输出完整的统计信息

### 输出示例

```
✅ 进化分析完成
📊 报告路径: .pi-invest/evolution/evolution-2026-05-15-143022.md
📈 目标收益: 10% | 实际收益: 8.5%
🎯 胜率: 65% | 交易次数: 12
🔍 归因: capability_insufficient
💡 优化建议: 3 条
✨ 已自动应用: 2 条
```

---

## 📚 相关文档

- [Evolution 使用指南](./evolution-usage-guide.md)
- [架构重构报告](./architecture-refactoring-report.md)
- [Evolution 技术文档](./evolution-system-analysis.md)

---

**文档维护**: 请在测试流程变更后更新此文档
