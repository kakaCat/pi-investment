import { BaseTool, ToolResponse, ValidationResult, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { evolutionRunPrompt, type EvolutionRunParams, type EvolutionRunResult } from './prompt';

/** qv2 引擎响应 camelCase → 工具 snake_case 输出归一（RFC 012 P2，仅映射已知键） */
function normalizeRunResult(raw: any): EvolutionRunResult {
  if (!raw || typeof raw !== 'object') return { data_source: 'degraded', degraded_reason: 'qv2 引擎返回空响应' } as any;
  const map: Record<string, string> = {
    runId: 'run_id',
    strategyId: 'strategy_id',
    symbol: 'symbol',
    mode: 'mode',
    klineWindow: 'kline_window',
    dataSource: 'data_source',
    degradedReason: 'degraded_reason',
    totalVariants: 'total_variants',
    successVariants: 'success_variants',
    degradedVariants: 'degraded_variants',
    bestParams: 'best_params',
    bestMetrics: 'best_metrics',
    fitness: 'fitness',
    fitnessImprovement: 'fitness_improvement',
    runAt: 'run_at',
  };
  const out: Record<string, any> = {};
  for (const [k, v] of Object.entries(raw)) {
    out[map[k] ?? k] = v;
  }
  // proposals 项键归一：estimatedFitness → estimated_fitness（params/metrics/rationale 不变）
  if (Array.isArray(out.proposals)) {
    out.proposals = out.proposals.map((p: any) => {
      if (!p || typeof p !== 'object') return p;
      const np: Record<string, any> = {};
      for (const [k, v] of Object.entries(p)) {
        np[k === 'estimatedFitness' ? 'estimated_fitness' : k] = v;
      }
      return np;
    });
  }
  if (out.data_source === 'qv2_real') {
    out.success = out.success ?? true;
  }
  // 引擎 qv2_real run 的 degradedReason=null（实测 2026-09-05）——schema 声明 string，
  // null 触发 dsh 输出校验 "degraded_reason must be a string"。删除 null 键（输出省略合法）。
  if (out.degraded_reason == null) delete out.degraded_reason;
  return out as EvolutionRunResult;
}

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  const m = `${d.getMonth() + 1}`.padStart(2, '0');
  const day = `${d.getDate()}`.padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

function todayISO(): string {
  return isoDaysAgo(0);
}

export class EvolutionRunTool extends BaseTool<EvolutionRunParams, EvolutionRunResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'evolution_run',
    category: 'evolution',
    version: '2.0.0',
    timeoutMs: 180000,
  };

  protected readonly prompt = evolutionRunPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(params: EvolutionRunParams): ValidationResult {
    const { strategy_id, symbol, mode, generations } = params;

    if (strategy_id == null || Number.isNaN(Number(strategy_id)) || Number(strategy_id) <= 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'strategy_id',
        issue: 'strategy_id 必填且必须是正整数（经 strategy_list 获取）',
      };
    }

    if (!symbol || !/^\d{6}$/.test(String(symbol))) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必填且必须是 6 位 A 股代码（如 600519）',
      };
    }

    if (mode && !['full', 'propose'].includes(mode)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'mode',
        issue: 'mode 必须是 full 或 propose',
        expected: 'full | propose',
      };
    }

    if (generations !== undefined && (generations <= 0 || generations > 10)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'generations',
        issue: 'generations 必须在 1-10 之间',
        expected: '1 <= generations <= 10',
      };
    }

    return { success: true };
  }

  protected async execute(params: EvolutionRunParams, context: ToolContext): Promise<EvolutionRunResult> {
    const endDate = params.end_date || todayISO();
    const startDate = params.start_date || isoDaysAgo(365);

    const qv2Result: any = await this.qv2.evolutionRunStrategy({
      strategyId: Number(params.strategy_id),
      symbol: String(params.symbol),
      startDate,
      endDate,
      mode: params.mode || 'propose',
      generations: params.generations ?? 3,
      initialCash: params.initial_cash ?? 1000000,
    });

    return sanitizeLossless(normalizeRunResult(qv2Result)) as EvolutionRunResult;
  }

  protected wrap(data: EvolutionRunResult, context: ToolContext): ToolResponse<EvolutionRunResult> {
    const { mode, proposals, fitness_improvement, data_source, degraded_reason, run_id } = data;

    if (data_source === 'degraded') {
      const message = `进化不可用（data_source=degraded）：${degraded_reason || 'qv2 引擎诚实降级，无真实 fitness 产出'}`;
      return {
        success: true,
        data: { ...data, proposals: [], fitness_improvement: undefined as any },
        message,
        metadata: {
          data_source,
          mode,
          proposal_count: 0,
        },
      };
    }

    let message = `进化完成（data_source=qv2_real）`;

    if (run_id) message += `，批次 ${run_id}`;
    if (proposals && proposals.length > 0) message += `，生成 ${proposals.length} 个改进建议`;
    if (fitness_improvement !== undefined && fitness_improvement !== null) {
      message += `，最优相对 base 提升 ${Number(fitness_improvement).toFixed(2)}%`;
    }

    return {
      success: true,
      data,
      message,
      metadata: {
        data_source,
        mode,
        run_id,
        proposal_count: proposals?.length || 0,
        fitness_improvement,
      },
    };
  }
}
