import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { MemoryClient } from '@pi-investment/agent-os-client';
import { memorySearchPrompt, type MemorySearchParams, type MemorySearchResult } from './prompt';

export class MemorySearchTool extends BaseTool<MemorySearchParams, MemorySearchResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'memory_search',
    category: 'memory',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = memorySearchPrompt;

  constructor(private memoryClient: MemoryClient) {
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

    const res = await this.memoryClient.search({
      query,
      top_k,
      // experience 命名空间对应后端 category=experience；其余命名空间不做 category 过滤
      category: namespace === 'experience' ? 'experience' : undefined,
    });

    const items = (res.items || []).map((it: any) => {
      const { embedding, ...rest } = it ?? {};
      return rest;
    });

    return {
      query: String(query ?? ''),
      results: items.map((it: any) => ({
        id: String(it?.id ?? ''),
        title: String(it?.title ?? ''),
        content: String(it?.content ?? ''),
        kind: String(it?.kind ?? ''),
        scope: String(it?.scope ?? ''),
        confidence: typeof it?.confidence === 'number' ? it.confidence : 0,
        created_at: String(it?.created_at ?? ''),
        payload: it?.payload,
      })),
      total: typeof res?.total === 'number' ? res.total : items.length,
      degraded: !!res?.degraded,
      strategy: String(res?.strategy ?? ''),
    };
  }

  protected wrap(data: MemorySearchResult, _context: ToolContext): ToolResponse<MemorySearchResult> {
    return {
      success: true,
      data,
    };
  }
}
