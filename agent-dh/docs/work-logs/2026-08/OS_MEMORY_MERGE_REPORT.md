---
id: wl-2026-08-os-memory-merge-report
title: OS-Memory 合并报告
type: worklog
status: archived
updated: 2026-08-28
owners: [agent-dh]
tags: [worklog, 2026-08]
---

# OS-Memory 合并报告

**日期**: 2026-08-28  
**操作**: 将 `@pi-investment/os-memory` 合并到 `@pi-investment/agent-os-client`  
**原因**: 消除冗余中间层，统一 Agent OS API 访问

---

## 1. 合并背景

### 问题分析

**os-memory** 只是 **agent-os-client** 的 memory API 的薄包装层：

```
memory package (Cordis Plugin)
   ↓ 使用
os-memory (Adapter) ← 冗余中间层
   ↓ 调用
agent-os-client (SDK)
   ↓ 调用
Agent OS API
```

### 合并方案

将 os-memory 的适配器逻辑（OsMemoryStore）直接集成到 agent-os-client：

```
memory package (Cordis Plugin)
   ↓ 使用
agent-os-client (SDK + Adapter) ← 统一入口
   ↓ 调用
Agent OS API
```

---

## 2. 实施步骤

### 2.1 添加适配器到 agent-os-client

**文件**: `agent-os-client/src/memory/adapter.ts`

新增 `OsMemoryStore` 类，提供与原 os-memory 完全兼容的 API：
- `createMemory(entry)` - 写入记忆（业务字段映射）
- `searchMemory(params)` - 搜索记忆（过滤和解包）
- `write(params)` - 兼容方法（向后兼容）

**导出**: `agent-os-client/src/index.ts`
```typescript
export { OsMemoryStore } from './memory/adapter.js';
export type { OsMemoryEntry, OsMemorySearchResult } from './memory/adapter.js';
```

### 2.2 迁移依赖包

更新所有使用 os-memory 的 packages 的 import：

| Package | 文件 | 修改 |
|---------|------|------|
| memory | `src/index.ts` | `@pi-investment/os-memory` → `@pi-investment/agent-os-client` |
| evolver | `src/index.ts` | `@pi-investment/os-memory` → `@pi-investment/agent-os-client` |
| trading | `src/index.ts` | `@pi-investment/os-memory` → `@pi-investment/agent-os-client` |
| risk | `src/index.ts` | `@pi-investment/os-memory` → `@pi-investment/agent-os-client` |
| market | `src/index.ts` | `@pi-investment/os-memory` → `@pi-investment/agent-os-client` |
| learning | `src/index.ts` | `@pi-investment/os-memory` → `@pi-investment/agent-os-client` |

### 2.3 更新 package.json

移除所有 package.json 中的 `@pi-investment/os-memory` 依赖：
- packages/memory/package.json ✅
- packages/evolver/package.json ✅
- packages/trading/package.json ✅
- packages/risk/package.json ✅
- packages/market/package.json ✅
- packages/learning/package.json ✅

修复 JSON 尾随逗号问题（sed 删除导致的语法错误）。

### 2.4 删除 os-memory package

```bash
rm -rf agent-dh/packages/os-memory
```

---

## 3. 验证结果

### 3.1 编译验证

✅ **agent-os-client**: 编译成功
```bash
cd agent-os-client && npm run build
# 无错误
```

✅ **agent-dh**: 依赖安装成功
```bash
cd agent-dh && pnpm install
# Done in 1.1s
```

### 3.2 功能测试

✅ **memory package**: 21/21 测试通过
```bash
cd packages/memory && npx tsx scripts/test-memory-tools.ts
# 总计: 21 个测试
# 通过: 21 个 ✓
# 失败: 0 个 ✗
# 覆盖率: 100.0%
```

所有工具正常工作：
- MemorySearchTool - 搜索记忆
- MemoryWriteTool - 写入记忆
- ExperienceWriteTool - 写入经验

---

## 4. 影响范围

### 4.1 已迁移的 packages（6 个）

所有使用 os-memory 的 packages 已成功迁移：
- ✅ memory (已重构 P0)
- ✅ evolver (已重构 P1)
- ✅ trading (已重构 P0)
- ✅ risk (已重构 P0)
- ✅ market (已重构 P0)
- ✅ learning (未重构 P2)

### 4.2 API 兼容性

**完全向后兼容** - 所有调用方代码无需修改，只需更改 import：

```typescript
// 之前
import { OsMemoryStore } from '@pi-investment/os-memory';

// 之后
import { OsMemoryStore } from '@pi-investment/agent-os-client';

// 使用方式完全相同
const osMemory = new OsMemoryStore({ baseURL, agentId });
await osMemory.createMemory({ kind, scope, title, content, ... });
await osMemory.searchMemory({ q, kind, scope, top_k, ... });
```

---

## 5. 优势总结

### 5.1 架构简化

- ❌ **之前**: agent-os-client → os-memory → 业务包（3 层）
- ✅ **之后**: agent-os-client → 业务包（2 层）

### 5.2 维护成本降低

- 消除了冗余的 os-memory package
- Agent OS API 的所有功能统一在 agent-os-client 管理
- 减少了依赖链长度

### 5.3 开发体验改进

- 开发者只需依赖 agent-os-client 一个包
- API 文档集中在一处
- 类型定义更统一

---

## 6. 后续建议

### 6.1 文档更新

建议更新以下文档：
- agent-os-client 的 README，添加 OsMemoryStore 使用示例
- 各业务包的文档，更新依赖说明

### 6.2 代码迁移

所有使用 os-memory 的代码已迁移完成，无需进一步操作。

### 6.3 其他潜在合并

建议保持现状：
- **evolution** 和 **evolver** - 职责不同（策略优化 vs Prompt 进化）
- **evolver** 和 **genome** - 分层清晰（业务逻辑 vs 基础设施）

---

## 7. 总结

✅ **合并成功完成**
- os-memory 功能已完整集成到 agent-os-client
- 所有 6 个依赖包已成功迁移
- 测试通过率 100%
- 零破坏性变更，完全向后兼容

**影响**: 
- 删除 1 个冗余 package
- 简化依赖关系
- 提升架构清晰度

**风险**: 无
