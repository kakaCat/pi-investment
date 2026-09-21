import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { MemoryClient } from '@pi-investment/agent-os-client';
import { memorySearchPrompt, type MemorySearchParams, type MemorySearchResult } from './prompt';

export class MemorySearchTool extends BaseTool<MemorySearchParams, MemorySearchResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'memory_search',
    category: 'memory',
    version: '1.0.0',
    timeoutMs: 25000, // 2026-09-11：放宽召回可能触发多次检索
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
    const category = namespace === 'experience' ? 'experience' : undefined;

    // 2026-09-11（REQ-342799 P2 续）：后端检索是**整串 ILIKE 子串匹配**
    //（agent-os/internal/repository/memory_repository.go:229 注释自述 'For now, use simple ILIKE search'，
    //  238 行 content ILIKE '%query%'），因此多词/自然语言查询必然 0 命中：
    //    『业绩归因』→ 3 命中；『业绩归因 超额 beta alpha』→ 0 命中；『这次修复的信号账本假数据问题是什么』→ 0 命中。
    // 后果：R-008『决策前检索历史教训』会拿到"无历史"的假结论。此处在工具层做**逐级放宽重试**：
    // 原查询 → 关键词逐个 → CJK 长词片段；命中即止，并在结果里标注 query_relaxed，避免把降级召回冒充精确召回。
    const call = async (q: string) => {
      const r: any = await this.memoryClient.search({ query: q, top_k, category });
      const raw = (r?.memories ?? r?.items ?? []) as any[];
      return { r, items: raw.map((it: any) => { const { embedding, ...rest } = it ?? {}; return rest; }) };
    };

    let { r: res, items } = await call(query);
    let relaxedQuery: string | null = null;
    const attempts: string[] = [];

    if (items.length === 0) {
      for (const cand of this.buildRelaxedQueries(query)) {
        if (attempts.length >= 20) break;
        attempts.push(cand);
        try {
          const next = await call(cand);
          if (next.items.length > 0) {
            res = next.r;
            items = next.items;
            relaxedQuery = cand;
            break;
          }
        } catch { /* 单个候选失败不影响主流程 */ }
      }
    }

    // 字段契约（2026-08-31 修复保留）：Agent OS 返回 { memories: [...] }，兼容 items；
    // embedding 字段剔除后再返回（体积大且无用于分析）。该解析已收敛进上面的 call() helper。
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
      query_relaxed: relaxedQuery,
      relax_note: relaxedQuery
        ? '原查询零命中，已放宽为「' + relaxedQuery + '」后命中；结果可能不完整，勿当作精确召回'
        : (attempts.length && items.length === 0
          ? '原查询与 ' + attempts.length + ' 个放宽候选均零命中（后端为整串子串匹配），本次确无相关历史'
          : '原查询命中'),
      relax_attempts: attempts,
    };
  }

  /**
   * 生成逐级放宽的候选查询（2026-09-11，REQ-342799）：针对后端整串 ILIKE 的局限。
   * 顺序：①空格/标点切分后的关键词（去停用词，长者优先）②CJK 长串去停用字符后的连续片段（长者优先，取前几个）。
   */
  private buildRelaxedQueries(query: string): string[] {
    const stop = new Set([
      '的','了','是','在','和','与','有','我','你','他','这','那','什么','怎么','如何','为什么','吗','呢','请','一下',
      '已经','今天','可以','需要','问题','是否','以及','我们','他们','这个','那个','还是','就是','没有','一个',
      'the','a','an','is','are','to','of','and','or','for','what','how','this','that',
    ]);
    const out: string[] = [];
    const tokens = String(query)
      .split(/[\s,，。、;；:：!！?？()（）\[\]【】"'`]+/)
      .map((t) => t.trim())
      .filter((t) => t.length >= 2 && !stop.has(t.toLowerCase()));
    // 长者优先：更长的词信息量更大、误命中更少
    for (const t of [...tokens].sort((a, b) => b.length - a.length)) {
      if (!out.includes(t)) out.push(t);
    }
    // CJK 长句：不能只取前缀（关键词常在句中）。做法——去掉停用字符后，对整串做 n-gram 切片，
    // 长者优先（精度高）：5-gram → 4-gram → 3-gram。
    const compact = String(query)
      .split('')
      .filter((ch) => !/\s/.test(ch) && !stop.has(ch))
      .join('');
    // 按『位置优先、多粒度交错』遍历：若先把所有 5-gram 排完，预算会被耗尽、
    // 永远轮不到句中真正存在的 4-gram 短语（实测踩过：'业绩归因' 在位置 5，被 12 次尝试全部浪费在前缀 5-gram 上）。
    for (let i = 0; i < compact.length; i++) {
      for (const len of [5, 4, 3]) {
        if (i + len > compact.length) continue;
        const gram = compact.slice(i, i + len);
        if (gram && !out.includes(gram)) out.push(gram);
      }
    }
    return out.slice(0, 30);
  }
  protected wrap(data: MemorySearchResult, _context: ToolContext): ToolResponse<MemorySearchResult> {
    return {
      success: true,
      data,
    };
  }
}
