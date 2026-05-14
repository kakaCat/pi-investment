/**
 * Code Generator - 使用 Agent 自身能力生成工具代码
 *
 * 根据补偿器的建议，自动生成完整的 TypeScript 工具实现。
 */

import { getSession } from '../../core/agent/agent-loop.js';
import { getLastMessage, extractTextContent } from '../../core/agent/session-adapter.js';
import type { ToolAddition } from '../../types/evolution.js';
import * as fs from 'fs/promises';
import * as path from 'path';

export interface GeneratedCode {
  toolCode: string;
  testCode: string;
  toolFileName: string;
  testFileName: string;
}

/**
 * 从 Agent 响应中提取代码块
 */
function extractCodeBlocks(text: string): { tool: string; test: string } {
  const codeBlockRegex = /```(?:typescript|ts)?\n([\s\S]*?)```/g;
  const blocks: string[] = [];
  let match;

  while ((match = codeBlockRegex.exec(text)) !== null) {
    blocks.push(match[1].trim());
  }

  if (blocks.length < 1) {
    throw new Error('未能从 Agent 响应中提取代码块');
  }

  // 第一个代码块是工具实现，第二个（如果有）是测试
  return {
    tool: blocks[0],
    test: blocks.length > 1 ? blocks[1] : ''
  };
}

/**
 * 读取现有工具作为参考示例
 */
async function getToolExamples(): Promise<string> {
  const examplePath = path.join(process.cwd(), 'src/infrastructure/tools/analyze-sector-rotation-tool.ts');
  try {
    const content = await fs.readFile(examplePath, 'utf-8');
    // 只取前100行作为示例
    const lines = content.split('\n').slice(0, 100);
    return lines.join('\n');
  } catch {
    return '// 无法读取示例文件';
  }
}

/**
 * 使用 Agent 生成工具代码
 */
export async function generateToolCode(toolSpec: ToolAddition): Promise<GeneratedCode> {
  console.log(`🤖 正在生成工具代码: ${toolSpec.name}`);

  const session = await getSession();
  const exampleCode = await getToolExamples();

  // 构造详细的生成提示词
  const prompt = `请生成一个投资工具的完整 TypeScript 实现代码。

## 工具规格

- **名称**: ${toolSpec.name}
- **描述**: ${toolSpec.description}
- **原因**: ${toolSpec.reason}
- **预期效果**: ${toolSpec.expectedImpact}

## 实现要求

1. **参考现有工具模式**（以下是示例）：

\`\`\`typescript
${exampleCode}
\`\`\`

2. **必须包含的元素**：
   - 文件顶部的 JSDoc 注释说明工具用途
   - 导入必要的类型：\`import type { ToolDefinition } from "./index.js";\`
   - 导入 Type 用于参数定义：\`import { Type } from "@sinclair/typebox";\`
   - 如果需要调用 Python，导入：\`import { callPython } from "./invest-tools.js";\`
   - 导出一个符合 ToolDefinition 接口的常量，命名为 \`${toolSpec.name}Tool\`
   - 包含 name, label, description, parameters, execute 字段
   - execute 函数返回 \`{ content: [{ type: "text", text: string }], details?: any }\`

3. **参数定义**：
   - 使用 Type.Object() 定义参数 schema
   - 为每个参数添加 description
   - 使用 Type.Optional() 标记可选参数

4. **错误处理**：
   - 使用 try-catch 包裹主要逻辑
   - 返回友好的错误消息

5. **代码风格**：
   - 使用 TypeScript 严格模式
   - 添加必要的类型注解
   - 保持代码简洁清晰

## 输出格式

请按以下格式输出两个代码块：

第一个代码块：工具实现代码（${toolSpec.name}-tool.ts）
第二个代码块：单元测试代码（${toolSpec.name}-tool.test.ts）

测试代码要求：
- 使用 Jest 测试框架
- 至少包含 3 个测试用例：正常情况、错误处理、边界条件
- Mock 外部依赖（如 callPython）

现在请生成代码，只输出代码块，不要包含其他解释文字。`;

  // 发送提示词给 Agent
  await session.prompt(prompt);

  // 获取 Agent 的响应
  const lastMsg = getLastMessage(session);
  if (!lastMsg || lastMsg.role !== 'assistant') {
    throw new Error('未能获取 Agent 响应');
  }

  const responseText = extractTextContent(lastMsg);
  if (!responseText) {
    throw new Error('Agent 响应为空');
  }

  console.log(`📝 Agent 响应长度: ${responseText.length} 字符`);

  // 提取代码块
  const { tool, test } = extractCodeBlocks(responseText);

  const toolFileName = `${toolSpec.name}-tool.ts`;
  const testFileName = `${toolSpec.name}-tool.test.ts`;

  console.log(`✅ 代码生成完成: ${toolFileName} (${tool.length} 字符)`);
  if (test) {
    console.log(`✅ 测试生成完成: ${testFileName} (${test.length} 字符)`);
  }

  return {
    toolCode: tool,
    testCode: test,
    toolFileName,
    testFileName
  };
}

/**
 * 将生成的代码写入文件
 */
export async function writeGeneratedCode(
  code: GeneratedCode,
  targetDir: string
): Promise<{ toolPath: string; testPath: string }> {
  const toolPath = path.join(targetDir, code.toolFileName);
  const testPath = path.join(targetDir, code.testFileName);

  await fs.writeFile(toolPath, code.toolCode, 'utf-8');
  console.log(`📄 已写入: ${toolPath}`);

  if (code.testCode) {
    await fs.writeFile(testPath, code.testCode, 'utf-8');
    console.log(`📄 已写入: ${testPath}`);
  }

  return { toolPath, testPath };
}
