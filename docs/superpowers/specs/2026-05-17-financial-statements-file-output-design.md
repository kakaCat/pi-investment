# get_financial_statements 文件输出设计

**日期**: 2026-05-17  
**状态**: 待实现

## 问题

`get_financial_statements` 工具返回的财务报表数据量过大（通常 > 10KB），直接返回给 LLM 会占用大量 token，影响性能和成本。

## 解决方案

参考 browser-tool 的实现模式，当数据超过阈值时，将完整数据写入临时文件，只返回预览内容和文件路径，让 LLM 使用 Read 工具按需浏览。

## 设计细节

### 数据流

1. LLM 调用 `get_financial_statements` 工具
2. TS 层调用 Python 的 `get_financial_statements` 函数
3. Python 返回完整 JSON 数据
4. **TS 层判断数据大小**：
   - 如果 `result.length > 2000` 字符：写入文件，返回预览 + 文件路径
   - 如果 `result.length <= 2000` 字符：直接返回原始数据
5. LLM 收到文件路径后，使用 Read 工具配合 offset/limit 浏览文件

### 实现逻辑

**修改文件**: `src/infrastructure/tools/invest/financial-tools.ts`

**修改位置**: `getFinancialStatementsTool.execute` 函数

**核心代码**:

```typescript
import { writeFile } from "fs/promises";
import { join } from "path";

execute: async (_toolCallId, params: any) => {
  const err = requireAshare(params.symbol);
  if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
  
  const args: Record<string, unknown> = { 
    symbol: params.symbol, 
    statement: params.statement ?? "all" 
  };
  if (params.recent_n !== undefined) args.recent_n = params.recent_n;
  
  const result = await callPython("get_financial_statements", args);
  
  // 判断数据大小
  if (result.length > 2000) {
    // 写入临时文件
    const filePath = `/tmp/pi-financials-${params.symbol}-${params.statement || 'all'}-${Date.now()}.json`;
    await writeFile(filePath, result, 'utf-8');
    
    // 返回预览（前 500 字符）+ 文件路径
    const preview = result.substring(0, 500);
    const resultText = `财务数据已保存到: ${filePath}\n\n数据预览 (前500字符):\n${preview}...\n\n[总长度: ${result.length} 字符，完整内容见文件。使用 Read 工具查看完整内容]`;
    
    return { content: [{ type: "text" as const, text: resultText }], details: undefined };
  } else {
    // 数据较小，直接返回
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  }
}
```

### 文件命名规范

**格式**: `/tmp/pi-financials-{symbol}-{statement}-{timestamp}.json`

**示例**:
- `/tmp/pi-financials-600519-all-1737158400000.json`
- `/tmp/pi-financials-000001-income-1737158500000.json`

### 返回格式示例

**大数据场景**（> 2000 字符）:

```
财务数据已保存到: /tmp/pi-financials-600519-all-1737158400000.json

数据预览 (前500字符):
{"income_statement":{"symbol":"600519","report_type":"利润表","count":8,"data":[{"报告日":"2024-09-30","更新日期":"2024-10-30","营业总收入":123456789.0,"营业成本":45678901.0,"营业税金及附加":1234567.0,"销售费用":2345678.0,"管理费用":3456789.0,"研发费用":4567890.0,"财务费用":567890.0,"资产减值损失":678901.0,"公允价值变动收益":789012.0,"投资收益":890123.0,"营业利润":12345678.0,"营业外收入":234567.0,"营业外支出":345678.0,"利润总额":12234567.0,"所得税费用":1234567.0,"净利润":11000000.0,"归属于母公司所有者的净利润":10500000.0,"少数股东损益":500000.0,"扣除非经常性损益后的净利润":10000000.0,"基本每股收益":8.5,"稀释每股收益":8.5},...

[总长度: 45678 字符，完整内容见文件。使用 Read 工具查看完整内容]
```

**小数据场景**（<= 2000 字符）:

直接返回完整 JSON 数据（保持现有行为）

## 技术细节

### 阈值选择

- **2000 字符**: 参考 browser-tool 的实现，选择 2000 作为阈值
- **预览长度 500 字符**: 与 browser-tool 保持一致

### 文件清理

临时文件存储在 `/tmp/` 目录，由操作系统自动清理（通常在重启时），无需手动清理逻辑。

### 依赖项

需要导入：
```typescript
import { writeFile } from "fs/promises";
import { join } from "path";
```

## 影响范围

### 修改文件

- `src/infrastructure/tools/invest/financial-tools.ts` - 修改 `getFinancialStatementsTool.execute`

### 不受影响

- Python 层 (`python/akshare_bridge.py`) - 无需修改
- 其他财务工具 (`get_financial_data`, `get_hk_financials`, `get_hk_analysis`) - 保持不变
- 工具描述和参数定义 - 保持不变

## 向后兼容性

- 小数据场景（<= 2000 字符）保持原有行为，完全向后兼容
- 大数据场景改为文件输出，LLM 需要使用 Read 工具查看，但这是预期行为改进

## 测试验证

### 测试场景

1. **小数据测试**: `get_financial_statements({symbol: "600519", statement: "income", recent_n: 2})` - 应直接返回数据
2. **大数据测试**: `get_financial_statements({symbol: "600519", statement: "all", recent_n: 8})` - 应返回文件路径
3. **文件可读性**: 使用 Read 工具读取生成的文件，验证数据完整性

### 验证标准

- 文件路径格式正确
- 预览内容为前 500 字符
- 文件内容与 Python 返回的原始数据一致
- Read 工具可以正常读取文件
