---
id: wl-2026-08-factor-memory-refactor-summary
title: Factor 和 Memory 包 BaseTool 重构总结
type: worklog
status: archived
updated: 2026-08-28
owners: [agent-dh]
tags: [worklog, 2026-08]
---

# Factor 和 Memory 包 BaseTool 重构总结

**完成日期**: 2026-08-28  
**重构人员**: Agent (Claude)  
**参考标准**: evolution 包的工厂函数模式

---

## ✅ 已完成的工作

### 1. Factor 包重构 (2 个工具)

#### 工具列表
- `factor_calculate` - 计算个股的技术因子和财务因子
- `factor_analyze` - 分析因子的历史有效性（IC、IR、覆盖率等）

#### 重构内容
1. **创建 BaseTool 类**
   - `FactorCalculateTool.ts` - 继承 BaseTool，实现三阶段架构
   - `FactorAnalyzeTool.ts` - 继承 BaseTool，实现三阶段架构

2. **创建工厂函数** (参考 evolution 标准)
   - `tools/FactorCalculateTool/index.ts` - 导出 `createFactorCalculateTool()`
   - `tools/FactorAnalyzeTool/index.ts` - 导出 `createFactorAnalyzeTool()`

3. **更新 index.ts**
   ```typescript
   ctx.tools.register(createFactorCalculateTool(qv2));
   ctx.tools.register(createFactorAnalyzeTool(qv2));
   ```

4. **修复 prompt.ts**
   - ✅ 将 `input`/`output` 改为 `params`/`expectedResult`
   - ✅ 添加 `notes`、`relatedTools`、`parameters`、`output` 字段

5. **修复 wrap 方法**
   - ✅ 移除非法的 `message` 和 `metadata` 字段
   - ✅ 只返回 `{ success: true, data }`

---

### 2. Memory 包重构 (3 个工具)

#### 工具列表
- `memory_search` - 语义搜索长期记忆
- `memory_write` - 写入长期记忆
- `experience_write` - 记录交易经验教训

#### 重构内容
1. **创建 BaseTool 类**
   - `MemorySearchTool.ts` - 继承 BaseTool
   - `MemoryWriteTool.ts` - 继承 BaseTool
   - `ExperienceWriteTool.ts` - 继承 BaseTool

2. **创建工厂函数**
   - `tools/MemorySearchTool/index.ts` - 导出 `createMemorySearchTool()`
   - `tools/MemoryWriteTool/index.ts` - 导出 `createMemoryWriteTool()`
   - `tools/ExperienceWriteTool/index.ts` - 导出 `createExperienceWriteTool()`

3. **更新 index.ts**
   ```typescript
   ctx.tools.register(createMemorySearchTool(osMemory));
   ctx.tools.register(createMemoryWriteTool(osMemory));
   ctx.tools.register(createExperienceWriteTool(osMemory));
   ```

4. **修复 prompt.ts** (同 factor 包)

5. **修复 wrap 方法** (同 factor 包)

---

## 📋 重构模式对比

### Evolution 标准模式 (推荐)

```typescript
// tools/XxxTool/index.ts
export function createXxxTool(client: Client) {
  const tool = new XxxTool(client);
  return defineTool(tool.toDSHToolDefinition());
}

// packages/xxx/src/index.ts
ctx.tools.register(createXxxTool(client));
```

**优点**:
- ✅ 更简洁，利用 `BaseTool.toDSHToolDefinition()` 自动转换
- ✅ 符合 evolution 包的标准实现
- ✅ 工厂函数封装了实例化逻辑
- ✅ 更容易测试和维护

### 旧的直接实例化模式 (已废弃)

```typescript
const tool = new XxxTool(client);
ctx.tools.register(defineTool({
  name: 'xxx',
  execute: async (args) => {
    const result = await tool.call(args);
    if (!result.success) throw new Error(result.error?.issue);
    return result.data;
  }
}));
```

**缺点**:
- ❌ 代码冗余，手动处理错误和返回值
- ❌ 没有利用 BaseTool 的 `toDSHToolDefinition()` 方法
- ❌ 不符合 evolution 标准

---

## ✅ 验证结果

### TypeScript 编译检查
```bash
cd /Users/yunpeng/pi-investment/agent-dh/packages/factor
npx tsc --noEmit
# ✅ 只剩未使用变量警告（正常）
```

### 工具导出验证
```bash
npx tsx scripts/verify-factor-memory.ts
# ✅ 所有工具类正确导出
# ✅ 工厂函数正常工作
```

---

## 📊 进度统计

- **P2 包进度**: 14/23 (60.9%)
- **总体进度**: 59/126 (46.8%)
- factor (2/2) ✅
- memory (3/3) ✅

---

## 🎯 关键学习点

1. **BaseTool 三阶段架构**
   - `validate()` - 参数校验
   - `execute()` - 业务逻辑
   - `wrap()` - 结果包装

2. **ToolResponse 接口**
   - 只有 `success`、`data`、`error`、`meta` 字段
   - 不支持 `message` 和 `metadata` 字段

3. **ToolPrompt 的 examples 格式**
   - 使用 `params` 和 `expectedResult`
   - 不是 `input` 和 `output`

4. **工厂函数模式是标准实现**
   - 参考 evolution 包
   - 利用 `BaseTool.toDSHToolDefinition()`

---

## 📝 后续工作

继续重构其他待重构的包：
- evolver (3 个工具)
- window-manager (2 个工具)
- 其他 P1/P2 包

参考本次重构的标准模式和经验教训。
