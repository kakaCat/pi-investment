import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { MemoryClient } from '@pi-investment/agent-os-client';
import { memoryWritePrompt, type MemoryWriteParams, type MemoryWriteResult } from './prompt';

export class MemoryWriteTool extends BaseTool<MemoryWriteParams, MemoryWriteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'memory_write',
    category: 'memory',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = memoryWritePrompt;

  constructor(private memoryClient: MemoryClient) {
    super();
  }

  protected validate(params: MemoryWriteParams): ValidationResult {
    const { content, importance, namespace } = params;

    // 检查 content 不为空
    if (!content || content.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'content',
        issue: '记忆内容不能为空',
      };
    }

    // 检查 importance 范围
    if (importance !== undefined && (importance < 0 || importance > 1)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'importance',
        issue: `importance 必须在 0-1 之间，当前值: ${importance}`,
      };
    }

    // 检查 namespace 有效性
    const validNamespaces = ['default', 'experience', 'decision', 'analysis'];
    if (namespace && !validNamespaces.includes(namespace)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'namespace',
        issue: `无效的命名空间: ${namespace}`,
        expected: validNamespaces.join(', '),
      };
    }

    return { success: true };
  }

  protected async execute(params: MemoryWriteParams, context: ToolContext): Promise<MemoryWriteResult> {
    const { content, importance = 0.5, namespace = 'default', tags = [] } = params;

    const res = await this.memoryClient.write({
      title: content.slice(0, 50),
      content,
      namespace: namespace === 'experience' ? 'experience' : 'knowledge',
      tags,
      importance,
    });

    return {
      success: true,
      memory_id: String(res?.id ?? ''),
      message: '已写入 Agent OS 记忆库',
    };
  }

  protected wrap(data: MemoryWriteResult, _context: ToolContext): ToolResponse<MemoryWriteResult> {
    return {
      success: true,
      data,
    };
  }
}
