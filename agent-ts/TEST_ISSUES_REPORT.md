# Jest 单元测试问题报告

**日期**: 2026-06-19
**状态**: 89/89 测试套件失败

## 问题概述

所有 Jest 测试都因为 Babel 解析器不支持某些 TypeScript 语法而失败。

## 主要问题类型

### 1. **类型导入语法不兼容**
```typescript
// ❌ 不支持
import { FactorLibrary, type TechnicalIndicators } from './factor-library.js';

// ✅ 需要改为
import { FactorLibrary } from './factor-library.js';
import type { TechnicalIndicators } from './factor-library.js';
```

### 2. **类型注解在变量声明中**
```typescript
// ❌ 不支持
const strategies: string[] = [];

// ✅ 需要改为
const strategies = [] as string[];
// 或者
const strategies = [];
```

### 3. **复杂类型注解**
```typescript
// ❌ 不支持
let cronHandler: ((payload: { kind: string; chatId?: string }) => Promise<void>) | null = null;

// ✅ 需要改为（定义类型别名）
type CronHandler = ((payload: { kind: string; chatId?: string }) => Promise<void>) | null;
let cronHandler: CronHandler = null;
```

### 4. **类方法中的访问修饰符**
```typescript
// ❌ 不支持
protected async executeCommand(domain: string, action: string): Promise<any> {}

// ✅ 需要改为
async executeCommand(domain: string, action: string): Promise<any> {}
```

### 5. **Vitest 导入混用**
一些测试文件使用了 `vitest` 而不是 `@jest/globals`：
- `timeseries-analyzer-tool.test.ts`
- `trade-monitor-tool.test.ts`

### 6. **类型断言语法**
```typescript
// ❌ 部分不支持
mockFetch as any

// ✅ 已修复，移除 as any
mockFetch
```

## 影响范围

- **总测试套件**: 89 个
- **失败套件**: 89 个
- **通过测试**: 0 个

## 解决方案

### 方案 A：升级 Babel 配置（推荐）

创建 `babel.config.js` 支持完整的 TypeScript 语法：

```javascript
module.exports = {
  presets: [
    ['@babel/preset-env', { targets: { node: 'current' } }],
    ['@babel/preset-typescript', {
      allowDeclareFields: true,
      onlyRemoveTypeImports: true,
    }],
  ],
};
```

安装依赖：
```bash
npm install --save-dev @babel/preset-typescript @babel/preset-env
```

### 方案 B：切换到 ts-jest（备选）

修改 Jest 配置使用 `ts-jest` 转换器：

```javascript
// jest.config.js
export default {
  preset: 'ts-jest/presets/default-esm',
  extensionsToTreatAsEsm: ['.ts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      useESM: true,
      tsconfig: {
        allowSyntheticDefaultImports: true,
        esModuleInterop: true,
      }
    }],
  },
};
```

### 方案 C：批量修复测试文件（最耗时）

逐个修复 89 个测试文件中的语法问题。

## 已修复的文件

1. ✅ `signal-generator.test.ts` - 修复类型导入
2. ✅ `backend-control-tool.test.ts` - 移除 `as any`
3. ✅ `timeseries-analyzer-tool.test.ts` - vitest → jest
4. ✅ `trade-monitor-tool.test.ts` - vitest → jest
5. ✅ `strategy-helpers.test.ts` - 移除类型注解

## 待修复文件

还有约 84 个测试文件需要修复类似问题。

## 建议行动

**立即执行**: 方案 A（升级 Babel 配置）
- 工作量最小
- 解决根本问题
- 不需要修改每个测试文件

**后续**: 
- 确认所有测试通过
- 建立 CI 检查防止引入新的语法问题
- 统一测试框架（移除 vitest 依赖或统一使用 vitest）
