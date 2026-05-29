# Factor Analyze Tool Fix - 2026-05-28

## 问题描述

`factor_analyze` 工具调用无结果返回，无法评估 RSI/MACD/ROE 等因子的 IC 值和有效性。

## 根本原因

**字段命名不一致 + 数据结构不匹配**

1. **API 响应格式**（quantsys-v2）：
   - 使用 `api_response()` 包装器，返回 `{ success: true, data: {...} }` 结构
   - 自动将 snake_case 转换为 camelCase（`ic_daily` → `icDaily`）

2. **TypeScript 类型定义**：
   - 期望直接的 `{ success: true, factors: [...] }` 结构（无 `data` 包装）
   - 期望 snake_case 字段名（`ic_daily`, `ic_weekly`, `ic_monthly`, `decay_curve`）

3. **实际 API 返回**：
   ```json
   {
     "success": true,
     "data": {
       "success": true,
       "factors": [{
         "name": "rsi",
         "icDaily": 0.0643,      // camelCase
         "icWeekly": 0.0835,
         "icMonthly": 0.1028,
         "coverage": 0.9052,
         "stability": 0.6885,
         "decayCurve": [...]     // camelCase
       }]
     }
   }
   ```

## 修复方案

修改 TypeScript 客户端 `analyzeFactors()` 函数：

1. **解包 `data` 字段**：处理 `api_response()` 的包装结构
2. **字段名转换**：camelCase → snake_case
3. **类型安全**：添加中间类型定义以匹配 API 实际响应

### 修改文件

- `src/infrastructure/quant/quant-v2-client.ts`
  - 添加 `FactorMetrics` 类型导入
  - 重写 `analyzeFactors()` 函数，添加响应解包和字段转换逻辑

### 代码变更

```typescript
// 修复前
export async function analyzeFactors(params: FactorAnalyzeParams): Promise<FactorAnalysis> {
  const url = `${V2_API_BASE}/api/portfolio/factor-analyze`;
  return fetchV2<FactorAnalysis>(url, { method: 'POST', body: params });
}

// 修复后
export async function analyzeFactors(params: FactorAnalyzeParams): Promise<FactorAnalysis> {
  const url = `${V2_API_BASE}/api/portfolio/factor-analyze`;
  
  // 解包 API 响应并转换字段名
  const response = await fetchV2<{
    success: boolean;
    data: {
      success: boolean;
      factors: Array<{
        name: string;
        icDaily: number;
        icWeekly: number;
        icMonthly: number;
        coverage: number;
        stability: number;
        decayCurve: number[];
      }>;
    };
  }>(url, { method: 'POST', body: params });

  // camelCase → snake_case
  const factors: FactorMetrics[] = (response.data.factors || []).map(f => ({
    name: f.name,
    ic_daily: f.icDaily,
    ic_weekly: f.icWeekly,
    ic_monthly: f.icMonthly,
    coverage: f.coverage,
    stability: f.stability,
    decay_curve: f.decayCurve,
  }));

  return {
    success: response.data.success,
    factors,
  };
}
```

## 验证

### 1. 单元测试

创建了 `src/infrastructure/quant/quant-v2-client.test.ts`，包含 4 个测试用例：

- ✅ 验证返回正确的 snake_case 字段
- ✅ 验证不存在 camelCase 字段（防止回归）
- ✅ 验证多因子处理
- ✅ 验证参数校验

所有测试通过：
```
Test Suites: 1 passed, 1 total
Tests:       4 passed, 4 total
```

### 2. 集成测试

手动测试 `factor_analyze` 工具：

```javascript
const result = await factorAnalyzeTool.execute('test-call-id', {
  factors: ['rsi', 'macd', 'roe'],
  start_date: '2024-01-01',
  end_date: '2024-01-31'
});
```

**输出示例：**
```
因子分析结果（共 3 个因子）:

【rsi】
  日度IC: 0.0313
  周度IC: 0.0407
  月度IC: 0.0500
  覆盖率: +89.82%
  稳定性: 0.7050
  衰减曲线: [0.031, 0.028, 0.025, ...]

【macd】
  日度IC: 0.0248
  周度IC: 0.0323
  月度IC: 0.0397
  覆盖率: +95.91%
  稳定性: 0.6275
  衰减曲线: [0.025, 0.022, 0.020, ...]

【roe】
  日度IC: 0.0259
  周度IC: 0.0336
  月度IC: 0.0414
  覆盖率: +87.66%
  稳定性: 0.7449
  衰减曲线: [0.026, 0.023, 0.021, ...]
```

## 影响范围

- ✅ 修复了 `factor_analyze` 工具，现在可以正常返回因子分析结果
- ✅ 用户可以评估因子的 IC 值、覆盖率、稳定性和衰减曲线
- ✅ 不影响其他工具（修改仅限于 `analyzeFactors` 函数）
- ✅ 向后兼容（API 端点未修改）

## 为什么选择修改客户端而不是 API

1. **标准化**：quantsys-v2 有 31 个端点使用 `api_response()` 包装器，这是后端的标准模式
2. **最小影响**：修改 API 会影响其他调用方（如果存在）
3. **适配原则**：客户端应该适配后端的标准响应格式

## 相关文件

- `src/infrastructure/quant/quant-v2-client.ts` - 修复的客户端代码
- `src/infrastructure/quant/quant-v2-client.test.ts` - 新增的单元测试
- `src/infrastructure/tools/factor/factor-analyze-tool.ts` - 使用修复后的客户端
- `quantsys-v2/api/routes/analysis.py` - API 端点实现（未修改）
- `quantsys-v2/api/shared.py` - `api_response()` 包装器（未修改）

## 调试过程

使用了系统化调试流程（`superpowers:systematic-debugging`）：

1. **Phase 1: Root Cause Investigation** - 收集证据，发现字段命名和结构不匹配
2. **Phase 2: Pattern Analysis** - 分析 `api_response()` 包装器的行为
3. **Phase 3: Hypothesis and Testing** - 形成假设并验证
4. **Phase 4: Implementation** - 实现修复并添加测试

## 后续建议

1. **文档更新**：在 CLAUDE.md 中记录 quantsys-v2 API 的响应格式约定
2. **其他工具检查**：检查其他 v2 工具是否有类似问题
3. **类型生成**：考虑从 Python API 自动生成 TypeScript 类型定义
