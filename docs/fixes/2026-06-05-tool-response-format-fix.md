# 工具响应格式修复

**日期**: 2026-06-05  
**问题**: `TypeError: Cannot read properties of undefined (reading 'filter')`  
**影响范围**: 所有自定义工具返回

## 问题分析

### 错误堆栈
```
TypeError: Cannot read properties of undefined (reading 'filter')
    at getTextOutput (/Users/mac/Documents/ai/pi-investment/node_modules/@mariozechner/pi-coding-agent/src/core/tools/render-utils.ts:36:36)
```

### 根本原因
框架 `render-utils.js` 的 `getTextOutput` 函数期望工具返回格式为：
```typescript
{
  content: [
    { type: "text", text: "结果内容" }
  ]
}
```

但某些情况下，工具返回的对象中：
1. `content` 属性为 `undefined`
2. `details` 属性为 `undefined`（而非 `null`）

导致框架在访问 `result.content.filter()` 时崩溃。

## 修复方案

### 1. 项目层面修复（src/infrastructure/tools/）

#### a. `shared/error-handler.ts`
修改 `formatToolResult` 函数，将 `details: undefined` 改为 `details: null`：

```typescript
// ✅ 修复后
if (typeof result === 'string') {
  return {
    content: [{ type: "text" as const, text: result }],
    details: null  // 从 undefined 改为 null
  };
}
```

#### b. `utils/tool-response-handler.ts`
更新注释说明 `details` 必须存在但可以为 `null`：

```typescript
export interface ToolResponse {
  content: Array<{ type: 'text'; text: string }>;
  details: any; // 必须存在，但可以为 null
}
```

### 2. 框架层面修复（node_modules/）

为 `@mariozechner/pi-coding-agent` 添加防御性检查：

```javascript
export function getTextOutput(result, showImages) {
    if (!result)
        return "";
    // ✅ 新增：防御性检查
    if (!result.content || !Array.isArray(result.content)) {
        return "";
    }
    const textBlocks = result.content.filter((c) => c.type === "text");
    // ...
}
```

使用 `patch-package` 管理补丁：
- 补丁文件: `patches/@mariozechner+pi-coding-agent+0.73.1.patch`
- 自动应用: `npm install` 时通过 `postinstall` 脚本

## 验证测试

创建测试文件 `src/infrastructure/tools/__tests__/tool-response-format.test.ts`：

```bash
npm test -- src/infrastructure/tools/__tests__/tool-response-format.test.ts
```

✅ 所有测试通过 (4/4)

## 影响评估

### 修复前
- 任何返回 `details: undefined` 的工具都会导致崩溃
- 框架无法处理缺少 `content` 的响应

### 修复后
- ✅ 统一使用 `details: null` 替代 `undefined`
- ✅ 框架层面增加防御性检查
- ✅ 所有现有工具兼容新格式
- ✅ 自动化补丁管理（patch-package）

## 后续行动

1. ✅ 提交代码到主分支
2. ⏳ 向 `@mariozechner/pi-coding-agent` 提交 issue/PR
3. ⏳ 审查所有自定义工具，确保返回格式正确

## 相关文件

- `src/infrastructure/tools/shared/error-handler.ts` (修复 formatToolResult)
- `src/infrastructure/tools/utils/tool-response-handler.ts` (修复 createErrorResponse)
- `patches/@mariozechner+pi-coding-agent+0.73.1.patch` (框架补丁)
- `package.json` (添加 postinstall 脚本)
- `src/infrastructure/tools/__tests__/tool-response-format.test.ts` (验证测试)

## 教训总结

1. **防御性编程**: 框架层面应对异常输入做容错处理
2. **类型一致性**: `undefined` vs `null` 需要明确区分
3. **补丁管理**: 使用 `patch-package` 管理第三方依赖的临时修复
4. **测试覆盖**: 边界情况需要充分测试
