import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { memorySearchPrompt, type MemorySearchParams, type MemorySearchResult } from './prompt';

export class MemorySearchTool extends BaseTool<MemorySearchParams, MemorySearchResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'memory_search',
    category: 'memory',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = memorySearchPrompt;

  constructor(private osMemory: OsMemoryStore) {
    super();
  }

  protected validate(params: MemorySearchParams): ValidationResult {
    const { query, top_k, namespace } = params;

    // 检查 query 不为空
    if (!query || query.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'query',
        issue: '搜索内容不能为空',
      };
    }

    // 检查 top_k 范围
    if (top_k !== undefined && (top_k < 1 || top_k > 50)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'top_k',
        issue: `top_k 必须在 1-50 之间，当前值: ${top_k}`,
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

  protected async execute(params: MemorySearchParams, context: ToolContext): Promise<MemorySearchResult> {
    const { query, top_k = 5, namespace = 'default' } = params;

    const res = await this.osMemory.searchMemory({
      q: query,
      limit: top_k,
      // experience 命名空间对应后端 kind=experience；其余命名空间不做 kind 过滤
      kind: namespace === 'experience' ? 'experience' : undefined,
    });

    // embedding 向量为千维数组，剔除以避免污染上下文
    const items = (res.items || []).map((it: any) => {
      const { embedding, ...rest } = it ?? {};
      return rest;
    });

    return {
      query,
      results: items,
      total: res.total ?? items.length,
      degraded: res.degraded,
      strategy: res.strategy,
    };
  }

  protected wrap(data: MemorySearchResult, _context: ToolContext): ToolResponse<MemorySearchResult> {
    return {
      success: true,
      data,
    };
  }
}
