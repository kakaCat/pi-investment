/**
 * Code Generator - 使用 LLM API 生成工具代码
 *
 * 根据补偿器的建议，使用 LLM API 自动生成完整的 TypeScript 工具实现。
 *
 * 架构说明：
 * - 投资 Agent (DeepSeek): 负责投资决策
 * - 代码生成 (DeepSeek API): 负责代码生成
 * - 职责分离，避免循环依赖
 */

import OpenAI from 'openai';
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
 * 从 Codex 响应中提取代码块
 */
function extractCodeBlocks(text: string): { tool: string; test: string } {
  const codeBlockRegex = /```(?:typescript|ts)?\n([\s\S]*?)```/g;
  const blocks: string[] = [];
  let match;

  while ((match = codeBlockRegex.exec(text)) !== null) {
    blocks.push(match[1].trim());
  }

  // 如果没有找到代码块，尝试直接提取 TypeScript 代码
  if (blocks.length === 0) {
    // 查找 import 语句开始的位置
    const importIndex = text.indexOf('import');
    if (importIndex === -1) {
      throw new Error('未能从 Codex 响应中找到 import 语句');
    }

    // 从 import 开始提取到文件末尾，确保获取完整代码
    const code = text.substring(importIndex).trim();

    // 验证代码包含必需的结构
    if (!code.includes('export const') || !code.includes('Tool')) {
      throw new Error('提取的代码缺少必需的 export 语句');
    }

    blocks.push(code);
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
    // 返回完整文件，确保 Codex 看到完整的结构
    return content;
  } catch {
    return '// 无法读取示例文件';
  }
}

/**
 * 构造 Codex 代码生成提示词
 */
function buildCodeGenPrompt(toolSpec: ToolAddition, exampleCode: string): string {
  return `你是一个 TypeScript 代码生成器。请根据以下规范生成工具代码。

## 工具规范

**名称**: ${toolSpec.name}
**标签**: ${toolSpec.label || toolSpec.name}
**描述**: ${toolSpec.description}

## 代码要求

1. **导入语句**:
   \`\`\`typescript
   import type { ToolDefinition } from "./index.js";
   import { Type } from "@sinclair/typebox";
   \`\`\`

2. **导出常量**: \`export const ${toolSpec.name}Tool: ToolDefinition = { ... }\`

3. **必需字段**:
   - name: "${toolSpec.name}"
   - label: "${toolSpec.label || toolSpec.name}"
   - description: "${toolSpec.description}"
   - parameters: Type.Object({ ... })
   - execute: async (_toolCallId: string, params: any) => { ... }

4. **execute 函数签名**:
   \`\`\`typescript
   execute: async (_toolCallId: string, params: any) => {
     // 实现逻辑
     return {
       content: [{ type: "text" as const, text: "结果文本" }],
       details: { /* 结构化数据 */ }
     };
   }
   \`\`\`

5. **返回格式**: 必须包含 \`content\` 和 \`details\` 两个字段

## 参考示例

\`\`\`typescript
${exampleCode}
\`\`\`

## 输出要求

请生成两个代码块：

**第一个代码块**: 工具实现代码
\`\`\`typescript
// 工具实现代码
\`\`\`

**第二个代码块**: 单元测试代码（使用 Jest）
\`\`\`typescript
import { describe, it, expect } from '@jest/globals';
import { ${toolSpec.name}Tool } from './${toolSpec.name}-tool.js';

describe('${toolSpec.name}Tool', () => {
  it('should execute successfully with valid params', async () => {
    const result = await (${toolSpec.name}Tool.execute as any)('test-id', {
      // 测试参数
    });
    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
  });

  it('should handle invalid params gracefully', async () => {
    const result = await (${toolSpec.name}Tool.execute as any)('test-id', {});
    expect(result.content).toBeDefined();
  });
});
\`\`\`

两个代码块都必须：
- 语法正确，可以直接编译
- 包含所有必需的闭合括号
- 遵循上述规范

不要包含任何解释文字，只输出代码块。`;
}

/**
 * 使用 Codex (GPT-5.4) 生成工具代码
 */
export async function generateToolCode(toolSpec: ToolAddition): Promise<GeneratedCode> {
  console.log(`🤖 正在使用 Codex 生成工具代码: ${toolSpec.name}`);

  const exampleCode = await getToolExamples();
  const prompt = buildCodeGenPrompt(toolSpec, exampleCode);

  // 使用临时文件传递 prompt，避免 shell 解析问题
  const tmpDir = '/tmp';
  const promptFile = path.join(tmpDir, `codex-prompt-${Date.now()}.txt`);

  try {
    // 写入 prompt 到临时文件
    await fs.writeFile(promptFile, prompt, 'utf-8');
    console.log(`  📡 调用 Codex...`);

    const { exec } = await import('child_process');
    const { promisify } = await import('util');
    const execAsync = promisify(exec);

    // 使用文件重定向而不是 echo
    const { stdout } = await execAsync(
      `codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral -C ${process.cwd()} < ${promptFile}`,
      {
        maxBuffer: 10 * 1024 * 1024,
        timeout: 120000
      }
    );

    // 提取 Codex 输出的代码部分
    const codexMarker = '\ncodex\n';
    const tokensMarker = '\ntokens used\n';

    let output = stdout;
    const codexIndex = output.lastIndexOf(codexMarker);
    if (codexIndex !== -1) {
      output = output.substring(codexIndex + codexMarker.length);
      const tokensIndex = output.indexOf(tokensMarker);
      if (tokensIndex !== -1) {
        output = output.substring(0, tokensIndex);
      }
    }

    output = output.trim();

    if (!output || output.length === 0) {
      throw new Error('Codex 返回空响应');
    }

    console.log(`  📝 Codex 代码长度: ${output.length} 字符`);

    // 提取代码块
    const { tool, test } = extractCodeBlocks(output);

    const toolFileName = `${toolSpec.name}-tool.ts`;
    const testFileName = `${toolSpec.name}-tool.test.ts`;

    console.log(`  ✅ 代码生成完成: ${toolFileName} (${tool.length} 字符)`);
    if (test) {
      console.log(`  ✅ 测试生成完成: ${testFileName} (${test.length} 字符)`);
    }

    return {
      toolCode: tool,
      testCode: test,
      toolFileName,
      testFileName
    };
  } catch (error: any) {
    console.error(`  ❌ Codex 调用失败:`, error.message);
    throw new Error(`Codex 代码生成失败: ${error.message}`);
  } finally {
    // 清理临时文件
    try {
      await fs.unlink(promptFile);
    } catch {
      // 忽略清理失败
    }
  }
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
